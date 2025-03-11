import tkinter as tk
from tkinter import ttk
import traceback
import sys
from prop_control import PropControl
import os

from network_broadcast_handler import NetworkBroadcastHandler
from kiosk_state_tracker import KioskStateTracker
from admin_interface_builder import AdminInterfaceBuilder
from admin_sync_manager import AdminSyncManager
from manager_settings import AdminPasswordManager, ManagerSettings

import json

import ctypes

def show_error_and_wait():
    print("[main]An error occurred. Error details above.")
    input("Press Enter to exit...")

try:
    class AdminApplication:
        def __init__(self):
            # Ensure we're in the correct directory
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            print(f"[main]Working directory set to: {os.getcwd()}")
            
            self.root = tk.Tk()
            self.root.title("Game Master Control Center")

            # Handle icon setting
            myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid) # allows icon to show in task bar

            try:
                # Construct the absolute path to the icon file
                icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")  # Assuming icon.ico is in the same directory

                self.root.iconbitmap(default=icon_path)  # Use -default for .ico with multiple sizes

            except tk.TclError as e:
                print(f"[main]Error loading icon: {e}")  # Handle icon loading error

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
            
            # Initialize password manager
            self.password_manager = AdminPasswordManager(self)
            
            # Initialize the sync manager
            self.sync_manager = AdminSyncManager(self)
            
            # Set up prop panel synchronization
            self.setup_prop_panel_sync()

            # --- Add screenshot handler ---
            from screenshot_handler import ScreenshotHandler
            self.screenshot_handler = ScreenshotHandler(self)
            
            # Start network handling
            self.network_handler.start()
            
            # Set up update timers
            self.root.after(5000, self.kiosk_tracker.check_timeouts)
            self.root.after(1000, self.interface_builder.update_stats_timer)
            self.root.after(2000, self.screenshot_handler.request_screenshot) # Request screenshots

            # Start the sync manager
            self.sync_manager.start()

            # Configure button callbacks with password protection
            self.interface_builder.sync_button.config(command=self.handle_sync_button_click)
            self.interface_builder.settings_button.config(command=self.handle_settings_button_click)
            self.interface_builder.soundcheck_button.config(command=self.handle_soundcheck_button_click)

            # Set up window close handler
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        def handle_sync_button_click(self):
            """Handle sync button click with password protection"""
            def on_success():
                self.sync_manager.handle_sync_button()
            self.password_manager.verify_password(callback=on_success)

        def handle_settings_button_click(self):
            """Handle settings button click with password protection"""
            def on_success():
                self.interface_builder.hint_manager.show_hint_manager()
            self.password_manager.verify_password(callback=on_success)

        def handle_soundcheck_button_click(self):
            if self.interface_builder.selected_kiosk:
                computer_name = self.interface_builder.selected_kiosk
                # Send soundcheck command through network handler
                self.network_handler.socket.sendto(
                    json.dumps({
                        'type': 'soundcheck',
                        'computer_name': computer_name
                    }).encode(),
                    ('255.255.255.255', 12346)
                )
            else:
                print("[main] No kiosk selected for soundcheck.")

        def setup_prop_panel_sync(self):
            """Set up synchronization between prop controls and hint panels"""
            # Create SavedHintsPanel if it doesn't exist
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
                            
                        # Try to select prop in image hint selection
                        if hasattr(self.interface_builder, 'stats_elements') and 'image_btn' in self.interface_builder.stats_elements:
                            # Find the matching prop in the image dropdown values
                            for formatted_name in self.interface_builder.stats_elements['image_btn']['values']:
                                if f"({prop_name})" in formatted_name:
                                    self.interface_builder.img_prop_var.set(formatted_name)
                                    self.interface_builder.on_image_prop_select(None)
                                    break

            # Register callback with PropControl
            self.prop_control.add_prop_select_callback(on_prop_select)

        def run(self):
            print("[main]Starting admin application...")
            self.root.mainloop()

        def on_closing(self):
            print("[main]Shutting down admin application...")
            if hasattr(self.interface_builder, 'cleanup'):
                self.interface_builder.cleanup()
            self.sync_manager.stop()
            self.root.destroy()

    if __name__ == '__main__':
        app = AdminApplication()
        app.run()

except Exception as e:
    print("[main]ERROR:")
    traceback.print_exc()
    show_error_and_wait()