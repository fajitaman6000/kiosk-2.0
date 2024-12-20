# ui.py
import tkinter as tk
from PIL import Image, ImageTk
import os

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

    def show_hint(self, text):
        """Shows the hint text rotated 270 degrees"""
        self.current_hint = text
        
        # Clear pending request label if it exists
        if self.request_pending_label:
            self.request_pending_label.destroy()
            self.request_pending_label = None
        
        # Canvas dimensions (swapped due to rotation)
        canvas_width = 150   # This will be the height of the text area
        canvas_height = 800  # This will be the width of the text area
        
        if self.hint_label is None:
            self.hint_label = tk.Canvas(
                self.root,
                width=canvas_width,
                height=canvas_height,
                bg='yellow',    # Yellow background for hints
                highlightthickness=0
            )
            # Position hint text on the right side of the help button
            self.hint_label.place(relx=0.4, rely=0.5, anchor='center')
        else:
            # Clear existing text
            self.hint_label.delete('all')
        
        # Create the rotated text
        self.hint_label.create_text(
            canvas_width/2,    # Center horizontally in canvas
            canvas_height/2,   # Center vertically in canvas
            text=text,
            fill='black',
            font=('Arial', 20),
            width=canvas_height-20,  # Leave some padding
            angle=270,         # Rotate text
            justify='center'   # Center the text
        )
            
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



