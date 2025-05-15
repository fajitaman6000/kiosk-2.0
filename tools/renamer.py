import os

# --- Configuration ---
# The directory containing the files.
# '.' means the current directory where the script is run.
# You can change this to a specific path like '/path/to/your/photos'
directory = '.'

# The current extension you want to rename from (case-sensitive)
old_extension = '.jpg'

# The new extension you want to rename to (case-sensitive)
new_extension = '.png'
# ---------------------

print(f"Looking for files with extension '{old_extension}' in '{directory}'...")
print(f"They will be renamed to use the '{new_extension}' extension.")

count = 0
try:
    # Get a list of all items in the directory
    for item_name in os.listdir(directory):
        old_path = os.path.join(directory, item_name)

        # Check if the item is a file and ends with the old extension
        if os.path.isfile(old_path) and item_name.endswith(old_extension):
            try:
                # Construct the new filename by replacing the extension
                # os.path.splitext splits the base name from the extension
                base_name, current_ext = os.path.splitext(item_name)
                new_name = base_name + new_extension
                new_path = os.path.join(directory, new_name)

                # Perform the actual renaming
                os.rename(old_path, new_path)
                print(f"Renamed '{item_name}' to '{new_name}'")
                count += 1

            except OSError as e:
                print(f"Error renaming '{item_name}': {e}")
            except Exception as e:
                print(f"An unexpected error occurred with '{item_name}': {e}")


except FileNotFoundError:
    print(f"Error: Directory '{directory}' not found.")
except PermissionError:
    print(f"Error: Permission denied to access directory '{directory}'.")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

print(f"\nFinished. Renamed {count} files.")