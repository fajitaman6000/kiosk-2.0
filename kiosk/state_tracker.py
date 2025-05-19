# state_tracker.py
print("[StateTracker] Beginning imports ...", flush=True)
import json
import os
import time
import threading
import traceback
import sys # For traceback.print_exc
print("[StateTracker] Imports complete.", flush=True)

def _log_kiosk_exception(kiosk_app_instance, exception, message):
    """
    Helper function to log an exception using the KioskApp's logger if available.
    This is a standalone function to avoid complex instance methods if logger is not yet fully set up.
    """
    try:
        # KioskApp initializes its logger as self.logger from init_logging()
        # and init_logging() returns a LoggerWrapper which has log_exception method.
        if hasattr(kiosk_app_instance, 'logger') and \
           kiosk_app_instance.logger is not None and \
           hasattr(kiosk_app_instance.logger, 'log_exception'):
            kiosk_app_instance.logger.log_exception(exception, message)
        else:
            # Fallback if logger is not available or not the expected type
            print(f"[StateTracker] KioskApp logger not available for exception: {message} - {str(exception)}", flush=True)
            # Optionally, print traceback here if it's a critical fallback path
            # traceback.print_exc(file=sys.stderr)
    except Exception as log_err:
        # This catch is to prevent the logging helper itself from crashing the app
        print(f"[StateTracker] CRITICAL: Error during exception logging attempt: {log_err}", flush=True)
        print(f"[StateTracker] Original   : {message} - {str(exception)}", flush=True)

class StateTracker:
    def __init__(self, kiosk_app, interval_seconds=5, filename="kiosk_state.json"):
        """
        Initializes the StateTracker.

        Args:
            kiosk_app: The instance of the main KioskApp.
            interval_seconds (int): How often to save the state in seconds.
            filename (str): The name of the JSON file to save state to.
        """
        print("[StateTracker] Initializing StateTracker...", flush=True)
        self.kiosk_app = kiosk_app
        self.interval_seconds = interval_seconds
        self.filename = filename
        self.thread = None
        self.stop_event = threading.Event()

        # Determine the path for the state file (in the same directory as this script)
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        except NameError: # __file__ is not defined in some contexts (e.g. interactive interpreter)
            base_dir = os.getcwd()
        self.state_file_path = os.path.join(base_dir, self.filename)
        
        print(f"[StateTracker] State will be saved to: {self.state_file_path}", flush=True)
        print("[StateTracker] StateTracker initialized.", flush=True)

    def _get_current_state(self):
        """
        Fetches the current state from the KioskApp instance.
        Returns a dictionary representing the state, or None if KioskApp is not available.
        """
        if not self.kiosk_app:
            print("[StateTracker] KioskApp reference is not available. Cannot get state.", flush=True)
            return None

        state = {
            "game_running": False,
            "timer_remaining_seconds": 0,
            "hints_requested_count": 0,
            "hints_received_count": 0,
            "music_position_ms": -1,
            "timestamp_utc": time.time(),
            "error_fetching_state": None # Placeholder for errors
        }

        try:
            # Game status (timer running)
            if hasattr(self.kiosk_app, 'timer') and self.kiosk_app.timer is not None:
                state["game_running"] = self.kiosk_app.timer.is_running
                state["timer_remaining_seconds"] = self.kiosk_app.timer.time_remaining
            else:
                state["error_fetching_state"] = (state["error_fetching_state"] or "") + "Timer not available. "

            # Hint counts
            # These are direct attributes of KioskApp
            state["hints_requested_count"] = getattr(self.kiosk_app, 'hints_requested', 0)
            state["hints_received_count"] = getattr(self.kiosk_app, 'hints_received', 0)

            # Music position
            if hasattr(self.kiosk_app, 'audio_manager') and self.kiosk_app.audio_manager is not None:
                state["music_position_ms"] = self.kiosk_app.audio_manager.get_music_position_ms()
            else:
                state["error_fetching_state"] = (state["error_fetching_state"] or "") + "Audio manager not available. "
            
            if state["error_fetching_state"] is None:
                del state["error_fetching_state"] # Remove if no errors

        except AttributeError as e:
            error_msg = f"AttributeError fetching state: {e}. Some KioskApp components might not be fully initialized or are being torn down."
            print(f"[StateTracker] {error_msg}", flush=True)
            state["error_fetching_state"] = (state["error_fetching_state"] or "") + error_msg
            # _log_kiosk_exception(self.kiosk_app, e, "[StateTracker] AttributeError while fetching state") # Can be noisy
        except Exception as e:
            error_msg = f"Unexpected error fetching state: {e}"
            print(f"[StateTracker] {error_msg}", flush=True)
            state["error_fetching_state"] = (state["error_fetching_state"] or "") + error_msg
            _log_kiosk_exception(self.kiosk_app, e, "[StateTracker] Unexpected error fetching state")
            
        return state

    def _write_state_to_json(self):
        """
        Retrieves the current state and writes it to the specified JSON file.
        Uses an atomic write (write to temp file, then rename).
        """
        if self.kiosk_app.is_closing:
            # Avoid writing state if the app is in the process of shutting down,
            # as some components might be in an inconsistent state.
            # print("[StateTracker] KioskApp is closing, skipping state write.", flush=True)
            return

        current_state = self._get_current_state()
        if current_state is None:
            # This case should ideally be rare if kiosk_app is always set during init.
            print("[StateTracker] Cannot write state: current_state is None.", flush=True)
            return

        temp_file_path = self.state_file_path + ".tmp"
        try:
            with open(temp_file_path, 'w') as f:
                json.dump(current_state, f, indent=2)
            
            # Atomically replace the old file with the new one
            os.replace(temp_file_path, self.state_file_path)
            # print(f"[StateTracker] State successfully written to {self.state_file_path}", flush=True) # Verbose
        except FileNotFoundError:
            # This might happen if the directory doesn't exist or permissions are wrong
            print(f"[StateTracker] Error: Could not write to {temp_file_path} or rename to {self.state_file_path}. File/directory not found or inaccessible.", flush=True)
            # No KioskApp logger call here, as this is a fundamental file system issue.
        except IOError as e:
            print(f"[StateTracker] IOError writing state to JSON: {e}", flush=True)
            traceback.print_exc(file=sys.stderr)
            _log_kiosk_exception(self.kiosk_app, e, "[StateTracker] IOError writing state to JSON")
        except Exception as e:
            print(f"[StateTracker] Unexpected error writing state to JSON: {e}", flush=True)
            traceback.print_exc(file=sys.stderr)
            _log_kiosk_exception(self.kiosk_app, e, "[StateTracker] Unexpected error writing state to JSON")

    def _run(self):
        """The main loop for the state tracking thread."""
        print("[StateTracker] Worker thread started. Saving state every "
              f"{self.interval_seconds} seconds.", flush=True)
        try:
            while not self.stop_event.wait(self.interval_seconds):
                if self.kiosk_app.is_closing:
                    print("[StateTracker] KioskApp is closing, worker thread will exit.", flush=True)
                    break
                self._write_state_to_json()
        except Exception as e:
            # Catch unexpected errors in the loop itself
            print(f"[StateTracker] Error in worker thread loop: {e}", flush=True)
            _log_kiosk_exception(self.kiosk_app, e, "[StateTracker] Error in worker thread loop")
        finally:
            print("[StateTracker] Worker thread stopped.", flush=True)

    def start(self):
        """Starts the state tracking background thread."""
        if self.thread is not None and self.thread.is_alive():
            print("[StateTracker] Tracker thread is already running.", flush=True)
            return

        print("[StateTracker] Starting tracker thread...", flush=True)
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="StateTrackerThread", daemon=True)
        self.thread.start()
        print("[StateTracker] Tracker thread initiated.", flush=True)

    def stop(self):
        """Signals the state tracking thread to stop and waits for it to join."""
        print("[StateTracker] Attempting to stop tracker thread...", flush=True)
        self.stop_event.set()
        if self.thread is not None and self.thread.is_alive():
            print("[StateTracker] Waiting for tracker thread to join...", flush=True)
            self.thread.join(timeout=self.interval_seconds + 1.0) # Wait a bit longer than one interval
            if self.thread.is_alive():
                print("[StateTracker] WARNING: Tracker thread did not terminate cleanly after timeout.", flush=True)
            else:
                print("[StateTracker] Tracker thread joined successfully.", flush=True)
        else:
            print("[StateTracker] Tracker thread was not running or already stopped.", flush=True)
        
        # Optionally, perform a final state write if needed and safe
        # print("[StateTracker] Performing a final state write on stop...", flush=True)
        # self._write_state_to_json() # Be cautious with this during app shutdown

        print("[StateTracker] Tracker stop sequence complete.", flush=True)
