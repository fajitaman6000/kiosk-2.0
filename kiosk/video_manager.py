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
from PyQt5.QtWidgets import QWidget, QLabel, QStackedWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QSize
from PyQt5.QtGui import QImage, QPixmap, QPainter, QTransform

class VideoWidget(QWidget):
    """Custom widget for video display with proper frame handling"""
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_frame = None
        self._current_pixmap = None  # Keep reference to prevent GC
        self.setAttribute(Qt.WA_OpaquePaintEvent)  # Optimization for full repaints
        self.setStyleSheet("background-color: black;")
        
    def updateFrame(self, frame):
        """Update the current frame, maintaining reference"""
        self._current_frame = frame
        if frame is not None:
            # Convert OpenCV frame to QPixmap
            height, width, channel = frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            self._current_pixmap = QPixmap.fromImage(q_image)
        self.update()
        
    def paintEvent(self, event):
        """Custom paint event for proper frame display"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        if self._current_pixmap:
            # Scale pixmap to widget size maintaining aspect ratio
            scaled_pixmap = self._current_pixmap.scaled(
                self.size(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            # Center the pixmap in widget
            x = (self.width() - scaled_pixmap.width()) // 2
            y = (self.height() - scaled_pixmap.height()) // 2
            painter.drawPixmap(x, y, scaled_pixmap)
        else:
            painter.fillRect(self.rect(), Qt.black)
            
    def mousePressEvent(self, event):
        """Handle mouse click events"""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()

class VideoManager(QObject):
    """PyQt5 implementation of video playback with synchronized audio"""
    
    # Signals for state changes
    video_started = pyqtSignal()
    video_stopped = pyqtSignal()
    video_completed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        print("Initializing VideoManager")
        
        # State variables
        self.video_widget = None
        self.is_playing = False
        self.should_stop = False
        self.original_widgets = []
        self.original_widget_info = []
        self._lock = threading.Lock()
        self.temp_dir = tempfile.mkdtemp()
        self.current_audio_path = None
        self.completion_callback = None
        
        # Get ffmpeg path
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        
        # Initialize Pygame mixer
        pygame.mixer.init(frequency=44100)
        self.video_sound_channel = pygame.mixer.Channel(0)
        
        # Create fade timer
        self.fade_timer = QTimer(self)
        self.fade_timer.timeout.connect(self._fade_step)
        self.fade_data = None
        
    def _store_widget_state(self):
        """Store current widget state with proper parent-child relationships"""
        print("Storing widget state")
        self.original_widgets.clear()
        self.original_widget_info.clear()
        
        parent = self.parent()
        if not parent:
            return
            
        for widget in parent.findChildren(QWidget):
            if widget is self.video_widget:
                continue
                
            info = {
                'widget': widget,
                'geometry': widget.geometry(),
                'visible': widget.isVisible(),
                'parent': widget.parent(),
                'stylesheet': widget.styleSheet(),
                'enabled': widget.isEnabled()
            }
            
            self.original_widgets.append(widget)
            self.original_widget_info.append(info)
            widget.hide()
            
    def _create_video_widget(self):
        """Create video display widget with proper initialization"""
        parent = self.parent()
        if not parent:
            raise RuntimeError("VideoManager requires a parent widget")
            
        # Create video widget
        self.video_widget = VideoWidget(parent)
        self.video_widget.setGeometry(parent.rect())
        
        # Connect click handler for solution videos
        self.video_widget.clicked.connect(self._handle_video_click)
        
        self.video_widget.show()
        self.video_widget.raise_()
        
    def _handle_video_click(self):
        """Handle video widget clicks"""
        if hasattr(self, '_video_path') and 'video_solutions' in self._video_path:
            print("Video clicked, stopping solution video")
            self.stop_video()
            
    def extract_audio(self, video_path):
        """Extract audio with proper error handling and cleanup"""
        try:
            if not self.ffmpeg_path:
                print("Error: ffmpeg not available")
                return None
                
            base_name = os.path.splitext(os.path.basename(video_path))[0]
            temp_audio = os.path.join(self.temp_dir, 
                                    f"{base_name}_{int(time.time())}.wav")
            
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
                print(f"ffmpeg error: {result.stderr}")
                return None
                
            return temp_audio if os.path.exists(temp_audio) else None
            
        except Exception as e:
            print(f"Error in audio extraction: {e}")
            traceback.print_exc()
            return None
            
    def play_video(self, video_path, on_complete=None):
        """Start video playback with proper initialization"""
        print(f"\nStarting video playback: {video_path}")
        
        try:
            self.completion_callback = on_complete
            self._video_path = video_path  # Store for click handler
            
            # Fade background music
            self._fade_background_music(0.3)
            
            # Stop any existing playback
            if self.is_playing:
                self.stop_video()
            
            # Store widget state
            self._store_widget_state()
            
            # Create video widget
            self._create_video_widget()
            
            # Reset state
            self.should_stop = False
            self.is_playing = True
            
            # Extract audio
            audio_path = self.extract_audio(video_path)
            self.current_audio_path = audio_path
            
            # Start playback thread
            self.video_thread = threading.Thread(
                target=self._play_video_thread,
                args=(video_path, audio_path, self.completion_callback),
                daemon=True
            )
            self.video_thread.start()
            
            self.video_started.emit()
            
        except Exception as e:
            print("Critical error in play_video:")
            traceback.print_exc()
            self._cleanup()
            if on_complete:
                on_complete()
                
    def _play_video_thread(self, video_path, audio_path, on_complete):
        """Video playback thread with proper synchronization"""
        print("\nVideo thread starting")
        start_time = None
        
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                print(f"Failed to open video: {video_path}")
                return
                
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_time = 1.0 / fps if fps > 0 else 1.0/30.0
            
            # Start audio if available
            if audio_path:
                try:
                    video_sound = pygame.mixer.Sound(audio_path)
                    self.video_sound_channel.play(video_sound)
                    start_time = time.time()
                    print("Started audio playback")
                except Exception as e:
                    print(f"Error starting audio: {e}")
                    audio_path = None
            
            frame_count = 0
            while cap.isOpened() and self.is_playing and not self.should_stop:
                if start_time is not None:
                    elapsed_time = time.time() - start_time
                    target_frame = int(elapsed_time * fps)
                    
                    if target_frame > frame_count + 1:
                        skip_frames = target_frame - frame_count - 1
                        print(f"Skipping {skip_frames} frames to catch up")
                        for _ in range(skip_frames):
                            cap.read()
                            frame_count += 1
                
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                
                # Process frame
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
                
                # Update frame in main thread
                self.video_widget.updateFrame(frame)
                
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
            print("Error in video thread:")
            traceback.print_exc()
        finally:
            print("Cleaning up video thread")
            cap.release()
            
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                
            # Schedule cleanup on main thread
            if self.parent():
                QTimer.singleShot(0, lambda: self._thread_cleanup(on_complete))
                
    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """Fade background music with proper volume control"""
        try:
            if not pygame.mixer.music.get_busy():
                return
                
            current_volume = pygame.mixer.music.get_volume()
            
            self.fade_data = {
                'current_volume': current_volume,
                'target_volume': target_volume,
                'step': 0,
                'total_steps': steps,
                'volume_diff': target_volume - current_volume
            }
            
            interval = int((duration * 1000) / steps)
            self.fade_timer.start(interval)
            
        except Exception as e:
            print(f"Error starting music fade: {e}")
            traceback.print_exc()
            
    def _fade_step(self):
        """Handle individual fade step"""
        try:
            if not self.fade_data or self.should_stop:
                self.fade_timer.stop()
                return
                
            step = self.fade_data['step']
            if step >= self.fade_data['total_steps']:
                pygame.mixer.music.set_volume(self.fade_data['target_volume'])
                self.fade_timer.stop()
                self.fade_data = None
                return
                
            progress = (step + 1) / self.fade_data['total_steps']
            new_volume = (self.fade_data['current_volume'] + 
                         (self.fade_data['volume_diff'] * progress))
            new_volume = max(0.0, min(1.0, new_volume))
            
            pygame.mixer.music.set_volume(new_volume)
            
            self.fade_data['step'] += 1
            
        except Exception as e:
            print(f"Error in fade step: {e}")
            self.fade_timer.stop()
            self.fade_data = None
            
    def _thread_cleanup(self, on_complete=None):
        """Handle cleanup and callbacks on main thread"""
        print("\n=== Video Thread Cleanup ===")
        
        try:
            if self.video_sound_channel.get_busy():
                self.video_sound_channel.stop()
                
            was_stopped_manually = self.should_stop
            
            if pygame.mixer.music.get_busy():
                self._fade_background_music(1.0, duration=0.3)
                
            self._cleanup()
            
            if self.current_audio_path and os.path.exists(self.current_audio_path):
                try:
                    os.remove(self.current_audio_path)
                    self.current_audio_path = None
                except Exception as e:
                    print(f"Error removing temp audio: {e}")
                    
            if not was_stopped_manually:
                if on_complete:
                    QTimer.singleShot(100, on_complete)
                elif self.completion_callback:
                    callback = self.completion_callback
                    self.completion_callback = None
                    QTimer.singleShot(100, callback)
                    
            self.video_completed.emit()
            
        except Exception as e:
            print(f"Error in thread cleanup: {e}")
            traceback.print_exc()
            
    def stop_video(self):
        """Stop video playback with proper cleanup"""
        print("\nStopping video playback")
        self.should_stop = True
        self.is_playing = False
        
        callback = self.completion_callback
        self.completion_callback = None
        
        if self.video_sound_channel.get_busy():
            self.video_sound_channel.stop()
            
        if hasattr(self, 'video_thread') and self.video_thread.is_alive():
            self.video_thread.join(timeout=0.5)
            
        self._cleanup()
        
        if callback:
            QTimer.singleShot(0, callback)
            
        self.video_stopped.emit()
        
    def _cleanup(self):
        """Clean up resources with proper widget restoration"""
        print("\nStarting cleanup")
        try:
            self.is_playing = False
            self.should_stop = True
            
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
                    if widget and not widget.isDestroyed() and widget.parent():
                        # Skip hint-related widgets - let UI class handle these
                        widget_name = widget.objectName().lower()
                        if any(name in widget_name for name in ['hint', 'video_solution', 'help']):
                            continue
                            
                        # Restore widget state
                        widget.setGeometry(info['geometry'])
                        widget.setStyleSheet(info['stylesheet'])
                        widget.setEnabled(info['enabled'])
                        
                        # Restore parent if needed
                        if info['parent'] and widget.parent() != info['parent']:
                            widget.setParent(info['parent'])
                            
                        # Only show if it was originally visible
                        if info['visible']:
                            widget.show()
                            
                except Exception as e:
                    print(f"Error restoring widget: {e}")
                    traceback.print_exc()
                    
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
                
            print("Cleanup complete")
            
        except Exception as e:
            print("\nError during cleanup:")
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
            if hasattr(self, 'fade_timer') and self.fade_timer.isActive():
                self.fade_timer.stop()
                
        except:
            pass