import cv2
import os
import threading
import time
import traceback
import tempfile
import subprocess
import imageio_ffmpeg
import pygame
from pygame import mixer
from PyQt5.QtWidgets import QWidget, QLabel
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt5.QtGui import QImage, QPixmap, QPainter

class VideoManager(QObject):
    """
    PyQt5 implementation of the video manager.
    Handles video playback with synchronized audio support.
    
    Key differences from Tkinter version:
    - Uses QObject instead of direct class
    - Implements proper Qt parent-child relationships
    - Uses QTimer for precise timing
    - Integrates with Qt's event system
    """
    
    # Signals for video state changes
    video_started = pyqtSignal()
    video_stopped = pyqtSignal()
    video_completed = pyqtSignal()
    
    def __init__(self, parent=None):
        """Initialize the video manager with parent for Qt memory management"""
        super().__init__(parent)
        print("Initializing VideoManager")
        
        # State variables (maintained from Tkinter version)
        self.video_widget = None
        self.is_playing = False
        self.should_stop = False
        self.original_widgets = []
        self.original_widget_info = []
        self._lock = threading.Lock()
        self.temp_dir = tempfile.mkdtemp()
        self.current_audio_path = None
        self.completion_callback = None
        
        # Get ffmpeg path from imageio-ffmpeg
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Initialize Pygame mixer with same settings as original
        pygame.mixer.init(frequency=44100)
        self.video_sound_channel = pygame.mixer.Channel(0)
        
        # Create QTimer for background music fading
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._fade_step)
        self.fade_data = None
        
    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """Gradually changes background music volume using Qt timer"""
        try:
            if not pygame.mixer.music.get_busy():
                print("No background music playing, skipping fade")
                return
                
            current_volume = pygame.mixer.music.get_volume()
            print(f"Starting volume fade from {current_volume} to {target_volume}")
            
            # Store fade data
            self.fade_data = {
                'current_volume': current_volume,
                'target_volume': target_volume,
                'step': 0,
                'total_steps': steps,
                'volume_diff': target_volume - current_volume
            }
            
            # Start fade timer
            interval = int((duration * 1000) / steps)  # Convert to milliseconds
            self.fade_timer.start(interval)
            
        except Exception as e:
            print(f"Error starting background music fade: {e}")
            traceback.print_exc()
            
    def _fade_step(self):
        """Handle individual fade step via Qt timer"""
        try:
            if not self.fade_data or self.should_stop:
                self.fade_timer.stop()
                return
                
            step = self.fade_data['step']
            if step >= self.fade_data['total_steps']:
                # Force final volume
                pygame.mixer.music.set_volume(self.fade_data['target_volume'])
                self.fade_timer.stop()
                self.fade_data = None
                return
                
            # Calculate new volume
            progress = (step + 1) / self.fade_data['total_steps']
            new_volume = (self.fade_data['current_volume'] + 
                         (self.fade_data['volume_diff'] * progress))
            new_volume = max(0.0, min(1.0, new_volume))
            
            pygame.mixer.music.set_volume(new_volume)
            print(f"Fade step {step + 1}/{self.fade_data['total_steps']}: "
                  f"Volume set to {new_volume}")
            
            self.fade_data['step'] += 1
            
        except Exception as e:
            print(f"Error in fade step: {e}")
            self.fade_timer.stop()
            self.fade_data = None
            
    def extract_audio(self, video_path):
        """Extract audio from video file to temporary WAV file"""
        try:
            if not self.ffmpeg_path:
                print("Error: ffmpeg not available")
                return None
                
            # Create unique temp WAV file
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, 
                                    f"{base_name}_{int(time.time())}.wav")
            
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
            
            result = subprocess.run(command, capture_output=True, text=True)
            
            if result.returncode != 0:
                print(f"ffmpeg error: {result.stderr}")
                return None
                
            return temp_audio if os.path.exists(temp_audio) else None
            
        except Exception as e:
            print(f"Exception during audio extraction: {e}")
            traceback.print_exc()
            return None
            
    def play_video(self, video_path, on_complete=None):
        """Play a video file in fullscreen with synchronized audio"""
        print(f"\nVideoManager: Starting video playback: {video_path}")
        
        try:
            # Store completion callback
            self.completion_callback = on_complete
            
            # Fade background music
            self._fade_background_music(0.3)
            
            # Stop any existing playback
            if self.is_playing:
                print("VideoManager: Stopping existing playback")
                self.stop_video()
            
            # Store widget state
            self._store_widget_state()
            
            # Create video widget
            self._create_video_widget()
            
            # Reset state flags
            self.should_stop = False
            self.is_playing = True
            
            # Extract and prepare audio
            audio_path = self.extract_audio(video_path)
            self.current_audio_path = audio_path
            
            # Start playback thread
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, self.completion_callback),
                daemon=True
            )
            self.video_thread.start()
            
            # Emit signal that video has started
            self.video_started.emit()
            
        except Exception as e:
            print("\nVideoManager: Critical error in play_video:")
            traceback.print_exc()
            self._cleanup()
            if on_complete:
                on_complete()
                
    def _store_widget_state(self):
        """Store current widget state before video playback"""
        print("VideoManager: Storing widget state")
        self.original_widgets = []
        self.original_widget_info = []
        
        parent = self.parent()
        if parent:
            for widget in parent.findChildren(QWidget):
                # Skip the video widget itself
                if widget is self.video_widget:
                    continue
                    
                info = {
                    'widget': widget,
                    'geometry': widget.geometry(),
                    'visible': widget.isVisible(),
                    'parent': widget.parent()
                }
                
                self.original_widgets.append(widget)
                self.original_widget_info.append(info)
                widget.hide()
                
    def _create_video_widget(self):
        """Create the video display widget"""
        parent = self.parent()
        if not parent:
            raise RuntimeError("VideoManager requires a parent widget")
            
        self.video_widget = QLabel(parent)
        self.video_widget.setAlignment(Qt.AlignCenter)
        self.video_widget.setStyleSheet("background-color: black;")
        self.video_widget.setGeometry(parent.rect())
        
        # Add click handler for solution videos
        def on_click(event):
            if hasattr(self, '_video_path') and 'video_solutions' in self._video_path:
                print("VideoManager: Video clicked, stopping solution video")
                self.stop_video()
                
        self.video_widget.mousePressEvent = on_click
        self.video_widget.show()
        self.video_widget.raise_()
        
    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Video playback thread with synchronized audio"""
        print("\nVideoManager: Video thread starting")
        self._video_path = video_path  # Store for click handler
        start_time = None
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"VideoManager: Failed to open video: {video_path}")
                return
                
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_time = 1.0 / fps if fps > 0 else 1.0/30.0
            
            # Start audio if available
            if audio_path:
                try:
                    video_sound = pygame.mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    start_time = time.time()
                    print("VideoManager: Started audio playback")
                except Exception as e:
                    print(f"VideoManager: Error starting audio: {e}")
                    audio_path = None
            
            frame_count = 0
            while cap.isOpened() and self.is_playing and not self.should_stop:
                # Sync to audio if available
                if start_time is not None:
                    elapsed_time = time.time() - start_time
                    target_frame = int(elapsed_time * fps)
                    
                    # Skip frames to catch up if needed
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
                
                # Process frame
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                
                # Convert to Qt image
                height, width, channel = frame.shape
                bytes_per_line = 3 * width
                q_image = QImage(frame.data, width, height, bytes_per_line, 
                               QImage.Format_RGB888)
                
                # Scale to widget size
                if self.video_widget:
                    scaled_pixmap = QPixmap.fromImage(q_image).scaled(
                        self.video_widget.size(),
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                    
                    # Update widget in main thread
                    self.video_widget.setPixmap(scaled_pixmap)
                    
                # Handle frame timing
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
            
            # Stop video audio
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                
            # Clean up on main thread
            if self.parent():
                self.parent().metaObject().invokeMethod(
                    self,
                    '_thread_cleanup',
                    Qt.QueuedConnection,
                    QTimer.singleShot(0, lambda: self._thread_cleanup(on_complete))
                )
                
    def _thread_cleanup(self, on_complete=None):
        """Handle cleanup and callbacks on the main thread"""
        print("\n=== Video Manager Thread Cleanup ===")
        
        try:
            # Stop video audio
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                
            # Store stop state
            was_stopped_manually = self.should_stop
            
            # Restore background music volume
            if pygame.mixer.music.get_busy():
                self._fade_background_music(1.0, duration=0.3)
                
            # Clean up UI
            self._cleanup()
            
            # Clean up temporary audio file
            if self.current_audio_path and os.path.exists(self.current_audio_path):
                try:
                    os.remove(self.current_audio_path)
                    self.current_audio_path = None
                except Exception as e:
                    print(f"Error removing temp audio file: {e}")
                    
            # Execute callbacks if video completed normally
            if not was_stopped_manually:
                if on_complete:
                    QTimer.singleShot(100, on_complete)
                elif self.completion_callback:
                    callback = self.completion_callback
                    self.completion_callback = None
                    QTimer.singleShot(100, callback)
                    
            # Emit completion signal
            self.video_completed.emit()
            
        except Exception as e:
            print(f"Error in thread cleanup: {e}")
            traceback.print_exc()
    
    def stop_video(self):
        """Stop video and audio playback"""
        print("\nVideoManager: Stopping video and audio")
        self.should_stop = True
        self.is_playing = False
        
        # Store callback before cleanup
        callback = self.completion_callback
        self.completion_callback = None
        
        # Stop video audio channel
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            
        # Wait for video thread to end
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.5)
            
        # Clean up UI and resources
        self._cleanup()
        
        # Execute completion callback if it exists
        if callback:
            QTimer.singleShot(0, callback)
            
        # Emit stopped signal
        self.video_stopped.emit()

    def _cleanup(self):
        """Clean up resources and restore UI state"""
        print("\nVideoManager: Starting cleanup")
        try:
            self.is_playing = False
            self.should_stop = True
            
            # Stop video audio
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
            
            # Clean up video widget
            if self.video_widget:
                try:
                    self.video_widget.hide()
                    self.video_widget.deleteLater()
                except Exception as e:
                    print(f"Error cleaning up video widget: {e}")
                finally:
                    self.video_widget = None
            
            # Restore original widgets
            for info in self.original_widget_info:
                widget = info['widget']
                try:
                    if widget and not widget.isDestroyed():
                        # Skip hint-related widgets
                        widget_name = widget.objectName().lower()
                        if any(name in widget_name for name in ['hint', 'video_solution', 'help']):
                            continue
                            
                        # Restore widget state
                        widget.setGeometry(info['geometry'])
                        if info['visible']:
                            widget.show()
                        
                        # Restore parent if needed
                        if info['parent'] and widget.parent() != info['parent']:
                            widget.setParent(info['parent'])
                            
                except Exception as e:
                    print(f"Error restoring widget: {e}")
                    
            # Clear stored widget info
            self.original_widgets.clear()
            self.original_widget_info.clear()
            
            # Force update
            if self.parent():
                self.parent().update()
            
            # Clean up temp audio file
            if self.current_audio_path and os.path.exists(self.current_audio_path):
                try:
                    os.remove(self.current_audio_path)
                    print(f"Removed temporary audio file: {self.current_audio_path}")
                except Exception as e:
                    print(f"Error removing temp file: {e}")
                self.current_audio_path = None
                
            print("VideoManager: Cleanup complete")
            
        except Exception as e:
            print("\nVideoManager: Error during cleanup:")
            traceback.print_exc()
        finally:
            # Ensure these are always reset
            self.is_playing = False
            self.should_stop = True
            self.video_widget = None

    def __del__(self):
        """Cleanup on object destruction"""
        try:
            # Stop any ongoing playback
            if self.is_playing:
                self.stop_video()
            
            # Clean up temp directory
            if hasattr(self, 'temp_dir') and os.path.exists(self.temp_dir):
                for file in os.listdir(self.temp_dir):
                    try:
                        os.remove(os.path.join(self.temp_dir, file))
                    except:
                        pass
                try:
                    os.rmdir(self.temp_dir)
                except:
                    pass
                    
            # Stop fade timer if active
            if self.fade_timer.isActive():
                self.fade_timer.stop()
                
        except:
            pass