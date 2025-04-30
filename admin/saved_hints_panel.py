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
        self.frame = tk.LabelFrame(parent, text="Saved Hints", fg='black', font=('Arial', 9, 'bold'), labelanchor='s')
        self.frame.pack(side='right', padx=0, pady=5)
        
        # Store callback
        self.send_hint_callback = send_hint_callback
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=5, pady=5)

        # Create prop dropdown section with refresh and open buttons
        self.prop_control_frame = ttk.Frame(self.list_container)
        self.prop_control_frame.pack(pady=(0, 5), fill='x')
        
        # Row 1: Prop dropdown with label
        self.prop_frame = ttk.Frame(self.prop_control_frame)
        self.prop_frame.pack(fill='x', pady=(0, 5))
        
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
        
        # Row 2: Buttons row
        button_frame = ttk.Frame(self.prop_control_frame)
        button_frame.pack(fill='x')
        
        # Refresh Button
        self.refresh_button = ttk.Button(
            button_frame,
            text="⟳",
            command=self.refresh_hints,
            width=2
        )
        self.refresh_button.pack(side='left', padx=(0, 5))
        
        # Open Button
        self.open_button = ttk.Button(
            button_frame,
            text="Open",
            command=self.open_hints_browser
        )
        self.open_button.pack(side='left', fill='x', expand=True)
        
        # Load hints
        self.hints_data = {}
        self.current_room = None
        self.load_hints()
        self.load_prop_name_mappings()
        
        # Track available hints for the selected prop
        self.available_hints = []

        # Register for prop selection notifications if parent has prop_control
        if hasattr(parent, 'app') and hasattr(parent.app, 'prop_control'):
            parent.app.prop_control.add_prop_select_callback(self.select_prop_by_name)
    
    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        try:
            mapping_file = Path("prop_name_mapping.json")
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    self.prop_name_mappings = json.load(f)
                #print("[saved hints panel]Loaded prop name mappings successfully")
            else:
                self.prop_name_mappings = {}
                print("[saved hints panel]No prop name mapping file found")
        except Exception as e:
            print(f"[saved hints panel]Error loading prop name mappings: {e}")
            self.prop_name_mappings = {}

    def get_display_name(self, prop_name):
        """Get the display name for a prop from the mapping file"""
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
        
        # Map room numbers to config sections
        room_map = {
            3: "wizard",
            1: "casino",
            2: "ma",
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
            #print("[saved hints panel]=== LOADING SAVED HINTS ===")
            hints_path = os.path.join(os.getcwd(), 'saved_hints.json')
            ##print(f"[saved hints panel]Looking for hints file at: {hints_path}")
            #print(f"[saved hints panel]File exists: {os.path.exists(hints_path)}")
            
            if os.path.exists(hints_path):
                with open(hints_path, 'r') as f:
                    data = json.load(f)
                    self.hints_data = data.get('rooms', {})
                    print(f"[saved hints panel]Loaded hints for {len(self.hints_data)} rooms")
            else:
                print("[saved hints panel]No hints file found!")
                self.hints_data = {}
        except Exception as e:
            print(f"[saved hints panel]Error loading hints: {str(e)}")
            import traceback
            traceback.print_exc()
            self.hints_data = {}

    def get_props_for_room(self, room_number):
        """Get available props for the current room from hints data"""
        # Load prop mappings
        try:
            with open('prop_name_mapping.json', 'r') as f:
                prop_mappings = json.load(f)
        except Exception as e:
            print(f"[saved hints panel]Error loading prop mappings: {e}")
            prop_mappings = {}
            
        # Get room-specific props if room is assigned
        props_list = []
        room_map = {
            3: "wizard",
            1: "casino",
            2: "ma",
            5: "haunted",
            4: "zombie",
            6: "atlantis",
            7: "time"
        }
        
        room_str = str(room_number)
        
        if room_number in room_map:
            room_key = room_map[room_number]
            if room_key in prop_mappings:
                # Sort props by order
                props = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
                props.sort(key=lambda x: x[1]["order"])
                
                # Get hint count for each prop
                for prop_key, prop_info in props:
                    display_name = prop_info['display']
                    hint_count = 0
                    
                    # Count hints for this prop
                    if room_str in self.hints_data:
                        for saved_prop_key in self.hints_data[room_str]:
                            if (saved_prop_key.lower() == prop_key.lower() or 
                                saved_prop_key.lower() == display_name.lower()):
                                hint_count = len(self.hints_data[room_str][saved_prop_key])
                                break
                    
                    # Add hint count to display name
                    props_list.append(f"{display_name} ({hint_count} hints) ({prop_key})")
        
        # Sort by display names
        sorted_display_names = sorted(props_list)
        return sorted_display_names

    def get_hints_for_prop(self, prop_display_name):
        """Get hints for the selected prop"""
        hints = []
        room_str = str(self.current_room)
        
        #print(f"[saved hints panel]Getting hints for room {room_str} and prop {prop_display_name}")
        #print(f"[saved hints panel]Available hints data: {self.hints_data}")
        
        # Extract original prop name from the combined format
        original_name = prop_display_name.split('(')[-1].rstrip(')')
        original_name = original_name.strip()  # Remove any whitespace
        #print(f"[saved hints panel]Extracted original name: '{original_name}'")
        
        # Get the display name mapping for this prop
        room_map = {
            3: "wizard",
            1: "casino",
            2: "ma",
            5: "haunted",
            4: "zombie",
            6: "atlantis",
            7: "time"
        }
        
        # Build a mapping of original names to display names
        name_mapping = {}
        if self.current_room in room_map:
            room_key = room_map[self.current_room]
            if room_key in self.prop_name_mappings:
                for orig_name, prop_info in self.prop_name_mappings[room_key]['mappings'].items():
                    display_name = prop_info.get('display', orig_name)
                    name_mapping[orig_name.lower()] = display_name
                    name_mapping[display_name.lower()] = display_name
        
        if room_str in self.hints_data:
            #print(f"[saved hints panel]Props in room {room_str}: {list(self.hints_data[room_str].keys())}")
            # Try to find hints using either the original name or its display name
            for prop_key in self.hints_data[room_str]:
                # Check if this prop matches either the original name or its mapped display name
                if (prop_key.lower() == original_name.lower() or 
                    (original_name.lower() in name_mapping and 
                     prop_key.lower() == name_mapping[original_name.lower()].lower())):
                    print(f"[saved hints panel]Found hints for prop: {list(self.hints_data[room_str][prop_key].keys())}")
                    hints = list(self.hints_data[room_str][prop_key].keys())
                    break
            else:
                print(f"[saved hints panel]No hints found for prop '{original_name}'")
        else:
            print(f"[saved hints panel]No hints found for room {room_str}")
            
        return sorted(hints)

    def get_image_path(self, room_number, prop_name, image_filename):
        """Construct the full path to a hint image based on room and prop"""
        if not image_filename:
            return None
            
        # Map room numbers to their folder names
        room_map = {
            1: "casino",
            2: "ma",
            3: "wizard",
            4: "zombie",
            5: "haunted",
            6: "atlantis",
            7: "time"
        }
        
        room_folder = room_map.get(room_number, "").lower()
        if not room_folder:
            return None

        # Get mappings from props to display names
        original_prop_name = None
        display_name = None
        
        if room_number in room_map:
            room_key = room_map[room_number]
            if room_key in self.prop_name_mappings:
                # Find the matching prop
                for orig_name, prop_info in self.prop_name_mappings[room_key]['mappings'].items():
                    prop_display = prop_info.get('display', orig_name)
                    # Check if this matches the prop name passed in (ignoring case)
                    if (prop_display.lower() == prop_name.lower() or 
                        orig_name.lower() == prop_name.lower()):
                        original_prop_name = orig_name
                        display_name = prop_display
                        print(f"[saved hints panel] Found mapping: '{orig_name}' => '{prop_display}'")
                        break
        
        # If we didn't find it in mappings, just use what was passed in
        if not original_prop_name:
            original_prop_name = prop_name
            display_name = prop_name
            print(f"[saved hints panel] No mapping found, using: '{prop_name}'")
            
        # Try multiple path combinations
        possible_paths = [
            # 1. Original folder as in mapping file
            os.path.join(os.path.dirname(__file__), "sync_directory", "hint_image_files", 
                         room_folder, original_prop_name, image_filename),
            
            # 2. Display name as folder
            os.path.join(os.path.dirname(__file__), "sync_directory", "hint_image_files", 
                         room_folder, display_name, image_filename),
            
            # 3. Exact prop name as passed in
            os.path.join(os.path.dirname(__file__), "sync_directory", "hint_image_files", 
                         room_folder, prop_name, image_filename)
        ]
        
        # Try each path
        for path in possible_paths:
            print(f"[saved hints panel] Checking if image exists at: {path}")
            if os.path.exists(path):
                print(f"[saved hints panel] Found image at: {path}")
                return path
                
        # If we get here, no image was found
        print(f"[saved hints panel] No image found in any possible locations for {image_filename}")
        return None

    def update_room(self, room_number):
        """Update the prop dropdown for the selected room"""
        #print(f"[saved hints panel]=== UPDATING SAVED HINTS FOR ROOM {room_number} ===")
        
        self.current_room = room_number
        
        # Update prop dropdown
        available_props = self.get_props_for_room(room_number)
        self.prop_dropdown['values'] = available_props
        self.prop_dropdown.set('')  # Clear selection
        
        # Reset available hints
        self.available_hints = []
        
        # Disable the open button until a prop is selected
        self.open_button.config(state='disabled')

    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        selected_display_name = self.prop_var.get()
        #print(f"[saved hints panel]Selected prop from dropdown: {selected_display_name}")
        
        if selected_display_name:
            # Extract original prop name from the combined format (now includes hint count)
            original_name = selected_display_name.split('(')[-1].rstrip(')')
            
            # Get available hints for this prop
            self.available_hints = self.get_hints_for_prop(original_name)
            #print(f"[saved hints panel]Found hints: {self.available_hints}")
            
            # Enable the open button if a prop is selected, regardless of hints availability
            self.open_button.config(state='normal')
        else:
            self.available_hints = []
            self.open_button.config(state='disabled')

    def select_prop_by_name(self, prop_name):
        """Try to select a prop by its original name"""
        if not self.current_room:
            print("[saved hints panel]No current room selected")
            return
            
        #print(f"[saved hints panel]Trying to select prop: {prop_name}")
        #print(f"[saved hints panel]Available dropdown values: {self.prop_dropdown['values']}")
            
        # Find the display name that matches this prop name in parentheses
        for formatted_name in self.prop_dropdown['values']:
            if f"({prop_name})" in formatted_name:
                #print(f"[saved hints panel]Found matching prop in dropdown: {formatted_name}")
                # Set the dropdown value
                self.prop_dropdown.set(formatted_name)
                self.on_prop_select(None)  # Trigger hint list update
                break
        else:
            print(f"[saved hints panel]No matching prop found for {prop_name}")

    def open_hints_browser(self):
        """Open a browser window with all hints for the selected prop"""
        prop_display_name = self.prop_var.get()
        if not prop_display_name:
            return
            
        # Extract original prop name from the combined format
        original_name = prop_display_name.split('(')[-1].rstrip(')')
        original_name = original_name.strip()
        
        # Show popup with first hint or empty state
        if self.available_hints:
            first_hint = self.available_hints[0]
            hint_data, prop_key = self.get_hint_data(first_hint, original_name)
            if hint_data:
                self.show_hint_popup(first_hint, original_name, prop_key, hint_data, 0)
        else:
            # No hints available, show empty state popup
            self.show_hint_popup(None, original_name, None, None, None)

    def get_hint_data(self, hint_name, original_name):
        """Get hint data for a specific hint and prop"""
        room_str = str(self.current_room)
        
        # Build name mapping
        room_map = {
            3: "wizard",
            1: "casino",
            2: "ma",
            5: "haunted",
            4: "zombie",
            6: "atlantis",
            7: "time"
        }
        
        name_mapping = {}
        if self.current_room in room_map:
            room_key = room_map[self.current_room]
            if room_key in self.prop_name_mappings:
                for orig_name, prop_info in self.prop_name_mappings[room_key]['mappings'].items():
                    display_name = prop_info.get('display', orig_name)
                    name_mapping[orig_name.lower()] = display_name
                    name_mapping[display_name.lower()] = display_name
        
        # Get hint data directly from the structure with name mapping lookup
        hint_data = None
        matched_prop_key = None
        
        if room_str in self.hints_data:
            for prop_key in self.hints_data[room_str]:
                if (prop_key.lower() == original_name.lower() or 
                    (original_name.lower() in name_mapping and 
                     prop_key.lower() == name_mapping[original_name.lower()].lower())):
                    if hint_name in self.hints_data[room_str][prop_key]:
                        hint_data = self.hints_data[room_str][prop_key][hint_name]
                        matched_prop_key = prop_key
                        break
        
        return hint_data, matched_prop_key

    def on_hint_listbox_select(self, event, image_label, text_widget, title_label, listbox, send_button):
        """Handle hint selection from the listbox in the popup"""
        selection = listbox.curselection()
        if not selection:
            return
            
        hint_index = selection[0]
        hint_name = self.available_hints[hint_index]
        prop_display_name = self.prop_var.get()
        
        # Extract original prop name from the combined format
        original_name = prop_display_name.split('(')[-1].rstrip(')')
        original_name = original_name.strip()
        
        # Get hint data
        hint_data, prop_key = self.get_hint_data(hint_name, original_name)
                
        if hint_data:
            # Update the popup title
            title_label.config(text=hint_name)
            
            # Update the image
            has_image = False
            if hint_data.get('image'):
                try:
                    image_path = self.get_image_path(
                        self.current_room,
                        original_name,
                        hint_data['image']
                    )
                    print(f"[saved hints panel] Trying to load image: {hint_data['image']}")
                    print(f"[saved hints panel] Full image path: {image_path}")
                    if image_path and os.path.exists(image_path):
                        print(f"[saved hints panel] Image found at path: {image_path}")
                        image = Image.open(image_path)
                        image.thumbnail((250, 150))
                        photo = ImageTk.PhotoImage(image)
                        image_label.configure(image=photo, text='')
                        image_label.image = photo
                        has_image = True
                    else:
                        print(f"[saved hints panel] Image not found at path: {image_path}")
                        image_label.configure(text="No image", image='')
                except Exception as e:
                    print(f"[saved hints panel] Error loading hint image for popup: {e}")
                    image_label.configure(text="No image", image='')
            else:
                print(f"[saved hints panel] No image specified for this hint")
                image_label.configure(text="No image", image='')
            
            # Update the text
            text_widget.config(state='normal')
            text_widget.delete('1.0', tk.END)
            text_widget.insert('1.0', hint_data.get('text', ''))
            text_widget.config(state='disabled')
            
            # Update send button command
            send_button.config(command=lambda: self.send_hint_from_popup(hint_data))

    def navigate_to_hint(self, popup, current_index, direction, image_label, text_widget, title_label, prev_button, next_button, listbox):
        """Navigate to the previous or next hint and update the current popup"""
        if direction == "prev":
            new_index = current_index - 1
        else:
            new_index = current_index + 1

        # Check if the new index is valid
        if 0 <= new_index < len(self.available_hints):
            # Select the new hint in the listbox
            listbox.selection_clear(0, tk.END)
            listbox.selection_set(new_index)
            listbox.see(new_index)
            
            # Get the new hint data
            new_hint_name = self.available_hints[new_index]
            prop_display_name = self.prop_var.get()
            original_name = prop_display_name.split('(')[-1].rstrip(')')
            original_name = original_name.strip()
            
            hint_data, prop_key = self.get_hint_data(new_hint_name, original_name)
            
            if hint_data:
                # Update the popup title
                popup.title(f"Hint: {new_hint_name}")
                title_label.config(text=new_hint_name)
                
                # Update the image
                has_image = False
                if hint_data.get('image'):
                    try:
                        image_path = self.get_image_path(
                            self.current_room,
                            original_name,
                            hint_data['image']
                        )
                        print(f"[saved hints panel] Trying to load image: {hint_data['image']}")
                        print(f"[saved hints panel] Full image path: {image_path}")
                        if image_path and os.path.exists(image_path):
                            print(f"[saved hints panel] Image found at path: {image_path}")
                            image = Image.open(image_path)
                            image.thumbnail((250, 150))
                            photo = ImageTk.PhotoImage(image)
                            image_label.configure(image=photo, text='')
                            image_label.image = photo
                            has_image = True
                        else:
                            print(f"[saved hints panel] Image not found at path: {image_path}")
                            image_label.configure(text="No image", image='')
                    except Exception as e:
                        print(f"[saved hints panel] Error loading hint image for popup: {e}")
                        image_label.configure(text="No image", image='')
                else:
                    print(f"[saved hints panel] No image specified for this hint")
                    image_label.configure(text="No image", image='')
                
                # Update the text
                text_widget.config(state='normal')
                text_widget.delete('1.0', tk.END)
                text_widget.insert('1.0', hint_data.get('text', ''))
                text_widget.config(state='disabled')
                
                # Update navigation buttons
                prev_button.config(state='normal' if new_index > 0 else 'disabled')
                next_button.config(state='normal' if new_index < len(self.available_hints) - 1 else 'disabled')
                
                # Update the buttons' commands to use the new index
                prev_button.config(command=lambda: self.navigate_to_hint(
                    popup, new_index, "prev", image_label, text_widget, title_label, prev_button, next_button, listbox))
                next_button.config(command=lambda: self.navigate_to_hint(
                    popup, new_index, "next", image_label, text_widget, title_label, prev_button, next_button, listbox))

    def show_hint_popup(self, hint_name, original_name, prop_key, hint_data, hint_index=None):
        """Show popup window with hint preview"""
        # Create popup window
        popup = tk.Toplevel(self.frame)
        popup.title(f"Hints: {original_name}")
        popup.transient(self.frame)
        popup.grab_set()
        
        # Make it modal
        popup.focus_set()
        
        # Set size and position
        popup_width = 600  # Increased width to accommodate list on left
        popup_height = 450
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width - popup_width) // 2
        y = (screen_height - popup_height) // 2
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # Create main content frame to hold both panels
        main_frame = ttk.Frame(popup)
        main_frame.pack(fill='both', expand=True, padx=5, pady=5)
        
        # Create left panel for hint list
        left_panel = ttk.Frame(main_frame, width=180)
        left_panel.pack(side='left', fill='y', padx=(0, 5))
        left_panel.pack_propagate(False)  # Keep fixed width
        
        # Add list label
        list_label = ttk.Label(left_panel, text="Available Hints:", font=('Arial', 10, 'bold'))
        list_label.pack(anchor='w', pady=(0, 5))
        
        # Create hint listbox with scrollbar
        list_frame = ttk.Frame(left_panel)
        list_frame.pack(fill='both', expand=True)
        
        hint_listbox = tk.Listbox(
            list_frame,
            selectmode=tk.SINGLE,
            exportselection=False,
            height=20
        )
        hint_listbox.pack(side='left', fill='both', expand=True)
        
        list_scrollbar = ttk.Scrollbar(list_frame, command=hint_listbox.yview)
        list_scrollbar.pack(side='right', fill='y')
        hint_listbox.config(yscrollcommand=list_scrollbar.set)
        
        # Create right panel for hint details
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side='left', fill='both', expand=True)
        
        # Check if there are any hints available
        if not self.available_hints:
            # Display message when no hints are available
            no_hints_label = ttk.Label(
                right_panel, 
                text="No hints available for this prop",
                font=('Arial', 12),
                foreground='gray'
            )
            no_hints_label.pack(expand=True, pady=20)
            
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
        
        # Fill listbox with available hints
        for hint in self.available_hints:
            hint_listbox.insert(tk.END, hint)
        
        # Select the current hint
        if hint_index is not None:
            hint_listbox.selection_set(hint_index)
            hint_listbox.see(hint_index)
        
        # Add hint name label
        title_frame = ttk.Frame(right_panel)
        title_frame.pack(fill='x', pady=5)
        
        title_label = ttk.Label(title_frame, text=hint_name, font=('Arial', 12, 'bold'))
        title_label.pack(pady=5)
        
        # Add image preview
        image_frame = ttk.Frame(right_panel)
        image_frame.pack(fill='x', pady=5)
        
        image_label = ttk.Label(image_frame)
        image_label.pack(pady=5)
        
        # Try to load image if present
        has_image = False
        if hint_data.get('image'):
            try:
                image_path = self.get_image_path(
                    self.current_room,
                    original_name,
                    hint_data['image']
                )
                print(f"[saved hints panel] Trying to load image: {hint_data['image']}")
                print(f"[saved hints panel] Full image path: {image_path}")
                if image_path and os.path.exists(image_path):
                    print(f"[saved hints panel] Image found at path: {image_path}")
                    image = Image.open(image_path)
                    image.thumbnail((250, 150))
                    photo = ImageTk.PhotoImage(image)
                    image_label.configure(image=photo, text='')
                    image_label.image = photo
                    has_image = True
                else:
                    print(f"[saved hints panel] Image not found at path: {image_path}")
                    image_label.configure(text="No image", image='')
            except Exception as e:
                print(f"[saved hints panel] Error loading hint image for popup: {e}")
                image_label.configure(text="No image", image='')
        else:
            print(f"[saved hints panel] No image specified for this hint")
            image_label.configure(text="No image", image='')
        
        # Add text preview in scrollable text widget
        text_frame = ttk.Frame(right_panel)
        text_frame.pack(fill='both', expand=True, pady=5)
        
        text_label = ttk.Label(text_frame, text="Hint Text:")
        text_label.pack(anchor='w')
        
        # Create text widget with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill='both', expand=True)
        
        text_widget = tk.Text(
            text_container,
            wrap=tk.WORD,
            height=5,
            width=40
        )
        text_widget.pack(side='left', fill='both', expand=True)
        
        scrollbar = ttk.Scrollbar(text_container, command=text_widget.yview)
        scrollbar.pack(side='right', fill='y')
        text_widget.config(yscrollcommand=scrollbar.set)
        
        # Insert hint text
        text_widget.insert('1.0', hint_data.get('text', ''))
        text_widget.config(state='disabled')
        
        # Add buttons - ensure they're visible by giving them their own frame with fixed height
        button_frame = ttk.Frame(popup, height=50)
        button_frame.pack(fill='x', padx=10, pady=10)
        button_frame.pack_propagate(False)  # Prevent the frame from shrinking
        
        # Back button on the left
        back_button = ttk.Button(
            button_frame,
            text="Back",
            command=popup.destroy
        )
        back_button.pack(side='left', padx=5)
        
        # Navigation buttons in the center
        nav_frame = ttk.Frame(button_frame)
        nav_frame.pack(side='left', expand=True, fill='x')
        
        # Center the navigation buttons within the nav_frame
        nav_center = ttk.Frame(nav_frame)
        nav_center.pack(side='top', anchor='center')
        
        # Previous button
        prev_button = ttk.Button(
            nav_center,
            text="<",
            width=2,
            command=lambda: self.navigate_to_hint(
                popup, hint_index, "prev", image_label, text_widget, title_label, prev_button, next_button, hint_listbox
            )
        )
        prev_button.pack(side='left', padx=2)
        
        # Next button
        next_button = ttk.Button(
            nav_center,
            text=">",
            width=2,
            command=lambda: self.navigate_to_hint(
                popup, hint_index, "next", image_label, text_widget, title_label, prev_button, next_button, hint_listbox
            )
        )
        next_button.pack(side='left', padx=2)
        
        # Disable buttons if at beginning/end of list
        if hint_index is not None:
            if hint_index == 0:
                prev_button.config(state='disabled')
            if hint_index == len(self.available_hints) - 1:
                next_button.config(state='disabled')
        
        # Send button on the right
        send_button = ttk.Button(
            button_frame,
            text="Send Hint",
            command=lambda: self.send_hint_from_popup(popup, hint_data)
        )
        send_button.pack(side='right', padx=5)
        
        # Bind listbox selection to update the displayed hint
        hint_listbox.bind('<<ListboxSelect>>', 
                          lambda event: self.on_hint_listbox_select(
                              event, image_label, text_widget, title_label, hint_listbox, send_button))

    def send_hint_from_popup(self, popup, hint_data):
        """Send hint from popup and close the window"""
        # Prepare hint data
        send_data = {'text': hint_data.get('text', '')}
        
        # Add image path if present
        if hint_data.get('image'):
            try:
                # Get path using room, prop display name, and image filename
                prop_name = self.prop_var.get().split('(')[-1].rstrip(')').strip()
                image_path = self.get_image_path(
                    self.current_room,
                    prop_name,
                    hint_data['image']
                )
                print(f"[saved hints panel] Sending hint with image: {hint_data['image']}")
                print(f"[saved hints panel] Full image path: {image_path}")
                
                if image_path and os.path.exists(image_path):
                    print(f"[saved hints panel] Image found at path: {image_path}")
                    # Get relative path from sync_directory
                    rel_path = os.path.relpath(image_path, os.path.join(os.path.dirname(__file__), "sync_directory"))
                    send_data['image_path'] = rel_path
                    print(f"[saved hints panel] Using relative image path: {rel_path}")
                else:
                    print(f"[saved hints panel] Image not found at path: {image_path}")
            except Exception as e:
                print(f"[saved hints panel] Error getting hint image path for sending: {e}")
        else:
            print(f"[saved hints panel] No image specified for this hint")
        
        # Send hint through callback
        print(f"[saved hints panel] Sending hint data: {send_data}")
        self.send_hint_callback(send_data)
        
        # Close popup
        popup.destroy()

    def refresh_hints(self):
        """Reloads hints from the JSON file and updates the display."""
        print("[saved hints panel] Refreshing hints...")
        self.load_hints() # Reload data
        
        # Remember currently selected prop
        selected_prop = self.prop_var.get()
        
        # Refresh prop list for current room (in case props changed)
        if self.current_room:
             self.update_room(self.current_room) # This updates dropdown
             
             # Re-select the previously selected prop if it still exists
             if selected_prop:
                  props_list = self.prop_dropdown['values']
                  if selected_prop in props_list:
                       self.prop_dropdown.set(selected_prop)
                       self.on_prop_select(None) # Trigger hint update
                  else:
                       # Prop no longer exists, clear selection
                       self.prop_var.set('')
                       self.available_hints = []
                       self.open_button.config(state='disabled')
                       print(f"[saved hints panel] Previously selected prop '{selected_prop}' no longer found after refresh.")
        else:
             # No room selected, just clear things
             self.prop_dropdown['values'] = []
             self.prop_var.set('')
             self.available_hints = []
             self.open_button.config(state='disabled')
        
        print("[saved hints panel] Hints refreshed.")