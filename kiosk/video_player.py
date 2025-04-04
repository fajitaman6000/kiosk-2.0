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
        # This now stores the path to the *temporary* extracted audio, if any
        self.current_temp_audio_path = None
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
                if width > 100 and height > 100:
                     self.target_width, self.target_height = width, height
                     print(f"[video player] Detected screen size: {self.target_width}x{self.target_height}")
                else:
                    raise ValueError(f"pyautogui returned invalid size: {width}x{height}")
            except Exception as e:
                 print(f"[video player] Error getting screen size via pyautogui: {e}. Using default {self.target_width}x{self.target_height}.")
        else:
             print(f"[video player] pyautogui not available. Using default screen size {self.target_width}x{self.target_height}.")

    def _reader_thread_func(self, video_path_to_open):
        """
        Reads frames from the specified video file (AVI or MP4), resizes if needed, puts them in the queue.
        """
        print(f"[video player] Reader thread starting for: {video_path_to_open}") # Use the provided path
        cap = None
        processed_frame_count = 0
        read_successful = False

        try:
            # cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG) # Default/often robust
            # cap = cv2.VideoCapture(video_path, cv2.CAP_MSMF) # Windows Media Foundation
            # cap = cv2.VideoCapture(video_path, cv2.CAP_DSHOW) # DirectShow (older Windows)
            cap = cv2.VideoCapture(video_path_to_open) # Open the specified video file

            if not cap.isOpened():
                print(f"[video player] CRITICAL: Failed to open video in reader thread: {video_path_to_open}")
                if self.frame_queue:
                    try: self.frame_queue.put(None, timeout=0.5)
                    except queue.Full: pass
                return

            read_successful = True # Mark that cap was opened

            # --- Get Video Properties ---
            self.source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            _fps = cap.get(cv2.CAP_PROP_FPS)

            # Validate FPS
            if _fps is None or not (0.1 < _fps < 121.0):
                # AVI files sometimes report weird FPS, fallback might be needed
                print(f"[video player] Warning: Invalid/unreliable FPS ({_fps}) from video '{os.path.basename(video_path_to_open)}'. Using default 30.")
                self.frame_rate = 30.0
            else:
                self.frame_rate = float(_fps)
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
                    break

                # --- Process Frame (Resizing if needed) ---
                if self.needs_resizing:
                    processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=resize_interpolation)
                else:
                    processed_frame = frame

                # --- Put Frame in Queue ---
                try:
                    self.frame_queue.put(processed_frame, block=True, timeout=1.0)
                    processed_frame_count += 1
                except queue.Full:
                    print("[video player] Reader: Frame queue full. Player might be lagging or stopped.")
                except Exception as q_err:
                     print(f"[video player] Reader: Error putting frame in queue: {q_err}")
                     self.should_stop = True


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


    def _player_thread_func(self, audio_path_to_play):
        """
        Takes frames from the queue, handles timing/sync, plays the specified audio file (WAV or temp extracted),
        and calls the frame update callback.
        """
        print(f"[video player] Player thread starting (Audio: {'Provided' if audio_path_to_play else 'None'})")
        frame_count = 0
        playback_start_perf_counter = -1.0
        audio_started = False
        got_first_frame = False

        try:
            print("[video player] Player: Waiting for first frame from reader...")
            first_frame = self.frame_queue.get(block=True, timeout=10.0)
            if first_frame is None:
                print("[video player] Player: Received None sentinel immediately. Reader likely failed.")
                self.is_playing = False
                self.playback_complete = True
                return

            print(f"[video player] Player: Received first frame. Frame Time: {self.frame_time:.4f}s")
            got_first_frame = True

            # --- Audio Playback ---
            # Use the audio_path_to_play provided by VideoManager
            if audio_path_to_play and os.path.exists(audio_path_to_play):
                try:
                    print(f"[video player] Player: Attempting to play audio: {audio_path_to_play}") # Log which audio file
                    if not mixer.get_init(): mixer.init(frequency=44100)
                    video_sound = mixer.Sound(audio_path_to_play)
                    self.video_sound_channel.play(video_sound)
                    audio_started = True
                    print("[video player] Player: Started audio playback.")
                except Exception as e:
                    print(f"[video player] Player: Error starting audio '{os.path.basename(audio_path_to_play)}': {e}")
                    traceback.print_exc()
            else:
                if audio_path_to_play:
                    print(f"[video player] Player: Audio file not found or invalid: {audio_path_to_play}")
                else:
                    print("[video player] Player: No audio path provided.")

            # --- Start Playback Timing ---
            playback_start_perf_counter = time.perf_counter()

            # --- Playback Loop ---
            current_frame = first_frame
            while True:
                if self.should_stop:
                    print("[video player] Player: Stop flag detected. Breaking loop.")
                    break

                # --- Process Current Frame ---
                if current_frame is not None:
                    try:
                        if self.frame_update_callback:
                            self.frame_update_callback(current_frame)
                        else:
                            print("[video player] Player: Error: frame_update_callback missing!")
                            self.should_stop = True
                        frame_count += 1
                    except Exception as frame_err:
                         print(f"[video player] Player: Error processing/sending frame {frame_count}: {frame_err}")


                # --- Timing Calculation ---
                current_time = time.perf_counter()
                expected_display_time = playback_start_perf_counter + frame_count * self.frame_time
                time_until_next_frame = expected_display_time - current_time

                # --- Get Next Frame (or wait) ---
                next_frame = None
                try:
                    if time_until_next_frame > 0.002:
                        sleep_duration = max(0, time_until_next_frame - 0.002)
                        time.sleep(sleep_duration)
                        next_frame = self.frame_queue.get(block=True, timeout=max(0.001, self.frame_time * 0.5))
                    else:
                        next_frame = self.frame_queue.get(block=False)

                except queue.Empty:
                     lag_time = -time_until_next_frame
                     # print(f"[video player] Player: Frame queue empty (lag: {lag_time:.3f}s). Waiting...") # Can be noisy
                     try:
                         next_frame = self.frame_queue.get(block=True, timeout=self.frame_time * 2.0)
                     except queue.Empty:
                          print("[video player] Player: Timed out waiting for frame after lag. Reader may be stuck/slow.")
                          continue
                except Exception as q_err:
                     print(f"[video player] Player: Error getting frame from queue: {q_err}")
                     self.should_stop = True

                # --- Check for End Sentinel ---
                if next_frame is None:
                    print("[video player] Player: Received None sentinel. End of stream.")
                    self.playback_complete = True
                    break

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
            print(f"[video player] Player thread cleaning up... (Played approx {frame_count} frames)")
            if not got_first_frame:
                 print("[video player] Player: Never received the first frame.")
                 self.playback_complete = True

            if audio_started and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Player: Stopped video audio channel.")
                time.sleep(0.05)

            was_playing = self.is_playing
            self.is_playing = False

            if was_playing and self.on_complete_callback:
                 if self.playback_complete:
                     print("[video player] Player: Triggering on_complete_callback (Normal Completion or Stop).")
                 else:
                     print("[video player] Player: Triggering on_complete_callback (Abnormal Termination).")

                 try:
                      self.on_complete_callback()
                 except Exception as cb_err:
                      print(f"[video player] Player: Error executing on_complete_callback: {cb_err}")
            elif not was_playing:
                 print("[video player] Player: Playback did not start or was already stopped, skipping final on_complete_callback.")


            print("[video player] Player thread finished.")

    def extract_audio(self, video_path_for_extraction):
        """
        Extract audio using ffmpeg FROM the specified video file TO a temporary file.
        Returns the path to the temporary WAV file on success, None otherwise.
        This is intended as a fallback when a pre-transcoded WAV is missing.
        """
        print(f"[video player] Attempting to extract audio from (for fallback): {video_path_for_extraction}")
        if not os.path.exists(video_path_for_extraction):
             print(f"[video player] Error: Video file for extraction not found: {video_path_for_extraction}")
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

        # --- ALWAYS save to the temporary directory ---
        temp_audio_path = None
        try:
             safe_basename = "".join(c if c.isalnum() else "_" for c in os.path.basename(video_path_for_extraction))
             # Ensure it's a WAV file in the temp dir
             temp_audio_path = os.path.join(self.temp_dir, f"extracted_audio_{safe_basename}_{int(time.time()*1000)}.wav")
        except Exception as temp_err:
             print(f"[video player] Error creating temp file path: {temp_err}")
             return None

        print(f"[video player] Extracting audio to temporary file: {temp_audio_path}")
        command = [
            self.ffmpeg_path, "-hide_banner", "-loglevel", "error",
            "-i", video_path_for_extraction, # Source video
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "44100",
            "-ac", "2",
            "-y",
            temp_audio_path, # Output temporary WAV
        ]

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(command, capture_output=True, text=True, check=False, startupinfo=startupinfo, encoding='utf-8', errors='ignore')

            if result.returncode != 0:
                print(f"[video player] ffmpeg error during extraction (code {result.returncode}): {result.stderr}")
                self._safe_remove(temp_audio_path) # Clean up failed temp file
                return None
            else:
                if os.path.exists(temp_audio_path) and os.path.getsize(temp_audio_path) > 1024:
                    print("[video player] Temporary audio extraction successful.")
                    # Clean up previous *temporary* audio if any
                    self._cleanup_resources()
                    # Store the path to *this* temporary file for later cleanup
                    self.current_temp_audio_path = temp_audio_path
                    return temp_audio_path # Return path to the temp file
                else:
                     print(f"[video player] Error: Temp audio file missing, empty, or too small after ffmpeg success: {temp_audio_path}")
                     self._safe_remove(temp_audio_path)
                     return None

        except FileNotFoundError:
             print(f"[video player] Error: ffmpeg executable not found at '{self.ffmpeg_path}'. Check path.")
             return None
        except Exception as e:
            print(f"[video player] Audio extraction error: {e}")
            traceback.print_exc()
            self._safe_remove(temp_audio_path) # Clean up temp file on error
            return None

    # Modified signature: takes paths determined by VideoManager
    def play_video(self, video_path_to_open, audio_path_to_play, frame_update_cb, on_complete_cb):
        """
        Start video playback using the specified video and audio files.
        """
        print(f"[video player] play_video called with Video: '{os.path.basename(video_path_to_open)}', Audio: '{os.path.basename(audio_path_to_play) if audio_path_to_play else 'None'}'")

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
        self.frame_queue = queue.Queue(maxsize=self.FRAME_QUEUE_SIZE)
        # Make sure temp audio path is cleared from previous runs
        self._cleanup_resources() # Cleans self.current_temp_audio_path

        # --- Set Callbacks ---
        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        # --- Set Playing Flag ---
        self.is_playing = True

        # --- Start Threads ---
        # Pass the determined paths to the threads
        self.video_reader_thread = threading.Thread(
            target=self._reader_thread_func,
            args=(video_path_to_open,), # Use the video path passed in
            daemon=True,
            name=f"VideoReader-{os.path.basename(video_path_to_open)}"
        )

        self.video_player_thread = threading.Thread(
            target=self._player_thread_func,
            args=(audio_path_to_play,), # Use the audio path passed in
            daemon=True,
            name=f"VideoPlayer-{os.path.basename(video_path_to_open)}"
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
             self._cleanup_resources() # Cleanup potential temp audio
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
            if self.video_reader_thread and self.video_reader_thread.is_alive():
                self.video_reader_thread.join(timeout=join_timeout/2)
                if self.video_reader_thread.is_alive():
                     print("[video player] Warning: Reader thread did not exit cleanly after stop request.")

            if self.video_player_thread and self.video_player_thread.is_alive():
                 self.video_player_thread.join(timeout=join_timeout/2)
                 if self.video_player_thread.is_alive():
                      print("[video player] Warning: Player thread did not exit cleanly after stop request.")

            self.is_playing = False
            print("[video player] Thread join finished.")

        # --- Cleanup of *temporary* resources happens automatically ---
        # when a new video is played or via __del__
        print("[video player] stop_video finished signaling.")

    def force_stop(self):
        """Force stop playback immediately, cleanup temporary resources NOW."""
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

        # Clean up *temporary* resources immediately
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
        """Clean up *temporary* audio files created by extract_audio."""
        # This method SPECIFICALLY targets self.current_temp_audio_path
        audio_to_remove = self.current_temp_audio_path
        if audio_to_remove:
            # print(f"[video player] Cleaning up temporary resource: {audio_to_remove}") # Reduce noise
            self._safe_remove(audio_to_remove)
            self.current_temp_audio_path = None # Clear path after removal


    def __del__(self):
        """Destructor: Ensure cleanup of temporary files and directory."""
        print(f"[video player] Destructor called for {id(self)}.")
        try:
            if self.is_playing:
                 print("[video player] Destructor: Stopping active playback...")
                 self.stop_video(wait=False)

            # Cleanup any lingering *temporary* audio
            self._cleanup_resources()

            temp_dir_to_remove = getattr(self, 'temp_dir', None)
            if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
                print(f"[video player] Destructor: Cleaning up temporary directory: {temp_dir_to_remove}")
                import shutil
                shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
                print(f"[video player] Destructor: Removed temporary directory (ignore_errors=True).")

        except Exception as e:
             print(f"[video player] Error during __del__: {e}")
        finally:
             pass
        self.temp_dir = None