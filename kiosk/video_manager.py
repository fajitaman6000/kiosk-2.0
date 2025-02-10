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

class VideoManager:
    def __init__(self, root):
        print("[video manager]Initializing VideoManager")
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
        #print(f"[video manager]Using ffmpeg from: {self.ffmpeg_path}")
            
        # Initialize Pygame mixer
        pygame.mixer.init(frequency=44100)
        # Initialize a dedicated channel for video audio
        self.video_sound_channel = pygame.mixer.Channel(0)  # Use channel 0 for video audio

    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """
        Gradually changes background music volume over the specified duration.
        """
        try:
            if not pygame.mixer.music.get_busy():
                print("[video manager]No background music playing, skipping fade")
                return
                
            current_volume = pygame.mixer.music.get_volume()
            print(f"[video manager]Starting volume fade from {current_volume} to {target_volume}")
            
            # Force volume to current value before starting fade
            pygame.mixer.music.set_volume(current_volume)
            time.sleep(0.05)  # Small delay to ensure volume is set
            
            volume_diff = target_volume - current_volume
            step_size = volume_diff / steps
            step_duration = duration / steps
            
            for i in range(steps):
                if self.should_stop:  # Check if video was stopped
                    print("[video manager]Video stopped during fade, breaking")
                    break
                next_volume = current_volume + (step_size * (i + 1))
                new_volume = max(0.0, min(1.0, next_volume))
                pygame.mixer.music.set_volume(new_volume)
                print(f"[video manager]Fade step {i+1}/{steps}: Volume set to {new_volume}")
                time.sleep(step_duration)
                
            # Force final volume
            pygame.mixer.music.set_volume(target_volume)
            time.sleep(0.05)  # Small delay to ensure final volume is set
            
            final_volume = pygame.mixer.music.get_volume()
            print(f"[video manager]Fade complete. Final volume: {final_volume}")
                
        except Exception as e:
            print(f"[video manager]Error fading background music: {e}")
            traceback.print_exc()

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
                print("[video manager]Error: ffmpeg not available")
                return None
                
            # Create unique temp WAV file name using timestamp
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, f"{base_name}_{int(time.time())}.wav")
            
            # Extract audio using ffmpeg
            print(f"[video manager]Extracting audio from video to: {temp_audio}")
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
                print(f"[video manager]ffmpeg error: {result.stderr}")
                return None
                
            if os.path.exists(temp_audio):
                return temp_audio
            return None
            
        except Exception as e:
            print(f"[video manager]Exception during audio extraction: {e}")
            traceback.print_exc()
            return None

    def play_video(self, video_path, on_complete=None):
        """Play a video file in fullscreen with synchronized audio."""
        print(f"[video manager]\nVideoManager: Starting video playback: {video_path}")
        
        try:
            # Store completion callback
            self.completion_callback = on_complete
            
            # Ensure background music is at full volume before fading
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(1.0)
                time.sleep(0.1)  # Small delay to ensure volume is set
            
            # Now fade out background music
            self._fade_background_music(0.3)  # Reduce to 30% volume
            print(f"[video manager]Background music volume after fade: {pygame.mixer.music.get_volume() if pygame.mixer.music.get_busy() else 'No music'}")

            # Stop any existing playback
            if self.is_playing:
                print("[video manager]VideoManager: Stopping existing playback")
                self.stop_video()
            
            # Store current widgets and their layout info
            print("[video manager]VideoManager: Storing current window state")
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
            print("[video manager]VideoManager: Creating video canvas")
            self.video_canvas = tk.Canvas(
                self.root,
                width=self.root.winfo_screenwidth(),
                height=self.root.winfo_screenheight(),
                bg='black',
                highlightthickness=0
            )
            # Use place with relwidth/relheight to ensure full coverage
            self.video_canvas.place(x=0, y=0, relwidth=1, relheight=1)
            
            # Ensure the canvas is on top
            self.root.update_idletasks()
            self.video_canvas.master.lift(self.video_canvas)
            
            # Reset state flags
            self.should_stop = False
            self.is_playing = True

            # Extract audio from video
            audio_path = self.extract_audio(video_path)
            self.current_audio_path = audio_path
            has_audio = audio_path is not None
            
            if has_audio:
                print(f"[video manager]VideoManager: Successfully extracted audio to: {audio_path}")
            else:
                print("[video manager]VideoManager: Failed to extract audio")
            
            print("[video manager]VideoManager: Starting playback thread")
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, self.completion_callback),
                daemon=True
            )
            self.video_thread.start()
            
        except Exception as e:
            print("[video manager]\nVideoManager: Critical error in play_video:")
            traceback.print_exc()
            self._cleanup()
            if on_complete:
                self.root.after(0, on_complete)
            
    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Video playback thread with synchronized audio"""
        print("[video manager]\nVideoManager: Video thread starting")
        start_time = None

        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"[video manager]VideoManager: Failed to open video: {video_path}")
                return

            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_time = 1.0 / fps if fps > 0 else 1.0 / 30.0
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            print(f"[video manager]VideoManager: Video opened successfully. FPS: {fps}")

            # Start audio playback if available
            if audio_path:
                try:
                    # Load audio as a Sound object instead of using music
                    video_sound = pygame.mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    start_time = time.time()
                    print("[video manager]VideoManager: Started audio playback")
                except Exception as e:
                    print(f"[video manager]VideoManager: Error starting audio: {e}")
                    audio_path = None

            # Rest of the method remains exactly the same...
            # Add click handler ONLY for solution videos (which contain 'video_solutions' in their path)
            if 'video_solutions' in video_path:
                def on_canvas_click(event):
                    print("[video manager]VideoManager: Video canvas clicked, stopping solution video playback")
                    self.stop_video()

                self.root.after(0, lambda: self.video_canvas.bind('<Button-1>', on_canvas_click))
                print("[video manager]VideoManager: Added click-to-skip for solution video")
            else:
                print("[video manager]VideoManager: Intro video - skip functionality disabled")

            frame_count = 0
            while cap.isOpened() and self.is_playing and not self.should_stop:
                # Calculate desired frame position based on elapsed time
                if start_time is not None:
                    elapsed_time = time.time() - start_time
                    target_frame = int(elapsed_time * fps)

                    # If we're behind, skip frames to catch up
                    if target_frame > frame_count + 1:
                        skip_frames = target_frame - frame_count - 1
                        print(f"[video manager]Skipping {skip_frames} frames to catch up")
                        for _ in range(skip_frames):
                            cap.read()
                            frame_count += 1

                ret, frame = cap.read()
                if not ret:
                    print("[video manager]VideoManager: End of video reached")
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
            print("[video manager]\nVideoManager: Error in video thread:")
            traceback.print_exc()
        finally:
            print("[video manager]VideoManager: Cleaning up video thread")
            cap.release()

            # Stop video audio channel instead of music
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                time.sleep(0.1)  # Give a small delay for the audio to stop

            # Schedule cleanup and callback on main thread
            self.root.after(0, lambda: self._thread_cleanup(on_complete))
    
    def _thread_cleanup(self, on_complete=None):
        """Handle cleanup and callbacks on the main thread"""
        print("[video manager]\n=== Video Manager Thread Cleanup ===")
        
        try:
            # Stop video audio first (not the background music)
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                time.sleep(0.1)  # Give a small delay for audio to stop

            # Store the should_stop state early
            was_stopped_manually = self.should_stop

            # Ensure background music volume is restored first
            print("[video manager]Restoring background music volume...")
            if pygame.mixer.music.get_busy():
                # Force immediate volume restoration by first ensuring volume is at reduced level
                current_vol = pygame.mixer.music.get_volume()
                print(f"[video manager]Current music volume before restore: {current_vol}")
                if current_vol > 0.3:  # If volume is somehow above our fade level
                    pygame.mixer.music.set_volume(0.3)  # Reset to faded state
                # Now do the fade up
                self._fade_background_music(1.0, duration=0.3)
                print(f"[video manager]Background music volume after restore: {pygame.mixer.music.get_volume()}")
            else:
                print("[video manager]No background music playing to restore")

            # Perform UI cleanup
            print("[video manager]Starting UI cleanup...")
            self._cleanup()
            print("[video manager]UI cleanup complete")

            # Clean up temporary audio file with retries
            if self.current_audio_path and os.path.exists(self.current_audio_path):
                for attempt in range(3):
                    try:
                        time.sleep(0.1 * (attempt + 1))  # Increasing delay between attempts
                        os.remove(self.current_audio_path)
                        print(f"[video manager]Removed temporary audio file on attempt {attempt + 1}")
                        break
                    except Exception as e:
                        print(f"[video manager]Attempt to remove temp file (attempt {attempt + 1}): {e}")
                self.current_audio_path = None

            # Always execute completion callbacks, even if stopped manually
            if on_complete:
                print("[video manager]Executing passed on_complete")
                self.root.after(0, on_complete)
            elif self.completion_callback:
                print("[video manager]Executing stored completion_callback")
                self.root.after(0, self.completion_callback)

            print("[video manager]=== Thread Cleanup Complete ===\n")

        except Exception as e:
            print(f"[video manager]Error in thread cleanup: {e}")
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
            print(f"[video manager]VideoManager: Error updating frame: {e}")
            self.stop_video()
            
    def stop_video(self):
        """Stop video and audio playback"""
        print("[video manager]\nVideoManager: Stopping video and audio")
        self.should_stop = True
        # Do not set self.is_playing to False here - restore original behavior

        # Stop video audio channel instead of music
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()

        # Force stop any ongoing playback
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.5)  # Wait briefly for thread to end
        
    def force_stop(self):
        """Force stop all video playback and cleanup for reset scenarios"""
        print("[video manager]\nVideoManager: Force stopping all video playback")
        
        # Store current state
        self._temp_callback = None
        if hasattr(self, 'completion_callback'):
            self._temp_callback = self.completion_callback
            self.completion_callback = None
        
        # Reset all state flags first
        self.reset_state()
        
        # Immediately stop video audio
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            time.sleep(0.1)  # Small delay to ensure audio stops

        # Force stop thread with a shorter timeout since we're in a reset
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.2)
            if self.video_thread.is_alive():
                print("[video manager]Warning: Video thread did not stop cleanly during reset")

        # Clear video canvas immediately
        if self.video_canvas and self.video_canvas.winfo_exists():
            try:
                self.video_canvas.delete('all')
                self.video_canvas.place_forget()
                self.video_canvas.destroy()
            except tk.TclError:
                pass
            self.video_canvas = None

        # Cancel any pending 'after' callbacks for the current video only
        try:
            if hasattr(self.root, 'after_cancel'):
                # Try to find and cancel any pending after calls
                pending = self.root.tk.call('after', 'info')
                for after_id in pending:
                    try:
                        # Only cancel callbacks related to _thread_cleanup
                        callback_info = self.root.tk.call('after', 'info', after_id)
                        if '_thread_cleanup' in str(callback_info):
                            self.root.after_cancel(after_id)
                    except Exception:
                        pass
        except Exception as e:
            print(f"[video manager]Error canceling callbacks during reset: {e}")

        # Force cleanup without callbacks
        self._force_cleanup()

    def _force_cleanup(self):
        """Clean up resources without executing callbacks - used for resets"""
        print("[video manager]\nVideoManager: Starting forced cleanup")
        try:
            self.is_playing = False
            self.should_stop = True
            
            # Stop only the video audio channel, not the music
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
            
            # Clean up video canvas with additional checks
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
                    
            # Clear current state but preserve callback system
            self.original_widgets = []
            self.original_widget_info = []
            self.current_audio_path = None
            
            print("[video manager]Forced cleanup complete")
            
        except Exception as e:
            print(f"[video manager]Error during forced cleanup: {e}")
            traceback.print_exc()
        finally:
            # Restore callback system for future videos
            if hasattr(self, '_temp_callback'):
                self.completion_callback = self._temp_callback
                delattr(self, '_temp_callback')

    def reset_state(self):
        """Reset all video manager state variables"""
        print("[video manager]Resetting all VideoManager state")
        self.should_stop = True
        self.is_playing = False
        # Don't clear completion_callback here
        self.original_widgets = []
        self.original_widget_info = []
        self.current_audio_path = None
        
        # Clear any stored video-related attributes
        if hasattr(self, 'video_thread'):
            delattr(self, 'video_thread')

    def _cleanup(self):
        """Clean up resources and restore UI state"""
        print("[video manager]\nVideoManager: Starting cleanup")
        try:
            self.is_playing = False
            self.should_stop = True
            
            # Stop only the video audio channel, not the music
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
            
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
                    print(f"[video manager]VideoManager: Error cleaning up canvas: {e}")
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
                    print(f"[video manager]Widget no longer exists, skipping restoration")
                except Exception as e:
                    print(f"[video manager]Error restoring widget: {e}")
            
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
                            time.sleep(0.1)
                            os.remove(self.current_audio_path)
                            print(f"[video manager]Removed temporary audio file: {self.current_audio_path}")
                            break
                    except Exception as e:
                        print(f"[video manager]Attempt to remove temp file failed: {e}")
                        time.sleep(0.1)
                self.current_audio_path = None
                        
            print("[video manager]VideoManager: Cleanup complete")
            
        except Exception as e:
            print("[video manager]\nVideoManager: Error during cleanup:")
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