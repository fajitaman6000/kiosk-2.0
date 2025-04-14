# kiosk_timer.py
print("[kiosk timer] Beginning imports ...")
import time
from qt_overlay import Overlay # Use Qt overlay for display
import os
import traceback
from PyQt5.QtCore import QMetaObject, Qt, QTimer, Q_ARG, QThread, pyqtSignal
# Removed tkinter and PIL imports as they are no longer needed for display

print("[kiosk timer] Ending imports ...")

class TimerUpdateThread(QThread):
    update_signal = pyqtSignal()
    
    def __init__(self, timer_instance):
        super().__init__()
        self.timer_instance = timer_instance
        self.running = True
        
    def run(self):
        while self.running:
            self.update_signal.emit()
            self.msleep(100)  # Sleep for 100ms
            
    def stop(self):
        self.running = False

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with root (for scheduling) and kiosk_app reference"""
        self.root = root # Still needed for root.after scheduling
        self.kiosk_app = kiosk_app
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_room = None
        self._update_scheduled = False  # Flag to track scheduled updates
        self.game_lost = False  #Flag to indicate game loss
        self.game_won = False # Flag for game won

        # Create and start the timer update thread
        self.timer_thread = TimerUpdateThread(self)
        self.timer_thread.update_signal.connect(self.update_timer_loop)
        self.timer_thread.start()

        # Delay Qt timer initialization until the Qt app/overlay is likely ready
        QTimer.singleShot(1000, self._delayed_qt_init)

    def _delayed_qt_init(self):
        """Initialize Qt timer display elements via the Overlay."""
        try:
            print("[kiosk timer] Initializing Qt timer display via Overlay...")
            Overlay.init_timer()
            # Perform an initial display update once Qt components are assumed ready
            self.update_display()
            print("[kiosk timer] Qt timer display initialized.")
        except Exception as e:
            print(f"[kiosk timer] Error during delayed Qt init: {e}")
            traceback.print_exc()
            # Optionally retry or handle the error
            # QTimer.singleShot(1000, self._delayed_qt_init) # Example retry

    def load_room_background(self, room_number):
        """Loads the timer background via the Qt Overlay."""
        self.current_room = room_number
        try:
            # Call the Overlay method to handle the background change
            print(f"[kiosk timer] Loading timer background for room {room_number} via Overlay.")
            Overlay.load_timer_background(room_number)
        except AttributeError:
            # Fallback if Overlay or its method isn't ready yet
            print("[kiosk timer] Overlay not ready for background load, scheduling retry.")
            QTimer.singleShot(500, lambda: self.load_room_background(room_number))
        except Exception as e:
            print(f"[kiosk timer] Error loading timer background via Overlay: {e}")
            traceback.print_exc()

    def handle_command(self, command, minutes=None):
        """Handles start, stop, and set commands for the timer."""
        print(f"\n[DEBUG TIMER] handle_command called with command: {command}, minutes: {minutes}")
        print(f"[DEBUG TIMER] Current state - is_running: {self.is_running}, time_remaining: {self.time_remaining}, last_update: {self.last_update}")
        
        if command == "start":
            if not self.is_running: # Prevent resetting last_update if already running
                self.is_running = True
                self.last_update = time.time()
                print(f"[DEBUG TIMER] Timer started - new last_update: {self.last_update}")
            else:
                print("[DEBUG TIMER] Timer already running, 'start' command ignored.")

        elif command == "stop":
            if self.is_running:
                # Update time remaining one last time before stopping
                if self.last_update:
                    current_time = time.time()
                    elapsed = current_time - self.last_update
                    self.time_remaining = max(0, self.time_remaining - elapsed)
                    print(f"[DEBUG TIMER] Timer stopped - elapsed: {elapsed}, new time_remaining: {self.time_remaining}")
                self.is_running = False
                self.last_update = None
                print("[DEBUG TIMER] Timer stopped - is_running set to False, last_update cleared")
            else:
                print("[DEBUG TIMER] Timer already stopped, 'stop' command ignored.")

        elif command == "set" and minutes is not None:
            print(f"[DEBUG TIMER] Setting timer to {minutes} minutes")
            self.time_remaining = minutes * 60
            self.game_lost = False  # Reset game_lost flag when timer is set
            self.game_won = False  # Reset game_won flag as well
            self.is_running = False # Setting the timer implies it's not running yet
            self.last_update = None
            print(f"[DEBUG TIMER] Timer set - time_remaining: {self.time_remaining}, is_running: {self.is_running}")

        # Update the display regardless of command to show current state/time
        self.update_display()

    def update_timer_loop(self):
        """Main loop executed periodically to update timer state."""
        print("\n[DEBUG TIMER] update_timer_loop called")
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                old_time = self.time_remaining
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time # Update last_update *after* calculating elapsed
                
                print(f"[DEBUG TIMER] update_timer_loop - elapsed: {elapsed:.2f}s")
                print(f"[DEBUG TIMER] Time update - old: {old_time:.2f}s, new: {self.time_remaining:.2f}s")
                print(f"[DEBUG TIMER] Current state - is_running: {self.is_running}, last_update: {self.last_update}")

                # Check for game loss condition
                if not self.game_lost and self.time_remaining <= 0:
                    print(f"[DEBUG TIMER] Timer reached zero - triggering game loss")
                    self.game_lost = True
                    self.is_running = False # Stop the timer definitively
                    self.last_update = None

                    # Trigger game loss audio and UI changes via kiosk_app
                    if self.kiosk_app:
                        print("[DEBUG TIMER] Triggering game loss handling")
                        self.kiosk_app.audio_manager.stop_background_music()
                        if self.kiosk_app.assigned_room:
                            self.kiosk_app.audio_manager.play_loss_audio(self.kiosk_app.assigned_room)
                        else:
                            print("[DEBUG TIMER] No room assigned, cannot play loss audio")
                        self.kiosk_app.handle_game_loss() # Tell kiosk app game is lost
                    else:
                        print("[DEBUG TIMER] KioskApp reference missing, cannot handle game loss")

                # Update the visual display
                self.update_display()
            else:
                if not self.is_running:
                    print("[DEBUG TIMER] Timer not running, skipping update")
                if self.last_update is None:
                    print("[DEBUG TIMER] last_update is None, skipping update")

        except Exception as e:
            print(f"[DEBUG TIMER] Error in update_timer_loop: {e}")
            traceback.print_exc()

    def get_time_str(self):
        """Get the current time remaining as a formatted string MM:SS."""
        # Ensure time doesn't go negative for display purposes
        display_time = max(0, self.time_remaining)
        minutes = int(display_time // 60)
        seconds = int(display_time % 60)
        return f"{minutes:02d}:{seconds:02d}"

    def update_display(self):
        """Updates the timer display via the Qt Overlay, checking conditions."""
        print(f"\n[DEBUG TIMER] update_display called")
        print(f"[DEBUG TIMER] Current state - time_remaining: {self.time_remaining:.2f}s, is_running: {self.is_running}")
        
        # Avoid queueing multiple updates if one is already scheduled/running
        if self._update_scheduled:
            print("[DEBUG TIMER] Update already scheduled, skipping")
            return
        self._update_scheduled = True

        try:
            # Check if UI should be hidden (video playing, fullscreen image, game ended)
            should_hide_timer = (
                self.kiosk_app.video_manager.is_playing or
                self.kiosk_app.ui.image_is_fullscreen or
                self.game_lost or # Hide timer on loss screen
                self.game_won   # Hide timer on win screen
            )

            if should_hide_timer:
                print("[DEBUG TIMER] Conditions met to hide timer")
                Overlay.hide_timer()
            else:
                # Conditions met to show/update the timer
                time_str = self.get_time_str()
                print(f"[DEBUG TIMER] Updating display with time: {time_str}")
                Overlay.update_timer_display(time_str)

        except Exception as e:
            print(f"[DEBUG TIMER] Error in update_display: {e}")
            traceback.print_exc()
        finally:
            self._update_scheduled = False

    # Removed _do_update_display as it's no longer needed; logic is in update_display