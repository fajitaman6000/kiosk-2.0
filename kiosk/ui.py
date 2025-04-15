# ui.py
print("[ui] Beginning imports ...")
from PIL import Image, ImageTk
import os
import base64
import io
import traceback
from qt_overlay import Overlay
import threading
from PyQt5.QtCore import QTimer # Import for delayed execution
print("[ui] Ending imports ...")

class KioskUI:
    def __init__(self, root, computer_name, room_config, message_handler):
        # root parameter kept for compatibility but no longer used
        self.computer_name = computer_name
        self.room_config = room_config
        self.message_handler = message_handler
        self.parent_app = message_handler
        
        self.background_image = None
        self.cooldown_label = None
        self.request_pending_label = None
        self.hint_label = None
        self.fullscreen_image = None
        self._lock = threading.Lock()

        self.hint_cooldown = False
        self.current_hint = None
        self.cooldown_after_id = None
        self.stored_image_data = None
        self.image_button = None  # Keep for compatibility
        self.image_is_fullscreen = False

        # Initialize the Qt overlay
        Overlay.init()
        
    def setup_root(self):
        # No longer needed with Qt
        pass

    def load_background(self, room_number):
        if room_number not in self.room_config['backgrounds']:
            return None
            
        filename = self.room_config['backgrounds'][room_number]
        path = os.path.join("Backgrounds", filename)
        
        try:
            if os.path.exists(path):
                return path
        except Exception as e:
            print(f"[ui.py]Error loading background: {str(e)}")
        return None
        
    def setup_waiting_screen(self):
        # Clear any existing room background/widgets first
        # No need to clear Tkinter widgets since we don't have any
        
        # Use the Qt Overlay for the waiting screen
        Overlay.show_waiting_screen_label(self.computer_name)
        
    def clear_all_labels(self):
        """Clear all UI elements and cancel any pending cooldown timer"""
        if self.cooldown_after_id:
            # Set the hint_cooldown to False to prevent further cooldown actions
            self.hint_cooldown = False
            self.cooldown_after_id = None
            
        self.hint_cooldown = False
        
        # No longer need to destroy Tkinter widgets
        self.hint_label = None
        
    def clear_hint_ui(self):
        """Clears hint UI elements and hides Qt elements."""
        print("[ui.py] Clearing hint UI elements and hiding Qt counterparts")

        # Hide Qt Hint Text/Buttons
        Overlay.hide_hint_text()
        Overlay.hide_view_image_button()
        Overlay.hide_view_solution_button()

    def setup_room_interface(self, room_number):
        """Set up the room interface for the given room number"""
        # Ensure the waiting screen label is hidden
        Overlay.hide_waiting_screen_label()

        # No need to clear Tkinter widgets

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
                    print("[ui.py]Restoring non-empty hint within setup_room_interface")
                    Overlay.show_hint_text(hint_text, self.current_room)
            else:
                # If there's NO current hint, then update the help button.
                print("[ui.py]No current hint, updating help button within setup_room_interface")
                # Use QTimer.singleShot
                QTimer.singleShot(100, lambda: self.message_handler._actual_help_button_update())
    
    def request_help(self):
        """Creates the 'Hint Requested' message in the status frame and clears any existing hints"""
        if not self.hint_cooldown:
            # Increase hint count
            if hasattr(self.message_handler, 'hints_requested'):
                self.message_handler.hints_requested += 1
            
            # Clear any existing hint display
            if self.hint_label:
                self.hint_label.destroy()
                self.hint_label = None
                self.current_hint = None
            
            # Remove help button if it exists
            Overlay.hide_help_button() # Replaced with this
            
            # Send help request
            self.message_handler.network.send_message({
                'type': 'help_request',
                **self.message_handler.get_stats()
            })

    def show_hint(self, text_or_data, start_cooldown=True):
        try:
            print("[ui.py show_hint] Showing hint...")
            Overlay.hide_help_button() # Hide main help button

            # Cleanup previous hint UI elements
            if self.fullscreen_image:
                self.fullscreen_image.destroy()
                self.fullscreen_image = None

            Overlay.hide_view_solution_button()

            # If video was playing, stop it (This logic seems less relevant here, maybe belongs elsewhere?)
            if hasattr(self.message_handler.video_manager, 'is_playing') and self.message_handler.video_manager.is_playing:
                 print("[ui.py show_hint] Warning: Stopping video playback because new hint arrived.")
                 self.message_handler.video_manager.stop_video()
                 # self.video_is_playing should be managed by video_manager callbacks

            # Clear stored video info if a new hint arrives
            self.stored_video_info = None

            if start_cooldown:
                self.start_cooldown() # Starts Qt cooldown overlay via Overlay.show_hint_cooldown

            self.current_hint = text_or_data # Store the new hint data

            Overlay.hide_hint_request_text() # Already handled by kiosk.py usually, but safe to call

            Overlay.hide_view_image_button()

            # Process hint data
            hint_text = ""
            self.stored_image_data = None # Reset stored image data

            if isinstance(text_or_data, str):
                hint_text = text_or_data
            elif isinstance(text_or_data, dict):
                hint_text = text_or_data.get('text', '')
                self.stored_image_data = text_or_data.get('image') # Store potential image data
            else:
                # Fallback if unexpected data type
                hint_text = str(text_or_data)
                print(f"[ui.py show_hint] Warning: Received hint data of unexpected type: {type(text_or_data)}")

            # Use placeholder if only image exists
            if self.stored_image_data and not hint_text:
                hint_text = "Image hint received" # Placeholder text

            # Show hint text via Qt Overlay
            print(f"[ui.py show_hint] Showing hint text: '{hint_text}'")
            Overlay.show_hint_text(hint_text, self.current_room)

            # --- Show Qt image button if image data exists ---
            if self.stored_image_data:
                print("[ui.py show_hint] Stored image data found, showing View Image button.")
                Overlay.show_view_image_button(self) # Pass self (ui_instance)
            # --- End Qt image button logic ---

        except Exception as e:
            print(f"[ui.py] Critical error in show_hint: {e}")
            traceback.print_exc()
            
    def show_fullscreen_image(self):
        """Display the image in nearly fullscreen using Qt Overlay"""
        print("[ui.py] Requesting Qt Overlay for fullscreen image.")
        self.image_is_fullscreen = True  # Set the flag FIRST
        if not self.stored_image_data:
            print("[ui.py] No stored image data to show.")
            self.image_is_fullscreen = False # Reset if no data
            return

        try:
            # Hide Tkinter hint button if it exists (assuming it might still be tk)
            if self.image_button:
                 self.image_button.place_forget()

            # Call the Qt Overlay to handle display
            Overlay.show_fullscreen_hint(self.stored_image_data, self) # Pass self

        except Exception as e:
            print("[ui.py]Error requesting fullscreen image overlay:")
            traceback.print_exc()
            self.image_is_fullscreen = False # Reset flag on error
        
    def restore_hint_view(self):
        """Restores the normal hint view after fullscreen Qt hint is closed."""
        print("[ui.py] Restoring hint view after Qt fullscreen hint.")
        self.image_is_fullscreen = False # Reset flag

        # Determine Hint Text (Keep this logic)
        hint_text = ""
        image_data_exists = False
        video_info_exists = False # Check if video info exists

        if isinstance(self.current_hint, str):
            hint_text = self.current_hint
        elif isinstance(self.current_hint, dict):
            hint_text = self.current_hint.get('text', '')
            image_data_exists = bool(self.current_hint.get('image')) # Check if image key exists
            if image_data_exists and not hint_text:
                hint_text = "Image hint received" # Restore placeholder text

        # Also check separately if video solution info is stored
        video_info_exists = bool(self.stored_video_info)

        # --- Trigger General UI Update ---
        # This ensures overlays (including side buttons) are shown/hidden correctly
        # based on the current state after the fullscreen hint is gone.
        print("[ui.py restore_hint_view] Triggering show_all_overlays.")
        # It's better if hide_fullscreen_hint calls show_all_overlays directly.
        # If not, call it here:
        # Overlay.show_all_overlays() # Ensure this gets called

        # Update help button state as well
        print("[ui.py restore_hint_view] Triggering help button update.")
        # Replace root.after with QTimer.singleShot
        QTimer.singleShot(50, lambda: self.message_handler._actual_help_button_update())

    def start_cooldown(self):
        """Start cooldown timer with matching overlay"""
        print("[ui.py]Starting cooldown timer")
        if self.cooldown_after_id:
            # Replace root.after_cancel with setting the flag to False
            self.hint_cooldown = False
            self.cooldown_after_id = None
        
        self.hint_cooldown = True
        Overlay.show_hint_cooldown(10)  # Show initial cooldown
        self.update_cooldown(10)
        
    def update_cooldown(self, seconds_left):
        if seconds_left > 0 and self.hint_cooldown:
            if not self.message_handler.video_manager.is_playing and not self.image_is_fullscreen:
                Overlay.show_hint_cooldown(seconds_left)
            # Replace root.after with QTimer.singleShot
            QTimer.singleShot(1000, lambda: self.update_cooldown(seconds_left - 1))
        else:
            self.hint_cooldown = False
            self.cooldown_after_id = None
            Overlay.hide_cooldown()
            # Replace root.after with QTimer.singleShot
            QTimer.singleShot(100, lambda: self.message_handler._actual_help_button_update())

    def show_video_solution(self, room_folder, video_filename):
        """Stores video info and shows the Qt 'View Solution' button."""
        try:
            print(f"[ui.py] Preparing video solution for {room_folder}/{video_filename}")

            # Store video info first
            self.stored_video_info = {
                'room_folder': room_folder,
                'video_filename': video_filename
            }

            # --- Show the Qt button instead ---
            Overlay.show_view_solution_button(self) # Pass self (ui_instance)
            print("[ui.py] Successfully requested Qt video solution button")

        except Exception as e:
            print(f"[ui.py] Error preparing video solution button:")
            traceback.print_exc()
            self.stored_video_info = None # Clear info on error
            Overlay.hide_view_solution_button() # Ensure button is hidden on error

    def toggle_solution_video(self):
         """Toggle video solution playback using Qt overlays"""
         with self._lock:
            print("[ui.toggle_solution_video] thread lock acquired")
            try:
                is_currently_playing = self.message_handler.video_manager.is_playing
                print(f"[ui.py] Toggling solution video. Currently playing: {is_currently_playing}")

                if is_currently_playing:
                    print("[ui.py] Stopping current video")
                    self.message_handler.video_manager.stop_video() # Should trigger on_complete if needed

                    # VideoManager's on_complete (handle_video_completion) should restore UI.
                    # We don't need to manually restore buttons/text here anymore.

                else:
                    print("[ui.py] Starting video playback")
                    if hasattr(self, 'stored_video_info') and self.stored_video_info:

                        # Hide hint text and the solution button itself via Overlay
                        Overlay.hide_hint_text()
                        Overlay.hide_view_solution_button()
                        # Also hide image button if present
                        Overlay.hide_view_image_button()

                        # Construct video path
                        video_path = os.path.join(
                            "video_solutions",
                            self.stored_video_info['room_folder'],
                            f"{self.stored_video_info['video_filename']}.mp4"
                        )

                        print(f"[ui.py] Video path: {video_path}")
                        if os.path.exists(video_path):
                            print("[ui.py] Playing video via VideoManager")
                            # self.video_is_playing = True # Let VideoManager handle state
                            self.message_handler.video_manager.play_video(
                                video_path,
                                on_complete=self.handle_video_completion # Keep existing completion handler
                            )
                        else:
                            print(f"[ui.py] Error: Video file not found at {video_path}")
                            # If video fails to start, restore the UI immediately
                            Overlay.show_all_overlays() # Restore relevant overlays
                    else:
                        print("[ui.py] Error: No video info stored")

            except Exception as e:
                print(f"[ui.py] Error in toggle_solution_video: {e}")
                traceback.print_exc()
            finally:
                 print("[ui.toggle_solution_video] thread lock released")

    def handle_video_completion(self):
        """Handle cleanup after video finishes, restoring Qt overlays"""
        print("[ui.py] Handling video completion (Qt version)")
        # self.video_is_playing = False # State managed by VideoManager

        try:
            # --- Rely on show_all_overlays to restore correct state ---
            print("[ui.py handle_video_completion] Triggering show_all_overlays")
            # This should show hint text, appropriate side buttons (image/video), timer, help button etc.
            # Ensure show_all_overlays correctly checks stored_image_data and stored_video_info
            Overlay.show_all_overlays()

            # Ensure help button state is correct (show_all_overlays might call update_help_button)
            # If not, trigger it explicitly AFTER show_all_overlays has potentially run
            # Replace root.after with QTimer.singleShot
            QTimer.singleShot(50, lambda: self.message_handler._actual_help_button_update())

        except Exception as e:
            print(f"[ui.py] Error in handle_video_completion: {e}")
            traceback.print_exc()