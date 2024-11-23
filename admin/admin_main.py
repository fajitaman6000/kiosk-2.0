import tkinter as tk
from tkinter import ttk
import traceback
import sys

from network_broadcast_handler import NetworkBroadcastHandler
from kiosk_state_tracker import KioskStateTracker
from admin_interface_builder import AdminInterfaceBuilder

def show_error_and_wait():
    print("\nAn error occurred. Error details above.")
    input("Press Enter to exit...")

try:
    class AdminApplication:
        def __init__(self):
            self.root = tk.Tk()
            self.root.title("Kiosk Control Center")
            self.root.geometry("900x600")
            
            # Room definitions
            self.rooms = {
                1: "Casino Heist",
                2: "Morning After",
                3: "Wizard Trials",
                4: "Zombie Outbreak",
                5: "Haunted Manor",
                6: "Atlantis Rising",
                7: "Time Machine"
            }
            
            # Initialize components
            self.kiosk_tracker = KioskStateTracker(self)
            self.network_handler = NetworkBroadcastHandler(self)
            self.interface_builder = AdminInterfaceBuilder(self)
            
            # Start network handling
            self.network_handler.start()
            
            # Set up update timers
            self.root.after(5000, self.kiosk_tracker.check_timeouts)
            self.root.after(1000, self.interface_builder.update_stats_timer)
        
        def run(self):
            print("Starting admin application...")
            self.root.mainloop()

    if __name__ == '__main__':
        app = AdminApplication()
        app.run()

except Exception as e:
    print("\nERROR:")
    traceback.print_exc()
    show_error_and_wait()
