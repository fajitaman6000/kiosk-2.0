import tkinter as tk
import time

class KioskTimer:
    def __init__(self, root, network_handler):
        self.root = root
        self.network_handler = network_handler
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        
        # Create a frame container for the timer that will stay on top
        self.timer_frame = tk.Frame(
            root,
            width=80,     # Height of the rotated text display
            height=200,   # Width of the rotated text display
            bg='black'
        )
        
        # Position frame on right center of screen
        self.timer_frame.place(
            relx=1.0,     # Right edge of screen
            rely=0.5,     # Vertical center
            anchor='e',   # Anchor to east (right) center
            x=-10        # Slight padding from edge
        )
        
        # Prevent frame from shrinking
        self.timer_frame.pack_propagate(False)
        
        # Create canvas inside the frame
        self.canvas = tk.Canvas(
            self.timer_frame,
            width=80,    
            height=200,  
            bg='black',
            highlightthickness=0
        )
        self.canvas.pack(fill='both', expand=True)
        
        # Create text item on canvas, rotated 90 degrees
        self.time_text = self.canvas.create_text(
            40,              # Horizontal center of canvas
            100,            # Vertical center of canvas
            text="45:00",
            font=('Arial', 36, 'bold'),
            fill='white',
            angle=270         # Rotate text 90 degrees clockwise
        )
        
        # Start update loop
        self.update_timer()
        
    def handle_command(self, command, minutes=None):
        if command == "start":
            self.is_running = True
            self.last_update = time.time()
            print("Timer started")
        elif command == "stop":
            self.is_running = False
            self.last_update = None
            print("Timer stopped")
        elif command == "set" and minutes is not None:
            self.time_remaining = minutes * 60
            self.is_running = False
            self.last_update = None
            print(f"Timer set to {minutes} minutes")
            
        self.update_display()
        
    def update_timer(self):
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time
                self.update_display()

            if self.timer_frame.winfo_exists():
                self.root.after(100, self.update_timer)
        except tk.TclError:
            pass  # Widget was destroyed
        
    def update_display(self):
        try:
            if self.canvas.winfo_exists():
                minutes = int(self.time_remaining // 60)
                seconds = int(self.time_remaining % 60)
                self.canvas.itemconfig(
                    self.time_text,
                    text=f"{minutes:02d}:{seconds:02d}",
                    fill='white' if self.is_running else 'yellow'
                )
                self.timer_frame.lift()  # Keep entire timer frame on top
        except tk.TclError:
            pass  # Widget was destroyed
        
    def lift_to_top(self):
        """Call this method when new UI elements are added"""
        if hasattr(self, 'timer_frame') and self.timer_frame.winfo_exists():
            self.timer_frame.lift()