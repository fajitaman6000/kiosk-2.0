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
POPUP_PREVIEW_SIZE = (600, 400) # Consider adjusting for text widget
ROOM_GRID_COLUMNS = 3
PROP_GRID_COLUMNS = 4 # Adjust as needed

# Map room folder names to room numbers (adjust if needed)
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
        
        # Create popup window
        self.popup = tk.Toplevel(parent)
        self.popup.title(f"Hint Editor: {prop_display_name} (Room {room_id})")
        self.popup.geometry("800x600")
        self.popup.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Main frame
        main_frame = ttk.Frame(self.popup, padding=10)
        main_frame.pack(expand=True, fill=tk.BOTH)
        
        # Info frame
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Title and information
        ttk.Label(info_frame, text=f"Room {room_id}: {prop_display_name}", 
                  font=("TkDefaultFont", 12, "bold")).pack(side=tk.LEFT, pady=5)
        
        # Button frame
        button_frame = ttk.Frame(info_frame)
        button_frame.pack(side=tk.RIGHT)
        
        ttk.Button(button_frame, text="Open Folder", 
                   command=lambda: self.app.open_folder(room_id, prop_original_name)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Save", 
                   command=self.save_hints).pack(side=tk.LEFT, padx=5)
        
        # Hints editor
        hints_frame = ttk.LabelFrame(main_frame, text="Hints")
        hints_frame.pack(expand=True, fill=tk.BOTH)
        
        # Hints text widget
        self.hints_text = tk.Text(hints_frame, wrap=tk.WORD, font=("TkDefaultFont", 10))
        text_scrollbar = ttk.Scrollbar(hints_frame, orient="vertical", command=self.hints_text.yview)
        self.hints_text.configure(yscrollcommand=text_scrollbar.set)
        
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.hints_text.pack(side=tk.LEFT, expand=True, fill=tk.BOTH)
        
        # Load existing hints
        self.load_hints()
    
    def load_hints(self):
        """Load existing hints into the text editor."""
        self.hints_text.delete("1.0", tk.END)  # Clear current content
        
        # Get hints for this prop
        hints_data = {}
        room_hints = self.app.hints_data.get(self.room_id, {})
        
        # Try to find hints by display name (case insensitive)
        for key in room_hints:
            if key.lower() == self.prop_display_name.lower():
                hints_data = room_hints[key]
                break
        
        # Convert hints to text
        if hints_data:
            hint_lines = []
            for level, hint in sorted(hints_data.items()):
                hint_lines.append(f"Level {level}:")
                hint_lines.append(hint)
                hint_lines.append("")  # Add blank line between hints
            
            self.hints_text.insert("1.0", "\n".join(hint_lines))
        
    def save_hints(self):
        """Save the hints from the text editor."""
        # Parse the hints text
        text = self.hints_text.get("1.0", tk.END).strip()
        lines = text.split("\n")
        
        hints = {}
        current_level = None
        current_hint_lines = []
        
        # Parse lines
        for line in lines:
            line = line.strip()
            if line.lower().startswith("level ") and ":" in line:
                # Save previous hint if any
                if current_level is not None and current_hint_lines:
                    hints[current_level] = "\n".join(current_hint_lines).strip()
                
                # Start new hint
                level_part = line.split(":")[0].replace("Level ", "").strip()
                try:
                    current_level = str(int(level_part))
                    current_hint_lines = []
                except:
                    # Invalid level format, treat as part of hint text
                    if current_level is not None:
                        current_hint_lines.append(line)
            else:
                # Add to current hint
                if current_level is not None:
                    current_hint_lines.append(line)
        
        # Save last hint
        if current_level is not None and current_hint_lines:
            hints[current_level] = "\n".join(current_hint_lines).strip()
        
        # Make sure room exists in hints data
        if self.room_id not in self.app.hints_data:
            self.app.hints_data[self.room_id] = {}
        
        # Save the hints with the exact display name provided
        self.app.hints_data[self.room_id][self.prop_display_name] = hints
        
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
            
            logging.debug(f"Creating section for room: {room_name} (ID: {room_id})")
            print(f"DEBUG: Creating section for room: {room_name} (ID: {room_id})")
            
            # Create a frame for this room
            room_frame = ttk.LabelFrame(self.scrollable_frame, text=f"{room_name.capitalize()} (ID: {room_id})")
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
        if hasattr(self, '_hint_viewer_popup') and self._hint_viewer_popup and self._hint_viewer_popup.winfo_exists():
            self._hint_viewer_popup.destroy()
        
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
        
        # Create folder if it doesn't exist
        if not folder_path.is_dir():
            if messagebox.askyesno("Create Folder?", f"The folder doesn't exist:\n{folder_path}\n\nCreate it?"):
                try:
                    folder_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("Error", f"Couldn't create folder:\n{e}")
                    return
        
        # Open the folder
        try:
            if self.system_platform == "Windows":
                os.startfile(folder_path)
            elif self.system_platform == "Darwin":  # macOS
                subprocess.Popen(["open", str(folder_path)])
            else:  # Linux and other Unix-like
                subprocess.Popen(["xdg-open", str(folder_path)])
        except Exception as e:
            messagebox.showerror("Error", f"Couldn't open folder:\n{e}")

    def on_viewer_closed(self):
        """Callback when the viewer popup is closed."""
        self._hint_viewer_popup = None

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