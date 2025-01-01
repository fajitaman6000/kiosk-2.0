# ui.py
import tkinter as tk
from PIL import Image, ImageTk
import os
import base64
import io
import traceback

class KioskUI:
    def __init__(self, root, computer_name, room_config, message_handler):
        self.root = root
        self.computer_name = computer_name
        self.room_config = room_config
        self.message_handler = message_handler
        
        self.background_image = None
        self.hint_cooldown = False
        self.help_button = None
        self.status_frame = None
        self.cooldown_label = None
        self.request_pending_label = None
        self.current_hint = None
        self.hint_label = None
        self.cooldown_after_id = None
        self.fullscreen_image = None
        self.image_button = None
        self.stored_image_data = None

        self.setup_root()
        self.create_status_frame()
        
    def setup_root(self):
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='black')
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        
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
            print(f"Error loading background: {str(e)}")
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
            
        for widget in [self.hint_label, self.help_button]:
            if widget:
                widget.destroy()
                
        self.hint_label = None
        self.help_button = None
        
    def setup_room_interface(self, room_number):
        # Store any existing status messages before clearing
        pending_text = None
        cooldown_text = None
        
        if self.status_frame:
            try:
                # Try to get pending text
                pending_items = self.status_frame.find_withtag('pending_text')
                if pending_items:
                    pending_text = self.status_frame.itemcget(pending_items[0], 'text')
                
                # Try to get cooldown text
                cooldown_items = self.status_frame.find_withtag('cooldown_text')
                if cooldown_items:
                    cooldown_text = self.status_frame.itemcget(cooldown_items[0], 'text')
            except:
                pass  # Ignore any errors trying to get old text
        
        # Clear all widgets except timer frame
        for widget in self.root.winfo_children():
            if widget is not self.message_handler.timer.timer_frame:
                widget.destroy()
        
        # Recreate status frame
        self.create_status_frame()
        
        # Restore any status messages that existed
        if pending_text:
            self.status_frame.create_text(
                50,  # center of width (100/2)
                540,  # center of height (1079/2)
                text=pending_text,
                fill='yellow',
                font=('Arial', 24),
                angle=270,
                tags='pending_text',
                justify='center'
            )
        
        if cooldown_text:
            self.status_frame.create_text(
                50,  # center of width (100/2)
                540,  # center of height (1079/2)
                text=cooldown_text,
                fill='yellow',
                font=('Arial', 24),
                angle=270,
                tags='cooldown_text',
                justify='center',
                width=1000
            )
        
        # Set up background first
        self.background_image = self.load_background(room_number)
        if self.background_image:
            background_label = tk.Label(self.root, image=self.background_image)
            background_label.place(x=0, y=0, relwidth=1, relheight=1)
            background_label.lower()  # Ensure background stays at the bottom
        
        # Load room-specific timer background
        self.message_handler.timer.load_room_background(room_number)
        
        # Restore hint if there was one
        if self.current_hint:
            self.show_hint(self.current_hint)
        
        # Restore help button if not in cooldown
        if not self.hint_cooldown:
            self.create_help_button()
        
        # Ensure timer stays on top
        self.message_handler.timer.lift_to_top()

    def _create_button_with_background(self):
        """Helper method to create the actual button with background"""
        # Define button dimensions
        canvas_width = 260
        canvas_height = 550
        
        try:
            # Get room-specific button background name
            button_name = None
            if hasattr(self.message_handler, 'assigned_room'):
                room_num = self.message_handler.assigned_room
                button_map = {
                    1: "casino_heist.png",
                    2: "morning_after.png",
                    3: "wizard_trials.png",
                    4: "zombie_outbreak.png",
                    5: "haunted_manor.png",
                    6: "atlantis_rising.png",
                    7: "time_machine.png"
                }
                if room_num in button_map:
                    button_name = button_map[room_num]

            if button_name:
                button_path = os.path.join("hint_button_backgrounds", button_name)
                if os.path.exists(button_path):
                    button_image = Image.open(button_path)
                    aspect_ratio = button_image.width / button_image.height
                    new_height = canvas_height
                    new_width = int(new_height * aspect_ratio)
                    button_image = button_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    button_photo = ImageTk.PhotoImage(button_image)
                    
                    self.help_button = tk.Canvas(
                        self.root,
                        width=canvas_width,
                        height=canvas_height,
                        highlightthickness=0
                    )
                    self.help_button.button_image = button_photo
                    
                    self.help_button.create_image(
                        canvas_width/2,
                        canvas_height/2,
                        image=button_photo,
                        anchor='center'
                    )
                    
                    self.help_button.place(relx=0.19, rely=0.5, anchor='center')
                    self.help_button.bind('<Button-1>', lambda e: self.request_help())
                    print("Successfully created new help button")
                else:
                    print(f"Button image not found at: {button_path}")
                    self._create_fallback_button(canvas_width, canvas_height)
            else:
                print("No room assigned or room number not in button map")
                self._create_fallback_button(canvas_width, canvas_height)
        except Exception as e:
            print(f"Error creating image button: {str(e)}")
            self._create_fallback_button(canvas_width, canvas_height)
            
    def create_help_button(self):
        """Creates the help request button using a room-specific background image if conditions are met"""
        # Get current timer value from message handler
        current_time = self.message_handler.timer.time_remaining
        minutes_remaining = current_time / 60
        print(f"\n=== Help Button Visibility Check ===")
        print(f"Current timer: {minutes_remaining:.2f} minutes")
        print(f"In cooldown: {self.hint_cooldown}")
        print(f"Timer running: {self.message_handler.timer.is_running}")

        # Check if timer has ever exceeded 45 minutes
        has_exceeded_45 = hasattr(self.message_handler, 'time_exceeded_45') and self.message_handler.time_exceeded_45
        print(f"Has exceeded 45: {has_exceeded_45}")

        # First check if we're in cooldown
        if self.hint_cooldown:
            print("In cooldown - hiding help button")
            if self.help_button:
                self.help_button.destroy()
                self.help_button = None
            return

        # Hide button if:
        # - Time is greater than 42 minutes AND
        # - Time is less than or equal to 45 minutes AND
        # - Timer has never exceeded 45 minutes since last reset
        should_hide = (
            minutes_remaining > 42 and 
            minutes_remaining <= 45 and 
            not has_exceeded_45
        )
        
        print(f"Time > 42: {minutes_remaining > 42}")
        print(f"Time <= 45: {minutes_remaining <= 45}")
        print(f"Should hide based on time window: {should_hide}")

        # Remove button if it exists and should be hidden
        if should_hide:
            if self.help_button:
                print("Removing help button due to timer conditions")
                self.help_button.destroy()
                self.help_button = None
            return
        elif self.help_button is None:
            # Only create new button if we don't already have one and conditions are met
            print("Conditions met to show help button - creating new button")
            self._create_button_with_background()
        else:
            print("Help button already exists")

    def _create_fallback_button(self, canvas_width, canvas_height):
        """Creates a fallback text-only button if the image loading fails"""
        self.help_button = tk.Canvas(
            self.root,
            width=canvas_width,
            height=canvas_height,
            bg='blue',
            highlightthickness=0
        )
        self.help_button.place(relx=0.19, rely=0.5, anchor='center')
        self.help_button.create_text(
            canvas_width/2,
            canvas_height/2,
            text="REQUEST NEW HINT",
            fill='white',
            font=('Arial', 24),
            angle=270
        )
        self.help_button.bind('<Button-1>', lambda e: self.request_help())
                
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
            if self.help_button:
                self.help_button.destroy()
                self.help_button = None
            
            # Show status frame and clear any existing text
            self.show_status_frame()
            self.status_frame.delete('pending_text')
            
            # Add rotated text to the canvas
            self.status_frame.create_text(
                50,  # center of width (100/2)
                540,  # center of height (1079/2)
                text="Hint Requested, please wait...",
                fill='yellow',
                font=('Arial', 24),
                angle=270,
                tags='pending_text',
                justify='center'
            )
            
            # Send help request
            self.message_handler.network.send_message({
                'type': 'help_request',
                **self.message_handler.get_stats()
            })

    def show_hint(self, text_or_data):
        """Shows the hint text and optionally creates an image received button"""
        print("\n=== PROCESSING NEW HINT ===")
        print(f"Received hint data: {type(text_or_data)}")
        
        try:
            # Remove existing UI elements
            if self.help_button:
                self.help_button.destroy()
                self.help_button = None
            
            if self.fullscreen_image:
                self.fullscreen_image.destroy()
                self.fullscreen_image = None
                
            # Clear any existing video solution
            if hasattr(self, 'video_solution_button') and self.video_solution_button:
                print("Clearing existing video solution")
                self.video_solution_button.destroy()
                self.video_solution_button = None
                
            # Stop any playing video
            if hasattr(self, 'video_is_playing') and self.video_is_playing:
                print("Stopping playing video")
                self.message_handler.video_manager.stop_video()
                self.video_is_playing = False
                
            # Clear stored video info
            if hasattr(self, 'stored_video_info'):
                self.stored_video_info = None

            # Start cooldown timer
            self.start_cooldown()
            self.current_hint = text_or_data
            
            # Clear pending request label if it exists
            if self.request_pending_label:
                self.request_pending_label.destroy()
                self.request_pending_label = None
            
            # Calculate dimensions for hint area
            hint_width = 1499 - 911  # = 588
            hint_height = 1015 - 64  # = 951
            
            # Create or clear hint container
            if self.hint_label is None:
                self.hint_label = tk.Canvas(
                    self.root,
                    width=hint_width,
                    height=hint_height,
                    bg='#000000',
                    highlightthickness=0
                )
                self.hint_label.place(x=911, y=64)
            else:
                self.hint_label.delete('all')

            # Load room-specific hint background
            background_name = None
            if hasattr(self.message_handler, 'assigned_room'):
                room_num = self.message_handler.assigned_room
                background_map = {
                    1: "casino_heist.png",
                    2: "morning_after.png",
                    3: "wizard_trials.png",
                    4: "zombie_outbreak.png",
                    5: "haunted_manor.png",
                    6: "atlantis_rising.png",
                    7: "time_machine.png"
                }
                if room_num in background_map:
                    background_name = background_map[room_num]

            if background_name:
                try:
                    bg_path = os.path.join("hint_backgrounds", background_name)
                    if os.path.exists(bg_path):
                        bg_image = Image.open(bg_path)
                        # Resize to fit canvas exactly
                        bg_image = bg_image.resize((hint_width, hint_height), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(bg_image)
                        self.hint_label.bg_image = photo
                        self.hint_label.create_image(0, 0, image=photo, anchor='nw', tags='background')
                        self.hint_label.tag_lower('background')
                except Exception as e:
                    print(f"Error loading hint background: {e}")

            # Parse hint data and clear any existing image button
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

            if hint_text:
                # If there's an image, use left half, otherwise use full width
                text_x = hint_width/2 if self.stored_image_data else hint_width/2
                self.hint_label.create_text(
                    text_x,
                    hint_height/2,
                    text=hint_text,
                    fill='black',
                    font=('Arial', 20),
                    width=hint_height-40,
                    angle=270,
                    justify='center',
                    anchor='center'
                )

            # Create image received button in left panel only if image exists
            if self.stored_image_data:
                button_width = 100  # Make button narrower
                button_height = 200  # Make button taller for better text visibility
                
                # Create button canvas
                self.image_button = tk.Canvas(
                    self.root,
                    width=button_width,
                    height=button_height,
                    bg='blue',
                    highlightthickness=0
                )
                
                # Position button well to the left of the hint text area
                self.image_button.place(
                    x=750,  # Move button further left, away from hint text
                    y=hint_height/2 - button_height/2 + 64  # Keep vertical center alignment
                )
                
                # Add button text
                self.image_button.create_text(
                    button_width/2,
                    button_height/2,
                    text="IMAGE RECEIVED",
                    fill='white',
                    font=('Arial', 24),
                    angle=270
                )
                
                # Bind click event
                self.image_button.bind('<Button-1>', lambda e: self.show_fullscreen_image())

        except Exception as e:
            print("\nCritical error in show_hint:")
            traceback.print_exc()
            try:
                if hasattr(self, 'hint_label') and self.hint_label:
                    self.hint_label.delete('all')
                    self.hint_label.create_text(
                        hint_width/2,
                        hint_height/2,
                        text=f"Error displaying hint: {str(e)}",
                        fill='red',
                        font=('Arial', 16),
                        width=hint_height-40,
                        angle=270,
                        justify='center'
                    )
            except:
                pass
            
    def show_fullscreen_image(self):
        """Display the image in nearly fullscreen with margins"""
        if not self.stored_image_data:
            return
            
        try:
            # Hide hint interface
            if self.hint_label:
                self.hint_label.place_forget()
            if self.image_button:
                self.image_button.place_forget()
                
            # Calculate dimensions (full screen minus margins)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            margin = 50  # pixels on each side
            
            # Create fullscreen canvas
            self.fullscreen_image = tk.Canvas(
                self.root,
                width=screen_width - (2 * margin),
                height=screen_height,
                bg='black',
                highlightthickness=0
            )
            self.fullscreen_image.place(x=margin, y=0)
            
            # Decode and process image
            image_bytes = base64.b64decode(self.stored_image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Calculate resize ratio maintaining aspect ratio
            width_ratio = (screen_height - 80) / image.width  # Leave margin for height
            height_ratio = (screen_width - (2 * margin) - 80) / image.height  # Leave margin for width
            ratio = min(width_ratio, height_ratio)
            
            new_size = (
                int(image.width * ratio),
                int(image.height * ratio)
            )
            
            # Resize and rotate image
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            image = image.rotate(90, expand=True)
            
            # Convert to PhotoImage and display
            photo = ImageTk.PhotoImage(image)
            self.fullscreen_image.photo = photo
            
            # Center image in canvas
            self.fullscreen_image.create_image(
                (screen_width - (2 * margin)) / 2,
                screen_height / 2,
                image=photo,
                anchor='center'
            )
            
            # Add click handler to return to hint view
            self.fullscreen_image.bind('<Button-1>', lambda e: self.restore_hint_view())
            
        except Exception as e:
            print("\nError displaying fullscreen image:")
            traceback.print_exc()
            if self.fullscreen_image:
                self.fullscreen_image.create_text(
                    screen_width/2,
                    screen_height/2,
                    text=f"Error displaying image: {str(e)}",
                    fill='red',
                    font=('Arial', 16),
                    angle=270
                )
        
    def restore_hint_view(self):
        """Return to the original hint view"""
        if self.fullscreen_image:
            self.fullscreen_image.destroy()
            self.fullscreen_image = None
            
        if self.hint_label:
            self.hint_label.place(x=911, y=64)
            
        # Restore image button with consistent positioning
        if self.image_button:
            hint_height = 1015 - 64  # Same calculation as in show_hint
            button_height = 200  # Match the height from show_hint
            self.image_button.place(
                x=750,  # Match the x-position from show_hint
                y=hint_height/2 - button_height/2 + 64  # Match the centering calculation from show_hint
            )

    def start_cooldown(self):
        """Start the cooldown timer, cancelling any existing one first"""
        print("Starting cooldown timer")
        # Cancel any existing cooldown timer
        if self.cooldown_after_id:
            self.root.after_cancel(self.cooldown_after_id)
            self.cooldown_after_id = None
            
        # Clear any existing request status
        self.status_frame.delete('pending_text')
        
        self.hint_cooldown = True
        self.show_status_frame()  # Add this line
        self.update_cooldown(60)  # Start 60 second cooldown
        
    def update_cooldown(self, seconds_left):
        """Updates the cooldown counter in the status frame"""
        if seconds_left > 0 and self.hint_cooldown:
            # Clear existing text
            self.status_frame.delete('cooldown_text')
            
            # Add new cooldown text
            self.status_frame.create_text(
                50,  # center of width (100/2)
                540,  # center of height (1079/2)
                text=f"Please wait {seconds_left} seconds until requesting the next hint.",
                fill='yellow',
                font=('Arial', 24),
                angle=270,
                tags='cooldown_text',
                justify='center',
                width=1000  # Allow text to wrap if needed
            )
            
            self.cooldown_after_id = self.root.after(1000, lambda: self.update_cooldown(seconds_left - 1))
        else:
            # Clean up the cooldown state
            print("Cooldown complete - resetting state")
            self.hint_cooldown = False
            self.cooldown_after_id = None
            self.status_frame.delete('cooldown_text')
            self.hide_status_frame()  # Add this line
            self.create_help_button()  # Recreate help button when cooldown ends

    def show_video_solution(self, room_folder, video_filename):
        """Shows a button to play the video solution, similar to image hints"""
        try:
            print(f"\nShowing video solution for {room_folder}/{video_filename}")
            
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
            button_height = 200
            
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
            print("Successfully created video solution button")
            
        except Exception as e:
            print(f"\nError creating video solution button:")
            traceback.print_exc()
            self.stored_video_info = None
            self.video_solution_button = None

    def toggle_solution_video(self):
        """Toggle video solution playback"""
        try:
            print("\nToggling solution video")
            # If video is already playing, stop it
            if hasattr(self, 'video_is_playing') and self.video_is_playing:
                print("Stopping current video")
                self.message_handler.video_manager.stop_video()
                self.video_is_playing = False
                
                # Restore the button
                if hasattr(self, 'video_solution_button') and self.video_solution_button:
                    print("Restoring solution button")
                    self.video_solution_button.place(
                        x=750,
                        y=(1015 - 64)/2 - 100 + 64
                    )
                
                # Restore hint label if it exists
                if hasattr(self, 'hint_label') and self.hint_label:
                    print("Restoring hint label")
                    self.hint_label.place(x=911, y=64)
                    
            # If video is not playing, start it
            else:
                print("Starting video playback")
                if hasattr(self, 'stored_video_info'):
                    # Only hide UI elements that exist
                    if hasattr(self, 'hint_label') and self.hint_label:
                        print("Hiding hint label")
                        self.hint_label.place_forget()
                    
                    if hasattr(self, 'video_solution_button') and self.video_solution_button:
                        print("Hiding solution button")
                        self.video_solution_button.place_forget()
                        
                    # Construct video path
                    video_path = os.path.join(
                        "video_solutions",
                        self.stored_video_info['room_folder'],
                        f"{self.stored_video_info['video_filename']}.mp4"
                    )
                    
                    print(f"Video path: {video_path}")
                    if os.path.exists(video_path):
                        print("Playing video")
                        self.video_is_playing = True
                        self.message_handler.video_manager.play_video(
                            video_path,
                            on_complete=self.handle_video_completion
                        )
                    else:
                        print(f"Error: Video file not found at {video_path}")
                else:
                    print("Error: No video info stored")
                    
        except Exception as e:
            print(f"\nError in toggle_solution_video: {e}")
            traceback.print_exc()

    def handle_video_completion(self):
        """Handle cleanup after video finishes playing"""
        print("\nHandling video completion")
        self.video_is_playing = False
        
        # Clear UI state
        print("Clearing UI state...")
        self.clear_all_labels()
        
        # Restore room interface - this will properly recreate the hint display area
        if self.message_handler.assigned_room:
            print("Restoring room interface")
            self.setup_room_interface(self.message_handler.assigned_room)
            
            # If we had a video solution, recreate its button
            if hasattr(self, 'stored_video_info') and self.stored_video_info:
                print("Recreating video solution button")
                self.show_video_solution(
                    self.stored_video_info['room_folder'],
                    self.stored_video_info['video_filename']
                )
        
        # Refresh help button state if needed
        if not self.hint_cooldown:
            self.message_handler.root.after(100, self.message_handler.update_help_button_state)
        
    def _restore_after_video(self):
        """Restore UI elements after video playback"""
        try:
            print("\nRestoring UI after video")
            
            # Verify we still have valid video info
            if not hasattr(self, 'stored_video_info') or not self.stored_video_info:
                print("Warning: No stored video info found during restore")
                return
                
            # Get video info before recreating button
            room_folder = self.stored_video_info.get('room_folder')
            video_filename = self.stored_video_info.get('video_filename')
            
            if room_folder and video_filename:
                print(f"Recreating solution button for {room_folder}/{video_filename}")
                # Recreate the button
                self.show_video_solution(room_folder, video_filename)
            else:
                print("Error: Incomplete video info")
                
            # Only recreate hint label if we still have a current hint
            if self.current_hint:
                print("Restoring hint label with current hint")
                self.show_hint(self.current_hint)
                
        except Exception as e:
            print(f"\nError restoring UI after video:")
            traceback.print_exc()
            # Ensure we don't leave invalid state
            self.stored_video_info = None 
            self.video_solution_button = None

    def _restore_after_video_with_info(self, video_info):
        """Restore UI elements with preserved video info"""
        if video_info:
            self.stored_video_info = video_info
        self._restore_after_video()