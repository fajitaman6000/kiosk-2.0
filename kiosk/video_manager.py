# video_manager.py
print("[video_manager] Beginning imports ...")
import threading
import time
import traceback
import os
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
from pygame import mixer
# import tempfile # No longer needed here
# import imageio_ffmpeg # No longer needed here for ffmpeg_path
from qt_overlay import Overlay # Keep this import
from video_player import VideoPlayer # Import the refactored VideoPlayer
# import subprocess # No longer needed here
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG # Import for invoking methods thread-safely

print("[video_manager] Ending imports ...")

class VideoManager:
    # Define expected preprocessed file extensions
    PREPROCESSED_VIDEO_EXT = ".avi"
    PREPROCESSED_AUDIO_EXT = ".wav" # Or ".ogg" if you used that in preprocessing

    def __init__(self, root):
        print("[video manager] Initializing VideoManager")
        self.root = root # Keep root for 'root.after'
        self.is_playing = False
        self.should_stop = False
        self._lock = threading.Lock()
        self.completion_callback = None
        self.resetting = False
        self.video_player = None # Instance of VideoPlayer

        # ffmpeg_path is no longer needed by the manager itself
        # self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        # print(f"[video manager] Using ffmpeg from: {self.ffmpeg_path}")

        # Initialize Pygame mixer
        try:
            # Ensure mixer is only initialized once globally if possible
            if not mixer.get_init():
                 pygame.mixer.init(frequency=44100)
                 print("[video manager] Pygame mixer initialized.")
            else:
                 print("[video manager] Pygame mixer already initialized.")
        except pygame.error as mixer_err:
            print(f"[video manager] Warning: Pygame mixer init error: {mixer_err}. Audio might not work.")
            # Attempt re-init or quit/init
            try:
                 pygame.mixer.quit()
                 pygame.mixer.init(frequency=44100)
                 print("[video manager] Pygame mixer re-initialized after error.")
            except Exception as reinit_err:
                 print(f"[video manager] Failed to re-initialize mixer: {reinit_err}")


    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """Gradually changes background music volume."""
        try:
            if not mixer.get_init() or not mixer.music.get_busy():
                return

            current_volume = mixer.music.get_volume()
            # print(f"[video manager] Starting music volume fade from {current_volume:.2f} to {target_volume:.2f}") # Debug noise

            volume_diff = target_volume - current_volume
            if abs(volume_diff) < 0.01:
                 mixer.music.set_volume(target_volume)
                 # print("[video manager] Music volume already at target.") # Debug noise
                 return

            step_size = volume_diff / steps
            step_duration = duration / steps

            for i in range(steps):
                if self.should_stop and target_volume < current_volume:
                     # print("[video manager] Stop requested during fade out, breaking fade.") # Debug noise
                     break
                next_volume = current_volume + (step_size * (i + 1))
                new_volume = max(0.0, min(1.0, next_volume))
                mixer.music.set_volume(new_volume)
                time.sleep(step_duration)

            mixer.music.set_volume(target_volume)
            # print(f"[video manager] Fade complete. Final volume: {mixer.music.get_volume():.2f}") # Debug noise

        except pygame.error as e:
             print(f"[video manager] Pygame error during music fade: {e}")
             if "mixer not initialized" in str(e):
                 try: pygame.mixer.init(frequency=44100)
                 except: pass
        except Exception as e:
            print(f"[video manager] Error fading background music: {e}")
            traceback.print_exc()


    def play_video(self, source_video_path, on_complete=None):
        """
        Play a video file using preprocessed assets.

        Args:
            source_video_path (str): The path to the *original* video file
                                     (e.g., 'path/to/video.mp4'). The manager
                                     will derive the expected preprocessed paths
                                     ('.avi', '.wav') from this.
            on_complete (callable, optional): Callback when playback finishes.
        """
        print(f"[video manager] play_video requested for source: {source_video_path}")

        # --- Derive expected preprocessed file paths ---
        base_name = os.path.splitext(source_video_path)[0]
        expected_video_path = base_name + self.PREPROCESSED_VIDEO_EXT
        expected_audio_path = base_name + self.PREPROCESSED_AUDIO_EXT

        print(f"[video manager] Expecting Video: {expected_video_path}")
        print(f"[video manager] Expecting Audio: {expected_audio_path}")

        # --- Check if preprocessed files exist ---
        if not os.path.exists(expected_video_path):
             print(f"[video manager] ERROR: Preprocessed video file not found: {expected_video_path}")
             print(f"[video manager] Please run the preprocessing script first for {source_video_path}")
             if on_complete:
                 self.root.after(0, on_complete) # Signal failure immediately
             return

        has_audio = True
        if not os.path.exists(expected_audio_path):
             print(f"[video manager] WARNING: Preprocessed audio file not found: {expected_audio_path}. Playing video without audio.")
             has_audio = False
             expected_audio_path = None # Pass None to player

        # --- Ensure Overlay and bridge are initialized ---
        if not Overlay._bridge:
             print("[video manager] Error: Overlay Bridge not initialized. Cannot play video.")
             if on_complete:
                  self.root.after(0, on_complete)
             return

        with self._lock: # Ensure atomic operation for starting playback
            if self.is_playing:
                print("[video manager] Warning: Playback already in progress. Stopping previous.")
                self.stop_video()
                time.sleep(0.3) # Give stop a moment

            print(f"[video manager] Starting video playback process using preprocessed files.")
            self.is_playing = True
            self.should_stop = False
            self.resetting = False
            self.completion_callback = on_complete

        try:
            # 1. Hide other overlays
            print("[video manager] Hiding non-video overlays...")
            QMetaObject.invokeMethod(Overlay._bridge, "hide_all_overlays_slot", Qt.QueuedConnection)

            # 2. Fade out background music
            print("[video manager] Fading out background music...")
            self._fade_background_music(0.3)

            # 3. Prepare Qt video display
            # Determine skippable based on the *original* path for consistency
            is_skippable = "video_solutions" in source_video_path.lower().replace("\\", "/")
            print(f"[video manager] Video skippable: {is_skippable}")
            QMetaObject.invokeMethod(
                Overlay._bridge,
                "prepare_video_display_slot",
                Qt.QueuedConnection,
                Q_ARG(bool, is_skippable),
                Q_ARG(object, self._handle_video_skip_request)
            )

            # 4. Show Qt video display
            QMetaObject.invokeMethod(Overlay._bridge, "show_video_display_slot", Qt.QueuedConnection)

            # 5. Instantiate VideoPlayer (No ffmpeg_path needed)
            print("[video manager] Instantiating VideoPlayer...")
            self.video_player = VideoPlayer()

            # 6. Audio Extraction step is REMOVED

            # 7. Start VideoPlayer playback with preprocessed paths
            print("[video manager] Starting video player...")
            self.video_player.play_video(
                video_path=expected_video_path, # Use the .avi path
                audio_path=expected_audio_path, # Use the .wav/.ogg path (or None)
                frame_update_cb=self._handle_frame_update,
                on_complete_cb=self._on_player_complete
            )
            print("[video manager] Video player started.")

        except Exception as e:
            print("[video manager] Critical error during play_video setup:")
            traceback.print_exc()
            self._cleanup_after_error() # Ensure cleanup on setup failure


    def _handle_frame_update(self, frame_data):
        """Callback received from VideoPlayer with a new frame."""
        if not self.is_playing or self.should_stop or self.resetting or not Overlay._bridge:
             return

        QMetaObject.invokeMethod(
            Overlay._bridge,
            "update_video_frame_slot",
            Qt.QueuedConnection,
            Q_ARG(object, frame_data)
        )

    def _handle_video_skip_request(self):
        """Callback received from Qt Overlay when video is clicked (if skippable)."""
        print("[video manager] Received video skip request from overlay.")
        self.stop_video()

    def _on_player_complete(self):
        """Callback received from VideoPlayer when its thread finishes/stops."""
        print("[video manager] _on_player_complete called (player thread finished).")
        # Schedule the final cleanup on the main Tkinter thread.
        # Use a small delay (e.g., 10ms) to ensure player thread has fully exited
        # before we potentially destroy resources it might touch briefly at the end.
        self.root.after(10, self._perform_post_playback_cleanup)


    def _perform_post_playback_cleanup(self):
        """Performs cleanup actions AFTER the player thread has confirmed completion."""
        print("[video manager] Performing post-playback cleanup...")
        if not Overlay._bridge:
             print("[video manager] Cleanup skipped: Overlay bridge missing.")
             with self._lock: # Still reset state
                  self.is_playing = False
                  self.should_stop = True
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None
             return

        with self._lock:
            if not self.is_playing and not self.should_stop and not self.resetting:
                 print("[video manager] Post-playback cleanup: Already stopped/reset, skipping.")
                 return
            # Now we know the player has stopped, mark manager as not playing
            self.is_playing = False
            was_stopped_manually = self.should_stop
            self.should_stop = True # Ensure stop state is set

        try:
            # 1. Destroy Qt video display
            print("[video manager] Destroying Qt video display...")
            QMetaObject.invokeMethod(
                Overlay._bridge,
                "destroy_video_display_slot",
                Qt.QueuedConnection
            )

            # 2. Restore background music volume
            print("[video manager] Restoring background music volume...")
            self._fade_background_music(1.0, duration=0.3)

            # 3. Show other overlays
            print("[video manager] Restoring non-video overlays...")
            QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)

            # 4. Clean up VideoPlayer instance reference
            # No temporary resources like audio files to clean (_cleanup_resources removed from player)
            if self.video_player:
                 print("[video manager] Releasing video player instance reference...")
                 self.video_player = None # Allow garbage collection
            else:
                 print("[video manager] No video player instance found during cleanup.")

            # 5. Execute the final completion callback
            final_callback = self.completion_callback
            self.completion_callback = None

            if final_callback and not self.resetting:
                print(f"[video manager] Executing final completion callback: {final_callback}")
                try:
                    # Ensure callback runs on the main GUI thread
                    self.root.after(0, final_callback)
                except Exception as cb_err:
                    print(f"[video manager] Error executing final completion callback: {cb_err}")
                    traceback.print_exc()
            elif self.resetting:
                 print("[video manager] Resetting, skipping final completion callback.")

            print("[video manager] Post-playback cleanup complete.")

        except Exception as e:
            print("[video manager] Error during post-playback cleanup:")
            traceback.print_exc()
        finally:
             with self._lock: # Ensure state is consistent after cleanup attempt
                  self.is_playing = False
                  self.should_stop = True
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None


    def _cleanup_after_error(self):
         """Simplified cleanup specifically for errors during setup."""
         print("[video manager] Cleaning up after setup error...")
         bridge_exists = Overlay._bridge is not None
         with self._lock:
              self.is_playing = False
              self.should_stop = True
              final_callback = self.completion_callback
              self.completion_callback = None

         # Attempt to destroy Qt display
         if bridge_exists:
              QMetaObject.invokeMethod(Overlay._bridge, "destroy_video_display_slot", Qt.BlockingQueuedConnection)
         # Restore music
         if mixer.get_init(): mixer.music.set_volume(1.0)
         # Show other overlays
         if bridge_exists:
              QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)

         # Cleanup player if instantiated
         if self.video_player:
              # Use force_stop which is designed for immediate cleanup
              self.video_player.force_stop()
              self.video_player = None

         # Call completion callback
         if final_callback and not self.resetting:
              print("[video manager] Executing completion callback after error.")
              self.root.after(0, final_callback)


    def stop_video(self):
        """Stop video playback gracefully."""
        print("[video manager] stop_video called.")
        player_instance = None
        with self._lock:
            if not self.is_playing:
                # If should_stop is true, a stop is already happening via _on_player_complete
                if not self.should_stop:
                     print("[video manager] Not currently playing and not already stopping.")
                return

            print("[video manager] Setting flags to stop playback.")
            self.should_stop = True # Signal intent to stop
            player_instance = self.video_player # Get reference to signal player outside lock

        if player_instance:
            print("[video manager] Signaling video player instance to stop...")
            # Ask the player thread to stop; it will call _on_player_complete when done
            player_instance.stop_video()
        else:
             print("[video manager] No video player instance to signal stop (may have already completed or errored).")
             # If no player, but we thought we were playing, trigger cleanup directly
             # Ensure it runs on the main thread
             self.root.after(10, self._perform_post_playback_cleanup)


    def force_stop(self):
        """Force stop all video playback immediately for reset scenarios."""
        print("[video manager] Force stopping all video playback.")
        bridge_exists = Overlay._bridge is not None
        player_instance = None
        with self._lock:
            # Check if already stopped/resetting to avoid redundant work
            if not self.is_playing and not self.should_stop and not self.resetting:
                print("[video manager] Force stop: Nothing actively playing or stopping.")
                return

            self.resetting = True # Mark as resetting to prevent completion callback
            self.should_stop = True
            self.is_playing = False # Immediately mark as not playing
            player_instance = self.video_player
            self.video_player = None # Clear reference immediately
            self.completion_callback = None

        try:
            if player_instance:
                print("[video manager] Force stopping video player instance...")
                # Use player's force_stop for immediate thread cleanup attempts
                player_instance.force_stop()
            else:
                print("[video manager] Force stop: No player instance found.")

            # Immediately attempt to destroy Qt video display
            if bridge_exists:
                 print("[video manager] Force destroying Qt video display...")
                 # Use BlockingQueuedConnection here because force_stop should be quick
                 QMetaObject.invokeMethod(Overlay._bridge, "destroy_video_display_slot", Qt.BlockingQueuedConnection)
                 print("[video manager] Force destroy Qt display complete.")

            # Immediately restore music volume
            print("[video manager] Force restoring music volume...")
            if mixer.get_init():
                 mixer.music.set_volume(1.0)

            # Immediately show other overlays
            if bridge_exists:
                 print("[video manager] Force showing non-video overlays...")
                 QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)

        except Exception as e:
            print(f"[video manager] Error during force_stop cleanup: {e}")
            traceback.print_exc()
        finally:
            with self._lock: # Ensure final state is clean
                 self.is_playing = False
                 self.should_stop = True
                 self.resetting = False
                 self.video_player = None
                 self.completion_callback = None
            print("[video manager] Force stop process finished.")