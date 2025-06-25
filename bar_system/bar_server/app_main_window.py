# bar_server/app_main_window.py
import sys
import json
import time
import base64
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout,
    QTextEdit, QPushButton, QHBoxLayout, QMessageBox, QTabWidget, QListWidget, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSlot

import socket
import config
import data_manager
from network_server import ServerWorker
from client_handler import ClientHandler # NEW: Import the client handler
from app_widgets import TileWidget, ItemDialog
from order_manager import OrderManager

class BarManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Bar Order Manager - {config.SERVER_HOSTNAME}")
        self.setGeometry(100, 100, 1000, 800)

        self.items_data = []
        self.items_map = {}
        self.tile_widgets_map = {}
        self.selected_item_id = None
        
        # --- NEW --- State for managing client threads and handlers
        self.client_threads = {} # {socket: QThread}
        self.client_handlers = {} # {socket: ClientHandler}

        self.order_manager = OrderManager()
        self._setup_network_server()

        self._setup_ui()
        
        self.load_and_display_items()
        self.refresh_order_list()
        self.start_server()

    def _setup_ui(self):
        # ... (UI setup is unchanged, so I'll omit it for brevity)
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.item_management_tab = QWidget()
        self.order_management_tab = QWidget()
        self.tabs.addTab(self.item_management_tab, "Item Management")
        self.tabs.addTab(self.order_management_tab, "Order Management")
        self._create_item_management_layout()
        self._create_order_management_layout()

    def _create_item_management_layout(self):
        layout = QVBoxLayout(self.item_management_tab)
        control_panel = QHBoxLayout()
        add_btn = QPushButton("Add New Item")
        add_btn.clicked.connect(self.add_item)
        self.edit_btn = QPushButton("Edit Selected Item")
        self.edit_btn.clicked.connect(self.edit_selected_item)
        self.delete_btn = QPushButton("Delete Selected Item")
        self.delete_btn.clicked.connect(self.delete_selected_item)
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        control_panel.addWidget(add_btn)
        control_panel.addWidget(self.edit_btn)
        control_panel.addWidget(self.delete_btn)
        layout.addLayout(control_panel)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tiles_container = QWidget()
        self.tiles_layout = QGridLayout(tiles_container)
        self.tiles_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll_area.setWidget(tiles_container)
        layout.addWidget(scroll_area, stretch=1)

    def _create_order_management_layout(self):
        layout = QVBoxLayout(self.order_management_tab)
        layout.addWidget(QLabel("<h2>Pending Orders</h2>"))
        self.pending_orders_list = QListWidget()
        self.pending_orders_list.setStyleSheet("font-size: 14px;")
        layout.addWidget(self.pending_orders_list)
        complete_button = QPushButton("Complete Selected Order")
        complete_button.clicked.connect(self.complete_selected_order)
        layout.addWidget(complete_button)
        layout.addWidget(QLabel("<h3>Server Log</h3>"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        self.server_status_label = QLabel("Server Status: Initializing...")
        layout.addWidget(self.server_status_label)
        self.order_manager.order_updated.connect(self.refresh_order_list)


    def load_and_display_items(self):
        self.items_data = data_manager.load_items_from_config()
        self.items_map = {item['id']: item for item in self.items_data}
        self.log_message(f"Loaded {len(self.items_data)} items from config.")
        self.refresh_all_tiles()

    def refresh_all_tiles(self):
        for i in reversed(range(self.tiles_layout.count())): 
            widget = self.tiles_layout.itemAt(i).widget()
            if widget: widget.deleteLater()
        self.tile_widgets_map.clear()
        self.selected_item_id = None
        self.edit_btn.setEnabled(False)
        self.delete_btn.setEnabled(False)
        row, col = 0, 0
        sorted_items = sorted(self.items_data, key=lambda x: x.get('name', ''))
        for item_data in sorted_items:
            tile = TileWidget(item_data)
            tile.tile_clicked.connect(self.handle_tile_clicked)
            # UX Improvement: Allow double-clicking to edit
            tile.tile_double_clicked.connect(self.edit_selected_item)
            self.tiles_layout.addWidget(tile, row, col)
            self.tile_widgets_map[item_data["id"]] = tile
            col = (col + 1) % config.MAX_TILE_COLUMNS
            if col == 0: row += 1
        self.broadcast_item_list_update()

    def handle_tile_clicked(self, item_id, tile_widget):
        if self.selected_item_id and self.selected_item_id in self.tile_widgets_map:
            self.tile_widgets_map[self.selected_item_id].set_selected(False)
        self.selected_item_id = item_id
        tile_widget.set_selected(True)
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    def add_item(self):
        # ... (This method is unchanged)
        dialog = ItemDialog(self)
        if dialog.exec_():
            data = dialog.get_data()
            if not all([data["id"], data["name"]]):
                QMessageBox.warning(self, "Input Error", "Item ID and Name are required.")
                return
            if data["id"] in self.items_map:
                QMessageBox.warning(self, "Input Error", f"Item ID '{data['id']}' already exists.")
                return
            data["image_file"] = data_manager.ensure_image_exists(data["image_source_path"], data["id"])
            self.items_data.append(data)
            self.items_map[data["id"]] = data
            data_manager.save_items_to_config(self.items_data)
            self.load_and_display_items()

    def edit_selected_item(self):
        # ... (This method is unchanged)
        if not self.selected_item_id: return
        item_to_edit = self.items_map.get(self.selected_item_id)
        dialog = ItemDialog(self, item_to_edit)
        if dialog.exec_():
            data = dialog.get_data()
            data["image_file"] = data_manager.ensure_image_exists(data["image_source_path"], data["id"])
            for i, item in enumerate(self.items_data):
                if item["id"] == self.selected_item_id: self.items_data[i] = data; break
            self.items_map[self.selected_item_id] = data
            data_manager.save_items_to_config(self.items_data)
            self.load_and_display_items()
            
    def delete_selected_item(self):
        # ... (This method is unchanged)
        if not self.selected_item_id: return
        item_name = self.items_map[self.selected_item_id]['name']
        reply = QMessageBox.question(self, 'Delete Item', f"Delete '{item_name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.items_data = [item for item in self.items_data if item["id"] != self.selected_item_id]
            del self.items_map[self.selected_item_id]
            data_manager.save_items_to_config(self.items_data)
            self.load_and_display_items()


    def refresh_order_list(self):
        # ... (This method is unchanged)
        self.pending_orders_list.clear()
        for order in self.order_manager.get_pending_orders():
            quantity = order.get("sender_stats", {}).get("quantity", 1)
            customer = order.get("sender_stats", {}).get("customer_name", "N/A")
            text = f"[{quantity}x] {order['item_name']} for {customer} (ID: ...{order['order_id'][-12:]})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, order['order_id'])
            self.pending_orders_list.addItem(item)
    
    def complete_selected_order(self):
        # ... (This method is unchanged)
        selected_item = self.pending_orders_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Order Selected", "Please select an order from the list to complete.")
            return
        order_id = selected_item.data(Qt.UserRole)
        self.order_manager.complete_order(order_id)
        
    def _setup_network_server(self):
        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.moveToThread(self.server_thread)
        
        # Connect signals from the main server listener
        self.server_worker.log_message_signal.connect(self.log_message)
        self.server_worker.new_connection_signal.connect(self.add_new_client)
        self.server_thread.started.connect(self.server_worker.run)

    def start_server(self):
        if self.server_thread.isRunning(): return
        self.server_thread.start()
        self.server_status_label.setText(f"Server Status: Running on {config.HOST}:{config.PORT}")
        self.log_message("Server thread started.")

    @pyqtSlot(socket.socket, tuple)
    def add_new_client(self, client_socket, address):
        """Creates a new thread and handler for a connecting client."""
        thread = QThread()
        handler = ClientHandler(client_socket, address)
        handler.moveToThread(thread)

        # Connect handler signals to main window slots
        handler.message_received.connect(self.handle_client_message)
        handler.client_disconnected.connect(self.remove_client)
        handler.log_message.connect(self.log_message)
        
        # Connect thread signals
        thread.started.connect(handler.run)
        
        # Store references
        self.client_threads[client_socket] = thread
        self.client_handlers[client_socket] = handler
        
        thread.start()
        self.log_message(f"Client {address} handler moved to new thread. Total clients: {len(self.client_handlers)}")

    @pyqtSlot(socket.socket)
    def remove_client(self, client_socket):
        """Cleans up resources for a disconnected client."""
        if client_socket in self.client_handlers:
            handler = self.client_handlers.pop(client_socket)
            handler.deleteLater() # Schedule for deletion
        
        if client_socket in self.client_threads:
            thread = self.client_threads.pop(client_socket)
            thread.quit()
            thread.wait() # Wait for thread to finish cleanly

        try:
            client_socket.close()
        except socket.error:
            pass # Socket may already be closed

        self.log_message(f"Cleaned up resources for disconnected client. Total clients: {len(self.client_handlers)}")

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
            self.log_message(f"Unknown message type '{msg_type}' from {client_socket.getpeername()}")

    def handle_order_request(self, client_handler, order_data):
        processed_order = self.order_manager.add_order(order_data, self.items_map)
        if processed_order:
            self.tile_widgets_map[processed_order["item_id"]].indicate_order()
            ack_payload = {"order_id": processed_order["order_id"], "item_id": processed_order["item_id"]}
            client_handler.send_message("ORDER_ACK", ack_payload)
        else:
            nack_payload = {"order_id": order_data["order_id"], "item_id": order_data["item_id"], "reason": "Item not found"}
            client_handler.send_message("ORDER_NACK", nack_payload)

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
            self.log_message(f"Client requested invalid image file: {filename}")
            return

        image_path = os.path.join(config.IMAGE_DIR, filename)
        if os.path.exists(image_path):
            try:
                with open(image_path, 'rb') as f:
                    image_data = f.read()
                
                image_hash = data_manager.get_file_hash(image_path)
                b64_data = base64.b64encode(image_data).decode('utf-8')
                
                payload = {"filename": filename, "hash": image_hash, "data": b64_data}
                client_handler.send_message("IMAGE_DATA", payload)
                self.log_message(f"Sent image {filename} to {client_handler.address}")
            except Exception as e:
                self.log_message(f"Error sending image {filename}: {e}")
        else:
            self.log_message(f"Client requested non-existent image: {filename}")

    def broadcast_item_list_update(self):
        if not (hasattr(self, 'server_worker') and self.server_worker._is_running): return
        if not self.client_handlers: return # No one to broadcast to

        self.log_message(f"Broadcasting item list update to {len(self.client_handlers)} clients.")
        
        client_item_list = [
            {"id": i["id"], "name": i["name"], "description": i.get("description"),
             "price": i.get("price", 0.0), "image_file": i.get("image_file"),
             "image_hash": i.get("image_hash")}
            for i in self.items_data
        ]
        payload = {"items": client_item_list}
        
        for handler in self.client_handlers.values():
            handler.send_message("AVAILABLE_ITEMS_UPDATE", payload)

    def log_message(self, message):
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        print(f"SERVER LOG: [{timestamp}] {message}")

    def closeEvent(self, event):
        self.log_message("Application closing. Shutting down server...")
        # Stop all client handlers
        for handler in list(self.client_handlers.values()):
            handler.stop()
        
        # Stop the main server listener
        if self.server_thread.isRunning():
            self.server_worker.stop()
            self.server_thread.quit()
            self.server_thread.wait(3000)
            
        event.accept()