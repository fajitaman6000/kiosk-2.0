import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import os
from PIL import Image, ImageTk
import shutil


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
        
    def load_prop_mappings(self):
        """Load prop name mappings from JSON"""
        try:
            with open('prop_name_mapping.json', 'r') as f:
                self.prop_mappings = json.load(f)
        except Exception as e:
            print(f"Error loading prop mappings: {e}")
            self.prop_mappings = {}
            
    def get_display_name(self, room_id, prop_name):
        """Get the display name for a prop from the mappings"""
        room_key = room_id.lower()  # Convert room IDs to match mapping keys
        if room_key in self.prop_mappings:
            room_mappings = self.prop_mappings[room_key]['mappings']
            if prop_name in room_mappings:
                return room_mappings[prop_name]['display']
        return prop_name
        
    def show_hint_manager(self):
        """Store current widgets and show hint management interface"""
        self.original_widgets = []
        for widget in self.admin_interface.main_container.winfo_children():
            widget.pack_forget()
            self.original_widgets.append(widget)
            
        self.create_hint_management_view()
        
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
        
        ttk.Label(
            header_frame,
            text="Hint Manager",
            font=('Arial', 14, 'bold')
        ).pack(side='left', padx=20)
        
        # Create scrollable content area
        content_frame = ttk.Frame(self.main_container)
        content_frame.pack(fill='both', expand=True)
        
        canvas = tk.Canvas(content_frame)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        self.scrollable_frame = ttk.Frame(canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Configure canvas to expand and scroll
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        # Load and display hints
        self.load_hints()
        
    def load_hints(self):
        """Load and display all hints from saved_hints.json"""
        try:
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)
                
            # Clear existing hint displays
            for widget in self.scrollable_frame.winfo_children():
                widget.destroy()
                
            # Display hints by room
            for room_id, room_data in hint_data.get('rooms', {}).items():
                room_frame = CollapsibleFrame(
                    self.scrollable_frame,
                    text=f"Room: {room_id}"
                )
                room_frame.pack(fill='x', padx=5, pady=2)
                
                # Group hints by prop
                prop_hints = {}
                for hint_id, hint_info in room_data.get('hints', {}).items():
                    prop_name = hint_info['prop']
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
            print(f"Error loading hints: {e}")
            
    def create_hint_display(self, parent, room_id, hint_id, hint_info):
        """Create a display frame for a single hint"""
        hint_frame = ttk.Frame(parent)
        
        # Header with hint name and delete button
        header_frame = ttk.Frame(hint_frame)
        header_frame.pack(fill='x', pady=(0, 5))
        
        ttk.Label(
            header_frame,
            text=f"Hint: {hint_info['name']}",
            font=('Arial', 10)
        ).pack(side='left')
        
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
            text.config(state='disabled')
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
                print(f"Error loading hint image: {e}")
                
        return hint_frame
        
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
            print(f"Error deleting hint: {e}")