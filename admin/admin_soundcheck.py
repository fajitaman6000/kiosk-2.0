# admin_soundcheck.py
import tkinter as tk
from tkinter import ttk, messagebox
import base64
import io
import pygame # For playing back audio samples
from threading import Thread

class AdminSoundcheckWindow:
    def __init__(self, parent_root, app, kiosk_names):
        self.app = app
        self.kiosk_names = kiosk_names
        self.soundcheck_instance = self # Reference for network handler
        self.closed = False

        # Initialize pygame mixer if not already done (e.g., by AdminAudioManager)
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except Exception as e:
                print(f"[Admin Soundcheck] Pygame mixer init error: {e}")
                messagebox.showerror("Audio Error", "Could not initialize audio playback.")
                # Optionally handle differently, maybe disable 'Listen' buttons

        # --- Window Setup ---
        self.window = tk.Toplevel(parent_root)
        self.window.title("Kiosk Soundcheck")
        self.window.geometry("600x500") # Adjust size as needed
        self.window.resizable(False, False)
        # Make window modal (optional, prevents interaction with main window)
        # self.window.grab_set()

        # --- Data Storage ---
        # Status: None (pending), True (pass), False (fail)
        self.kiosk_status = {
            name: {'touch': None, 'audio': None, 'mic': None, 'audio_sample': None}
            for name in kiosk_names
        }
        self.ui_elements = {name: {} for name in kiosk_names} # To store labels/buttons

        # --- UI Creation ---
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(expand=True, fill="both")

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        ttk.Label(header_frame, text="Kiosk", width=20, anchor="w").pack(side="left", padx=5)
        ttk.Label(header_frame, text="Touch", width=8, anchor="center").pack(side="left", padx=5)
        ttk.Label(header_frame, text="Audio Out", width=8, anchor="center").pack(side="left", padx=5)
        ttk.Label(header_frame, text="Mic In", width=8, anchor="center").pack(side="left", padx=5)
        ttk.Label(header_frame, text="Sample", width=15, anchor="center").pack(side="left", padx=5)

        # Separator
        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=(0, 10))

        # Kiosk Rows Frame
        rows_canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=rows_canvas.yview)
        rows_frame = ttk.Frame(rows_canvas)

        rows_frame.bind(
            "<Configure>",
            lambda e: rows_canvas.configure(
                scrollregion=rows_canvas.bbox("all")
            )
        )

        rows_canvas.create_window((0, 0), window=rows_frame, anchor="nw")
        rows_canvas.configure(yscrollcommand=scrollbar.set)

        rows_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Create rows for each kiosk
        for name in self.kiosk_names:
            self.create_kiosk_row(rows_frame, name)

        # --- Bottom Buttons ---
        button_frame = ttk.Frame(self.window, padding="10")
        button_frame.pack(fill="x", side="bottom")

        self.finish_button = ttk.Button(button_frame, text="Finish Soundcheck", command=self.finish_soundcheck)
        self.finish_button.pack(side="right", padx=5)

        self.cancel_button = ttk.Button(button_frame, text="Cancel", command=self.cancel_soundcheck)
        self.cancel_button.pack(side="right", padx=5)

        # --- Window Close Handling ---
        self.window.protocol("WM_DELETE_WINDOW", self.cancel_soundcheck)

        # --- Start the Soundcheck ---
        self.send_start_command()

    def create_kiosk_row(self, parent_frame, kiosk_name):
        """Creates the UI elements for a single kiosk row."""
        row_frame = ttk.Frame(parent_frame)
        row_frame.pack(fill="x", pady=2)

        ttk.Label(row_frame, text=kiosk_name, width=20, anchor="w").pack(side="left", padx=5)

        # Status Indicators (using Labels with text/color)
        touch_label = ttk.Label(row_frame, text="?", width=8, anchor="center", foreground="gray")
        touch_label.pack(side="left", padx=5)
        audio_label = ttk.Label(row_frame, text="?", width=8, anchor="center", foreground="gray")
        audio_label.pack(side="left", padx=5)
        mic_label = ttk.Label(row_frame, text="?", width=8, anchor="center", foreground="gray")
        mic_label.pack(side="left", padx=5)

        # Sample Frame (Listen button and optional Mic result)
        sample_frame = ttk.Frame(row_frame)
        sample_frame.pack(side="left", padx=5, fill="x", expand=True)

        listen_button = ttk.Button(sample_frame, text="Listen", width=8, state="disabled",
                                   command=lambda n=kiosk_name: self.play_audio_sample(n))
        listen_button.pack(side="left")

        # Store UI elements for later updates
        self.ui_elements[kiosk_name] = {
            'touch': touch_label,
            'audio': audio_label,
            'mic': mic_label,
            'listen_btn': listen_button,
        }

    def send_start_command(self):
        """Sends the soundcheck start command to all relevant kiosks."""
        print("[Admin Soundcheck] Sending start command to kiosks:", self.kiosk_names)
        # Use network handler to send command to each kiosk
        for name in self.kiosk_names:
            self.app.network_handler.send_soundcheck_command(name) # Needs implementation in network handler

    def update_status(self, kiosk_name, test_type, result, audio_data=None):
        """Updates the status for a kiosk and refreshes its UI row."""
        if self.closed or kiosk_name not in self.kiosk_status:
            print(f"[Admin Soundcheck] Update ignored for {kiosk_name} (window closed or kiosk unknown)")
            return # Ignore updates if window is closed or kiosk not part of this check

        print(f"[Admin Soundcheck] Received update: Kiosk={kiosk_name}, Test={test_type}, Result={result}")

        self.kiosk_status[kiosk_name][test_type] = result

        if test_type == 'audio_sample' and result: # Result is True if sample received
             # Decode and store the audio sample
            try:
                decoded_data = base64.b64decode(audio_data)
                self.kiosk_status[kiosk_name]['audio_sample'] = io.BytesIO(decoded_data)
                print(f"[Admin Soundcheck] Audio sample stored for {kiosk_name}")
                # Enable the listen button
                if kiosk_name in self.ui_elements and 'listen_btn' in self.ui_elements[kiosk_name]:
                    self.ui_elements[kiosk_name]['listen_btn'].config(state="normal")
            except Exception as e:
                print(f"[Admin Soundcheck] Error decoding/storing audio sample for {kiosk_name}: {e}")
                self.kiosk_status[kiosk_name]['mic'] = False # Mark mic as failed if sample is bad
                result = False # Update result for UI
                test_type = 'mic' # Update the UI for the mic test

        # Update the corresponding UI label
        if test_type in self.ui_elements[kiosk_name]:
            label = self.ui_elements[kiosk_name][test_type]
            if result is True:
                label.config(text="✓", foreground="green")
            elif result is False:
                label.config(text="✕", foreground="red")
            else: # None or other
                label.config(text="?", foreground="gray")

    def play_audio_sample(self, kiosk_name):
        """Plays the received audio sample for a specific kiosk."""
        if kiosk_name not in self.kiosk_status or not self.kiosk_status[kiosk_name]['audio_sample']:
            print(f"[Admin Soundcheck] No audio sample available for {kiosk_name}")
            messagebox.showinfo("No Sample", f"No audio sample received from {kiosk_name}.")
            return

        sample_data = self.kiosk_status[kiosk_name]['audio_sample']
        sample_data.seek(0) # Rewind the buffer

        print(f"[Admin Soundcheck] Playing audio sample for {kiosk_name}")

        # Check if mixer is initialized
        if not pygame.mixer.get_init():
            messagebox.showerror("Audio Error", "Audio playback system not initialized.")
            return

        # Stop any currently playing sound
        pygame.mixer.stop()

        try:
            # Load the sample from the BytesIO buffer
            sound = pygame.mixer.Sound(buffer=sample_data.read())
            sound.play()
            # Prompt for feedback after a short delay (adjust as needed)
            self.window.after(6000, lambda: self.prompt_mic_feedback(kiosk_name))
        except Exception as e:
            print(f"[Admin Soundcheck] Error playing audio sample for {kiosk_name}: {e}")
            messagebox.showerror("Playback Error", f"Could not play audio sample for {kiosk_name}:\n{e}")

    def prompt_mic_feedback(self, kiosk_name):
        """Asks the admin if the microphone worked based on the sample."""
        answer = messagebox.askyesnocancel("Microphone Check",
                                           f"Did the microphone for {kiosk_name} seem functional?",
                                           parent=self.window)
        if answer is True:
            self.update_status(kiosk_name, 'mic', True)
        elif answer is False:
            self.update_status(kiosk_name, 'mic', False)
        # If Cancel, do nothing, status remains pending (or whatever it was)

    def finish_soundcheck(self):
        """Generates a report and closes the soundcheck."""
        report = "Soundcheck Results:\n\n"
        all_complete = True
        for name, status in self.kiosk_status.items():
            report += f"Kiosk: {name}\n"
            results = []
            for test in ['touch', 'audio', 'mic']:
                result = status[test]
                if result is True:
                    results.append(f"  - {test.capitalize()}: Pass")
                elif result is False:
                    results.append(f"  - {test.capitalize()}: Fail")
                else:
                    results.append(f"  - {test.capitalize()}: Incomplete")
                    all_complete = False
            report += "\n".join(results) + "\n\n"

        if not all_complete:
            report += "Note: Some tests were incomplete."

        messagebox.showinfo("Soundcheck Report", report, parent=self.window)
        self.send_cancel_command() # Tell kiosks to stop
        self.close_window()

    def cancel_soundcheck(self):
        """Cancels the soundcheck and closes the window."""
        print("[Admin Soundcheck] Cancelling soundcheck...")
        self.send_cancel_command()
        self.close_window()

    def send_cancel_command(self):
        """Sends the cancel command to kiosks."""
        print("[Admin Soundcheck] Sending cancel command to kiosks.")
        for name in self.kiosk_names:
             # Check if kiosk still exists in the main interface before sending cancel
            if name in self.app.interface_builder.connected_kiosks:
                self.app.network_handler.send_soundcheck_cancel_command(name) # Needs implementation
            else:
                print(f"[Admin Soundcheck] Kiosk {name} no longer connected, skipping cancel command.")

    def close_window(self):
        """Safely closes the window and cleans up."""
        if not self.closed:
            self.closed = True
            print("[Admin Soundcheck] Closing window.")
            # Stop pygame mixer if we initialized it here and nothing else is using it
            # (Be cautious if AdminAudioManager is also used)
            # if pygame.mixer.get_init():
            #    pygame.mixer.stop()
            #    # pygame.mixer.quit() # Maybe too aggressive if other parts use it
            if self.window:
                self.window.destroy()
            # Nullify reference in network handler if passed
            if hasattr(self.app.network_handler, 'soundcheck_instance') and \
               self.app.network_handler.soundcheck_instance == self:
                self.app.network_handler.soundcheck_instance = None

#=================================================
# Modifications in other admin files
#=================================================

# --- In admin_interface_builder.py ---
# Add import at the top:
# from admin_soundcheck import AdminSoundcheckWindow

# Modify the handle_soundcheck_button_click method (around line 1189):
# def handle_soundcheck_button_click(self):
#     # Get list of currently connected kiosks
#     connected_kiosk_names = list(self.connected_kiosks.keys())
#
#     if not connected_kiosk_names:
#         messagebox.showinfo("No Kiosks", "No kiosks are currently connected.", parent=self.app.root)
#         print("[Admin UI] No kiosks connected for soundcheck.")
#         return
#
#     print("[Admin UI] Initiating soundcheck for kiosks:", connected_kiosk_names)
#     # Create and show the soundcheck window
#     soundcheck_win = AdminSoundcheckWindow(self.app.root, self.app, connected_kiosk_names)
#     # Pass the instance to the network handler so it can call update_status
#     self.app.network_handler.soundcheck_instance = soundcheck_win

# --- In network_broadcast_handler.py ---
# Add new methods:
# def send_soundcheck_command(self, computer_name):
#     """Sends a soundcheck command to a specific kiosk."""
#     message = {
#         'type': 'soundcheck_command',
#         'command_id': str(uuid.uuid4()),
#         'computer_name': computer_name
#     }
#     self._send_tracked_message(message, computer_name)
#     print(f"[Network Handler] Sent soundcheck command to {computer_name}")
#
# def send_soundcheck_cancel_command(self, computer_name):
#     """Sends a command to cancel the soundcheck on a kiosk."""
#     message = {
#         'type': 'soundcheck_cancel',
#         'command_id': str(uuid.uuid4()),
#         'computer_name': computer_name
#     }
#     self._send_tracked_message(message, computer_name)
#     print(f"[Network Handler] Sent soundcheck cancel command to {computer_name}")

# Add to __init__:
# self.soundcheck_instance = None # Will hold ref to AdminSoundcheckWindow

# Modify listen_for_messages:
# Add a new elif block:
#                 elif msg_type == 'soundcheck_status':
#                     computer_name = msg.get('computer_name')
#                     test_type = msg.get('test_type')
#                     result = msg.get('result')
#                     audio_data = msg.get('audio_data') # Base64 string or None
#                     if computer_name and test_type is not None and result is not None:
#                         if self.soundcheck_instance and not self.soundcheck_instance.closed:
#                             # Use after to ensure UI update happens on main thread
#                             self.app.root.after(0, self.soundcheck_instance.update_status,
#                                                 computer_name, test_type, result, audio_data)
#                         # else: print(f"Received soundcheck status for {computer_name}, but no active window.")
#                     else:
#                         print(f"[Network Handler] Invalid soundcheck_status message received: {msg}")

# --- In admin_main.py ---
# Add import near top:
# import pygame

# Add near the end of __init__ before the main loop starts:
#         # Initialize pygame mixer globally for admin app (if not done elsewhere)
#         try:
#             pygame.mixer.init()
#             print("[Main Admin] Pygame mixer initialized.")
#         except Exception as e:
#             print(f"[Main Admin] Failed to initialize pygame mixer: {e}")

# Add in on_closing method:
#         # Quit pygame mixer
#         if pygame.mixer.get_init():
#             pygame.mixer.quit()
#             print("[Main Admin] Pygame mixer quit.")