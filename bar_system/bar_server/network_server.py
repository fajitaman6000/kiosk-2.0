# bar_server/network_server.py
import socket
import json
import threading
import base64
import os
from PyQt5.QtCore import QObject, pyqtSignal

import config
import data_manager

class ServerWorker(QObject):
    log_message_signal = pyqtSignal(str)
    order_received_signal = pyqtSignal(dict)
    client_connected_signal = pyqtSignal(socket.socket)
    client_disconnected_signal = pyqtSignal(socket.socket)

    _is_running = False
    server_socket = None

    def run(self):
        self._is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((config.HOST, config.PORT))
            self.server_socket.listen(5)
            self.log_message_signal.emit(f"Server listening on {config.HOST}:{config.PORT}")
        except OSError as e:
            self.log_message_signal.emit(f"ERROR: Could not bind to {config.HOST}:{config.PORT} - {e}")
            self._is_running = False
            return

        self.server_socket.settimeout(1.0)

        while self._is_running:
            try:
                conn, addr = self.server_socket.accept()
                self.log_message_signal.emit(f"Accepted connection from {addr}")
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
            except socket.timeout:
                continue
            except OSError:
                if self._is_running:
                     self.log_message_signal.emit("Server socket error during accept.")
                break

        if self.server_socket: self.server_socket.close()
        self.log_message_signal.emit("Server shutdown complete.")
        self._is_running = False

    def handle_client(self, conn, addr):
        try:
            buffer = b""
            # Use a timeout on recv to prevent the thread from blocking indefinitely
            # This can help with cleaner shutdowns.
            conn.settimeout(5.0) 
            while self._is_running:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        self.log_message_signal.emit(f"Client {addr} disconnected gracefully.")
                        break # Normal, clean disconnect
                    buffer += chunk
                
                    while b'\n' in buffer:
                        message_json_str, buffer = buffer.split(b'\n', 1)
                        if not message_json_str.strip(): continue

                        try:
                            message = json.loads(message_json_str.decode('utf-8'))

                            print(f"SERVER DEBUG: Received raw message from {addr}: {message}")

                            msg_type = message.get("type")
                            payload = message.get("payload", {})

                            if msg_type == "REQUEST_ITEMS":
                                self.client_connected_signal.emit(conn)
                            elif msg_type == "REQUEST_IMAGE":
                                filename = payload.get("filename")
                                self.send_image_to_client(conn, filename)
                            elif msg_type == "ORDER_ITEM":
                                print("SERVER DEBUG: Message type is ORDER_ITEM. Emitting signal.")
                                payload["_client_address"] = addr 
                                payload["_client_socket"] = conn
                                self.order_received_signal.emit(payload)
                            else:
                                self.log_message_signal.emit(f"Unknown message type from {addr}: {msg_type}")
                        except json.JSONDecodeError:
                            self.log_message_signal.emit(f"Invalid JSON from {addr}: {message_json_str.decode(errors='ignore')}")
                        except Exception as e:
                            self.log_message_signal.emit(f"Error processing client message: {e}")
                except (socket.timeout, InterruptedError):
                    # Timeout is not an error, just continue the loop to check _is_running
                    continue
                except ConnectionResetError:
                    # This is the specific error from the traceback. Treat it as a disconnect.
                    self.log_message_signal.emit(f"Client {addr} connection reset.")
                    break # Exit the loop
                except Exception as e:
                    # Catch any other potential errors during communication
                    self.log_message_signal.emit(f"Error with client {addr}: {e}")
                    break # Exit the loop
        finally:
            self.client_disconnected_signal.emit(conn)

    def send_image_to_client(self, conn, filename):
        """Finds an image, base64 encodes it, and sends it to the client."""
        if not filename or '..' in filename or filename.startswith('/'):
            self.log_message_signal.emit(f"Client requested invalid image file: {filename}")
            return

        image_path = os.path.join(config.IMAGE_DIR, filename)
        if os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                image_hash = data_manager.get_file_hash(image_path)
                b64_data = base64.b64encode(image_data).decode('utf-8')
                
                payload = {"filename": filename, "hash": image_hash, "data": b64_data}
                message = {"type": "IMAGE_DATA", "payload": payload}
                conn.sendall(json.dumps(message).encode('utf-8') + b'\n')
                self.log_message_signal.emit(f"Sent image {filename} to {conn.getpeername()}")
            except Exception as e:
                self.log_message_signal.emit(f"Error sending image {filename}: {e}")
        else:
            self.log_message_signal.emit(f"Client requested non-existent image: {filename}")

    def stop(self):
        self.log_message_signal.emit("Attempting to stop server worker...")
        self._is_running = False
        if self.server_socket:
            try:
                # Use a dummy socket to unblock the accept() call
                connect_host = '127.0.0.1' if config.HOST == '0.0.0.0' else config.HOST
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dummy_socket:
                    dummy_socket.settimeout(0.1)
                    dummy_socket.connect((connect_host, config.PORT))
            except Exception:
                pass