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
        self.cooldown_label = None
        self.request_pending_label = None
        self.current_hint = None
        self.hint_label = None
        self.cooldown_after_id = None
        
        self.setup_root()
        
    def setup_root(self):
        self.root.attributes('-fullscreen', True)
        self.root.configure(bg='black')
        self.root.bind('<Escape>', lambda e: self.root.attributes('-fullscreen', False))
        
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
        # Cancel any pending cooldown timer
        if self.cooldown_after_id:
            self.root.after_cancel(self.cooldown_after_id)
            self.cooldown_after_id = None
            
        # Reset cooldown state
        self.hint_cooldown = False
        
        for widget in [self.hint_label, self.request_pending_label, 
                      self.cooldown_label, self.help_button]:
            if widget:
                widget.destroy()
        self.hint_label = None
        self.request_pending_label = None
        self.cooldown_label = None
        self.help_button = None
        
    def setup_room_interface(self, room_number):
        # Clear all widgets except timer frame
        for widget in self.root.winfo_children():
            if widget is not self.message_handler.timer.timer_frame:  # Keep timer frame
                widget.destroy()
        
        # Set up background first
        self.background_image = self.load_background(room_number)
        if self.background_image:
            background_label = tk.Label(self.root, image=self.background_image)
            background_label.place(x=0, y=0, relwidth=1, relheight=1)
        
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
            
    def create_help_button(self):
        """Creates the help request button using a room-specific background image"""
        if self.help_button is None and not self.hint_cooldown:
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
                    # Load and rotate the button background image
                    button_path = os.path.join("hint_button_backgrounds", button_name)
                    if os.path.exists(button_path):
                        # Open and rotate the image
                        button_image = Image.open(button_path)
                        # Resize maintaining aspect ratio
                        aspect_ratio = button_image.width / button_image.height
                        new_height = canvas_height
                        new_width = int(new_height * aspect_ratio)
                        button_image = button_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                        # Rotate 90 degrees clockwise
                        #button_image = button_image.rotate(270, expand=True)
                        button_photo = ImageTk.PhotoImage(button_image)
                        
                        # Create canvas and store the image reference
                        self.help_button = tk.Canvas(
                            self.root,
                            width=canvas_width,
                            height=canvas_height,
                            highlightthickness=0
                        )
                        self.help_button.button_image = button_photo  # Prevent garbage collection
                        
                        # Add the image to the canvas
                        self.help_button.create_image(
                            canvas_width/2,
                            canvas_height/2,
                            image=button_photo,
                            anchor='center'
                        )
                        
                        # Position canvas on the left side
                        self.help_button.place(relx=0.19, rely=0.5, anchor='center')
                        
                        # Bind click event to the canvas
                        self.help_button.bind('<Button-1>', lambda e: self.request_help())
                    else:
                        print(f"Button image not found at: {button_path}")
                        self._create_fallback_button(canvas_width, canvas_height)
                else:
                    print("No room assigned or room number not in button map")
                    self._create_fallback_button(canvas_width, canvas_height)
            except Exception as e:
                print(f"Error creating image button: {str(e)}")
                self._create_fallback_button(canvas_width, canvas_height)

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
        """Creates the 'Hint Requested' message with rotated text"""
        if not self.hint_cooldown:
            # Increase hint count
            if hasattr(self.message_handler, 'hints_requested'):
                self.message_handler.hints_requested += 1
            
            # Remove help button if it exists
            if self.help_button:
                self.help_button.destroy()
                self.help_button = None
            
            # Canvas dimensions (swapped due to rotation)
            canvas_width = 260   # This will be the height of the text area
            canvas_height = 550  # This will be the width of the text area
            
            if self.request_pending_label is None:
                self.request_pending_label = tk.Canvas(
                    self.root,
                    width=canvas_width,
                    height=canvas_height,
                    bg='black',
                    highlightthickness=0
                )
                # Position the pending request text on the left side
                self.request_pending_label.place(relx=0.19, rely=0.5, anchor='center')
                
                # Create the rotated text
                self.request_pending_label.create_text(
                    canvas_width/2,
                    canvas_height/2,
                    text="Hint Requested, please wait...",
                    fill='yellow',
                    font=('Arial', 24),
                    width=canvas_height-20,  # Leave some padding
                    angle=270,
                    justify='center'
                )
            
            # Send help request
            self.message_handler.network.send_message({
                'type': 'help_request',
                **self.message_handler.get_stats()
            })

    def show_hint(self, text_or_data):
        """Shows the hint text and image in separate, non-overlapping areas, rotated 270 degrees.
        Text appears in left panel, image in right panel if present."""
        print("\n=== PROCESSING NEW HINT ===")
        print(f"Received hint data: {type(text_or_data)}")
        
        try:
            self.current_hint = text_or_data
            
            # Clear pending request label if it exists
            if self.request_pending_label:
                self.request_pending_label.destroy()
                self.request_pending_label = None
            
            
            # Create hint container if needed
            if self.hint_label is None:
                print("Creating new hint canvas")
                # Create much wider canvas to accommodate separated text and image
                total_width = 600  # Total width for both panels
                
                # Initialize canvas with black background (fallback)
                self.hint_label = tk.Canvas(
                    self.root,
                    width=total_width,   # Width accommodates both text and image
                    height=800,          # Height (becomes width when rotated)
                    bg='#000000',         # Default background
                    highlightthickness=0
                )
                self.hint_label.place(relx=0.4, rely=0.5, anchor='center')
            else:
                print("Clearing existing hint canvas")
                self.hint_label.delete('all')

            # Load room-specific hint background regardless of whether canvas is new or existing
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
                        # Resize to fit canvas
                        bg_image = bg_image.resize((600, 800), Image.Resampling.LANCZOS)
                        photo = ImageTk.PhotoImage(bg_image)
                        # Store reference to prevent garbage collection
                        self.hint_label.bg_image = photo
                        # Create background image on canvas at layer 0
                        self.hint_label.create_image(0, 0, image=photo, anchor='nw', tags='background')
                        # Move background to bottom layer
                        self.hint_label.tag_lower('background')
                except Exception as e:
                    print(f"Error loading hint background: {e}")

            # Create visual separator between text and image areas
            #self.hint_label.create_line(
                #300, 0,    # Start at middle top
                #300, 800,  # End at middle bottom
                #fill='black',
                #width=2
            #)

            # Parse hint data
            hint_text = ""
            image_data = None
            
            if isinstance(text_or_data, str):
                print("Processing text-only hint")
                hint_text = text_or_data
            elif isinstance(text_or_data, dict):
                print("Processing hint dictionary")
                hint_text = text_or_data.get('text', '')
                image_data = text_or_data.get('image')
                print(f"Found text: {bool(hint_text)}")
                print(f"Found image data: {bool(image_data)}")
            else:
                print(f"WARNING: Unexpected hint data type: {type(text_or_data)}")
                hint_text = str(text_or_data)
            
            # Define panel dimensions
            panel_width = 300   # Width of each panel (text and image)
            panel_height = 800  # Height of each panel
            
            # Position text in left panel
            if hint_text:
                print("Adding hint text to left panel")
                self.hint_label.create_text(
                    panel_width/2,     # Center of left panel
                    panel_height/2,    # Vertical center
                    text=hint_text,
                    fill='black',
                    font=('Arial', 20),
                    width=panel_height-40,  # Leave margin
                    angle=270,
                    justify='center'
                )
            
            # Add image in right panel if present
            if image_data:
                print("Processing hint image for right panel")
                try:
                    print("Decoding base64 image data")
                    image_bytes = base64.b64decode(image_data)
                    print(f"Decoded image size: {len(image_bytes)} bytes")
                    
                    print("Opening image from bytes")
                    image = Image.open(io.BytesIO(image_bytes))
                    print(f"Original image size: {image.size}")
                    
                    # Calculate maximum size for right panel
                    max_width = panel_height - 40   # Leave margin
                    max_height = panel_width - 40   # Leave margin
                    
                    # Calculate resize ratio maintaining aspect ratio
                    width_ratio = max_width / image.width
                    height_ratio = max_height / image.height
                    ratio = min(width_ratio, height_ratio)
                    
                    new_size = (
                        int(image.width * ratio),
                        int(image.height * ratio)
                    )
                    print(f"Resizing to: {new_size}")
                    
                    # Resize and rotate
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                    image = image.rotate(90, expand=True)
                    
                    print("Converting to PhotoImage")
                    photo = ImageTk.PhotoImage(image)
                    self.hint_label.photo = photo
                    
                    # Position image in center of right panel
                    self.hint_label.create_image(
                        panel_width + panel_width/2,  # Center of right panel
                        panel_height/2,               # Vertical center
                        image=photo,
                        anchor='center'
                    )
                    print("Image successfully added to right panel")
                    
                except Exception as e:
                    print("\nError processing hint image:")
                    traceback.print_exc()
                    self.hint_label.create_text(
                        225,    # Right side position
                        400,    # Vertical center
                        text=f"[Error displaying image: {str(e)}]",
                        fill='red',
                        font=('Arial', 16),
                        width=780,
                        angle=270,
                        justify='center'
                    )
        except Exception as e:
            print("\nCritical error in show_hint:")
            traceback.print_exc()
            # Try to show error message in UI
            try:
                if hasattr(self, 'hint_label') and self.hint_label:
                    self.hint_label.delete('all')
                    self.hint_label.create_text(
                        150, 400,
                        text=f"Error displaying hint: {str(e)}",
                        fill='red',
                        font=('Arial', 16),
                        width=780,
                        angle=270,
                        justify='center'
                    )
            except:
                pass
            
    def start_cooldown(self):
        """Start the cooldown timer, cancelling any existing one first"""
        # Cancel any existing cooldown timer
        if self.cooldown_after_id:
            self.root.after_cancel(self.cooldown_after_id)
            self.cooldown_after_id = None
            
        self.hint_cooldown = True
        self.update_cooldown(60)
        
    def update_cooldown(self, seconds_left):
        """Updates the cooldown counter with rotated text"""
        if seconds_left > 0 and self.hint_cooldown:  # Only continue if cooldown is still active
            # Canvas dimensions (swapped due to rotation)
            canvas_width = 150   # This will be the height of the text area
            canvas_height = 600  # This will be the width of the text area
            
            if self.cooldown_label is None:
                self.cooldown_label = tk.Canvas(
                    self.root,
                    width=canvas_width,
                    height=canvas_height,
                    bg='black',
                    highlightthickness=0
                )
                # Position cooldown text on the left side
                self.cooldown_label.place(relx=0.2, rely=0.5, anchor='center')
            else:
                # Clear existing text
                self.cooldown_label.delete('all')
            
            # Create the rotated text
            self.cooldown_label.create_text(
                canvas_width/2,
                canvas_height/2,
                text=f"Please wait {seconds_left} seconds until requesting the next hint.",
                fill='yellow',
                font=('Arial', 24),
                width=canvas_height-20,  # Leave some padding
                angle=270,
                justify='center'
            )
            
            # Store the ID of the next timer callback so we can cancel it if needed
            self.cooldown_after_id = self.root.after(1000, lambda: self.update_cooldown(seconds_left - 1))
        else:
            # Clean up the cooldown state
            self.hint_cooldown = False
            self.cooldown_after_id = None
            if self.cooldown_label:
                self.cooldown_label.destroy()
                self.cooldown_label = None
            self.create_help_button()



