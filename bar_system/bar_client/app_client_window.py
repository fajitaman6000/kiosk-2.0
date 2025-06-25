# bar_client/app_client_window.py
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QScrollArea, QGridLayout, QFrame, QPushButton, QMessageBox,
    QInputDialog, QTextEdit, QHBoxLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSlot, pyqtSignal, QTimer
import os
import time
import config
from network_worker import NetworkWorker
from image_cache_manager import ImageCacheManager
from discovery_listener import DiscoveryListener

class ItemTileWidget(QFrame):
    """A custom widget to display a single item in the grid."""
    def __init__(self, item_data, image_path, parent=None):
        super().__init__(parent)
        self.item_id = item_data['id']
        self.item_name = item_data['name']

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setFixedWidth(220)
        self.setMinimumHeight(320)

        layout = QVBoxLayout(self)

        # Image
        self.image_label = QLabel()
        self.image_label.setFixedSize(150, 150)
        self.image_label.setAlignment(Qt.AlignCenter)
        self.set_image(image_path) # Use helper method
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Name and Price
        price = item_data.get("price")
        if price is None:
            price = 0.0 # Default to 0.0 if price is None

        name_text = f"{self.item_name}\n(${price:.2f})"
        name_label = QLabel(name_text)
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        # Description
        desc_label = QLabel(item_data.get("description", "No description."))
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("font-size: 10px; color: #555;")
        layout.addWidget(desc_label)

        layout.addStretch()

        # Order Button
        self.order_button = QPushButton("Order Now")
        layout.addWidget(self.order_button)

    def set_image(self, image_path):
        """Helper method to set the image label's pixmap from a path."""
        if image_path and os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            self.image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Using a placeholder image for better visual consistency
            placeholder_path = os.path.join(config.APP_ROOT, "placeholder.png")
            pixmap = QPixmap(placeholder_path)
            if not pixmap.isNull():
                 self.image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.image_label.setText("(Loading Image...)")
                self.image_label.setStyleSheet("border: 1px solid gray; background-color: #eee;")


class AppClientWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Bar Kiosk - {config.CLIENT_HOSTNAME}")
        self.setGeometry(100, 100, 850, 600)

        self.items_cache = {} # {item_id: item_data}
        self.tile_widgets = {} # To easily access tiles by item_id: {item_id: ItemTileWidget}

        self.server_host = None
        self.server_port = None
        
        self._setup_network()
        self.cache_manager = ImageCacheManager(self.network_worker)
        self._setup_ui()
        
        self.start_connection_process()

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Status Bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Initializing...")
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        main_layout.addLayout(status_layout)

        # Item Display Area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.tiles_container = QWidget()
        self.tiles_layout = QGridLayout(self.tiles_container)
        self.tiles_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_area.setWidget(self.tiles_container)
        main_layout.addWidget(self.scroll_area, stretch=1)
        
        # Log Area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(100)
        main_layout.addWidget(self.log_area)
        
        self.log_message("Client application started.")
        self.update_items_display() # Initial empty display

    def _setup_network(self):
        # --- Setup for TCP Worker (for main communication) ---
        self.network_thread = QThread()
        self.network_worker = NetworkWorker()
        self.network_worker.moveToThread(self.network_thread)
        self.network_worker.status_updated.connect(self.log_message)
        self.network_worker.status_updated.connect(self.update_status_bar)
        self.network_worker.items_received.connect(self.handle_items_update)
        self.network_worker.image_received.connect(self.handle_image_update)
        self.network_worker.order_acknowledged.connect(self.handle_order_ack)
        self.network_worker.order_rejected.connect(self.handle_order_nack)
        self.network_worker.server_error.connect(self.handle_server_error)
        self.network_worker.disconnected.connect(self.on_disconnected)
        self.network_thread.started.connect(self.network_worker.run)

        # --- Setup for UDP Listener (for discovery) ---
        self.discovery_thread = QThread()
        self.discovery_listener = DiscoveryListener()
        self.discovery_listener.moveToThread(self.discovery_thread)
        self.discovery_listener.log_message.connect(self.log_message)
        self.discovery_listener.server_found.connect(self.on_server_discovered)
        self.discovery_thread.started.connect(self.discovery_listener.run)
    
    @pyqtSlot()
    def start_connection_process(self):
        if self.network_thread.isRunning() or self.discovery_thread.isRunning():
            return
        
        self.items_cache.clear()
        self.update_items_display()
        
        self.update_status_bar("Searching for server...")
        self.discovery_thread.start()
        
    @pyqtSlot(str, int)
    def on_server_discovered(self, host, port):
        if self.discovery_thread.isRunning():
            self.discovery_listener.stop()
            self.discovery_thread.quit()
            self.discovery_thread.wait()

        # Save the server details and start the main TCP connection worker
        self.log_message(f"Server found. Connecting to {host}:{port} via TCP...")
        self.network_worker.set_server_details(host, port)
        self.network_thread.start()

    @pyqtSlot(str)
    def update_status_bar(self, status):
        self.status_label.setText(f"Status: {status}")

    @pyqtSlot(dict)
    def handle_items_update(self, items_dict):
        if set(self.items_cache.keys()) != set(items_dict.keys()):
            self.items_cache = items_dict
            self.log_message(f"Received full item list update with {len(items_dict)} items.")
            self.update_items_display(full_redraw=True)
        else:
            # If it's just a data update (e.g., price change), update in place.
            self.items_cache = items_dict
            self.log_message(f"Received item data update for {len(items_dict)} items.")
            self.update_items_display(full_redraw=False)

    @pyqtSlot(dict)
    def handle_image_update(self, image_payload):
        local_path = self.cache_manager.save_image_from_server(image_payload)
        if not local_path:
            return

        self.log_message(f"Image '{image_payload.get('filename')}' cached.")
        
        # Find which item this image belongs to
        item_id_to_update = None
        for item_id, item_data in self.items_cache.items():
            if item_data.get("image_file") == image_payload.get("filename"):
                item_id_to_update = item_id
                break
        
        # If we found the corresponding item and its tile widget exists, update it directly
        if item_id_to_update and item_id_to_update in self.tile_widgets:
            tile = self.tile_widgets[item_id_to_update]
            tile.set_image(local_path)
            self.log_message(f"Updated tile image for item '{item_data.get('name')}'.")
        else:
            # Fallback to a full redraw if something is out of sync
            self.update_items_display(full_redraw=True)

    # --- METHOD ACTUALLY FIXED THIS TIME ---
    def update_items_display(self, full_redraw=True):
        """
        Updates the item grid. Clears the existing grid and repopulates it based
        on the current state of self.items_cache. This is now stateless and safe.
        """
        # 1. Clear all existing widgets from the layout
        for i in reversed(range(self.tiles_layout.count())):
            widget = self.tiles_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Always clear the tile widget map when doing a redraw
        self.tile_widgets.clear()

        # 2. Decide what to display based on the current cache
        if not self.items_cache:
            # If cache is empty, display a temporary "waiting" message.
            waiting_label = QLabel("Searching for server...")
            waiting_label.setAlignment(Qt.AlignCenter)
            waiting_label.setStyleSheet("font-size: 22px; color: #888;")
            self.tiles_layout.addWidget(waiting_label, 0, 0, 1, 3)
        else:
            # If we have items, populate the grid with tiles
            row, col = 0, 0
            max_cols = 3
            sorted_items = sorted(self.items_cache.values(), key=lambda x: x.get('name', ''))
            
            for item_data in sorted_items:
                local_image_path = self.cache_manager.check_and_request_image(item_data)
                
                tile = ItemTileWidget(item_data, local_image_path)
                tile.order_button.clicked.connect(
                    lambda checked, i=item_data['id']: self.prompt_and_send_order(i)
                )
                
                self.tiles_layout.addWidget(tile, row, col)
                self.tile_widgets[item_data['id']] = tile
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

    def prompt_and_send_order(self, item_id):
        if not self.network_thread.isRunning():
            QMessageBox.warning(self, "Not Connected", "Could not place order: not connected to the server.")
            return

        item = self.items_cache.get(item_id)
        if not item: return

        quantity, ok = QInputDialog.getInt(self, "Order Quantity", f"Enter quantity for {item['name']}:", 1, 1, 99)
        if not ok: return

        customer_name, ok = QInputDialog.getText(self, "Customer Name", "Enter customer name (optional):")
        if not ok: customer_name = "Anonymous"
        
        order_id = f"{config.CLIENT_HOSTNAME}_{int(time.time())}_{item_id}"
        order_payload = {
            "order_id": order_id, "item_id": item_id,
            "sender_stats": {"quantity": quantity, "customer_name": customer_name or "Anonymous",
                             "order_time_local": time.strftime("%Y-%m-%d %H:%M:%S")},
            "sender_hostname": config.CLIENT_HOSTNAME
        }
        
        self.network_worker.send_message("ORDER_ITEM", order_payload)
        
        tile = self.tile_widgets.get(item_id)
        if tile:
            tile.order_button.setEnabled(False)
            tile.order_button.setText("Ordering...")

        self.log_message(f"Sent order for {quantity} of {item['name']} (ID: {order_id}).")

    @pyqtSlot(str)
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        print(f"CLIENT LOG: [{timestamp}] {message}")
        
    @pyqtSlot(dict)
    def handle_order_ack(self, payload):
        item_id = payload.get('item_id')
        QMessageBox.information(self, "Order Confirmed", f"Order for item '{self.items_cache.get(item_id, {}).get('name', item_id)}' was processed successfully!")
        tile = self.tile_widgets.get(item_id)
        if tile: # UX: Re-enable button
            tile.order_button.setEnabled(True)
            tile.order_button.setText("Order Now")

    @pyqtSlot(dict)
    def handle_order_nack(self, payload):
        item_id = payload.get('item_id')
        QMessageBox.critical(self, "Order Rejected", f"Order for item '{self.items_cache.get(item_id, {}).get('name', item_id)}' was rejected: {payload.get('reason')}")
        tile = self.tile_widgets.get(item_id)
        if tile: # UX: Re-enable button
            tile.order_button.setEnabled(True)
            tile.order_button.setText("Order Now")

    @pyqtSlot(str)
    def handle_server_error(self, message):
        QMessageBox.critical(self, "Server Error", f"The server reported an error:\n\n{message}")

    @pyqtSlot()
    def on_disconnected(self):
        self.log_message("Connection closed.")
        self.update_status_bar("Disconnected. Will try to reconnect...")
        
        if self.network_thread.isRunning():
            self.network_thread.quit()
            self.network_thread.wait()
            
        QTimer.singleShot(3000, self.start_connection_process)

    def closeEvent(self, event):
        self.log_message("Application closing...")
        self.on_disconnected = lambda: None
        
        if self.discovery_thread.isRunning():
            self.discovery_listener.stop()
            self.discovery_thread.quit()
            self.discovery_thread.wait(1500)
        # Stop network thread if it's running
        if self.network_thread.isRunning():
            self.network_worker.stop()
            self.network_thread.quit()
            self.network_thread.wait(1500)
        event.accept()