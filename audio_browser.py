import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import shutil
import platform # Added for OS-specific actions
import subprocess # Added for Linux/Mac
from pathlib import Path
# Removed PIL imports: from PIL import Image, ImageTk
# Import pygame for audio playback
import pygame
import threading # Still needed for potentially long operations like initial load?
# Check if pygame was initialized successfully
PYGAME_MIXER_INITIALIZED = False
try:
    pygame.init() # Initialize all pygame modules
    pygame.mixer.init() # Initialize the mixer module
    PYGAME_MIXER_INITIALIZED = True
    print("Pygame mixer initialized successfully.")
except pygame.error as e:
    print(f"Error initializing pygame mixer: {e}")
    print("Audio playback will be disabled.")
    messagebox.showerror("Pygame Error", f"Failed to initialize audio playback: {e}")
# Removed playsound imports and checks


# --- Constants ---
# Changed BASE_IMAGE_DIR to BASE_AUDIO_DIR and updated path
BASE_AUDIO_DIR = Path("admin/sync_directory/hint_audio_files")
# Removed THUMBNAIL_SIZE
# PROP_BLOCK_THUMBNAIL_SIZE = (100, 75) # No longer needed for visual size
POPUP_PREVIEW_SIZE = (400, 200) # Adjusted size for audio player
ROOM_GRID_COLUMNS = 3
PROP_GRID_COLUMNS = 4 # Adjust as needed
# MAX_THUMBNAILS_DISPLAYED = 5 # Commented out

# --- Helper Functions ---

# Renamed get_image_files to get_audio_files and updated extensions
def get_audio_files(prop_dir: Path) -> list[Path]:
    """Gets a list of audio files (mp3, wav, ogg) in a directory."""
    audio_files = []
    if prop_dir.is_dir():
        for item in prop_dir.iterdir():
            # Added common audio formats
            if item.is_file() and item.suffix.lower() in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
                audio_files.append(item)
    return audio_files

# Removed create_thumbnail function

# --- Application Class ---

# Renamed ImageBrowserApp to AudioBrowserApp
class AudioBrowserApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        # Updated title
        self.root.title("Hint Audio Browser")
        self.root.geometry("800x600")

        # Keep track of widgets per prop for targeted updates
        self.prop_widgets = {}
        # Removed thumbnail_references

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

        # Track if audio player popup is open
        self.player_popup_open = False
        self.player_popup = None # Reference to the popup window

        # --- Populate UI ---
        self.populate_rooms()

        # Handle main window closing
        self.root.protocol("WM_DELETE_WINDOW", self.on_app_close)


    def on_app_close(self):
        """Cleanup resources when the main application window is closed."""
        print("DEBUG: on_app_close called") # Debug print
        if self.player_popup_open and self.player_popup:
            self.player_popup.on_close() # Ensure popup cleans up
        if PYGAME_MIXER_INITIALIZED:
            pygame.mixer.quit()
            pygame.quit() # Quit pygame itself
        print("DEBUG: destroying root window") # Debug print
        self.root.destroy()


    def populate_rooms(self):
        """Scans the base directory and populates the UI with rooms and props in grids."""
        # Clear existing content and references
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        # Removed self.thumbnail_references.clear()
        self.prop_widgets.clear()

        # Updated directory check
        if not BASE_AUDIO_DIR.is_dir():
            ttk.Label(self.scrollable_frame, text=f"Error: Base directory not found: {BASE_AUDIO_DIR}").pack(pady=10)
            return

        # Updated directory variable name
        room_dirs = sorted([d for d in BASE_AUDIO_DIR.iterdir() if d.is_dir()])
        num_rooms = len(room_dirs)

        for idx, room_dir in enumerate(room_dirs):
            room_name = room_dir.name
            grid_row = idx // ROOM_GRID_COLUMNS
            grid_col = idx % ROOM_GRID_COLUMNS

            room_frame = ttk.LabelFrame(self.scrollable_frame, text=room_name, padding="10")
            room_frame.grid(row=grid_row, column=grid_col, padx=10, pady=10, sticky="nsew")
            # Configure column weights within the scrollable frame for room distribution
            self.scrollable_frame.grid_columnconfigure(grid_col, weight=1)

            prop_dirs = sorted([d for d in room_dir.iterdir() if d.is_dir()])
            prop_row_index = 0
            prop_col_index = 0
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

        # Status Label Area (replaces thumbnail area)
        # Using a simpler label directly, no fixed size frame needed unless desired
        status_label = ttk.Label(block_frame, anchor="center")
        status_label.pack(pady=5, expand=True)


        # Store widgets needed for updates (using 'status_label' instead of 'thumb_label')
        self.prop_widgets[prop_dir] = {
            'block_frame': block_frame,
            'name_label': name_label,
            'status_label': status_label # Changed from thumb_label
        }
        # Removed thumbnail reference storage

        # Initial update of the block's content (status text)
        self.update_prop_block(prop_dir)

        # --- Bind Clicks ---
        # Bind click on all elements within the block to open the player
        # Renamed open_image_viewer to open_audio_player
        for widget in [block_frame, name_label, status_label]: # Updated widget list
             widget.bind("<Button-1>", lambda e, p=prop_dir: self.open_audio_player(p, 0))


    def update_prop_block(self, prop_dir: Path):
        """Updates the content (status text) of a specific prop block."""
        if prop_dir not in self.prop_widgets:
            print(f"Warning: Cannot update block for {prop_dir.name}, widgets not found.")
            return

        widgets = self.prop_widgets[prop_dir]
        # Updated widget name
        status_label = widgets['status_label']
        name_label = widgets['name_label']

        # Use get_audio_files
        audio_files = sorted(get_audio_files(prop_dir))
        audio_count = len(audio_files)

        # Update the name label with the count
        prop_name = prop_dir.name
        name_label.configure(text=f"{prop_name} ({audio_count})")

        # Removed thumbnail logic

        # Update status label based on audio file presence
        if audio_count == 0:
            status_label.configure(text="NO AUDIO", foreground="red")
        else:
            # Using a simple checkmark or count as indicator
            status_label.configure(text="✅ Audio Present", foreground="green")
            # Or show count: status_label.configure(text=f"{audio_count} file(s)", foreground="green")


    # Renamed add_images to add_audio_files
    def add_audio_files(self, prop_dir: Path, file_paths: list[str]) -> int:
        """Handles copying audio files. Returns number of files successfully copied."""
        # This is now called FROM the popup, file_paths are provided
        if not file_paths:
            return 0

        copied_count = 0
        errors = []
        for file_path in file_paths:
            try:
                source_path = Path(file_path)
                # Check if it's an audio file before copying
                if source_path.suffix.lower() not in ['.mp3', '.wav', '.ogg', '.flac', '.m4a']:
                    print(f"Skipping non-audio file: {source_path.name}")
                    continue

                destination_path = prop_dir / source_path.name
                if destination_path.exists():
                   print(f"Skipping copy: {destination_path} already exists.")
                   # Future: Could ask user to overwrite/rename via dialog
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

        if copied_count > 0:
            # Updated print message
            print(f"Successfully copied {copied_count} audio file(s) to {prop_dir.name}. Refreshing block...")
            # Refresh ONLY the affected prop's block
            self.update_prop_block(prop_dir)

        return copied_count # Return count for potential use in popup


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

    # Renamed open_image_viewer to open_audio_player
    def open_audio_player(self, prop_dir: Path, initial_index: int):
        """Opens the audio player popup window for the selected prop."""
        # Prevent opening multiple popups
        if self.player_popup_open:
            print("Audio player popup already open.")
            if self.player_popup:
                self.player_popup.lift() # Bring existing popup to front
            return

        # Renamed ImageViewerPopup to AudioPlayerPopup
        self.player_popup = AudioPlayerPopup(
            parent=self.root,
            app_controller=self,
            prop_dir=prop_dir,
            initial_index=initial_index
        )
        self.player_popup_open = True
        self.player_popup.protocol("WM_DELETE_WINDOW", self.on_player_closed) # Handle closing via 'X'

    # Renamed on_viewer_closed to on_player_closed
    def on_player_closed(self):
        """Callback when the audio player popup is closed."""
        # Called by the popup's on_close method *before* it's destroyed
        print("Audio player popup closed notification received.")
        self.player_popup_open = False
        self.player_popup = None # Clear reference


# --- Audio Player Popup Class ---

# Renamed ImageViewerPopup to AudioPlayerPopup
class AudioPlayerPopup(tk.Toplevel):
    # Update __init__ signature and content
    def __init__(self, parent, app_controller, prop_dir: Path, initial_index: int):
        super().__init__(parent)
        self.app_controller = app_controller # Reference to the main app
        self.prop_dir = prop_dir
        self.audio_files = []
        self.current_index = -1
        # Removed playback_process
        # Add state for paused status
        self.is_paused = False
        # Variable to store the id for the after loop
        self._after_id_playback_check = None

        # Updated title and geometry
        self.title(f"Audio Player - {prop_dir.name}")
        self.geometry(f"{POPUP_PREVIEW_SIZE[0]}x{POPUP_PREVIEW_SIZE[1]}") # Use updated constant
        self.minsize(350, 150) # Set a minimum size

        # --- UI Elements ---
        self.main_frame = ttk.Frame(self, padding="10")
        self.main_frame.pack(expand=True, fill=tk.BOTH)
        self.main_frame.grid_rowconfigure(1, weight=1) # Allow controls/info to expand if needed
        self.main_frame.grid_columnconfigure(0, weight=1)


        # Top frame for file info and navigation
        self.top_frame = ttk.Frame(self.main_frame)
        # self.top_frame.pack(fill=tk.X, pady=(0, 10))
        self.top_frame.grid(row=0, column=0, sticky="ew", pady=(0,10))

        self.prev_button = ttk.Button(self.top_frame, text="< Previous", command=self.go_previous, state=tk.DISABLED)
        # self.prev_button.pack(side=tk.LEFT, padx=5)
        self.prev_button.grid(row=0, column=0, padx=(0,5))

        # Label to display current file name and index
        self.filename_label = ttk.Label(self.top_frame, text="No audio files.", anchor=tk.CENTER)
        # self.filename_label.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=5)
        self.filename_label.grid(row=0, column=1, sticky="ew", padx=5)

        self.next_button = ttk.Button(self.top_frame, text="Next >", command=self.go_next, state=tk.DISABLED)
        # self.next_button.pack(side=tk.LEFT, padx=5)
        self.next_button.grid(row=0, column=2, padx=(5,0))

        self.top_frame.grid_columnconfigure(1, weight=1) # Allow filename label to expand

        # Middle frame for playback controls
        self.controls_frame = ttk.Frame(self.main_frame)
        # self.controls_frame.pack(pady=10)
        self.controls_frame.grid(row=1, column=0, pady=10)

        # Updated Play/Pause button
        self.play_pause_button = ttk.Button(self.controls_frame, text="Play", command=self.toggle_play_pause, state=tk.DISABLED)
        self.play_pause_button.pack(side=tk.LEFT, padx=5)

        # Add a Stop button using pygame.mixer.music.stop()
        self.stop_button = ttk.Button(self.controls_frame, text="Stop", command=self.stop_audio, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        # Bottom frame for file management buttons
        self.bottom_frame = ttk.Frame(self.main_frame)
        # self.bottom_frame.pack(fill=tk.X, pady=(10, 0))
        self.bottom_frame.grid(row=2, column=0, sticky="ew", pady=(10,0))

        # Renamed button commands
        self.add_button = ttk.Button(self.bottom_frame, text="Add Audio...", command=self.add_audio_files_from_popup)
        self.add_button.pack(side=tk.LEFT, padx=5)

        self.rename_button = ttk.Button(self.bottom_frame, text="Rename Audio", command=self.rename_audio, state=tk.DISABLED)
        self.rename_button.pack(side=tk.LEFT, padx=5)

        self.delete_button = ttk.Button(self.bottom_frame, text="Delete Audio", command=self.delete_audio, state=tk.DISABLED)
        self.delete_button.pack(side=tk.LEFT, padx=5)

        self.open_folder_button = ttk.Button(self.bottom_frame, text="Open Folder", command=self.open_folder_from_popup)
        self.open_folder_button.pack(side=tk.RIGHT, padx=5) # Keep on the right

        # --- Load Initial Data ---
        self.load_audio_list() # Renamed method
        if self.audio_files:
            self.load_audio(initial_index if 0 <= initial_index < len(self.audio_files) else 0)
        else:
             self.show_no_audio() # Ensure UI is updated if no files initially

        # Start the playback status check loop
        self.check_playback_status()

        # Handle popup closing via 'X' button
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Make popup modal (prevents interaction with main window)
        self.grab_set()
        self.focus_set()
        # Don't use wait_window here if the main app needs to know immediately
        # self.wait_window(self) # Wait until this window is destroyed


    def on_close(self):
        """Handles cleanup when the popup is closed."""
        print("Popup closing...")
        # Stop the after loop
        if self._after_id_playback_check:
            self.after_cancel(self._after_id_playback_check)
            self._after_id_playback_check = None
            print("Cancelled playback check loop.")

        self.stop_audio() # Ensure audio stops using pygame
        # Release the grab before destroying
        self.grab_release()
        self.app_controller.on_player_closed() # Notify the main app
        self.destroy() # Close the Toplevel window

    # Renamed load_image_list to load_audio_list
    def load_audio_list(self):
        """Loads the list of audio files from the prop directory."""
        # Use get_audio_files helper
        self.audio_files = sorted(get_audio_files(self.prop_dir))
        self.current_index = -1 # Reset index

    # Renamed show_no_image to show_no_audio
    def show_no_audio(self):
        """Updates the UI when no audio files are found."""
        self.filename_label.config(text=f"No audio files in '{self.prop_dir.name}'.")
        # Removed image label config
        # Disable playback and file-specific buttons
        self.prev_button.config(state=tk.DISABLED)
        self.next_button.config(state=tk.DISABLED)
        self.play_pause_button.config(state=tk.DISABLED, text="Play")
        self.stop_button.config(state=tk.DISABLED)
        self.rename_button.config(state=tk.DISABLED)
        self.delete_button.config(state=tk.DISABLED)
        self.is_paused = False # Reset paused state
        # Ensure mixer is stopped if no files are available
        if PYGAME_MIXER_INITIALIZED:
             pygame.mixer.music.stop()


    # Renamed load_image to load_audio
    def load_audio(self, index: int):
        """Loads the audio file at the given index and updates the UI."""
        if not self.audio_files or not (0 <= index < len(self.audio_files)):
            self.show_no_audio()
            return

        # Stop currently playing audio before loading next
        self.stop_audio()
        # Reset pause state explicitly when loading new audio
        self.is_paused = False

        self.current_index = index
        audio_path = self.audio_files[self.current_index]

        # Update filename label
        self.filename_label.config(
            text=f"{self.current_index + 1}/{len(self.audio_files)}: {audio_path.name}"
        )

        # Removed image loading and display logic

        # Update button states
        self.update_button_states()

    def update_button_states(self):
        """Enables/disables navigation and action buttons based on current state."""
        num_files = len(self.audio_files)
        has_files = num_files > 0
        current_valid = 0 <= self.current_index < num_files
        can_play = current_valid and PYGAME_MIXER_INITIALIZED
        is_playing_or_paused = False
        if PYGAME_MIXER_INITIALIZED:
            is_playing_or_paused = pygame.mixer.music.get_busy()

        # Navigation buttons
        self.prev_button.config(state=tk.NORMAL if current_valid and self.current_index > 0 else tk.DISABLED)
        self.next_button.config(state=tk.NORMAL if current_valid and self.current_index < num_files - 1 else tk.DISABLED)

        # Playback buttons
        self.play_pause_button.config(state=tk.NORMAL if can_play else tk.DISABLED)
        if is_playing_or_paused and not self.is_paused:
            self.play_pause_button.config(text="Pause")
        else:
            # Button should show "Play" if paused OR if stopped/finished
            self.play_pause_button.config(text="Play")

        self.stop_button.config(state=tk.NORMAL if can_play and is_playing_or_paused else tk.DISABLED)

        # File action buttons
        self.rename_button.config(state=tk.NORMAL if current_valid else tk.DISABLED)
        self.delete_button.config(state=tk.NORMAL if current_valid else tk.DISABLED)

    # Renamed go_previous
    def go_previous(self):
        """Loads the previous audio file."""
        if self.current_index > 0:
            self.load_audio(self.current_index - 1)

    # Renamed go_next
    def go_next(self):
        """Loads the next audio file."""
        if self.current_index < len(self.audio_files) - 1:
            self.load_audio(self.current_index + 1)

    # --- Audio Playback Methods (using pygame.mixer) ---

    def toggle_play_pause(self):
        """Toggles playback/pause of the current audio file using pygame."""
        if not PYGAME_MIXER_INITIALIZED or self.current_index == -1:
            return

        try:
            if pygame.mixer.music.get_busy():
                if self.is_paused:
                    pygame.mixer.music.unpause()
                    print("Resuming audio")
                    self.is_paused = False
                    self.play_pause_button.config(text="Pause")
                else:
                    pygame.mixer.music.pause()
                    print("Pausing audio")
                    self.is_paused = True
                    self.play_pause_button.config(text="Play") # Show Play when paused
            else:
                # Not playing or paused, so start playing
                audio_path = str(self.audio_files[self.current_index])
                self.play_audio(audio_path)
                self.is_paused = False # Ensure pause state is reset
                # Button text updated in play_audio or update_button_states

            # Update button states after action
            # self.update_button_states() # update_button_states is called within play_audio now

        except pygame.error as e:
            print(f"Pygame error during toggle_play_pause: {e}")
            messagebox.showerror("Playback Error", f"Error during playback control:\n{e}", parent=self)
            # Don't usually need a messagebox for stop errors unless debugging
            self.update_button_states()


    def play_audio(self, audio_path: str):
        """Loads and plays an audio file using pygame.mixer.music."""
        if not PYGAME_MIXER_INITIALIZED:
            # Should have been caught earlier, but safety check
            messagebox.showwarning("Playback Unavailable", "Pygame mixer not initialized.", parent=self)
            return

        print(f"Loading: {audio_path}")
        try:
            # Stop previous playback first
            pygame.mixer.music.stop()
            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()
            print("Playing audio")
            self.is_paused = False # Reset pause state on new playback
            # Update UI immediately after starting play
            self.update_button_states()
        except pygame.error as e:
            print(f"Pygame error loading/playing {audio_path}: {e}")
            messagebox.showerror("Playback Error", f"Could not load or play audio file: {os.path.basename(audio_path)} Error: {e}", parent=self)
            self.update_button_states() # Refresh UI state


    def stop_audio(self):
        """Stops the currently playing audio using pygame.mixer.music."""
        if not PYGAME_MIXER_INITIALIZED:
            return

        print("Stopping audio")
        try:
            pygame.mixer.music.stop()
            self.is_paused = False # Reset pause state on stop
            # Update UI immediately after stopping
            self.update_button_states()
        except pygame.error as e: # Should be unlikely for stop, but handle defensively
            print(f"Pygame error during stop_audio: {e}")
            # Don't usually need a messagebox for stop errors unless debugging
            self.update_button_states()

    # --- Playback Status Check ---
    def check_playback_status(self):
        """Periodically checks if the music has stopped playing naturally."""
        if self._after_id_playback_check:
            self.after_cancel(self._after_id_playback_check)
            self._after_id_playback_check = None

        should_reschedule = False
        try:
            if self.winfo_exists():
                should_reschedule = True
                if PYGAME_MIXER_INITIALIZED:
                    music_busy = pygame.mixer.music.get_busy()
                    if not music_busy and not self.is_paused and self.current_index != -1:
                        if self.play_pause_button["text"] != "Play":
                            print("Music finished playing naturally. Updating UI.")
                            self.update_button_states()
        except (tk.TclError, pygame.error) as e:
            print(f"Error during status check: {e}")
            should_reschedule = False # Stop checking if error occurs

        if should_reschedule:
            self._after_id_playback_check = self.after(250, self.check_playback_status)

    # --- File Management Methods ---

    # Renamed rename_image to rename_audio
    def rename_audio(self):
        """Renames the current audio file."""
        if self.current_index == -1:
            return

        old_path = self.audio_files[self.current_index]
        old_name = old_path.name
        # Suggest current name without extension
        suggestion = old_path.stem

        new_name_base = simpledialog.askstring(
            "Rename Audio",
            f"Enter new name for '{old_name}' (without extension):",
            initialvalue=suggestion,
            parent=self # Make dialog appear over the popup
        )

        if not new_name_base or new_name_base == suggestion:
            print("Rename cancelled or name unchanged.")
            return # User cancelled or entered the same name

        # Add back the original extension
        new_name = new_name_base + old_path.suffix
        new_path = self.prop_dir / new_name

        if new_path.exists():
            messagebox.showerror("Rename Error", f"A file named '{new_name}' already exists.", parent=self)
            return

        try:
            old_path.rename(new_path)
            print(f"Renamed '{old_name}' to '{new_name}'")

            # Update the list and UI
            self.audio_files[self.current_index] = new_path
            self.load_audio(self.current_index) # Reload to update label
            self.app_controller.update_prop_block(self.prop_dir) # Update main browser view

        except OSError as e:
            messagebox.showerror("Rename Error", f"Failed to rename file: {e}", parent=self)
            print(f"Error renaming {old_name}: {e}")

    # Renamed delete_image to delete_audio
    def delete_audio(self):
        """Deletes the current audio file."""
        if self.current_index == -1:
            return

        audio_path = self.audio_files[self.current_index]
        file_name = audio_path.name

        confirm = messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to permanently delete '{file_name}'?",
            parent=self # Make dialog appear over the popup
        )

        if not confirm:
            print("Deletion cancelled.")
            return

        try:
            # Stop playback before deleting
            self.stop_audio()

            audio_path.unlink() # Delete the file
            print(f"Deleted '{file_name}'")

            # Remove from list
            del self.audio_files[self.current_index]

            # Determine next index to show
            new_index = -1
            if not self.audio_files:
                # No files left
                self.show_no_audio()
            elif self.current_index < len(self.audio_files):
                # Show file at the same index (which is now the next file)
                new_index = self.current_index
            else:
                # Was the last file, show the new last file
                new_index = len(self.audio_files) - 1

            if new_index != -1:
                 self.load_audio(new_index)
            else:
                 # Ensure UI is updated even if show_no_audio was called
                 self.update_button_states()


            # Refresh the main browser block
            self.app_controller.update_prop_block(self.prop_dir)

        except OSError as e:
            messagebox.showerror("Delete Error", f"Failed to delete file: {e}", parent=self)
            print(f"Error deleting {file_name}: {e}")

    # Renamed add_images_from_popup to add_audio_files_from_popup
    def add_audio_files_from_popup(self):
        """Opens a file dialog to select audio files to add."""
        file_types = [
            ("Audio Files", "*.mp3 *.wav *.ogg *.flac *.m4a"),
            ("All Files", "*.*")
        ]
        file_paths = filedialog.askopenfilenames(
            title="Select Audio Files to Add",
            filetypes=file_types,
            parent=self # Make dialog appear over the popup
        )

        if not file_paths:
            print("No files selected.")
            return

        # Call the main app's add function
        copied_count = self.app_controller.add_audio_files(self.prop_dir, file_paths)

        if copied_count > 0:
            # Refresh the list in the popup
            old_index = self.current_index
            old_name = self.audio_files[old_index].name if old_index != -1 else None

            self.load_audio_list() # Reload file list

            # Try to find the previously selected file or the first new one
            new_index = -1
            if old_name:
                try:
                    new_index = [f.name for f in self.audio_files].index(old_name)
                except ValueError:
                    pass # Old file might have been overwritten/renamed? Fallback below.

            if new_index == -1 and self.audio_files: # If old file not found or wasn't one, find first
                new_index = 0 # Default to first file

            # Load the determined index
            if new_index != -1:
                self.load_audio(new_index)
            else:
                self.show_no_audio() # Should not happen if copied_count > 0 but safeguard


    # Renamed open_folder_from_popup
    def open_folder_from_popup(self):
        """Opens the prop's folder in the system's file explorer."""
        self.app_controller.open_folder(self.prop_dir)


# --- Main Execution ---

if __name__ == "__main__":
    # Ensure base directory exists
    if not BASE_AUDIO_DIR.exists():
         print(f"Warning: Base audio directory '{BASE_AUDIO_DIR}' does not exist. Creating it.")
         try:
            BASE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
         except Exception as e:
             print(f"Error: Could not create base directory '{BASE_AUDIO_DIR}': {e}")
             # Don't exit if pygame failed, but exit if dir creation fails
             if PYGAME_MIXER_INITIALIZED:
                pygame.quit()
             exit(1)
    elif not BASE_AUDIO_DIR.is_dir():
        print(f"Error: The path '{BASE_AUDIO_DIR}' exists but is not a directory.")
        if PYGAME_MIXER_INITIALIZED:
            pygame.quit()
        exit(1)

    # Check again if mixer is usable before starting app
    if not PYGAME_MIXER_INITIALIZED:
         print("Exiting application because audio playback could not be initialized.")
         # pygame.quit() might have already been called or failed
         exit(1)


    root = tk.Tk()
    # Updated App Class name
    app = AudioBrowserApp(root)
    root.mainloop()
    # pygame.quit() is now handled in app.on_app_close


# --- Additional Notes ---

# If you want to handle pygame quit automatically when the application closes,
# you can use the `atexit` module to call `pygame.quit()` when the program exits.
# This is useful if you want to ensure that pygame resources are cleaned up properly.

# import atexit
# atexit.register(pygame.quit)

    root.mainloop() 