import tkinter as tk
import time
from PIL import Image, ImageTk
from qt_overlay import Overlay
import os

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with root and kiosk_app reference"""
        self.root = root
        self.kiosk_app = kiosk_app
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_room = None
        
        # Initialize Qt timer display
        Overlay.init_timer()
        
        # Start update loop
        self.update_timer()
    
    # Update these methods to use Qt display
    def load_room_background(self, room_number):
        if room_number == self.current_room:
            return
        self.current_room = room_number
        Overlay.load_timer_background(room_number)
        
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

            # Schedule next update using Tkinter's after method
            self.root.after(100, self.update_timer)
                
        except Exception as e:
            print(f"Error in update_timer: {e}")
        
    def get_time_str(self):
        """Get the current time as a formatted string"""
        minutes = int(self.time_remaining // 60)
        seconds = int(self.time_remaining % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_display(self):
        try:
            time_str = self.get_time_str()
            Overlay.update_timer_display(time_str)
        except Exception as e:
            print(f"Error updating timer display: {e}")