# bar_server/client_manager.py
import socket
import json
from PyQt5.QtCore import QObject, pyqtSignal

# A simple thread-safe object to manage client connections
class ClientManager(QObject):
    log_message = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.clients = []

    def add_client(self, client_socket):
        if client_socket not in self.clients:
            self.clients.append(client_socket)
            self.log_message.emit(f"Client added: {client_socket.getpeername()}. Total clients: {len(self.clients)}")

    def remove_client(self, client_socket):
        if client_socket in self.clients:
            self.clients.remove(client_socket)
            self.log_message.emit(f"Client removed. Total clients: {len(self.clients)}")
            try:
                client_socket.close()
            except socket.error:
                pass # Already closed

    def broadcast(self, msg_type, payload):
        self.log_message.emit(f"Broadcasting '{msg_type}' to {len(self.clients)} clients.")
        message = {"type": msg_type, "payload": payload}
        message_bytes = json.dumps(message).encode('utf-8') + b'\n'

        # Iterate over a copy in case the list is modified during iteration
        for client in list(self.clients):
            try:
                client.sendall(message_bytes)
            except (socket.error, BrokenPipeError) as e:
                self.log_message.emit(f"Broadcast error to {client.getpeername()}: {e}. Removing.")
                self.remove_client(client)