# video_player.py
import cv2
import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import traceback
import os
import subprocess
import tempfile
import numpy as np
from pygame import mixer

class VideoPlayer:
    def __init__(self, root, ffmpeg_path, performance_mode=False):
        print("[video player] Initializing VideoPlayer")
        self.root = root
        self.ffmpeg_path = ffmpeg_path
        self.performance_mode = performance_mode
        self.video_canvas = None
        self.image_item = None
        self.is_playing = False
        self.should_stop = False
        self.resetting = False
        self.video_sound_channel = mixer.Channel(0)
        self.current_audio_path = None
        self.temp_dir = tempfile.mkdtemp()
        self.frame_rate = 30
        self.last_frame_time = time.time()
        self.buffer = None
        self.frame_update_interval = 1  # Fixed at 1 frame displayed per update

    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Optimized video playback thread with strict 30 FPS maintenance"""
        print(f"[video player] Starting playback: {video_path}")
        start_time = None
        self.on_complete = on_complete
        audio_start_time = None

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[video player] Failed to open video: {video_path}")
                return

            # Get video properties
            orig_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            orig_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            # Enforce minimum 30 FPS processing
            if self.frame_rate <= 0:
                self.frame_rate = 30
            frame_time = 1.0 / self.frame_rate

            # Set target resolution
            target_width = self.root.winfo_screenwidth()
            target_height = self.root.winfo_screenheight()
            if not self.performance_mode:
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)

            # Initialize processing buffer
            self.buffer = np.zeros((target_height, target_width, 3), dtype=np.uint8)

            # Audio initialization
            if audio_path:
                try:
                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    audio_start_time = time.time()
                    print("[video player] Audio playback started")
                except Exception as e:
                    print(f"[video player] Audio error: {e}")
                    audio_path = None

            # Video sync variables
            frame_count = 0
            last_frame_processed = time.time()
            deadline = time.time()

            while cap.isOpened() and self.is_playing and not self.should_stop:
                if self.resetting:
                    break

                # Calculate target frame based on elapsed time
                current_time = time.time()
                elapsed_time = current_time - (audio_start_time if audio_start_time else start_time)
                target_frame = int(elapsed_time * self.frame_rate)
                
                # Jump ahead if behind
                if target_frame > frame_count:
                    skip_frames = target_frame - frame_count
                    new_pos = min(frame_count + skip_frames, total_frames - 1)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
                    frame_count = new_pos

                # Read and process frame
                ret, frame = cap.read()
                if not ret:
                    break
                frame_count += 1

                # Process frame
                try:
                    # Optimized resize and color conversion
                    cv2.resize(frame, (target_width, target_height), self.buffer)
                    cv2.cvtColor(self.buffer, cv2.COLOR_BGR2RGB, self.buffer)
                    photo = ImageTk.PhotoImage(image=Image.fromarray(self.buffer))
                    self.root.after(0, self._update_canvas, photo)
                except Exception as e:
                    print(f"[video player] Frame error: {e}")

                # Strict timing control
                now = time.time()
                next_deadline = deadline + frame_time
                sleep_time = next_deadline - now
                
                if sleep_time > 0.001:  # Only sleep if meaningful
                    time.sleep(sleep_time * 0.95)  # Account for wakeup latency
                
                deadline = next_deadline

                # Emergency catch-up if falling behind
                if now > deadline + (frame_time * 2):
                    #print(f"[video player] Critical lag detected, skipping ahead")
                    new_pos = min(frame_count + int((now - deadline) * self.frame_rate), total_frames - 1)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, new_pos)
                    frame_count = new_pos
                    deadline = time.time()

        except Exception as e:
            print(f"[video player] Playback error: {str(e)}")
            traceback.print_exc()
        finally:
            cap.release()
            self._cleanup_playback()

    def _update_canvas(self, photo):
        """Thread-safe canvas update with error handling"""
        if not self.is_playing or self.should_stop or not self.video_canvas:
            return
            
        try:
            if self.image_item:
                self.video_canvas.itemconfig(self.image_item, image=photo)
                self.video_canvas.photo = photo
            else:
                self._create_image_item(photo)
        except tk.TclError:
            pass  # Handle window destruction during update

    def _create_image_item(self, photo):
        """Initialize canvas image item"""
        if self.video_canvas and self.video_canvas.winfo_exists():
            self.image_item = self.video_canvas.create_image(
                self.root.winfo_screenwidth() // 2,
                self.root.winfo_screenheight() // 2,
                image=photo,
                anchor="center",
            )
            self.video_canvas.photo = photo

    def extract_audio(self, video_path):
        """Extract audio from video using ffmpeg"""
        try:
            if not self.ffmpeg_path:
                return None

            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time())}.wav")

            command = [
                self.ffmpeg_path,
                "-i", video_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "44100",
                "-ac", "2",
                "-y",
                temp_audio,
            ]
            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode == 0 and os.path.exists(temp_audio):
                return temp_audio
            return None

        except Exception as e:
            print(f"[video player] Audio extraction failed: {e}")
            return None

    def play_video(self, video_path, audio_path, on_complete):
        """Start video playback"""
        print(f"[video player] Starting playback: {video_path}")
        try:
            self.video_canvas = tk.Canvas(
                self.root,
                width=self.root.winfo_screenwidth(),
                height=self.root.winfo_screenheight(),
                bg="black",
                highlightthickness=0,
            )
            self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.root.update_idletasks()

            self.should_stop = False
            self.is_playing = True

            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, on_complete),
                daemon=True,
            )
            self.video_thread.start()

        except Exception as e:
            print(f"[video player] Play failed: {e}")
            self._cleanup_playback()
            self.root.after(0, on_complete)

    def stop_video(self):
        """Stop video playback"""
        print("[video player] Stopping playback")
        self.should_stop = True
        self.is_playing = False

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

        if hasattr(self, "video_thread") and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.5)

        self._cleanup_playback()

    def force_stop(self):
        """Emergency stop for application resets"""
        print("[video player] Force stopping")
        self.resetting = True
        self.stop_video()
        self.resetting = False

    def _cleanup_playback(self):
        """Clean up resources"""
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            time.sleep(0.1)

        try:
            if self.video_canvas:
                self.video_canvas.delete("all")
                self.video_canvas.place_forget()
                self.video_canvas.destroy()
        except tk.TclError:
            pass
        finally:
            self.video_canvas = None
            self.image_item = None
            self.buffer = None

        if hasattr(self, "on_complete") and not self.resetting:
            self.root.after(0, self.on_complete)

    def reset_state(self):
        """Reset internal state"""
        self.should_stop = True
        self.is_playing = False
        self.image_item = None
        if hasattr(self, "video_thread"):
            del self.video_thread

    def __del__(self):
        """Cleanup temporary files"""
        try:
            if os.path.exists(self.temp_dir):
                for f in os.listdir(self.temp_dir):
                    os.remove(os.path.join(self.temp_dir, f))
                os.rmdir(self.temp_dir)
        except Exception as e:
            pass