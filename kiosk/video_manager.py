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
        self.original_widget_info = []  # Store complete widget layout info
        self._lock = threading.Lock()
        self.temp_dir = tempfile.mkdtemp()
        self.current_audio_path = None
        self.completion_callback = None
        
        # Get ffmpeg path from imageio-ffmpeg
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        #print(f"Using ffmpeg from: {self.ffmpeg_path}")
            
        # Initialize Pygame mixer
        pygame.mixer.init(frequency=44100)
        #print("Pygame mixer initialized")

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
                
            # Create unique temp WAV file name using timestamp
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time())}.wav")
            
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
        
        try:
            # Store completion callback
            self.completion_callback = on_complete
            
            # Stop any existing playback
            if self.is_playing:
                print("VideoManager: Stopping existing playback")
                self.stop_video()
            
            # Store current widgets and their layout info
            print("VideoManager: Storing current window state")
            self.original_widgets = []
            self.original_widget_info = []
            
            for widget in self.root.winfo_children():
                self.original_widgets.append(widget)
                info = {
                    'widget': widget,
                    'geometry_info': None,
                    'manager': None
                }
                
                # Detect geometry manager
                if widget.winfo_manager():
                    info['manager'] = widget.winfo_manager()
                    if info['manager'] == 'place':
                        info['geometry_info'] = {
                            'x': widget.winfo_x(),
                            'y': widget.winfo_y(),
                            'width': widget.winfo_width(),
                            'height': widget.winfo_height()
                        }
                    elif info['manager'] == 'grid':
                        info['geometry_info'] = widget.grid_info()
                    elif info['manager'] == 'pack':
                        info['geometry_info'] = widget.pack_info()
                
                self.original_widget_info.append(info)
                widget.place_forget()
                
            # Create video canvas and ensure it covers the full window
            print("VideoManager: Creating video canvas")
            self.video_canvas = tk.Canvas(
                self.root,
                width=self.root.winfo_screenwidth(),
                height=self.root.winfo_screenheight(),
                bg='black',
                highlightthickness=0
            )
            # Use place with relwidth/relheight to ensure full coverage
            self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            
            # Ensure the canvas is on top using the proper widget raise method
            self.root.update_idletasks()  # Make sure geometry is updated
            self.video_canvas.master.lift(self.video_canvas)
            
            # Reset state flags
            self.should_stop = False
            self.is_playing = True

            # Extract audio from video
            audio_path = self.extract_audio(video_path)
            self.current_audio_path = audio_path
            has_audio = audio_path is not None
            
            if has_audio:
                print(f"VideoManager: Successfully extracted audio to: {audio_path}")
            else:
                print("VideoManager: Failed to extract audio")
            
            print("VideoManager: Starting playback thread")
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, self.completion_callback),
                daemon=True
            )
            self.video_thread.start()
            
        except Exception as e:
            print("\nVideoManager: Critical error in play_video:")
            traceback.print_exc()
            self._cleanup()
            if on_complete:
                self.root.after(0, on_complete)
            
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
            
            # Add click handler ONLY for solution videos (which contain 'video_solutions' in their path)
            if 'video_solutions' in video_path:
                def on_canvas_click(event):
                    print("VideoManager: Video canvas clicked, stopping solution video playback")
                    self.stop_video()
                    
                self.root.after(0, lambda: self.video_canvas.bind('<Button-1>', on_canvas_click))
                print("VideoManager: Added click-to-skip for solution video")
            else:
                print("VideoManager: Intro video - skip functionality disabled")
            
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
            
            # Stop audio playback
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                time.sleep(0.1)  # Give a small delay for the audio to stop
            
            # Schedule cleanup and callback on main thread
            self.root.after(0, lambda: self._thread_cleanup(on_complete))
    
    def _thread_cleanup(self, on_complete=None):
        """Handle cleanup and callbacks on the main thread"""
        print("\n=== Video Manager Thread Cleanup ===")
        print(f"should_stop flag: {self.should_stop}")
        print(f"on_complete callback present: {on_complete is not None}")
        print(f"stored completion callback present: {self.completion_callback is not None}")
        
        try:
            # Stop audio first
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                time.sleep(0.1)  # Give a small delay for audio to stop
            
            # Store the should_stop state early
            was_stopped_manually = self.should_stop
            
            # Perform UI cleanup
            print("Starting UI cleanup...")
            self._cleanup()
            print("UI cleanup complete")
            
            # Clean up temporary audio file with retries
            if self.current_audio_path and os.path.exists(self.current_audio_path):
                for attempt in range(3):
                    try:
                        time.sleep(0.1 * (attempt + 1))  # Increasing delay between attempts
                        os.remove(self.current_audio_path)
                        print(f"Removed temporary audio file on attempt {attempt + 1}")
                        break
                    except Exception as e:
                        print(f"Error removing temp file (attempt {attempt + 1}): {e}")
                self.current_audio_path = None
            
            # Execute callbacks based on the stored manual stop state
            if not was_stopped_manually and (on_complete or self.completion_callback):
                print("Video completed normally, executing callbacks...")
                if on_complete:
                    print("Executing passed completion callback")
                    self.root.after(100, on_complete)  # Schedule callback with slight delay
                elif self.completion_callback:
                    print("Executing stored completion callback")
                    callback = self.completion_callback
                    self.completion_callback = None  # Clear the callback
                    self.root.after(100, callback)  # Schedule callback with slight delay
            else:
                print(f"Skipping callbacks - Video was stopped manually: {was_stopped_manually}")
            print("=== Thread Cleanup Complete ===\n")
                    
        except Exception as e:
            print(f"Error in thread cleanup: {e}")
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
            print(f"VideoManager: Error updating frame: {e}")
            self.stop_video()
            
    def stop_video(self):
        """Stop video and audio playback"""
        print("\nVideoManager: Stopping video and audio")
        self.should_stop = True
        self.is_playing = False
        
        # Store callback before cleanup
        callback = self.completion_callback
        self.completion_callback = None  # Clear immediately to prevent double execution
        
        # Ensure pygame mixer is properly stopped
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()  # Unload current audio
            except Exception as e:
                print(f"Error stopping pygame mixer: {e}")
            
        # Force stop any ongoing playback
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.5)  # Wait briefly for thread to end
            
        # Clean up UI and resources
        self._cleanup()
        
        # Execute completion callback if it exists
        if callback:
            self.root.after(0, callback)  # Schedule callback on main thread
        
    def _cleanup(self):
        """Clean up resources and restore UI state"""
        print("\nVideoManager: Starting cleanup")
        try:
            self.is_playing = False
            self.should_stop = True
            
            # Stop audio first
            if pygame.mixer.get_init():
                try:
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                except Exception as e:
                    print(f"Error stopping audio: {e}")
            
            # Clean up video canvas with additional checks
            if self.video_canvas:
                try:
                    if self.video_canvas.winfo_exists():
                        # Clear all items from canvas first
                        try:
                            self.video_canvas.delete('all')
                        except tk.TclError:
                            pass
                        
                        # Remove from layout manager
                        try:
                            self.video_canvas.place_forget()
                        except tk.TclError:
                            pass
                            
                        # Ensure canvas is destroyed
                        try:
                            self.video_canvas.destroy()
                        except tk.TclError:
                            pass
                    self.video_canvas = None
                    # Force garbage collection for good measure
                    try:
                        self.root.update()
                    except tk.TclError:
                        pass
                except Exception as e:
                    print(f"VideoManager: Error cleaning up canvas: {e}")
                finally:
                    self.video_canvas = None
            
            # Restore original widgets with their original geometry management
            restored_widgets = []
            for info in self.original_widget_info:
                widget = info['widget']
                try:
                    if widget.winfo_exists():
                        # Skip hint-related widgets - let UI class handle these
                        widget_name = widget.winfo_name() if hasattr(widget, 'winfo_name') else ''
                        if any(name in widget_name.lower() for name in ['hint', 'video_solution', 'help']):
                            continue
                            
                        manager = info['manager']
                        if manager == 'place':
                            widget.place(
                                x=info['geometry_info']['x'],
                                y=info['geometry_info']['y'],
                                width=info['geometry_info']['width'],
                                height=info['geometry_info']['height']
                            )
                            restored_widgets.append(widget)
                        elif manager == 'grid':
                            widget.grid(**info['geometry_info'])
                            restored_widgets.append(widget)
                        elif manager == 'pack':
                            widget.pack(**info['geometry_info'])
                            restored_widgets.append(widget)
                except tk.TclError:
                    print(f"Widget no longer exists, skipping restoration")
                except Exception as e:
                    print(f"Error restoring widget: {e}")
            
            # Only keep track of successfully restored widgets
            self.original_widgets = restored_widgets
            self.original_widget_info = [info for info in self.original_widget_info 
                                       if info['widget'] in restored_widgets]
            
            # Force a complete update of the window with error handling
            try:
                self.root.update_idletasks()
                self.root.update()
            except tk.TclError:
                pass
            
            # Clean up temp audio file
            if self.current_audio_path:
                for _ in range(3):
                    try:
                        if os.path.exists(self.current_audio_path):
                            pygame.mixer.quit()
                            time.sleep(0.1)
                            os.remove(self.current_audio_path)
                            print(f"Removed temporary audio file: {self.current_audio_path}")
                            break
                    except Exception as e:
                        print(f"Attempt to remove temp file failed: {e}")
                        time.sleep(0.1)
                self.current_audio_path = None
            
            # Reinitialize pygame mixer
            try:
                pygame.mixer.init(frequency=44100)
            except Exception as e:
                print(f"Error reinitializing pygame mixer: {e}")
            
            print("VideoManager: Cleanup complete")
            
        except Exception as e:
            print("\nVideoManager: Error during cleanup:")
            traceback.print_exc()
        finally:
            # Ensure these are always reset
            self.is_playing = False
            self.should_stop = True
            self.video_canvas = None

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