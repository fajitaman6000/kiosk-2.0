# transcoder.py
import os
import subprocess
import sys
import imageio_ffmpeg # <<< USES THIS TO FIND FFMPEG
import traceback # Keep for unexpected errors

# --- Configuration ---
TARGET_DIRECTORY = "."      # Process files in this directory
OUTPUT_SUBFOLDER = "resized_720p" # Place resized files in this subfolder
OUTPUT_EXTENSION = ".mp4"   # Output file format (should remain .mp4)
OVERWRITE_EXISTING = False  # Set to True if you want to re-process files if they exist in the output subfolder

# --- FFmpeg Settings for 720p Resizing ---
# Video codec (libx264 is common for H.264 MP4)
VIDEO_CODEC = "libx264"
# Constant Rate Factor (lower = better quality, larger size. 18-28 is typical range, 23 is a good default)
VIDEO_CRF = 23
# Encoding speed preset (ultrafast, superfast, veryfast, faster, fast, medium, slow, slower, veryslow)
# Faster presets are quicker but less efficient compression. 'medium' is a good balance.
VIDEO_PRESET = "medium"
# Audio codec ('copy' directly copies the stream - faster, preserves quality if compatible)
# Use 'aac' for re-encoding if 'copy' causes issues.
AUDIO_CODEC = "copy"
# Target video height (width will be calculated automatically to maintain aspect ratio)
TARGET_HEIGHT = 720

# --- Helper Functions ---

def get_ffmpeg_executable():
    """Gets the ffmpeg executable path using imageio_ffmpeg."""
    print("Attempting to find ffmpeg executable using imageio-ffmpeg...")
    try:
        exe_path = imageio_ffmpeg.get_ffmpeg_exe()
        # Basic check if the path seems valid and exists
        if exe_path and isinstance(exe_path, str) and os.path.exists(exe_path):
             print(f"Found ffmpeg via imageio_ffmpeg: {exe_path}")
             return exe_path
        elif exe_path:
             print(f"ERROR: imageio_ffmpeg reported an ffmpeg path, but it does not exist or is invalid: '{exe_path}'", file=sys.stderr)
             return None
        else:
             print("ERROR: imageio_ffmpeg.get_ffmpeg_exe() returned an empty or invalid path.", file=sys.stderr)
             return None
    except FileNotFoundError:
        print("ERROR: imageio-ffmpeg could not find or download the ffmpeg executable.", file=sys.stderr)
        print("  Ensure 'imageio-ffmpeg' is installed (`pip install imageio-ffmpeg`) and has download permissions.", file=sys.stderr)
        return None
    except Exception as e:
        print("ERROR: Failed to get ffmpeg path using imageio_ffmpeg.", file=sys.stderr)
        print(f"  Error details: {e}", file=sys.stderr)
        print("  Please ensure 'imageio-ffmpeg' is installed (`pip install imageio-ffmpeg`).", file=sys.stderr)
        return None

def run_ffmpeg_command(ffmpeg_executable, command_args, input_file, output_file):
    """Runs an ffmpeg command using subprocess."""
    full_command = [str(ffmpeg_executable)] + [str(arg) for arg in command_args]
    print(f"  Running: {' '.join(full_command)}")

    startupinfo = None
    if sys.platform == "win32": # Hide console window on Windows
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    try:
        result = subprocess.run(
            full_command,
            check=True,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore',
            startupinfo=startupinfo
        )
        if result.stderr:
            filtered_stderr = "\n".join(line for line in result.stderr.splitlines()
                                        if "deprecated pixel format used" not in line.lower()
                                        and "use -update true" not in line.lower())
            if filtered_stderr.strip():
                 print(f"  FFmpeg stderr:\n{filtered_stderr}")

        print(f"  Successfully created: {output_file}")
        return True

    except FileNotFoundError:
        print(f"ERROR: Could not execute ffmpeg. Path '{ffmpeg_executable}' not found or invalid.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"ERROR: ffmpeg failed for {input_file} -> {output_file}", file=sys.stderr)
        print(f"  Return code: {e.returncode}", file=sys.stderr)
        print(f"  Command: {' '.join(e.cmd)}", file=sys.stderr)
        print(f"  Stderr:\n{e.stderr}", file=sys.stderr)
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                print(f"  Removed potentially corrupt output file: {output_file}")
            except OSError as remove_err:
                 print(f"  Warning: Could not remove output file {output_file}: {remove_err}")
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred running ffmpeg: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return False

# --- Main Processing Logic ---

if __name__ == "__main__":
    print("Starting MP4 resizing process...")
    target_abs_path = os.path.abspath(TARGET_DIRECTORY)
    output_dir_abs_path = os.path.join(target_abs_path, OUTPUT_SUBFOLDER)

    print(f"Looking for .mp4 files in: {target_abs_path}")
    print(f"Resized files ({TARGET_HEIGHT}p) will be placed in: {output_dir_abs_path}")
    print(f"Video settings: Codec={VIDEO_CODEC}, CRF={VIDEO_CRF}, Preset={VIDEO_PRESET}")
    print(f"Audio settings: Codec={AUDIO_CODEC}")
    if OVERWRITE_EXISTING:
        print(f"WARNING: OVERWRITE_EXISTING is True. Existing files in '{OUTPUT_SUBFOLDER}' will be replaced.")

    # --- Get ffmpeg path ---
    ffmpeg_executable = get_ffmpeg_executable()
    if not ffmpeg_executable:
        print("\nERROR: Could not find ffmpeg executable. Processing aborted.", file=sys.stderr)
        sys.exit(1)

    # --- Create output directory ---
    try:
        os.makedirs(output_dir_abs_path, exist_ok=True)
        print(f"Ensured output directory exists: {output_dir_abs_path}")
    except OSError as e:
        print(f"\nERROR: Could not create output directory '{output_dir_abs_path}'. Error: {e}", file=sys.stderr)
        print("Please check permissions.", file=sys.stderr)
        sys.exit(1)

    processed_count = 0
    skipped_count = 0
    error_count = 0

    try:
        found_mp4 = False
        for filename in os.listdir(target_abs_path):
            input_file_path = os.path.join(target_abs_path, filename)

            # Process only .mp4 files that are actually files (not directories)
            # and are located in the TARGET_DIRECTORY (not already in the OUTPUT_SUBFOLDER)
            if filename.lower().endswith(".mp4") and os.path.isfile(input_file_path):
                # Crucially, check if the *input* path is inside the output path.
                # This prevents processing files if TARGET_DIRECTORY is the same as OUTPUT_SUBFOLDER
                # or if OUTPUT_SUBFOLDER is accidentally set to "."
                if os.path.abspath(input_file_path).startswith(os.path.abspath(output_dir_abs_path)):
                   # print(f"  Skipping {filename} as it is inside the output directory.")
                   continue # Skip files already in the output directory

                found_mp4 = True

                # Define expected output path: original filename inside the output subfolder
                output_mp4_path = os.path.join(output_dir_abs_path, filename) # Use original filename

                print(f"\nProcessing: {filename}")

                # --- Check if the output file already exists in the output subfolder ---
                output_exists = os.path.exists(output_mp4_path)

                if output_exists and not OVERWRITE_EXISTING:
                    print(f"  Skipping: Output file '{os.path.join(OUTPUT_SUBFOLDER, filename)}' already exists.")
                    skipped_count += 1
                    continue # Move to the next mp4 file

                # --- Transcode Video and Audio to new MP4 in the output folder ---
                print(f"  Creating Resized Video in '{OUTPUT_SUBFOLDER}' folder...")

                resize_command = [
                    "-hide_banner", "-loglevel", "error",
                    "-i", input_file_path, # Use the full input path
                    "-vf", f"scale=-2:{TARGET_HEIGHT}",
                    "-c:v", VIDEO_CODEC,
                    "-crf", str(VIDEO_CRF),
                    "-preset", VIDEO_PRESET,
                    "-c:a", AUDIO_CODEC,
                    "-y",
                    output_mp4_path # Use the full output path
                ]

                success = run_ffmpeg_command(ffmpeg_executable, resize_command, input_file_path, output_mp4_path)

                if success:
                     processed_count += 1
                else:
                     error_count += 1

        if not found_mp4:
             print(f"\nWarning: No source .mp4 files found directly in '{target_abs_path}' (excluding the '{OUTPUT_SUBFOLDER}' directory).")

    except FileNotFoundError:
        print(f"ERROR: Target directory not found: {target_abs_path}", file=sys.stderr)
        error_count += 1
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during directory processing: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        error_count += 1


    print("\n-------------------------------------")
    print("Resizing Complete.")
    print(f"  Files Processed Successfully: {processed_count}")
    print(f"  Files Skipped (already exist): {skipped_count}")
    print(f"  Errors Encountered: {error_count}")
    print(f"  Output directory: {output_dir_abs_path}")
    print("-------------------------------------")

    if error_count > 0:
        print("Please review the error messages above.", file=sys.stderr)
        sys.exit(1)
    else:
        sys.exit(0)