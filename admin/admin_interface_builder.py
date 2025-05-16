import tkinter as tk
from tkinter import ttk, filedialog
import time
from video_client import VideoClient
from audio_client import AudioClient
from audio_hints import AudioHints
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
        self.select_kiosk_debug = app.select_kiosk_debug
        self.hint_debug = app.hint_debug
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
        self.no_kiosks_label = None  # Initialize reference to no kiosks label
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
            # Clear dropdown text instead of label
            if computer_name in self.connected_kiosks and 'dropdown' in self.connected_kiosks[computer_name]:
                dropdown = self.connected_kiosks[computer_name]['dropdown']
                dropdown.set('')

        # Schedule the reset_kiosk call and store the after_id
        after_id = self.app.root.after(duration*1000, reset_and_clear)
        self.auto_reset_timer_ids[computer_name] = after_id

        # Start countdown
        self.auto_reset_countdown(computer_name, duration) # Start the countdown 

    def auto_reset_countdown(self, computer_name, remaining_seconds):
        """Countdown for auto-reset timer"""
        if remaining_seconds > 0 and computer_name in self.auto_reset_timer_ids:
            # Update the display
            self.update_auto_reset_timer_display(computer_name, remaining_seconds)
            # Schedule next update
            self.app.root.after(1000, 
                lambda: self.auto_reset_countdown(computer_name, remaining_seconds - 1))

    def update_auto_reset_timer_display(self, computer_name, remaining_seconds):
        """Update the auto reset timer display"""
        if computer_name in self.connected_kiosks:
            # Get the dropdown from the connected kiosks frame
            dropdown = self.connected_kiosks[computer_name].get('dropdown')
            if dropdown:
                # Format the countdown text
                countdown_text = f"Auto-reset: {remaining_seconds}s"
                # Set the dropdown text to show the countdown
                dropdown.set(countdown_text)

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
            padx=(0,9),
            pady=5
        )
        
        # Create frames within main container
        left_frame = tk.Frame(self.main_container)
        left_frame.pack(side='left', fill='both', expand=True, padx=0)
        
        # Create a horizontal container for kiosk frame and hints button
        kiosk_container = tk.Frame(left_frame)
        kiosk_container.pack(fill='x', expand=False, pady=(0,10))
        
        # Create kiosk frame on the left side of container
        self.kiosk_frame = tk.LabelFrame(kiosk_container, text="", padx=10, pady=3, labelanchor='ne')
        self.kiosk_frame.pack(side='left', fill='x', expand=True, anchor='nw')
        
        # Create "No kiosks" label but don't pack it yet
        self.no_kiosks_label = tk.Label(
            self.kiosk_frame,
            text="No kiosk computers found online on this network",
            font=('Arial', 11),
            fg='#555555',
            pady=20
        )
        # Show no kiosks message initially if there are no kiosks
        self.update_no_kiosks_message()
        
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
        hints_button_frame.pack(side='left', anchor='n', padx=(10,0), pady=4)  # Anchor to top
        
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
        self.stats_frame.pack(fill='both', expand=True, pady=0, anchor='nw', side='top')

    def _repack_kiosk_elements(self, computer_name, include_icon=False):
        if computer_name not in self.connected_kiosks:
            return

        kiosk_data = self.connected_kiosks[computer_name]
        parent_frame = kiosk_data.get('frame')

        if not parent_frame or not parent_frame.winfo_exists():
            return

        # Retrieve all relevant widgets
        icon_label = kiosk_data.get('icon_label')
        name_label = kiosk_data.get('name_label')
        dropdown = kiosk_data.get('dropdown')
        help_label = kiosk_data.get('help_label')
        reboot_btn = kiosk_data.get('reboot_btn')
        timer_label = kiosk_data.get('timer_label')

        # Widgets to manage
        widgets_to_repack = [icon_label, dropdown, name_label, help_label, reboot_btn, timer_label]

        # Forget all of them to ensure clean repacking in the correct order
        for widget in widgets_to_repack:
            if widget and widget.winfo_exists() and widget.winfo_manager():
                widget.pack_forget()

        # Repack in the correct original order

        if include_icon and icon_label and icon_label.winfo_exists():
            icon_label.pack(side='left', padx=(0, 5))

        # Determine name_label padding based on whether room is assigned (approximating original logic)
        name_label_padx = (30, 3)  # Default for assigned room
        if computer_name not in self.app.kiosk_tracker.kiosk_assignments or \
           not self.app.kiosk_tracker.kiosk_assignments.get(computer_name):
            name_label_padx = 5  # For unassigned

        if dropdown and dropdown.winfo_exists():
            dropdown.pack(side='left', padx=5, anchor='e')
        if name_label and name_label.winfo_exists():
            name_label.pack(side='left', padx=name_label_padx)
        if help_label and help_label.winfo_exists():
            help_label.pack(side='left', padx=5)
        
        # Pack right-aligned elements last to ensure they take precedence from the right
        if reboot_btn and reboot_btn.winfo_exists():
            reboot_btn.pack(side='right', padx=(20, 5), anchor='e')
        
        # Timer label is packed left, after help_label and before reboot_btn claims space from right
        if timer_label and timer_label.winfo_exists():
            timer_label.pack(side='left', padx=5)

    def show_hints_library(self):
        """Show the Hints Library interface"""
        self.hint_manager.show_hint_manager() # call the show method

    def setup_audio_hints(self):
        """Set up the audio hints panel"""
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
        
        # Create AudioHints instance
        #print("[interface builder]Creating new AudioHints instance...")
        self.audio_hints = AudioHints(self.stats_frame, on_room_change, self.app)
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
            print(f"[interface_builder image hints] Error loading prop mappings: {e}")
            prop_mappings = {}

        # Use current room from audio hints if available
        room_name = self.audio_hints.current_room if hasattr(self, "audio_hints") else None
        room_name = room_name.lower() if room_name else None
        
        room_key = None
        if hasattr(self, "audio_hints") and hasattr(self.audio_hints, "ROOM_MAP"):
            room_key = self.audio_hints.ROOM_MAP.get(room_name)
            if(self.select_kiosk_debug):
                print(f"[interface_builder image hints] Updating props dropdown for room: {room_name} (key: {room_key})")
        
        props_list = []
        if room_key and room_key in prop_mappings:
            props = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
            props.sort(key=lambda x: x[1]["order"])
            props_list = [f"{p[1]['display']} ({p[0]})" for p in props]
            if(self.select_kiosk_debug):
                print(f"[interface_builder image hints] Found {len(props_list)} props for room")
        
        self.stats_elements['image_btn']['values'] = props_list
        self.img_prop_var.set("")

    # admin_interface_builder.py
# Inside AdminInterfaceBuilder class, modify on_image_prop_select method

    def on_image_prop_select(self, event):
        """When a prop is selected, hide manual hint and show image selection"""
        selected_item = self.img_prop_var.get()
        if not selected_item:
            return
        
        # Hide manual hint text box and buttons
        if 'msg_entry' in self.stats_elements and self.stats_elements['msg_entry'].winfo_ismapped():
            self.stats_elements['msg_entry'].pack_forget()
        if 'hint_buttons_frame' in self.stats_elements and self.stats_elements['hint_buttons_frame'].winfo_ismapped():
            self.stats_elements['hint_buttons_frame'].pack_forget()
        
        # Show back button, open browser button, and listbox
        if 'prop_control_buttons' in self.stats_elements:
            self.stats_elements['prop_control_buttons'].pack(fill='x', pady=5)
            self.stats_elements['prop_back_btn'].pack(side='left', padx=5)
            self.stats_elements['open_browser_btn'].pack(side='left', padx=5) # Pack the new button
            # Ensure the listbox's attach button is hidden initially
            if 'prop_attach_btn' in self.stats_elements and self.stats_elements['prop_attach_btn'].winfo_ismapped():
                 self.stats_elements['prop_attach_btn'].pack_forget()
        
        self.stats_elements['image_listbox'].delete(0, tk.END)
        self.stats_elements['image_listbox'].pack(pady=5, fill='x', expand=True)
        
        # --- Use the new helper to get image data ---
        room_name_for_images = self.audio_hints.current_room if hasattr(self, "audio_hints") else None
        
        try:
            with open("prop_name_mapping.json", "r") as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[interface_builder image hints] Error loading prop mappings: {e}")
            prop_mappings = {}

        all_images_data = self._get_image_files_for_prop_and_cousins(
            selected_item, 
            room_name_for_images, 
            prop_mappings
        )

        # Initialize or clear the image data mapping for the listbox
        if not hasattr(self, 'image_data_mapping'):
            self.image_data_mapping = {}
        else:
            self.image_data_mapping.clear()

        for index, image_data_item in enumerate(all_images_data):
            # Listbox shows "filename (from Prop: prop_name)"
            display_text = f"{image_data_item['filename']}"
            self.stats_elements['image_listbox'].insert(tk.END, display_text)
            self.image_data_mapping[index] = image_data_item
        
        # Update the layout to ensure proper spacing
        if 'img_prop_frame' in self.stats_elements:
            self.stats_elements['img_prop_frame'].pack(fill='x', expand=True)
        
        # Hide image preview and listbox-attach button until a listbox item is selected
        if 'img_control_frame' in self.stats_elements and self.stats_elements['img_control_frame'].winfo_ismapped():
            self.stats_elements['img_control_frame'].pack_forget()

    def on_image_file_select(self, event):
        """When an image is selected from the listbox, show preview and enable attach button"""
        selection = self.stats_elements['image_listbox'].curselection()
        if not selection:
            return
            
        selected_index = selection[0]
        
        # Get image data from our mapping
        if not hasattr(self, 'image_data_mapping') or selected_index not in self.image_data_mapping:
            print(f"[interface_builder image hints] Error: No image data found for index {selected_index}")
            return
        
        image_data = self.image_data_mapping[selected_index]
        image_path = image_data['path']
        
        try:
            from PIL import Image, ImageTk
            image = Image.open(image_path)
            ratio = min(200 / image.width, 200 / image.height)
            new_size = (int(image.width * ratio), int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.stats_elements['image_preview'].configure(image=photo)
            self.stats_elements['image_preview'].image = photo
            
            # Store the image data for attaching
            self.current_image_data = image_data
            
            # Show the preview and attach button
            self.stats_elements['img_control_frame'].pack(fill='x', pady=5)
            self.stats_elements['prop_attach_btn'].pack(side='left', padx=5)
        except Exception as e:
            print(f"[interface_builder image hints] Error previewing image: {e}")
            print(f"[interface_builder image hints] Attempted to load from path: {image_path}")

    def show_manual_hint(self):
        """Show the manual hint text box and hide image selection"""
        if 'image_listbox' in self.stats_elements and self.stats_elements['image_listbox'].winfo_ismapped():
            self.stats_elements['image_listbox'].pack_forget()
        if 'img_control_frame' in self.stats_elements and self.stats_elements['img_control_frame'].winfo_ismapped():
            self.stats_elements['img_control_frame'].pack_forget()
        if 'attached_image_label' in self.stats_elements and self.stats_elements['attached_image_label'].winfo_ismapped():
            self.stats_elements['attached_image_label'].pack_forget()
        
        if 'prop_control_buttons' in self.stats_elements:
            # Hide specific buttons if they are packed
            if self.stats_elements['prop_back_btn'].winfo_ismapped():
                self.stats_elements['prop_back_btn'].pack_forget()
            if self.stats_elements['open_browser_btn'].winfo_ismapped(): # New button
                self.stats_elements['open_browser_btn'].pack_forget()
            # If the frame itself is still visible because of other content (should not be the case here),
            # or to be absolutely sure it's gone if it only contained these.
            if not self.stats_elements['prop_control_buttons'].winfo_children():
                 self.stats_elements['prop_control_buttons'].pack_forget()
            elif not any(btn.winfo_ismapped() for btn in [self.stats_elements['prop_back_btn'], self.stats_elements['open_browser_btn']]):
                 # If both are now gone, hide the parent frame
                 if self.stats_elements['prop_control_buttons'].winfo_ismapped():
                    self.stats_elements['prop_control_buttons'].pack_forget()


        # Show text box and buttons
        if 'msg_entry' in self.stats_elements:
            self.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)
        if 'hint_buttons_frame' in self.stats_elements:
            self.stats_elements['hint_buttons_frame'].pack(pady=5)
        
        # Reset image selection state
        self.current_hint_image = None
        if hasattr(self, 'current_image_data'):
            delattr(self, 'current_image_data')
        
        if 'image_btn' in self.stats_elements: # image_btn is the Combobox (dropdown)
            try: # Check if it's a Combobox and has a 'set' method
                if hasattr(self.stats_elements['image_btn'], 'set'):
                    self.stats_elements['image_btn'].set('')
                elif hasattr(self.stats_elements['image_btn'], '_name'): # sv_ttk Combobox workaround
                    self.app.root.nametowidget(self.stats_elements['image_btn']._name).set('')
            except Exception as e:
                print(f"Error resetting image_btn (dropdown): {e}")

    def attach_image(self):
        """Attach the selected image to the hint"""
        if hasattr(self, "current_image_data"):
            image_data = self.current_image_data
            # Show the attached filename
            filename = image_data['filename']
            prop_name = image_data['prop_name']
            
            # Display info about the attachment
            display_text = filename
            self.stats_elements['attached_image_label'].config(text=f"Attached: {display_text}")
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
                rel_path = os.path.relpath(image_data['path'], os.path.join(os.path.dirname(__file__), "sync_directory"))
                self.current_hint_image = rel_path
                    
                # Enable send button
                if self.stats_elements['send_btn']:
                    self.stats_elements['send_btn'].config(state='normal')
                
                print(f"[interface_builder image hints] Attached image from path: {image_data['path']}")
                print(f"[interface_builder image hints] Relative path for sending: {rel_path}")
                print(f"[interface_builder image hints] From prop: {prop_name} (key: {image_data['prop_key']})")
            except Exception as e:
                print(f"[interface_builder image hints] Error getting image path: {e}")

    def _get_image_files_for_prop_and_cousins(self, selected_prop_item_text, room_name_str, prop_mappings_data):
        """
        Gathers a list of image data dictionaries for the selected prop and its cousins.
        Uses prop_name_mapping.json to find related 'cousin' props.
        Looks for image files in the sync_directory/hint_image_files/<room_folder>/<prop_display_name> folder.
        Output: [{'filename': str, 'prop_name': str, 'prop_key': str, 'path': str}, ...]
        """
        image_list_data = []
        if not selected_prop_item_text or not room_name_str:
            print("[InterfaceBuilder] _get_image_files: Missing prop text or room name.")
            return image_list_data

        # Extract original prop name from the dropdown text "Display Name (original_name)"
        # Handle cases where the format might be slightly different or missing ()
        original_name = selected_prop_item_text
        if '(' in original_name and original_name.endswith(')'):
             try:
                 original_name = selected_prop_item_text.split("(")[-1].rstrip(")")
             except IndexError:
                 print(f"[InterfaceBuilder] _get_image_files: Could not parse original_name from: {selected_prop_item_text}")


        room_key = None
        if hasattr(self, "audio_hints") and hasattr(self.audio_hints, "ROOM_MAP"):
            room_key = self.audio_hints.ROOM_MAP.get(room_name_str.lower())
            if room_key is None:
                 print(f"[InterfaceBuilder] _get_image_files: Room name '{room_name_str.lower()}' not found in audio_hints.ROOM_MAP.")


        # Get display name for the primary selected prop - use original_name as fallback
        primary_display_name = original_name
        if room_key and room_key in prop_mappings_data:
            mappings = prop_mappings_data[room_key]["mappings"]
            if original_name in mappings:
                primary_display_name = mappings[original_name].get("display", original_name)
            else:
                 print(f"[InterfaceBuilder] _get_image_files: Original prop key '{original_name}' not found in mappings for room key '{room_key}'.")
        else:
             if room_key: # Only print if room_key was determined but not in mappings
                 print(f"[InterfaceBuilder] _get_image_files: Room key '{room_key}' not found in prop_mappings_data.")


        # Find cousin props
        cousin_props_data = [] # List of {'key': str, 'display': str}
        if room_key and room_key in prop_mappings_data:
            mappings = prop_mappings_data[room_key]["mappings"]
            prop_info = mappings.get(original_name, {}) # Get info for the primary prop
            cousin_value = prop_info.get("cousin")

            if cousin_value is not None: # Check if cousin value exists (can be 0, False, etc.)
                print(f"[InterfaceBuilder] _get_image_files: Primary prop '{original_name}' has cousin value '{cousin_value}'. Looking for cousins.")
                for p_key, info in mappings.items():
                    # Ensure the cousin value matches AND it's not the primary prop itself
                    if info.get("cousin") == cousin_value and p_key != original_name:
                        cousin_display = info.get("display", p_key)
                        cousin_props_data.append({'key': p_key, 'display': cousin_display})
                if cousin_props_data:
                    print(f"[InterfaceBuilder] _get_image_files: Found {len(cousin_props_data)} cousin(s) with cousin value '{cousin_value}'.")
                else:
                     print(f"[InterfaceBuilder] _get_image_files: Found no other props with cousin value '{cousin_value}'.")
            else:
                 print(f"[InterfaceBuilder] _get_image_files: Primary prop '{original_name}' has no 'cousin' value defined.")


        # Collect images
        # List of props to scan. Start with the primary prop, then add cousins found.
        props_to_scan = [{'key': original_name, 'display': primary_display_name}] + cousin_props_data
        added_image_paths = set() # To avoid duplicates

        print(f"[InterfaceBuilder] _get_image_files: Scanning {len(props_to_scan)} prop folder(s) for images.")
        for prop_data in props_to_scan:
            # Construct the expected folder path based on the display name
            folder_path = os.path.join(
                os.path.dirname(__file__), # Start from the script's directory
                "sync_directory",
                "hint_image_files",
                room_name_str.lower(),
                prop_data['display'] # Use the display name for the folder
            )
            print(f"[InterfaceBuilder] _get_image_files: Checking folder: {folder_path}")

            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                allowed_exts = [".png", ".jpg", ".jpeg", ".gif", ".bmp"]
                try:
                    image_files = [f for f in os.listdir(folder_path) if os.path.splitext(f)[1].lower() in allowed_exts]
                    print(f"[InterfaceBuilder] _get_image_files: Found {len(image_files)} image files in {prop_data['display']} folder.")
                    for img_filename in sorted(image_files):
                        full_path = os.path.join(folder_path, img_filename)
                        if full_path not in added_image_paths:
                            image_list_data.append({
                                'filename': img_filename,
                                'prop_name': prop_data['display'], # The display name of the folder it was found in
                                'prop_key': prop_data['key'],     # The original key of the folder it was found in
                                'path': full_path
                            })
                            added_image_paths.add(full_path)
                except OSError as e:
                    print(f"[InterfaceBuilder] _get_image_files Error listing files in {folder_path}: {e}")
            else:
                print(f"[InterfaceBuilder] _get_image_files: Folder not found or is not a directory: {folder_path}")

        print(f"[InterfaceBuilder] _get_image_files: Finished scanning. Total images found: {len(image_list_data)}")
        return image_list_data

    def clear_manual_hint(self):
        """Clear the manual hint text and reset image attachment state"""
        # Clear text input
        if 'msg_entry' in self.stats_elements:
            self.stats_elements['msg_entry'].delete('1.0', tk.END)
            self.stats_elements['msg_entry'].pack(fill='x', pady=8, padx=5)
        
        # Reset image attachment state
        self.current_hint_image = None
        if hasattr(self, 'current_image_data'):
            delattr(self, 'current_image_data')
        
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
        
        # Reset hint requested flag
        self.app.kiosk_tracker.kiosk_stats[computer_name]['hint_requested'] = False
        
        # Update tracking state
        if not hasattr(self, '_last_hint_request_states'):
            self._last_hint_request_states = {}
        self._last_hint_request_states[computer_name] = False

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
        
        # Stop auto-reset timer if running
        if computer_name in self.auto_reset_timer_ids:
            self.app.root.after_cancel(self.auto_reset_timer_ids[computer_name])
            del self.auto_reset_timer_ids[computer_name]
        
        # Clear auto-reset countdown in dropdown if present
        if computer_name in self.connected_kiosks and 'dropdown' in self.connected_kiosks[computer_name]:
            dropdown = self.connected_kiosks[computer_name]['dropdown']
            dropdown.set('')

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

        # Assume the video command will succeed and update local state immediately
        try:
            self.app.kiosk_tracker.kiosk_stats[computer_name]['video_playing'] = True
            print(f"[interface builder] Optimistically set video_playing=True for {computer_name}")
            # Immediately update the stats display for the selected kiosk
            if self.selected_kiosk == computer_name:
                self.update_stats_display(computer_name)
        except Exception as e:
            # Log error but don't stop the process, the next status update will correct the state
            print(f"[interface builder] Error during optimistic video_playing update: {e}")

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

                ttc_text = f"Escape Time:\n{ttc_minutes:02d}:{ttc_seconds:02d}"
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
        
        # Update all kiosk hint request indicators
        self.update_all_kiosk_hint_statuses()
        
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
            
            # After removing a kiosk, update the "No kiosks" message visibility
            self.update_no_kiosks_message()

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
        def hide_icon(event, cn=computer_name): # Pass computer_name via default arg for clarity
            if cn not in self.connected_kiosks:
                return

            kiosk_data = self.connected_kiosks[cn]
            current_icon_label = kiosk_data.get('icon_label')

            if current_icon_label and current_icon_label.winfo_exists() and current_icon_label.winfo_manager():  # If visible
                # Stop the blink timer if it exists
                if kiosk_data.get('icon_blink_after_id'):
                    self.app.root.after_cancel(kiosk_data['icon_blink_after_id'])
                    kiosk_data['icon_blink_after_id'] = None
                
                # Repack elements without the icon
                self._repack_kiosk_elements(cn, include_icon=False)
        
        icon_label.bind('<Button-1>', hide_icon)
        
        # Pack the icon label first, before any other elements, then immediately hide it
        icon_label.pack(side='left', padx=(0,5))
        icon_label.pack_forget()
        
        # Now create and pack other elements
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            room_num = self.app.kiosk_tracker.kiosk_assignments[computer_name]
            room_name = self.app.rooms[room_num]
            
            # Get room color from mapping, default to black if not found
            room_color = self.ROOM_COLORS.get(room_num, "black")
            
            # Create room name label
            name_label = tk.Label(frame, 
                text=room_name,
                font=('Arial', 12, 'bold'),
                fg=room_color,
                width=15,
                anchor='center')  # Apply room-specific color
            
            # Create dropdown first
            room_var = tk.StringVar()
            dropdown = ttk.Combobox(frame, textvariable=room_var, 
                values=list(self.app.rooms.values()), state='readonly')
            dropdown.pack(side='left', padx=5, anchor='e')
            
            # Pack room name after dropdown
            name_label.pack(side='left', padx=(30,3))
        else:
            # Create dropdown first  
            room_var = tk.StringVar()
            dropdown = ttk.Combobox(frame, textvariable=room_var, 
                values=list(self.app.rooms.values()), state='readonly')
            dropdown.pack(side='left', padx=5, anchor='e')
            
            # Pack unassigned label after dropdown
            name_label = tk.Label(frame, 
                text="Unassigned",
                font=('Arial', 12, 'bold'),
                width=15,
                anchor='center')
            name_label.pack(side='left', padx=5)
        
        def click_handler(cn=computer_name):
            self.select_kiosk(cn)
        
        frame.bind('<Button-1>', lambda e: click_handler())
        name_label.bind('<Button-1>', lambda e: click_handler())
        
        # Store the dropdown reference in connected_kiosks for auto-reset display
        if computer_name not in self.connected_kiosks:
            self.connected_kiosks[computer_name] = {}
        self.connected_kiosks[computer_name]['dropdown'] = dropdown
        
        def on_room_select(event):
            if not room_var.get():
                return
            
            # Check if the text contains "Auto-reset" - don't process if it's the timer
            if "Auto-reset:" in room_var.get():
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
            text="Reboot Computer",
            bg='#FF6B6B',
            fg='white',
            cursor="hand2",
            anchor='e'
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
        reboot_btn.pack(side='right', padx=(20, 5), anchor='e')

        # Add mini timer label at the end
        timer_label = tk.Label(frame,
            text="--:--",
            font=('Arial', 10, 'bold'),
            width=6,
            anchor='center')
        timer_label.pack(side='left', padx=5)
        
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
        
        # After adding a kiosk, update the "No kiosks" message visibility
        self.update_no_kiosks_message()

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
                    
                    # Ensure tracking dictionary is initialized and updated
                    if not hasattr(self, '_last_hint_request_states'):
                        self._last_hint_request_states = {}
                    self._last_hint_request_states[computer_name] = True
                else:
                    if(self.hint_debug):
                        print(f"[interface builder][AdminInterface] mark_help_requested: Clearing HINT REQUESTED for {computer_name} from state")
                    self.connected_kiosks[computer_name]['help_label'].config(
                         text="",
                         fg='red',
                         font=('Arial', 14, 'bold')
                    )
                    
                    # Update tracking state
                    if not hasattr(self, '_last_hint_request_states'):
                        self._last_hint_request_states = {}
                    self._last_hint_request_states[computer_name] = False
            else:
                print(f"[interface builder][AdminInterface] mark_help_requested: Ignoring help request - no kiosk stats found for {computer_name}")

        else:
            print(f"[interface builder][AdminInterface] mark_help_requested: Ignoring help request - kiosk {computer_name} not in connected kioskl list")
            
    def handle_gm_assistance_accepted(self, computer_name):
        """Handle when GM assistance is accepted by showing and blinking the icon"""
        if computer_name not in self.connected_kiosks:
            return
        
        kiosk_data = self.connected_kiosks[computer_name]
        icon_label = kiosk_data.get('icon_label') # Use .get() for safety
        
        # Ensure icon_label exists and is valid
        if not icon_label or not icon_label.winfo_exists():
            return

        # Cancel any existing blink timer
        if kiosk_data.get('icon_blink_after_id'): # Use .get()
            self.app.root.after_cancel(kiosk_data['icon_blink_after_id'])
            kiosk_data['icon_blink_after_id'] = None # Explicitly set to None
        
        def blink():
            """Toggle icon visibility every 500ms"""
            if computer_name not in self.connected_kiosks: # Kiosk might have been removed
                return
            
            # Fetch kiosk_data and icon_label again inside blink, in case they changed
            # or to ensure we have the most current references, though less likely to change rapidly.
            current_kiosk_data = self.connected_kiosks.get(computer_name)
            if not current_kiosk_data: return # Kiosk removed during blink cycle

            current_icon_label = current_kiosk_data.get('icon_label')
            if not current_icon_label or not current_icon_label.winfo_exists(): # Icon label might be destroyed
                if current_kiosk_data.get('icon_blink_after_id'): # Stop further blinking if icon is gone
                    self.app.root.after_cancel(current_kiosk_data['icon_blink_after_id'])
                    current_kiosk_data['icon_blink_after_id'] = None
                return

            is_currently_visible = current_icon_label.winfo_manager()

            if is_currently_visible:
                # Icon is currently shown, so the blink will hide it. Repack without icon.
                self._repack_kiosk_elements(computer_name, include_icon=False)
            else:
                # Icon is currently hidden, so the blink will show it. Repack with icon.
                self._repack_kiosk_elements(computer_name, include_icon=True)
            
            # Schedule next blink
            current_kiosk_data['icon_blink_after_id'] = self.app.root.after(500, blink)
        
        # Start blinking
        blink()

    def stop_gm_assistance_icon(self, computer_name):
        """Stop the GM assistance icon from blinking and hide it, then repack."""
        if computer_name not in self.connected_kiosks:
            return
        
        kiosk_data = self.connected_kiosks[computer_name]
        
        # Cancel blink timer if it exists
        if kiosk_data.get('icon_blink_after_id'): # Use .get()
            self.app.root.after_cancel(kiosk_data['icon_blink_after_id'])
            kiosk_data['icon_blink_after_id'] = None
        
        # Repack elements without the icon (this will also hide it if it was visible
        # because _repack_kiosk_elements only packs it if include_icon is True)
        self._repack_kiosk_elements(computer_name, include_icon=False)

    def select_kiosk(self, computer_name):
        """Handle selection of a kiosk and setup of its interface"""
        try:
            #print(f"[interface builder] === KIOSK SELECTION START: {computer_name} ===")

            # --- Clean up existing streams before switching ---
            # Check if a kiosk was previously selected AND it's a different kiosk
            if self.selected_kiosk is not None and self.selected_kiosk != computer_name:
                previous_kiosk_name = self.selected_kiosk
                if(self.select_kiosk_debug):
                    print(f"[interface builder] Switching kiosk from {previous_kiosk_name} to {computer_name}. Cleaning up previous.")

                # --- Stop Camera if active for the previous kiosk ---
                if getattr(self, 'camera_active', False) and \
                   self.stats_elements.get('current_computer') == previous_kiosk_name:
                    if(self.select_kiosk_debug):
                        print(f"[interface builder] Disconnecting camera for {previous_kiosk_name} due to kiosk switch.")
                    try:
                        self.video_client.disconnect()
                        self.camera_active = False
                    except Exception as e:
                        print(f"[interface builder] Error disconnecting video for {previous_kiosk_name}: {e}")
                    # No need to update old UI buttons as they are destroyed/recreated

                # --- Stop Audio if active for the previous kiosk ---
                audio_client = self.audio_clients.get(previous_kiosk_name)
                if audio_client and self.audio_active.get(previous_kiosk_name, False):
                    print(f"[interface builder] Disconnecting audio for {previous_kiosk_name} due to kiosk switch.")
                    try:
                        # Stop speaking first if active
                        if self.speaking.get(previous_kiosk_name, False):
                             print(f"[interface builder] Stopping speaking for {previous_kiosk_name}.")
                             audio_client.stop_speaking()
                             self.speaking[previous_kiosk_name] = False
                             # Reset root background only if it was the one actively speaking visually
                             # if previous_kiosk_name == self.selected_kiosk: # This check might be tricky now
                             #    self.app.root.configure(bg='systemButtonFace')

                        print(f"[interface builder] Disconnecting audio client for {previous_kiosk_name}.")
                        audio_client.disconnect()
                        self.audio_active[previous_kiosk_name] = False
                    except Exception as e:
                        print(f"[interface builder] Error disconnecting audio for {previous_kiosk_name}: {e}")
                if(self.select_kiosk_debug):
                    print(f"[interface builder] Cleanup finished for {previous_kiosk_name}.")

            elif self.selected_kiosk is not None and self.selected_kiosk == computer_name:
                 # Selecting the same kiosk - allow refresh
                 print(f"[interface builder] Re-selecting the same kiosk: {computer_name}. Refreshing UI.")
                 # Execution will continue below, effectively refreshing the UI
            else:
                 # No kiosk was previously selected, or it's the very first selection
                 print(f"[interface builder] No previous kiosk selected or first selection. Setting up {computer_name}.")


            # ***** MODIFICATION START *****
            # Set the selected kiosk state *before* setting up the new UI
            # This ensures subsequent functions/callbacks have the correct context.
            if(self.select_kiosk_debug):
                print(f"[interface builder] Setting self.selected_kiosk from '{self.selected_kiosk}' to '{computer_name}'")
            self.selected_kiosk = computer_name
            # ***** MODIFICATION END *****


            # Setup stats panel (this clears and rebuilds the stats frame)
            if(self.select_kiosk_debug):
                print(f"[interface builder] Calling setup_stats_panel for {computer_name}")
            self.setup_stats_panel(computer_name) # Pass computer_name explicitly
            if(self.select_kiosk_debug):
                print(f"[interface builder] setup_stats_panel finished for {computer_name}")

            # Now update the UI elements based on the NEWLY selected kiosk
            # Use self.selected_kiosk (or computer_name, they are now the same)

            # Update stats frame title, hints, etc.
            room_num = None # Initialize room_num
            if self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
                room_num = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
                room_name = self.app.rooms[room_num]
                title = f"{room_name} ({self.selected_kiosk})"
                if(self.select_kiosk_debug):
                    print(f"[interface builder] Room assigned: {room_name} (#{room_num})")
                room_color = self.ROOM_COLORS.get(room_num, "black")
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 7, 'bold'), # Reduced font size slightly
                    fg=room_color,
                    labelanchor='n'
                )

                # Map room number to directory name for audio hints and image props
                room_dirs = { 6: "atlantis", 1: "casino", 5: "haunted", 2: "ma", 7: "time", 3: "wizard", 4: "zombie" }
                if room_num in room_dirs:
                    room_dir = room_dirs[room_num]
                    if hasattr(self, 'audio_hints'):
                        if(self.select_kiosk_debug):
                            print(f"[interface builder] Updating audio hints for room: {room_dir}")
                        self.audio_hints.update_room(room_dir)
                    if(self.select_kiosk_debug):
                        print(f"[interface builder] Updating image props dropdown")
                    self.update_image_props() # Update image props when room changes
                else:
                     print(f"[interface builder] Room number {room_num} not found in room_dirs mapping.")

            else:
                title = f"Unassigned ({self.selected_kiosk})"
                print(f"[interface builder] Kiosk {self.selected_kiosk} is unassigned.")
                self.stats_frame.configure(
                    text=title,
                    font=('Arial', 10, 'bold'),
                    fg='black',
                    labelanchor='n'
                )
                # Clear hints/props if unassigned
                if hasattr(self, 'audio_hints'): self.audio_hints.clear_hints()
                self.update_image_props() # Update to show empty props


            # Update Saved Hints Panel (if it exists)
            if hasattr(self, 'saved_hints'):
                if(self.select_kiosk_debug):
                    print(f"[interface builder] Updating saved hints panel for room: {room_num}")
                if room_num is not None: # Check if room_num was assigned
                    self.saved_hints.update_room(room_num)
                else:
                    self.saved_hints.clear_preview() # Clear if no room assigned

            # Update highlighting with dotted border
            if(self.select_kiosk_debug):
                print(f"[interface builder] Updating kiosk highlighting...")
            for cn, data in self.connected_kiosks.items():
                frame_widget = data.get('frame')
                if not frame_widget or not frame_widget.winfo_exists(): # Check if widget exists
                    continue

                if cn == self.selected_kiosk:
                    frame_widget.configure(
                        relief='solid',
                        borderwidth=1, # Use a thin solid border
                        highlightthickness=1, # Highlight thickness
                        highlightbackground='#363636', # Color of border when not focused
                        highlightcolor='#0078D7'  # A standard selection color
                    )
                    # --- Keep original button colors ---
                    # (This loop seems redundant if setup_stats_panel handles button colors,
                    #  but keeping it for safety unless confirmed unnecessary)
                    for widget in frame_widget.winfo_children():
                        if not widget.winfo_exists(): continue
                        if isinstance(widget, tk.Button):
                             # Example: find specific buttons if needed by text or name
                             if 'reboot_btn' in data and widget == data['reboot_btn']:
                                 widget.configure(bg='#FF6B6B', fg='white')
                             # Add other specific button styling if needed
                else:
                     frame_widget.configure(
                        relief='flat',
                        borderwidth=0,
                        highlightthickness=0
                    )
                    # --- Keep original button colors ---
                    # (Same redundancy note as above)
                for widget in frame_widget.winfo_children():
                        if not widget.winfo_exists(): continue
                        if isinstance(widget, tk.Button):
                            if 'reboot_btn' in data and widget == data['reboot_btn']:
                                widget.configure(bg='#FF6B6B', fg='white')
                            # Add other specific button styling if needed
            if(self.select_kiosk_debug):
                print(f"[interface builder] Highlighting updated.")


            # Update the actual stats display content for the selected kiosk
            if(self.select_kiosk_debug):
                print(f"[interface builder] Calling update_stats_display for {self.selected_kiosk}")
            self.update_stats_display(self.selected_kiosk)
            if(self.select_kiosk_debug):
                print(f"[interface builder] update_stats_display finished.")

            # Notify PropControl about room change (with safety check)
            if hasattr(self.app, 'prop_control') and self.app.prop_control:
                if self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
                    # room_num is already defined above if assigned
                    if room_num is not None:
                        print(f"[interface builder] Notifying prop control about room change to {room_num}")
                        # Use after to ensure UI updates settle before potential prop comms
                        self.app.root.after(100, lambda rn=room_num: self.app.prop_control.connect_to_room(rn)) # Pass room_num via lambda default
                    else:
                        print("[interface builder] Prop control notification skipped: Room number not resolved.")
                else:
                    print("[interface builder] No room assignment, skipping prop control notification")
                    # Consider disconnecting prop control if previously connected
                    self.app.prop_control.disconnect_current_room()


            #print(f"[interface builder] === KIOSK SELECTION END: {self.selected_kiosk} ===\n")

        except Exception as e:
            print(f"[interface builder] CRITICAL Error in select_kiosk for {computer_name}: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for easier debugging
            
    def update_stats_display(self, computer_name):
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return

        stats = self.app.kiosk_tracker.kiosk_stats[computer_name]

        if not self.stats_elements:  # Should not happen if panel is built
            return

        # Check if hints_label_below exists and is valid before configuring
        if self.stats_elements.get('hints_label_below') and hasattr(self.stats_elements['hints_label_below'], 'winfo_exists') and self.stats_elements['hints_label_below'].winfo_exists():
            total_hints = stats.get('total_hints', 0)
            try:
                self.stats_elements['hints_label_below'].config(
                    text=f"Hints Requested:\n{total_hints}"
                )
            except Exception as e:
                print(f"[interface builder] Error updating hints_label_below: {e}")
            
        # Check if hints_received_label exists and is valid before configuring
        if self.stats_elements.get('hints_received_label') and hasattr(self.stats_elements['hints_received_label'], 'winfo_exists') and self.stats_elements['hints_received_label'].winfo_exists():
            hints_received = stats.get('hints_received', 0)
            try:
                self.stats_elements['hints_received_label'].config(
                    text=f"Hints Received:\n{hints_received}"
                )
            except Exception as e:
                print(f"[interface builder] Error updating hints_received_label: {e}")

        # Music button state update
        music_button = self.stats_elements.get('music_button')
        if music_button and hasattr(music_button, 'winfo_exists') and music_button.winfo_exists():
            music_playing = stats.get('music_playing', False)

            if hasattr(music_button, 'music_on_icon') and hasattr(music_button, 'music_off_icon'):
                try:
                    current_image = music_button.cget('image')
                    
                    if music_playing and str(current_image) != str(music_button.music_on_icon):
                        music_button.config(
                            image=music_button.music_on_icon
                        )
                    elif not music_playing and str(current_image) != str(music_button.music_off_icon):
                        music_button.config(
                            image=music_button.music_off_icon
                        )
                except tk.TclError:
                    print("[interface builder] Music button was destroyed")

        timer_time = stats.get('timer_time', 3600)
        timer_minutes = int(timer_time // 60)
        timer_seconds = int(timer_time % 60)
        
        if self.stats_elements.get('current_time') and hasattr(self.stats_elements['current_time'], 'winfo_exists') and self.stats_elements['current_time'].winfo_exists():
            try:
                self.stats_elements['current_time'].config(
                    text=f"{timer_minutes:02d}:{timer_seconds:02d}"
                )
            except Exception as e:
                print(f"[interface builder] Error updating current_time: {e}")

        # Continue with similar pattern for other UI elements
        
        timer_button = self.stats_elements.get('timer_button')
        if timer_button and hasattr(timer_button, 'winfo_exists') and timer_button.winfo_exists():
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
                    print("[interface builder] Timer button was destroyed")
            else:
                try:
                    if is_running and timer_button.cget('text') != "Stop Room":
                        timer_button.config(text="Stop Room")
                    elif not is_running and timer_button.cget('text') != "Start Room":
                        timer_button.config(text="Start Room")
                except tk.TclError:
                    print("[interface builder] Timer button was destroyed")
        
        if computer_name in self.app.kiosk_tracker.kiosk_assignments:
            if self.stats_elements.get('send_btn') and hasattr(self.stats_elements['send_btn'], 'winfo_exists') and self.stats_elements['send_btn'].winfo_exists():
                try:
                    self.stats_elements['send_btn'].config(state='normal')
                except Exception as e:
                    print(f"[interface builder] Error updating send_btn: {e}")
        else:
            if self.stats_elements.get('send_btn') and hasattr(self.stats_elements['send_btn'], 'winfo_exists') and self.stats_elements['send_btn'].winfo_exists():
                try:
                    self.stats_elements['send_btn'].config(state='disabled')
                except Exception as e:
                    print(f"[interface builder] Error updating send_btn: {e}")
        
        current_hint_request = stats.get('hint_requested', False)
        if not hasattr(self, '_last_hint_request_states'):
            self._last_hint_request_states = {}

        last_hint_request = self._last_hint_request_states.get(computer_name)
        
        if last_hint_request != current_hint_request:
            self.mark_help_requested(computer_name)
            self._last_hint_request_states[computer_name] = current_hint_request
        
        # Update hint request status for ALL connected kiosks, not just the selected one
        self.update_all_kiosk_hint_statuses()
        
        # Check for prop control and last progress time
        if self.app.prop_control and self.selected_kiosk in self.app.kiosk_tracker.kiosk_assignments:
            room_number = self.app.kiosk_tracker.kiosk_assignments[self.selected_kiosk]
            
            if room_number in self.app.prop_control.last_progress_times:
                self.update_last_progress_time_display(room_number)
        else:
            if self.stats_elements.get('last_progress_label') and hasattr(self.stats_elements['last_progress_label'], 'winfo_exists') and self.stats_elements['last_progress_label'].winfo_exists():
                try:
                    self.stats_elements['last_progress_label'].config(text="Last Progress:\nN/A", anchor='w')
                except Exception as e:
                    print(f"[interface builder] Error updating last_progress_label: {e}")

        # Update last prop finished name
        room_number = self.app.kiosk_tracker.kiosk_assignments.get(self.selected_kiosk, None)
        if room_number and self.app.prop_control:
            last_prop_finished = self.app.prop_control.last_prop_finished.get(room_number, 'N/A')
            if self.stats_elements.get('last_prop_label') and hasattr(self.stats_elements['last_prop_label'], 'winfo_exists') and self.stats_elements['last_prop_label'].winfo_exists():
                try:
                    self.stats_elements['last_prop_label'].config(text=f"Last Prop Finished:\n{last_prop_finished}", anchor='w')
                except Exception as e:
                    print(f"[interface builder] Error updating last_prop_label: {e}")
            else:
                if self.stats_elements.get('last_prop_label') and hasattr(self.stats_elements['last_prop_label'], 'winfo_exists') and self.stats_elements['last_prop_label'].winfo_exists():
                    try:
                        self.stats_elements['last_prop_label'].config(text="Last Prop Finished:\nN/A", anchor='w')
                    except Exception as e:
                        print(f"[interface builder] Error updating last_prop_label: {e}")

        # Auto-start state update
        auto_start_check = self.stats_elements.get('auto_start_check')
        if auto_start_check and hasattr(auto_start_check, 'winfo_exists') and auto_start_check.winfo_exists():
            auto_start = stats.get('auto_start', False)
            try:
                auto_start_check.config(text="[✓] Auto-Start" if auto_start else "[  ] Auto-Start")
            except tk.TclError:
                print("[interface builder] Auto-start checkbox was destroyed")

        # Update Music Volume Label
        music_vol_label = self.stats_elements.get('music_volume_label')
        if music_vol_label and music_vol_label.winfo_exists():
            level = stats.get('music_volume_level', 7)
            try:
                music_vol_label.config(text=f"Music Volume: {level}/10")
            except tk.TclError:
                print("[interface builder] Music volume label was destroyed")

        # Update Hint Volume Label
        hint_vol_label = self.stats_elements.get('hint_volume_label')
        if hint_vol_label and hint_vol_label.winfo_exists():
            level = stats.get('hint_volume_level', 7)
            try:
                hint_vol_label.config(text=f"Hint Volume: {level}/10")
            except tk.TclError:
                print("[interface builder] Hint volume label was destroyed")

        # --- VIDEO BUTTON ICON UPDATE (Revised) ---
        video_button = self.stats_elements.get('video_button')  # Use the correct key

        if video_button and hasattr(video_button, 'winfo_exists') and video_button.winfo_exists():
            is_video_playing = stats.get('video_playing', False)
            
            # Check if the button has the necessary icon object attributes
            if hasattr(video_button, 'video_icon_obj') and \
               hasattr(video_button, 'video_playing_icon_obj'):
                
                try:
                    current_img_name_str = video_button.cget('image')  # This is a string name like "pyimageX"
                    
                    target_icon_to_set = None
                    expected_icon_name_str = ""

                    if is_video_playing:
                        target_icon_to_set = video_button.video_playing_icon_obj
                        if target_icon_to_set:
                             expected_icon_name_str = str(target_icon_to_set)
                    else:
                        target_icon_to_set = video_button.video_icon_obj
                        if target_icon_to_set:
                             expected_icon_name_str = str(target_icon_to_set)

                    # Only attempt to config if the target PhotoImage object exists (is not None)
                    # AND the current image is different from the target image.
                    if target_icon_to_set is not None:
                        if current_img_name_str != expected_icon_name_str:
                            video_button.config(image=target_icon_to_set)

                except tk.TclError as e:
                    print(f"[interface builder] Video button TclError: {e}")

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
        
        # Also clear the hint requested status
        if computer_name in self.app.kiosk_tracker.kiosk_stats:
            self.app.kiosk_tracker.kiosk_stats[computer_name]['hint_requested'] = False
            
            # Update tracking state
            if not hasattr(self, '_last_hint_request_states'):
                self._last_hint_request_states = {}
            self._last_hint_request_states[computer_name] = False
            
            # Clear help label
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")

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
        
        # Also update the kiosk_stats to set hint_requested to False    
        if computer_name in self.app.kiosk_tracker.kiosk_stats:
            self.app.kiosk_tracker.kiosk_stats[computer_name]['hint_requested'] = False
            
            # Update tracking state
            if not hasattr(self, '_last_hint_request_states'):
                self._last_hint_request_states = {}
            self._last_hint_request_states[computer_name] = False
            
            # Clear help label text
            if computer_name in self.connected_kiosks:
                self.connected_kiosks[computer_name]['help_label'].config(text="")

        # Clear ALL hint entry fields regardless of which method was used
        if self.stats_elements['msg_entry']:
            self.stats_elements['msg_entry'].delete('1.0', 'end')

        if self.stats_elements['image_preview']:
            self.stats_elements['image_preview'].configure(image='')
            self.stats_elements['image_preview'].image = None
            
        self.clear_manual_hint()

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
        audio_client = self.audio_clients.get(computer_name)
        if not audio_client:
            print(f"[interface builder] Creating new AudioClient for {computer_name}")
            audio_client = AudioClient()
            self.audio_clients[computer_name] = audio_client
            self.audio_active[computer_name] = False
            self.speaking[computer_name] = False
            preferred_index = self.preferred_audio_device_index.get(computer_name)
            if preferred_index is not None:
                    print(f"[interface builder] Using preferred device index {preferred_index} for {computer_name}")
                    audio_client.selected_input_device_index = preferred_index
        
        is_active = self.audio_active.get(computer_name, False)
        listen_btn = self.stats_elements.get('listen_btn') 
        speak_btn = self.stats_elements.get('speak_btn')

        if is_active:
            try:
                print(f"[interface builder] Disconnecting audio for {computer_name}")
                
                if self.speaking.get(computer_name, False):
                    print(f"[interface builder] Audio is being stopped, also stopping speaking for {computer_name}")
                    self.toggle_speaking(computer_name) 

                if audio_client: 
                    audio_client.disconnect()

                self.audio_active[computer_name] = False
                if self.speaking.get(computer_name, False): 
                    print(f"[interface builder] Forcing speaking flag to false for {computer_name} as audio is now inactive.")
                    self.speaking[computer_name] = False

                if self.app.root and self.app.root.winfo_exists():
                    self.app.root.configure(bg='systemButtonFace') 

                if listen_btn and listen_btn.winfo_exists(): 
                    if hasattr(listen_btn, 'listen_icon'):
                        listen_btn.config(image=listen_btn.listen_icon, text="Start Listening")
                    else:
                        listen_btn.config(text="Start Listening")

                if speak_btn and speak_btn.winfo_exists(): 
                    speak_btn.config(state='disabled') 
                    if hasattr(speak_btn, 'enable_mic_icon'):
                        if speak_btn.cget('image') != str(speak_btn.enable_mic_icon): 
                            speak_btn.config(image=speak_btn.enable_mic_icon, text="Enable Microphone")
                    else:
                        if speak_btn.cget('text') != "Enable Microphone": 
                            speak_btn.config(text="Enable Microphone")
                    
                    current_speak_btn_bg = None
                    try:
                        current_speak_btn_bg = speak_btn.cget('bg')
                    except tk.TclError: 
                        pass
                        
                    if speak_btn.cget('activebackground') == '#ffcccc' or current_speak_btn_bg == '#ffcccc':
                            speak_btn.config(bg='systemButtonFace', activebackground='systemButtonFace')
            
            except Exception as e:
                print(f"[interface builder] Error stopping audio for {computer_name}: {e}")
                self.audio_active[computer_name] = False
                self.speaking[computer_name] = False 
                
                if self.app.root and self.app.root.winfo_exists():
                    self.app.root.configure(bg='systemButtonFace')

                if listen_btn and listen_btn.winfo_exists():
                    if hasattr(listen_btn, 'listen_icon'):
                        listen_btn.config(image=listen_btn.listen_icon, text="Start Listening")
                    else:
                        listen_btn.config(text="Start Listening")
                if speak_btn and speak_btn.winfo_exists():
                    speak_btn.config(state='disabled')
                    if hasattr(speak_btn, 'enable_mic_icon'):
                        speak_btn.config(image=speak_btn.enable_mic_icon, text="Enable Microphone")
                    else:
                        speak_btn.config(text="Enable Microphone")
                    speak_btn.config(bg='systemButtonFace', activebackground='systemButtonFace')
        else:
            # Start audio
            if listen_btn:
                listen_btn.config(text="Connecting...")

            def connect():
                try:
                    print(f"[interface builder] Attempting audio connection to {computer_name}")
                    if audio_client.connect(computer_name): 
                        print(f"[interface builder] Audio connected for {computer_name}")
                        self.audio_active[computer_name] = True
                        
                        if listen_btn and listen_btn.winfo_exists():
                            if hasattr(listen_btn, 'stop_listening_icon'):
                                listen_btn.config(
                                    image=listen_btn.stop_listening_icon,
                                    text="Stop Listening"
                                )
                            else:
                                listen_btn.config(text="Stop Listening")
                        if speak_btn and speak_btn.winfo_exists():
                                speak_btn.config(state='normal')
                    else:
                        print(f"[interface builder] Audio connection failed for {computer_name}")
                        self.audio_active[computer_name] = False
                        if listen_btn and listen_btn.winfo_exists():
                            if hasattr(listen_btn, 'listen_icon'):
                                listen_btn.config(image=listen_btn.listen_icon, text="Start Listening")
                            else:
                                listen_btn.config(text="Start Listening")

                except Exception as e:
                    print(f"[interface builder] Error connecting audio for {computer_name}: {e}")
                    self.audio_active[computer_name] = False 
                    if listen_btn and listen_btn.winfo_exists():
                        if hasattr(listen_btn, 'listen_icon'):
                            listen_btn.config(image=listen_btn.listen_icon, text="Start Listening")
                        else:
                            listen_btn.config(text="Start Listening")

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

        is_speaking_aib = self.speaking.get(computer_name, False) # AdminInterfaceBuilder's flag
        listen_btn = self.stats_elements.get('listen_btn')
        speak_btn = self.stats_elements.get('speak_btn')

        if is_speaking_aib: # If AdminInterfaceBuilder thinks it's speaking, try to STOP
            try:
                print(f"[interface builder] Stopping speaking for {computer_name}")
                if audio_client:
                    audio_client.stop_speaking() # Command the client to stop sending audio data

                self.speaking[computer_name] = False # Update AIB's state: no longer speaking

                # Update UI to reflect that speaking has stopped
                if computer_name == self.selected_kiosk: # Check if it's the currently selected kiosk
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.configure(bg='systemButtonFace')  # Reset main window background
                        self.stats_frame.configure(bg='systemButtonFace')

                if speak_btn and speak_btn.winfo_exists():
                    # Reset speak button to "Enable Microphone" appearance
                    if hasattr(speak_btn, 'enable_mic_icon'):
                        speak_btn.config(
                            image=speak_btn.enable_mic_icon,
                            text="Enable Microphone",
                            bg='systemButtonFace',       # Reset background color
                            activebackground='systemButtonFace'  # Reset active background color
                        )
                    else:
                        speak_btn.config(
                            text="Enable Microphone",
                            bg='systemButtonFace',
                            activebackground='systemButtonFace'
                        )
                    # The speak_btn state (normal/disabled) is primarily managed by 'toggle_audio'.
                    # If audio is still active, speak_btn should be in a 'normal' state here.

            except Exception as e:
                print(f"[interface builder] Error stopping speaking for {computer_name}: {e}")
                self.speaking[computer_name] = False # Ensure state is false on error
                # Attempt to reset UI as well
                if computer_name == self.selected_kiosk:
                    if self.app.root and self.app.root.winfo_exists():
                        self.app.root.configure(bg='systemButtonFace')
                        self.stats_frame.configure(bg='systemButtonFace')
                if speak_btn and speak_btn.winfo_exists():
                    if hasattr(speak_btn, 'enable_mic_icon'):
                        speak_btn.config(image=speak_btn.enable_mic_icon, text="Enable Microphone", bg='systemButtonFace', activebackground='systemButtonFace')
                    else:
                        speak_btn.config(text="Enable Microphone", bg='systemButtonFace', activebackground='systemButtonFace')
        else: # If AdminInterfaceBuilder thinks it's not speaking, try to START
            try:
                print(f"[interface builder] Starting speaking for {computer_name}")
                if audio_client.start_speaking(): 
                    self.speaking[computer_name] = True

                    if computer_name == self.selected_kiosk:
                            self.app.root.configure(bg='#f50202')  # Light red
                            self.stats_frame.configure(bg='#f50202')

                    if speak_btn:
                        if hasattr(speak_btn, 'disable_mic_icon'):
                            speak_btn.config(
                                image=speak_btn.disable_mic_icon,
                                text="Disable Microphone",
                                activebackground='#ffcccc'
                            )
                        else:
                            speak_btn.config(
                                text="Disable Microphone",
                                activebackground='#ffcccc'
                            )
                else: # This block executes if audio_client.start_speaking() returned False
                    print(f"[interface builder] audio_client.start_speaking() failed for {computer_name}.")
                    self.speaking[computer_name] = False # Ensure AIB's flag is false
                    # Reset button to "Enable Microphone" state
                    if speak_btn:
                        if hasattr(speak_btn, 'enable_mic_icon'):
                            speak_btn.config(
                                image=speak_btn.enable_mic_icon,
                                text="Enable Microphone",
                                bg='systemButtonFace',
                                activebackground='systemButtonFace'
                            )
                        else:
                            speak_btn.config(
                                text="Enable Microphone",
                                bg='systemButtonFace',
                                activebackground='systemButtonFace'
                            )
            except Exception as e:
                print(f"[interface builder] Error enabling microphone for {computer_name}: {e}")
                self.speaking[computer_name] = False # Ensure state is false on error
                    # Also reset button UI on exception during start attempt
                if speak_btn:
                    if hasattr(speak_btn, 'enable_mic_icon'):
                        speak_btn.config(
                            image=speak_btn.enable_mic_icon,
                            text="Enable Microphone",
                            bg='systemButtonFace',
                            activebackground='systemButtonFace'
                        )
                    else:
                        speak_btn.config(
                            text="Enable Microphone",
                            bg='systemButtonFace',
                            activebackground='systemButtonFace'
                        )

    def update_no_kiosks_message(self):
        """Show or hide the 'No kiosks found' message based on connection status"""
        if not self.connected_kiosks:
            # No kiosks connected, show the message
            self.no_kiosks_label.pack(fill='x', expand=True)
        else:
            # Kiosks are connected, hide the message
            if self.no_kiosks_label.winfo_manager():
                self.no_kiosks_label.pack_forget()

    # Add this new method to update all kiosk hint statuses
    def update_all_kiosk_hint_statuses(self):
        """Update hint request indicators for all connected kiosks"""
        for computer_name, kiosk_data in self.connected_kiosks.items():
            if computer_name in self.app.kiosk_tracker.kiosk_stats:
                current_hint_request = self.app.kiosk_tracker.kiosk_stats[computer_name].get('hint_requested', False)
                
                # Initialize tracking dict if needed
                if not hasattr(self, '_last_hint_request_states'):
                    self._last_hint_request_states = {}
                    
                last_hint_request = self._last_hint_request_states.get(computer_name)
                
                # Update UI if hint request state has changed
                if last_hint_request != current_hint_request:
                    help_label = kiosk_data.get('help_label')
                    if help_label and help_label.winfo_exists():
                        if current_hint_request:
                            help_label.config(
                                text="HINT REQUESTED",
                                fg='red',
                                font=('Arial', 14, 'bold')
                            )
                        else:
                            help_label.config(text="")
                        
                        # Update our tracking of the last state
                        self._last_hint_request_states[computer_name] = current_hint_request

    def change_music_volume(self, computer_name, delta):
        """Changes the music volume for the specified kiosk by delta (+1 or -1)."""
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return
        
        current_level = self.app.kiosk_tracker.kiosk_stats[computer_name].get('music_volume_level', 7)
        new_level = max(0, min(10, current_level + delta))  # Clamp between 0 and 10

        # Optimistically update local stats and UI
        self.app.kiosk_tracker.kiosk_stats[computer_name]['music_volume_level'] = new_level
        if self.selected_kiosk == computer_name:  # Update UI only if it's the selected kiosk
            if self.stats_elements.get('music_volume_label') and self.stats_elements['music_volume_label'].winfo_exists():
                self.stats_elements['music_volume_label'].config(text=f"Music Volume: {new_level}/10")
        
        # Send command to kiosk
        self.app.network_handler.send_set_music_volume_command(computer_name, new_level)

    def change_hint_volume(self, computer_name, delta):
        """Changes the hint audio volume for the specified kiosk by delta (+1 or -1)."""
        if computer_name not in self.app.kiosk_tracker.kiosk_stats:
            return
            
        current_level = self.app.kiosk_tracker.kiosk_stats[computer_name].get('hint_volume_level', 7)
        new_level = max(0, min(10, current_level + delta))  # Clamp between 0 and 10

        # Optimistically update local stats and UI
        self.app.kiosk_tracker.kiosk_stats[computer_name]['hint_volume_level'] = new_level
        if self.selected_kiosk == computer_name:  # Update UI only if it's the selected kiosk
            if self.stats_elements.get('hint_volume_label') and self.stats_elements['hint_volume_label'].winfo_exists():
                self.stats_elements['hint_volume_label'].config(text=f"Hint Volume: {new_level}/10")

        # Send command to kiosk
        self.app.network_handler.send_set_hint_volume_command(computer_name, new_level)
    
    def open_full_image_browser(self):
        """Opens a popup window to browse images for the currently selected prop."""
        selected_prop_item_text = self.img_prop_var.get()
        if not selected_prop_item_text:
            print("[InterfaceBuilder] open_full_image_browser: No prop selected in dropdown.")
            self.app.messagebox.showinfo("Image Browser", "Please select a prop first.", parent=self.app.root)
            return

        room_name_for_images = self.audio_hints.current_room if hasattr(self, "audio_hints") else None
        if not room_name_for_images:
            print("[InterfaceBuilder] open_full_image_browser: Room not determined from audio hints.")
            self.app.messagebox.showerror("Image Browser Error", "Could not determine the current room.", parent=self.app.root)
            return

        try:
            with open("prop_name_mapping.json", "r") as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[InterfaceBuilder] open_full_image_browser Error loading prop mappings for browser: {e}")
            self.app.messagebox.showerror("Image Browser Error", f"Failed to load prop mappings:\n{e}", parent=self.app.root)
            prop_mappings = {} # Continue with empty mappings

        # Use the helper function to get the list of all relevant image data
        all_images_data = self._get_image_files_for_prop_and_cousins(
            selected_prop_item_text,
            room_name_for_images,
            prop_mappings
        )

        if not all_images_data:
            print(f"[InterfaceBuilder] open_full_image_browser: No images found for prop '{selected_prop_item_text}' in room '{room_name_for_images}'.")
            self.app.messagebox.showinfo("Image Browser", "No images found for the selected prop or its cousins.", parent=self.app.root)
            return

        print(f"[InterfaceBuilder] open_full_image_browser: Opening browser popup with {len(all_images_data)} images.")
        self._build_image_browser_popup(all_images_data, selected_prop_item_text)

    def _build_image_browser_popup(self, image_data_list, prop_text):
        """Builds and displays the image browser popup window."""
        # Create popup window
        browser_popup = tk.Toplevel(self.app.root)
        browser_popup.title(f"Image Browser - {prop_text}")
        # Set initial size and position (can be resized by user)
        popup_width = 900
        popup_height = 900
        screen_width = browser_popup.winfo_screenwidth()
        screen_height = browser_popup.winfo_screenheight()
        x = (screen_width - popup_width) // 2
        y = (screen_height - popup_height) // 2
        browser_popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        # Make it transient to the main window and grab focus (modal-like)
        browser_popup.transient(self.app.root)
        browser_popup.grab_set()

        # Store references for event handlers and state tracking
        browser_popup.current_selected_image_data = None
        browser_popup.is_current_image_valid = False # Flag to indicate if current preview is attachable

        # --- Main Paned Window ---
        main_paned_window = ttk.PanedWindow(browser_popup, orient=tk.HORIZONTAL)
        main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # --- Left Panel: Scrollable Thumbnail Grid ---
        grid_frame_container = ttk.Frame(main_paned_window, width=400) # Initial width hint
        main_paned_window.add(grid_frame_container, weight=2) # Allow this panel to grow/shrink horizontally

        # Canvas and Scrollbar for the grid
        canvas = tk.Canvas(grid_frame_container)
        scrollbar = ttk.Scrollbar(grid_frame_container, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        # Frame to hold the grid items inside the canvas
        scrollable_frame = ttk.Frame(canvas)

        # Bind configure event to update scrollregion when content changes size
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Place the scrollable frame inside the canvas
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Configure grid columns to resize appropriately (optional but good)
        # Example: scrollable_frame.grid_columnconfigure(0, weight=1) etc.

        # Populate the thumbnail grid
        max_cols = 4 # Number of columns in the grid
        thumbnail_size = (120, 120) # Max size for thumbnails

        print(f"[InterfaceBuilder] _build_image_browser_popup: Populating grid with {len(image_data_list)} images.")
        for i, img_data in enumerate(image_data_list):
            row, col = divmod(i, max_cols)

            # Frame for each individual thumbnail item
            item_frame = ttk.Frame(scrollable_frame, padding=3, relief="solid", borderwidth=0) # Changed relief/border
            item_frame.grid(row=row, column=col, padx=3, pady=3, sticky="nsew") # Reduced padding

            try:
                # --- Load and resize thumbnail ---
                img = Image.open(img_data['path'])
                img.thumbnail(thumbnail_size) # Resize image while maintaining aspect ratio
                photo = ImageTk.PhotoImage(img)

                # --- Create image label ---
                img_label = ttk.Label(item_frame, image=photo, cursor="hand2") # Add hand cursor
                img_label.image = photo # Keep a reference to prevent garbage collection
                img_label.pack(pady=(0,2))

                # --- Create filename label ---
                filename_label = ttk.Label(item_frame, text=img_data.get('filename', 'N/A'), wraplength=thumbnail_size[0], font=("Arial", 8), anchor="center") # Use get, adjust wraplength
                filename_label.pack()

                # Store img_data with the label for easy access on click/double-click
                img_label.img_data_ref = img_data

                # --- Bind events ---
                img_label.bind("<Button-1>", lambda e, data=img_data: self._on_browser_thumbnail_select(e, data, browser_popup))
                img_label.bind("<Double-Button-1>", lambda e, data=img_data: self._on_browser_thumbnail_double_click(e, data, browser_popup))
                # Also bind clicks/double-clicks on the filename label
                filename_label.bind("<Button-1>", lambda e, data=img_data: self._on_browser_thumbnail_select(e, data, browser_popup))
                filename_label.bind("<Double-Button-1>", lambda e, data=img_data: self._on_browser_thumbnail_double_click(e, data, browser_popup))

            except Exception as e:
                # Handle errors loading individual thumbnails
                print(f"[InterfaceBuilder] _build_image_browser_popup Error loading thumbnail {img_data.get('path', 'N/A')}: {e}")
                error_label = ttk.Label(item_frame, text="Load Error", foreground="red", font=("Arial", 8))
                error_label.pack()
                filename_label = ttk.Label(item_frame, text=img_data.get('filename', 'N/A'), wraplength=thumbnail_size[0], font=("Arial", 8), anchor="center")
                filename_label.pack()


        # --- Right Panel: Preview and Attach ---
        preview_frame = ttk.Frame(main_paned_window, width=350) # Initial width hint
        main_paned_window.add(preview_frame, weight=3) # Allow this panel to grow/shrink more

        # Frame to center content vertically in preview pane
        preview_content_frame = ttk.Frame(preview_frame)
        preview_content_frame.pack(expand=True) # Center vertically

        # Label for preview image
        # Set a placeholder text and size it dynamically if possible
        browser_popup.preview_image_label = ttk.Label(preview_content_frame, text="Select an image to preview", anchor="center", padding=10)
        browser_popup.preview_image_label.pack(padx=10, pady=10) # No fill/expand here, let parent frame center

        # Frame for buttons below preview
        preview_button_frame = ttk.Frame(preview_content_frame)
        preview_button_frame.pack(pady=5)

        # Attach button (initially disabled)
        browser_popup.attach_button = ttk.Button(preview_button_frame, text="Attach Image", state="disabled",
                                     command=lambda: self._on_browser_attach_click(browser_popup))
        browser_popup.attach_button.pack(side="left", padx=5)

        # Back/Close button
        close_button = ttk.Button(preview_button_frame, text="Close", command=browser_popup.destroy)
        close_button.pack(side="left", padx=5)

    def _on_browser_thumbnail_select(self, event, image_data, popup_window):
        """
        Handles clicking a thumbnail in the image browser.
        Loads and displays the full-size preview, and enables the Attach button.
        Sets the `is_current_image_valid` flag on the popup window.
        """
        print(f"[InterfaceBuilder] _on_browser_thumbnail_select called for: {image_data.get('filename', 'N/A')}")

        # Ensure popup window and its widgets still exist
        if not popup_window or not hasattr(popup_window, 'preview_image_label') or not hasattr(popup_window, 'attach_button') or not popup_window.winfo_exists():
             print("[InterfaceBuilder] _on_browser_thumbnail_select: Popup window missing or destroyed. Aborting.")
             return # Abort if window is gone. Widgets are checked below before use.


        # Store the selected image data
        popup_window.current_selected_image_data = image_data

        # --- Reset flag and button state initially for robustness ---
        # Assume it's invalid until successfully loaded and processed below
        popup_window.is_current_image_valid = False
        if hasattr(popup_window, 'attach_button') and popup_window.attach_button.winfo_exists():
             popup_window.attach_button.config(state="disabled")
        # --- End Reset ---

        image_path = image_data.get('path') # Use .get() for safety
        if not image_path:
             print("[InterfaceBuilder] _on_browser_thumbnail_select: No 'path' found in image_data for preview.")
             if hasattr(popup_window, 'preview_image_label') and popup_window.preview_image_label.winfo_exists():
                  popup_window.preview_image_label.config(text="No Path Found", image=None)
             return # Cannot proceed without a path


        try:
            print(f"[InterfaceBuilder] _on_browser_thumbnail_select: Attempting to load preview image from {image_path}")
            image = Image.open(image_path)

            # Get current size of the preview label area to fit the preview
            # This requires the preview_image_label to be mapped (visible).
            # Use geometry manager info to get size, fall back to a default if not mapped yet.
            preview_area_width = 0
            preview_area_height = 0
            if hasattr(popup_window, 'preview_image_label') and popup_window.preview_image_label.winfo_exists():
                 # Get size from the parent container that centers the preview
                 preview_container = popup_window.preview_image_label.master
                 if preview_container and preview_container.winfo_exists():
                     # Use the size of the PanedWindow pane itself for better fitting
                     # Find the preview pane in the PanedWindow
                     preview_pane = None
                     if hasattr(popup_window, 'main_paned_window') and popup_window.main_paned_window.winfo_exists():
                          for pane in popup_window.main_paned_window.panes():
                              if pane == str(preview_container.master): # Compare widget names/paths
                                   preview_pane = popup_window.main_paned_window.nametowidget(pane)
                                   break # Found it

                     if preview_pane and preview_pane.winfo_exists():
                         preview_area_width = preview_pane.winfo_width()
                         preview_area_height = preview_pane.winfo_height() - (self.app.preview_button_frame.winfo_height() if hasattr(self.app.preview_button_frame, 'winfo_height') and self.app.preview_button_frame.winfo_exists() else 50) # Subtract button area

            # Fallback to a reasonable default size if dynamic size couldn't be determined
            preview_area_width = max(100, preview_area_width if preview_area_width > 0 else 350) # Match initial pane width hint
            preview_area_height = max(100, preview_area_height if preview_area_height > 0 else 500) # A bit taller


            img_copy = image.copy() # Work on a copy for resizing
            # Adjust scaling to fit within the preview area, allowing some padding
            max_preview_size = (preview_area_width - 20, preview_area_height - 20)
            img_copy.thumbnail(max_preview_size) # Resize image while maintaining aspect ratio

            photo = ImageTk.PhotoImage(img_copy)

            # --- Image loading and processing successful ---
            print(f"[InterfaceBuilder] _on_browser_thumbnail_select: Image loaded and processed successfully.")
            if hasattr(popup_window, 'preview_image_label') and popup_window.preview_image_label.winfo_exists():
                 popup_window.preview_image_label.config(image=photo, text="")
                 popup_window.preview_image_label.image = photo # Keep reference

            # --- Set flag and button state on success ---
            popup_window.is_current_image_valid = True # Set the flag!
            if hasattr(popup_window, 'attach_button') and popup_window.attach_button.winfo_exists():
                 popup_window.attach_button.config(state="normal") # Update button visually
                 print("[InterfaceBuilder] _on_browser_thumbnail_select: is_current_image_valid flag set to True, Attach button set to 'normal'.")
            else:
                 print("[InterfaceBuilder] _on_browser_thumbnail_select: Attach button widget not found or destroyed after successful load.")


        except FileNotFoundError:
            print(f"[InterfaceBuilder] _on_browser_thumbnail_select Error: Image file not found at {image_path}")
            if hasattr(popup_window, 'preview_image_label') and popup_window.preview_image_label.winfo_exists():
                 popup_window.preview_image_label.config(text="File Not Found", image=None)
            # Flag and button already disabled at the start of the method

        except Exception as e:
            # Catch other exceptions during image processing (PIL errors, etc.)
            print(f"[InterfaceBuilder] _on_browser_thumbnail_select Error: Failed to load or process image {image_data.get('path', 'N/A')}: {e}")
            if hasattr(popup_window, 'preview_image_label') and popup_window.preview_image_label.winfo_exists():
                 popup_window.preview_image_label.config(text=f"Load Error:\n{type(e).__name__}", image=None) # Show error type
            # Flag and button already disabled at the start of the method

    def _on_browser_attach_click(self, popup_window):
        """Handles clicking the Attach button in the image browser."""
        print("[InterfaceBuilder] _on_browser_attach_click called.")
        # Check if the flag indicates the currently selected image is valid
        if popup_window and hasattr(popup_window, 'is_current_image_valid') and popup_window.is_current_image_valid:
            if hasattr(popup_window, 'current_selected_image_data') and popup_window.current_selected_image_data:
                print(f"[InterfaceBuilder] Attaching image: {popup_window.current_selected_image_data.get('filename', 'N/A')}")
                self.current_image_data = popup_window.current_selected_image_data # Set for the main attach_image method
                self.attach_image() # Call the existing method to handle the attachment in the main UI
                popup_window.destroy() # Close the browser popup window
            else:
                print("[InterfaceBuilder] _on_browser_attach_click Error: is_current_image_valid is True but no current_selected_image_data found.")
                # This state indicates an internal logic issue if the flag was True but data wasn't set.
                self.app.messagebox.showerror("Attach Error", "No image data available to attach.", parent=popup_window)
        else:
             print("[InterfaceBuilder] _on_browser_attach_click ignored: is_current_image_valid is False or popup/flag missing.")
             # This condition should technically not be reachable if the button state is correctly tied to the flag,
             # as the button should be disabled when the flag is False.

    def _on_browser_thumbnail_double_click(self, event, image_data, popup_window):
        """Handles double-clicking a thumbnail in the image browser."""
        print(f"[InterfaceBuilder] Double-clicked thumbnail for: {image_data.get('filename', 'N/A')}")

        # First, simulate a single click to select and update preview.
        # This call will load the image, update the preview, and set the `is_current_image_valid` flag on the popup window.
        try:
            self._on_browser_thumbnail_select(event, image_data, popup_window)
            # Note: _on_browser_thumbnail_select handles its own errors and sets the flag/button state.
        except Exception as e:
             # Catch any unexpected errors that might occur *during* the call to _on_browser_thumbnail_select itself,
             # although image loading errors within _on_browser_thumbnail_select should be handled internally.
             print(f"[InterfaceBuilder] Unexpected error during _on_browser_thumbnail_select call from double-click for {image_data.get('filename', 'N/A')}: {e}")
             # In case of an unhandled error, ensure the flag is false
             if popup_window and hasattr(popup_window, 'is_current_image_valid'):
                 popup_window.is_current_image_valid = False


        # --- Check the is_current_image_valid flag to determine if attachment is possible ---
        # Ensure the popup window and the flag attribute exist before checking
        if popup_window and hasattr(popup_window, 'is_current_image_valid') and popup_window.is_current_image_valid:
            print(f"[InterfaceBuilder] Double-click: is_current_image_valid is True. Proceeding to attach via _on_browser_attach_click.")
            # If selection/loading was successful (flag is True), perform the attach action
            # Call the _on_browser_attach_click method, passing the popup_window
            try:
                self._on_browser_attach_click(popup_window)
            except Exception as e:
                 print(f"[InterfaceBuilder] Unexpected error during _on_browser_attach_click call from double-click: {e}")
        else:
            # If the flag is False, it means _on_browser_thumbnail_select determined
            # the image was not valid or the popup/flag is gone.
            # The error message from _on_browser_thumbnail_select should explain the image issue.
            print(f"[InterfaceBuilder] Double-click: is_current_image_valid is False. Image preview/selection likely failed or window closed. Attach aborted.")
            # No additional error message needed here, as _on_browser_thumbnail_select
            # already provided feedback if it failed to load the image.