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
    # Timeout for waiting for the reader to produce a frame.
    # If the reader is stalled for longer than this, playback aborts.
    # 5 frame times seems reasonable.
    READER_FRAME_TIMEOUT_FACTOR = 5.0
    # Small epsilon for time.sleep() to avoid sleeping for zero or negative time
    SLEEP_EPSILON = 0.0005


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
            cap = cv2.VideoCapture(video_path) # Stick to default if unsure

            if not cap.isOpened():
                print(f"[video player] CRITICAL: Failed to open video in reader thread: {video_path}")
                if self.frame_queue:
                    try: self.frame_queue.put(None, timeout=0.5)
                    except queue.Full: pass
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
                # Add a small epsilon to prevent potential division by zero or overly large frame times
                self.frame_rate = float(_fps) + 1e-6
            self.frame_time = 1.0 / self.frame_rate

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
                    print("[video player] Reader: End of video stream reached.")
                    break # Exit loop naturally

                # --- Process Frame (Resizing if needed) ---
                if self.needs_resizing:
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    processed_frame = frame # Use frame directly (it's BGR)

                # --- Put Frame in Queue ---
                try:
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0) # Wait up to 1 sec if full
                    processed_frame_count += 1
                except queue.Full:
                    print("[video player] Reader: Frame queue full. Player might be lagging or stopped.")
                    if self.should_stop: # Check stop flag if queue is full
                        break
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
            if self.frame_queue:
                 try:
                     self.frame_queue.put(None, block=False) # Non-blocking put sentinel
                     print("[video player] Reader: Put None sentinel in queue.")
                 except queue.Full:
                      print("[video player] Reader: Queue full when trying to put None sentinel.")
                 except Exception as e:
                     print(f"[video player] Reader: Error putting None sentinel: {e}")

            if not read_successful:
                print("[video player] Reader: Setting playback_complete=True as video never opened.")
                self.playback_complete = True
                self.is_playing = False

            print("[video player] Reader thread finished.")


    def _player_thread_func(self, audio_path):
        """
        Takes frames from the queue, handles timing/sync, plays audio,
        and calls the frame update callback.
        Starts audio and timing together for better sync.
        Pauses playback if the reader lags.
        """
        print("[video player] Player thread starting.")
        playback_start_perf_counter = -1.0 # Timer base for frame sync
        audio_started = False
        got_first_frame = False
        processed_frame_count = 0 # How many frames actually sent to callback

        try:
            # --- Wait for the first frame ---
            # This ensures the reader has initialized and determined frame rate etc.
            print("[video player] Player: Waiting for first frame from reader...")
            first_frame = self.frame_queue.get(block=True, timeout=10.0) # Wait up to 10s
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                # Ensure state reflects failure before finally block
                self.is_playing = False
                self.playback_complete = True
                return # Exit thread

            print(f"[video player] Player: Received first frame. Frame Time: {self.frame_time:.4f}s")
            got_first_frame = True

            # --- Prepare Audio (Load but don't play yet) ---
            audio_sound = None
            if audio_path and os.path.exists(audio_path):
                try:
                    if not mixer.get_init(): mixer.init(frequency=44100)
                    audio_sound = mixer.Sound(audio_path)
                    print("[video player] Player: Audio loaded successfully.")
                except Exception as e:
                    print(f"[video player] Player: Error loading audio: {e}")
                    traceback.print_exc()
                    # Continue without audio
            else:
                print("[video player] Player: No valid audio path or file missing.")

            # --- Initialize Loop Variables ---
            current_frame_to_display = first_frame
            frame_index = 0 # Index of the frame we are about to display/process

            print("[video player] Player: Entering playback loop.")
            while True: # Loop invariant: current_frame_to_display holds the frame for this iteration
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Start Audio and Timer (ONCE, before first frame calculations) ---
                if frame_index == 0:
                    print("[video player] Player: Starting audio and timer for frame 0.")
                    playback_start_perf_counter = time.perf_counter() # Start timer FIRST
                    if audio_sound:
                        self.video_sound_channel.play(audio_sound) # Start audio immediately after
                        audio_started = True
                        print("[video player] Player: Started audio playback.")
                    else:
                        print("[video player] Player: No audio to play.")

                    # Check if timer started correctly
                    if playback_start_perf_counter < 0:
                        print("[video player] Player: CRITICAL - Failed to start timer.")
                        self.should_stop = True; break

                # --- Calculate display time for CURRENT frame and wait ---
                expected_display_time = playback_start_perf_counter + frame_index * self.frame_time
                current_time = time.perf_counter()
                time_to_wait = expected_display_time - current_time

                if time_to_wait > self.SLEEP_EPSILON:
                    time.sleep(time_to_wait)
                # else: We are on time or late, display immediately.

                # --- Double-check stop signal AFTER sleeping ---
                if self.should_stop:
                    print("[video player] Player: Stop flag detected after sleep. Breaking loop.")
                    break

                # --- Process/Display Current Frame ---
                if current_frame_to_display is not None:
                    try:
                        if self.frame_update_callback:
                            self.frame_update_callback(current_frame_to_display)
                            processed_frame_count += 1
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True; break # Stop if we can't display
                    except Exception as frame_err:
                        print(f"[video player] Player: Error processing/sending frame {frame_index}: {frame_err}")
                        # Option: Stop if callback fails repeatedly?
                        # self.should_stop = True; break
                else:
                    # Should not happen normally due to checks, but handle defensively
                    print(f"[video player] Player: Error - current_frame_to_display is None for index {frame_index}.")
                    break # Exit loop

                # --- Get the NEXT frame for the *next* iteration ---
                next_frame_index = frame_index + 1
                next_frame = None
                try:
                    # Block-wait for the next frame. Pauses playback if reader lags.
                    get_timeout = self.frame_time * self.READER_FRAME_TIMEOUT_FACTOR
                    next_frame = self.frame_queue.get(block=True, timeout=get_timeout)

                except queue.Empty:
                    # Reader failed to produce the frame within the timeout.
                    print(f"[video player] Player: Timeout ({get_timeout:.2f}s) waiting for frame {next_frame_index}. Reader thread might be stalled or finished unexpectedly.")
                    # Check if the reader thread is still alive
                    reader_alive = self.video_reader_thread and self.video_reader_thread.is_alive()
                    if not reader_alive:
                        print("[video player] Player: Reader thread is not alive.")
                        # Check queue again non-blocking for a potential late sentinel
                        try:
                            final_item = self.frame_queue.get_nowait()
                            if final_item is None:
                                print("[video player] Player: Found None sentinel after reader thread died.")
                                self.playback_complete = True
                                break # Normal exit path if sentinel found
                        except queue.Empty:
                            print("[video player] Player: No final sentinel found in queue.")
                        except Exception as qe:
                            print(f"[video player] Player: Error checking queue after reader death: {qe}")

                    # Whether reader is alive or not, timeout means playback cannot continue correctly
                    self.playback_complete = False # Indicate abnormal termination
                    self.should_stop = True # Ensure cleanup happens via finally block
                    break # Exit loop

                except Exception as q_err:
                    print(f"[video player] Player: Error getting frame {next_frame_index} from queue: {q_err}")
                    traceback.print_exc()
                    self.playback_complete = False
                    self.should_stop = True # Signal stop
                    break # Exit loop

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print(f"[video player] Player: Received None sentinel after displaying frame {frame_index}. End of stream.")
                    self.playback_complete = True # Normal completion
                    # Last valid frame (frame_index) was displayed in this iteration.
                    break # Exit loop

                # Prepare for next iteration
                current_frame_to_display = next_frame
                frame_index = next_frame_index # Move to the next index

            # --- Loop End ---
            print(f"[video player] Player: Exited playback loop after processing {processed_frame_count} frames.")

        except queue.Empty:
             # This handles the timeout waiting for the *first* frame
             print("[video player] Player: Timed out waiting for the first frame. Aborting.")
             self.is_playing = False # Ensure state reflects failure
             self.playback_complete = True # Treat as complete if couldn't start
        except Exception as e:
            print("[video player] CRITICAL: Error in player thread:")
            traceback.print_exc()
            self.playback_complete = False # Indicate abnormal termination
        finally:
            print(f"[video player] Player thread cleaning up... (Processed approx {processed_frame_count} frames)")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 # Ensure completion runs if we never started playing frames
                 self.playback_complete = True
                 if not self.is_playing: # If it was already set false by reader fail
                      pass # Keep it false
                 else: # If is_playing was true but we failed before loop
                      self.is_playing = False # Mark as not playing

            # Ensure audio stops if it was playing and the thread exits
            if audio_started and self.video_sound_channel.get_busy():
                print("[video player] Player: Stopping video audio channel in finally.")
                self.video_sound_channel.stop()
                # Give mixer a moment
                time.sleep(0.05)

            # --- Final State Update & Callback ---
            was_playing = self.is_playing # Store state before modifying
            self.is_playing = False # Mark as not playing *before* callback

            # If playback finished normally OR was stopped externally OR ended abnormally
            # *and* a callback is registered, call it.
            # Check 'was_playing' to avoid calling completion if play_video failed very early.
            # Check 'got_first_frame' as another guard against calling completion if player never really started.
            if (was_playing or got_first_frame) and self.on_complete_callback:
                 if self.playback_complete:
                     print("[video player] Player: Triggering on_complete_callback (Normal Completion or Stop).")
                 else:
                     print("[video player] Player: Triggering on_complete_callback (Abnormal Termination/Error).")

                 try:
                      self.on_complete_callback()
                 except Exception as cb_err:
                      print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
            elif not (was_playing or got_first_frame):
                 print("[video player] Player: Playback did not effectively start, skipping final on_complete_callback.")


            print("[video player] Player thread finished.")


    # --- extract_audio: Remains largely the same ---
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
            self.stop_video(wait=True) # Wait for previous stop to complete
            print("[video player] Previous video stopped.")
            time.sleep(0.1) # Brief pause after stop

        # --- Reset State ---
        self.should_stop = False
        self.playback_complete = False # Reset completion status
        self.needs_resizing = False
        self.source_width = 0
        self.source_height = 0
        # Ensure previous queue is discarded and a new one is created
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)

        # --- Set Callbacks ---
        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        # --- Set Playing Flag (Crucial: Before starting threads) ---
        # This indicates the *intent* to play. The player thread sets it False on exit.
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
        print(f"[video player] stop_video called (wait={wait}). is_playing={self.is_playing}, should_stop={self.should_stop}")

        # If already stopped or in the process of stopping, just return
        if self.should_stop:
            # print("[video player] Already stopping/stopped.")
             # If wait is requested, still wait for threads even if stop was already signaled
             if wait:
                 self._wait_for_threads(2.0)
             return

        if not self.is_playing:
             # Was not playing and stop wasn't signaled before.
             print("[video player] stop_video called but not playing and not stopping. Cleaning up resources just in case.")
             self._cleanup_resources()
             # Reset stop flag in case it was leftover from a previous failed stop
             self.should_stop = False
             return

        # --- Signal Threads to Stop ---
        self.should_stop = True
        # is_playing will be set to False by the player thread itself upon exit

        print("[video player] Stop signal sent to threads.")

        # --- Stop Audio Immediately ---
        # Player thread also stops audio in its finally block, but doing it here
        # gives a faster response to the stop command.
        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel immediately.")
            self.video_sound_channel.stop()
            time.sleep(0.05) # Give mixer a moment

        # --- Unblock Queue ---
        # Help threads exit faster if blocked on queue operations.
        if self.frame_queue:
            try:
                # Clear the queue to potentially unblock reader faster if queue was full
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                # Put sentinel to ensure player thread unblocks from get()
                self.frame_queue.put(None, block=False)
                print("[video player] Cleared queue and put None sentinel during stop.")
            except queue.Full:
                 print("[video player] Warning: Queue full when trying to clear/put None during stop.")
            except Exception as e:
                 print(f"[video player] Error interacting with queue during stop: {e}")

        # --- Wait for Threads to Join (if requested) ---
        if wait:
            self._wait_for_threads(2.0) # Use helper for waiting

        # Final state should be handled by player thread's finally block

        print("[video player] stop_video finished signaling.")

    def _wait_for_threads(self, join_timeout):
        """Helper function to wait for reader and player threads."""
        print(f"[video player] Waiting for threads to join (timeout {join_timeout}s)...")
        start_wait = time.perf_counter()
        reader_waited = False
        player_waited = False

        if self.video_reader_thread and self.video_reader_thread.is_alive():
             reader_timeout = join_timeout / 2 # Split timeout
             self.video_reader_thread.join(timeout=reader_timeout)
             reader_waited = True
             if self.video_reader_thread.is_alive():
                  print("[video player] Warning: Reader thread still alive after join timeout.")

        remaining_timeout = join_timeout - (time.perf_counter() - start_wait)
        if self.video_player_thread and self.video_player_thread.is_alive():
             player_timeout = max(0.1, remaining_timeout) # Ensure some positive timeout
             self.video_player_thread.join(timeout=player_timeout)
             player_waited = True
             if self.video_player_thread.is_alive():
                   print("[video player] Warning: Player thread still alive after join timeout.")

        # Final check after waiting
        # Force state if threads didn't exit cleanly or player didn't set it
        if self.is_playing and (player_waited and not (self.video_player_thread and self.video_player_thread.is_alive())):
             # If we waited for player and it exited, but is_playing is still true
             print("[video player] Forcing is_playing=False after waiting for threads.")
             self.is_playing = False
        elif not reader_waited and not player_waited:
             print("[video player] No threads were active to wait for.")
        else:
             print("[video player] Thread join attempt finished.")


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
        self._wait_for_threads(0.2) # Use helper with short timeout

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
        self.current_audio_path = None # Clear audio path


    def _safe_remove(self, filepath):
        """Attempts to remove a file, ignoring errors if it doesn't exist."""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                # print(f"[video player] Removed file: {filepath}") # Debug noise
            except OSError as e:
                # Common issue on Windows if file is still in use (e.g., mixer hasn't released it)
                print(f"[video player] Warning: Could not remove file {filepath}: {e}. Will likely be cleaned up later or on exit.")
            except Exception as e:
                 print(f"[video player] Error removing file {filepath}: {e}")

    def _cleanup_resources(self):
        """Clean up temporary audio files."""
        # print("[video player] Cleaning up resources...") # Reduce noise
        audio_to_remove = self.current_audio_path
        self.current_audio_path = None # Clear path immediately

        if audio_to_remove:
             # Give mixer a tiny bit more time before trying to delete
             time.sleep(0.1)
             self._safe_remove(audio_to_remove)


    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            # Ensure playback is stopped (use non-waiting stop)
            if self.is_playing or self.should_stop:
                 print("[video player] Destructor: Stopping active/pending playback...")
                 # Use force_stop here? Or a non-waiting stop?
                 # Non-waiting stop is safer in __del__
                 self.stop_video(wait=False) # Signal stop, don't block destructor

            # Cleanup any lingering temp audio
            self._cleanup_resources()

            # Remove the temporary directory
            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
                print(f"[video player] Destructor: Attempting to clean up temporary directory: {temp_dir_to_remove}")
                import shutil
                # Use ignore_errors=True as files might still be locked briefly,
                # especially the audio file if mixer didn't release it.
                shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                # Check again if it was removed
                if not os.path.isdir(temp_dir_to_remove):
                    print(f"[video player] Destructor: Removed temporary directory.")
                else:
                    print(f"[video player] Destructor: Failed to remove temporary directory (ignore_errors=True). Might contain locked files.")

        except Exception as e:
             # Catch errors during __del__ as they can be problematic
             print(f"[video player] Error during __del__: {e}")
        finally:
             # Ensure base class __del__ is called if necessary (though not needed here)
             # super().__del__()
             pass
        self.temp_dir = None