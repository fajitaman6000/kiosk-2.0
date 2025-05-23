# qt_manager.py
print("[qt_manager] Beginning imports ...", flush=True)
print("[qt_manager] Importing os...", flush=True)
import os
print("[qt_manager] Imported os.", flush=True)
print("[qt_manager] Importing threading...", flush=True)
import threading
print("[qt_manager] Imported threading.", flush=True)
print("[qt_manager] Importing traceback...", flush=True)
import traceback
print("[qt_manager] Imported traceback.", flush=True)
print("[qt_manager] Importing qt_overlay...", flush=True)
from qt_overlay import Overlay
print("[qt_manager] Imported qt_overlay.", flush=True)
print("[qt_manager] Importing PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import QTimer, QObject, pyqtSlot, QMetaObject, Qt, Q_ARG
print("[qt_manager] Imported PyQt5.QtCore.", flush=True)
print("[qt_manager] Importing base64...", flush=True)
import base64
print("[qt_manager] Imported base64.", flush=True)
print("[qt_manager] Importing json...", flush=True)
import json
print("[qt_manager] Imported json.", flush=True)
print("[qt_manager] Ending imports ...", flush=True)

class QtManager:
    def __init__(self, computer_name, room_config, message_handler):
        print("[qt_manager] Initializing QtManager...", flush=True)
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
        self.last_displayed_hint_image_filename = None  # Store just the filename of the last displayed image

        # Load room themes once
        try:
            with open(os.path.join(os.path.dirname(__file__), 'room_themes.json'), 'r') as f:
                self.room_themes = json.load(f)
        except Exception as e:
            print(f"[qt_manager] Error loading room_themes.json: {e}", flush=True)
            self.room_themes = {}
        self.current_theme = None

        # Register this instance with the overlay for callbacks
        self.register_with_overlay()

        # Initialize the Qt overlay if not already initialized
        print("[qt_manager] Initializing Qt overlay...", flush=True)
        Overlay.init()
        print("[qt_manager] Qt overlay initialized.", flush=True)
        print("[qt_manager] QtManager initialization complete.", flush=True)

    def register_with_overlay(self):
        """Register this instance with the overlay for callbacks."""
        print("[qt_manager] Registering with overlay for callbacks...", flush=True)
        # Use the _on_view_image_button_clicked and _on_view_solution_button_clicked 
        # static methods from Overlay, but have them call methods in this class
        Overlay.register_ui_manager(self)
        print("[qt_manager] Registered with overlay.", flush=True)

    def on_view_image_clicked(self):
        """Handler for view image button clicks."""
        print("[qt_manager] View image button clicked", flush=True)
        if self.stored_image_data:
            self.show_fullscreen_image()
        else:
            print("[qt_manager] No image data to show", flush=True)

    def on_view_solution_clicked(self):
        """Handler for view solution button clicks."""
        print("[qt_manager] View solution button clicked", flush=True)
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
            print(f"[qt_manager] Error loading background: {str(e)}", flush=True)
        return None
        
    def setup_waiting_screen(self):
        # Use the Qt Overlay for the waiting screen
        print("[qt_manager] Setting up waiting screen...", flush=True)
        Overlay.show_waiting_screen_label(self.computer_name)
        print("[qt_manager] Waiting screen set up.", flush=True)
        
    def clear_all_labels(self):
        """Clear all UI elements and cancel any pending cooldown timer"""
        if(self.message_handler.UI_DEBUG): print("[qt_manager] Clearing all labels...", flush=True)
        if self.cooldown_after_id:
            # Cancel any running QTimer
            self.cooldown_after_id.stop()
            self.cooldown_after_id = None
            
        self.hint_cooldown = False
        if(self.message_handler.UI_DEBUG): print("[qt_manager] All labels cleared.", flush=True)
        
    def clear_hint_ui(self):
        """Clears hint UI elements and hides Qt elements."""
        if(self.message_handler.UI_DEBUG): print("[qt_manager] Clearing hint UI elements and hiding Qt counterparts", flush=True)

        # Hide Qt Hint Text/Buttons
        Overlay.hide_hint_text()
        Overlay.hide_view_image_button()
        Overlay.hide_view_solution_button()

        # Clear hint text content directly (don't use QMetaObject.invokeMethod which causes errors)
        if hasattr(Overlay, '_hint_text') and Overlay._hint_text and 'text_item' in Overlay._hint_text:
            try:
                # Direct call instead of using QMetaObject.invokeMethod
                Overlay._hint_text['text_item'].setPlainText("")
                if(self.message_handler.UI_DEBUG):print("[qt_manager] Cleared hint text content", flush=True)
            except Exception as e:
                print(f"[qt_manager] Error clearing hint text: {e}", flush=True)
            
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
        if(self.message_handler.UI_DEBUG):print("[qt_manager] Hint UI cleared.", flush=True)

    def get_current_theme(self):
        """Return the theme dict for the current room, or a default if not found."""
        if not self.current_room:
            return {"hint_text_color": "#ffffff", "timer_text_color": "#ffffff"}
        theme = self.room_themes.get(str(self.current_room))
        if theme is None:
            return {"hint_text_color": "#ffffff", "timer_text_color": "#ffffff"}
        return theme

    def setup_room_interface(self, room_number):
        """Set up the room interface for the given room number"""
        print(f"[qt_manager] Setting up room interface for room {room_number}...", flush=True)
        # Ensure the waiting screen label is hidden
        Overlay.hide_waiting_screen_label()

        # Configure the room-specific elements
        if room_number > 0:
            self.current_room = room_number
            # Update current theme for this room
            self.current_theme = self.get_current_theme()
            # Set theme colors in Overlay
            Overlay.set_theme_colors(
                self.current_theme.get("hint_text_color", "#ffffff"),
                self.current_theme.get("timer_text_color", "#ffffff")
            )
            
            # Get background path and set background using Qt overlay
            background_path = self.load_background(room_number)
            if background_path:
                # Use Qt to render the background
                print(f"[qt_manager] Setting background image: {background_path}", flush=True)
                Overlay.set_background_image(background_path)

            # Load room-specific timer background
            print(f"[qt_manager] Loading timer background for room {room_number}", flush=True)
            self.message_handler.timer.load_room_background(room_number)

            # Show the timer if it exists
            if hasattr(self.message_handler, 'timer'):
                print("[qt_manager] Updating timer display", flush=True)
                Overlay.update_timer_display(self.message_handler.timer.get_time_str())

            # Conditional Help Button and Hint Restore ---
            # Only update the help button OR restore the hint if there is an active hint.
            if self.current_hint is not None:
                hint_text = self.current_hint if isinstance(self.current_hint, str) else self.current_hint.get('text', '')
                # Check again here, just before showing the hint.
                if hint_text is not None and hint_text.strip() != "":
                    print("[qt_manager] Restoring non-empty hint within setup_room_interface", flush=True)
                    Overlay.show_hint_text(hint_text, self.current_room)
            else:
                # If there's NO current hint, then update the help button.
                print("[qt_manager] No current hint, updating help button within setup_room_interface", flush=True)
                # Use QTimer.singleShot
                QTimer.singleShot(100, lambda: self.message_handler._actual_help_button_update())
        print(f"[qt_manager] Room interface setup complete for room {room_number}.", flush=True)
    
    def request_help(self):
        """Creates the 'Hint Requested' message without clearing existing hints"""
        print("[qt_manager] Requesting help...", flush=True)
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
            print("[qt_manager] Help request sent.", flush=True)

    def get_last_displayed_hint_image_filename(self):
        """Return the filename of the last displayed hint image, or None."""
        return self.last_displayed_hint_image_filename

    def show_hint(self, text_or_data, start_cooldown=True):
        try:
            print("[qt_manager] Showing hint...", flush=True)
            Overlay.hide_help_button() # Hide main help button

            # If video was playing, stop it
            if hasattr(self.message_handler.video_manager, 'is_playing') and self.message_handler.video_manager.is_playing:
                 print("[qt_manager] Warning: Stopping video playback because new hint arrived.", flush=True)
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
            self.last_displayed_hint_image_filename = None
            if isinstance(text_or_data, str):
                hint_text = text_or_data
            elif isinstance(text_or_data, dict):
                hint_text = text_or_data.get('text', '')
                self.stored_image_data = text_or_data.get('image') # Store potential image data
                # If image is a path or filename, store just the filename
                img_val = text_or_data.get('image', None) or text_or_data.get('image_path', None)
                if isinstance(img_val, str):
                    self.last_displayed_hint_image_filename = os.path.basename(img_val)
                elif isinstance(img_val, dict):
                    self.last_displayed_hint_image_filename = img_val.get('filename', None) or img_val.get('name', None)
                else:
                    self.last_displayed_hint_image_filename = None
            else:
                # Fallback if unexpected data type
                hint_text = str(text_or_data)
                print(f"[qt_manager] Warning: Received hint data of unexpected type: {type(text_or_data)}", flush=True)

            # Use placeholder if only image exists
            if self.stored_image_data and not hint_text:
                hint_text = "Image hint received" # Placeholder text

            # Show hint text via Qt Overlay
            print(f"[qt_manager] Showing hint text: '{hint_text}'", flush=True)
            Overlay.show_hint_text(hint_text, self.current_room, priority=self.stored_image_data is not None)

            # --- Show Qt image button if image data exists ---
            if self.stored_image_data:
                print("[qt_manager] Stored image data found, showing View Image button.", flush=True)
                Overlay.show_view_image_button(self) # Pass self (qt_manager_instance)
            
            print("[qt_manager] Hint display complete.", flush=True)

        except Exception as e:
            print(f"[qt_manager] Critical error in show_hint: {e}", flush=True)
            traceback.print_exc()
            
    def show_fullscreen_image(self):
        """Display the image in nearly fullscreen using Qt Overlay"""
        print("[qt_manager] Requesting Qt Overlay for fullscreen image.", flush=True)
        self.image_is_fullscreen = True  # Set the flag FIRST
        if not self.stored_image_data:
            print("[qt_manager] No stored image data to show.", flush=True)
            self.image_is_fullscreen = False # Reset if no data
            return

        try:
            # Call the Qt Overlay to handle display
            Overlay.show_fullscreen_hint(self.stored_image_data, self) # Pass self
        except Exception as e:
            print("[qt_manager] Error requesting fullscreen image overlay:", flush=True)
            traceback.print_exc()
            self.image_is_fullscreen = False # Reset flag on error
        
    def restore_hint_view(self):
        """Restores the normal hint view after fullscreen Qt hint is closed."""
        print("[qt_manager] Restoring hint view after Qt fullscreen hint.", flush=True)
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
        
        print("[qt_manager] Hint view restoration complete.", flush=True)

    def start_cooldown(self):
        """Starts the hint cooldown timer and displays the cooldown message."""
        print("[qt_manager] Starting hint cooldown...", flush=True)
        
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
        print("[qt_manager] Creating cooldown QTimer...", flush=True)
        self.cooldown_after_id = QTimer()
        self.cooldown_after_id.timeout.connect(lambda: self.update_cooldown())
        self.cooldown_after_id.start(1000)  # Update every second
        print("[qt_manager] Cooldown QTimer started.", flush=True)
        
        # Store the end time to have a single source of truth
        self.cooldown_end_time = cooldown_seconds
        self.cooldown_current_time = cooldown_seconds
        
        print("[qt_manager] Hint cooldown initialized with {cooldown_seconds} seconds.", flush=True)

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
            print("[qt_manager] Cooldown complete.", flush=True)
            self.hint_cooldown = False
            if self.cooldown_after_id:
                self.cooldown_after_id.stop()
                self.cooldown_after_id = None
            Overlay.hide_hint_cooldown()
            # Update help button immediately
            self.message_handler._actual_help_button_update()

    def show_video_solution(self, room_folder, video_filename):
        """Prepares and shows a video solution."""
        print(f"[qt_manager] Showing video solution: {room_folder}/{video_filename}", flush=True)
        # Store the video info
        self.stored_video_info = {
            'room_folder': room_folder,
            'video_filename': video_filename
        }
        
        # Start cooldown for video solutions
        self.start_cooldown()
        
        # Show the video solution button
        Overlay.show_view_solution_button(self)
        print("[qt_manager] Video solution prepared.", flush=True)
        
    def toggle_solution_video(self):
        """Toggles the solution video playback."""
        with self._lock:
            print("[qt_manager.toggle_solution_video] thread lock acquired", flush=True)
            try:
                is_currently_playing = self.message_handler.video_manager.is_playing
                print(f"[qt_manager] Toggling solution video. Currently playing: {is_currently_playing}", flush=True)

                if is_currently_playing:
                    print("[qt_manager.py] Stopping current video", flush=True)
                    self.message_handler.video_manager.stop_video() # Should trigger on_complete if needed
                else:
                    print("[qt_manager.py] Starting video playback", flush=True)
                    if hasattr(self, 'stored_video_info') and self.stored_video_info:
                        # Construct video path
                        video_path = os.path.join(
                            "video_solutions",
                            self.stored_video_info['room_folder'],
                            f"{self.stored_video_info['video_filename']}.mp4"
                        )

                        print(f"[qt_manager] Video path: {video_path}", flush=True)
                        if os.path.exists(video_path):
                            print("[qt_manager] Playing video via VideoManager", flush=True)
                            self.message_handler.video_manager.play_video(
                                video_path,
                                on_complete=self.handle_video_completion # Keep existing completion handler
                            )
                        else:
                            print(f"[qt_manager] Error: Video file not found at {video_path}", flush=True)
                    else:
                        print("[qt_manager.py] Error: No video info stored", flush=True)

            except Exception as e:
                print(f"[qt_manager] Error in toggle_solution_video: {e}", flush=True)
                traceback.print_exc()
            finally:
                print("[qt_manager.toggle_solution_video] thread lock released", flush=True)
        
    def handle_video_completion(self):
        """Handles the completion of video playback."""
        print("[qt_manager] Handling video completion (top-level window version)", flush=True)
        try:
            # Only update help button state if needed
            QTimer.singleShot(50, lambda: self.message_handler._actual_help_button_update())
        except Exception as e:
            print(f"[qt_manager] Error in handle_video_completion: {e}", flush=True)
            traceback.print_exc() 