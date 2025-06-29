# kiosk_timer.py
print("[kiosk timer] Beginning imports ...", flush=True)
print("[kiosk timer] Importing time...", flush=True)
import time
print("[kiosk timer] Imported time.", flush=True)
print("[kiosk timer] Importing qt_overlay...", flush=True)
from qt_overlay import Overlay # Use Qt overlay for display
print("[kiosk timer] Imported qt_overlay.", flush=True)
print("[kiosk timer] Importing os...", flush=True)
import os
print("[kiosk timer] Imported os.", flush=True)
print("[kiosk timer] Importing traceback...", flush=True)
import traceback
print("[kiosk timer] Imported traceback.", flush=True)
print("[kiosk timer] Importing PyQt5.QtCore...", flush=True)
from PyQt5.QtCore import QMetaObject, Qt, QTimer, Q_ARG, QThread, pyqtSignal
print("[kiosk timer] Imported PyQt5.QtCore.", flush=True)
# Removed tkinter and PIL imports as they are no longer needed for display

print("[kiosk timer] Ending imports ...", flush=True)

class TimerUpdateThread(QThread):
    update_signal = pyqtSignal()
    
    def __init__(self, timer_instance):
        print("[kiosk timer] Initializing TimerUpdateThread...", flush=True)
        super().__init__()
        self.timer_instance = timer_instance
        self.running = True
        print("[kiosk timer] TimerUpdateThread initialized.", flush=True)
        
    def run(self):
        while self.running:
            self.update_signal.emit()
            self.msleep(100)  # Sleep for 100ms
            
    def stop(self):
        print("[kiosk timer] Stopping TimerUpdateThread...", flush=True)
        self.running = False
        print("[kiosk timer] TimerUpdateThread stopped.", flush=True)

class KioskTimer:
    def __init__(self, root, kiosk_app):
        """Initialize the timer with kiosk_app reference"""
        print("[kiosk timer] Initializing KioskTimer...", flush=True)
        # root parameter is kept for compatibility but is no longer used
        self.kiosk_app = kiosk_app
        self.time_remaining = 60 * 45  # Default 45 minutes
        self.is_running = False
        self.last_update = None
        self.current_room = None
        self._update_scheduled = False  # Flag to track scheduled updates
        self.game_lost = False  #Flag to indicate game loss
        self.game_won = False # Flag for game won

        # Create and start the timer update thread
        print("[kiosk timer] Creating timer update thread...", flush=True)
        self.timer_thread = TimerUpdateThread(self)
        self.timer_thread.update_signal.connect(self.update_timer_loop)
        self.timer_thread.start()
        print("[kiosk timer] Timer update thread started.", flush=True)

        # Delay Qt timer initialization until the Qt app/overlay is likely ready
        print("[kiosk timer] Scheduling delayed Qt initialization...", flush=True)
        QTimer.singleShot(1000, self._delayed_qt_init)
        print("[kiosk timer] KioskTimer initialization complete.", flush=True)

    def _delayed_qt_init(self):
        """Initialize Qt timer display elements via the Overlay."""
        try:
            print("[kiosk timer] Initializing Qt timer display via Overlay...", flush=True)
            Overlay.init_timer()
            # Perform an initial display update once Qt components are assumed ready
            self.update_display()
            print("[kiosk timer] Qt timer display initialized.", flush=True)
        except Exception as e:
            print(f"[kiosk timer] Error during delayed Qt init: {e}", flush=True)
            traceback.print_exc()
            # Optionally retry or handle the error
            # QTimer.singleShot(1000, self._delayed_qt_init) # Example retry

    def load_room_background(self, room_number):
        """Loads the timer background via the Qt Overlay."""
        print(f"[kiosk timer] Loading room background for room {room_number}...", flush=True)
        self.current_room = room_number
        try:
            # Call the Overlay method to handle the background change
            print(f"[kiosk timer] Loading timer background for room {room_number} via Overlay.", flush=True)
            Overlay.load_timer_background(room_number)
            print(f"[kiosk timer] Timer background for room {room_number} loaded.", flush=True)
        except AttributeError:
            # Fallback if Overlay or its method isn't ready yet
            print("[kiosk timer] Overlay not ready for background load, scheduling retry.", flush=True)
            QTimer.singleShot(500, lambda: self.load_room_background(room_number))
        except Exception as e:
            print(f"[kiosk timer] Error loading timer background via Overlay: {e}", flush=True)
            traceback.print_exc()

    def handle_command(self, command, minutes=None):
        """Handles start, stop, and set commands for the timer."""
        print(f"[kiosk timer] Handling timer command: {command}, minutes: {minutes}", flush=True)
        if command == "start":
            if not self.is_running: # Prevent resetting last_update if already running
                self.is_running = True
                self.last_update = time.time()
                print("[kiosk timer] Timer started", flush=True)
            else:
                print("[kiosk timer] Timer already running, 'start' command ignored.", flush=True)

        elif command == "stop":
            if self.is_running:
                # Update time remaining one last time before stopping
                if self.last_update:
                    current_time = time.time()
                    elapsed = current_time - self.last_update
                    self.time_remaining = max(0, self.time_remaining - elapsed)
                self.is_running = False
                self.last_update = None
                print("[kiosk timer] Timer stopped", flush=True)
            else:
                print("[kiosk timer] Timer already stopped, 'stop' command ignored.", flush=True)

        elif command == "set" and minutes is not None:
            self.time_remaining = minutes * 60
            self.game_lost = False  # Reset game_lost flag when timer is set
            self.game_won = False  # Reset game_won flag as well
            self.last_update = time.time()  # Update the last_update time to now
            print(f"[kiosk timer] Timer set to {minutes} minutes (maintaining current running state)", flush=True)

        # Update the display regardless of command to show current state/time
        self.update_display()
        print(f"[kiosk timer] Timer command {command} handling complete.", flush=True)

    def update_timer_loop(self):
        """Main loop executed periodically to update timer state."""
        try:
            if self.is_running and self.last_update is not None:
                current_time = time.time()
                elapsed = current_time - self.last_update
                old_time = self.time_remaining
                self.time_remaining = max(0, self.time_remaining - elapsed)
                self.last_update = current_time # Update last_update *after* calculating elapsed

                # Check for timer crossing the 42-minute threshold
                if old_time > 2520 and self.time_remaining <= 2520:
                    print("[kiosk timer] Timer crossed the 42-minute threshold, updating help button", flush=True)
                    if self.kiosk_app:
                        self.kiosk_app._actual_help_button_update()

                # Check for game loss condition
                if not self.game_lost and self.time_remaining <= 0:
                    print(f"[kiosk timer] Timer reached zero.", flush=True)
                    self.game_lost = True
                    self.is_running = False # Stop the timer definitively
                    self.last_update = None

                    # Trigger game loss audio and UI changes via kiosk_app
                    if self.kiosk_app:
                        self.kiosk_app.handle_game_loss() # Tell kiosk app game is lost
                    else:
                        print("[kiosk timer] KioskApp reference missing, cannot handle game loss.", flush=True)

                # Update the visual display
                self.update_display()

        except Exception as e:
            print(f"[kiosk timer] Error in update_timer_loop: {e}", flush=True)
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
        # Avoid queueing multiple updates if one is already scheduled/running
        if self._update_scheduled:
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
                Overlay.hide_timer()
            else:
                # Conditions met to show/update the timer
                time_str = self.get_time_str()
                #print(f"[kiosk timer] Updating timer display to {time_str}", flush=True)
                Overlay.update_timer_display(time_str)

        except Exception as e:
            print(f"[kiosk timer] Error in update_display: {e}", flush=True)
            traceback.print_exc()
        finally:
            self._update_scheduled = False

    def start(self, duration_seconds=None):
        """Start the timer with optional duration in seconds"""
        print(f"[kiosk timer] Starting timer with duration {duration_seconds if duration_seconds is not None else 'default'}...", flush=True)
        if duration_seconds is not None:
            self.time_remaining = duration_seconds
        
        self.is_running = True
        self.last_update = time.time()
        self.game_lost = False  # Reset game lost flag
        self.game_won = False   # Reset game won flag
        print(f"[kiosk timer] Timer started with {self.time_remaining} seconds remaining", flush=True)
        self.update_display()

    # Removed _do_update_display as it's no longer needed; logic is in update_display