# saved_hints_panel.py
import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import os
from PIL import Image, ImageTk
import base64
import io

class SavedHintsPanel:
    def __init__(self, parent, send_hint_callback):
        """
        Initialize the Saved Hints panel.
        
        Args:
            parent: Parent frame to attach to
            send_hint_callback: Callback function for sending hints, expects dict with 'text' and optional 'image'
        """
        self.frame = ttk.LabelFrame(parent, text="Saved Hints")
        self.frame.pack(side='left', padx=5, pady=5)
        
        # Store callback
        self.send_hint_callback = send_hint_callback
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=5, pady=5)
        
        # Create prop dropdown section
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
        
        # Create hint selection section
        self.hint_frame = ttk.Frame(self.list_container)
        self.hint_frame.pack(pady=5)
        hint_label = ttk.Label(self.hint_frame, text="Available Hints:", font=('Arial', 10, 'bold'))
        hint_label.pack(anchor='w')
        
        # Create list view
        self.hint_listbox = tk.Listbox(
            self.hint_frame,
            height=6,
            width=40,
            selectmode=tk.SINGLE,
            exportselection=False,
            bg='white',
            fg='black'
        )
        self.hint_listbox.pack(pady=5)
        self.hint_listbox.bind('<<ListboxSelect>>', self.on_hint_select)

        # Create detail view (initially hidden)
        self.detail_view = ttk.Frame(self.list_container)
        
        # Preview text in detail view
        self.preview_text = tk.Text(
            self.detail_view,
            height=4,
            width=38,
            wrap=tk.WORD,
            state='disabled'
        )
        self.preview_text.pack(pady=(5, 10), padx=5)
        
        # Image preview in detail view
        self.image_label = ttk.Label(self.detail_view)
        self.image_label.pack(pady=(0, 10))
        
        # Control buttons in detail view
        button_frame = ttk.Frame(self.detail_view)
        button_frame.pack(fill='x', pady=(0, 5), padx=5)
        
        self.back_button = ttk.Button(
            button_frame,
            text="Back",
            command=self.show_list_view
        )
        self.back_button.pack(side='left', padx=5)
        
        self.send_button = ttk.Button(
            button_frame,
            text="Send Hint",
            command=self.send_hint
        )
        self.send_button.pack(side='right', padx=5)
        
        # Load hints
        self.hints_data = {}
        self.current_room = None
        self.load_hints()
        self.load_prop_name_mappings()

        # Show list view initially
        self.show_list_view()
    
    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        try:
            mapping_file = Path("prop_name_mapping.json")
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    self.prop_name_mappings = json.load(f)
                #print("Loaded prop name mappings successfully")
            else:
                self.prop_name_mappings = {}
                print("No prop name mapping file found")
        except Exception as e:
            print(f"Error loading prop name mappings: {e}")
            self.prop_name_mappings = {}

    def get_display_name(self, prop_name):
        """Get the display name for a prop from the mapping file"""
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
        
        # Map room numbers to config sections
        room_map = {
            3: "wizard",
            1: "casino_ma",
            2: "casino_ma",
            5: "haunted",
            4: "zombie",
            6: "atlantis",
            7: "time"
        }
        
        if self.current_room not in room_map:
            return prop_name
        
        room_key = room_map[self.current_room]
        room_mappings = self.prop_name_mappings.get(room_key, {}).get('mappings', {})
        
        # Get the mapping info for this prop
        prop_info = room_mappings.get(prop_name, {})
        
        # Return mapped display name if it exists and isn't empty, otherwise return original
        mapped_name = prop_info.get('display', '')
        return mapped_name if mapped_name else prop_name

    def load_hints(self):
        """Load all hints from the JSON file"""
        try:
            #print("\n=== LOADING SAVED HINTS ===")
            hints_path = os.path.join(os.getcwd(), 'saved_hints.json')
            ##print(f"Looking for hints file at: {hints_path}")
            #print(f"File exists: {os.path.exists(hints_path)}")
            
            if os.path.exists(hints_path):
                with open(hints_path, 'r') as f:
                    data = json.load(f)
                    self.hints_data = data.get('rooms', {})
                    print(f"Loaded hints for {len(self.hints_data)} rooms")
            else:
                print("No hints file found!")
                self.hints_data = {}
        except Exception as e:
            print(f"Error loading hints: {str(e)}")
            import traceback
            traceback.print_exc()
            self.hints_data = {}
            
    def show_list_view(self):
        """Switch to list view"""
        self.detail_view.pack_forget()
        self.prop_frame.pack(pady=(0, 5))
        self.hint_frame.pack(pady=5)
        
    def show_detail_view(self):
        """Switch to detail view"""
        self.prop_frame.pack_forget()
        self.hint_frame.pack_forget()
        self.detail_view.pack(fill='both', expand=True, padx=5, pady=5)

    def get_props_for_room(self, room_number):
        """Get available props for the current room from hints data"""
        props = {}  # Using dict to maintain mapping of display name to original name
        room_str = str(room_number)  # Convert room number to string for dict key
        
        if room_str in self.hints_data:
            room_hints = self.hints_data[room_str].get('hints', {})
            for hint in room_hints.values():
                original_name = hint['prop']
                display_name = self.get_display_name(original_name)
                # Format as "[Display Name] ([Original Name])"
                formatted_name = f"{display_name} ({original_name})"
                props[formatted_name] = original_name
        
        # Sort by formatted names but maintain mapping
        sorted_display_names = sorted(props.keys())
        self.prop_name_map = props  # Store mapping for later use
        return sorted_display_names

    def get_hints_for_prop(self, prop_name):
        """Get hints for the selected prop"""
        hints = []
        room_str = str(self.current_room)
        
        if room_str in self.hints_data:
            room_hints = self.hints_data[room_str].get('hints', {})
            for hint in room_hints.values():
                if hint['prop'] == prop_name:
                    hints.append(hint['name'])
        return sorted(hints)

    def update_room(self, room_number):
        """Update the prop dropdown for the selected room"""
        print(f"\n=== UPDATING SAVED HINTS FOR ROOM {room_number} ===")
        
        self.current_room = room_number
        self.clear_preview()
        
        # Update prop dropdown
        available_props = self.get_props_for_room(room_number)
        self.prop_dropdown['values'] = available_props
        self.prop_dropdown.set('')  # Clear selection
        
        # Clear hint listbox
        self.hint_listbox.delete(0, tk.END)
        
    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        selected_display_name = self.prop_var.get()
        self.hint_listbox.delete(0, tk.END)
        
        if selected_display_name and hasattr(self, 'prop_name_map'):
            original_name = self.prop_name_map[selected_display_name]
            hints = self.get_hints_for_prop(original_name)
            for hint in hints:
                self.hint_listbox.insert(tk.END, hint)

    def select_prop_by_name(self, prop_name):
        """Try to select a prop by its original name"""
        if not hasattr(self, 'prop_name_map'):
            return
            
        # Find the display name that contains this prop name in parentheses
        for formatted_name in self.prop_dropdown['values']:
            if f"({prop_name})" in formatted_name:
                # Set the dropdown value
                self.prop_dropdown.set(formatted_name)
                self.on_prop_select(None)  # Trigger hint list update
                break

    def on_hint_select(self, event):
        """Handle hint selection from listbox"""
        selection = self.hint_listbox.curselection()
        if not selection:
            return
            
        hint_name = self.hint_listbox.get(selection[0])
        selected_display_name = self.prop_var.get()
        
        # Get original prop name from the mapping
        if not hasattr(self, 'prop_name_map') or not selected_display_name in self.prop_name_map:
            return
            
        original_prop_name = self.prop_name_map[selected_display_name]
        room_str = str(self.current_room)
        
        # Find hint data by name and prop
        selected_hint = None
        if room_str in self.hints_data:
            room_hints = self.hints_data[room_str].get('hints', {})
            for hint_data in room_hints.values():
                if (hint_data['name'] == hint_name and 
                    hint_data['prop'] == original_prop_name):
                    selected_hint = hint_data
                    break
                
        if selected_hint:
            # Update preview text
            self.preview_text.config(state='normal')
            self.preview_text.delete('1.0', tk.END)
            self.preview_text.insert('1.0', selected_hint['text'])
            self.preview_text.config(state='disabled')
            
            # Update image preview
            if selected_hint.get('image'):
                try:
                    image_path = os.path.join('saved_hint_images', selected_hint['image'])
                    if os.path.exists(image_path):
                        image = Image.open(image_path)
                        image.thumbnail((200, 200))
                        photo = ImageTk.PhotoImage(image)
                        self.image_label.configure(image=photo, text='')
                        self.image_label.image = photo
                    else:
                        self.image_label.configure(text="Image file not found", image='')
                except Exception as e:
                    print(f"Error loading hint image: {e}")
                    self.image_label.configure(text="Error loading image", image='')
            else:
                self.image_label.configure(text="No image for this hint", image='')
            
            # Switch to detail view
            self.show_detail_view()
    
    def clear_preview(self):
        """Clear the preview area and return to list view"""
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.config(state='disabled')
        self.image_label.configure(text="", image='')
        self.show_list_view()
    
    def send_hint(self):
        """Send the currently selected hint"""
        selection = self.hint_listbox.curselection()
        if not selection or not hasattr(self, 'prop_name_map'):
            return
        
        hint_name = self.hint_listbox.get(selection[0])
        selected_display_name = self.prop_var.get()
        original_prop_name = self.prop_name_map[selected_display_name]
        room_str = str(self.current_room)
        
        # Find hint data by name and prop
        selected_hint = None
        if room_str in self.hints_data:
            room_hints = self.hints_data[room_str].get('hints', {})
            for hint_data in room_hints.values():
                try:
                    if (hint_data.get('name') == hint_name and 
                        hint_data.get('prop') == original_prop_name):
                        selected_hint = hint_data
                        break
                except (KeyError, AttributeError) as e:
                    print(f"Error accessing hint data: {e}")
                    continue
                
        if selected_hint:
            # Prepare hint data
            hint_data = {'text': selected_hint.get('text', '')}
            
            # Add image if present
            if selected_hint.get('image'):
                try:
                    image_path = os.path.join('saved_hint_images', selected_hint['image'])
                    if os.path.exists(image_path):
                        with open(image_path, 'rb') as img_file:
                            img_data = img_file.read()
                            hint_data['image'] = base64.b64encode(img_data).decode()
                except Exception as e:
                    print(f"Error loading hint image for sending: {e}")
            
            # Send hint through callback
            self.send_hint_callback(hint_data)
            
            # Return to list view
            self.clear_preview()