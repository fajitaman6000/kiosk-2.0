import tkinter as tk
from tkinter import ttk, filedialog
import os
import shutil
import platform # Added for OS-specific actions
import subprocess # Added for Linux/Mac
from pathlib import Path
from PIL import Image, ImageTk

# --- Constants ---
BASE_IMAGE_DIR = Path("admin/sync_directory/hint_image_files")
THUMBNAIL_SIZE = (64, 64) # Size for the preview thumbnails
MAX_THUMBNAILS_DISPLAYED = 5 # Max thumbnails to show per prop initially

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
        self.thumbnail_references = []

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


    def add_prop_section(self, parent_frame: ttk.Frame, prop_dir: Path, row: int):
        """Adds a section for a single prop to the parent (room) frame."""
        prop_name = prop_dir.name
        image_files = get_image_files(prop_dir)
        image_count = len(image_files)

        prop_frame = ttk.Frame(parent_frame, padding="5")
        # Use grid within the room_frame
        prop_frame.grid(row=row, column=0, padx=5, pady=2, sticky="ew")
        prop_frame.grid_columnconfigure(1, weight=1) # Allow thumbnail frame to expand

        # Prop Name and Count
        label_text = f"{prop_name} ({image_count} image{'s' if image_count != 1 else ''})"
        prop_label = ttk.Label(prop_frame, text=label_text)
        prop_label.grid(row=0, column=0, sticky="w", padx=(0, 10))

        # Thumbnail Area
        thumbnail_frame = ttk.Frame(prop_frame)
        thumbnail_frame.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        # Display thumbnails
        for i, img_path in enumerate(image_files[:MAX_THUMBNAILS_DISPLAYED]):
            thumb = create_thumbnail(img_path, THUMBNAIL_SIZE)
            if thumb:
                thumb_label = ttk.Label(thumbnail_frame, image=thumb)
                thumb_label.image = thumb # Keep reference
                thumb_label.pack(side=tk.LEFT, padx=2)
                self.thumbnail_references.append(thumb) # Store reference globally in the app

        if image_count > MAX_THUMBNAILS_DISPLAYED:
             ttk.Label(thumbnail_frame, text=f"... (+{image_count - MAX_THUMBNAILS_DISPLAYED})").pack(side=tk.LEFT, padx=2)
        elif image_count == 0:
             ttk.Label(thumbnail_frame, text="No images").pack(side=tk.LEFT, padx=2)

        # Add Images Button
        add_button = ttk.Button(
            prop_frame,
            text="Add Images...",
            command=lambda p=prop_dir: self.add_images(p)
        )
        add_button.grid(row=0, column=2, sticky="e")

        # Open Folder Button
        open_button = ttk.Button(
            prop_frame,
            text="Open Folder",
            command=lambda p=prop_dir: self.open_folder(p)
        )
        open_button.grid(row=0, column=3, sticky="e", padx=(5, 0))


    def add_images(self, prop_dir: Path):
        """Handles the 'Add Images' button click."""
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
                # Optional: Add check to prevent overwriting or rename if exists
                if destination_path.exists():
                   print(f"Skipping copy: {destination_path} already exists.")
                   continue
                shutil.copy2(source_path, destination_path) # copy2 preserves metadata
                print(f"Copied {source_path.name} to {prop_dir.name}")
                copied_count += 1
            except Exception as e:
                print(f"Error copying {file_path} to {prop_dir}: {e}")
                # Consider showing an error message to the user

        if copied_count > 0:
            print(f"Successfully copied {copied_count} image(s). Refreshing UI...")
            # Refresh the UI to show new counts and thumbnails
            self.populate_rooms()

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