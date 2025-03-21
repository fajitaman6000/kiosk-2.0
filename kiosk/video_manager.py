# video_manager.py
print("[video_manager] Beginning imports ...")
import tkinter as tk
import threading
import time
import traceback
import os
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
from pygame import mixer
import tempfile
import imageio_ffmpeg
from qt_overlay import Overlay  # Keep this import
from video_player import VideoPlayer # Import the VideoPlayer class
import subprocess
print("[video_manager] Ending imports ...")

class VideoManager:
    def __init__(self, root):
        print("[video manager]Initializing VideoManager")
        self.root = root
        self.is_playing = False
        self.should_stop = False
        self.original_widgets = []
        self.original_widget_info = []
        self._lock = threading.Lock()
        self.temp_dir = tempfile.mkdtemp()
        self.current_audio_path = None
        self.completion_callback = None
        self.resetting = False
        self.video_player = None  # Instance of VideoPlayer

        # Get ffmpeg path from imageio-ffmpeg
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"[video manager]Using ffmpeg from: {self.ffmpeg_path}")

        # Initialize Pygame mixer
        pygame.mixer.init(frequency=44100)

    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """Gradually changes background music volume."""
        # (Same implementation as before, no changes needed)
        try:
            if not pygame.mixer.music.get_busy():
                print("[video manager]No background music playing, skipping fade")
                return

            current_volume = pygame.mixer.music.get_volume()
            print(f"[video manager]Starting volume fade from {current_volume} to {target_volume}")

            pygame.mixer.music.set_volume(current_volume)
            time.sleep(0.05)

            volume_diff = target_volume - current_volume
            step_size = volume_diff / steps
            step_duration = duration / steps

            for i in range(steps):
                if self.should_stop:
                    print("[video manager]Video stopped during fade, breaking")
                    break
                next_volume = current_volume + (step_size * (i + 1))
                new_volume = max(0.0, min(1.0, next_volume))
                pygame.mixer.music.set_volume(new_volume)
                print(f"[video manager]Fade step {i+1}/{steps}: Volume set to {new_volume}")
                time.sleep(step_duration)

            pygame.mixer.music.set_volume(target_volume)
            time.sleep(0.05)
            final_volume = pygame.mixer.music.get_volume()
            print(f"[video manager]Fade complete. Final volume: {final_volume}")

        except Exception as e:
            print(f"[video manager]Error fading background music: {e}")
            traceback.print_exc()

    def _check_ffmpeg_in_path(self):
        """Check if ffmpeg is available in system PATH"""
        # (Same implementation as before, no changes needed)
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True)
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            return False

    def play_video(self, video_path, on_complete=None):
        """Play a video file - manages UI and creates VideoPlayer."""
        print(f"[video manager]Starting video playback: {video_path}")

        try:
            self.completion_callback = on_complete

            if self.is_playing:
                print("[video manager]Stopping existing playback")
                self.stop_video()  # Call VideoManager.stop_video

            print("[video manager]Hiding Qt overlays before video start")
            self.root.after(0, Overlay.hide_all_overlays)


            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(1.0)
                time.sleep(0.1)

            self._fade_background_music(0.3)
            print(f"[video manager]Background music volume after fade: {pygame.mixer.music.get_volume() if pygame.mixer.music.get_busy() else 'No music'}")

            print("[video manager]Storing current window state")
            self.original_widgets = []
            self.original_widget_info = []
            for widget in self.root.winfo_children():
                self.original_widgets.append(widget)
                info = {
                    'widget': widget,
                    'geometry_info': None,
                    'manager': None
                }

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


            self.should_stop = False
            self.is_playing = True

            # Instantiate the VideoPlayer
            self.video_player = VideoPlayer(self.root, self.ffmpeg_path)
            # Extract audio (using VideoPlayer's method)
            audio_path = self.video_player.extract_audio(video_path)
            self.current_audio_path = audio_path
            if audio_path:
                print(f"[video manager]Successfully extracted audio to: {audio_path}")
            else:
                print("[video manager]Failed to extract audio")
            # Start playback (using VideoPlayer's method)

            self.video_player.play_video(video_path, audio_path, self._on_player_complete)

        except Exception as e:
            print("[video manager]Critical error in play_video:")
            traceback.print_exc()
            self._cleanup()
            if on_complete:
                self.root.after(0, on_complete)


    def _on_player_complete(self):
        """Callback when VideoPlayer finishes (or is stopped)."""
        self._thread_cleanup(self.completion_callback)

    def _thread_cleanup(self, on_complete=None):
        """Handle cleanup and callbacks on the main thread"""
        print("[video manager]=== Video Manager Thread Cleanup ===")

        if self.resetting:
            print("[video manager]Resetting in progress, skipping normal thread cleanup")
            return
        try:
            Overlay.show_all_overlays()

            was_stopped_manually = self.should_stop

            print("[video manager]Restoring background music volume...")
            if pygame.mixer.music.get_busy():
                current_vol = pygame.mixer.music.get_volume()
                print(f"[video manager]Current music volume before restore: {current_vol}")
                if current_vol > 0.3:
                    pygame.mixer.music.set_volume(0.3)
                self._fade_background_music(1.0, duration=0.3)
                print(f"[video manager]Background music volume after restore: {pygame.mixer.music.get_volume()}")
            else:
                print("[video manager]No background music playing to restore")

            print("[video manager]Starting UI cleanup...")
            self._cleanup()
            print("[video manager]UI cleanup complete")

            # Clean up temporary audio file. Delegate to video player as current audio path is now in there.
            if self.video_player.current_audio_path and os.path.exists(self.video_player.current_audio_path):
                for attempt in range(3):
                    try:
                        time.sleep(0.1 * (attempt + 1))
                        os.remove(self.video_player.current_audio_path)
                        print(f"[video_manager]Removed temporary audio file on attempt {attempt+1}")
                        break;
                    except Exception as e:
                        print(f"[video_manager]Attempt to remove temp file (attempt {attempt+1}): {e}")
                self.video_player.current_audio_path = None

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


    def stop_video(self):
        """Stop video playback - manages UI and stops VideoPlayer."""
        print("[video manager]Stopping video and audio")
        self.should_stop = True
        self.completion_callback = None # Clearing callback.

        if self.video_player:
            self.video_player.stop_video() # Delegate to VideoPlayer


    def force_stop(self):
        """Force stop all video playback and cleanup for reset scenarios."""
        print("[video manager]Force stopping all video playback")
        self.resetting = True
        self._temp_callback = None
        if hasattr(self, 'completion_callback'):
            self.completion_callback = None

        self.reset_state()

        if self.video_player:
            self.video_player.force_stop() # Delegate to VideoPlayer

        self._force_cleanup()
        self.resetting = False


    def reset_state(self):
        """Reset all video manager state variables"""
        print("[video manager]Resetting all VideoManager state")
        self.should_stop = True
        self.is_playing = False
        self.original_widgets = []
        self.original_widget_info = []
        self.current_audio_path = None

        if self.video_player:
             self.video_player.reset_state() # Reset VideoPlayer state

    def _cleanup(self):
        """Clean up video resources and restore UI state."""
        print("[video manager]Starting cleanup")
        self.is_playing = False
        self.should_stop = True

        # Restore original widgets with their original geometry management
        restored_widgets = []
        for info in self.original_widget_info:
            widget = info['widget']
            try:
                if widget.winfo_exists():
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

        self.original_widgets = restored_widgets
        self.original_widget_info = [info for info in self.original_widget_info
                                   if info['widget'] in restored_widgets]

        try:
            self.root.update_idletasks()
            self.root.update()
        except tk.TclError:
            pass

        print("[video manager]Cleanup complete")


    def _force_cleanup(self):
      """Force cleanup resources without executing callbacks (for resets)"""
      print("[video manager]VideoManager: Starting forced cleanup")

      try:
          self.is_playing = False
          self.should_stop = True

          # Clear current state but preserve callback system
          self.original_widgets = []
          self.original_widget_info = []
          self.current_audio_path = None # Resetting audio path.

          # Delegate force cleanup to the VideoPlayer.
          if self.video_player:
              self.video_player._force_cleanup()

          print("[video manager]Forced cleanup complete")
      except Exception as e:
          print(f"[video manager]Error during forced cleanup: {e}")
          traceback.print_exc()

      finally:
          # Restore callback system for future videos
            if hasattr(self, '_temp_callback'):
                self.completion_callback = self._temp_callback
                delattr(self, '_temp_callback')