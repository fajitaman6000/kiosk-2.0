# bar_client/app_client_window.py
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QScrollArea, QGridLayout, QFrame, QPushButton, QMessageBox,
    QLineEdit, QTextEdit, QHBoxLayout, QGraphicsView, QGraphicsScene,
    QGraphicsProxyWidget, QSpinBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSlot, pyqtSignal, QTimer, QRectF
import os
import time
import config
from network_worker import NetworkWorker
from image_cache_manager import ImageCacheManager
from discovery_listener import DiscoveryListener

DEBUG = False

class ItemTileWidget(QFrame):
    """
    A custom widget to display a single item, now with an integrated,
    touch-friendly ordering interface that appears within the tile itself.
    """
    # This new signal is emitted when the user confirms an order.
    order_placed = pyqtSignal(str, int, str) # item_id, quantity, customer_name

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
        layout.addWidget(self.image_label, alignment=Qt.AlignCenter)

        # Name and Price
        self.name_label = QLabel()
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Description
        self.description_label = QLabel()
        self.description_label.setAlignment(Qt.AlignCenter)
        self.description_label.setWordWrap(True)
        self.description_label.setStyleSheet("font-size: 10px; color: #555;")
        layout.addWidget(self.description_label)

        layout.addStretch()

        # --- NEW: Ordering UI (initially hidden) ---
        self._setup_ordering_ui(layout)

        # --- NEW: Browsing UI (initially visible) ---
        self.order_button = QPushButton("Order Now")
        self.order_button.setStyleSheet("font-size: 16px; padding: 10px; font-weight: bold;")
        self.order_button.clicked.connect(self._enter_ordering_mode)
        layout.addWidget(self.order_button)

        # Set initial data and state
        self.update_data(item_data, image_path)
        self._enter_browsing_mode()

    def _setup_ordering_ui(self, parent_layout):
        """Creates the hidden widget containing controls for ordering."""
        self.ordering_widget = QWidget()
        ordering_layout = QVBoxLayout(self.ordering_widget)
        ordering_layout.setContentsMargins(0, 5, 0, 5)
        ordering_layout.setSpacing(8)

        # Quantity input with large, touch-friendly buttons
        qty_layout = QHBoxLayout()
        qty_layout.addWidget(QLabel("<b>Quantity:</b>"))
        self.quantity_spinbox = QSpinBox()
        self.quantity_spinbox.setRange(1, 99)
        self.quantity_spinbox.setButtonSymbols(QSpinBox.PlusMinus)
        self.quantity_spinbox.setStyleSheet("QSpinBox { font-size: 16px; height: 35px; } QSpinBox::up-button, QSpinBox::down-button { width: 45px; }")
        qty_layout.addWidget(self.quantity_spinbox)
        ordering_layout.addLayout(qty_layout)

        # Customer Name input
        ordering_layout.addWidget(QLabel("<b>Name:</b> (optional)"))
        self.customer_name_edit = QLineEdit()
        self.customer_name_edit.setPlaceholderText("Anonymous")
        self.customer_name_edit.setStyleSheet("font-size: 14px; padding: 5px;")
        ordering_layout.addWidget(self.customer_name_edit)

        # Action Buttons for confirming or canceling
        button_layout = QHBoxLayout()
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px; font-size: 14px;")
        self.confirm_button.clicked.connect(self._confirm_order)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("background-color: #dc3545; color: white; font-weight: bold; padding: 8px; font-size: 14px;")
        self.cancel_button.clicked.connect(self._enter_browsing_mode)
        button_layout.addWidget(self.confirm_button)
        button_layout.addWidget(self.cancel_button)
        ordering_layout.addLayout(button_layout)
        
        parent_layout.addWidget(self.ordering_widget)

    def _enter_browsing_mode(self):
        """Shows the default view of the tile, hiding the order controls."""
        self.description_label.show()
        self.order_button.show()
        self.ordering_widget.hide()
        # Reset order button state in case it was "Ordering..."
        self.order_button.setEnabled(True)
        self.order_button.setText("Order Now")

    def _enter_ordering_mode(self):
        """Shows the ordering controls, hiding the default button and description."""
        self.description_label.hide()
        self.order_button.hide()
        self.ordering_widget.show()
        self.quantity_spinbox.setValue(1) # Reset to default
        self.customer_name_edit.clear()
        self.customer_name_edit.setFocus() # Focus for keyboard input

    def _confirm_order(self):
        """Gathers data and emits the order_placed signal for the main window to handle."""
        quantity = self.quantity_spinbox.value()
        customer_name = self.customer_name_edit.text().strip()
        
        # Visually indicate that the order is being processed
        self.order_button.setText("Ordering...")
        self.order_button.setEnabled(False)
        self._enter_browsing_mode()

        # Emit the signal
        self.order_placed.emit(self.item_id, quantity, customer_name)

    def update_data(self, item_data, image_path):
        """Updates the tile's display with new data without recreating the whole widget."""
        self.item_name = item_data['name']
        price = item_data.get("price", 0.0)
        self.name_label.setText(f"{self.item_name}\n(${price:.2f})")
        self.description_label.setText(item_data.get("description", "No description."))
        self.set_image(image_path)

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
        # --- MODIFIED --- Window geometry is now portrait (swapped width/height)
        self.setGeometry(100, 100, 600, 850)

        self.items_cache = {} # {item_id: item_data}
        self.tile_widgets = {} # To easily access tiles by item_id: {item_id: ItemTileWidget}

        self.server_host = None
        self.server_port = None
        
        self._setup_network()
        self.cache_manager = ImageCacheManager(self.network_worker)
        self._setup_ui()
        
        self.start_connection_process()

    def _setup_ui(self):
        # --- NEW: Graphics View Rotation ---
        # 1. Create the original UI on a standard widget, as if it were not rotated.
        #    This is our "source" widget.
        source_widget = QWidget()
        # --- MODIFIED --- This layout is the ORIGINAL landscape layout.
        main_layout = QVBoxLayout(source_widget)

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
        
        # We need to give the source widget a fixed size that matches the
        # un-rotated dimensions we want.
        source_widget.setFixedSize(850, 600)

        # 2. Create a QGraphicsScene and a proxy to hold our source widget.
        scene = QGraphicsScene()
        proxy = QGraphicsProxyWidget()
        proxy.setWidget(source_widget)
        scene.addItem(proxy)

        # 3. Create a QGraphicsView to display the scene. This view will be the
        #    actual central widget of our main window.
        view = QGraphicsView(self)
        view.setScene(scene)
        
        # Remove borders and scrollbars for a clean look
        view.setFrameStyle(QFrame.NoFrame)
        view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # --- THE MAGIC --- Rotate the entire view 90 degrees clockwise.
        view.rotate(90)
        
        # 4. Set the rotated view as the central widget.
        self.setCentralWidget(view)
        
        # Final setup
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
        # The new item data is stored, and the display is updated intelligently.
        self.items_cache = items_dict
        self.log_message(f"Received item list update with {len(items_dict)} items.")
        self.update_items_display()

    @pyqtSlot(dict)
    def handle_image_update(self, image_payload):
        local_path = self.cache_manager.save_image_from_server(image_payload)
        if not local_path:
            return

        self.log_message(f"Image '{image_payload.get('filename')}' cached.")
        
        # Find which item this image belongs to and update its tile directly
        for item_id, item_data in self.items_cache.items():
            if item_data.get("image_file") == image_payload.get("filename"):
                if item_id in self.tile_widgets:
                    self.tile_widgets[item_id].set_image(local_path)
                    self.log_message(f"Updated tile image for item '{item_data.get('name')}'.")
                break
        
    def update_items_display(self):
        """
        Updates the item grid intelligently. Instead of a full-redraw, this
        method adds, removes, or updates only the necessary tiles, resulting
        in a smoother, flicker-free user experience.
        """
        # 1. Synchronize the set of visible tiles with the item cache
        new_item_ids = set(self.items_cache.keys())
        current_tile_ids = set(self.tile_widgets.keys())

        # Remove tiles for items that no longer exist in the cache
        for item_id in current_tile_ids - new_item_ids:
            tile_to_remove = self.tile_widgets.pop(item_id)
            tile_to_remove.deleteLater()

        # Clear the layout so we can re-add widgets in the correct sorted order
        # This does NOT delete the widgets themselves, just their layout position
        while self.tiles_layout.count():
            child = self.tiles_layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # 2. Update existing tiles and create new ones
        for item_id in new_item_ids:
            item_data = self.items_cache[item_id]
            # Check cache for image; this will request it if missing
            local_image_path = self.cache_manager.check_and_request_image(item_data)
            
            if item_id in self.tile_widgets:
                # If the tile widget already exists, just update its data in-place
                self.tile_widgets[item_id].update_data(item_data, local_image_path)
            else:
                # If it's a new item, create a new tile widget
                new_tile = ItemTileWidget(item_data, local_image_path)
                # Connect the new tile's custom signal to our handler slot
                new_tile.order_placed.connect(self.send_order_request)
                self.tile_widgets[item_id] = new_tile

        # 3. Repopulate the grid layout with all the up-to-date widgets, sorted by name
        max_cols = 3 
        if not self.tile_widgets:
            # If there are no items, display a "waiting" message
            waiting_label = QLabel("Searching for server or waiting for items...")
            waiting_label.setAlignment(Qt.AlignCenter)
            waiting_label.setStyleSheet("font-size: 22px; color: #888;")
            self.tiles_layout.addWidget(waiting_label, 0, 0, 1, max_cols)
        else:
            row, col = 0, 0
            # Sort tiles alphabetically by name for a consistent layout
            sorted_tiles = sorted(self.tile_widgets.values(), key=lambda tile: tile.item_name)
            for tile in sorted_tiles:
                self.tiles_layout.addWidget(tile, row, col)
                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1

    @pyqtSlot(str, int, str)
    def send_order_request(self, item_id, quantity, customer_name):
        """A slot that receives order details from a tile and sends it to the server."""
        if not self.network_thread.isRunning():
            QMessageBox.warning(self, "Not Connected", "Could not place order: not connected to the server.")
            # If not connected, reset the tile's UI back to browsing mode
            if item_id in self.tile_widgets:
                self.tile_widgets[item_id]._enter_browsing_mode()
            return
        
        order_id = f"{config.CLIENT_HOSTNAME}_{int(time.time())}_{item_id}"
        order_payload = {
            "order_id": order_id, "item_id": item_id,
            "sender_stats": {"quantity": quantity, "customer_name": customer_name or "Anonymous",
                             "order_time_local": time.strftime("%Y-%m-%d %H:%M:%S")},
            "sender_hostname": config.CLIENT_HOSTNAME
        }
        
        self.network_worker.send_message("ORDER_ITEM", order_payload)
        
        item_name = self.items_cache.get(item_id, {}).get('name', 'Unknown Item')
        self.log_message(f"Sent order for {quantity} of {item_name} (ID: {order_id}).")

    @pyqtSlot(str)
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        print(f"CLIENT LOG: [{timestamp}] {message}")
        
    @pyqtSlot(dict)
    def handle_order_ack(self, payload):
        item_id = payload.get('item_id')
        item_name = self.items_cache.get(item_id, {}).get('name', item_id)
        #QMessageBox.information(self, "Order Confirmed", f"Your order for '{item_name}' was received successfully!")
        tile = self.tile_widgets.get(item_id)
        if tile: # UX: Reset the tile back to its default browsing state
            tile._enter_browsing_mode()

    @pyqtSlot(dict)
    def handle_order_nack(self, payload):
        item_id = payload.get('item_id')
        item_name = self.items_cache.get(item_id, {}).get('name', item_id)
        #QMessageBox.critical(self, "Order Rejected", f"Your order for '{item_name}' was rejected: {payload.get('reason')}")
        tile = self.tile_widgets.get(item_id)
        if tile: # UX: Reset the tile back to its default browsing state
            tile._enter_browsing_mode()

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