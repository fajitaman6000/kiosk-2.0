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
POLL_INTERVAL_SECONDS = 0.5  # How often to check for hangs/success/output
TERMINATE_WAIT_SECONDS = 2   # Time to wait after terminate before kill

# --- Globals ---
kiosk_process = None
shutdown_requested = False
launch_successful = False
last_output_time = time.time()
output_queue = queue.Queue()
reader_thread = None
# 'monitor_active' will now primarily signal the reader thread to stop during shutdown or termination.
# The reader thread will otherwise attempt to read as long as the process/pipe is alive.
monitor_active_flag_for_reader = threading.Event() # Used to signal reader thread to stop
restart_count = 0
lock = threading.Lock()

# --- Functions ---

def print_watchdog(message):
    print(f"[WATCHDOG] {message}", flush=True)

def read_kiosk_output(process_stdout, stop_event):
    global last_output_time, launch_successful # Modified by this thread

    try:
        print_watchdog(f"Output reader thread started (PID: {os.getpid()}, Thread: {threading.get_ident()}).")
        while not stop_event.is_set():
            try:
                line = process_stdout.readline()
                if not line:
                    if not stop_event.is_set():
                        print_watchdog("Kiosk stdout stream ended (readline returned empty).")
                    break # Pipe closed or EOF

                line = line.strip()
                if line:
                    timestamp = time.time()
                    with lock: # Protect shared variables
                        last_output_time = timestamp
                        if not launch_successful and SUCCESS_MARKER in line:
                            launch_successful = True
                            print_watchdog(f"Success marker found: '{SUCCESS_MARKER}'")
                    output_queue.put(line)
                else:
                    # Empty line might mean the process is still alive but just printed a newline
                    # To prevent busy-looping on empty lines if readline doesn't block appropriately:
                    time.sleep(0.01)


            except ValueError: # I/O operation on closed file
                if not stop_event.is_set():
                    print_watchdog("Kiosk stdout pipe closed unexpectedly (ValueError).")
                break
            except Exception as e:
                if not stop_event.is_set():
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
    global kiosk_process
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
                kiosk_process.wait() # Wait for kill to complete
                print_watchdog(f"Kiosk process (PID: {kiosk_process.pid}) killed.")
        except ProcessLookupError: # Process already died
            print_watchdog(f"Kiosk process (PID: {kiosk_process.pid}) already exited.")
        except Exception as e:
            print_watchdog(f"Error terminating/killing kiosk process (PID: {kiosk_process.pid}): {e}")
        kiosk_process = None

def signal_handler(sig, frame):
    global shutdown_requested
    if not shutdown_requested: # Ensure this runs only once
        print_watchdog("\nCtrl+C received. Initiating shutdown...")
        shutdown_requested = True
        monitor_active_flag_for_reader.set() # Signal reader thread to stop
        terminate_kiosk_process()
        # Main loop will see shutdown_requested and exit

def drain_output_queue():
    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            print(line, flush=True)
        except queue.Empty:
            break

def main():
    global kiosk_process, last_output_time, launch_successful
    global reader_thread, restart_count, shutdown_requested

    script_dir = os.path.dirname(os.path.abspath(__file__))
    kiosk_script_path = os.path.join(script_dir, KIOSK_SCRIPT)

    if not os.path.exists(kiosk_script_path):
        print_watchdog(f"ERROR: Kiosk script not found at '{kiosk_script_path}'")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    print_watchdog("Starting Kiosk Watchdog...")
    # ... (print config messages)

    while restart_count <= MAX_RESTARTS and not shutdown_requested:
        launch_successful = False
        monitor_active_flag_for_reader.clear() # Reset for new launch
        last_output_time = time.time()

        print_watchdog(f"\n--- Attempting Kiosk Launch (Attempt {restart_count + 1}/{MAX_RESTARTS + 1}) ---")
        cmd = [PYTHON_EXECUTABLE, "-u", kiosk_script_path]
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_CONSOLE

        try:
            kiosk_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, # Capture stderr to the same pipe
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
                creationflags=creationflags
            )
            print_watchdog(f"Kiosk process launched (PID: {kiosk_process.pid}). Monitoring output...")

            reader_thread = threading.Thread(
                target=read_kiosk_output,
                args=(kiosk_process.stdout, monitor_active_flag_for_reader),
                daemon=True
            )
            reader_thread.start()

            # --- Launch Monitoring Loop ---
            launch_monitoring_active = True
            while launch_monitoring_active and not shutdown_requested:
                drain_output_queue() # Always print output

                if kiosk_process.poll() is not None: # Process exited
                    print_watchdog(f"Kiosk process exited during launch phase (Return Code: {kiosk_process.returncode}).")
                    launch_monitoring_active = False # Exit this loop
                    # launch_successful remains False
                    break

                with lock: # Access shared launch_successful and last_output_time
                    if launch_successful:
                        print_watchdog("Kiosk launch reported successful by reader thread.")
                        launch_monitoring_active = False # Exit this loop
                        break

                    time_since_last_output = time.time() - last_output_time

                if time_since_last_output > LAUNCH_TIMEOUT_SECONDS:
                    print_watchdog(f"TIMEOUT: No output from kiosk for {LAUNCH_TIMEOUT_SECONDS} seconds during launch.")
                    terminate_kiosk_process() # Terminate before concluding this attempt
                    launch_monitoring_active = False # Exit this loop
                    # launch_successful remains False
                    break
                
                time.sleep(POLL_INTERVAL_SECONDS)
            
            # --- Post Launch Monitoring ---
            drain_output_queue() # Drain any remaining output from launch phase

            if launch_successful and not shutdown_requested and kiosk_process.poll() is None:
                print_watchdog("Kiosk launch successful. Watchdog is now passively monitoring...")
                while not shutdown_requested and kiosk_process.poll() is None:
                    drain_output_queue()
                    time.sleep(POLL_INTERVAL_SECONDS) # Passive wait, regularly check for output/exit
                
                drain_output_queue() # Final drain after passive monitoring
                if not shutdown_requested and kiosk_process.poll() is not None:
                    print_watchdog(f"Kiosk process exited passively (Return Code: {kiosk_process.returncode}).")
                # If shutdown_requested, signal handler/main loop condition handles it
                terminate_kiosk_process() # Ensure cleanup if it exited on its own
                break # Exit the main restart loop as it was successful

            elif shutdown_requested:
                print_watchdog("Shutdown requested during or after launch phase.")
                # Signal handler already called terminate_kiosk_process and set flag for reader.
                # Main loop `while` condition will catch `shutdown_requested`.
                pass

            else: # Launch not successful (timeout or premature exit)
                if kiosk_process.poll() is None: # It was a timeout, process might still be running
                    print_watchdog("Launch timeout occurred, ensuring process is terminated.")
                    terminate_kiosk_process() # Ensure termination after timeout
                # If process already exited, its return code was logged.
                print_watchdog("Kiosk launch failed.")
                restart_count += 1
            
            # Cleanup reader thread for this attempt if it's still going
            monitor_active_flag_for_reader.set() # Signal reader to stop
            if reader_thread and reader_thread.is_alive():
                print_watchdog("Waiting for reader thread to join after attempt...")
                reader_thread.join(timeout=3.0) # Increased timeout slightly
                if reader_thread.is_alive():
                    print_watchdog("Reader thread did not join cleanly after attempt.")
            drain_output_queue() # Drain any final output from reader

        except FileNotFoundError:
            print_watchdog(f"ERROR: Python executable not found at '{PYTHON_EXECUTABLE}'")
            shutdown_requested = True # Critical error, stop
        except Exception as e:
            print_watchdog(f"ERROR launching/monitoring kiosk process: {e}")
            import traceback
            traceback.print_exc()
            restart_count += 1
            if restart_count <= MAX_RESTARTS and not shutdown_requested:
                print_watchdog("Pausing before retrying after error...")
                time.sleep(3)
        
        if kiosk_process and kiosk_process.poll() is None: # If loop broken for restart but process alive
            print_watchdog("Ensuring kiosk process from failed attempt is terminated...")
            terminate_kiosk_process() # Clean up before next attempt

    # --- End of Main Loop ---
    if shutdown_requested:
        print_watchdog("Watchdog shutdown complete.")
    elif restart_count > MAX_RESTARTS:
        print_watchdog(f"Kiosk failed to launch successfully after {restart_count} attempts. Giving up.")
    else:
        print_watchdog("Watchdog exiting (kiosk was successful and then exited, or other).")

    # Final cleanup of reader thread if it somehow persisted (shouldn't happen with daemon=True and join)
    monitor_active_flag_for_reader.set()
    if reader_thread and reader_thread.is_alive():
        reader_thread.join(timeout=1.0)
    drain_output_queue() # Very final drain

    # Ensure kiosk_process is None if terminated
    if kiosk_process and kiosk_process.poll() is None:
         terminate_kiosk_process()

    sys.exit(0 if launch_successful and not shutdown_requested else 1)


if __name__ == "__main__":
    main()