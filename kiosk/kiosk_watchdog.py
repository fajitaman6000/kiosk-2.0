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
spinner_chars = ['|', '/', '-', '\\']
spinner_idx = 0

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
    global last_output_time, launch_successful
    try:
        while not stop_event.is_set():
            try:
                line = process_stdout.readline()
                if not line:
                    break
                line = line.strip()
                if line:
                    timestamp = time.time()
                    with lock:
                        last_output_time = timestamp
                        if not launch_successful and SUCCESS_MARKER in line:
                            launch_successful = True
                    output_queue.put(line)
                else:
                    time.sleep(0.01)
            except ValueError:
                break
            except Exception:
                break
    finally:
        pass

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
        monitor_active_flag_for_reader.clear()
        last_output_time = time.time()
        spinner_idx = 0

        clear_spinner_line() # Ensure clean line before launch attempt message
        print_watchdog(f"Attempting Kiosk Launch (Attempt {restart_count + 1}/{MAX_RESTARTS + 1})")
        
        cmd = [PYTHON_EXECUTABLE, "-u", kiosk_script_path]
        
        try:
            kiosk_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',
            )
            print_watchdog(f"Kiosk process launched (PID: {kiosk_process.pid}). Monitoring output...")

            reader_thread = threading.Thread(
                target=read_kiosk_output,
                args=(kiosk_process.stdout, monitor_active_flag_for_reader),
                daemon=True
            )
            reader_thread.start()

            while not launch_successful and not shutdown_requested and kiosk_process.poll() is None:
                drain_output_queue_and_print()
                with lock:
                    if launch_successful: break
                    time_since_last_output = time.time() - last_output_time
                
                if time_since_last_output > LAUNCH_TIMEOUT_SECONDS:
                    clear_spinner_line()
                    print_watchdog(f"TIMEOUT: No success marker/output from Kiosk for {LAUNCH_TIMEOUT_SECONDS}s.")
                    terminate_kiosk_process()
                    break 
                time.sleep(POLL_INTERVAL_SECONDS)

            drain_output_queue_and_print()

            if launch_successful and not shutdown_requested and kiosk_process.poll() is None:
                clear_spinner_line()
                print_watchdog("Kiosk launch successful.")
                while not shutdown_requested and kiosk_process.poll() is None:
                    drain_output_queue_and_print()
                    update_spinner()
                    time.sleep(PASSIVE_POLL_INTERVAL_SECONDS)
                
                clear_spinner_line()
                drain_output_queue_and_print()
                if not shutdown_requested and kiosk_process.poll() is not None:
                    print_watchdog(f"Kiosk process exited (Return Code: {kiosk_process.returncode}).")
                terminate_kiosk_process()
                if not shutdown_requested:
                    break

            elif shutdown_requested:
                pass
            else:
                clear_spinner_line()
                if kiosk_process and kiosk_process.poll() is None:
                     print_watchdog("Ensuring kiosk process is terminated after failed launch.")
                     terminate_kiosk_process()
                elif kiosk_process:
                     print_watchdog(f"Kiosk process failed to launch successfully (exited with code: {kiosk_process.poll()}).")
                restart_count += 1
            
            monitor_active_flag_for_reader.set()
            if reader_thread and reader_thread.is_alive():
                reader_thread.join(timeout=1.0)
            drain_output_queue_and_print()

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