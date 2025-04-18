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

        # Target dimensions (screen size)
        self.target_width = 1920
        self.target_height = 1080
        self._update_target_dimensions() # Get screen size on init

        # State for resizing check
        self.source_width = 0
        self.source_height = 0
        self.needs_resizing = False # Will be True only if source > target

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
        Reads frames from video, resizes IF SOURCE IS LARGER than target,
        puts them in the queue.
        """
        print(f"[video player] Reader thread starting for: {video_path}")
        cap = None
        processed_frame_count = 0
        read_successful = False

        try:
            cap = cv2.VideoCapture(video_path) # Stick to default

            if not cap.isOpened():
                print(f"[video player] CRITICAL: Failed to open video in reader thread: {video_path}")
                if self.frame_queue:
                    try: self.frame_queue.put(None, timeout=0.5)
                    except queue.Full: pass
                return

            read_successful = True

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

            # --- Determine if resizing (downscaling) is needed ONCE ---
            # Resize *only* if the source dimensions are *larger* than the target dimensions.
            self.needs_resizing = (self.source_width > self.target_width or
                                   self.source_height > self.target_height)

            if self.needs_resizing:
                print(f"[video player] Downscaling needed: Source {self.source_width}x{self.source_height} -> Target {self.target_width}x{self.target_height}")
                # Using INTER_LINEAR is a balance between speed and quality for downscaling.
                resize_interpolation = cv2.INTER_LINEAR
            elif self.source_width == self.target_width and self.source_height == self.target_height:
                 print("[video player] No resizing needed (source matches target).")
            else:
                 # Source is smaller or equal in both dimensions (but not exact match)
                 print(f"[video player] No resizing needed (source {self.source_width}x{self.source_height} <= target {self.target_width}x{self.target_height}).")
                 # The frame_update_callback receiver will need to handle scaling if fullscreen display is desired.


            # --- Frame Reading Loop ---
            while not self.should_stop:
                ret, frame = cap.read()

                if not ret:
                    print("[video player] Reader: End of video stream reached.")
                    break

                # --- Process Frame (Downscaling if needed) ---
                if self.needs_resizing:
                    # Only resize (downscale) if source is larger than target
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    # Use frame directly (BGR) at its original resolution
                    processed_frame = frame

                # --- Convert to RGB ---
                # Assuming the display layer (Qt) prefers RGB format.
                try:
                    processed_frame_rgb = cv2.cvtColor(processed_frame, cv2.COLOR_BGR2RGB)
                except cv2.error as cvt_err:
                    print(f"[video player] Reader: Error converting frame to RGB: {cvt_err}. Sending BGR.")
                    processed_frame_rgb = processed_frame # Send original BGR if conversion fails

                # --- Put Frame in Queue ---
                try:
                    # Send the processed (or original) RGB frame
                    self.frame_queue.put(processed_frame_rgb, block=True, timeout=1.0)
                    processed_frame_count += 1
                except queue.Full:
                    print("[video player] Reader: Frame queue full. Player might be lagging or stopped.")
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
                self.playback_complete = True
                self.is_playing = False

            print("[video player] Reader thread finished.")


    def _player_thread_func(self, audio_path):
        """
        Takes frames from the queue, handles timing/sync, plays audio,
        and calls the frame update callback.
        NOTE: Frames received might be smaller than target dimensions and may
              need scaling by the callback receiver for fullscreen display.
        """
        print("[video player] Player thread starting.")
        frame_count = 0
        playback_start_perf_counter = -1.0 # Initialize later
        audio_started = False
        got_first_frame = False

        try:
            # --- Wait for the first frame ---
            print("[video player] Player: Waiting for first frame from reader...")
            first_frame = self.frame_queue.get(block=True, timeout=10.0)
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                self.is_playing = False
                self.playback_complete = True
                return

            print(f"[video player] Player: Received first frame (resolution: {first_frame.shape[1]}x{first_frame.shape[0]}). Frame Time: {self.frame_time:.4f}s")
            got_first_frame = True

            # --- Audio Playback ---
            if audio_path and os.path.exists(audio_path):
                try:
                    # Initialize mixer here to ensure it's ready before use
                    desired_freq = 44100
                    init_params = mixer.get_init() # Check current status

                    if not init_params:
                        print(f"[video player] Player: Initializing Pygame mixer (Freq: {desired_freq})...")
                        mixer.init(frequency=desired_freq) # Initialize if not already
                    elif init_params[0] != desired_freq: # Check frequency if already initialized
                        # init_params is a tuple (frequency, format, channels)
                        print(f"[video player] Player: Re-initializing Pygame mixer. Current freq: {init_params[0]}, Target: {desired_freq}")
                        mixer.quit()
                        mixer.init(frequency=desired_freq)
                    # else: # Already initialized with the correct frequency
                    #    print(f"[video player] Player: Mixer already initialized with correct frequency ({desired_freq}).")


                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    audio_started = True
                    print("[video player] Player: Started audio playback.")
                except Exception as e:
                    print(f"[video player] Player: Error starting or initializing audio: {e}")
                    traceback.print_exc()
                    # Decide if playback should continue without audio or stop
                    # For now, let it continue without audio if init fails
            else:
                print("[video player] Player: No valid audio path or file missing.")

            # --- Start Playback Timing ---
            playback_start_perf_counter = time.perf_counter()
            # Initialize the expected display time for the *first* frame
            expected_display_time = playback_start_perf_counter

            # --- Pre-Loop Checks ---
            # Check callback existence once before the loop
            callback_exists = self.frame_update_callback is not None
            if not callback_exists:
                print("[video player] Player: Error: frame_update_callback missing!")
                # Decide if playback should stop if callback is missing
                # self.should_stop = True # Optional: stop if callback essential

            # --- Playback Loop ---
            current_frame = first_frame
            while True: # Loop until sentinel or stop signal
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Process Current Frame ---
                if current_frame is not None:
                    try:
                        # Frame is RGB numpy array (potentially original size if < target)
                        if callback_exists:
                            # The callback function is responsible for any necessary
                            # display scaling if current_frame dimensions != screen dimensions
                            self.frame_update_callback(current_frame)
                        # No 'else' needed here because we checked existence before the loop
                        frame_count += 1
                    except Exception as frame_err:
                         # Check for the specific Qt object deleted error during shutdown
                         # This often happens if the main GUI closes while the thread is still sending frames
                         err_str = str(frame_err).lower()
                         if "c++ object" in err_str and "deleted" in err_str:
                             if not self.should_stop: # Only log if not already stopping
                                 print(f"[video player] Player: GUI object likely deleted during shutdown. Stopping. (Error: {frame_err})")
                             self.should_stop = True # Ensure loop terminates
                             break # Exit loop immediately
                         else:
                            print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")
                            # Decide if we should stop on other frame errors too
                            # self.should_stop = True


                # --- Timing Calculation ---
                # Increment expected time for the *next* frame BEFORE getting current time
                expected_display_time += self.frame_time
                current_time = time.perf_counter()
                time_until_next_frame = expected_display_time - current_time

                # --- Get Next Frame (or wait) ---
                next_frame = None
                try:
                    if time_until_next_frame > 0.002: # If we have time, wait
                        sleep_duration = max(0, time_until_next_frame - 0.002)
                        # Adjust sleep if queue is getting empty to prevent unnecessary waiting
                        # q_size = self.frame_queue.qsize()
                        # if q_size < 5 : sleep_duration *= 0.5 # Example heuristic

                        time.sleep(sleep_duration)
                        # Reduce timeout slightly if we slept, maybe half the remaining wait time
                        get_timeout = max(0.001, (time_until_next_frame - sleep_duration) * 1.5)
                        next_frame = self.frame_queue.get(block=True, timeout=min(get_timeout, self.frame_time * 0.8)) # Don't wait too long
                    else:
                        # On time or slightly behind, try non-blocking get first
                        try:
                            next_frame = self.frame_queue.get(block=False)
                        except queue.Empty:
                            # Queue empty when we expected a frame - reader is lagging
                            lag_time = -time_until_next_frame
                            # print(f"[video player] Player: Frame queue empty (lag: {lag_time:.3f}s). Waiting briefly...") # Can be noisy
                            # Block briefly - if reader is really stuck, we'll timeout later
                            try:
                                next_frame = self.frame_queue.get(block=True, timeout=self.frame_time * 1.5) # Wait a bit longer than one frame time
                            except queue.Empty:
                                print("[video player] Player: Timed out waiting for frame after lag. Reader may be stuck/slow.")
                                # Don't 'continue' here, let the loop timing naturally adjust
                                # or potentially receive the None sentinel next iteration.
                                # If we skip frames, timing gets worse. Let timing logic handle it.
                                pass # next_frame is still None, process below

                except queue.Empty:
                     # This catch is mainly for the timeout cases
                     #print(f"[video player] Player: Timed out waiting for next frame ({get_timeout:.3f}s).") # Can be noisy
                     pass # next_frame is still None, process below
                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame from queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error

                # --- Check for End Sentinel ---
                if next_frame is None and self.frame_queue.empty():
                    # Check if the reader thread is still alive; if so, it might just be slow
                    reader_alive = self.video_reader_thread and self.video_reader_thread.is_alive()
                    # Only consider it the end if we got None AND the reader isn't alive OR the queue remains empty for a bit
                    if not reader_alive:
                        print("[video player] Player: Received None sentinel or queue empty and reader dead. End of stream.")
                        self.playback_complete = True # Normal completion
                        break # Exit loop
                    else:
                        # Got None, but reader is alive, might be transient issue or real end sentinel
                        # Let's wait very briefly and check again
                        try:
                            next_frame = self.frame_queue.get(block=True, timeout=0.1)
                            if next_frame is None:
                                print("[video player] Player: Confirmed None sentinel. End of stream.")
                                self.playback_complete = True
                                break
                            # else: got a real frame, continue processing it
                        except queue.Empty:
                            print("[video player] Player: Queue still empty after brief wait, assuming end of stream.")
                            self.playback_complete = True
                            break


                # Prepare for next iteration
                # Only update current_frame if we actually got a new one
                if next_frame is not None:
                    current_frame = next_frame
                # If next_frame was None (due to timeout/lag), current_frame remains the same,
                # effectively displaying the previous frame again while waiting.

        except queue.Empty:
             print("[video player] Player: Timed out waiting for the first frame. Aborting.")
             self.is_playing = False
             self.playback_complete = True # Treat as completed (abnormally)
        except Exception as e:
            print("[video player] CRITICAL: Error in player thread:")
            traceback.print_exc()
            self.playback_complete = False # Mark as abnormal completion
        finally:
            print("[video player][PLAYER_FINALLY_1] Entering player thread finally block.")
            print(f"[video player] Player thread cleaning up... (Processed approx {frame_count} frames)")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 # Ensure state reflects this wasn't a normal completion if we expected playback
                 if not self.should_stop: # If stop wasn't explicitly called
                     self.playback_complete = False

            print("[video player][PLAYER_FINALLY_2] Checking audio channel.")
            if audio_started and self.video_sound_channel.get_busy():
                print("[video player][PLAYER_FINALLY_3] Audio channel busy, stopping...")
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                time.sleep(0.05) # Short pause to allow sound system to react
                print("[video player][PLAYER_FINALLY_4] Audio channel stopped.")
            else:
                print("[video player][PLAYER_FINALLY_3] Audio channel not busy or not started.")

            was_playing = self.is_playing # Capture state before setting false
            print(f"[video player] Player thread finishing. Player state: is_playing={was_playing}, should_stop={self.should_stop}, playback_complete={self.playback_complete}, got_first_frame={got_first_frame}") # DEBUG
            print("[video player][PLAYER_FINALLY_5] Setting self.is_playing = False.")
            self.is_playing = False # Mark as no longer playing *before* callback

            # Determine if completion callback should run
            # Run if playback started (got first frame) OR if stop was explicitly called
            should_run_callback = got_first_frame or self.should_stop
            print(f"[video player] Player thread cleanup: should_run_callback = {should_run_callback}") # DEBUG
            print("[video player][PLAYER_FINALLY_6] Determined should_run_callback.")

            if should_run_callback and self.on_complete_callback:
                print("[video player][PLAYER_FINALLY_7] Callback should run and exists.")
                if self.playback_complete and not self.should_stop:
                    print("[video player] Player: Triggering on_complete_callback (Normal Completion).")
                elif self.should_stop:
                    print("[video player] Player: Triggering on_complete_callback (Playback Stopped).")
                else: # playback_complete is False and not should_stop -> abnormal termination
                    print("[video player] Player: Triggering on_complete_callback (Abnormal Termination).")

                try:
                     print("[video player] Player: About to execute self.on_complete_callback()...") # DEBUG
                     print("[video player][PLAYER_FINALLY_8] Executing callback now.")
                     # Run callback in a separate thread to avoid blocking player cleanup?
                     # For simplicity now, run directly. If callbacks are long, consider threading.
                     self.on_complete_callback()
                     print("[video player] Player: Successfully executed self.on_complete_callback().") # DEBUG
                     print("[video player][PLAYER_FINALLY_9] Callback execution finished.")
                except Exception as cb_err:
                     print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
                     traceback.print_exc() # DEBUG: Print traceback for callback error
                     print("[video player][PLAYER_FINALLY_9_ERR] Callback execution failed.")
            elif not should_run_callback:
                 print("[video player] Player: Playback did not effectively start or stop wasn't called, skipping final on_complete_callback.")
                 print("[video player][PLAYER_FINALLY_7_SKIP] Skipping callback (not needed).")
            elif self.on_complete_callback is None:
                 print("[video player] Player: on_complete_callback is None, cannot trigger.") # DEBUG
                 print("[video player][PLAYER_FINALLY_7_NONE] Skipping callback (is None).")


            print("[video player] Player thread finished.")
            print("[video player][PLAYER_FINALLY_10] Exiting player thread finally block.")

    # --- extract_audio --- (No changes needed here)
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
             # Adding timestamp to prevent potential reuse issues if cleanup fails and same video is played again
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
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024: # Basic sanity check
                    print("[video player] Audio extraction successful.")
                    # Clean up previous audio *before* setting the new path
                    self._cleanup_resources()
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

    # --- play_video --- (No changes needed here)
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
        self.needs_resizing = False # Reset resize flag
        self.source_width = 0
        self.source_height = 0
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)

        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        self.is_playing = True # Signal that playback is intended to start

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


    # --- stop_video --- (No changes needed here)
    def stop_video(self, wait=True):
        """Stop video playback gracefully."""
        print(f"[video player] stop_video called (wait={wait}). is_playing={self.is_playing}")

        if not self.is_playing and self.should_stop:
             print("[video player] stop_video called but already stopping.") # INFO
             return

        if not self.is_playing and not self.should_stop:
             print("[video player] stop_video called but not playing. Cleaning up resources just in case.")
             self._cleanup_resources()
             return

        self.should_stop = True

        print("[video player] Stop signal sent to threads.")

        # Try stopping audio earlier
        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()
            time.sleep(0.05) # Allow brief time for audio system

        # Drain the queue and add sentinel
        if self.frame_queue:
            print("[video player] Draining frame queue...") # INFO
            drained_count = 0
            try:
                while not self.frame_queue.empty():
                    try:
                        self.frame_queue.get_nowait()
                        drained_count += 1
                    except queue.Empty:
                        break
                self.frame_queue.put(None, block=False) # Signal end to player
                print(f"[video player] Drained {drained_count} frames and added sentinel.") # INFO
            except queue.Full:
                 print("[video player] Warning: Queue full when trying to put None during stop.")
            except Exception as e:
                 print(f"[video player] Error interacting with queue during stop: {e}")

        # --- JOIN THREADS IF wait=True ---
        if wait:
            join_timeout = 2.0 # Max wait time for threads
            print(f"[video player] Waiting for threads to join (timeout {join_timeout}s)...")
            current_thread = threading.current_thread() # Don't join self

            reader_thread = self.video_reader_thread
            player_thread = self.video_player_thread

            # Wait for Reader Thread
            if reader_thread and reader_thread.is_alive() and reader_thread != current_thread:
                reader_thread.join(timeout=join_timeout / 2)
                if reader_thread.is_alive():
                     print("[video player] Warning: Reader thread did not exit cleanly after stop request.")
                else:
                     print("[video player] Reader thread joined successfully.")

            # Wait for Player Thread
            if player_thread and player_thread.is_alive() and player_thread != current_thread:
                 # Player thread might take slightly longer if it was processing the last frame/callback
                 player_thread.join(timeout=join_timeout / 2) # Give it its own timeout portion
                 if player_thread.is_alive():
                      print("[video player] Warning: Player thread did not exit cleanly after stop request.")
                 else:
                      print("[video player] Player thread joined successfully.")

            # If waiting, ensure is_playing is false after joins attempt
            # (Player thread's finally block *should* set this, but this is a safeguard)
            print("[video player] Setting is_playing = False after join attempt.")
            self.is_playing = False # Force state if threads didn't exit cleanly
            print("[video player] Thread join finished.")
        # If not waiting, is_playing will be set False by the player thread's finally block

        print("[video player] stop_video finished signaling.")

    # --- force_stop --- (No changes needed here)
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
        reader_thread = self.video_reader_thread
        player_thread = self.video_player_thread
        current_thread = threading.current_thread()

        if reader_thread and reader_thread.is_alive() and reader_thread != current_thread:
             reader_thread.join(timeout=join_timeout)
        if player_thread and player_thread.is_alive() and player_thread != current_thread:
             player_thread.join(timeout=join_timeout)

        self._cleanup_resources()
        self.reset_state()
        print("[video player] Force stop complete.")

    # --- reset_state --- (No changes needed here)
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


    # --- _safe_remove --- (No changes needed here)
    def _safe_remove(self, filepath):
        """Attempts to remove a file, ignoring errors if it doesn't exist."""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError as e:
                # Common issue on Windows is file lock, log as warning
                print(f"[video player] Warning: Could not remove file {filepath}: {e}")
            except Exception as e:
                 print(f"[video player] Error removing file {filepath}: {e}")

    # --- _cleanup_resources --- (No changes needed here)
    def _cleanup_resources(self):
        """Clean up temporary audio files."""
        audio_to_remove = self.current_audio_path
        self.current_audio_path = None
        self._safe_remove(audio_to_remove)


    # --- __del__ --- (No changes needed here)
    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            # Signal threads to stop without waiting in destructor
            if self.is_playing or self.should_stop:
                 print("[video player] Destructor: Signaling stop to any active threads...")
                 self.should_stop = True
                 self.is_playing = False # Assume stopped immediately for cleanup logic
                 # Don't join threads in __del__

            self._cleanup_resources()

            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
                print(f"[video player] Destructor: Cleaning up temporary directory: {temp_dir_to_remove}")
                import shutil
                shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                print(f"[video player] Destructor: Removed temporary directory (ignore_errors=True).")
                self.temp_dir = None # Mark as removed

        except Exception as e:
             print(f"[video player] Error during __del__: {e}")
        finally:
            # Make sure mixer is quit *if* this instance initialized it and nothing else needs it
            # This is tricky - safer to leave mixer management outside the player instance
            # Or use a shared initialization counter. For now, leave it.
            pass