import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import os
from PIL import Image, ImageTk
import shutil
import hashlib  # For simple password storage

class CollapsibleFrame(ttk.Frame):
    def __init__(self, parent, text, **kwargs):
        ttk.Frame.__init__(self, parent, **kwargs)
        self.columnconfigure(0, weight=1)

        self.show = tk.BooleanVar(value=False)
        self.toggle_button = ttk.Checkbutton(
            self,
            text=text,
            command=self.toggle,
            style='Toolbutton',
            variable=self.show
        )
        self.toggle_button.grid(row=0, column=0, sticky='ew')

        self.sub_frame = ttk.Frame(self)
        self.sub_frame.grid(row=1, column=0, sticky='nsew')
        self.sub_frame.grid_remove()

    def toggle(self):
        if bool(self.show.get()):
            self.sub_frame.grid()
        else:
            self.sub_frame.grid_remove()

class ManagerSettings:
    def __init__(self, app, admin_interface):
        self.app = app
        self.admin_interface = admin_interface
        self.main_container = None
        # self.original_widgets = []  # No longer needed
        self.load_prop_mappings()
        self.password_manager = AdminPasswordManager(app)
        self.current_page = None
        self.autosave_after_id = None  # Store the after() ID for debouncing

    def load_prop_mappings(self):
        """Load prop name mappings from JSON"""
        try:
            with open('prop_name_mapping.json', 'r') as f:
                self.prop_mappings = json.load(f)
        except Exception as e:
            print(f"[hint library]Error loading prop mappings: {e}")
            self.prop_mappings = {}

    def get_display_name(self, room_id, prop_name):
        """Get the display name for a prop from the mappings"""
        # Map numeric room IDs to their corresponding keys
        room_mapping = {
            '1': 'casino_ma',
            '2': 'wizard',
            '3': 'haunted',
            '4': 'zombie',
            '5': 'wizard',
            '6': 'atlantis',
            '7': 'time_machine'
        }

        room_key = room_mapping.get(str(room_id))
        if not room_key:
            return prop_name

        if room_key in self.prop_mappings:
            room_mappings = self.prop_mappings[room_key]['mappings']
            if prop_name in room_mappings:
                return room_mappings[prop_name]['display']
        return prop_name

    def check_credentials(self):
        """Prompt for credentials and validate them."""
        def on_success():
            self.create_hint_management_view()

        return self.password_manager.verify_password(callback=on_success)


    def show_hint_manager(self):
        """Show the hint management interface in a new window."""

        # Directly create the hint management view without password check in initial call
        self.check_credentials()

    def change_password(self):
        """Prompt for old password, new password, and save the new hash"""
        change_window = tk.Toplevel(self.app.root)
        change_window.title("Change Password")
        change_window.geometry("300x250")

        # Old password entry
        tk.Label(change_window, text="Old Password:", font=('Arial', 12)).pack(pady=5)
        old_password_entry = tk.Entry(change_window, show="*", width=20)
        old_password_entry.pack(pady=5)

        # New password entry
        tk.Label(change_window, text="New Password:", font=('Arial', 12)).pack(pady=5)
        new_password_entry = tk.Entry(change_window, show="*", width=20)
        new_password_entry.pack(pady=5)

        # Confirm new password entry
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

            # Hash and save new password
            self.password_manager.hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
            with open("hint_manager_password.txt", 'w') as f:
                f.write(self.password_manager.hashed_password)

            messagebox.showinfo("Success", "Password changed successfully.")
            change_window.destroy()

        # Bind Enter key to save_new_password for all entry fields
        old_password_entry.bind('<Return>', lambda e: new_password_entry.focus())
        new_password_entry.bind('<Return>', lambda e: confirm_password_entry.focus())
        confirm_password_entry.bind('<Return>', lambda e: save_new_password())

        change_button = tk.Button(change_window, text="Save Changes", command=save_new_password)
        change_button.pack(pady=10)

        change_window.transient(self.app.root)
        change_window.grab_set()

        # Focus the old password entry
        old_password_entry.focus_set()

        self.app.root.wait_window(change_window)

    def create_hint_management_view(self):
        """Create the hint management interface in a new window."""
        settings_window = tk.Toplevel(self.app.root)  # Create a new window
        settings_window.title("Settings")
        settings_window.geometry("800x600")  # Adjust size as needed

        self.main_container = ttk.Frame(settings_window)  # Use the new window
        self.main_container.pack(fill='both', expand=True, padx=10, pady=5)

        # Create header (without back button)
        header_frame = ttk.Frame(self.main_container)
        header_frame.pack(fill='x', pady=(0, 10))

        # Create settings navigation frame
        nav_frame = ttk.Frame(self.main_container)
        nav_frame.pack(fill='x', pady=(0, 10))

        # Create buttons for different settings pages
        hint_btn = ttk.Button(
            nav_frame,
            text="Hint Management",
            command=lambda: self.show_settings_page('hints')
        )
        hint_btn.pack(side='left', padx=5)

        password_btn = ttk.Button(
            nav_frame,
            text="Password Settings",
            command=lambda: self.show_settings_page('password')
        )
        password_btn.pack(side='left', padx=5)

        # Create container for settings pages
        self.settings_container = ttk.Frame(self.main_container)
        self.settings_container.pack(fill='both', expand=True)

        # Show hints page by default
        self.show_settings_page('hints')



    def show_settings_page(self, page):
        """Switch to the specified settings page"""
        # Clear current page
        for widget in self.settings_container.winfo_children():
            widget.destroy()

        self.current_page = page

        if page == 'hints':
            self.create_hints_page()
        elif page == 'password':
            self.create_password_page()

    def create_hints_page(self):
        """Create the hints management page"""
        # Create scrollable frame for hints
        canvas = tk.Canvas(self.settings_container)
        scrollbar = ttk.Scrollbar(self.settings_container, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack scrolling components
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Load and display hints
        self.load_hints()

    def create_password_page(self):
        """Create the password management page"""
        password_frame = ttk.Frame(self.settings_container)
        password_frame.pack(fill='both', expand=True, padx=20, pady=20)

        ttk.Label(
            password_frame,
            text="Password Management",
            font=('Arial', 12, 'bold')
        ).pack(pady=(0, 20))

        change_pass_btn = ttk.Button(
            password_frame,
            text="Change Admin Password",
            command=self.change_password
        )
        change_pass_btn.pack(pady=10)

    def load_hints(self):
        """Load and display all hints from saved_hints.json"""
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            # Clear existing hint displays
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()

            # Room ID to name mapping
            room_mapping = {
                '1': 'casino_ma',
                '2': 'wizard',
                '3': 'haunted',
                '4': 'zombie',
                '5': 'wizard',
                '6': 'atlantis',
                '7': 'time_machine'
            }

            # Display hints by room
            for room_id, room_data in hint_data.get('rooms', {}).items():
                mapped_room = room_mapping.get(str(room_id))
                room_frame = CollapsibleFrame(
                    self.scrollable_frame,
                    text=f"Room: {room_id}"
                )
                room_frame.pack(fill='x', padx=5, pady=2)

                # Create collapsible sections for each prop
                for prop_name, prop_hints in room_data.items():
                    display_name = self.get_display_name(room_id, prop_name)
                    print(f"[hint library]Room: {room_id} -> {mapped_room}, Prop: {prop_name} -> {display_name}")

                    prop_frame = CollapsibleFrame(
                        room_frame.sub_frame,
                        text=f"Prop: {display_name}"
                    )
                    prop_frame.pack(fill='x', padx=5, pady=2)

                    # Add hints for this prop
                    for hint_name, hint_info in prop_hints.items():
                        hint_display = self.create_hint_display(
                            prop_frame.sub_frame,
                            room_id,
                            display_name,
                            hint_name,
                            hint_info
                        )
                        hint_display.pack(fill='x', padx=5, pady=2)

        except Exception as e:
            print(f"[hint library]Error loading hints: {e}")

    def get_image_path(self, room_id, prop_display_name, image_filename):
        """Construct the full path to a hint image based on room and prop"""
        if not image_filename:
            return None

        # Map room IDs to their folder names
        room_map = {
            '1': "casino",
            '2': "ma",
            '3': "wizard",
            '4': "zombie",
            '5': "haunted",
            '6': "atlantis",
            '7': "time"
        }

        room_folder = room_map.get(str(room_id), "").lower()
        if not room_folder:
            return None

        # Construct path: sync_directory/hint_image_files/room/prop/image
        image_path = os.path.join(
            os.path.dirname(__file__),
            "sync_directory",
            "hint_image_files",
            room_folder,
            prop_display_name,
            image_filename
        )

        return image_path if os.path.exists(image_path) else None

    def create_hint_display(self, parent, room_id, prop_display_name, hint_name, hint_info):
        """Create a display frame for a single hint"""
        hint_frame = ttk.Frame(parent)

        # Create header with hint name
        header_frame = ttk.Frame(hint_frame)
        header_frame.pack(fill='x', pady=(2,0))

        name_label = ttk.Label(
            header_frame,
            text=f"Name: {hint_name}",
            font=('Arial', 9, 'bold')
        )
        name_label.pack(side='left')

        # Create text display
        text_frame = ttk.Frame(hint_frame)
        text_frame.pack(fill='x', pady=2)

        text_widget = tk.Text(
            text_frame,
            height=3,
            width=40,
            wrap=tk.WORD
        )
        text_widget.insert('1.0', hint_info.get('text', ''))
        text_widget.pack(side='left', fill='x', expand=True)

        # Add a status label for save feedback
        self.status_label = ttk.Label(text_frame, text="")  # Use self for access
        self.status_label.pack(side='left', padx=5)


        # Delete button
        delete_button = ttk.Button(
            header_frame,
            text="Delete",
            command=lambda: self.delete_hint(room_id, prop_display_name, hint_name)
        )
        delete_button.pack(side='right')

        # --- Autosave Setup ---
        text_widget.bind("<<Modified>>", lambda event, r_id=room_id, p_name=prop_display_name, h_name=hint_name, t_widget=text_widget:
                         self.autosave_hint(r_id, p_name, h_name, t_widget))


        # --- Image Selection ---
        image_frame = ttk.Frame(hint_frame)
        image_frame.pack(fill='x', pady=2)

        # "Select Image" button
        select_image_btn = ttk.Button(
            image_frame,
            text="Select Image",
            command=lambda r_id=room_id, p_name=prop_display_name, h_name=hint_name: self.show_image_selector(r_id, p_name, h_name)
        )
        select_image_btn.pack(side='left', padx=5)
        
        # Image controls (listbox and preview - initially hidden)
        self.image_listbox = tk.Listbox(
            image_frame,
            height=4,
            width=30,
            selectmode=tk.SINGLE,
            exportselection=False
        )
        self.image_listbox.bind('<<ListboxSelect>>', self.preview_selected_image)

        self.image_preview_label = ttk.Label(image_frame)  # For image preview


        # Hint image if present (display existing image)
        if hint_info.get('image'):
            try:
                # Get path using room, prop display name, and image filename
                image_path = self.get_image_path(room_id, prop_display_name, hint_info['image'])

                # Create image info frame
                image_info_frame = ttk.Frame(hint_frame)
                image_info_frame.pack(fill='x', pady=2)

                # Show image filename
                ttk.Label(
                    image_info_frame,
                    text=f"Image: {hint_info['image']}",
                    font=('Arial', 9)
                ).pack(side='left')

                if image_path and os.path.exists(image_path):
                    # Show relative path from sync_directory
                    rel_path = os.path.relpath(
                        image_path,
                        os.path.join(os.path.dirname(__file__), "sync_directory")
                    )
                    ttk.Label(
                        image_info_frame,
                        text=f"Path: {rel_path}",
                        foreground='green'
                    ).pack(side='left', padx=5)

                    # Show image preview
                    image = Image.open(image_path)
                    image.thumbnail((200, 200))
                    photo = ImageTk.PhotoImage(image)
                    image_label = ttk.Label(hint_frame, image=photo)
                    image_label.image = photo
                    image_label.pack(pady=2)
                else:
                    ttk.Label(
                        image_info_frame,
                        text="(Image file not found)",
                        foreground='red'
                    ).pack(side='left', padx=5)

            except Exception as e:
                print(f"[hint library]Error loading hint image: {e}")
                ttk.Label(
                    hint_frame,
                    text=f"Error loading image: {str(e)}",
                    foreground='red'
                ).pack(pady=2)

        return hint_frame

    def show_image_selector(self, room_id, prop_display_name, hint_name):
        """Show the image selection listbox and preview"""

        # 1. Determine the image directory.
        room_map = {
            '1': "casino",
            '2': "ma",
            '3': "wizard",
            '4': "zombie",
            '5': "haunted",
            '6': "atlantis",
            '7': "time"
        }
        room_folder = room_map.get(str(room_id), "").lower()
        image_dir = os.path.join(
            os.path.dirname(__file__),
            "sync_directory",
            "hint_image_files",
            room_folder,
            prop_display_name
        )

        # 2. Populate the listbox.
        self.image_listbox.delete(0, tk.END)  # Clear previous entries
        if os.path.exists(image_dir):
            for filename in os.listdir(image_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    self.image_listbox.insert(tk.END, filename)

            # 3. Pack the listbox and preview label (make them visible).
            self.image_listbox.pack(pady=5)
            self.image_preview_label.pack(pady=5)
            
            # Store current context
            self.current_image_context = {
                'room_id': room_id,
                'prop_display_name': prop_display_name,
                'hint_name': hint_name,
                'image_dir': image_dir
            }
          
        else:
            print(f"[hint library]Image directory not found: {image_dir}")
            # Handle the case where the directory doesn't exist, perhaps show a message.

    def preview_selected_image(self, event=None):
        """Preview the selected image from the listbox"""

        selection = self.image_listbox.curselection()
        if not selection:
            return  # Nothing selected

        filename = self.image_listbox.get(selection[0])
        if not hasattr(self, 'current_image_context'):
            return
        image_path = os.path.join(self.current_image_context['image_dir'], filename)

        try:
            image = Image.open(image_path)
            image.thumbnail((200, 200))  # Resize for preview
            photo = ImageTk.PhotoImage(image)
            self.image_preview_label.config(image=photo)
            self.image_preview_label.image = photo  # Keep a reference!

            # Update the hint data with the new image and save
            self.update_hint_image(filename)

        except Exception as e:
            print(f"[hint library]Error displaying image preview: {e}")
            self.image_preview_label.config(text="Error loading preview")

    def update_hint_image(self, filename):
        """Update the hint data with the selected image and save"""
        if not hasattr(self, 'current_image_context'):
            return # No image context

        room_id = self.current_image_context['room_id']
        prop_display_name = self.current_image_context['prop_display_name']
        hint_name = self.current_image_context['hint_name']
        
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            # Update the image filename
            hint_data['rooms'][room_id][prop_display_name][hint_name]['image'] = filename
            
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)
            
            # Reload to update the display, showing new image
            self.load_hints()
            
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            print(f"Error updating hint image: {e}")
            messagebox.showerror("Error", f"Failed to update image: {e}")

    def autosave_hint(self, room_id, prop_display_name, hint_name, text_widget):
        """Debounced autosave function."""

        # If there's a pending save, cancel it
        if self.autosave_after_id:
            self.status_label.after_cancel(self.autosave_after_id)

        # Schedule the save after a short delay (e.g., 500ms)
        self.autosave_after_id = self.status_label.after(500, lambda: self.save_hint_changes(room_id, prop_display_name, hint_name, text_widget))

    def save_hint_changes(self, room_id, prop_display_name, hint_name, text_widget):
        """Save changes made to a hint's text"""
        try:
            # Get the current text from the widget
            new_text = text_widget.get('1.0', 'end-1c')

            # Load current hint data
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            # Update the hint text
            hint_data['rooms'][room_id][prop_display_name][hint_name]['text'] = new_text

            # Save the updated data
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)

            # Show success message (briefly)
            self.status_label.config(text="Saved!", foreground='green')
            self.status_label.after(1000, lambda: self.status_label.config(text=""))

            # Reset the modified flag on the text widget
            text_widget.edit_modified(False)

        except Exception as e:
            print(f"[hint library]Error saving hint changes: {e}")
            self.status_label.config(text="Error saving!", foreground='red')
            self.status_label.after(2000, lambda: self.status_label.config(text=""))



    def show_save_status(self, message, error=False):
        """Show a temporary status message"""
        status_window = tk.Toplevel(self.app)
        status_window.title("Save Status")

        # Position the window near the center of the main window
        x = self.app.winfo_x() + (self.app.winfo_width() // 2) - 100
        y = self.app.winfo_y() + (self.app.winfo_height() // 2) - 50
        status_window.geometry(f"+{x}+{y}")

        # Remove window decorations
        status_window.overrideredirect(True)

        # Create label with message
        label = ttk.Label(
            status_window,
            text=message,
            padding=10,
            foreground='red' if error else 'green'
        )
        label.pack()

        # Auto-close after 2 seconds
        status_window.after(2000, status_window.destroy)

    def delete_hint(self, room_id, prop_display_name, hint_name):
        """Delete a hint and its associated image"""
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            # Delete the hint
            del hint_data['rooms'][room_id][prop_display_name][hint_name]

            # Clean up empty structures
            if not hint_data['rooms'][room_id][prop_display_name]:
                del hint_data['rooms'][room_id][prop_display_name]
            if not hint_data['rooms'][room_id]:
                del hint_data['rooms'][room_id]

            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)

            # No need to delete the image file since it's now stored in the sync directory
            # and may be used by other hints

            self.load_hints()  # Reload to refresh the display

        except Exception as e:
            print(f"[hint library]Error deleting hint: {e}")

class AdminPasswordManager:
    def __init__(self, app):
        self.app = app
        self.hashed_password = self.load_hashed_password()

    def load_hashed_password(self):
        """Load or create and save hashed password"""
        password_file = Path("hint_manager_password.txt")
        if password_file.exists():
            with open(password_file, 'r') as f:
                return f.read().strip()
        else:
            # No password, set up a temporary default
            default_pass = "admin" # set a default
            hashed_default = hashlib.sha256(default_pass.encode()).hexdigest()
            with open(password_file, 'w') as f:
                f.write(hashed_default)
            print(f"[password manager]Password file created with default password for 'admin'")
            return hashed_default

    def verify_password(self, callback=None):
        """Prompt for password and verify it"""
        login_window = tk.Toplevel(self.app.root)
        login_window.title("Enter Password (DO NOT RUN SYNC DURING GAMES!)")
        login_window.geometry("400x150")

        tk.Label(login_window, text="Password:", font=('Arial', 12)).pack(pady=10)
        password_entry = tk.Entry(login_window, show="*", width=40)
        password_entry.pack(pady=5)

        def validate():
            entered_password = password_entry.get()
            hashed_entered = hashlib.sha256(entered_password.encode()).hexdigest()
            if hashed_entered == self.hashed_password:  # Corrected line
                login_window.destroy()
                if callback:
                    callback()
            else:
                messagebox.showerror("Error", "Incorrect password.")
                #login_window.destroy()  # Removed unnecessary destroy

        def on_close():
            login_window.destroy()

        # Bind Enter key to validate
        password_entry.bind('<Return>', lambda e: validate())

        login_window.protocol("WM_DELETE_WINDOW", on_close)

        login_button = tk.Button(login_window, text="Login", command=validate)
        login_button.pack(pady=10)

        login_window.transient(self.app.root)
        login_window.grab_set()

        # Focus the password entry
        password_entry.focus_set()

        self.app.root.wait_window(login_window)