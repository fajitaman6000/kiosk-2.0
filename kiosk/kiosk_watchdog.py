# launcher_watchdog.py
import subprocess
import sys
import os
import time
import threading
import signal
import queue
import json # Added for parsing watchdog commands
import socket # Added for watchdog command listener
from colorama import init as colorama_init, Fore, Style
import datetime  # For timestamps

# Initialize colorama
colorama_init(autoreset=True) # autoreset=True automatically adds Style.RESET_ALL after each print

# --- Configuration ---
KIOSK_SCRIPT = "kiosk.py"
PYTHON_EXECUTABLE = sys.executable
SUCCESS_MARKER = "[kiosk main] KioskApp initialization complete."
LAUNCH_TIMEOUT_SECONDS = 25
MAX_RESTARTS = 5 # Set to -1 for unlimited automatic restarts after failures
POLL_INTERVAL_SECONDS = 0.1
PASSIVE_POLL_INTERVAL_SECONDS = 0.5
TERMINATE_WAIT_SECONDS = 2

# --- New Heartbeat Configuration ---
HEARTBEAT_MARKER = "[HEARTBEAT_KIOSK_ALIVE]"
HEARTBEAT_TIMEOUT_SECONDS = 20

# --- New Watchdog Command Configuration ---
WATCHDOG_CMD_PORT = 12347

# --- Debug Mode Configuration ---
DEBUG_MODE = "--debug" in sys.argv
DEBUG_CRASH_TIME = 10 # Seconds before crash after successful launch

# --- New for Watchdog Log Broadcasting ---
WATCHDOG_LOG_BROADCAST_PORT = 12348  # Arbitrary port for admin to listen on
ADMIN_BROADCAST_IP = '255.255.255.255'  # Default to broadcast; can be set to admin IP if known
LOG_SEND_INTERVAL = 10  # seconds
watchdog_log_buffer = []  # List of dicts: {timestamp, text, is_error}
watchdog_log_lock = threading.Lock()
watchdog_log_sender_thread = None
watchdog_log_sender_stop_event = threading.Event()

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
spinner_chars = ["⠁", "⠂", "⠄", "⡀", "⡈", "⡐", "⡠", "⣀", "⣁", "⣂", "⣄", "⣌", "⣔", "⣤", "⣥", "⣦", "⣮", "⣶", "⣷", "⣿", "⡿", "⠿", "⢟", "⠟", "⡛", "⠛", "⠫", "⢋", "⠋", "⠍", "⡉", "⠉", "⠑", "⠡", "⢁"]
spinner_idx = 0
last_heartbeat_time = 0.0
is_crash_restart = False  # Track if this is a crash restart

# --- Globals for Watchdog Commands ---
remote_restart_requested = False
watchdog_cmd_listener_thread = None
watchdog_cmd_listener_stop_event = threading.Event()
watchdog_cmd_socket = None


# --- Functions ---

def print_watchdog(message):
    sys.stdout.write(f"\r{Fore.RED}[WATCHDOG]{Style.RESET_ALL} {message}{' ' * 20}\n")
    sys.stdout.flush()
    add_to_watchdog_log(message, is_error=False)

def print_watchdog_idle(message):
    sys.stdout.write(f"\r{Fore.CYAN}[WATCHDOG-IDLE]{Style.RESET_ALL} {message}{' ' * 20}\n")
    sys.stdout.flush()

def print_kiosk_line(line):
    kiosk_tag = f"{Fore.GREEN}[KIOSK]{Style.RESET_ALL}"
    if launch_successful and not shutdown_requested and not (MAX_RESTARTS != -1 and restart_count > MAX_RESTARTS):
        sys.stdout.write("\r" + " " * 100 + "\r") 
        sys.stdout.write(f"{kiosk_tag} {line}\n")
        update_spinner() 
    else:
        sys.stdout.write(f"{kiosk_tag} {line}\n")
    sys.stdout.flush()
    add_to_watchdog_log(line, is_error=False)


def update_spinner():
    global spinner_idx
    if launch_successful and not shutdown_requested:
        char = spinner_chars[spinner_idx]
        watchdog_spinner_tag = f"{Fore.RED}[WATCHDOG]{Style.RESET_ALL}"
        sys.stdout.write(f"\r{watchdog_spinner_tag} Passively monitoring... {char} (Ctrl+C to exit)")
        sys.stdout.flush()
        spinner_idx = (spinner_idx + 1) % len(spinner_chars)

def update_spinner_idle():
    global spinner_idx
    if not shutdown_requested: 
        char = spinner_chars[spinner_idx]
        watchdog_spinner_tag = f"{Fore.CYAN}[WATCHDOG-IDLE]{Style.RESET_ALL}"
        sys.stdout.write(f"\r{watchdog_spinner_tag} Awaiting commands or Ctrl+C... {char}")
        sys.stdout.flush()
        spinner_idx = (spinner_idx + 1) % len(spinner_chars)

def clear_spinner_line():
    # Clear if spinner might have been active (running or idle)
    sys.stdout.write("\r" + " " * 100 + "\r") 
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
                            continue 
                        
                        last_output_time = timestamp 
                        if not launch_successful and SUCCESS_MARKER in line:
                            launch_successful = True
                            last_heartbeat_time = timestamp 
                    
                    if not is_heartbeat: 
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
        current_pid = kiosk_process.pid # Store PID before it might become None
        clear_spinner_line()
        print_watchdog(f"Attempting to terminate kiosk process (PID: {current_pid})...")
        try:
            kiosk_process.terminate()
            try:
                kiosk_process.wait(timeout=TERMINATE_WAIT_SECONDS)
                print_watchdog(f"Kiosk process (PID: {current_pid}) terminated gracefully.")
            except subprocess.TimeoutExpired:
                print_watchdog(f"Kiosk process (PID: {current_pid}) did not terminate, killing...")
                kiosk_process.kill()
                kiosk_process.wait() # Wait for kill to complete
                print_watchdog(f"Kiosk process (PID: {current_pid}) killed.")
        except Exception as e:
            print_watchdog(f"Error during kiosk process termination (PID: {current_pid}): {e}")
        finally: # Ensure kiosk_process is set to None after termination attempt
             kiosk_process = None


def signal_handler(sig, frame):
    global shutdown_requested
    if not shutdown_requested: # Prevent multiple calls
        clear_spinner_line()
        sys.stdout.write(f"\n{Fore.RED}[WATCHDOG]{Style.RESET_ALL} Ctrl+C received. Initiating shutdown...\n")
        sys.stdout.flush()
        
        shutdown_requested = True
        monitor_active_flag_for_reader.set() 
        watchdog_cmd_listener_stop_event.set() 
        terminate_kiosk_process()

def drain_output_queue_and_print():
    while not output_queue.empty():
        try:
            line = output_queue.get_nowait()
            print_kiosk_line(line)
        except queue.Empty:
            break

def listen_for_watchdog_commands():
    global remote_restart_requested, watchdog_cmd_socket
    
    try:
        watchdog_cmd_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        watchdog_cmd_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        watchdog_cmd_socket.bind(('', WATCHDOG_CMD_PORT))
        watchdog_cmd_socket.settimeout(1.0) # Timeout to allow checking stop_event
        print_watchdog(f"Command listener started on UDP port {WATCHDOG_CMD_PORT}")

        while not watchdog_cmd_listener_stop_event.is_set():
            try:
                data, addr = watchdog_cmd_socket.recvfrom(1024)
                message_str = data.decode('utf-8')
                print_watchdog(f"Received command from {addr[0]}:{addr[1]}: {message_str}")
                try:
                    command = json.loads(message_str)
                    if command.get("type") == "restart_app":
                        print_watchdog("Processing 'restart_app' command.")
                        with lock: 
                            remote_restart_requested = True
                    elif command.get("type") == "reboot_kiosk":
                        print_watchdog("Processing 'reboot_kiosk' command.")
                        #print_watchdog("Reboot command doesn't exist yet in kiosk_watchdog.py")
                        os.system('shutdown /r /t 1')
                    else:
                        print_watchdog(f"Unknown command type received: {command.get('type')}")
                except json.JSONDecodeError:
                    print_watchdog(f"Invalid JSON in command from {addr[0]}:{addr[1]}: {message_str}")
            except socket.timeout:
                continue 
            except Exception as e:
                if not watchdog_cmd_listener_stop_event.is_set():
                    print_watchdog(f"Error in command listener: {e}")
                    time.sleep(1) 
    
    except Exception as e:
        print_watchdog(f"CRITICAL: Watchdog command listener failed to start/run: {e}")
    finally:
        if watchdog_cmd_socket:
            watchdog_cmd_socket.close()
            watchdog_cmd_socket = None
        print_watchdog("Command listener stopped.")

def send_watchdog_udp_message(payload, is_error=False):
    try:
        msg = {
            'type': 'watchdog_error' if is_error else 'watchdog_log',
            'computer_name': os.environ.get('COMPUTERNAME', 'unknown'),
            'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'log': payload
        }
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.sendto(json.dumps(msg).encode('utf-8'), (ADMIN_BROADCAST_IP, WATCHDOG_LOG_BROADCAST_PORT))
    except Exception as e:
        # Don't log this to buffer to avoid recursion
        sys.stdout.write(f"\n[WATCHDOG] Failed to send UDP log: {e}\n")
        sys.stdout.flush()

def watchdog_log_sender_loop():
    while not watchdog_log_sender_stop_event.is_set():
        time.sleep(LOG_SEND_INTERVAL)
        with watchdog_log_lock:
            # Always send, even if buffer is empty (send empty list)
            payload = watchdog_log_buffer.copy()
            send_watchdog_udp_message(payload, is_error=False)
            if payload:
                watchdog_log_buffer.clear()
            #print(f"[WATCHDOG] Sent log update to admin. Entries: {len(payload)}")

def add_to_watchdog_log(text, is_error=False):
    entry = {
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'text': text,
        'is_error': is_error
    }
    with watchdog_log_lock:
        watchdog_log_buffer.append(entry)
    # If error, send immediately
    if is_error:
        send_watchdog_udp_message([entry], is_error=True)

def main():
    global kiosk_process, last_output_time, launch_successful
    global reader_thread, restart_count, shutdown_requested, spinner_idx
    global remote_restart_requested, watchdog_cmd_listener_thread, is_crash_restart
    global watchdog_log_sender_thread

    print_watchdog("Starting Kiosk Watchdog...")
    if DEBUG_MODE:
        print_watchdog("DEBUG MODE ENABLED - Will simulate crash after successful launch")
    print_watchdog(f"Monitoring script: {KIOSK_SCRIPT}")
    print_watchdog(f"Max auto-restarts: {'Unlimited' if MAX_RESTARTS == -1 else MAX_RESTARTS}")

    script_dir = os.path.dirname(os.path.abspath(__file__))
    kiosk_script_path = os.path.join(script_dir, KIOSK_SCRIPT)

    if not os.path.exists(kiosk_script_path):
        print_watchdog(f"ERROR: Kiosk script not found: '{kiosk_script_path}'")
        add_to_watchdog_log(f"ERROR: Kiosk script not found: '{kiosk_script_path}'", is_error=True)
        sys.exit(1)

    signal.signal(signal.SIGINT, signal_handler)

    watchdog_cmd_listener_thread = threading.Thread(target=listen_for_watchdog_commands, daemon=True)
    watchdog_cmd_listener_thread.start()

    # Start watchdog log sender thread
    watchdog_log_sender_thread = threading.Thread(target=watchdog_log_sender_loop, daemon=True)
    watchdog_log_sender_thread.start()

    while not shutdown_requested:
        if remote_restart_requested:
            clear_spinner_line()
            print_watchdog("Remote restart command received. Resetting and attempting launch.")
            add_to_watchdog_log("Remote restart command received. Resetting and attempting launch.", is_error=True)
            if kiosk_process and kiosk_process.poll() is None:
                 terminate_kiosk_process()
            restart_count = 0 
            with lock: remote_restart_requested = False
            launch_successful = False 
            is_crash_restart = False  # Reset crash restart flag for remote restart

        # Main condition for attempting a launch (either unlimited or within limits)
        if MAX_RESTARTS == -1 or restart_count <= MAX_RESTARTS:
            current_attempt_successful = False # Tracks success of this specific attempt
            kiosk_run_failed_after_launch = False 
            
            monitor_active_flag_for_reader.clear()
            last_output_time = time.time() 
            spinner_idx = 0

            clear_spinner_line()
            print_watchdog(f"Attempting Kiosk Launch (Attempt {restart_count + 1}/{MAX_RESTARTS + 1 if MAX_RESTARTS != -1 else 'Unlimited'})")
            
            # Add --restore-state argument if this is a crash restart
            cmd = [PYTHON_EXECUTABLE, "-u", kiosk_script_path]
            if is_crash_restart:
                cmd.append("--restore-state")
                print_watchdog("Adding --restore-state argument for crash recovery")
            
            try:
                # Reset launch_successful for this specific attempt before Popen
                # It's a global flag, so ensure its state is correct for the current context
                with lock: launch_successful = False

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

                launch_start_time = time.time()
                while kiosk_process and kiosk_process.poll() is None: # Kiosk still running
                    if shutdown_requested or remote_restart_requested: break
                    
                    drain_output_queue_and_print()
                    with lock:
                        current_launch_status = launch_successful # Read it once under lock
                    
                    if not current_launch_status: # Still in launch phase
                        if (time.time() - launch_start_time > LAUNCH_TIMEOUT_SECONDS) and \
                           (time.time() - last_output_time > LAUNCH_TIMEOUT_SECONDS / 2) :
                            clear_spinner_line()
                            print_watchdog(f"TIMEOUT: Kiosk launch exceeded {LAUNCH_TIMEOUT_SECONDS}s or no output.")
                            add_to_watchdog_log(f"TIMEOUT: Kiosk launch exceeded {LAUNCH_TIMEOUT_SECONDS}s or no output.", is_error=True)
                            if kiosk_process and kiosk_process.poll() is None: terminate_kiosk_process()
                            kiosk_run_failed_after_launch = True 
                            break 
                    else: # Launch was successful, now in passive heartbeat monitoring
                        if not hasattr(main, 'announced_heartbeat_monitoring'): # Announce only once per successful launch
                            clear_spinner_line()
                            print_watchdog("Kiosk launch successful. Monitoring with heartbeat...")
                            main.announced_heartbeat_monitoring = True
                            
                            # If in debug mode, simulate a crash after successful launch
                            if DEBUG_MODE and not is_crash_restart:
                                print_watchdog("DEBUG MODE: Simulating crash after successful launch...")
                                time.sleep(DEBUG_CRASH_TIME)  # Give it a moment to stabilize
                                if kiosk_process and kiosk_process.poll() is None:
                                    terminate_kiosk_process()
                                is_crash_restart = True
                                break
                        
                        time_since_last_heartbeat = 0
                        with lock: time_since_last_heartbeat = time.time() - last_heartbeat_time
                    
                        if time_since_last_heartbeat > HEARTBEAT_TIMEOUT_SECONDS:
                            clear_spinner_line()
                            print_watchdog(f"HEARTBEAT TIMEOUT: Kiosk unresponsive for over {HEARTBEAT_TIMEOUT_SECONDS}s.")
                            add_to_watchdog_log(f"HEARTBEAT TIMEOUT: Kiosk unresponsive for over {HEARTBEAT_TIMEOUT_SECONDS}s.", is_error=True)
                            if kiosk_process and kiosk_process.poll() is None: terminate_kiosk_process()
                            kiosk_run_failed_after_launch = True 
                            is_crash_restart = True  # Set crash restart flag for heartbeat timeout
                            break
                        update_spinner() # Show passive monitoring spinner

                    time.sleep(POLL_INTERVAL_SECONDS if not current_launch_status else PASSIVE_POLL_INTERVAL_SECONDS)
                
                if hasattr(main, 'announced_heartbeat_monitoring'): # Clean up attribute
                    del main.announced_heartbeat_monitoring

                drain_output_queue_and_print() 

                if shutdown_requested or remote_restart_requested: continue 

                monitor_active_flag_for_reader.set() 
                if reader_thread and reader_thread.is_alive():
                    reader_thread.join(timeout=1.0) 
                drain_output_queue_and_print() 

                # Assess outcome of the attempt
                with lock: current_launch_status_final = launch_successful 

                if kiosk_process and kiosk_process.poll() is not None: # Kiosk exited on its own
                    if current_launch_status_final and not kiosk_run_failed_after_launch:
                        print_watchdog(f"Kiosk process exited cleanly (Return Code: {kiosk_process.returncode}). Watchdog will now exit.")
                        add_to_watchdog_log(f"Kiosk process exited cleanly (Return Code: {kiosk_process.returncode}). Watchdog will now exit.", is_error=True)
                        shutdown_requested = True # Clean exit, watchdog can stop
                        current_attempt_successful = True
                    else: # Exited before success or after a failure (e.g. heartbeat)
                        print_watchdog(f"Kiosk process exited prematurely or after failure (Code: {kiosk_process.returncode}).")
                        add_to_watchdog_log(f"Kiosk process exited prematurely or after failure (Code: {kiosk_process.returncode}).", is_error=True)
                elif kiosk_run_failed_after_launch: # Timeout or heartbeat failure
                     print_watchdog("Kiosk run failed (timeout or heartbeat).")
                     add_to_watchdog_log("Kiosk run failed (timeout or heartbeat).", is_error=True)
                elif not current_launch_status_final: # Did not reach success marker, process might still be running if shutdown/remote_restart broke loop
                    if not (shutdown_requested or remote_restart_requested):
                        print_watchdog("Kiosk launch was not successful (no success marker, process may have died).")
                        add_to_watchdog_log("Kiosk launch was not successful (no success marker, process may have died).", is_error=True)
                else: # Should mean it was successful and loop was broken by shutdown/remote
                    current_attempt_successful = True


                if not current_attempt_successful and not shutdown_requested:
                    restart_count += 1
                
                if kiosk_process and kiosk_process.poll() is None:
                     print_watchdog("Ensuring kiosk process is terminated before next step (post-attempt).")
                     terminate_kiosk_process()
                kiosk_process = None 

                if not current_attempt_successful and not shutdown_requested and (MAX_RESTARTS == -1 or restart_count <= MAX_RESTARTS):
                    print_watchdog(f"Pausing before retry...")
                    add_to_watchdog_log("Pausing before retry...", is_error=True)
                    time.sleep(2) 

            except FileNotFoundError:
                print_watchdog(f"ERROR: Python executable not found: '{PYTHON_EXECUTABLE}'")
                add_to_watchdog_log(f"ERROR: Python executable not found: '{PYTHON_EXECUTABLE}'", is_error=True)
                shutdown_requested = True 
            except Exception as e: 
                clear_spinner_line()
                print_watchdog(f"CRITICAL WATCHDOG ERROR during Kiosk Management: {e}")
                add_to_watchdog_log(f"CRITICAL WATCHDOG ERROR during Kiosk Management: {e}", is_error=True)
                if not shutdown_requested:
                    restart_count += 1
                    if MAX_RESTARTS == -1 or restart_count <= MAX_RESTARTS:
                        print_watchdog("Pausing before retry due to critical error...")
                        add_to_watchdog_log("Pausing before retry due to critical error...", is_error=True)
                        time.sleep(5) 
            
            if kiosk_process and kiosk_process.poll() is None: # Final safety net for this attempt cycle
                terminate_kiosk_process()

        else: # MAX_RESTARTS (finite) exceeded, enter IDLE mode
            clear_spinner_line()
            print_watchdog_idle(f"Max auto-restarts ({MAX_RESTARTS}) reached. Idling.")
            
            idle_start_time = time.time()
            while not shutdown_requested and not remote_restart_requested:
                update_spinner_idle()
                if time.time() - idle_start_time > 300: 
                    clear_spinner_line()
                    print_watchdog_idle(f"Still idle. Max auto-restarts ({MAX_RESTARTS}) reached. Awaiting commands or Ctrl+C.")
                    idle_start_time = time.time() 
                time.sleep(PASSIVE_POLL_INTERVAL_SECONDS)
            
            if shutdown_requested: break 
            # If loop exited due to remote_restart_requested, main 'while not shutdown_requested' loop will pick it up.

    # === Shutdown Sequence ===
    clear_spinner_line()
    if not remote_restart_requested : # Avoid "Watchdog shutdown sequence complete" if it's about to restart by outer loop
         print_watchdog("Watchdog shutdown sequence initiated...")
         add_to_watchdog_log("Watchdog shutdown sequence initiated...", is_error=True)

    watchdog_cmd_listener_stop_event.set()
    if watchdog_cmd_listener_thread and watchdog_cmd_listener_thread.is_alive():
        print_watchdog("Waiting for command listener to stop...")
        watchdog_cmd_listener_thread.join(timeout=2.0)
        if watchdog_cmd_listener_thread.is_alive():
            print_watchdog("Warning: Command listener did not stop cleanly.")

    monitor_active_flag_for_reader.set() 
    if reader_thread and reader_thread.is_alive():
        reader_thread.join(timeout=1.0)
    
    drain_output_queue_and_print() 
    
    if kiosk_process and kiosk_process.poll() is None:
        terminate_kiosk_process() 

    final_launch_status = False
    with lock: final_launch_status = launch_successful

    if remote_restart_requested: 
        print_watchdog("Watchdog is terminating to allow external restart/relaunch if applicable.")
    elif shutdown_requested :
        print_watchdog("Watchdog shutdown complete.")
    elif MAX_RESTARTS != -1 and restart_count > MAX_RESTARTS:
         print_watchdog(f"Kiosk failed after {restart_count} attempts. Watchdog gave up.")
    else: # Should ideally not be reached if other conditions are met
        print_watchdog("Watchdog processing finished.")

    watchdog_log_sender_stop_event.set()
    if watchdog_log_sender_thread and watchdog_log_sender_thread.is_alive():
        watchdog_log_sender_thread.join(timeout=2.0)

    sys.exit(0 if final_launch_status and not (shutdown_requested or remote_restart_requested) else 1)

if __name__ == "__main__":
    main()