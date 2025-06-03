import sys
import os
import json
import socket
import threading
import datetime
import time
import shutil
from datetime import timezone

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel,
    QScrollArea, QGridLayout, QFrame, QTextEdit, QPushButton,
    QHBoxLayout, QLineEdit, QFileDialog, QMessageBox, QDialog, QFormLayout,
    QInputDialog
)
from PyQt5.QtGui import QPixmap, QImage, QColor, QPainter, QFont
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QThread, QTimer

# --- Configuration ---
HOST = '0.0.0.0'
PORT = 50888
IMAGE_DIR = "images"
ITEMS_CONFIG_FILE = "items_config.json"
RECEIVER_HOSTNAME = socket.gethostname()

# --- Helper to create/copy images ---
def ensure_image_exists(source_path, item_id, size=(150, 150)):
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    _, ext = os.path.splitext(source_path)
    if not ext: ext = ".png"
    target_filename = f"{item_id.replace(' ', '_').lower()}{ext}"
    target_path = os.path.join(IMAGE_DIR, target_filename)

    if source_path.startswith("#") or source_path.lower() in [c.lower() for c in QColor.colorNames()]:
        print(f"Generating placeholder for: {item_id} with color {source_path}")
        img = QImage(size[0], size[1], QImage.Format.Format_RGB32)
        
        color_obj = QColor(source_path)
        if not color_obj.isValid():
            print(f"Warning: Invalid color string '{source_path}'. Using lightgray.")
            color_obj = QColor("lightgray")
        img.fill(color_obj)

        painter = QPainter(img)
        painter.setFont(QFont("Arial", 10))
        painter.setPen(Qt.black)
        painter.drawText(img.rect(), Qt.AlignCenter, f"{item_id}\n(Color Fill)")
        painter.end()
        img.save(target_path)
    elif os.path.exists(source_path):
        if os.path.abspath(source_path) != os.path.abspath(target_path):
            try:
                shutil.copy(source_path, target_path)
                print(f"Copied image from {source_path} to {target_path}")
            except shutil.SameFileError:
                print(f"Source and target image are the same: {source_path}")
            except Exception as e:
                print(f"Error copying image {source_path} to {target_path}: {e}")
                return None
        else:
            print(f"Image {target_path} already in image directory.")
    elif not os.path.exists(target_path):
        print(f"Warning: Source image {source_path} not found. Generating default placeholder for {item_id}.")
        img = QImage(size[0], size[1], QImage.Format.Format_RGB32)
        img.fill(QColor("lightgray"))
        painter = QPainter(img)
        painter.setFont(QFont("Arial", 10))
        painter.setPen(Qt.black)
        painter.drawText(img.rect(), Qt.AlignCenter, f"{item_id}\n(No Image)")
        painter.end()
        img.save(target_path)
    else:
        print(f"Image {target_path} already exists. Skipping generation/copy.")

    return target_filename if os.path.exists(target_path) else None


# --- Tile Widget ---
class TileWidget(QFrame):
    tile_clicked = pyqtSignal(str, QWidget) # Emits item_id and self (the tile widget)

    def __init__(self, item_data):
        super().__init__()
        self.item_id = item_data["id"]
        self.item_name = item_data["name"]
        self.item_image_file = item_data.get("image_file", "default.png")

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setFixedWidth(180)
        self.setFixedHeight(220)
        self.setCursor(Qt.PointingHandCursor) # Indicate clickable

        self._original_stylesheet = self.styleSheet() # Store base style
        self.set_selected(False) # Initialize as not selected

        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        
        image_full_path = os.path.join(IMAGE_DIR, self.item_image_file)
        if not os.path.exists(image_full_path):
            print(f"Warning: Tile image {image_full_path} not found. Attempting to generate default placeholder.")
            default_img_name = ensure_image_exists("lightgray", f"{self.item_id}_missing_fallback") 
            if default_img_name:
                image_full_path = os.path.join(IMAGE_DIR, default_img_name)
            else:
                image_full_path = ""

        if image_full_path and os.path.exists(image_full_path):
            pixmap = QPixmap(image_full_path)
            self.image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            self.image_label.setText(f"No Image\n({self.item_image_file})")
            self.image_label.setStyleSheet("border: 1px solid gray; color: gray;")

        layout.addWidget(self.image_label)

        self.name_label = QLabel(item_data["name"])
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-weight: bold;")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        desc = item_data.get("description", "No description.")
        self.description_label = QLabel(desc)
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignCenter)
        self.description_label.setStyleSheet("font-size: 10px; color: #555;")
        layout.addWidget(self.description_label)

        layout.addStretch()
        self.setLayout(layout)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.tile_clicked.emit(self.item_id, self)
        super().mousePressEvent(event) # Pass event to base class

    def set_selected(self, is_selected):
        if is_selected:
            self.setStyleSheet(f"{self._original_stylesheet} border: 3px solid blue;")
        else:
            self.setStyleSheet(self._original_stylesheet)

    # For order indication, instead of highlight which was for selection
    def indicate_order(self):
        original_style = self.styleSheet()
        self.setStyleSheet(f"{original_style} background-color: #aaffaa; border: 3px solid green;")
        QTimer.singleShot(500, lambda: self.setStyleSheet(original_style))


# --- Add/Edit Item Dialog ---
class ItemDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Item" if item_data is None else "Edit Item")
        self.item_data = item_data if item_data else {}

        layout = QFormLayout(self)

        self.id_edit = QLineEdit(self.item_data.get("id", ""))
        if item_data:
            self.id_edit.setReadOnly(True) # ID cannot be changed when editing
        layout.addRow("Item ID:", self.id_edit)

        self.name_edit = QLineEdit(self.item_data.get("name", ""))
        layout.addRow("Name:", self.name_edit)

        self.desc_edit = QTextEdit(self.item_data.get("description", ""))
        self.desc_edit.setFixedHeight(80)
        layout.addRow("Description:", self.desc_edit)

        self.image_path_edit = QLineEdit(self.item_data.get("image_source_path", ""))
        self.image_path_edit.setPlaceholderText("Path to image file or color name (e.g., #FF0000 or 'red')")
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_image)
        image_layout = QHBoxLayout()
        image_layout.addWidget(self.image_path_edit)
        image_layout.addWidget(browse_button)
        layout.addRow("Image File/Color:", image_layout)

        buttons = QHBoxLayout()
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(self.ok_button)
        buttons.addWidget(cancel_button)
        layout.addRow(buttons)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg *.jpeg *.bmp)")
        if file_path:
            self.image_path_edit.setText(file_path)

    def get_data(self):
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "description": self.desc_edit.toPlainText().strip(),
            "image_source_path": self.image_path_edit.text().strip()
        }

# --- Network Server Worker ---
class ServerWorker(QObject):
    log_message_signal = pyqtSignal(str)
    order_received_signal = pyqtSignal(dict)
    client_connected_signal = pyqtSignal(socket.socket)
    client_disconnected_signal = pyqtSignal(socket.socket)

    _is_running = False
    server_socket = None

    def run(self):
        print("DEBUG: ServerWorker.run() called.")
        self._is_running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            self.server_socket.bind((HOST, PORT))
            self.server_socket.listen(5)
            self.log_message_signal.emit(f"Server listening on {HOST}:{PORT}")
            print(f"DEBUG: Server bound and listening on {HOST}:{PORT}")
        except OSError as e:
            self.log_message_signal.emit(f"ERROR: Could not bind to {HOST}:{PORT} - {e}")
            print(f"DEBUG: ERROR: Could not bind to {HOST}:{PORT} - {e}")
            self._is_running = False
            if self.server_socket: self.server_socket.close()
            return

        self.server_socket.settimeout(1.0)

        while self._is_running:
            try:
                conn, addr = self.server_socket.accept()
                self.log_message_signal.emit(f"Accepted connection from {addr}")
                print(f"DEBUG: Accepted connection from {addr}")
                self.client_connected_signal.emit(conn)
                client_thread = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                client_thread.start()
            except socket.timeout:
                continue
            except OSError:
                if self._is_running:
                     self.log_message_signal.emit("Server socket error during accept.")
                break
            except Exception as e:
                if self._is_running:
                    self.log_message_signal.emit(f"Server accept error: {e}")
                    print(f"DEBUG: Server accept error: {e}")
                break
        
        if self.server_socket: self.server_socket.close()
        self.log_message_signal.emit("Server shutdown complete.")
        print("DEBUG: ServerWorker.run() finished.")
        self._is_running = False

    def handle_client(self, conn, addr):
        try:
            conn.settimeout(5.0)
            buffer = b""
            while self._is_running:
                try:
                    chunk = conn.recv(4096)
                    if not chunk:
                        self.log_message_signal.emit(f"Client {addr} disconnected.")
                        break 
                    buffer += chunk
                    
                    while b'\n' in buffer:
                        message_json_str, buffer = buffer.split(b'\n', 1)
                        if not message_json_str.strip(): continue

                        try:
                            message = json.loads(message_json_str.decode('utf-8'))
                            self.log_message_signal.emit(f"From {addr}: {message}")
                            print(f"DEBUG: From {addr}: {message}")

                            msg_type = message.get("type")
                            payload = message.get("payload", {})

                            if msg_type == "REQUEST_ITEMS":
                                self.client_connected_signal.emit(conn)
                                print("DEBUG: Client re-requested items.")

                            elif msg_type == "ORDER_ITEM":
                                payload["_client_address"] = addr 
                                payload["_client_socket"] = conn
                                self.order_received_signal.emit(payload)
                            else:
                                self.log_message_signal.emit(f"Unknown message type from {addr}: {msg_type}")
                                conn.sendall(json.dumps({"type": "ERROR", "payload": {"message": "Unknown command"}}).encode() + b'\n')
                        
                        except json.JSONDecodeError:
                            self.log_message_signal.emit(f"Invalid JSON from {addr}: {message_json_str.decode(errors='ignore')}")
                            conn.sendall(json.dumps({"type": "ERROR", "payload": {"message": "Invalid JSON"}}).encode() + b'\n')
                        except Exception as e:
                            self.log_message_signal.emit(f"Error processing client message: {e}")
                            print(f"DEBUG: Error processing client message {addr}: {e}")
                            try:
                                conn.sendall(json.dumps({"type": "ERROR", "payload": {"message": f"Server-side error: {type(e).__name__}"}}).encode() + b'\n')
                            except: pass

                except socket.timeout:
                    continue
                except ConnectionResetError:
                    self.log_message_signal.emit(f"Client {addr} reset connection.")
                    break
                except Exception as e:
                    self.log_message_signal.emit(f"Error with client {addr}: {e}")
                    print(f"DEBUG: Error with client {addr}: {e}")
                    break
        finally:
            self.client_disconnected_signal.emit(conn)
            print(f"DEBUG: Client handler for {addr} finished.")

    def stop(self):
        self.log_message_signal.emit("Attempting to stop server worker...")
        print("DEBUG: ServerWorker.stop() called.")
        self._is_running = False
        if self.server_socket:
            try:
                connect_host = '127.0.0.1' if HOST == '0.0.0.0' else HOST
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as dummy_socket:
                    dummy_socket.settimeout(0.1)
                    dummy_socket.connect((connect_host, PORT))
                    dummy_socket.sendall(b"shutdown_ping")
            except Exception as e:
                print(f"DEBUG: Dummy socket connect error during stop: {e}")
                pass

# --- Main Application Window (Receiver) ---
class ItemAuthorityApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Item Authority - {RECEIVER_HOSTNAME}")
        self.setGeometry(100, 100, 900, 750)

        self.items_data = []
        self.items_map = {}
        self.tile_widgets_map = {}
        self.connected_clients = []

        # Track selected item
        self.selected_item_id = None
        self.selected_tile_widget = None

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # --- Log Area ---
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setStyleSheet("font-family: monospace; font-size: 10px; background-color: #f0f0f0;")
        main_layout.addWidget(self.log_area, stretch=1)

        self.log_message("Application initialized.")
        self.load_items_from_config()

        # --- Control Panel ---
        control_panel = QHBoxLayout()
        add_item_button = QPushButton("Add New Item")
        add_item_button.clicked.connect(lambda: self.add_edit_item_dialog(None))
        control_panel.addWidget(add_item_button)

        self.edit_item_button = QPushButton("Edit Selected Item")
        self.edit_item_button.clicked.connect(self.edit_selected_item)
        self.edit_item_button.setEnabled(False) # Disable until an item is selected
        control_panel.addWidget(self.edit_item_button)

        self.delete_item_button = QPushButton("Delete Selected Item")
        self.delete_item_button.clicked.connect(self.delete_selected_item)
        self.delete_item_button.setEnabled(False) # Disable until an item is selected
        control_panel.addWidget(self.delete_item_button)

        main_layout.addLayout(control_panel)

        # --- Tile Display Area ---
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.tiles_container_widget = QWidget()
        self.tiles_layout = QGridLayout(self.tiles_container_widget)
        self.tiles_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.scroll_area.setWidget(self.tiles_container_widget)
        main_layout.addWidget(self.scroll_area, stretch=3)

        self.refresh_all_tiles()

        # --- Server Status Label ---
        self.server_status_label = QLabel("Server Status: Initializing...")
        main_layout.addWidget(self.server_status_label)
        
        self.start_server()

    def load_items_from_config(self):
        if os.path.exists(ITEMS_CONFIG_FILE):
            try:
                with open(ITEMS_CONFIG_FILE, 'r') as f:
                    self.items_data = json.load(f)
                self.items_map = {item['id']: item for item in self.items_data}
                self.log_message(f"Loaded {len(self.items_data)} items from {ITEMS_CONFIG_FILE}")
            except Exception as e:
                self.log_message(f"Error loading {ITEMS_CONFIG_FILE}: {e}. Starting with empty list.")
                self.items_data = []
                self.items_map = {}
        else:
            self.log_message(f"{ITEMS_CONFIG_FILE} not found. Creating default items.")
            self.items_data = [
                {"id": "apple", "name": "Red Apple", "image_source_path": "red", "description": "A crisp, juicy red apple."},
                {"id": "banana", "name": "Yellow Banana", "image_source_path": "yellow", "description": "A sweet, ripe banana."},
                {"id": "orange", "name": "Juicy Orange", "image_source_path": "orange", "description": "A tangy, vitamin C packed orange."},
            ]
            for item in self.items_data:
                item["image_file"] = ensure_image_exists(item["image_source_path"], item["id"])
            self.items_map = {item['id']: item for item in self.items_data}
            self.save_items_to_config()

    def save_items_to_config(self):
        try:
            with open(ITEMS_CONFIG_FILE, 'w') as f:
                json.dump(self.items_data, f, indent=2)
            self.log_message(f"Saved {len(self.items_data)} items to {ITEMS_CONFIG_FILE}")
        except Exception as e:
            self.log_message(f"Error saving to {ITEMS_CONFIG_FILE}: {e}")

    def refresh_all_tiles(self):
        # Clear selected item state before refreshing
        self.selected_item_id = None
        if self.selected_tile_widget:
            self.selected_tile_widget.set_selected(False)
            self.selected_tile_widget = None
        self.edit_item_button.setEnabled(False)
        self.delete_item_button.setEnabled(False)

        for i in reversed(range(self.tiles_layout.count())): 
            widget_to_remove = self.tiles_layout.itemAt(i).widget()
            self.tiles_layout.removeWidget(widget_to_remove)
            widget_to_remove.setParent(None)
            widget_to_remove.deleteLater()
        self.tile_widgets_map.clear()

        row, col = 0, 0
        max_cols = 4
        for item_data in self.items_data:
            final_image_file = item_data.get("image_file")
            if not final_image_file or not os.path.exists(os.path.join(IMAGE_DIR, final_image_file)):
                 self.log_message(f"Warning: Image file for '{item_data['id']}' missing or invalid. Attempting to regenerate.")
                 final_image_file = ensure_image_exists(item_data.get("image_source_path", "lightgray"), item_data["id"])
                 if not final_image_file:
                     final_image_file = "default_placeholder.png"
                     ensure_image_exists("lightgray", final_image_file.split('.')[0])

            item_data["image_file"] = final_image_file

            tile = TileWidget(item_data)
            tile.tile_clicked.connect(self.handle_tile_clicked) # CONNECT TILE CLICK SIGNAL
            self.tiles_layout.addWidget(tile, row, col)
            self.tile_widgets_map[item_data["id"]] = tile
            col += 1
            if col >= max_cols: col = 0; row += 1
        
        if hasattr(self, 'server_worker') and self.server_worker._is_running:
             self.broadcast_item_list_update()

    def handle_tile_clicked(self, item_id: str, tile_widget: QWidget):
        # Deselect previously selected tile
        if self.selected_tile_widget and self.selected_tile_widget != tile_widget:
            self.selected_tile_widget.set_selected(False)
        
        # Set new selection
        self.selected_item_id = item_id
        self.selected_tile_widget = tile_widget
        self.selected_tile_widget.set_selected(True)
        
        self.log_message(f"Selected item: {item_id}")
        self.edit_item_button.setEnabled(True)
        self.delete_item_button.setEnabled(True)


    def add_edit_item_dialog(self, item_to_edit=None):
        dialog = ItemDialog(self, item_data=item_to_edit)
        if dialog.exec_():
            data = dialog.get_data()
            item_id = data["id"]
            if not item_id or not data["name"]:
                QMessageBox.warning(self, "Input Error", "Item ID and Name cannot be empty.")
                return

            image_source = data["image_source_path"]
            generated_image_filename = ensure_image_exists(image_source, item_id)
            if not generated_image_filename:
                QMessageBox.warning(self, "Image Error", f"Could not process or find image: {image_source}. Using default placeholder.")
                generated_image_filename = ensure_image_exists("lightgray", item_id + "_fallback")

            new_item_data = {
                "id": item_id,
                "name": data["name"],
                "description": data["description"],
                "image_source_path": image_source,
                "image_file": generated_image_filename
            }

            if item_to_edit:
                # Update existing item
                for i, item in enumerate(self.items_data):
                    if item["id"] == item_id:
                        self.items_data[i] = new_item_data
                        break
            elif item_id in self.items_map:
                 QMessageBox.warning(self, "Input Error", f"Item ID '{item_id}' already exists.")
                 return
            else:
                self.items_data.append(new_item_data)
            
            self.items_map[item_id] = new_item_data
            self.save_items_to_config()
            self.refresh_all_tiles()
            self.log_message(f"Item '{item_id}' added/updated.")

    def edit_selected_item(self):
        if not self.selected_item_id:
            QMessageBox.warning(self, "No Item Selected", "Please select an item to edit by clicking its tile.")
            return

        item_to_edit = self.items_map.get(self.selected_item_id)
        if item_to_edit:
            self.add_edit_item_dialog(item_to_edit)
        else:
            # This case should ideally not happen if self.selected_item_id is kept consistent
            QMessageBox.critical(self, "Error", f"Selected item with ID '{self.selected_item_id}' not found in data. Please refresh or restart.")
            self.selected_item_id = None # Clear invalid selection
            self.selected_tile_widget = None


    def delete_selected_item(self):
        if not self.selected_item_id:
            QMessageBox.warning(self, "No Item Selected", "Please select an item to delete by clicking its tile.")
            return
        
        item_id_to_delete = self.selected_item_id
        if item_id_to_delete in self.items_map:
            reply = QMessageBox.question(self, 'Delete Item', 
                                         f"Are you sure you want to delete '{self.items_map[item_id_to_delete]['name']}' ({item_id_to_delete})?", 
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.items_data = [item for item in self.items_data if item["id"] != item_id_to_delete]
                del self.items_map[item_id_to_delete]
                self.save_items_to_config()
                self.refresh_all_tiles() # This will also clear selection
                self.log_message(f"Item '{item_id_to_delete}' deleted.")
        else:
            QMessageBox.critical(self, "Error", f"Selected item with ID '{item_id_to_delete}' not found in data. Please refresh or restart.")
            self.selected_item_id = None
            self.selected_tile_widget = None

    def start_server(self):
        if hasattr(self, 'server_thread') and self.server_thread.isRunning():
            self.log_message("Server already running.")
            return

        self.server_thread = QThread()
        self.server_worker = ServerWorker()
        self.server_worker.moveToThread(self.server_thread)

        self.server_worker.log_message_signal.connect(self.log_message)
        self.server_worker.order_received_signal.connect(self.handle_order_request)
        self.server_worker.client_connected_signal.connect(self.handle_new_client)
        self.server_worker.client_disconnected_signal.connect(self.handle_client_disconnect)
        
        self.server_thread.started.connect(self.server_worker.run)
        self.server_thread.finished.connect(self.server_worker.deleteLater)
        self.server_thread.finished.connect(self.server_thread.deleteLater)
        self.server_thread.finished.connect(lambda: self.server_status_label.setText("Server Status: Stopped"))

        self.server_thread.start()
        self.server_status_label.setText(f"Server Status: Running on {HOST}:{PORT}")
        self.log_message("Server starting thread...")

    def stop_server(self):
        if hasattr(self, 'server_worker') and self.server_worker._is_running:
            self.log_message("Stopping server...")
            self.server_worker.stop()
            
            for client_sock in list(self.connected_clients):
                try:
                    self.send_message_to_client(client_sock, "SERVER_SHUTDOWN", {})
                    time.sleep(0.1) 
                    client_sock.shutdown(socket.SHUT_RDWR)
                    client_sock.close()
                except Exception as e:
                    self.log_message(f"Error closing client socket during shutdown: {e}")
                if client_sock in self.connected_clients:
                    self.connected_clients.remove(client_sock)
            
            if hasattr(self, 'server_thread') and self.server_thread.isRunning():
                if not self.server_thread.wait(5000):
                    self.log_message("Warning: Server thread did not finish cleanly. Terminating...")
                    self.server_thread.terminate()
                    self.server_thread.wait()
            self.log_message("Server stopped.")
        else:
            self.log_message("Server not running or already stopped.")
    
    def send_message_to_client(self, client_socket, msg_type, payload):
        message = {"type": msg_type, "payload": payload}
        try:
            client_socket.sendall(json.dumps(message).encode('utf-8') + b'\n')
            print(f"DEBUG: Sent {msg_type} to {client_socket.getpeername()}: {str(message.get('payload', {}).get('items', '...'))[:50]}...")
        except (socket.error, BrokenPipeError, ConnectionResetError) as e:
            self.log_message(f"Error sending {msg_type} to client {client_socket.getpeername()}: {e}. Removing client.")
            self.handle_client_disconnect(client_socket)
        except Exception as e:
            self.log_message(f"Unexpected error sending to client {client_socket.getpeername()}: {e}")
            self.handle_client_disconnect(client_socket)

    def handle_new_client(self, client_socket):
        if client_socket not in self.connected_clients:
            self.connected_clients.append(client_socket)
            self.log_message(f"New client connected: {client_socket.getpeername()}. Sending item list.")
            client_item_list = [{"id": i["id"], "name": i["name"], "description": i["description"]} for i in self.items_data]
            self.send_message_to_client(client_socket, "AVAILABLE_ITEMS", {"items": client_item_list})

    def handle_client_disconnect(self, client_socket):
        if client_socket in self.connected_clients:
            try:
                peername = client_socket.getpeername()
                self.log_message(f"Client {peername} disconnected or removed.")
            except OSError:
                 self.log_message(f"A client disconnected (socket info unavailable).")
            
            self.connected_clients.remove(client_socket)
            try:
                client_socket.close()
            except: pass
        else:
            self.log_message("Received disconnect for an unknown or already removed client.")

    def broadcast_item_list_update(self):
        self.log_message("Broadcasting item list update to all clients.")
        client_item_list = [{"id": i["id"], "name": i["name"], "description": i["description"]} for i in self.items_data]
        for client_sock in list(self.connected_clients):
            try:
                self.send_message_to_client(client_sock, "AVAILABLE_ITEMS_UPDATE", {"items": client_item_list})
            except Exception as e:
                pass

    def log_message(self, message):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")

    def handle_order_request(self, order_data_from_client):
        client_address = order_data_from_client.pop("_client_address", "Unknown Client")
        client_socket_for_ack = order_data_from_client.pop("_client_socket", None)

        self.log_message(f"Processing order from {client_address}: {order_data_from_client}")
        item_id = order_data_from_client.get("item_id")
        order_id = order_data_from_client.get("order_id")

        if item_id in self.items_map:
            item_info = self.items_map[item_id]
            processed_order = {
                **order_data_from_client,
                "item_name": item_info["name"],
                "receiver_hostname": RECEIVER_HOSTNAME,
                "received_timestamp_utc": datetime.datetime.now(timezone.utc).isoformat(timespec='seconds'),
                "status": "Processed"
            }
            self.log_message(f"Processed Order: {json.dumps(processed_order, indent=2)}")
            
            if item_id in self.tile_widgets_map:
                self.tile_widgets_map[item_id].indicate_order() # Indicate order on tile
            
            if client_socket_for_ack and client_socket_for_ack in self.connected_clients:
                self.send_message_to_client(client_socket_for_ack, "ORDER_ACK", 
                                            {"order_id": order_id, "item_id": item_id, "status": "Processed", "receiver_timestamp": processed_order["received_timestamp_utc"]})
        else:
            self.log_message(f"Error: Item ID '{item_id}' not found in order from {client_address}. Order rejected.")
            if client_socket_for_ack and client_socket_for_ack in self.connected_clients:
                self.send_message_to_client(client_socket_for_ack, "ORDER_NACK", 
                                            {"order_id": order_id, "item_id": item_id, "reason": "Item not found"})

    def closeEvent(self, event):
        self.log_message("Application closing. Shutting down server...")
        self.stop_server()
        event.accept()

if __name__ == "__main__":
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)

    app = QApplication(sys.argv)
    window = ItemAuthorityApp()
    window.show()
    sys.exit(app.exec_())