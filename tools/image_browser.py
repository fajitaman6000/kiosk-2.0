import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import platform # Added for OS-specific actions
import subprocess # Added for Linux/Mac
from pathlib import Path
import json # Added for handling JSON hint files
from PIL import Image, ImageTk

# --- Constants ---
BASE_IMAGE_DIR = Path("admin/sync_directory/hint_image_files")
HINTS_FILE = Path("admin/saved_hints.json")
# THUMBNAIL_SIZE = (64, 64) # Old thumbnail size
PROP_BLOCK_THUMBNAIL_SIZE = (100, 75) # Thumbnail size for the prop block
POPUP_PREVIEW_SIZE = (600, 400)
# ROOM_GRID_COLUMNS = 3  # Removed this as we're stacking rooms vertically
PROP_GRID_COLUMNS = 4 # Adjust as needed
# MAX_THUMBNAILS_DISPLAYED = 5 # Commented out - we'll try showing all

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
        print(f"[image browser] Error creating thumbnail for {image_path}: {e}")
        return None

def get_room_id_from_folder(room_folder: str) -> str:
    """Convert a room folder name to its room ID."""
    room_map = {
        "casino": "1",
        "ma": "2", 
        "wizard": "3",
        "zombie": "4",
        "haunted": "5",
        "atlantis": "6",
        "time": "7"
    }
    return room_map.get(room_folder, "")

def update_image_references(old_filename: str, new_filename: str, prop_dir: Path) -> int:
    """
    Updates all hint references to an image in saved_hints.json when the image is renamed.
    Returns the number of references updated.
    """
    if not HINTS_FILE.exists():
        print(f"[image browser] Hints file not found: {HINTS_FILE}")
        return 0

    try:
        # Load the hints file
        with open(HINTS_FILE, 'r') as f:
            hints_data = json.load(f)
        
        # Determine room and prop from prop_dir
        # Path format is BASE_IMAGE_DIR/room_folder/prop_name
        room_folder = prop_dir.parent.name
        prop_name = prop_dir.name
        room_id = get_room_id_from_folder(room_folder)
        
        if not room_id:
            print(f"[image browser] Could not determine room ID for folder: {room_folder}")
            return 0
            
        update_count = 0
        
        # Check if this room exists in the hints data
        if room_id in hints_data.get('rooms', {}):
            # Check if this prop exists in the room
            if prop_name in hints_data['rooms'][room_id]:
                # Go through all hints for this prop
                for hint_name, hint_data in hints_data['rooms'][room_id][prop_name].items():
                    # If this hint uses the renamed image, update it
                    if hint_data.get('image') == old_filename:
                        hint_data['image'] = new_filename
                        update_count += 1
                        print(f"[image browser] Updated image reference in hint: {room_id}/{prop_name}/{hint_name}")
                
                # If any updates were made, save the file
                if update_count > 0:
                    with open(HINTS_FILE, 'w') as f:
                        json.dump(hints_data, f, indent=4)
                    print(f"[image browser] Saved {update_count} image reference updates to {HINTS_FILE}")
                
        return update_count
        
    except Exception as e:
        print(f"[image browser] Error updating image references: {e}")
        return 0

def remove_image_references(filename: str, prop_dir: Path) -> int:
    """
    Removes all hint references to an image in saved_hints.json when the image is deleted.
    Returns the number of references removed.
    """
    if not HINTS_FILE.exists():
        print(f"[image browser] Hints file not found: {HINTS_FILE}")
        return 0

    try:
        # Load the hints file
        with open(HINTS_FILE, 'r') as f:
            hints_data = json.load(f)
        
        # Determine room and prop from prop_dir
        # Path format is BASE_IMAGE_DIR/room_folder/prop_name
        room_folder = prop_dir.parent.name
        prop_name = prop_dir.name
        room_id = get_room_id_from_folder(room_folder)
        
        if not room_id:
            print(f"[image browser] Could not determine room ID for folder: {room_folder}")
            return 0
            
        remove_count = 0
        
        # Check if this room exists in the hints data
        if room_id in hints_data.get('rooms', {}):
            # Check if this prop exists in the room
            if prop_name in hints_data['rooms'][room_id]:
                # Go through all hints for this prop
                for hint_name, hint_data in hints_data['rooms'][room_id][prop_name].items():
                    # If this hint uses the deleted image, remove the image reference
                    if hint_data.get('image') == filename:
                        if 'image' in hint_data:
                            del hint_data['image']
                            remove_count += 1
                            print(f"[image browser] Removed image reference in hint: {room_id}/{prop_name}/{hint_name}")
                
                # If any updates were made, save the file
                if remove_count > 0:
                    with open(HINTS_FILE, 'w') as f:
                        json.dump(hints_data, f, indent=4)
                    print(f"[image browser] Saved {remove_count} image reference removals to {HINTS_FILE}")
                
        return remove_count
        
    except Exception as e:
        print(f"[image browser] Error removing image references: {e}")
        return 0

# --- Application Class ---

class ImageBrowserApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Hint Image Browser (FILES MUST BE SYNCED BEFORE IMAGES CAN BE SHOWN ON KIOSK-SIDE)")
        self.root.geometry("800x600")

        # Keep track of thumbnail image objects to prevent garbage collection
        self.thumbnail_references = {}
        # Keep track of widgets per prop for targeted updates
        self.prop_widgets = {}

        # --- Top Bar for Controls ---
        self.control_frame = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        self.control_frame.grid(row=0, column=0, sticky="ew")

        self.refresh_button = ttk.Button(self.control_frame, text="Refresh", command=self.populate_rooms)
        self.refresh_button.pack(side=tk.LEFT)

        # Make the main frame expandable below the control bar
        self.root.grid_rowconfigure(1, weight=1) # Row 1 is now the main content
        self.root.grid_columnconfigure(0, weight=1)

        # --- Scrollable Frame Setup ---
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.grid(row=1, column=0, sticky="nsew") # Changed row to 1

        self.canvas = tk.Canvas(self.main_frame)
        self.scrollbar = ttk.Scrollbar(self.main_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.scrollbar.grid(row=0, column=1, sticky="ns")
        self.main_frame.grid_rowconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Platform specific setup
        self.system_platform = platform.system()

        # --- Populate UI ---
        self.populate_rooms()


    def populate_rooms(self):
        """Scans the base directory and populates the UI with rooms and props in grids."""
        # Clear existing content and references
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.thumbnail_references.clear()
        self.prop_widgets.clear()

        if not BASE_IMAGE_DIR.is_dir():
            ttk.Label(self.scrollable_frame, text=f"Error: Base directory not found: {BASE_IMAGE_DIR}").pack(pady=10)
            return

        room_dirs = sorted([d for d in BASE_IMAGE_DIR.iterdir() if d.is_dir()])
        
        # Stack rooms vertically - each room gets its own row
        for idx, room_dir in enumerate(room_dirs):
            room_name = room_dir.name
            
            # Place each room in its own row (idx) and span all columns
            room_frame = ttk.LabelFrame(self.scrollable_frame, text=room_name, padding="10")
            room_frame.grid(row=idx, column=0, padx=10, pady=10, sticky="ew")
            
            # Make room frame expand horizontally
            self.scrollable_frame.grid_columnconfigure(0, weight=1)

            prop_dirs = sorted([d for d in room_dir.iterdir() if d.is_dir()])
            if not prop_dirs:
                 # Make the label span across potential prop columns if needed
                 ttk.Label(room_frame, text="No prop directories found.").grid(row=0, column=0, columnspan=PROP_GRID_COLUMNS, padx=5, pady=5, sticky="w")
            else:
                for p_idx, prop_dir in enumerate(prop_dirs):
                    prop_grid_row = p_idx // PROP_GRID_COLUMNS
                    prop_grid_col = p_idx % PROP_GRID_COLUMNS
                    self.add_prop_block(room_frame, prop_dir, prop_grid_row, prop_grid_col)
                    # Configure column weights within the room frame for prop distribution
                    room_frame.grid_columnconfigure(prop_grid_col, weight=1)

        # Ensure canvas scroll region is updated after initial population
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def add_prop_block(self, parent_room_frame: ttk.Frame, prop_dir: Path, grid_row: int, grid_col: int):
        """Adds a clickable block for a single prop to the parent (room) frame's grid."""
        prop_name = prop_dir.name

        # Create the main block frame
        block_frame = ttk.Frame(parent_room_frame, padding=5, relief=tk.RAISED, borderwidth=1)
        block_frame.grid(row=grid_row, column=grid_col, padx=5, pady=5, sticky="nsew")

        # Prop Name Label
        name_label = ttk.Label(block_frame, text=prop_name, anchor="center", font=("TkDefaultFont", 9, "bold"))
        name_label.pack(pady=(0, 5), fill=tk.X)

        # Thumbnail/Status Label Area (using a fixed-size frame)
        thumb_area_frame = ttk.Frame(
            block_frame,
            width=PROP_BLOCK_THUMBNAIL_SIZE[0],
            height=PROP_BLOCK_THUMBNAIL_SIZE[1],
            # style="Thumb.TFrame" # Optional: Define a style for padding/border if needed
        )
        thumb_area_frame.pack(expand=True, fill=tk.BOTH)
        # Prevent the frame from shrinking to fit the label
        thumb_area_frame.pack_propagate(False)

        thumb_label = ttk.Label(thumb_area_frame, anchor="center")
        # Pack the label to fill the frame, it will center automatically
        thumb_label.pack(expand=True, fill=tk.BOTH)

        # Store widgets needed for updates
        self.prop_widgets[prop_dir] = {
            'block_frame': block_frame,
            'name_label': name_label,
            'thumb_label': thumb_label
        }
        # Initialize thumbnail reference storage for this prop
        self.thumbnail_references[prop_dir] = None

        # Initial update of the block's content (thumbnail or text)
        self.update_prop_block(prop_dir)

        # --- Bind Clicks --- 
        # Bind click on all elements within the block to open the viewer
        for widget in [block_frame, name_label, thumb_label]:
             widget.bind("<Button-1>", lambda e, p=prop_dir: self.open_image_viewer(p, 0))


    def update_prop_block(self, prop_dir: Path):
        """Updates the content (thumbnail or text) of a specific prop block."""
        if prop_dir not in self.prop_widgets:
            print(f"[image browser] Warning: Cannot update block for {prop_dir.name}, widgets not found.")
            return

        widgets = self.prop_widgets[prop_dir]
        thumb_label = widgets['thumb_label']
        name_label = widgets['name_label']

        # Always clear the label's current image reference before updating.
        thumb_label.configure(image='')
        thumb_label.image = None
        self.thumbnail_references[prop_dir] = None # Also clear our internal reference tracking

        image_files = sorted(get_image_files(prop_dir))
        image_count = len(image_files)

        # Update the name label with the count
        prop_name = prop_dir.name
        name_label.configure(text=f"{prop_name} ({image_count})")

        if image_count == 0:
            thumb_label.configure(text="NO IMAGES", compound=tk.CENTER, foreground="red")
        else:
            first_image_path = image_files[0]
            thumb = create_thumbnail(first_image_path, PROP_BLOCK_THUMBNAIL_SIZE)
            if thumb:
                thumb_label.configure(image=thumb, compound=tk.NONE) # Show only image
                thumb_label.image = thumb # Keep reference
                self.thumbnail_references[prop_dir] = thumb # Store reference
            else:
                thumb_label.configure(text="IMG ERR", compound=tk.CENTER, foreground="orange")


    def add_images(self, prop_dir: Path, file_paths: list[str]) -> int:
        """Handles copying images. Returns number of files successfully copied."""
        # This is now called FROM the popup, file_paths are provided
        if not file_paths:
            return 0

        copied_count = 0
        errors = []
        for file_path in file_paths:
            try:
                source_path = Path(file_path)
                destination_path = prop_dir / source_path.name
                if destination_path.exists():
                   print(f"[image browser] Skipping copy: {destination_path} already exists.")
                   # Future: Could ask user to overwrite/rename via dialog
                   continue
                shutil.copy2(source_path, destination_path)
                print(f"[image browser] Copied {source_path.name} to {prop_dir.name}")
                copied_count += 1
            except Exception as e:
                err_msg = f"Failed to copy {Path(file_path).name}:\n{e}"
                print(f"[image browser] Error copying {file_path} to {prop_dir}: {e}")
                errors.append(err_msg)

        if errors:
            messagebox.showerror("Copy Error(s)", "\n\n".join(errors))

        if copied_count > 0:
            print(f"[image browser] Successfully copied {copied_count} image(s) to {prop_dir.name}. Refreshing block...")
            # Refresh ONLY the affected prop's block
            self.update_prop_block(prop_dir)
            # Update main scroll region in case block size changed (e.g., NO IMAGES -> thumb)
            self.scrollable_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

        return copied_count

    def open_folder(self, folder_path: Path):
        """Opens the specified folder in the system's file explorer."""
        try:
            if self.system_platform == "Windows":
                os.startfile(folder_path)
            elif self.system_platform == "Darwin":  # macOS
                subprocess.Popen(["open", str(folder_path)])
            else:  # Linux and other Unix-like
                subprocess.Popen(["xdg-open", str(folder_path)])
        except Exception as e:
            print(f"[image browser] Error opening folder {folder_path}: {e}")
            # Optionally show an error message in the UI

    def open_image_viewer(self, prop_dir: Path, initial_index: int):
        """Opens the image viewer popup for the selected prop and image."""
        # Only allow one viewer popup at a time maybe?
        if hasattr(self, '_viewer_popup') and self._viewer_popup and self._viewer_popup.winfo_exists():
            self._viewer_popup.lift()
            self._viewer_popup.focus_set()
            # Optionally load the new image if different prop/index?
            # For now, just bring the existing one to front.
            return

        self._viewer_popup = ImageViewerPopup(self.root, self, prop_dir, initial_index)
        # No mainloop here, let it run alongside the main app
        # self._viewer_popup.mainloop()

    def on_viewer_closed(self):
        """Callback when the viewer popup is closed."""
        self._viewer_popup = None


# --- Image Viewer Popup Class ---

class ImageViewerPopup(tk.Toplevel):
    def __init__(self, parent, app_controller, prop_dir: Path, initial_index: int):
        super().__init__(parent)
        self.parent = parent
        self.app_controller = app_controller # Reference to ImageBrowserApp
        self.prop_dir = prop_dir
        self.load_image_list()
        self.current_index = initial_index

        # Register cleanup
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Ensure index is valid if list changed somehow
        if not (0 <= self.current_index < len(self.image_files)):
            self.current_index = 0 if self.image_files else -1

        self.title(f"Image Viewer - {prop_dir.name}")
        self.geometry("700x550") # Initial geometry
        self.minsize(500, 400) # Prevent making it too small

        # Make popup modal (optional - uncomment if needed)
        # self.grab_set()
        # self.focus_set()
        # self.transient(parent)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # --- Image Display Area ---
        self.image_label = ttk.Label(self, anchor='center')
        self.image_label.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        # --- Info and Controls Area ---
        self.controls_frame = ttk.Frame(self, padding="10")
        self.controls_frame.grid(row=1, column=0, sticky="ew")

        # Configure columns for layout
        # Columns: 0: Prev, 1: Spacer, 2: Info, 3: Spacer, 4: Next, 5: Add, 6: Open, 7: Rename, 8: Delete, 9: Close
        self.controls_frame.grid_columnconfigure(2, weight=1) # Center filename/index
        self.controls_frame.grid_columnconfigure(0, weight=0)
        self.controls_frame.grid_columnconfigure(4, weight=0)
        # Add weights for other columns if needed for spacing

        # Navigation Buttons
        self.prev_button = ttk.Button(self.controls_frame, text="< Prev", command=self.go_previous)
        self.prev_button.grid(row=0, column=0, padx=(0, 5), sticky='w')

        self.next_button = ttk.Button(self.controls_frame, text="Next >", command=self.go_next)
        self.next_button.grid(row=0, column=4, padx=(5, 10), sticky='e') # Increased padding before actions

        # Filename and Index Label (centered)
        self.info_frame = ttk.Frame(self.controls_frame)
        self.info_frame.grid(row=0, column=2, sticky="ew") # Spans middle column
        self.info_frame.grid_columnconfigure(0, weight=1)

        self.filename_label = ttk.Label(self.info_frame, text="Filename: ", anchor="center")
        self.filename_label.grid(row=0, column=0, sticky='ew')
        self.index_label = ttk.Label(self.info_frame, text="0 / 0", anchor="center")
        self.index_label.grid(row=1, column=0, sticky='ew')

        # Action Buttons Frame (Grouped on the right)
        self.actions_frame = ttk.Frame(self.controls_frame)
        self.actions_frame.grid(row=0, column=5, columnspan=5, sticky='e') # Place actions starting from col 5

        self.add_button = ttk.Button(self.actions_frame, text="Add...", command=self.add_images_from_popup)
        self.add_button.pack(side=tk.LEFT, padx=3)

        self.open_folder_button = ttk.Button(self.actions_frame, text="Open Folder", command=self.open_folder_from_popup)
        self.open_folder_button.pack(side=tk.LEFT, padx=3)

        self.rename_button = ttk.Button(self.actions_frame, text="Rename...", command=self.rename_image)
        # self.rename_button.grid(row=0, column=3, padx=5)
        self.rename_button.pack(side=tk.LEFT, padx=3)

        self.delete_button = ttk.Button(self.actions_frame, text="Delete", command=self.delete_image)
        # self.delete_button.grid(row=0, column=4, padx=5)
        self.delete_button.pack(side=tk.LEFT, padx=3)

        self.close_button = ttk.Button(self.actions_frame, text="Close", command=self.on_close)
        # self.close_button.grid(row=0, column=5, padx=(20, 0))
        self.close_button.pack(side=tk.LEFT, padx=(10, 0)) # Add more padding before close

        # --- Load Initial Image ---
        if self.current_index != -1:
            self.load_image(self.current_index)
        else:
            self.show_no_image()

    def on_close(self):
        """Handle window close actions."""
        self.app_controller.on_viewer_closed() # Notify main app
        self.destroy()

    def load_image_list(self):
        """Loads or reloads the list of image files for the current prop."""
        self.image_files = sorted(get_image_files(self.prop_dir))

    def show_no_image(self):
        """Displays a message when no image is available."""
        self.image_label.configure(image='', text='No image available')
        self.image_label.image = None
        self.filename_label.configure(text="Filename: N/A")
        self.index_label.configure(text="0 / 0")
        self.update_button_states()

    def load_image(self, index: int):
        """Loads and displays the image at the specified index."""
        if not self.image_files or not (0 <= index < len(self.image_files)):
            self.show_no_image()
            return

        self.current_index = index
        img_path = self.image_files[self.current_index]

        # Update info labels
        self.filename_label.configure(text=f"Filename: {img_path.name}")
        self.index_label.configure(text=f"{self.current_index + 1} / {len(self.image_files)}")

        # Load and display the image (resized for preview)
        try:
            img = Image.open(img_path)
            # Make a copy to avoid modifying the original image object with thumbnail
            img_copy = img.copy()
            img_copy.thumbnail(POPUP_PREVIEW_SIZE, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img_copy)

            self.image_label.configure(image=photo, text='') # Clear text if image loads
            self.image_label.image = photo # Keep reference
        except Exception as e:
            print(f"[image browser] Error loading image {img_path} for preview: {e}")
            self.image_label.configure(image='', text=f"Error loading\n{img_path.name}")
            self.image_label.image = None
            messagebox.showerror("Image Load Error", f"Could not load image:\n{img_path.name}\n\nError: {e}")

        self.update_button_states()

    def update_button_states(self):
        """Enable/disable buttons based on current state."""
        num_images = len(self.image_files)

        if num_images == 0:
            self.prev_button.config(state=tk.DISABLED)
            self.next_button.config(state=tk.DISABLED)
            self.rename_button.config(state=tk.DISABLED)
            self.delete_button.config(state=tk.DISABLED)
        else:
            self.prev_button.config(state=tk.NORMAL if self.current_index > 0 else tk.DISABLED)
            self.next_button.config(state=tk.NORMAL if self.current_index < num_images - 1 else tk.DISABLED)
            self.rename_button.config(state=tk.NORMAL)
            self.delete_button.config(state=tk.NORMAL)
        # Add/Open Folder are always enabled (related to the prop, not specific image)
        self.add_button.config(state=tk.NORMAL)
        self.open_folder_button.config(state=tk.NORMAL)

    def go_previous(self):
        if self.current_index > 0:
            self.load_image(self.current_index - 1)

    def go_next(self):
        if self.current_index < len(self.image_files) - 1:
            self.load_image(self.current_index + 1)

    def rename_image(self):
        """Renames the currently displayed image file."""
        if not self.image_files or not (0 <= self.current_index < len(self.image_files)):
            return

        old_path = self.image_files[self.current_index]
        old_name = old_path.name
        old_name_stem = old_path.stem
        old_suffix = old_path.suffix

        new_name_stem = simpledialog.askstring(
            "Rename Image",
            f"Enter new name for '{old_path.name}' (without extension):",
            initialvalue=old_name_stem,
            parent=self
        )

        if not new_name_stem or new_name_stem == old_name_stem:
            return # User cancelled or didn't change name

        # Basic validation (can be enhanced)
        if any(c in r'<>:"/\|?*' for c in new_name_stem):
            messagebox.showerror("Invalid Name", "Filename contains invalid characters.", parent=self)
            return

        new_name = new_name_stem + old_suffix
        new_path = self.prop_dir / new_name

        if new_path.exists():
            messagebox.showerror("Rename Error", f"A file named '{new_name}' already exists.", parent=self)
            return

        try:
            os.rename(old_path, new_path)
            print(f"[image browser] Renamed '{old_path.name}' to '{new_path.name}'")

            # Update references in saved_hints.json
            updated_count = update_image_references(old_name, new_name, self.prop_dir)
            if updated_count > 0:
                print(f"[image browser] Updated {updated_count} hint references to this image")
                messagebox.showinfo("References Updated", 
                                   f"Updated {updated_count} hint references to point to the renamed image.", 
                                   parent=self)

            # Update internal list and refresh viewer
            self.load_image_list() # Reload the list to get sorted order potentially
            # Find the new index (should be same position if sorted)
            try:
                 new_index = self.image_files.index(new_path)
            except ValueError:
                 print(f"[image browser] Warning: Renamed file not found in refreshed list?")
                 new_index = 0 # Fallback or handle error

            self.load_image(new_index) # Load the renamed image (same index)

            # Refresh thumbnails in the main app
            self.app_controller.update_prop_block(self.prop_dir)

        except OSError as e:
            print(f"[image browser] Error renaming file {old_path} to {new_path}: {e}")
            messagebox.showerror("Rename Error", f"Could not rename file:\n{e}", parent=self)
        except Exception as e:
            print(f"[image browser] Unexpected error during rename: {e}")
            messagebox.showerror("Rename Error", f"An unexpected error occurred:\n{e}", parent=self)

    def delete_image(self):
        """Deletes the currently displayed image file."""
        if not self.image_files or not (0 <= self.current_index < len(self.image_files)):
            return

        img_path = self.image_files[self.current_index]
        img_name = img_path.name

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{img_name}'?", parent=self):
            return

        try:
            # Check for references in saved hints before deletion
            reference_count = 0
            try:
                # Load the hints file to check references
                if HINTS_FILE.exists():
                    with open(HINTS_FILE, 'r') as f:
                        hints_data = json.load(f)
                    
                    # Get room ID
                    room_folder = self.prop_dir.parent.name
                    prop_name = self.prop_dir.name
                    room_id = get_room_id_from_folder(room_folder)
                    
                    # Count references
                    if room_id and room_id in hints_data.get('rooms', {}):
                        if prop_name in hints_data['rooms'][room_id]:
                            for hint_name, hint_data in hints_data['rooms'][room_id][prop_name].items():
                                if hint_data.get('image') == img_name:
                                    reference_count += 1
            except Exception as e:
                print(f"[image browser] Error checking hint references: {e}")
            
            # Warn if references exist
            if reference_count > 0:
                confirm = messagebox.askyesno(
                    "References Found",
                    f"This image is used in {reference_count} hint(s). Delete anyway and remove all references?",
                    parent=self
                )
                if not confirm:
                    return

            # Delete the file
            os.remove(img_path)
            print(f"[image browser] Deleted '{img_name}'")

            # --- Keep the popup's image clearing ---
            # Clear the image from the popup's display immediately
            self.image_label.configure(image='')
            self.image_label.image = None # Explicitly clear the reference
            self.image_label.update_idletasks() # Force the UI update now
            # --- End popup clearing ---

            # Remove references from saved_hints.json
            removed_count = remove_image_references(img_name, self.prop_dir)
            if removed_count > 0:
                print(f"[image browser] Removed {removed_count} hint references to the deleted image")
                messagebox.showinfo("References Removed",
                                   f"Removed {removed_count} hint references to the deleted image.",
                                   parent=self)

            # Update internal list
            del self.image_files[self.current_index]

            # Refresh thumbnails in the main app *before* determining next image in popup
            self.app_controller.update_prop_block(self.prop_dir)

            # Determine next image to show in popup
            new_index = self.current_index
            if new_index >= len(self.image_files):
                new_index = len(self.image_files) - 1

            if new_index < 0:
                self.show_no_image()
            else:
                self.load_image(new_index)

        except OSError as e:
            print(f"[image browser] Error deleting file {img_path}: {e}")
            messagebox.showerror("Delete Error", f"Could not delete file:\n{e}", parent=self)
        except Exception as e:
            print(f"[image browser] Unexpected error during delete: {e}")
            messagebox.showerror("Delete Error", f"An unexpected error occurred:\n{e}", parent=self)

    # --- New methods for relocated buttons ---

    def add_images_from_popup(self):
        """Handles the 'Add Images' button click from the popup."""
        file_paths = filedialog.askopenfilenames(
            title=f"Select images for {self.prop_dir.name}",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.gif"), ("All Files", "*.*")]
        )

        if not file_paths:
            return # User cancelled

        # Call the main app's add_images method
        copied_count = self.app_controller.add_images(self.prop_dir, file_paths)

        if copied_count > 0:
            # Reload image list within the popup
            self.load_image_list()
            # Try to stay on the same image if possible, otherwise go to last?
            # For simplicity, let's just reload the current index if it's still valid,
            # otherwise go to the last image of the new list.
            new_index = self.current_index
            if not (0 <= new_index < len(self.image_files)):
                new_index = len(self.image_files) - 1
            
            if new_index >= 0:
                self.load_image(new_index)
            else:
                self.show_no_image() # Should not happen if we copied files, but safety check

            # Bring popup to front
            self.lift()
            self.focus_set()

    def open_folder_from_popup(self):
        """Calls the main app's open_folder method."""
        self.app_controller.open_folder(self.prop_dir)


# --- Main Execution ---

if __name__ == "__main__":
    # Check if Pillow is installed
    try:
        from PIL import Image, ImageTk
    except ImportError:
        print("Error: Pillow library is required but not installed.")
        print("Please install it using: pip install Pillow")
        exit(1) # Exit if Pillow is not available

    # Ensure base directory exists
    if not BASE_IMAGE_DIR.exists():
         print(f"[image browser] Warning: Base image directory '{BASE_IMAGE_DIR}' does not exist. Creating it.")
         try:
            BASE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
         except Exception as e:
             print(f"[image browser] Error: Could not create base directory '{BASE_IMAGE_DIR}': {e}")
             exit(1)
    elif not BASE_IMAGE_DIR.is_dir():
        print(f"[image browser] Error: The path '{BASE_IMAGE_DIR}' exists but is not a directory.")
        exit(1)


    root = tk.Tk()
    app = ImageBrowserApp(root)
    root.mainloop() 