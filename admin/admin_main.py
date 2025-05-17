# --- START OF FILE admin_main.py ---

import tkinter as tk
from tkinter import ttk
import traceback
import sys
from prop_control import PropControl
import os
import pygame
from admin_soundcheck import AdminSoundcheckWindow
from tkinter import messagebox
from bug_report_manager import BugReportManager

from network_broadcast_handler import NetworkBroadcastHandler
from kiosk_state_tracker import KioskStateTracker
from admin_interface_builder import AdminInterfaceBuilder
from admin_sync_manager import AdminSyncManager
from manager_settings import AdminPasswordManager, ManagerSettings

import json

import ctypes
import time # Import time for potential timing checks (though not strictly needed for this heartbeat)

# --- Heartbeat Configuration (Add these constants) ---
# NOTE: This MUST match the HEARTBEAT_MARKER in admin_watchdog.py
ADMIN_HEARTBEAT_MARKER = "[ADMIN_HEARTBEAT_ALIVE]" 
# Send heartbeat more frequently than the watchdog timeout (e.g., every 5 seconds)
HEARTBEAT_INTERVAL_MS = 2000

def show_error_and_wait():
    print("[main]An error occurred. Error details above.")
    input("Press Enter to exit...")

try:
    class AdminApplication:
        select_kiosk_debug = False
        hint_debug = False
        
        def __init__(self):
            # Ensure we're in the correct directory
            os.chdir(os.path.dirname(os.path.abspath(__file__)))
            print(f"[main]Working directory set to: {os.getcwd()}")
            
            self.root = tk.Tk()
            
            # Initialize pygame mixer globally for admin app (if not done elsewhere)
            try:
                pygame.mixer.init()
                print("[Main Admin] Pygame mixer initialized.")
            except Exception as e:
                print(f"[Main Admin] Failed to initialize pygame mixer: {e}")

            self.root.title("PanIQ Game Master Control Center")

            # Handle icon setting
            myappid = 'mycompany.myproduct.subproduct.version' # arbitrary string
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

            try:
                icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
                self.root.iconbitmap(default=icon_path)
            except tk.TclError as e:
                print(f"[main]Error loading icon: {e}")

            # Get screen dimensions and set geometry (existing code)
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            window_width = screen_width // 2 - 45
            window_height = screen_height - 69
            x_position = -10
            y_position = 0
            self.root.geometry(f"{window_width}x{window_height}+{x_position}+{y_position}")
            
            # Set dark theme (existing code)
            #sv_ttk.set_theme("dark")

            # Room definitions (existing code)
            self.rooms = {
                1: "Casino Heist",
                2: "Morning After",
                3: "Wizard Trials",
                4: "Zombie Outbreak",
                5: "Haunted Manor",
                6: "Atlantis Rising",
                7: "Time Machine"
            }
            
            # Initialize components (existing code)
            self.kiosk_tracker = KioskStateTracker(self)
            self.network_handler = NetworkBroadcastHandler(self)
            self.bug_report_manager = BugReportManager(self)
            self.interface_builder = AdminInterfaceBuilder(self)
            self.prop_control = PropControl(self)

            # Initialize password manager (existing code)
            self.password_manager = AdminPasswordManager(self)
            
            # Initialize the sync manager (existing code)
            self.sync_manager = AdminSyncManager(self)
            
            # Set up prop panel synchronization (existing code)
            self.setup_prop_panel_sync()

            # --- Add screenshot handler --- (existing code)
            from screenshot_handler import ScreenshotHandler
            self.screenshot_handler = ScreenshotHandler(self)
            
            # Start network handling (existing code)
            self.network_handler.start()
            
            # Set up update timers (existing code)
            self.root.after(5000, self.kiosk_tracker.check_timeouts)
            self.root.after(1000, self.interface_builder.update_stats_timer)
            #self.root.after(2000, self.screenshot_handler.request_screenshot)

            # Start the sync manager (existing code)
            self.sync_manager.start()

            # Configure button callbacks with password protection (existing code)
            self.interface_builder.sync_button.config(command=self.handle_sync_button_click)
            self.interface_builder.settings_button.config(command=self.handle_settings_button_click)
            self.interface_builder.soundcheck_button.config(command=self.handle_soundcheck_button_click)
            self.interface_builder.bug_report_button.config(command=self.handle_bug_report_button_click)

            # Set up window close handler (existing code)
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

            self.root.after(1000, self.resend_check_timer)  # Check every second (existing code)

            # --- Start the Heartbeat Timer (Add this) ---
            # Store the timer ID so we can cancel it later
            self._heartbeat_timer_id = None 
            self._send_heartbeat() # Start the first heartbeat cycle
            # -------------------------------------------

            print("[main]Starting admin application...") # This is the ADMIN_SUCCESS_MARKER

        # --- Add the heartbeat method ---
        def _send_heartbeat(self):
            """Sends a heartbeat signal to stdout for the watchdog."""
            # Print the specific marker string followed by a newline
            print(ADMIN_HEARTBEAT_MARKER, flush=True)
            # Optionally print a more descriptive log message for debugging the admin app itself
            # print(f"[Admin Heartbeat] Sent heartbeat at {time.strftime('%Y-%m-%d %H:%M:%S')}") 

            # Reschedule the method to run again after the interval
            self._heartbeat_timer_id = self.root.after(HEARTBEAT_INTERVAL_MS, self._send_heartbeat)
        # ------------------------------

        def resend_check_timer(self): # Existing method
            """Timer callback to resend unacknowledged messages."""
            if hasattr(self.network_handler, 'resend_unacknowledged_messages'):
                self.network_handler.resend_unacknowledged_messages()
            self.root.after(1000, self.resend_check_timer)  # Reschedule

        def handle_sync_button_click(self): # Existing method
            """Handle sync button click with password protection"""
            def on_success():
                self.sync_manager.handle_sync_button()
            self.password_manager.verify_password(callback=on_success)

        def handle_settings_button_click(self): # Existing method
            """Handle settings button click with password protection"""
            def on_success():
                self.interface_builder.hint_manager.show_hint_manager()
            self.password_manager.verify_password(callback=on_success)

        def handle_soundcheck_button_click(self): # Existing method
            # Get list of currently connected kiosks
            connected_kiosk_names = list(self.interface_builder.connected_kiosks.keys())

            if not connected_kiosk_names:
                messagebox.showinfo("No Kiosks", "No kiosks are currently connected.", parent=self.root)
                print("[Admin Main] No kiosks connected for soundcheck.")
                return

            print("[Admin Main] Initiating soundcheck for kiosks:", connected_kiosk_names)
            # Create and show the soundcheck window
            soundcheck_win = AdminSoundcheckWindow(self.root, self, connected_kiosk_names)
            # Pass the instance to the network handler so it can call update_status
            self.network_handler.soundcheck_instance = soundcheck_win

        def handle_bug_report_button_click(self): # Existing method
            """Handle bug report button click."""
            print("[Admin Main] Bug report button clicked.")
            if hasattr(self, 'bug_report_manager') and self.bug_report_manager:
                self.bug_report_manager.show_report_submission_popup()
            else:
                messagebox.showerror("Error", "Bug Report Manager is not initialized.", parent=self.root)
                print("[Admin Main] Error: BugReportManager not found.")

        def setup_prop_panel_sync(self): # Existing method
            """Set up synchronization between prop controls and hint panels"""
            from saved_hints_panel import SavedHintsPanel
            if not hasattr(self.interface_builder, 'saved_hints'):
                self.interface_builder.saved_hints = SavedHintsPanel(
                    self.interface_builder.stats_frame,
                    lambda hint_data: self.interface_builder.send_hint(
                        self.interface_builder.selected_kiosk, 
                        hint_data
                    )
                )

            if not hasattr(self.interface_builder, 'audio_hints'):
                self.interface_builder.setup_audio_hints()

            def on_prop_select(prop_name): # Existing inner function
                """Handle prop selection from PropControl"""
                if self.interface_builder.selected_kiosk:
                    room_num = self.kiosk_tracker.kiosk_assignments.get(
                        self.interface_builder.selected_kiosk
                    )
                    if room_num:
                        if hasattr(self.interface_builder, 'saved_hints'):
                            self.interface_builder.saved_hints.select_prop_by_name(prop_name)
                        if hasattr(self.interface_builder, 'audio_hints'):
                            self.interface_builder.audio_hints.select_prop_by_name(prop_name)
                        if hasattr(self.interface_builder, 'stats_elements') and 'image_btn' in self.interface_builder.stats_elements:
                             for formatted_name in self.interface_builder.stats_elements['image_btn']['values']:
                                 if f"({prop_name})" in formatted_name:
                                     self.interface_builder.img_prop_var.set(formatted_name)
                                     # Need to call the actual update logic here
                                     # Assuming on_image_prop_select exists and updates the preview
                                     if hasattr(self.interface_builder, 'on_image_prop_select'):
                                         self.interface_builder.on_image_prop_select(None) # Pass None as event arg
                                     break

            self.prop_control.add_prop_select_callback(on_prop_select)

        def run(self): # Existing method
            print("[main]Starting admin application...")
            self.root.mainloop()

        def on_closing(self): # Existing method - ADD timer cancellation here
            print("[main]Shutting down admin application...")
            
            # --- Cancel the heartbeat timer (Add this) ---
            if hasattr(self, '_heartbeat_timer_id') and self._heartbeat_timer_id is not None:
                print("[Admin Main] Cancelling heartbeat timer...")
                self.root.after_cancel(self._heartbeat_timer_id)
                self._heartbeat_timer_id = None # Clear the ID
            # ------------------------------------------

            if hasattr(self.interface_builder, 'cleanup'):
                self.interface_builder.cleanup()
            self.sync_manager.stop()
            # Quit pygame mixer
            if pygame.mixer.get_init():
                pygame.mixer.quit()
                print("[Main Admin] Pygame mixer quit.")
            self.root.destroy()

    if __name__ == '__main__':
        app = AdminApplication()
        app.run()

except Exception as e:
    print("[main]ERROR:")
    traceback.print_exc()
    show_error_and_wait()