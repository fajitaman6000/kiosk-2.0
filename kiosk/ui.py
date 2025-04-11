# ui.py
print("[ui] Beginning imports ...")
import tkinter as tk
from PIL import Image, ImageTk
import os
import base64
import io
import traceback
from qt_overlay import Overlay
import threading
print("[ui] Ending imports ...")

class KioskUI:
    def __init__(self, root, computer_name, room_config, message_handler):
        self.root = root
        self.computer_name = computer_name
        self.room_config = room_config
        self.message_handler = message_handler
        self.parent_app = message_handler
        
        self.background_image = None
        self.status_frame = None
        self.cooldown_label = None
        self.request_pending_label = None
        self.hint_label = None
        self.fullscreen_image = None
        self.image_button = None
        self.video_solution_button = None # keep the video solution button
        self._lock = threading.Lock()

        self.hint_cooldown = False
        self.current_hint = None
        self.cooldown_after_id = None
        self.stored_image_data = None

        self.image_is_fullscreen = False

        self.setup_root()
        self.create_status_frame()

        # Pass the Tkinter root window to Overlay.init()
        Overlay.init(tkinter_root=self.root)
        
    def setup_root(self):
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='black')
        #self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))

    def create_status_frame(self):
        """Creates a fixed canvas for status messages at coordinates (510,0) to (610,1079)"""
        # Create the status canvas
        self.status_frame = tk.Canvas(
            self.root,
            width=100,  # 610 - 510 = 100
            height=1079,
            bg='black',
            highlightthickness=0
        )
        # Initially hide the status frame
        self.status_frame.place_forget()
    
    def show_status_frame(self):
        """Shows the status frame and positions it correctly"""
        if self.status_frame:
            self.status_frame.place(x=510, y=0)

    def hide_status_frame(self):
        """Hides the status frame from view"""
        if self.status_frame:
            self.status_frame.place_forget()

    def load_background(self, room_number):
        if room_number not in self.room_config['backgrounds']:
            return None
            
        filename = self.room_config['backgrounds'][room_number]
        path = os.path.join("Backgrounds", filename)
        
        try:
            if os.path.exists(path):
                image = Image.open(path)
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                image = image.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
                return ImageTk.PhotoImage(image)
        except Exception as e:
            print(f"[ui.py]Error loading background: {str(e)}")
        return None
        
    def setup_waiting_screen(self):
        self.status_label = tk.Label(
            self.root, 
            text=f"Waiting for room assignment...\nComputer Name: {self.computer_name}",
            fg='white', bg='black', font=('Arial', 24)
        )
        self.status_label.place(relx=0.5, rely=0.5, anchor='center')
        
    def clear_all_labels(self):
        """Clear all UI elements and cancel any pending cooldown timer"""
        if self.cooldown_after_id:
            self.root.after_cancel(self.cooldown_after_id)
            self.cooldown_after_id = None
            
        self.hint_cooldown = False
        
        if self.status_frame:
            self.status_frame.delete('all')
            
        for widget in [self.hint_label]: # Removed self.help_button from here
            if widget:
                widget.destroy()
                
        self.hint_label = None
        
    def clear_hint_ui(self):
        """Clears Tkinter-related UI elements associated with hints."""
        print("[ui.py] Clearing Tkinter hint UI elements")

        # Clear any status frame content.
        if self.status_frame:
            self.status_frame.delete('all')
            self.hide_status_frame()
        print("[ui.clear_hint_ui] 1")
        # Clear image button.
        if hasattr(self, 'image_button') and self.image_button:
            self.image_button.destroy()
            self.image_button = None
        print("[ui.clear_hint_ui] 2")
        # Clear video solution button
        if hasattr(self, 'video_solution_button') and self.video_solution_button:
            self.video_solution_button.destroy()
            self.video_solution_button = None
        print("[ui.clear_hint_ui] 3")
        # Clear fullscreen image if shown
        if hasattr(self, 'fullscreen_image') and self.fullscreen_image:
            self.fullscreen_image.destroy()
            self.fullscreen_image = None
        print("[ui.clear_hint_ui] 4")

    def setup_room_interface(self, room_number):
        """Set up the room interface for the given room number"""
        # Clear any existing widgets except persistent ones
        for widget in self.root.winfo_children():
            # Skip destroying widgets marked as persistent
            if hasattr(widget, 'is_persistent'):
                continue
            # Skip status frame if it exists
            if widget is self.status_frame:
                continue
            widget.destroy()

        # Configure the room-specific elements
        if room_number > 0:
            self.current_room = room_number
            self.background_image = self.load_background(room_number)
            if self.background_image:
                bg_label = tk.Label(self.root, image=self.background_image)
                bg_label.place(x=0, y=0, relwidth=1, relheight=1)

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
                self.message_handler.root.after(100, lambda: self.message_handler._actual_help_button_update())
    
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
            
            # Show status frame and clear any existing text
            self.show_status_frame()
            self.status_frame.delete('pending_text')
            
            # Add rotated text to the canvas # DEPRECATED
            self.status_frame.create_text(
                50,  # center of width (100/2)
                540,  # center of height (1079/2)
                text="HINT REQUESTED\nPlease wait for your game master to evaluate your game",
                fill='yellow',
                font=('Arial', 24),
                angle=90,
                tags='pending_text',
                justify='center'
            )
            
            # Send help request
            self.message_handler.network.send_message({
                'type': 'help_request',
                **self.message_handler.get_stats()
            })

    def show_hint(self, text_or_data, start_cooldown=True):
        try:
            Overlay.hide_help_button()

            if self.fullscreen_image:
                self.fullscreen_image.destroy()
                self.fullscreen_image = None

            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                self.video_solution_button.destroy()
                self.video_solution_button = None

            if hasattr(self, 'video_is_playing') and self.video_is_playing:
                self.message_handler.video_manager.stop_video()
                self.video_is_playing = False

            if hasattr(self, 'stored_video_info'):
                self.stored_video_info = None

            if start_cooldown:
                self.start_cooldown()

            self.current_hint = text_or_data

            if self.request_pending_label:
                self.request_pending_label.destroy()
                self.request_pending_label = None

            if self.image_button:
                self.image_button.destroy()
                self.image_button = None

            hint_text = ""
            self.stored_image_data = None

            if isinstance(text_or_data, str):
                hint_text = text_or_data
            elif isinstance(text_or_data, dict):
                hint_text = text_or_data.get('text', '')
                self.stored_image_data = text_or_data.get('image')
            else:
                hint_text = str(text_or_data)

            if self.stored_image_data and not hint_text:
                hint_text = "Image hint received"

            Overlay.show_hint_text(hint_text, self.current_room)

            if self.stored_image_data:
                button_width = 100
                button_height = 300

                self.image_button = tk.Canvas(
                    self.root,
                    width=button_width,
                    height=button_height,
                    bg='blue',
                    highlightthickness=0
                )

                self.image_button.place(
                    x=750,
                    y= (1015-64)/2 - button_height/2 + 64
                )

                self.image_button.create_text(
                    button_width/2,
                    button_height/2,
                    text="VIEW IMAGE HINT",
                    fill='white',
                    font=('Arial', 24),
                    angle=270
                )
                self.image_button.bind('<Button-1>', lambda e: self.show_fullscreen_image())

        except Exception as e:
            print(f"[ui.py]Critical error in show_hint: {e}")
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
            # --- Remove Tkinter Canvas Creation ---
            # if self.fullscreen_image:
            #     self.fullscreen_image.destroy()
            #     self.fullscreen_image = None
            # ---

            # Hide Tkinter hint button if it exists (assuming it might still be tk)
            if self.image_button:
                 self.image_button.place_forget()

            # --- Call the Qt Overlay to handle display ---
            Overlay.show_fullscreen_hint(self.stored_image_data, self) # Pass self

            # --- Remove Tkinter Image Loading, Scaling, Rotating, Display ---
            # screen_width = self.root.winfo_screenwidth()
            # screen_height = self.root.winfo_screenheight()
            # margin = 50
            # self.fullscreen_image = tk.Canvas(...)
            # self.fullscreen_image.place(x=margin, y=0)
            # image_bytes = base64.b64decode(self.stored_image_data)
            # image = Image.open(io.BytesIO(image_bytes))
            # ... (ratio calculation, resize, rotate) ...
            # photo = ImageTk.PhotoImage(image)
            # self.fullscreen_image.photo = photo
            # self.fullscreen_image.create_image(...)
            # self.fullscreen_image.bind('<Button-1>', lambda e: self.restore_hint_view())
            # --- End Removed Tkinter Code ---

        except Exception as e:
            print("[ui.py]Error requesting fullscreen image overlay:")
            traceback.print_exc()
            self.image_is_fullscreen = False # Reset flag on error
            # Optionally try to restore view if overlay call failed badly
            # self.restore_hint_view()
        
    def restore_hint_view(self):
        """Restores the normal hint view after fullscreen Qt hint is closed."""
        print("[ui.py] Restoring hint view after Qt fullscreen hint.")
        self.image_is_fullscreen = False # Reset flag

        # --- Remove Tkinter Canvas Destruction ---
        # if self.fullscreen_image:
        #     self.fullscreen_image.destroy()
        #     self.fullscreen_image = None
        # ---

        # --- Determine Hint Text (Keep this logic) ---
        hint_text = ""
        if isinstance(self.current_hint, str):
            hint_text = self.current_hint
        elif isinstance(self.current_hint, dict):
            hint_text = self.current_hint.get('text', '')
            # Check if it was an image-only hint
            if self.current_hint.get('image') and not hint_text and self.stored_image_data:
                hint_text = "Image hint received" # Restore placeholder text
        # else: # Handle unexpected types if necessary
        #    hint_text = str(self.current_hint) if self.current_hint else ""

        # --- Restore Qt Hint Text Overlay ---
        # Make sure Overlay.show_all_overlays() called by hide_fullscreen_hint
        # handles showing the hint text if applicable.
        # We might still need to explicitly show it here if show_all_overlays isn't enough
        # or if the text needs re-setting. Let's assume show_all_overlays is sufficient for now.
        # If issues arise, uncomment and test this:
        if hint_text:
            print(f"[ui.py restore_hint_view] Showing hint text: '{hint_text}'")
            Overlay.show_hint_text(hint_text, self.current_room)
        else:
            print("[ui.py restore_hint_view] No hint text to restore, hiding hint overlay.")
            Overlay.hide_hint_text() # Explicitly hide if no text

        # --- Restore Tkinter Image Button (if it exists and belongs here) ---
        # This button might also become a Qt element later
        if self.image_button and self.stored_image_data: # Check if there *was* an image
             print("[ui.py] Restoring Tkinter image button.")
             button_height = 300 # Or get from original creation logic
             self.image_button.place(
                 x=750,
                 y= (1015-64)/2 - button_height/2 + 64 # Adjust coords as needed
             )
        elif self.image_button:
             # Destroy button if there's no image data to view anymore
             print("[ui.py] Destroying image button as there's no image data.")
             self.image_button.destroy()
             self.image_button = None

        # --- Restore Qt Help Button / Timer ---
        # These should be handled by Overlay.show_all_overlays(), but an explicit
        # update ensures the help button state is correct.
        print("[ui.py] Triggering help button update.")
        self.message_handler.root.after(50, lambda: self.message_handler._actual_help_button_update()) # Use small delay

        # Timer visibility check (redundant if show_all_overlays works, but safe)
        # if hasattr(Overlay, '_timer_window') and Overlay._timer_window:
        #    if not self.message_handler.video_manager.is_playing:
        #        print("[ui.py] Showing timer window.")
        #        Overlay._timer_window.show()

    def start_cooldown(self):
        """Start cooldown timer with matching overlay"""
        print("[ui.py]Starting cooldown timer")
        if self.cooldown_after_id:
            self.root.after_cancel(self.cooldown_after_id)
            self.cooldown_after_id = None
        
        self.hint_cooldown = True
        Overlay.show_hint_cooldown(10)  # Show initial cooldown
        self.update_cooldown(10)
        
    def update_cooldown(self, seconds_left):
        if seconds_left > 0 and self.hint_cooldown:
            if not self.message_handler.video_manager.is_playing and not self.image_is_fullscreen:
                Overlay.show_hint_cooldown(seconds_left)
            self.cooldown_after_id = self.root.after(
                1000,
                lambda: self.update_cooldown(seconds_left - 1)
            )
        else:
            self.hint_cooldown = False
            self.cooldown_after_id = None
            Overlay.hide_cooldown()
            self.message_handler.root.after(100, lambda: self.message_handler._actual_help_button_update()) # Removed and added lambda for thread safety

    def show_video_solution(self, room_folder, video_filename):
        """Shows a button to play the video solution, similar to image hints"""
        try:
            print(f"[ui.py]Showing video solution for {room_folder}/{video_filename}")
            
            # Store video info first
            self.stored_video_info = {
                'room_folder': room_folder,
                'video_filename': video_filename
            }
            
            # Safely remove existing button if it exists
            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                try:
                    self.video_solution_button.destroy()
                except:
                    pass
                self.video_solution_button = None
                
            # Create video solution button
            button_width = 100
            button_height = 400
            
            self.video_solution_button = tk.Canvas(
                self.root,
                width=button_width,
                height=button_height,
                bg='blue',
                highlightthickness=0
            )
            
            # Position button
            hint_height = 1015 - 64
            self.video_solution_button.place(
                x=750,
                y=hint_height/2 - button_height/2 + 64
            )
            
            # Add button text
            self.video_solution_button.create_text(
                button_width/2,
                button_height/2,
                text="VIEW SOLUTION",
                fill='white',
                font=('Arial', 24),
                angle=270
            )
            
            # Bind click event
            self.video_solution_button.bind('<Button-1>', lambda e: self.toggle_solution_video())
            print("[ui.py]Successfully created video solution button")
            
        except Exception as e:
            print(f"[ui.py]Error creating video solution button:")
            traceback.print_exc()
            self.stored_video_info = None
            self.video_solution_button = None

    def toggle_solution_video(self):
         """Toggle video solution playback while preserving cooldown state"""
         # Wrap the logic in a thread-safe lock
         with self._lock:
            print("[ui.toggle_solution_video] thread lock here")
            try:
                print("[ui.py]Toggling solution video")
                # If video is already playing, stop it
                if hasattr(self, 'video_is_playing') and self.video_is_playing:
                    print("[ui.py]Stopping current video")
                    self.message_handler.video_manager.stop_video()
                    self.video_is_playing = False
                    
                    # Restore the button
                    if hasattr(self, 'video_solution_button') and self.video_solution_button:
                        print("[ui.py]Restoring solution button")
                        self.video_solution_button.place(
                            x=750,
                            y=(1015 - 64)/2 - 100 + 64
                        )
                    
                    # Restore the text overlay
                    Overlay.show_hint_text(self.current_hint if isinstance(self.current_hint, str) else self.current_hint.get('text', ''), self.current_room)

                    # Restore cooldown display if still in cooldown
                    if self.hint_cooldown:
                        print("[ui.py]Restoring cooldown display")
                        self.show_status_frame()
                        
                # If video is not playing, start it
                else:
                    print("[ui.py]Starting video playback")
                    if hasattr(self, 'stored_video_info'):
                        # Store cooldown state before hiding UI
                        cooldown_items = self.status_frame.find_withtag('cooldown_text')
                        if cooldown_items:
                            self.stored_cooldown_text = self.status_frame.itemcget(cooldown_items[0], 'text')
                        else:
                            self.stored_cooldown_text = None
                        
                        # Only hide UI elements that exist
                        Overlay.hide_hint_text()
                        
                        if hasattr(self, 'video_solution_button') and self.video_solution_button:
                            print("[ui.py]Hiding solution button")
                            self.video_solution_button.place_forget()
                            
                        if self.hint_cooldown:
                            self.status_frame.place_forget()
                            
                        # Construct video path
                        video_path = os.path.join(
                            "video_solutions",
                            self.stored_video_info['room_folder'],
                            f"{self.stored_video_info['video_filename']}.mp4"
                        )
                        
                        print(f"[ui.py]Video path: {video_path}")
                        if os.path.exists(video_path):
                            print("[ui.py]Playing video")
                            self.video_is_playing = True
                            self.message_handler.video_manager.play_video(
                                video_path,
                                on_complete=self.handle_video_completion
                            )
                        else:
                            print(f"[ui.py]Error: Video file not found at {video_path}")
                    else:
                        print("[ui.py]Error: No video info stored")
                        
            except Exception as e:
                print(f"[ui.py]Error in toggle_solution_video: {e}")
                traceback.print_exc()

    def handle_video_completion(self):
        """Handle cleanup after video finishes playing while maintaining cooldown state"""
        print("[ui.py]Handling video completion")
        self.video_is_playing = False

        try:
            # Store video info before cleanup
            stored_video_info = None
            if hasattr(self, 'stored_video_info') and self.stored_video_info:
                stored_video_info = self.stored_video_info.copy()

            # Store cooldown state
            was_in_cooldown = self.hint_cooldown
            cooldown_after_id = self.cooldown_after_id

            # Clear UI state without affecting cooldown
            print("[ui.py]Clearing UI state...")
            # Don't call clear_all_labels() as it would reset cooldown
            Overlay.hide_hint_text()
            Overlay.hide_help_button()  # Replaced help button removal with this
            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                self.video_solution_button.destroy()
                self.video_solution_button = None

            # Restore room interface - this will properly recreate the hint display area
            if self.message_handler.assigned_room:
                print("[ui.py]Restoring room interface")
                self.setup_room_interface(self.message_handler.assigned_room)

                # Restore hint text *after* setup_room_interface
                if self.current_hint:
                    print("[ui.py]Restoring hint text")
                    hint_text = self.current_hint if isinstance(self.current_hint, str) else self.current_hint.get('text', '')
                    Overlay.show_hint_text(hint_text, self.message_handler.assigned_room)

                # If we had a video solution, create a fresh button
                if stored_video_info:
                    print("[ui.py]Creating fresh video solution button")
                    self.show_video_solution(
                        stored_video_info['room_folder'],
                        stored_video_info['video_filename']
                    )
            # Restore cooldown state if it was active
            if was_in_cooldown:
                print("[ui.py]Restoring cooldown state")
                self.hint_cooldown = True
                self.cooldown_after_id = cooldown_after_id
                self.show_status_frame()
                if hasattr(self, 'stored_cooldown_text') and self.stored_cooldown_text:
                    self.status_frame.create_text(
                        50,
                        540,
                        text=self.stored_cooldown_text,
                        fill='yellow',
                        font=('Arial', 24),
                        angle=270,
                        tags='cooldown_text',
                        justify='center',
                        width=1000
                    )
            else:
                # Only refresh help button if not in cooldown
                self.message_handler.root.after(100, lambda: self.message_handler._actual_help_button_update()) # Removed and added lambda for thread safety

        except Exception as e:
            print(f"[ui.py]Error in handle_video_completion: {e}")
            traceback.print_exc()