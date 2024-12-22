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
        """Creates the help request button rotated 270 degrees using a canvas"""
        if self.help_button is None and not self.hint_cooldown:
            # Create a canvas container for the rotated button
            # Height and width are swapped due to rotation
            canvas_width = 150  # This will be the height of the button
            canvas_height = 400  # This will be the width of the button
            
            self.help_button = tk.Canvas(
                self.root,
                width=canvas_width,
                height=canvas_height,
                bg='blue',    # Match button background
                highlightthickness=0  # Remove canvas border
            )
            
            # Position canvas on the left side
            self.help_button.place(relx=0.2, rely=0.5, anchor='center')
            
            # Create the rotated text
            text = self.help_button.create_text(
                canvas_width/2,  # Center horizontally
                canvas_height/2, # Center vertically
                text="REQUEST NEW HINT",
                fill='white',    # White text
                font=('Arial', 24),
                angle=270        # Rotate text 270 degrees
            )
            
            # Bind click event to the canvas
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
            canvas_width = 150   # This will be the height of the text area
            canvas_height = 400  # This will be the width of the text area
            
            if self.request_pending_label is None:
                self.request_pending_label = tk.Canvas(
                    self.root,
                    width=canvas_width,
                    height=canvas_height,
                    bg='black',
                    highlightthickness=0
                )
                # Position the pending request text on the left side
                self.request_pending_label.place(relx=0.2, rely=0.5, anchor='center')
                
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
        """Shows the hint text and/or image rotated 270 degrees"""
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
                self.hint_label = tk.Canvas(
                    self.root,
                    width=150,   # Height of rotated content
                    height=800,  # Width of content
                    bg='yellow',
                    highlightthickness=0
                )
                self.hint_label.place(relx=0.4, rely=0.5, anchor='center')
            else:
                print("Clearing existing hint canvas")
                self.hint_label.delete('all')
            
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
            
            y_position = 400  # Start at vertical center
            
            # Add text if present
            if hint_text:
                print("Adding hint text to canvas")
                self.hint_label.create_text(
                    75,     # Center horizontally
                    y_position,
                    text=hint_text,
                    fill='black',
                    font=('Arial', 20),
                    width=780,
                    angle=270,
                    justify='center'
                )
                y_position += len(hint_text.split('\n')) * 30
            
            # Add image if present
            if image_data:
                print("Processing hint image")
                try:
                    print("Decoding base64 image data")
                    image_bytes = base64.b64decode(image_data)
                    print(f"Decoded image size: {len(image_bytes)} bytes")
                    
                    print("Opening image from bytes")
                    image = Image.open(io.BytesIO(image_bytes))
                    print(f"Original image size: {image.size}")
                    
                    # Calculate size to fit
                    max_width = 700
                    max_height = 140
                    ratio = min(max_width/image.width, max_height/image.height)
                    new_size = (int(image.width * ratio), int(image.height * ratio))
                    print(f"Resizing to: {new_size}")
                    
                    # Resize and rotate
                    image = image.resize(new_size, Image.Resampling.LANCZOS)
                    image = image.rotate(90, expand=True)
                    
                    print("Converting to PhotoImage")
                    photo = ImageTk.PhotoImage(image)
                    self.hint_label.photo = photo
                    
                    # Position and display
                    image_x = 75
                    image_y = y_position + (new_size[1] / 2)
                    print(f"Placing image at: ({image_x}, {image_y})")
                    
                    self.hint_label.create_image(
                        image_x, image_y,
                        image=photo,
                        anchor='center'
                    )
                    print("Image successfully added to canvas")
                    
                except Exception as e:
                    print("\nError processing hint image:")
                    traceback.print_exc()
                    self.hint_label.create_text(
                        75,
                        y_position + 50,
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
                        75, 400,
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
                fill='white',
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



