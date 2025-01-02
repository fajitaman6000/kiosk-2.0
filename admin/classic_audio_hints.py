import os
import pygame
import tkinter as tk
from tkinter import ttk
import json

class ClassicAudioHints:
    def __init__(self, parent, room_change_callback):
        print("\n=== INITIALIZING CLASSIC AUDIO HINTS ===")
        self.parent = parent
        self.room_change_callback = room_change_callback
        self.current_room = None
        self.current_audio_file = None
        self.audio_root = "audio_hints"
        
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
        
        print("=== CLASSIC AUDIO HINTS INITIALIZATION COMPLETE ===\n")

        self.load_prop_name_mappings()

    def update_room(self, room_name):
        """Update the prop list for the selected room"""
        print(f"\n=== UPDATING AUDIO HINTS FOR {room_name} ===")
        
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
            print(f"Error loading prop mappings: {e}")
            prop_mappings = {}

        # Get room-specific props if room is assigned
        props_list = []
        room_map = {
            "wizard": "wizard",
            "casino": "casino",
            "ma": "casino",  # Using casino props for MA room
            "haunted": "haunted",
            "zombie": "zombie",
            "atlantis": "atlantis",
            "time": "time"
        }
        
        room_key = room_map.get(room_name)
        print(f"Room name: {room_name}, Room key: {room_key}")
        
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
            
        # Extract original prop name from the combined format
        # Format is "Display Name (original_name)"
        original_name = selected_item.split('(')[-1].rstrip(')')
        
        prop_path = os.path.join(self.audio_root, self.current_room, original_name)
        
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
            
        self.current_audio_file = os.path.join(
            self.audio_root,
            self.current_room,
            selected_prop,
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
            pygame.mixer.music.load(self.current_audio_file)
            pygame.mixer.music.play()

    def send_audio(self):
        """Send the selected audio hint and return to list view"""
        if self.current_audio_file and os.path.exists(self.current_audio_file):
            print(f"Would send audio hint: {self.current_audio_file}")
            # Here you would implement the actual sending logic
            self.show_lists()

    def select_prop_by_name(self, prop_name):
        """Try to select a prop by its name"""
        print(f"\nTrying to select prop: {prop_name}")
        
        # Get current room mapping - using same mapping as update_room
        room_map = {
            "wizard": "wizard",
            "casino": "casino",
            "ma": "ma",
            "haunted": "haunted",
            "zombie": "zombie",
            "atlantis": "atlantis",
            "time": "time"
        }
        
        if not self.current_room:
            print("No current room")
            return
            
        room_key = room_map.get(self.current_room)
        print(f"Current room: {self.current_room}, Room key: {room_key}")
        
        if not room_key:
            print(f"No room key for {self.current_room}")
            return

        # Search for prop in dropdown items
        for item in self.prop_dropdown['values']:
            if f"({prop_name})" in item:  # Match by original name in parentheses
                print(f"Found matching prop: {item}")
                self.prop_dropdown.set(item)
                self.on_prop_select(None)
                return

    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        try:
            with open("prop_name_mapping.json", 'r') as f:
                self.prop_name_mappings = json.load(f)
            print("Loaded prop name mappings successfully")
        except Exception as e:
            print(f"Error loading prop name mappings: {e}")
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