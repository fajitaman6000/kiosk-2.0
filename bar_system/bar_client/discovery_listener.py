# bar_client/discovery_listener.py
import socket
import json
from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal

from network_protocol import DISCOVERY_PORT, DISCOVERY_MESSAGE_HEADER

class DiscoveryListener(QObject):
    """
    Listens for UDP broadcasts from the server to automatically find its IP and port.
    """
    # Signal: emits (str: host, int: port)
    server_found = pyqtSignal(str, int)
    log_message = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._is_running = False
        self.udp_socket = None

    @pyqtSlot()
    def run(self):
        self._is_running = True
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Allow reuse of the address, important for quick restarts
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Bind to the discovery port on all interfaces
            self.udp_socket.bind(('', DISCOVERY_PORT))
            self.udp_socket.settimeout(1.0) # Check for stop signal every second
        except OSError as e:
            self.log_message.emit(f"FATAL: Could not bind to UDP port {DISCOVERY_PORT}. Is another client running? Error: {e}")
            self._is_running = False
            return

        self.log_message.emit(f"Listening for server broadcast on UDP port {DISCOVERY_PORT}...")

        while self._is_running:
            try:
                data, addr = self.udp_socket.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))

                # Validate the message
                if message.get("header") == DISCOVERY_MESSAGE_HEADER:
                    host = message.get("host")
                    port = message.get("port")
                    if host and isinstance(port, int):
                        self.log_message.emit(f"Discovered server at {host}:{port}")
                        self.server_found.emit(host, port)
                        break # Found it, our job is done. Exit the loop.

            except socket.timeout:
                continue # Just a timeout, loop again
            except (json.JSONDecodeError, KeyError, TypeError):
                # Invalid message, ignore and continue listening
                continue
            except Exception as e:
                self.log_message.emit(f"Discovery error: {e}")

        self.log_message.emit("Discovery listener stopped.")
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None

    @pyqtSlot()
    def stop(self):
        self._is_running = False