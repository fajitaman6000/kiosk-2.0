import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, Frame, Label, Button, filedialog
import os
import json
import shutil
import pygame # Make sure to install pygame: pip install pygame
from pathlib import Path
import sys
import subprocess # Import for opening folders

# --- Configuration (Paths relative to the script in the 'tools' directory) ---

# Get the directory where the script is located (should be 'tools')
SCRIPT_DIR = Path(sys.argv[0] if getattr(sys, 'frozen', False) else __file__).resolve().parent

# Go up one level from 'tools' to reach the parent ('kiosk-2.0')
BASE_DIR = SCRIPT_DIR.parent

# Path to the target directory structure (under 'admin')
TARGET_BASE_DIR_CONST = BASE_DIR / "admin" / "sync_directory" / "hint_audio_files"

# Path to the prop mapping JSON file (under 'admin')
PROP_MAPPING_FILE = BASE_DIR / "admin" / "prop_name_mapping.json"

# --- Application Class ---

class AudioSorterApp:
    def __init__(self, master):
        self.master = master
        self.master.title("Audio File Sorter")
        self.master.withdraw() # Hide main window initially until dir is selected

        # Store the target base directory as an instance variable
        self.target_base_dir = TARGET_BASE_DIR_CONST

        # --- Prompt for Source Directory ---
        self.source_audio_dir = self.prompt_for_source_dir()
        if not self.source_audio_dir:
            messagebox.showinfo("Info", "No source directory selected. Exiting.", parent=self.master)
            self.master.destroy()
            return # Exit if no directory chosen

        # --- Define the path for the processed files tracking file (relative to source dir) ---
        self.processed_files_path = self.source_audio_dir / "processed_files.json"

        self.master.geometry("600x750") # Adjust size slightly for source dir display
        self.master.deiconify() # Show main window now

        # --- Data Loading ---
        self.prop_data = self.load_prop_mapping()
        if not self.prop_data:
            messagebox.showerror("Error", f"Could not load or parse {PROP_MAPPING_FILE}.\nMake sure it exists in the 'admin' directory.\nExiting.", parent=self.master)
            self.master.destroy()
            return

        self.processed_files = self.load_processed_files()
        # Find audio files using the selected directory
        self.all_audio_files = self.find_audio_files(self.source_audio_dir)

        # Filter out files that are already in the processed_files set
        self.files_to_process = [f for f in self.all_audio_files if f.name not in self.processed_files]

        self.current_file_index = 0 # Index within the files_to_process list
        self.current_file_path = None
        self.selected_room_key = None

        # --- Initialize Pygame Mixer ---
        try:
            pygame.mixer.init()
        except pygame.error as e:
            messagebox.showerror("Pygame Error", f"Could not initialize audio mixer: {e}\nMake sure audio drivers are working.", parent=self.master)
            self.master.destroy()
            return

        # --- GUI Setup ---
        self.setup_gui()

        # --- Start Processing ---
        if not self.files_to_process:
            messagebox.showinfo("Done", f"No unprocessed audio files found in:\n{self.source_audio_dir}", parent=self.master)
            self.filename_label.config(text="No files to process.")
            self.source_dir_label.config(text=f"Source: {self.source_audio_dir}") # Set source dir label
        else:
            self.next_file() # Load the first file

    def prompt_for_source_dir(self):
        """Asks the user to select the source audio directory."""
        # Initial dir suggestion - try the directory above the base kiosk dir, or the base kiosk dir itself
        initial_dir = BASE_DIR.parent if BASE_DIR.parent.exists() else BASE_DIR

        messagebox.showinfo("Select Source", "Please select the directory containing the unsorted MP3 audio files.", parent=self.master)
        directory = filedialog.askdirectory(
            title="Select Unsorted Audio Files Directory",
            parent=self.master, # Make dialog parented to main window
            initialdir=initial_dir # Suggest a likely location
        )
        if directory:
            return Path(directory)
        else:
            return None

    def load_prop_mapping(self):
        """Loads the prop mapping data from the JSON file."""
        if not PROP_MAPPING_FILE.is_file():
            # Pass parent=self.master to show the error over the main window
            messagebox.showerror("Error", f"Mapping file not found: {PROP_MAPPING_FILE}", parent=self.master)
            return None
        try:
            with open(PROP_MAPPING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            messagebox.showerror("JSON Error", f"Error decoding {PROP_MAPPING_FILE}: {e}", parent=self.master)
            return None
        except Exception as e:
            messagebox.showerror("File Error", f"Error reading {PROP_MAPPING_FILE}: {e}", parent=self.master)
            return None

    def load_processed_files(self):
        """Loads the set of processed filenames from the tracking JSON located in the source dir."""
        # Use self.processed_files_path which is determined after source dir selection
        if self.processed_files_path and self.processed_files_path.is_file():
            try:
                with open(self.processed_files_path, 'r', encoding='utf-8') as f:
                    return set(json.load(f))
            except (json.JSONDecodeError, Exception) as e:
                messagebox.showwarning("Load Warning", f"Could not load {self.processed_files_path}.\nStarting fresh for this directory.\nError: {e}", parent=self.master)
                return set()
        return set() # Return empty set if file doesn't exist or path isn't set

    def save_processed_files(self):
        """Saves the set of processed filenames to the tracking JSON in the source dir."""
        # Use self.processed_files_path
        if not self.processed_files_path:
             print("Warning: Cannot save processed files path is not set.")
             return # Should not happen if app initialized correctly
        try:
            with open(self.processed_files_path, 'w', encoding='utf-8') as f:
                json.dump(list(self.processed_files), f, indent=4)
        except Exception as e:
            messagebox.showerror("Save Error", f"Could not save progress to {self.processed_files_path}: {e}", parent=self.master)

    def find_audio_files(self, source_dir):
        """Finds all .mp3 files in the specified source directory."""
        if not source_dir or not source_dir.is_dir():
             # This error should ideally be caught by prompt_for_source_dir, but belt-and-suspenders
             messagebox.showerror("Config Error", f"Selected source audio path is not a valid directory:\n{source_dir}", parent=self.master)
             return []
        try:
            return sorted([p for p in source_dir.glob("*.mp3") if p.is_file()], key=lambda x: x.name)
        except Exception as e:
            messagebox.showerror("File Scan Error", f"Error scanning source directory {source_dir}: {e}", parent=self.master)
            return []

    def setup_gui(self):
        """Creates the main GUI elements."""
        # --- Top Frame: Filename and Source Display ---
        top_frame = ttk.Frame(self.master, padding="10")
        top_frame.pack(fill=tk.X, side=tk.TOP)

        # Source Directory Label
        self.source_dir_label = ttk.Label(top_frame, text=f"Source: {self.source_audio_dir}", wraplength=550, foreground="grey")
        self.source_dir_label.pack(fill=tk.X, pady=(0, 5))

        # Current File Row
        file_row_frame = ttk.Frame(top_frame)
        file_row_frame.pack(fill=tk.X)
        ttk.Label(file_row_frame, text="Current File:", font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        self.filename_label = ttk.Label(file_row_frame, text="Loading...", anchor=tk.W, wraplength=450) # Reduced wraplength
        self.filename_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.progress_label = ttk.Label(file_row_frame, text="", anchor=tk.E) # Start with empty text
        self.progress_label.pack(side=tk.RIGHT)


        # --- Middle Frame: Audio Controls ---
        control_frame = ttk.Frame(self.master, padding="5")
        control_frame.pack(fill=tk.X, side=tk.TOP)

        self.replay_button = ttk.Button(control_frame, text="Replay", command=self.replay_audio, width=15)
        self.replay_button.pack(side=tk.LEFT, padx=5, pady=5)

        self.skip_button = ttk.Button(control_frame, text="Skip This File", command=self.skip_file, width=15)
        self.skip_button.pack(side=tk.LEFT, padx=5, pady=5)

        # New button to open the target directory
        self.open_target_button = ttk.Button(control_frame, text="Admin Sync Directory", command=self.open_target_folder, width=20)
        self.open_target_button.pack(side=tk.RIGHT, padx=5, pady=5)


        # --- Bottom Frame: Dynamic Buttons (Rooms/Props) ---
        self.button_frame = ttk.Frame(self.master, padding="10")
        self.button_frame.pack(fill=tk.BOTH, expand=True, side=tk.TOP)

        # Label for the dynamic section
        self.button_area_label = ttk.Label(self.button_frame, text="Select Room:", font=('Arial', 12, 'bold'))
        self.button_area_label.pack(pady=(0, 10))


    def open_target_folder(self):
        """Opens the target sync directory in the default file explorer."""
        target_path = str(self.target_base_dir) # Convert Path object to string

        if not os.path.isdir(target_path):
            # Try to create the directory if it doesn't exist before opening
            try:
                os.makedirs(target_path)
                print(f"Created target directory: {target_path}")
            except OSError as e:
                 messagebox.showerror("Error", f"Target directory does not exist and could not be created:\n{target_path}\nError: {e}", parent=self.master)
                 return

        try:
            if sys.platform == "win32":
                os.startfile(target_path)
            elif sys.platform == "darwin": # macOS
                subprocess.run(['open', target_path], check=True)
            else: # linux variants
                subprocess.run(['xdg-open', target_path], check=True)
        except FileNotFoundError:
            messagebox.showerror("Error", f"Could not find the command to open the folder.\nTry installing xdg-utils on Linux.", parent=self.master)
        except subprocess.CalledProcessError as e:
             messagebox.showerror("Error", f"Failed to open directory {target_path}\nError: {e}", parent=self.master)
        except Exception as e:
             messagebox.showerror("Error", f"An unexpected error occurred while trying to open the folder: {e}", parent=self.master)


    def update_filename_display(self):
        """Updates the label showing the current filename and progress."""
        total_files_initially = len(self.all_audio_files)
        processed_count_total = len(self.processed_files)
        files_remaining = total_files_initially - processed_count_total

        # Update filename display
        if self.current_file_path:
            display_name = self.current_file_path.name
            self.filename_label.config(text=display_name)
        else:
            self.filename_label.config(text="No file loaded.") # Or "All files processed!"


        # Update progress display
        if total_files_initially == 0:
            self.progress_label.config(text="No files found")
        elif files_remaining == 0:
             self.progress_label.config(text="All files processed!")
        else:
            self.progress_label.config(text=f"{files_remaining} files remain")


    def play_current_audio(self):
        """Plays the audio file currently selected."""
        if not self.current_file_path or not self.current_file_path.is_file():
            print(f"Warning: Audio file not found or not selected: {self.current_file_path}")
            return

        try:
            pygame.mixer.music.stop() # Stop previous music
            pygame.mixer.music.load(str(self.current_file_path))
            pygame.mixer.music.play()
        except pygame.error as e:
            messagebox.showerror("Audio Playback Error", f"Could not play file: {self.current_file_path.name}\nError: {e}", parent=self.master)
        except Exception as e:
             messagebox.showerror("Audio Playback Error", f"An unexpected error occurred during playback: {e}", parent=self.master)

    def replay_audio(self):
        """Callback for the Replay button."""
        self.play_current_audio()

    def skip_file(self):
        """Callback for the Skip button."""
        if not self.current_file_path:
            return # No file loaded

        try:
            pygame.mixer.music.stop() # Stop playback
        except pygame.error:
            pass # Ignore if mixer wasn't playing

        # Add to processed set and save
        self.processed_files.add(self.current_file_path.name)
        self.save_processed_files()

        # Re-calculate files_to_process list to exclude the skipped file
        self.files_to_process = [f for f in self.all_audio_files if f.name not in self.processed_files]
        self.current_file_index = 0 # Reset index as we have a new list

        self.next_file()

    def clear_button_frame(self):
        """Removes all widgets from the dynamic button frame."""
        for widget in self.button_frame.winfo_children():
            # Keep the label
            if widget != self.button_area_label:
                 widget.destroy()

    def show_room_buttons(self):
        """Displays buttons for selecting a room."""
        self.clear_button_frame()
        self.button_area_label.config(text="Select Room:")
        self.selected_room_key = None # Reset selection

        room_keys = sorted(self.prop_data.keys())
        for room_key in room_keys:
            if room_key == "ma":
                btn = ttk.Button(self.button_frame, text="Morning After",
                                command=lambda rk=room_key: self.select_room(rk),
                                width=20)
                btn.pack(pady=3)
            elif room_key == "time":
                btn = ttk.Button(self.button_frame, text="Time Machine",
                                command=lambda rk=room_key: self.select_room(rk),
                                width=20)
                btn.pack(pady=3)
            else:
                btn = ttk.Button(self.button_frame, text=room_key.capitalize(),
                                command=lambda rk=room_key: self.select_room(rk),
                                width=20)
                btn.pack(pady=3)

    def select_room(self, room_key):
        """Handles room selection and displays prop buttons."""
        print(f"Room selected: {room_key}")
        self.selected_room_key = room_key
        self.show_prop_buttons()

    def show_prop_buttons(self):
        """Displays buttons for props within the selected room."""
        if not self.selected_room_key:
            return

        self.clear_button_frame()
        self.button_area_label.config(text=f"'{self.selected_room_key.capitalize()}' - Select Prop:")

        room_mappings = self.prop_data.get(self.selected_room_key, {}).get("mappings", {})
        if not room_mappings:
             messagebox.showwarning("No Props", f"No props found for room '{self.selected_room_key}' in the mapping file.", parent=self.master)
             self.show_room_buttons()
             return

        def get_order(item):
            try:
                return int(item[1].get('order', 9999))
            except (ValueError, TypeError):
                return 9999

        sorted_props = sorted(room_mappings.items(), key=get_order)

        # --- Create a scrollable area ---
        canvas = tk.Canvas(self.button_frame)
        scrollbar = ttk.Scrollbar(self.button_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        # --- Place scrollable area ---
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Add prop buttons to the scrollable frame
        for prop_key, prop_details in sorted_props:
            display_name = prop_details.get("display", prop_key)
            # Ensure the target directory name matches the button text EXACTLY
            target_dir_name = display_name
            btn = ttk.Button(scrollable_frame, text=display_name,
                             command=lambda rk=self.selected_room_key, pk=prop_key, tdn=target_dir_name: self.select_prop(rk, pk, tdn),
                             width=30)
            btn.pack(pady=2, padx=10)

        # Add "Back" button
        back_button = ttk.Button(scrollable_frame, text="< Back to Rooms", command=self.show_room_buttons, width=30)
        back_button.pack(pady=(15, 2), padx=10)


    def select_prop(self, room_key, prop_key, target_dir_name):
        """Handles prop selection, asks for filename, and copies the file."""
        if not self.current_file_path:
            messagebox.showwarning("No File", "No file is currently loaded.", parent=self.master)
            return

        original_filename = self.current_file_path.name
        new_filename_base = simpledialog.askstring(
            "Rename File (Optional)",
            f"Enter new name for:\n'{original_filename}'\n\n(Leave blank or cancel to keep original name)\nTarget: {room_key} / {target_dir_name}",
            parent=self.master
        )

        if new_filename_base is None:
            print("Rename cancelled.")
            return

        # --- Replace spaces with hyphens ---
        new_filename_base = new_filename_base.replace(' ', '-')
        # --- End space replacement ---


        if not new_filename_base.strip():
            final_filename = original_filename
        else:
            # Sanitize filename (remove invalid characters if any) - rudimentary
            # Windows invalid chars: < > : " / \ | ? *
            invalid_chars = '<>:"/\\|?*'
            sanitized_name = "".join(c for c in new_filename_base if c not in invalid_chars)
            if not sanitized_name:
                 messagebox.showwarning("Invalid Filename", "The entered name contained only invalid characters after space replacement. Please try again.", parent=self.master)
                 return # Stay on the current file

            final_filename = sanitized_name + ".mp3" if not sanitized_name.lower().endswith(".mp3") else sanitized_name


        # Construct target path using the exact target_dir_name from the button
        target_prop_dir = self.target_base_dir / room_key / target_dir_name
        target_filepath = target_prop_dir / final_filename

        print(f"Attempting copy to: {target_filepath}")

        if self.copy_file(self.current_file_path, target_filepath):
            try:
                pygame.mixer.music.stop()
            except pygame.error: pass

            # Add the *original* filename to the processed set
            self.processed_files.add(self.current_file_path.name)
            self.save_processed_files()

            # Re-calculate files_to_process list to exclude the newly processed file
            self.files_to_process = [f for f in self.all_audio_files if f.name not in self.processed_files]
            self.current_file_index = 0 # Reset index as we have a new list

            self.next_file()


    def copy_file(self, source_path, target_path):
        """Copies the source file to the target path, creating directories."""
        try:
            # Ensure the target directory exists. It will be created if it doesn't.
            # This relies on the prop_dir_name (display name) matching the actual folder name.
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists():
                 overwrite = messagebox.askyesno("File Exists", f"The file '{target_path.name}' already exists in\n{target_path.parent}\n\nOverwrite it?", parent=self.master)
                 if not overwrite:
                     print("Copy cancelled, file exists.")
                     return False

            shutil.copy2(source_path, target_path)
            print(f"Copied '{source_path.name}' to '{target_path}'")
            return True
        except OSError as e:
            messagebox.showerror("Copy Error", f"Failed to copy file:\n{source_path}\nto\n{target_path}\n\nError: {e}", parent=self.master)
            return False
        except Exception as e:
             messagebox.showerror("Unexpected Copy Error", f"An unexpected error occurred during copy:\nError: {e}", parent=self.master)
             return False

    def next_file(self):
        """Loads and plays the next unprocessed file."""
        # Before moving to the next file, ensure the list of files to process is up-to-date
        # based on the current state of self.processed_files.
        # This is done in skip_file and select_prop now.

        self.selected_room_key = None
        self.show_room_buttons() # Always go back to Room selection for the next file

        if self.current_file_index < len(self.files_to_process):
             # Get the actual file path from the *current* list of files_to_process
            self.current_file_path = self.files_to_process[self.current_file_index]
            self.update_filename_display()
            self.play_current_audio()
        else:
            # Reached the end of the current list of unprocessed files
            # This means all files initially found have been processed
            self.current_file_path = None
            self.update_filename_display() # Will now show "All files processed!"
            try: pygame.mixer.music.stop()
            except pygame.error: pass
            messagebox.showinfo("Finished", "All audio files in the selected directory have been processed!", parent=self.master)
            self.filename_label.config(text="All files processed!")
            self.replay_button.config(state=tk.DISABLED)
            self.skip_button.config(state=tk.DISABLED)
            self.clear_button_frame()
            self.button_area_label.config(text="Done!")


    def run(self):
        """Starts the Tkinter event loop."""
        self.master.mainloop()
        # Clean up pygame mixer when the window is closed
        try:
            pygame.mixer.quit()
        except pygame.error:
            # Ignore if mixer wasn't initialized or already quit
            pass


# --- Main Execution ---
if __name__ == "__main__":
    root = tk.Tk()
    # Check if target structure's parent exists (sanity check)
    if not TARGET_BASE_DIR_CONST.parent.parent.is_dir(): # Checks if 'admin/sync_directory' exists
        print(f"WARNING: Expected 'admin/sync_directory' not found relative to the script's location.")
        print(f"Script expects to be in 'tools' next to 'admin'.")
        print(f"Target base path will be {TARGET_BASE_DIR_CONST}")
        # Allow script to continue, it will try to create dirs later via copy_file

    if not PROP_MAPPING_FILE.is_file():
         print(f"ERROR: Prop mapping file not found: {PROP_MAPPING_FILE}")
         print("Please ensure prop_name_mapping.json is inside the 'admin' directory relative to the script.")
         # Don't exit here, let the App handle it with a messagebox
         # sys.exit(1)

    app = AudioSorterApp(root)
    # Check if app initialization failed (e.g., user cancelled dir selection or mapping load failed)
    if app and app.master and app.master.winfo_exists():
         app.run()
    else:
        # Ensure root window is destroyed if app init failed early
        if root.winfo_exists():
             root.destroy()