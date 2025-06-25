# bar_server/network_server.py
import socket
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

import config

class ServerWorker(QObject):
    """
    Listens for incoming connections and passes them off to a new ClientHandler
    running in its own QThread. This object itself runs in a dedicated QThread.
    """
    log_message_signal = pyqtSignal(str)
    # Signal to the main window that a new client needs to be managed
    new_connection_signal = pyqtSignal(socket.socket, tuple)
    server_stopped_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._is_running = False
        self.server_socket = None

    @pyqtSlot()
    def run(self):
        self._is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((config.HOST, config.PORT))
            self.server_socket.listen(10) # Increased backlog for multiple clients
            self.log_message_signal.emit(f"Server listening on {config.HOST}:{config.PORT}")
        except OSError as e:
            self.log_message_signal.emit(f"FATAL: Could not bind to {config.HOST}:{config.PORT} - {e}")
            self._is_running = False
            return

        self.server_socket.settimeout(1.0) # Non-blocking accept

        while self._is_running:
            try:
                conn, addr = self.server_socket.accept()
                self.log_message_signal.emit(f"Accepted connection from {addr}")
                # Pass the new connection to the main window to be managed
                self.new_connection_signal.emit(conn, addr)
            except socket.timeout:
                continue
            except OSError:
                if self._is_running:
                     self.log_message_signal.emit("Server socket accept error. Shutting down listener.")
                break
        
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
            
        self.log_message_signal.emit("Server listener has stopped.")
        self.server_stopped_signal.emit()

    @pyqtSlot()
    def stop(self):
        self.log_message_signal.emit("Stopping server listener...")
        self._is_running = False
        # To unblock the accept() call, we can just close the socket from this thread
        if self.server_socket:
             # This will cause accept() to raise an OSError, breaking the loop
             self.server_socket.close()