# admin_soundcheck.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import base64
import io
import pygame # For playing back audio samples
from threading import Thread
import tempfile
import os
import wave

class AdminSoundcheckWindow:
    def __init__(self, parent_root, app, kiosk_names):
        self.app = app
        self.kiosk_names = kiosk_names
        self.soundcheck_instance = self # Reference for network handler
        self.closed = False
        self.temp_files = {} # Store temporary audio files for playback
        self.report_window = None # Keep track of the report window

        # Initialize pygame mixer if not already done (e.g., by AdminAudioManager)
        if not pygame.mixer.get_init():
            try:
                # Initialize with settings matching recording parameters
                pygame.mixer.init(frequency=11025, size=16, channels=1)
                print("[Admin Soundcheck] Pygame mixer initialized with optimal settings.")
            except Exception as e:
                print(f"[Admin Soundcheck] Pygame mixer init error: {e}")
                messagebox.showerror("Audio Error", "Could not initialize audio playback.")
                # Optionally handle differently, maybe disable 'Listen' buttons

        # --- Window Setup ---
        self.window = tk.Toplevel(parent_root)
        self.window.title("Kiosk Soundcheck")
        self.window.geometry("700x500") # Adjusted size for additional buttons
        self.window.resizable(False, False)
        # Make window modal (optional, prevents interaction with main window)
        self.window.grab_set() # Make the soundcheck window modal initially

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
        ttk.Label(header_frame, text="Sample", width=25, anchor="center").pack(side="left", padx=5)

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

        # Sample Frame (Listen button and mic validation buttons)
        sample_frame = ttk.Frame(row_frame)
        sample_frame.pack(side="left", padx=5, fill="x", expand=True)

        listen_button = ttk.Button(sample_frame, text="Listen", width=8, state="disabled",
                                   command=lambda n=kiosk_name: self.play_audio_sample(n))
        listen_button.pack(side="left")

        # Mic validation buttons (initially hidden)
        mic_buttons_frame = ttk.Frame(sample_frame)
        # mic_buttons_frame.pack(side="left", padx=(10, 0)) # Pack when shown by play_audio_sample

        mic_check_button = ttk.Button(mic_buttons_frame, text="✓", width=3,
                                      command=lambda n=kiosk_name: self.set_mic_status(n, True))
        mic_check_button.pack(side="left", padx=(0, 2))

        mic_fail_button = ttk.Button(mic_buttons_frame, text="✕", width=3,
                                    command=lambda n=kiosk_name: self.set_mic_status(n, False))
        mic_fail_button.pack(side="left")

        # Store UI elements for later updates
        self.ui_elements[kiosk_name] = {
            'touch': touch_label,
            'audio': audio_label,
            'mic': mic_label,
            'listen_btn': listen_button,
            'mic_buttons_frame': mic_buttons_frame, # Frame itself needs to be packed/unpacked
            'mic_check_btn': mic_check_button,
            'mic_fail_btn': mic_fail_button
        }
        # Hide frame initially
        mic_buttons_frame.pack_forget()


    def send_start_command(self):
        """Sends the soundcheck start command to all relevant kiosks."""
        print("[Admin Soundcheck] Sending start command to kiosks:", self.kiosk_names)
        # Use network handler to send command to each kiosk
        for name in self.kiosk_names:
            # Add check if kiosk is actually connected according to network handler?
            self.app.network_handler.send_soundcheck_command(name) # Needs implementation in network handler

    def update_status(self, kiosk_name, test_type, result, audio_data=None):
        """Updates the status for a kiosk and refreshes its UI row."""
        # Ensure updates run in the Tkinter thread
        if self.window.winfo_exists():
             self.window.after(0, self._update_status_ui, kiosk_name, test_type, result, audio_data)
        else:
             print(f"[Admin Soundcheck] Update ignored for {kiosk_name} (window destroyed)")


    def _update_status_ui(self, kiosk_name, test_type, result, audio_data=None):
        """Internal method to update UI, called via window.after"""
        if self.closed or kiosk_name not in self.kiosk_status:
            # print(f"[Admin Soundcheck] Update ignored for {kiosk_name} (window closed or kiosk unknown)")
            return # Ignore updates if window is closed or kiosk not part of this check

        print(f"[Admin Soundcheck] UI Update: Kiosk={kiosk_name}, Test={test_type}, Result={result}")

        # --- Handle audio sample logic first ---
        if test_type == 'audio_sample':
            if result: # Result is True if sample received
                # Decode and store the audio sample
                try:
                    # Clear any existing temp file
                    if kiosk_name in self.temp_files and self.temp_files[kiosk_name] and os.path.exists(self.temp_files[kiosk_name]):
                        try:
                            os.remove(self.temp_files[kiosk_name])
                        except OSError as e:
                             print(f"[Admin Soundcheck] Error removing old temp file {self.temp_files[kiosk_name]}: {e}")
                        self.temp_files[kiosk_name] = None

                    # Decode data
                    decoded_data = base64.b64decode(audio_data)

                    # Create a temporary file for better playback reliability
                    fd, temp_path = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)

                    # Save the WAV data to the temporary file
                    with open(temp_path, 'wb') as f:
                        f.write(decoded_data)

                    # Store the path to the temporary file
                    self.temp_files[kiosk_name] = temp_path
                    print(f"[Admin Soundcheck] Audio sample saved to temp file for {kiosk_name}: {temp_path}")

                    # Store path for playback reference
                    self.kiosk_status[kiosk_name]['audio_sample'] = temp_path

                    # Enable the listen button
                    if kiosk_name in self.ui_elements and 'listen_btn' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['listen_btn'].config(state="normal")

                    # Don't update mic status here yet, let user validate via buttons
                    # self.kiosk_status[kiosk_name]['mic'] = None # Reset mic status pending validation

                except Exception as e:
                    print(f"[Admin Soundcheck] Error processing audio sample for {kiosk_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    # Mark mic as failed if sample is bad or processing fails
                    self.kiosk_status[kiosk_name]['mic'] = False
                    self.kiosk_status[kiosk_name]['audio_sample'] = None # Clear sample reference
                    if kiosk_name in self.ui_elements and 'listen_btn' in self.ui_elements[kiosk_name]:
                         self.ui_elements[kiosk_name]['listen_btn'].config(state="disabled")
                    # Update the mic UI immediately to show failure
                    if 'mic' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['mic'].config(text="✕", foreground="red")
                    # Hide validation buttons if they were somehow visible
                    if 'mic_buttons_frame' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['mic_buttons_frame'].pack_forget()

            else: # Result is False for audio_sample (e.g., kiosk failed to record/send)
                 print(f"[Admin Soundcheck] Received failed audio_sample status for {kiosk_name}")
                 self.kiosk_status[kiosk_name]['mic'] = False # Mark mic as failed
                 self.kiosk_status[kiosk_name]['audio_sample'] = None
                 if kiosk_name in self.ui_elements:
                     if 'listen_btn' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['listen_btn'].config(state="disabled")
                     if 'mic' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['mic'].config(text="✕", foreground="red")
                     if 'mic_buttons_frame' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['mic_buttons_frame'].pack_forget()

            return # Don't process further UI for 'audio_sample' type itself

        # --- Update status for touch, audio, mic (manual update) ---
        if test_type in self.kiosk_status[kiosk_name]:
             self.kiosk_status[kiosk_name][test_type] = result

        # Update the corresponding UI label
        if test_type in self.ui_elements[kiosk_name]:
            label = self.ui_elements[kiosk_name][test_type]
            if result is True:
                label.config(text="✓", foreground="green")
            elif result is False:
                label.config(text="✕", foreground="red")
            else: # None (pending/reset)
                label.config(text="?", foreground="gray")

        # Special handling for 'mic' update: hide validation buttons if failed/reset
        if test_type == 'mic' and result is not True:
             if kiosk_name in self.ui_elements and 'mic_buttons_frame' in self.ui_elements[kiosk_name]:
                 self.ui_elements[kiosk_name]['mic_buttons_frame'].pack_forget()


    def play_audio_sample(self, kiosk_name):
        """Plays the received audio sample for a specific kiosk."""
        if kiosk_name not in self.kiosk_status or not self.kiosk_status[kiosk_name]['audio_sample']:
            print(f"[Admin Soundcheck] No audio sample available for {kiosk_name}")
            messagebox.showinfo("No Sample", f"No audio sample received from {kiosk_name}.", parent=self.window)
            return

        temp_path = self.kiosk_status[kiosk_name]['audio_sample']

        if not temp_path or not os.path.exists(temp_path):
            print(f"[Admin Soundcheck] Audio file missing or path invalid for {kiosk_name}: {temp_path}")
            messagebox.showerror("Playback Error", f"Audio file for {kiosk_name} not found.", parent=self.window)
            # Consider marking mic as failed?
            self.update_status(kiosk_name, 'mic', False)
            return

        print(f"[Admin Soundcheck] Playing audio sample for {kiosk_name} from {temp_path}")

        # Check if mixer is initialized
        if not pygame.mixer.get_init():
            messagebox.showerror("Audio Error", "Audio playback system not initialized.", parent=self.window)
            return

        # Stop any currently playing sound
        pygame.mixer.stop()

        try:
            # Load and play the audio file
            sound = pygame.mixer.Sound(temp_path)
            sound.play()

            # Show the mic validation buttons AND reset mic status display to '?'
            if kiosk_name in self.ui_elements:
                if 'mic' in self.ui_elements[kiosk_name]:
                     self.ui_elements[kiosk_name]['mic'].config(text="?", foreground="gray")
                     self.kiosk_status[kiosk_name]['mic'] = None # Reset status pending validation

                if 'mic_buttons_frame' in self.ui_elements[kiosk_name]:
                    # Ensure it's packed correctly within its parent (sample_frame)
                    frame_widget = self.ui_elements[kiosk_name]['mic_buttons_frame']
                    if not frame_widget.winfo_ismapped(): # Only pack if not already visible
                        frame_widget.pack(side="left", padx=(10, 0))


        except Exception as e:
            print(f"[Admin Soundcheck] Error playing audio sample for {kiosk_name}: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Playback Error", f"Could not play audio sample for {kiosk_name}:\n{e}", parent=self.window)
            # Mark mic as failed if playback fails
            self.update_status(kiosk_name, 'mic', False)


    def set_mic_status(self, kiosk_name, is_working):
        """Sets the microphone status based on user validation."""
        print(f"[Admin Soundcheck] Setting mic status for {kiosk_name} to {is_working}")
        self.update_status(kiosk_name, 'mic', is_working)
        # Optionally hide the buttons again after selection? Or leave them? Let's leave them for now.
        # if kiosk_name in self.ui_elements and 'mic_buttons_frame' in self.ui_elements[kiosk_name]:
        #     self.ui_elements[kiosk_name]['mic_buttons_frame'].pack_forget()


    def finish_soundcheck(self):
        """Generates a report using a custom window. Does NOT close main window yet."""
        # Prevent opening multiple report windows
        if self.report_window and self.report_window.winfo_exists():
            self.report_window.lift()
            return

        # --- Create a new Toplevel window for the report ---
        # Make it a child of the root window, not the soundcheck window,
        # so it doesn't get destroyed if the soundcheck window is hidden/iconified.
        self.report_window = tk.Toplevel(self.app.root) # Use app's root window as parent
        self.report_window.title("Soundcheck Report")
        self.report_window.geometry("500x400")
        # Make the report window modal *relative to the application*
        self.report_window.grab_set()
        # Make it transient to the main soundcheck window (optional, helps with window stacking)
        self.report_window.transient(self.window)


        report_text = scrolledtext.ScrolledText(self.report_window, wrap=tk.WORD, state='disabled', height=15)
        report_text.pack(expand=True, fill='both', padx=10, pady=5)

        # Configure tags for formatting
        report_text.tag_configure("green_italic", foreground="green", font=('TkDefaultFont', 9, 'italic'))
        report_text.tag_configure("red", foreground="red")
        report_text.tag_configure("bold", font=('TkDefaultFont', 9, 'bold'))

        report_text.configure(state='normal') # Enable editing to insert text
        report_text.insert(tk.END, "")

        any_issues_found = False
        # Sort kiosks by name for consistent report order
        sorted_kiosk_names = sorted(self.kiosk_status.keys())

        for name in sorted_kiosk_names:
            status = self.kiosk_status[name]
            all_success = True
            issue_details = []
            success_details = []

            for test in ['touch', 'audio', 'mic']:
                result = status.get(test, None) # Use .get for safety
                test_name_cap = test.capitalize()
                if result is True:
                    success_details.append(f"  - {test_name_cap}: Pass")
                elif result is False:
                    issue_details.append((f"  - {test_name_cap}: Fail", ["bold"])) # Mark bold
                    all_success = False
                    any_issues_found = True
                else: # None (incomplete)
                    issue_details.append((f"  - {test_name_cap}: Incomplete", ["bold"])) # Mark bold
                    all_success = False
                    any_issues_found = True # Treat incomplete as an issue requiring attention

            # Format the output for this kiosk
            if all_success:
                # Green italics: Only show name, marked as successful
                report_text.insert(tk.END, f"Kiosk: {name} - OK\n", ("green_italic"))
            else: # Has issues (red)
                # Red: Mark kiosk name
                report_text.insert(tk.END, f"Kiosk: {name} - ISSUES FOUND\n", ("red"))
                # Add failed/incomplete first (bold)
                for text, tags in issue_details:
                    report_text.insert(tk.END, f"{text}\n", tags)
                # Then add successful items for this kiosk (green italic)
                for text in success_details:
                    report_text.insert(tk.END, f"{text}\n", ("green_italic"))

            report_text.insert(tk.END, "\n") # Add a blank line between kiosks

        if not self.kiosk_status:
             report_text.insert(tk.END, "No kiosks were included in this soundcheck.\n")
        elif not any_issues_found:
             report_text.insert(tk.END, "\nAll checked kiosks reported OK.", ("green_italic"))
        else:
             report_text.insert(tk.END, "\nISSUES FOUND.")

        report_text.configure(state='disabled') # Make read-only

        # --- Add buttons to the report window ---
        report_button_frame = ttk.Frame(self.report_window)
        report_button_frame.pack(pady=(5, 10))

        # Button to close report AND the main soundcheck window
        close_all_button = ttk.Button(report_button_frame, text="Close Report & Finish",
                                      command=self.close_report_and_main)
        close_all_button.pack(side=tk.RIGHT, padx=5)

        # Allow user to just close report and keep soundcheck window open? Maybe not needed.

        # Handle report window 'X' button press
        self.report_window.protocol("WM_DELETE_WINDOW", self.close_report_and_main)

        # --- Important: DO NOT close the main soundcheck window here ---
        # self.send_cancel_command() # Send cancel only when closing for good
        # self.close_window() # Defer this call


    def close_report_and_main(self):
        """Closes the report window (if open) and then the main soundcheck window."""
        print("[Admin Soundcheck] Closing report and finishing soundcheck.")
        # Destroy report window first
        if self.report_window and self.report_window.winfo_exists():
            self.report_window.destroy()
            self.report_window = None

        # Now proceed with the main window cleanup and closure
        self.send_cancel_command()
        self.close_window()


    def cancel_soundcheck(self):
        """Cancels the soundcheck and closes the main window. Also closes report if open."""
        print("[Admin Soundcheck] Cancelling soundcheck...")
        if self.report_window and self.report_window.winfo_exists():
             self.report_window.destroy()
             self.report_window = None
        self.send_cancel_command()
        self.close_window()

    def send_cancel_command(self):
        """Sends the cancel command to kiosks."""
        print("[Admin Soundcheck] Sending cancel command to kiosks.")
        # Ensure app and interface_builder are accessible and kiosks are present
        if hasattr(self.app, 'interface_builder') and hasattr(self.app.interface_builder, 'connected_kiosks'):
            for name in self.kiosk_names:
                 # Check if kiosk still exists in the main interface before sending cancel
                if name in self.app.interface_builder.connected_kiosks:
                    try:
                        self.app.network_handler.send_soundcheck_cancel_command(name) # Needs implementation
                    except Exception as e:
                        print(f"[Admin Soundcheck] Error sending cancel to {name}: {e}")
                else:
                    print(f"[Admin Soundcheck] Kiosk {name} no longer connected, skipping cancel command.")
        else:
             print("[Admin Soundcheck] Warning: Cannot access connected kiosks list to send cancel commands.")


    def close_window(self):
        """Safely closes the main soundcheck window and cleans up resources."""
        if not self.closed:
            self.closed = True
            print("[Admin Soundcheck] Closing main soundcheck window and cleaning up temp files.")

            # Stop any active playback
            if pygame.mixer.get_init():
                pygame.mixer.stop()

            # Clean up temporary files
            for kiosk_name, temp_path in self.temp_files.items():
                if temp_path and os.path.exists(temp_path): # Check if path is not None/empty
                    try:
                        os.remove(temp_path)
                        print(f"[Admin Soundcheck] Removed temp file: {temp_path}")
                    except Exception as e:
                        print(f"[Admin Soundcheck] Error removing temp file {temp_path}: {e}")
            self.temp_files.clear() # Clear the dictionary

            # Destroy the main soundcheck window if it exists
            if self.window and self.window.winfo_exists():
                try:
                    self.window.grab_release() # Release grab before destroying
                    self.window.destroy()
                except tk.TclError as e:
                    print(f"[Admin Soundcheck] Error destroying window: {e}") # Handle race condition/errors

            # Nullify reference in network handler if passed
            # Check existence carefully
            if hasattr(self.app, 'network_handler') and \
               hasattr(self.app.network_handler, 'soundcheck_instance') and \
               self.app.network_handler.soundcheck_instance == self:
                self.app.network_handler.soundcheck_instance = None
                print("[Admin Soundcheck] Cleared network handler reference.")

            print("[Admin Soundcheck] Cleanup complete.")
        else:
            print("[Admin Soundcheck] close_window called but already closed.")
