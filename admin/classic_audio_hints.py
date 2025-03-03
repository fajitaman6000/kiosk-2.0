import os
import pygame
import tkinter as tk
from tkinter import ttk
import json

class ClassicAudioHints:
    # Room mapping dictionary to convert room names to their canonical forms
    ROOM_MAP = {
        "wizard": "wizard",
        "casino": "casino",
        "ma": "casino",  # Using casino props for MA room
        "haunted": "haunted",
        "zombie": "zombie",
        "atlantis": "atlantis",
        "time": "time"
    }

    def __init__(self, parent, room_change_callback, app):
        #print("[classic audio hints]\n=== INITIALIZING CLASSIC AUDIO HINTS ===")
        self.app = app
        self.parent = parent
        self.room_change_callback = room_change_callback
        self.current_room = None
        self.current_audio_file = None
        self.audio_root = os.path.join(os.path.dirname(__file__), "sync_directory", "hint_audio_files")
        
        # Initialize pygame mixer for audio playback
        pygame.mixer.init()
        
        # Create main frame with fixed width
        self.frame = ttk.LabelFrame(parent, text="Audio Hints")
        self.frame.pack(side='left', padx=5, pady=5)
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=5, pady=5)  # Remove fill='x' to prevent expansion
        
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
        
        # Create audio file section with fixed width
        self.audio_frame = ttk.Frame(self.list_container)
        self.audio_frame.pack(pady=5)  # Remove fill='x' to prevent expansion
        audio_label = ttk.Label(self.audio_frame, text="Audio Files:", font=('Arial', 10, 'bold'))
        audio_label.pack(anchor='w')
        
        # Fixed-width listbox container
        listbox_container = ttk.Frame(self.audio_frame)
        listbox_container.pack()  # No expansion
        
        self.audio_listbox = tk.Listbox(
            listbox_container, 
            height=6,
            width=40,
            selectmode=tk.SINGLE,
            exportselection=False,
            bg='white',
            fg='black'
        )
        self.audio_listbox.pack()  # No expansion
        self.audio_listbox.bind('<<ListboxSelect>>', self.on_audio_select)
        
        # Create control buttons frame (initially hidden)
        self.control_frame = ttk.Frame(self.list_container)
        
        # Add selected file label
        self.selected_file_label = ttk.Label(self.control_frame, font=('Arial', 10))
        self.selected_file_label.pack(side='left', padx=5)
        
        self.preview_btn = ttk.Button(self.control_frame, text="Preview", command=self.preview_audio)
        self.preview_btn.pack(side='left', padx=5)
        self.send_btn = ttk.Button(self.control_frame, text="Send", command=self.send_audio)
        self.send_btn.pack(side='left', padx=5)
        self.back_btn = ttk.Button(self.control_frame, text="Back", command=self.show_lists)
        self.back_btn.pack(side='left', padx=5)
        
        #print("[classic audio hints]=== CLASSIC AUDIO HINTS INITIALIZATION COMPLETE ===\n")

        self.load_prop_name_mappings()

    def update_room(self, room_name):
        """Update the prop list for the selected room"""
        #print(f"[classic audio hints]\n=== UPDATING AUDIO HINTS FOR {room_name} ===")
        
        # Convert room_name to lowercase for consistent comparison
        room_name = room_name.lower() if room_name else None
        self.current_room = room_name
        
        self.show_lists()
        self.prop_dropdown['values'] = ()
        self.audio_listbox.delete(0, tk.END)

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
            props_list = [f"{p[1]['display']} ({p[0]})" for p in props]

        # Update dropdown with the combined display name + original name format
        self.prop_dropdown['values'] = props_list

    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        self.audio_listbox.delete(0, tk.END)
        selected_item = self.prop_var.get()
        
        if not selected_item:
            return
            
        # Extract ORIGINAL prop name from the combined format
        original_name = selected_item.split('(')[-1].rstrip(')')
        
        # Get the DISPLAY NAME for the selected prop 
        room_key = self.ROOM_MAP.get(self.current_room)
        display_name = self.get_display_name(room_key, original_name)

        
        prop_path = os.path.join(self.audio_root, self.current_room, display_name)
        
        if os.path.exists(prop_path):
            audio_files = [f for f in os.listdir(prop_path) 
                        if f.lower().endswith('.mp3')]
            for audio in sorted(audio_files):
                self.audio_listbox.insert(tk.END, audio)

    def on_audio_select(self, event):
        """Handle audio file selection"""
        selection = self.audio_listbox.curselection()
        if not selection:
            return
            
        audio_name = self.audio_listbox.get(selection[0])
        selected_prop = self.prop_var.get()
        
        if not selected_prop:
            return
            
        # Extract original prop name from the combined format
        original_name = selected_prop.split('(')[-1].rstrip(')')
        
        # Get the DISPLAY NAME for the selected prop 
        room_key = self.ROOM_MAP.get(self.current_room)
        display_name = self.get_display_name(room_key, original_name)
            
        self.current_audio_file = os.path.join(
            self.audio_root,
            self.current_room,
            display_name,  # Use the DISPLAY NAME here
            audio_name
        )
        
        # Update selected file label
        self.selected_file_label.config(text=f"Selected: {audio_name}")
        
        # Show control buttons
        self.show_controls()

    def show_controls(self):
        """Show control buttons and hide lists"""
        self.prop_frame.pack_forget()
        self.audio_frame.pack_forget()
        self.control_frame.pack(pady=5)

    def show_lists(self):
        """Show dropdown and audio list, hide control buttons"""
        #print("[audio hints] showing audio list")
        self.control_frame.pack_forget()
        self.prop_frame.pack(pady=(0, 5))
        self.audio_frame.pack(pady=5)
        
        # Clear selected file label
        self.selected_file_label.config(text="")
        
        # Stop any playing audio
        pygame.mixer.music.stop()

    def preview_audio(self):
        """Play the selected audio file"""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            print(f"[audio_hints] loading audio file for admin preview: {self.current_audio_file}")
            pygame.mixer.music.load(self.current_audio_file)
            pygame.mixer.music.play()
        else:
            print(f"[audio hints] preview audio check failed because path exists:{os.path.exists(self.current_audio_file)} and self.current_audio_file = {self.current_audio_file}")

    def send_audio(self):
        """Send the selected audio hint and return to list view"""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            print(f"[classic audio hints]Sending audio hint: {self.current_audio_file}")
            
            # Construct relative audio path
            relative_path = os.path.relpath(self.current_audio_file, start=self.audio_root)
            
            # Construct audio_hint message
            message = {
                'type': 'audio_hint',
                'computer_name': self.app.interface_builder.selected_kiosk,
                'audio_path': relative_path  # Relative path from the hint_audio_files folder
            }
            
            # Send audio hint using the app's network handler
            self.app.network_handler.socket.sendto(
               json.dumps(message).encode(),
               ('255.255.255.255', 12346)
            )
            self.show_lists()

    def select_prop_by_name(self, prop_name):
        """Try to select a prop by its name"""
        print(f"[classic audio hints]\nTrying to select prop: {prop_name}")
        
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