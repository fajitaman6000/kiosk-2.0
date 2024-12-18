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
        
        # Restore hint if there was one
        if self.current_hint:
            self.show_hint(self.current_hint)
        
        # Restore help button if not in cooldown
        if not self.hint_cooldown:
            self.create_help_button()
        
        # Ensure timer stays on top
        self.message_handler.timer.lift_to_top()
            
    def create_help_button(self):
        """Creates the help request button"""
        if self.help_button is None and not self.hint_cooldown:
            self.help_button = tk.Button(
                self.root,
                text="REQUEST NEW HINT",
                command=self.message_handler.request_help,
                height=5, width=30,
                font=('Arial', 24),
                bg='blue', fg='white'
            )
            # Position button on the left side
            self.help_button.place(relx=0.2, rely=0.5, anchor='center')
            
    def show_hint(self, text):
        """Shows the hint text"""
        self.current_hint = text
        
        if self.request_pending_label:
            self.request_pending_label.destroy()
            self.request_pending_label = None
            
        if self.hint_label is None:
            self.hint_label = tk.Label(
                self.root,
                text=text,
                fg='black', bg='yellow',
                font=('Arial', 20),
                wraplength=800
            )
            # Position hint text on the left side
            self.hint_label.place(relx=0.2, rely=0.3, anchor='center')
        else:
            self.hint_label.config(text=text)
            
    def start_cooldown(self):
        self.hint_cooldown = True
        self.update_cooldown(60)
        
    def update_cooldown(self, seconds_left):
        if seconds_left > 0:
            if self.cooldown_label is None:
                self.cooldown_label = tk.Label(
                    self.root,
                    bg='black',
                    fg='white',
                    font=('Arial', 24)
                )
                # Position cooldown text on the left side
                self.cooldown_label.place(relx=0.2, rely=0.7, anchor='center')
            
            self.cooldown_label.config(
                text=f"Please wait {seconds_left} seconds until requesting the next hint."
            )
            self.root.after(1000, lambda: self.update_cooldown(seconds_left - 1))
        else:
            self.hint_cooldown = False
            if self.cooldown_label:
                self.cooldown_label.destroy()
                self.cooldown_label = None
            self.create_help_button()

