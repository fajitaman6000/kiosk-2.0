import tkinter as tk
from tkinter import ttk
import traceback
import sys
from prop_control import PropControl
import os  # Add this import

from network_broadcast_handler import NetworkBroadcastHandler
from kiosk_state_tracker import KioskStateTracker
from admin_interface_builder import AdminInterfaceBuilder

def show_error_and_wait():
    print("[main]\nAn error occurred. Error details above.")
    input("Press Enter to exit...")

try:
    class AdminApplication:
        def __init__(self):
            # Ensure we're in the correct directory
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            print(f"[main]Working directory set to: {os.getcwd()}")
            
            self.root = tk.Tk()
            self.root.title("Kiosk Control Center (WIP, Do not use to run rooms yet)")
            
            # Get screen dimensions
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            # Calculate window size with manual adjustments:
            window_width = screen_width // 2
            window_height = screen_height - 69 # nice
            x_position = -10
            y_position = 0
            
            # Set window geometry with manual adjustments
            self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
            
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
            self.prop_control = PropControl(self)
            
            # Set up prop panel synchronization
            self.setup_prop_panel_sync()
            
            # Start network handling
            self.network_handler.start()
            
            # Set up update timers
            self.root.after(5000, self.kiosk_tracker.check_timeouts)
            self.root.after(1000, self.interface_builder.update_stats_timer)

        def setup_prop_panel_sync(self):
            """Set up synchronization between prop controls and hint panels"""
            # Create SavedHintsPanel if it doesn't exist (you'll need to import this)
            from saved_hints_panel import SavedHintsPanel
            if not hasattr(self.interface_builder, 'saved_hints'):
                self.interface_builder.saved_hints = SavedHintsPanel(
                    self.interface_builder.stats_frame,
                    lambda hint_data: self.interface_builder.send_hint(
                        self.interface_builder.selected_kiosk, 
                        hint_data
                    )
                )

            # Create ClassicAudioHints if it doesn't exist
            if not hasattr(self.interface_builder, 'audio_hints'):
                self.interface_builder.setup_audio_hints()

            # Add prop selection callback to PropControl
            def on_prop_select(prop_name):
                """Handle prop selection from PropControl"""
                if self.interface_builder.selected_kiosk:
                    room_num = self.kiosk_tracker.kiosk_assignments.get(
                        self.interface_builder.selected_kiosk
                    )
                    if room_num:
                        # Try to select prop in saved hints panel
                        if hasattr(self.interface_builder, 'saved_hints'):
                            self.interface_builder.saved_hints.select_prop_by_name(prop_name)
                        
                        # Try to select prop in audio hints panel
                        if hasattr(self.interface_builder, 'audio_hints'):
                            self.interface_builder.audio_hints.select_prop_by_name(prop_name)

            # Register callback with PropControl
            self.prop_control.add_prop_select_callback(on_prop_select)

        def run(self):
            print("[main]Starting admin application...")
            self.root.mainloop()

        def on_closing(self):
            print("[main]Shutting down admin application...")
            if hasattr(self.interface_builder, 'cleanup'):
                self.interface_builder.cleanup()
            self.root.destroy()

    if __name__ == '__main__':
        app = AdminApplication()
        app.run()

except Exception as e:
    print("[main]\nERROR:")
    traceback.print_exc()
    show_error_and_wait()