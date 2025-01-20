import tkinter as tk
import time
from PIL import Image, ImageTk
from qt_overlay import Overlay
import os
import traceback

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with root and kiosk_app reference"""
        self.root = root
        self.kiosk_app = kiosk_app
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_room = None
        
        # Delay Qt timer initialization until UI is ready
        self.root.after(1000, self._delayed_init)
        
        # Start update loop
        self.update_timer()
    
    def _delayed_init(self):
        """Initialize Qt timer after UI has had time to initialize"""
        #print("[kiosk timer][DEBUG] Timer._delayed_init - START")
        try:
            # Initialize Qt timer display
            Overlay.init_timer()
            # Initial display update
            self.update_display()
        except Exception as e:
            #print(f"[kiosk timer][DEBUG] Exception in Timer._delayed_init: {e}")
            traceback.print_exc()
        #print("[kiosk timer][DEBUG] Timer._delayed_init - END")

    # Update these methods to use Qt display
    def load_room_background(self, room_number):
        self.current_room = room_number
        # Ensure timer is initialized before loading background
        if hasattr(Overlay, '_timer'):
            Overlay.load_timer_background(room_number)
        else:
            # Schedule another attempt if timer isn't ready
            self.root.after(500, lambda: self.load_room_background(room_number))

        
    def handle_command(self, command, minutes=None):
        if command == "start":
            self.is_running = True
            self.last_update = time.time()
            print("[kiosk timer]Timer started")
            
        elif command == "stop":
            self.is_running = False
            self.last_update = None
            print("[kiosk timer]Timer stopped")
            
        elif command == "set" and minutes is not None:
            self.time_remaining = minutes * 60
            print(f"[kiosk timer]Timer set to {minutes} minutes")
            
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
                    print(f"[kiosk timer]\nTimer crossed 42-minute threshold (down)")
                    print(f"[kiosk timer]Old time: {old_minutes:.2f} minutes")
                    print(f"[kiosk timer]New time: {new_minutes:.2f} minutes")
                    # Use the kiosk_app reference to access UI
                    if hasattr(self.kiosk_app, 'ui'):
                        self.kiosk_app.ui.show_status_frame()
                        self.kiosk_app.ui.status_frame.delete('pending_text')

                
                self.update_display()

            # Schedule next update using Tkinter's after method
            self.root.after(100, self.update_timer)
                
        except Exception as e:
            print(f"[kiosk timer]Error in update_timer: {e}")
        
    def get_time_str(self):
        """Get the current time as a formatted string"""
        minutes = int(self.time_remaining // 60)
        seconds = int(self.time_remaining % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_display(self):
        """Updates the timer display safely"""
        try:
            time_str = self.get_time_str()
            # Use root.after to ensure we're on the main thread
            self.root.after(0, lambda: Overlay.update_timer_display(time_str))
        except Exception as e:
            print(f"[kiosk timer]Error updating timer display: {e}")