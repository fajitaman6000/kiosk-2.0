# video_manager.py
print("[video_manager] Beginning imports ...", flush=True)
print("[video_manager] Importing threading...", flush=True)
import threading
print("[video_manager] Imported threading.", flush=True)
print("[video_manager] Importing time...", flush=True)
import time
print("[video_manager] Imported time.", flush=True)
print("[video_manager] Importing traceback...", flush=True)
import traceback
print("[video_manager] Imported traceback.", flush=True)
print("[video_manager] Importing os...", flush=True)
import os
print("[video_manager] Imported os.", flush=True)
print("[video_manager] Importing environ from os...", flush=True)
from os import environ
print("[video_manager] Imported environ from os.", flush=True)
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
print("[video_manager] Importing pygame...", flush=True)
import pygame
print("[video_manager] Imported pygame.", flush=True)
print("[video_manager] Importing mixer from pygame...", flush=True)
from pygame import mixer
print("[video_manager] Imported mixer from pygame.", flush=True)
print("[video_manager] Importing tempfile...", flush=True)
import tempfile # Keep for consistency, though player manages its own temp
print("[video_manager] Imported tempfile.", flush=True)
print("[video_manager] Importing imageio_ffmpeg...", flush=True)
import imageio_ffmpeg
print("[video_manager] Imported imageio_ffmpeg.", flush=True)
print("[video_manager] Importing Overlay from qt_overlay...", flush=True)
from qt_overlay import Overlay # Keep this import
print("[video_manager] Imported Overlay from qt_overlay.", flush=True)
print("[video_manager] Importing VideoPlayer from video_player...", flush=True)
from video_player import VideoPlayer # Import the refactored VideoPlayer
print("[video_manager] Imported VideoPlayer from video_player.", flush=True)
print("[video_manager] Importing subprocess...", flush=True)
import subprocess
print("[video_manager] Imported subprocess.", flush=True)
print("[video_manager] Importing Qt classes from PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, QTimer # Import for invoking methods thread-safely
print("[video_manager] Imported Qt classes from PyQt5.QtCore.", flush=True)

print("[video_manager] Ending imports ...", flush=True)

class VideoManager:
    def __init__(self, root=None):
        print("[video manager] Initializing VideoManager", flush=True)
        # root is kept for compatibility but no longer used
        self.root = None
        self.is_playing = False
        self.should_stop = False # User/logic requested stop
        self._lock = threading.Lock() # Lock for managing state changes
        self.completion_callback = None # Callback for when playback finishes *and cleanup is done*
        self.resetting = False # Flag for hard resets
        self.video_player = None # Instance of VideoPlayer

        # Get ffmpeg path from imageio-ffmpeg
        print("[video manager] Getting ffmpeg path from imageio-ffmpeg...", flush=True)
        self.ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        print(f"[video manager] Using ffmpeg from: {self.ffmpeg_path}", flush=True)

        # Initialize Pygame mixer (idempotent)
        try:
            print("[video manager] Initializing Pygame mixer...", flush=True)
            pygame.mixer.init(frequency=44100, buffer=4096)
            print("[video manager] Pygame mixer initialized.", flush=True)
        except pygame.error as mixer_err:
            print(f"[video manager] Warning: Pygame mixer init error: {mixer_err}. Audio might not work.", flush=True)
            # Attempt re-init or quit/init
            try:
                 print("[video manager] Attempting mixer re-initialization...", flush=True)
                 pygame.mixer.quit()
                 pygame.mixer.init(frequency=44100, buffer=4096)
                 print("[video manager] Pygame mixer re-initialized after error.", flush=True)
            except Exception as reinit_err:
                 print(f"[video manager] Failed to re-initialize mixer: {reinit_err}", flush=True)
        
        print("[video manager] VideoManager initialization complete.", flush=True)


    def _fade_background_music(self, target_volume, duration=0.2, steps=10):
        """Gradually changes background music volume."""
        try:
            # Check if music is actually playing and mixer is initialized
            if not mixer.get_init() or not mixer.music.get_busy():
                # print("[video manager] No background music playing or mixer not ready, skipping fade.")
                return

            current_volume = mixer.music.get_volume()
            print(f"[video manager] Starting music volume fade from {current_volume:.2f} to {target_volume:.2f}", flush=True)

            volume_diff = target_volume - current_volume
            if abs(volume_diff) < 0.01: # Already at target
                 mixer.music.set_volume(target_volume) # Ensure exact target
                 print("[video manager] Music volume already at target.", flush=True)
                 return

            step_size = volume_diff / steps
            step_duration = duration / steps

            for i in range(steps):
                # Check stop flag inside loop for responsiveness
                if self.should_stop and target_volume < current_volume: # Allow fade in even if stopping video
                     print("[video manager] Stop requested during fade out, breaking fade.", flush=True)
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
             print(f"[video manager] Pygame error during music fade: {e}", flush=True)
             # Attempt to handle potential mixer issues
             if "mixer not initialized" in str(e):
                 try:
                     print("[video manager] Attempting to re-initialize mixer...", flush=True)
                     pygame.mixer.init(frequency=44100)
                     print("[video manager] Mixer re-initialized.", flush=True)
                 except: pass # Ignore if re-init fails here
        except Exception as e:
            print(f"[video manager] Error fading background music: {e}", flush=True)
            traceback.print_exc()


    def play_video(self, video_path, on_complete=None):
        """Play a video file using PyQt overlay for display."""
        print(f"[video manager] play_video requested: {video_path}", flush=True)
        # --- Ensure Overlay and bridge are initialized ---
        if not Overlay._bridge:
             print("[video manager] Error: Overlay Bridge not initialized. Cannot play video.", flush=True)
             if on_complete:
                  # Replace root.after with QTimer.singleShot
                  QTimer.singleShot(0, on_complete) # Call completion callback to signal failure
             return

        with self._lock: # Ensure atomic operation for starting playback
            print(f"[video manager][PLAY_VIDEO] Checking state. Current state: is_playing={self.is_playing}, should_stop={self.should_stop}, resetting={self.resetting}", flush=True)
            if self.is_playing:
                print("[video manager][PLAY_VIDEO] Warning: Playback already in progress. Forcing stop of previous video.", flush=True)
                # Perform force_stop while holding the lock to ensure atomicity
                bridge_exists = Overlay._bridge is not None
                player_instance = self.video_player
                
                print("[video manager][PLAY_VIDEO] Setting state for cleanup...", flush=True)
                self.resetting = True # Mark as resetting
                self.should_stop = True # Signal any active player to stop
                self.is_playing = False # Assume stopped state immediately
                self.video_player = None # Clear player reference
                self.completion_callback = None # Clear callback
                
                # Release lock before potentially blocking operations
                self._lock.release()
                try:
                    # Stop player if it exists
                    if player_instance:
                        print(f"[video manager][PLAY_VIDEO] Force stopping video player instance: {player_instance}...", flush=True)
                        player_instance.force_stop()
                        print(f"[video manager][PLAY_VIDEO] Video player force_stop completed.", flush=True)
                    
                    # Force destroy video display
                    if bridge_exists:
                        print("[video manager][PLAY_VIDEO] Force destroying video display (Auto connection)...", flush=True)
                        QMetaObject.invokeMethod(
                            Overlay._bridge,
                            "destroy_video_display_slot",
                            Qt.AutoConnection  # CHANGED: Let Qt decide based on thread context
                        )
                        print("[video manager][PLAY_VIDEO] Video display destroy request sent.", flush=True)
                        # Add a small delay to allow Qt events to process
                        time.sleep(0.1)
                        print("[video manager][PLAY_VIDEO] Waited for Qt event processing.", flush=True)
                finally:
                    # Re-acquire lock
                    self._lock.acquire()
                    
            # Reset state for new playback (regardless of whether we had to force stop)
            print(f"[video manager][PLAY_VIDEO] Starting new video playback process for: {video_path}", flush=True)
            self.is_playing = True
            self.should_stop = False
            self.resetting = False # Ensure resetting is false for the new playback
            self.completion_callback = on_complete # Store the final callback
            print(f"[video manager][PLAY_VIDEO] New state set: is_playing=True, should_stop=False, resetting=False", flush=True)

        try:
            # 1. Fade out background music (can run in this thread)
            print("[video manager] Fading out background music...", flush=True)
            self._fade_background_music(0.3) # Fade down to 30%

            # 2. Prepare Qt video display (Invoke slot on bridge)
            is_skippable = "video_solutions" in video_path.lower().replace("\\", "/")
            print(f"[video manager] Video skippable: {is_skippable}", flush=True)

            # Use QueuedConnection for asynchronous preparation. This avoids deadlocks.
            # The update_video_frame_slot has checks to handle frames arriving before
            # preparation is fully complete in the Qt thread.
            print("[video manager] Invoking prepare_video_display_slot...", flush=True)
            QMetaObject.invokeMethod(
                Overlay._bridge, # Target the bridge instance
                "prepare_video_display_slot", # Call the slot
                Qt.QueuedConnection, # <<< CHANGED FROM BlockingQueuedConnection
                # Arguments passed to the slot
                Q_ARG(bool, is_skippable),
                Q_ARG(object, self._handle_video_skip_request) # Pass method reference
            )
            print("[video manager] prepare_video_display_slot invoked.", flush=True)
            # invokeMethod now returns immediately.

            # 3. Show Qt video display (Invoke slot on bridge) - Keep as Queued
            print("[video manager] Invoking show_video_display_slot...", flush=True)
            QMetaObject.invokeMethod(Overlay._bridge, "show_video_display_slot", Qt.QueuedConnection)
            print("[video manager] show_video_display_slot invoked.", flush=True)

            # 4. Instantiate VideoPlayer
            print("[video manager] Instantiating VideoPlayer...", flush=True)
            # --- Ensure player is created only if bridge calls succeed ---
            self.video_player = VideoPlayer(self.ffmpeg_path)
            print("[video manager] VideoPlayer instantiated.", flush=True)

            # 5. Extract audio (can run in this thread)
            print("[video manager] Extracting audio...", flush=True)
            audio_path = self.video_player.extract_audio(video_path)
            if audio_path:
                print(f"[video manager] Audio extracted successfully: {audio_path}", flush=True)
            else:
                print("[video manager] Audio extraction failed or no audio track.", flush=True)

            # 6. Start VideoPlayer playback (runs its own thread)
            print("[video manager] Starting video player...", flush=True)
            self.video_player.play_video(
                video_path,
                audio_path,
                frame_update_cb=self._handle_frame_update,
                on_complete_cb=self._on_player_complete
            )
            print("[video manager] Video player started.", flush=True)


        except Exception as e:
            print("[video manager] Critical error during play_video setup:", flush=True)
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
        print("[video manager] Received video skip request from overlay.", flush=True)
        # This is called from the Qt GUI thread.
        # Trigger the stop_video logic.
        self.stop_video() # OK to call from GUI thread

    def _on_player_complete(self):
        """Callback received from VideoPlayer when its thread finishes/stops."""
        thread_id = threading.get_ident()
        print(f"[video manager][CALLBACK_{thread_id}] +++ _on_player_complete entered (Thread: {thread_id}) +++", flush=True)
        
        # Check both should_stop and resetting flags
        current_should_stop = self.should_stop
        current_resetting = self.resetting
        print(f"[video manager][CALLBACK_{thread_id}] Current state: should_stop = {current_should_stop}, resetting = {current_resetting}", flush=True)

        # --- Cleanup Trigger Logic ---
        if not current_should_stop and not current_resetting:
            print(f"[video manager][CALLBACK_{thread_id}] Natural Completion detected. Scheduling cleanup via invokeMethod.", flush=True)
            with self._lock:
                callback = self.completion_callback
                print(f"[video manager][CALLBACK_{thread_id}] Captured completion_callback: {callback}", flush=True)
            # Use invokeMethod to ensure the trigger runs in the main Qt thread
            if Overlay._bridge: # Make sure bridge exists
                QMetaObject.invokeMethod(
                    Overlay._bridge, # Target the bridge instance
                    "execute_callback", # Use the generic callback executor slot
                    Qt.QueuedConnection,
                    Q_ARG(object, lambda cb=callback: self._trigger_cleanup_from_main_thread(cb))
                )
                print(f"[video manager][CALLBACK_{thread_id}] Queued _trigger_cleanup_from_main_thread via bridge.", flush=True)
            else:
                print(f"[video manager][CALLBACK_{thread_id}] !!! ERROR: Overlay._bridge is None, cannot schedule cleanup!", flush=True)
        else:
            print(f"[video manager][CALLBACK_{thread_id}] Manual Stop or Reset detected (should_stop={current_should_stop}, resetting={current_resetting}). Skipping natural completion.", flush=True)
            print(f"[video manager][CALLBACK_{thread_id}] Cleanup should be handled by stop_video or force_stop.", flush=True)
        # --- End Cleanup Trigger Logic ---

        print(f"[video manager][CALLBACK_{thread_id}] --- _on_player_complete finished (Thread: {thread_id}) ---", flush=True)

    def _trigger_cleanup_from_main_thread(self, preserved_callback):
        """Intermediate step called by invokeMethod to run cleanup in the main thread."""
        thread_id = threading.get_ident()
        print(f"[video manager][TRIGGER_{thread_id}] +++ _trigger_cleanup_from_main_thread ENTERED (Thread: {thread_id}) +++", flush=True)
        # Now call the actual cleanup function
        self._perform_post_playback_cleanup(preserved_callback=preserved_callback, trigger_context="NaturalCompletionScheduled")
        print(f"[video manager][TRIGGER_{thread_id}] --- _trigger_cleanup_from_main_thread FINISHED (Thread: {thread_id}) ---", flush=True)

    def _perform_post_playback_cleanup(self, preserved_callback=None, trigger_context="Unknown"):
        """Performs cleanup actions AFTER the player thread has confirmed completion."""
        thread_id = threading.get_ident()
        print(f"[video manager][CLEANUP_{thread_id}] +++ _perform_post_playback_cleanup ENTERED (Thread: {thread_id}, Trigger: {trigger_context}) +++", flush=True)
        # --- Check if bridge exists before invoking methods ---
        print(f"[video manager][CLEANUP_{thread_id}] Checking Overlay._bridge...", flush=True)
        if not Overlay._bridge:
             print(f"[video manager][CLEANUP_{thread_id}] Cleanup ABORTED: Overlay bridge missing.", flush=True)
             # Ensure state is still reset
             with self._lock:
                  self.is_playing = False
                  self.should_stop = True # Mark as stopped
                  self.resetting = False
                  self.video_player = None
                  self.completion_callback = None
             print(f"[video manager][CLEANUP_{thread_id}] State reset despite bridge missing.", flush=True)
             return

        print(f"[video manager][CLEANUP_{thread_id}] Bridge exists. Acquiring lock...", flush=True)
        final_callback = None
        with self._lock:
            print(f"[video manager][CLEANUP_{thread_id}] Lock acquired. Current state: is_playing={self.is_playing}, should_stop={self.should_stop}, resetting={self.resetting}", flush=True)
            # This check might prevent cleanup if stop_video ran cleanup AFTER natural completion already started scheduling it.
            # Let's refine this: cleanup should always run if trigger_context is 'StopVideo' or if it was scheduled naturally.
            # if not self.is_playing and not self.should_stop and not self.resetting:
            #      print(f"[video manager][CLEANUP_{thread_id}] Post-playback cleanup: State indicates already stopped/reset, skipping.")
            #      return
            print(f"[video manager][CLEANUP_{thread_id}] Proceeding with cleanup. Setting state: is_playing=False, should_stop=True", flush=True)
            self.is_playing = False
            self.should_stop = True # Ensure it's marked as stopped

            # Get the callback from instance or use the preserved one
            final_callback = preserved_callback if preserved_callback is not None else self.completion_callback
            self.completion_callback = None  # Clear it immediately
            print(f"[video manager][CLEANUP_{thread_id}] final_callback obtained: {final_callback}", flush=True)

        print(f"[video manager][CLEANUP_{thread_id}] Lock released.", flush=True)

        try:
            # 1. Destroy Qt video display (Invoke slot on bridge)
            print(f"[video manager][CLEANUP_{thread_id}] Queuing destroy_video_display_slot...", flush=True)
            QMetaObject.invokeMethod(
                Overlay._bridge,
                "destroy_video_display_slot",
                Qt.QueuedConnection # Keep as Queued
            )
            print(f"[video manager][CLEANUP_{thread_id}] destroy_video_display_slot queued.", flush=True)

            # 2. Restore background music volume
            print(f"[video manager][CLEANUP_{thread_id}] Restoring background music...", flush=True)
            self._fade_background_music(1.0, duration=0.3)
            print(f"[video manager][CLEANUP_{thread_id}] Background music restoration initiated.", flush=True)

            # 3. Clean up VideoPlayer instance resources
            player_to_clean = self.video_player # Grab ref before nulling
            print(f"[video manager][CLEANUP_{thread_id}] Checking video_player instance ({player_to_clean})...", flush=True)
            if player_to_clean:
                 print(f"[video manager][CLEANUP_{thread_id}] Cleaning up video player instance resources ({player_to_clean})...", flush=True)
                 player_to_clean._cleanup_resources()
                 self.video_player = None # Null the reference AFTER cleanup
                 print(f"[video manager][CLEANUP_{thread_id}] Video player instance cleaned and set to None.", flush=True)
            else:
                 print(f"[video manager][CLEANUP_{thread_id}] No video player instance found during cleanup.", flush=True)

            # 4. Execute the final completion callback IF provided and NOT resetting
            print(f"[video manager][CLEANUP_{thread_id}] Checking final callback. Callback = {final_callback}, Resetting = {self.resetting}", flush=True)
            if final_callback and not self.resetting:
                print(f"[video manager][CLEANUP_{thread_id}] Scheduling final completion callback via QTimer (100ms delay): {final_callback}", flush=True)
                try:
                    QTimer.singleShot(100, final_callback) # Keep the delay for now
                    print(f"[video manager][CLEANUP_{thread_id}] Final callback scheduled successfully with delay.", flush=True)
                except Exception as cb_err:
                    print(f"[video manager][CLEANUP_{thread_id}] Error scheduling final completion callback: {cb_err}", flush=True)
                    traceback.print_exc()
            elif self.resetting:
                 print(f"[video manager][CLEANUP_{thread_id}] Resetting flag is True, skipping final completion callback.", flush=True)
            else: # Callback was None
                print(f"[video manager][CLEANUP_{thread_id}] No final callback provided, skipping.", flush=True)

        except Exception as e:
            print(f"[video manager][CLEANUP_{thread_id}] !!! Error during post-playback cleanup:", flush=True)
            traceback.print_exc()
        finally:
             # Ensure state is reset even if errors occurred during cleanup steps
             print(f"[video manager][CLEANUP_{thread_id}] Entering finally block for state reset.", flush=True)
             with self._lock:
                  print(f"[video manager][CLEANUP_{thread_id}] (Finally) Lock acquired. Resetting state.", flush=True)
                  self.is_playing = False
                  self.should_stop = True # Ensure stopped state
                  self.resetting = False
                  self.video_player = None # Ensure player is None
                  self.completion_callback = None # Ensure callback is None
                  print(f"[video manager][CLEANUP_{thread_id}] (Finally) State reset completed.", flush=True)
             print(f"[video manager][CLEANUP_{thread_id}] Lock released.", flush=True)
             print(f"[video manager][CLEANUP_{thread_id}] --- _perform_post_playback_cleanup FINISHED (Thread: {thread_id}) ---", flush=True)


    def _cleanup_after_error(self):
         """Simplified cleanup specifically for errors during setup."""
         print("[video manager] Cleaning up after setup error...", flush=True)
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
              print("[video manager] Executing completion callback after error.", flush=True)
              # Replace root.after with QTimer.singleShot
              QTimer.singleShot(0, final_callback)


    def stop_video(self):
        """Stop video playback gracefully."""
        thread_id = threading.get_ident()
        print(f"[video manager][STOP_{thread_id}] +++ stop_video called (Thread: {thread_id}) +++", flush=True)
        player_instance = None
        cleanup_needed = False
        with self._lock:
            print(f"[video manager][STOP_{thread_id}] Lock acquired. Current state: is_playing={self.is_playing}, should_stop={self.should_stop}", flush=True)
            if not self.is_playing:
                print(f"[video manager][STOP_{thread_id}] Stop ignored: Not currently playing.", flush=True)
                if self.should_stop:
                     print(f"[video manager][STOP_{thread_id}] Stop ignored: Stop request already processed or in progress.", flush=True)
                return

            print(f"[video manager][STOP_{thread_id}] Setting should_stop = True", flush=True)
            self.should_stop = True # Signal intent to stop FIRST
            player_instance = self.video_player # Get reference to signal player
            cleanup_needed = True # Mark that cleanup should happen after player stops
            print(f"[video manager][STOP_{thread_id}] Player instance: {player_instance}, Cleanup needed: {cleanup_needed}", flush=True)

        print(f"[video manager][STOP_{thread_id}] Lock released.", flush=True)

        # Signal the VideoPlayer instance to stop (if it exists)
        if player_instance:
            print(f"[video manager][STOP_{thread_id}] Signaling video player instance ({player_instance}) to stop and waiting...", flush=True)
            player_instance.stop_video(wait=True) # Ask the player thread to stop AND WAIT
            print(f"[video manager][STOP_{thread_id}] Video player stop_video returned (threads should be joined).", flush=True)
            # --- Trigger cleanup directly AFTER player stops ---
            if cleanup_needed:
                 print(f"[video manager][STOP_{thread_id}] Triggering post-playback cleanup directly...", flush=True)
                 # Pass context to cleanup function
                 self._perform_post_playback_cleanup(trigger_context="StopVideo")
                 print(f"[video manager][STOP_{thread_id}] Post-playback cleanup triggered.", flush=True)
            else:
                 # This case should ideally not happen if we got here, but log it.
                 print(f"[video manager][STOP_{thread_id}] Warning: Player instance existed, but cleanup_needed was False?", flush=True)
        else:
             print(f"[video manager][STOP_{thread_id}] No video player instance to signal stop.", flush=True)
             # If no player instance, but we were 'playing' according to the initial check, trigger cleanup directly
             if cleanup_needed:
                  print(f"[video manager][STOP_{thread_id}] No player instance, but cleanup_needed is True. Triggering cleanup directly...", flush=True)
                  self._perform_post_playback_cleanup(trigger_context="StopVideoNoInstance")
                  print(f"[video manager][STOP_{thread_id}] Post-playback cleanup triggered.", flush=True)
             else:
                 print(f"[video manager][STOP_{thread_id}] No player instance and cleanup_needed is False. Nothing to do.", flush=True)

        print(f"[video manager][STOP_{thread_id}] --- stop_video finished (Thread: {thread_id}) ---", flush=True)


    def force_stop(self):
        """Force stop all video playback immediately for reset scenarios."""
        print("[video manager] Force stopping all video playback.", flush=True)
        bridge_exists = Overlay._bridge is not None
        player_instance = None
        with self._lock:
            print(f"[video manager][FORCE_STOP] Setting state flags. Current state: is_playing={self.is_playing}, should_stop={self.should_stop}, resetting={self.resetting}", flush=True)
            self.resetting = True # Mark as resetting
            self.should_stop = True # Signal any active player to stop
            self.is_playing = False # Assume stopped state immediately
            player_instance = self.video_player # Grab reference before nulling
            self.video_player = None # Clear player reference
            self.completion_callback = None # Clear callback
            print(f"[video manager][FORCE_STOP] State flags set. New state: is_playing=False, should_stop=True, resetting=True", flush=True)
        
        try:
            # Step 1: Stop the player thread if it exists
            if player_instance:
                print(f"[video manager][FORCE_STOP] Force stopping video player instance: {player_instance}...", flush=True)
                player_instance.force_stop() # Ask player thread to terminate and clean up
                print(f"[video manager][FORCE_STOP] Video player force_stop completed.", flush=True)
            else:
                print("[video manager][FORCE_STOP] No player instance found.", flush=True)
            
            # Step 2: Restore music volume immediately
            print("[video manager][FORCE_STOP] Force restoring music volume...", flush=True)
            if mixer.get_init():
                 mixer.music.set_volume(1.0) # Set volume directly
                 print("[video manager][FORCE_STOP] Music volume restored to 1.0", flush=True)
            else:
                 print("[video manager][FORCE_STOP] Mixer not initialized, cannot restore music volume", flush=True)
            
            # Step 3: Just destroy the video display, no need for other UI manipulation
            if bridge_exists:
                print("[video manager][FORCE_STOP] Force destroying video display (Auto connection)...", flush=True)
                QMetaObject.invokeMethod(
                    Overlay._bridge,
                    "destroy_video_display_slot",
                    Qt.AutoConnection  # CHANGED: Let Qt decide based on thread context
                )
                print("[video manager][FORCE_STOP] Video display destroy request sent.", flush=True)
                # Add a small delay to allow Qt events to process
                time.sleep(0.1)
                print("[video manager][FORCE_STOP] Waited for Qt event processing.", flush=True)
            else:
                print("[video manager][FORCE_STOP] Warning: Bridge missing, cannot destroy video display.", flush=True)

        except Exception as e:
            print(f"[video manager][FORCE_STOP] Error during force_stop cleanup: {e}", flush=True)
            traceback.print_exc()
        finally:
            # Ensure state is definitely reset even if errors occurred
            with self._lock:
                 print("[video manager][FORCE_STOP] Final state reset in finally block", flush=True)
                 self.is_playing = False
                 self.should_stop = True
                 self.resetting = False # Reset the resetting flag after cleanup attempt
                 self.video_player = None
                 self.completion_callback = None
            print("[video manager] Force stop process finished.", flush=True)

    # --- No longer need UI hiding/restoring logic here ---
    # --- No longer need _cleanup, _force_cleanup, reset_state (handled within play/stop/force_stop) ---