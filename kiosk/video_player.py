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
        self.is_playing = False
        self.should_stop = False
        self.resetting = False
        self.video_sound_channel = mixer.Channel(0)  # Initialize here
        self.current_audio_path = None # Initialising it here.
        self.temp_dir = tempfile.mkdtemp()

    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Video playback thread with synchronized audio"""
        print("[video player]Video thread starting")
        start_time = None
        self.on_complete = on_complete # Store for later

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[video player]Failed to open video: {video_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_time = 1.0 / fps if fps > 0 else 1.0 / 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            print(f"[video player]Video opened successfully. FPS: {fps}")

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

            # Add click handler (remains the same)
            if 'video_solutions' in video_path:
                def on_canvas_click(event):
                    print("[video player]Video canvas clicked, stopping solution video playback")
                    self.stop_video() # Calls VideoPlayer.stop_video

                self.root.after(0, lambda: self.video_canvas.bind('<Button-1>', on_canvas_click))
                print("[video player]Added click-to-skip for solution video")
            else:
                print("[video player]Intro video - skip functionality disabled")

            frame_count = 0
            while cap.isOpened() and self.is_playing and not self.should_stop:

                if self.resetting:
                    print("[video player]Resetting flag is True, breaking out of video playback loop")
                    break

                # Calculate desired frame position
                if start_time is not None:
                    elapsed_time = time.time() - start_time
                    target_frame = int(elapsed_time * fps)

                    # If we're behind, skip frames to catch up
                    if target_frame > frame_count + 1:
                        skip_frames = target_frame - frame_count - 1
                        print(f"[video player]Skipping {skip_frames} frames to catch up")
                        for _ in range(skip_frames):
                            cap.read()
                            frame_count += 1

                ret, frame = cap.read()
                if not ret:
                    print("[video player]End of video reached")
                    break

                frame_count += 1

                self._process_frame_and_update(frame)

                # Calculate time until next frame
                if start_time is not None:
                    elapsed = time.time() - start_time
                    target_time = frame_count * frame_time
                    sleep_time = target_time - elapsed

                    if sleep_time > 0:
                        time.sleep(sleep_time)
                else:
                    time.sleep(frame_time)

        except Exception as e:
            print("[video player]Error in video thread:")
            traceback.print_exc()
        finally:
            print("[video player]Cleaning up video thread")
            cap.release()

            # Stop video audio channel instead of music
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                time.sleep(0.1)

            if not self.resetting:
                # self.root.after(0, on_complete)  # Removed direct call
                # Instead, call _cleanup, and call on_complete from there.
                self.root.after(0, self._cleanup)
            else:
                print("[video player]Resetting is True, skipping on_complete")

    def _process_frame_and_update(self, frame):
        """Process the frame and schedule the UI update."""
        try:
            # Convert frame
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Create PhotoImage
            image = Image.fromarray(frame)
            photo = ImageTk.PhotoImage(image=image)

            # Schedule the UI update using after
            self.root.after(0, self._update_frame, photo)

        except Exception as e:
            print(f"[video player]Error processing frame: {e}")
            traceback.print_exc()

    def _update_frame(self, photo):
        """Update video frame on canvas"""
        try:
            if self.video_canvas and self.video_canvas.winfo_exists():
                self.video_canvas.delete("all")
                self.video_canvas.create_image(
                    self.root.winfo_screenwidth()//2,
                    self.root.winfo_screenheight()//2,
                    image=photo,
                    anchor='center'
                )
                self.video_canvas.photo = photo
        except Exception as e:
            print(f"[video player]Error updating frame: {e}")
            self.stop_video() # Call VideoPlayer.stop_video

    def extract_audio(self, video_path):
        """Extract audio from video file to temporary WAV file"""
        try:
            if not self.ffmpeg_path:
                print("[video player]Error: ffmpeg not available")
                return None

            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time())}.wav")

            print(f"[video player]Extracting audio from video to: {temp_audio}")
            command = [
                self.ffmpeg_path,
                '-i', video_path,
                '-vn',
                '-acodec', 'pcm_s16le',
                '-ar', '44100',
                '-ac', '2',
                '-y',
                temp_audio
            ]

            result = subprocess.run(command, capture_output=True, text=True)

            if result.returncode != 0:
                print(f"[video player]ffmpeg error: {result.stderr}")
                return None

            if os.path.exists(temp_audio):
                return temp_audio
            return None

        except Exception as e:
            print(f"[video player]Exception during audio extraction: {e}")
            traceback.print_exc()
            return None
    def play_video(self, video_path, audio_path, on_complete):
        """Start the video playback."""
        print(f"[video player] play_video: Starting video playback: {video_path}, audio_path: {audio_path}, on_complete: {on_complete}")
        try:
            # Create video canvas and ensure it covers the full window
            print("[video player] play_video: Creating video canvas")
            self.video_canvas = tk.Canvas(
                self.root,
                width=self.root.winfo_screenwidth(),
                height=self.root.winfo_screenheight(),
                bg='black',
                highlightthickness=0
            )
            self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)

            # Ensure the canvas is on top
            self.root.update_idletasks()
            self.video_canvas.master.lift(self.video_canvas)

            # Reset State Flags
            self.should_stop = False
            self.is_playing = True
            print(f"[video_player] play_video: is_playing and should_stop flags set.")

            print("[video player] play_video: Starting playback thread")
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, on_complete),
                daemon=True
            )
            self.video_thread.start()

        except Exception as e:
            print("[video player] play_video: Critical error:")
            traceback.print_exc()
            self.root.after(0, on_complete)  # Ensure callback is called on error

    def stop_video(self):
        """Stop video and audio playback"""
        print(f"[video player] stop_video: Called. is_playing: {self.is_playing}, should_stop: {self.should_stop}")
        self.should_stop = True
        self.is_playing = False  # Set immediately

        # Stop video audio channel
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

        # Force stop any ongoing playback
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            print(f"[video player] stop_video: Joining video_thread")
            self.video_thread.join(timeout=0.5)
        else:
            print(f"[video player] stop_video: No active video_thread")

    def force_stop(self):
        """Force stop all video playback and cleanup for reset scenarios"""
        print("[video player]Force stopping all video playback")
        self.resetting = True
        self.reset_state() # Reset the state.

        # Immediately stop video audio
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            time.sleep(0.1)  # Small delay to ensure audio stops

        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.2)
            if self.video_thread.is_alive():
                print("[video player]Warning: Video thread did not stop cleanly during reset")

        self._force_cleanup()
        self.resetting = False

    def reset_state(self):
        """Reset all video player state variables"""
        print("[video player]Resetting all VideoPlayer state")
        self.should_stop = True
        self.is_playing = False

        # Clear any stored video-related attributes
        if hasattr(self, 'video_thread'):
            delattr(self, 'video_thread')


    def _cleanup(self):
        """Clean up video resources and restore canvas if required."""
        print("[video player]Starting cleanup")
        self.is_playing = False
        self.should_stop = True

        # Stop audio
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
            if hasattr(self, "on_complete") and self.on_complete:  # Check for on_complete.
                self.on_complete()  # Call the completion callback here.
            # Remove the on_complete after it's called to avoid multiple invocations
            if hasattr(self, 'on_complete'):
                del self.on_complete

    def _force_cleanup(self):
        """Clean up resources without executing callbacks - used for resets"""
        print("[video player]Starting forced cleanup")
        # Call cleanup, but prevent the callback using del self.on_complete.
        if hasattr(self, "on_complete") and self.on_complete:
            del self.on_complete  # Don't execute callbacks
        self._cleanup() # cleanup and force cleanup are the same for video player.

    def __del__(self):
        """Cleanup temp directory on object destruction"""
        try:
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                os.rmdir(self.temp_dir)
        except:
            pass