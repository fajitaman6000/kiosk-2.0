import tkinter as tk
import time
from PIL import Image, ImageTk
import os

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with root and kiosk_app reference"""
        self.root = root
        self.kiosk_app = kiosk_app  # Store reference to main app
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_image = None  # Store reference to prevent garbage collection
        self.current_room = None
        
        # Define room to timer background mapping
        self.timer_backgrounds = {
            1: "casino_heist.png",
            2: "morning_after.png",
            3: "wizard_trials.png",
            4: "zombie_outbreak.png",
            5: "haunted_manor.png",
            6: "atlantis_rising.png",
            7: "time_machine.png"
        }
        
        # Create a frame container for the timer that will stay on top
        self.timer_frame = tk.Frame(
            root,
            width=270,     # Height of the rotated text display
            height=530,    # Width of the rotated text display
        )
        
        # Position frame on right center of screen
        self.timer_frame.place(
            relx=1.017,   # Right edge of screen
            rely=0.5,     # Vertical center
            anchor='e',   # Anchor to east (right) center
            x=-182        # Slight padding from edge
        )
        
        # Prevent frame from shrinking
        self.timer_frame.pack_propagate(False)
        
        # Create canvas inside the frame
        self.canvas = tk.Canvas(
            self.timer_frame,
            width=200,    
            height=400,  
            highlightthickness=0,
            bg='black'  # Fallback color if no background loaded
        )
        self.canvas.pack(fill='both', expand=True)
        
        # Create background image on canvas (initially None)
        self.bg_image_item = self.canvas.create_image(
            135,              # Horizontal center
            265,             # Vertical center
            image=None       # Will be set when room is assigned
        )
        
        # Create text item on canvas, rotated 90 degrees
        self.time_text = self.canvas.create_text(
            135,              # Horizontal center of canvas
            265,             # Vertical center of canvas
            text="45:00",
            font=('Arial', 70, 'bold'),
            fill='white',
            angle=270         # Rotate text 90 degrees clockwise
        )
        
        # Start update loop
        self.update_timer()
    
    def load_room_background(self, room_number):
        """Load the timer background for the specified room"""
        try:
            if room_number == self.current_room:
                return  # Already loaded
                
            self.current_room = room_number
            bg_filename = self.timer_backgrounds.get(room_number)
            
            if not bg_filename:
                print(f"No timer background defined for room {room_number}")
                return
                
            bg_path = os.path.join("timer_backgrounds", bg_filename)
            print(f"Loading timer background: {bg_path}")
            
            if not os.path.exists(bg_path):
                print(f"Timer background not found: {bg_path}")
                return
                
            # Load and resize the background image
            bg_img = Image.open(bg_path)
            bg_img = bg_img.resize((270, 530), Image.Resampling.LANCZOS)
            
            # Store the PhotoImage and update canvas
            self.current_image = ImageTk.PhotoImage(bg_img)
            self.canvas.itemconfig(self.bg_image_item, image=self.current_image)
            
            #print(f"Successfully loaded timer background for room {room_number}")
            
        except Exception as e:
            print(f"Error loading timer background for room {room_number}: {e}")
        
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
            print(f"Timer set to {minutes} minutes")
            
        self.update_display()
        
    def update_timer(self):
        """Updates the timer display and checks for threshold crossings"""
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                old_time = self.time_remaining
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time
                
                # Check if we crossed any significant thresholds
                old_minutes = old_time / 60
                new_minutes = self.time_remaining / 60
                
                # If we crossed the 42-minute threshold (going down)
                if old_minutes > 42 and new_minutes <= 42:
                    print(f"\nTimer crossed 42-minute threshold (down)")
                    print(f"Old time: {old_minutes:.2f} minutes")
                    print(f"New time: {new_minutes:.2f} minutes")
                    # Use the kiosk_app reference to access UI
                    if hasattr(self.kiosk_app, 'ui'):
                        self.root.after(0, self.kiosk_app.ui.create_help_button)
                
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
                    fill='white'
                )
                self.timer_frame.lift()  # Keep entire timer frame on top
        except tk.TclError:
            pass  # Widget was destroyed
        
    def lift_to_top(self):
        """Call this method when new UI elements are added"""
        if hasattr(self, 'timer_frame') and self.timer_frame.winfo_exists():
            self.timer_frame.lift()