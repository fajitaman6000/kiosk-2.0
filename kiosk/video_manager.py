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
# No longer need tempfile directly here, player manages its own
import imageio_ffmpeg
from qt_overlay import Overlay # Keep this import
from video_player import VideoPlayer # Import the refactored VideoPlayer
import subprocess
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG # Import for invoking methods thread-safely

print("[video_manager] Ending imports ...")

class VideoManager:
    def __init__(self, root):
        print("[video manager] Initializing VideoManager")
        self.root = root # Keep root for 'root.after' for now
        self.is_playing = False
        self.should_stop = False # User/logic requested stop
        self._lock = threading.Lock() # Lock for managing state changes
        self.completion_callback = None # Callback for when playback finishes *and cleanup is done*
        self.resetting = False # Flag for hard resets
        self.video_player = None # Instance of VideoPlayer

        # Get ffmpeg path from imageio-ffmpeg
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"[video manager] Using ffmpeg from: {self.ffmpeg_path}")

        # Initialize Pygame mixer (idempotent)
        try:
            pygame.mixer.init(frequency=44100)
            print("[video manager] Pygame mixer initialized.")
        except pygame.error as mixer_err:
            print(f"[video manager] Warning: Pygame mixer init error: {mixer_err}. Audio might not work.")
            try:
                 pygame.mixer.quit()
                 pygame.mixer.init(frequency=44100)
                 print("[video manager] Pygame mixer re-initialized after error.")
            except Exception as reinit_err:
                 print(f"[video manager] Failed to re-initialize mixer: {reinit_err}")

    # --- _fade_background_music remains the same ---
    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """Gradually changes background music volume."""
        try:
            if not mixer.get_init() or not mixer.music.get_busy():
                return

            current_volume = mixer.music.get_volume()
            # print(f"[video manager] Starting music volume fade from {current_volume:.2f} to {target_volume:.2f}") # Debug Noise

            volume_diff = target_volume - current_volume
            if abs(volume_diff) < 0.01:
                 mixer.music.set_volume(target_volume)
                 # print("[video manager] Music volume already at target.") # Debug Noise
                 return

            step_size = volume_diff / steps
            step_duration = duration / steps

            for i in range(steps):
                if self.should_stop and target_volume < current_volume:
                     # print("[video manager] Stop requested during fade out, breaking fade.") # Debug Noise
                     break
                next_volume = current_volume + (step_size * (i + 1))
                new_volume = max(0.0, min(1.0, next_volume))
                mixer.music.set_volume(new_volume)
                time.sleep(step_duration)

            mixer.music.set_volume(target_volume)
            # print(f"[video manager] Fade complete. Final volume: {mixer.music.get_volume():.2f}") # Debug Noise

        except pygame.error as e:
             print(f"[video manager] Pygame error during music fade: {e}")
             if "mixer not initialized" in str(e):
                 try: pygame.mixer.init(frequency=44100)
                 except: pass
        except Exception as e:
            print(f"[video manager] Error fading background music: {e}")
            traceback.print_exc()


    def play_video(self, video_path, on_complete=None):
        """
        Play a video file, prioritizing pre-transcoded AVI/WAV if available.
        Uses PyQt overlay for display.
        """
        print(f"[video manager] play_video requested: {video_path}")
        if not Overlay._bridge:
             print("[video manager] Error: Overlay Bridge not initialized. Cannot play video.")
             if on_complete:
                  self.root.after(0, on_complete)
             return
        if not os.path.exists(video_path):
            print(f"[video manager] Error: Video file not found: {video_path}")
            if on_complete:
                self.root.after(0, on_complete)
            return

        with self._lock:
            if self.is_playing:
                print("[video manager] Warning: Playback already in progress. Stopping previous.")
                # Signal stop, but don't wait here, let the new play sequence proceed
                # The player itself handles stopping the previous instance if needed
                self.stop_video()
                time.sleep(0.2) # Short pause to allow stop signal processing

            print(f"[video manager] Starting video playback process for: {video_path}")
            self.is_playing = True
            self.should_stop = False
            self.resetting = False
            self.completion_callback = on_complete

        try:
            # --- Instantiate VideoPlayer EARLY ---
            # We need it to potentially extract audio
            print("[video manager] Instantiating VideoPlayer...")
            self.video_player = VideoPlayer(self.ffmpeg_path)

            # --- Determine Video and Audio Paths ---
            video_path_to_use = None
            audio_path_to_use = None
            base_path, _ = os.path.splitext(video_path)
            potential_avi_path = base_path + ".avi"
            potential_wav_path = base_path + ".wav"

            has_avi = os.path.exists(potential_avi_path)
            has_wav = os.path.exists(potential_wav_path)

            if has_avi:
                print(f"[video manager] Found pre-transcoded AVI: {potential_avi_path}")
                video_path_to_use = potential_avi_path
                if has_wav:
                    print(f"[video manager] Found pre-transcoded WAV: {potential_wav_path}")
                    audio_path_to_use = potential_wav_path
                    print("[video manager] Using pre-transcoded AVI and WAV.")
                else:
                    print("[video manager] Pre-transcoded WAV not found. Attempting audio extraction from original MP4.")
                    # Extract audio from the *original* video file to a *temporary* file
                    audio_path_to_use = self.video_player.extract_audio(video_path)
                    if audio_path_to_use:
                        print(f"[video manager] Using pre-transcoded AVI and extracted temp audio: {audio_path_to_use}")
                    else:
                        print("[video manager] Audio extraction failed. Using pre-transcoded AVI without audio.")
            else:
                print("[video manager] Pre-transcoded AVI not found. Using original MP4.")
                video_path_to_use = video_path # Fallback to original
                print("[video manager] Attempting audio extraction from original MP4.")
                # Extract audio from the *original* video file to a *temporary* file
                audio_path_to_use = self.video_player.extract_audio(video_path)
                if audio_path_to_use:
                    print(f"[video manager] Using original MP4 and extracted temp audio: {audio_path_to_use}")
                else:
                    print("[video manager] Audio extraction failed. Using original MP4 without audio.")

            # --- Safety check: Ensure we have a video path ---
            if not video_path_to_use:
                 print("[video manager] CRITICAL ERROR: Could not determine video path to use. Aborting playback.")
                 self._cleanup_after_error()
                 return


            # 1. Hide other overlays
            print("[video manager] Hiding non-video overlays...")
            QMetaObject.invokeMethod(Overlay._bridge, "hide_all_overlays_slot", Qt.QueuedConnection)

            # 2. Fade out background music
            print("[video manager] Fading out background music...")
            self._fade_background_music(0.3)

            # 3. Prepare Qt video display
            # Determine skippability based on the *original* path request
            is_skippable = "video_solutions" in video_path.lower().replace("\\", "/")
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

            # 5. Start VideoPlayer playback using determined paths
            print("[video manager] Starting video player with determined paths...")
            self.video_player.play_video(
                video_path_to_use,      # Use the chosen video file (AVI or MP4)
                audio_path_to_use,      # Use the chosen audio file (WAV or temp extracted WAV)
                frame_update_cb=self._handle_frame_update,
                on_complete_cb=self._on_player_complete
            )
            print("[video manager] Video player started.")


        except Exception as e:
            print("[video manager] Critical error during play_video setup:")
            traceback.print_exc()
            self._cleanup_after_error()


    # --- _handle_frame_update remains the same ---
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

    # --- _handle_video_skip_request remains the same ---
    def _handle_video_skip_request(self):
        """Callback received from Qt Overlay when video is clicked (if skippable)."""
        print("[video manager] Received video skip request from overlay.")
        self.stop_video()

    # --- _on_player_complete remains the same ---
    def _on_player_complete(self):
        """Callback received from VideoPlayer when its thread finishes/stops."""
        print("[video manager] _on_player_complete called (player thread finished).")
        self.root.after(0, self._perform_post_playback_cleanup)

    # --- _perform_post_playback_cleanup remains mostly the same ---
    # The self.video_player._cleanup_resources() call correctly handles
    # cleaning up ONLY temporary extracted audio files.
    def _perform_post_playback_cleanup(self):
        """Performs cleanup actions AFTER the player thread has confirmed completion."""
        print("[video manager] Performing post-playback cleanup...")
        if not Overlay._bridge:
             print("[video manager] Cleanup skipped: Overlay bridge missing.")
             with self._lock:
                  self.is_playing = False
                  self.should_stop = True
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None
             return

        with self._lock:
            # Check if cleanup is still relevant
            if not self.is_playing and not self.should_stop and not self.resetting:
                 # This can happen if stop_video/force_stop already ran AND finished fully
                 # before this scheduled call executes.
                 print("[video manager] Post-playback cleanup: Already stopped/reset, skipping.")
                 return
            # Proceed with cleanup
            self.is_playing = False
            self.should_stop = True # Mark as definitively stopped

        player_instance = self.video_player # Get ref before potentially nulling it

        try:
            # 1. Destroy Qt video display
            print("[video manager] Destroying Qt video display...")
            QMetaObject.invokeMethod(
                Overlay._bridge,
                "destroy_video_display_slot",
                Qt.QueuedConnection # Use QueuedConnection
            )

            # 2. Restore background music volume
            print("[video manager] Restoring background music volume...")
            self._fade_background_music(1.0, duration=0.3)

            # 3. Show other overlays
            print("[video manager] Restoring non-video overlays...")
            QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)

            # 4. Clean up VideoPlayer instance's *temporary* resources
            if player_instance:
                 print("[video manager] Cleaning up video player instance's temporary resources...")
                 # This specifically calls the player's cleanup for temp files
                 player_instance._cleanup_resources()
                 # Don't null self.video_player here yet, might be needed by stop logic if called concurrently
            else:
                 print("[video manager] No video player instance found during cleanup.")

            # 5. Execute the final completion callback
            final_callback = self.completion_callback # Get callback before clearing
            # Clear state under lock
            with self._lock:
                 self.video_player = None # Now safe to clear the instance reference
                 self.completion_callback = None

            if final_callback and not self.resetting:
                print(f"[video manager] Executing final completion callback: {final_callback}")
                try:
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
             # Ensure state is reset even if errors occurred
             with self._lock:
                  self.is_playing = False
                  self.should_stop = True
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None


    # --- _cleanup_after_error remains mostly the same ---
    # force_stop() within it correctly handles player cleanup.
    def _cleanup_after_error(self):
         """Simplified cleanup specifically for errors during setup."""
         print("[video manager] Cleaning up after setup error...")
         bridge_exists = Overlay._bridge is not None
         with self._lock:
              self.is_playing = False
              self.should_stop = True
              final_callback = self.completion_callback
              self.completion_callback = None
              player_instance = self.video_player # Get instance before nulling
              self.video_player = None

         # Attempt to destroy Qt display if bridge exists
         if bridge_exists:
              try:
                # Use Blocking here might be okay as it's an error path, less risk of GUI deadlock
                QMetaObject.invokeMethod(Overlay._bridge, "destroy_video_display_slot", Qt.BlockingQueuedConnection)
              except Exception as qt_err:
                  print(f"[video manager] Error destroying video display after setup error: {qt_err}")

         # Restore music immediately
         if mixer.get_init():
             try: mixer.music.set_volume(1.0)
             except Exception as mix_err: print(f"[video manager] Error setting music volume after setup error: {mix_err}")

         # Show other overlays (if bridge exists)
         if bridge_exists:
              try: QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)
              except Exception as qt_err: print(f"[video manager] Error showing overlays after setup error: {qt_err}")

         # Cleanup player if instantiated
         if player_instance:
              print("[video manager] Force stopping player instance after setup error...")
              player_instance.force_stop() # Force stop player thread and cleanup *its* temp resources

         # Call completion callback
         if final_callback and not self.resetting: # Check resetting flag
              print("[video manager] Executing completion callback after error.")
              try: self.root.after(0, final_callback)
              except Exception as cb_err: print(f"[video manager] Error executing completion callback after error: {cb_err}")
         elif self.resetting:
              print("[video manager] Resetting, skipping completion callback after error.")


    # --- stop_video remains the same ---
    def stop_video(self):
        """Stop video playback gracefully."""
        print("[video manager] stop_video called.")
        player_instance = None
        with self._lock:
            if not self.is_playing:
                if self.should_stop:
                     print("[video manager] Stop request already processed or in progress.")
                else:
                     print("[video manager] Not currently playing.")
                return # Already stopped or stopping

            # Only set should_stop, let _on_player_complete handle is_playing=False
            print("[video manager] Setting flags to signal stop playback.")
            self.should_stop = True
            player_instance = self.video_player

        # Signal the VideoPlayer instance outside the lock
        if player_instance:
            print("[video manager] Signaling video player instance to stop...")
            player_instance.stop_video(wait=False) # Non-blocking signal to player
            # The player completing will trigger _on_player_complete -> _perform_post_playback_cleanup
        else:
             print("[video manager] Stop called, but no video player instance found. Triggering cleanup directly.")
             # If somehow is_playing was true but player is None, force cleanup
             self.root.after(0, self._perform_post_playback_cleanup)


    # --- force_stop remains the same ---
    def force_stop(self):
        """Force stop all video playback immediately for reset scenarios."""
        print("[video manager] Force stopping all video playback.")
        bridge_exists = Overlay._bridge is not None
        player_instance = None
        with self._lock:
            if not self.is_playing and not self.should_stop:
                print("[video manager] Force stop: Nothing to stop.")
                # Reset flags just in case they are in a weird state
                self.resetting = False
                self.should_stop = False
                self.is_playing = False
                return

            print("[video manager] Setting flags for force stop.")
            self.resetting = True # Indicate a forced reset is happening
            self.should_stop = True
            self.is_playing = False # Force state immediately
            player_instance = self.video_player
            self.video_player = None # Clear reference immediately
            self.completion_callback = None # Clear callback

        try:
            if player_instance:
                print("[video manager] Force stopping video player instance...")
                player_instance.force_stop() # Calls player's immediate stop and temp cleanup
            else:
                print("[video manager] Force stop: No player instance found to stop.")

            # Immediately attempt to destroy Qt video display (if bridge exists)
            if bridge_exists:
                 print("[video manager] Force destroying Qt video display...")
                 try:
                     # Blocking might be acceptable here as we are force stopping everything
                     QMetaObject.invokeMethod(Overlay._bridge, "destroy_video_display_slot", Qt.BlockingQueuedConnection)
                     print("[video manager] Force destroy Qt display potentially complete.")
                 except Exception as qt_err:
                     print(f"[video manager] Error force destroying Qt display: {qt_err}")


            # Immediately restore music volume
            print("[video manager] Force restoring music volume...")
            if mixer.get_init():
                 try: mixer.music.set_volume(1.0)
                 except Exception as mix_err: print(f"[video manager] Error force setting music volume: {mix_err}")

            # Immediately show other overlays (if bridge exists)
            if bridge_exists:
                 print("[video manager] Force showing non-video overlays...")
                 try: QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)
                 except Exception as qt_err: print(f"[video manager] Error force showing overlays: {qt_err}")

        except Exception as e:
            print(f"[video manager] Error during force_stop cleanup actions: {e}")
            traceback.print_exc()
        finally:
            # Ensure flags are correctly set after force stop attempt
            with self._lock:
                 self.is_playing = False
                 self.should_stop = True # Leave as true after stop
                 self.resetting = False # Resetting phase is over
                 self.video_player = None
                 self.completion_callback = None
            print("[video manager] Force stop process finished.")