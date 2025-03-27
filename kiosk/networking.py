# networking.py
print("[networking] Beginning imports ...")
import socket
import json
import time
import threading
from threading import Thread
import traceback

print("[networking] Ending imports ...")

class KioskNetwork:
    def __init__(self, computer_name, message_handler):
        self.computer_name = computer_name
        self.message_handler = message_handler
        self.running = True
        self.socket = None
        # Use a lock for socket operations during recovery/setup
        self._socket_lock = threading.Lock()
        self.setup_socket()
        self.last_message = {}  # Initialize the last_message cache here

    def setup_socket(self):
        print("[networking.py]=== Setting up network socket ===")
        # Ensure exclusive access when modifying the socket
        with self._socket_lock:
            # Close existing socket if it exists
            if self.socket:
                try:
                    self.socket.close()
                    print("[networking.py] Closed existing socket before setup.")
                except Exception as close_err:
                    print(f"[networking.py] Error closing existing socket: {close_err}")
                finally:
                    self.socket = None # Ensure it's None if closing fails

            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.socket.bind(('', 12346))
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

                # Set larger buffer size (e.g., 1MB, adjust as needed, 16MB might be excessive)
                # UDP datagrams are still limited (~64KB theoretical max, less in practice)
                # Larger OS buffer helps handle bursts but doesn't increase UDP packet size limit.
                buffer_size_req = 1 * 1024 * 1024
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, buffer_size_req)

                # Get actual buffer size
                buf_size_actual = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
                print(f"[networking.py] Requested RCVBUF: {buffer_size_req / 1024:.0f}KB, Actual RCVBUF: {buf_size_actual / 1024:.0f}KB")

                # IMPORTANT: Set the default timeout for the socket *after* creation
                self.socket.settimeout(1.0) # Default timeout for operations

            except Exception as e:
                print(f"[networking.py] Socket setup error: {e}")
                self.socket = None # Ensure socket is None on error
                # Re-raise if needed, or handle appropriately
                # raise # Uncomment if startup should fail hard on socket error

    def start_threads(self):
        # Ensure socket is valid before starting threads
        if not self.socket:
            print("[networking.py] Cannot start threads, socket setup failed.")
            return
        self.announce_thread = Thread(target=self.announce_presence, daemon=True, name="AnnounceThread")
        self.listen_thread = Thread(target=self.listen_for_messages, daemon=True, name="ListenThread")
        self.announce_thread.start()
        self.listen_thread.start()

    def send_message(self, message):
        # Acquire lock to ensure socket isn't being modified during send
        with self._socket_lock:
            # Check if socket is valid before attempting to send
            if not self.socket:
                # print("[networking.py] send_message: Socket is not valid, skipping send.") # Reduce log noise
                return

            try:
                encoded = json.dumps(message).encode()
                msg_size = len(encoded)
                max_udp_payload = 65507 # Theoretical max UDP payload size

                if msg_size > max_udp_payload:
                    print(f"[networking.py] WARNING: Message size ({msg_size} bytes) exceeds theoretical UDP limit! May be truncated.")
                elif msg_size > 60000: # Practical warning threshold
                     print(f"[networking.py] WARNING: Message size ({msg_size} bytes) is large for UDP.")


                # Use the socket's default timeout set during setup_socket
                # Or set temporary timeout if needed, but ensure it's reset or consistent
                # self.socket.settimeout(2.0) # Example: temporary send timeout

                self.socket.sendto(encoded, ('255.255.255.255', 12345))

                # Reset timeout if you used a temporary one
                # self.socket.settimeout(1.0) # Reset to default listening timeout

            except socket.timeout:
                print("[networking.py] send_message: sendto timed out!")
            except socket.error as e:
                # Avoid printing excessively if socket is closed normally
                if self.running:
                    print(f"[networking.py] send_message: Socket error: {e}")
            except Exception as e:
                print(f"[networking.py] send_message: Error encoding/sending message: {e}")
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
                print(f"[networking.py] Error in announce_presence loop: {e}")
                traceback.print_exc()
                if not self.running:
                    break # Exit loop if shutdown requested
                time.sleep(5) # Wait before retrying if an error occurred

    def listen_for_messages(self):
        print("[networking.py]=== Starting message listener ===")
        buffer_recv_size = 1 * 1024 * 1024 # Match buffer size used in setup (or slightly larger)

        while self.running:
            # Ensure socket is valid at the start of each loop iteration
            if not self.socket:
                 print("[networking.py] listen_for_messages: Socket is not valid, attempting recovery...")
                 try:
                      self.setup_socket() # Try to re-establish the socket
                      if not self.socket:
                           print("[networking.py] listen_for_messages: Recovery failed, waiting...")
                           time.sleep(5) # Wait before retrying recovery
                           continue # Skip to next loop iteration
                      else:
                           print("[networking.py] listen_for_messages: Socket recovered.")
                 except Exception as recovery_err:
                      print(f"[networking.py] listen_for_messages: Error during socket recovery: {recovery_err}")
                      time.sleep(5)
                      continue

            try:
                # Timeout is now set by default on the socket during setup_socket
                # Or could be set here: self.socket.settimeout(1.0)
                data, addr = self.socket.recvfrom(buffer_recv_size)

                try:
                    msg = json.loads(data.decode())

                    # --- Removed Hint Message Debug Noise ---
                    # if msg.get('type') == 'hint':
                    #     # ... (keep if needed for debugging, but noisy)

                    self.message_handler.handle_message(msg)

                except json.JSONDecodeError as e:
                    print(f"[networking.py] Failed to decode message from {addr}: {e}")
                    # Optional: Log the raw data snippet for debugging
                    # print(f"Raw data snippet: {data[:100]}...")
                except Exception as e:
                    print(f"[networking.py] Error processing message from {addr}: {e}")
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
                    print(f"[networking.py] Socket error in listen_for_messages: {e}")
                    traceback.print_exc()
                    # Socket error occurred, attempt recovery
                    print("[networking.py] Attempting socket recovery...")
                    try:
                        # setup_socket handles closing and recreating
                        self.setup_socket()
                        if self.socket:
                             print("[networking.py] Successfully recovered socket after error.")
                        else:
                             print("[networking.py] Socket recovery failed, will retry.")
                             time.sleep(5) # Wait before next loop iteration tries again
                    except Exception as setup_error:
                        print(f"[networking.py] Failed to recover socket: {setup_error}")
                        # Ensure socket is None if recovery fails hard
                        with self._socket_lock:
                           self.socket = None
                        if self.running:
                            time.sleep(5) # Wait before next loop iteration
                else:
                    print("[networking.py] Socket error during shutdown.")
                    break # Exit loop if not running
            except Exception as e:
                # Catch any other unexpected errors
                if self.running:
                    print(f"[networking.py] Unexpected error in listen_for_messages: {e}")
                    traceback.print_exc()
                    time.sleep(1) # Brief pause before continuing
                else:
                    print("[networking.py] Unexpected error during shutdown.")
                    break # Exit loop if not running

        print("[networking.py] Message listener loop finished.")


    def shutdown(self):
        print("[networking.py] Shutting down network...")
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
                    self.socket.settimeout(0.5)
                    self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12345))
        except Exception as e:
            print(f"[networking.py] Error sending disconnect message: {e}")
        finally:
            # Close the socket safely
            with self._socket_lock:
                if self.socket:
                    try:
                        self.socket.close()
                        print("[networking.py] Socket closed.")
                    except Exception as e:
                        print(f"[networking.py] Error closing socket during shutdown: {e}")
                    finally:
                        self.socket = None # Ensure it's None

        # Wait briefly for threads to potentially exit (optional)
        # if hasattr(self, 'listen_thread') and self.listen_thread.is_alive():
        #     self.listen_thread.join(timeout=1.0)
        # if hasattr(self, 'announce_thread') and self.announce_thread.is_alive():
        #     self.announce_thread.join(timeout=1.0)

        print("[networking.py] Network shutdown complete.")

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