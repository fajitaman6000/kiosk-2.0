import os
import subprocess
import shutil
import cv2
import tempfile
import threading
from queue import Queue

def get_video_dimensions(video_path):
    """Gets the width and height of a video using OpenCV."""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"Error: Could not open video file: {video_path}")
            return None, None

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        cap.release()
        return width, height
    except Exception as e:
        print(f"Error getting video dimensions for {video_path}: {e}")
        return None, None

def rotate_video(input_path, output_path, angle, error_queue):
    """Rotates an MP4 video, handling errors, using a temp file."""
    try:
        if angle not in [90, -90, 270]:
            raise ValueError("Only 90, -90 (270) rotations are supported.")

        width, height = get_video_dimensions(input_path)
        if width is None or height is None:
            error_queue.put((input_path, "Dimension retrieval error."))
            return

        if angle == 90:
            transpose_filter = "transpose=1"
        elif angle == -90 or angle == 270:
            transpose_filter = "transpose=2"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as temp_file:
            temp_output_path = temp_file.name

        ffmpeg_command = [
            "ffmpeg",
            "-i", input_path,
            "-vf", transpose_filter,
            "-c:a", "copy",
            "-y",  # Overwrite output files without asking
            temp_output_path
        ]

        # Use subprocess.PIPE to handle output buffering correctly
        process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()  # Read output *while* running
        returncode = process.returncode

        if returncode != 0:
            error_message = (f"FFmpeg error: Return code: {returncode}, "
                             f"Stdout: {stdout}, Stderr: {stderr}")
            error_queue.put((input_path, error_message))
        else:
            print(f"Successfully rotated '{input_path}' to '{temp_output_path}'")
            shutil.move(temp_output_path, output_path)
            print(f"Moved temporary file to '{output_path}'")


    except FileNotFoundError:
        error_message = ("FFmpeg not found.  Ensure FFmpeg is installed "
                         "and in your system's PATH.")
        error_queue.put((input_path, error_message))
    except Exception as e:
        error_message = f"An unexpected error occurred: {e}"
        error_queue.put((input_path, error_message))
    finally:
        if 'temp_output_path' in locals() and os.path.exists(temp_output_path):
            try:
                os.remove(temp_output_path)
            except OSError as e:
                print(f"Error removing temporary file {temp_output_path}: {e}")



def worker(queue, output_directory, error_queue):
    """Processes video rotation tasks from the queue."""
    while True:
        filename = queue.get()
        if filename is None:  # Sentinel value
            break
        input_filepath = os.path.join(os.getcwd(), filename)
        output_filepath = os.path.join(output_directory, filename)
        rotate_video(input_filepath, output_filepath, 90, error_queue)
        queue.task_done()

def main():
    """Finds, rotates (90 degrees), and saves MP4 files (threaded)."""
    current_directory = os.getcwd()
    output_directory = os.path.join(current_directory, "rotated_videos")

    if not os.path.exists(output_directory):
        os.makedirs(output_directory)
        print(f"Created output directory: {output_directory}")

    print(f"Processing MP4 files in: {current_directory}")

    queue = Queue()
    error_queue = Queue()
    num_threads = os.cpu_count() or 1
    threads = []

    for _ in range(num_threads):
        thread = threading.Thread(target=worker, args=(queue, output_directory, error_queue))
        thread.start()
        threads.append(thread)

    for filename in os.listdir(current_directory):
        if filename.lower().endswith(".mp4"):
            output_filepath = os.path.join(output_directory, filename)
            if os.path.exists(output_filepath):
                print(f"Skipping '{filename}': already exists.")
                continue
            queue.put(filename)

    queue.join()

    for _ in range(num_threads):
        queue.put(None)
    for thread in threads:
        thread.join()

    if not error_queue.empty():
        print("\nErrors during processing:")
        while not error_queue.empty():
            input_file, error_message = error_queue.get()
            print(f"- File: {input_file}, Error: {error_message}")

if __name__ == "__main__":
    main()