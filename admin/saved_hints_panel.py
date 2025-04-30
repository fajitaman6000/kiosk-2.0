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
        self.frame.pack(side='right', padx=0, pady=5)
        
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

        # --- Hint Header Frame (Label + Button) ---
        hint_header_frame = ttk.Frame(self.hint_frame)
        hint_header_frame.pack(fill='x') # Use fill='x' to make it span the width

        hint_label = ttk.Label(hint_header_frame, text="Available Hints:", font=('Arial', 10, 'bold'))
        hint_label.pack(side='left', anchor='w', padx=(0, 5)) # Pack label to the left

        # --- Refresh Button ---
        self.refresh_button = ttk.Button(
            hint_header_frame, # Pack into the header frame
            text="⟳",
            command=self.refresh_hints,
            width=2 # Small button
        )
        self.refresh_button.pack(side='right', anchor='e', padx=(5, 0)) # Pack button to the right
        # --------------------

        # Create list view
        self.hint_listbox = tk.Listbox(
            self.hint_frame, # Pack listbox into self.hint_frame below the header
            height=6,
            width=40,
            selectmode=tk.SINGLE,
            exportselection=False,
            bg='white',
            fg='black'
        )
        self.hint_listbox.pack(pady=5, fill='x', expand=True) # Use fill='x' to make it span the width
        self.hint_listbox.bind('<<ListboxSelect>>', self.on_hint_select)
        
        # Load hints
        self.hints_data = {}
        self.current_room = None
        self.load_hints()
        self.load_prop_name_mappings()

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
            
    def show_list_view(self):
        """Make sure the list view is properly displayed"""
        # Ensure the prop frame and hint frame are packed
        if not self.refresh_btn_frame.winfo_ismapped():
            self.refresh_btn_frame.pack(fill='x', pady=(5,0))
        if not self.prop_frame.winfo_ismapped():
            self.prop_frame.pack(pady=(0, 5))
        if not self.hint_frame.winfo_ismapped():
            self.hint_frame.pack(pady=5)

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
        
        if room_number in room_map:
            room_key = room_map[room_number]
            if room_key in prop_mappings:
                # Sort props by order
                props = [(k, v) for k, v in prop_mappings[room_key]["mappings"].items()]
                props.sort(key=lambda x: x[1]["order"])
                props_list = [f"{p[1]['display']} ({p[0]})" for p in props]
        
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
        self.clear_preview()
        
        # Update prop dropdown
        available_props = self.get_props_for_room(room_number)
        self.prop_dropdown['values'] = available_props
        self.prop_dropdown.set('')  # Clear selection
        
        # Clear hint listbox
        self.hint_listbox.delete(0, tk.END)

    def clear_preview(self):
        """Clear selection in the listbox"""
        if hasattr(self, 'hint_listbox') and self.hint_listbox:
            self.hint_listbox.selection_clear(0, tk.END)

    def on_prop_select(self, event):
        """Handle prop selection from dropdown"""
        selected_display_name = self.prop_var.get()
        #print(f"[saved hints panel]Selected prop from dropdown: {selected_display_name}")
        
        self.hint_listbox.delete(0, tk.END)
        
        if selected_display_name:
            hints = self.get_hints_for_prop(selected_display_name)
            #print(f"[saved hints panel]Found hints: {hints}")
            for hint in hints:
                self.hint_listbox.insert(tk.END, hint)

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

    def on_hint_select(self, event):
        """Handle hint selection from listbox"""
        selection = self.hint_listbox.curselection()
        if not selection:
            return
            
        hint_name = self.hint_listbox.get(selection[0])
        prop_display_name = self.prop_var.get()
        
        # Extract original prop name from the combined format
        original_name = prop_display_name.split('(')[-1].rstrip(')')
        original_name = original_name.strip()
        
        # Get hint data
        hint_data, prop_key = self.get_hint_data(hint_name, original_name)
                
        if hint_data:
            self.show_hint_popup(hint_name, original_name, prop_key, hint_data, selection[0])
            
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

    def navigate_to_hint(self, popup, current_index, direction, image_label, text_widget, title_label, prev_button, next_button):
        """Navigate to the previous or next hint and update the current popup"""
        if direction == "prev":
            new_index = current_index - 1
        else:
            new_index = current_index + 1

        # Check if the new index is valid
        if 0 <= new_index < self.hint_listbox.size():
            # Select the new hint in the listbox (but don't trigger a new popup)
            self.hint_listbox.selection_clear(0, tk.END)
            self.hint_listbox.selection_set(new_index)
            self.hint_listbox.see(new_index)
            
            # Get the new hint data
            new_hint_name = self.hint_listbox.get(new_index)
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
                next_button.config(state='normal' if new_index < self.hint_listbox.size() - 1 else 'disabled')
                
                # Update the buttons' commands to use the new index
                prev_button.config(command=lambda: self.navigate_to_hint(
                    popup, new_index, "prev", image_label, text_widget, title_label, prev_button, next_button))
                next_button.config(command=lambda: self.navigate_to_hint(
                    popup, new_index, "next", image_label, text_widget, title_label, prev_button, next_button))

    def show_hint_popup(self, hint_name, original_name, prop_key, hint_data, hint_index=None):
        """Show popup window with hint preview"""
        # Create popup window
        popup = tk.Toplevel(self.frame)
        popup.title(f"Hint: {hint_name}")
        popup.transient(self.frame)
        popup.grab_set()
        
        # Make it modal
        popup.focus_set()
        
        # Set size and position
        popup_width = 400
        popup_height = 450  # Reduced height
        screen_width = popup.winfo_screenwidth()
        screen_height = popup.winfo_screenheight()
        x = (screen_width - popup_width) // 2
        y = (screen_height - popup_height) // 2
        popup.geometry(f"{popup_width}x{popup_height}+{x}+{y}")
        
        # Add hint name label
        title_frame = ttk.Frame(popup)
        title_frame.pack(fill='x', padx=10, pady=5)
        
        title_label = ttk.Label(title_frame, text=hint_name, font=('Arial', 12, 'bold'))
        title_label.pack(pady=5)
        
        # Add image preview
        image_frame = ttk.Frame(popup)
        image_frame.pack(fill='x', padx=10, pady=5)
        
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
        text_frame = ttk.Frame(popup)
        text_frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        text_label = ttk.Label(text_frame, text="Hint Text:")
        text_label.pack(anchor='w')
        
        # Create text widget with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill='both', expand=True)
        
        text_widget = tk.Text(
            text_container,
            wrap=tk.WORD,
            height=5,  # Reduced height
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
                popup, hint_index, "prev", image_label, text_widget, title_label, prev_button, next_button
            )
        )
        prev_button.pack(side='left', padx=2)
        
        # Next button
        next_button = ttk.Button(
            nav_center,
            text=">",
            width=2,
            command=lambda: self.navigate_to_hint(
                popup, hint_index, "next", image_label, text_widget, title_label, prev_button, next_button
            )
        )
        next_button.pack(side='left', padx=2)
        
        # Disable buttons if at beginning/end of list
        if hint_index is not None:
            if hint_index == 0:
                prev_button.config(state='disabled')
            if hint_index == self.hint_listbox.size() - 1:
                next_button.config(state='disabled')
        
        # Send button on the right
        send_button = ttk.Button(
            button_frame,
            text="Send Hint",
            command=lambda: self.send_hint_from_popup(popup, hint_data)
        )
        send_button.pack(side='right', padx=5)

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
    
    def send_hint(self):
        """Send the currently selected hint"""
        selection = self.hint_listbox.curselection()
        if not selection:
            return
        
        hint_name = self.hint_listbox.get(selection[0])
        prop_display_name = self.prop_var.get()
        room_str = str(self.current_room)
        
        # Extract original prop name from the combined format
        original_name = prop_display_name.split('(')[-1].rstrip(')')
        original_name = original_name.strip()
        
        # Build name mapping just like in get_hints_for_prop
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
        selected_hint = None
        if room_str in self.hints_data:
            for prop_key in self.hints_data[room_str]:
                if (prop_key.lower() == original_name.lower() or 
                    (original_name.lower() in name_mapping and 
                     prop_key.lower() == name_mapping[original_name.lower()].lower())):
                    if hint_name in self.hints_data[room_str][prop_key]:
                        selected_hint = self.hints_data[room_str][prop_key][hint_name]
                        break
                
        if selected_hint:
            # Prepare hint data
            hint_data = {'text': selected_hint.get('text', '')}
            
            # Add image path if present
            if selected_hint.get('image'):
                try:
                    # Get path using room, prop display name, and image filename
                    image_path = self.get_image_path(
                        self.current_room,
                        original_name,
                        selected_hint['image']
                    )
                    print(f"[saved hints panel] Sending hint with image: {selected_hint['image']}")
                    print(f"[saved hints panel] Full image path: {image_path}")
                    
                    if image_path and os.path.exists(image_path):
                        print(f"[saved hints panel] Image found at path: {image_path}")
                        # Get relative path from sync_directory
                        rel_path = os.path.relpath(image_path, os.path.join(os.path.dirname(__file__), "sync_directory"))
                        hint_data['image_path'] = rel_path
                        print(f"[saved hints panel] Using relative image path: {rel_path}")
                    else:
                        print(f"[saved hints panel] Image not found at path: {image_path}")
                except Exception as e:
                    print(f"[saved hints panel] Error getting hint image path for sending: {e}")
            else:
                print(f"[saved hints panel] No image specified for this hint")
            
            # Send hint through callback
            print(f"[saved hints panel] Sending hint data: {hint_data}")
            self.send_hint_callback(hint_data)
        else:
            print(f"[saved hints panel] No hint data found for {hint_name} in {original_name}")

    def refresh_hints(self):
        """Reloads hints from the JSON file and updates the display."""
        print("[saved hints panel] Refreshing hints...")
        self.load_hints() # Reload data
        
        # Remember currently selected prop
        selected_prop = self.prop_var.get()
        
        # Refresh prop list for current room (in case props changed)
        if self.current_room:
             self.update_room(self.current_room) # This clears hints too
             
             # Re-select the previously selected prop if it still exists
             if selected_prop:
                  props_list = self.prop_dropdown['values']
                  if selected_prop in props_list:
                       self.prop_var.set(selected_prop)
                       self.on_prop_select(None) # Trigger hint list update
                  else:
                       # Prop no longer exists, clear selection and hints
                       self.prop_var.set('')
                       self.hint_listbox.delete(0, tk.END)
                       print(f"[saved hints panel] Previously selected prop '{selected_prop}' no longer found after refresh.")
        else:
             # No room selected, just clear things
             self.prop_dropdown['values'] = []
             self.prop_var.set('')
             self.hint_listbox.delete(0, tk.END)
        
        print("[saved hints panel] Hints refreshed.")