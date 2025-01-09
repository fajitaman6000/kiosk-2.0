import tkinter as tk
import time
from qt_overlay import Overlay

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with root and kiosk_app reference"""
        self.root = root
        self.kiosk_app = kiosk_app  # Store reference to main app
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
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
        
        # Start update loop
        self.update_timer()
    
    def load_room_background(self, room_number):
        """Load the timer background for the specified room"""
        if room_number == self.current_room:
            return
            
        self.current_room = room_number
        # Update timer display with new room number
        self.update_display()
        
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

            # Schedule next update
            self.root.after(100, self.update_timer)
        except tk.TclError:
            pass  # Widget was destroyed
        
    def update_display(self):
        """Update the timer display using Qt overlay"""
        try:
            minutes = int(self.time_remaining // 60)
            seconds = int(self.time_remaining % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            
            # Use Qt overlay to show timer
            Overlay.show_timer(time_str, self.current_room)
            
        except Exception as e:
            print(f"Error updating timer display: {e}")
            
    def lift_to_top(self):
        """Ensure timer stays on top"""
        # Qt overlay handles staying on top automatically
        pass