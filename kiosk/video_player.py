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
    # Threshold for frame skipping: If display time is lagging behind ideal time
    # by more than this multiple of frame_time, skip the frame.
    FRAME_SKIP_THRESHOLD_FACTOR = 1.5 # e.g., skip if more than 1.5 frames behind

    def __init__(self, ffmpeg_path):
        print("[video player] Initializing VideoPlayer (Optimized + Frame Skipping)")
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
            # Consider trying specific backends if default is slow, but default is often reliable
            # cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
            cap = cv2.VideoCapture(video_path) # Stick to default

            if not cap.isOpened():
                print(f"[video player] CRITICAL: Failed to open video in reader thread: {video_path}")
                if self.frame_queue:
                    try: self.frame_queue.put(None, timeout=0.5)
                    except queue.Full: pass
                return # Exit thread

            read_successful = True

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
            # Ensure frame_time is not zero if FPS is ridiculously high
            self.frame_time = 1.0 / self.frame_rate if self.frame_rate > 0 else 1.0/30.0

            print(f"[video player] Video properties: {self.source_width}x{self.source_height} @ {self.frame_rate:.2f} FPS (Frame Time: {self.frame_time:.4f}s)")

            # --- Determine if resizing is needed ONCE ---
            self.needs_resizing = not (self.source_width == self.target_width and self.source_height == self.target_height)
            if self.needs_resizing:
                print(f"[video player] Resizing needed: Source {self.source_width}x{self.source_height} -> Target {self.target_width}x{self.target_height}")
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
                if self.needs_resizing:
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    processed_frame = frame # Use frame directly (it's BGR)

                # --- Put Frame in Queue ---
                try:
                    # We send the BGR frame directly
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0) # Wait up to 1 sec if full
                    processed_frame_count += 1
                except queue.Full:
                    # Reader is outpacing player, or player stopped.
                    # print("[video player] Reader: Frame queue full. Player might be lagging or stopped.") # Can be noisy
                    if self.should_stop: break # Exit if stop signal is set
                    # If not stopping, continue trying to put (backpressure)
                except Exception as q_err:
                     print(f"[video player] Reader: Error putting frame in queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error

            print(f"[video player] Reader: Processed {processed_frame_count} frames.")

        except Exception as e:
            print("[video player] CRITICAL: Error in reader thread:")
            traceback.print_exc()
            self.should_stop = True
        finally:
            print("[video player] Reader thread cleaning up...")
            if cap and cap.isOpened():
                cap.release()
                print("[video player] Reader: Released video capture.")

            # Signal player thread that reading is finished
            if self.frame_queue:
                 try:
                     self.frame_queue.put(None, block=False) # Non-blocking put is safer here
                     print("[video player] Reader: Put None sentinel in queue.")
                 except queue.Full:
                      print("[video player] Reader: Queue full when trying to put None sentinel.")
                 except Exception as e:
                     print(f"[video player] Reader: Error putting None sentinel: {e}")

            if not read_successful:
                print("[video player] Reader: Setting playback_complete to True as video never opened.")
                self.playback_complete = True
                self.is_playing = False

            print("[video player] Reader thread finished.")


    def _player_thread_func(self, audio_path):
        """
        Takes frames from the queue, handles timing/sync (with frame skipping),
        plays audio, and calls the frame update callback.
        """
        print("[video player] Player thread starting.")
        frame_count = 0 # Index of the frame we are about to process/display/skip
        playback_start_perf_counter = -1.0
        audio_started = False
        got_first_frame = False
        skipped_frame_count = 0

        try:
            # --- Wait for the first frame ---
            print("[video player] Player: Waiting for first frame from reader...")
            first_frame = self.frame_queue.get(block=True, timeout=10.0)
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                self.is_playing = False
                self.playback_complete = True
                return

            print(f"[video player] Player: Received first frame. Target Frame Time: {self.frame_time:.4f}s")
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
            else:
                print("[video player] Player: No valid audio path or file missing.")

            # --- Start Playback Timing ---
            playback_start_perf_counter = time.perf_counter()

            # --- Playback Loop ---
            current_frame = first_frame
            while True:
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Time Check BEFORE Processing Current Frame ---
                current_time = time.perf_counter()
                # Ideal time this *current* frame (index frame_count) should have started display
                ideal_display_time = playback_start_perf_counter + frame_count * self.frame_time
                lag = current_time - ideal_display_time

                # --- Frame Skipping Decision ---
                # Skip if we are too far behind the ideal time for this frame.
                # Also skip if current_frame is somehow None (shouldn't happen unless queue error)
                should_skip = (lag > (self.frame_time * self.FRAME_SKIP_THRESHOLD_FACTOR)) or (current_frame is None)

                if not should_skip:
                    # --- Process and Display Current Frame ---
                    try:
                        if self.frame_update_callback:
                            self.frame_update_callback(current_frame) # Pass the BGR frame
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True
                            break # Stop if we cannot display frames
                    except Exception as frame_err:
                         print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")
                         # Consider stopping if callback consistently fails
                         # self.should_stop = True
                else:
                    # Only log skips occasionally to avoid spamming console
                    if skipped_frame_count % 30 == 0: # Log approx once per second if skipping heavily
                       print(f"[video player] Player: Skipping frame {frame_count} due to lag: {lag:.3f}s (Total skips: {skipped_frame_count+1})")
                    skipped_frame_count += 1


                # Increment frame count regardless of whether it was displayed or skipped.
                # This keeps the timeline moving forward according to the video's frame rate.
                frame_count += 1

                # --- Timing Calculation for NEXT Frame ---
                # Calculate the ideal display time for the *next* frame (index frame_count)
                expected_next_display_time = playback_start_perf_counter + frame_count * self.frame_time
                time_until_next = expected_next_display_time - time.perf_counter() # Use updated current time

                # --- Get Next Frame ---
                next_frame = None
                try:
                    if time_until_next > 0.001: # If we have *any* time before the next deadline
                        # Wait, but wake up slightly early (e.g., 1-2ms) to fetch the frame
                        sleep_duration = max(0, time_until_next - 0.002)
                        time.sleep(sleep_duration)

                        # Try to get the next frame with a timeout that doesn't exceed
                        # the remaining time until the next frame, preventing unnecessary blocking
                        # if the reader is slightly slow. Use at least a minimal timeout.
                        get_timeout = max(0.001, min(self.frame_time * 0.8, time_until_next))
                        next_frame = self.frame_queue.get(block=True, timeout=get_timeout)

                    else:
                        # We are already late for the next frame (or exactly on time).
                        # Try a non-blocking get immediately. If it's not there, the reader is behind.
                        next_frame = self.frame_queue.get(block=False)

                except queue.Empty:
                    # Either the non-blocking get failed (we're late) or the timed get failed (reader slow).
                    # This indicates the reader is the bottleneck *right now*.
                    # print(f"[video player] Player: Frame queue empty waiting for frame {frame_count}.") # Can be noisy
                    # We *must* wait for the reader to produce the next frame to continue.
                    # Block until a frame arrives or we time out / stop signal.
                    try:
                        # Wait for a reasonable time (e.g., 2-3 frame times)
                        # If reader is permanently slow, this will keep timing out.
                        wait_timeout = self.frame_time * 3.0
                        next_frame = self.frame_queue.get(block=True, timeout=wait_timeout)
                    except queue.Empty:
                        # If we time out here, the reader is significantly stalled or stopped.
                        print(f"[video player] Player: WARN - Timed out ({wait_timeout:.2f}s) waiting for frame {frame_count} after queue was empty. Reader may be stuck/slow or video ended abruptly.")
                        # Option 1: Continue loop, hoping reader catches up (might cause infinite loop if reader died)
                        # Option 2: Assume playback error and stop
                        self.should_stop = True # Let's choose to stop if reader seems stuck
                        print("[video player] Player: Assuming reader issue, stopping playback.")
                        self.playback_complete = False # Indicate abnormal termination reason
                        break # Exit the main loop
                    except Exception as q_err_inner:
                        print(f"[video player] Player: Error during blocking get for frame {frame_count}: {q_err_inner}")
                        self.should_stop = True
                        break

                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame {frame_count} from queue: {q_err}")
                     traceback.print_exc()
                     self.should_stop = True # Signal stop on other queue errors
                     break # Exit loop

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print(f"[video player] Player: Received None sentinel after processing {frame_count} frames ({skipped_frame_count} skipped). End of stream.")
                    self.playback_complete = True # Normal completion
                    break # Exit loop

                # Prepare for next iteration
                current_frame = next_frame


        except queue.Empty:
             print("[video player] Player: Timed out waiting for the first frame. Aborting.")
             self.is_playing = False
             self.playback_complete = True # Treat as complete if couldn't start
        except Exception as e:
            print("[video player] CRITICAL: Error in player thread:")
            traceback.print_exc()
            self.playback_complete = False # Indicate abnormal termination
        finally:
            print(f"[video player] Player thread cleaning up... (Processed approx {frame_count} frames, Skipped: {skipped_frame_count})")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 self.playback_complete = True # Ensure completion runs if we never started

            # Ensure audio stops
            if audio_started and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                time.sleep(0.05)

            # --- Final State Update & Callback ---
            was_playing = self.is_playing
            self.is_playing = False

            if was_playing and self.on_complete_callback:
                 completion_reason = "Normal" if self.playback_complete else "Abnormal/Error"
                 print(f"[video player] Player: Triggering on_complete_callback ({completion_reason}).")
                 try:
                      self.on_complete_callback()
                 except Exception as cb_err:
                      print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
            elif not was_playing:
                 print("[video player] Player: Playback did not start or was already stopped, skipping final on_complete_callback.")


            print("[video player] Player thread finished.")

    # --- extract_audio: Remains the same ---
    def extract_audio(self, video_path):
        """Extract audio using ffmpeg."""
        print(f"[video player] Attempting to extract audio from: {video_path}")
        if not os.path.exists(video_path):
             print(f"[video player] Error: Video file not found: {video_path}")
             return None
        if not self.ffmpeg_path or not os.path.exists(self.ffmpeg_path):
            print("[video player] Error: ffmpeg path not configured or invalid.")
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

        try:
             if not os.path.exists(self.temp_dir):
                 os.makedirs(self.temp_dir)
                 print(f"[video player] Created temp directory: {self.temp_dir}")
        except OSError as dir_err:
             print(f"[video player] Error creating temp directory {self.temp_dir}: {dir_err}")
             return None

        try:
             safe_basename = "".join(c if c.isalnum() else "_" for c in os.path.basename(video_path))
             temp_audio = os.path.join(self.temp_dir, f"audio_{safe_basename}_{int(time.time()*1000)}.wav")
        except Exception as temp_err:
             print(f"[video player] Error creating temp file path: {temp_err}")
             return None

        print(f"[video player] Extracting audio to: {temp_audio}")
        command = [
            self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            "-y",
            temp_audio,
        ]

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(command, capture_output=True, text=True, check=False, startupinfo=startupinfo, encoding='utf-8', errors='ignore')

            if result.returncode != 0:
                print(f"[video player] ffmpeg error (code {result.returncode}): {result.stderr}")
                self._safe_remove(temp_audio)
                return None
            else:
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024:
                    print("[video player] Audio extraction successful.")
                    self._cleanup_resources() # Clean up previous audio
                    self.current_audio_path = temp_audio
                    return temp_audio
                else:
                     print(f"[video player] Error: Temp audio file missing, empty, or too small after ffmpeg success: {temp_audio}")
                     self._safe_remove(temp_audio)
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
            self.stop_video(wait=True)
            print("[video player] Previous video stopped.")
            time.sleep(0.1)

        # --- Reset State ---
        self.should_stop = False
        self.playback_complete = False
        self.needs_resizing = False
        self.source_width = 0
        self.source_height = 0
        # Reset frame rate/time here, reader will update them
        self.frame_rate = 30.0
        self.frame_time = 1.0 / self.frame_rate
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)

        # --- Set Callbacks ---
        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        # --- Set Playing Flag ---
        self.is_playing = True

        # --- Start Threads ---
        self.video_reader_thread = threading.Thread(
            target=self._reader_thread_func,
            args=(video_path,),
            daemon=True,
            name=f"VideoReader-{os.path.basename(video_path)}"
        )
        self.video_player_thread = threading.Thread(
            target=self._player_thread_func,
            args=(audio_path,),
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
             return

        if not self.is_playing and not self.should_stop:
             print("[video player] stop_video called but not playing. Cleaning up resources just in case.")
             self._cleanup_resources()
             return

        # --- Signal Threads to Stop ---
        self.should_stop = True
        print("[video player] Stop signal sent to threads.")

        # --- Stop Audio Immediately ---
        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()
            time.sleep(0.05)

        # --- Unblock Queue ---
        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False)
            except queue.Full:
                 print("[video player] Warning: Queue full when trying to clear/put None during stop.")
            except Exception as e:
                 print(f"[video player] Error interacting with queue during stop: {e}")

        # --- Wait for Threads to Join ---
        if wait:
            join_timeout = 2.0
            print(f"[video player] Waiting for threads to join (timeout {join_timeout}s)...")
            start_join = time.monotonic()
            reader_alive = self.video_reader_thread and self.video_reader_thread.is_alive()
            player_alive = self.video_player_thread and self.video_player_thread.is_alive()

            if reader_alive:
                self.video_reader_thread.join(timeout=max(0.1, join_timeout - (time.monotonic() - start_join)))
                if self.video_reader_thread.is_alive():
                     print("[video player] Warning: Reader thread did not exit cleanly after stop request.")

            if player_alive:
                 self.video_player_thread.join(timeout=max(0.1, join_timeout - (time.monotonic() - start_join)))
                 if self.video_player_thread.is_alive():
                      print("[video player] Warning: Player thread did not exit cleanly after stop request.")

            # Force state if threads didn't exit cleanly after wait
            self.is_playing = False
            print("[video player] Thread join finished.")
        else:
            # If not waiting, we assume the threads will stop eventually,
            # but don't update is_playing here - the player thread should do that.
            pass

        print("[video player] stop_video finished signaling.")


    def force_stop(self):
        """Force stop playback immediately, cleanup resources NOW."""
        print("[video player] Force stopping playback.")
        self.should_stop = True
        self.is_playing = False

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            print("[video player] Force stopped audio channel.")
            time.sleep(0.05)

        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False)
            except Exception: pass

        join_timeout = 0.2
        if self.video_reader_thread and self.video_reader_thread.is_alive():
             self.video_reader_thread.join(timeout=join_timeout)
        if self.video_player_thread and self.video_player_thread.is_alive():
             self.video_player_thread.join(timeout=join_timeout)

        self._cleanup_resources()
        self.reset_state()
        print("[video player] Force stop complete.")

    def reset_state(self):
        """Reset state variables, typically after a force_stop or for reuse."""
        print("[video player] Resetting internal state.")
        self.should_stop = False
        self.is_playing = False
        self.playback_complete = True
        self.video_reader_thread = None
        self.video_player_thread = None
        self.frame_queue = None
        self.on_complete_callback = None
        self.frame_update_callback = None
        self.needs_resizing = False
        self.source_width = 0
        self.source_height = 0
        # Reset frame rate/time to default
        self.frame_rate = 30.0
        self.frame_time = 1.0 / self.frame_rate

    def _safe_remove(self, filepath):
        """Attempts to remove a file, ignoring errors if it doesn't exist."""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError as e:
                print(f"[video player] Warning: Could not remove file {filepath}: {e}")
            except Exception as e:
                 print(f"[video player] Error removing file {filepath}: {e}")

    def _cleanup_resources(self):
        """Clean up temporary audio files."""
        audio_to_remove = self.current_audio_path
        self.current_audio_path = None
        self._safe_remove(audio_to_remove)

    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            if self.is_playing:
                 print("[video player] Destructor: Signaling stop for active playback...")
                 self.stop_video(wait=False) # Signal stop, don't block destructor

            self._cleanup_resources()

            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
                print(f"[video player] Destructor: Cleaning up temporary directory: {temp_dir_to_remove}")
                import shutil
                shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                # print(f"[video player] Destructor: Removed temporary directory (ignore_errors=True).") # Reduce noise

        except Exception as e:
             print(f"[video player] Error during __del__: {e}")
        finally:
             self.temp_dir = None # Avoid trying to delete again if __del__ runs twice somehow