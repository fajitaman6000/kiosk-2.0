# bar_client/app_client_window.py
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QScrollArea, QGridLayout, QFrame, QPushButton, QMessageBox,
    QInputDialog, QTextEdit, QHBoxLayout
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, QThread, pyqtSlot, pyqtSignal

import time
import config
from network_worker import NetworkWorker
from image_cache_manager import ImageCacheManager

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
        if image_path:
            pixmap = QPixmap(image_path)
            self.image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_label.setText("(Loading Image...)")
            self.image_label.setStyleSheet("border: 1px solid gray;")
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


class AppClientWindow(QMainWindow):
    # Signal to send a message via the network worker
    send_message_signal = pyqtSignal(str, dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Bar Kiosk - {config.CLIENT_HOSTNAME}")
        self.setGeometry(100, 100, 850, 600)

        self.items_cache = {} # {item_id: item_data}

        self._setup_network()
        self.cache_manager = ImageCacheManager(self.network_worker)
        self._setup_ui()

        # Initial connection attempt
        self.toggle_connection()

    def _setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Status Bar
        status_layout = QHBoxLayout()
        self.status_label = QLabel("Status: Initializing...")
        self.connect_button = QPushButton("Connect")
        self.connect_button.setCheckable(True)
        self.connect_button.clicked.connect(self.toggle_connection)
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.connect_button)
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
        self.network_thread = QThread()
        self.network_worker = NetworkWorker()
        self.network_worker.moveToThread(self.network_thread)

        # Connect worker signals to UI slots
        self.network_worker.status_updated.connect(self.log_message)
        self.network_worker.status_updated.connect(self.update_status_bar)
        self.network_worker.items_received.connect(self.handle_items_update)
        self.network_worker.image_received.connect(self.handle_image_update)
        self.network_worker.order_acknowledged.connect(self.handle_order_ack)
        self.network_worker.order_rejected.connect(self.handle_order_nack)
        self.network_worker.server_error.connect(self.handle_server_error)
        self.network_worker.disconnected.connect(self.on_disconnected)

        # Connect UI signals to worker slots
        #self.send_message_signal.connect(self.network_worker.send_message)
        self.network_thread.started.connect(self.network_worker.run)
        
    def toggle_connection(self):
        if self.connect_button.isChecked():
            if not self.network_thread.isRunning():
                self.network_thread.start()
                self.connect_button.setText("Disconnect")
        else:
            if self.network_thread.isRunning():
                self.log_message("Disconnecting...")
                self.network_worker.stop()
                self.connect_button.setText("Connect")
                # The on_disconnected slot will handle final cleanup

    @pyqtSlot(str)
    def update_status_bar(self, status):
        self.status_label.setText(f"Status: {status}")

    @pyqtSlot(dict)
    def handle_items_update(self, items_dict):
        self.items_cache = items_dict
        self.log_message(f"Received {len(items_dict)} items from server.")
        self.update_items_display()
        
    @pyqtSlot(dict)
    def handle_image_update(self, image_payload):
        local_path = self.cache_manager.save_image_from_server(image_payload)
        if local_path:
            self.log_message(f"Image '{image_payload.get('filename')}' cached.")
            self.update_items_display() # Redraw to show the new image

    def update_items_display(self):
        # Clear existing widgets
        for i in reversed(range(self.tiles_layout.count())): 
            self.tiles_layout.itemAt(i).widget().deleteLater()

        if not self.items_cache:
            # You can add a placeholder label here if you want
            return

        row, col = 0, 0
        max_cols = 3
        for item_id, item_data in self.items_cache.items():
            local_image_path = self.cache_manager.check_and_request_image(item_data)
            
            tile = ItemTileWidget(item_data, local_image_path)
            # Use a lambda to capture the item_id for the click event
            tile.order_button.clicked.connect(
                lambda checked, i=item_id: self.prompt_and_send_order(i)
            )
            
            self.tiles_layout.addWidget(tile, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def prompt_and_send_order(self, item_id):
        print(f"DEBUG: 1. Click registered for item_id: {item_id}")
        if not self.network_thread.isRunning():
            QMessageBox.warning(self, "Not Connected", "Please connect to the server to place an order.")
            return

        item = self.items_cache.get(item_id)
        if not item:
            print(f"DEBUG: ERROR - Item ID {item_id} not found in cache.")
            return

        quantity, ok = QInputDialog.getInt(self, "Order Quantity", f"Enter quantity for {item['name']}:", 1, 1, 99)
        if not ok: return

        customer_name, ok = QInputDialog.getText(self, "Customer Name", "Enter customer name (optional):")
        if not ok: customer_name = "Anonymous"
        
        order_id = f"{config.CLIENT_HOSTNAME}_{int(time.time())}_{item_id}"
        order_payload = {
            "order_id": order_id,
            "item_id": item_id,
            "sender_stats": {
                "quantity": quantity,
                "customer_name": customer_name,
                "order_time_local": time.strftime("%Y-%m-%d %H:%M:%S")
            },
            "sender_hostname": config.CLIENT_HOSTNAME
        }
        print(f"DEBUG: 2. Assembled payload for order {order_id}. Emitting signal.")
        self.network_worker.send_message("ORDER_ITEM", order_payload)
        self.log_message(f"Sent order for {quantity} of {item_id} (Order ID: {order_id}).")

    @pyqtSlot(str)
    def log_message(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        
    @pyqtSlot(dict)
    def handle_order_ack(self, payload):
        QMessageBox.information(self, "Order Confirmed", f"Order for {payload.get('item_id')} was processed successfully!")

    @pyqtSlot(dict)
    def handle_order_nack(self, payload):
        QMessageBox.critical(self, "Order Rejected", f"Order for {payload.get('item_id')} was rejected: {payload.get('reason')}")

    @pyqtSlot(str)
    def handle_server_error(self, message):
        QMessageBox.critical(self, "Server Error", f"The server reported an error:\n\n{message}")

    @pyqtSlot()
    def on_disconnected(self):
        self.log_message("Connection closed.")
        self.update_status_bar("Disconnected")
        self.connect_button.setChecked(False)
        self.connect_button.setText("Connect")
        
        # Stop the thread cleanly
        self.network_thread.quit()
        self.network_thread.wait()

    def closeEvent(self, event):
        self.log_message("Application closing...")
        self.network_worker.stop()
        if self.network_thread.isRunning():
            self.network_thread.quit()
            self.network_thread.wait(3000) # Wait up to 3 seconds
        event.accept()