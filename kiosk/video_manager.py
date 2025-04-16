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
import tempfile # Keep for consistency, though player manages its own temp
import imageio_ffmpeg
from qt_overlay import Overlay # Keep this import
from video_player import VideoPlayer # Import the refactored VideoPlayer
import subprocess
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, QTimer # Import for invoking methods thread-safely

print("[video_manager] Ending imports ...")

class VideoManager:
    def __init__(self, root=None):
        print("[video manager] Initializing VideoManager")
        # root is kept for compatibility but no longer used
        self.root = None
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
            # Check if music is actually playing and mixer is initialized
            if not mixer.get_init() or not mixer.music.get_busy():
                # print("[video manager] No background music playing or mixer not ready, skipping fade.")
                return

            current_volume = mixer.music.get_volume()
            print(f"[video manager] Starting music volume fade from {current_volume:.2f} to {target_volume:.2f}")

            volume_diff = target_volume - current_volume
            if abs(volume_diff) < 0.01: # Already at target
                 mixer.music.set_volume(target_volume) # Ensure exact target
                 print("[video manager] Music volume already at target.")
                 return

            step_size = volume_diff / steps
            step_duration = duration / steps

            for i in range(steps):
                # Check stop flag inside loop for responsiveness
                if self.should_stop and target_volume < current_volume: # Allow fade in even if stopping video
                     print("[video manager] Stop requested during fade out, breaking fade.")
                     break
                next_volume = current_volume + (step_size * (i + 1))
                new_volume = max(0.0, min(1.0, next_volume)) # Clamp volume [0.0, 1.0]
                mixer.music.set_volume(new_volume)
                # print(f"[video manager] Fade step {i+1}/{steps}: Volume set to {new_volume:.2f}") # Debug noise
                time.sleep(step_duration)

            # Ensure final volume is set precisely
            mixer.music.set_volume(target_volume)
            # print(f"[video manager] Fade complete. Final volume: {mixer.music.get_volume():.2f}")

        except pygame.error as e:
             print(f"[video manager] Pygame error during music fade: {e}")
             # Attempt to handle potential mixer issues
             if "mixer not initialized" in str(e):
                 try:
                     pygame.mixer.init(frequency=44100)
                 except: pass # Ignore if re-init fails here
        except Exception as e:
            print(f"[video manager] Error fading background music: {e}")
            traceback.print_exc()


    def play_video(self, video_path, on_complete=None):
        """Play a video file using PyQt overlay for display."""
        print(f"[video manager] play_video requested: {video_path}")
        # --- Ensure Overlay and bridge are initialized ---
        if not Overlay._bridge:
             print("[video manager] Error: Overlay Bridge not initialized. Cannot play video.")
             if on_complete:
                  # Replace root.after with QTimer.singleShot
                  QTimer.singleShot(0, on_complete) # Call completion callback to signal failure
             return

        with self._lock: # Ensure atomic operation for starting playback
            if self.is_playing:
                print("[video manager] Warning: Playback already in progress. Stopping previous.")
                self.stop_video() # Signal stop
                # Consider adding a short wait here if needed for transitions
                time.sleep(0.3) # Give stop a moment

            print(f"[video manager] Starting video playback process for: {video_path}")
            self.is_playing = True
            self.should_stop = False
            self.resetting = False
            self.completion_callback = on_complete # Store the final callback

        try:
            # 1. Hide other overlays (Invoke slot on bridge)
            print("[video manager] Hiding UI elements for video playback...")
            # Use the new safer method that won't cause white screen issues
            QMetaObject.invokeMethod(Overlay._bridge, "hide_overlays_for_video_slot", Qt.QueuedConnection)


            # 2. Fade out background music (can run in this thread)
            print("[video manager] Fading out background music...")
            self._fade_background_music(0.3) # Fade down to 30%

            # 3. Prepare Qt video display (Invoke slot on bridge)
            is_skippable = "video_solutions" in video_path.lower().replace("\\", "/")
            print(f"[video manager] Video skippable: {is_skippable}")

            # Use QueuedConnection for asynchronous preparation. This avoids deadlocks.
            # The update_video_frame_slot has checks to handle frames arriving before
            # preparation is fully complete in the Qt thread.
            QMetaObject.invokeMethod(
                Overlay._bridge, # Target the bridge instance
                "prepare_video_display_slot", # Call the slot
                Qt.QueuedConnection, # <<< CHANGED FROM BlockingQueuedConnection
                # Arguments passed to the slot
                Q_ARG(bool, is_skippable),
                Q_ARG(object, self._handle_video_skip_request) # Pass method reference
            )
            # invokeMethod now returns immediately.

            # 4. Show Qt video display (Invoke slot on bridge) - Keep as Queued
            QMetaObject.invokeMethod(Overlay._bridge, "show_video_display_slot", Qt.QueuedConnection)


            # 5. Instantiate VideoPlayer
            print("[video manager] Instantiating VideoPlayer...")
            # --- Ensure player is created only if bridge calls succeed ---
            self.video_player = VideoPlayer(self.ffmpeg_path)

            # 6. Extract audio (can run in this thread)
            print("[video manager] Extracting audio...")
            audio_path = self.video_player.extract_audio(video_path)
            if audio_path:
                print(f"[video manager] Audio extracted successfully: {audio_path}")
            else:
                print("[video manager] Audio extraction failed or no audio track.")

            # 7. Start VideoPlayer playback (runs its own thread)
            print("[video manager] Starting video player...")
            self.video_player.play_video(
                video_path,
                audio_path,
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
             return # Don't process frames if not playing or bridge missing

        # Use QueuedConnection for asynchronous update
        QMetaObject.invokeMethod(
            Overlay._bridge, # +++ Target the bridge instance +++
            "update_video_frame_slot", # +++ Call the slot +++
            Qt.QueuedConnection,
            Q_ARG(object, frame_data) # Pass the frame data (numpy array)
        )

    def _handle_video_skip_request(self):
        """Callback received from Qt Overlay when video is clicked (if skippable)."""
        print("[video manager] Received video skip request from overlay.")
        # This is called from the Qt GUI thread.
        # Trigger the stop_video logic.
        self.stop_video() # OK to call from GUI thread

    def _on_player_complete(self):
        """Callback received from VideoPlayer when its thread finishes/stops."""
        print("[video manager][CALLBACK_1] _on_player_complete entered (received from VideoPlayer thread).")
        # This might be called from the VideoPlayer's thread.

        # --- Cleanup Trigger Logic --- 
        # If the video completed naturally (should_stop is False), 
        # we need to trigger the cleanup from here.
        # If stop_video was called, it handles the cleanup itself after waiting.
        if not self.should_stop:
            print("[video manager][CALLBACK_NATURAL_COMPLETION] Video finished naturally. Scheduling cleanup via QTimer.")
            # Replace root.after with QTimer.singleShot
            QTimer.singleShot(0, self._perform_post_playback_cleanup)
        else:
            print("[video manager][CALLBACK_STOPPED] Video was stopped manually. Cleanup handled by stop_video.")
        # --- End Cleanup Trigger Logic ---

        print("[video manager][CALLBACK_END] _on_player_complete finished.")

    def _perform_post_playback_cleanup(self):
        """Performs cleanup actions AFTER the player thread has confirmed completion."""
        print("[video manager][CLEANUP_ENTRY] $$$ _perform_post_playback_cleanup HAS BEEN ENTERED $$$")
        print("[video manager][CLEANUP_1] _perform_post_playback_cleanup entered (scheduled by QTimer). ")
        print("[video manager] Performing post-playback cleanup...")
        # --- Check if bridge exists before invoking methods --- 
        print("[video manager][CLEANUP_2] Checking Overlay._bridge.")
        if not Overlay._bridge:
             print("[video manager][CLEANUP_3_FAIL] Cleanup skipped: Overlay bridge missing.")
             # Ensure state is still reset
             print("[video manager][CLEANUP_4_FAIL] Acquiring lock to reset state (bridge missing)." )
             with self._lock:
                  print("[video manager][CLEANUP_5_FAIL] Lock acquired. Resetting state.")
                  self.is_playing = False
                  self.should_stop = True
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None
             print("[video manager][CLEANUP_6_FAIL] Lock released. State reset.")
             return

        print("[video manager][CLEANUP_3] Bridge exists. Acquiring lock...")
        with self._lock:
            print("[video manager][CLEANUP_4] Lock acquired. Checking state.")
            if not self.is_playing and not self.should_stop and not self.resetting:
                 print("[video manager][CLEANUP_5_SKIP] Post-playback cleanup: Already stopped/reset, skipping.")
                 # Lock is released automatically here
                 return
            print("[video manager][CLEANUP_5] State indicates cleanup needed. Setting flags: is_playing=False, should_stop=True")
            self.is_playing = False
            was_stopped_manually = self.should_stop # Maybe log this? print(f"[CLEANUP_5b] was_stopped_manually={was_stopped_manually}")
            self.should_stop = True
            print("[video manager][CLEANUP_6] Lock released.")

        try:
            # 1. Destroy Qt video display (Invoke slot on bridge)
            print("[video manager][CLEANUP_7] Destroying Qt video display (Queued)...")
            # Use QueuedConnection to avoid blocking the Tkinter thread and causing deadlocks.
            # The Qt window will be destroyed asynchronously by the Qt event loop.
            QMetaObject.invokeMethod(
                Overlay._bridge, # Target the bridge instance
                "destroy_video_display_slot", # Call the slot
                Qt.QueuedConnection # <<< CHANGED FROM BlockingQueuedConnection
            )
            print("[video manager][CLEANUP_8] destroy_video_display_slot queued.")
            # Don't print "destroyed" here, as it happens asynchronously now.
            # print("[video manager] Qt video display destruction queued.") # Optional log

            # 2. Restore background music volume (can run here)
            print("[video manager][CLEANUP_9] Restoring background music volume...")
            self._fade_background_music(1.0, duration=0.3)
            print("[video manager][CLEANUP_10] Background music fade initiated/completed.")

            # 3. Show other overlays (Invoke slot on bridge)
            print("[video manager][CLEANUP_11] Restoring non-video overlays (Queued)...")
            # Use QueuedConnection - doesn't need to block
            QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)
            print("[video manager][CLEANUP_12] show_all_overlays_slot queued.")

            # 4. Clean up VideoPlayer instance resources
            print("[video manager][CLEANUP_13] Checking video_player instance.")
            if self.video_player:
                 print("[video manager][CLEANUP_14] Cleaning up video player instance resources...")
                 self.video_player._cleanup_resources() # Explicitly clean temp audio
                 print("[video manager][CLEANUP_15] Video player resources cleaned.")
                 self.video_player = None
                 print("[video manager][CLEANUP_16] Video player instance set to None.")
            else:
                 print("[video manager][CLEANUP_14_SKIP] No video player instance found during cleanup.")


            # 5. Execute the final completion callback IF provided and NOT resetting
            print("[video manager][CLEANUP_17] Checking for final completion callback.")
            final_callback = self.completion_callback
            print(f"[video manager][CLEANUP_18] final_callback = {final_callback}, self.resetting = {self.resetting}")
            self.completion_callback = None # Clear it regardless
            print("[video manager][CLEANUP_19] Set self.completion_callback to None.")

            if final_callback and not self.resetting:
                print(f"[video manager][CLEANUP_20] Scheduling final completion callback via QTimer: {final_callback}")
                try:
                    # Replace root.after with QTimer.singleShot
                    QTimer.singleShot(0, final_callback) # Schedule on Qt thread
                    print("[video manager][CLEANUP_21] Final callback scheduled successfully.")
                except Exception as cb_err:
                    print(f"[video manager][CLEANUP_21_ERR] Error scheduling final completion callback: {cb_err}")
                    traceback.print_exc()
            elif self.resetting:
                 print("[video manager][CLEANUP_20_SKIP] Resetting, skipping final completion callback.")
            else: # Callback was None
                print("[video manager][CLEANUP_20_SKIP] No final callback provided, skipping.")

            print("[video manager][CLEANUP_22] Post-playback cleanup complete.")

        except Exception as e:
            print("[video manager][CLEANUP_ERR] Error during post-playback cleanup:")
            traceback.print_exc()
        finally:
             print("[video manager][CLEANUP_FINALLY_1] Entering finally block.")
             print("[video manager][CLEANUP_FINALLY_2] Acquiring lock...")
             with self._lock:
                  print("[video manager][CLEANUP_FINALLY_3] Lock acquired. Resetting state.")
                  self.is_playing = False
                  self.should_stop = True
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None
                  print("[video manager][CLEANUP_FINALLY_4] State reset.")
             print("[video manager][CLEANUP_FINALLY_5] Lock released. Exiting finally block.")


    def _cleanup_after_error(self):
         """Simplified cleanup specifically for errors during setup."""
         print("[video manager] Cleaning up after setup error...")
         bridge_exists = Overlay._bridge is not None
         with self._lock:
              self.is_playing = False
              self.should_stop = True
              final_callback = self.completion_callback
              self.completion_callback = None

         # Attempt to destroy Qt display if bridge exists
         if bridge_exists:
              QMetaObject.invokeMethod(Overlay._bridge, "destroy_video_display_slot", Qt.BlockingQueuedConnection)
         # Restore music immediately
         if mixer.get_init(): mixer.music.set_volume(1.0)
         # Show other overlays (if bridge exists)
         if bridge_exists:
              QMetaObject.invokeMethod(Overlay._bridge, "show_all_overlays_slot", Qt.QueuedConnection)

         # Cleanup player if instantiated
         if self.video_player:
              self.video_player.force_stop() # Force stop player thread and cleanup
              self.video_player = None

         # Call completion callback
         if final_callback and not self.resetting:
              print("[video manager] Executing completion callback after error.")
              # Replace root.after with QTimer.singleShot
              QTimer.singleShot(0, final_callback)


    def stop_video(self):
        """Stop video playback gracefully."""
        print("[video manager] stop_video called.")
        player_instance = None
        cleanup_needed = False # Flag to track if cleanup should run
        with self._lock:
            if not self.is_playing:
                print("[video manager] Not currently playing.")
                # If should_stop is true, maybe a stop is already in progress
                if self.should_stop:
                     print("[video manager] Stop request already processed or in progress.")
                return

            print("[video manager] Setting flags to stop playback.")
            self.should_stop = True # Signal intent to stop
            # Keep is_playing True until cleanup confirms player stopped
            player_instance = self.video_player # Get reference to signal player
            cleanup_needed = True # Mark that cleanup should happen after player stops

        # Signal the VideoPlayer instance to stop (if it exists)
        # This runs outside the lock to avoid potential deadlocks if player calls back quickly
        if player_instance:
            print("[video manager] Signaling video player instance to stop and waiting...")
            player_instance.stop_video(wait=True) # <<< MODIFIED: Ask the player thread to stop AND WAIT
            print("[video manager] Video player stop_video returned (threads should be joined). ")
            # --- Trigger cleanup directly AFTER player stops --- 
            if cleanup_needed:
                 print("[video manager] Triggering post-playback cleanup directly after player stop.")
                 self._perform_post_playback_cleanup()
            # --- End Trigger --- 
        else:
             print("[video manager] No video player instance to signal stop.")
             # If no player instance, but we were 'playing', trigger cleanup directly
             if cleanup_needed:
                  print("[video manager] No player instance, triggering cleanup directly.")
                  self._perform_post_playback_cleanup()


    def force_stop(self):
        """Force stop all video playback immediately for reset scenarios."""
        print("[video manager] Force stopping all video playback.")
        bridge_exists = Overlay._bridge is not None
        player_instance = None
        with self._lock:
            # Check if there's actually anything happening that needs stopping
            # It's okay to call force_stop multiple times during a reset.
            # if not self.is_playing and not self.should_stop:
            #     print("[video manager] Force stop: Nothing actively playing or stopping.")
                # return # Let's allow it to proceed to ensure cleanup anyway

            print("[video manager] Force stop: Setting state flags.")
            self.resetting = True # Mark as resetting
            self.should_stop = True # Signal any active player to stop
            self.is_playing = False # Assume stopped state immediately
            player_instance = self.video_player # Grab reference before nulling
            self.video_player = None # Clear player reference
            self.completion_callback = None # Clear callback

        try:
            # Stop the player thread if it exists
            if player_instance:
                print("[video manager] Force stopping video player instance...")
                player_instance.force_stop() # Ask player thread to terminate and clean up
            else:
                print("[video manager] Force stop: No player instance found.")

            # Immediately attempt to destroy Qt video display (if bridge exists)
            # Use QueuedConnection because this method (force_stop) might be called
            # from the main thread (via reset handler's root.after)
            if bridge_exists:
                 print("[video manager] Force destroying Qt video display (Queued)...")
                 QMetaObject.invokeMethod(
                     Overlay._bridge,
                     "destroy_video_display_slot",
                     Qt.QueuedConnection # <<< FIX: Use QueuedConnection
                 )
                 # We don't wait for completion here.
                 print("[video manager] Force destroy Qt display request queued.")
            else:
                 print("[video manager] Warning: Bridge missing, cannot destroy Qt display.")

            # Immediately restore music volume
            print("[video manager] Force restoring music volume...")
            if mixer.get_init():
                 mixer.music.set_volume(1.0) # Set volume directly

            # Immediately request showing other overlays (if bridge exists)
            # Use QueuedConnection for safety.
            if bridge_exists:
                 print("[video manager] Force showing non-video overlays (Queued)...")
                 QMetaObject.invokeMethod(
                     Overlay._bridge,
                     "show_all_overlays_slot",
                     Qt.QueuedConnection # <<< FIX: Use QueuedConnection
                 )
                 print("[video manager] Show all overlays request queued.")
            else:
                 print("[video manager] Warning: Bridge missing, cannot show overlays.")

        except Exception as e:
            print(f"[video manager] Error during force_stop cleanup: {e}")
            traceback.print_exc()
        finally:
            # Ensure state is definitely reset even if errors occurred
            with self._lock:
                 self.is_playing = False
                 self.should_stop = True
                 self.resetting = False # Reset the resetting flag after cleanup attempt
                 self.video_player = None
                 self.completion_callback = None
            print("[video manager] Force stop process finished.")

    # --- No longer need UI hiding/restoring logic here ---
    # --- No longer need _cleanup, _force_cleanup, reset_state (handled within play/stop/force_stop) ---