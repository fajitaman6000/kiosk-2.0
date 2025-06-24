import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
from pathlib import Path
import os
from PIL import Image, ImageTk
import hashlib

class ManagerSettings:
    def __init__(self, app, admin_interface):
        self.app = app
        self.admin_interface = admin_interface
        self.main_container = None
        self.load_prop_mappings()
        self.password_manager = AdminPasswordManager(app)
        self.current_page = None
        self.autosave_after_id = None
        self.selected_hint_key = None
        self.hint_tree = None
        self.hint_map = {}
        self.tree_items = {}
        self.current_prop_info = None
        self.highlighted_cousin_items = set()
        self.image_listbox_data = []
        
        # Full room names mapping
        self.room_full_names = {
            '1': 'Casino Heist',
            '2': 'Morning After',
            '3': 'Wizard Trials',
            '4': 'Zombie Outbreak',
            '5': 'Haunted Manor',
            '6': 'Atlantis Rising',
            '7': 'Time Machine'
        }

    def load_prop_mappings(self):
        try:
            with open('prop_name_mapping.json', 'r') as f:
                self.prop_mappings = json.load(f)
        except Exception as e:
            print(f"[hint library]Error loading prop mappings: {e}")
            self.prop_mappings = {}

    def get_display_name(self, room_id, prop_name):
        # Corrected mapping based on admin_main.py
        room_mapping = {'1': 'casino', '2': 'ma', '3': 'wizard', '4': 'zombie', '5': 'haunted', '6': 'atlantis', '7': 'time'} # Corrected
        room_key = room_mapping.get(str(room_id))
        if not room_key:
            return prop_name
        if room_key in self.prop_mappings:
            room_mappings = self.prop_mappings[room_key]['mappings']
            if prop_name in room_mappings:
                return room_mappings[prop_name]['display']
        return prop_name

    def check_credentials(self):
        def on_success():
            self.show_hint_manager()
        return self.password_manager.verify_password(callback=on_success)

    def show_hint_manager(self):
        self.create_hint_management_view()

    def change_password(self):
        change_window = tk.Toplevel(self.app.root)
        change_window.title("Change Password")
        change_window.geometry("300x250")
        tk.Label(change_window, text="Old Password:", font=('Arial', 12)).pack(pady=5)
        old_password_entry = tk.Entry(change_window, show="*", width=20)
        old_password_entry.pack(pady=5)
        tk.Label(change_window, text="New Password:", font=('Arial', 12)).pack(pady=5)
        new_password_entry = tk.Entry(change_window, show="*", width=20)
        new_password_entry.pack(pady=5)
        tk.Label(change_window, text="Confirm New Password:", font=('Arial', 12)).pack(pady=5)
        confirm_password_entry = tk.Entry(change_window, show="*", width=20)
        confirm_password_entry.pack(pady=5)

        def save_new_password():
            old_password = old_password_entry.get()
            new_password = new_password_entry.get()
            confirm_password = confirm_password_entry.get()
            hashed_old = hashlib.sha256(old_password.encode()).hexdigest()
            if hashed_old != self.password_manager.hashed_password:
                messagebox.showerror("Error", "Incorrect old password.")
                return
            if new_password != confirm_password:
                messagebox.showerror("Error", "New passwords do not match.")
                return
            if not new_password:
                messagebox.showerror("Error", "New password cannot be blank.")
                return
            self.password_manager.hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            with open("hint_manager_password.txt", 'w') as f:
                f.write(self.password_manager.hashed_password)
            messagebox.showinfo("Success", "Password changed successfully.")
            change_window.destroy()

        old_password_entry.bind('<Return>', lambda e: new_password_entry.focus())
        new_password_entry.bind('<Return>', lambda e: confirm_password_entry.focus())
        confirm_password_entry.bind('<Return>', lambda e: save_new_password())
        change_button = tk.Button(change_window, text="Save Changes", command=save_new_password)
        change_button.pack(pady=10)
        change_window.transient(self.app.root)
        change_window.grab_set()
        old_password_entry.focus_set()
        self.app.root.wait_window(change_window)

    def create_hint_management_view(self):
        settings_window = tk.Toplevel(self.app.root)
        settings_window.title("Manager Settings")
        settings_window.geometry("800x600")
        self.main_container = ttk.Frame(settings_window)
        self.main_container.pack(fill='both', expand=True, padx=10, pady=5)
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill='x', pady=(0, 10))
        nav_frame = ttk.Frame(self.main_container)
        nav_frame.pack(fill='x', pady=(0, 10))
        hint_btn = ttk.Button(nav_frame, text="Hint Management", command=lambda: self.show_settings_page('hints'))
        hint_btn.pack(side='left', padx=5)
        password_btn = ttk.Button(nav_frame, text="Password Settings", command=lambda: self.show_settings_page('password'))
        password_btn.pack(side='left', padx=5)
        image_browser_btn = ttk.Button(nav_frame, text="Image Browser", command=self.launch_image_browser)
        image_browser_btn.pack(side='left', padx=5)
        image_cropper_btn = ttk.Button(nav_frame, text="Image Cropper", command=self.launch_image_cropper)
        image_cropper_btn.pack(side='left', padx=5)
        self.settings_container = ttk.Frame(self.main_container)
        self.settings_container.pack(fill='both', expand=True)
        self.show_settings_page('hints')

    def show_settings_page(self, page):
        for widget in self.settings_container.winfo_children():
            widget.destroy()
        self.current_page = page
        if page == 'hints':
            self.create_hints_page()
        elif page == 'password':
            self.create_password_page()

    def create_hints_page(self):
        paned_window = ttk.PanedWindow(self.settings_container, orient=tk.HORIZONTAL)
        paned_window.pack(fill='both', expand=True)

        # --- Left side: Hint list (using Treeview) ---
        self.hint_list_frame = ttk.Frame(paned_window)
        paned_window.add(self.hint_list_frame, weight=1)

        ttk.Label(self.hint_list_frame, text="Hint Manager", font=('Arial', 14, 'bold')).pack(pady=(5,2))

        self.hint_tree = ttk.Treeview(self.hint_list_frame, selectmode='browse')
        # Configure tags for coloring props
        self.hint_tree.tag_configure('has_hints', foreground='green')
        self.hint_tree.tag_configure('no_hints', foreground='red')
        self.hint_tree.tag_configure('room', font=('Arial', 10, 'bold'))
        self.hint_tree.tag_configure('cousin_highlight', background='lightgreen')
        self.hint_tree.pack(side="left", fill="both", expand=True)
        self.hint_tree.bind('<<TreeviewSelect>>', self.on_hint_select)
        self.hint_tree.bind('<Motion>', self.on_item_motion)
        self.hint_tree.bind('<Leave>', self.on_tree_leave)

        scrollbar = ttk.Scrollbar(self.hint_list_frame, orient="vertical", command=self.hint_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.hint_tree['yscrollcommand'] = scrollbar.set

        # --- Right side: Hint editor ---
        self.hint_editor_frame = ttk.Frame(paned_window)
        paned_window.add(self.hint_editor_frame, weight=3)

        # --- Selected Hint Name Label ---
        self.selected_hint_name_label = ttk.Label(self.hint_editor_frame, text="", font=('Arial', 12, 'bold'))
        self.selected_hint_name_label.pack(pady=(5, 0))

        # --- Add New Hint Button ---
        self.add_hint_button = ttk.Button(self.hint_editor_frame, text="Add New Hint", command=self.add_new_hint, state=tk.DISABLED)
        self.add_hint_button.pack(pady=5)

        # --- Rename Hint Section ---
        rename_frame = ttk.Frame(self.hint_editor_frame)
        rename_frame.pack(fill='x', pady=5)
        ttk.Label(rename_frame, text="Rename Hint:", font=('Arial', 10, 'bold')).pack(side='left', padx=5)
        self.rename_entry = ttk.Entry(rename_frame, width=30, state=tk.DISABLED)
        self.rename_entry.pack(side='left', padx=5)
        self.rename_button = ttk.Button(rename_frame, text="Rename", command=self.rename_selected_hint, state=tk.DISABLED)
        self.rename_button.pack(side='left', padx=5)
        self.rename_entry.bind('<Return>', lambda e: self.rename_selected_hint())

        ttk.Label(self.hint_editor_frame, text="Text content:", font=('Arial', 10, 'bold')).pack(anchor='w', padx=5, pady=2)
        self.text_widget = tk.Text(self.hint_editor_frame, height=6, width=40, wrap=tk.WORD, state=tk.DISABLED)
        self.text_widget.pack(pady=5)

        # --- Image section with refresh button ---
        image_header_frame = ttk.Frame(self.hint_editor_frame)
        image_header_frame.pack(fill='x', pady=(5,0), padx=5, anchor='w')
        
        self.image_label = ttk.Label(image_header_frame, text="", font=('Arial', 10, 'bold'))
        self.image_label.pack(side='left')
        
        self.refresh_images_button = ttk.Button(image_header_frame, text="↻", width=3, command=self.refresh_image_selector)
        self.refresh_images_button.pack(side='left', padx=5)
        self.refresh_images_button.config(state=tk.DISABLED)

        image_frame = ttk.Frame(self.hint_editor_frame)
        image_frame.pack(fill='x', pady=5)

        self.image_listbox = tk.Listbox(image_frame, height=8, width=30, selectmode=tk.SINGLE, exportselection=False, state=tk.DISABLED)
        self.image_listbox.pack(side='left', padx=5)
        self.image_listbox.bind('<<ListboxSelect>>', self.preview_selected_image)

        self.image_preview_label = ttk.Label(image_frame)
        self.image_preview_label.pack(side='left', padx=5)

        # --- Selected Image Filename Label ---
        self.selected_image_label = ttk.Label(self.hint_editor_frame, text="")
        self.selected_image_label.pack(pady=2, anchor='w', padx=5)

        self.status_label = ttk.Label(self.hint_editor_frame, text="")
        self.status_label.pack(pady=5)

        self.delete_button = ttk.Button(self.hint_editor_frame, text="Delete Hint", command=self.delete_selected_hint, state=tk.DISABLED)
        self.delete_button.pack(pady=5)

        self.text_widget.bind("<<Modified>>", lambda event: self.autosave_hint())

        self.load_hints()

    def create_password_page(self):
        password_frame = ttk.Frame(self.settings_container)
        password_frame.pack(fill='both', expand=True, padx=20, pady=20)
        ttk.Label(password_frame, text="Password Management", font=('Arial', 12, 'bold')).pack(pady=(0, 20))
        change_pass_btn = ttk.Button(password_frame, text="Change Admin Password", command=self.change_password)
        change_pass_btn.pack(pady=10)

    def on_treeview_open(self, event):
        pass

    def on_treeview_close(self, event):
        pass

    def load_hints(self):
        # Save expanded items before refreshing
        expanded_items = []
        if self.hint_tree:
            # Get all currently expanded items
            for item_id in self.tree_items:
                try:
                    if self.hint_tree.item(item_id, 'open'):
                        item_info = self.tree_items.get(item_id)
                        if item_info:
                            expanded_items.append(item_info)
                except (tk.TclError, KeyError):
                    # Skip items that no longer exist
                    continue
            
        # Save current selection if any
        current_selection = None
        if self.hint_tree and self.hint_tree.selection():
            try:
                selected_id = self.hint_tree.selection()[0]
                if selected_id in self.tree_items:
                    current_selection = self.tree_items[selected_id]
            except (tk.TclError, KeyError):
                # Handle case where selection is invalid
                pass
        
        # Clear the tree
        if self.hint_tree:
            for item in self.hint_tree.get_children():
                self.hint_tree.delete(item)
                
        self.hint_map = {}
        self.tree_items = {}
        hint_data = {}

        try:
            with open('saved_hints.json', 'r') as f:
                content = f.read().strip()
                if not content:
                    # File exists but is empty
                    print("[hint library] saved_hints.json is empty. Starting fresh.")
                    self.create_empty_hints_file()
                    hint_data = {}
                else:
                    hint_data = json.loads(content).get('rooms', {}) # Load only rooms subtree
        except FileNotFoundError:
            print("[hint library] saved_hints.json not found. Starting fresh.")
            self.create_empty_hints_file()
            hint_data = {} # Ensure hint_data is a dict
        except json.JSONDecodeError as e:
            print(f"[hint library]Error decoding saved_hints.json: {e}")
            #messagebox.showerror("Error", f"Error reading saved_hints.json: {e}. Starting with empty hint data.")
            self.create_empty_hints_file()
            hint_data = {} # Ensure hint_data is a dict
        except Exception as e:
            print(f"[hint library]Error loading hints: {e}")
            self.create_empty_hints_file()
            hint_data = {} # Ensure hint_data is a dict

        # Iterate through rooms defined in prop_mappings first
        # Corrected reverse mapping based on admin_main.py
        room_mapping_reverse = {'casino': '1', 'ma': '2', 'wizard': '3', 'zombie': '4', 'haunted': '5', 'atlantis': '6', 'time': '7'} # Corrected
        for room_key, room_info in self.prop_mappings.items():
            room_id = room_mapping_reverse.get(room_key)
            if not room_id: continue # Skip if room key isn't in our reverse map

            # Use full room name with bold font
            room_text = self.room_full_names.get(room_id, room_key.capitalize())
            room_item = self.hint_tree.insert("", "end", text=room_text, open=False) # Start closed
            self.tree_items[room_item] = {"type": "room", "id": room_id, "key": room_key}

            # Apply bold font to room items
            self.hint_tree.item(room_item, tags=('room',))

            # Get hints for this room from loaded data, default to empty dict
            room_hints_data = hint_data.get(str(room_id), {})

            # Iterate through all props defined for this room in prop_mappings
            for prop_name, prop_details in room_info.get('mappings', {}).items():
                display_name = prop_details.get('display', prop_name)

                # *** Use display_name to look up hints in saved_hints.json data ***
                prop_hints = room_hints_data.get(display_name, {}) # Get saved hints using display_name as key

                hint_count = len(prop_hints)
                tag_to_use = 'has_hints' if hint_count > 0 else 'no_hints'

                prop_text = f"{display_name} ({hint_count})"
                prop_item = self.hint_tree.insert(room_item, "end", text=prop_text, tags=(tag_to_use,), open=False) # Start closed
                # Store internal prop_name here for consistency, but display_name for lookup
                self.tree_items[prop_item] = {
                    "type": "prop",
                    "room_id": room_id,
                    "prop_name": prop_name, # Internal name
                    "display_name": display_name # Display name
                }

                # Now add the actual hints if they exist
                for hint_name, hint_info in prop_hints.items():
                     # Create key using display_name for consistency
                    hint_key = f"{room_id}-{display_name}-{hint_name}"
                    display_text = f"{hint_name}" # Just the hint name for the tree
                    hint_item = self.hint_tree.insert(prop_item, "end", text=display_text)
                    # Store hint key in tree_items
                    self.tree_items[hint_item] = {"type": "hint", "key": hint_key}
                    # Store hint info with display_name reference
                    self.hint_map[hint_key] = {
                        "room_id": room_id,
                        "prop_display_name": display_name,
                        "hint_name": hint_name,
                        "data": hint_info # Store the actual hint data (text, image)
                     }

        # Configure room tag for bold font
        if self.hint_tree:
            self.hint_tree.tag_configure('room', font=('Arial', 10, 'bold'))
        
        # Restore expanded state
        for item_info in expanded_items:
            item_type = item_info.get('type')
            if item_type == 'room':
                room_id = item_info.get('id')
                # Find the corresponding new item
                for item_id, info in self.tree_items.items():
                    if info.get('type') == 'room' and info.get('id') == room_id:
                        self.hint_tree.item(item_id, open=True)
                        break
            elif item_type == 'prop':
                room_id = item_info.get('room_id')
                display_name = item_info.get('display_name')
                # Find the corresponding new prop item
                for item_id, info in self.tree_items.items():
                    if (info.get('type') == 'prop' and 
                        info.get('room_id') == room_id and 
                        info.get('display_name') == display_name):
                        self.hint_tree.item(item_id, open=True)
                        # Also expand its parent
                        parent_id = self.hint_tree.parent(item_id)
                        if parent_id:
                            self.hint_tree.item(parent_id, open=True)
                        break
        
        # Restore selection if possible
        if current_selection:
            select_type = current_selection.get('type')
            if select_type == 'hint':
                hint_key = current_selection.get('key')
                for item_id, info in self.tree_items.items():
                    if info.get('type') == 'hint' and info.get('key') == hint_key:
                        self.hint_tree.selection_set(item_id)
                        self.hint_tree.focus(item_id)
                        self.hint_tree.see(item_id)
                        # Make sure parents are expanded
                        parent_id = self.hint_tree.parent(item_id)
                        if parent_id:
                            self.hint_tree.item(parent_id, open=True)
                            grand_parent = self.hint_tree.parent(parent_id)
                            if grand_parent:
                                self.hint_tree.item(grand_parent, open=True)
                        break
            elif select_type == 'prop':
                room_id = current_selection.get('room_id')
                display_name = current_selection.get('display_name')
                for item_id, info in self.tree_items.items():
                    if (info.get('type') == 'prop' and 
                        info.get('room_id') == room_id and 
                        info.get('display_name') == display_name):
                        self.hint_tree.selection_set(item_id)
                        self.hint_tree.focus(item_id)
                        self.hint_tree.see(item_id)
                        # Expand parent
                        parent_id = self.hint_tree.parent(item_id)
                        if parent_id:
                            self.hint_tree.item(parent_id, open=True)
                        break
            elif select_type == 'room':
                room_id = current_selection.get('id')
                for item_id, info in self.tree_items.items():
                    if info.get('type') == 'room' and info.get('id') == room_id:
                        self.hint_tree.selection_set(item_id)
                        self.hint_tree.focus(item_id)
                        self.hint_tree.see(item_id)
                        break

    def create_empty_hints_file(self):
        """Creates an empty but valid hints file with proper structure."""
        empty_hints = {"rooms": {}}
        
        # Initialize with empty structures for all rooms
        room_mapping_reverse = {'casino': '1', 'ma': '2', 'wizard': '3', 'zombie': '4', 'haunted': '5', 'atlantis': '6', 'time': '7'}
        
        for room_key in room_mapping_reverse.keys():
            room_id = room_mapping_reverse[room_key]
            empty_hints["rooms"][room_id] = {}
        
        try:
            with open('saved_hints.json', 'w') as f:
                json.dump(empty_hints, f, indent=4)
            print("[hint library] Created empty hints file with proper structure")
        except Exception as e:
            print(f"[hint library] Error creating empty hints file: {e}")

    def get_prop_details(self, room_id, internal_prop_name):
        """Gets the full details for a prop from prop_mappings."""
        # Corrected mapping based on admin_main.py
        room_mapping = {'1': 'casino', '2': 'ma', '3': 'wizard', '4': 'zombie', '5': 'haunted', '6': 'atlantis', '7': 'time'} # Corrected
        room_key = room_mapping.get(str(room_id))
        if not room_key or room_key not in self.prop_mappings:
            return None # Room key not found or not in mappings
        room_mappings = self.prop_mappings[room_key].get('mappings', {})
        return room_mappings.get(internal_prop_name) # Returns details or None if prop_name not found

    def on_hint_select(self, event):
        selection = self.hint_tree.selection()
        if not selection:
            self.clear_editor_and_disable()
            return

        selected_item = selection[0]
        item_info = self.tree_items.get(selected_item)

        if not item_info:
            print(f"Error: Could not find info for selected tree item {selected_item}")
            self.clear_editor_and_disable()
            return

        item_type = item_info['type']

        if item_type == 'room':
            self.clear_editor_and_disable()
            self.add_hint_button.config(state=tk.DISABLED)
            self.current_prop_info = None
            self.refresh_images_button.config(state=tk.DISABLED)

        elif item_type == 'prop':
            self.clear_editor_and_disable()
            self.add_hint_button.config(state=tk.NORMAL)
            self.current_prop_info = item_info
            prop_display_name = item_info['display_name']
            prop_internal_name = item_info['prop_name'] # Get internal name
            room_id = item_info['room_id']

            # Get cousin ID
            prop_details = self.get_prop_details(room_id, prop_internal_name)
            cousin_id = prop_details.get('cousin', 'None') if prop_details else 'N/A'

            # Update the main label
            self.selected_hint_name_label.config(text=f"{prop_display_name} - Cousin ID: {cousin_id}")

            self.image_label.config(text=f"Images available for {prop_display_name}:", font=('Arial', 10, 'bold'))
            # Enable the image listbox for prop selection too
            self.image_listbox.config(state=tk.NORMAL)
            self.show_image_selector(room_id, prop_display_name, None, load_only=True)
            self.refresh_images_button.config(state=tk.NORMAL)

        elif item_type == 'hint':
            self.add_hint_button.config(state=tk.DISABLED)
            self.current_prop_info = None # Clear prop info when hint is selected
            hint_key = item_info['key']
            if hint_key in self.hint_map:
                hint_full_info = self.hint_map[hint_key]
                hint_name = hint_full_info['hint_name']
                room_id = hint_full_info['room_id']
                prop_display_name = hint_full_info['prop_display_name']

                # Find the parent prop to get its internal name and cousin ID
                parent_prop_item = self.hint_tree.parent(selected_item)
                parent_prop_info = self.tree_items.get(parent_prop_item)
                cousin_id = 'N/A' # Default if parent info is missing
                if parent_prop_info and parent_prop_info['type'] == 'prop':
                    prop_internal_name = parent_prop_info['prop_name']
                    prop_details = self.get_prop_details(room_id, prop_internal_name)
                    cousin_id = prop_details.get('cousin', 'None') if prop_details else 'N/A'
                    # Configure image label text using parent prop display name
                    self.image_label.config(text=f"Images available for {prop_display_name}:", font=('Arial', 10, 'bold'))
                else:
                    print(f"Warning: Could not find parent prop info for hint {hint_key}")
                    self.image_label.config(text="Images available:", font=('Arial', 10, 'bold'))

                # Update the main label according to the request format
                self.selected_hint_name_label.config(text=f"Editing Hint: {hint_name} - Cousin ID: {cousin_id}")

                # Populate editor fields (calls select_hint which updates image selector etc.)
                self.select_hint(hint_key, hint_full_info)

                # Enable controls
                self.rename_entry.config(state=tk.NORMAL)
                self.rename_button.config(state=tk.NORMAL)
                self.text_widget.config(state=tk.NORMAL)
                self.image_listbox.config(state=tk.NORMAL)
                self.delete_button.config(state=tk.NORMAL)
                self.refresh_images_button.config(state=tk.NORMAL)

            else:
                print(f"Error: Could not find hint key {hint_key} in hint map.")
                self.clear_editor_and_disable()
                self.refresh_images_button.config(state=tk.DISABLED)
                self.selected_hint_name_label.config(text="") # Clear label on error

    def clear_editor_and_disable(self):
        """Clears hint editor fields and disables controls."""
        self.selected_hint_key = None
        self.rename_entry.delete(0, tk.END)
        self.rename_entry.config(state=tk.DISABLED)
        self.rename_button.config(state=tk.DISABLED)
        
        # First set state to NORMAL to modify content, then disable
        self.text_widget.config(state=tk.NORMAL)
        self.text_widget.delete('1.0', tk.END)
        self.text_widget.config(state=tk.DISABLED)
        self.text_widget.edit_modified(False)
        
        self.image_listbox.delete(0, tk.END)
        self.image_listbox.config(state=tk.DISABLED)
        self.refresh_images_button.config(state=tk.DISABLED)
        
        # Safely clear the image by setting a None image
        try:
            self.image_preview_label.config(image='')
            self.image_preview_label.image = None
        except Exception as e:
            print(f"[hint library]Error clearing image preview: {e}")
        
        self.image_label.config(text="")
        self.delete_button.config(state=tk.DISABLED)
        self.status_label.config(text="")
        self.selected_hint_name_label.config(text="")
        self.selected_image_label.config(text="")
        
        # Safely cancel the autosave timer if it exists
        if self.autosave_after_id is not None:
            try:
                self.status_label.after_cancel(self.autosave_after_id)
            except ValueError:
                # The after_id was invalid, just ignore
                pass
            self.autosave_after_id = None

    def select_hint(self, hint_key, hint_full_info):
        """Populates the editor fields for the selected hint."""
        self.selected_hint_key = hint_key
        hint_data = hint_full_info['data']
        hint_name = hint_full_info['hint_name']
        room_id = hint_full_info['room_id']
        prop_display_name = hint_full_info['prop_display_name']

        self.rename_entry.delete(0, tk.END)
        self.rename_entry.insert(0, hint_name)

        # First enable the text widget so we can edit it
        self.text_widget.config(state=tk.NORMAL)
        # Then clear and insert the text
        self.text_widget.delete('1.0', tk.END)
        self.text_widget.insert('1.0', hint_data.get('text', ''))
        self.text_widget.edit_modified(False)
        # We don't disable it here because on_hint_select will enable it after this

        self.selected_hint_name_label.config(text=f"Editing Hint: {hint_name}")
        self.show_image_selector(room_id, prop_display_name, hint_name, selected_image=hint_data.get('image'))
        # Update the selected image label after selector is shown and context is set
        self.update_selected_image_label(hint_data.get('image'))

    def delete_selected_hint(self):
        if not self.selected_hint_key:
             messagebox.showwarning("Warning", "No hint selected to delete.")
             return

        try:
            room_id = self.hint_map[self.selected_hint_key]['room_id']
            prop_display_name = self.hint_map[self.selected_hint_key]['prop_display_name']
            hint_name = self.hint_map[self.selected_hint_key]['hint_name']

            with open('saved_hints.json', 'r') as f:
                hint_data_file = json.load(f)

            room_hints = hint_data_file.get('rooms', {}).get(str(room_id), {})
            prop_hints = room_hints.get(prop_display_name)

            if prop_hints and hint_name in prop_hints:
                del prop_hints[hint_name]
                print(f"Deleted hint '{hint_name}' from prop '{prop_display_name}' in room '{room_id}'")

                if not prop_hints:
                    del room_hints[prop_display_name]
                    print(f"Removed empty prop '{prop_display_name}' from room '{room_id}'")
                    if not room_hints:
                        del hint_data_file['rooms'][str(room_id)]
                        print(f"Removed empty room '{room_id}'")

                with open('saved_hints.json', 'w') as f:
                    json.dump(hint_data_file, f, indent=4)

                self.clear_editor_and_disable()
                self.load_hints() #problematic line here
                self.status_label.config(text="Hint deleted.", foreground='green')
                self.status_label.after(2000, lambda: self.status_label.config(text=""))

            else:
                 messagebox.showerror("Error", f"Could not find hint '{hint_name}' in saved data for deletion.")

        except FileNotFoundError:
             messagebox.showerror("Error", "saved_hints.json not found.")
        except KeyError as e:
             messagebox.showerror("Error", f"Data structure error during delete: Missing key {e}")
             print(f"[hint library]KeyError during delete: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred deleting hint: {e}")
            print(f"[hint library]Error deleting hint: {e}")

        # Update the selected image label after preview/update attempt
        # This ensures the label reflects the currently selected *list item*, even if preview fails
        self.update_selected_image_label(None)

    def show_image_selector(self, room_id, current_prop_display_name, hint_name, selected_image=None, load_only=False):
        """Populates the image listbox with images from the current prop and its cousins."""
        self.image_listbox.delete(0, tk.END)
        self.image_listbox_data = []  # Clear previous data

        # Always add "None" option
        self.image_listbox.insert(tk.END, "None")
        self.image_listbox_data.append(("None", None))  # Add placeholder metadata for "None"
        self.image_listbox.itemconfig(0, {'fg': 'black'})  # Ensure "None" is black

        # Reset preview
        try:
            self.image_preview_label.config(image='', text="")
            self.image_preview_label.image = None
        except Exception as e:
            print(f"[hint library]Error clearing image preview in selector: {e}")

        room_map = {'1': "casino", '2': "ma", '3': "wizard", '4': "zombie", '5': "haunted", '6': "atlantis", '7': "time"}
        room_folder = room_map.get(str(room_id))
        if not room_folder:
            print(f"Cannot find room folder for room ID {room_id}")
            self.image_listbox.selection_set(0)  # Select "None"
            return

        # Find the current prop's cousin ID
        current_prop_internal_name = None
        for p_internal, p_details in self.prop_mappings.get(room_folder, {}).get('mappings', {}).items():
            if p_details.get('display') == current_prop_display_name:
                current_prop_internal_name = p_internal
                break

        if not current_prop_internal_name:
            print(f"Could not find internal name for current prop: {current_prop_display_name}")
            self.image_listbox.selection_set(0)  # Select "None"
            return  # Cannot proceed without internal name

        current_prop_details = self.get_prop_details(room_id, current_prop_internal_name)
        current_cousin_id = current_prop_details.get('cousin') if current_prop_details else None

        # Gather list of prop display names to check (current + cousins)
        props_to_scan = {current_prop_display_name}  # Use a set to avoid duplicates
        if current_cousin_id is not None:
            all_room_props = self.prop_mappings.get(room_folder, {}).get('mappings', {})
            for p_internal, p_details in all_room_props.items():
                if p_details.get('cousin') == current_cousin_id:
                    props_to_scan.add(p_details.get('display', p_internal))

        base_dir = Path(os.path.dirname(__file__)) / "sync_directory" / "hint_image_files" / room_folder
        found_images = {}  # Use dict to handle duplicates gracefully {filename: source_prop}

        # Scan directories of the current prop and its cousins
        for prop_name_to_scan in props_to_scan:
            image_dir_path = base_dir / prop_name_to_scan
            if image_dir_path.is_dir():
                try:
                    for item in os.listdir(str(image_dir_path)):
                        if not item.startswith('.') and item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                            # Store filename and its source prop
                            # If duplicate filename, the last one scanned wins (or choose logic if needed)
                            found_images[item] = prop_name_to_scan
                except OSError as e:
                    print(f"[Hint Manager] Error reading image directory {image_dir_path}: {e}")

        # Sort filenames alphabetically for consistent display
        sorted_filenames = sorted(found_images.keys())

        # Populate listbox and metadata list
        listbox_index_to_select = 0  # Default to "None"
        for filename in sorted_filenames:
            source_prop = found_images[filename]
            self.image_listbox.insert(tk.END, filename)
            self.image_listbox_data.append((filename, source_prop))
            current_index = self.image_listbox.size() - 1

            # Set text color
            text_color = 'grey' if source_prop != current_prop_display_name else 'black'
            self.image_listbox.itemconfig(current_index, {'fg': text_color})

            # Check if this is the item we need to pre-select
            if not load_only and filename == selected_image and source_prop == current_prop_display_name:
                # Only auto-select if it's the current prop's image matching the saved one
                listbox_index_to_select = current_index
            elif not load_only and filename == selected_image and source_prop != current_prop_display_name and hint_name is not None:
                # If the saved image belongs to a cousin, maybe still highlight it but don't auto-select?
                # For now, we only auto-select if it belongs to the *current* prop.
                pass

        # Set the current image context (used by preview and update)
        # Important: image_dir now points to the *current* prop's dir, even though list shows cousins
        current_prop_image_dir = str(base_dir / current_prop_display_name)
        self.current_image_context = {
            'room_id': room_id,
            'prop_display_name': current_prop_display_name,  # The prop context for the editor
            'hint_name': hint_name,
            'image_dir': current_prop_image_dir  # Base directory for *potential* saves/previews of OWN images
        }

        # Set the initial selection in the listbox
        self.image_listbox.selection_clear(0, tk.END)
        self.image_listbox.selection_set(listbox_index_to_select)
        self.image_listbox.see(listbox_index_to_select)

        # Trigger preview if not just loading
        if not load_only:
            # Manually call preview for the initially selected item
            self.preview_selected_image()  # This will handle the "None" case too

    def preview_selected_image(self, event=None):
        selection = self.image_listbox.curselection()
        if not selection:
            self.clear_preview_and_selection()
            return

        selected_index = selection[0]
        if selected_index < 0 or selected_index >= len(self.image_listbox_data):
            print(f"Error: Invalid listbox index {selected_index}")
            self.clear_preview_and_selection()
            return

        filename, source_prop_display_name = self.image_listbox_data[selected_index]

        # Handle "None" selection
        if filename == "None":
            self.clear_preview_and_selection(update_hint=True)  # Update hint to remove image
            return

        # Check context (is a hint selected? what is its prop?)
        context_prop_display_name = None
        is_hint_selected = bool(self.selected_hint_key)

        if is_hint_selected:
            # Extract context prop from the selected hint key
            try:
                parts = self.selected_hint_key.split('-', 2)
                context_prop_display_name = parts[1]  # Assumes key format "roomid-propdisplay-hintname"
            except IndexError:
                print(f"Error parsing selected hint key: {self.selected_hint_key}")
                self.clear_preview_and_selection()
                return
        elif self.current_prop_info:
            # If only a prop is selected in the tree, get its display name
            context_prop_display_name = self.current_prop_info.get('display_name')
        else:
            # Should not happen if listbox is enabled, but safeguard
            print("Preview error: No hint or prop context available.")
            self.clear_preview_and_selection()
            return

        if not context_prop_display_name:
            print("Preview error: Could not determine context prop display name.")
            self.clear_preview_and_selection()
            return

        # Determine the correct image path based on the *source* prop
        room_id = self.current_image_context['room_id']  # Get room ID from context
        room_map = {'1': "casino", '2': "ma", '3': "wizard", '4': "zombie", '5': "haunted", '6': "atlantis", '7': "time"}
        room_folder = room_map.get(str(room_id))
        if not room_folder:
            print(f"Preview error: Cannot map room ID {room_id}")
            self.clear_preview_and_selection()
            return

        base_dir = Path(os.path.dirname(__file__)) / "sync_directory" / "hint_image_files" / room_folder
        image_path = base_dir / source_prop_display_name / filename

        # --- Image Belongs to a Cousin ---
        if source_prop_display_name != context_prop_display_name:
            if not is_hint_selected:
                # Only a prop selected - just show preview, don't allow move
                self.display_image_preview(image_path, filename)
                self.update_selected_image_label(f"{filename} (from {source_prop_display_name})")  # Indicate source
                return  # Do not update hint data or prompt

            # A hint is selected, prompt to move
            confirm = messagebox.askyesno(
                "Move Hint?",
                f"Image '{filename}' belongs to prop '{source_prop_display_name}'.\n\n"
                f"Move the current hint ('{self.hint_map[self.selected_hint_key]['hint_name']}') "
                f"to prop '{source_prop_display_name}' and use this image?",
                parent=self.settings_container  # Ensure popup is on top
            )

            if confirm:
                # Move the hint
                success = self.move_hint_to_cousin(self.selected_hint_key, source_prop_display_name, filename)
                if not success:
                    # Move failed, revert selection to None
                    self.clear_preview_and_selection(update_hint=False)  # Don't overwrite original hint's image yet
                    self.image_listbox.selection_clear(0, tk.END)
                    self.image_listbox.selection_set(0)  # Select "None"
            else:
                # User clicked No, select "None"
                self.clear_preview_and_selection(update_hint=True)  # Update original hint to have no image
                self.image_listbox.selection_clear(0, tk.END)
                self.image_listbox.selection_set(0)  # Select "None"

        # --- Image Belongs to the Current Prop (or move was successful) ---
        else:  # source_prop_display_name == context_prop_display_name
            preview_success = self.display_image_preview(image_path, filename)
            if preview_success and is_hint_selected:
                # Update the *currently selected* hint's image data
                self.update_hint_image(filename)  # Use existing method
            elif not preview_success and is_hint_selected:
                # Preview failed (e.g., file not found), ensure hint data reflects no image
                self.update_hint_image(None)

            # Update the label showing the selected file
            self.update_selected_image_label(filename)  # Use the method that checks existence

    def update_hint_image(self, filename):
        if not hasattr(self, 'current_image_context') or not self.current_image_context:
            return
        
        # If no hint is selected (prop selected instead), just skip updating hint data
        if not self.selected_hint_key:
             return

        room_id = self.current_image_context['room_id']
        prop_display_name = self.current_image_context['prop_display_name']
        hint_name = self.current_image_context['hint_name']

        # Skip validation for prop selection (where hint_name is None)
        if hint_name is None:
            return

        expected_key = f"{room_id}-{prop_display_name}-{hint_name}"
        if self.selected_hint_key != expected_key:
             print(f"Warning: Image context key '{expected_key}' does not match selected hint key '{self.selected_hint_key}'. Skipping update.")
             return

        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            room_data = hint_data.get('rooms', {}).get(str(room_id))
            if not room_data: raise KeyError(f"Room {room_id} not found in saved_hints.json")
            prop_data = room_data.get(prop_display_name)
            if not prop_data: raise KeyError(f"Prop {prop_display_name} not found in room {room_id}")
            hint_entry = prop_data.get(hint_name)
            if not hint_entry: raise KeyError(f"Hint {hint_name} not found in prop {prop_display_name}")

            if filename:
                 hint_entry['image'] = filename
            elif 'image' in hint_entry:
                 del hint_entry['image']

            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)

            if self.selected_hint_key in self.hint_map:
                 if filename:
                    self.hint_map[self.selected_hint_key]['data']['image'] = filename
                 elif 'image' in self.hint_map[self.selected_hint_key]['data']:
                    del self.hint_map[self.selected_hint_key]['data']['image']

            # Update the label after successfully changing the data
            self.update_selected_image_label(filename)

        except FileNotFoundError:
             messagebox.showerror("Error", "saved_hints.json not found.")
             print("Error updating hint image: saved_hints.json not found.")
        except KeyError as e:
             messagebox.showerror("Error", f"Data structure error updating image: {e}")
             print(f"Error updating hint image due to KeyError: {e}")
        except json.JSONDecodeError as e:
             messagebox.showerror("Error", f"Error reading saved_hints.json: {e}")
             print(f"Error updating hint image due to JSONDecodeError: {e}")
        except Exception as e:
            print(f"Error updating hint image: {e}")
            messagebox.showerror("Error", f"Failed to update image: {e}")

    def autosave_hint(self):
        if self.text_widget.cget('state') == tk.DISABLED or self.selected_hint_key is None:
             if self.autosave_after_id:
                 self.status_label.after_cancel(self.autosave_after_id)
                 self.autosave_after_id = None
             return

        if not self.text_widget.edit_modified():
             return

        if self.autosave_after_id:
            self.status_label.after_cancel(self.autosave_after_id)

        self.status_label.config(text="Saving...", foreground='orange')
        self.autosave_after_id = self.status_label.after(750, self.save_hint_changes)

    def save_hint_changes(self):
        if self.selected_hint_key is None:
            print("Save attempt failed: No hint selected.")
            self.status_label.config(text="Error: No hint selected", foreground='red')
            self.status_label.after(2000, lambda: self.status_label.config(text=""))
            return

        if not self.text_widget.edit_modified():
             if self.status_label.cget('text') == "Saving...":
                 self.status_label.config(text="")
             return

        if self.selected_hint_key not in self.hint_map:
            print(f"Save attempt failed: Selected hint key '{self.selected_hint_key}' not found in map.")
            self.status_label.config(text="Error: Hint data mismatch", foreground='red')
            self.status_label.after(2000, lambda: self.status_label.config(text=""))
            return

        try:
            new_text = self.text_widget.get('1.0', 'end-1c').strip()
            room_id = self.hint_map[self.selected_hint_key]['room_id']
            prop_display_name = self.hint_map[self.selected_hint_key]['prop_display_name']
            hint_name = self.hint_map[self.selected_hint_key]['hint_name']

            with open('saved_hints.json', 'r') as f:
                hint_data_file = json.load(f)

            room_data = hint_data_file.get('rooms', {}).get(str(room_id))
            if not room_data: raise KeyError(f"Room {room_id} not found")
            prop_data = room_data.get(prop_display_name)
            if not prop_data: raise KeyError(f"Prop {prop_display_name} not found")
            hint_entry = prop_data.get(hint_name)
            if not hint_entry: raise KeyError(f"Hint {hint_name} not found")

            hint_entry['text'] = new_text

            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data_file, f, indent=4)

            self.hint_map[self.selected_hint_key]['data']['text'] = new_text

            self.status_label.config(text="Saved!", foreground='green')
            self.status_label.after(1500, lambda: self.status_label.config(text=""))
            self.text_widget.edit_modified(False)
            self.autosave_after_id = None

        except FileNotFoundError:
             messagebox.showerror("Error", "saved_hints.json not found.")
             self.status_label.config(text="Error: File not found!", foreground='red')
        except KeyError as e:
             messagebox.showerror("Error", f"Data structure error saving text: {e}")
             print(f"[hint library]Error saving hint changes (KeyError): {e}")
             self.status_label.config(text="Error saving!", foreground='red')
        except json.JSONDecodeError as e:
             messagebox.showerror("Error", f"Error reading saved_hints.json: {e}")
             self.status_label.config(text="Error reading file!", foreground='red')
        except Exception as e:
            print(f"[hint library]Error saving hint changes: {e}")
            self.status_label.config(text="Error saving!", foreground='red')

        if self.autosave_after_id and self.status_label.cget('text') == "Saving...":
             self.status_label.config(text="Error saving!", foreground='red')

        self.autosave_after_id = None

    def rename_selected_hint(self):
        if not self.selected_hint_key:
            messagebox.showwarning("Warning", "No hint selected to rename.")
            return

        old_hint_info = self.hint_map.get(self.selected_hint_key)
        if not old_hint_info:
            messagebox.showerror("Error", "Could not find data for the selected hint.")
            return

        new_hint_name = self.rename_entry.get().strip()
        old_hint_name = old_hint_info['hint_name']

        if not new_hint_name:
            messagebox.showerror("Error", "New hint name cannot be empty.")
            return

        if new_hint_name == old_hint_name:
            # No change, do nothing silently
            return

        room_id = old_hint_info['room_id']
        prop_display_name = old_hint_info['prop_display_name']

        # Check if the new name already exists under the same prop
        new_hint_key = f"{room_id}-{prop_display_name}-{new_hint_name}"
        if new_hint_key in self.hint_map:
            messagebox.showerror("Error", f"A hint named '{new_hint_name}' already exists for this prop.")
            # Revert the entry widget to the old name
            self.rename_entry.delete(0, tk.END)
            self.rename_entry.insert(0, old_hint_name)
            return

        # Confirmation (optional, but good practice)
        # if not messagebox.askyesno("Confirm Rename", f"Rename hint '{old_hint_name}' to '{new_hint_name}'?"):
        #     self.rename_entry.delete(0, tk.END)
        #     self.rename_entry.insert(0, old_hint_name)
        #     return

        try:
            with open('saved_hints.json', 'r') as f:
                hint_data_file = json.load(f)

            # Navigate safely
            room_data = hint_data_file.get('rooms', {}).get(str(room_id))
            if not room_data: raise KeyError(f"Room {room_id} not found")
            prop_data = room_data.get(prop_display_name)
            if not prop_data: raise KeyError(f"Prop {prop_display_name} not found")

            if old_hint_name not in prop_data:
                raise KeyError(f"Original hint '{old_hint_name}' not found in saved data.")

            # Preserve data, remove old entry, add new entry
            hint_content = prop_data.pop(old_hint_name)
            prop_data[new_hint_name] = hint_content

            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data_file, f, indent=4)

            # --- Update internal state ---
            # Remove old mapping
            del self.hint_map[self.selected_hint_key]
            # Add new mapping
            new_hint_full_info = {
                "room_id": room_id,
                "prop_display_name": prop_display_name,
                "hint_name": new_hint_name,
                "data": hint_content
            }
            self.hint_map[new_hint_key] = new_hint_full_info
            # Update the selected key itself!
            self.selected_hint_key = new_hint_key

            # Update tree_items map (find the tree item ID associated with the old key and update its key)
            selected_tree_id = self.hint_tree.selection()[0] # Should still be selected
            if selected_tree_id and self.tree_items.get(selected_tree_id, {}).get('type') == 'hint':
                 self.tree_items[selected_tree_id]['key'] = new_hint_key
                 # Update the text displayed in the Treeview
                 self.hint_tree.item(selected_tree_id, text=new_hint_name)
            else:
                 print("Warning: Could not find or update selected tree item after rename.")
                 # Consider reloading the whole tree as a fallback if this happens often
                 # self.load_hints()

            # Update image context if it exists and matches
            if hasattr(self, 'current_image_context') and self.current_image_context:
                 if (self.current_image_context['room_id'] == room_id and
                     self.current_image_context['prop_display_name'] == prop_display_name and
                     self.current_image_context['hint_name'] == old_hint_name):
                     self.current_image_context['hint_name'] = new_hint_name

            # Update the hint name label
            self.selected_hint_name_label.config(text=f"Editing Hint: {new_hint_name}")

            self.status_label.config(text="Hint renamed.", foreground='green')
            self.status_label.after(2000, lambda: self.status_label.config(text=""))

        except FileNotFoundError:
             messagebox.showerror("Error", "saved_hints.json not found.")
             self.status_label.config(text="Error: File not found!", foreground='red')
        except KeyError as e:
             messagebox.showerror("Error", f"Data structure error during rename: {e}")
             print(f"[hint library]Error renaming hint (KeyError): {e}")
             self.status_label.config(text="Error renaming!", foreground='red')
             # Revert entry on error
             self.rename_entry.delete(0, tk.END)
             self.rename_entry.insert(0, old_hint_name)
        except json.JSONDecodeError as e:
             messagebox.showerror("Error", f"Error reading saved_hints.json: {e}")
             self.status_label.config(text="Error reading file!", foreground='red')
        except Exception as e:
            print(f"[hint library]Error renaming hint: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred during rename: {e}")
            self.status_label.config(text="Error renaming!", foreground='red')
            # Revert entry on error
            self.rename_entry.delete(0, tk.END)
            self.rename_entry.insert(0, old_hint_name)

    def add_new_hint(self):
        if not self.current_prop_info:
             messagebox.showwarning("Warning", "Please select a prop in the tree before adding a hint.")
             return

        room_id = self.current_prop_info['room_id']
        prop_display_name = self.current_prop_info['display_name']

        # Ask user for the new hint name
        new_hint_name = simpledialog.askstring("New Hint Name",
                                               f"Enter a name for the new hint under '{prop_display_name}':",
                                               parent=self.settings_container)

        if not new_hint_name:
            return

        new_hint_name = new_hint_name.strip()
        if not new_hint_name:
            messagebox.showerror("Error", "Hint name cannot be empty.")
            return

        # *** Use display_name for key generation for hint_map ***
        new_hint_key = f"{room_id}-{prop_display_name}-{new_hint_name}"
        # *** Check hint_map for conflicts based on display_name key ***
        if new_hint_key in self.hint_map:
            messagebox.showerror("Error", f"A hint named '{new_hint_name}\' already exists for prop '{prop_display_name}' in the save file.")
            return # Prevent overwriting just in case hint_map was out of sync

        new_hint_data = {"text": ""}

        try:
            try:
                with open('saved_hints.json', 'r') as f:
                    content = f.read().strip()
                    if not content:
                        # File exists but is empty
                        hint_data_file = {"rooms": {}}
                    else:
                        hint_data_file = json.loads(content)
            except FileNotFoundError:
                hint_data_file = {"rooms": {}}
            except json.JSONDecodeError:
                # File exists but is corrupt
                hint_data_file = {"rooms": {}}

            if 'rooms' not in hint_data_file:
                 hint_data_file['rooms'] = {}
            if str(room_id) not in hint_data_file['rooms']:
                 hint_data_file['rooms'][str(room_id)] = {}

            # *** Use display_name as the key when writing to the JSON file structure ***
            if prop_display_name not in hint_data_file['rooms'][str(room_id)]:
                 hint_data_file['rooms'][str(room_id)][prop_display_name] = {}

            # Check conflict again directly in the dictionary using display_name key
            if new_hint_name in hint_data_file['rooms'][str(room_id)][prop_display_name]:
                 messagebox.showerror("Error", f"A hint named '{new_hint_name}\' already exists for prop '{prop_display_name}' in the save file.")
                 return # Prevent overwriting just in case hint_map was out of sync

            # Add the new hint using display_name key
            hint_data_file['rooms'][str(room_id)][prop_display_name][new_hint_name] = new_hint_data

            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data_file, f, indent=4)

            print(f"Added new hint \'{new_hint_name}\' to prop \'{prop_display_name}\' in room \'{room_id}\'")

            # --- Refresh and Select New Hint ---
            # Store current selection/scroll state if desired (optional)
            # selected_prop_id = self.hint_tree.selection()[0] if self.hint_tree.selection() else None

            self.load_hints() # Reload the tree

            # Find the tree item ID for the new hint
            new_item_id = None
            for item_id, item_data in self.tree_items.items():
                if item_data.get('key') == new_hint_key:
                    new_item_id = item_id
                    break

            if new_item_id:
                # Ensure parent nodes are open
                parent_prop = self.hint_tree.parent(new_item_id)
                if parent_prop:
                    self.hint_tree.item(parent_prop, open=True)
                    parent_room = self.hint_tree.parent(parent_prop)
                    if parent_room:
                        self.hint_tree.item(parent_room, open=True)

                # Select, focus, and scroll to the new item
                self.hint_tree.selection_set(new_item_id)
                self.hint_tree.focus(new_item_id)
                self.hint_tree.see(new_item_id)
                print(f"Selected newly added hint item: {new_item_id}")
                # Calling selection_set should trigger on_hint_select, enabling the editor
            else:
                print(f"Warning: Could not find tree item for new hint key {new_hint_key} after reload.")
                # Maybe re-select the original prop as fallback?
                # if selected_prop_id:
                #     self.hint_tree.selection_set(selected_prop_id)

            self.status_label.config(text="New hint added.", foreground='green')
            self.status_label.after(2000, lambda: self.status_label.config(text=""))

        except json.JSONDecodeError as e:
             messagebox.showerror("Error", f"Error reading/writing saved_hints.json: {e}")
             self.status_label.config(text="Error accessing file!", foreground='red')
        except Exception as e:
            print(f"[hint library]Error adding new hint: {e}")
            messagebox.showerror("Error", f"An unexpected error occurred adding the hint: {e}")
            self.status_label.config(text="Error adding hint!", foreground='red')

    def update_selected_image_label(self, filename_or_full_text):
        """Updates the label showing the selected image filename and status.
           Can accept just filename or filename + source info."""
        label_widget = self.selected_image_label  # Reference to the label widget

        # If context is missing (e.g., prop selected, not hint), clear or show default
        if not hasattr(self, 'current_image_context') or not self.current_image_context:
            try:
                label_widget.config(text="Selected Image: N/A", foreground='grey')
            except Exception as e:
                print(f"[hint library]Error updating selected image label (no context): {e}")
            return

        if filename_or_full_text and filename_or_full_text != "None":
            # If the text already includes source info (from cousin selection), use it directly
            if "(from " in filename_or_full_text:
                label_widget.config(text=f"Selected Image: {filename_or_full_text}", foreground='darkorange')  # Use orange for cousin images
            else:
                # Otherwise, check the file from the *current* prop's context directory
                filename = filename_or_full_text  # Assume it's just the filename
                image_path = Path(self.current_image_context['image_dir']) / filename
                try:
                    if image_path.is_file():
                        label_widget.config(text=f"Selected Image: {filename}", foreground='black')
                    else:
                        label_widget.config(text=f"Selected Image: {filename} (Not found!)", foreground='red')
                except OSError as e:
                    print(f"[hint library]Error checking image file status {image_path}: {e}")
                    label_widget.config(text=f"Selected Image: {filename} (Check Error!)", foreground='orange')
        else:
            # Handle "None" or empty filename
            label_widget.config(text="Selected Image: None", foreground='black')

    def launch_image_browser(self):
        """Launch the image browser as a separate process."""
        import subprocess
        import sys
        import os
        
        try:
            # Get the correct script path
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "image_browser.py")
            # Use the same Python executable that's running this script
            python_exe = sys.executable
            
            # Set the working directory to the root of the project
            # This ensures image_browser.py can find the admin/sync_directory path correctly
            working_dir = os.path.dirname(os.path.dirname(__file__))
            
            # Launch with the correct working directory
            subprocess.Popen([python_exe, script_path], cwd=working_dir)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Image Browser: {e}")

    def launch_image_cropper(self):
        """Launch the image cropper as a separate process."""
        import subprocess
        import sys
        import os
        
        try:
            # Get the correct script path
            script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tools", "cropper.py")
            # Use the same Python executable that's running this script
            python_exe = sys.executable
            
            # Set the working directory to the root of the project
            working_dir = os.path.dirname(os.path.dirname(__file__))
            
            # Launch with the correct working directory
            subprocess.Popen([python_exe, script_path], cwd=working_dir)
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch Image Cropper: {e}")

    def refresh_image_selector(self):
        """Refresh the image list for the current prop."""
        if not hasattr(self, 'current_image_context') or not self.current_image_context:
            return
        
        room_id = self.current_image_context.get('room_id')
        prop_display_name = self.current_image_context.get('prop_display_name')
        hint_name = self.current_image_context.get('hint_name')
        selected_image = None
        
        # If we have a currently selected hint with an image, preserve that selection
        if self.selected_hint_key and self.selected_hint_key in self.hint_map:
            selected_image = self.hint_map[self.selected_hint_key]['data'].get('image')
        
        self.show_image_selector(room_id, prop_display_name, hint_name, selected_image)
        self.status_label.config(text="Images refreshed.", foreground='green')
        self.status_label.after(2000, lambda: self.status_label.config(text=""))

    def clear_cousin_highlights(self):
        """Removes the cousin highlight tag from previously highlighted items."""
        if not self.hint_tree: return  # Safety check
        try:
            for item_id in self.highlighted_cousin_items:
                if self.hint_tree.exists(item_id):  # Check if item still exists
                    current_tags = list(self.hint_tree.item(item_id, 'tags'))
                    if 'cousin_highlight' in current_tags:
                        current_tags.remove('cousin_highlight')
                        self.hint_tree.item(item_id, tags=tuple(current_tags))
        except tk.TclError as e:
            print(f"[Hint Manager] Mild TclError during highlight clear: {e}")
        except Exception as e:
            print(f"[Hint Manager] Error clearing highlights: {e}")
        finally:
            self.highlighted_cousin_items.clear()

    def on_item_motion(self, event):
        """Handles mouse motion over the tree, detecting entering new items."""
        if not self.hint_tree: return
        try:
            item_id = self.hint_tree.identify_row(event.y)
        except tk.TclError:
            item_id = None  # Error identifying row

        if not item_id:
            self.clear_cousin_highlights()
            return

        if item_id in self.highlighted_cousin_items:
            return

        self.clear_cousin_highlights()

        item_info = self.tree_items.get(item_id)
        if not item_info or item_info.get('type') != 'prop':
            return

        room_id = item_info.get('room_id')
        prop_internal_name = item_info.get('prop_name')

        if not room_id or not prop_internal_name:
            return

        prop_details = self.get_prop_details(room_id, prop_internal_name)
        target_cousin_id = prop_details.get('cousin') if prop_details else None

        if target_cousin_id is None:
            return

        for other_item_id, other_info in self.tree_items.items():
            if (other_info.get('type') == 'prop' and
                other_info.get('room_id') == room_id):
                other_prop_internal_name = other_info.get('prop_name')
                if not other_prop_internal_name: continue

                other_prop_details = self.get_prop_details(room_id, other_prop_internal_name)
                other_cousin_id = other_prop_details.get('cousin') if other_prop_details else None

                if other_cousin_id == target_cousin_id:
                    if self.hint_tree.exists(other_item_id):
                        current_tags = list(self.hint_tree.item(other_item_id, 'tags'))
                        if 'cousin_highlight' not in current_tags:
                            current_tags.append('cousin_highlight')
                            self.hint_tree.item(other_item_id, tags=tuple(current_tags))
                        self.highlighted_cousin_items.add(other_item_id)

    def on_tree_leave(self, event):
        """Clears highlights when the mouse leaves the Treeview widget entirely."""
        self.clear_cousin_highlights()

    def move_hint_to_cousin(self, hint_key_to_move, target_prop_display_name, new_image_filename):
        """Moves a hint to a different prop (cousin) in saved_hints.json and refreshes."""
        try:
            # 1. Extract info from the key
            parts = hint_key_to_move.split('-', 2)
            room_id = parts[0]
            original_prop_display_name = parts[1]
            hint_name = parts[2]

            # 2. Load hint data file
            try:
                with open('saved_hints.json', 'r') as f:
                    hint_data_file = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                messagebox.showerror("Error", f"Failed to load saved_hints.json: {e}")
                return False

            # 3. Get the hint data to move
            rooms_data = hint_data_file.get('rooms', {})
            original_room_hints = rooms_data.get(str(room_id), {})
            original_prop_hints = original_room_hints.get(original_prop_display_name, {})
            hint_content_to_move = original_prop_hints.get(hint_name)

            if hint_content_to_move is None:
                messagebox.showerror("Error", f"Could not find original hint '{hint_name}' under prop '{original_prop_display_name}' to move.")
                return False

            # Preserve text, update image
            moved_hint_data = {
                "text": hint_content_to_move.get("text", ""),  # Keep original text
                "image": new_image_filename  # Set the new image
            }

            # 4. Delete from original location
            del original_prop_hints[hint_name]
            print(f"Removed hint '{hint_name}' from '{original_prop_display_name}'")
            # Optional: Clean up empty prop/room dictionaries if desired
            if not original_prop_hints:
                del original_room_hints[original_prop_display_name]
                print(f"Removed empty prop '{original_prop_display_name}'")
                if not original_room_hints:
                    del rooms_data[str(room_id)]
                    print(f"Removed empty room '{room_id}'")

            # 5. Add to new location
            target_room_hints = rooms_data.setdefault(str(room_id), {})
            target_prop_hints = target_room_hints.setdefault(target_prop_display_name, {})

            # Check for overwrite (optional but recommended)
            if hint_name in target_prop_hints:
                if not messagebox.askyesno("Overwrite Confirmation",
                                            f"A hint named '{hint_name}' already exists under '{target_prop_display_name}'.\n\nOverwrite it?",
                                            parent=self.settings_container):
                    # User cancelled overwrite - need to revert the deletion? Or just stop?
                    # For simplicity now, we stop, but the original is already deleted.
                    # A better implementation would copy first, then delete on success.
                    print("Move cancelled due to potential overwrite.")
                    # Reload might be needed to restore state if we stopped mid-way
                    self.load_hints()
                    return False  # Indicate failure

            target_prop_hints[hint_name] = moved_hint_data
            print(f"Added hint '{hint_name}' to '{target_prop_display_name}' with image '{new_image_filename}'")

            # 6. Save changes
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data_file, f, indent=4)

            # 7. Refresh UI and select the moved hint
            new_hint_key = f"{room_id}-{target_prop_display_name}-{hint_name}"
            self.load_hints()  # Reload tree and internal maps

            # Find the new item ID in the refreshed tree
            new_item_id = None
            for item_id, item_data in self.tree_items.items():
                if item_data.get('key') == new_hint_key:
                    new_item_id = item_id
                    break

            if new_item_id:
                # Ensure parent nodes are open
                parent_prop = self.hint_tree.parent(new_item_id)
                if parent_prop:
                    self.hint_tree.item(parent_prop, open=True)
                    parent_room = self.hint_tree.parent(parent_prop)
                    if parent_room:
                        self.hint_tree.item(parent_room, open=True)

                # Select, focus, and scroll to the new item
                self.hint_tree.selection_set(new_item_id)
                self.hint_tree.focus(new_item_id)
                self.hint_tree.see(new_item_id)
                # on_hint_select should be triggered by selection_set, updating the editor
                print(f"Successfully moved and selected hint item: {new_item_id}")
                self.status_label.config(text="Hint moved successfully.", foreground='green')
                self.status_label.after(2500, lambda: self.status_label.config(text=""))
                return True  # Indicate success
            else:
                print(f"Warning: Could not find tree item for moved hint key {new_hint_key} after reload.")
                messagebox.showinfo("Move Complete", "Hint moved, but could not automatically select it in the tree. Please find it manually.", parent=self.settings_container)
                return True  # Move succeeded, selection failed

        except KeyError as e:
            messagebox.showerror("Error", f"Data structure error during move: Missing key {e}", parent=self.settings_container)
            print(f"[hint library]KeyError during move: {e}")
            # Consider reloading hints to try and restore a consistent state
            self.load_hints()
            return False
        except Exception as e:
            messagebox.showerror("Error", f"An unexpected error occurred moving the hint: {e}", parent=self.settings_container)
            print(f"[hint library]Error moving hint: {e}")
            # Consider reloading hints
            self.load_hints()
            return False

    def display_image_preview(self, image_path, filename):
        """Attempts to load and display the image preview. Returns True on success."""
        try:
            if not image_path.is_file():
                raise FileNotFoundError(f"Path is not a file: {image_path}")

            image = Image.open(str(image_path))
            image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(image)
            self.image_preview_label.config(image=photo, text="") # Clear any error text
            self.image_preview_label.image = photo
            return True
        except FileNotFoundError:
            print(f"[hint library]Preview Error: Image file not found at {image_path}")
            try:
                self.image_preview_label.config(text="Image not found", image='', foreground='red')
                self.image_preview_label.image = None
            except Exception as e:
                print(f"[hint library]Error clearing preview after not found: {e}")
            return False
        except Exception as e:
            print(f"[hint library]Error displaying image preview for {image_path}: {e}")
            try:
                self.image_preview_label.config(text=f"Preview Error", image='', foreground='red') # Keep error msg short
                self.image_preview_label.image = None
            except Exception as e2:
                print(f"[hint library]Error clearing preview after error: {e2}")
            return False

    def clear_preview_and_selection(self, update_hint=False):
         """Clears the preview, label, and optionally updates the hint data."""
         try:
             self.image_preview_label.config(text="", image='') # Clear text and image
             self.image_preview_label.image = None
         except Exception as e:
             print(f"[hint library]Error clearing image preview: {e}")
         self.update_selected_image_label(None) # Update label to "None"

         if update_hint and self.selected_hint_key:
             # Update hint data only if requested and a hint is selected
             self.update_hint_image(None)

class AdminPasswordManager:
    def __init__(self, app):
        self.app = app
        self.hashed_password = self.load_hashed_password()

    def load_hashed_password(self):
        password_file = Path("hint_manager_password.txt")
        if password_file.exists():
            with open(password_file, 'r') as f:
                return f.read().strip()
        else:
            default_pass = "admin"
            hashed_default = hashlib.sha256(default_pass.encode()).hexdigest()
            with open(password_file, 'w') as f:
                f.write(hashed_default)
            print(f"[password manager]Password file created with default password for 'admin'")
            return hashed_default

    def verify_password(self, callback=None):
        login_window = tk.Toplevel(self.app.root)
        login_window.title("Enter Password (DO NOT RUN SYNC DURING GAMES!)")
        login_window.geometry("400x150")
        tk.Label(login_window, text="Password:", font=('Arial', 12)).pack(pady=10)
        password_entry = tk.Entry(login_window, show="*", width=40)
        password_entry.pack(pady=5)

        def validate():
            entered_password = password_entry.get()
            hashed_entered = hashlib.sha256(entered_password.encode()).hexdigest()
            if hashed_entered == self.hashed_password:
                login_window.destroy()
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", "Incorrect password.")

        def on_close():
            login_window.destroy()

        password_entry.bind('<Return>', lambda e: validate())
        login_window.protocol("WM_DELETE_WINDOW", on_close)
        login_button = tk.Button(login_window, text="Login", command=validate)
        login_button.pack(pady=10)
        login_window.transient(self.app.root)
        login_window.grab_set()
        password_entry.focus_set()
        self.app.root.wait_window(login_window)