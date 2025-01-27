import tkinter as tk
from tkinter import ttk, messagebox
import json
from pathlib import Path
import os
from PIL import Image, ImageTk
import shutil
import hashlib # For simple password storage

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

class HintManager:
    def __init__(self, app, admin_interface):
        self.app = app
        self.admin_interface = admin_interface
        self.main_container = None
        self.original_widgets = []
        self.load_prop_mappings()
        self.hashed_password = self.load_hashed_password()  # Load hashed password

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
            print(f"[hint library]Password file created with default password for 'admin'")
            return hashed_default
    
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
        """Prompt for credentials and validate them"""
        
        login_window = tk.Toplevel(self.app.root)
        login_window.title("Enter Credentials")
        login_window.geometry("300x150")  # Set a fixed size

        tk.Label(login_window, text="Password:", font=('Arial', 12)).pack(pady=10)
        password_entry = tk.Entry(login_window, show="*", width=20)
        password_entry.pack(pady=5)

        def validate():
            entered_password = password_entry.get()
            hashed_entered = hashlib.sha256(entered_password.encode()).hexdigest()
            if hashed_entered == self.hashed_password:
                 login_window.destroy()
                 self.create_hint_management_view()  # Proceed to Hint Manager if creds valid
            else:
                messagebox.showerror("Error", "Incorrect password.")
                login_window.destroy()  # Close if password was incorrect
                self.admin_interface.app.root.focus_set()

        login_button = tk.Button(login_window, text="Login", command=validate)
        login_button.pack(pady=10)

        login_window.transient(self.admin_interface.app.root)  # Associate with main window
        login_window.grab_set()  # Make modal
        self.admin_interface.app.root.wait_window(login_window)  # Keep control in this modal, prevent interaction in main

    def show_hint_manager(self):
        """Store current widgets and show hint management interface"""
        self.original_widgets = []
        for widget in self.admin_interface.main_container.winfo_children():
            widget.pack_forget()
            self.original_widgets.append(widget)
        
        self.check_credentials() # Prompt for login before continuing

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
               if hashed_old != self.hashed_password:
                   messagebox.showerror("Error", "Incorrect old password.")
                   return

               if new_password != confirm_password:
                  messagebox.showerror("Error", "New passwords do not match.")
                  return
               
               if not new_password:
                   messagebox.showerror("Error", "New password cannot be blank.")
                   return

               # Hash and save new password
               self.hashed_password = hashlib.sha256(new_password.encode()).hexdigest()
               with open("hint_manager_password.txt", 'w') as f:
                  f.write(self.hashed_password)

               messagebox.showinfo("Success", "Password changed successfully.")
               change_window.destroy()

           change_button = tk.Button(change_window, text="Save Changes", command=save_new_password)
           change_button.pack(pady=10)

           change_window.transient(self.admin_interface.app.root)
           change_window.grab_set()
           self.admin_interface.app.root.wait_window(change_window)

    def restore_original_view(self):
        """Restore the original interface"""
        if self.main_container:
            self.main_container.destroy()

        for widget in self.original_widgets:
            widget.pack(side='left', fill='both', expand=True, padx=5)

    def create_hint_management_view(self):
            """Create the hint management interface"""
            self.main_container = ttk.Frame(self.admin_interface.main_container)
            self.main_container.pack(fill='both', expand=True, padx=10, pady=5)

            # Create header with back button
            header_frame = ttk.Frame(self.main_container)
            header_frame.pack(fill='x', pady=(0, 10))

            back_btn = ttk.Button(
                header_frame,
                text="← Back to Control Panel",
                command=self.restore_original_view
            )
            back_btn.pack(side='left')
            
            change_pass_btn = ttk.Button(
                    header_frame,
                    text="Change Password",
                    command=self.change_password
                )
            change_pass_btn.pack(side='left', padx=5)


            ttk.Label(
                header_frame,
                text="Hint Manager",
                font=('Arial', 14, 'bold')
            ).pack(side='left', padx=20)

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

                # Group hints by prop
                prop_hints = {}
                for hint_id, hint_info in room_data.get('hints', {}).items():
                    prop_name = hint_info['prop']
                    display_name = self.get_display_name(room_id, prop_name)
                    print(f"[hint library]Room: {room_id} -> {mapped_room}, Prop: {prop_name} -> {display_name}")
                    if prop_name not in prop_hints:
                        prop_hints[prop_name] = []
                    prop_hints[prop_name].append((hint_id, hint_info))

                # Create collapsible sections for each prop
                for prop_name, hints in prop_hints.items():
                    display_name = self.get_display_name(room_id, prop_name)
                    prop_frame = CollapsibleFrame(
                        room_frame.sub_frame,
                        text=f"Prop: {display_name}"
                    )
                    prop_frame.pack(fill='x', padx=5, pady=2)

                    # Add hints for this prop
                    for hint_id, hint_info in hints:
                        hint_display = self.create_hint_display(
                            prop_frame.sub_frame,
                            room_id,
                            hint_id,
                            hint_info
                        )
                        hint_display.pack(fill='x', padx=5, pady=2)

        except Exception as e:
            print(f"[hint library]Error loading hints: {e}")

    def create_hint_display(self, parent, room_id, hint_id, hint_info):
        """Create a display frame for a single hint"""
        hint_frame = ttk.Frame(parent)

        # Header with hint name and buttons
        header_frame = ttk.Frame(hint_frame)
        header_frame.pack(fill='x', pady=(0, 5))

        ttk.Label(
            header_frame,
            text=f"Hint: {hint_info['name']}",
            font=('Arial', 10)
        ).pack(side='left')

        # Status label (hidden by default)
        status_label = ttk.Label(header_frame, text="", foreground='green')
        status_label.pack(side='right', padx=5)

        # Save button
        save_btn = ttk.Button(
            header_frame,
            text="Save Changes",
            command=lambda: self.save_hint_changes(room_id, hint_id, text, status_label)
        )
        save_btn.pack(side='right', padx=(0, 5))

        # Delete button
        delete_btn = ttk.Button(
            header_frame,
            text="Delete",
            command=lambda: self.delete_hint(room_id, hint_id)
        )
        delete_btn.pack(side='right')

        # Hint text
        if hint_info.get('text'):
            text_frame = ttk.Frame(hint_frame)
            text_frame.pack(fill='x', pady=2)
            text = tk.Text(text_frame, height=3, width=50, wrap='word')
            text.insert('1.0', hint_info['text'])
            text.pack(fill='x')

        # Hint image if present
        if hint_info.get('image'):
            try:
                image_path = os.path.join('saved_hint_images', hint_info['image'])
                if os.path.exists(image_path):
                    image = Image.open(image_path)
                    image.thumbnail((200, 200))
                    photo = ImageTk.PhotoImage(image)
                    image_label = ttk.Label(hint_frame, image=photo)
                    image_label.image = photo
                    image_label.pack(pady=2)
            except Exception as e:
                print(f"[hint library]Error loading hint image: {e}")

        return hint_frame

    def save_hint_changes(self, room_id, hint_id, text_widget, status_label):
        """Save changes made to a hint's text"""
        try:
            # Get the current text from the widget
            new_text = text_widget.get('1.0', 'end-1c')

            # Load current hint data
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            # Update the hint text
            hint_data['rooms'][room_id]['hints'][hint_id]['text'] = new_text

            # Save the updated data
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)

            # Show success message
            status_label.config(text="Saved!", foreground='green')
            status_label.after(2000, lambda: status_label.config(text=""))

        except Exception as e:
            print(f"[hint library]Error saving hint changes: {e}")
            status_label.config(text="Error saving!", foreground='red')
            status_label.after(2000, lambda: status_label.config(text=""))

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

    def delete_hint(self, room_id, hint_id):
        """Delete a hint and its associated image"""
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            image_filename = hint_data['rooms'][room_id]['hints'][hint_id].get('image')

            del hint_data['rooms'][room_id]['hints'][hint_id]

            if not hint_data['rooms'][room_id]['hints']:
                del hint_data['rooms'][room_id]

            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)

            if image_filename:
                image_path = os.path.join('saved_hint_images', image_filename)
                if os.path.exists(image_path):
                    os.remove(image_path)

            self.load_hints()

        except Exception as e:
            print(f"[hint library]Error deleting hint: {e}")