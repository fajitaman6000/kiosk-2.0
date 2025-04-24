# qt_manager.py
print("[qt_manager] Beginning imports ...")
import os
import threading
import traceback
from qt_overlay import Overlay
from PyQt5.QtCore import QTimer, QObject, pyqtSlot, QMetaObject, Qt, Q_ARG
import base64
print("[qt_manager] Ending imports ...")

class QtManager:
    def __init__(self, computer_name, room_config, message_handler):
        self.computer_name = computer_name
        self.room_config = room_config
        self.message_handler = message_handler
        self.parent_app = message_handler
        
        self._lock = threading.Lock()

        # State variables migrated from KioskUI
        self.hint_cooldown = False
        self.current_hint = None
        self.cooldown_after_id = None  # This will be replaced with QTimer objects
        self.stored_image_data = None
        self.stored_video_info = None
        self.image_is_fullscreen = False
        self.current_room = 0

        # Register this instance with the overlay for callbacks
        self.register_with_overlay()

        # Initialize the Qt overlay if not already initialized
        Overlay.init()

    def register_with_overlay(self):
        """Register this instance with the overlay for callbacks."""
        # Use the _on_view_image_button_clicked and _on_view_solution_button_clicked 
        # static methods from Overlay, but have them call methods in this class
        Overlay.register_ui_manager(self)

    def on_view_image_clicked(self):
        """Handler for view image button clicks."""
        print("[qt_manager] View image button clicked")
        if self.stored_image_data:
            self.show_fullscreen_image()
        else:
            print("[qt_manager] No image data to show")

    def on_view_solution_clicked(self):
        """Handler for view solution button clicks."""
        print("[qt_manager] View solution button clicked")
        self.toggle_solution_video()

    def load_background(self, room_number):
        if room_number not in self.room_config['backgrounds']:
            return None
            
        filename = self.room_config['backgrounds'][room_number]
        path = os.path.join("Backgrounds", filename)
        
        try:
            if os.path.exists(path):
                return path
        except Exception as e:
            print(f"[qt_manager] Error loading background: {str(e)}")
        return None
        
    def setup_waiting_screen(self):
        # Use the Qt Overlay for the waiting screen
        Overlay.show_waiting_screen_label(self.computer_name)
        
    def clear_all_labels(self):
        """Clear all UI elements and cancel any pending cooldown timer"""
        if self.cooldown_after_id:
            # Cancel any running QTimer
            self.cooldown_after_id.stop()
            self.cooldown_after_id = None
            
        self.hint_cooldown = False
        
    def clear_hint_ui(self):
        """Clears hint UI elements and hides Qt elements."""
        print("[qt_manager] Clearing hint UI elements and hiding Qt counterparts")

        # Hide Qt Hint Text/Buttons
        Overlay.hide_hint_text()
        Overlay.hide_view_image_button()
        Overlay.hide_view_solution_button()

        # Clear hint text content directly (don't use QMetaObject.invokeMethod which causes errors)
        if hasattr(Overlay, '_hint_text') and Overlay._hint_text and 'text_item' in Overlay._hint_text:
            try:
                # Direct call instead of using QMetaObject.invokeMethod
                Overlay._hint_text['text_item'].setPlainText("")
                print("[qt_manager] Cleared hint text content")
            except Exception as e:
                print(f"[qt_manager] Error clearing hint text: {e}")
            
        # Reset hint data
        self.current_hint = None
        self.stored_image_data = None
        self.stored_video_info = None
        
        # Clear hint cooldown
        if self.cooldown_after_id:
            self.cooldown_after_id.stop()
            self.cooldown_after_id = None
        self.hint_cooldown = False
        Overlay.hide_hint_cooldown()
        
        # Hide hint request text
        Overlay.hide_hint_request_text()

    def setup_room_interface(self, room_number):
        """Set up the room interface for the given room number"""
        # Ensure the waiting screen label is hidden
        Overlay.hide_waiting_screen_label()

        # Configure the room-specific elements
        if room_number > 0:
            self.current_room = room_number
            
            # Get background path and set background using Qt overlay
            background_path = self.load_background(room_number)
            if background_path:
                # Use Qt to render the background
                Overlay.set_background_image(background_path)

            # Load room-specific timer background
            self.message_handler.timer.load_room_background(room_number)

            # Show the timer if it exists
            if hasattr(self.message_handler, 'timer'):
                Overlay.update_timer_display(self.message_handler.timer.get_time_str())

            # Conditional Help Button and Hint Restore ---
            # Only update the help button OR restore the hint if there is an active hint.
            if self.current_hint is not None:
                hint_text = self.current_hint if isinstance(self.current_hint, str) else self.current_hint.get('text', '')
                # Check again here, just before showing the hint.
                if hint_text is not None and hint_text.strip() != "":
                    print("[qt_manager] Restoring non-empty hint within setup_room_interface")
                    Overlay.show_hint_text(hint_text, self.current_room)
            else:
                # If there's NO current hint, then update the help button.
                print("[qt_manager] No current hint, updating help button within setup_room_interface")
                # Use QTimer.singleShot
                QTimer.singleShot(100, lambda: self.message_handler._actual_help_button_update())
    
    def request_help(self):
        """Creates the 'Hint Requested' message without clearing existing hints"""
        if not self.hint_cooldown:
            # Increase hint count
            if hasattr(self.message_handler, 'hints_requested'):
                self.message_handler.hints_requested += 1
            
            # No longer clear existing hint
            # Remove help button if it exists
            Overlay.hide_help_button()
            
            # Send help request
            self.message_handler.network.send_message({
                'type': 'help_request',
                **self.message_handler.get_stats()
            })

    def show_hint(self, text_or_data, start_cooldown=True):
        try:
            print("[qt_manager] Showing hint...")
            Overlay.hide_help_button() # Hide main help button

            # If video was playing, stop it
            if hasattr(self.message_handler.video_manager, 'is_playing') and self.message_handler.video_manager.is_playing:
                 print("[qt_manager] Warning: Stopping video playback because new hint arrived.")
                 self.message_handler.video_manager.stop_video()

            # Clear stored video info if a new hint arrives
            self.stored_video_info = None
            
            # Explicitly hide the view solution button when receiving a text hint
            Overlay.hide_view_solution_button()

            if start_cooldown:
                self.start_cooldown() # Starts Qt cooldown overlay via Overlay.show_hint_cooldown

            self.current_hint = text_or_data # Store the new hint data

            Overlay.hide_hint_request_text()

            Overlay.hide_view_image_button()

            # Process hint data
            hint_text = ""
            self.stored_image_data = None

            if isinstance(text_or_data, str):
                hint_text = text_or_data
            elif isinstance(text_or_data, dict):
                hint_text = text_or_data.get('text', '')
                self.stored_image_data = text_or_data.get('image') # Store potential image data
            else:
                # Fallback if unexpected data type
                hint_text = str(text_or_data)
                print(f"[qt_manager] Warning: Received hint data of unexpected type: {type(text_or_data)}")

            # Use placeholder if only image exists
            if self.stored_image_data and not hint_text:
                hint_text = "Image hint received" # Placeholder text

            # Show hint text via Qt Overlay
            print(f"[qt_manager] Showing hint text: '{hint_text}'")
            Overlay.show_hint_text(hint_text, self.current_room, priority=self.stored_image_data is not None)

            # --- Show Qt image button if image data exists ---
            if self.stored_image_data:
                print("[qt_manager] Stored image data found, showing View Image button.")
                Overlay.show_view_image_button(self) # Pass self (qt_manager_instance)

        except Exception as e:
            print(f"[qt_manager] Critical error in show_hint: {e}")
            traceback.print_exc()
            
    def show_fullscreen_image(self):
        """Display the image in nearly fullscreen using Qt Overlay"""
        print("[qt_manager] Requesting Qt Overlay for fullscreen image.")
        self.image_is_fullscreen = True  # Set the flag FIRST
        if not self.stored_image_data:
            print("[qt_manager] No stored image data to show.")
            self.image_is_fullscreen = False # Reset if no data
            return

        try:
            # Call the Qt Overlay to handle display
            Overlay.show_fullscreen_hint(self.stored_image_data, self) # Pass self
        except Exception as e:
            print("[qt_manager] Error requesting fullscreen image overlay:")
            traceback.print_exc()
            self.image_is_fullscreen = False # Reset flag on error
        
    def restore_hint_view(self):
        """Restores the normal hint view after fullscreen Qt hint is closed."""
        print("[qt_manager] Restoring hint view after Qt fullscreen hint.")
        self.image_is_fullscreen = False # Reset flag

        # Determine Hint Text
        hint_text = ""
        image_data_exists = False
        video_info_exists = False

        if isinstance(self.current_hint, str):
            hint_text = self.current_hint
        elif isinstance(self.current_hint, dict):
            hint_text = self.current_hint.get('text', '')
            image_data_exists = bool(self.current_hint.get('image'))
            if image_data_exists and not hint_text:
                hint_text = "Image hint received" # Restore placeholder text

        # Also check separately if video solution info is stored
        video_info_exists = bool(self.stored_video_info)

        # Re-show hint text
        if hint_text:
            Overlay.show_hint_text(hint_text, self.current_room)

        # Re-show image button if needed, but only if not in fullscreen mode
        if image_data_exists and not self.image_is_fullscreen:
            Overlay.show_view_image_button(self)
        else:
            # Ensure button is hidden
            Overlay.hide_view_image_button()

        # Re-show video solution button if needed
        if video_info_exists:
            Overlay.show_view_solution_button(self)
        else:
            # Ensure button is hidden
            Overlay.hide_view_solution_button()

    def start_cooldown(self):
        """Starts the hint cooldown timer and displays the cooldown message."""
        print("[qt_manager] Starting hint cooldown...")
        
        # Cancel any existing cooldown timer
        if self.cooldown_after_id:
            self.cooldown_after_id.stop()
            self.cooldown_after_id = None
        
        # Set the cooldown flag
        self.hint_cooldown = True
        
        # Use fixed 10 seconds cooldown instead of from config
        cooldown_seconds = 60
        
        # Show initial cooldown
        Overlay.show_hint_cooldown(cooldown_seconds)
        
        # Create a new QTimer for the cooldown
        self.cooldown_after_id = QTimer()
        self.cooldown_after_id.timeout.connect(lambda: self.update_cooldown())
        self.cooldown_after_id.start(1000)  # Update every second
        
        # Store the end time to have a single source of truth
        self.cooldown_end_time = cooldown_seconds
        self.cooldown_current_time = cooldown_seconds

    def update_cooldown(self):
        """Updates the cooldown timer display with the seconds left."""
        # Decrement the cooldown time
        self.cooldown_current_time -= 1
        seconds_left = self.cooldown_current_time
        
        if seconds_left > 0 and self.hint_cooldown:
            # Update the cooldown display if appropriate
            if not self.message_handler.video_manager.is_playing and not self.image_is_fullscreen:
                Overlay.show_hint_cooldown(seconds_left)
        else:
            # Cooldown is complete
            self.hint_cooldown = False
            if self.cooldown_after_id:
                self.cooldown_after_id.stop()
                self.cooldown_after_id = None
            Overlay.hide_hint_cooldown()
            # Update help button immediately
            self.message_handler._actual_help_button_update()

    def show_video_solution(self, room_folder, video_filename):
        """Prepares and shows a video solution."""
        print(f"[qt_manager] Showing video solution: {room_folder}/{video_filename}")
        # Store the video info
        self.stored_video_info = {
            'room_folder': room_folder,
            'video_filename': video_filename
        }
        
        # Start cooldown for video solutions
        self.start_cooldown()
        
        # Show the video solution button
        Overlay.show_view_solution_button(self)
        
    def toggle_solution_video(self):
        """Toggles the solution video playback."""
        with self._lock:
            print("[qt_manager.toggle_solution_video] thread lock acquired")
            try:
                is_currently_playing = self.message_handler.video_manager.is_playing
                print(f"[qt_manager] Toggling solution video. Currently playing: {is_currently_playing}")

                if is_currently_playing:
                    print("[qt_manager.py] Stopping current video")
                    self.message_handler.video_manager.stop_video() # Should trigger on_complete if needed
                else:
                    print("[qt_manager.py] Starting video playback")
                    if hasattr(self, 'stored_video_info') and self.stored_video_info:
                        # Construct video path
                        video_path = os.path.join(
                            "video_solutions",
                            self.stored_video_info['room_folder'],
                            f"{self.stored_video_info['video_filename']}.mp4"
                        )

                        print(f"[qt_manager] Video path: {video_path}")
                        if os.path.exists(video_path):
                            print("[qt_manager] Playing video via VideoManager")
                            self.message_handler.video_manager.play_video(
                                video_path,
                                on_complete=self.handle_video_completion # Keep existing completion handler
                            )
                        else:
                            print(f"[qt_manager] Error: Video file not found at {video_path}")
                    else:
                        print("[qt_manager.py] Error: No video info stored")

            except Exception as e:
                print(f"[qt_manager] Error in toggle_solution_video: {e}")
                traceback.print_exc()
            finally:
                print("[qt_manager.toggle_solution_video] thread lock released")
        
    def handle_video_completion(self):
        """Handles the completion of video playback."""
        print("[qt_manager] Handling video completion (top-level window version)")
        try:
            # Only update help button state if needed
            QTimer.singleShot(50, lambda: self.message_handler._actual_help_button_update())
        except Exception as e:
            print(f"[qt_manager] Error in handle_video_completion: {e}")
            traceback.print_exc() 