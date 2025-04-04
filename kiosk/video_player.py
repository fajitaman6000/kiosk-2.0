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
import numpy as np
import queue  # Added for thread-safe queue

try:
    import pyautogui # For screen size detection
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[video player] Warning: pyautogui not found. Screen size detection unavailable, assuming 1920x1080.")


class VideoPlayer:
    # --- Constants ---
    # Increased queue size allows more buffering, potentially smoothing over
    # temporary hiccups in decoding speed, at the cost of memory.
    FRAME_QUEUE_SIZE = 30 # Number of frames to buffer ahead

    def __init__(self, ffmpeg_path):
        print("[video player] Initializing VideoPlayer (Optimized)")
        self.ffmpeg_path = ffmpeg_path
        self.is_playing = False
        self.should_stop = False # Flag to signal threads to stop
        self.playback_complete = True # Indicates if the last playback finished normally

        self.video_sound_channel = mixer.Channel(0)
        self.current_audio_path = None
        self.temp_dir = tempfile.mkdtemp(prefix="vidplayer_")

        self.frame_rate = 30.0
        self.frame_time = 1.0 / self.frame_rate

        # Threading and Queue
        self.video_reader_thread = None
        self.video_player_thread = None
        self.frame_queue = None # Will be initialized in play_video

        # Callbacks
        self.on_complete_callback = None
        self.frame_update_callback = None

        # Target dimensions
        self.target_width = 1920
        self.target_height = 1080
        self._update_target_dimensions() # Get screen size on init

        # State for resizing check
        self.source_width = 0
        self.source_height = 0
        self.needs_resizing = False

    def _update_target_dimensions(self):
        """Attempts to get screen size, falls back to default."""
        if PYAUTOGUI_AVAILABLE:
            try:
                width, height = pyautogui.size()
                # Basic sanity check for screen dimensions
                if width > 100 and height > 100:
                     self.target_width, self.target_height = width, height
                     print(f"[video player] Detected screen size: {self.target_width}x{self.target_height}")
                else:
                    raise ValueError(f"pyautogui returned invalid size: {width}x{height}")
            except Exception as e:
                 print(f"[video player] Error getting screen size via pyautogui: {e}. Using default {self.target_width}x{self.target_height}.")
        else:
             print(f"[video player] pyautogui not available. Using default screen size {self.target_width}x{self.target_height}.")

    def _reader_thread_func(self, video_path):
        """
        Reads frames from video, resizes if needed, puts them in the queue.
        Runs independently to decouple reading/decoding from playback timing.
        """
        print(f"[video player] Reader thread starting for: {video_path}")
        cap = None
        processed_frame_count = 0
        read_successful = False

        try:
            # Try opening with preferred backends for potential hardware acceleration
            # Note: Availability & effectiveness depend heavily on OpenCV build & system config
            # cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG) # Default/often robust
            # cap = cv2.VideoCapture(video_path, cv2.CAP_MSMF) # Windows Media Foundation
            # cap = cv2.VideoCapture(video_path, cv2.CAP_DSHOW) # DirectShow (older Windows)
            cap = cv2.VideoCapture(video_path) # Stick to default if unsure

            if not cap.isOpened():
                print(f"[video player] CRITICAL: Failed to open video in reader thread: {video_path}")
                # Signal player thread to stop by putting None in the queue
                if self.frame_queue:
                    try: self.frame_queue.put(None, timeout=0.5)
                    except queue.Full: pass # Player might already be stopping
                return # Exit thread

            read_successful = True # Mark that cap was opened

            # --- Get Video Properties ---
            self.source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            _fps = cap.get(cv2.CAP_PROP_FPS)

            # Validate FPS
            if _fps is None or not (0.1 < _fps < 121.0):
                print(f"[video player] Warning: Invalid/unreliable FPS ({_fps}) from video. Using default 30.")
                self.frame_rate = 30.0
            else:
                self.frame_rate = float(_fps)
            self.frame_time = 1.0 / self.frame_rate

            print(f"[video player] Video properties: {self.source_width}x{self.source_height} @ {self.frame_rate:.2f} FPS (Frame Time: {self.frame_time:.4f}s)")

            # --- Determine if resizing is needed ONCE ---
            self.needs_resizing = not (self.source_width == self.target_width and self.source_height == self.target_height)
            if self.needs_resizing:
                print(f"[video player] Resizing needed: Source {self.source_width}x{self.source_height} -> Target {self.target_width}x{self.target_height}")
                # Using INTER_LINEAR is a balance between speed and quality.
                # INTER_NEAREST is fastest but looks blocky. INTER_CUBIC is slower but better quality.
                resize_interpolation = cv2.INTER_LINEAR
            else:
                 print("[video player] No resizing needed.")


            # --- Frame Reading Loop ---
            while not self.should_stop:
                ret, frame = cap.read()

                if not ret:
                    # End of video stream
                    print("[video player] Reader: End of video stream reached.")
                    break # Exit loop naturally

                # --- Process Frame (Resizing if needed) ---
                # This is where the CPU work for resizing happens, offloaded
                # from the player timing thread.
                if self.needs_resizing:
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    processed_frame = frame # Use frame directly (it's BGR)

                # --- Put Frame in Queue ---
                # This will block if the queue is full, acting as backpressure
                # to prevent the reader from consuming too much memory if the
                # player thread falls behind.
                try:
                    # We send the BGR frame directly
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0) # Wait up to 1 sec if full
                    processed_frame_count += 1
                except queue.Full:
                    # This happens if the player thread is significantly delayed
                    # or stopped. Log it and check the stop flag again.
                    print("[video player] Reader: Frame queue full. Player might be lagging or stopped.")
                    # No 'continue' needed, the main loop condition self.should_stop handles exit
                except Exception as q_err:
                     print(f"[video player] Reader: Error putting frame in queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error


            print(f"[video player] Reader: Processed {processed_frame_count} frames.")

        except Exception as e:
            print("[video player] CRITICAL: Error in reader thread:")
            traceback.print_exc()
            self.should_stop = True # Ensure player thread stops if reader crashes
        finally:
            print("[video player] Reader thread cleaning up...")
            if cap and cap.isOpened():
                cap.release()
                print("[video player] Reader: Released video capture.")

            # Signal player thread that reading is finished (normally or abnormally)
            # Put 'None' sentinel value in the queue.
            if self.frame_queue:
                 try:
                     # Non-blocking put is safer here in finally, player might be dead
                     self.frame_queue.put(None, block=False)
                     print("[video player] Reader: Put None sentinel in queue.")
                 except queue.Full:
                      print("[video player] Reader: Queue full when trying to put None sentinel (player likely stopped abruptly).")
                 except Exception as e:
                     print(f"[video player] Reader: Error putting None sentinel: {e}")

            if not read_successful:
                print("[video player] Reader: Setting playback_complete to True as video never opened.")
                self.playback_complete = True # Ensure completion callback runs if start failed
                self.is_playing = False # Ensure state reflects failure

            print("[video player] Reader thread finished.")


    def _player_thread_func(self, audio_path):
        """
        Takes frames from the queue, handles timing/sync, plays audio,
        and calls the frame update callback.
        """
        print("[video player] Player thread starting.")
        frame_count = 0
        playback_start_perf_counter = -1.0 # Initialize later
        audio_started = False
        got_first_frame = False

        try:
            # --- Wait for the first frame ---
            # This ensures the reader has initialized and determined frame rate etc.
            # It also introduces the intended startup delay for buffering.
            print("[video player] Player: Waiting for first frame from reader...")
            first_frame = self.frame_queue.get(block=True, timeout=10.0) # Wait up to 10s for reader startup
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                self.is_playing = False
                self.playback_complete = True # Assume completion on immediate fail
                # No callback needed here, handled in finally
                return

            print(f"[video player] Player: Received first frame. Frame Time: {self.frame_time:.4f}s")
            got_first_frame = True

            # --- Audio Playback ---
            if audio_path and os.path.exists(audio_path):
                try:
                    if not mixer.get_init(): mixer.init(frequency=44100)
                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    audio_started = True
                    print("[video player] Player: Started audio playback.")
                except Exception as e:
                    print(f"[video player] Player: Error starting audio: {e}")
                    traceback.print_exc()
                    # Continue without audio
            else:
                print("[video player] Player: No valid audio path or file missing.")

            # --- Start Playback Timing ---
            playback_start_perf_counter = time.perf_counter()

            # --- Playback Loop ---
            current_frame = first_frame
            while True: # Loop until sentinel or stop signal
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Process Current Frame ---
                # We already have 'current_frame' (either first_frame or from previous loop end)
                if current_frame is not None: # Should always be true unless queue error
                    try:
                        # Frame is already processed (resized if needed) BGR numpy array
                        if self.frame_update_callback:
                            self.frame_update_callback(current_frame)
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True # Stop if we can't display
                        frame_count += 1
                    except Exception as frame_err:
                         print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")
                         # Consider stopping if callback fails repeatedly
                         # self.should_stop = True

                # --- Timing Calculation ---
                current_time = time.perf_counter()
                # Expected time for the *next* frame's display deadline
                expected_display_time = playback_start_perf_counter + frame_count * self.frame_time
                time_until_next_frame = expected_display_time - current_time

                # --- Get Next Frame (or wait) ---
                next_frame = None
                try:
                    if time_until_next_frame > 0.002: # If we have time, wait
                        # Wait, but wake up slightly early to fetch the next frame
                        sleep_duration = max(0, time_until_next_frame - 0.002)
                        time.sleep(sleep_duration)

                        # Try to get the next frame without blocking excessively
                        # If frame isn't ready exactly on time, we might skip it below
                        next_frame = self.frame_queue.get(block=True, timeout=max(0.001, self.frame_time * 0.5))
                    else:
                        # We are on time or slightly behind schedule
                        # Try to get the next frame immediately, non-blocking if possible
                        next_frame = self.frame_queue.get(block=False) # Non-blocking fetch

                except queue.Empty:
                     # Reader hasn't produced the next frame in time.
                     # This indicates the reader is the bottleneck.
                     lag_time = -time_until_next_frame # How much we are behind
                     # print(f"[video player] Player: Frame queue empty (lag: {lag_time:.3f}s). Waiting...")
                     # We simply loop back and try getting the frame again, effectively pausing playback
                     # until the reader catches up. We use the *blocking* get below.
                     # Alternative: Could implement frame skipping here if preferred.
                     try:
                         next_frame = self.frame_queue.get(block=True, timeout=self.frame_time * 2.0) # Wait longer
                     except queue.Empty:
                          print("[video player] Player: Timed out waiting for frame after lag. Reader may be stuck/slow.")
                          # If still empty after waiting, maybe stop?
                          # self.should_stop = True
                          # break # Or just continue trying? Continue is safer for now.
                          continue # Go back to start of loop and try get again
                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame from queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print("[video player] Player: Received None sentinel. End of stream.")
                    self.playback_complete = True # Normal completion
                    break # Exit loop

                # Prepare for next iteration
                current_frame = next_frame

                # --- Frame Skipping (Optional - if player itself is slow) ---
                # If, after getting the frame, we are *still* significantly behind
                # the *next* frame's deadline, we might skip processing/displaying
                # the 'current_frame' we just fetched. This is less common if the
                # callback is fast, as the bottleneck is usually reading or queue empty.
                # current_time = time.perf_counter()
                # time_until_next_frame = expected_display_time - current_time
                # if time_until_next_frame < -self.frame_time * 1.5: # Example: More than 1.5 frames behind
                #     print(f"[video player] Player: Skipping display of frame {frame_count} due to significant lag ({time_until_next_frame:.3f}s)")
                #     # Don't call callback, just loop to get the *next* frame immediately
                #     continue


        except queue.Empty:
             print("[video player] Player: Timed out waiting for the first frame. Aborting.")
             self.is_playing = False
             self.playback_complete = True # Treat as complete if couldn't start
        except Exception as e:
            print("[video player] CRITICAL: Error in player thread:")
            traceback.print_exc()
            self.playback_complete = False # Indicate abnormal termination
        finally:
            print(f"[video player] Player thread cleaning up... (Played approx {frame_count} frames)")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 self.playback_complete = True # Ensure completion runs if we never started

            # Ensure audio stops if it was playing and the thread exits
            if audio_started and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                # Give mixer a moment
                time.sleep(0.05)

            # --- Final State Update & Callback ---
            # This logic runs regardless of how the thread exited (normal, stopped, error)
            was_playing = self.is_playing # Store state before modifying
            self.is_playing = False # Mark as not playing *before* callback

            # If playback finished normally (got None sentinel) or was stopped externally
            # *and* a callback is registered, call it.
            # We check 'was_playing' to avoid calling completion if it failed to even start.
            if was_playing and self.on_complete_callback:
                 if self.playback_complete:
                     print("[video player] Player: Triggering on_complete_callback (Normal Completion or Stop).")
                 else:
                     print("[video player] Player: Triggering on_complete_callback (Abnormal Termination).")

                 try:
                      # Run callback in a separate thread to avoid blocking cleanup? Usually not necessary.
                      # threading.Timer(0.01, self.on_complete_callback).start()
                      self.on_complete_callback()
                 except Exception as cb_err:
                      print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
            elif not was_playing:
                 print("[video player] Player: Playback did not start or was already stopped, skipping final on_complete_callback.")


            print("[video player] Player thread finished.")

    # --- extract_audio: Remains largely the same, ensure temp dir handling is robust ---
    def extract_audio(self, video_path):
        """Extract audio using ffmpeg."""
        print(f"[video player] Attempting to extract audio from: {video_path}")
        if not os.path.exists(video_path):
             print(f"[video player] Error: Video file not found: {video_path}")
             return None
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            print("[video player] Error: ffmpeg path not configured or invalid.")
            # Try finding ffmpeg using imageio as a fallback
            try:
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                if ffmpeg_exe and os.path.exists(ffmpeg_exe):
                    print(f"[video player] Found ffmpeg via imageio_ffmpeg: {ffmpeg_exe}")
                    self.ffmpeg_path = ffmpeg_exe
                else:
                    print("[video player] Fallback: imageio_ffmpeg could not find ffmpeg.")
                    return None
            except Exception as ff_find_err:
                 print(f"[video player] Error trying to find ffmpeg via imageio_ffmpeg: {ff_find_err}")
                 return None

        # Ensure temp dir exists
        try:
             if not os.path.exists(self.temp_dir):
                 os.makedirs(self.temp_dir)
                 print(f"[video player] Created temp directory: {self.temp_dir}")
        except OSError as dir_err:
             print(f"[video player] Error creating temp directory {self.temp_dir}: {dir_err}")
             return None

        # Generate temp file path
        try:
             # Use a more unique name, less likely to clash if cleanup fails
             safe_basename = "".join(c if c.isalnum() else "_" for c in os.path.basename(video_path))
             temp_audio = os.path.join(self.temp_dir, f"audio_{safe_basename}_{int(time.time()*1000)}.wav")
        except Exception as temp_err:
             print(f"[video player] Error creating temp file path: {temp_err}")
             return None

        print(f"[video player] Extracting audio to: {temp_audio}")
        command = [
            self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vn",                  # No video
            "-acodec", "pcm_s16le", # Standard WAV codec
            "-ar", "44100",         # Audio sample rate
            "-ac", "2",             # Stereo audio
            "-y",                   # Overwrite output file without asking
            temp_audio,
        ]

        try:
            startupinfo = None
            if os.name == 'nt': # Hide console window on Windows
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(command, capture_output=True, text=True, check=False, startupinfo=startupinfo, encoding='utf-8', errors='ignore') # Added errors='ignore' for weird ffmpeg output

            if result.returncode != 0:
                print(f"[video player] ffmpeg error (code {result.returncode}): {result.stderr}")
                self._safe_remove(temp_audio)
                return None
            else:
                # Check if file exists and has a reasonable size (e.g., > 1KB)
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024:
                    print("[video player] Audio extraction successful.")
                    # Clean up previous audio if any
                    self._cleanup_resources()
                    self.current_audio_path = temp_audio
                    return temp_audio
                else:
                     print(f"[video player] Error: Temp audio file missing, empty, or too small after ffmpeg success: {temp_audio}")
                     self._safe_remove(temp_audio) # Clean up invalid file
                     return None

        except FileNotFoundError:
             print(f"[video player] Error: ffmpeg executable not found at '{self.ffmpeg_path}'. Check path.")
             return None
        except Exception as e:
            print(f"[video player] Audio extraction error: {e}")
            traceback.print_exc()
            self._safe_remove(temp_audio)
            return None

    def play_video(self, video_path, audio_path, frame_update_cb, on_complete_cb):
        """Start video playback using reader and player threads."""
        print(f"[video player] play_video called for: {video_path}")

        if self.is_playing:
            print("[video player] Warning: Already playing, stopping previous video first...")
            self.stop_video(wait=True) # Wait for previous stop to complete
            print("[video player] Previous video stopped.")
            time.sleep(0.1) # Brief pause after stop

        # --- Reset State ---
        self.should_stop = False
        self.playback_complete = False # Reset completion status
        self.needs_resizing = False # Reset resize flag
        self.source_width = 0
        self.source_height = 0
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)

        # --- Set Callbacks ---
        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        # --- Set Playing Flag (Crucial: Before starting threads) ---
        self.is_playing = True # Signal that playback is intended to start

        # --- Start Threads ---
        # 1. Reader Thread
        self.video_reader_thread = threading.Thread(
            target=self._reader_thread_func,
            args=(video_path,),
            daemon=True,
            name=f"VideoReader-{os.path.basename(video_path)}"
        )

        # 2. Player Thread
        self.video_player_thread = threading.Thread(
            target=self._player_thread_func,
            args=(audio_path,), # Player handles audio start
            daemon=True,
            name=f"VideoPlayer-{os.path.basename(video_path)}"
        )

        print("[video player] Starting reader thread...")
        self.video_reader_thread.start()

        print("[video player] Starting player thread...")
        self.video_player_thread.start()

        print("[video player] Playback initiated.")


    def stop_video(self, wait=False):
        """Stop video playback gracefully."""
        print(f"[video player] stop_video called (wait={wait}). is_playing={self.is_playing}")

        if not self.is_playing and self.should_stop:
             # Already stopping or stopped
             # print("[video player] Already stopping/stopped.")
             return

        if not self.is_playing and not self.should_stop:
             # Was not playing and not trying to stop, maybe cleanup stale resources?
             print("[video player] stop_video called but not playing. Cleaning up resources just in case.")
             self._cleanup_resources()
             return

        # --- Signal Threads to Stop ---
        self.should_stop = True
        # is_playing will be set to False by the player thread itself upon exit

        print("[video player] Stop signal sent to threads.")

        # --- Stop Audio Immediately ---
        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()
            time.sleep(0.05) # Give mixer a moment

        # --- Unblock Queue (Optional but helpful) ---
        # If threads are blocked on queue put/get, putting None helps them exit faster.
        if self.frame_queue:
            try:
                # Clear the queue to potentially unblock reader faster if queue was full
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                # Put sentinel to ensure player thread unblocks from get()
                self.frame_queue.put(None, block=False)
            except queue.Full:
                 print("[video player] Warning: Queue full when trying to clear/put None during stop.")
            except Exception as e:
                 print(f"[video player] Error interacting with queue during stop: {e}")

        # --- Wait for Threads to Join (if requested) ---
        if wait:
            join_timeout = 2.0 # Max wait time for threads
            print(f"[video player] Waiting for threads to join (timeout {join_timeout}s)...")
            if self.video_reader_thread and self.video_reader_thread.is_alive():
                self.video_reader_thread.join(timeout=join_timeout/2)
                if self.video_reader_thread.is_alive():
                     print("[video player] Warning: Reader thread did not exit cleanly after stop request.")

            if self.video_player_thread and self.video_player_thread.is_alive():
                 # Player thread should exit after getting None or seeing should_stop
                 self.video_player_thread.join(timeout=join_timeout/2)
                 if self.video_player_thread.is_alive():
                      print("[video player] Warning: Player thread did not exit cleanly after stop request.")

            # Final check after waiting
            self.is_playing = False # Force state if threads didn't exit cleanly
            print("[video player] Thread join finished.")

        # Resource cleanup happens via the player thread's finally block and on_complete callback
        # Or via _cleanup_resources if called explicitly or by __del__
        print("[video player] stop_video finished signaling.")

    def force_stop(self):
        """Force stop playback immediately, cleanup resources NOW."""
        print("[video player] Force stopping playback.")

        # Signal threads immediately
        self.should_stop = True
        self.is_playing = False # Set state immediately

        # Stop audio
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            print("[video player] Force stopped audio channel.")
            time.sleep(0.05)

        # Help threads exit queue waits
        if self.frame_queue:
            try:
                # Clear queue
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False) # Unblock player
            except Exception: pass # Ignore errors during force stop queue interaction

        # Don't wait long for threads in force_stop
        join_timeout = 0.2
        if self.video_reader_thread and self.video_reader_thread.is_alive():
             self.video_reader_thread.join(timeout=join_timeout)
        if self.video_player_thread and self.video_player_thread.is_alive():
             self.video_player_thread.join(timeout=join_timeout)

        # Clean up resources immediately in force stop scenario
        self._cleanup_resources()

        # Reset internal state completely
        self.reset_state()
        print("[video player] Force stop complete.")

    def reset_state(self):
        """Reset state variables, typically after a force_stop or for reuse."""
        print("[video player] Resetting internal state.")
        self.should_stop = False
        self.is_playing = False
        self.playback_complete = True # Default to true when reset
        self.video_reader_thread = None
        self.video_player_thread = None
        self.frame_queue = None # Ensure queue is gone
        self.on_complete_callback = None
        self.frame_update_callback = None
        self.needs_resizing = False
        self.source_width = 0
        self.source_height = 0


    def _safe_remove(self, filepath):
        """Attempts to remove a file, ignoring errors if it doesn't exist."""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                # print(f"[video player] Removed file: {filepath}") # Debug noise
            except OSError as e:
                print(f"[video player] Warning: Could not remove file {filepath}: {e}")
            except Exception as e:
                 print(f"[video player] Error removing file {filepath}: {e}")

    def _cleanup_resources(self):
        """Clean up temporary audio files."""
        # print("[video player] Cleaning up resources...") # Reduce noise
        audio_to_remove = self.current_audio_path
        self.current_audio_path = None # Clear path immediately

        self._safe_remove(audio_to_remove)


    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            # Ensure playback is stopped (use non-waiting stop)
            if self.is_playing:
                 print("[video player] Destructor: Stopping active playback...")
                 self.stop_video(wait=False) # Signal stop, don't block destructor

            # Cleanup any lingering temp audio
            self._cleanup_resources()

            # Remove the temporary directory
            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
                print(f"[video player] Destructor: Cleaning up temporary directory: {temp_dir_to_remove}")
                import shutil
                # Use ignore_errors=True as files might still be locked briefly
                shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                print(f"[video player] Destructor: Removed temporary directory (ignore_errors=True).")

        except Exception as e:
             # Catch errors during __del__ as they can be problematic
             print(f"[video player] Error during __del__: {e}")
        finally:
             # Ensure base class __del__ is called if necessary (though not needed here)
             # super().__del__()
             pass
        self.temp_dir = None