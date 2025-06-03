import sys
import os
import json
import socket
import threading
import datetime
import time

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QScrollArea, QGridLayout, QFrame, QTextEdit, QPushButton
)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QFont # Import QPainter, QFont here
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread, QSize, QTimer # Import QTimer for highlights

# --- Configuration ---
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 50888      # <--- IMPORTANT: MATCH THIS PORT WITH YOUR SENDER SCRIPT
IMAGE_DIR = "images" # Subdirectory for images
RECEIVER_HOSTNAME = socket.gethostname()

# --- Dummy Item Data ---
# In a real app, this might come from a database or config file
ITEMS_DATA = [
    {"id": "apple", "name": "Red Apple", "image_file": "apple.png", "description": "A crisp, juicy red apple."},
    {"id": "banana", "name": "Yellow Banana", "image_file": "banana.png", "description": "A sweet, ripe banana."},
    {"id": "orange", "name": "Juicy Orange", "image_file": "orange.png", "description": "A tangy, vitamin C packed orange."},
    {"id": "grape", "name": "Purple Grapes", "image_file": "grape.png", "description": "A bunch of sweet grapes."},
    {"id": "mango", "name": "Sweet Mango", "image_file": "mango.png", "description": "A tropical delight."},
    {"id": "1", "name": "Test Item 1", "image_file": "default.png", "description": "A generic test item."}, # Added your '1' item
    {"id": "default", "name": "Unknown Item", "image_file": "default.png", "description": "Placeholder for items not found."}
]

# --- Helper to create placeholder images if real ones are missing ---
def get_image_path(filename, size=(150, 150)):
    path = os.path.join(IMAGE_DIR, filename)
    if not os.path.exists(path):
        print(f"Warning: Image {path} not found. Generating placeholder.") # Warning when actually generating
        
        # Create a dummy placeholder if it doesn't exist
        base_name = filename.split('.')[0].lower()
        color_map = {
            "apple": QColor("red"), "banana": QColor("yellow"), "orange": QColor("orange"),
            "grape": QColor("purple"), "mango": QColor("gold"), "default": QColor("lightgray"),
            "1": QColor("#aaddaa") # Specific color for item "1"
        }
        fill_color = color_map.get(base_name, QColor("lightgray"))

        img = QImage(size[0], size[1], QImage.Format.Format_RGB32)
        img.fill(fill_color)
        
        # Add text to placeholder
        painter = QPainter(img)
        painter.setFont(QFont("Arial", 12))
        painter.setPen(Qt.GlobalColor.black)
        painter.drawText(img.rect(), Qt.AlignmentFlag.AlignCenter, f"No Image\n({filename})")
        painter.end()

        img.save(path) # Save it so it's only generated once
        print(f"Generated placeholder for: {path}")
    return path

# --- Tile Widget ---
class TileWidget(QFrame):
    def __init__(self, item_data):
        super().__init__()
        self.item_id = item_data["id"]
        self.item_name = item_data["name"]

        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Raised)
        self.setFixedWidth(180)
        self.setFixedHeight(220)

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5) # Add some padding
        layout.setSpacing(5) # Space between widgets

        # Image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(get_image_path(item_data["image_file"])) # Calls get_image_path (will generate if needed)
        self.image_label.setPixmap(pixmap.scaled(150, 150, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(self.image_label)

        # Name
        self.name_label = QLabel(item_data["name"])
        self.name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        # Description
        self.description_label = QLabel(item_data["description"])
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.description_label.setStyleSheet("font-size: 10px; color: #555;")
        layout.addWidget(self.description_label)

        layout.addStretch() # Push content to top
        self.setLayout(layout)

    def highlight(self):
        # Store original stylesheet to restore it
        self._original_stylesheet = self.styleSheet()
        self.setStyleSheet("background-color: lightblue; border: 2px solid blue;")
        # Reset after a short period (using QTimer for GUI thread safety)
        QTimer.singleShot(1000, self.unhighlight)

    def unhighlight(self):
        self.setStyleSheet(self._original_stylesheet)


# --- Network Server (runs in a separate QThread) ---
class OrderServerWorker(QObject):
    order_received_signal = pyqtSignal(dict) # Signal to emit when an order comes in
    log_message_signal = pyqtSignal(str)
    
    _is_running = False # Control flag for the server loop

    def run(self):
        # DEBUG PRINTS - these will appear in your console/terminal
        print("DEBUG: OrderServerWorker.run() called.")
        self._is_running = True
        
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address
        
        try:
            server_socket.bind((HOST, PORT))
            server_socket.listen()
            self.log_message_signal.emit(f"Server listening on {HOST}:{PORT}")
            print(f"DEBUG: Server bound and listening on {HOST}:{PORT}") # Debug print
        except OSError as e:
            self.log_message_signal.emit(f"ERROR: Could not bind to {HOST}:{PORT} - {e}")
            print(f"DEBUG: ERROR: Could not bind to {HOST}:{PORT} - {e}") # Debug print
            self._is_running = False # Stop if bind fails
            server_socket.close()
            return

        server_socket.settimeout(1.0) # Set a timeout to allow checking _is_running

        while self._is_running:
            try:
                conn, addr = server_socket.accept() # This will block until a connection or timeout
                with conn:
                    self.log_message_signal.emit(f"Connected by {addr}")
                    print(f"DEBUG: Connected by {addr}") # Debug print
                    data_buffer = b""
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        data_buffer += chunk
                    
                    if data_buffer:
                        try:
                            order_data = json.loads(data_buffer.decode('utf-8'))
                            self.log_message_signal.emit(f"Received raw order: {order_data}")
                            print(f"DEBUG: Received raw order: {order_data}") # Debug print
                            self.order_received_signal.emit(order_data)
                            conn.sendall(b"Order Received ACK") # Acknowledge
                        except json.JSONDecodeError:
                            self.log_message_signal.emit(f"Error decoding JSON from {addr}")
                            print(f"DEBUG: Error decoding JSON from {addr}") # Debug print
                            conn.sendall(b"Error: Invalid JSON")
                        except Exception as e:
                            self.log_message_signal.emit(f"Error processing data: {e}")
                            print(f"DEBUG: Error processing data: {e}") # Debug print
                            conn.sendall(b"Error: Processing failed")
                    else:
                         self.log_message_signal.emit(f"No data received from {addr}, closing connection.")
                         print(f"DEBUG: No data received from {addr}") # Debug print

            except socket.timeout:
                continue # Timeout occurred, loop again to check _is_running
            except Exception as e:
                if self._is_running: # Only log if we weren't intentionally stopped
                    self.log_message_signal.emit(f"Server error: {e}")
                    print(f"DEBUG: Server error: {e}") # Debug print
                break # Exit loop on other major errors
        
        server_socket.close() # Ensure the socket is closed
        self.log_message_signal.emit("Server shutdown.")
        print("DEBUG: Server shutdown.") # Debug print
        self._is_running = False

    def stop(self):
        self.log_message_signal.emit("Attempting to stop server...")
        print("DEBUG: OrderServerWorker.stop() called.") # Debug print
        self._is_running = False
        
        # To unblock s.accept() if it's waiting:
        # We connect to the server briefly to force it out of accept().
        # Use '127.0.0.1' (localhost) if the server binds to '0.0.0.0'.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dummy_socket:
                dummy_socket.settimeout(0.1) # Don't wait long
                connect_host = '127.0.0.1' if HOST == '0.0.0.0' else HOST
                dummy_socket.connect((connect_host, PORT))
                dummy_socket.sendall(b"shutdown_ping") # Send some data to ensure wake-up
        except Exception as e:
            print(f"DEBUG: Dummy socket connect error during stop: {e}") # Debug print
            pass # Ignore errors, we're just trying to unblock

# --- Main Application Window ---
class OrderReceiverApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Order Receiver App")
        self.setGeometry(100, 100, 850, 700) # Slightly wider for more columns

        self.items_map = {item["id"]: item for item in ITEMS_DATA}
        self.tile_widgets_map = {} # To access TileWidget by item_id

        # --- Main Layout ---
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --- Tile Display Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.tiles_container_widget = QWidget()
        self.tiles_layout = QGridLayout(self.tiles_container_widget)
        self.tiles_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll_area.setWidget(self.tiles_container_widget)
        main_layout.addWidget(self.scroll_area, stretch=3)

        self.populate_tiles() # This will call get_image_path for each tile AFTER QApplication is ready

        # --- Log Area ---
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-family: monospace; font-size: 10px; background-color: #f0f0f0;")
        main_layout.addWidget(self.log_area, stretch=1)

        # --- Server Status Label ---
        self.server_status_label = QLabel("Server Status: Initializing...")
        self.server_status_label.setStyleSheet("font-weight: bold; color: blue;")
        main_layout.addWidget(self.server_status_label)
        
        # Start server automatically
        self.start_server()
        self.log_message("Application initialized.")

    def populate_tiles(self):
        row, col = 0, 0
        max_cols = 4 # Adjust as needed for width
        for item_data in ITEMS_DATA:
            tile = TileWidget(item_data)
            self.tiles_layout.addWidget(tile, row, col)
            self.tile_widgets_map[item_data["id"]] = tile # Store reference
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

    def start_server(self):
        if hasattr(self, 'server_thread') and self.server_thread.isRunning():
            self.log_message("Server already running.")
            return

        self.server_thread = QThread()
        self.server_worker = OrderServerWorker()
        self.server_worker.moveToThread(self.server_thread)

        # Connect signals
        self.server_worker.order_received_signal.connect(self.handle_order)
        self.server_worker.log_message_signal.connect(self.log_message)
        
        # Connect thread lifecycle signals
        self.server_thread.started.connect(self.server_worker.run)
        self.server_thread.finished.connect(self.server_worker.deleteLater) # Clean up worker
        self.server_thread.finished.connect(self.server_thread.deleteLater) # Clean up thread
        self.server_thread.finished.connect(lambda: self.server_status_label.setText("Server Status: Stopped"))

        self.server_thread.start()
        self.server_status_label.setText(f"Server Status: Running on {HOST}:{PORT}")
        self.log_message("Server starting thread...")


    def stop_server(self):
        if hasattr(self, 'server_worker') and self.server_worker._is_running:
            self.log_message("Stopping server...")
            self.server_worker.stop() # Signal the worker to stop
            
            # Wait for the thread to finish, with a timeout
            if hasattr(self, 'server_thread') and self.server_thread.isRunning():
                if not self.server_thread.wait(3000): # Wait up to 3 seconds
                    self.log_message("Warning: Server thread did not finish cleanly within timeout. Terminating...")
                    print("DEBUG: Forcing server thread termination.")
                    self.server_thread.terminate() # Force stop if still running (less graceful)
                    self.server_thread.wait() # Wait for it to actually terminate
            self.log_message("Server stopped.")
        else:
            self.log_message("Server not running or already stopped.")


    def log_message(self, message):
        # This slot is executed in the main (GUI) thread
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")

    def handle_order(self, order_data):
        # This slot is executed in the main (GUI) thread
        self.log_message(f"Processing order: {order_data}")
        item_id = order_data.get("item_id")

        if item_id in self.items_map:
            item_info = self.items_map[item_id]
            
            # Add receiver-side stats
            processed_order = {
                **order_data, # Original data from sender
                "item_name": item_info["name"],
                "receiver_hostname": RECEIVER_HOSTNAME,
                "received_timestamp_utc": datetime.datetime.utcnow().isoformat(timespec='seconds') + "Z",
                "status": "Processed"
            }
            self.log_message(f"Processed Order: {json.dumps(processed_order, indent=2)}")

            # UI feedback: highlight the tile
            if item_id in self.tile_widgets_map:
                self.tile_widgets_map[item_id].highlight()
        else:
            self.log_message(f"Error: Item ID '{item_id}' not found. Order rejected.")
            # You might want to send a NACK (Negative Acknowledgement) here too.

    def closeEvent(self, event):
        """Ensure server thread is stopped cleanly on application exit."""
        self.log_message("Application closing. Shutting down server...")
        self.stop_server()
        event.accept()


if __name__ == "__main__":
    # Ensure images directory exists (for placeholders)
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    app = QApplication(sys.argv)
    window = OrderReceiverApp()
    window.show()
    sys.exit(app.exec())