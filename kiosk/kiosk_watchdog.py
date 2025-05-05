# launcher_watchdog.py
import subprocess
import sys
import os
import time
import threading
import signal
import queue

# --- Configuration ---
KIOSK_SCRIPT = "kiosk.py"
PYTHON_EXECUTABLE = sys.executable  # Use the same python that's running the watchdog
SUCCESS_MARKER = "[kiosk main] KioskApp initialization complete."
LAUNCH_TIMEOUT_SECONDS = 25  # Time without output during launch before restarting
MAX_RESTARTS = 5             # Max attempts before giving up
POLL_INTERVAL_SECONDS = 0.5  # How often to check for hangs/success
TERMINATE_WAIT_SECONDS = 2   # Time to wait after terminate before kill

# --- Globals ---
# These are declared here to define them at the module level
kiosk_process = None
shutdown_requested = False # This is the global variable modified by signal_handler
launch_successful = False
last_output_time = time.time()
output_queue = queue.Queue()
reader_thread = None
monitor_active = True
restart_count = 0
lock = threading.Lock()

# --- Functions ---

def print_watchdog(message):
    """Helper to print messages clearly identified as from the watchdog."""
    print(f"[WATCHDOG] {message}", flush=True)

def read_kiosk_output(process_stdout):
    """
    Thread target function to read output from the kiosk process.
    Updates last_output_time and checks for the success marker.
    """
    # These variables are modified in this thread, so declare them global
    global last_output_time, launch_successful, monitor_active

    try:
        print_watchdog(f"Output reader thread started (PID: {os.getpid()}, Thread: {threading.get_ident()}).")
        while monitor_active:
            try:
                line = process_stdout.readline()
                if not line:
                    # Process likely exited or stdout closed
                    if monitor_active:
                         print_watchdog("Kiosk stdout stream ended.")
                    break

                line = line.strip()
                if line:
                    timestamp = time.time()
                    # Update shared state safely using the lock
                    with lock:
                        last_output_time = timestamp
                        if not launch_successful and SUCCESS_MARKER in line:
                            launch_successful = True
                            print_watchdog(f"Success marker found: '{SUCCESS_MARKER}'")

                    # Put line onto queue for main thread to print
                    output_queue.put(line)

            except ValueError:
                 if monitor_active:
                     print_watchdog("Kiosk stdout pipe closed unexpectedly.")
                 break
            except Exception as e:
                if monitor_active:
                    print_watchdog(f"Error reading kiosk output: {e}")
                break
    finally:
        if process_stdout and not process_stdout.closed:
            try:
                process_stdout.close()
            except Exception:
                pass
        print_watchdog("Output reader thread finished.")


def terminate_kiosk_process():
    """Attempts to gracefully terminate the kiosk process."""
    global kiosk_process # Declare global as we modify kiosk_process
    if kiosk_process and kiosk_process.poll() is None:
        print_watchdog(f"Attempting to terminate kiosk process (PID: {kiosk_process.pid})...")
        try:
            kiosk_process.terminate()
            try:
                kiosk_process.wait(timeout=TERMINATE_WAIT_SECONDS)
                print_watchdog(f"Kiosk process (PID: {kiosk_process.pid}) terminated gracefully.")
            except subprocess.TimeoutExpired:
                print_watchdog(f"Kiosk process (PID: {kiosk_process.pid}) did not terminate, killing...")
                kiosk_process.kill()
                kiosk_process.wait()
                print_watchdog(f"Kiosk process (PID: {kiosk_process.pid}) killed.")
        except Exception as e:
            print_watchdog(f"Error terminating/killing kiosk process: {e}")
        kiosk_process = None

def signal_handler(sig, frame):
    """Handles SIGINT (Ctrl+C) for graceful shutdown."""
    global shutdown_requested, monitor_active # Declare global as we modify these
    if not shutdown_requested:
        print_watchdog("\nCtrl+C received. Initiating shutdown...")
        shutdown_requested = True
        monitor_active = False # Signal reader thread to stop
        terminate_kiosk_process()
        # No sys.exit(0) here, let the main loop finish cleanup

def main():
    """Main watchdog logic."""
    # Explicitly declare global variables that are assigned within this function
    global kiosk_process, last_output_time, launch_successful
    global reader_thread, monitor_active, restart_count
    global shutdown_requested # <-- ADDED THIS LINE

    # --- Setup ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    kiosk_script_path = os.path.join(script_dir, KIOSK_SCRIPT)

    if not os.path.exists(kiosk_script_path):
        print_watchdog(f"ERROR: Kiosk script not found at '{kiosk_script_path}'")
        sys.exit(1)

    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)

    print_watchdog("Starting Kiosk Watchdog...")
    print_watchdog(f"Monitoring script: {kiosk_script_path}")
    print_watchdog(f"Success Marker: '{SUCCESS_MARKER}'")
    print_watchdog(f"Launch Timeout: {LAUNCH_TIMEOUT_SECONDS} seconds")
    print_watchdog(f"Max Restarts: {MAX_RESTARTS}")

    # --- Main Launch and Monitor Loop ---
    while restart_count <= MAX_RESTARTS and not shutdown_requested:
        # Reset flags for a new launch attempt
        launch_successful = False
        monitor_active = True # Re-activate monitoring for this attempt
        last_output_time = time.time() # Reset timer

        print_watchdog(f"\n--- Attempting Kiosk Launch (Attempt {restart_count + 1}/{MAX_RESTARTS + 1}) ---")

        cmd = [PYTHON_EXECUTABLE, "-u", kiosk_script_path]

        creationflags = 0
        if sys.platform == "win32":
            # CREATE_NEW_CONSOLE ensures it launches in a new console window
            # DETACHED_PROCESS can also be used but CREATE_NEW_CONSOLE is usually sufficient
            creationflags = subprocess.CREATE_NEW_CONSOLE

        try:
            kiosk_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                creationflags=creationflags
            )
            print_watchdog(f"Kiosk process launched (PID: {kiosk_process.pid}). Monitoring output...")

            reader_thread = threading.Thread(
                target=read_kiosk_output,
                args=(kiosk_process.stdout,),
                daemon=True
            )
            reader_thread.start()

            # --- Inner Monitoring Loop (during launch) ---
            # Stay in this loop until launch is successful, timeout, process exits, or shutdown requested
            while monitor_active and not launch_successful and kiosk_process.poll() is None and not shutdown_requested:
                # 1. Print any captured output
                try:
                    while not output_queue.empty():
                        line = output_queue.get_nowait()
                        print(line)
                except queue.Empty:
                    pass

                # 2. Check for timeout
                current_time = time.time()
                with lock:
                    time_since_last_output = current_time - last_output_time

                if time_since_last_output > LAUNCH_TIMEOUT_SECONDS:
                    print_watchdog(f"TIMEOUT: No output from kiosk for {LAUNCH_TIMEOUT_SECONDS} seconds during launch.")
                    monitor_active = False # Signal reader thread to stop
                    terminate_kiosk_process()
                    restart_count += 1
                    break # Exit inner loop

                # 3. Sleep briefly
                time.sleep(POLL_INTERVAL_SECONDS)

            # --- Post Inner Loop ---

            # Ensure reader thread is stopped gracefully
            if monitor_active:
                 monitor_active = False

            if reader_thread and reader_thread.is_alive():
                 print_watchdog("Waiting for reader thread to join...")
                 reader_thread.join(timeout=2.0)
                 if reader_thread.is_alive():
                      print_watchdog("Reader thread did not join cleanly.")

            # Drain any remaining output
            try:
                 while not output_queue.empty():
                      line = output_queue.get_nowait()
                      print(line)
            except queue.Empty:
                 pass

            # Check status after monitoring attempt
            process_return_code = kiosk_process.poll() if kiosk_process else None

            if launch_successful:
                print_watchdog("Kiosk launch successful. Watchdog is now passively monitoring...")
                # Wait for the process to exit normally or for SIGINT
                try:
                     while kiosk_process and kiosk_process.poll() is None and not shutdown_requested:
                          time.sleep(1) # Passive wait
                     if not shutdown_requested and kiosk_process and kiosk_process.returncode is not None:
                         print_watchdog(f"Kiosk process exited normally (Return Code: {kiosk_process.returncode}).")
                except Exception as e:
                     print_watchdog(f"Error during passive wait: {e}")
                finally:
                    terminate_kiosk_process() # Ensure cleanup
                break # Exit the main restart loop

            elif shutdown_requested:
                print_watchdog("Shutdown requested during launch/monitoring loop.")
                break # Exit main loop

            elif process_return_code is not None:
                # Kiosk exited but didn't signal success. Could be a crash or quick failure.
                print_watchdog(f"Kiosk process exited prematurely during launch (Return Code: {process_return_code}).")
                restart_count += 1
                # Continue to next restart attempt in the main loop

            # If we reach here, it was a timeout, and we haven't exceeded MAX_RESTARTS.
            # The loop condition will check restart_count and continue if <= MAX_RESTARTS.

        except FileNotFoundError:
            print_watchdog(f"ERROR: Python executable not found at '{PYTHON_EXECUTABLE}'")
            shutdown_requested = True
            break # Exit main loop on critical error
        except Exception as e:
            print_watchdog(f"ERROR launching kiosk process: {e}")
            import traceback
            traceback.print_exc()
            restart_count += 1 # Treat launch error as a failed attempt
            if restart_count <= MAX_RESTARTS:
                print_watchdog("Pausing before retrying after launch error...")
                time.sleep(3)
            # Loop condition will check restart_count

    # --- End of Main Loop ---
    if shutdown_requested:
        print_watchdog("Watchdog shutdown complete.")
    elif restart_count > MAX_RESTARTS:
        print_watchdog(f"Kiosk failed to launch successfully after {MAX_RESTARTS + 1} attempts. Giving up.")
    else:
         # Should only happen if launch was successful and kiosk exited normally
         print_watchdog("Watchdog exiting normally.")

    # Final cleanup check
    terminate_kiosk_process()
    sys.exit(0 if launch_successful else 1)


if __name__ == "__main__":
    main()