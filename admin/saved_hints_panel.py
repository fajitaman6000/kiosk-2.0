# saved_hints_panel.py
import tkinter as tk
from tkinter import ttk
import json
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
        # Create main frame with fixed width
        self.frame = ttk.LabelFrame(parent, text="Saved Hints")
        self.frame.pack(side='left', padx=5, pady=5)
        
        # Store callback
        self.send_hint_callback = send_hint_callback
        
        # Create fixed-width inner container
        self.list_container = ttk.Frame(self.frame)
        self.list_container.pack(padx=5, pady=5)
        
        # Create hint listbox
        self.hint_listbox = tk.Listbox(
            self.list_container,
            height=6,
            width=40,
            selectmode=tk.SINGLE,
            exportselection=False,
            bg='white',
            fg='black'
        )
        self.hint_listbox.pack(pady=(0, 5))
        self.hint_listbox.bind('<<ListboxSelect>>', self.on_hint_select)
        
        # Preview frame
        self.preview_frame = ttk.Frame(self.list_container)
        self.preview_frame.pack(fill='x', pady=5)
        
        # Preview text
        self.preview_text = tk.Text(
            self.preview_frame,
            height=4,
            width=38,
            wrap=tk.WORD,
            state='disabled'
        )
        self.preview_text.pack(pady=(0, 5))
        
        # Image preview label
        self.image_label = ttk.Label(self.preview_frame, text="No image")
        self.image_label.pack(pady=(0, 5))
        
        # Send button (initially disabled)
        self.send_button = ttk.Button(
            self.preview_frame,
            text="Send Hint",
            command=self.send_hint,
            state='disabled'
        )
        self.send_button.pack(pady=(0, 5))
        
        # Load initial hints
        self.hints_data = {}
        self.load_hints()

    def load_hints(self):
        """Load all hints from the JSON file"""
        try:
            print("\n=== LOADING SAVED HINTS ===")
            hints_path = os.path.join(os.getcwd(), 'saved_hints.json')
            print(f"Looking for hints file at: {hints_path}")
            print(f"File exists: {os.path.exists(hints_path)}")
            
            if os.path.exists(hints_path):
                with open(hints_path, 'r') as f:
                    data = json.load(f)
                    self.hints_data = data['hints']
                    print(f"Loaded {len(self.hints_data)} hints")
                    print(f"Available hints: {list(self.hints_data.keys())}")
            else:
                print("No hints file found!")
                self.hints_data = {}
        except Exception as e:
            print(f"Error loading hints: {str(e)}")
            import traceback
            traceback.print_exc()
            self.hints_data = {}

    # Replace the entire update_room method:
    def update_room(self, room_number):
        """Update the hints list for the selected room"""
        print(f"\n=== UPDATING SAVED HINTS FOR ROOM {room_number} ===")
        print(f"Current hints data: {self.hints_data}")
        
        self.hint_listbox.delete(0, tk.END)
        self.clear_preview()
        
        # Filter hints for current room and add to listbox
        matching_hints = 0
        for hint_id, hint_data in self.hints_data.items():
            print(f"Checking hint {hint_id}: {hint_data}")
            if hint_data['room'] == room_number:
                print(f"Adding hint: {hint_data['name']}")
                self.hint_listbox.insert(tk.END, hint_data['name'])
                matching_hints += 1
        
        print(f"Added {matching_hints} hints for room {room_number}")

    def on_hint_select(self, event):
        """Handle hint selection from listbox"""
        selection = self.hint_listbox.curselection()
        if not selection:
            return
            
        hint_name = self.hint_listbox.get(selection[0])
        
        # Find hint data by name
        selected_hint = None
        for hint_data in self.hints_data.values():
            if hint_data['name'] == hint_name:
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
                        # Resize image to fit preview (e.g., max 200px width)
                        image.thumbnail((200, 200))
                        photo = ImageTk.PhotoImage(image)
                        self.image_label.configure(image=photo)
                        self.image_label.image = photo
                    else:
                        self.image_label.configure(text="Image file not found", image='')
                except Exception as e:
                    print(f"Error loading hint image: {e}")
                    self.image_label.configure(text="Error loading image", image='')
            else:
                self.image_label.configure(text="No image for this hint", image='')
            
            # Enable send button
            self.send_button.config(state='normal')

    def clear_preview(self):
        """Clear the preview area"""
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.config(state='disabled')
        self.image_label.configure(text="No image", image='')
        self.send_button.config(state='disabled')

    def send_hint(self):
        """Send the currently selected hint"""
        selection = self.hint_listbox.curselection()
        if not selection:
            return
            
        hint_name = self.hint_listbox.get(selection[0])
        
        # Find hint data by name
        selected_hint = None
        for hint_data in self.hints_data.values():
            if hint_data['name'] == hint_name:
                selected_hint = hint_data
                break
                
        if selected_hint:
            # Prepare hint data
            hint_data = {'text': selected_hint['text']}
            
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
            
            # Clear preview after sending
            self.clear_preview()
            
            # Clear listbox selection
            self.hint_listbox.selection_clear(0, tk.END)