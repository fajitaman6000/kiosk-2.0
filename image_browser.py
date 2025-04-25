import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import platform # Added for OS-specific actions
import subprocess # Added for Linux/Mac
from pathlib import Path
from PIL import Image, ImageTk

# --- Constants ---
BASE_IMAGE_DIR = Path("admin/sync_directory/hint_image_files")
THUMBNAIL_SIZE = (64, 64) # Size for the preview thumbnails
POPUP_PREVIEW_SIZE = (600, 400)
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
        print(f"Error creating thumbnail for {image_path}: {e}")
        return None

# --- Application Class ---

class ImageBrowserApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Hint Image Browser")
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
        """Scans the base directory and populates the UI with rooms and props."""
        # Clear existing content and references
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.thumbnail_references.clear()
        self.prop_widgets.clear()

        if not BASE_IMAGE_DIR.is_dir():
            ttk.Label(self.scrollable_frame, text=f"Error: Base directory not found: {BASE_IMAGE_DIR}").pack(pady=10)
            return

        row_index = 0
        room_dirs = sorted([d for d in BASE_IMAGE_DIR.iterdir() if d.is_dir()])

        for room_dir in room_dirs:
            room_name = room_dir.name
            room_frame = ttk.LabelFrame(self.scrollable_frame, text=room_name, padding="10")
            room_frame.grid(row=row_index, column=0, padx=10, pady=5, sticky="ew")
            room_frame.grid_columnconfigure(0, weight=1) # Make prop frames expand
            self.scrollable_frame.grid_columnconfigure(0, weight=1) # Make room frames expand
            row_index += 1

            prop_dirs = sorted([d for d in room_dir.iterdir() if d.is_dir()])
            prop_row_index = 0
            if not prop_dirs:
                 ttk.Label(room_frame, text="No prop directories found.").grid(row=0, column=0, padx=5, pady=2, sticky="w")

            for prop_dir in prop_dirs:
                self.add_prop_section(room_frame, prop_dir, prop_row_index)
                prop_row_index += 1
        # Ensure canvas scroll region is updated after initial population
        self.scrollable_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))


    def add_prop_section(self, parent_frame: ttk.Frame, prop_dir: Path, row: int):
        """Adds a section for a single prop to the parent (room) frame."""
        prop_name = prop_dir.name
        image_files = sorted(get_image_files(prop_dir)) # Sort images by name
        image_count = len(image_files)

        prop_frame = ttk.Frame(parent_frame, padding="5")
        prop_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")
        # Grid config for the prop_frame
        prop_frame.grid_columnconfigure(1, weight=1) # Allow thumbnail frame to expand

        # --- Top Row: Label and Buttons ---
        top_frame = ttk.Frame(prop_frame)
        top_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))

        label_text = f"{prop_name}"
        prop_label = ttk.Label(top_frame, text=label_text, font=("TkDefaultFont", 10, "bold"))
        prop_label.pack(side=tk.LEFT, padx=(0, 10))

        # Image Count Label (will be updated)
        count_label = ttk.Label(top_frame, text=f"({image_count} image{'s' if image_count != 1 else ''})")
        count_label.pack(side=tk.LEFT, padx=(0, 20))

        # Buttons Frame
        buttons_frame = ttk.Frame(top_frame)
        buttons_frame.pack(side=tk.RIGHT)

        add_button = ttk.Button(
            buttons_frame,
            text="Add...",
            command=lambda p=prop_dir: self.add_images(p)
        )
        add_button.pack(side=tk.RIGHT, padx=(5, 0))

        open_button = ttk.Button(
            buttons_frame,
            text="Open Folder",
            command=lambda p=prop_dir: self.open_folder(p)
        )
        open_button.pack(side=tk.RIGHT)

        # --- Bottom Row: Thumbnails ---
        # Create a canvas for horizontal scrolling if needed
        thumb_canvas = tk.Canvas(prop_frame, height=THUMBNAIL_SIZE[1] + 30) # Height for thumb + name
        thumb_scrollbar = ttk.Scrollbar(prop_frame, orient="horizontal", command=thumb_canvas.xview)
        thumbnail_area_frame = ttk.Frame(thumb_canvas) # Frame inside canvas

        thumb_canvas.configure(xscrollcommand=thumb_scrollbar.set)

        thumb_canvas.grid(row=1, column=0, columnspan=2, sticky="ew")
        thumb_scrollbar.grid(row=2, column=0, columnspan=2, sticky="ew")

        thumb_canvas.create_window((0, 0), window=thumbnail_area_frame, anchor="nw")

        thumbnail_area_frame.bind("<Configure>", lambda e, c=thumb_canvas: c.configure(scrollregion=c.bbox("all")))

        # Store widgets for updates
        self.prop_widgets[prop_dir] = {
            'frame': prop_frame,
            'thumb_area': thumbnail_area_frame,
            'count_label': count_label,
            'thumb_canvas': thumb_canvas
        }
        self.thumbnail_references[prop_dir] = [] # Initialize list for this prop

        self.update_prop_thumbnails(prop_dir) # Call dedicated update function

    def update_prop_thumbnails(self, prop_dir: Path):
        """Clears and redraws the thumbnail area for a specific prop."""
        if prop_dir not in self.prop_widgets:
            return # Prop section not yet created or already removed

        widgets = self.prop_widgets[prop_dir]
        thumbnail_area_frame = widgets['thumb_area']
        count_label = widgets['count_label']
        thumb_canvas = widgets['thumb_canvas']

        # Clear existing thumbnails for this prop
        for widget in thumbnail_area_frame.winfo_children():
            widget.destroy()
        self.thumbnail_references[prop_dir] = [] # Clear specific references

        image_files = sorted(get_image_files(prop_dir))
        image_count = len(image_files)

        # Update count label
        count_label.configure(text=f"({image_count} image{'s' if image_count != 1 else ''})")

        if image_count == 0:
             ttk.Label(thumbnail_area_frame, text="No images").pack(side=tk.LEFT, padx=10, pady=5)
        else:
            # Display thumbnails with names
            for i, img_path in enumerate(image_files):
                thumb_container = ttk.Frame(thumbnail_area_frame)
                thumb_container.pack(side=tk.LEFT, padx=5, pady=5, anchor='nw')

                thumb = create_thumbnail(img_path, THUMBNAIL_SIZE)
                if thumb:
                    thumb_label = ttk.Label(thumb_container, image=thumb)
                    thumb_label.image = thumb # Keep reference
                    thumb_label.pack()
                    self.thumbnail_references[prop_dir].append(thumb) # Store reference

                    # Add filename label
                    filename_label = ttk.Label(thumb_container, text=img_path.name, wraplength=THUMBNAIL_SIZE[0], justify='center')
                    filename_label.pack()

                    # Bind click to open popup (passing prop_dir and index)
                    thumb_label.bind("<Button-1>", lambda e, p=prop_dir, idx=i: self.open_image_viewer(p, idx))
                    filename_label.bind("<Button-1>", lambda e, p=prop_dir, idx=i: self.open_image_viewer(p, idx))

        # Update the scrollregion of the thumbnail canvas
        thumbnail_area_frame.update_idletasks()
        thumb_canvas.configure(scrollregion=thumb_canvas.bbox("all"))
        # Reset scroll position to the beginning
        thumb_canvas.xview_moveto(0)


    def add_images(self, prop_dir: Path):
        """Handles the 'Add Images' button click. Refreshes only the specific prop."""
        file_paths = filedialog.askopenfilenames(
            title=f"Select images for {prop_dir.name}",
            filetypes=[("Image Files", "*.jpg *.jpeg *.png *.gif"), ("All Files", "*.*")]
        )

        if not file_paths:
            return # User cancelled

        copied_count = 0
        for file_path in file_paths:
            try:
                source_path = Path(file_path)
                destination_path = prop_dir / source_path.name
                if destination_path.exists():
                   print(f"Skipping copy: {destination_path} already exists.")
                   # Maybe ask user if they want to overwrite?
                   continue
                shutil.copy2(source_path, destination_path)
                print(f"Copied {source_path.name} to {prop_dir.name}")
                copied_count += 1
            except Exception as e:
                print(f"Error copying {file_path} to {prop_dir}: {e}")
                messagebox.showerror("Copy Error", f"Failed to copy {source_path.name}:\n{e}")

        if copied_count > 0:
            print(f"Successfully copied {copied_count} image(s). Refreshing UI for {prop_dir.name}...")
            # Refresh ONLY the affected prop's thumbnail section
            self.update_prop_thumbnails(prop_dir)
            # Also update the main canvas scroll region if layout changed significantly
            self.scrollable_frame.update_idletasks()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))

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
            print(f"Error opening folder {folder_path}: {e}")
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

        if not self.image_files:
            self.destroy()
            messagebox.showwarning("Image Viewer", "No images found in this directory.")
            return

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
        self.controls_frame.grid_columnconfigure(1, weight=1) # Center filename/index

        # Navigation Buttons
        self.prev_button = ttk.Button(self.controls_frame, text="< Prev", command=self.go_previous)
        self.prev_button.grid(row=0, column=0, padx=(0, 5))

        self.next_button = ttk.Button(self.controls_frame, text="Next >", command=self.go_next)
        self.next_button.grid(row=0, column=2, padx=(5, 20))

        # Filename and Index Label (centered)
        self.info_frame = ttk.Frame(self.controls_frame)
        self.info_frame.grid(row=0, column=1, sticky="ew")
        self.info_frame.grid_columnconfigure(0, weight=1)

        self.filename_label = ttk.Label(self.info_frame, text="Filename: ", anchor="center")
        self.filename_label.grid(row=0, column=0, sticky='ew')
        self.index_label = ttk.Label(self.info_frame, text="0 / 0", anchor="center")
        self.index_label.grid(row=1, column=0, sticky='ew')

        # Action Buttons
        self.rename_button = ttk.Button(self.controls_frame, text="Rename...", command=self.rename_image)
        self.rename_button.grid(row=0, column=3, padx=5)

        self.delete_button = ttk.Button(self.controls_frame, text="Delete", command=self.delete_image)
        self.delete_button.grid(row=0, column=4, padx=5)

        self.close_button = ttk.Button(self.controls_frame, text="Close", command=self.on_close)
        self.close_button.grid(row=0, column=5, padx=(20, 0))

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
            print(f"Error loading image {img_path} for preview: {e}")
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
            print(f"Renamed '{old_path.name}' to '{new_path.name}'")

            # Update internal list and refresh viewer
            self.load_image_list() # Reload the list to get sorted order potentially
            # Find the new index (should be same position if sorted)
            try:
                 new_index = self.image_files.index(new_path)
            except ValueError:
                 print("Warning: Renamed file not found in refreshed list?")
                 new_index = 0 # Fallback or handle error

            self.load_image(new_index) # Load the renamed image (same index)

            # Refresh thumbnails in the main app
            self.app_controller.update_prop_thumbnails(self.prop_dir)

        except OSError as e:
            print(f"Error renaming file {old_path} to {new_path}: {e}")
            messagebox.showerror("Rename Error", f"Could not rename file:\n{e}", parent=self)
        except Exception as e:
            print(f"Unexpected error during rename: {e}")
            messagebox.showerror("Rename Error", f"An unexpected error occurred:\n{e}", parent=self)

    def delete_image(self):
        """Deletes the currently displayed image file."""
        if not self.image_files or not (0 <= self.current_index < len(self.image_files)):
            return

        img_path = self.image_files[self.current_index]

        if not messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{img_path.name}'?", parent=self):
            return

        try:
            os.remove(img_path)
            print(f"Deleted '{img_path.name}'")

            # Update internal list
            del self.image_files[self.current_index]

            # Refresh thumbnails in the main app *before* loading next image in popup
            self.app_controller.update_prop_thumbnails(self.prop_dir)

            # Determine next image to show in popup
            new_index = self.current_index
            if new_index >= len(self.image_files):
                # If we deleted the last one, move to the new last one
                new_index = len(self.image_files) - 1

            if new_index < 0:
                # List is now empty
                 self.show_no_image()
            else:
                self.load_image(new_index)

        except OSError as e:
            print(f"Error deleting file {img_path}: {e}")
            messagebox.showerror("Delete Error", f"Could not delete file:\n{e}", parent=self)
        except Exception as e:
            print(f"Unexpected error during delete: {e}")
            messagebox.showerror("Delete Error", f"An unexpected error occurred:\n{e}", parent=self)


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
         print(f"Warning: Base image directory '{BASE_IMAGE_DIR}' does not exist. Creating it.")
         try:
            BASE_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
         except Exception as e:
             print(f"Error: Could not create base directory '{BASE_IMAGE_DIR}': {e}")
             exit(1)
    elif not BASE_IMAGE_DIR.is_dir():
        print(f"Error: The path '{BASE_IMAGE_DIR}' exists but is not a directory.")
        exit(1)


    root = tk.Tk()
    app = ImageBrowserApp(root)
    root.mainloop() 