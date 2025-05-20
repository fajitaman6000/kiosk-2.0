# screenshot_handler.py
import tkinter as tk
from PIL import Image, ImageTk
import io
import base64
import time
import json

class ScreenshotHandler:
    def __init__(self, app):
        self.app = app
        self.last_request_time = {}
        self.request_interval = 1  # seconds

    def request_screenshot(self, computer_name, force=False):
        """Request a screenshot from a specific kiosk.
        Args:
            computer_name (str): The name of the target kiosk.
            force (bool): If True, request will bypass video playing checks on kiosk.
        """
        if not computer_name:
            print("[screenshot handler] No computer_name provided for screenshot request.")
            return

        current_time = time.time()
        last_req_time = self.last_request_time.get(computer_name, 0)

        # Apply interval check only for non-forced requests
        if not force and (current_time - last_req_time < self.request_interval):
            #print(f"[screenshot handler] Ignoring non-forced screenshot request for {computer_name}: too soon.")
            # Do not schedule `after` here, the periodic caller handles that.
            return

        # Use the network handler's method
        self.app.network_handler.send_request_screenshot_command(computer_name, force=force) # <--- PASS FORCE
        self.last_request_time[computer_name] = current_time
        #print(f"[screenshot handler] Requested screenshot from {computer_name} (Force: {force})")


    def handle_screenshot(self, computer_name, image_data):
        """Handles the received screenshot."""
        if self.app.interface_builder.selected_kiosk != computer_name:
            #print(f"[screenshot handler] Ignoring screenshot from {computer_name} (not selected)")
            return

        try:
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))

            # Convert to PhotoImage and update the label
            photo = ImageTk.PhotoImage(image)

            # Make sure the label exists
            if 'image_display_label' in self.app.interface_builder.stats_elements:
                self.app.interface_builder.stats_elements['image_display_label'].config(image=photo)
                self.app.interface_builder.stats_elements['image_display_label'].image = photo  # Keep reference
            else:
                print("[screenshot handler] Error: image_display_label not found in stats_elements")

        except Exception as e:
            print(f"[screenshot handler] Error displaying screenshot: {e}")
            import traceback
            traceback.print_exc()