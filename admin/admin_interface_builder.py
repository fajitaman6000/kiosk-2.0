import tkinter as tk
from tkinter import ttk, filedialog
import time
from video_client import VideoClient
from audio_client import AudioClient
from classic_audio_hints import ClassicAudioHints
from setup_stats_panel import setup_stats_panel, update_volume_meter
from hint_functions import save_manual_hint, clear_manual_hint, send_hint
from admin_audio_manager import AdminAudioManager
from manager_settings import ManagerSettings
import cv2 # type: ignore
from PIL import Image, ImageTk
import threading
import os
import json
import io
import base64


class AdminInterfaceBuilder:
    def __init__(self, app):
        self.app = app
        self.main_container = None
        self.connected_kiosks = {}
        self.selected_kiosk = None
        self.stats_elements = {
            'time_label': None,
            'hints_label': None,
            'msg_entry': None,
            'send_btn': None,
            'camera_btn': None
        }
        self.video_client = VideoClient()
        self.audio_clients = {}
        self.audio_active = {}
        self.speaking = {}
        self.preferred_audio_device_index = {}
        self.current_hint_image = None
        self.hint_manager = ManagerSettings(app, self)  # Initialize hint manager
        self.auto_reset_timer_ids = {}
        self.setup_ui()
        
        # Start timer update loop using app's root
        self.app.root.after(1000, self.update_timer_display)

    ROOM_COLORS = {
        4: "#006400",  # Zombie - dark green
        2: "#FF1493",  # Morning After - dark pink 
        1: "#8B0000",  # Casino - dark red
        6: "#377d94",  # Atlantis - light blue
        7: "#FF8C00",  # Time Machine - orange
        3: "#9240a8",  # Wizard - dark teal
        5: "#808080",  # Haunted - grey
    }

    def start_auto_reset_timer(self, computer_name):
        """Starts (or restarts) the auto-reset timer."""

        duration = 60

        # Cancel any existing timer for this kiosk
        if computer_name in self.auto_reset_timer_ids:
            self.app.root.after_cancel(self.auto_reset_timer_ids[computer_name])
            del self.auto_reset_timer_ids[computer_name]

        # Initial update of the label
        self.update_auto_reset_timer_display(computer_name, duration)

        def reset_and_clear():
            self.reset_kiosk(computer_name)
            if computer_name in self.auto_reset_timer_ids:
                del self.auto_reset_timer_ids[computer_name]
            if self.stats_elements['auto_reset_label']:
                self.stats_elements['auto_reset_label'].config(text=" ")

        # Schedule the reset_kiosk call and store the after_id
        after_id = self.app.root.after(duration*1000, reset_and_clear)
        self.auto_reset_timer_ids[computer_name] = after_id

        # Start countdown
        self.auto_reset_countdown(computer_name, duration) # Start the countdown   

    def auto_reset_countdown(self, computer_name, remaining_seconds):
        """Updates the auto-reset timer display every second"""
        if computer_name in self.auto_reset_timer_ids:
            self.update_auto_reset_timer_display(computer_name, remaining_seconds)

            if remaining_seconds > 0:
                self.app.root.after(1000, self.auto_reset_countdown, computer_name, remaining_seconds -1)

    def update_auto_reset_timer_display(self, computer_name, remaining_seconds):
        """Updates the 'Auto resetting kiosk in...' label."""
        if 'auto_reset_label' in self.stats_elements and self.stats_elements['auto_reset_label']:
            minutes = remaining_seconds // 60
            seconds = remaining_seconds % 60
            self.stats_elements['auto_reset_label'].config(
                text=f"Auto resetting kiosk in... {minutes:02d}:{seconds:02d}"
            )

    def setup_ui(self):
        # Create left panel that spans full height
        self.left_panel = tk.Frame(
            self.app.root,
            bg='SystemButtonFace',  # Use system default background color
            width=220  # Fixed width for left panel
        )
        self.left_panel.pack(
            side='left',     # Place on left side
            fill='y',        # Fill vertical space
            expand=False,    # Don't expand horizontally
            padx=5,          # Add padding from window edge
            pady=5           # Add padding from top/bottom
        )
        
        # Prevent the panel from shrinking below requested width
        self.left_panel.pack_propagate(False)
        
        # Create main container for existing content (kiosks and stats)
        self.main_container = tk.Frame(self.app.root)
        self.main_container.pack(
            side='left',      # Place to right of left panel
            fill='both',      # Fill remaining space
            expand=True,      # Expand to fill space
            padx=10,
            pady=5
        )
        
        # Create frames within main container
        left_frame = tk.Frame(self.main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=0)
        
        # Create a horizontal container for kiosk frame and hints button
        kiosk_container = tk.Frame(left_frame)
        kiosk_container.pack(fill='both', expand=True)
        
        # Create kiosk frame on the left side of container
        self.kiosk_frame = tk.LabelFrame(kiosk_container, text="Online Kiosk Computers", padx=10, pady=5)
        self.kiosk_frame.pack(side='left', fill='both', expand=True)
        
        # Load all required icons
        icon_dir = os.path.join("admin_icons")
        try:
            settings_icon = Image.open(os.path.join(icon_dir, "settings.png"))
            settings_icon = settings_icon.resize((32, 32), Image.Resampling.LANCZOS)
            settings_icon = ImageTk.PhotoImage(settings_icon)
        except Exception as e:
            print(f"[interface builder]Error loading icons: {e}")
            settings_icon = None

        # Create small frame for hints button on the right side of container
        hints_button_frame = tk.Frame(kiosk_container)
        hints_button_frame.pack(side='left', anchor='n', padx=(10,0), pady=8)  # Anchor to top
        
        # Add Hints Library button in its own frame - small and square
        self.settings_button = tk.Button(
            hints_button_frame,
            image=settings_icon if settings_icon else None,
            command=lambda: self.show_hints_library(),
            #bg='#C6AE66',
            fg='white',
            font=('Arial', 9),
            width=32,       # Set fixed width for the icon
            height=32,     # Set fixed height for the icon
            bd=0,
            highlightthickness=0,
            compound=tk.LEFT,
            cursor="hand2"
        )
        self.settings_button.pack(anchor='n')  # Anchor to top of its frame
        
        # Keep a reference to settings icon so that it does not get gc'ed
        if settings_icon:
           self.settings_button.image = settings_icon
        
        # Load Sync Icon
        try:
           sync_icon = Image.open(os.path.join(icon_dir, "sync.png"))
           sync_icon = sync_icon.resize((28,28), Image.Resampling.LANCZOS)
           sync_icon = ImageTk.PhotoImage(sync_icon)
        except Exception as e:
            print(f"[interface builder] Error loading sync icon: {e}")
            sync_icon = None
        
        # Add Sync button, directly below the hints button
        self.sync_button = tk.Button( # Assign to self so that we can access it
            hints_button_frame,
            image=sync_icon if sync_icon else None,
            fg='white',
            font=('Arial', 9),
            width=32,  # set to same width as hints button
            height=32, # set to same height as hints button
            bd=0,
            highlightthickness=0,
            compound=tk.LEFT,
            cursor="hand2"
        )
        self.sync_button.pack(anchor='n', pady=(25,0))  # Keep below hints button

        if sync_icon:
            self.sync_button.image = sync_icon

        # Load soundcheck icon button                                                    --BUTTON PLACEHOLDER
        try:
           soundcheck_icon = Image.open(os.path.join(icon_dir, "soundcheck.png"))
           soundcheck_icon = soundcheck_icon.resize((32,32), Image.Resampling.LANCZOS)
           soundcheck_icon = ImageTk.PhotoImage(soundcheck_icon)
        except Exception as e:
            print(f"[interface builder] Error loading soundcheck icon: {e}")
            soundcheck_icon = None
        
        # Add soundcheck button, directly below the sync button
        self.soundcheck_button = tk.Button(
            hints_button_frame,
            image=soundcheck_icon if soundcheck_icon else None,
            #command=lambda: self.app.methodDoesn'tExistYet(),
            #bg='#C6AE66',
            fg='white',
            font=('Arial', 9),
            width=32,  # set to same width as hints button
            height=32, # set to same height as hints button
            bd=0,
            highlightthickness=0,
            compound=tk.LEFT,
            cursor="hand2"
        )
        self.soundcheck_button.pack(anchor='n', pady=(25,0))  # Keep below hints button

        if soundcheck_icon:
            self.soundcheck_button.image = soundcheck_icon

        # Create stats frame below the kiosk container
        self.stats_frame = tk.LabelFrame(left_frame, text="No Room Selected", padx=10, pady=5)
        self.stats_frame.pack(fill='both', expand=True, pady=10)

    def show_hints_library(self):
        """Show the Hints Library interface"""
        self.hint_manager.show_hint_manager() # call the show method

    def setup_audio_hints(self):
        """Set up the Classic Audio Hints panel"""
        #print("[interface builder]=== AUDIO HINTS SETUP START ===")
        
        def on_room_change(room_name):
            print(f"[interface builder]=== ROOM CHANGE CALLBACK ===")
            print(f"[interface builder]Audio hints room change called for: {room_name}")
            print(f"[interface builder]Selected kiosk: {self.selected_kiosk}")
            print(f"[interface builder]Has assignments: {self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments}")
            
            if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
                print(f"[interface builder]Room number: {room_num}")
                room_dirs = {
                    6: "atlantis",
                    1: "casino",
                    5: "haunted",
                    2: "ma",
                    7: "time",
                    3: "wizard",
                    4: "zombie"
                }
                if room_num in room_dirs:
                    print(f"[interface builder]Mapped to directory: {room_dirs[room_num]}")
                    self.audio_hints.update_room(room_dirs[room_num])
            print("[interface builder]=== ROOM CHANGE CALLBACK END ===\n")
        
        # Create ClassicAudioHints instance
        #print("[interface builder]Creating new ClassicAudioHints instance...")
        self.audio_hints = ClassicAudioHints(self.stats_frame, on_room_change, self.app)
        #print("[interface builder]=== AUDIO HINTS SETUP END ===\n")

    def setup_stats_panel(self, computer_name):
        # use helper function setup_stats_panel.py
        setup_stats_panel(self, computer_name)

    def select_image(self):
        """Update the image prop dropdown with available props."""
        self.update_image_props()

    def update_image_props(self):
        """Update the image prop dropdown with props for the current room"""
        if 'image_btn' not in self.stats_elements:
            return
            
        # Load prop mappings from JSON
        try:
            with open("prop_name_mapping.json", "r") as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[image hints] Error loading prop mappings: {e}")
            prop_mappings = {}

        # Use current room from audio hints if available
        room_name = self.audio_hints.current_room if hasattr(self, "audio_hints") else None
        room_name = room_name.lower() if room_name else None
        
        room_key = None
        if hasattr(self, "audio_hints") and hasattr(self.audio_hints, "ROOM_MAP"):
            room_key = self.audio_hints.ROOM_MAP.get(room_name)
            #if(room_name != None):
                #print(f"[image hints] Updating props for room: {room_name} (key: {room_key})")
        
        props_list = []
        if room_key and room_key in prop_mappings:
            props = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
            props.sort(key=lambda x: x[1]["order"])
            props_list = [f"{p[1]['display']} ({p[0]})" for p in props]
            #print(f"[image hints] Found {len(props_list)} props for room")
        
        self.stats_elements['image_btn']['values'] = props_list
        self.img_prop_var.set("")

    def on_image_prop_select(self, event):
        """When a prop is selected, hide manual hint and show image selection"""
        selected_item = self.img_prop_var.get()
        if not selected_item:
            return
        
        # Hide manual hint text box and buttons
        if 'msg_entry' in self.stats_elements:
            self.stats_elements['msg_entry'].pack_forget()
        if 'hint_buttons_frame' in self.stats_elements:
            self.stats_elements['hint_buttons_frame'].pack_forget()
        
        # Show back button and listbox
        if 'prop_control_buttons' in self.stats_elements:
            self.stats_elements['prop_control_buttons'].pack(fill='x', pady=5)
            self.stats_elements['prop_back_btn'].pack(side='left', padx=5)
            self.stats_elements['prop_attach_btn'].pack_forget()
        
        # Clear the listbox and show it
        self.stats_elements['image_listbox'].delete(0, tk.END)
        self.stats_elements['image_listbox'].pack(pady=5, fill='x')
        
        # Extract original prop name from the dropdown text
        original_name = selected_item.split("(")[-1].rstrip(")")
        
        room_name = self.audio_hints.current_room if hasattr(self, "audio_hints") else None
        room_name = room_name.lower() if room_name else None
        
        try:
            with open("prop_name_mapping.json", "r") as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[image hints] Error loading prop mappings: {e}")
            prop_mappings = {}
        
        room_key = None
        if hasattr(self, "audio_hints") and hasattr(self.audio_hints, "ROOM_MAP"):
            room_key = self.audio_hints.ROOM_MAP.get(room_name)
        
        display_name = ""
        if room_key and room_key in prop_mappings:
            mappings = prop_mappings[room_key]["mappings"]
            if original_name in mappings:
                display_name = mappings[original_name]["display"]
        
        folder_path = os.path.join(self.image_root, room_name, display_name)
        if os.path.exists(folder_path):
            allowed_exts = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
            image_files = [f for f in os.listdir(folder_path) if os.path.splitext(f)[1].lower() in allowed_exts]
            for img in sorted(image_files):
                self.stats_elements['image_listbox'].insert(tk.END, img)
                
        # Update the layout to ensure proper spacing
        if 'img_prop_frame' in self.stats_elements:
            self.stats_elements['img_prop_frame'].pack(fill='x', expand=True)

    def on_image_file_select(self, event):
        """When an image is selected from the listbox, show preview and enable attach button"""
        selection = self.stats_elements['image_listbox'].curselection()
        if not selection:
            return
            
        image_name = self.stats_elements['image_listbox'].get(selection[0])
        selected_item = self.img_prop_var.get()
        if not selected_item:
            return
            
        # Extract original prop name from the dropdown text
        original_name = selected_item.split("(")[-1].rstrip(")")
        
        room_name = self.audio_hints.current_room if hasattr(self, "audio_hints") else None
        room_name = room_name.lower() if room_name else None
        
        try:
            with open("prop_name_mapping.json", "r") as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[image hints] Error loading prop mappings: {e}")
            prop_mappings = {}
        
        room_key = None
        if hasattr(self, "audio_hints") and hasattr(self.audio_hints, "ROOM_MAP"):
            room_key = self.audio_hints.ROOM_MAP.get(room_name)
        
        display_name = ""
        if room_key and room_key in prop_mappings:
            mappings = prop_mappings[room_key]["mappings"]
            if original_name in mappings:
                display_name = mappings[original_name]["display"]
        
        image_path = os.path.join(self.image_root, room_name, display_name, image_name)
        try:
            from PIL import Image, ImageTk
            image = Image.open(image_path)
            ratio = min(200 / image.width, 200 / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.stats_elements['image_preview'].configure(image=photo)
            self.stats_elements['image_preview'].image = photo
            
            # Store the image path for attaching
            self.current_image_file = image_path
            
            # Show the preview and attach button
            self.stats_elements['img_control_frame'].pack(fill='x', pady=5)
            self.stats_elements['prop_attach_btn'].pack(side='left', padx=5)
        except Exception as e:
            print(f"[image hints] Error previewing image: {e}")

    def show_manual_hint(self):
        """Show the manual hint text box and hide image selection"""
        if 'image_listbox' in self.stats_elements:
            self.stats_elements['image_listbox'].pack_forget()
        if 'img_control_frame' in self.stats_elements:
            self.stats_elements['img_control_frame'].pack_forget()
        if 'attached_image_label' in self.stats_elements:
            self.stats_elements['attached_image_label'].pack_forget()
        if 'prop_control_buttons' in self.stats_elements:
            self.stats_elements['prop_control_buttons'].pack_forget()
            
        # Show text box and buttons
        if 'msg_entry' in self.stats_elements:
            self.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)
        if 'hint_buttons_frame' in self.stats_elements:
            self.stats_elements['hint_buttons_frame'].pack(pady=5)
        
        # Reset image selection state
        self.current_hint_image = None
        if 'image_btn' in self.stats_elements:
            self.stats_elements['image_btn'].set('')

    def attach_image(self):
        """Attach the selected image to the hint"""
        if hasattr(self, "current_image_file") and self.current_image_file:
            # Show the attached filename
            filename = os.path.basename(self.current_image_file)
            self.stats_elements['attached_image_label'].config(text=f"Attached: {filename}")
            self.stats_elements['img_control_frame'].pack_forget()
            self.stats_elements['image_listbox'].pack_forget()
            self.stats_elements['prop_control_buttons'].pack_forget()
            self.stats_elements['attached_image_label'].pack(pady=5)
            
            # Show manual hint text box and buttons
            if 'msg_entry' in self.stats_elements:
                self.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)
            if 'hint_buttons_frame' in self.stats_elements:
                self.stats_elements['hint_buttons_frame'].pack(pady=5)
            
            # Store image path for sending
            try:
                # Get relative path from sync_directory
                rel_path = os.path.relpath(self.current_image_file, os.path.join(os.path.dirname(__file__), "sync_directory"))
                self.current_hint_image = rel_path
                    
                # Enable send button
                if self.stats_elements['send_btn']:
                    self.stats_elements['send_btn'].config(state='normal')
            except Exception as e:
                print(f"[image hints] Error getting image path: {e}")

    def clear_manual_hint(self):
        """Clear the manual hint text and reset image attachment state"""
        # Clear text input
        if 'msg_entry' in self.stats_elements:
            self.stats_elements['msg_entry'].delete('1.0', tk.END)
            self.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)
        
        # Reset image attachment state
        self.current_hint_image = None
        if 'attached_image_label' in self.stats_elements:
            self.stats_elements['attached_image_label'].pack_forget()
        
        # Hide image selection components
        if 'image_listbox' in self.stats_elements:
            self.stats_elements['image_listbox'].pack_forget()
        if 'img_control_frame' in self.stats_elements:
            self.stats_elements['img_control_frame'].pack_forget()
        if 'prop_control_buttons' in self.stats_elements:
            self.stats_elements['prop_control_buttons'].pack_forget()
            
        # Reset the image dropdown selection
        if 'image_btn' in self.stats_elements:
            self.stats_elements['image_btn'].set('')
            
        # Show hint buttons and disable send button
        if 'hint_buttons_frame' in self.stats_elements:
            self.stats_elements['hint_buttons_frame'].pack(pady=5)
        if 'send_btn' in self.stats_elements:
            self.stats_elements['send_btn'].config(state='disabled')

    def play_hint_sound(self, computer_name, sound_name='hint_received.mp3'):
        """
        Sends a command to play a sound on the specified kiosk
        Uses the app's network handler to broadcast the message

        Args:
            computer_name (str): The target kiosk
            sound_name (str): The sound file to play, defaults to hint_received.mp3
        """
        self.app.network_handler.send_play_sound_command(computer_name, sound_name)

    def reset_kiosk(self, computer_name):
        """Reset all kiosk stats and state"""
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return

        # Reset hints count locally
        self.app.kiosk_tracker.kiosk_stats[computer_name]['total_hints'] = 0

        # Reset and stop timer (local actions, combined with network command)
        self.app.network_handler.send_timer_command(computer_name, "set", 45)
        self.app.network_handler.send_timer_command(computer_name, "stop")


        # Clear any pending help requests
        if computer_name in self.app.kiosk_tracker.help_requested:
            self.app.kiosk_tracker.help_requested.remove(computer_name)
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")

        # Stop GM assistance icon if it's blinking
        self.stop_gm_assistance_icon(computer_name)

        # Send reset message through network handler
        self.app.network_handler.send_reset_kiosk_command(computer_name)


        # Force immediate UI update
        self.update_stats_display(computer_name)

    def play_video(self, computer_name):
        video_type = self.stats_elements['video_type'].get().lower().split()[0]
        # Get time from timer entry, default to 45 if empty or invalid
        try:
            minutes = int(self.stats_elements['time_entry'].get())
        except (ValueError, AttributeError):
            minutes = 45

        self.app.network_handler.send_video_command(computer_name, video_type, minutes)

    def handle_intro_video_complete(self, computer_name):
        """Handle the 'intro_video_completed' message"""
        print(f"[AdminInterfaceBuilder] Intro video completed by {computer_name}")
        
        do_autostart = self.app.kiosk_tracker.kiosk_stats[computer_name].get("auto_start")

        if(do_autostart == True):
            print("auto start was true, would start props")
            self.app.prop_control.start_game()
        else:
            print(f"auto start was read as {do_autostart}, not starting props")

    def toggle_music(self, computer_name):
        """Sends a command to toggle music playback on the specified kiosk."""

        # Assume music will be toggled on the kiosk - update icon immediately
        # (The actual state will be confirmed and corrected by the next broadcast message)
        if 'music_button' in self.stats_elements and self.stats_elements['music_button']:
            music_button = self.stats_elements['music_button']
            if hasattr(music_button, 'music_on_icon') and hasattr(music_button, 'music_off_icon'):
                try:
                    if music_button.cget('image') == str(music_button.music_off_icon):
                        music_button.config(
                            image=music_button.music_on_icon
                        )
                    else:
                        music_button.config(
                            image=music_button.music_off_icon
                        )
                except tk.TclError:
                    print("[interface builder]Music button was destroyed")

        self.app.network_handler.send_toggle_music_command(computer_name)

    def toggle_timer(self, computer_name):
        if 'timer_button' not in self.stats_elements:
            return

        timer_button = self.stats_elements['timer_button']
        is_running = timer_button.cget('text') == "Stop Room"

        # Switch icons before sending command
        if hasattr(timer_button, 'play_icon') and hasattr(timer_button, 'stop_icon'):
            if is_running:
                timer_button.config(
                    image=timer_button.play_icon,
                    text="Start Room"
                )
            else:
                timer_button.config(
                    image=timer_button.stop_icon,
                    text="Stop Room"
                )
        else:
            # Fallback to text-only if icons aren't available
            timer_button.config(text="Start Room" if is_running else "Stop Room")

        command = "stop" if is_running else "start"
        self.app.network_handler.send_timer_command(computer_name, command)

    def set_timer(self, computer_name):
        try:
            minutes = int(self.stats_elements['time_entry'].get())
            if 0 <= minutes <= 99:  # Validate input range
                self.app.network_handler.send_timer_command(computer_name, "set", minutes)
        except ValueError:
            pass  # Invalid input handling

    def add_timer_time(self, computer_name):
        """Add specified minutes to current timer without affecting running state"""
        try:
            minutes_to_add = int(self.stats_elements['time_entry'].get())
            if 0 <= minutes_to_add <= 99:  # Validate input range
                # Get current time from stats
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                    current_seconds = stats.get('timer_time', 0)
                    # Add new time in seconds (convert minutes to seconds)
                    new_seconds = current_seconds + (minutes_to_add * 60)
                    # Convert total seconds back to minutes for the command
                    new_minutes = new_seconds / 60
                    # Send set command with new total time, keeping decimal precision
                    self.app.network_handler.send_timer_command(computer_name, "set", new_minutes)
        except ValueError:
            pass  # Invalid input handling

    def reduce_timer_time(self, computer_name):
        """Reduce specified minutes from current timer without affecting running state"""
        try:
            minutes_to_reduce = int(self.stats_elements['time_entry'].get())
            if 0 <= minutes_to_reduce <= 99:  # Validate input range
                # Get current time from stats
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                    current_seconds = stats.get('timer_time', 0)

                    # Calculate new time in seconds (convert minutes to seconds)
                    new_seconds = current_seconds - (minutes_to_reduce * 60)

                    # Prevent negative time
                    if new_seconds < 0:
                        new_seconds = 0

                    # Convert total seconds back to minutes for the command
                    new_minutes = new_seconds / 60
                    # Send set command with new total time, keeping decimal precision
                    self.app.network_handler.send_timer_command(computer_name, "set", new_minutes)
        except ValueError:
            pass  # Invalid input handling

    def update_timer_display(self):
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_stats:
            stats = self.app.kiosk_tracker.kiosk_stats[self.selected_kiosk]
            timer_time = stats.get('timer_time', 2700)
            timer_minutes = int(timer_time // 60)
            timer_seconds = int(timer_time % 60)
            if 'current_time' in self.stats_elements and self.stats_elements['current_time']:
                self.stats_elements['current_time'].config(
                    text=f"{timer_minutes:02d}:{timer_seconds:02d}"
                )
            if 'ttc_label' in self.stats_elements and self.stats_elements['ttc_label']:
                minutes_remaining = int(45 - (timer_time / 60))
                seconds_remaining = int(timer_time % 60)
                
                if seconds_remaining > 0:
                    ttc_minutes = minutes_remaining
                    ttc_seconds = 60- seconds_remaining
                else:
                    ttc_minutes = minutes_remaining
                    ttc_seconds = 0

                ttc_text = f"TTC:\n{ttc_minutes:02d}:{ttc_seconds:02d}"
                self.stats_elements['ttc_label'].config(text=ttc_text)
        
        for computer_name, kiosk_data in self.connected_kiosks.items():
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                is_running = stats.get('timer_running', False)
                
                if is_running:
                    timer_time = stats.get('timer_time', 2700)
                    timer_minutes = int(timer_time // 60)
                    timer_seconds = int(timer_time % 60)
                    display_text = f"{timer_minutes:02d}:{timer_seconds:02d}"
                else:
                    display_text = "- - : - -"
                    
                kiosk_data['timer_label'].config(text=display_text)
                
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
            room_number = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if room_number in self.app.prop_control.last_progress_times:
                    self.update_last_progress_time_display(room_number)
        
        self.app.root.after(1000, self.update_timer_display)

    def toggle_camera(self, computer_name):
        """Toggle camera feed from kiosk"""
        if getattr(self, 'camera_active', False):
            # Stop camera
            self.video_client.disconnect()
            self.camera_active = False
            if hasattr(self.stats_elements['camera_btn'], 'camera_icon'):
                self.stats_elements['camera_btn'].config(
                    image=self.stats_elements['camera_btn'].camera_icon,
                    text="Start Camera"
                )
            else:
                self.stats_elements['camera_btn'].config(text="Start Camera")
            if 'video_label' in self.stats_elements:
                self.stats_elements['video_label'].config(image='')
        else:
            # Start camera
            self.stats_elements['camera_btn'].config(text="Connecting...")
            
            def connect():
                if self.video_client.connect(computer_name):
                    self.camera_active = True
                    if hasattr(self.stats_elements['camera_btn'], 'stop_camera_icon'):
                        self.stats_elements['camera_btn'].config(
                            image=self.stats_elements['camera_btn'].stop_camera_icon,
                            text="Stop Camera"
                        )
                    else:
                        self.stats_elements['camera_btn'].config(text="Stop Camera")
                    self.update_video_feed()
                else:
                    if hasattr(self.stats_elements['camera_btn'], 'camera_icon'):
                        self.stats_elements['camera_btn'].config(
                            image=self.stats_elements['camera_btn'].camera_icon,
                            text="Start Camera"
                        )
                    else:
                        self.stats_elements['camera_btn'].config(text="Start Camera")
                    if 'video_label' in self.stats_elements:
                        self.stats_elements['video_label'].config(
                            text="Camera connection failed",
                            fg='red'
                        )
            
            threading.Thread(target=connect, daemon=True).start()

    def update_video_feed(self):
        if getattr(self, 'camera_active', False) and 'video_label' in self.stats_elements:
            try:
                frame = self.video_client.get_frame()
                if frame is not None:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame = cv2.resize(frame, (500, 375))
                    img = Image.fromarray(frame)
                    imgtk = ImageTk.PhotoImage(image=img)
                    self.stats_elements['video_label'].imgtk = imgtk
                    self.stats_elements['video_label'].config(image=imgtk)
            except Exception as e:
                print(f"[interface builder]Error updating video feed: {e}")
                
        if self.camera_active:
            self.app.root.after(30, self.update_video_feed)

    def skip_video(self, computer_name):
        """Skip any currently playing videos on the specified kiosk"""
        self.app.network_handler.send_stop_video_command(computer_name)

    def remove_kiosk(self, computer_name):
        """Remove a kiosk from the UI"""
        # Stop camera if it was active for this kiosk
        if getattr(self, 'camera_active', False) and \
           self.stats_elements.get('current_computer') == computer_name:
            self.toggle_camera(computer_name)
        
        if computer_name in self.connected_kiosks:
            # Stop GM assistance icon if it's blinking
            self.stop_gm_assistance_icon(computer_name)
            
            # Cancel any blinking timer
            if self.connected_kiosks[computer_name]['icon_blink_after_id']:
                self.app.root.after_cancel(self.connected_kiosks[computer_name]['icon_blink_after_id'])
            
            self.connected_kiosks[computer_name]['frame'].destroy()
            del self.connected_kiosks[computer_name]
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                del self.app.kiosk_tracker.kiosk_assignments[computer_name]
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                del self.app.kiosk_tracker.kiosk_stats[computer_name]
            if computer_name in self.app.kiosk_tracker.assigned_rooms:
                del self.app.kiosk_tracker.assigned_rooms[computer_name]
            if computer_name in self.app.kiosk_tracker.help_requested:
                self.app.kiosk_tracker.help_requested.remove(computer_name)
            
            if self.selected_kiosk == computer_name:
                self.selected_kiosk = None
                self.stats_frame.configure(text="No Room Selected")
                for widget in self.stats_frame.winfo_children():
                    widget.destroy()
                self.stats_elements = {key: None for key in self.stats_elements}

    def update_stats_timer(self):
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_stats:
            self.update_stats_display(self.selected_kiosk)
        self.app.root.after(1000, self.update_stats_timer)

    def add_kiosk_to_ui(self, computer_name):
        """Add or update a kiosk in the UI with room-specific colors"""
        current_time = time.time()
        
        if computer_name in self.connected_kiosks:
            self.connected_kiosks[computer_name]['last_seen'] = current_time
            return
            
        frame = tk.Frame(self.kiosk_frame)
        frame.configure(relief='flat', borderwidth=0, highlightthickness=0)
        frame.pack(fill='x', pady=2)
        
        # Load kiosk icon
        try:
            kiosk_icon = Image.open(os.path.join("admin_icons", "assistance_requested.png"))
            kiosk_icon = kiosk_icon.resize((16, 16), Image.Resampling.LANCZOS)
            kiosk_icon = ImageTk.PhotoImage(kiosk_icon)
        except Exception as e:
            print(f"[interface builder]Error loading kiosk icon: {e}")
            kiosk_icon = None
            
        # Create icon label but don't pack it yet
        icon_label = tk.Label(frame, image=kiosk_icon if kiosk_icon else None, cursor="hand2")
        icon_label.image = kiosk_icon  # Keep reference to prevent garbage collection
        
        # Add click handler to hide the icon
        def hide_icon(event):
            if icon_label.winfo_manager():  # If visible
                icon_label.pack_forget()
                # Also stop the blink timer if it exists
                if self.connected_kiosks[computer_name]['icon_blink_after_id']:
                    self.app.root.after_cancel(self.connected_kiosks[computer_name]['icon_blink_after_id'])
                    self.connected_kiosks[computer_name]['icon_blink_after_id'] = None
        
        icon_label.bind('<Button-1>', hide_icon)  # Bind left click to hide function
        
        # Pack the icon label first, before any other elements, then immediately hide it
        icon_label.pack(side='left', padx=(0,5))
        icon_label.pack_forget()
        
        # Now create and pack other elements
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
            room_name = self.app.rooms[room_num]
            
            # Get room color from mapping, default to black if not found
            room_color = self.ROOM_COLORS.get(room_num, "black")
            
            name_label = tk.Label(frame, 
                text=room_name,
                font=('Arial', 12, 'bold'),
                fg=room_color)  # Apply room-specific color
            name_label.pack(side='left', padx=5)
        else:
            name_label = tk.Label(frame, 
                text="Unassigned",
                font=('Arial', 12, 'bold'))
            name_label.pack(side='left', padx=5)
        
        def click_handler(cn=computer_name):
            self.select_kiosk(cn)
        
        frame.bind('<Button-1>', lambda e: click_handler())
        name_label.bind('<Button-1>', lambda e: click_handler())
        
        room_var = tk.StringVar()
        dropdown = ttk.Combobox(frame, textvariable=room_var, 
            values=list(self.app.rooms.values()), state='readonly')
        dropdown.pack(side='left', padx=5)
        
        def on_room_select(event):
            if not room_var.get():
                return
            selected_room = next(num for num, name in self.app.rooms.items() 
                            if name == room_var.get())
            self.app.kiosk_tracker.assign_kiosk_to_room(computer_name, selected_room)
            dropdown.set('')
            name_label.config(
                text=self.app.rooms[selected_room],
                fg=self.ROOM_COLORS.get(selected_room, "black")
            )
        
        dropdown.bind('<<ComboboxSelected>>', on_room_select)
        
        help_label = tk.Label(frame, text="", font=('Arial', 14, 'bold'), fg='red')
        help_label.pack(side='left', padx=5)
        
        reboot_btn = tk.Button(
            frame, 
            text="Reboot Kiosk Computer",
            bg='#FF6B6B',
            fg='white',
            cursor="hand2"
        )
        
        # Track confirmation state
        reboot_btn.confirmation_pending = False
        reboot_btn.after_id = None
        
        def reset_reboot_button(btn=reboot_btn):
            """Reset the button to its original state"""
            btn.confirmation_pending = False
            btn.config(text="Reboot Kiosk Computer")
            btn.after_id = None
            
        def handle_reboot_click():
            """Handle reboot button clicks with confirmation"""
            if reboot_btn.confirmation_pending:
                # Second click - perform reboot
                self.app.network_handler.send_reboot_signal(computer_name)
                reset_reboot_button()
            else:
                # First click - show confirmation
                reboot_btn.confirmation_pending = True
                reboot_btn.config(text="Confirm")
                
                # Cancel any existing timer
                if reboot_btn.after_id:
                    reboot_btn.after_cancel(reboot_btn.after_id)
                    
                # Set timer to reset button after 2 seconds
                reboot_btn.after_id = reboot_btn.after(2000, lambda: reset_reboot_button()) # Changed to lambda

        reboot_btn.config(command=handle_reboot_click)
        reboot_btn.pack(side='left', padx=(20, 5))

        # Add mini timer label at the end
        timer_label = tk.Label(frame,
            text="--:--",
            font=('Arial', 10, 'bold'),
            width=6)
        timer_label.pack(side='right', padx=5)
        
        self.connected_kiosks[computer_name] = {
            'frame': frame,
            'help_label': help_label,
            'dropdown': dropdown,
            'reboot_btn': reboot_btn,
            'last_seen': current_time,
            'name_label': name_label,
            'timer_label': timer_label,  # Store timer label reference
            'icon_label': icon_label,  # Store icon label reference
            'icon_blink_after_id': None  # For tracking blink timer
        }
        
        # Check if the hint requested flag was set
        if computer_name in self.app.kiosk_tracker.kiosk_stats:
            stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
            # Use .get() for safe access
            self.mark_help_requested(computer_name)
        else:
            print(f"[interface builder][AdminInterface] add_kiosk_to_ui: No kiosk stats from {computer_name}")
        
        if computer_name == self.selected_kiosk:
            self.select_kiosk(computer_name)

    def update_kiosk_display(self, computer_name):
        """Update kiosk display including room-specific colors"""
        if computer_name in self.connected_kiosks:
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                self.connected_kiosks[computer_name]['name_label'].config(
                    text=self.app.rooms[room_num],
                    fg=self.ROOM_COLORS.get(room_num, "black")  # Apply room color
                )
                
                if computer_name == self.selected_kiosk:
                    self.stats_frame.configure(
                        text=f"{self.app.rooms[room_num]} ({computer_name})"
                    )
                    if self.stats_elements['send_btn']:
                        self.stats_elements['send_btn'].config(state='normal')

    def mark_help_requested(self, computer_name):
        """Mark a kiosk as requesting help and play notification sound"""
        if computer_name in self.connected_kiosks:
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                stats = self.app.kiosk_tracker.kiosk_stats[computer_name]
                if stats.get('hint_requested', False):
                    print(f"[interface builder][AdminInterface] mark_help_requested: Showing HINT REQUESTED for {computer_name}")
                    self.connected_kiosks[computer_name]['help_label'].config(
                        text="HINT REQUESTED",
                        fg='red',
                        font=('Arial', 14, 'bold')
                    )
                    self.audio_manager = AdminAudioManager()
                    self.audio_manager.play_sound("hint_notification")
                else:
                    print(f"[interface builder][AdminInterface] mark_help_requested: Clearing HINT REQUESTED for {computer_name} from state")
                    self.connected_kiosks[computer_name]['help_label'].config(
                         text="",
                         fg='red',
                         font=('Arial', 14, 'bold')
                    )
            else:
                print(f"[interface builder][AdminInterface] mark_help_requested: Ignoring help request - no kiosk stats found for {computer_name}")

        else:
            print(f"[interface builder][AdminInterface] mark_help_requested: Ignoring help request - kiosk {computer_name} not in connected kioskl list")
            
    def handle_gm_assistance_accepted(self, computer_name):
        """Handle when GM assistance is accepted by showing and blinking the icon"""
        if computer_name not in self.connected_kiosks:
            return
        
        kiosk_data = self.connected_kiosks[computer_name]
        icon_label = kiosk_data['icon_label']
        
        # Cancel any existing blink timer
        if kiosk_data['icon_blink_after_id']:
            self.app.root.after_cancel(kiosk_data['icon_blink_after_id'])
        
        def blink():
            """Toggle icon visibility every 500ms"""
            if computer_name not in self.connected_kiosks:
                return
            
            if icon_label.winfo_manager():  # If visible
                icon_label.pack_forget()
            else:
                # Ensure icon is packed first by unpacking and repacking all siblings
                for widget in kiosk_data['frame'].winfo_children():
                    if widget != icon_label and widget.winfo_manager():
                        widget.pack_forget()
                icon_label.pack(side='left', padx=(0,5))
                # Repack other widgets in their original order
                if computer_name in self.connected_kiosks:
                    name_label = self.connected_kiosks[computer_name]['name_label']
                    help_label = self.connected_kiosks[computer_name]['help_label']
                    dropdown = self.connected_kiosks[computer_name]['dropdown']
                    reboot_btn = self.connected_kiosks[computer_name]['reboot_btn']
                    timer_label = self.connected_kiosks[computer_name]['timer_label']
                    
                    name_label.pack(side='left', padx=5)
                    dropdown.pack(side='left', padx=5)
                    help_label.pack(side='left', padx=5)
                    reboot_btn.pack(side='left', padx=(20, 5))
                    timer_label.pack(side='right', padx=5)
            
            # Schedule next blink
            kiosk_data['icon_blink_after_id'] = self.app.root.after(500, blink)
        
        # Start blinking
        blink()

    def stop_gm_assistance_icon(self, computer_name):
        """Stop the GM assistance icon from blinking and hide it"""
        if computer_name not in self.connected_kiosks:
            return
        
        kiosk_data = self.connected_kiosks[computer_name]
        
        # Cancel blink timer if it exists
        if kiosk_data['icon_blink_after_id']:
            self.app.root.after_cancel(kiosk_data['icon_blink_after_id'])
            kiosk_data['icon_blink_after_id'] = None
        
        # Hide the icon
        if kiosk_data['icon_label'].winfo_manager():
            kiosk_data['icon_label'].pack_forget()

    def select_kiosk(self, computer_name):
        """Handle selection of a kiosk and setup of its interface"""
        try:
            #print(f"[interface builder]=== KIOSK SELECTION START: {computer_name} ===")
            
            # Clean up existing audio/video streams before switching
            if hasattr(self, 'camera_active') and self.camera_active:
                self.video_client.disconnect()
                self.camera_active = False
                if 'camera_btn' in self.stats_elements:
                    self.stats_elements['camera_btn'].config(text="Start Camera")
                if 'video_label' in self.stats_elements:
                    self.stats_elements['video_label'].config(image='')
                    
            if hasattr(self, 'audio_active') and self.audio_active:
                if hasattr(self, 'speaking') and self.speaking:
                    self.audio_clients[computer_name].stop_speaking()
                    self.speaking = {}
                    if 'speak_btn' in self.stats_elements:
                        self.stats_elements['speak_btn'].config(text="Enable Microphone")
                self.audio_clients[computer_name].disconnect()
                self.audio_active = {}
                if 'listen_btn' in self.stats_elements:
                    self.stats_elements['listen_btn'].config(text="Start Listening")
                if 'speak_btn' in self.stats_elements:
                    self.stats_elements['speak_btn'].config(state='disabled')
            
            # Setup stats panel and audio hints first
            self.setup_stats_panel(computer_name)
            
            self.selected_kiosk = computer_name
            
            if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                room_name = self.app.rooms[room_num]
                title = f"{room_name} ({computer_name})"
                print(f"[interface builder]Room assigned: {room_name} (#{room_num})")
                
                # Get room color from mapping, default to black if not found
                room_color = self.ROOM_COLORS.get(room_num, "black")
                
                # Configure title with room-specific color
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg=room_color  # Add color to match room color scheme
                )
                
                # Map room number to directory name for audio hints
                room_dirs = {
                    6: "atlantis",
                    1: "casino",
                    5: "haunted",
                    2: "ma",
                    7: "time",
                    3: "wizard",
                    4: "zombie"
                }
                
                if room_num in room_dirs:
                    room_dir = room_dirs[room_num]
                    if hasattr(self, 'audio_hints'):
                        self.audio_hints.update_room(room_dir)
                        # Update image props when room changes
                        self.update_image_props()
            else:
                title = f"Unassigned ({computer_name})"
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg='black'
                )
            
            if hasattr(self, 'saved_hints'):
                if room_num:
                    self.saved_hints.update_room(room_num)
                else:
                    self.saved_hints.clear_preview()
            
            # Update highlighting with dotted border
            for cn, data in self.connected_kiosks.items():
                if cn == computer_name:
                    # Create dotted border effect
                    data['frame'].configure(
                        relief='solid',  # Solid relief creates border base
                        borderwidth=0,   # Border thickness
                        highlightthickness=0,  # Additional highlight border
                        highlightbackground='#363636',  # Color of dotted border
                        highlightcolor='#363636'  # Color when focused
                    )
                    # Create dotted border effect using character spacing
                    border_pattern = '. ' * 20  # Alternating dot and space
                    data['frame'].configure(bd=2, relief='solid')
                    # Keep button colors consistent
                    for widget in data['frame'].winfo_children():
                        if isinstance(widget, tk.Button):
                            if widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')  # Keep reboot button red
                            elif widget == data['assign_btn']:
                                widget.configure(bg='#90EE90', fg='black')  # Light green for assign button
                else:
                    # Remove highlighting for unselected kiosks
                    data['frame'].configure(
                        relief='flat',
                        borderwidth=0,
                        highlightthickness=0
                    )
                    # Keep button colors consistent for unselected kiosks
                    for widget in data['frame'].winfo_children():
                        if isinstance(widget, tk.Button):
                            if widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')  # Keep reboot button red
                            elif widget == data['assign_btn']:
                                widget.configure(bg='#90EE90', fg='black')  # Light green for assign button
            
            self.update_stats_display(computer_name)
            
            # Notify PropControl about room change (with safety check)
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if computer_name in self.app.kiosk_tracker.kiosk_assignments:
                    room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
                    print(f"[interface builder]Notifying prop control about room change to {room_num}")
                    self.app.root.after(100, lambda: self.app.prop_control.connect_to_room(room_num))
                else:
                    print("[interface builder]No room assignment, skipping prop control notification")
                    
            #print(f"[interface builder]=== KIOSK SELECTION END: {computer_name} ===\n")
            
        except Exception as e:
            print(f"[interface builder]Error in select_kiosk: {e}")
            
    def update_stats_display(self, computer_name):
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return

        stats = self.app.kiosk_tracker.kiosk_stats[computer_name]

        if not self.stats_elements:
            return

        if self.stats_elements.get('hints_label_below'):
            total_hints = stats.get('total_hints', 0)
            self.stats_elements['hints_label_below'].config(
                text=f"Hints requested:\n{total_hints}"
            )
            
        if self.stats_elements.get('hints_received_label'):
            hints_received = stats.get('hints_received', 0)
            self.stats_elements['hints_received_label'].config(
                text=f"Hints received:\n{hints_received}"
            )

        # Music button state update
        music_button = self.stats_elements.get('music_button')
        if music_button and music_button.winfo_exists():
            music_playing = stats.get('music_playing', False)
            #print(f"[DEBUG] Raw stats music_playing value: {music_playing}")

            if hasattr(music_button, 'music_on_icon') and hasattr(music_button, 'music_off_icon'):
                try:
                    current_image = music_button.cget('image')
                    #print(f"[DEBUG] music_playing: {music_playing}, current_image: {current_image}, on_icon: {music_button.music_on_icon}, off_icon: {music_button.music_off_icon}")
                    
                    if music_playing and str(current_image) != str(music_button.music_on_icon):
                        music_button.config(
                            image=music_button.music_on_icon
                        )
                    elif not music_playing and str(current_image) != str(music_button.music_off_icon):
                        music_button.config(
                            image=music_button.music_off_icon
                        )
                except tk.TclError:
                    print("[interface builder]Music button was destroyed")
                    return

        timer_time = stats.get('timer_time', 3600)
        timer_minutes = int(timer_time // 60)
        timer_seconds = int(timer_time % 60)
        if self.stats_elements.get('current_time'):
            self.stats_elements['current_time'].config(
                text=f"{timer_minutes:02d}:{timer_seconds:02d}"
            )

        timer_button = self.stats_elements.get('timer_button')
        if timer_button and timer_button.winfo_exists():
            is_running = stats.get('timer_running', False)

            if hasattr(timer_button, 'stop_icon') and hasattr(timer_button, 'play_icon'):
                try:
                    if is_running and timer_button.cget('text') != "Stop Room":
                        timer_button.config(
                            image=timer_button.stop_icon,
                            text="Stop Room"
                        )
                    elif not is_running and timer_button.cget('text') != "Start Room":
                        timer_button.config(
                            image=timer_button.play_icon,
                            text="Start Room"
                        )
                except tk.TclError:
                    print("[interface builder]Timer button was destroyed")
                    return
            else:
                try:
                    if is_running and timer_button.cget('text') != "Stop Room":
                        timer_button.config(text="Stop Room")
                    elif not is_running and timer_button.cget('text') != "Start Room":
                        timer_button.config(text="Start Room")
                except tk.TclError:
                    print("[interface builder]Timer button was destroyed")
                    return
        
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            if self.stats_elements.get('send_btn'):
                self.stats_elements['send_btn'].config(state='normal')
        else:
            if self.stats_elements.get('send_btn'):
                self.stats_elements['send_btn'].config(state='disabled')
        
        current_hint_request = stats.get('hint_requested', False)
        if not hasattr(self, '_last_hint_request_states'):
            self._last_hint_request_states = {}

        last_hint_request = self._last_hint_request_states.get(computer_name)
        
        if last_hint_request != current_hint_request:
            self.mark_help_requested(computer_name)
            self._last_hint_request_states[computer_name] = current_hint_request
        
        if self.app.prop_control and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
            room_number = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
            
            if room_number in self.app.prop_control.last_progress_times:
                self.update_last_progress_time_display(room_number)
        else:
            self.stats_elements['last_progress_label'].config(text="Last Progress:\nN/A", anchor='w')

        # Update last prop finished name
        last_prop_finished = self.app.prop_control.last_prop_finished.get(room_number, 'N/A')
        if 'last_prop_label' in self.stats_elements and self.stats_elements['last_prop_label']:
          self.stats_elements['last_prop_label'].config(text=f"Last Prop Finished:\n{last_prop_finished}",anchor='w')
        else:
            if 'last_prop_label' in self.stats_elements and self.stats_elements['last_prop_label']:
                self.stats_elements['last_prop_label'].config(text="Last Prop Finished:\nN/A", anchor='w')

        # Auto-start state update
        auto_start_check = self.stats_elements.get('auto_start_check')
        if auto_start_check and auto_start_check.winfo_exists():
            auto_start = stats.get('auto_start', False)
            try:
                auto_start_check.config(text="[✓] Auto-Start" if auto_start else "[  ] Auto-Start")
            except tk.TclError:
                print("[interface builder]Auto-start checkbox was destroyed")
                return

    def update_last_progress_time_display(self, room_number):
        if room_number in self.app.prop_control.last_progress_times:
            last_progress_time = self.app.prop_control.last_progress_times[room_number]
            time_diff = time.time() - last_progress_time
            
            minutes = int(time_diff // 60)
            seconds = int(time_diff % 60)
            
            if minutes == 0 and seconds == 0:
                time_string = "Just now"
            elif minutes == 0:
                time_string = f"{seconds} seconds ago"
            elif seconds == 0:
                time_string = f"{minutes} minutes ago"
            else:
                time_string = f"{minutes} minutes {seconds} seconds ago"
            
            self.stats_elements['last_progress_label'].config(text=f"Last Progress:\n{time_string}", anchor='w')

    def save_manual_hint(self):
        # Wrapper for the extracted save_manual_hint function
        save_manual_hint(self)

    def clear_kiosk_hints(self, computer_name):
      self.app.network_handler.send_clear_hints_command(computer_name)

    def send_hint(self, computer_name, hint_data=None):
        """Send a hint to the selected kiosk."""
        # Validate kiosk assignment
        if not computer_name in self.app.kiosk_tracker.kiosk_assignments:
            return

        if hint_data is None:
            # Using manual entry
            message_text = self.stats_elements['msg_entry'].get('1.0', 'end-1c') if self.stats_elements['msg_entry'] else ""
            if not message_text and not self.current_hint_image:
                return

            hint_data = {
                'text': message_text,
                'image_path': self.current_hint_image if self.current_hint_image else None
            }

        # Get room number
        room_number = self.app.kiosk_tracker.kiosk_assignments[computer_name]

        # Send the hint
        self.app.network_handler.send_hint(room_number, hint_data)

        # Stop GM assistance icon if it's blinking
        self.stop_gm_assistance_icon(computer_name)

        # Clear any pending help requests
        if computer_name in self.app.kiosk_tracker.help_requested:
            self.app.kiosk_tracker.help_requested.remove(computer_name)
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")

        # Clear ALL hint entry fields regardless of which method was used
        if self.stats_elements['msg_entry']:
            self.stats_elements['msg_entry'].delete('1.0', 'end')

        if self.stats_elements['image_preview']:
            self.stats_elements['image_preview'].configure(image='')
            self.stats_elements['image_preview'].image = None

    def play_solution_video(self, computer_name):
      """Play a solution video for the selected prop"""
      if not self.stats_elements['solution_prop'].get():
          return

      # Extract the display name from the dropdown value
      # Format is "Display Name (original_name)"
      display_name = self.stats_elements['solution_prop'].get().split('(')[0].strip()

      # Convert display name to lowercase and replace spaces with underscores
      video_filename = display_name.lower().replace(' ', '_')

      # Get the room folder name based on room number
      room_folders = {
          3: "wizard",
          1: "casino",
          2: "ma",
          5: "haunted",
          4: "zombie",
          6: "atlantis",
          7: "time"
      }

      room_num = self.app.kiosk_tracker.kiosk_assignments.get(computer_name)
      if room_num and room_num in room_folders:
          room_folder = room_folders[room_num]

          # Clear help request status if it exists
          if computer_name in self.app.kiosk_tracker.help_requested:
              self.app.kiosk_tracker.help_requested.remove(computer_name)
              if computer_name in self.connected_kiosks:
                  self.connected_kiosks[computer_name]['help_label'].config(text="")

          # Send video command to kiosk
          self.app.network_handler.send_solution_video_command(computer_name, room_folder, video_filename)

    def cleanup(self):
        """Clean up resources before closing"""
        print("[interface builder] Cleaning up audio clients...")
        for computer_name, client in self.audio_clients.items():
            print(f"[interface builder] Disconnecting audio client for {computer_name}")
            try:
                client.disconnect()
            except Exception as e:
                print(f"[interface builder] Error disconnecting client for {computer_name}: {e}")
        self.audio_clients.clear()

        # Cleanup video client if necessary
        if hasattr(self, 'video_client') and hasattr(self.video_client, 'disconnect'):
             try:
                 self.video_client.disconnect() # Assuming a similar disconnect method exists
             except Exception as e:
                  print(f"[interface builder] Error disconnecting video client: {e}")

        # Original cleanup call (if any)
        # if hasattr(self, 'audio_manager'):
        #    self.audio_manager.cleanup() # Keep if audio_manager is still used elsewhere

    def toggle_audio(self, computer_name):
        """Toggle audio listening from kiosk"""
        # --- Get or create audio client for this computer ---
        audio_client = self.audio_clients.get(computer_name)
        if not audio_client:
            print(f"[interface builder] Creating new AudioClient for {computer_name}")
            audio_client = AudioClient()
            self.audio_clients[computer_name] = audio_client
            # Initialize states for new client
            self.audio_active[computer_name] = False
            self.speaking[computer_name] = False
            # --- Use preferred device if set --- 
            preferred_index = self.preferred_audio_device_index.get(computer_name)
            if preferred_index is not None:
                 print(f"[interface builder] Using preferred device index {preferred_index} for {computer_name}")
                 # We don't call set_input_device here, just set the index
                 # get_input_devices() called later will validate and use it.
                 audio_client.selected_input_device_index = preferred_index
            # -----------------------------------
        # ----------------------------------------------------

        is_active = self.audio_active.get(computer_name, False)
        listen_btn = self.stats_elements.get('listen_btn') # Assume stats_elements corresponds to the selected kiosk
        speak_btn = self.stats_elements.get('speak_btn')

        if is_active:
            try:
                # Stop audio
                print(f"[interface builder] Disconnecting audio for {computer_name}")
                audio_client.disconnect() # Use the specific client
                self.audio_active[computer_name] = False
                # Ensure speaking state is also false
                if self.speaking.get(computer_name, False):
                     self.toggle_speaking(computer_name) # Stop speaking if active
                     # Need small delay or check before updating button state?

                if listen_btn:
                    if hasattr(listen_btn, 'listen_icon'):
                        listen_btn.config(
                            image=listen_btn.listen_icon,
                            text="Start Listening"
                        )
                    else:
                        listen_btn.config(text="Start Listening")
                if speak_btn:
                    speak_btn.config(state='disabled')

            except Exception as e:
                print(f"[interface builder] Error stopping audio for {computer_name}: {e}")
        else:
            # Start audio
            if listen_btn:
                listen_btn.config(text="Connecting...")

            def connect():
                try:
                    print(f"[interface builder] Attempting audio connection to {computer_name}")
                    if audio_client.connect(computer_name): # Use the specific client
                        print(f"[interface builder] Audio connected for {computer_name}")
                        self.audio_active[computer_name] = True
                        # Update UI elements (assuming they are for the current tab)
                        if listen_btn:
                            if hasattr(listen_btn, 'stop_listening_icon'):
                                listen_btn.config(
                                    image=listen_btn.stop_listening_icon,
                                    text="Stop Listening"
                                )
                            else:
                                listen_btn.config(text="Stop Listening")
                        if speak_btn:
                             speak_btn.config(state='normal')
                    else:
                        print(f"[interface builder] Audio connection failed for {computer_name}")
                        self.audio_active[computer_name] = False
                except Exception as e:
                    print(f"[interface builder] Error connecting audio for {computer_name}: {e}")
                    self.audio_active[computer_name] = False # Ensure state is updated on error

            # Run connect in a separate thread to avoid blocking UI
            threading.Thread(target=connect, daemon=True).start()

    def toggle_auto_start(self, computer_name):
        """Sends a command to toggle auto-start on the specified kiosk."""

        # Assume auto_start will be toggled on the kiosk - update state immediately
        if self.selected_kiosk and self.selected_kiosk in self.app.kiosk_tracker.kiosk_stats:
            current_status = self.app.kiosk_tracker.kiosk_stats[computer_name]['auto_start']
            self.app.kiosk_tracker.kiosk_stats[computer_name]['auto_start'] = not current_status

            if 'auto_start_check' in self.stats_elements and self.stats_elements['auto_start_check']:
                self.stats_elements['auto_start_check'].config(text="[✓] Auto-Start" if not current_status else "[  ] Auto-Start")

        self.app.network_handler.send_toggle_auto_start_command(computer_name)

    def toggle_speaking(self, computer_name):
        """Toggle microphone for speaking to kiosk"""
        is_active = self.audio_active.get(computer_name, False)
        if not is_active:
             print(f"[interface builder] Cannot toggle speaking for {computer_name}: audio not active.")
             return

        # --- Get the audio client for this computer ---
        audio_client = self.audio_clients.get(computer_name)
        if not audio_client:
            print(f"[interface builder] Error: No audio client found for {computer_name} during toggle_speaking.")
            return
        # ---------------------------------------------

        is_speaking = self.speaking.get(computer_name, False)
        speak_btn = self.stats_elements.get('speak_btn') # Assume stats_elements corresponds to the selected kiosk

        if is_speaking:
            try:
                # Stop speaking
                print(f"[interface builder] Stopping speaking for {computer_name}")
                audio_client.stop_speaking() # Use the specific client
                self.speaking[computer_name] = False

                # Reset background color of the entire interface (only if this is the currently selected kiosk?)
                if computer_name == self.selected_kiosk:
                    self.app.root.configure(bg='systemButtonFace')
                    # Potentially reset more specific frames if needed
                    # for frame in [self.main_container, self.kiosk_frame, self.stats_frame]:
                    #    frame.configure(bg='systemButtonFace')

                # Reset button appearance
                if speak_btn:
                    if hasattr(speak_btn, 'enable_mic_icon'):
                        speak_btn.config(
                            image=speak_btn.enable_mic_icon,
                            text="Enable Microphone",
                            bg='systemButtonFace', # Reset background
                            activebackground='systemButtonFace'
                        )
                    else:
                        speak_btn.config(
                             text="Enable Microphone",
                             bg='systemButtonFace',
                             activebackground='systemButtonFace'
                         )
            except Exception as e:
                print(f"[interface builder] Error stopping microphone for {computer_name}: {e}")
        else:
            # Start speaking
            try:
                print(f"[interface builder] Starting speaking for {computer_name}")
                if audio_client.start_speaking(): # Use the specific client
                    self.speaking[computer_name] = True

                    # Set red background (only if this is the currently selected kiosk?)
                    if computer_name == self.selected_kiosk:
                         self.app.root.configure(bg='#ff5252')  # Light red
                        # Potentially set more specific frames if needed
                        # for frame in [self.main_container, self.kiosk_frame, self.stats_frame]:
                        #     frame.configure(bg='#ffcccc')

                    # Update button appearance
                    if speak_btn:
                        if hasattr(speak_btn, 'disable_mic_icon'):
                            speak_btn.config(
                                image=speak_btn.disable_mic_icon,
                                text="Disable Microphone",
                                bg='#ffcccc', # Red background for button too
                                activebackground='#ffcccc'
                            )
                        else:
                            speak_btn.config(
                                text="Disable Microphone",
                                bg='#ffcccc',
                                activebackground='#ffcccc'
                            )
            except Exception as e:
                print(f"[interface builder] Error enabling microphone for {computer_name}: {e}")
                self.speaking[computer_name] = False # Ensure state is false on error