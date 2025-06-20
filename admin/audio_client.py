# audio_client.py manages microphone activity, not admin application sounds
import pyaudio
import socket
import threading
import struct
import numpy as np
import math
import time
import traceback
import sys
import subprocess # For calling external script

class AudioClient:
    def __init__(self):
        """Initializes the AudioClient."""
        self.running = False
        self.current_socket = None
        self.audio = None
        self.input_stream = None
        self.output_stream = None
        self.speaking = False
        self.current_volume = 0.0
        self.selected_input_device_index = None
        self.current_output_mode = None # Can be 'default' or 'communication'
        self._pyaudio_initialized = False
        self._lock = threading.Lock() # Lock for protecting stream/speaking state
        self._cached_output_device_index = None # NEW: Cache for Windows communication device index

        # Audio parameters
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 44100

        try:
            print("[audio client] Attempting to initialize PyAudio...")
            self.audio = pyaudio.PyAudio()
            self._pyaudio_initialized = True
            print("[audio client] PyAudio initialized successfully.")
        except Exception as e:
            print(f"[audio client] FATAL ERROR: Failed to initialize PyAudio: {e}")
            traceback.print_exc()
            self.audio = None
            self._pyaudio_initialized = False
            print("[audio client] Audio functionality is disabled.")

    def _run_windows_comm_device_script(self):
        """
        Executes the external script to get the Windows Default Communication Device name.
        Returns the device name string on success, None on failure.
        """
        script_path = "get_windows_comm_device.py" # Assumes script is in the same directory

        print(f"[audio client] Running external script to get comm device: '{script_path}'...")
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                check=False
            )

            if result.returncode == 0:
                comm_device_name_str = result.stdout.strip()
                if not comm_device_name_str:
                    print(f"[audio client] Script '{script_path}' returned no device name (stdout empty).")
                    if result.stderr:
                         print(f"[audio client] Script stderr: {result.stderr.strip()}")
                    return None
                print(f"[audio client] Script returned Windows Default Communication Device: '{comm_device_name_str}'")
                return comm_device_name_str
            else:
                print(f"[audio client] Script '{script_path}' failed with exit code {result.returncode}.")
                if result.stdout: print(f"[audio client] Script stdout: {result.stdout.strip()}")
                if result.stderr: print(f"[audio client] Script stderr: {result.stderr.strip()}")
                return None
        except FileNotFoundError:
            print(f"[audio client] ERROR: Script '{script_path}' not found. Cannot determine communication device.")
            return None
        except Exception as e:
            print(f"[audio client] ERROR: Exception running script '{script_path}': {e}")
            traceback.print_exc()
            return None

    def _get_pyaudio_index_from_device_name(self, target_name):
        """
        Finds the PyAudio device index that matches the given target_name (exact or partial).
        Returns the PyAudio device index (int) or None.
        """
        if not self._pyaudio_initialized or self.audio is None:
            print("[audio client] PyAudio not initialized. Cannot match device name.")
            return None

        pyaudio_index = None
        matched_device_name = None
        num_devices = self.audio.get_device_count()

        # First pass: exact match
        for i in range(num_devices):
            dev_info = self.audio.get_device_info_by_index(i)
            if dev_info.get('maxOutputChannels', 0) > 0:
                pyaudio_dev_name = dev_info['name']
                if isinstance(pyaudio_dev_name, bytes):
                    try: pyaudio_dev_name = pyaudio_dev_name.decode('utf-8', errors='ignore')
                    except UnicodeDecodeError: continue

                if pyaudio_dev_name == target_name:
                    pyaudio_index = i
                    matched_device_name = pyaudio_dev_name
                    break
        
        if pyaudio_index is not None:
            print(f"[audio client] Found exact PyAudio match: '{matched_device_name}' (Index: {pyaudio_index}) for target name '{target_name}'")
        else: # Second pass: partial match
            print("[audio client] No exact name match. Trying partial match for output device...")
            candidate_partial_match_idx = None
            candidate_partial_match_name = None
            for i in range(num_devices):
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info.get('maxOutputChannels', 0) > 0:
                    pyaudio_dev_name = dev_info['name']
                    if isinstance(pyaudio_dev_name, bytes):
                        try: pyaudio_dev_name = pyaudio_dev_name.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError: continue
                    
                    if target_name and pyaudio_dev_name: # Ensure not empty
                        # Simple substring check (target name in PyAudio name or vice-versa)
                        if target_name.lower() in pyaudio_dev_name.lower() or \
                           pyaudio_dev_name.lower() in target_name.lower():
                            candidate_partial_match_idx = i
                            candidate_partial_match_name = pyaudio_dev_name
                            break
            
            if candidate_partial_match_idx is not None:
                pyaudio_index = candidate_partial_match_idx
                print(f"[audio client] Found partial PyAudio match: '{candidate_partial_match_name}' (Index: {pyaudio_index}) for target name '{target_name}'")
        
        if pyaudio_index is None:
            print(f"[audio client] Could not find a matching PyAudio output device for target name '{target_name}'. Listing available PyAudio output devices:")
            for i in range(num_devices):
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info.get('maxOutputChannels', 0) > 0:
                    name_to_print = dev_info['name']
                    if isinstance(name_to_print, bytes):
                        try: name_to_print = name_to_print.decode('utf-8', errors='replace')
                        except: name_to_print = "<undecodable name>"
                    print(f"  PyAudio Output Device Index {i}: {name_to_print}")
        
        return pyaudio_index


    def _determine_output_device_index_for_windows_comm_device(self):
        """
        Determines the PyAudio output device index for Windows' Default Communication Device.
        Uses a cached value if available, otherwise runs external script and finds PyAudio match.
        Returns: PyAudio device index (int) or None.
        """
        if self._cached_output_device_index is not None:
            print(f"[audio client] Using cached Windows communication device index: {self._cached_output_device_index}")
            return self._cached_output_device_index

        print("[audio client] Cache empty. Attempting to determine Windows Default Communication Device for output.")
        comm_device_name_from_script = self._run_windows_comm_device_script()
        
        if comm_device_name_from_script:
            comm_pyaudio_index = self._get_pyaudio_index_from_device_name(comm_device_name_from_script)
            self._cached_output_device_index = comm_pyaudio_index # Cache the result
            return comm_pyaudio_index
        else:
            print("[audio client] Could not determine Windows Default Communication Device name via script. Falling back to PyAudio default.")
            return None


    def connect(self, host, port=8090):
        """Connects to the audio server and starts the receiving stream."""
        if not self._pyaudio_initialized or self.audio is None:
             print("[audio client] PyAudio was not initialized or instance is missing. Cannot connect.")
             return False

        if self.current_socket:
            print("[audio client] Already connected. Disconnecting existing connection first.")
            self.disconnect()
            time.sleep(0.2) # Give a moment for resources to clear after disconnect

        print(f"[audio client] Attempting to connect to {host}:{port}")
        try:
            self.current_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.current_socket.settimeout(3)  # 3 second timeout for connection
            self.current_socket.connect((host, port))
            self.current_socket.settimeout(None) # Reset to blocking for regular operations
            self.current_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.running = True # Set running flag only after successful socket connection
            print("[audio client] Socket connected successfully.")

            # Initialize output stream for receiving audio
            if self.audio is None: # Double check audio instance
                print("[audio client] PyAudio instance is None after socket connect. Critical error.")
                self.disconnect()
                return False

            print("[audio client] Opening output stream...")
            # MODIFICATION: Always start with the default device.
            # The logic for switching to the comms device is now in `set_output_device`.
            output_device_idx_to_use = None
            
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK,
                output_device_index=output_device_idx_to_use # PyAudio handles None as default
            )
            self.current_output_mode = 'default' # Set initial mode
            print(f"[audio client] Output stream opened on default device.")

            # Start receiving thread
            print("[audio client] Starting receive thread...")
            threading.Thread(target=self._safe_receive_loop, daemon=True).start()
            print("[audio client] Receive thread started.")
            return True

        except socket.timeout:
            print(f"[audio client] Audio connection timed out to {host}:{port}.")
            self.disconnect() # Ensure cleanup on timeout
            return False
        except Exception as e:
            print(f"[audio client] Audio connection failed: {e}")
            traceback.print_exc()
            self.disconnect() # Ensure cleanup on other errors
            return False

    def set_output_device(self, use_communication_device: bool):
        """
        Switches the audio output device between default and default communication.
        This should be called while the client is connected and receiving.
        """
        if not self.running or not self.audio:
            return

        target_mode = 'communication' if use_communication_device else 'default'
        if self.current_output_mode == target_mode:
            return # No change needed

        print(f"[audio client] Switching output device to '{target_mode}'...")

        # Determine target device index
        target_device_index = None
        if use_communication_device and sys.platform == 'win32':
            target_device_index = self._determine_output_device_index_for_windows_comm_device()

        # Safely stop and close the existing output stream
        old_stream = self.output_stream
        self.output_stream = None # Clear the reference
        if old_stream:
            try:
                if old_stream.is_active(): old_stream.stop_stream()
                old_stream.close()
            except Exception as e:
                print(f"[audio client] Error closing old output stream: {e}")

        # Open the new output stream
        try:
            self.output_stream = self.audio.open(
                format=self.FORMAT, channels=self.CHANNELS, rate=self.RATE,
                output=True, frames_per_buffer=self.CHUNK,
                output_device_index=target_device_index
            )
            self.current_output_mode = target_mode
        except Exception as e:
            print(f"[audio client] FAILED to open new output stream: {e}. Disconnecting.")
            self.disconnect()

    def _safe_receive_loop(self):
        """Wrapper for receive_audio to handle exceptions within the thread."""
        try:
            self.receive_audio()
        except Exception as e:
            print(f"[audio client] Receive thread CRASHED: {e}")
            traceback.print_exc()
            # Trigger disconnect if the thread crashes while running
            if self.running:
                 self.disconnect()
        finally:
             print("[audio client] Receive thread finished.")

    def receive_audio(self):
        """Listens for and plays incoming audio data."""
        print("[audio client] Starting audio reception loop.")
        while self.running:
            try:
                # 1. Receive chunk size (blocking with timeout via _recv_exactly)
                size_data = self._recv_exactly(struct.calcsize("Q"))
                if not size_data:
                    if self.running: # Avoid log noise if disconnect was intentional
                        print("[audio client] Receive loop: Failed to get size data (connection closed?).")
                    break # Exit loop

                chunk_size = struct.unpack("Q", size_data)[0]
                # Sanity check size for float32 data (4 bytes per sample)
                # Corrected: Use pyaudio.get_sample_size(self.FORMAT) instead of struct.calcsize(self.FORMAT)
                if chunk_size <= 0 or chunk_size > self.CHUNK * pyaudio.get_sample_size(self.FORMAT) * 20:
                     print(f"[audio client] Receive loop: Invalid chunk size received ({chunk_size}). Closing.")
                     break

                # 2. Receive audio data (blocking with timeout via _recv_exactly)
                audio_data = self._recv_exactly(chunk_size)
                if not audio_data:
                    if self.running:
                        print("[audio client] Receive loop: Failed to get audio data (connection closed?).")
                    break # Exit loop

                # 3. Play audio data
                current_output_stream = self.output_stream # Local ref for safety
                if current_output_stream and self.running:
                    try:
                        # Check if stream is active *before* writing
                        if current_output_stream.is_active():
                             current_output_stream.write(bytes(audio_data))
                    except OSError as e:
                         # Common error if stream is closed unexpectedly
                         print(f"[audio client] Receive loop: OSError writing to output stream: {e}")
                         break # Exit loop on stream write errors
                    except Exception as e:
                         print(f"[audio client] Receive loop: Error playing audio chunk: {e}")

            except socket.error as e:
                if self.running: # Only log if not intentionally stopped
                    print(f"[audio client] Receive loop: Socket error: {e}")
                break # Exit loop on socket errors
            except Exception as e:
                if self.running:
                    print(f"[audio client] Receive loop: Unexpected error: {e}")
                    traceback.print_exc()
                break # Exit loop on other major errors

        print("[audio client] Audio reception loop ended.")

    def start_speaking(self):
        """Starts capturing and sending audio. Protected by lock."""
        print("[audio client] Attempting to start speaking...")
        if not self.running:
            print("[audio client] Cannot start speaking: Not connected.")
            return False

        # Acquire lock to ensure atomic start operation
        with self._lock:
            if self.speaking:
                print("[audio client] Already speaking (lock acquired).")
                return True # Already running, nothing to do

            # --- Pre-checks (within lock) ---
            if not self._pyaudio_initialized or self.audio is None:
                print("[audio client] PyAudio not available. Cannot start speaking.")
                return False

            if self.selected_input_device_index is None:
                print("[audio client] No input device selected. Attempting to find default.")
                self.get_input_devices() # Sets default if possible (also uses lock briefly)
                if self.selected_input_device_index is None:
                    print("[audio client] Error: No input device available or selected.")
                    return False # Still no device after checking

            print(f"[audio client] Starting microphone on device {self.selected_input_device_index} (lock acquired).")

            # --- Attempt to open stream ---
            try:
                # Ensure any previous stream reference is definitely cleared before opening
                if self.input_stream is not None:
                    print("[audio client] Warning: input_stream was not None before opening. Cleaning up.")
                    try:
                        # No need to check is_active here, just try close
                        self.input_stream.close()
                    except Exception as e_clean:
                         print(f"[audio client] Info: Error during pre-cleanup: {e_clean}")
                    finally:
                         self.input_stream = None

                print("[audio client] Opening input stream...")
                self.input_stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK,
                    input_device_index=self.selected_input_device_index
                )
                print("[audio client] Input stream opened successfully.")

                # --- Stream opened successfully ---
                self.speaking = True # Set flag *after* stream is confirmed open
                self.current_volume = 0.0
                print("[audio client] Starting send thread...")
                threading.Thread(target=self._safe_send_loop, daemon=True).start()
                print("[audio client] Send thread started. Microphone active.")
                return True # Success

            except Exception as e:
                # --- Failed to open stream ---
                print(f"[audio client] Failed to open input stream on device {self.selected_input_device_index}: {e}")
                traceback.print_exc()
                # Clean up potentially partially opened stream
                if self.input_stream:
                    try: self.input_stream.close()
                    except: pass
                self.input_stream = None
                self.speaking = False # Ensure flag is false
                print("[audio client] Microphone start failed.")
                # Removed remediation logic for simplicity and stability
                return False # Failure
        # Lock released automatically here

    def _safe_send_loop(self):
        """Wrapper for send_audio to handle exceptions within the thread."""
        try:
            self.send_audio()
        except Exception as e:
            print(f"[audio client] Send thread CRASHED: {e}")
            traceback.print_exc()
            # If the send thread crashes, we should probably stop the speaking state
            if self.speaking:
                 self.stop_speaking() # Attempt graceful stop
        finally:
             print("[audio client] Send thread finished.")


    def stop_speaking(self):
        """Stops capturing and sending audio. Protected by lock."""
        print("[audio client] Attempting to stop microphone...")
        # Acquire lock to ensure atomic stop operation
        with self._lock:
            if not self.speaking:
                print("[audio client] Already stopped (lock acquired).")
                return # Already stopped

            print("[audio client] Stopping microphone (lock acquired).")
            self.speaking = False # Signal send thread to stop *first*
            self.current_volume = 0.0

            stream_to_close = self.input_stream # Get reference
            self.input_stream = None # Clear the shared reference immediately

        # --- Close stream (outside primary lock section, closing can block) ---
        if stream_to_close:
            print("[audio client] Closing input stream...")
            try:
                # Check activity before stopping, might prevent some errors on some platforms
                if stream_to_close.is_active():
                     stream_to_close.stop_stream()
                     print("[audio client] Input stream stopped.")
                stream_to_close.close()
                print("[audio client] Input stream closed.")
            except Exception as e:
                print(f"[audio client] Error closing input stream: {e}")
                # traceback.print_exc() # Can be noisy, error is common if closed abruptly
        else:
             # This case shouldn't happen if self.speaking was true, but log if it does
             print("[audio client] Warning: stop_speaking called but input_stream was already None.")

        print("[audio client] Stop speaking finished.")
        # Lock was released after clearing self.input_stream and self.speaking


    def send_audio(self):
        """Reads audio from the input stream and sends it over the socket."""
        print("[audio client] Starting audio transmission loop.")

        # Check initial state
        with self._lock: # Briefly lock to get consistent initial stream reference
            initial_stream = self.input_stream

        if not initial_stream:
             print("[audio client] Send loop: Started with no input stream. Exiting.")
             return

        while True: # Loop relies on self.speaking flag and stream state
            # --- Check state before blocking read ---
            # Read speaking flag without lock (volatile read is okay here)
            if not self.speaking:
                 print("[audio client] Send loop: speaking flag is false. Exiting.")
                 break
            # Read stream ref without lock (it's set to None atomically in stop_speaking)
            current_stream = self.input_stream
            if current_stream is None:
                 print("[audio client] Send loop: input_stream is None. Exiting.")
                 break

            # --- Blocking Read ---
            try:
                # Use the stream reference captured at the start of the loop iteration
                data = current_stream.read(self.CHUNK, exception_on_overflow=False)
            except IOError as e:
                # This is the *expected* way to exit when stop_speaking closes the stream
                # Check the speaking flag again to differentiate expected vs unexpected IOErrors
                if not self.speaking:
                    print(f"[audio client] Send loop: IOError reading audio (expected on stop): {e}")
                else:
                    # If speaking is still true, this might be an unexpected error
                    print(f"[audio client] Send loop: IOError reading audio unexpectedly: {e}")
                break # Exit loop on IOError
            except AttributeError as e:
                # Handles case where current_stream becomes None *between* check and read (rare)
                 print(f"[audio client] Send loop: AttributeError (stream likely became None): {e}")
                 break
            except Exception as e:
                print(f"[audio client] Send loop: Unexpected error reading audio stream: {e}")
                traceback.print_exc()
                break # Exit loop on other errors

            # --- Process and Send Data ---
            if data:
                # Calculate volume
                self.current_volume = self._calculate_volume(data)

                # Send data - check socket existence too
                current_sock = self.current_socket
                if current_sock and self.running:
                    try:
                        size = len(data)
                        # Pack size and data together for efficiency
                        packet = struct.pack("Q", size) + data
                        current_sock.sendall(packet)
                    except socket.error as e:
                        print(f"[audio client] Send loop: Socket error sending audio packet: {e}")
                        # Assume connection is lost, trigger disconnect
                        if self.running: self.disconnect()
                        break # Exit send loop
                    except Exception as e:
                        print(f"[audio client] Send loop: Unexpected error sending audio packet: {e}")
                        traceback.print_exc()
                        if self.running: self.disconnect() # Assume fatal error
                        break # Exit send loop
                else:
                    # Socket closed or client stopped during send attempt
                    print("[audio client] Send loop: Socket closed or client stopped. Cannot send.")
                    break # Exit send loop
            else:
                # read() returned empty data without error? Should not happen with blocking read.
                print("[audio client] Send loop: Read returned empty data. Exiting.")
                break

        print("[audio client] Audio transmission loop ended.")
        self.current_volume = 0.0 # Reset volume when transmission stops

    def _recv_exactly(self, size):
        """Helper to receive exactly 'size' bytes or return None on failure/timeout."""
        data = bytearray()
        current_sock = self.current_socket # Capture reference
        if not current_sock or not self.running:
             return None

        # Implement overall timeout for receiving the whole message
        start_time = time.time()
        timeout_duration = 5.0 # E.g., 5 seconds to receive the full chunk + size

        while len(data) < size:
            if not self.running: return None # Check running flag each iteration
            if time.time() - start_time > timeout_duration:
                print(f"[audio client] _recv_exactly: Timeout waiting for {size} bytes (got {len(data)}).")
                return None

            try:
                remaining = size - len(data)
                # Use a short timeout for individual recv calls to keep it responsive
                current_sock.settimeout(0.2) # Shorter timeout for responsiveness
                packet = current_sock.recv(min(remaining, 4096))
                current_sock.settimeout(None) # Reset to default blocking behavior (or previous state if needed)

                if not packet:
                    # print(f"[audio client] _recv_exactly: Connection closed by peer gracefully.") # Can be noisy
                    return None # Peer closed connection

                data.extend(packet)

            except socket.timeout:
                 # It's okay to timeout on the short individual recv, just continue the outer loop
                 continue
            except socket.error as e:
                 print(f"[audio client] _recv_exactly: Socket error: {e}")
                 return None # Failure
            except Exception as e:
                 print(f"[audio client] _recv_exactly: Unexpected error: {e}")
                 traceback.print_exc()
                 return None # Failure

        return data # Return the complete data

    def disconnect(self):
        """Disconnects, closes streams, and cleans up resources."""
        print("[audio client] Disconnecting audio client...")
        self.running = False # Signal all loops to stop *first*
        self.current_output_mode = None # Reset the mode
        self._cached_output_device_index = None # NEW: Clear cache on disconnect

        # Close socket - triggers threads blocked on socket ops to exit
        socket_to_close = self.current_socket
        self.current_socket = None # Clear reference
        if socket_to_close:
            print("[audio client] Shutting down and closing socket...")
            try:
                socket_to_close.shutdown(socket.SHUT_RDWR)
            except: pass # Ignore errors, socket might already be closed
            try:
                socket_to_close.close()
                print("[audio client] Socket closed.")
            except Exception as e:
                 print(f"[audio client] Error closing socket: {e}")

        # Use lock to handle input stream shutdown safely with speaking flag
        with self._lock:
            self.speaking = False # Ensure speaking is off
            input_stream_to_close = self.input_stream
            self.input_stream = None # Clear reference within lock

        # Close input stream (outside lock)
        if input_stream_to_close:
            print("[audio client] Closing input stream during disconnect...")
            try:
                if input_stream_to_close.is_active(): input_stream_to_close.stop_stream()
                input_stream_to_close.close()
                print("[audio client] Input stream closed.")
            except Exception as e:
                print(f"[audio client] Error closing input stream during disconnect: {e}")

        # Close output stream (doesn't need the input stream lock)
        output_stream_to_close = self.output_stream
        self.output_stream = None # Clear reference
        if output_stream_to_close:
            print("[audio client] Closing output stream during disconnect...")
            try:
                if output_stream_to_close.is_active(): output_stream_to_close.stop_stream()
                output_stream_to_close.close()
                print("[audio client] Output stream closed.")
            except Exception as e:
                print(f"[audio client] Error closing output stream during disconnect: {e}")

        print("[audio client] Audio client disconnected.")

    def __del__(self):
        """Destructor, attempts cleanup."""
        print(f"[audio client] AudioClient __del__ called (ID: {id(self)}).")
        # Ensure disconnect is called if not already stopped
        if self.running or self.current_socket or self.input_stream or self.output_stream:
             print("[audio client] __del__: Performing cleanup via disconnect().")
             self.disconnect()

        # Terminate PyAudio only if initialized and not already None
        audio_instance = self.audio # Local ref
        pyaudio_was_initialized = self._pyaudio_initialized # Capture state before clearing
        if audio_instance and pyaudio_was_initialized:
            print("[audio client] __del__: Terminating PyAudio instance...")
            try:
                audio_instance.terminate()
                print("[audio client] PyAudio terminated.")
            except Exception as e:
                print(f"[audio client] Error terminating PyAudio in __del__: {e}")
            finally:
                 self.audio = None
                 self._pyaudio_initialized = False

    def get_input_devices(self):
        """Returns a list of available input devices. Briefly uses lock for default setting."""
        if not self._pyaudio_initialized or self.audio is None:
            # print("[audio client] PyAudio not initialized. Cannot get input devices.") # Noisy
            return []

        devices = []
        try:
            num_devices = self.audio.get_device_count()
            if num_devices <= 0:
                 print("[audio client] No audio devices found by PyAudio.")
                 return []

            for i in range(num_devices):
                try:
                    dev_info = self.audio.get_device_info_by_index(i)
                    # Handle potential byte strings for device names
                    dev_name = dev_info['name']
                    if isinstance(dev_name, bytes):
                        try: dev_name = dev_name.decode('utf-8', errors='ignore')
                        except UnicodeDecodeError: dev_name = f"Undecodable Device Name (Index {i})"
                    
                    # Check if it's an input device
                    if dev_info.get('maxInputChannels', 0) > 0:
                        devices.append({'index': i, 'name': dev_name})
                except Exception as e_dev:
                     print(f"[audio client] Error getting info for device index {i}: {e_dev}")
                     # Continue to next device

            # Set default if none selected and devices were found (use lock for this part)
            with self._lock:
                 if self.selected_input_device_index is None and devices:
                     print("[audio client] Setting default input device...")
                     try:
                         default_info = self.audio.get_default_input_device_info()
                         default_index = default_info.get('index')
                         default_name = default_info.get('name')
                         if isinstance(default_name, bytes):
                            default_name = default_name.decode('utf-8', errors='ignore')

                         # Verify default index is in our list of usable devices
                         if any(d['index'] == default_index for d in devices):
                             self.selected_input_device_index = default_index
                             print(f"[audio client] Default input device set to: index {default_index} Name: {default_name}")
                         elif devices: # Default not usable, pick first from our list
                             self.selected_input_device_index = devices[0]['index']
                             print(f"[audio client] Default device unusable, set to first available: index {self.selected_input_device_index} Name: {devices[0]['name']}")
                     except Exception as e_default:
                         print(f"[audio client] Error getting default device ({e_default}), selecting first.")
                         if devices: # Fallback if default query fails
                             self.selected_input_device_index = devices[0]['index']
                             print(f"[audio client] Set to first available: index {self.selected_input_device_index} Name: {devices[0]['name']}")
                     if self.selected_input_device_index is None:
                           print("[audio client] No suitable input device found.")


        except Exception as e:
            print(f"[audio client] Error getting input devices list: {e}")
            traceback.print_exc()
        return devices

    def set_input_device(self, index):
        """Sets the input device. Restarts the stream if currently speaking."""
        print(f"[audio client] Request to set input device to index: {index}")
        if not self._pyaudio_initialized or self.audio is None:
            print("[audio client] PyAudio not available. Cannot set input device.")
            return

        # Consider validating index against get_input_devices() here if needed

        # Use lock to check/change index and manage speaking state transition
        with self._lock:
            if self.selected_input_device_index == index:
                print(f"[audio client] Device index {index} already selected.")
                return # No change needed

            print(f"[audio client] Changing selected input device index to {index} (lock acquired).")
            was_speaking = self.speaking
            old_index = self.selected_input_device_index
            self.selected_input_device_index = index # Change index

        # Perform stop/start outside the main index change lock section
        # Stop/Start methods acquire the lock themselves.
        if was_speaking:
            print(f"[audio client] Restarting microphone for new device {index} (was {old_index})...")
            self.stop_speaking() # This will acquire lock, stop stream, release lock
            # Give a moment for OS/driver to release the old device handle
            time.sleep(0.1) # Adjust delay if needed
            self.start_speaking() # This will acquire lock, start stream, release lock
        else:
             print(f"[audio client] Input device set to {index}. Not restarting as microphone was off.")

    def get_current_volume(self):
        """Returns the current normalized microphone volume (0.0 to 1.0)."""
        # Reading a float is generally atomic, no lock needed
        return self.current_volume

    def _calculate_volume(self, data):
        """Calculates normalized volume from audio data chunk."""
        try:
            audio_data = np.frombuffer(data, dtype=np.float32)
            # RMS calculation using numpy
            rms = np.sqrt(np.mean(np.square(audio_data)))

            # Parameters for logarithmic normalization (adjust sensitivity here)
            scaling_factor = 10  # Amplification before log conversion
            min_db = -35         # The dB level corresponding to 0.0 output
            max_db = 0           # The dB level corresponding to 1.0 output (0 dBFS)
            epsilon = 1e-9       # To avoid log10(0)

            if rms > epsilon:
                # Apply scaling factor
                scaled_rms = rms * scaling_factor
                # Convert RMS to dB relative to full scale
                db_volume = 20 * math.log10(max(scaled_rms, epsilon)) # Ensure arg > 0
                # Clamp dB value to the defined range [min_db, max_db]
                clamped_db = max(min_db, min(db_volume, max_db))
                # Normalize the clamped dB value to the range [0.0, 1.0]
                normalized_volume = (clamped_db - min_db) / (max_db - min_db)
            else:
                normalized_volume = 0.0

            # Final safety clamp (shouldn't be necessary if logic above is correct)
            return max(0.0, min(1.0, normalized_volume))

        except Exception:
            # print(f"[audio client] Error calculating volume: {e}") # Avoid log spam
            return 0.0