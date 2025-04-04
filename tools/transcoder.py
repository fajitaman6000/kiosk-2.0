# transcoder.py
import os
import subprocess
import shutil
import sys
import imageio_ffmpeg # <<< USES THIS TO FIND FFMPEG

# --- Configuration ---
TARGET_DIRECTORY = "." # Process files in the current directory
MJPEG_QUALITY = 3      # MJPEG quality (lower = better quality/larger size, 2-5 is often good)
OVERWRITE_EXISTING = False # Set to True if you want to re-process existing files

# Define expected output extensions
OUTPUT_VIDEO_EXT = ".avi"
OUTPUT_AUDIO_EXT = ".wav" # Or ".ogg" if you chose that format

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
        # This specific error might occur if imageio_ffmpeg fails its download/lookup
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
    # Ensure all args are strings, especially important for quality value
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
            check=True, # Raise exception on non-zero exit code
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='ignore', # Ignore potential decoding errors in ffmpeg output
            startupinfo=startupinfo
        )
        # Optional: print stdout for debugging
        # if result.stdout: print(f"  FFmpeg stdout:\n{result.stdout}")

        # Print stderr (often contains useful info/warnings even on success)
        # Filter out common noisy messages if desired
        if result.stderr:
            filtered_stderr = "\n".join(line for line in result.stderr.splitlines()
                                        if "deprecated pixel format used" not in line.lower()
                                        and "use -update true" not in line.lower()) # Filter more noise
            if filtered_stderr.strip():
                 print(f"  FFmpeg stderr:\n{filtered_stderr}")

        print(f"  Successfully created: {output_file}")
        return True

    except FileNotFoundError:
        # This specific error inside run() means the executable path itself was wrong
        print(f"ERROR: Could not execute ffmpeg. Path '{ffmpeg_executable}' not found or invalid.", file=sys.stderr)
        return False
    except subprocess.CalledProcessError as e:
        print(f"ERROR: ffmpeg failed for {input_file} -> {output_file}", file=sys.stderr)
        print(f"  Return code: {e.returncode}", file=sys.stderr)
        print(f"  Command: {' '.join(e.cmd)}", file=sys.stderr)
        # Print the full stderr on error, as it's crucial for diagnosis
        print(f"  Stderr:\n{e.stderr}", file=sys.stderr)
        # Clean up partially created file if it exists
        if os.path.exists(output_file):
            try:
                os.remove(output_file)
                print(f"  Removed potentially corrupt output file: {output_file}")
            except OSError as remove_err:
                 print(f"  Warning: Could not remove output file {output_file}: {remove_err}")
        return False
    except Exception as e:
        print(f"ERROR: An unexpected error occurred running ffmpeg: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr) # Print full traceback for unexpected errors
        return False

# --- Main Processing Logic ---

if __name__ == "__main__":
    print("Starting video pre-processing...")
    print(f"Looking for .mp4 files in: {os.path.abspath(TARGET_DIRECTORY)}")
    print(f"Will create {OUTPUT_VIDEO_EXT} (MJPEG Q={MJPEG_QUALITY}) and {OUTPUT_AUDIO_EXT} files.")
    if OVERWRITE_EXISTING:
        print("WARNING: OVERWRITE_EXISTING is True. Existing preprocessed files will be replaced.")

    # --- Get ffmpeg path using imageio_ffmpeg ---
    ffmpeg_executable = get_ffmpeg_executable()
    if not ffmpeg_executable:
        print("\nERROR: Could not find ffmpeg executable. Preprocessing aborted.", file=sys.stderr)
        sys.exit(1) # Exit if ffmpeg is not found

    processed_count = 0
    skipped_count = 0
    error_count = 0

    target_abs_path = os.path.abspath(TARGET_DIRECTORY)

    try:
        found_mp4 = False
        for filename in os.listdir(target_abs_path):
            if filename.lower().endswith(".mp4"):
                found_mp4 = True
                input_mp4_path = os.path.join(target_abs_path, filename)
                base_name = os.path.splitext(filename)[0]

                # Define expected output paths
                output_video_path = os.path.join(target_abs_path, base_name + OUTPUT_VIDEO_EXT)
                output_audio_path = os.path.join(target_abs_path, base_name + OUTPUT_AUDIO_EXT)

                print(f"\nProcessing: {filename}")

                # --- Check if files already exist ---
                video_exists = os.path.exists(output_video_path)
                audio_exists = os.path.exists(output_audio_path)

                skip_video = video_exists and not OVERWRITE_EXISTING
                skip_audio = audio_exists and not OVERWRITE_EXISTING

                if skip_video and skip_audio:
                    print(f"  Skipping: Both {os.path.basename(output_video_path)} and {os.path.basename(output_audio_path)} already exist.")
                    skipped_count += 1
                    continue # Move to the next mp4 file

                # Count as processed only if we attempt at least one operation
                is_processing = False

                # --- 1. Transcode Video ---
                video_success = True # Assume success if skipped
                if skip_video:
                    print(f"  Skipping video transcode: {os.path.basename(output_video_path)} already exists.")
                else:
                    is_processing = True
                    print(f"  Creating Video ({os.path.basename(output_video_path)})...")
                    video_command = [
                        "-hide_banner", "-loglevel", "error", # Reduce console noise
                        "-i", input_mp4_path,
                        "-c:v", "mjpeg",
                        "-q:v", str(MJPEG_QUALITY), # Ensure quality is a string
                        "-an", # No audio in the video file
                        "-y", # Overwrite output without asking
                        output_video_path
                    ]
                    video_success = run_ffmpeg_command(ffmpeg_executable, video_command, input_mp4_path, output_video_path)
                    if not video_success:
                        error_count += 1
                        # Decide if you want to stop processing this file if video fails
                        # continue # Uncomment to skip audio extraction if video fails

                # --- 2. Extract Audio ---
                audio_success = True # Assume success if skipped
                if skip_audio:
                     print(f"  Skipping audio extraction: {os.path.basename(output_audio_path)} already exists.")
                else:
                    # Only process audio if video step was successful (or skipped)
                    if video_success:
                        is_processing = True
                        print(f"  Creating Audio ({os.path.basename(output_audio_path)})...")
                        audio_command = [
                            "-hide_banner", "-loglevel", "error", # Reduce console noise
                            "-i", input_mp4_path,
                            "-vn", # No video
                            "-acodec", "pcm_s16le", # Standard WAV codec
                            "-ar", "44100",        # Audio sample rate
                            "-ac", "2",            # Stereo audio
                            "-y", # Overwrite output without asking
                            output_audio_path
                        ]
                        audio_success = run_ffmpeg_command(ffmpeg_executable, audio_command, input_mp4_path, output_audio_path)
                        if not audio_success:
                            error_count += 1
                    else:
                        print("  Skipping audio extraction because video transcoding failed.")


                if is_processing and video_success and audio_success:
                     processed_count += 1 # Increment only if new files were attempted and succeeded

        if not found_mp4:
             print(f"\nWarning: No .mp4 files found in the target directory: {target_abs_path}")

    except FileNotFoundError:
        print(f"ERROR: Target directory not found: {target_abs_path}", file=sys.stderr)
        error_count += 1
    except Exception as e:
        print(f"ERROR: An unexpected error occurred during directory processing: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        error_count += 1


    print("\n-------------------------------------")
    print("Preprocessing Complete.")
    print(f"  Files Processed Successfully: {processed_count}")
    print(f"  Files Skipped (already exist): {skipped_count}")
    print(f"  Errors Encountered: {error_count}")
    print("-------------------------------------")

    if error_count > 0:
        print("Please review the error messages above.", file=sys.stderr)
        sys.exit(1) # Exit with error code if errors occurred
    else:
        sys.exit(0) # Exit with success code