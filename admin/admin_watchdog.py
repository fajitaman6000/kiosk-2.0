# admin_watchdog.py
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
ADMIN_SCRIPT_NAME = "admin_main.py"
PYTHON_EXECUTABLE = sys.executable
# Ensure this marker is reliably printed by admin_main.py upon successful initialization
ADMIN_SUCCESS_MARKER = "[main]Starting admin application..."
LAUNCH_TIMEOUT_SECONDS = 30 # Admin app might take a bit longer to initialize GUI
MAX_RESTARTS = 5
POLL_INTERVAL_SECONDS = 0.1
PASSIVE_POLL_INTERVAL_SECONDS = 0.5
TERMINATE_WAIT_SECONDS = 3 # Give admin GUI a bit more time to close

# --- Heartbeat Configuration ---
# IMPORTANT: admin_main.py currently does NOT send a periodic stdout heartbeat.
# If this watchdog is used as-is, it WILL restart the admin app after ADMIN_HEARTBEAT_TIMEOUT_SECONDS
# if the admin app doesn't print ADMIN_HEARTBEAT_MARKER.
# Consider this a feature to detect a completely frozen/silent admin app,
# or modify admin_main.py to send heartbeats if continuous active monitoring is needed.
ADMIN_HEARTBEAT_MARKER = "[ADMIN_HEARTBEAT_ALIVE]" # Hypothetical marker
ADMIN_HEARTBEAT_TIMEOUT_SECONDS = 15 # Allow admin to be silent for longer

# --- Globals ---
admin_process = None
shutdown_requested = False
launch_successful = False
last_output_time = time.time()
output_queue = queue.Queue()
reader_thread = None
monitor_active_flag_for_reader = threading.Event()
restart_count = 0
lock = threading.Lock()
spinner_chars = ["⠁", "⠂", "⠄", "⡀", "⡈", "⡐", "⡠", "⣀", "⣁", "⣂", "⣄", "⣌", "⣔", "⣤", "⣥", "⣦", "⣮", "⣶", "⣷", "⣿", "⡿", "⠿", "⢟", "⠟", "⡛", "⠛", "⠫", "⢋", "⠋", "⠍", "⡉", "⠉", "⠑", "⠡", "⢁"]
spinner_idx = 0
last_heartbeat_time = 0.0

# --- Functions ---

def print_watchdog(message):
    sys.stdout.write(f"\r{Fore.RED}[WATCHDOG]{Style.RESET_ALL} {message}{' ' * 20}\n")
    sys.stdout.flush()

def print_admin_line(line):
    admin_tag = f"{Fore.BLUE}[ADMIN]{Style.RESET_ALL}"
    if launch_successful and not shutdown_requested:
        sys.stdout.write("\r" + " " * 100 + "\r") # Clear spinner line
        sys.stdout.write(f"{admin_tag} {line}\n")
        update_spinner() # Redraw spinner
    else:
        sys.stdout.write(f"{admin_tag} {line}\n")
    sys.stdout.flush()

def update_spinner():
    global spinner_idx
    if launch_successful and not shutdown_requested:
        char = spinner_chars[spinner_idx]
        watchdog_spinner_tag = f"{Fore.RED}[WATCHDOG]{Style.RESET_ALL}"
        sys.stdout.write(f"\r{watchdog_spinner_tag} Passively monitoring Admin... {char} (Ctrl+C to exit)")
        sys.stdout.flush()
        spinner_idx = (spinner_idx + 1) % len(spinner_chars)

def clear_spinner_line():
    if launch_successful:
        sys.stdout.write("\r" + " " * 100 + "\r")
        sys.stdout.flush()

def read_admin_output(process_stdout, stop_event):
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
                    is_heartbeat = (line == ADMIN_HEARTBEAT_MARKER)
                    
                    with lock:
                        if is_heartbeat:
                            last_heartbeat_time = timestamp
                            # Heartbeat is not "user output" and shouldn't reset launch timeout logic
                            # It also shouldn't be printed to the console as regular ADMIN output.
                            continue # Skip queuing this line for printing
                        
                        last_output_time = timestamp 
                        if not launch_successful and ADMIN_SUCCESS_MARKER in line:
                            launch_successful = True
                            # When launch is successful, set last_heartbeat_time.
                            # This gives admin_main.py ADMIN_HEARTBEAT_TIMEOUT_SECONDS 
                            # to send its first actual heartbeat (if it's designed to).
                            last_heartbeat_time = timestamp 
                    
                    if not is_heartbeat: # Only queue non-heartbeat lines for display
                        output_queue.put(line)
                else:
                    time.sleep(0.01) 
            except ValueError:
                break
            except Exception:
                break
    finally:
        pass

def terminate_admin_process():
    global admin_process
    if admin_process and admin_process.poll() is None:
        clear_spinner_line()
        print_watchdog(f"Attempting to terminate Admin process (PID: {admin_process.pid})...")
        try:
            # For GUI applications, SIGTERM (terminate) is often better first
            admin_process.terminate()
            try:
                admin_process.wait(timeout=TERMINATE_WAIT_SECONDS)
                print_watchdog(f"Admin process (PID: {admin_process.pid}) terminated gracefully.")
            except subprocess.TimeoutExpired:
                print_watchdog(f"Admin process (PID: {admin_process.pid}) did not terminate, killing...")
                admin_process.kill()
                admin_process.wait()
                print_watchdog(f"Admin process (PID: {admin_process.pid}) killed.")
        except Exception as e:
            print_watchdog(f"Error during Admin process termination (PID: {admin_process.pid}): {e}")
        admin_process = None

def signal_handler(sig, frame):
    global shutdown_requested
    if not shutdown_requested:
        clear_spinner_line()
        sys.stdout.write(f"\n{Fore.RED}[WATCHDOG]{Style.RESET_ALL} Ctrl+C received. Initiating shutdown...\n")
        sys.stdout.flush()
        shutdown_requested = True
        monitor_active_flag_for_reader.set()
        terminate_admin_process()

def drain_output_queue_and_print():
    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            print_admin_line(line)
        except queue.Empty:
            break

def main():
    global admin_process, last_output_time, launch_successful
    global reader_thread, restart_count, shutdown_requested, spinner_idx, last_heartbeat_time

    print_watchdog("Starting Admin Watchdog...")
    print_watchdog(f"Monitoring script: {ADMIN_SCRIPT_NAME}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    admin_script_path = os.path.join(script_dir, ADMIN_SCRIPT_NAME)

    if not os.path.exists(admin_script_path):
        print_watchdog(f"ERROR: Admin script not found: '{admin_script_path}'")
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    while restart_count <= MAX_RESTARTS and not shutdown_requested:
        launch_successful = False
        admin_run_failed_after_launch = False
        
        monitor_active_flag_for_reader.clear()
        last_output_time = time.time()
        # last_heartbeat_time reset here implicitly by not being set until success/heartbeat
        spinner_idx = 0

        clear_spinner_line()
        print_watchdog(f"Attempting Admin Launch (Attempt {restart_count + 1}/{MAX_RESTARTS + 1})")
        
        cmd = [PYTHON_EXECUTABLE, "-u", admin_script_path]
        
        try:
            admin_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, encoding='utf-8', errors='replace',
                # cwd=script_dir # Ensuring admin_main.py runs in its own directory
            )
            print_watchdog(f"Admin process launched (PID: {admin_process.pid}). Monitoring output...")

            reader_thread = threading.Thread(
                target=read_admin_output,
                args=(admin_process.stdout, monitor_active_flag_for_reader),
                daemon=True
            )
            reader_thread.start()

            launch_start_time = time.time()
            while not launch_successful and not shutdown_requested and admin_process.poll() is None:
                drain_output_queue_and_print()
                with lock:
                    if launch_successful: break
                    if (time.time() - launch_start_time > LAUNCH_TIMEOUT_SECONDS) and \
                       (time.time() - last_output_time > LAUNCH_TIMEOUT_SECONDS / 2) :
                        clear_spinner_line()
                        print_watchdog(f"TIMEOUT: Admin launch exceeded {LAUNCH_TIMEOUT_SECONDS}s or no output.")
                        terminate_admin_process()
                        admin_run_failed_after_launch = True
                        break 
                time.sleep(POLL_INTERVAL_SECONDS)
            drain_output_queue_and_print()

            if launch_successful and not shutdown_requested and admin_process.poll() is None:
                clear_spinner_line()
                print_watchdog("Admin launch successful. Monitoring with heartbeat/activity...")
                # last_heartbeat_time was set by read_admin_output when ADMIN_SUCCESS_MARKER was seen.

                while not shutdown_requested and admin_process.poll() is None:
                    drain_output_queue_and_print()
                    time_since_last_heartbeat = 0
                    with lock:
                        time_since_last_heartbeat = time.time() - last_heartbeat_time
                
                    # This will trigger if admin_main.py doesn't send ADMIN_HEARTBEAT_MARKER
                    # or doesn't print any output that resets last_heartbeat_time (via ADMIN_SUCCESS_MARKER logic).
                    if time_since_last_heartbeat > ADMIN_HEARTBEAT_TIMEOUT_SECONDS:
                        clear_spinner_line()
                        print_watchdog(f"HEARTBEAT/ACTIVITY TIMEOUT: Admin unresponsive for over {ADMIN_HEARTBEAT_TIMEOUT_SECONDS}s.")
                        terminate_admin_process()
                        admin_run_failed_after_launch = True
                        break

                    update_spinner()
                    time.sleep(PASSIVE_POLL_INTERVAL_SECONDS)
                
                clear_spinner_line()
                drain_output_queue_and_print()

                if not shutdown_requested and not admin_run_failed_after_launch and admin_process and admin_process.poll() is not None:
                    print_watchdog(f"Admin process exited cleanly (Return Code: {admin_process.returncode}). Watchdog will now exit.")
                    shutdown_requested = True

            monitor_active_flag_for_reader.set()
            if reader_thread and reader_thread.is_alive():
                reader_thread.join(timeout=1.0)
            drain_output_queue_and_print()

            if shutdown_requested:
                terminate_admin_process()
                break

            should_increment_restart = False
            if admin_run_failed_after_launch:
                print_watchdog("Admin run failed (timeout or heartbeat/activity).")
                should_increment_restart = True
            elif not launch_successful:
                if admin_process and admin_process.poll() is not None:
                    print_watchdog(f"Admin process failed to launch (exited with code: {admin_process.poll()}).")
                else:
                    print_watchdog("Admin launch was not successful (unknown reason).")
                should_increment_restart = True
            
            if should_increment_restart:
                restart_count += 1

            if admin_process and admin_process.poll() is None:
                print_watchdog("Ensuring Admin process is terminated before next step.")
                terminate_admin_process()
            admin_process = None

            if restart_count <= MAX_RESTARTS and should_increment_restart:
                print_watchdog(f"Pausing before retry attempt {restart_count + 1}/{MAX_RESTARTS + 1}...")
                time.sleep(3) # Slightly longer pause for admin
            elif not shutdown_requested:
                if restart_count > MAX_RESTARTS:
                    print_watchdog(f"Admin failed after {restart_count} attempts. Watchdog giving up.")
                break 

        except FileNotFoundError:
            print_watchdog(f"ERROR: Python executable not found: '{PYTHON_EXECUTABLE}'")
            shutdown_requested = True
        except Exception as e:
            clear_spinner_line()
            print_watchdog(f"CRITICAL WATCHDOG ERROR: {e}")
            import traceback
            traceback.print_exc() # Print full traceback for watchdog errors
            restart_count += 1
            if restart_count <= MAX_RESTARTS and not shutdown_requested:
                print_watchdog("Pausing before retry...")
                time.sleep(3)
        
        if admin_process and admin_process.poll() is None:
            terminate_admin_process()

    clear_spinner_line()
    if shutdown_requested:
        print_watchdog("Admin Watchdog shutdown sequence complete.")
    elif restart_count > MAX_RESTARTS:
        print_watchdog(f"Admin failed after {restart_count} attempts. Watchdog giving up.")
    else:
        print_watchdog("Admin Watchdog processing finished.")

    if reader_thread and reader_thread.is_alive():
        monitor_active_flag_for_reader.set()
        reader_thread.join(timeout=1.0)
    drain_output_queue_and_print()
    if admin_process and admin_process.poll() is None:
        terminate_admin_process()

    sys.exit(0 if launch_successful and not shutdown_requested else 1)

if __name__ == "__main__":
    main()