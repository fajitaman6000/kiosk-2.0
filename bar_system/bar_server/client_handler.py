# bar_server/client_handler.py
import socket
import json
from queue import Queue, Empty  # Import Queue and Empty
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

class ClientHandler(QObject):
    """
    Handles all communication for a single client in its own thread.
    Communicates with the main application thread via signals.
    """
    # Signals to the main window
    message_received = pyqtSignal(socket.socket, dict)
    client_disconnected = pyqtSignal(socket.socket)
    log_message = pyqtSignal(str)
    
    # --- REMOVED --- No longer need an internal signal for sending
    # _send_data_signal = pyqtSignal(bytes)

    def __init__(self, client_socket, address):
        super().__init__()
        self.socket = client_socket
        self.address = address
        self._is_running = False
        self.send_queue = Queue()  # --- NEW --- A thread-safe queue for outgoing messages

    @pyqtSlot()
    def run(self):
        """Main loop to listen for messages from this client."""
        self._is_running = True
        self.log_message.emit(f"Client handler started for {self.address}")
        
        # --- REMOVED --- No longer need to connect the internal signal
        # self._send_data_signal.connect(self._send_data)
        
        buffer = b""
        self.socket.settimeout(1.0) # Use timeout for non-blocking operations

        while self._is_running:
            # --- NEW: Part 1: Process the send queue ---
            try:
                # Get an outgoing message without blocking the loop
                data_to_send = self.send_queue.get_nowait()
                self.socket.sendall(data_to_send)
            except Empty:
                pass  # Queue is empty, which is normal
            except (socket.error, BrokenPipeError) as e:
                self.log_message.emit(f"Send error to {self.address}: {e}. Disconnecting.")
                break # Exit the loop on send error

            # --- Part 2: Process the receive socket ---
            try:
                chunk = self.socket.recv(4096)
                if not chunk:
                    self.log_message.emit(f"Client {self.address} disconnected gracefully.")
                    break

                buffer += chunk
                while b'\n' in buffer:
                    message_json_str, buffer = buffer.split(b'\n', 1)
                    if not message_json_str.strip():
                        continue
                    
                    try:
                        message = json.loads(message_json_str.decode('utf-8'))
                        # Emit a generic signal with the raw message data
                        self.message_received.emit(self.socket, message)
                    except json.JSONDecodeError:
                        self.log_message.emit(f"Invalid JSON from {self.address}: {message_json_str.decode(errors='ignore')}")

            except socket.timeout:
                continue # Allows checking _is_running and the send_queue
            except (socket.error, ConnectionResetError) as e:
                self.log_message.emit(f"Socket error with {self.address}: {e}")
                break
        
        self.log_message.emit(f"Client handler for {self.address} is stopping.")
        self.client_disconnected.emit(self.socket)

    @pyqtSlot()
    def stop(self):
        """Signals the run loop to exit."""
        self._is_running = False

    # --- MODIFIED --- This method is now simpler and thread-safe
    @pyqtSlot(str, dict)
    def send_message(self, msg_type, payload):
        """Public slot to allow the main thread to send a message to this client."""
        message = {"type": msg_type, "payload": payload}
        message_bytes = json.dumps(message).encode('utf-8') + b'\n'
        # Simply put the message on the queue. The run() loop will send it.
        self.send_queue.put(message_bytes)

    # --- REMOVED --- This private slot is no longer needed
    # @pyqtSlot(bytes)
    # def _send_data(self, data):
    #     """Private slot that executes on this thread to send data."""
    #     if not self._is_running: return
    #     try:
    #         self.socket.sendall(data)
    #     except (socket.error, BrokenPipeError) as e:
    #         self.log_message.emit(f"Send error to {self.address}: {e}")
    #         self.stop() # Trigger shutdown of this handler