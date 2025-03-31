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

try:
    import pyautogui # For screen size detection
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[video player] Warning: pyautogui not found. Screen size detection unavailable, assuming 1920x1080.")


class VideoPlayer:
    FRAME_QUEUE_SIZE = 30
    # Introduce a threshold for how far behind we can be before skipping aggressively
    # If we are more than (e.g.) 2 frames behind schedule, skip rendering.
    FRAME_SKIP_THRESHOLD_SECONDS = 2.5 # (Adjust as needed, e.g., 2.0 or 3.0)

    def __init__(self, ffmpeg_path):
        print("[video player] Initializing VideoPlayer (Optimized w/ Frame Skipping)")
        self.ffmpeg_path = ffmpeg_path
        self.is_playing = False
        self.should_stop = False
        self.playback_complete = True

        self.video_sound_channel = mixer.Channel(0)
        self.current_audio_path = None
        self.temp_dir = tempfile.mkdtemp(prefix="vidplayer_")

        self.frame_rate = 30.0
        self.frame_time = 1.0 / self.frame_rate

        self.video_reader_thread = None
        self.video_player_thread = None
        self.frame_queue = None

        self.on_complete_callback = None
        self.frame_update_callback = None

        self.target_width = 1920
        self.target_height = 1080
        self._update_target_dimensions()

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
        read_start_time = 0.0
        resize_start_time = 0.0
        put_start_time = 0.0
        read_total_time = 0.0
        resize_total_time = 0.0
        put_total_time = 0.0
        loop_count = 0

        try:
            # Explicitly try FFMPEG backend if available, often better performance
            # Note: If this causes errors opening certain files, revert to default
            cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
            if not cap.isOpened():
                print("[video player] Warning: Failed to open with FFMPEG backend, trying default.")
                cap = cv2.VideoCapture(video_path) # Fallback to default

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

            # --- Determine resizing ---
            self.needs_resizing = not (self.source_width == self.target_width and self.source_height == self.target_height)
            resize_interpolation = cv2.INTER_LINEAR # Good balance
            if self.needs_resizing:
                print(f"[video player] Resizing needed: Source {self.source_width}x{self.source_height} -> Target {self.target_width}x{self.target_height}")
            else:
                 print("[video player] No resizing needed.")

            # --- Frame Reading Loop ---
            while not self.should_stop:
                loop_start_time = time.perf_counter() # Start timing loop iteration

                # --- Read Frame ---
                read_start_time = time.perf_counter()
                ret, frame = cap.read()
                read_time = time.perf_counter() - read_start_time
                read_total_time += read_time

                if not ret:
                    print("[video player] Reader: End of video stream reached.")
                    break

                processed_frame = None # Initialize

                # --- Process Frame (Resizing) ---
                if self.needs_resizing:
                    resize_start_time = time.perf_counter()
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                    resize_time = time.perf_counter() - resize_start_time
                    resize_total_time += resize_time
                else:
                    processed_frame = frame
                    resize_time = 0.0 # No resize time

                # --- Put Frame in Queue ---
                put_start_time = time.perf_counter()
                try:
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0) # Wait up to 1 sec if full
                    processed_frame_count += 1
                except queue.Full:
                    print("[video player] Reader: Frame queue full. Player might be lagging or stopped. Waiting...")
                    # If the queue is full, wait a bit before trying again, check stop flag more often
                    try:
                        self.frame_queue.put(processed_frame, block=True, timeout=0.5) # Try again with shorter timeout
                        processed_frame_count += 1
                    except queue.Full:
                         print("[video player] Reader: Queue STILL full. Likely stopped.")
                         # No 'continue', let the main loop check self.should_stop
                except Exception as q_err:
                     print(f"[video player] Reader: Error putting frame in queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error

                put_time = time.perf_counter() - put_start_time
                put_total_time += put_time
                loop_count += 1

                # Optional: Periodic performance log
                # if loop_count % 100 == 0: # Log every 100 frames
                #     avg_read = (read_total_time / loop_count) * 1000
                #     avg_resize = (resize_total_time / loop_count) * 1000
                #     avg_put = (put_total_time / loop_count) * 1000
                #     print(f"[Perf Reader Frame {processed_frame_count}] Avg Read: {avg_read:.2f}ms, Avg Resize: {avg_resize:.2f}ms, Avg Put: {avg_put:.2f}ms")


            print(f"[video player] Reader: Processed {processed_frame_count} frames.")
            if loop_count > 0:
                 avg_read = (read_total_time / loop_count) * 1000
                 avg_resize = (resize_total_time / loop_count) * 1000
                 avg_put = (put_total_time / loop_count) * 1000
                 print(f"[Perf Reader Final] Avg Read: {avg_read:.2f}ms, Avg Resize: {avg_resize:.2f}ms, Avg Put: {avg_put:.2f}ms")


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
        frame_count = 0
        skipped_frame_count = 0 # Track skipped frames
        playback_start_perf_counter = -1.0
        audio_started = False
        got_first_frame = False

        try:
            print("[video player] Player: Waiting for first frame...")
            first_frame = self.frame_queue.get(block=True, timeout=10.0)
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                self.is_playing = False
                self.playback_complete = True
                return

            print(f"[video player] Player: Received first frame. Frame Time: {self.frame_time:.4f}s")
            got_first_frame = True

            # --- Audio Playback ---
            # (Audio setup remains the same)
            if audio_path and os.path.exists(audio_path):
                try:
                    if not mixer.get_init(): mixer.init(frequency=44100)
                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    audio_started = True
                    print("[video player] Player: Started audio playback.")
                except Exception as e:
                    print(f"[video player] Player: Error starting audio: {e}")
                    # Continue without audio
            else:
                print("[video player] Player: No valid audio path or file missing.")


            # --- Start Playback Timing ---
            playback_start_perf_counter = time.perf_counter()
            current_frame = first_frame # Initialize with the first frame
            last_display_time = playback_start_perf_counter # For calculating sleep

            # --- Playback Loop ---
            while True:
                if self.should_stop:
                    print("[video player] Player: Stop flag detected.")
                    break

                # --- Timing Calculation ---
                # Calculate the ideal display time for the *current* frame we are about to process
                target_display_time = playback_start_perf_counter + frame_count * self.frame_time
                current_time = time.perf_counter()
                time_until_target = target_display_time - current_time

                # --- Synchronization & Frame Skipping Logic ---
                frame_to_display = current_frame # Assume we display the current one

                if time_until_target > 0.001: # We have time before target display time
                    # Sleep until slightly before the target time
                    sleep_duration = max(0, time_until_target - 0.001)
                    time.sleep(sleep_duration)
                elif time_until_target < -(self.frame_time * self.FRAME_SKIP_THRESHOLD_SECONDS):
                    # We are significantly behind schedule (e.g., more than ~2 frames late)
                    # Skip displaying this frame and try to get the next one immediately
                    # to catch up to the clock.
                    skipped_frame_count += 1
                    print(f"[video player] Player: Skipping frame {frame_count} (Lag: {-time_until_target:.3f}s > Threshold)")
                    frame_to_display = None # Mark frame as skipped

                # If we are only slightly behind, we just proceed immediately without sleeping.

                # --- Display Frame (if not skipped) ---
                if frame_to_display is not None:
                    try:
                        if self.frame_update_callback:
                            self.frame_update_callback(frame_to_display) # Send BGR frame
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True # Stop if we can't display
                            break
                    except Exception as frame_err:
                        print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")
                        # Maybe add a counter here, stop if errors persist?

                # --- Prepare for Next Frame ---
                frame_count += 1 # Increment frame counter regardless of skip
                next_frame_target_time = playback_start_perf_counter + frame_count * self.frame_time

                # --- Get Next Frame from Queue ---
                next_frame = None
                try:
                    # How long should we wait for the next frame?
                    # Ideally, it should be ready very close to its target time.
                    # We can calculate a dynamic timeout based on how close we are to the next frame's deadline.
                    wait_timeout = max(0.001, next_frame_target_time - time.perf_counter())
                    # Cap the timeout to avoid excessively long waits if something is really wrong
                    wait_timeout = min(wait_timeout, self.frame_time * 2.0) # Wait max 2 frame times

                    if wait_timeout < 0.001: # If next frame is already due or overdue
                         # Try non-blocking first
                         next_frame = self.frame_queue.get(block=False)
                    else:
                         # Wait dynamically
                         next_frame = self.frame_queue.get(block=True, timeout=wait_timeout)

                except queue.Empty:
                     # Reader is lagging! The frame wasn't ready by its (dynamically calculated) deadline.
                     # The frame skipping logic above should help recover, but if it happens
                     # consistently, the reader is the bottleneck.
                     # We don't necessarily need to skip *here*, the logic at the start of the loop handles it.
                     # We just need to try getting the *next* available frame without crashing.
                     # print(f"[video player] Player: Queue empty when fetching frame {frame_count}. Reader lagging.")
                     # Try one more blocking get, maybe it arrived just now?
                     try:
                          next_frame = self.frame_queue.get(block=True, timeout=self.frame_time * 0.5) # Short extra wait
                     except queue.Empty:
                          print(f"[video player] Player: Still empty after short wait for frame {frame_count}. Will attempt skip on next cycle if lag persists.")
                          # Continue the loop - the skipping logic at the top will decide based on accumulated lag.
                          # We set current_frame to None to avoid re-displaying the old one.
                          current_frame = None # Ensure we don't redisplay old frame
                          continue # Go to start of next loop iteration


                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame from queue: {q_err}")
                     self.should_stop = True # Signal stop on queue error
                     break # Exit loop immediately

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print("[video player] Player: Received None sentinel. End of stream.")
                    self.playback_complete = True # Normal completion
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
            print(f"[video player] Player thread cleaning up... (Displayed approx {frame_count - skipped_frame_count}/{frame_count} frames, Skipped: {skipped_frame_count})")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 self.playback_complete = True

            if audio_started and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                time.sleep(0.05)

            # --- Final State Update & Callback (same as before) ---
            was_playing = self.is_playing
            self.is_playing = False

            if was_playing and self.on_complete_callback:
                 completion_reason = "Normal" if self.playback_complete else "Abnormal"
                 if self.should_stop and self.playback_complete: # If stopped externally, but stream finished
                     completion_reason = "Stopped"
                 elif self.should_stop and not self.playback_complete: # If stopped externally before finish
                     completion_reason = "Stopped (Abnormal)"

                 print(f"[video player] Player: Triggering on_complete_callback ({completion_reason}).")

                 try:
                      self.on_complete_callback()
                 except Exception as cb_err:
                      print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
            elif not was_playing:
                 print("[video player] Player: Playback did not start or was already stopped, skipping final on_complete_callback.")

            print("[video player] Player thread finished.")


    # --- extract_audio (unchanged) ---
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
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2", "-y",
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
                    self._cleanup_resources() # Clean up previous before assigning new
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

    # --- play_video (mostly unchanged, ensure state reset is thorough) ---
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
        # Ensure queue is definitely None before creating new one
        self.frame_queue = None
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE) # Create new queue

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


    # --- stop_video (unchanged logic, maybe more aggressive queue clearing) ---
    def stop_video(self, wait=False):
        """Stop video playback gracefully."""
        print(f"[video player] stop_video called (wait={wait}). is_playing={self.is_playing}, should_stop={self.should_stop}")

        # Prevent multiple stop calls causing issues
        if self.should_stop:
             # print("[video player] Already stopping.")
             # If wait=True, we might still need to join here if the first call didn't wait
             if wait:
                 join_timeout = 2.0
                 if self.video_reader_thread and self.video_reader_thread.is_alive(): self.video_reader_thread.join(timeout=join_timeout/2)
                 if self.video_player_thread and self.video_player_thread.is_alive(): self.video_player_thread.join(timeout=join_timeout/2)
             return

        if not self.is_playing:
             print("[video player] stop_video called but not playing. Cleaning up resources.")
             self._cleanup_resources() # Cleanup potential leftovers
             self.reset_state() # Ensure clean state
             return

        self.should_stop = True
        # is_playing is set by player thread on exit

        print("[video player] Stop signal sent to threads.")

        if self.video_sound_channel.get_busy():
            print("[video player] Stopping audio channel.")
            self.video_sound_channel.stop()
            time.sleep(0.05)

        # Try to unblock threads waiting on the queue
        if self.frame_queue:
            # Drain queue quickly - helps reader if blocked on put(), helps player if blocked on get()
            # print("[video player] Draining frame queue during stop...")
            drained_count = 0
            while True:
                try:
                    self.frame_queue.get_nowait()
                    drained_count += 1
                except queue.Empty:
                    break # Queue is empty
                except Exception as e:
                    print(f"[video player] Error draining queue item during stop: {e}")
                    break
            # print(f"[video player] Drained {drained_count} items.")

            # Put sentinel AFTER draining to ensure player sees it quickly
            try:
                self.frame_queue.put(None, block=False)
                # print("[video player] Put None sentinel in queue during stop.")
            except queue.Full:
                 print("[video player] Warning: Queue full when trying to put None during stop (should be rare after drain).")
            except Exception as e:
                 print(f"[video player] Error putting None sentinel during stop: {e}")

        if wait:
            join_timeout = 2.0
            print(f"[video player] Waiting for threads to join (timeout {join_timeout}s)...")
            start_join = time.time()
            try:
                if self.video_reader_thread and self.video_reader_thread.is_alive():
                    self.video_reader_thread.join(timeout=join_timeout)
                    if self.video_reader_thread.is_alive(): print("[video player] Warning: Reader thread did not exit cleanly.")
            except Exception as e: print(f"[video player] Error joining reader thread: {e}")

            remaining_timeout = max(0.1, join_timeout - (time.time() - start_join))
            try:
                if self.video_player_thread and self.video_player_thread.is_alive():
                     self.video_player_thread.join(timeout=remaining_timeout)
                     if self.video_player_thread.is_alive(): print("[video player] Warning: Player thread did not exit cleanly.")
            except Exception as e: print(f"[video player] Error joining player thread: {e}")

            # Force state if threads didn't set it (e.g., timed out join)
            self.is_playing = False
            print("[video player] Thread join finished.")
        else:
             # If not waiting, we can't guarantee is_playing is False yet.
             # The player thread will set it when it exits.
             pass

        print("[video player] stop_video finished signaling.")


    # --- force_stop (Mostly unchanged, ensure reset_state is called) ---
    def force_stop(self):
        """Force stop playback immediately, cleanup resources NOW."""
        print("[video player] Force stopping playback.")
        self.should_stop = True
        self.is_playing = False # Set state immediately

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            print("[video player] Force stopped audio channel.")
            time.sleep(0.05)

        if self.frame_queue:
            try:
                while not self.frame_queue.empty(): self.frame_queue.get_nowait()
                self.frame_queue.put(None, block=False)
            except Exception: pass

        join_timeout = 0.2
        if self.video_reader_thread and self.video_reader_thread.is_alive(): self.video_reader_thread.join(timeout=join_timeout)
        if self.video_player_thread and self.video_player_thread.is_alive(): self.video_player_thread.join(timeout=join_timeout)

        self._cleanup_resources()
        self.reset_state() # Explicitly reset state after force stop
        print("[video player] Force stop complete.")


    # --- reset_state (Unchanged) ---
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


    # --- _safe_remove (Unchanged) ---
    def _safe_remove(self, filepath):
        """Attempts to remove a file, ignoring errors if it doesn't exist."""
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError as e:
                print(f"[video player] Warning: Could not remove file {filepath}: {e}")
            except Exception as e:
                 print(f"[video player] Error removing file {filepath}: {e}")


    # --- _cleanup_resources (Unchanged) ---
    def _cleanup_resources(self):
        """Clean up temporary audio files."""
        audio_to_remove = self.current_audio_path
        self.current_audio_path = None
        self._safe_remove(audio_to_remove)


    # --- __del__ (Unchanged, but added check for temp_dir existence before shutil) ---
    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            if self.is_playing:
                 print("[video player] Destructor: Stopping active playback...")
                 # Use force stop logic here for faster cleanup in destructor context
                 self.should_stop = True
                 if self.video_sound_channel.get_busy(): self.video_sound_channel.stop()
                 # Don't wait for threads in __del__
                 # self.stop_video(wait=False) # Non-waiting stop is better in __del__

            self._cleanup_resources()

            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove): # Check if it exists
                print(f"[video player] Destructor: Cleaning up temporary directory: {temp_dir_to_remove}")
                import shutil
                try:
                    shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                    print(f"[video player] Destructor: Removed temporary directory.")
                except Exception as rmtree_err:
                     print(f"[video player] Destructor: Error removing temp dir {temp_dir_to_remove}: {rmtree_err}")
            # Ensure temp_dir attribute is cleared
            self.temp_dir = None

        except Exception as e:
             print(f"[video player] Error during __del__: {e}")
             traceback.print_exc() # Show more detail for destructor errors