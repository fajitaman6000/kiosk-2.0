import tkinter as tk
from tkinter import ttk
import json
from pathlib import Path
import os
from PIL import Image, ImageTk
import shutil

class HintManager:
    def __init__(self, app, admin_interface):
        self.app = app
        self.admin_interface = admin_interface
        self.main_container = None
        self.original_widgets = []
        
    def show_hint_manager(self):
        """Store current widgets and show hint management interface"""
        # Store all current widgets in main container
        self.original_widgets = []
        for widget in self.admin_interface.main_container.winfo_children():
            widget.pack_forget()  # Unpack but don't destroy
            self.original_widgets.append(widget)
            
        # Create hint management interface
        self.create_hint_management_view()
        
    def restore_original_view(self):
        """Restore the original interface"""
        # Remove hint management interface
        if self.main_container:
            self.main_container.destroy()
            
        # Restore original widgets
        for widget in self.original_widgets:
            widget.pack(side='left', fill='both', expand=True, padx=5)
            
    def create_hint_management_view(self):
        """Create the hint management interface"""
        # Create main container
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
        
        # Create main content area
        content_frame = ttk.Frame(self.main_container)
        content_frame.pack(fill='both', expand=True)
        
        # Create hint list with scrollbar
        scroll_frame = ttk.Frame(content_frame)
        scroll_frame.pack(fill='both', expand=True)
        
        self.hint_canvas = tk.Canvas(scroll_frame)
        scrollbar = ttk.Scrollbar(scroll_frame, orient="vertical", command=self.hint_canvas.yview)
        self.scrollable_frame = ttk.Frame(self.hint_canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.hint_canvas.configure(scrollregion=self.hint_canvas.bbox("all"))
        )
        
        self.hint_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.hint_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.hint_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
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
                room_frame = ttk.LabelFrame(
                    self.scrollable_frame,
                    text=f"Room {room_id}"
                )
                room_frame.pack(fill='x', padx=5, pady=5)
                
                for hint_id, hint_info in room_data.get('hints', {}).items():
                    hint_frame = self.create_hint_display(
                        room_frame,
                        room_id,
                        hint_id,
                        hint_info
                    )
                    hint_frame.pack(fill='x', padx=5, pady=5)
                    
        except Exception as e:
            print(f"Error loading hints: {e}")
            
    def create_hint_display(self, parent, room_id, hint_id, hint_info):
        """Create a display frame for a single hint"""
        hint_frame = ttk.Frame(parent)
        
        # Header with prop name and delete button
        header_frame = ttk.Frame(hint_frame)
        header_frame.pack(fill='x', pady=(0, 5))
        
        ttk.Label(
            header_frame,
            text=f"Prop: {hint_info['prop']} - {hint_info['name']}",
            font=('Arial', 10, 'bold')
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
            # Load current hints
            with open('saved_hints.json', 'r') as f:
                hint_data = json.load(f)
                
            # Get image filename before deleting hint
            image_filename = hint_data['rooms'][room_id]['hints'][hint_id].get('image')
            
            # Delete hint from JSON
            del hint_data['rooms'][room_id]['hints'][hint_id]
            
            # Remove room if empty
            if not hint_data['rooms'][room_id]['hints']:
                del hint_data['rooms'][room_id]
                
            # Save updated JSON
            with open('saved_hints.json', 'w') as f:
                json.dump(hint_data, f, indent=4)
                
            # Delete image file if it exists
            if image_filename:
                image_path = os.path.join('saved_hint_images', image_filename)
                if os.path.exists(image_path):
                    os.remove(image_path)
                    
            # Reload hints display
            self.load_hints()
            
        except Exception as e:
            print(f"Error deleting hint: {e}")