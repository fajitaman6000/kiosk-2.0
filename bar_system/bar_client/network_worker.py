# bar_client/network_worker.py
import socket
import json
import time
from queue import Queue, Empty
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

import config

class NetworkWorker(QObject):
    """
    Handles all network communication in a separate thread using a dedicated
    producer-consumer queue for thread-safe message sending.
    """
    # Signals to send data back to the UI
    status_updated = pyqtSignal(str)
    items_received = pyqtSignal(dict)
    image_received = pyqtSignal(dict)
    order_acknowledged = pyqtSignal(dict)
    order_rejected = pyqtSignal(dict)
    server_error = pyqtSignal(str)
    disconnected = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.sock = None
        self._is_running = False

        self.send_queue = Queue()
        self.server_host = None
        self.server_port = None

    def set_server_details(self, host, port):
        """Sets the server address and port to connect to."""
        self.server_host = host
        self.server_port = port

    @pyqtSlot()
    def run(self):
        """The main loop for the network worker."""
        if self._is_running or not self.server_host or not self.server_port:
            self.status_updated.emit("Cannot connect: Server details not set.")
            self._handle_disconnect()
            return
        
        self._is_running = True
        
        try:
            self.status_updated.emit(f"Connecting to {self.server_host}:{self.server_port}...")
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5.0)
            self.sock.connect((self.server_host, self.server_port))
            self.sock.settimeout(0.1)  # Short timeout for non-blocking operations
            self.status_updated.emit("Connected")
            self.send_message("REQUEST_ITEMS", {}) # Initial request
        except Exception as e:
            self.status_updated.emit(f"Connection Failed: {e}")
            self._handle_disconnect()
            return

        buffer = b""
        while self._is_running:
            # --- FIX --- Part 1: Process the send queue ---
            try:
                # Get a message without blocking the whole loop
                msg_to_send = self.send_queue.get_nowait()
                try:
                    self.sock.sendall(json.dumps(msg_to_send).encode('utf-8') + b'\n')
                except (socket.error, BrokenPipeError) as e:
                    self.status_updated.emit(f"Send Error: {e}")
                    break # Exit loop
            except Empty:
                pass # Queue is empty, which is normal

            # --- FIX --- Part 2: Process the receive socket ---
            try:
                chunk = self.sock.recv(4096)
                if not chunk:
                    self.status_updated.emit("Server closed the connection.")
                    break # Exit loop
                
                buffer += chunk
                while b'\n' in buffer:
                    message_json, buffer = buffer.split(b'\n', 1)
                    if message_json.strip():
                        self._process_server_message(message_json)

            except socket.timeout:
                continue # This is expected, allows the loop to check _is_running and the send_queue
            except (socket.error, json.JSONDecodeError) as e:
                self.status_updated.emit(f"Network Error: {e}")
                break # Exit loop
            
            # A small sleep prevents this loop from busy-waiting and eating CPU
            time.sleep(0.01)
        
        self._handle_disconnect()

    def _process_server_message(self, message_json):
        """Decodes the message and emits the appropriate signal."""
        try:
            message = json.loads(message_json.decode('utf-8'))
            msg_type = message.get("type")
            payload = message.get("payload", {})

            if msg_type in ["AVAILABLE_ITEMS", "AVAILABLE_ITEMS_UPDATE"]:
                items_dict = {item['id']: item for item in payload.get("items", [])}
                self.items_received.emit(items_dict)
            elif msg_type == "IMAGE_DATA":
                self.image_received.emit(payload)
            elif msg_type == "ORDER_ACK":
                self.order_acknowledged.emit(payload)
            elif msg_type == "ORDER_NACK":
                self.order_rejected.emit(payload)
            elif msg_type == "ERROR":
                self.server_error.emit(payload.get('message', 'Unknown server error'))
            elif msg_type == "SERVER_SHUTDOWN":
                self.status_updated.emit("Server is shutting down.")
                self.stop()
            else:
                print(f"Unknown message type received: {msg_type}")

        except json.JSONDecodeError:
            print(f"Received invalid JSON: {message_json.decode(errors='ignore')}")
        except Exception as e:
            print(f"Error processing server message: {e}")

    def _handle_disconnect(self):
        """Cleans up the connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
        self._is_running = False
        self.disconnected.emit()

    @pyqtSlot()
    def stop(self):
        """Stops the network loop."""
        self._is_running = False

    def send_message(self, msg_type, payload):
        """
        Public method to be called from other threads.
        It safely adds the message to a queue to be sent by the worker's run loop.
        """
        message = {"type": msg_type, "payload": payload}
        self.send_queue.put(message)