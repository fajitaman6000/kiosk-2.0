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
import imageio_ffmpeg
from pygame import mixer


class VideoPlayer:
    def __init__(self, root, ffmpeg_path):
        print("[video player]Initializing VideoPlayer")
        self.root = root
        self.ffmpeg_path = ffmpeg_path
        self.video_canvas = None
        self.image_item = None  # Store the image item ID
        self.is_playing = False
        self.should_stop = False
        self.resetting = False
        self.video_sound_channel = mixer.Channel(0)
        self.current_audio_path = None
        self.temp_dir = tempfile.mkdtemp()
        self.frame_rate = 30  # Default frame rate

    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Video playback thread with synchronized audio."""
        print("[video player]Video thread starting")
        start_time = None
        self.on_complete = on_complete

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[video player]Failed to open video: {video_path}")
                return

            self.frame_rate = cap.get(cv2.CAP_PROP_FPS)
            if self.frame_rate <= 0:
                self.frame_rate = 30  # Fallback to 30 FPS
            frame_time = 1.0 / self.frame_rate
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            print(f"[video player]Video opened. FPS: {self.frame_rate}")

            # --- Get target dimensions (screen size) ---
            target_width = self.root.winfo_screenwidth()
            target_height = self.root.winfo_screenheight()


            # Start audio playback if available
            if audio_path:
                try:
                    video_sound = mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    start_time = time.time()
                    print("[video player]Started audio playback")
                except Exception as e:
                    print(f"[video player]Error starting audio: {e}")
                    audio_path = None

            # Click handler (solution video skipping)
            if "video_solutions" in video_path:
                def on_canvas_click(event):
                    print("[video player]Video canvas clicked (solution)")
                    self.stop_video()

                self.root.after(
                    0, lambda: self.video_canvas.bind("<Button-1>", on_canvas_click)
                )
            else:
                print("[video player]Intro video - skip disabled")

            frame_count = 0
            last_frame_time = time.time()

            while cap.isOpened() and self.is_playing and not self.should_stop:
                if self.resetting:
                    print("[video player]Resetting, breaking playback")
                    break

                # Calculate desired frame based on elapsed time
                if start_time is not None:
                    elapsed_time = time.time() - start_time
                    target_frame = int(elapsed_time * self.frame_rate)

                    # Frame skipping to catch up
                    skip_frames = target_frame - frame_count
                    if skip_frames > 0:
                        for _ in range(min(skip_frames, 10)):  # Limit skips
                            ret, _ = cap.read()
                            if not ret:
                                break  # End of video
                            frame_count += 1

                ret, frame = cap.read()
                if not ret:
                    print("[video player]End of video reached")
                    break
                frame_count += 1

                self._process_frame_and_update(frame, target_width, target_height)


                # --- Precise Timing ---
                current_time = time.time()
                elapsed_since_last_frame = current_time - last_frame_time
                sleep_time = frame_time - elapsed_since_last_frame
                if sleep_time > 0:
                    time.sleep(sleep_time)
                last_frame_time = time.time()  # Update for next iteration


        except Exception as e:
            print("[video player]Error in video thread:")
            traceback.print_exc()
        finally:
            print("[video player]Cleaning up video thread")
            cap.release()

            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                time.sleep(0.1)

            if not self.resetting:
                self.root.after(0, self._cleanup)
            else:
                print("[video player]Resetting, skipping on_complete")

    def _process_frame_and_update(self, frame, target_width, target_height):
        """Process and update the frame, resizing with OpenCV."""
        try:
            # --- Resize with OpenCV (potentially faster) ---
            frame = cv2.resize(frame, (target_width, target_height))
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image=image)

            # --- Update existing image item ---
            if self.image_item:  # Update if it exists
                self.root.after(0, lambda p=photo: self.video_canvas.itemconfig(self.image_item, image=p))
                self.root.after(0, lambda p=photo: setattr(self.video_canvas, 'photo', p)) #Crucial

            else:  # Create if it doesn't exist (first frame)
                self.root.after(0, self._create_image_item, photo)

        except Exception as e:
            print(f"[video player]Error processing/updating frame: {e}")
            traceback.print_exc()

    def _create_image_item(self, photo):
        """Create the image item on the canvas (for the first frame)."""
        if self.video_canvas and self.video_canvas.winfo_exists():
            self.image_item = self.video_canvas.create_image(
                self.root.winfo_screenwidth() // 2,
                self.root.winfo_screenheight() // 2,
                image=photo,
                anchor="center",
            )
            self.video_canvas.photo = photo  # Keep a reference


    def extract_audio(self, video_path):
        """Extract audio (same as before, but uses self.temp_dir)."""
        try:
            if not self.ffmpeg_path:
                print("[video player]Error: ffmpeg not available")
                return None

            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time())}.wav")

            print(f"[video player]Extracting audio to: {temp_audio}")
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

            if result.returncode != 0:
                print(f"[video player]ffmpeg error: {result.stderr}")
                return None

            if os.path.exists(temp_audio):
                return temp_audio
            return None

        except Exception as e:
            print(f"[video player]Audio extraction error: {e}")
            traceback.print_exc()
            return None
        
    def play_video(self, video_path, audio_path, on_complete):
        """Start video playback (creates canvas and thread)."""
        print(f"[video player]play_video: Starting: {video_path}, audio: {audio_path}")
        try:
            # Create video canvas
            self.video_canvas = tk.Canvas(
                self.root,
                width=self.root.winfo_screenwidth(),
                height=self.root.winfo_screenheight(),
                bg="black",
                highlightthickness=0,
            )
            self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.root.update_idletasks()
            self.video_canvas.master.lift(self.video_canvas)


            self.should_stop = False
            self.is_playing = True

            # Start playback thread
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, on_complete),
                daemon=True,
            )
            self.video_thread.start()

        except Exception as e:
            print("[video player]play_video error:")
            traceback.print_exc()
            self.root.after(0, on_complete)

    def stop_video(self):
        """Stop video and audio playback."""
        print("[video player]stop_video called")
        self.should_stop = True
        self.is_playing = False  # Set immediately

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

        if hasattr(self, "video_thread") and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.5)

    def force_stop(self):
        """Force stop for resets."""
        print("[video player]Force stopping")
        self.resetting = True
        self.reset_state()

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            time.sleep(0.1)

        if hasattr(self, "video_thread") and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.2)

        self._force_cleanup()
        self.resetting = False

    def reset_state(self):
        """Reset state variables."""
        print("[video player]Resetting state")
        self.should_stop = True
        self.is_playing = False
        if hasattr(self, "video_thread"):
            delattr(self, "video_thread")
        self.image_item = None

    def _cleanup(self):
        """Clean up and restore."""
        print("[video player]Starting cleanup")
        self.is_playing = False
        self.should_stop = True

        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            time.sleep(0.1)

        try:
            if self.video_canvas:
                if self.video_canvas.winfo_exists():
                    self.video_canvas.delete("all")
                    self.video_canvas.place_forget()
                    self.video_canvas.destroy()
        except tk.TclError:
            pass
        finally:
            self.video_canvas = None
            self.image_item = None  # Reset image item
            if hasattr(self, "on_complete") and self.on_complete:
                self.on_complete()
            if hasattr(self, 'on_complete'):
                del self.on_complete

    def _force_cleanup(self):
        """Cleanup without callbacks (for resets)."""
        print("[video player]Forced cleanup")
        if hasattr(self, "on_complete") and self.on_complete:
            del self.on_complete
        self._cleanup()

    def __del__(self):
        """Cleanup temp directory."""
        try:
            if hasattr(self, "temp_dir") and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                os.rmdir(self.temp_dir)
        except:
            pass