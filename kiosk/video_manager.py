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
            # 1. Fade out background music (can run in this thread)
            print("[video manager] Fading out background music...")
            self._fade_background_music(0.3) # Fade down to 30%

            # 2. Prepare Qt video display (Invoke slot on bridge)
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

            # 3. Show Qt video display (Invoke slot on bridge) - Keep as Queued
            QMetaObject.invokeMethod(Overlay._bridge, "show_video_display_slot", Qt.QueuedConnection)

            # 4. Instantiate VideoPlayer
            print("[video manager] Instantiating VideoPlayer...")
            # --- Ensure player is created only if bridge calls succeed ---
            self.video_player = VideoPlayer(self.ffmpeg_path)

            # 5. Extract audio (can run in this thread)
            print("[video manager] Extracting audio...")
            audio_path = self.video_player.extract_audio(video_path)
            if audio_path:
                print(f"[video manager] Audio extracted successfully: {audio_path}")
            else:
                print("[video manager] Audio extraction failed or no audio track.")

            # 6. Start VideoPlayer playback (runs its own thread)
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
        thread_id = threading.get_ident()
        print(f"[video manager][CALLBACK_{thread_id}] +++ _on_player_complete entered (Thread: {thread_id}) +++")
        current_should_stop = self.should_stop # Check state early
        print(f"[video manager][CALLBACK_{thread_id}] Current state: should_stop = {current_should_stop}")

        # --- Cleanup Trigger Logic ---
        if not current_should_stop:
            print(f"[video manager][CALLBACK_{thread_id}] Natural Completion detected. Scheduling cleanup via invokeMethod.")
            with self._lock:
                callback = self.completion_callback
                print(f"[video manager][CALLBACK_{thread_id}] Captured completion_callback: {callback}")
            # Use invokeMethod to ensure the trigger runs in the main Qt thread
            if Overlay._bridge: # Make sure bridge exists
                QMetaObject.invokeMethod(
                    Overlay._bridge, # Target the bridge instance
                    "execute_callback", # Use the generic callback executor slot
                    Qt.QueuedConnection,
                    Q_ARG(object, lambda cb=callback: self._trigger_cleanup_from_main_thread(cb))
                )
                print(f"[video manager][CALLBACK_{thread_id}] Queued _trigger_cleanup_from_main_thread via bridge.")
            else:
                print(f"[video manager][CALLBACK_{thread_id}] !!! ERROR: Overlay._bridge is None, cannot schedule cleanup!")
        else:
            print(f"[video manager][CALLBACK_{thread_id}] Manual Stop detected. Cleanup should be handled by stop_video.")
        # --- End Cleanup Trigger Logic ---

        print(f"[video manager][CALLBACK_{thread_id}] --- _on_player_complete finished (Thread: {thread_id}) ---")

    def _trigger_cleanup_from_main_thread(self, preserved_callback):
        """Intermediate step called by invokeMethod to run cleanup in the main thread."""
        thread_id = threading.get_ident()
        print(f"[video manager][TRIGGER_{thread_id}] +++ _trigger_cleanup_from_main_thread ENTERED (Thread: {thread_id}) +++")
        # Now call the actual cleanup function
        self._perform_post_playback_cleanup(preserved_callback=preserved_callback, trigger_context="NaturalCompletionScheduled")
        print(f"[video manager][TRIGGER_{thread_id}] --- _trigger_cleanup_from_main_thread FINISHED (Thread: {thread_id}) ---")

    def _perform_post_playback_cleanup(self, preserved_callback=None, trigger_context="Unknown"):
        """Performs cleanup actions AFTER the player thread has confirmed completion."""
        thread_id = threading.get_ident()
        print(f"[video manager][CLEANUP_{thread_id}] +++ _perform_post_playback_cleanup ENTERED (Thread: {thread_id}, Trigger: {trigger_context}) +++")
        # --- Check if bridge exists before invoking methods ---
        print(f"[video manager][CLEANUP_{thread_id}] Checking Overlay._bridge...")
        if not Overlay._bridge:
             print(f"[video manager][CLEANUP_{thread_id}] Cleanup ABORTED: Overlay bridge missing.")
             # Ensure state is still reset
             with self._lock:
                  self.is_playing = False
                  self.should_stop = True # Mark as stopped
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None
             print(f"[video manager][CLEANUP_{thread_id}] State reset despite bridge missing.")
             return

        print(f"[video manager][CLEANUP_{thread_id}] Bridge exists. Acquiring lock...")
        final_callback = None
        with self._lock:
            print(f"[video manager][CLEANUP_{thread_id}] Lock acquired. Current state: is_playing={self.is_playing}, should_stop={self.should_stop}, resetting={self.resetting}")
            # This check might prevent cleanup if stop_video ran cleanup AFTER natural completion already started scheduling it.
            # Let's refine this: cleanup should always run if trigger_context is 'StopVideo' or if it was scheduled naturally.
            # if not self.is_playing and not self.should_stop and not self.resetting:
            #      print(f"[video manager][CLEANUP_{thread_id}] Post-playback cleanup: State indicates already stopped/reset, skipping.")
            #      return
            print(f"[video manager][CLEANUP_{thread_id}] Proceeding with cleanup. Setting state: is_playing=False, should_stop=True")
            self.is_playing = False
            self.should_stop = True # Ensure it's marked as stopped

            # Get the callback from instance or use the preserved one
            final_callback = preserved_callback if preserved_callback is not None else self.completion_callback
            self.completion_callback = None  # Clear it immediately
            print(f"[video manager][CLEANUP_{thread_id}] final_callback obtained: {final_callback}")

        print(f"[video manager][CLEANUP_{thread_id}] Lock released.")

        try:
            # 1. Destroy Qt video display (Invoke slot on bridge)
            print(f"[video manager][CLEANUP_{thread_id}] Queuing destroy_video_display_slot...")
            QMetaObject.invokeMethod(
                Overlay._bridge,
                "destroy_video_display_slot",
                Qt.QueuedConnection # Keep as Queued
            )
            print(f"[video manager][CLEANUP_{thread_id}] destroy_video_display_slot queued.")

            # 2. Restore background music volume
            print(f"[video manager][CLEANUP_{thread_id}] Restoring background music...")
            self._fade_background_music(1.0, duration=0.3)
            print(f"[video manager][CLEANUP_{thread_id}] Background music restoration initiated.")

            # 3. Clean up VideoPlayer instance resources
            player_to_clean = self.video_player # Grab ref before nulling
            print(f"[video manager][CLEANUP_{thread_id}] Checking video_player instance ({player_to_clean})...")
            if player_to_clean:
                 print(f"[video manager][CLEANUP_{thread_id}] Cleaning up video player instance resources ({player_to_clean})...")
                 player_to_clean._cleanup_resources()
                 self.video_player = None # Null the reference AFTER cleanup
                 print(f"[video manager][CLEANUP_{thread_id}] Video player instance cleaned and set to None.")
            else:
                 print(f"[video manager][CLEANUP_{thread_id}] No video player instance found during cleanup.")

            # 4. Execute the final completion callback IF provided and NOT resetting
            print(f"[video manager][CLEANUP_{thread_id}] Checking final callback. Callback = {final_callback}, Resetting = {self.resetting}")
            if final_callback and not self.resetting:
                print(f"[video manager][CLEANUP_{thread_id}] Scheduling final completion callback via QTimer (100ms delay): {final_callback}")
                try:
                    QTimer.singleShot(100, final_callback) # Keep the delay for now
                    print(f"[video manager][CLEANUP_{thread_id}] Final callback scheduled successfully with delay.")
                except Exception as cb_err:
                    print(f"[video manager][CLEANUP_{thread_id}] Error scheduling final completion callback: {cb_err}")
                    traceback.print_exc()
            elif self.resetting:
                 print(f"[video manager][CLEANUP_{thread_id}] Resetting flag is True, skipping final completion callback.")
            else: # Callback was None
                print(f"[video manager][CLEANUP_{thread_id}] No final callback provided, skipping.")

        except Exception as e:
            print(f"[video manager][CLEANUP_{thread_id}] !!! Error during post-playback cleanup:")
            traceback.print_exc()
        finally:
             # Ensure state is reset even if errors occurred during cleanup steps
             print(f"[video manager][CLEANUP_{thread_id}] Entering finally block for state reset.")
             with self._lock:
                  print(f"[video manager][CLEANUP_{thread_id}] (Finally) Lock acquired. Resetting state.")
                  self.is_playing = False
                  self.should_stop = True # Ensure stopped state
                  self.resetting = False
                  self.video_player = None # Ensure player is None
                  self.completion_callback = None # Ensure callback is None
                  print(f"[video manager][CLEANUP_{thread_id}] (Finally) State reset completed.")
             print(f"[video manager][CLEANUP_{thread_id}] Lock released.")
             print(f"[video manager][CLEANUP_{thread_id}] --- _perform_post_playback_cleanup FINISHED (Thread: {thread_id}) ---")


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
        thread_id = threading.get_ident()
        print(f"[video manager][STOP_{thread_id}] +++ stop_video called (Thread: {thread_id}) +++")
        player_instance = None
        cleanup_needed = False
        with self._lock:
            print(f"[video manager][STOP_{thread_id}] Lock acquired. Current state: is_playing={self.is_playing}, should_stop={self.should_stop}")
            if not self.is_playing:
                print(f"[video manager][STOP_{thread_id}] Stop ignored: Not currently playing.")
                if self.should_stop:
                     print(f"[video manager][STOP_{thread_id}] Stop ignored: Stop request already processed or in progress.")
                return

            print(f"[video manager][STOP_{thread_id}] Setting should_stop = True")
            self.should_stop = True # Signal intent to stop FIRST
            player_instance = self.video_player # Get reference to signal player
            cleanup_needed = True # Mark that cleanup should happen after player stops
            print(f"[video manager][STOP_{thread_id}] Player instance: {player_instance}, Cleanup needed: {cleanup_needed}")

        print(f"[video manager][STOP_{thread_id}] Lock released.")

        # Signal the VideoPlayer instance to stop (if it exists)
        if player_instance:
            print(f"[video manager][STOP_{thread_id}] Signaling video player instance ({player_instance}) to stop and waiting...")
            player_instance.stop_video(wait=True) # Ask the player thread to stop AND WAIT
            print(f"[video manager][STOP_{thread_id}] Video player stop_video returned (threads should be joined).")
            # --- Trigger cleanup directly AFTER player stops ---
            if cleanup_needed:
                 print(f"[video manager][STOP_{thread_id}] Triggering post-playback cleanup directly...")
                 # Pass context to cleanup function
                 self._perform_post_playback_cleanup(trigger_context="StopVideo")
                 print(f"[video manager][STOP_{thread_id}] Post-playback cleanup triggered.")
            else:
                 # This case should ideally not happen if we got here, but log it.
                 print(f"[video manager][STOP_{thread_id}] Warning: Player instance existed, but cleanup_needed was False?")
        else:
             print(f"[video manager][STOP_{thread_id}] No video player instance to signal stop.")
             # If no player instance, but we were 'playing' according to the initial check, trigger cleanup directly
             if cleanup_needed:
                  print(f"[video manager][STOP_{thread_id}] No player instance, but cleanup_needed is True. Triggering cleanup directly...")
                  self._perform_post_playback_cleanup(trigger_context="StopVideoNoInstance")
                  print(f"[video manager][STOP_{thread_id}] Post-playback cleanup triggered.")
             else:
                 print(f"[video manager][STOP_{thread_id}] No player instance and cleanup_needed is False. Nothing to do.")

        print(f"[video manager][STOP_{thread_id}] --- stop_video finished (Thread: {thread_id}) ---")


    def force_stop(self):
        """Force stop all video playback immediately for reset scenarios."""
        print("[video manager] Force stopping all video playback.")
        bridge_exists = Overlay._bridge is not None
        player_instance = None
        with self._lock:
            print("[video manager] Force stop: Setting state flags.")
            self.resetting = True # Mark as resetting
            self.should_stop = True # Signal any active player to stop
            self.is_playing = False # Assume stopped state immediately
            player_instance = self.video_player # Grab reference before nulling
            self.video_player = None # Clear player reference
            self.completion_callback = None # Clear callback
        
        try:
            # Step 1: Stop the player thread if it exists
            if player_instance:
                print("[video manager] Force stopping video player instance...")
                player_instance.force_stop() # Ask player thread to terminate and clean up
            else:
                print("[video manager] Force stop: No player instance found.")
            
            # Step 2: Restore music volume immediately
            print("[video manager] Force restoring music volume...")
            if mixer.get_init():
                 mixer.music.set_volume(1.0) # Set volume directly
            
            # Step 3: Just destroy the video display, no need for other UI manipulation
            if bridge_exists:
                print("[video manager] Force destroying video display (Queued)...")
                QMetaObject.invokeMethod(
                    Overlay._bridge,
                    "destroy_video_display_slot",
                    Qt.QueuedConnection
                )
                print("[video manager] Video display destroy request queued.")
            else:
                print("[video manager] Warning: Bridge missing, cannot destroy video display.")

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