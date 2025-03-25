# video_player.py
import cv2
import threading
import time
import traceback
import os
import subprocess
import tempfile
import imageio_ffmpeg
from pygame import mixer
import numpy as np # Need numpy if passing raw frames

# --- NO LONGER NEED tkinter, PIL, ImageTk ---

class VideoPlayer:
    def __init__(self, ffmpeg_path):
        print("[video player] Initializing VideoPlayer")
        self.ffmpeg_path = ffmpeg_path
        self.is_playing = False
        self.should_stop = False
        self.resetting = False # Flag for forced resets
        self.video_sound_channel = mixer.Channel(0) # Use a dedicated channel
        self.current_audio_path = None
        self.temp_dir = tempfile.mkdtemp(prefix="vidplayer_")
        self.frame_rate = 30  # Default frame rate
        self.video_thread = None
        self.on_complete_callback = None # Callback for video_manager
        self.frame_update_callback = None # Callback to send frames TO video_manager/overlay

    def _play_video_thread(self, video_path, audio_path):
        """Video playback thread: reads frames, sends them via callback, syncs audio."""
        print(f"[video player] Video thread starting for: {video_path}")
        start_time = None
        playback_start_perf_counter = time.perf_counter() # More precise timing

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[video player] Failed to open video: {video_path}")
                self.is_playing = False # Ensure state reflects failure
                if self.on_complete_callback:
                    # Use a delay before calling back to avoid race conditions
                    threading.Timer(0.1, self.on_complete_callback).start()
                return

            self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
            if self.frame_rate <= 0 or self.frame_rate > 120: # Sanity check FPS
                print(f"[video player] Warning: Invalid frame rate ({self.frame_rate}), using 30.")
                self.frame_rate = 30
            frame_time = 1.0 / self.frame_rate
            print(f"[video player] Video opened. FPS: {self.frame_rate:.2f}, Frame time: {frame_time:.4f}s")

            # --- Get target dimensions (screen size) ---
            # Note: We get this from the overlay now, or assume fullscreen
            # For now, let's get screen size here just for potential resizing logic
            # This requires a way to get screen size without Tkinter.
            # Using 'pyautogui' or platform-specific calls is an option,
            # but simplest is to assume frames are SENT raw and RESIZED by Overlay if needed.
            # Let's resize here using OpenCV for efficiency. We need target W/H.
            # Hacky way: Assume standard HD for now. Replace with proper screen detection later.
            target_width = 1920
            target_height = 1080
            try:
                # A better way might involve passing screen dimensions during play_video
                import pyautogui # Requires installation: pip install pyautogui
                target_width, target_height = pyautogui.size()
                print(f"[video player] Detected screen size: {target_width}x{target_height}")
            except ImportError:
                print("[video player] pyautogui not found, assuming 1920x1080.")
            except Exception as e:
                 print(f"[video player] Error getting screen size: {e}, assuming 1920x1080.")


            # Start audio playback if available
            if audio_path and os.path.exists(audio_path):
                try:
                    # Ensure mixer is ready
                    if not mixer.get_init():
                        mixer.init(frequency=44100)
                        print("[video player] Re-initialized pygame mixer.")
                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    start_time = time.time() # For frame sync if needed (less critical with perf_counter)
                    playback_start_perf_counter = time.perf_counter() # Reset start time for precision
                    print("[video player] Started audio playback.")
                except Exception as e:
                    print(f"[video player] Error starting audio: {e}")
                    traceback.print_exc()
                    audio_path = None # Proceed without audio
            else:
                print("[video player] No valid audio path provided or file missing.")
                playback_start_perf_counter = time.perf_counter() # Start timer even without audio


            frame_count = 0
            last_frame_display_time = playback_start_perf_counter

            while cap.isOpened() and self.is_playing and not self.should_stop:
                if self.resetting:
                    print("[video player] Resetting flag set, breaking playback loop.")
                    break

                # --- Precise Timing Calculation ---
                current_time = time.perf_counter()
                expected_time = playback_start_perf_counter + frame_count * frame_time
                wait_time = expected_time - current_time

                # Frame Skipping Logic (if falling behind)
                while wait_time < -frame_time * 2 and self.is_playing: # Skip if more than 2 frames behind
                    ret, _ = cap.read() # Read and discard frame
                    if not ret: break # End of video
                    frame_count += 1
                    expected_time = playback_start_perf_counter + frame_count * frame_time
                    wait_time = expected_time - current_time
                    # print(f"[video player] Skipped frame {frame_count}") # Debug noise

                if wait_time < -frame_time * 10: # Major lag, maybe reset start time?
                     print(f"[video player] Warning: Significant lag detected ({wait_time:.3f}s).")
                     # Consider resetting playback_start_perf_counter here if sync is lost

                # Wait if we are ahead
                if wait_time > 0.001: # Sleep threshold
                    time.sleep(max(0, wait_time - 0.001)) # Sleep slightly less than needed

                # Read the actual frame
                ret, frame = cap.read()
                if not ret:
                    print("[video player] End of video stream.")
                    break # Exit loop normally

                # Process and send frame *only if still playing*
                if self.is_playing and not self.should_stop:
                    try:
                         # --- Resize frame using OpenCV ---
                        resized_frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR) # Use INTER_LINEAR for speed

                        # --- Send frame data (NumPy array) via callback ---
                        if self.frame_update_callback:
                            self.frame_update_callback(resized_frame)
                        else:
                            print("[video player] Error: frame_update_callback not set!")
                            self.should_stop = True # Stop if callback missing
                    except Exception as frame_err:
                         print(f"[video player] Error processing/sending frame {frame_count}: {frame_err}")
                         # Decide whether to stop or continue on frame error

                frame_count += 1
                last_frame_display_time = time.perf_counter() # Update last display time

                # --- Small sleep to yield thread ---
                # time.sleep(0.001) # Maybe not needed with precise timing? Test.


        except Exception as e:
            print("[video player] Error in video thread:")
            traceback.print_exc()
        finally:
            print("[video player] Cleaning up video thread...")
            if cap and cap.isOpened():
                cap.release()
                print("[video player] Released video capture.")

            # Stop audio if playing
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Stopped video audio channel.")
                time.sleep(0.05) # Allow mixer to process stop

            # --- Crucial: Call the completion callback via main thread ---
            # This signals video_manager that the *player* has finished/stopped.
            if self.on_complete_callback and not self.resetting:
                print("[video player] Triggering on_complete_callback.")
                # video_manager is responsible for calling this in the main thread (via root.after or Qt equivalent)
                # We just call it directly here, assuming video_manager handles threading.
                try:
                    self.on_complete_callback()
                except Exception as cb_err:
                    print(f"[video player] Error executing on_complete_callback: {cb_err}")
            elif self.resetting:
                print("[video player] Resetting, skipping final on_complete_callback.")

            self.is_playing = False # Final state update
            print("[video player] Video thread finished.")

    def extract_audio(self, video_path):
        """Extract audio using ffmpeg."""
        print(f"[video player] Attempting to extract audio from: {video_path}")
        if not os.path.exists(video_path):
             print(f"[video player] Error: Video file not found: {video_path}")
             return None
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            print("[video player] Error: ffmpeg path not configured or invalid.")
            return None

        # Create a unique temp file name
        base_name = os.path.splitext(os.path.basename(video_path))[0]
        # Use a more robust temp file creation in the designated temp dir
        try:
             # fd, temp_audio = tempfile.mkstemp(suffix=".wav", prefix=f"{base_name}_", dir=self.temp_dir)
             # os.close(fd) # Close the file descriptor
             # Using fixed name pattern in temp dir for simplicity, ensure cleanup
             temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time()*1000)}.wav")
        except Exception as temp_err:
             print(f"[video player] Error creating temp file path: {temp_err}")
             return None


        print(f"[video player] Extracting audio to: {temp_audio}")
        command = [
            self.ffmpeg_path,
            "-i", video_path,
            "-vn",  # No video
            "-acodec", "pcm_s16le",  # Standard WAV codec
            "-ar", "44100",  # Sample rate
            "-ac", "2",  # Stereo audio
            "-y",  # Overwrite output file if it exists
            temp_audio,
        ]

        try:
            # Use STARTUPINFO to hide console window on Windows
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(command, capture_output=True, text=True, check=False, startupinfo=startupinfo) # check=False to inspect errors

            if result.returncode != 0:
                print(f"[video player] ffmpeg error (return code {result.returncode}):")
                print(f"--- STDOUT ---\n{result.stdout}")
                print(f"--- STDERR ---\n{result.stderr}")
                # Clean up failed attempt
                if os.path.exists(temp_audio):
                    try:
                        os.remove(temp_audio)
                    except OSError as rm_err:
                        print(f"[video player] Could not remove failed temp audio file {temp_audio}: {rm_err}")
                return None
            else:
                print("[video player] ffmpeg audio extraction successful.")
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
                    self.current_audio_path = temp_audio # Store path for cleanup
                    return temp_audio
                else:
                     print(f"[video player] Error: Temp audio file not created or empty: {temp_audio}")
                     return None

        except FileNotFoundError:
             print(f"[video player] Error: ffmpeg not found at '{self.ffmpeg_path}'. Ensure it's installed and path is correct.")
             return None
        except Exception as e:
            print(f"[video player] Audio extraction error: {e}")
            traceback.print_exc()
            # Clean up failed attempt
            if os.path.exists(temp_audio):
                 try:
                     os.remove(temp_audio)
                 except OSError as rm_err:
                     print(f"[video player] Could not remove failed temp audio file {temp_audio}: {rm_err}")
            return None

    def play_video(self, video_path, audio_path, frame_update_cb, on_complete_cb):
        """Start video playback in a separate thread."""
        print(f"[video player] play_video called for: {video_path}")
        if self.is_playing:
            print("[video player] Warning: Already playing, stopping previous video first.")
            self.stop_video()
            time.sleep(0.2) # Give previous stop some time

        self.should_stop = False
        self.resetting = False
        self.is_playing = True
        self.frame_update_callback = frame_update_cb # Store the frame update callback
        self.on_complete_callback = on_complete_cb   # Store the completion callback

        # --- NO UI CREATION HERE ---
        # The overlay is handled by video_manager calling Overlay methods.

        # Start playback thread
        self.video_thread = threading.Thread(
            target=self._play_video_thread,
            args=(video_path, audio_path),
            daemon=True, # Daemon thread exits if main program exits
            name=f"VideoPlayerThread-{os.path.basename(video_path)}"
        )
        print("[video player] Starting video thread...")
        self.video_thread.start()

    def stop_video(self):
        """Stop video and audio playback gracefully."""
        print("[video player] stop_video called.")
        if not self.is_playing and not self.should_stop:
             print("[video player] Not playing, stop request ignored.")
             return # Already stopped or stop already requested

        self.should_stop = True # Signal the thread to stop
        self.is_playing = False # Set state immediately

        # Stop audio channel directly
        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()

        # Wait briefly for the thread to potentially exit on its own
        if self.video_thread and self.video_thread.is_alive():
             print("[video player] Waiting for video thread to join (timeout 0.5s)...")
             self.video_thread.join(timeout=0.5) # Wait max 0.5 seconds
             if self.video_thread.is_alive():
                  print("[video player] Warning: Video thread did not exit cleanly after 0.5s.")
                  # Consider more forceful cleanup if needed, but usually letting it finish is ok

        self._cleanup_resources() # Perform resource cleanup (like temp files)
        print("[video player] stop_video finished.")


    def force_stop(self):
        """Force stop playback immediately, intended for reset scenarios."""
        print("[video player] Force stopping playback.")
        self.resetting = True # Signal a forced reset
        self.should_stop = True
        self.is_playing = False

        # Stop audio immediately
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            print("[video player] Force stopped audio channel.")
            time.sleep(0.05)

        # Don't wait long for the thread, just signal and clean up
        if self.video_thread and self.video_thread.is_alive():
            print("[video player] Video thread still alive during force_stop (expected).")
            # self.video_thread.join(timeout=0.1) # Very short wait if any

        self._cleanup_resources() # Clean up resources
        self.reset_state() # Reset internal state variables
        print("[video player] Force stop complete.")

    def reset_state(self):
        """Reset state variables, typically after a force_stop."""
        print("[video player] Resetting internal state.")
        self.should_stop = False # Ready for next playback
        self.is_playing = False
        self.resetting = False
        self.video_thread = None
        self.on_complete_callback = None
        self.frame_update_callback = None
        # Keep self.current_audio_path until cleaned up
        # Keep temp_dir until __del__

    def _cleanup_resources(self):
        """Clean up temporary files and potentially other resources."""
        print("[video player] Cleaning up resources...")
        # Clean up the temporary audio file *if* it exists and belongs to this instance
        audio_to_remove = self.current_audio_path
        if audio_to_remove and os.path.exists(audio_to_remove):
            print(f"[video player] Attempting to remove temp audio file: {audio_to_remove}")
            try:
                # Retry mechanism for removal
                for attempt in range(3):
                    time.sleep(0.1 * (attempt + 1))
                    os.remove(audio_to_remove)
                    print(f"[video player] Removed temp audio file on attempt {attempt+1}.")
                    self.current_audio_path = None # Clear path after successful removal
                    break # Exit retry loop
                else:
                    print(f"[video player] Warning: Failed to remove temp audio file after multiple attempts: {audio_to_remove}")
            except PermissionError as pe:
                 print(f"[video player] Permission error removing temp audio file {audio_to_remove}: {pe}")
            except OSError as e:
                print(f"[video player] Error removing temp audio file {audio_to_remove}: {e}")
            except Exception as e:
                print(f"[video player] Unexpected error removing temp audio file: {e}")
        elif audio_to_remove:
            print(f"[video player] Temp audio file path stored but file not found: {audio_to_remove}")
            self.current_audio_path = None # Clear path if file doesn't exist
        else:
            print("[video player] No current audio file path to clean up.")


    def __del__(self):
        """Destructor: Ensure cleanup of the temporary directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        self.force_stop() # Ensure everything is stopped

        # Clean up the entire temporary directory
        temp_dir_to_remove = getattr(self, 'temp_dir', None)
        if temp_dir_to_remove and os.path.exists(temp_dir_to_remove):
            print(f"[video player] Cleaning up temporary directory: {temp_dir_to_remove}")
            try:
                # First, remove files within the directory
                for filename in os.listdir(temp_dir_to_remove):
                    file_path = os.path.join(temp_dir_to_remove, filename)
                    try:
                        if os.path.isfile(file_path) or os.path.islink(file_path):
                            os.unlink(file_path)
                            # print(f"[video player] Removed file: {file_path}")
                        # Optionally remove subdirectories if needed, but safer not to unless intended
                        # elif os.path.isdir(file_path):
                        #     shutil.rmtree(file_path)
                    except Exception as e:
                        print(f"[video player] Failed to remove item {file_path}: {e}")

                # Now remove the empty directory
                os.rmdir(temp_dir_to_remove)
                print(f"[video player] Removed temporary directory: {temp_dir_to_remove}")
            except OSError as e:
                print(f"[video player] Error removing temporary directory {temp_dir_to_remove}: {e}")
            except Exception as e:
                 print(f"[video player] Unexpected error cleaning temp directory: {e}")
        elif temp_dir_to_remove:
             print(f"[video player] Temporary directory path exists but directory not found: {temp_dir_to_remove}")

        self.temp_dir = None # Clear reference