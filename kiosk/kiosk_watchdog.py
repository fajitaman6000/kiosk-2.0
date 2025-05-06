# launcher_watchdog.py
import subprocess
import sys
import os
import time
import threading
import signal
import queue
from colorama import init as colorama_init, Fore, Style

# Initialize colorama
colorama_init(autoreset=True) # autoreset=True automatically adds Style.RESET_ALL after each print

# --- Configuration ---
KIOSK_SCRIPT = "kiosk.py"
PYTHON_EXECUTABLE = sys.executable
SUCCESS_MARKER = "[kiosk main] KioskApp initialization complete."
LAUNCH_TIMEOUT_SECONDS = 25
MAX_RESTARTS = 5
POLL_INTERVAL_SECONDS = 0.1
PASSIVE_POLL_INTERVAL_SECONDS = 0.5
TERMINATE_WAIT_SECONDS = 2

# --- New Heartbeat Configuration ---
HEARTBEAT_MARKER = "[HEARTBEAT_KIOSK_ALIVE]"
# Kiosk.py should send a heartbeat MORE frequently than this timeout.
# E.g., if Kiosk sends every 5s, a 15-20s timeout here is reasonable.
HEARTBEAT_TIMEOUT_SECONDS = 20
# This is for Kiosk's internal reference if needed, Watchdog mainly uses HEARTBEAT_TIMEOUT_SECONDS
# EXPECTED_HEARTBEAT_INTERVAL_SECONDS = 5 # Kiosk should aim to send heartbeats around this often

# --- Globals ---
kiosk_process = None
shutdown_requested = False
launch_successful = False
last_output_time = time.time()
output_queue = queue.Queue()
reader_thread = None
monitor_active_flag_for_reader = threading.Event()
restart_count = 0
lock = threading.Lock()
spinner_chars = ["⠁",
			"⠂",
			"⠄",
			"⡀",
			"⡈",
			"⡐",
			"⡠",
			"⣀",
			"⣁",
			"⣂",
			"⣄",
			"⣌",
			"⣔",
			"⣤",
			"⣥",
			"⣦",
			"⣮",
			"⣶",
			"⣷",
			"⣿",
			"⡿",
			"⠿",
			"⢟",
			"⠟",
			"⡛",
			"⠛",
			"⠫",
			"⢋",
			"⠋",
			"⠍",
			"⡉",
			"⠉",
			"⠑",
			"⠡",
			"⢁"]
spinner_idx = 0
last_heartbeat_time = 0.0 # NEW: Tracks time of the last received heartbeat

# --- Functions ---

def print_watchdog(message):
    # Using f-string to embed color codes directly
    # Style.RESET_ALL is implicitly handled by colorama_init(autoreset=True) at the end of the print
    sys.stdout.write(f"\r{Fore.RED}[WATCHDOG]{Style.RESET_ALL} {message}{' ' * 20}\n")
    sys.stdout.flush()

def print_kiosk_line(line):
    kiosk_tag = f"{Fore.GREEN}[KIOSK]{Style.RESET_ALL}"
    if launch_successful and not shutdown_requested:
        sys.stdout.write("\r" + " " * 100 + "\r") # Clear spinner line (make it wide enough)
        sys.stdout.write(f"{kiosk_tag} {line}\n")
        update_spinner() # Redraw spinner
    else:
        sys.stdout.write(f"{kiosk_tag} {line}\n")
    sys.stdout.flush()


def update_spinner():
    global spinner_idx
    if launch_successful and not shutdown_requested:
        char = spinner_chars[spinner_idx]
        # Color the [WATCHDOG] part of the spinner message
        watchdog_spinner_tag = f"{Fore.RED}[WATCHDOG]{Style.RESET_ALL}"
        sys.stdout.write(f"\r{watchdog_spinner_tag} Passively monitoring... {char} (Ctrl+C to exit)")
        sys.stdout.flush()
        spinner_idx = (spinner_idx + 1) % len(spinner_chars)

def clear_spinner_line():
    if launch_successful: # Only clear if spinner might have been active
        sys.stdout.write("\r" + " " * 100 + "\r") # Clear the line (make it wide enough)
        sys.stdout.flush()


def read_kiosk_output(process_stdout, stop_event):
    global last_output_time, launch_successful, last_heartbeat_time
    try:
        while not stop_event.is_set():
            try:
                line = process_stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    timestamp = time.time()
                    is_heartbeat = (line == HEARTBEAT_MARKER)
                    
                    with lock:
                        if is_heartbeat:
                            last_heartbeat_time = timestamp
                            # Heartbeat is not "user output" and shouldn't reset launch timeout logic
                            # It also shouldn't be printed to the console as regular KIOSK output.
                            continue # Skip queuing this line
                        
                        # For any other non-heartbeat output:
                        last_output_time = timestamp 
                        if not launch_successful and SUCCESS_MARKER in line:
                            launch_successful = True
                            # Important: When launch is successful, immediately set last_heartbeat_time.
                            # This gives kiosk.py HEARTBEAT_TIMEOUT_SECONDS to send its first actual heartbeat.
                            last_heartbeat_time = timestamp 
                    
                    if not is_heartbeat: # Only queue non-heartbeat lines for display
                        output_queue.put(line)
                else:
                    # Small sleep if readline returns empty but stream not closed (e.g. process busy)
                    time.sleep(0.01) 
            except ValueError: # Raised if stream is closed while readline is active
                break
            except Exception: # Catch other potential readline errors
                break
    finally:
        pass # Thread will exit

def terminate_kiosk_process():
    global kiosk_process
    if kiosk_process and kiosk_process.poll() is None:
        clear_spinner_line()
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
        except Exception:
            print_watchdog(f"Error during kiosk process termination (PID: {kiosk_process.pid}).")
        kiosk_process = None

def signal_handler(sig, frame):
    global shutdown_requested
    if not shutdown_requested:
        clear_spinner_line()
        # Manually add newline because the default print_watchdog adds one after the \r
        sys.stdout.write(f"\n{Fore.RED}[WATCHDOG]{Style.RESET_ALL} Ctrl+C received. Initiating shutdown...\n")
        sys.stdout.flush()
        shutdown_requested = True
        monitor_active_flag_for_reader.set()
        terminate_kiosk_process()

def drain_output_queue_and_print():
    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            print_kiosk_line(line)
        except queue.Empty:
            break

def main():
    global kiosk_process, last_output_time, launch_successful
    global reader_thread, restart_count, shutdown_requested, spinner_idx

    print_watchdog("Starting Kiosk Watchdog...")
    print_watchdog(f"Monitoring script: {KIOSK_SCRIPT}")
    # ... other initial watchdog messages

    script_dir = os.path.dirname(os.path.abspath(__file__))
    kiosk_script_path = os.path.join(script_dir, KIOSK_SCRIPT)

    if not os.path.exists(kiosk_script_path):
        print_watchdog(f"ERROR: Kiosk script not found: '{kiosk_script_path}'")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    while restart_count <= MAX_RESTARTS and not shutdown_requested:
        launch_successful = False
        kiosk_run_failed_after_launch = False # NEW: True if kiosk fails *after* successful launch (e.g. heartbeat)
        
        monitor_active_flag_for_reader.clear()
        last_output_time = time.time()
        # last_heartbeat_time will be set upon successful launch or first heartbeat
        spinner_idx = 0

        clear_spinner_line()
        print_watchdog(f"Attempting Kiosk Launch (Attempt {restart_count + 1}/{MAX_RESTARTS + 1})")
        
        cmd = [PYTHON_EXECUTABLE, "-u", kiosk_script_path]
        
        try:
            kiosk_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding='utf-8', errors='replace',
            )
            print_watchdog(f"Kiosk process launched (PID: {kiosk_process.pid}). Monitoring output...")

            reader_thread = threading.Thread(
                target=read_kiosk_output,
                args=(kiosk_process.stdout, monitor_active_flag_for_reader),
                daemon=True
            )
            reader_thread.start()

            # === Launch Monitoring Phase ===
            launch_start_time = time.time()
            while not launch_successful and not shutdown_requested and kiosk_process.poll() is None:
                drain_output_queue_and_print()
                with lock:
                    if launch_successful: break # Success marker found by reader thread
                    # Check for launch timeout based on actual launch duration, not just last output
                    if (time.time() - launch_start_time > LAUNCH_TIMEOUT_SECONDS) and \
                       (time.time() - last_output_time > LAUNCH_TIMEOUT_SECONDS / 2) : # Allow some silence if still starting
                        clear_spinner_line()
                        print_watchdog(f"TIMEOUT: Kiosk launch exceeded {LAUNCH_TIMEOUT_SECONDS}s or no output.")
                        terminate_kiosk_process()
                        kiosk_run_failed_after_launch = True # Treat as a run failure for restart logic
                        break 
                time.sleep(POLL_INTERVAL_SECONDS)
            drain_output_queue_and_print() # Process any final output from launch phase

            # === Passive Monitoring Phase (if launch was successful) ===
            if launch_successful and not shutdown_requested and kiosk_process.poll() is None:
                clear_spinner_line()
                print_watchdog("Kiosk launch successful. Monitoring with heartbeat...")
                # last_heartbeat_time was set by read_kiosk_output when SUCCESS_MARKER was seen.

                while not shutdown_requested and kiosk_process.poll() is None:
                    drain_output_queue_and_print()
                    time_since_last_heartbeat = 0
                    with lock: # Read last_heartbeat_time safely
                        time_since_last_heartbeat = time.time() - last_heartbeat_time
                
                    if time_since_last_heartbeat > HEARTBEAT_TIMEOUT_SECONDS:
                        clear_spinner_line()
                        print_watchdog(f"HEARTBEAT TIMEOUT: Kiosk unresponsive for over {HEARTBEAT_TIMEOUT_SECONDS}s.")
                        terminate_kiosk_process()
                        kiosk_run_failed_after_launch = True # Mark as failed for restart
                        break # Exit passive monitoring

                    update_spinner()
                    time.sleep(PASSIVE_POLL_INTERVAL_SECONDS)
                
                # After passive monitoring loop (due to kiosk exit, heartbeat timeout, or shutdown_requested)
                clear_spinner_line()
                drain_output_queue_and_print()

                if not shutdown_requested and not kiosk_run_failed_after_launch and kiosk_process and kiosk_process.poll() is not None:
                    # Kiosk exited on its own cleanly *after* successful launch & *no* heartbeat failure
                    print_watchdog(f"Kiosk process exited cleanly (Return Code: {kiosk_process.returncode}). Watchdog will now exit.")
                    shutdown_requested = True # Signal watchdog to exit, not restart

            # === Post-monitoring / Pre-restart Logic ===
            monitor_active_flag_for_reader.set() # Signal reader thread to stop
            if reader_thread and reader_thread.is_alive():
                reader_thread.join(timeout=1.0) # Wait for reader to finish
            drain_output_queue_and_print() # Final drain after reader stops

            if shutdown_requested: # If Ctrl+C or clean kiosk exit (which sets shutdown_requested)
                terminate_kiosk_process() # Ensure child is gone
                break # Exit the main watchdog restart loop

            # If we reach here, shutdown was NOT requested (so no clean exit or Ctrl+C that sets it)
            # Now determine if a restart is warranted.
            should_increment_restart = False
            if kiosk_run_failed_after_launch: # Covers launch timeout OR heartbeat timeout
                print_watchdog("Kiosk run failed (timeout or heartbeat).")
                should_increment_restart = True
            elif not launch_successful: # Covers other launch failures (e.g., kiosk crashed before success marker)
                if kiosk_process and kiosk_process.poll() is not None:
                    print_watchdog(f"Kiosk process failed to launch (exited with code: {kiosk_process.poll()}).")
                else:
                    print_watchdog("Kiosk launch was not successful (unknown reason).")
                should_increment_restart = True
            
            if should_increment_restart:
                restart_count += 1

            # Ensure process is terminated if it's somehow still running before a potential restart or giving up
            if kiosk_process and kiosk_process.poll() is None:
                print_watchdog("Ensuring kiosk process is terminated before next step.")
                terminate_kiosk_process()
            kiosk_process = None # Clear it

            if restart_count <= MAX_RESTARTS and should_increment_restart:
                print_watchdog(f"Pausing before retry attempt {restart_count + 1}/{MAX_RESTARTS + 1}...")
                time.sleep(2) # Or your preferred retry delay
            elif not shutdown_requested: # Exceeded MAX_RESTARTS or no failure indicated a restart
                if restart_count > MAX_RESTARTS:
                    print_watchdog(f"Kiosk failed after {restart_count} attempts. Watchdog giving up.")
                # If no increment and not shutting down, this implies a state not leading to restart or exit
                # This path should ideally not be hit if logic is correct, leads to watchdog exit.
                break 

        except FileNotFoundError:
            print_watchdog(f"ERROR: Python executable not found: '{PYTHON_EXECUTABLE}'")
            shutdown_requested = True
        except Exception as e:
            clear_spinner_line()
            print_watchdog(f"CRITICAL WATCHDOG ERROR: {e}")
            restart_count += 1
            if restart_count <= MAX_RESTARTS and not shutdown_requested:
                print_watchdog("Pausing before retry...")
                time.sleep(2)
        
        if kiosk_process and kiosk_process.poll() is None:
            terminate_kiosk_process()

    clear_spinner_line()
    if shutdown_requested:
        # SIGINT handler already printed its message
        print_watchdog("Watchdog shutdown sequence complete.")
    elif restart_count > MAX_RESTARTS:
        print_watchdog(f"Kiosk failed after {restart_count} attempts. Watchdog giving up.")
    else:
        print_watchdog("Watchdog processing finished.")

    if reader_thread and reader_thread.is_alive():
        monitor_active_flag_for_reader.set()
        reader_thread.join(timeout=1.0)
    drain_output_queue_and_print()
    if kiosk_process and kiosk_process.poll() is None:
        terminate_kiosk_process()

    sys.exit(0 if launch_successful and not shutdown_requested else 1)

if __name__ == "__main__":
    main()