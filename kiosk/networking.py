# networking.py
print("[networking] Beginning imports ...", flush=True)
print("[networking] Importing socket...", flush=True)
import socket
print("[networking] Imported socket.", flush=True)
print("[networking] Importing json...", flush=True)
import json
print("[networking] Imported json.", flush=True)
print("[networking] Importing time...", flush=True)
import time
print("[networking] Imported time.", flush=True)
print("[networking] Importing threading...", flush=True)
import threading
print("[networking] Imported threading.", flush=True)
print("[networking] Importing Thread from threading...", flush=True)
from threading import Thread
print("[networking] Imported Thread from threading.", flush=True)
print("[networking] Importing traceback...", flush=True)
import traceback
print("[networking] Imported traceback.", flush=True)

print("[networking] Ending imports ...", flush=True)

class KioskNetwork:
    def __init__(self, computer_name, message_handler):
        print("[networking] Initializing KioskNetwork...", flush=True)
        self.computer_name = computer_name
        self.message_handler = message_handler
        self.running = True
        self.socket = None
        # Use a lock for socket operations during recovery/setup
        self._socket_lock = threading.Lock()
        self.setup_socket()
        self.last_message = {}  # Initialize the last_message cache here
        print("[networking] KioskNetwork initialization complete.", flush=True)

    def setup_socket(self):
        print("[networking.py]=== Setting up network socket ===", flush=True)
        # Ensure exclusive access when modifying the socket
        with self._socket_lock:
            # Close existing socket if it exists
            if self.socket:
                try:
                    print("[networking.py] Closing existing socket before setup...", flush=True)
                    self.socket.close()
                    print("[networking.py] Closed existing socket before setup.", flush=True)
                except Exception as close_err:
                    print(f"[networking.py] Error closing existing socket: {close_err}", flush=True)
                finally:
                    self.socket = None # Ensure it's None if closing fails

            try:
                print("[networking.py] Creating new socket...", flush=True)
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                print("[networking.py] Binding socket to port 12346...", flush=True)
                self.socket.bind(('', 12346))
                print("[networking.py] Setting socket to broadcast mode...", flush=True)
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                # Set larger buffer size (e.g., 1MB, adjust as needed, 16MB might be excessive)
                # UDP datagrams are still limited (~64KB theoretical max, less in practice)
                # Larger OS buffer helps handle bursts but doesn't increase UDP packet size limit.
                print("[networking.py] Setting socket buffer size...", flush=True)
                buffer_size_req = 1 * 1024 * 1024
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size_req)

                # Get actual buffer size
                buf_size_actual = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                print(f"[networking.py] Requested RCVBUF: {buffer_size_req / 1024:.0f}KB, Actual RCVBUF: {buf_size_actual / 1024:.0f}KB", flush=True)

                # IMPORTANT: Set the default timeout for the socket *after* creation
                print("[networking.py] Setting socket timeout to 1.0 second...", flush=True)
                self.socket.settimeout(1.0) # Default timeout for operations
                print("[networking.py] Socket setup complete.", flush=True)

            except Exception as e:
                print(f"[networking.py] Socket setup error: {e}", flush=True)
                self.socket = None # Ensure socket is None on error
                # Re-raise if needed, or handle appropriately
                # raise # Uncomment if startup should fail hard on socket error

    def start_threads(self):
        # Ensure socket is valid before starting threads
        if not self.socket:
            print("[networking.py] Cannot start threads, socket setup failed.", flush=True)
            return
        print("[networking.py] Starting announce thread...", flush=True)
        self.announce_thread = Thread(target=self.announce_presence, daemon=True, name="AnnounceThread")
        print("[networking.py] Starting listen thread...", flush=True)
        self.listen_thread = Thread(target=self.listen_for_messages, daemon=True, name="ListenThread")
        self.announce_thread.start()
        self.listen_thread.start()
        print("[networking.py] Network threads started.", flush=True)

    def send_message(self, message):
        # Acquire lock to ensure socket isn't being modified during send
        with self._socket_lock:
            # Check if socket is valid before attempting to send
            if not self.socket:
                # print("[networking.py] send_message: Socket is not valid, skipping send.") # Reduce log noise
                return

            try:
                #print(f"[networking.py] Encoding message of type: {message.get('type', 'unknown')}...", flush=True)
                encoded = json.dumps(message).encode()
                msg_size = len(encoded)
                max_udp_payload = 65507 # Theoretical max UDP payload size

                if msg_size > max_udp_payload:
                    print(f"[networking.py] WARNING: Message size ({msg_size} bytes) exceeds theoretical UDP limit! May be truncated.", flush=True)
                elif msg_size > 60000: # Practical warning threshold
                     print(f"[networking.py] WARNING: Message size ({msg_size} bytes) is large for UDP.", flush=True)


                # Use the socket's default timeout set during setup_socket
                # Or set temporary timeout if needed, but ensure it's reset or consistent
                # self.socket.settimeout(2.0) # Example: temporary send timeout

                #print(f"[networking.py] Sending {msg_size} bytes to broadcast address...", flush=True)
                self.socket.sendto(encoded, ('255.255.255.255', 12345))
                #print(f"[networking.py] Message sent successfully.", flush=True)

                # Reset timeout if you used a temporary one
                # self.socket.settimeout(1.0) # Reset to default listening timeout

            except socket.timeout:
                print("[networking.py] send_message: sendto timed out!", flush=True)
            except socket.error as e:
                # Avoid printing excessively if socket is closed normally
                if self.running:
                    print(f"[networking.py] send_message: Socket error: {e}", flush=True)
            except Exception as e:
                print(f"[networking.py] send_message: Error encoding/sending message: {e}", flush=True)
                traceback.print_exc()

    def announce_presence(self):
        while self.running:
            try:
                stats = self.message_handler.get_stats()
                message = {
                    'type': 'kiosk_announce',
                    **stats
                }
                self.send_message(message)
                time.sleep(1) # Consider slightly longer interval if network load is high e.g., 2-5 seconds
            except Exception as e:
                # Catch broad exceptions to prevent thread death
                print(f"[networking.py] Error in announce_presence loop: {e}", flush=True)
                traceback.print_exc()
                if not self.running:
                    break # Exit loop if shutdown requested
                time.sleep(5) # Wait before retrying if an error occurred

    def listen_for_messages(self):
        print("[networking.py]=== Starting message listener ===", flush=True)
        buffer_recv_size = 1 * 1024 * 1024 # Match buffer size used in setup (or slightly larger)

        while self.running:
            # Ensure socket is valid at the start of each loop iteration
            if not self.socket:
                 print("[networking.py] listen_for_messages: Socket is not valid, attempting recovery...", flush=True)
                 try:
                      self.setup_socket() # Try to re-establish the socket
                      if not self.socket:
                           print("[networking.py] listen_for_messages: Recovery failed, waiting...", flush=True)
                           time.sleep(5) # Wait before retrying recovery
                           continue # Skip to next loop iteration
                      else:
                           print("[networking.py] listen_for_messages: Socket recovered.", flush=True)
                 except Exception as recovery_err:
                      print(f"[networking.py] listen_for_messages: Error during socket recovery: {recovery_err}", flush=True)
                      time.sleep(5)
                      continue
                

            try:
                # Timeout is now set by default on the socket during setup_socket
                # Or could be set here: self.socket.settimeout(1.0)
                #print("[networking.py] Waiting for incoming data...", flush=True)
                data, addr = self.socket.recvfrom(buffer_recv_size)
                #print(f"[networking.py] Received {len(data)} bytes from {addr}...", flush=True)

                try:
                    #print("[networking.py] Decoding received data...", flush=True)
                    msg = json.loads(data.decode())

                    # --- Removed Hint Message Debug Noise ---
                    # if msg.get('type') == 'hint':
                    #     # ... (keep if needed for debugging, but noisy)

                    print(f"[networking.py] Handling message of type: {msg.get('type', 'unknown')}", flush=True)
                    self.message_handler.handle_message(msg)

                except json.JSONDecodeError as e:
                    print(f"[networking.py] Failed to decode message from {addr}: {e}", flush=True)
                    # Optional: Log the raw data snippet for debugging
                    # print(f"Raw data snippet: {data[:100]}...")
                except Exception as e:
                    print(f"[networking.py] Error processing message from {addr}: {e}", flush=True)
                    traceback.print_exc()

            except socket.timeout:
                # This is expected when no data arrives within the timeout period
                pass # Just continue the loop
            except BlockingIOError:
                # Treat this the same as timeout if socket somehow becomes non-blocking
                # print("[networking.py] listen_for_messages: BlockingIOError occurred (treated as timeout).") # Debug log
                pass # Just continue the loop
            except socket.error as e:
                if self.running:
                    print(f"[networking.py] Socket error in listen_for_messages: {e}", flush=True)
                    traceback.print_exc()
                    # Socket error occurred, attempt recovery
                    print("[networking.py] Attempting socket recovery...", flush=True)
                    try:
                        # setup_socket handles closing and recreating
                        self.setup_socket()
                        if self.socket:
                             print("[networking.py] Successfully recovered socket after error.", flush=True)
                        else:
                             print("[networking.py] Socket recovery failed, will retry.", flush=True)
                             time.sleep(5) # Wait before next loop iteration tries again
                    except Exception as setup_error:
                        print(f"[networking.py] Failed to recover socket: {setup_error}", flush=True)
                        # Ensure socket is None if recovery fails hard
                        with self._socket_lock:
                           self.socket = None
                        if self.running:
                            time.sleep(5) # Wait before next loop iteration
                else:
                    print("[networking.py] Socket error during shutdown.", flush=True)
                    break # Exit loop if not running
            except Exception as e:
                # Catch any other unexpected errors
                if self.running:
                    print(f"[networking.py] Unexpected error in listen_for_messages: {e}", flush=True)
                    traceback.print_exc()
                    time.sleep(1) # Brief pause before continuing
                else:
                    print("[networking.py] Unexpected error during shutdown.", flush=True)
                    break # Exit loop if not running

        print("[networking.py] Message listener loop finished.", flush=True)


    def shutdown(self):
        print("[networking.py] Shutting down network...", flush=True)
        self.running = False # Signal threads to stop

        # Send disconnect message (best effort)
        try:
            message = {
                'type': 'kiosk_disconnect',
                'computer_name': self.computer_name
            }
            # Use a short timeout for the final message
            with self._socket_lock:
                if self.socket:
                    print("[networking.py] Sending disconnect message...", flush=True)
                    self.socket.settimeout(0.5)
                    self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12345))
                    print("[networking.py] Disconnect message sent.", flush=True)
        except Exception as e:
            print(f"[networking.py] Error sending disconnect message: {e}", flush=True)
        finally:
            # Close the socket safely
            with self._socket_lock:
                if self.socket:
                    try:
                        print("[networking.py] Closing socket...", flush=True)
                        self.socket.close()
                        print("[networking.py] Socket closed.", flush=True)
                    except Exception as e:
                        print(f"[networking.py] Error closing socket during shutdown: {e}", flush=True)
                    finally:
                        self.socket = None # Ensure it's None

        # Wait briefly for threads to potentially exit (optional)
        # if hasattr(self, 'listen_thread') and self.listen_thread.is_alive():
        #     self.listen_thread.join(timeout=1.0)
        # if hasattr(self, 'announce_thread') and self.announce_thread.is_alive():
        #     self.announce_thread.join(timeout=1.0)

        print("[networking.py] Network shutdown complete.", flush=True)

# --- Example Usage Placeholder ---
# class MockMessageHandler:
#     def handle_message(self, msg):
#         print(f"Mock Handler received: {msg.get('type', 'Unknown type')}")
#     def get_stats(self):
#         return {'status': 'OK', 'room': 'TestRoom1'}
#
# if __name__ == "__main__":
#     print("Starting network test...")
#     handler = MockMessageHandler()
#     network = KioskNetwork("TestKiosk", handler)
#     if network.socket: # Check if socket setup was successful
#         network.start_threads()
#         try:
#             while True:
#                 time.sleep(10)
#                 print("Main thread sleeping...")
#                 # Example sending a custom message
#                 # network.send_message({'type': 'custom_event', 'data': 'hello world'})
#         except KeyboardInterrupt:
#             print("KeyboardInterrupt received.")
#         finally:
#             network.shutdown()
#     else:
#         print("Network setup failed, exiting.")