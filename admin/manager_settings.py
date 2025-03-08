import tkinter as tk
from tkinter import ttk, messagebox
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
        self.selected_hint = None
        self.hint_tree = None
        self.hint_map = {}
        self.tree_items = {}
        self.current_prop_name = ""  # Store current prop name for image label

    def load_prop_mappings(self):
        try:
            with open('prop_name_mapping.json', 'r') as f:
                self.prop_mappings = json.load(f)
        except Exception as e:
            print(f"[hint library]Error loading prop mappings: {e}")
            self.prop_mappings = {}

    def get_display_name(self, room_id, prop_name):
        room_mapping = {'1': 'casino_ma', '2': 'wizard', '3': 'haunted', '4': 'zombie', '5': 'wizard', '6': 'atlantis', '7': 'time_machine'}
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
            self.create_hint_management_view()
        return self.password_manager.verify_password(callback=on_success)

    def show_hint_manager(self):
        self.check_credentials()

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

        self.hint_tree = ttk.Treeview(self.hint_list_frame, selectmode='browse')
        self.hint_tree.pack(side="left", fill="both", expand=True)
        self.hint_tree.bind('<<TreeviewSelect>>', self.on_hint_select)
        self.hint_tree.bind("<<TreeviewOpen>>", self.on_treeview_open)
        self.hint_tree.bind("<<TreeviewClose>>", self.on_treeview_close)

        scrollbar = ttk.Scrollbar(self.hint_list_frame, orient="vertical", command=self.hint_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.hint_tree['yscrollcommand'] = scrollbar.set

        # --- Right side: Hint editor ---
        self.hint_editor_frame = ttk.Frame(paned_window)
        paned_window.add(self.hint_editor_frame, weight=3)

        # Hint text
        ttk.Label(self.hint_editor_frame, text="Text content:").pack(anchor='w', padx=5, pady=2) # Added label
        self.text_widget = tk.Text(self.hint_editor_frame, height=3, width=40, wrap=tk.WORD)
        self.text_widget.pack(pady=5)

        # Image selection and preview (using a frame for layout)
        self.image_label = ttk.Label(self.hint_editor_frame, text="") # Initially empty
        self.image_label.pack(anchor='w', padx=5, pady=2) # align left

        image_frame = ttk.Frame(self.hint_editor_frame)
        image_frame.pack(fill='x', pady=5)

        self.image_listbox = tk.Listbox(image_frame, height=8, width=30, selectmode=tk.SINGLE, exportselection=False)
        self.image_listbox.pack(side='left', padx=5)
        self.image_listbox.bind('<<ListboxSelect>>', self.preview_selected_image)

        self.image_preview_label = ttk.Label(image_frame)
        self.image_preview_label.pack(side='left', padx=5)

        self.status_label = ttk.Label(self.hint_editor_frame, text="")
        self.status_label.pack(pady=5)
        self.delete_button = ttk.Button(self.hint_editor_frame, text="Delete Hint", command=self.delete_selected_hint)
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
        for item in self.hint_tree.get_children():
            self.hint_tree.delete(item)
        self.hint_map = {}
        self.tree_items = {}

        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)

            for room_id, room_data in hint_data.get('rooms', {}).items():
                room_text = f"Room {room_id}"
                room_item = self.hint_tree.insert("", "end", text=room_text, open=True)
                self.tree_items[room_item] = {"type": "room", "id": room_id}

                for prop_name, prop_hints in room_data.items():
                    display_name = self.get_display_name(room_id, prop_name)
                    prop_text = f"{display_name}"
                    prop_item = self.hint_tree.insert(room_item, "end", text=prop_text, open=True)
                    self.tree_items[prop_item] = {"type": "prop", "room_id": room_id, "prop_name": prop_name, "display_name": display_name}

                    for hint_name, hint_info in prop_hints.items():
                        hint_key = f"{room_id}-{prop_name}-{hint_name}"
                        display_text = f"{hint_name}"
                        hint_item = self.hint_tree.insert(prop_item, "end", text=display_text)
                        self.hint_map[hint_key] = (room_id, prop_name, hint_name, hint_info)

        except Exception as e:
            print(f"[hint library]Error loading hints: {e}")

    def on_hint_select(self, event):
      selection = self.hint_tree.selection()
      if not selection:
          return

      selected_item = selection[0]

      if selected_item not in self.tree_items:
          parent_prop_item = self.hint_tree.parent(selected_item)
          parent_room_item = self.hint_tree.parent(parent_prop_item)

          room_id = self.tree_items[parent_room_item]["id"]
          # prop_name = self.tree_items[parent_prop_item]["prop_name"]  # Get original prop_name
          hint_name = self.hint_tree.item(selected_item, "text")
          display_name = self.tree_items[parent_prop_item]['display_name']  # Get display_name

          hint_key = f"{room_id}-{self.tree_items[parent_prop_item]['prop_name']}-{hint_name}" # use original prop name
          if hint_key in self.hint_map:
            room_id, prop_name_returned, hint_name_returned, hint_info = self.hint_map[hint_key]
            self.select_hint(room_id, display_name, hint_name, hint_info)  # Use display_name

            # Update current_prop_name for image label
            self.current_prop_name = display_name
            self.image_label.config(text=f"Images available for {self.current_prop_name}:")

          else:
            print(f"could not find {hint_key} in hint map.")
            return

    def select_hint(self, room_id, prop_display_name, hint_name, hint_info):
        self.selected_hint = (room_id, prop_display_name, hint_name)
        self.text_widget.delete('1.0', tk.END)
        self.text_widget.insert('1.0', hint_info.get('text', ''))
        self.text_widget.edit_modified(False)
        self.show_image_selector(room_id, prop_display_name, hint_name)

    def delete_selected_hint(self):
        if self.selected_hint:
            room_id, prop_display_name, hint_name = self.selected_hint
            self.delete_hint(room_id, prop_display_name, hint_name)
            self.selected_hint = None
            self.text_widget.delete('1.0', tk.END)
            self.image_listbox.delete(0, tk.END)
            self.image_preview_label.config(image=None)
            self.image_preview_label.image = None
            self.image_label.config(text="") # clear image label
            self.current_prop_name = "" # clear prop name

    def get_image_path(self, room_id, prop_display_name, image_filename):
        if not image_filename:
            return None
        room_map = {'1': "casino", '2': "ma", '3': "wizard", '4': "zombie", '5': "haunted", '6': "atlantis", '7': "time"}
        room_folder = room_map.get(str(room_id), "").lower()
        if not room_folder:
            return None
        image_path = os.path.join(os.path.dirname(__file__), "sync_directory", "hint_image_files", room_folder, prop_display_name, image_filename)
        return image_path if os.path.exists(image_path) else None

    def show_image_selector(self, room_id, prop_display_name, hint_name):
        room_map = {'1': "casino", '2': "ma", '3': "wizard", '4': "zombie", '5': "haunted", '6': "atlantis", '7': "time"}
        room_folder = room_map.get(str(room_id), "").lower()
        image_dir = os.path.join(os.path.dirname(__file__), "sync_directory", "hint_image_files", room_folder, prop_display_name)
        self.image_listbox.delete(0, tk.END)
        if os.path.exists(image_dir):
            try:
                with open('saved_hints.json', 'r') as f:
                    hint_data = json.load(f)
                current_image = hint_data['rooms'][str(room_id)][prop_display_name][hint_name].get('image')
            except (FileNotFoundError, KeyError, json.JSONDecodeError):
                current_image = None

            for filename in os.listdir(image_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                    self.image_listbox.insert(tk.END, filename)
                    if filename == current_image:
                        self.image_listbox.selection_set(tk.END)
            self.current_image_context = {'room_id': room_id, 'prop_display_name': prop_display_name, 'hint_name': hint_name, 'image_dir': image_dir}
            self.preview_selected_image()
        else:
            print(f"[hint library]Image directory not found: {image_dir}")

    def preview_selected_image(self, event=None):
        selection = self.image_listbox.curselection()
        if not selection:
            return
        filename = self.image_listbox.get(selection[0])
        if not hasattr(self, 'current_image_context'):
            return
        image_path = os.path.join(self.current_image_context['image_dir'], filename)
        try:
            image = Image.open(image_path)
            image.thumbnail((200, 200))
            photo = ImageTk.PhotoImage(image)
            self.image_preview_label.config(image=photo)
            self.image_preview_label.image = photo
            self.update_hint_image(filename)
        except Exception as e:
            print(f"[hint library]Error displaying image preview: {e}")
            self.image_preview_label.config(text="Error loading preview")

    def update_hint_image(self, filename):
        if not hasattr(self, 'current_image_context'):
            return
        room_id = self.current_image_context['room_id']
        prop_display_name = self.current_image_context['prop_display_name']
        hint_name = self.current_image_context['hint_name']
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)
            hint_data['rooms'][str(room_id)][prop_display_name][hint_name]['image'] = filename
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)
        except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
            print(f"Error updating hint image: {e}")
            messagebox.showerror("Error", f"Failed to update image: {e}")

    def autosave_hint(self):
        if self.selected_hint is None:
            return
        if self.autosave_after_id:
            self.status_label.after_cancel(self.autosave_after_id)
        self.autosave_after_id = self.status_label.after(500, self.save_hint_changes)

    def save_hint_changes(self):
        if self.selected_hint is None:
            return
        room_id, prop_display_name, hint_name = self.selected_hint
        try:
            new_text = self.text_widget.get('1.0', 'end-1c')
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)
            hint_data['rooms'][str(room_id)][prop_display_name][hint_name]['text'] = new_text
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)
            self.status_label.config(text="Saved!", foreground='green')
            self.status_label.after(1000, lambda: self.status_label.config(text=""))
            self.text_widget.edit_modified(False)
        except Exception as e:
            print(f"[hint library]Error saving hint changes: {e}")
            self.status_label.config(text="Error saving!", foreground='red')
            self.status_label.after(2000, lambda: self.status_label.config(text=""))

    def show_save_status(self, message, error=False):
        status_window = tk.Toplevel(self.app)
        status_window.title("Save Status")
        x = self.app.winfo_x() + (self.app.winfo_width() // 2) - 100
        y = self.app.winfo_y() + (self.app.winfo_height() // 2) - 50
        status_window.geometry(f"+{x}+{y}")
        status_window.overrideredirect(True)
        label = ttk.Label(status_window, text=message, padding=10, foreground='red' if error else 'green')
        label.pack()
        status_window.after(2000, status_window.destroy)

    def delete_hint(self, room_id, prop_display_name, hint_name):
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)
            del hint_data['rooms'][str(room_id)][prop_display_name][hint_name]
            if not hint_data['rooms'][str(room_id)][prop_display_name]:
                del hint_data['rooms'][str(room_id)][prop_display_name]
            if not hint_data['rooms'][str(room_id)]:
                del hint_data['rooms'][str(room_id)]
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)
            self.load_hints()

        except Exception as e:
            print(f"[hint library]Error deleting hint: {e}")

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