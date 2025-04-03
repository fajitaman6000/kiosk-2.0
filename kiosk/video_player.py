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
import queue
import shutil # Added for directory cleanup in __del__

try:
    import pyautogui # For screen size detection
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[video player] Warning: pyautogui not found. Screen size detection unavailable, assuming 1920x1080.")


class VideoPlayer:
    # --- Constants ---
    FRAME_QUEUE_SIZE = 30 # Number of frames to buffer ahead
    # Timeout for waiting on audio extraction within the player thread
    AUDIO_EXTRACTION_TIMEOUT_S = 15.0

    def __init__(self, ffmpeg_path):
        print("[video player] Initializing VideoPlayer (Optimized)")
        self.ffmpeg_path = ffmpeg_path
        self.is_playing = False
        self.should_stop = False # Flag to signal threads to stop
        self.playback_complete = True # Indicates if the last playback finished normally

        self.video_sound_channel = mixer.Channel(0)
        # self.current_audio_path = None # Replaced by extracted_audio_path_internal
        self.temp_dir = tempfile.mkdtemp(prefix="vidplayer_")

        self.frame_rate = 30.0
        self.frame_time = 1.0 / self.frame_rate

        # Threading and Queue
        self.video_reader_thread = None
        self.video_player_thread = None
        self.audio_extraction_thread = None # <<< NEW: Thread for audio extraction
        self.frame_queue = None

        # Synchronization for Audio Extraction
        self.audio_ready_event = threading.Event() # <<< NEW: Signals audio is ready/failed
        self.extracted_audio_path_internal = None # <<< NEW: Stores the path from the audio thread

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
            # --- Open Video Capture ---
            # Add a small delay *before* opening, allowing other threads (like audio)
            # a chance to start potentially overlapping disk I/O slightly.
            # time.sleep(0.05) # Experiment: Small delay before opening
            cap = cv2.VideoCapture(video_path) # Stick to default

            if not cap.isOpened():
                print(f"[video player] CRITICAL: Failed to open video in reader thread: {video_path}")
                self.should_stop = True # Signal other threads
                if self.frame_queue:
                    try: self.frame_queue.put(None, timeout=0.5)
                    except queue.Full: pass
                return # Exit thread

            read_successful = True # Mark that cap was opened
            print("[video player] Reader: Video capture opened successfully.")

            # --- Get Video Properties ---
            self.source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            _fps = cap.get(cv2.CAP_PROP_FPS)

            if _fps is None or not (0.1 < _fps < 121.0):
                print(f"[video player] Warning: Invalid/unreliable FPS ({_fps}) from video. Using default 30.")
                self.frame_rate = 30.0
            else:
                self.frame_rate = float(_fps)
            self.frame_time = 1.0 / self.frame_rate

            print(f"[video player] Video properties: {self.source_width}x{self.source_height} @ {self.frame_rate:.2f} FPS (Frame Time: {self.frame_time:.4f}s)")

            # --- Determine if resizing is needed ---
            self.needs_resizing = not (self.source_width == self.target_width and self.source_height == self.target_height)
            resize_interpolation = cv2.INTER_LINEAR if self.needs_resizing else None
            if self.needs_resizing:
                print(f"[video player] Resizing needed: Source {self.source_width}x{self.source_height} -> Target {self.target_width}x{self.target_height}")
            else:
                 print("[video player] No resizing needed.")


            # --- Frame Reading Loop ---
            while not self.should_stop:
                ret, frame = cap.read()

                if not ret:
                    print("[video player] Reader: End of video stream reached.")
                    break # Exit loop naturally

                # --- Process Frame ---
                if self.needs_resizing:
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    processed_frame = frame # Use BGR frame directly

                # --- Put Frame in Queue ---
                try:
                    # Send BGR frame
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0)
                    processed_frame_count += 1
                except queue.Full:
                    print("[video player] Reader: Frame queue full. Player might be lagging or stopped.")
                    if self.should_stop: break # Exit if stop requested while queue full
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

    def _player_thread_func(self): # <<< Removed audio_path argument
        """
        Takes frames from the queue, handles timing/sync, plays audio (after extraction),
        and calls the frame update callback.
        """
        print("[video player] Player thread starting.")
        frame_count = 0
        playback_start_perf_counter = -1.0
        audio_started = False
        got_first_frame = False
        video_sound = None # Keep reference to prevent garbage collection

        try:
            # --- Wait for the first frame ---
            print("[video player] Player: Waiting for first frame from reader...")
            # Increased timeout slightly, reader might need a moment
            first_frame = self.frame_queue.get(block=True, timeout=12.0)
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                self.is_playing = False
                self.playback_complete = True
                return # Exit thread early

            print(f"[video player] Player: Received first frame. Frame Time: {self.frame_time:.4f}s")
            got_first_frame = True

            # --- Wait for Audio Extraction (Happens Concurrently) --- # <<< NEW
            print("[video player] Player: Waiting for audio extraction...")
            audio_ready = self.audio_ready_event.wait(timeout=self.AUDIO_EXTRACTION_TIMEOUT_S)

            # --- Audio Playback (If Ready) --- # <<< MODIFIED
            local_audio_path = self.extracted_audio_path_internal # Get path set by audio thread
            if audio_ready and local_audio_path and os.path.exists(local_audio_path):
                print(f"[video player] Player: Audio ready. Path: {local_audio_path}")
                try:
                    # Ensure mixer is initialized (safe to call multiple times)
                    if not mixer.get_init(): mixer.init(frequency=44100)
                    video_sound = mixer.Sound(local_audio_path)
                    self.video_sound_channel.play(video_sound)
                    audio_started = True
                    print("[video player] Player: Started audio playback.")
                except Exception as e:
                    print(f"[video player] Player: Error starting extracted audio: {e}")
                    traceback.print_exc()
                    # Continue without audio
            elif not audio_ready:
                print(f"[video player] Player: Timed out waiting {self.AUDIO_EXTRACTION_TIMEOUT_S}s for audio extraction. Continuing without audio.")
            else: # audio_ready is true but path is None or file missing
                print("[video player] Player: Audio extraction finished but failed or file missing. Continuing without audio.")

            # --- Start Playback Timing (AFTER potential audio wait) ---
            playback_start_perf_counter = time.perf_counter()
            print("[video player] Player: Starting playback loop.")

            # --- Playback Loop ---
            current_frame = first_frame
            while True: # Loop until sentinel or stop signal
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Process Current Frame ---
                if current_frame is not None:
                    try:
                        if self.frame_update_callback:
                            # Frame is BGR numpy array
                            self.frame_update_callback(current_frame)
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True
                        frame_count += 1
                    except Exception as frame_err:
                         print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")
                         # Optionally stop if callback fails repeatedly: self.should_stop = True

                # --- Timing Calculation ---
                current_time = time.perf_counter()
                expected_display_time = playback_start_perf_counter + frame_count * self.frame_time
                time_until_next_frame = expected_display_time - current_time

                # --- Get Next Frame (or wait) ---
                next_frame = None
                try:
                    if time_until_next_frame > 0.002: # If we have time, sleep then get
                        sleep_duration = max(0, time_until_next_frame - 0.002)
                        time.sleep(sleep_duration)
                        # Try get with shorter timeout now that we've waited
                        next_frame = self.frame_queue.get(block=True, timeout=max(0.001, self.frame_time * 0.6))
                    else: # On time or behind, try non-blocking first
                        next_frame = self.frame_queue.get(block=False)

                except queue.Empty:
                     # Queue empty - reader is lagging or finished
                     # print(f"[video player] Player: Frame queue empty (lag: {-time_until_next_frame:.3f}s). Waiting...")
                     try:
                         # Block with longer timeout, waiting for reader
                         next_frame = self.frame_queue.get(block=True, timeout=self.frame_time * 2.5)
                     except queue.Empty:
                          print("[video player] Player: Timed out waiting for frame after lag. Reader may be stuck/slow.")
                          # If still empty, check if stop is requested, otherwise keep trying
                          if self.should_stop: break
                          continue # Go back to start of loop and try get again
                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame from queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print("[video player] Player: Received None sentinel. End of stream.")
                    self.playback_complete = True # Normal completion
                    break # Exit loop

                current_frame = next_frame
                # Frame skipping logic could be added here if needed

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

            # Stop audio if it was playing
            if audio_started and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                time.sleep(0.05)
            video_sound = None # Release reference

            # --- Final State Update & Callback ---
            was_playing = self.is_playing
            self.is_playing = False # Mark as not playing *before* callback

            # Call completion callback if registered and playback actually started/attempted
            if was_playing and self.on_complete_callback:
                 completion_status = "Normal Completion or Stop" if self.playback_complete else "Abnormal Termination"
                 print(f"[video player] Player: Triggering on_complete_callback ({completion_status}).")
                 try:
                      self.on_complete_callback()
                 except Exception as cb_err:
                      print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
            elif not was_playing:
                 print("[video player] Player: Playback did not start or was already stopped, skipping final on_complete_callback.")

            print("[video player] Player thread finished.")

    # --- NEW: Audio extraction runs in its own thread ---
    def _extract_audio_thread_func(self, video_path):
        """Target function for the audio extraction thread."""
        print(f"[video player] Audio extraction thread starting for: {video_path}")
        extracted_path = None
        try:
            # === Start of original extract_audio logic ===
            if not os.path.exists(video_path):
                 print(f"[video player] AudioThread: Video file not found: {video_path}")
                 return # Signal failure via event below

            _ffmpeg_path = self.ffmpeg_path
            if not _ffmpeg_path or not os.path.exists(_ffmpeg_path):
                print("[video player] AudioThread: ffmpeg path not configured or invalid. Trying fallback...")
                try:
                    _ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
                    if not (_ffmpeg_path and os.path.exists(_ffmpeg_path)):
                        print("[video player] AudioThread: Fallback: imageio_ffmpeg could not find ffmpeg.")
                        _ffmpeg_path = None # Ensure it's None if not found
                except Exception as ff_find_err:
                     print(f"[video player] AudioThread: Error trying to find ffmpeg via imageio_ffmpeg: {ff_find_err}")
                     _ffmpeg_path = None

            if not _ffmpeg_path:
                print("[video player] AudioThread: No valid ffmpeg path found. Cannot extract audio.")
                return # Signal failure

            # Ensure temp dir exists
            try:
                 if not os.path.exists(self.temp_dir): os.makedirs(self.temp_dir)
            except OSError as dir_err:
                 print(f"[video player] AudioThread: Error creating temp directory {self.temp_dir}: {dir_err}")
                 return # Signal failure

            # Generate temp file path
            try:
                 safe_basename = "".join(c if c.isalnum() else "_" for c in os.path.basename(video_path))
                 temp_audio = os.path.join(self.temp_dir, f"audio_{safe_basename}_{int(time.time()*1000)}.wav")
            except Exception as temp_err:
                 print(f"[video player] AudioThread: Error creating temp file path: {temp_err}")
                 return # Signal failure

            print(f"[video player] AudioThread: Extracting audio to: {temp_audio}")
            command = [
                _ffmpeg_path, "-hide_banner", "-loglevel", "error",
                "-i", video_path,
                "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                "-y", temp_audio,
            ]

            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            # --- Run ffmpeg ---
            result = subprocess.run(command, capture_output=True, text=True, check=False, startupinfo=startupinfo, encoding='utf-8', errors='ignore')

            if result.returncode != 0:
                print(f"[video player] AudioThread: ffmpeg error (code {result.returncode}): {result.stderr}")
                self._safe_remove(temp_audio)
                # Do not set extracted_path
            else:
                # Check file existence and size
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024:
                    print("[video player] AudioThread: Audio extraction successful.")
                    extracted_path = temp_audio # Success!
                else:
                     print(f"[video player] AudioThread: Error: Temp audio file missing/empty/small after ffmpeg success: {temp_audio}")
                     self._safe_remove(temp_audio)
                     # Do not set extracted_path
            # === End of original extract_audio logic ===

        except FileNotFoundError:
             print(f"[video player] AudioThread: Error: ffmpeg executable not found at '{_ffmpeg_path}'.")
        except Exception as e:
            print(f"[video player] AudioThread: Audio extraction error: {e}")
            traceback.print_exc()
            # Ensure temp file is removed on error if it exists
            if 'temp_audio' in locals() and os.path.exists(temp_audio):
                 self._safe_remove(temp_audio)
        finally:
            # Store the result (path or None) and signal the player thread
            self.extracted_audio_path_internal = extracted_path
            print(f"[video player] Audio extraction thread finished. Result path: {self.extracted_audio_path_internal}. Signaling event.")
            self.audio_ready_event.set() # Signal completion (success or failure)


    def play_video(self, video_path, frame_update_cb, on_complete_cb): # <<< Removed audio_path argument
        """Start video playback using reader, player, and audio extraction threads."""
        print(f"[video player] play_video called for: {video_path}")

        if self.is_playing:
            print("[video player] Warning: Already playing, stopping previous video first...")
            self.stop_video(wait=True) # Wait for previous stop to complete
            print("[video player] Previous video stopped.")
            time.sleep(0.1) # Brief pause

        # --- Reset State ---
        self.should_stop = False
        self.playback_complete = False
        self.needs_resizing = False
        self.source_width = 0
        self.source_height = 0
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)
        self.audio_ready_event.clear() # <<< Reset event
        self.extracted_audio_path_internal = None # <<< Reset path
        self._cleanup_resources() # Clean any *old* audio file before starting new

        # --- Set Callbacks ---
        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        # --- Set Playing Flag (Before starting threads) ---
        self.is_playing = True

        # --- Start Threads ---
        # 1. Audio Extraction Thread (Starts first, runs concurrently)
        self.audio_extraction_thread = threading.Thread(
            target=self._extract_audio_thread_func,
            args=(video_path,),
            daemon=True,
            name=f"AudioExtractor-{os.path.basename(video_path)}"
        )
        print("[video player] Starting audio extraction thread...")
        self.audio_extraction_thread.start()

        # 2. Video Reader Thread
        self.video_reader_thread = threading.Thread(
            target=self._reader_thread_func,
            args=(video_path,),
            daemon=True,
            name=f"VideoReader-{os.path.basename(video_path)}"
        )
        print("[video player] Starting reader thread...")
        self.video_reader_thread.start()

        # 3. Video Player Thread
        self.video_player_thread = threading.Thread(
            target=self._player_thread_func,
            # No arguments needed now for audio path
            daemon=True,
            name=f"VideoPlayer-{os.path.basename(video_path)}"
        )
        print("[video player] Starting player thread...")
        self.video_player_thread.start()

        print("[video player] Playback initiated (audio extraction running concurrently).")


    def stop_video(self, wait=False):
        """Stop video playback gracefully."""
        print(f"[video player] stop_video called (wait={wait}). is_playing={self.is_playing}")

        if not self.is_playing and self.should_stop:
             # print("[video player] Already stopping/stopped.") # Reduce noise
             # Still wait if requested, even if already stopping
             if wait: self._wait_for_threads(2.0)
             return

        if not self.is_playing and not self.should_stop:
             print("[video player] stop_video called but not playing. Cleaning up resources just in case.")
             self._cleanup_resources()
             # Reset threads just in case they are dead but references exist
             self.video_reader_thread = None
             self.video_player_thread = None
             self.audio_extraction_thread = None
             return

        # --- Signal Threads to Stop ---
        self.should_stop = True
        # is_playing will be set to False by the player thread's finally block

        print("[video player] Stop signal sent to threads.")

        # --- Stop Audio Immediately ---
        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()
            time.sleep(0.05)

        # --- Signal Audio Event (to unblock player if waiting) ---
        self.audio_ready_event.set() # Signal immediately on stop

        # --- Unblock Frame Queue ---
        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False)
            except Exception as e:
                 print(f"[video player] Error interacting with frame queue during stop: {e}")

        # --- Wait for Threads (if requested) ---
        if wait:
            self._wait_for_threads(2.0) # Use helper for waiting

        # Resource cleanup happens via the player thread's finally block (for completion callback)
        # and _cleanup_resources() which should be called by the completion callback or __del__
        print("[video player] stop_video finished signaling.")

    def _wait_for_threads(self, timeout_s):
        """Helper function to join all active threads."""
        print(f"[video player] Waiting for threads to join (timeout {timeout_s}s)...")
        start_time = time.perf_counter()
        remaining_time = timeout_s

        # Join Order: Player -> Reader -> Audio (Player depends on Reader, Audio is independent)
        if self.video_player_thread and self.video_player_thread.is_alive():
             join_time = max(0.1, remaining_time * 0.4) # Allocate portion of time
             self.video_player_thread.join(timeout=join_time)
             remaining_time = timeout_s - (time.perf_counter() - start_time)
             if self.video_player_thread.is_alive():
                 print("[video player] Warning: Player thread did not exit cleanly after stop request.")

        if self.video_reader_thread and self.video_reader_thread.is_alive():
             join_time = max(0.1, remaining_time * 0.5)
             self.video_reader_thread.join(timeout=join_time)
             remaining_time = timeout_s - (time.perf_counter() - start_time)
             if self.video_reader_thread.is_alive():
                  print("[video player] Warning: Reader thread did not exit cleanly after stop request.")

        if self.audio_extraction_thread and self.audio_extraction_thread.is_alive():
             join_time = max(0.1, remaining_time) # Use remaining time
             self.audio_extraction_thread.join(timeout=join_time)
             if self.audio_extraction_thread.is_alive():
                  print("[video player] Warning: Audio extraction thread did not exit cleanly after stop request.")

        # Final state check after waiting
        self.is_playing = False # Force state if threads didn't exit cleanly
        # Clear thread references after join attempt
        self.video_reader_thread = None
        self.video_player_thread = None
        self.audio_extraction_thread = None
        print("[video player] Thread join finished.")


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

        # Signal event / Unblock queue
        self.audio_ready_event.set()
        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False)
            except Exception: pass # Ignore errors during force stop

        # Don't wait long for threads
        self._wait_for_threads(0.3) # Very short wait

        # Clean up resources immediately
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
        self.audio_extraction_thread = None
        self.frame_queue = None
        self.audio_ready_event.clear()
        self.extracted_audio_path_internal = None
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
                # print(f"[video player] Removed file: {filepath}") # Reduce debug noise
            except OSError as e:
                # Common issue on Windows if file is still technically in use
                print(f"[video player] Warning: Could not remove file {filepath} immediately: {e}. Will likely be cleaned with temp dir.")
            except Exception as e:
                 print(f"[video player] Error removing file {filepath}: {e}")

    def _cleanup_resources(self):
        """Clean up the currently tracked temporary audio file."""
        # print("[video player] Cleaning up resources...") # Reduce noise
        audio_to_remove = self.extracted_audio_path_internal
        self.extracted_audio_path_internal = None # Clear path immediately

        self._safe_remove(audio_to_remove)


    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            # Ensure playback is stopped (use non-waiting stop)
            if self.is_playing or self.should_stop: # Check if potentially active
                 print("[video player] Destructor: Stopping active/pending playback...")
                 # Use force_stop logic elements without waiting long
                 self.should_stop = True
                 self.is_playing = False
                 if self.video_sound_channel.get_busy(): self.video_sound_channel.stop()
                 self.audio_ready_event.set()
                 if self.frame_queue:
                     try: self.frame_queue.put(None, block=False)
                     except Exception: pass

                 # Give threads a *very* brief moment, don't block destructor long
                 time.sleep(0.1)


            # Cleanup any lingering temp audio file reference
            self._cleanup_resources()

            # Remove the temporary directory
            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
                print(f"[video player] Destructor: Attempting to clean up temporary directory: {temp_dir_to_remove}")
                # Use ignore_errors=True as files might still be locked briefly by threads
                # that didn't terminate instantly, especially on Windows.
                shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                print(f"[video player] Destructor: Removed temporary directory (ignore_errors=True).")
            self.temp_dir = None # Clear reference

        except Exception as e:
             # Catch errors during __del__ as they can be problematic
             print(f"[video player] Error during __del__: {e}")
             traceback.print_exc()