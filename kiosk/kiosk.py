# kiosk.py
print("[kiosk main] Beginning imports ...")
# import tkinter as tk - removed
import socket, sys, os, traceback, ctypes # type: ignore
from networking import KioskNetwork
from ui import KioskUI
from config import ROOM_CONFIG
from video_server import VideoServer
from video_manager import VideoManager
from audio_server import AudioServer
from message_handler import MessageHandler, init_timer_scheduler
from pathlib import Path
from room_persistence import RoomPersistence
from kiosk_timer import KioskTimer
from audio_manager import AudioManager
from kiosk_file_downloader import KioskFileDownloader
from qt_overlay import Overlay
from qt_main import QtKioskApp  # Import the new QtKioskApp class
from ctypes import windll
import signal
import threading
import time
from PyQt5.QtCore import QMetaObject, Qt, QTimer, Q_ARG
print("[kiosk main] Ending imports ...")

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
        self.needs_restart = False
        self.start_time = None
        self.take_screenshot_requested = False
        self.time_exceeded_45 = False
        self.room_started = False

        # Create Qt application first, before any other component
        self.qt_app = QtKioskApp(self)
        
        # Handle icon setting
        myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

        # Initialize Qt overlay with explicit reference to the QApplication instance
        # We'll modify the Overlay.init method to accept a reference to the Qt application
        Overlay._app = self.qt_app  # Set the app reference directly
        Overlay.init()
        
        # Set the kiosk_app reference directly
        Overlay.set_kiosk_app(self)
        
        # Now initialize other components
        self.current_video_process = None
        self.audio_manager = AudioManager(self)  # Pass the KioskApp instance
        self.video_manager = VideoManager(None)  # No longer need to pass root
        self.message_handler = MessageHandler(self, self.video_manager)
        
        # Initialize components as before
        self.network = KioskNetwork(self.computer_name, self)
        self.video_server = VideoServer()
        print("[kiosk main]Starting video server...")
        self.video_server.start()
        
        from kiosk_timer import KioskTimer
        self.timer = KioskTimer(None, self)  # Pass self but no longer need root
        self.timer.game_won = False 
        
        # Create UI after setting kiosk_app reference
        self.ui = KioskUI(None, self.computer_name, ROOM_CONFIG, self)  # No longer need to pass root
        self.ui.setup_waiting_screen()
        self.network.start_threads()

        self.audio_server = AudioServer()
        print("[kiosk main]Starting audio server...")
        self.audio_server.start()

        print(f"[kiosk main]Computer name: {self.computer_name}")
        print("[kiosk main]Creating RoomPersistence...")
        self.room_persistence = RoomPersistence()
        self.assigned_room = self.room_persistence.load_room_assignment()
        print(f"[kiosk main]Loaded room assignment: {self.assigned_room}")

        #Initialize the file downloader
        self.file_downloader = KioskFileDownloader(self)
        self.file_downloader.start() # Start it immediately
        
        # Initialize UI with saved room if available
        if self.assigned_room:
            # Use QTimer.singleShot instead of root.after
            QTimer.singleShot(100, lambda: self.ui.setup_room_interface(self.assigned_room))
        else:
            self.ui.setup_waiting_screen()

        # Create a timer for the help button update
        self.help_button_timer = QTimer()
        self.help_button_timer.timeout.connect(self._actual_help_button_update)
        self.help_button_timer.start(1000)  # Update every 1 second

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
            # Start a new thread to handle the screenshot
            threading.Thread(target=self.send_screenshot, daemon=True).start()
            self.take_screenshot_requested = False  # Reset flag after sending


        return stats
    
    def send_screenshot(self):
        """Takes and sends a screenshot to the admin."""
        if self.is_closing:
            print("[kiosk]Screenshot send prevented: Kiosk is closing.")
            return

        try:
            from PIL import ImageGrab, Image
            import io, base64

            # Add a small delay.  This is the most important change.
            time.sleep(0.1)  # Wait 100ms.  Adjust as needed.

            if self.is_closing:  # Re-check after the delay.
                print("[kiosk]Screenshot send prevented after delay: Kiosk is closing.")
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

        except Exception as e:
            print(f"[kiosk]Screenshot error: {e}")
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
    
    def handle_game_win(self):
        """Displays the game win screen"""
        print("[kiosk main]Displaying game win screen...")
        # Clear current UI
        self.clear_hints()
        # Display game win screen via Overlay
        Overlay.show_victory_screen()
    
    def request_help(self):
        """Request help (hint) from the server. Called by UI and network handlers."""
        print("[kiosk main]Request help called.")
        # Set flag for stats update
        self.hint_requested_flag = True
        # Have UI display the request pending message
        Overlay.show_hint_request_text()
        # Have UI handle the help request (includes sending network message)
        self.ui.request_help()
            
    def show_hint(self, text, start_cooldown=True):
        # Clear any pending request status
        Overlay.hide_hint_request_text()
        self.hint_requested_flag = False  # Reset hint flag
        
        if text:
            print(f"[kiosk main]Showing hint: {text[:30]}{'...' if len(text) > 30 else ''}")
            self.hints_received += 1  # Count hints actually shown
            self.ui.show_hint(text, start_cooldown)
    
    def play_video(self, video_type, minutes):
        print(f"[kiosk main]play_video called: {video_type}, {minutes} minutes")
        
        # Ensure needed objects exist
        if not hasattr(self, 'video_manager') or not hasattr(self, 'timer'):
            print("[kiosk main]Error: video_manager or timer not initialized.")
            return
             
        # Get video path based on type
        video_path = None
        if video_type == "start":
            video_type_folder = "game_start_videos"
        elif video_type == "end":
            video_type_folder = "game_completion"
        elif video_type == "loss":
            video_type_folder = "game_loss"
        else:  # Default to video_solutions for any other type
            video_type_folder = "video_solutions"
            
        # Get room folder for video
        if not self.assigned_room:
            print("[kiosk main]Error: No assigned room for video.")
            return
            
        room_folder = f"Room_{self.assigned_room}"
        videos_base = os.path.join("..", "Videos", room_folder, video_type_folder)
        
        # Build completion callback
        def finish_video_sequence():
            print("[kiosk main] Video sequence finished.")
            # If this is a game end video, do nothing special: UI should remain victory screen
            if video_type == "end":
                print("[kiosk main] Game completion video finished.")
                return
                
            # If this is a game loss video, do nothing special: UI should remain game over
            if video_type == "loss":
                print("[kiosk main] Game loss video finished.")
                return
                
            if video_type == "start":
                print("[kiosk main] Game start video finished. Starting timer.")
                # Start timer if a game start video
                self.timer.start(minutes * 60) # minutes converted to seconds
                # Show all overlays once video is done
                Overlay.show_all_overlays()
            else:
                # For solution videos, restore all overlays
                print("[kiosk main] Solution video finished. Restoring overlays.")
                Overlay.show_all_overlays()
                
        # Build and get video path, ensure file exists
        video_path = None
        if video_type == "start":
            video_path = os.path.join(videos_base, "start.mp4")
        elif video_type == "end":
            video_path = os.path.join(videos_base, "end.mp4")
        elif video_type == "loss":
            video_path = os.path.join(videos_base, "loss.mp4")
        else:  # solution video            
            # Look for a video matching the minutes
            video_path = os.path.join(videos_base, f"{minutes}min.mp4")
            
        # Final check for video file
        if not video_path or not os.path.exists(video_path):
            print(f"[kiosk main]Error: Video file not found: {video_path}")
            return
            
        # Play game video only when we have a valid path
        def play_game_video():
            print(f"[kiosk main]Playing video: {video_path}")
            
            # Check if this is a solution video
            is_solution = (video_type not in ["start", "end", "loss"])
            
            # Tell video_manager to play the video with completion callback
            self.video_manager.play_video(video_path, finish_video_sequence)
            
        # Start playback immediately if already prepared
        play_game_video()
    
    def on_closing(self):
        """Handle application close."""
        if self.is_closing:
            print("[kiosk main]WARNING: on_closing() called but already closing.")
            return
        
        self.is_closing = True
        print("[kiosk main]on_closing() called, starting shutdown sequence...")
        
        # Stop video player if running
        if hasattr(self, 'video_manager'):
            print("[kiosk main]Stopping video manager...")
            self.video_manager.force_stop()
        
        # Close Qt overlay
        if Overlay._bridge:
            print("[kiosk main]Calling Overlay.on_closing_slot...")
            QMetaObject.invokeMethod(Overlay._bridge, "on_closing_slot", Qt.QueuedConnection)
        
        # Shutdown components
        if hasattr(self, 'network'):
            print("[kiosk main]Stopping network...")
            self.network.stop()
        
        if hasattr(self, 'video_server'):
            print("[kiosk main]Stopping video server...")
            self.video_server.stop()
            
        if hasattr(self, 'audio_server'):
            print("[kiosk main]Stopping audio server...")
            self.audio_server.stop()
        
        if hasattr(self, 'file_downloader'):
            print("[kiosk main]Stopping file downloader...")
            self.file_downloader.stop()
            
        print("[kiosk main]Shutdown sequence complete.")
        
    def clear_hints(self):
        """Clear all hints"""
        print("[kiosk main]Clearing hints...")
        # Clear any pending request status
        Overlay.hide_hint_request_text()
        self.hint_requested_flag = False  # Reset hint flag

        # Have UI clear labels
        if hasattr(self, 'ui'):
            self.ui.clear_all_labels()
            self.ui.clear_hint_ui()

    def run(self):
        """Start the application"""
        print("[kiosk main]run() called")
        # Run the Qt event loop 
        self.qt_app.run()

def main():
    """Program entry point"""
    # Create and run app
    app = KioskApp()
    
    # Set up signal handler for Ctrl+C
    def signal_handler(sig, frame):
        print('\n[kiosk main]SIGINT received, initiating shutdown...')
        app.on_closing()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the app
    app.run()
    
if __name__ == "__main__":
    main()