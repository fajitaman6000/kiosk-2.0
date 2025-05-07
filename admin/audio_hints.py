import os
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
import tkinter as tk
from tkinter import ttk
import json

class AudioHints:
    # Room mapping dictionary to convert room names to their canonical forms
    ROOM_MAP = {
        "wizard": "wizard",
        "casino": "casino",
        "ma": "ma",  # Using ma instead of casino for MA room
        "haunted": "haunted",
        "zombie": "zombie",
        "atlantis": "atlantis",
        "time": "time"
    }

    # Special keys and display names for miscellaneous audio folders
    GLOBAL_OTHER_KEY = "_SPECIAL_GLOBAL_OTHER_"
    GLOBAL_OTHER_DISPLAY = "OTHER"
    ROOM_MISC_KEY = "_SPECIAL_ROOM_MISC_"
    ROOM_MISC_DISPLAY = "ROOM MISC"


    def __init__(self, parent, room_change_callback, app):
        #print("[audio hints]=== INITIALIZING audio hints ===")
        self.app = app
        self.parent = parent
        self.room_change_callback = room_change_callback
        self.current_room = None
        self.current_audio_file = None
        self.audio_root = os.path.join(os.path.dirname(__file__), "sync_directory", "hint_audio_files")
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # Create main frame with fixed width
        self.frame = tk.LabelFrame(parent, text="Play Audio", fg='black', font=('Arial', 10, 'bold'), labelanchor='ne')
        self.frame.pack(side='left', padx=10, pady=0, anchor='sw')
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=10, pady=5)
        
        # Create prop dropdown section with fixed width
        self.prop_frame = ttk.Frame(self.list_container)
        self.prop_frame.pack(pady=(0, 5))
        prop_label = ttk.Label(self.prop_frame, text="Select Prop:", font=('Arial', 10, 'bold'))
        prop_label.pack(side='left', padx=(0, 5))
        
        # Create prop dropdown (Combobox)
        self.prop_var = tk.StringVar()
        self.prop_dropdown = ttk.Combobox(
            self.prop_frame,
            textvariable=self.prop_var,
            state='readonly',
            width=30
        )
        self.prop_dropdown.pack(side='left')
        self.prop_dropdown.bind('<<ComboboxSelected>>', self.on_prop_select)
        
        # Create buttons row
        self.button_frame = ttk.Frame(self.list_container)
        self.button_frame.pack(fill='x')
        
        # Refresh Button
        self.refresh_button = ttk.Button(
            self.button_frame,
            text="⟳",
            command=self.refresh_audio_files,
            width=2
        )
        self.refresh_button.pack(side='left', padx=(0, 5))
        
        # Open Button
        self.open_button = ttk.Button(
            self.button_frame,
            text="Open",
            command=self.open_audio_browser,
            state='disabled'
        )
        self.open_button.pack(side='left', fill='x', expand=True)
        
        # Store available audio files for the selected prop
        self.available_audio_files = []
        
        # Add a mapping to store prop_key for each display item
        self.prop_data_mapping = {}
        
        #print("[audio hints]=== audio hints INITIALIZATION COMPLETE ===\n")

        self.load_prop_name_mappings()

    def update_room(self, room_name):
        """Update the prop list for the selected room"""
        #print(f"[audio hints]=== UPDATING AUDIO HINTS FOR {room_name} ===")
        
        room_name = room_name.lower() if room_name else None
        self.current_room = room_name
        
        self.prop_dropdown['values'] = ()
        self.available_audio_files = []
        self.open_button.config(state='disabled')
        self.prop_data_mapping = {} # Clear previous mapping
        
        props_list = []

        # 1. Add "OTHER" (Global Miscellaneous) - always at the top
        props_list.append(self.GLOBAL_OTHER_DISPLAY)
        self.prop_data_mapping[self.GLOBAL_OTHER_DISPLAY] = self.GLOBAL_OTHER_KEY
        
        # Load prop mappings from JSON (for regular props)
        try:
            with open('prop_name_mapping.json', 'r') as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[audio hints]Error loading prop mappings: {e}")
            prop_mappings = {}

        room_key = self.ROOM_MAP.get(room_name)
        
        if room_key: # Only add ROOM MISC and room-specific props if a room is selected
            # 2. Add "ROOM MISC" (Room-specific Miscellaneous) - after "OTHER"
            props_list.append(self.ROOM_MISC_DISPLAY)
            self.prop_data_mapping[self.ROOM_MISC_DISPLAY] = self.ROOM_MISC_KEY
            
            # 3. Add regular room props
            if room_key in prop_mappings:
                # Sort props by order as defined in prop_name_mapping.json
                room_props_data = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
                room_props_data.sort(key=lambda x: x[1]["order"])
                
                for prop_key_from_mapping, prop_info in room_props_data:
                    display_name = prop_info['display']
                    # The original code counted audio files here for the display string,
                    # but the request implies simple names "OTHER", "ROOM MISC", and prop display names.
                    # If counts are desired for props, uncomment and adapt the counting logic.
                    # prop_path = os.path.join(self.audio_root, self.current_room, display_name)
                    # audio_count = 0
                    # if os.path.exists(prop_path):
                    #     audio_files_in_prop_dir = [f for f in os.listdir(prop_path) if f.lower().endswith('.mp3')]
                    #     audio_count = len(audio_files_in_prop_dir)
                    # display_string = f"{display_name} ({audio_count})"
                    
                    display_string = f"{display_name}" # Just the display name
                    props_list.append(display_string)
                    self.prop_data_mapping[display_string] = prop_key_from_mapping # Map display name to original key

        # Update dropdown with the constructed list
        self.prop_dropdown['values'] = props_list
        self.prop_dropdown.set('')  # Clear selection

    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        selected_display_name = self.prop_var.get()
        
        if not selected_display_name:
            self.available_audio_files = []
            self.open_button.config(state='disabled')
            return
            
        # Get the identifier (prop_key or special key) from our mapping
        prop_identifier = self.prop_data_mapping.get(selected_display_name)
        if not prop_identifier:
            print(f"[audio hints]No mapping found for {selected_display_name}")
            self.available_audio_files = []
            self.open_button.config(state='disabled') # Disable if mapping fails
            return
        
        self.available_audio_files = []
        room_key = self.ROOM_MAP.get(self.current_room) # For regular props

        if prop_identifier == self.GLOBAL_OTHER_KEY:
            # Handle "OTHER" (Global Miscellaneous)
            prop_path = os.path.join(self.audio_root, "other")
            owner_name_for_list = self.GLOBAL_OTHER_DISPLAY # "OTHER"
            if os.path.exists(prop_path):
                audio_files = [f"{owner_name_for_list}:{fn}" for fn in os.listdir(prop_path) if fn.lower().endswith('.mp3')]
                self.available_audio_files.extend(audio_files)
        
        elif prop_identifier == self.ROOM_MISC_KEY:
            # Handle "ROOM MISC" (Room-specific Miscellaneous)
            if self.current_room: # Should always have a current_room if ROOM_MISC is selectable
                prop_path = os.path.join(self.audio_root, self.current_room, "other")
                owner_name_for_list = self.ROOM_MISC_DISPLAY # "ROOM MISC"
                if os.path.exists(prop_path):
                    audio_files = [f"{owner_name_for_list}:{fn}" for fn in os.listdir(prop_path) if fn.lower().endswith('.mp3')]
                    self.available_audio_files.extend(audio_files)
            else:
                print(f"[audio hints] ROOM MISC selected but no current_room. This should not happen.")
        
        else: # It's a regular prop, use original_name (which is prop_identifier here)
            original_name = prop_identifier # This is the prop_key from prop_name_mapping.json
            
            props_to_check = [original_name] # Start with the selected prop
            
            # Cousin logic (only applies to regular props from prop_name_mapping.json)
            if room_key and room_key in self.prop_name_mappings:
                prop_info = self.prop_name_mappings[room_key]['mappings'].get(original_name, {})
                cousin_value = prop_info.get('cousin')
                
                if cousin_value:
                    for prop_key_iter, info_iter in self.prop_name_mappings[room_key]['mappings'].items():
                        if info_iter.get('cousin') == cousin_value and prop_key_iter != original_name:
                            props_to_check.append(prop_key_iter)
            
            # Check for audio files for each prop (original and cousins)
            for prop_to_check_key in props_to_check:
                # Get the display name for this prop (this is the owner's display name)
                owner_display_name = self.get_display_name(room_key, prop_to_check_key)
                # Path to the prop's specific folder (using its display name)
                prop_folder_path = os.path.join(self.audio_root, self.current_room, owner_display_name) 
                
                if os.path.exists(prop_folder_path):
                    audio_files_for_owner = [f"{owner_display_name}:{audio_filename}" for audio_filename in os.listdir(prop_folder_path) 
                                  if audio_filename.lower().endswith('.mp3')]
                    self.available_audio_files.extend(audio_files_for_owner)
        
        # Sort the combined list of available audio files
        self.available_audio_files = sorted(self.available_audio_files)
        
        # Enable open button if a prop is selected (even if no audio files are found, to show "No audio files" message)
        self.open_button.config(state='normal')

    def open_audio_browser(self):
        """Open popup window with audio files browser"""
        selected_display_name = self.prop_var.get()
        if not selected_display_name:
            return # Should not happen if button is enabled only on selection
            
        # Get original prop key or special key using our mapping
        # This identifier is passed to show_audio_popup but not directly used by it anymore for title.
        prop_identifier = self.prop_data_mapping.get(selected_display_name)
        if not prop_identifier:
            print(f"[audio hints]No mapping found for {selected_display_name} during open_audio_browser.")
            return
        
        # Show popup with audio browser
        self.show_audio_popup(prop_identifier) # Pass the identifier for context if needed later
    
    def show_audio_popup(self, prop_identifier_context): # prop_identifier_context is the key from mapping
        """Show popup window with audio files browser"""
        # Get the display name directly from the dropdown for the popup's title
        dropdown_selected_display_name = self.prop_var.get()

        popup = tk.Toplevel(self.frame)
        popup.title(f"Audio Files: {dropdown_selected_display_name}") # Title uses the name selected in dropdown
        popup.transient(self.frame)
        popup.grab_set()
        popup.focus_set()

        popup_width = 600
        popup_height = 450
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width - popup_width) // 2
        y = (screen_height - popup_height) // 2
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")

        # Add protocol handler to stop audio when window is closed
        popup.protocol("WM_DELETE_WINDOW", lambda: self.stop_and_close_popup(popup))

        main_frame = ttk.Frame(popup)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)

        left_panel = ttk.Frame(main_frame, width=220)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)

        list_label = ttk.Label(left_panel, text="Available Audio Files:", font=('Arial', 10, 'bold'))
        list_label.pack(anchor='w', pady=(0, 5))

        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill='both', expand=True)

        audio_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.SINGLE,
            exportselection=False,
            height=20
        )
        audio_listbox.pack(side='left', fill='both', expand=True)

        list_scrollbar = ttk.Scrollbar(list_frame, command=audio_listbox.yview)
        list_scrollbar.pack(side='right', fill='y')
        audio_listbox.config(yscrollcommand=list_scrollbar.set)

        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side='left', fill='both', expand=True)

        if not self.available_audio_files:
            no_audio_label = ttk.Label(
                right_panel,
                text=f"No audio files available for\n'{dropdown_selected_display_name}'", # Use selected name
                font=('Arial', 12),
                foreground='gray',
                justify='center'
            )
            no_audio_label.pack(expand=True, pady=20)
            button_frame_popup = ttk.Frame(popup, height=50)
            button_frame_popup.pack(fill='x', padx=10, pady=10)
            close_button_popup = ttk.Button(button_frame_popup, text="Close", command=lambda: self.stop_and_close_popup(popup))
            close_button_popup.pack(side='right', padx=5)
            return

        for audio_file_entry in self.available_audio_files: # "OwnerDisplayName:filename.mp3"
            parts = audio_file_entry.split(':', 1)
            filename_only_for_display = parts[1] if len(parts) > 1 else parts[0]
            audio_listbox.insert(tk.END, filename_only_for_display)

        if self.available_audio_files:
            audio_listbox.selection_set(0)
            audio_listbox.see(0)

        title_frame = ttk.Frame(right_panel)
        title_frame.pack(fill='x', pady=5)
        title_label = ttk.Label(title_frame, text="Selected Audio File:", font=('Arial', 12, 'bold'))
        title_label.pack(pady=5)

        file_name_label = ttk.Label(right_panel, text="")
        file_name_label.pack(pady=10)
        
        # Add checkbox for "Count as hint"
        count_as_hint_var = tk.BooleanVar(value=True)  # Default checked
        count_as_hint_check = ttk.Checkbutton(
            right_panel, 
            text="Count as hint",
            variable=count_as_hint_var
        )
        count_as_hint_check.pack(pady=5)

        controls_frame = ttk.Frame(right_panel)
        controls_frame.pack(pady=20)

        preview_button = ttk.Button(controls_frame, text="Preview", width=10, state='disabled')
        preview_button.pack(side='left', padx=5)
        send_button = ttk.Button(controls_frame, text="Send", width=10, state='disabled')
        send_button.pack(side='left', padx=5)

        button_frame_bottom = ttk.Frame(popup, height=50)
        button_frame_bottom.pack(fill='x', padx=10, pady=10)
        button_frame_bottom.pack_propagate(False)
        close_button_bottom = ttk.Button(button_frame_bottom, text="Close", command=lambda: self.stop_and_close_popup(popup))
        close_button_bottom.pack(side='right', padx=5)

        def on_audio_select_popup(event): # Renamed from on_audio_select to avoid conflict
            # Stop any currently playing audio when a new selection is made
            self.stop_audio()
            
            selection = audio_listbox.curselection()
            if not selection:
                preview_button.config(state='disabled')
                send_button.config(state='disabled')
                file_name_label.config(text="")
                return

            selected_index = selection[0]
            full_audio_entry = ""
            if 0 <= selected_index < len(self.available_audio_files):
                 full_audio_entry = self.available_audio_files[selected_index]
            else:
                 print(f"[audio hints] Error: Selected index {selected_index} out of bounds.")
                 preview_button.config(state='disabled'); send_button.config(state='disabled')
                 file_name_label.config(text="Error"); return

            actual_owner_display_name_for_path = ""
            actual_filename_only = ""

            try:
                actual_owner_display_name_for_path, actual_filename_only = full_audio_entry.split(':', 1)
            except ValueError:
                print(f"[audio hints] Warning: Could not parse full entry '{full_audio_entry}'.")
                # Fallback: use the display name from the main dropdown as the presumed "owner" folder
                # This is only if the format "owner:file" is missing from self.available_audio_files
                actual_owner_display_name_for_path = dropdown_selected_display_name 
                actual_filename_only = full_audio_entry

            file_name_label.config(text=actual_filename_only)
            
            current_audio_file_path = ""
            if actual_owner_display_name_for_path == self.GLOBAL_OTHER_DISPLAY: # "OTHER"
                current_audio_file_path = os.path.join(
                    self.audio_root, "other", actual_filename_only
                )
            elif actual_owner_display_name_for_path == self.ROOM_MISC_DISPLAY: # "ROOM MISC"
                if not self.current_room: # Should not happen if it was selectable
                    print("[audio hints] Error: ROOM MISC audio selected but no current_room for path.")
                    preview_button.config(state='disabled'); send_button.config(state='disabled')
                    return
                current_audio_file_path = os.path.join(
                    self.audio_root, self.current_room, "other", actual_filename_only
                )
            else: # Regular prop, owner display name is the folder name under current_room
                if not self.current_room: # Should not happen if it was selectable
                    print(f"[audio hints] Error: Regular prop audio selected but no current_room for path (owner: {actual_owner_display_name_for_path}).")
                    preview_button.config(state='disabled'); send_button.config(state='disabled')
                    return
                current_audio_file_path = os.path.join(
                    self.audio_root, self.current_room, actual_owner_display_name_for_path, actual_filename_only
                )

            preview_button.config(state='normal', command=lambda: self.preview_audio_file(current_audio_file_path))
            send_button.config(state='normal', command=lambda: self.send_audio_file(popup, current_audio_file_path, count_as_hint_var.get()))

        audio_listbox.bind('<<ListboxSelect>>', on_audio_select_popup)
        if self.available_audio_files:
            on_audio_select_popup(None) 
    
    def stop_audio(self):
        """Stop any currently playing audio"""
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()
            print("[audio hints] Stopped currently playing audio")
    
    def stop_and_close_popup(self, popup):
        """Stop audio playback and close the popup window"""
        self.stop_audio()
        popup.destroy()
    
    def preview_audio_file(self, audio_file):
        """Play the selected audio file"""
        if audio_file and os.path.exists(audio_file):
            print(f"[audio_hints] loading audio file for admin preview: {audio_file}")
            try:
                # Stop any currently playing audio first
                self.stop_audio()
                pygame.mixer.music.load(audio_file)
                pygame.mixer.music.play()
            except pygame.error as e:
                print(f"[audio hints] Pygame error loading/playing audio: {e}")
        else:
            print(f"[audio hints] preview audio check failed because path exists:{os.path.exists(audio_file)} and audio_file = {audio_file}")
    
    def send_audio_file(self, popup, audio_file, count_as_hint=True):
        """Send the selected audio hint and close the popup"""
        # First stop any currently playing audio
        self.stop_audio()
        
        if audio_file and os.path.exists(audio_file):
            print(f"[audio hints]Sending audio hint: {audio_file}")
            relative_path = os.path.relpath(audio_file, start=self.audio_root)
            computer_name = self.app.interface_builder.selected_kiosk
            if computer_name:
                self.app.network_handler.send_audio_hint_command(computer_name, relative_path, count_as_hint)
                print(f"[audio hints]Sent audio hint to {computer_name}: {relative_path}, count as hint: {count_as_hint}")
            else:
                print(f"[audio hints]No kiosk selected, cannot send audio hint")
            popup.destroy()
        else:
            print(f"[audio hints]Cannot send audio hint - file does not exist: {audio_file}")

    def select_prop_by_name(self, prop_name):
        """Try to select a prop by its name (prop_key from mapping)"""
        if not self.current_room: return
        room_key = self.ROOM_MAP.get(self.current_room)
        if not room_key: return

        # This method is for selecting props defined in prop_name_mapping.json by their key.
        # It won't select "OTHER" or "ROOM MISC" via this method unless prop_name is one of the special keys.
        for display_name_iter, key_iter in self.prop_data_mapping.items():
            if key_iter.lower() == prop_name.lower(): # prop_name is expected to be a prop_key
                self.prop_dropdown.set(display_name_iter)
                self.on_prop_select(None) # Simulate event
                return
        # print(f"[audio hints]No matching prop found for key {prop_name} in select_prop_by_name")


    def refresh_audio_files(self):
        """Refresh audio files for the selected prop"""
        selected_display_name_before_refresh = self.prop_var.get()
        
        # update_room will repopulate dropdown including OTHER, ROOM MISC, and regular props
        # It also clears and resets prop_data_mapping
        if self.current_room:
            self.update_room(self.current_room) 
        else: # No room selected, effectively only "OTHER" should be listed
            self.update_room(None)
            
        if selected_display_name_before_refresh:
            props_list_after_refresh = self.prop_dropdown['values']
            if selected_display_name_before_refresh in props_list_after_refresh:
                self.prop_dropdown.set(selected_display_name_before_refresh)
                self.on_prop_select(None) # Trigger re-evaluation of audio files for the selection
            else:
                # If the previously selected item is no longer valid (e.g., room changed, prop removed)
                self.prop_var.set('') # Clear selection in dropdown variable
                self.available_audio_files = []
                self.open_button.config(state='disabled')
                print(f"[audio hints] Previously selected prop '{selected_display_name_before_refresh}' no longer found after refresh.")

    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        try:
            with open("prop_name_mapping.json", 'r') as f:
                self.prop_name_mappings = json.load(f)
        except Exception as e:
            print(f"[audio hints]Error loading prop name mappings: {e}")
            self.prop_name_mappings = {}

    def get_display_name(self, room_key, prop_name_key):
        """Get the display name for a prop (from prop_name_mapping.json) in a given room"""
        if room_key in self.prop_name_mappings:
            mappings = self.prop_name_mappings[room_key]['mappings']
            if prop_name_key in mappings:
                return mappings[prop_name_key]['display']
        # Fallback if not found in mappings (should ideally not happen for mapped props)
        return prop_name_key 

    def get_original_name(self, room_key, display_name_to_find):
        """Find original prop name (key) from display name (for props in prop_name_mapping.json)"""
        if room_key in self.prop_name_mappings:
            mappings = self.prop_name_mappings[room_key]['mappings']
            for orig_name, prop_info in mappings.items():
                if prop_info.get('display') == display_name_to_find:
                    return orig_name
        # Fallback if not found (e.g. if display_name_to_find is already an original name or special)
        return display_name_to_find

    def cleanup(self):
        """Clean up pygame mixer"""
        pygame.mixer.quit()