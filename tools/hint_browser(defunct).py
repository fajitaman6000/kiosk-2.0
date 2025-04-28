import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import platform # Added for OS-specific actions
import subprocess # Added for Linux/Mac
from pathlib import Path
from PIL import Image, ImageTk
import json # Added for hint data
import traceback # For improved error handling
import sys
import logging

# Set up debug log file
DEBUG_LOG_FILE = "hint_browser_debug.log"
try:
    # Clear previous log
    with open(DEBUG_LOG_FILE, 'w') as f:
        f.write(f"=== Hint Browser Debug Log ===\n")
        f.write(f"Python version: {sys.version}\n")
        f.write(f"Platform: {platform.platform()}\n\n")
except Exception as e:
    print(f"Failed to initialize debug log: {e}")

def debug_log(message):
    """Write a message to the debug log file."""
    try:
        with open(DEBUG_LOG_FILE, 'a') as f:
            f.write(f"{message}\n")
    except Exception as e:
        print(f"Failed to write to debug log: {e}")

# --- Constants ---
ADMIN_DIR = Path("admin")
BASE_IMAGE_DIR = ADMIN_DIR / "sync_directory" / "hint_image_files"
SAVED_HINTS_FILE = ADMIN_DIR / "saved_hints.json"
PROP_MAPPING_FILE = ADMIN_DIR / "prop_name_mapping.json"

# THUMBNAIL_SIZE = (64, 64) # Old thumbnail size
PROP_BLOCK_THUMBNAIL_SIZE = (100, 75) # Thumbnail size for the prop block
POPUP_PREVIEW_SIZE = (600, 400) # Image preview size for popup
ROOM_GRID_COLUMNS = 3
PROP_GRID_COLUMNS = 4 # Adjust as needed

# Map room folder names to room display names
ROOM_NAME_MAP = {
    "casino": "Casino Heist",
    "ma": "Morning After",
    "wizard": "Wizard Trials",
    "zombie": "Zombie Outbreak",
    "haunted": "Haunted Manor",
    "atlantis": "Atlantis Rising",
    "time": "Time Machine"
}
# Map room folder names to room IDs
ROOM_NAME_TO_ID_MAP = {
    "casino": "1",
    "ma": "2",
    "wizard": "3",
    "zombie": "4",
    "haunted": "5",
    "atlantis": "6",
    "time": "7"
}
ROOM_ID_TO_NAME_MAP = {v: k for k, v in ROOM_NAME_TO_ID_MAP.items()}


# --- Helper Functions ---

def get_image_files(prop_dir: Path) -> list[Path]:
    """Gets a list of image files (jpg, png, gif) in a directory."""
    images = []
    if prop_dir.is_dir():
        for item in prop_dir.iterdir():
            if item.is_file() and item.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
                images.append(item)
    return images

def create_thumbnail(image_path: Path, size: tuple[int, int]) -> ImageTk.PhotoImage | None:
    """Creates a PhotoImage thumbnail for the given image path."""
    try:
        img = Image.open(image_path)
        img.thumbnail(size, Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception as e:
        print(f"Error creating thumbnail for {image_path}: {e}")
        return None

# --- HintViewerPopup Class ---

class HintViewerPopup:
    """Popup window for viewing and editing hint information."""
    def __init__(self, parent, app, room_id, prop_original_name, prop_display_name):
        self.parent = parent
        self.app = app
        self.room_id = room_id
        self.prop_original_name = prop_original_name
        self.prop_display_name = prop_display_name
        
        # Get the room folder name and prop directory
        self.room_folder_name = ROOM_ID_TO_NAME_MAP.get(room_id)
        self.prop_dir = BASE_IMAGE_DIR / self.room_folder_name / prop_original_name if self.room_folder_name else None
        
        # Image and hint navigation state
        self.image_list = []
        self.current_image_index = -1  # -1 means no image selected (None)
        self.current_image_obj = None
        
        # Hint navigation state
        self.hints_data = {}
        self.hint_levels = []
        self.current_hint_index = 0
        
        # Create popup window
        self.popup = tk.Toplevel(parent)
        self.popup.title(f"Hint Editor: {prop_display_name} ({ROOM_NAME_MAP.get(self.room_folder_name, f'Room {room_id}')})")
        self.popup.geometry("900x700")
        self.popup.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Main frame with padding
        main_frame = ttk.Frame(self.popup, padding=10)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Info and control frame (top)
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title and navigation
        title_frame = ttk.Frame(info_frame)
        title_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        ttk.Label(title_frame, 
                  text=f"{ROOM_NAME_MAP.get(self.room_folder_name, f'Room {room_id}')} » {prop_display_name}", 
                  font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, pady=5)
        
        # Image selector dropdown
        self.image_var = tk.StringVar()
        self.image_dropdown = ttk.Combobox(title_frame, textvariable=self.image_var, state="readonly", width=30)
        self.image_dropdown.pack(side=tk.LEFT, padx=10)
        self.image_dropdown.bind("<<ComboboxSelected>>", self.on_image_selected)
        
        # Button frame
        button_frame = ttk.Frame(info_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="Open Folder", 
                   command=self.open_folder_from_popup).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Add Images", 
                   command=self.add_images_from_popup).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Save Hints", 
                   command=self.save_hints).pack(side=tk.LEFT, padx=5)
        
        # Content frame
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(expand=True, fill=tk.BOTH)
        
        # Image display frame (top)
        image_frame = ttk.LabelFrame(content_frame, text="Image")
        image_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Image preview area
        self.image_preview_frame = ttk.Frame(image_frame)
        self.image_preview_frame.pack(expand=True, fill=tk.BOTH, pady=5)
        
        self.image_label = ttk.Label(self.image_preview_frame, anchor="center")
        self.image_label.pack(expand=True, fill=tk.BOTH)
        
        # Image action buttons
        action_frame = ttk.Frame(image_frame)
        action_frame.pack(fill=tk.X, pady=5)
        
        self.prev_button = ttk.Button(action_frame, text="Previous", command=self.go_previous)
        self.prev_button.pack(side=tk.LEFT, padx=5)
        
        self.image_count_label = ttk.Label(action_frame, text="No image selected")
        self.image_count_label.pack(side=tk.LEFT, expand=True)
        
        self.next_button = ttk.Button(action_frame, text="Next", command=self.go_next)
        self.next_button.pack(side=tk.RIGHT, padx=5)
        
        button_frame2 = ttk.Frame(image_frame)
        button_frame2.pack(fill=tk.X, pady=5)
        
        self.rename_button = ttk.Button(button_frame2, text="Rename", command=self.rename_image)
        self.rename_button.pack(side=tk.LEFT, padx=5)
        
        self.delete_button = ttk.Button(button_frame2, text="Delete", command=self.delete_image)
        self.delete_button.pack(side=tk.RIGHT, padx=5)
        
        # Hint viewer frame (bottom)
        hint_frame = ttk.LabelFrame(content_frame, text="Hint")
        hint_frame.pack(fill=tk.BOTH, expand=True)
        
        # Hint navigation
        hint_nav_frame = ttk.Frame(hint_frame)
        hint_nav_frame.pack(fill=tk.X, pady=5)
        
        self.prev_hint_button = ttk.Button(hint_nav_frame, text="Previous Hint", command=self.prev_hint)
        self.prev_hint_button.pack(side=tk.LEFT, padx=5)
        
        self.hint_level_label = ttk.Label(hint_nav_frame, text="No hints available", font=("TkDefaultFont", 10, "bold"))
        self.hint_level_label.pack(side=tk.LEFT, expand=True)
        
        self.next_hint_button = ttk.Button(hint_nav_frame, text="Next Hint", command=self.next_hint)
        self.next_hint_button.pack(side=tk.RIGHT, padx=5)
        
        # Hint text editor
        self.hint_editor = tk.Text(hint_frame, wrap=tk.WORD, height=10, font=("TkDefaultFont", 10))
        self.hint_editor.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add/Delete hint buttons
        hint_action_frame = ttk.Frame(hint_frame)
        hint_action_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(hint_action_frame, text="Add New Hint", command=self.add_hint).pack(side=tk.LEFT, padx=5)
        ttk.Button(hint_action_frame, text="Delete This Hint", command=self.delete_hint).pack(side=tk.RIGHT, padx=5)
        
        # Load images and populate dropdown
        self.load_image_list()
        # Load hints
        self.load_hints()
    
    def load_image_list(self):
        """Load the list of images for this prop and populate the dropdown."""
        self.image_list = []
        
        # Always add a "None" option
        dropdown_values = ["(None)"]
        
        if self.prop_dir and self.prop_dir.is_dir():
            # Get all images in the directory
            self.image_list = sorted(get_image_files(self.prop_dir))
            
            # Add image filenames to dropdown
            for img_path in self.image_list:
                dropdown_values.append(img_path.name)
        
        # Update dropdown
        self.image_dropdown['values'] = dropdown_values
        
        # Default to "None" if no images or first image if available
        if len(dropdown_values) > 1:
            self.image_var.set(dropdown_values[1])  # Select first actual image
            self.on_image_selected(None)  # Trigger loading the image
        else:
            self.image_var.set(dropdown_values[0])  # Select "None"
            self.show_no_image()
    
    def on_image_selected(self, event):
        """Handle selection of an image from the dropdown."""
        selected = self.image_var.get()
        
        if selected == "(None)":
            self.current_image_index = -1
            self.show_no_image()
            return
        
        # Find the corresponding index in the image_list
        for i, img_path in enumerate(self.image_list):
            if img_path.name == selected:
                self.load_image(i)
                return
    
    def show_no_image(self):
        """Display a message when no images are available or selected."""
        self.image_label.configure(image=None, text="No image selected")
        self.image_count_label.configure(text="No image selected")
        self.current_image_obj = None
        self.update_button_states()
    
    def load_image(self, index):
        """Load and display the image at the given index."""
        if not self.image_list or index < 0 or index >= len(self.image_list):
            self.show_no_image()
            return
        
        try:
            self.current_image_index = index
            image_path = self.image_list[index]
            
            # Update dropdown to match
            self.image_var.set(image_path.name)
            
            # Load and display the image
            img = Image.open(image_path)
            img.thumbnail(POPUP_PREVIEW_SIZE, Image.Resampling.LANCZOS)
            
            photo = ImageTk.PhotoImage(img)
            self.image_label.configure(image=photo, text="")
            self.image_label.image = photo  # Keep a reference
            self.current_image_obj = photo  # Store for later reference
            
            # Update the image count label
            self.image_count_label.configure(text=f"Image {index + 1} of {len(self.image_list)}")
            
            # Update button states
            self.update_button_states()
            
        except Exception as e:
            print(f"Error loading image {image_path}: {e}")
            self.image_label.configure(image=None, text=f"Error loading image:\n{e}")
    
    def update_button_states(self):
        """Update the state of navigation buttons based on current index."""
        image_count = len(self.image_list)
        
        # Update Previous button
        if image_count == 0 or self.current_image_index <= 0:
            self.prev_button.configure(state="disabled")
        else:
            self.prev_button.configure(state="normal")
        
        # Update Next button
        if image_count == 0 or self.current_image_index >= image_count - 1:
            self.next_button.configure(state="disabled")
        else:
            self.next_button.configure(state="normal")
        
        # Update Rename and Delete buttons
        if self.current_image_index < 0:  # No image selected
            self.rename_button.configure(state="disabled")
            self.delete_button.configure(state="disabled")
        else:
            self.rename_button.configure(state="normal")
            self.delete_button.configure(state="normal")
        
        # Update hint navigation buttons
        hint_count = len(self.hint_levels)
        if hint_count <= 1:
            self.prev_hint_button.configure(state="disabled")
            self.next_hint_button.configure(state="disabled")
        else:
            if self.current_hint_index <= 0:
                self.prev_hint_button.configure(state="disabled")
            else:
                self.prev_hint_button.configure(state="normal")
                
            if self.current_hint_index >= hint_count - 1:
                self.next_hint_button.configure(state="disabled")
            else:
                self.next_hint_button.configure(state="normal")
    
    def go_previous(self):
        """Navigate to the previous image."""
        if self.current_image_index > 0:
            self.load_image(self.current_image_index - 1)
    
    def go_next(self):
        """Navigate to the next image."""
        if self.current_image_index < len(self.image_list) - 1:
            self.load_image(self.current_image_index + 1)
    
    def load_hints(self):
        """Load existing hints and prepare for navigation."""
        # Get hints for this prop
        self.hints_data = {}
        room_hints = self.app.hints_data.get(self.room_id, {})
        
        # Try to find hints by display name (case insensitive)
        for key in room_hints:
            if key.lower() == self.prop_display_name.lower():
                self.hints_data = room_hints[key]
                break
        
        # Extract and sort hint levels
        self.hint_levels = sorted([level for level in self.hints_data.keys()], 
                                  key=lambda x: int(x) if x.isdigit() else 999)
        
        # Show first hint if available
        if self.hint_levels:
            self.current_hint_index = 0
            self.show_current_hint()
        else:
            self.show_no_hint()
        
        # Update navigation buttons
        self.update_button_states()
    
    def show_current_hint(self):
        """Display the current hint in the editor."""
        if not self.hint_levels or self.current_hint_index >= len(self.hint_levels):
            self.show_no_hint()
            return
        
        # Get the current level and hint text
        level = self.hint_levels[self.current_hint_index]
        hint_text = self.hints_data.get(level, "")
        
        # Clear and update the hint editor
        self.hint_editor.delete("1.0", tk.END)
        self.hint_editor.insert("1.0", hint_text)
        
        # Update the hint level label
        self.hint_level_label.configure(text=f"Level {level} Hint")
    
    def show_no_hint(self):
        """Display an empty hint editor when no hints are available."""
        self.hint_editor.delete("1.0", tk.END)
        self.hint_level_label.configure(text="No hints available")
    
    def prev_hint(self):
        """Navigate to the previous hint level."""
        if self.current_hint_index > 0:
            # Save current hint before navigating
            self.save_current_hint()
            
            self.current_hint_index -= 1
            self.show_current_hint()
            self.update_button_states()
    
    def next_hint(self):
        """Navigate to the next hint level."""
        if self.hint_levels and self.current_hint_index < len(self.hint_levels) - 1:
            # Save current hint before navigating
            self.save_current_hint()
            
            self.current_hint_index += 1
            self.show_current_hint()
            self.update_button_states()
    
    def save_current_hint(self):
        """Save the current hint text to the hints data."""
        if not self.hint_levels or self.current_hint_index >= len(self.hint_levels):
            return
        
        level = self.hint_levels[self.current_hint_index]
        hint_text = self.hint_editor.get("1.0", tk.END).strip()
        
        # Update the hint in the data structure
        self.hints_data[level] = hint_text
    
    def add_hint(self):
        """Add a new hint level."""
        # Save current hint first
        self.save_current_hint()
        
        # Determine the next available level
        next_level = "1"
        if self.hint_levels:
            # Try to find the highest numeric level and add 1
            numeric_levels = [int(l) for l in self.hint_levels if l.isdigit()]
            if numeric_levels:
                next_level = str(max(numeric_levels) + 1)
        
        # Let the user choose a level
        level = simpledialog.askstring(
            "Add Hint", 
            "Enter hint level:",
            initialvalue=next_level
        )
        
        if not level:
            return  # User cancelled
        
        # Add the new hint
        self.hints_data[level] = ""
        
        # Refresh the hint levels and display the new hint
        self.hint_levels = sorted([level for level in self.hints_data.keys()], 
                                  key=lambda x: int(x) if x.isdigit() else 999)
        
        # Find the index of the new level
        try:
            self.current_hint_index = self.hint_levels.index(level)
            self.show_current_hint()
            self.update_button_states()
        except ValueError:
            # Level not found (shouldn't happen)
            self.current_hint_index = 0
            self.show_current_hint()
            self.update_button_states()
    
    def delete_hint(self):
        """Delete the current hint level."""
        if not self.hint_levels or self.current_hint_index >= len(self.hint_levels):
            return
        
        level = self.hint_levels[self.current_hint_index]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", 
                             f"Are you sure you want to delete hint level {level}?"):
            return
        
        # Remove this hint
        if level in self.hints_data:
            del self.hints_data[level]
        
        # Refresh hint levels
        self.hint_levels = sorted([level for level in self.hints_data.keys()], 
                                 key=lambda x: int(x) if x.isdigit() else 999)
        
        # Adjust current index if needed
        if not self.hint_levels:
            self.current_hint_index = 0
            self.show_no_hint()
        elif self.current_hint_index >= len(self.hint_levels):
            self.current_hint_index = len(self.hint_levels) - 1
            self.show_current_hint()
        else:
            self.show_current_hint()
        
        self.update_button_states()
    
    def rename_image(self):
        """Rename the current image file."""
        if self.current_image_index < 0 or not self.image_list or self.current_image_index >= len(self.image_list):
            return
        
        current_path = self.image_list[self.current_image_index]
        current_name = current_path.name
        
        # Ask for a new name
        new_name = simpledialog.askstring(
            "Rename Image", 
            "Enter new filename:",
            initialvalue=current_name
        )
        
        if not new_name:
            return  # User cancelled
        
        # Add extension if missing
        if not any(new_name.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            # Keep the original extension
            new_name = f"{new_name}{current_path.suffix}"
        
        # Check if name exists
        new_path = current_path.parent / new_name
        if new_path.exists() and new_path != current_path:
            if not messagebox.askyesno("File Exists", 
                                 f"File '{new_name}' already exists. Overwrite?"):
                return
        
        try:
            # Rename the file
            current_path.rename(new_path)
            
            # Reload the image list and display the renamed image
            current_index = self.current_image_index
            self.load_image_list()
            
            # Find the renamed image's new index
            for i, img_path in enumerate(self.image_list):
                if img_path.name == new_name:
                    self.load_image(i)
                    return
            
            # If not found, load the image at the old index if possible
            if 0 <= current_index < len(self.image_list):
                self.load_image(current_index)
            elif self.image_list:
                self.load_image(0)
            else:
                self.show_no_image()
                
        except Exception as e:
            messagebox.showerror("Rename Error", f"Could not rename file:\n{e}")
    
    def delete_image(self):
        """Delete the current image file."""
        if self.current_image_index < 0 or not self.image_list or self.current_image_index >= len(self.image_list):
            return
        
        current_path = self.image_list[self.current_image_index]
        
        # Confirm deletion
        if not messagebox.askyesno("Confirm Delete", 
                             f"Are you sure you want to delete '{current_path.name}'?"):
            return
        
        try:
            # Delete the file
            current_path.unlink()
            
            # Reload the image list
            current_index = self.current_image_index
            self.load_image_list()
            
            # Display the next image, or the previous if there is no next
            if self.image_list:
                if current_index < len(self.image_list):
                    self.load_image(current_index)
                else:
                    self.load_image(len(self.image_list) - 1)
            else:
                self.show_no_image()
                
        except Exception as e:
            messagebox.showerror("Delete Error", f"Could not delete file:\n{e}")
    
    def add_images_from_popup(self):
        """Add images to the prop directory from the popup."""
        if not self.prop_dir:
            messagebox.showerror("Error", "No prop directory available")
            return
        
        # Create directory if it doesn't exist
        if not self.prop_dir.exists():
            try:
                self.prop_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create directory:\n{e}")
                return
        
        # Ask for image files
        file_paths = filedialog.askopenfilenames(
            title="Select Image Files",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.gif"),
                ("All files", "*.*")
            ]
        )
        
        if not file_paths:
            return  # User cancelled
        
        # Copy the files
        copied_count = self.app.add_images(self.prop_dir, file_paths)
        
        if copied_count > 0:
            # Reload the image list
            self.load_image_list()
    
    def open_folder_from_popup(self):
        """Open the prop folder from the popup."""
        if self.prop_dir:
            self.app.open_folder(self.room_id, self.prop_original_name)
    
    def save_hints(self):
        """Save all hints to the main app's data structure."""
        # Save the current hint being edited
        self.save_current_hint()
        
        # Make sure room exists in hints data
        if self.room_id not in self.app.hints_data:
            self.app.hints_data[self.room_id] = {}
        
        # Save the hints with the exact display name provided
        self.app.hints_data[self.room_id][self.prop_display_name] = self.hints_data
        
        # Save to file and update UI
        if self.app.save_hints():
            # Update the prop status
            self.app.update_prop_status(self.room_id, self.prop_original_name)
            messagebox.showinfo("Success", "Hints saved successfully!")
    
    def on_close(self):
        """Handle window close event."""
        # Tell the main app the popup is closed
        self.app.on_viewer_closed()
        # Close the window
        self.popup.destroy()

# --- Application Class ---

class HintBrowserApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Hint Browser & Editor")
        self.root.geometry("800x600")
        
        # --- Data structures ---
        self.prop_widgets = {}  # Stores UI widgets per prop
        self.prop_name_mappings = {}  # Room -> Props mapping from JSON
        self.hints_data = {}  # Hints data from saved_hints.json
        self._hint_viewer_popup = None
        
        # Initialize styles
        style = ttk.Style()
        style.configure("NoHints.TFrame", background="#ffcccc")  # Light red
        style.configure("HasHints.TFrame", background="#ccffcc")  # Light green
        
        # --- Load data ---
        self.load_prop_name_mappings()
        self.load_hints()
        
        # --- Create UI ---
        # Control Frame
        self.control_frame = ttk.Frame(self.root, padding=(10, 5, 10, 5))
        self.control_frame.pack(side=tk.TOP, fill=tk.X)
        
        self.refresh_button = ttk.Button(self.control_frame, text="Refresh", command=self.refresh_data)
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        # Scrollable Main Frame
        self.main_canvas = tk.Canvas(self.root)
        self.main_scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)
        
        self.main_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.main_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        self.scrollable_frame = ttk.Frame(self.main_canvas)
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        # Platform specific setup
        self.system_platform = platform.system()
        
        # Populate UI with rooms and props
        self.populate_rooms()

    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        self.prop_name_mappings = {}
        try:
            if PROP_MAPPING_FILE.exists():
                with open(PROP_MAPPING_FILE, 'r', encoding='utf-8') as f:
                    self.prop_name_mappings = json.load(f)
                print(f"Loaded prop name mappings. Found {len(self.prop_name_mappings)} rooms.")
            else:
                print(f"Prop name mapping file not found: {PROP_MAPPING_FILE}")
                messagebox.showwarning("Missing File", f"Prop name mapping file not found:\n{PROP_MAPPING_FILE}")
        except Exception as e:
            print(f"Error loading prop name mappings: {e}")
            messagebox.showerror("Load Error", f"Failed to load prop name mappings:\n{e}")

    def load_hints(self):
        """Load saved hints from the JSON file"""
        self.hints_data = {}
        try:
            if SAVED_HINTS_FILE.exists():
                with open(SAVED_HINTS_FILE, 'r', encoding='utf-8') as f:
                    full_data = json.load(f)
                    self.hints_data = full_data.get('rooms', {})
                print(f"Loaded hints for {len(self.hints_data)} rooms from {SAVED_HINTS_FILE}.")
            else:
                print(f"Saved hints file not found: {SAVED_HINTS_FILE}")
        except Exception as e:
            print(f"Error loading hints: {e}")
            messagebox.showerror("Load Error", f"Failed to load hints:\n{e}")

    def save_hints(self):
        """Saves the current state of hints_data back to the JSON file."""
        try:
            data_to_save = {"rooms": self.hints_data}
            with open(SAVED_HINTS_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Successfully saved hints to {SAVED_HINTS_FILE}")
            return True
        except Exception as e:
            print(f"Error saving hints: {e}")
            messagebox.showerror("Save Error", f"Could not save hints:\n{e}")
            return False

    def refresh_data(self):
        """Reloads data from files and refreshes the UI."""
        print("Refreshing data...")
        self.load_prop_name_mappings()
        self.load_hints()
        self.populate_rooms()
        print("Refresh complete.")

    def populate_rooms(self):
        """Populate the left panel with room sections based on available room directories."""
        # Clear existing rooms
        for child in self.scrollable_frame.winfo_children():
            child.destroy()
        self.prop_widgets.clear()
        
        # Add debug logging
        print(f"DEBUG: Starting populate_rooms()")
        logging.debug(f"Starting populate_rooms() - Found {len(self.prop_name_mappings.items())} items")

        # For each room in the mappings
        for row_idx, (room_name, room_data) in enumerate(sorted(self.prop_name_mappings.items())):
            room_id = ROOM_NAME_TO_ID_MAP.get(room_name)
            if not room_id:
                continue  # Skip rooms without ID mapping
            
            # Get the room display name
            room_display_name = ROOM_NAME_MAP.get(room_name, f"Room {room_id}")
            
            logging.debug(f"Creating section for room: {room_name} (ID: {room_id})")
            print(f"DEBUG: Creating section for room: {room_name} (ID: {room_id})")
            
            # Create a frame for this room
            room_frame = ttk.LabelFrame(self.scrollable_frame, text=f"{room_display_name} (ID: {room_id})")
            room_frame.grid(row=row_idx, column=0, padx=10, pady=10, sticky="ew")
            
            # Create a frame for props in this room
            props_frame = ttk.Frame(room_frame)
            props_frame.pack(fill="both", expand=True, padx=5, pady=5)
            
            # Configure the grid layout for props
            for i in range(PROP_GRID_COLUMNS):
                props_frame.columnconfigure(i, weight=1)
            
            # Get and sort props by order
            props_data = room_data.get("mappings", {})
            sorted_props = sorted(
                props_data.items(),
                key=lambda item: item[1].get("order", 999)
            )
            
            # Add each prop
            for p_idx, (prop_orig_name, prop_info) in enumerate(sorted_props):
                # Get display name
                prop_display_name = prop_info.get("display", prop_orig_name)
                
                # Calculate grid position
                p_row = p_idx // PROP_GRID_COLUMNS
                p_col = p_idx % PROP_GRID_COLUMNS
                
                # Add the prop block
                self.add_prop_block(
                    props_frame, 
                    room_id, 
                    prop_orig_name, 
                    prop_display_name,
                    p_row, 
                    p_col
                )
        
        logging.debug("Finished populate_rooms()")
        print("DEBUG: Finished populate_rooms()")

    def add_prop_block(self, parent_frame, room_id, prop_original_name, prop_display_name, grid_row, grid_col):
        """Adds a block for a prop to the grid."""
        # Create a frame with appropriate styling
        block_frame = ttk.Frame(parent_frame, padding=5)
        block_frame.grid(row=grid_row, column=grid_col, padx=5, pady=5, sticky="nsew")
        
        # Property name label
        name_label = ttk.Label(
            block_frame, 
            text=prop_display_name,
            font=("TkDefaultFont", 9, "bold"),
            anchor="center"
        )
        name_label.pack(pady=(0, 5), fill=tk.X)
        
        # Status area
        status_frame = ttk.Frame(
            block_frame,
            width=PROP_BLOCK_THUMBNAIL_SIZE[0],
            height=PROP_BLOCK_THUMBNAIL_SIZE[1]
        )
        status_frame.pack(expand=True, fill=tk.BOTH)
        status_frame.pack_propagate(False)
        
        status_label = ttk.Label(status_frame, anchor="center")
        status_label.pack(expand=True, fill=tk.BOTH)
        
        # Store widget references
        prop_id = (room_id, prop_original_name)
        self.prop_widgets[prop_id] = {
            'block_frame': block_frame,
            'name_label': name_label,
            'status_label': status_label,
            'display_name': prop_display_name
        }
        
        # Update visual status
        self.update_prop_status(room_id, prop_original_name)
        
        # Bind click events
        for widget in [block_frame, name_label, status_label]:
            widget.bind("<Button-1>", lambda e, rid=room_id, pname=prop_original_name: 
                         self.open_hint_viewer(rid, pname))
    
    def update_prop_status(self, room_id, prop_original_name):
        """Updates the visual status of a prop block based on hints."""
        prop_id = (room_id, prop_original_name)
        if prop_id not in self.prop_widgets:
            return
        
        widgets = self.prop_widgets[prop_id]
        display_name = widgets['display_name']
        status_label = widgets['status_label']
        block_frame = widgets['block_frame']
        
        # Check for hints
        hints = {}
        if room_id in self.hints_data:
            # Try exact match first
            if display_name in self.hints_data[room_id]:
                hints = self.hints_data[room_id][display_name]
            else:
                # Try case-insensitive
                for key in self.hints_data[room_id]:
                    if key.lower() == display_name.lower():
                        hints = self.hints_data[room_id][key]
                        break
        
        hint_count = len(hints)
        
        # Update visuals
        if hint_count > 0:
            status_label.configure(text=f"Hints: {hint_count}")
            block_frame.configure(style="HasHints.TFrame")
        else:
            status_label.configure(text="No Hints")
            block_frame.configure(style="NoHints.TFrame")
    
    def open_hint_viewer(self, room_id, prop_original_name):
        """Opens the hint viewer popup for the selected prop."""
        # Close existing popup if needed
        if hasattr(self, '_hint_viewer_popup') and self._hint_viewer_popup:
            try:
                self._hint_viewer_popup.popup.destroy()
            except (tk.TclError, AttributeError):
                pass  # Window might already be gone
        
        # Get display name
        prop_id = (room_id, prop_original_name)
        prop_display_name = self.prop_widgets.get(prop_id, {}).get('display_name', prop_original_name)
        
        # Create new popup
        self._hint_viewer_popup = HintViewerPopup(
            self.root, 
            self, 
            room_id, 
            prop_original_name, 
            prop_display_name
        )
    
    def open_folder(self, room_id, prop_original_name):
        """Opens the folder containing hint images for a prop."""
        room_folder_name = ROOM_ID_TO_NAME_MAP.get(room_id)
        if not room_folder_name:
            messagebox.showerror("Error", f"Cannot determine folder name for room ID {room_id}")
            return
        
        folder_path = BASE_IMAGE_DIR / room_folder_name / prop_original_name
        print(f"Opening folder: {folder_path}")
        
        # Create folder if it doesn't exist
        if not folder_path.is_dir():
            if messagebox.askyesno("Create Folder?", f"The folder doesn't exist:\n{folder_path}\n\nCreate it?"):
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                    print(f"Created folder: {folder_path}")
                except Exception as e:
                    messagebox.showerror("Error", f"Couldn't create folder:\n{e}")
                    return
        
        # Open the folder
        try:
            folder_path_str = str(folder_path.resolve())
            print(f"Opening folder path: {folder_path_str}")
            
            if self.system_platform == "Windows":
                # Use subprocess for Windows to handle spaces in paths properly
                subprocess.Popen(["explorer", folder_path_str])
            elif self.system_platform == "Darwin":  # macOS
                subprocess.Popen(["open", folder_path_str])
            else:  # Linux and other Unix-like
                subprocess.Popen(["xdg-open", folder_path_str])
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't open folder:\n{e}")
            print(f"Error opening folder: {e}")

    def on_viewer_closed(self):
        """Callback when the viewer popup is closed."""
        self._hint_viewer_popup = None

    def add_images(self, prop_dir: Path, file_paths: list[str]) -> int:
        """Handles copying images. Returns number of files successfully copied."""
        if not file_paths:
            return 0

        copied_count = 0
        errors = []
        for file_path in file_paths:
            try:
                source_path = Path(file_path)
                destination_path = prop_dir / source_path.name
                if destination_path.exists():
                   print(f"Skipping copy: {destination_path} already exists.")
                   continue
                shutil.copy2(source_path, destination_path)
                print(f"Copied {source_path.name} to {prop_dir.name}")
                copied_count += 1
            except Exception as e:
                err_msg = f"Failed to copy {Path(file_path).name}:\n{e}"
                print(f"Error copying {file_path} to {prop_dir}: {e}")
                errors.append(err_msg)

        if errors:
            messagebox.showerror("Copy Error(s)", "\n\n".join(errors))

        return copied_count

# --- Main Execution ---

if __name__ == "__main__":
    try:
        # Check if Pillow is installed
        try:
            from PIL import Image, ImageTk
        except ImportError:
            print("Error: Pillow library is required but not installed.")
            print("Please install it using: pip install Pillow")
            exit(1)
            
        # Ensure base directory exists
        if not BASE_IMAGE_DIR.exists():
            print(f"Creating base directory: {BASE_IMAGE_DIR}")
            try:
                BASE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory: {e}")
                exit(1)
                
        # Start the application
        root = tk.Tk()
        app = HintBrowserApp(root)
        root.mainloop()
    except Exception as e:
        print(f"Unhandled error: {e}")
        messagebox.showerror("Error", f"An unhandled error occurred:\n{e}") 