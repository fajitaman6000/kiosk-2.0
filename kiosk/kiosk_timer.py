# kiosk_timer.py - Kiosk side
import tkinter as tk
import time

class KioskTimer:
    def __init__(self, root, network_handler):
        self.root = root
        self.network_handler = network_handler
        self.time_remaining = 60 * 45  # Default 60 minutes
        self.is_running = False
        self.last_update = None
        
        # Create timer display
        self.timer_frame = tk.Frame(root, bg='black')
        self.timer_frame.pack(fill='x', side='top')
        
        self.time_label = tk.Label(
            self.timer_frame,
            text="45:00",
            font=('Arial', 36, 'bold'),
            fg='white',
            bg='black',
            highlightbackground='white',
            highlightthickness=1,
            padx=10,
            pady=5
        )
        self.time_label.pack(pady=10)
        
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

            # Only schedule next update if widget exists
            if self.time_label.winfo_exists():
                self.root.after(100, self.update_timer)
        except tk.TclError:
            pass  # Widget was destroyed
        
    def update_display(self):
        try:
            if self.time_label.winfo_exists():
                minutes = int(self.time_remaining // 60)
                seconds = int(self.time_remaining % 60)
                self.time_label.config(
                    text=f"{minutes:02d}:{seconds:02d}",
                    fg='white' if self.is_running else 'yellow'
                )
                
                # Keep timer on top
                self.timer_frame.lift()
        except tk.TclError:
            pass  # Widget was destroyed
        
    def lift_to_top(self):
        """Call this method when new UI elements are added"""
        self.timer_frame.lift()