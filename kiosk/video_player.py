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
try:
    import pyautogui # For screen size detection
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    print("[video player] Warning: pyautogui not found. Screen size detection unavailable, assuming 1920x1080.")


class VideoPlayer:
    def __init__(self, ffmpeg_path):
        print("[video player] Initializing VideoPlayer")
        self.ffmpeg_path = ffmpeg_path
        self.is_playing = False
        self.should_stop = False
        self.resetting = False
        self.video_sound_channel = mixer.Channel(0)
        self.current_audio_path = None
        self.temp_dir = tempfile.mkdtemp(prefix="vidplayer_")
        self.frame_rate = 30
        self.video_thread = None
        self.on_complete_callback = None
        self.frame_update_callback = None
        self.target_width = 1920 # Default target size
        self.target_height = 1080 # Default target size

        # Try to get actual screen size
        if PYAUTOGUI_AVAILABLE:
            try:
                self.target_width, self.target_height = pyautogui.size()
                print(f"[video player] Detected screen size: {self.target_width}x{self.target_height}")
            except Exception as e:
                 print(f"[video player] Error getting screen size via pyautogui: {e}. Using default {self.target_width}x{self.target_height}.")
        else:
             print(f"[video player] Using default screen size {self.target_width}x{self.target_height}.")


    def _play_video_thread(self, video_path, audio_path):
        """Video playback thread: reads frames, sends them via callback, syncs audio."""
        print(f"[video player] Video thread starting for: {video_path}")
        playback_start_perf_counter = time.perf_counter()
        cap = None # Initialize cap to None
        ret = False # Initialize ret to False

        # --- Timing accumulation variables ---
        accumulated_read_time = 0
        accumulated_processing_time = 0
        accumulated_callback_time = 0
        accumulated_wait_time = 0
        accumulated_sleep_time = 0
        accumulated_loop_time = 0
        timing_frame_count = 0
        PRINT_INTERVAL = 60 # Print average timings every 60 frames

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[video player] Failed to open video: {video_path}")
                self.is_playing = False
                if self.on_complete_callback:
                     threading.Timer(0.1, self.on_complete_callback).start()
                return # Exit thread

            self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
            if self.frame_rate <= 0 or self.frame_rate > 120:
                print(f"[video player] Warning: Invalid frame rate ({self.frame_rate}), using 30.")
                self.frame_rate = 30
            frame_time = 1.0 / self.frame_rate
            print(f"[video player] Video opened. FPS: {self.frame_rate:.2f}, Frame time: {frame_time:.4f}s")


            # --- Audio Playback ---
            audio_started = False
            if audio_path and os.path.exists(audio_path):
                try:
                    if not mixer.get_init(): mixer.init(frequency=44100)
                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    playback_start_perf_counter = time.perf_counter() # Reset start time after potential mixer init delay
                    print("[video player] Started audio playback.")
                    audio_started = True
                except Exception as e:
                    print(f"[video player] Error starting audio: {e}")
                    traceback.print_exc()
                    playback_start_perf_counter = time.perf_counter() # Reset start time
            else:
                print("[video player] No valid audio path or file missing.")
                playback_start_perf_counter = time.perf_counter() # Reset start time


            # --- Frame Loop ---
            frame_count = 0
            loop_start_time = time.perf_counter() # For loop duration measurement

            while True: # Loop until break
                # --- Check Flags First ---
                if self.should_stop or self.resetting:
                    print(f"[video player] Stop/Reset flag detected (stop={self.should_stop}, reset={self.resetting}). Breaking loop.")
                    break

                # --- Timing Calculation ---
                current_time = time.perf_counter()
                expected_time = playback_start_perf_counter + frame_count * frame_time
                wait_time = expected_time - current_time
                accumulated_wait_time += wait_time # Can be negative

                # --- Read Frame *BEFORE* Skipping Logic ---
                read_start = time.perf_counter()
                ret, frame = cap.read()
                read_duration = time.perf_counter() - read_start
                accumulated_read_time += read_duration

                if not ret:
                    print("[video player] End of video stream reached.")
                    break # Exit loop normally if read fails

                # --- Frame Skipping (Simplified) ---
                if wait_time < -frame_time * 1.5 and self.is_playing:
                    # print(f"Skipping frame {frame_count} due to lag ({wait_time:.3f}s)") # Debug noise
                    frame_count += 1
                    # Measure loop time even for skipped frames
                    loop_end_time = time.perf_counter()
                    accumulated_loop_time += loop_end_time - loop_start_time
                    loop_start_time = loop_end_time
                    timing_frame_count += 1
                    continue # Go straight to next loop iteration (reads next frame)

                # --- Wait if ahead ---
                actual_sleep_duration = 0
                if wait_time > 0.001:
                    sleep_start = time.perf_counter()
                    # Use a slightly more robust sleep target
                    sleep_target = max(0, wait_time - 0.001)
                    time.sleep(sleep_target)
                    actual_sleep_duration = time.perf_counter() - sleep_start
                accumulated_sleep_time += actual_sleep_duration

                # --- Process and Send Frame ---
                # (Only if not skipped)
                if self.is_playing and not self.should_stop and not self.resetting:
                    processing_start = time.perf_counter()
                    try:
                        # Check dimensions (optional but recommended)
                        frame_h, frame_w = frame.shape[:2]
                        if frame_w == self.target_width and frame_h == self.target_height:
                            # Dimensions match - USE FRAME DIRECTLY (frame is BGR)
                            processed_frame = frame
                        else:
                            # Fallback: Dimensions differ (unexpected), so resize (still BGR)
                            print(f"[video player] Warning: Frame size {frame_w}x{frame_h} differs from target {self.target_width}x{self.target_height}. Resizing.")
                            processed_frame = cv2.resize(frame, (self.target_width, self.target_height), interpolation=cv2.INTER_NEAREST)

                        # *** NO cv2.cvtColor HERE *** - We send BGR

                        processing_duration = time.perf_counter() - processing_start
                        accumulated_processing_time += processing_duration

                        # Send frame data (BGR) via callback
                        callback_start = time.perf_counter()
                        if self.frame_update_callback:
                            self.frame_update_callback(processed_frame) # Sending BGR frame
                        else:
                            print("[video player] Error: frame_update_callback missing!")
                            self.should_stop = True # Stop if callback invalid
                        callback_duration = time.perf_counter() - callback_start
                        accumulated_callback_time += callback_duration

                    except Exception as frame_err:
                         print(f"[video player] Error processing/sending frame {frame_count}: {frame_err}")
                         # self.should_stop = True # Optionally stop on frame errors
                         accumulated_processing_time += time.perf_counter() - processing_start # Add time even if error
                         accumulated_callback_time += 0 # No callback happened

                frame_count += 1
                timing_frame_count += 1 # Increment counter for averaging

                # --- Periodic Timing Report ---
                if timing_frame_count >= PRINT_INTERVAL:
                    avg_read = (accumulated_read_time / timing_frame_count) * 1000
                    avg_processing = (accumulated_processing_time / timing_frame_count) * 1000
                    avg_callback = (accumulated_callback_time / timing_frame_count) * 1000
                    avg_wait = (accumulated_wait_time / timing_frame_count) * 1000
                    avg_sleep = (accumulated_sleep_time / timing_frame_count) * 1000
                    avg_loop = (accumulated_loop_time / timing_frame_count) * 1000
                    actual_fps = timing_frame_count / accumulated_loop_time if accumulated_loop_time > 0 else 0

                    print(f"[PERF Player Loop (avg over {timing_frame_count} frames)]")
                    print(f"  - Avg Read:      {avg_read:.2f} ms")
                    print(f"  - Avg Process:   {avg_processing:.2f} ms (Resize/Prep)")
                    print(f"  - Avg Callback:  {avg_callback:.2f} ms (Signal Emit)")
                    print(f"  - Avg Wait Time: {avg_wait:.2f} ms (Target sleep/lag)")
                    print(f"  - Avg Sleep:     {avg_sleep:.2f} ms (Actual sleep)")
                    print(f"  - Avg Total Loop:{avg_loop:.2f} ms")
                    print(f"  - Actual FPS:    {actual_fps:.2f}")

                    # Reset accumulators
                    accumulated_read_time = 0
                    accumulated_processing_time = 0
                    accumulated_callback_time = 0
                    accumulated_wait_time = 0
                    accumulated_sleep_time = 0
                    accumulated_loop_time = 0
                    timing_frame_count = 0

                # Measure loop time for the next iteration
                loop_end_time = time.perf_counter()
                accumulated_loop_time += loop_end_time - loop_start_time
                loop_start_time = loop_end_time

                # End loop check (redundant?)
                if not self.is_playing:
                    print("[video player] is_playing became False. Breaking loop.")
                    break

        except Exception as e:
            print("[video player] Unexpected error in video thread:")
            traceback.print_exc()
        finally:
            print("[video player] Cleaning up video thread...")
            if cap and cap.isOpened():
                cap.release()
                print("[video player] Released video capture.")

            if audio_started and self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                print("[video player] Stopped video audio channel.")
                time.sleep(0.05)

            self.is_playing = False
            if self.on_complete_callback and not self.resetting:
                print("[video player] Triggering on_complete_callback.")
                try:
                    self.on_complete_callback()
                except Exception as cb_err:
                    print(f"[video player] Error executing on_complete_callback: {cb_err}")
            elif self.resetting:
                print("[video player] Resetting, skipping final on_complete_callback.")

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

        try:
             base_name = os.path.splitext(os.path.basename(video_path))[0]
             # Ensure temp dir exists
             if not os.path.exists(self.temp_dir): os.makedirs(self.temp_dir)
             temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time()*1000)}.wav")
        except Exception as temp_err:
             print(f"[video player] Error creating temp file path: {temp_err}")
             return None


        print(f"[video player] Extracting audio to: {temp_audio}")
        command = [
            self.ffmpeg_path, "-hide_banner", "-loglevel", "error", # Reduce ffmpeg noise
            "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
            "-y", temp_audio,
        ]

        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            result = subprocess.run(command, capture_output=True, text=True, check=False, startupinfo=startupinfo, encoding='utf-8')

            if result.returncode != 0:
                print(f"[video player] ffmpeg error (code {result.returncode}): {result.stderr}")
                if os.path.exists(temp_audio):
                    try: os.remove(temp_audio)
                    except OSError as rm_err: print(f"[video player] Could not remove failed temp audio {temp_audio}: {rm_err}")
                return None
            else:
                if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 1024: # Check size > 1KB
                    self.current_audio_path = temp_audio
                    return temp_audio
                else:
                     print(f"[video player] Error: Temp audio file missing, empty, or too small: {temp_audio}")
                     if os.path.exists(temp_audio): os.remove(temp_audio) # Clean up invalid file
                     return None

        except FileNotFoundError:
             print(f"[video player] Error: ffmpeg not found at '{self.ffmpeg_path}'.")
             return None
        except Exception as e:
            print(f"[video player] Audio extraction error: {e}")
            traceback.print_exc()
            if os.path.exists(temp_audio):
                 try: os.remove(temp_audio)
                 except OSError as rm_err: print(f"[video player] Could not remove failed temp audio {temp_audio}: {rm_err}")
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
        # Set is_playing True *before* starting thread
        self.is_playing = True
        self.frame_update_callback = frame_update_cb
        self.on_complete_callback = on_complete_cb

        # Start playback thread
        self.video_thread = threading.Thread(
            target=self._play_video_thread,
            args=(video_path, audio_path),
            daemon=True,
            name=f"VideoPlayerThread-{os.path.basename(video_path)}"
        )
        print("[video player] Starting video thread...")
        self.video_thread.start()

    def stop_video(self):
        """Stop video and audio playback gracefully."""
        print("[video player] stop_video called.")
        if not self.is_playing and not self.should_stop:
             # print("[video player] Not playing, stop request ignored.") # Reduce noise
             return

        self.should_stop = True # Signal the thread to stop

        # Stop audio channel directly
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

        # Wait briefly for the thread to potentially exit on its own
        if self.video_thread and self.video_thread.is_alive():
             self.video_thread.join(timeout=0.5)
             if self.video_thread.is_alive():
                  print("[video player] Warning: Video thread did not exit cleanly after stop request.")

        print("[video player] stop_video finished signaling.")


    def force_stop(self):
        """Force stop playback immediately, intended for reset scenarios."""
        print("[video player] Force stopping playback.")
        self.resetting = True # Signal a forced reset
        self.should_stop = True
        self.is_playing = False # Set immediately for force stop

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            print("[video player] Force stopped audio channel.")
            time.sleep(0.05)

        if self.video_thread and self.video_thread.is_alive():
            print("[video player] Video thread still alive during force_stop (expected).")

        self._cleanup_resources() # Clean up resources *now* in force stop
        self.reset_state() # Reset internal state variables
        print("[video player] Force stop complete.")

    def reset_state(self):
        """Reset state variables, typically after a force_stop."""
        print("[video player] Resetting internal state.")
        self.should_stop = False
        self.is_playing = False
        self.resetting = False
        self.video_thread = None
        self.on_complete_callback = None
        self.frame_update_callback = None


    def _cleanup_resources(self):
        """Clean up temporary files and potentially other resources."""
        audio_to_remove = self.current_audio_path
        self.current_audio_path = None

        if audio_to_remove and os.path.exists(audio_to_remove):
            try:
                for attempt in range(2):
                    try:
                        os.remove(audio_to_remove)
                        break
                    except PermissionError:
                        if attempt == 0: time.sleep(0.2)
                    except FileNotFoundError:
                         break
                else:
                    print(f"[video player] Warning: Failed to remove temp audio file after retries: {audio_to_remove}")
            except Exception as e:
                print(f"[video player] Error removing temp audio file {audio_to_remove}: {e}")

    def __del__(self):
        """Destructor: Ensure cleanup of the temporary directory."""
        temp_dir_to_remove = getattr(self, 'temp_dir', None)
        if temp_dir_to_remove and os.path.isdir(temp_dir_to_remove):
            import shutil
            shutil.rmtree(temp_dir_to_remove, ignore_errors=True)
        self.temp_dir = None