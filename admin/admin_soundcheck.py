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
        self.font = ('TkDefaultFont', 10, 'bold')

        # Initialize pygame mixer if not already done (e.g., by AdminAudioManager)
        #if not pygame.mixer.get_init():
        #    try:
        #        # Initialize with settings matching recording parameters
        #        pygame.mixer.init(frequency=11025, size=16, channels=1)
        #        print("[Admin Soundcheck] Pygame mixer initialized with optimal settings.")
        #    except Exception as e:
        #        print(f"[Admin Soundcheck] Pygame mixer init error: {e}")
        #        messagebox.showerror("Audio Error", "Could not initialize audio playback.")
        #        # Optionally handle differently, maybe disable 'Listen' buttons

        # --- Window Setup ---
        self.window = tk.Toplevel(parent_root)
        self.window.title("Kiosk Soundcheck Tool")
        self.window.geometry("700x400") # Adjusted size for additional buttons
        self.window.resizable(False, False)
        self.window.grab_set() # Make the soundcheck window modal initially

        # --- Data Storage ---
        # Status: None (pending), True (pass), False (fail)
        # 'initiated' tracks if the soundcheck process has started for this kiosk
        self.kiosk_status = {
            name: {'initiated': False, 'touch': None, 'audio': None, 'mic': None, 'audio_sample': None}
            for name in kiosk_names
        }
        self.ui_elements = {name: {} for name in kiosk_names} # To store labels/buttons

        # --- UI Creation ---
        main_frame = ttk.Frame(self.window, padding="10")
        main_frame.pack(expand=True, fill="both")

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        # Adjusted widths/paddings for headers to align with dynamic content
        ttk.Label(header_frame, text="Computer Name", width=18, anchor="w", font=self.font).pack(side="left", padx=(5,10))
        ttk.Label(header_frame, text="Touch", width=8, anchor="center", font=self.font).pack(side="left", padx=5)
        ttk.Label(header_frame, text="Audio Out", width=10, anchor="center", font=self.font).pack(side="left", padx=5)
        ttk.Label(header_frame, text="Mic In", width=8, anchor="center", font=self.font).pack(side="left", padx=5)
        ttk.Label(header_frame, text="Mic Sample", width=25, anchor="center", font=self.font).pack(side="left", padx=5, fill="x", expand=True)


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

        # --- Soundcheck no longer starts automatically for all kiosks ---
        # self.send_start_command() # REMOVED

    def create_kiosk_row(self, parent_frame, kiosk_name):
        """Creates the UI elements for a single kiosk row. Status elements are initially hidden."""
        row_frame = ttk.Frame(parent_frame)
        row_frame.pack(fill="x", pady=2)

        # Kiosk name as a button to initiate its soundcheck
        kiosk_name_button = ttk.Button(row_frame, text=kiosk_name, width=21, # Matches header width
                                      command=lambda n=kiosk_name: self.initiate_soundcheck_for_kiosk(n))
        kiosk_name_button.pack(side="left", padx=(5,0)) # Matches header padx

        # Status Indicators (created with font, but NOT PACKED initially)
        touch_label = ttk.Label(row_frame, text="", font=self.font, width=8, anchor="center")
        audio_label = ttk.Label(row_frame, text="", font=self.font, width=10, anchor="center") # Match header width
        mic_label = ttk.Label(row_frame, text="", font=self.font, width=8, anchor="center")

        # Sample Frame (created, but NOT PACKED initially)
        sample_frame = ttk.Frame(row_frame)
        # sample_frame children are created but packed when sample_frame itself is shown/configured

        listen_button = ttk.Button(sample_frame, text="Listen", width=8, state="disabled",
                                   command=lambda n=kiosk_name: self.play_audio_sample(n))
        # listen_button will be packed into sample_frame later

        mic_buttons_frame = ttk.Frame(sample_frame)
        # mic_buttons_frame will be packed into sample_frame later (by play_audio_sample)

        mic_check_button = ttk.Button(mic_buttons_frame, text="✓", width=3,
                                      command=lambda n=kiosk_name: self.set_mic_status(n, True))
        mic_check_button.pack(side="left", padx=(0, 2)) # Packed within its parent

        mic_fail_button = ttk.Button(mic_buttons_frame, text="✕", width=3,
                                    command=lambda n=kiosk_name: self.set_mic_status(n, False))
        mic_fail_button.pack(side="left") # Packed within its parent

        self.ui_elements[kiosk_name] = {
            'name_btn': kiosk_name_button,
            'touch_label': touch_label,
            'audio_label': audio_label,
            'mic_label': mic_label,
            'sample_frame': sample_frame,
            'listen_btn': listen_button,
            'mic_buttons_frame': mic_buttons_frame
            # 'mic_check_btn' and 'mic_fail_btn' are part of mic_buttons_frame
        }

    def initiate_soundcheck_for_kiosk(self, kiosk_name):
        """Sends soundcheck command to one kiosk and reveals its UI elements."""
        if self.kiosk_status[kiosk_name].get('initiated', False):
            # Should not happen if button is disabled, but good for safety
            print(f"[Admin Soundcheck] Soundcheck already initiated for {kiosk_name}")
            return

        print(f"[Admin Soundcheck] Initiating soundcheck for {kiosk_name}")
        self.app.network_handler.send_soundcheck_command(kiosk_name)

        # Update status: mark as initiated and reset test results
        self.kiosk_status[kiosk_name]['initiated'] = True
        self.kiosk_status[kiosk_name]['touch'] = None
        self.kiosk_status[kiosk_name]['audio'] = None
        self.kiosk_status[kiosk_name]['mic'] = None
        self.kiosk_status[kiosk_name]['audio_sample'] = None # Clear any old sample path

        ui = self.ui_elements[kiosk_name]

        # Pack and configure the status labels for this kiosk
        ui['touch_label'].config(text="?", foreground="gray")
        ui['touch_label'].pack(side="left", padx=5) # Matches header padx

        ui['audio_label'].config(text="?", foreground="gray")
        ui['audio_label'].pack(side="left", padx=5) # Matches header padx

        ui['mic_label'].config(text="?", foreground="gray")
        ui['mic_label'].pack(side="left", padx=5) # Matches header padx

        # Pack and configure the sample_frame and its listen_button
        ui['sample_frame'].pack(side="left", padx=5, fill="x", expand=True) # Matches header
        
        ui['listen_btn'].config(state="disabled")
        ui['listen_btn'].pack(side="left", padx=(50, 0)) # Original padding for listen button

        # Ensure mic_buttons_frame (child of sample_frame) is initially hidden
        ui['mic_buttons_frame'].pack_forget()

        # Disable the kiosk name button to prevent re-initiation
        ui['name_btn'].config(state="disabled")
        # Optionally, change text: ui['name_btn'].config(text=f"{kiosk_name} (Pending)")

    # send_start_command(self) method is now removed.

    def update_status(self, kiosk_name, test_type, result, audio_data=None):
        """Updates the status for a kiosk and refreshes its UI row, if initiated."""
        if self.window.winfo_exists():
            # Only process update if soundcheck was initiated for this kiosk
            if kiosk_name in self.kiosk_status and self.kiosk_status[kiosk_name].get('initiated', False):
                 self.window.after(0, self._update_status_ui, kiosk_name, test_type, result, audio_data)
            # else:
            #    print(f"[Admin Soundcheck] Update for {kiosk_name} (type {test_type}) ignored (soundcheck not initiated).")
        # else:
        #      print(f"[Admin Soundcheck] Update ignored for {kiosk_name} (window destroyed)")


    def _update_status_ui(self, kiosk_name, test_type, result, audio_data=None):
        """Internal method to update UI, called via window.after"""
        # Double check, as state might change between after() call and execution
        if self.closed or kiosk_name not in self.kiosk_status or \
           not self.kiosk_status[kiosk_name].get('initiated', False):
            return

        print(f"[Admin Soundcheck] UI Update: Kiosk={kiosk_name}, Test={test_type}, Result={result}")

        # --- Handle audio sample logic first ---
        if test_type == 'audio_sample':
            if result: # Result is True if sample received
                try:
                    # Clear any existing temp file
                    if kiosk_name in self.temp_files and self.temp_files[kiosk_name] and os.path.exists(self.temp_files[kiosk_name]):
                        try: os.remove(self.temp_files[kiosk_name])
                        except OSError as e: print(f"[Admin Soundcheck] Error removing old temp file {self.temp_files[kiosk_name]}: {e}")
                        self.temp_files[kiosk_name] = None

                    decoded_data = base64.b64decode(audio_data)
                    fd, temp_path = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    with open(temp_path, 'wb') as f: f.write(decoded_data)
                    self.temp_files[kiosk_name] = temp_path
                    print(f"[Admin Soundcheck] Audio sample saved to temp file for {kiosk_name}: {temp_path}")
                    self.kiosk_status[kiosk_name]['audio_sample'] = temp_path

                    if kiosk_name in self.ui_elements and 'listen_btn' in self.ui_elements[kiosk_name]:
                        self.ui_elements[kiosk_name]['listen_btn'].config(state="normal")
                except Exception as e:
                    print(f"[Admin Soundcheck] Error processing audio sample for {kiosk_name}: {e}")
                    import traceback; traceback.print_exc()
                    self.kiosk_status[kiosk_name]['mic'] = False
                    self.kiosk_status[kiosk_name]['audio_sample'] = None
                    if kiosk_name in self.ui_elements:
                         if 'listen_btn' in self.ui_elements[kiosk_name]: self.ui_elements[kiosk_name]['listen_btn'].config(state="disabled")
                         if 'mic_label' in self.ui_elements[kiosk_name]: self.ui_elements[kiosk_name]['mic_label'].config(text="✕", foreground="red") # Use mic_label
                         if 'mic_buttons_frame' in self.ui_elements[kiosk_name]: self.ui_elements[kiosk_name]['mic_buttons_frame'].pack_forget()
            else: # Result is False for audio_sample (e.g., kiosk failed to record/send)
                 print(f"[Admin Soundcheck] Received failed audio_sample status for {kiosk_name}")
                 self.kiosk_status[kiosk_name]['mic'] = False
                 self.kiosk_status[kiosk_name]['audio_sample'] = None
                 if kiosk_name in self.ui_elements:
                     if 'listen_btn' in self.ui_elements[kiosk_name]: self.ui_elements[kiosk_name]['listen_btn'].config(state="disabled")
                     if 'mic_label' in self.ui_elements[kiosk_name]: self.ui_elements[kiosk_name]['mic_label'].config(text="✕", foreground="red") # Use mic_label
                     if 'mic_buttons_frame' in self.ui_elements[kiosk_name]: self.ui_elements[kiosk_name]['mic_buttons_frame'].pack_forget()
            return # Don't process further UI for 'audio_sample' type itself

        # --- Update status for touch, audio, mic (manual update by user or direct status) ---
        if test_type in self.kiosk_status[kiosk_name]:
             self.kiosk_status[kiosk_name][test_type] = result

        # Update the corresponding UI label (touch_label, audio_label, mic_label)
        label_widget_key_map = {
            'touch': 'touch_label',
            'audio': 'audio_label',
            'mic': 'mic_label'
        }
        if test_type in label_widget_key_map:
            actual_ui_key = label_widget_key_map[test_type]
            label = self.ui_elements[kiosk_name].get(actual_ui_key)
            if label: # Check if label widget exists and is packed
                if result is True:
                    label.config(text="✓", foreground="green")
                elif result is False:
                    label.config(text="✕", foreground="red")
                else: # None (pending/reset)
                    label.config(text="?", foreground="gray")
            # else: print(f"Warning: UI element {actual_ui_key} not found or not packed for {kiosk_name}")

        # Special handling for 'mic' update: hide validation buttons if mic test explicitly fails or is reset.
        if test_type == 'mic' and result is not True: # Mic failed or reset to pending by something other than play_audio_sample
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
            self.update_status(kiosk_name, 'mic', False) # Mark mic as failed, will hide buttons
            return

        print(f"[Admin Soundcheck] Playing audio sample for {kiosk_name} from {temp_path}")

        if not pygame.mixer.get_init():
            messagebox.showerror("Audio Error", "Audio playback system not initialized.", parent=self.window)
            return

        pygame.mixer.stop() # Stop any currently playing sound

        try:
            sound = pygame.mixer.Sound(temp_path)
            sound.play()

            # Show the mic validation buttons AND reset mic status display to '?'
            if kiosk_name in self.ui_elements:
                if 'mic_label' in self.ui_elements[kiosk_name]: # Target the specific label widget
                     self.ui_elements[kiosk_name]['mic_label'].config(text="?", foreground="gray")
                self.kiosk_status[kiosk_name]['mic'] = None # Reset status pending validation

                if 'mic_buttons_frame' in self.ui_elements[kiosk_name]:
                    frame_widget = self.ui_elements[kiosk_name]['mic_buttons_frame']
                    # Pack into its parent (sample_frame) if not already visible
                    if not frame_widget.winfo_ismapped():
                        frame_widget.pack(side="left", padx=(10, 0))
        except Exception as e:
            print(f"[Admin Soundcheck] Error playing audio sample for {kiosk_name}: {e}")
            import traceback; traceback.print_exc()
            messagebox.showerror("Playback Error", f"Could not play audio sample for {kiosk_name}:\n{e}", parent=self.window)
            self.update_status(kiosk_name, 'mic', False) # Mark mic as failed, will hide buttons


    def set_mic_status(self, kiosk_name, is_working):
        """Sets the microphone status based on user validation."""
        print(f"[Admin Soundcheck] Setting mic status for {kiosk_name} to {is_working}")
        self.update_status(kiosk_name, 'mic', is_working)
        # If is_working is False, _update_status_ui's mic handling will hide buttons.
        # If True, buttons remain visible.

    def finish_soundcheck(self):
        """Generates a report for initiated soundchecks. Does NOT close main window yet."""
        if self.report_window and self.report_window.winfo_exists():
            self.report_window.lift()
            return

        self.report_window = tk.Toplevel(self.app.root)
        self.report_window.title("Soundcheck Report")
        self.report_window.geometry("500x400")
        self.report_window.grab_set()
        self.report_window.transient(self.window)

        report_text = scrolledtext.ScrolledText(self.report_window, wrap=tk.WORD, state='disabled', height=15)
        report_text.pack(expand=True, fill='both', padx=10, pady=5)
        report_text.tag_configure("green_italic", foreground="green", font=('TkDefaultFont', 9, 'italic'))
        report_text.tag_configure("red", foreground="red")
        report_text.tag_configure("bold", font=('TkDefaultFont', 9, 'bold'))

        report_text.configure(state='normal')
        report_text.insert(tk.END, "")

        any_issues_found = False
        any_initiated = False # Flag to check if any soundcheck was run
        sorted_kiosk_names = sorted(self.kiosk_status.keys())

        for name in sorted_kiosk_names:
            # Only include kiosks for which soundcheck was initiated in the report
            if not self.kiosk_status[name].get('initiated', False):
                continue
            any_initiated = True

            status = self.kiosk_status[name]
            all_success = True
            issue_details = []
            success_details = []

            for test in ['touch', 'audio', 'mic']:
                result = status.get(test, None)
                test_name_cap = test.capitalize()
                if result is True:
                    success_details.append(f"  - {test_name_cap}: Pass")
                elif result is False:
                    issue_details.append((f"  - {test_name_cap}: Fail", ["bold"]))
                    all_success = False
                    any_issues_found = True
                else: # None (incomplete)
                    issue_details.append((f"  - {test_name_cap}: Incomplete", ["bold"]))
                    all_success = False
                    any_issues_found = True # Treat incomplete as an issue

            if all_success:
                report_text.insert(tk.END, f"Kiosk: {name} - OK\n", ("green_italic"))
            else:
                report_text.insert(tk.END, f"Kiosk: {name} - ISSUES FOUND\n", ("red"))
                for text_content, tags in issue_details:
                    report_text.insert(tk.END, f"{text_content}\n", tags)
                for text_content in success_details:
                    report_text.insert(tk.END, f"{text_content}\n", ("green_italic"))
            report_text.insert(tk.END, "\n")

        if not any_initiated:
             report_text.insert(tk.END, "No soundchecks were initiated for any kiosk.\n")
        elif not any_issues_found: # This means all *initiated* soundchecks were OK
             report_text.insert(tk.END, "\nAll initiated soundchecks reported OK.", ("green_italic"))
        else: # Issues found in at least one *initiated* soundcheck
             report_text.insert(tk.END, "\nISSUES FOUND in initiated soundchecks.")

        report_text.configure(state='disabled')

        report_button_frame = ttk.Frame(self.report_window)
        report_button_frame.pack(pady=(5, 10))
        close_all_button = ttk.Button(report_button_frame, text="Close Report & Finish",
                                      command=self.close_report_and_main)
        close_all_button.pack(side=tk.RIGHT, padx=5)
        self.report_window.protocol("WM_DELETE_WINDOW", self.close_report_and_main)


    def close_report_and_main(self):
        """Closes the report window (if open) and then the main soundcheck window."""
        print("[Admin Soundcheck] Closing report and finishing soundcheck.")
        if self.report_window and self.report_window.winfo_exists():
            self.report_window.destroy()
            self.report_window = None
        self.send_cancel_command() # Send cancel to kiosks
        self.close_window() # Close main soundcheck window and cleanup


    def cancel_soundcheck(self):
        """Cancels the soundcheck and closes the main window. Also closes report if open."""
        print("[Admin Soundcheck] Cancelling soundcheck...")
        if self.report_window and self.report_window.winfo_exists():
             self.report_window.destroy()
             self.report_window = None
        self.send_cancel_command() # Send cancel to kiosks
        self.close_window() # Close main soundcheck window and cleanup

    def send_cancel_command(self):
        """Sends the cancel command to relevant kiosks."""
        print("[Admin Soundcheck] Sending cancel command to kiosks.")
        if hasattr(self.app, 'interface_builder') and hasattr(self.app.interface_builder, 'connected_kiosks'):
            for name in self.kiosk_names: # Iterate over all kiosks originally intended for soundcheck
                # Optionally, only send cancel to 'initiated' kiosks:
                # if self.kiosk_status[name].get('initiated', False):
                if name in self.app.interface_builder.connected_kiosks: # Check if kiosk is still listed as connected
                    try:
                        self.app.network_handler.send_soundcheck_cancel_command(name)
                    except Exception as e:
                        print(f"[Admin Soundcheck] Error sending cancel to {name}: {e}")
                # else:
                #    print(f"[Admin Soundcheck] Kiosk {name} no longer connected, skipping cancel command.")
        else:
             print("[Admin Soundcheck] Warning: Cannot access connected kiosks list to send cancel commands.")


    def close_window(self):
        """Safely closes the main soundcheck window and cleans up resources."""
        if not self.closed:
            self.closed = True
            print("[Admin Soundcheck] Closing main soundcheck window and cleaning up temp files.")
            if pygame.mixer.get_init():
                pygame.mixer.stop()
            for kiosk_name, temp_path in self.temp_files.items():
                if temp_path and os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                        print(f"[Admin Soundcheck] Removed temp file: {temp_path}")
                    except Exception as e:
                        print(f"[Admin Soundcheck] Error removing temp file {temp_path}: {e}")
            self.temp_files.clear()
            if self.window and self.window.winfo_exists():
                try:
                    self.window.grab_release()
                    self.window.destroy()
                except tk.TclError as e:
                    print(f"[Admin Soundcheck] Error destroying window: {e}")
            if hasattr(self.app, 'network_handler') and \
               hasattr(self.app.network_handler, 'soundcheck_instance') and \
               self.app.network_handler.soundcheck_instance == self:
                self.app.network_handler.soundcheck_instance = None
                print("[Admin Soundcheck] Cleared network handler reference.")
            print("[Admin Soundcheck] Cleanup complete.")
        # else:
        #    print("[Admin Soundcheck] close_window called but already closed.")