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
        self.last_request_time = 0
        self.request_interval = 1  # seconds

    def request_screenshot(self):
        """Request a screenshot from the currently selected kiosk."""
        current_time = time.time()
        if current_time - self.last_request_time < self.request_interval:
            self.app.root.after(int((self.request_interval - (current_time - self.last_request_time)) * 1000), self.request_screenshot)
            return

        if self.app.interface_builder.selected_kiosk:
            # Use the network handler's method
            self.app.network_handler.send_request_screenshot_command(self.app.interface_builder.selected_kiosk)
            self.last_request_time = current_time
            #print(f"[screenshot handler] Requested screenshot from {self.app.interface_builder.selected_kiosk}")

        self.app.root.after(2000, self.request_screenshot) # Schedule next request


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