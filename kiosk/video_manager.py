import cv2
import tkinter as tk
from PIL import Image, ImageTk
import threading
import time
import traceback
import os
import pygame
import subprocess
import tempfile
import sys
import imageio_ffmpeg

class VideoManager:
    def __init__(self, root):
        print("Initializing VideoManager")
        self.root = root
        self.video_canvas = None
        self.is_playing = False
        self.should_stop = False
        self.original_widgets = []
        self._lock = threading.Lock()
        self.temp_dir = tempfile.mkdtemp()
        
        # Get ffmpeg path from imageio-ffmpeg
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"Using ffmpeg from: {self.ffmpeg_path}")
            
        # Initialize Pygame mixer
        pygame.mixer.init(frequency=44100)
        print("Pygame mixer initialized")

    def _check_ffmpeg_in_path(self):
        """Check if ffmpeg is available in system PATH"""
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def extract_audio(self, video_path):
        """Extract audio from video file to temporary WAV file"""
        try:
            if not self.ffmpeg_path:
                print("Error: ffmpeg not available")
                return None
                
            # Create unique temp WAV file name
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}.wav")
            
            # Extract audio using ffmpeg
            print(f"Extracting audio from video to: {temp_audio}")
            command = [
                self.ffmpeg_path,
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # PCM 16-bit output
                '-ar', '44100',  # 44.1kHz sample rate
                '-ac', '2',  # Stereo
                '-y',  # Overwrite output file
                temp_audio
            ]
            
            # Run ffmpeg command and capture output
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"ffmpeg error: {result.stderr}")
                return None
                
            if os.path.exists(temp_audio):
                return temp_audio
            return None
            
        except Exception as e:
            print(f"Exception during audio extraction: {e}")
            traceback.print_exc()
            return None

    def play_video(self, video_path, on_complete=None):
        """Play a video file in fullscreen with synchronized audio."""
        print(f"\nVideoManager: Starting video playback: {video_path}")
        
        if not os.path.exists(video_path):
            print(f"VideoManager: Error - Video file not found: {video_path}")
            return
            
        try:
            # Stop any existing playback
            if self.is_playing:
                print("VideoManager: Stopping existing playback")
                self.stop_video()
            
            # Store and hide current widgets
            print("VideoManager: Storing current window state")
            self.original_widgets = [w for w in self.root.winfo_children()]
            for widget in self.original_widgets:
                try:
                    widget.place_forget()
                except Exception as e:
                    print(f"VideoManager: Warning - Could not hide widget: {e}")
            
            # Create video canvas
            print("VideoManager: Creating video canvas")
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            
            self.video_canvas = tk.Canvas(
                self.root,
                width=screen_width,
                height=screen_height,
                bg='black',
                highlightthickness=0
            )
            self.video_canvas.place(x=0, y=0)
            
            # Reset state flags
            self.should_stop = False
            self.is_playing = True

            # Extract audio from video
            audio_path = self.extract_audio(video_path)
            has_audio = audio_path is not None
            
            if has_audio:
                print(f"VideoManager: Successfully extracted audio to: {audio_path}")
            else:
                print("VideoManager: Failed to extract audio")
            
            print("VideoManager: Starting playback thread")
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, on_complete),
                daemon=True
            )
            self.video_thread.start()
            
        except Exception as e:
            print("\nVideoManager: Critical error in play_video:")
            traceback.print_exc()
            self._cleanup()
            
    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Video playback thread with synchronized audio"""
        print("\nVideoManager: Video thread starting")
        start_time = None
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"VideoManager: Failed to open video: {video_path}")
                return
                
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_time = 1.0 / fps if fps > 0 else 1.0/30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            
            print(f"VideoManager: Video opened successfully. FPS: {fps}")
            
            # Start audio playback if available
            if audio_path:
                try:
                    pygame.mixer.music.load(audio_path)
                    pygame.mixer.music.play()
                    start_time = time.time()
                    print("VideoManager: Started audio playback")
                except Exception as e:
                    print(f"VideoManager: Error starting audio: {e}")
                    audio_path = None
            
            frame_count = 0
            while cap.isOpened() and self.is_playing and not self.should_stop:
                # Calculate desired frame position based on elapsed time
                if start_time is not None:
                    elapsed_time = time.time() - start_time
                    target_frame = int(elapsed_time * fps)
                    
                    # If we're behind, skip frames to catch up
                    if target_frame > frame_count + 1:
                        skip_frames = target_frame - frame_count - 1
                        print(f"Skipping {skip_frames} frames to catch up")
                        for _ in range(skip_frames):
                            cap.read()
                            frame_count += 1
                
                ret, frame = cap.read()
                if not ret:
                    print("VideoManager: End of video reached")
                    break
                
                frame_count += 1
                
                # Convert frame
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                frame = cv2.resize(frame, (
                    self.root.winfo_screenwidth(),
                    self.root.winfo_screenheight()
                ))
                
                # Create PhotoImage
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image=image)
                
                # Update canvas in main thread
                self.root.after(0, self._update_frame, photo)
                
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
            print("\nVideoManager: Error in video thread:")
            traceback.print_exc()
        finally:
            print("VideoManager: Cleaning up video thread")
            cap.release()
            if audio_path:
                pygame.mixer.music.stop()
                try:
                    # Clean up temporary audio file
                    os.remove(audio_path)
                    print(f"Removed temporary audio file: {audio_path}")
                except Exception as e:
                    print(f"Error removing temp audio file: {e}")
            if not self.should_stop and on_complete:
                print("VideoManager: Calling completion callback")
                self.root.after(0, on_complete)
            self.root.after(0, self._cleanup)
    
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
            print(f"VideoManager: Error updating frame: {e}")
            self.stop_video()
            
    def stop_video(self):
        """Stop video and audio playback"""
        print("\nVideoManager: Stopping video and audio")
        self.should_stop = True
        self.is_playing = False
        pygame.mixer.music.stop()
        self._cleanup()
        
    def _cleanup(self):
        """Clean up resources"""
        print("\nVideoManager: Starting cleanup")
        try:
            self.is_playing = False
            self.should_stop = True
            
            # Stop audio
            pygame.mixer.music.stop()
            
            # Hide video canvas
            if self.video_canvas:
                try:
                    self.video_canvas.place_forget()
                    self.video_canvas = None
                except Exception as e:
                    print(f"VideoManager: Error hiding canvas: {e}")
            
            # Restore original widgets
            for widget in self.original_widgets:
                try:
                    widget.place(x=widget.winfo_x(), y=widget.winfo_y())
                except Exception as e:
                    print(f"VideoManager: Error restoring widget: {e}")
                    
            self.original_widgets = []
            print("VideoManager: Cleanup complete")
            
        except Exception as e:
            print("\nVideoManager: Error during cleanup:")
            traceback.print_exc()

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