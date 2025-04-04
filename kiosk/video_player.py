# video_player.py
import cv2
import threading
import time
import traceback
import os
from pygame import mixer
import numpy as np
import queue

try:
    import pyautogui # For screen size detection
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[video player] Warning: pyautogui not found. Screen size detection unavailable, assuming 1920x1080.")


class VideoPlayer:
    # --- Constants ---
    FRAME_QUEUE_SIZE = 30 # Number of frames to buffer ahead
    # Threshold for frame skipping: Skip if display lag > threshold * frame_time
    FRAME_SKIP_THRESHOLD_FACTOR = 1.5

    def __init__(self):
        # Removed ffmpeg_path dependency
        print("[video player] Initializing VideoPlayer (Preprocessed Files Version)")
        self.is_playing = False
        self.should_stop = False
        self.playback_complete = True

        # Initialize mixer if not already done
        if not mixer.get_init():
            try:
                mixer.init(frequency=44100) # Standard frequency
            except Exception as mix_err:
                 print(f"[video player] CRITICAL: Failed to initialize pygame mixer: {mix_err}")
                 # Optionally raise an exception or handle this state
                 # raise RuntimeError("Pygame mixer initialization failed") from mix_err
        # Ensure channel is valid even if mixer init failed above
        try:
            self.video_sound_channel = mixer.Channel(0)
        except Exception as chan_err:
             print(f"[video player] CRITICAL: Failed to get mixer Channel(0): {chan_err}")
             self.video_sound_channel = None # Mark as unusable

        # Removed temp_dir and current_audio_path logic

        self.frame_rate = 30.0
        self.frame_time = 1.0 / self.frame_rate

        # Threading and Queue
        self.video_reader_thread = None
        self.video_player_thread = None
        self.frame_queue = None

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
        Reads frames from video (e.g., preprocessed .avi), resizes if needed,
        puts them in the queue. Optimized for faster decoding (like MJPEG).
        """
        print(f"[video player] Reader thread starting for: {video_path}")
        cap = None
        processed_frame_count = 0
        read_successful = False

        try:
            # Use default backend, should handle AVI/MJPEG well
            cap = cv2.VideoCapture(video_path)

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
                print(f"[video player] Warning: Invalid/unreliable FPS ({_fps}) from video {os.path.basename(video_path)}. Using default 30.")
                self.frame_rate = 30.0
            else:
                self.frame_rate = float(_fps)

            # Prevent division by zero
            self.frame_time = 1.0 / self.frame_rate if self.frame_rate > 0 else 1.0/30.0

            print(f"[video player] Video properties: {self.source_width}x{self.source_height} @ {self.frame_rate:.2f} FPS (Frame Time: {self.frame_time:.4f}s)")

            # --- Determine if resizing is needed ONCE ---
            # Still relevant if target screen size differs from preprocessed video size
            self.needs_resizing = not (self.source_width == self.target_width and self.source_height == self.target_height)
            if self.needs_resizing:
                print(f"[video player] Resizing needed: Source {self.source_width}x{self.source_height} -> Target {self.target_width}x{self.target_height}")
                resize_interpolation = cv2.INTER_LINEAR # Good balance for speed/quality
            else:
                 print("[video player] No resizing needed.")

            # --- Frame Reading Loop ---
            while not self.should_stop:
                # --- Performance measurement (optional) ---
                # start_read = time.perf_counter()
                ret, frame = cap.read()
                # read_duration = time.perf_counter() - start_read
                # if processed_frame_count % 60 == 0: # Log approx every 2 seconds
                #     print(f"[DBG Reader] Frame {processed_frame_count}, Last read took: {read_duration:.4f}s (Frame Time: {self.frame_time:.4f}s)")
                # --- End performance measurement ---

                if not ret:
                    # End of video stream
                    print("[video player] Reader: End of video stream reached.")
                    break # Exit loop naturally

                # --- Process Frame (Resizing if needed) ---
                if self.needs_resizing:
                    # Even with MJPEG, resizing still takes CPU time
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    processed_frame = frame # Use BGR frame directly

                # --- Put Frame in Queue ---
                try:
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0) # Wait up to 1 sec if full
                    processed_frame_count += 1
                except queue.Full:
                    if self.should_stop: break # Exit if stop signal is set while queue is full
                    # print("[video player] Reader: Frame queue full.") # Can be noisy
                except Exception as q_err:
                     print(f"[video player] Reader: Error putting frame in queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error

            print(f"[video player] Reader: Processed {processed_frame_count} frames.")

        except Exception as e:
            print(f"[video player] CRITICAL: Error in reader thread for {video_path}:")
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
                     self.frame_queue.put(None, block=False)
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
        plays pre-extracted audio, and calls the frame update callback.
        """
        print(f"[video player] Player thread starting (Audio: {os.path.basename(audio_path or 'None')}).")
        frame_count = 0 # Index of the frame we are about to process/display/skip
        playback_start_perf_counter = -1.0
        audio_started = False
        got_first_frame = False
        skipped_frame_count = 0
        video_sound = None

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
            # Ensure mixer and channel are ready before playing
            if audio_path and os.path.exists(audio_path) and self.video_sound_channel:
                try:
                    print(f"[video player] Player: Loading audio: {audio_path}")
                    video_sound = mixer.Sound(audio_path) # Load the pre-extracted audio
                    self.video_sound_channel.play(video_sound)
                    audio_started = True
                    print("[video player] Player: Started audio playback.")
                except Exception as e:
                    print(f"[video player] Player: Error loading/playing audio '{audio_path}': {e}")
                    traceback.print_exc()
            elif not self.video_sound_channel:
                 print("[video player] Player: Cannot play audio, sound channel not available.")
            else:
                print(f"[video player] Player: No valid audio path ('{audio_path}') or file missing.")

            # --- Start Playback Timing ---
            # Start clock slightly *after* starting audio (if any) to sync better
            playback_start_perf_counter = time.perf_counter()

            # --- Playback Loop ---
            current_frame = first_frame
            while True:
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Time Check BEFORE Processing Current Frame ---
                current_time = time.perf_counter()
                ideal_display_time = playback_start_perf_counter + frame_count * self.frame_time
                lag = current_time - ideal_display_time

                # --- Frame Skipping Decision ---
                should_skip = (lag > (self.frame_time * self.FRAME_SKIP_THRESHOLD_FACTOR)) or (current_frame is None)

                if not should_skip:
                    # --- Process and Display Current Frame ---
                    try:
                        if self.frame_update_callback:
                            self.frame_update_callback(current_frame) # Pass BGR frame
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True
                            break
                    except Exception as frame_err:
                         print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")
                         # self.should_stop = True # Optional: stop on callback error
                else:
                    if skipped_frame_count % 60 == 0: # Log approx once every 2 seconds if skipping
                       print(f"[video player] Player: Skipping frame {frame_count} due to lag: {lag:.3f}s (Total skips: {skipped_frame_count+1})")
                    skipped_frame_count += 1

                # Increment frame count regardless of display/skip
                frame_count += 1

                # --- Timing Calculation for NEXT Frame ---
                expected_next_display_time = playback_start_perf_counter + frame_count * self.frame_time
                time_until_next = expected_next_display_time - time.perf_counter()

                # --- Get Next Frame ---
                next_frame = None
                try:
                    if time_until_next > 0.001: # If we have any time
                        sleep_duration = max(0, time_until_next - 0.002) # Sleep but wake early
                        time.sleep(sleep_duration)
                        # Try timed get
                        get_timeout = max(0.001, min(self.frame_time * 0.8, time_until_next))
                        next_frame = self.frame_queue.get(block=True, timeout=get_timeout)
                    else: # We are late
                        next_frame = self.frame_queue.get(block=False) # Non-blocking

                except queue.Empty:
                    # Reader is bottlenecked
                    # print(f"[video player] Player: Queue empty for frame {frame_count}.")
                    try:
                        wait_timeout = self.frame_time * 3.0 # Wait up to 3 frame times
                        next_frame = self.frame_queue.get(block=True, timeout=wait_timeout)
                    except queue.Empty:
                        print(f"[video player] Player: WARN - Timed out ({wait_timeout:.2f}s) waiting for frame {frame_count} after queue was empty. Reader stuck/slow or video ended abruptly?")
                        self.should_stop = True
                        print("[video player] Player: Assuming reader issue, stopping playback.")
                        self.playback_complete = False
                        break # Exit loop
                    except Exception as q_err_inner:
                        print(f"[video player] Player: Error during blocking get for frame {frame_count}: {q_err_inner}")
                        self.should_stop = True
                        break

                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame {frame_count} from queue: {q_err}")
                     traceback.print_exc()
                     self.should_stop = True
                     break # Exit loop

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print(f"[video player] Player: Received None sentinel after processing {frame_count} frames ({skipped_frame_count} skipped). End of stream.")
                    self.playback_complete = True
                    break # Exit loop

                # Prepare for next iteration
                current_frame = next_frame


        except queue.Empty:
             print("[video player] Player: Timed out waiting for the first frame. Aborting.")
             self.is_playing = False
             self.playback_complete = True
        except Exception as e:
            print("[video player] CRITICAL: Error in player thread:")
            traceback.print_exc()
            self.playback_complete = False
        finally:
            print(f"[video player] Player thread cleaning up... (Processed approx {frame_count} frames, Skipped: {skipped_frame_count})")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 self.playback_complete = True

            # Ensure audio stops
            if audio_started and self.video_sound_channel and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                # No need to unload sound explicitly unless managing memory tightly
                # if video_sound: video_sound = None # Let garbage collector handle
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

    # --- extract_audio method is REMOVED ---

    def play_video(self, video_path, audio_path, frame_update_cb, on_complete_cb):
        """
        Start video playback using preprocessed files.
        Assumes video_path is playable by OpenCV (e.g., .avi with MJPEG)
        and audio_path is playable by Pygame Mixer (e.g., .wav or .ogg).
        """
        print(f"[video player] play_video called for (Video: {video_path}, Audio: {audio_path})")

        # Check if paths exist before starting threads (optional but helpful)
        if not os.path.exists(video_path):
             print(f"[video player] Error: Video file not found: {video_path}")
             # Call completion callback immediately? Or just return? Let's just print error.
             # if on_complete_cb: on_complete_cb() # Or signal failure differently
             return
        if audio_path and not os.path.exists(audio_path):
             print(f"[video player] Warning: Audio file not found: {audio_path}. Will play video without audio.")
             audio_path = None # Ensure player thread doesn't try to load missing file

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
        self.frame_rate = 30.0 # Reset defaults, reader will update
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
            args=(audio_path,), # Pass the path to the pre-extracted audio
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
             return # Already stopping

        if not self.is_playing and not self.should_stop:
             # Not playing and not stopping. Maybe just ensure audio is stopped?
             if self.video_sound_channel and self.video_sound_channel.get_busy():
                  print("[video player] stop_video called but not playing; stopping lingering audio.")
                  self.video_sound_channel.stop()
             return

        # --- Signal Threads to Stop ---
        self.should_stop = True
        print("[video player] Stop signal sent to threads.")

        # --- Stop Audio Immediately ---
        if self.video_sound_channel and self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()
            time.sleep(0.05)

        # --- Unblock Queue ---
        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False) # Help player thread exit get()
            except queue.Full:
                 print("[video player] Warning: Queue full when trying to clear/put None during stop.")
            except Exception as e:
                 print(f"[video player] Error interacting with queue during stop: {e}")

        # --- Wait for Threads to Join ---
        if wait:
            join_timeout = 2.0
            print(f"[video player] Waiting for threads to join (timeout {join_timeout}s)...")
            start_join = time.monotonic()
            reader_thread = self.video_reader_thread
            player_thread = self.video_player_thread

            if reader_thread and reader_thread.is_alive():
                reader_thread.join(timeout=max(0.1, join_timeout - (time.monotonic() - start_join)))
                if reader_thread.is_alive():
                     print("[video player] Warning: Reader thread did not exit cleanly after stop request.")

            if player_thread and player_thread.is_alive():
                 player_thread.join(timeout=max(0.1, join_timeout - (time.monotonic() - start_join)))
                 if player_thread.is_alive():
                      print("[video player] Warning: Player thread did not exit cleanly after stop request.")

            # Force state if threads didn't exit cleanly after wait
            self.is_playing = False
            print("[video player] Thread join finished.")
        # else: is_playing state is set by the player thread itself when it exits

        print("[video player] stop_video finished signaling.")


    def force_stop(self):
        """Force stop playback immediately."""
        print("[video player] Force stopping playback.")
        self.should_stop = True
        self.is_playing = False # Set state immediately

        if self.video_sound_channel and self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            print("[video player] Force stopped audio channel.")
            time.sleep(0.05)

        if self.frame_queue:
            try:
                while not self.frame_queue.empty():
                    try: self.frame_queue.get_nowait()
                    except queue.Empty: break
                self.frame_queue.put(None, block=False)
            except Exception: pass # Ignore errors during force stop

        join_timeout = 0.2
        reader_thread = self.video_reader_thread
        player_thread = self.video_player_thread
        if reader_thread and reader_thread.is_alive():
             reader_thread.join(timeout=join_timeout)
        if player_thread and player_thread.is_alive():
             player_thread.join(timeout=join_timeout)

        # No temporary resources to clean here
        self.reset_state() # Reset state variables
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
        self.frame_rate = 30.0 # Reset defaults
        self.frame_time = 1.0 / self.frame_rate

    # --- _safe_remove method is REMOVED ---
    # --- _cleanup_resources method is REMOVED ---

    def __del__(self):
        """Destructor: Ensure playback is stopped."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            if self.is_playing:
                 print("[video player] Destructor: Signaling stop for active playback...")
                 # Use non-waiting stop to avoid blocking the destructor
                 self.stop_video(wait=False)

            # No temporary directory or files to clean up in this version
            print(f"[video player] Destructor finished for {id(self)}.")

        except Exception as e:
             # Catch errors during __del__ as they can be problematic
             print(f"[video player] Error during __del__: {e}")