# kiosk.py
import tkinter as tk
import socket, time, sys, os, subprocess, traceback, pygame, ctypes # type: ignore
from networking import KioskNetwork
from ui import KioskUI
from config import ROOM_CONFIG
from video_server import VideoServer
from video_manager import VideoManager
from audio_server import AudioServer
from message_handler import MessageHandler
from pathlib import Path
from room_persistence import RoomPersistence
from kiosk_timer import KioskTimer
from audio_manager import AudioManager
from kiosk_file_downloader import KioskFileDownloader
from qt_overlay import Overlay
from ctypes import windll
import signal

class KioskApp:
    def __init__(self):
        print("[kiosk main]Starting KioskApp initialization...")
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

        #get_stats items to pass with info payload
        self.computer_name = socket.gethostname()
        self.hint_requested_flag = False
        self.auto_start = False
        self.hints_requested = 0
        self.hints_received = 0
        self.assigned_room = None
        self.times_touched_screen = 0
        self.is_closing = False

        self.root = tk.Tk()
        #self.root.title(f"Kiosk App: {self.computer_name}")\
        self.root.title(f"Kiosk App")

        # Handle icon setting
        myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        try:
            # Construct the absolute path to the icon file
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")  # Assuming icon.ico is in the same directory

            self.root.iconbitmap(default=icon_path)  # Use -default for .ico with multiple sizes

        except tk.TclError as e:
            print(f"[kiosk main]Error loading icon: {e}")  # Handle icon loading erro
        
        # Add fullscreen and cursor control
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="none")  # Hide cursor
        #self.root.bind('<Escape>', lambda e: self.toggle_fullscreen())

        # Set kiosk_app reference on root window BEFORE creating UI
        self.root.kiosk_app = self
        
        self.start_time = None
        self.room_started = False
        self.current_video_process = None
        self.time_exceeded_45 = False
        #print("[kiosk main]Initialized time_exceeded_45 flag to False")
        self.audio_manager = AudioManager(self)  # Pass the KioskApp instance
        self.video_manager = VideoManager(self.root) # Initialize video manager
        self.message_handler = MessageHandler(self, self.video_manager)
        
        # Initialize components as before
        self.network = KioskNetwork(self.computer_name, self)
        self.video_server = VideoServer()
        print("[kiosk main]Starting video server...")
        self.video_server.start()
        
        from kiosk_timer import KioskTimer
        self.timer = KioskTimer(self.root, self)  # Pass self
        self.timer.game_won = False 
        
        # Create UI after setting kiosk_app reference
        self.ui = KioskUI(self.root, self.computer_name, ROOM_CONFIG, self)
        self.ui.setup_waiting_screen()
        self.network.start_threads()
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.audio_server = AudioServer()
        print("[kiosk main]Starting audio server...")
        self.audio_server.start()

        print(f"[kiosk main]Computer name: {self.computer_name}")
        print("[kiosk main]Creating RoomPersistence...")
        self.room_persistence = RoomPersistence()
        #print("[kiosk main]Loading saved room...")
        self.assigned_room = self.room_persistence.load_room_assignment()
        print(f"[kiosk main]Loaded room assignment: {self.assigned_room}")

        #Initialize the file downloader
        self.file_downloader = KioskFileDownloader(self)
        self.file_downloader.start() # Start it immediately
        
        # Initialize UI with saved room if available
        if self.assigned_room:
            self.root.after(100, lambda: self.ui.setup_room_interface(self.assigned_room))
        else:
            self.ui.setup_waiting_screen()

    def _actual_help_button_update(self):
        """Check timer and update help button state"""
        try:
            Overlay.update_help_button(self.ui, self.timer, self.hints_requested, self.time_exceeded_45, self.assigned_room)
        except Exception as e:
            traceback.print_exc()

    def toggle_fullscreen(self):
        """Development helper to toggle fullscreen"""
        is_fullscreen = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not is_fullscreen)
        if is_fullscreen:
            self.root.config(cursor="")
        else:
            self.root.config(cursor="none")

    def get_stats(self):
        if self.is_closing:
            print("[kiosk get_stats] Prevented stats update and screenshot: Kiosk is closing.")
            return {} # Return empty dict to avoid issues if stats are expected
        stats = {
            'computer_name': self.computer_name,
            'room': self.assigned_room,
            'total_hints': self.hints_requested,
            'timer_time': self.timer.time_remaining,
            'timer_running': self.timer.is_running,
            'hint_requested': self.hint_requested_flag, # Include the new hint flag in the stats
            'hints_received': self.hints_received,
            'times_touched_screen': self.times_touched_screen,
            'music_playing': self.audio_manager.is_playing if hasattr(self.audio_manager, 'is_playing') else False,
            'auto_start': self.auto_start,
            
        }
        # Only log if stats have changed from last time
        if not hasattr(self, '_last_stats') or self._last_stats != stats:
            #print(f"[kiosk main]Stats updated: {stats}")
            self._last_stats = stats.copy()

        # --- Add screenshot logic HERE ---
        if hasattr(self, 'take_screenshot_requested') and self.take_screenshot_requested:
            self.send_screenshot()
            self.take_screenshot_requested = False  # Reset flag after sending

        return stats
    
    def send_screenshot(self):
        """Takes and sends a screenshot to the admin."""
        if self.is_closing:
            print("[kiosk]Screenshot send prevented: Kiosk is closing.")
            return
        #else:
            #print(f"[kiosk] is_closing = {self.is_closing}")
        try:
            from PIL import ImageGrab, Image
            import io, base64

            # Take screenshot
            screen = ImageGrab.grab()

            # Resize and rotate, fitting to admin interface
            max_height = 300  # Example, adjust as needed based on your UI
            screen = screen.rotate(90, expand=True)
            ratio = max_height / screen.height
            new_width = int(screen.width * ratio)
            screen = screen.resize((new_width, max_height), Image.Resampling.LANCZOS)

            # Convert to JPEG and base64
            buf = io.BytesIO()
            screen.save(buf, format='JPEG', quality=30)  # Much lower quality
            image_data = base64.b64encode(buf.getvalue()).decode()

            # Send message
            self.network.send_message({
                'type': 'screenshot',
                'computer_name': self.computer_name,
                'image_data': image_data
            })
            #print(f"[kiosk]Screenshot sent ({len(image_data)} bytes)")

        except Exception as e:
            print(f"[kiosk]Error taking/sending screenshot: {e}")
            traceback.print_exc()
        
    def handle_message(self, msg):
        self.message_handler.handle_message(msg)
    
    def handle_game_loss(self):
        """Handles the game loss event."""
        print("[kiosk app]Handling game loss...")

        # Stop all audio/video (you already have this logic, keep it):
        #self.audio_manager.stop_all_audio() redundant as timer already does this
        self.video_manager.force_stop()  # Ensure video is stopped

        # Hide all other UI elements and show loss screen:
        self.root.after(0, lambda: Overlay._check_game_loss_visibility(True))

    def handle_game_win(self):
        """Handles the game win event"""
        print("[Kiosk app] Handling game win...")

        #Stop all audio and video
        self.audio_manager.stop_all_audio()
        self.video_manager.force_stop()

        # Hide all other UI elements and show the victory screen using qt_overlay
        self.root.after(0, lambda: Overlay._check_game_win_visibility(True))

    def request_help(self):
        if not self.ui.hint_cooldown:
            self.hints_requested += 1
            Overlay.hide_help_button()

            # Set help requested flag to TRUE
            self.hint_requested_flag = True
            print(f"[Kiosk] request_help: Setting hint_requested_flag to True")
            
            # Use PyQt overlay for "Hint Requested" message
            Overlay.show_hint_request_text()
            
            self.network.send_message({
                'type': 'help_request',
                **self.get_stats()
            })

    def show_hint(self, text, start_cooldown=True):
        # Clear any pending request status
        Overlay.hide_hint_request_text()
        
        # Play the hint received sound
        self.audio_manager.play_sound("hint_received.mp3")
        
        # Show the hint
        self.ui.show_hint(text, start_cooldown)
        
        # Start cooldown timer
        self.ui.start_cooldown()

    def play_video(self, video_type, minutes):
        print(f"[kiosk main]=== Video Playback Sequence Start ===")
        print(f"[kiosk main]Starting play_video with type: {video_type}")
        print(f"[kiosk main]Current room assignment: {self.assigned_room}")
        
        # Define video paths upfront
        video_dir = Path("intro_videos")
        video_file = video_dir / f"{video_type}.mp4" if video_type != 'game' else None
        game_video = None
        
        # Get room-specific game video name from config if room is assigned
        if self.assigned_room is not None and self.assigned_room in ROOM_CONFIG['backgrounds']:
            game_video_name = ROOM_CONFIG['backgrounds'][self.assigned_room].replace('.png', '.mp4')
            game_video = video_dir / game_video_name
            print(f"[kiosk main]Found room-specific game video path: {game_video}")
            print(f"[kiosk main]Game video exists? {game_video.exists() if game_video else False}")

        def finish_video_sequence():
            """Final callback after all videos are complete"""
            print("[kiosk main]=== Video Sequence Completion ===")
            print("[kiosk main]Executing finish_video_sequence callback")
            print(f"[kiosk main]Setting timer to {minutes} minutes")
            
            # Send admin notification - before timer starts
            self.network.send_message({
                'type': 'intro_video_completed',
                'computer_name': self.computer_name
            })

            if (self.auto_start == True):
                print("[kiosk main]Autostart was on, game will typically be started by this. \n Setting auto_start to false.")
                self.auto_start = False
                print(f"and autostart = {self.auto_start}")
            
            self.timer.handle_command("set", minutes)
            self.timer.handle_command("start")
            
            # Start playing background music for the assigned room
            if self.assigned_room:
                print(f"[kiosk main]Starting background music for room: {self.assigned_room}")
                self.audio_manager.play_background_music(self.assigned_room)
            
            print("[kiosk main]Resetting UI state...")
            self.ui.hint_cooldown = False

            # Clear hint if it's empty before restoring UI
            if self.ui.current_hint is not None:
                hint_text = self.ui.current_hint if isinstance(self.ui.current_hint, str) else self.ui.current_hint.get('text', '')
                if hint_text is None or hint_text.strip() == "":
                    print("[kiosk main]Clearing empty hint before setup_room_interface")
                    self.ui.current_hint = None  # Explicitly clear the hint
                    Overlay.hide_hint_text() # Hide the hint.
                    

            self.ui.clear_all_labels() # moved this BELOW the new IF statement.
            if self.assigned_room:
                print(f"[kiosk main]Restoring room interface for: {self.assigned_room}")
                self.ui.setup_room_interface(self.assigned_room)
                if not self.ui.hint_cooldown:
                    print("[kiosk main]Creating help button")
                    Overlay.update_help_button(self.ui, self.timer, self.hints_requested, self.time_exceeded_45, self.assigned_room)
            print("[kiosk main]=== Video Sequence Complete ===\n")
        def play_game_video():
            """Helper to play game video if it exists"""
            print("[kiosk main]=== Starting Game Video Sequence ===")
            print(f"[kiosk main]Game video path: {game_video}")
            if game_video and game_video.exists():
                print(f"[kiosk main]Starting playback of game video: {game_video}")
                print("[kiosk main]Setting up completion callback to finish_video_sequence")
                self.video_manager.play_video(str(game_video), on_complete=finish_video_sequence)
            else:
                print("[kiosk main]No valid game video found, proceeding to finish sequence")
                print(f"[kiosk main]Game video exists? {game_video.exists() if game_video else False}")
                finish_video_sequence()
            print("[kiosk main]=== Game Video Sequence Initiated ===\n")

        # Play video based on type
        if video_type != 'game':
            print("[kiosk main]=== Starting Intro Video Sequence ===")
            if video_file.exists():
                print(f"[kiosk main]Found intro video at: {video_file}")
                print("[kiosk main]Setting up completion callback to play_game_video")
                self.video_manager.play_video(str(video_file), on_complete=play_game_video)
            else:
                print(f"[kiosk main]Intro video not found at: {video_file}")
                print("[kiosk main]Skipping to game video")
                play_game_video()  # Skip to game video if intro doesn't exist
        else:
            print("[kiosk main]=== Skipping Intro, Playing Game Video ===")
            play_game_video()
        
    def on_closing(self):
        print("[kiosk main]Shutting down kiosk...")
        #self.is_closing = True
        if self.current_video_process:
            self.current_video_process.terminate()
        self.network.shutdown()
        self.video_server.stop()
        self.audio_server.stop()
        self.file_downloader.stop()

        if hasattr(self, 'take_screenshot_requested'):
            self.take_screenshot_requested = False
        
        self.root.destroy()
        #sys.exit(0)


    def clear_hints(self):
        """Clears all visible hints and resets hint-related state."""
        print("[kiosk main] Clearing hints (delegated approach)")

        # 1. Reset KioskApp's internal state.  This is the *source of truth*.
        self.ui.hint_cooldown = False
        self.ui.current_hint = None
        self.ui.stored_image_data = None
        if self.ui.cooldown_after_id:
            self.root.after_cancel(self.ui.cooldown_after_id)
            self.ui.cooldown_after_id = None

        # 2. Issue commands to the UI handlers.
        self.ui.clear_hint_ui()  # Command to ui.py to handle Tkinter cleanup
        print("[kiosk main.clear_hints] 1")
        Overlay.hide_hint_text() # Command to qt_overlay.py
        print("[kiosk main.clear_hints] 2")
        Overlay.hide_hint_request_text()  # Hide any pending request
        print("[kiosk main.clear_hints] 3")
        Overlay.hide_cooldown() # Hide Cooldown
        print("[kiosk main.clear_hints] 4")
        self._actual_help_button_update() # Update help button (which checks state)
        print("[kiosk main.clear_hints] 5")

    def signal_handler(self, sig, frame):
        print(f"[kiosk main]Signal {sig} received. Setting is_closing = True immediately.")
        self.is_closing = True
        self.root.after(0, self.on_closing) # Call on_closing in main thread

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler) # REGISTER SIGNAL HANDLER HERE
        try:
            self.root.mainloop()
        except KeyboardInterrupt: # Keep this for cleanup in case signal handler fails
            print("[kiosk main]KeyboardInterrupt detected in mainloop (fallback).")
            self.on_closing() # Explicitly call on_closing on Ctrl+C
            print("[kiosk main]Kiosk shutdown initiated.")

if __name__ == '__main__':
    app = KioskApp()
    try:
        app.run()
    except Exception as e: # Catch any other errors during startup too
        print(f"[kiosk main]Unhandled exception during startup/runtime: {e}")
        traceback.print_exc()
    finally: # Ensure cleanup even if startup fails badly
        print("[kiosk main]Ensuring kiosk cleanup after main loop (or error).")
        # if hasattr(app, 'on_closing'): # Check if app and on_closing exist to avoid errors if init failed
        #     app.on_closing()
        # else:
        #     print("[kiosk main]App or on_closing not properly initialized, basic cleanup only.")
        sys.exit(1) # Indicate error exit if on_closing couldn't run