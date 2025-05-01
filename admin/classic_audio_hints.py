import os
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
import tkinter as tk
from tkinter import ttk
import json

class ClassicAudioHints:
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

    def __init__(self, parent, room_change_callback, app):
        #print("[classic audio hints]=== INITIALIZING CLASSIC AUDIO HINTS ===")
        self.app = app
        self.parent = parent
        self.room_change_callback = room_change_callback
        self.current_room = None
        self.current_audio_file = None
        self.audio_root = os.path.join(os.path.dirname(__file__), "sync_directory", "hint_audio_files")
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # Create main frame with fixed width
        self.frame = tk.LabelFrame(parent, text="Audio Hints", fg='black', font=('Arial', 10, 'bold'), labelanchor='ne')
        self.frame.pack(side='left', padx=10, pady=0, anchor='sw')
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=10, pady=5)  # Remove fill='x' to prevent expansion
        
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
        
        #print("[classic audio hints]=== CLASSIC AUDIO HINTS INITIALIZATION COMPLETE ===\n")

        self.load_prop_name_mappings()

    def update_room(self, room_name):
        """Update the prop list for the selected room"""
        #print(f"[classic audio hints]=== UPDATING AUDIO HINTS FOR {room_name} ===")
        
        # Convert room_name to lowercase for consistent comparison
        room_name = room_name.lower() if room_name else None
        self.current_room = room_name
        
        self.prop_dropdown['values'] = ()
        self.available_audio_files = []
        self.open_button.config(state='disabled')

        # Load prop mappings
        try:
            with open('prop_name_mapping.json', 'r') as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[classic audio hints]Error loading prop mappings: {e}")
            prop_mappings = {}

        # Get room-specific props if room is assigned
        props_list = []
        
        room_key = self.ROOM_MAP.get(room_name)
        print(f"[classic audio hints]Room name: {room_name}, Room key: {room_key}")
        
        if room_key and room_key in prop_mappings:
            # Sort props by order like in video solutions
            props = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
            props.sort(key=lambda x: x[1]["order"])
            
            # Count audio files for each prop and add to display name
            for prop_key, prop_info in props:
                display_name = prop_info['display']
                
                # Get the path to check for audio files
                prop_path = os.path.join(self.audio_root, self.current_room, display_name)
                audio_count = 0
                
                if os.path.exists(prop_path):
                    audio_files = [f for f in os.listdir(prop_path) if f.lower().endswith('.mp3')]
                    audio_count = len(audio_files)
                
                # Add audio count to display name
                props_list.append(f"{display_name} ({audio_count} audio) ({prop_key})")

        # Update dropdown with the combined display name + original name format
        self.prop_dropdown['values'] = props_list
        self.prop_dropdown.set('')  # Clear selection

    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        selected_item = self.prop_var.get()
        
        if not selected_item:
            self.available_audio_files = []
            self.open_button.config(state='disabled')
            return
            
        # Extract ORIGINAL prop name from the combined format (now with audio count)
        original_name = selected_item.split('(')[-1].rstrip(')')
        original_name = original_name.strip()
        
        # Get the DISPLAY NAME for the selected prop 
        room_key = self.ROOM_MAP.get(self.current_room)
        display_name = self.get_display_name(room_key, original_name)
        
        prop_path = os.path.join(self.audio_root, self.current_room, display_name)
        
        # Update available audio files
        self.available_audio_files = []
        
        if os.path.exists(prop_path):
            audio_files = [f for f in os.listdir(prop_path) 
                        if f.lower().endswith('.mp3')]
            self.available_audio_files = sorted(audio_files)
        
        # Enable open button if a prop is selected, regardless of audio file availability
        self.open_button.config(state='normal')

    def open_audio_browser(self):
        """Open popup window with audio files browser"""
        selected_prop = self.prop_var.get()
        if not selected_prop:
            return
            
        # Extract original prop name from the combined format
        original_name = selected_prop.split('(')[-1].rstrip(')')
        original_name = original_name.strip()
        
        # Show popup with audio browser
        self.show_audio_popup(original_name)
    
    def show_audio_popup(self, original_name):
        """Show popup window with audio files browser"""
        # Get the display name for the selected prop
        room_key = self.ROOM_MAP.get(self.current_room)
        display_name = self.get_display_name(room_key, original_name)
        
        # Create popup window
        popup = tk.Toplevel(self.frame)
        popup.title(f"Audio Files: {display_name}")
        popup.transient(self.frame)
        popup.grab_set()
        
        # Make it modal
        popup.focus_set()
        
        # Set size and position
        popup_width = 600
        popup_height = 450
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width - popup_width) // 2
        y = (screen_height - popup_height) // 2
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # Create main content frame
        main_frame = ttk.Frame(popup)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Create left panel for audio list
        left_panel = ttk.Frame(main_frame, width=180)
        left_panel.pack(side='left', fill='y', padx=(0, 10))
        left_panel.pack_propagate(False)  # Keep fixed width
        
        # Add list label
        list_label = ttk.Label(left_panel, text="Available Audio Files:", font=('Arial', 10, 'bold'))
        list_label.pack(anchor='w', pady=(0, 5))
        
        # Create audio listbox with scrollbar
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
        
        # Create right panel for audio details and controls
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side='left', fill='both', expand=True)
        
        # Check if there are any audio files available
        if not self.available_audio_files:
            # Display message when no audio files are available
            no_audio_label = ttk.Label(
                right_panel, 
                text="No audio files available for this prop",
                font=('Arial', 12),
                foreground='gray'
            )
            no_audio_label.pack(expand=True, pady=20)
            
            # Add close button at the bottom
            button_frame = ttk.Frame(popup, height=50)
            button_frame.pack(fill='x', padx=10, pady=10)
            
            close_button = ttk.Button(
                button_frame,
                text="Close",
                command=popup.destroy
            )
            close_button.pack(side='right', padx=5)
            
            return
        
        # Fill listbox with available audio files
        for audio_file in self.available_audio_files:
            audio_listbox.insert(tk.END, audio_file)
        
        # Select the first audio file
        if self.available_audio_files:
            audio_listbox.selection_set(0)
            audio_listbox.see(0)
        
        # Add title label
        title_frame = ttk.Frame(right_panel)
        title_frame.pack(fill='x', pady=5)
        
        title_label = ttk.Label(title_frame, text="Selected Audio File:", font=('Arial', 12, 'bold'))
        title_label.pack(pady=5)
        
        # Add selected file name label
        file_name_label = ttk.Label(right_panel, text="")
        file_name_label.pack(pady=10)
        
        # Add audio controls frame
        controls_frame = ttk.Frame(right_panel)
        controls_frame.pack(pady=20)
        
        # Preview button
        preview_button = ttk.Button(
            controls_frame,
            text="Preview",
            width=10,
            state='disabled'
        )
        preview_button.pack(side='left', padx=5)
        
        # Send button
        send_button = ttk.Button(
            controls_frame,
            text="Send",
            width=10,
            state='disabled'
        )
        send_button.pack(side='left', padx=5)
        
        # Add navigation and close buttons at the bottom
        button_frame = ttk.Frame(popup, height=50)
        button_frame.pack(fill='x', padx=10, pady=10)
        button_frame.pack_propagate(False)  # Prevent the frame from shrinking
        
        # Close button
        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=popup.destroy
        )
        close_button.pack(side='right', padx=5)
        
        # Create function to handle audio selection
        def on_audio_select(event):
            selection = audio_listbox.curselection()
            if not selection:
                preview_button.config(state='disabled')
                send_button.config(state='disabled')
                file_name_label.config(text="")
                return
                
            audio_name = audio_listbox.get(selection[0])
            file_name_label.config(text=audio_name)
            
            # Set current audio file path
            current_audio_file = os.path.join(
                self.audio_root,
                self.current_room,
                display_name,
                audio_name
            )
            
            # Enable buttons
            preview_button.config(
                state='normal',
                command=lambda: self.preview_audio_file(current_audio_file)
            )
            
            send_button.config(
                state='normal',
                command=lambda: self.send_audio_file(popup, current_audio_file)
            )
        
        # Bind audio selection event
        audio_listbox.bind('<<ListboxSelect>>', on_audio_select)
        
        # Trigger initial selection
        if self.available_audio_files:
            on_audio_select(None)
    
    def preview_audio_file(self, audio_file):
        """Play the selected audio file"""
        if audio_file and os.path.exists(audio_file):
            print(f"[audio_hints] loading audio file for admin preview: {audio_file}")
            pygame.mixer.music.load(audio_file)
            pygame.mixer.music.play()
        else:
            print(f"[audio hints] preview audio check failed because path exists:{os.path.exists(audio_file)} and audio_file = {audio_file}")
    
    def send_audio_file(self, popup, audio_file):
        """Send the selected audio hint and close the popup"""
        if audio_file and os.path.exists(audio_file):
            print(f"[classic audio hints]Sending audio hint: {audio_file}")

            # Construct relative audio path
            relative_path = os.path.relpath(audio_file, start=self.audio_root)

            # Send audio hint using the app's network handler
            computer_name = self.app.interface_builder.selected_kiosk
            if computer_name: # check to make sure there is even a selected computer
                self.app.network_handler.send_audio_hint_command(computer_name, relative_path)

            # Close the popup
            popup.destroy()

    def select_prop_by_name(self, prop_name):
        """Try to select a prop by its name"""
        print(f"[classic audio hints]Trying to select prop: {prop_name}")
        
        if not self.current_room:
            print("[classic audio hints]No current room")
            return
            
        room_key = self.ROOM_MAP.get(self.current_room)
        #print(f"[classic audio hints]Current room: {self.current_room}, Room key: {room_key}")
        
        if not room_key:
            print(f"[classic audio hints]No room key for {self.current_room}")
            return

        # Search for prop in dropdown items
        for item in self.prop_dropdown['values']:
            if f"({prop_name})" in item:  # Match by original name in parentheses
                #print(f"[classic audio hints]Found matching prop: {item}")
                self.prop_dropdown.set(item)
                self.on_prop_select(None)
                return

    def refresh_audio_files(self):
        """Refresh audio files for the selected prop"""
        # Remember currently selected prop
        selected_prop = self.prop_var.get()
        
        # Refresh prop list for current room
        if self.current_room:
            self.update_room(self.current_room)
            
            # Re-select the previously selected prop if it still exists
            if selected_prop:
                props_list = self.prop_dropdown['values']
                if selected_prop in props_list:
                    self.prop_dropdown.set(selected_prop)
                    self.on_prop_select(None) # Trigger audio files update
                else:
                    # Prop no longer exists, clear selection
                    self.prop_var.set('')
                    self.available_audio_files = []
                    self.open_button.config(state='disabled')
                    print(f"[classic audio hints] Previously selected prop '{selected_prop}' no longer found after refresh.")

    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        try:
            with open("prop_name_mapping.json", 'r') as f:
                self.prop_name_mappings = json.load(f)
            #print("[classic audio hints]Loaded prop name mappings successfully")
        except Exception as e:
            print(f"[classic audio hints]Error loading prop name mappings: {e}")
            self.prop_name_mappings = {}

    def get_display_name(self, room_key, prop_name):
        """Get the display name for a prop in a given room"""
        if room_key in self.prop_name_mappings:
            mappings = self.prop_name_mappings[room_key]['mappings']
            if prop_name in mappings:
                return mappings[prop_name]['display']
        return prop_name

    def get_original_name(self, room_key, display_name):
        """Find original prop name from display name"""
        if room_key in self.prop_name_mappings:
            mappings = self.prop_name_mappings[room_key]['mappings']
            for orig_name, prop_info in mappings.items():
                if prop_info.get('display') == display_name:
                    return orig_name
        return display_name

    def cleanup(self):
        """Clean up pygame mixer"""
        pygame.mixer.quit()