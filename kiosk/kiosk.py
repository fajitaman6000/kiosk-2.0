# kiosk.py
print("[kiosk main] Beginning imports ...", flush=True)
# import tkinter as tk - removed
print("[kiosk main] Importing socket, sys, os, traceback, ctypes...", flush=True)
import socket, sys, os, traceback, ctypes, json # type: ignore
print("[kiosk main] Imported socket, sys, os, traceback, ctypes.", flush=True)
print("[kiosk main] Importing KioskNetwork from networking...", flush=True)
from networking import KioskNetwork
print("[kiosk main] Imported KioskNetwork from networking.", flush=True)
print("[kiosk main] Importing QtManager from qt_manager...", flush=True)
from qt_manager import QtManager
print("[kiosk main] Imported QtManager from qt_manager.", flush=True)
print("[kiosk main] Importing ROOM_CONFIG from config...", flush=True)
from config import ROOM_CONFIG
print("[kiosk main] Imported ROOM_CONFIG from config.", flush=True)
print("[kiosk main] Importing VideoServer from video_server...", flush=True)
from video_server import VideoServer
print("[kiosk main] Imported VideoServer from video_server.", flush=True)

print("[kiosk main] Importing StateTracker...", flush=True)
from state_tracker import StateTracker
print("[kiosk main] Imported StateTracker.", flush=True)

print("[kiosk main] Importing VideoManager from video_manager...", flush=True)
from video_manager import VideoManager
print("[kiosk main] Imported VideoManager from video_manager.", flush=True)
print("[kiosk main] Importing AudioServer from audio_server...", flush=True)
from audio_server import AudioServer
print("[kiosk main] Imported AudioServer from audio_server.", flush=True)
print("[kiosk main] Importing MessageHandler, init_timer_scheduler from message_handler...", flush=True)
from message_handler import MessageHandler, init_timer_scheduler
print("[kiosk main] Imported MessageHandler, init_timer_scheduler from message_handler.", flush=True)
print("[kiosk main] Importing Path from pathlib...", flush=True)
from pathlib import Path
print("[kiosk main] Imported Path from pathlib.", flush=True)
print("[kiosk main] Importing RoomPersistence from room_persistence...", flush=True)
from room_persistence import RoomPersistence
print("[kiosk main] Imported RoomPersistence from room_persistence.", flush=True)
print("[kiosk main] Importing KioskTimer from kiosk_timer...", flush=True)
from kiosk_timer import KioskTimer
print("[kiosk main] Imported KioskTimer from kiosk_timer.", flush=True)
print("[kiosk main] Importing AudioManager from audio_manager...", flush=True)
from audio_manager import AudioManager
print("[kiosk main] Imported AudioManager from audio_manager.", flush=True)
print("[kiosk main] Importing KioskFileDownloader from kiosk_file_downloader...", flush=True)
from kiosk_file_downloader import KioskFileDownloader
print("[kiosk main] Imported KioskFileDownloader from kiosk_file_downloader.", flush=True)
print("[kiosk main] Importing Overlay from qt_overlay...", flush=True)
from qt_overlay import Overlay
print("[kiosk main] Imported Overlay from qt_overlay.", flush=True)
print("[kiosk main] Importing QtKioskApp from qt_main...", flush=True)
from qt_main import QtKioskApp  # Import the new QtKioskApp class
print("[kiosk main] Imported QtKioskApp from qt_main.", flush=True)
print("[kiosk main] Importing init_logging, log_exception from logger...", flush=True)
from logger import init_logging, log_exception  # Import our new logger
print("[kiosk main] Imported init_logging, log_exception from logger.", flush=True)
print("[kiosk main] Importing windll from ctypes...", flush=True)
from ctypes import windll
print("[kiosk main] Imported windll from ctypes.", flush=True)
print("[kiosk main] Importing signal...", flush=True)
import signal
print("[kiosk main] Imported signal.", flush=True)
print("[kiosk main] Importing threading...", flush=True)
import threading
print("[kiosk main] Imported threading.", flush=True)
print("[kiosk main] Importing time...", flush=True)
import time
print("[kiosk main] Imported time.", flush=True)
print("[kiosk main] Importing PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import QMetaObject, Qt, QTimer, Q_ARG
print("[kiosk main] Imported PyQt5.QtCore.", flush=True)
print("[kiosk main] Importing screen_rotation_manager...", flush=True)
try:
    from screen_rotation_manager import rotate_to_preferred_landscape
    print("[kiosk main] Imported screen_rotation_manager.", flush=True)
except ImportError:
    print("[kiosk main] WARNING: Could not import screen_rotation_manager.py. Screen rotation will be skipped.", flush=True)
    rotate_to_preferred_landscape = None
print("[kiosk main] Importing TapDetector from tap_detector...", flush=True)
try:
    from tap_detector import TapDetector
    TAP_DETECTOR_ENABLED = True
except Exception as e:
    print(f"[kiosk main] WARNING: Could not import or use TapDetector. Secret tap pattern will be disabled. Error: {e}", flush=True)
    TapDetector = None
    TAP_DETECTOR_ENABLED = False
print("[kiosk main] Tap Detector", flush=True)
print("[kiosk main] Ending imports ...", flush=True)

class KioskApp:
    UI_DEBUG = False
    def __init__(self):
        print("[kiosk main]Starting KioskApp initialization...", flush=True)
        os.chdir(os.path.dirname(os.path.abspath(__file__)))
        
        # Initialize logging
        print("[kiosk main] Initializing logging...", flush=True)
        self.logger = init_logging()
        print("[kiosk main] Console logging initialized.", flush=True)

        # --- Apply Screen Rotation Preference ---
        # Do this after logging is set up, but before the main Qt app is created.
        # The Qt app might read display configuration when created.
        if rotate_to_preferred_landscape: # Check if the import was successful
            print("[kiosk main] Applying screen rotation preference...", flush=True)
            try:
                rotate_to_preferred_landscape()
            except Exception as e:
                 # This catch is mostly for unexpected errors *during* the function call,
                 # as the function itself has internal catches.
                 print(f"[kiosk main] ERROR during screen rotation function call: {e}", flush=True)
            print("[kiosk main] Screen rotation check complete.", flush=True)
        else:
             print("[kiosk main] Skipping screen rotation as manager was not imported.", flush=True)
        # --- End Screen Rotation Logic ---

        #get_stats items to pass with info payload
        self.computer_name = socket.gethostname()
        self.hint_requested_flag = False
        self.auto_start = False
        self.hints_requested = 0
        self.hints_received = 0
        self.assigned_room = None
        self.times_touched_screen = 0
        self.is_closing = False
        self.needs_restart = False
        self.start_time = None
        self.take_screenshot_requested = False
        self.time_exceeded_45 = False
        self.room_started = False
        # Volume levels (0-10 integer representation)
        self.music_volume_level = 7  # Default 7/10 (70%)
        self.hint_volume_level = 7   # Default 7/10 (70%)

        # Create Qt application first, before any other component
        print("[kiosk main] Creating Qt application...", flush=True)
        self.qt_app = QtKioskApp(self)
        print("[kiosk main] Qt application created.", flush=True)

        print("[kiosk main] Setting up proactive state saving timer...", flush=True)
        self.state_save_timer = QTimer()
        self.state_save_timer.timeout.connect(self.save_state_periodically)
        # Save state every 10 seconds. Adjust as needed.
        self.state_save_timer.start(10000)
        print("[kiosk main] State saving timer started.", flush=True)
        
        # Set the proper application ID for Windows taskbar grouping
        # This should be a registered application identifier for your app
        print("[kiosk main] Setting Windows application ID...", flush=True)
        myappid = 'EscapeRoomKiosk.App.2.0'  # Use a consistent, specific app ID
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
            print("[kiosk main] Windows application ID set successfully.", flush=True)
        except Exception as e:
            print(f"[kiosk main] Failed to set app ID: {str(e)}", flush=True)

        # Initialize Qt overlay with explicit reference to the QApplication instance
        # We'll modify the Overlay.init method to accept a reference to the Qt application
        print("[kiosk main] Setting up Qt overlay...", flush=True)
        Overlay._app = self.qt_app  # Set the app reference directly
        Overlay.init()
        
        # Set the kiosk_app reference directly
        Overlay.set_kiosk_app(self)
        print("[kiosk main] Qt overlay initialized.", flush=True)
        
        # Now initialize other components
        self.current_video_process = None
        print("[kiosk main] Initializing AudioManager...", flush=True)
        self.audio_manager = AudioManager(self)  # Pass the KioskApp instance
        print("[kiosk main] AudioManager initialized.", flush=True)
        
        print("[kiosk main] Initializing VideoManager...", flush=True)
        self.video_manager = VideoManager(None)  # No longer need to pass root
        print("[kiosk main] VideoManager initialized.", flush=True)
        
        print("[kiosk main] Initializing MessageHandler...", flush=True)
        self.message_handler = MessageHandler(self, self.video_manager)
        print("[kiosk main] MessageHandler initialized.", flush=True)
        
        # Initialize components as before
        print("[kiosk main] Initializing KioskNetwork...", flush=True)
        self.network = KioskNetwork(self.computer_name, self)
        print("[kiosk main] KioskNetwork initialized.", flush=True)
        
        print("[kiosk main] Initializing VideoServer...", flush=True)
        self.video_server = VideoServer()
        print("[kiosk main] Starting video server...", flush=True)
        self.video_server.start()
        print("[kiosk main] VideoServer started.", flush=True)
        
        print("[kiosk main] Initializing KioskTimer...", flush=True)
        self.timer = KioskTimer(None, self)  # Pass self but no longer need root
        self.timer.game_won = False
        print("[kiosk main] KioskTimer initialized.", flush=True)
        
        # Create UI manager with QtManager instead of KioskUI
        print("[kiosk main] Initializing QtManager...", flush=True)
        self.ui = QtManager(self.computer_name, ROOM_CONFIG, self)
        self.ui.setup_waiting_screen()
        self.ui.current_hint_image_filename = None
        print("[kiosk main] QtManager initialized.", flush=True)
        
        print("[kiosk main] Starting network threads...", flush=True)
        self.network.start_threads()
        print("[kiosk main] Network threads started.", flush=True)

        print("[kiosk main] Initializing AudioServer...", flush=True)
        self.audio_server = AudioServer()
        print("[kiosk main] Starting audio server...", flush=True)
        self.audio_server.start()
        print("[kiosk main] AudioServer started.", flush=True)

        print(f"[kiosk main] Computer name: {self.computer_name}", flush=True)
        print("[kiosk main] Creating RoomPersistence...", flush=True)
        self.room_persistence = RoomPersistence()
        self.assigned_room = self.room_persistence.load_room_assignment()
        print(f"[kiosk main] Loaded room assignment: {self.assigned_room}", flush=True)

        #Initialize the file downloader
        print("[kiosk main] Initializing KioskFileDownloader...", flush=True)
        self.file_downloader = KioskFileDownloader(self)
        self.file_downloader.start() # Start it immediately
        print("[kiosk main] KioskFileDownloader started.", flush=True)
        
        # Initialize UI with saved room if available
        if self.assigned_room:
            print(f"[kiosk main] Setting up room interface for room {self.assigned_room}...", flush=True)
            # Use QTimer.singleShot instead of root.after
            QTimer.singleShot(100, lambda: self.ui.setup_room_interface(self.assigned_room))
        else:
            print("[kiosk main] Setting up waiting screen...", flush=True)
            self.ui.setup_waiting_screen()

        # Create a timer for the help button update
        print("[kiosk main] Setting up help button update timer...", flush=True)
        self.help_button_timer = QTimer()
        self.help_button_timer.timeout.connect(self._actual_help_button_update)
        self.help_button_timer.start(5000)
        print("[kiosk main] Help button update timer started.", flush=True)
        
        print("[kiosk main] Initializing StateTracker...", flush=True)
        self.state_tracker = StateTracker(self) # Pass self (the KioskApp instance)
        self.state_tracker.start()
        print("[kiosk main] StateTracker started.", flush=True)

        print("[kiosk main] Initializing heartbeat thread...", flush=True)
        self.heartbeat_stop_event = threading.Event()
        self.heartbeat_thread = threading.Thread(target=self._send_heartbeats, daemon=True)
        self.heartbeat_thread.start()
        print("[kiosk main] Heartbeat thread started.", flush=True)
        
        # Volume levels (0-10 integer representation)
        self.music_volume_level = 7  # Default 7/10 (70%)
        self.hint_volume_level = 7   # Default 7/10 (70%)

        # Init tap detector for reset commands
        self.tap_detector = None
        if TAP_DETECTOR_ENABLED and TapDetector:
            print("[kiosk main] Initializing TapDetector...", flush=True)
            try:
                # Pass a method from this class as the callback
                self.tap_detector = TapDetector(pattern_callback=self.on_tap_pattern_detected)
                self.tap_detector.start()
                print("[kiosk main] TapDetector started.", flush=True)
            except Exception as e:
                print(f"[kiosk main] ERROR: Failed to start TapDetector: {e}", flush=True)
                self.tap_detector = None # Ensure it's None on failure
        
        print("[kiosk main] KioskApp initialization complete.", flush=True)

    def on_tap_pattern_detected(self):
        """
        Callback function executed by the TapDetector when the secret pattern is detected.
        """
        print("[kiosk main] Secret tap pattern detected! Relaying to message handler.", flush=True)
        if hasattr(self, 'message_handler'):
            # The tap detector callback runs in its own thread.
            # We use the message_handler's scheduler to safely call the final
            # function on the main Qt thread.
            self.message_handler.schedule_timer(0, self.message_handler.handle_tap_pattern_detected)
        else:
            print("[kiosk main] ERROR: message_handler not found, cannot process tap pattern.", flush=True)

    def _actual_help_button_update(self):
        """Check timer and update help button state"""
        try:
            Overlay.update_help_button(self.ui, self.timer, self.hints_requested, self.time_exceeded_45, self.assigned_room)
        except Exception as e:
            traceback.print_exc()

    def toggle_fullscreen(self):
        """Development helper to toggle fullscreen - no longer needed with Qt"""
        pass

    def get_stats(self):
        if self.is_closing:
            print("[kiosk get_stats] Prevented stats update and screenshot: Kiosk is closing.", flush=True)
            return {} # Return empty dict to avoid issues if stats are expected
        # --- BEGIN: Add currently displayed hint info ---
        hint_text = None
        hint_image = None
        if hasattr(self, 'ui') and hasattr(self.ui, 'current_hint'):
            ch = self.ui.current_hint
            if isinstance(ch, str):
                hint_text = ch
            elif isinstance(ch, dict):
                hint_text = ch.get('text', None)
        # Use the new QtManager method to get just the filename
        if hasattr(self, 'ui') and hasattr(self.ui, 'current_hint_image_filename'):
            hint_image = self.ui.current_hint_image_filename
        # --- END: Add currently displayed hint info ---
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
            'music_volume_level': self.music_volume_level, # Add music volume level
            'hint_volume_level': self.hint_volume_level,   # Add hint volume level
            'video_playing': self.video_manager.is_playing if hasattr(self, 'video_manager') else False,
            # --- NEW FIELDS ---
            'current_hint_text': hint_text,
            'current_hint_image': hint_image,
        }
        # Only log if stats have changed from last time
        if not hasattr(self, '_last_stats') or self._last_stats != stats:
            #print(f"[kiosk main]Stats updated: {stats}")
            self._last_stats = stats.copy()

        # --- Add screenshot logic HERE ---
        if hasattr(self, 'take_screenshot_requested') and self.take_screenshot_requested:
            # Start a new thread to handle the screenshot
            threading.Thread(target=self.send_screenshot, daemon=True).start()
            self.take_screenshot_requested = False  # Reset flag after sending


        return stats
    
    def send_screenshot(self):
        """Takes and sends a screenshot to the admin."""
        if self.is_closing:
            print("[kiosk]Screenshot send prevented: Kiosk is closing.", flush=True)
            return

        try:
            #print("[kiosk] Taking screenshot...", flush=True)
            from PIL import ImageGrab, Image
            import io, base64

            # Add a small delay.  This is the most important change.
            time.sleep(0.1)  # Wait 100ms.  Adjust as needed.

            if self.is_closing:  # Re-check after the delay.
                print("[kiosk]Screenshot send prevented after delay: Kiosk is closing.", flush=True)
                return
            
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
            #print("[kiosk] Screenshot sent.", flush=True)

        except Exception as e:
            print(f"[kiosk]Screenshot error: {e}", flush=True)
            traceback.print_exc()
    
    def handle_message(self, msg):
        """Use delegate pattern to dispatch messages to MessageHandler"""
        self.message_handler.handle_message(msg)
        
    def handle_game_loss(self):
        """Displays the game loss screen"""
        print("[kiosk main]Displaying game loss screen...")
        # Clear current UI
        self.clear_hints()
        # Display game loss screen via Overlay
        Overlay.show_loss_screen()
        print("[kiosk] Handling game loss", flush=True)
        if(self.audio_manager):
            self.audio_manager.stop_background_music()
            if self.assigned_room:
                print(f"[kiosk] Playing loss audio for room {self.assigned_room}.", flush=True)
                self.audio_manager.play_loss_audio(self.assigned_room)
            else:
                print("[kiosk] No room assigned, cannot play loss audio.", flush=True)
        else:
            print("[kiosk] ERROR: No audio manager found")

    
    def handle_game_win(self):
        """Displays the game win screen"""
        print("[kiosk main]Displaying game win screen...")
        try:
            # Stop the music
            if(self.audio_manager):
                self.audio_manager.stop_background_music()
            else:
                print("[kiosk main] ERROR: No audio manager found")
            # Pause the timer
            if self.timer.is_running:
                print("[kiosk main]Pausing timer due to victory")
                self.timer.handle_command("stop")
            # Clear current UI
            self.clear_hints()
            # Display game win screen via Overlay
            try:
                # Check if Overlay is initialized before trying to show victory screen
                if Overlay._initialized:
                    Overlay.show_victory_screen()
                else:
                    print("[kiosk main]WARNING: Overlay not initialized when trying to show victory screen")
            except Exception as e:
                print(f"[kiosk main]ERROR showing victory screen: {e}")
                import traceback
                traceback.print_exc()
        except Exception as e:
            print(f"[kiosk main]ERROR in handle_game_win: {e}")
            import traceback
            traceback.print_exc()
    
    def request_help(self):
        """Request help (hint) from the server. Called by UI and network handlers."""
        print("[kiosk main]Request help called.")
        # Set flag for stats update
        self.hint_requested_flag = True
        # Trigger immediate help button update to hide it
        self._actual_help_button_update()
        # Have UI display the request pending message
        Overlay.show_hint_request_text()
        # Have UI handle the help request (includes sending network message)
        self.ui.request_help()
            
    def show_hint(self, text, start_cooldown=True):
        # Clear any pending request status
        Overlay.hide_hint_request_text()
        self.hint_requested_flag = False  # Reset hint flag

        Overlay.hide_fullscreen_hint() #hide any previous fullscreen hint
        
        # Trigger immediate help button update
        self._actual_help_button_update()
        
        # Handle different types of hint data
        if isinstance(text, dict):
            # Handle dictionary format (used for image hints)
            hint_text = text.get('text', '')
            if hint_text:
                print(f"[kiosk main]Showing hint: {hint_text[:30]}{'...' if len(hint_text) > 30 else ''}")
            else:
                print("[kiosk main]Showing image hint (no text)")
            self.ui.show_hint(text, start_cooldown)
        elif text:
            # Handle string format (text-only hints)
            print(f"[kiosk main]Showing hint: {text[:30]}{'...' if len(text) > 30 else ''}")
            self.ui.show_hint(text, start_cooldown)
            self.ui.current_hint_image_filename = None 
        else:
            # If hint is empty/None, clear both text and image
            self.ui.current_hint_image_filename = None

        image_path = text # wrong
        if image_path:
            # Assuming image_path is like 'hint_image_files/room/prop_name/image.png'
            # We need just 'image.png'
            self.ui.current_hint_image_filename = "image name not available" #os.path.basename(image_path)
        else:
            self.ui.current_hint_image_filename = None
    
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
                self.audio_manager.play_background_music(self.assigned_room)  # Pass the room NUMBER
            
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
            thread_id = threading.get_ident()
            print(f"[kiosk main][CALLBACK_{thread_id}] +++ play_game_video ENTERED (Thread: {thread_id}) +++")
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
        """Handle application close."""
        if self.is_closing:
            print("[kiosk main] Already closing, ignoring duplicate on_closing call.")
            return
            
        print("[kiosk main] Closing kiosk application...")
        self.is_closing = True
        
        # Save state before closing
        self.save_state()
        
        # Wrap each shutdown step in try-except to ensure complete shutdown
        try:
            # Stop video player if running
            if hasattr(self, 'video_manager'):
                print("[kiosk main] Stopping video manager...")
                self.video_manager.force_stop()
        except Exception as e:
            print(f"[kiosk main] Error stopping video manager: {e}")
            log_exception(e, "Error stopping video manager")
        
        try:
            # Close Qt overlay
            if Overlay._bridge:
                print("[kiosk main] Calling Overlay.on_closing_slot...")
                QMetaObject.invokeMethod(Overlay._bridge, "on_closing_slot", Qt.QueuedConnection)
        except Exception as e:
            print(f"[kiosk main] Error closing overlay: {e}")
            log_exception(e, "Error closing overlay")
        
        try:
            # Shutdown network component
            if hasattr(self, 'network'):
                print("[kiosk main] Stopping network...")
                # Check which method exists and call it
                if hasattr(self.network, 'shutdown'):
                    self.network.shutdown()
                else:
                    print("[kiosk main] Warning: No stop method found in network component")
        except Exception as e:
            print(f"[kiosk main] Error stopping network: {e}")
            log_exception(e, "Error stopping network")
        
        try:
            if hasattr(self, 'video_server'):
                print("[kiosk main] Stopping video server...")
                self.video_server.stop()
        except Exception as e:
            print(f"[kiosk main] Error stopping video server: {e}")
            log_exception(e, "Error stopping video server")
            
        try:
            if hasattr(self, 'audio_server'):
                print("[kiosk main] Stopping audio server...")
                self.audio_server.stop()
        except Exception as e:
            print(f"[kiosk main] Error stopping audio server: {e}")
            log_exception(e, "Error stopping audio server")
        
        try:
            if hasattr(self, 'file_downloader'):
                print("[kiosk main] Stopping file downloader...")
                self.file_downloader.stop()
        except Exception as e:
            print(f"[kiosk main] Error stopping file downloader: {e}")
            log_exception(e, "Error stopping file downloader")
        
        try:
            # Stop any video playback
            if hasattr(self, "current_video_process") and self.current_video_process:
                # Try to terminate the process
                try:
                    import psutil
                    p = psutil.Process(self.current_video_process.pid)
                    p.terminate()
                except Exception as e:
                    print(f"[kiosk main] Error terminating video process: {e}")
                    log_exception(e, "Error terminating video process")
                self.current_video_process = None
        except Exception as e:
            print(f"[kiosk main] Error handling video process: {e}")
            log_exception(e, "Error handling video process")
        
        try:
            if hasattr(self, 'heartbeat_stop_event') and self.heartbeat_stop_event:
                print("[kiosk main] Stopping heartbeat thread...", flush=True)
                self.heartbeat_stop_event.set()  # Signal the thread to stop
            if hasattr(self, 'heartbeat_thread') and self.heartbeat_thread.is_alive():
                self.heartbeat_thread.join(timeout=2.0)  # Wait for thread to finish
                if self.heartbeat_thread.is_alive():
                    print("[kiosk main] Warning: Heartbeat thread did not terminate cleanly.", flush=True)
        except Exception as e:
            print(f"[kiosk main] Error stopping heartbeat thread: {e}", flush=True)
            # log_exception(e, "Error stopping heartbeat thread")  # If logger is still active
        
        # Stop the logger last to catch all cleanup messages
        try:
            if hasattr(self, 'logger') and self.logger:
                print("[kiosk main] Stopping console logger...")
                self.logger.stop()
        except Exception as e:
            print(f"[kiosk main] Error stopping logger: {e}")
            # Can't use log_exception here as logger is being stopped
            traceback.print_exc()
        
        # Kill tap detector
        try:
            if hasattr(self, 'tap_detector') and self.tap_detector:
                print("[kiosk main] Stopping tap detector...")
                self.tap_detector.stop()
        except Exception as e:
            print(f"[kiosk main] Error stopping tap detector: {e}")
            log_exception(e, "Error stopping tap detector")

        # Cancel soundcheck if active
        try:
            # Access soundcheck_widget via message_handler
            if hasattr(self, 'message_handler') and hasattr(self.message_handler, 'soundcheck_widget') and self.message_handler.soundcheck_widget:
                print("[Kiosk Main] Closing active soundcheck window...")
                # Ensure cancel runs on main thread
                QMetaObject.invokeMethod(self.message_handler.soundcheck_widget, "cancel_soundcheck", Qt.QueuedConnection)
        except Exception as e:
            print(f"[Kiosk Main] Error cancelling soundcheck on close: {e}")
            # log_exception(e, "Error cancelling soundcheck on close") # If logger available

        print("[kiosk main] Shutdown sequence complete.")

    def clear_hints(self):
        """Clear all hints"""
        print("[kiosk main]Clearing hints...")
        # Clear any pending request status
        Overlay.hide_hint_request_text()
        self.hint_requested_flag = False  # Reset hint flag

        # Reset hint tracking variables
        if hasattr(self, 'ui'):
            # Reset UI state variables
            self.ui.hint_cooldown = False
            self.ui.current_hint = None
            self.ui.stored_image_data = None
            self.ui.stored_video_info = None
            self.ui.current_hint_image_filename = None
            
            # Have UI clear labels and hint UI elements
            self.ui.clear_all_labels()
            self.ui.clear_hint_ui()
        
        # Update help button to show it again if needed
        self._actual_help_button_update()

    def run(self):
        """Start the application"""
        print("[kiosk main]run() called")
        # Run the Qt event loop 
        self.qt_app.run()

    def _send_heartbeats(self):
        # This interval should be noticeably SHORTER than HEARTBEAT_TIMEOUT_SECONDS in the watchdog
        HEARTBEAT_INTERVAL_SECONDS = 5 
        HEARTBEAT_MESSAGE = "[HEARTBEAT_KIOSK_ALIVE]"  # Must match HEARTBEAT_MARKER in watchdog

        # Optional: Initial small delay to ensure watchdog is ready if kiosk starts super fast
        # time.sleep(1) 
        
        print(f"[kiosk heartbeat] Thread started. Sending '{HEARTBEAT_MESSAGE}' every {HEARTBEAT_INTERVAL_SECONDS}s.", flush=True)
        try:
            while not self.heartbeat_stop_event.wait(HEARTBEAT_INTERVAL_SECONDS):  # wait returns True if event set
                if self.is_closing:  # Check if application is closing
                    break
                # We print directly to stdout. The watchdog will capture this.
                print(HEARTBEAT_MESSAGE, flush=True)
                # print(f"[kiosk heartbeat] Sent heartbeat.", flush=True)  # Optional: for kiosk's own logs
        except Exception as e:
            print(f"[kiosk heartbeat] Error in heartbeat loop: {e}", flush=True)
        finally:
            print("[kiosk heartbeat] Thread stopping.", flush=True)

    def restore_state(self):
        """Attempt to restore state from kiosk_state.json if it exists and is recent"""
        try:
            state_file = Path("kiosk_state.json")
            if not state_file.exists():
                print("[kiosk main] No state file found to restore from.")
                return

            with open(state_file, 'r') as f:
                state = json.load(f)

            # Check if state is recent (within 5 minutes)
            current_time = time.time()
            state_time = state.get('timestamp_utc', 0)
            # Allow restoration only if state is recent and room is assigned
            if current_time - state_time > 300 or not self.assigned_room:  # 5 minutes = 300 seconds
                print(f"[kiosk main] State file is too old ({int(current_time - state_time)}s old) or no room assigned ({self.assigned_room}) to restore from.")
                return

            print("[kiosk main] Restoring state from kiosk_state.json...")

            # Restore timer state
            if 'timer_remaining_seconds' in state and state['timer_remaining_seconds'] > 0:
                print(f"[kiosk main] Restoring timer to {state['timer_remaining_seconds']}s")
                # Set timer first
                self.timer.handle_command("set", state['timer_remaining_seconds'] // 60) # Set minutes
                # Handle remainder seconds if needed (KioskTimer set expects minutes, but it stores seconds)
                # The KioskTimer already stores seconds internally, so setting minutes
                # might lose precision. Let's adjust KioskTimer if needed, but for now,
                # assume 'set' handles seconds correctly or accepts total seconds.
                # Based on the provided code snippet `handle_command("set", minutes)`,
                # it seems it only takes minutes. We'll stick to setting minutes from restored seconds.
                # A more robust solution would modify KioskTimer.set to accept total seconds.
                # For now, floor division is used.
                
                # If game was running, start the timer
                if state.get('game_running', False):
                    print("[kiosk main] Restoring timer state: Starting timer")
                    self.timer.handle_command("start")
                else:
                     print("[kiosk main] Restoring timer state: Timer not running in saved state")


            # Restore hint counts
            if 'hints_requested_count' in state:
                self.hints_requested = state['hints_requested_count']
                print(f"[kiosk main] Restored hints requested: {self.hints_requested}")
            if 'hints_received_count' in state:
                self.hints_received = state['hints_received_count']
                print(f"[kiosk main] Restored hints received: {self.hints_received}")

            # Restore music position if applicable
            # Ensure audio_manager exists, room is assigned, and position is valid
            if hasattr(self, 'audio_manager') and self.assigned_room and state.get('music_position_ms', -1) >= 0:
                music_pos_ms = state['music_position_ms']
                music_pos_sec = music_pos_ms / 1000.0 # Convert milliseconds to seconds
                print(f"[kiosk main] Restoring music for room {self.assigned_room} from position {music_pos_ms} ms ({music_pos_sec:.2f} s)")
                # Use the existing play_background_music method, which takes a start time in seconds
                self.audio_manager.play_background_music(self.assigned_room, start_time_seconds=music_pos_sec)
            else:
                print("[kiosk main] Skipped music restoration (audio_manager missing, no room, or invalid position).")


            print("[kiosk main] State restoration complete.")

        except FileNotFoundError:
             # Already handled by the state_file.exists() check, but good practice
            print("[kiosk main] State file disappeared during restoration attempt.")
        except json.JSONDecodeError:
            print("[kiosk main] Error decoding kiosk_state.json. File might be corrupted.")
            traceback.print_exc()
        except Exception as e:
            print(f"[kiosk main] General error restoring state: {e}")
            traceback.print_exc()
        finally:
            # Clean up the state file after attempting restoration, regardless of success
            # This prevents restoring old or corrupted state on subsequent runs
            try:
                state_file = Path("kiosk_state.json")
                if state_file.exists():
                    print("[kiosk main] Removing kiosk_state.json after restoration attempt.")
                    state_file.unlink()
            except Exception as e:
                print(f"[kiosk main] Error removing kiosk_state.json: {e}")
                traceback.print_exc()

    def save_state(self):
        """Save current state to kiosk_state.json"""
        #print("saving state", flush=True)
        try:
            state = {
                'game_running': self.timer.is_running if hasattr(self, 'timer') else False,
                'timer_remaining_seconds': self.timer.time_remaining if hasattr(self, 'timer') else 0,
                'hints_requested_count': self.hints_requested,
                'hints_received_count': self.hints_received,
                'music_position_ms': self.audio_manager.get_music_position_ms() if hasattr(self, 'audio_manager') else -1,
                'timestamp_utc': time.time()
            }

            with open('kiosk_state.json', 'w') as f:
                json.dump(state, f, indent=2)

        except Exception as e:
            print(f"[kiosk main] Error saving state: {e}")
            traceback.print_exc()

    def save_state_periodically(self):
        """
        Called by a QTimer to periodically save the application state.
        This is the primary defense against data loss from a hard crash.
        """
        # Don't save if the game isn't running or if we are closing down.
        if self.is_closing or not self.timer.is_running:
            return
            
        self.save_state() # This already has the logic and error handling

def main():
    """Main entry point for the kiosk application."""
    # Setup exception handling for main thread
    try:
        # Check for state restoration argument
        should_restore_state = "--restore-state" in sys.argv
        
        app = KioskApp()
        
        # If state restoration is requested, attempt to restore from kiosk_state.json
        if should_restore_state:
            app.restore_state()
        
        # Set up signal handler for Ctrl+C
        def signal_handler(sig, frame):
            print('\n[kiosk main] SIGINT received, initiating shutdown...')
            app.on_closing()
            sys.exit(0)
        
        # Set signal handler after KioskApp is created
        signal.signal(signal.SIGINT, signal_handler)
        app.run()
    except Exception as e:
        print(f"[kiosk main] Fatal error in main thread: {str(e)}")
        traceback.print_exc()
        if 'app' in locals() and hasattr(app, 'logger') and app.logger:
            log_exception(e, "Fatal error in main thread")
            app.logger.stop()
        sys.exit(1)
    
if __name__ == "__main__":
    main()