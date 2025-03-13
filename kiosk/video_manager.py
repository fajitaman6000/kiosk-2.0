# video_manager.py
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
from pygame import mixer
from qt_overlay import Overlay

# Enable/disable debug logging (set to False in production)
DEBUG = False

def log(message):
    """Only print logs when DEBUG is enabled"""
    if DEBUG:
        print(f"[video manager]{message}")

class VideoManager:
    def __init__(self, root):
        log("Initializing VideoManager")
        self.root = root
        self.video_canvas = None
        self.is_playing = False
        self.should_stop = False
        self.original_widgets = []
        self.original_widget_info = []
        self._lock = threading.Lock()
        self.temp_dir = tempfile.mkdtemp()
        self.current_audio_path = None
        self.completion_callback = None
        self.resetting = False
        self.frame_buffer = []  # Pre-loaded frames buffer
        self.buffer_size = 10   # Number of frames to buffer
        
        # Get ffmpeg path from imageio-ffmpeg once at initialization
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Initialize Pygame mixer only once
        if not pygame.mixer.get_init():
            pygame.mixer.init(frequency=44100)
        
        # Initialize a dedicated channel for video audio
        self.video_sound_channel = pygame.mixer.Channel(0)

    def _fade_background_music(self, target_volume, duration=0.2, steps=5):
        """Optimized version with fewer steps and checks"""
        try:
            if not pygame.mixer.music.get_busy():
                return

            current_volume = pygame.mixer.music.get_volume()
            
            # Skip fading if volumes are already close
            if abs(current_volume - target_volume) < 0.05:
                pygame.mixer.music.set_volume(target_volume)
                return
                
            volume_diff = target_volume - current_volume
            step_size = volume_diff / steps
            step_duration = duration / steps

            for i in range(steps):
                if self.should_stop:
                    break
                next_volume = current_volume + (step_size * (i + 1))
                new_volume = max(0.0, min(1.0, next_volume))
                pygame.mixer.music.set_volume(new_volume)
                time.sleep(step_duration)

            # Force final volume
            pygame.mixer.music.set_volume(target_volume)

        except Exception as e:
            log(f"Error fading background music: {e}")

    def extract_audio(self, video_path):
        """Extract audio with guaranteed output checking"""
        try:
            if not self.ffmpeg_path or not os.path.exists(video_path):
                log(f"Missing ffmpeg or invalid video path: {video_path}")
                return None

            # Create unique temp WAV file
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time())}.wav")
            
            # Use more reliable ffmpeg settings
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

            # Run ffmpeg command with proper output handling
            process = subprocess.Popen(
                command, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate()
            
            # Verify file exists and has content
            if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
                log(f"Audio extraction successful: {temp_audio}")
                return temp_audio
            else:
                log("Audio extraction failed or created empty file")
                return None

        except Exception as e:
            log(f"Exception during audio extraction: {e}")
            return None

    def play_video(self, video_path, on_complete=None):
        """Play a video file with better performance"""
        log(f"Starting video playback: {video_path}")

        try:
            # Store completion callback
            self.completion_callback = on_complete

            # Stop any existing playback
            if self.is_playing:
                self.stop_video()

            # Hide all Qt overlays before video starts
            self.root.after(0, Overlay.hide_all_overlays)

            # Fade background music with shorter duration
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(1.0)
                self._fade_background_music(0.3, duration=0.1)

            # Store current widgets and their layout info (optimized)
            self.original_widgets = []
            self.original_widget_info = []

            for widget in self.root.winfo_children():
                manager = widget.winfo_manager()
                if not manager:
                    continue
                    
                info = {
                    'widget': widget,
                    'geometry_info': None,
                    'manager': manager
                }

                # Collect geometry info based on manager
                if manager == 'place':
                    info['geometry_info'] = {
                        'x': widget.winfo_x(),
                        'y': widget.winfo_y(),
                        'width': widget.winfo_width(),
                        'height': widget.winfo_height()
                    }
                elif manager == 'grid':
                    info['geometry_info'] = widget.grid_info()
                elif manager == 'pack':
                    info['geometry_info'] = widget.pack_info()

                self.original_widget_info.append(info)
                widget.place_forget()

            # Create video canvas and ensure it covers the full window
            self.video_canvas = tk.Canvas(
                self.root,
                width=self.root.winfo_screenwidth(),
                height=self.root.winfo_screenheight(),
                bg='black',
                highlightthickness=0
            )
            self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            self.root.update_idletasks()

            # Reset state flags
            self.should_stop = False
            self.is_playing = True

            # Pre-process video to determine dimensions once
            self._preprocess_video(video_path)

            # Extract audio from video
            audio_path = self.extract_audio(video_path)
            self.current_audio_path = audio_path

            # Start playback thread
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, self.completion_callback),
                daemon=True
            )
            self.video_thread.start()

        except Exception as e:
            log(f"Critical error in play_video: {e}")
            traceback.print_exc()
            self._cleanup()
            if on_complete:
                self.root.after(0, on_complete)

    def _preprocess_video(self, video_path):
        """Preprocess video to get dimensions and create a small buffer of frames"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return
                
            # Read the first frame to get dimensions
            ret, frame = cap.read()
            if ret:
                self.frame_height, self.frame_width = frame.shape[:2]
                
            # Release the capture object
            cap.release()
        except Exception as e:
            log(f"Error in video preprocessing: {e}")

    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Fixed video playback thread with proper synchronization"""
        log("Video thread starting")
        start_time = None

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                log(f"Failed to open video: {video_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_time = 1.0 / fps if fps > 0 else 1.0 / 30.0
            
            # Start audio playback first - CRITICAL for sync
            if audio_path and os.path.exists(audio_path):
                try:
                    # Ensure audio file is fully ready before playing
                    time.sleep(0.1)  # Small delay to ensure file is accessible
                    video_sound = pygame.mixer.Sound(audio_path)
                    # Set higher volume to ensure audibility
                    video_sound.set_volume(1.0)
                    self.video_sound_channel.play(video_sound)
                    # Set start time AFTER audio begins
                    time.sleep(0.05)  # Small delay to ensure audio started
                    start_time = time.time()
                    log("Started audio playback successfully")
                except Exception as e:
                    log(f"Error starting audio: {e}")
                    traceback.print_exc()
                    audio_path = None
            else:
                log("No audio path available or file doesn't exist")

            # Use frame timestamp from video file for better sync
            frame_count = 0
            while cap.isOpened() and self.is_playing and not self.should_stop and not self.resetting:
                current_time = time.time()
                
                # Simplified frame timing for better stability
                if start_time is not None:
                    elapsed_time = current_time - start_time
                    target_frame = int(elapsed_time * fps)
                    
                    # If we're behind or ahead, adjust playback
                    if frame_count < target_frame - 1:
                        # Skip frames more carefully to catch up
                        skip_count = min(target_frame - frame_count - 1, 5)  # Limit skipping
                        for _ in range(skip_count):
                            cap.read()  # Skip frames
                            frame_count += 1
                    elif frame_count > target_frame + 1:
                        # We're ahead - wait longer
                        time.sleep(0.01)  # Small delay
                        continue  # Skip this iteration
                
                # Read and process frame
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Create PhotoImage and update UI
                image = Image.fromarray(frame)
                photo = ImageTk.PhotoImage(image=image)
                self.root.after(0, self._update_frame, photo)
                
                # Sleep precisely to maintain timing
                if start_time is not None:
                    # Calculate next frame time based on frame count
                    next_frame_time = start_time + (frame_count * frame_time)
                    sleep_time = max(0.001, next_frame_time - time.time())
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                else:
                    # If no audio sync, use consistent frame pacing
                    time.sleep(frame_time)

        except Exception as e:
            log(f"Error in video thread: {e}")
            traceback.print_exc()
        finally:
            log("Cleaning up video thread")
            cap.release()
            
            # Ensure audio is properly stopped
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                
            # Check resetting flag before cleanup
            if not self.resetting:
                self.root.after(0, lambda: self._thread_cleanup(on_complete))

    def _thread_cleanup(self, on_complete=None):
        """Handle cleanup and callbacks with better threading practices"""
        log("=== Video Manager Thread Cleanup ===")

        if self.resetting:
            log("Resetting in progress, skipping normal thread cleanup")
            return

        try:
            # Show all Qt overlays after video ends
            Overlay.show_all_overlays()

            # Stop video audio first
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()

            # Store the should_stop state early
            was_stopped_manually = self.should_stop

            # Restore background music volume
            if pygame.mixer.music.get_busy():
                self._fade_background_music(1.0, duration=0.2)

            # Perform UI cleanup
            self._cleanup()

            # Clean up temporary audio file efficiently
            if self.current_audio_path and os.path.exists(self.current_audio_path):
                try:
                    os.remove(self.current_audio_path)
                except Exception:
                    # Schedule another attempt
                    threading.Timer(0.5, lambda: self._cleanup_temp_file(self.current_audio_path)).start()
                self.current_audio_path = None

            # Execute completion callbacks
            if on_complete:
                self.root.after(0, on_complete)
            elif self.completion_callback:
                self.root.after(0, self.completion_callback)

        except Exception as e:
            log(f"Error in thread cleanup: {e}")
            traceback.print_exc()

    def _cleanup_temp_file(self, file_path):
        """Helper to clean up temp files in background"""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                log(f"Removed temporary file: {file_path}")
            except Exception as e:
                log(f"Failed to remove temp file: {e}")

    def _update_frame(self, photo):
        """Update video frame on canvas efficiently"""
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
            log(f"Error updating frame: {e}")
            self.stop_video()

    def stop_video(self):
        """Stop video and audio playback"""
        log("Stopping video and audio")
        self.should_stop = True
        self.completion_callback = None

        # Stop video audio immediately
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

    def force_stop(self):
        """Force stop all video playback and cleanup for reset scenarios"""
        log("Force stopping all video playback")

        # Set resetting flag to True
        self.resetting = True
        
        # Store current state
        self._temp_callback = None
        if hasattr(self, 'completion_callback'):
            self.completion_callback = None

        # Reset all state flags first
        self.reset_state()

        # Immediately stop video audio
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

        # Force stop thread with shorter timeout
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.2)

        # Clear video canvas immediately
        if self.video_canvas and self.video_canvas.winfo_exists():
            try:
                self.video_canvas.delete('all')
                self.video_canvas.place_forget()
                self.video_canvas.destroy()
            except tk.TclError:
                pass
            self.video_canvas = None

        # Cancel any pending 'after' callbacks efficiently
        try:
            if hasattr(self.root, 'after_cancel'):
                pending = self.root.tk.call('after', 'info')
                for after_id in pending:
                    try:
                        callback_info = self.root.tk.call('after', 'info', after_id)
                        if '_thread_cleanup' in str(callback_info):
                            self.root.after_cancel(after_id)
                    except Exception:
                        pass
        except Exception as e:
            log(f"Error canceling callbacks during reset: {e}")

        # Force cleanup without callbacks
        self._force_cleanup()
        
        # Reset resetting flag
        self.resetting = False

    def _force_cleanup(self):
        """Clean up resources without executing callbacks - used for resets"""
        log("Starting forced cleanup")
        try:
            self.is_playing = False
            self.should_stop = True

            # Stop video audio channel
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()

            # Clean up video canvas efficiently
            if self.video_canvas:
                try:
                    if self.video_canvas.winfo_exists():
                        self.video_canvas.delete('all')
                        self.video_canvas.place_forget()
                        self.video_canvas.destroy()
                except tk.TclError:
                    pass
                finally:
                    self.video_canvas = None

            # Clear current state
            self.original_widgets = []
            self.original_widget_info = []
            self.current_audio_path = None
            # Clear frame buffer to free memory
            if hasattr(self, 'frame_buffer'):
                self.frame_buffer = []

        except Exception as e:
            log(f"Error during forced cleanup: {e}")
        finally:
            # Restore callback system for future videos
            if hasattr(self, '_temp_callback'):
                self.completion_callback = self._temp_callback
                delattr(self, '_temp_callback')

    def reset_state(self):
        """Reset all video manager state variables"""
        log("Resetting all VideoManager state")
        self.should_stop = True
        self.is_playing = False
        self.original_widgets = []
        self.original_widget_info = []
        self.current_audio_path = None
        
        # Clear frame buffer
        self.frame_buffer = []

        # Clear any stored video-related attributes
        if hasattr(self, 'video_thread'):
            delattr(self, 'video_thread')

    def _cleanup(self):
        """Clean up resources and restore UI state efficiently"""
        log("Starting cleanup")
        try:
            self.is_playing = False
            self.should_stop = True

            # Stop only the video audio channel
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()

            # Clean up video canvas efficiently
            if self.video_canvas:
                try:
                    if self.video_canvas.winfo_exists():
                        # Clear all items from canvas first
                        self.video_canvas.delete('all')
                        self.video_canvas.place_forget()
                        self.video_canvas.destroy()
                except tk.TclError:
                    pass
                finally:
                    self.video_canvas = None
                    # Force a single update
                    try:
                        self.root.update()
                    except tk.TclError:
                        pass

            # Restore original widgets more efficiently
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
                except (tk.TclError, AttributeError, KeyError):
                    log("Widget restoration error, skipping")

            # Only keep track of successfully restored widgets
            self.original_widgets = restored_widgets
            self.original_widget_info = [info for info in self.original_widget_info
                                       if info['widget'] in restored_widgets]

            # Force an update with minimal overhead
            try:
                self.root.update_idletasks()
            except tk.TclError:
                pass

            # Clean up temp audio file efficiently
            if self.current_audio_path:
                self._cleanup_temp_file(self.current_audio_path)
                self.current_audio_path = None

        except Exception as e:
            log(f"Error during cleanup: {e}")
        finally:
            # Ensure these are always reset
            self.is_playing = False
            self.should_stop = True
            self.video_canvas = None
            # Clear frame buffer
            self.frame_buffer = []

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