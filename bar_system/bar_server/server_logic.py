# bar_server/server_logic.py
import socket
import base64
import os
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QThread

import config
import data_manager
from network_server import ServerWorker
from client_handler import ClientHandler
from order_manager import OrderManager
from discovery_broadcaster import DiscoveryBroadcaster
from bar_audio_manager import AudioManager

class ServerLogic(QObject):
    """
    Handles all backend server logic, separating it from the UI.
    This includes network management, client handling, and business rules.
    """
    # Signals for the UI
    log_message = pyqtSignal(str)
    server_status_update = pyqtSignal(str)
    order_list_updated = pyqtSignal() # Signals that the order list UI should be refreshed
    ui_notification = pyqtSignal() # General signal for flashing UI elements

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Core data and managers
        self.items_data = []
        self.items_map = {}
        self.order_manager = OrderManager()
        self.audio_manager = AudioManager()
        
        # Client management
        self.client_threads = {}
        self.client_handlers = {}
        
        # Connect order manager signal to our own relay signal
        self.order_manager.order_updated.connect(self.order_list_updated)
        
        self._setup_network_server()
        self.load_items()

    def _setup_network_server(self):
        # TCP Server for Clients
        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.moveToThread(self.server_thread)
        self.server_worker.log_message_signal.connect(self.log_message)
        self.server_worker.new_connection_signal.connect(self.add_new_client)
        self.server_thread.started.connect(self.server_worker.run)

        # UDP Broadcaster for Discovery
        self.discovery_thread = QThread()
        self.discovery_broadcaster = DiscoveryBroadcaster()
        self.discovery_broadcaster.moveToThread(self.discovery_thread)
        self.discovery_thread.started.connect(self.discovery_broadcaster.run)
        
    def start(self):
        """Starts the network listeners."""
        if not self.server_thread.isRunning():
            self.server_thread.start()
            self.log_message.emit("[ServerLogic] Server TCP listener thread started.")
        
        if not self.discovery_thread.isRunning():
            self.discovery_thread.start()
            self.log_message.emit("[ServerLogic] Server UDP discovery thread started.")
            
        self.server_status_update.emit(f"Running and Broadcasting on {config.HOST}:{config.PORT}")
        
    def stop(self):
        """Stops the network listeners and cleans up threads."""
        self.log_message.emit("[ServerLogic] Shutting down server...")
        for handler in list(self.client_handlers.values()):
            handler.stop()
        if self.discovery_thread.isRunning():
            self.discovery_broadcaster.stop()
            self.discovery_thread.quit()
            self.discovery_thread.wait(3000)
        if self.server_thread.isRunning():
            self.server_worker.stop()
            self.server_thread.quit()
            self.server_thread.wait(3000)
        self.log_message.emit("[ServerLogic] Shutdown complete.")

    def load_items(self):
        """Loads item data from config and stores it internally."""
        self.items_data = data_manager.load_items_from_config()
        self.items_map = {item['id']: item for item in self.items_data}
        self.log_message.emit(f"Loaded {len(self.items_data)} items from config.")

    @pyqtSlot()
    def on_items_changed(self):
        """Public slot to be called when the item config is changed by the UI."""
        self.log_message.emit("Item configuration updated. Reloading and broadcasting to clients.")
        self.load_items()
        self.broadcast_item_list_update()

    @pyqtSlot(socket.socket, tuple)
    def add_new_client(self, client_socket, address):
        """Creates a new thread and handler for a connecting client."""
        thread = QThread()
        handler = ClientHandler(client_socket, address)
        handler.moveToThread(thread)

        handler.message_received.connect(self.handle_client_message)
        handler.client_disconnected.connect(self.remove_client)
        handler.log_message.connect(self.log_message)
        
        thread.started.connect(handler.run)
        
        self.client_threads[client_socket] = thread
        self.client_handlers[client_socket] = handler
        
        thread.start()
        self.log_message.emit(f"[ServerLogic] Client {address} handler moved to new thread. Total clients: {len(self.client_handlers)}")

    @pyqtSlot(socket.socket)
    def remove_client(self, client_socket):
        """Cleans up resources for a disconnected client."""
        if client_socket in self.client_handlers:
            self.client_handlers.pop(client_socket).deleteLater()
        if client_socket in self.client_threads:
            thread = self.client_threads.pop(client_socket)
            thread.quit()
            thread.wait()
        try:
            client_socket.close()
        except socket.error: pass
        self.log_message.emit(f"Cleaned up resources for disconnected client. Total clients: {len(self.client_handlers)}")

    @pyqtSlot(socket.socket, dict)
    def handle_client_message(self, client_socket, message):
        """The central dispatcher for all incoming messages from all clients."""
        msg_type = message.get("type")
        payload = message.get("payload", {})
        handler = self.client_handlers.get(client_socket)
        if not handler: return

        if msg_type == "REQUEST_ITEMS":
            self.send_item_list_to_client(handler)
        elif msg_type == "REQUEST_IMAGE":
            self.send_image_to_client(handler, payload.get("filename"))
        elif msg_type == "ORDER_ITEM":
            self.handle_order_request(handler, payload)
        else:
            self.log_message.emit(f"Unknown message type '{msg_type}' from {client_socket.getpeername()}")

    def handle_order_request(self, client_handler, order_data):
        processed_order = self.order_manager.add_order(order_data, self.items_map)
        if processed_order:
            self.trigger_order_notification()
            ack_payload = {"order_id": processed_order["order_id"], "item_id": processed_order["item_id"]}
            client_handler.send_message("ORDER_ACK", ack_payload)
        else:
            nack_payload = {"order_id": order_data["order_id"], "item_id": order_data["item_id"], "reason": "Item not found"}
            client_handler.send_message("ORDER_NACK", nack_payload)

    def trigger_order_notification(self):
        """Plays a sound and emits a signal for the UI to flash."""
        self.audio_manager.play_order_notification()
        self.ui_notification.emit()

    def send_item_list_to_client(self, client_handler, msg_type="AVAILABLE_ITEMS"):
        client_item_list = [
            {"id": i["id"], "name": i["name"], "description": i.get("description"),
             "price": i.get("price", 0.0), "image_file": i.get("image_file"),
             "image_hash": i.get("image_hash")} 
            for i in self.items_data
        ]
        client_handler.send_message(msg_type, {"items": client_item_list})

    def send_image_to_client(self, client_handler, filename):
        if not filename or '..' in filename or filename.startswith('/'):
            self.log_message.emit(f"Client requested invalid image file: {filename}")
            return
        image_path = os.path.join(config.IMAGE_DIR, filename)
        if os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as f: image_data = f.read()
                image_hash = data_manager.get_file_hash(image_path)
                b64_data = base64.b64encode(image_data).decode('utf-8')
                payload = {"filename": filename, "hash": image_hash, "data": b64_data}
                client_handler.send_message("IMAGE_DATA", payload)
                self.log_message.emit(f"Sent image {filename} to {client_handler.address}")
            except Exception as e:
                self.log_message.emit(f"Error sending image {filename}: {e}")
        else:
            self.log_message.emit(f"Client requested non-existent image: {filename}")

    def broadcast_item_list_update(self):
        if not (hasattr(self, 'server_worker') and self.server_worker._is_running) or not self.client_handlers: return
        self.log_message.emit(f"Broadcasting item list update to {len(self.client_handlers)} clients.")
        client_item_list = [
            {"id": i["id"], "name": i["name"], "description": i.get("description"),
             "price": i.get("price", 0.0), "image_file": i.get("image_file"),
             "image_hash": i.get("image_hash")}
            for i in self.items_data
        ]
        payload = {"items": client_item_list}
        for handler in self.client_handlers.values():
            handler.send_message("AVAILABLE_ITEMS_UPDATE", payload)