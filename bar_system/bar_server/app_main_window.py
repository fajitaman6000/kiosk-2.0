# bar_server/app_main_window.py
import time
import os
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QScrollArea, QGridLayout,
    QTextEdit, QPushButton, QHBoxLayout, QMessageBox, QListWidget, QListWidgetItem,
    QDialog, QToolBar, QAction
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer, pyqtSignal, QSize
from PyQt5.QtGui import QIcon

import config
import data_manager
from app_widgets import TileWidget, ItemDialog
from server_logic import ServerLogic

# --- WIDGET for a collapsible log/status area ---
class CollapsibleLogWidget(QWidget):
    """A widget that can be collapsed to hide the detailed server log and status."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)
        
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 5, 0, 0)
        main_layout.setSpacing(5)
        self.setLayout(main_layout)

        # This button will control the visibility of the content area
        self.toggle_button = QPushButton("Show Server Log & Status")
        self.toggle_button.setCheckable(True)
        # --- MODIFIED FOR TOUCH --- Made button larger and more distinct
        self.toggle_button.setStyleSheet("""
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                text-align: left;
                padding: 10px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background-color: #f0f0f0;
            }
            QPushButton:checked {
                background-color: #e0e0e0;
            }
        """)
        
        # A separate widget to hold the content that will be hidden/shown
        self.content_widget = QWidget()
        content_layout = QVBoxLayout(self.content_widget)
        content_layout.setContentsMargins(5, 0, 5, 0)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMaximumHeight(150) # Keep the log area compact
        
        self.server_status_label = QLabel("Server Status: Initializing...")
        self.server_status_label.setStyleSheet("font-size: 14px;") # Make status slightly larger

        content_layout.addWidget(QLabel("<h3>Server Log</h3>"))
        content_layout.addWidget(self.log_area)
        content_layout.addWidget(self.server_status_label)
        
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_widget)

        # Connect the button's toggled signal to show/hide the content
        self.toggle_button.toggled.connect(self.on_toggled)
        
        # Start in a collapsed state
        self.toggle_button.setChecked(False)
        self.content_widget.setVisible(False)

    def on_toggled(self, checked):
        """Updates button text and content visibility."""
        self.content_widget.setVisible(checked)
        if checked:
            self.toggle_button.setText("Hide Server Log & Status")
        else:
            self.toggle_button.setText("Show Server Log & Status")

    @pyqtSlot(str)
    def log_message(self, message):
        """Public slot to append a message to the log area."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        print(f"SERVER LOG: [{timestamp}] {message}") # Also print to console for debugging

    @pyqtSlot(str)
    def set_status(self, text):
        """Public slot to update the server status label."""
        self.server_status_label.setText(f"Server Status: {text}")


# --- DIALOG to handle all item management ---
class ItemManagementDialog(QDialog):
    """
    A self-contained dialog for managing menu items. It handles its own
    data loading, UI, and saving, then signals the main window upon changes.
    """
    # Signal to notify the main window that data has changed and clients need an update.
    items_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Menu Items")
        self.setMinimumSize(800, 600)
        self.setModal(True) # Block the main window while this is open

        # Internal state for this dialog
        self.items_data = []
        self.items_map = {}
        self.tile_widgets_map = {}
        self.selected_item_id = None
        
        self._setup_ui()
        self.load_and_display_items()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Control panel for add/edit/delete actions
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
        control_panel.addStretch()
        layout.addLayout(control_panel)

        # Scroll area for item tiles
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        tiles_container = QWidget()
        self.tiles_layout = QGridLayout(tiles_container)
        self.tiles_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll_area.setWidget(tiles_container)
        layout.addWidget(scroll_area, stretch=1)

        # Dialog buttons at the bottom
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def load_and_display_items(self):
        self.items_data = data_manager.load_items_from_config()
        self.items_map = {item['id']: item for item in self.items_data}
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
            tile.tile_double_clicked.connect(self.edit_selected_item)
            self.tiles_layout.addWidget(tile, row, col)
            self.tile_widgets_map[item_data["id"]] = tile
            col = (col + 1) % config.MAX_TILE_COLUMNS
            if col == 0: row += 1

    def handle_tile_clicked(self, item_id, tile_widget):
        if self.selected_item_id and self.selected_item_id in self.tile_widgets_map:
            self.tile_widgets_map[self.selected_item_id].set_selected(False)
        self.selected_item_id = item_id
        tile_widget.set_selected(True)
        self.edit_btn.setEnabled(True)
        self.delete_btn.setEnabled(True)

    def add_item(self):
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
            data_manager.save_items_to_config(self.items_data)
            self.load_and_display_items() # Reload to get correct hashes and refresh UI
            self.items_changed.emit() # Notify main window

    def edit_selected_item(self):
        if not self.selected_item_id: return
        item_to_edit = self.items_map.get(self.selected_item_id)
        dialog = ItemDialog(self, item_to_edit)
        if dialog.exec_():
            data = dialog.get_data()
            data["image_file"] = data_manager.ensure_image_exists(data["image_source_path"], data["id"])
            for i, item in enumerate(self.items_data):
                if item["id"] == self.selected_item_id: self.items_data[i] = data; break
            data_manager.save_items_to_config(self.items_data)
            self.load_and_display_items()
            self.items_changed.emit()
            
    def delete_selected_item(self):
        if not self.selected_item_id: return
        item_name = self.items_map[self.selected_item_id]['name']
        reply = QMessageBox.question(self, 'Delete Item', f"Delete '{item_name}'?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.items_data = [item for item in self.items_data if item["id"] != self.selected_item_id]
            data_manager.save_items_to_config(self.items_data)
            self.load_and_display_items()
            self.items_changed.emit()

# --- REFACTORED MAIN WINDOW (NOW A 'VIEW') ---
class BarManagerWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Room Order Manager")
        self.setGeometry(100, 100, 800, 700)

        icon_path = os.path.join(config.APP_ROOT, 'icon_bar.ico')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        # The logic handler now manages all backend operations
        self.server_logic = ServerLogic(self)

        self._setup_ui()
        self._connect_signals()

        # The UI simply tells the logic handler to start its operations
        self.server_logic.start()
        # Initialize the order list on startup
        self.refresh_order_list()

    def _setup_ui(self):
        main_widget = QWidget()
        # --- MODIFIED --- Give the widget an object name for specific styling
        main_widget.setObjectName("mainContentWidget")
        # --- MODIFIED --- Crucial step: tell the widget to paint its background
        main_widget.setAutoFillBackground(True)
        self.setCentralWidget(main_widget)
        
        main_layout = QVBoxLayout(main_widget)

        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        toolbar.setMovable(False) 
        toolbar.setIconSize(QSize(48, 48)) 
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        toolbar.setStyleSheet("""
            QToolBar {
                spacing: 10px; padding: 8px; border: none;
            }
            QToolButton {
                font-size: 18px; font-weight: bold; padding: 10px; border-radius: 5px;
            }
            QToolButton:hover { background-color: #e0e0e0; }
        """)

        settings_icon_path = os.path.join(config.APP_ROOT, 'app_icons', 'item_config_settings.png')
        settings_icon = QIcon.fromTheme("preferences-system", QIcon(settings_icon_path)) 
        manage_items_action = QAction(settings_icon, "Manage Menu Items", self)
        manage_items_action.triggered.connect(self.open_item_management_dialog)
        toolbar.addAction(manage_items_action)

        main_layout.addWidget(QLabel("<h2>Pending Orders</h2>"))
        self.pending_orders_list = QListWidget()
        self.pending_orders_list.setStyleSheet("font-size: 20px; padding: 5px;")
        main_layout.addWidget(self.pending_orders_list, stretch=1)
        
        complete_button = QPushButton("Complete Selected Order")
        complete_button.setStyleSheet("""
            QPushButton {
                font-size: 22px; font-weight: bold; padding: 20px;
                background-color: #28a745; color: white;
                border: none; border-radius: 5px;
            }
            QPushButton:hover { background-color: #218838; }
            QPushButton:pressed { background-color: #1e7e34; }
        """)
        complete_button.clicked.connect(self.complete_selected_order)
        main_layout.addWidget(complete_button)
        
        main_layout.addSpacing(10)
        
        self.log_widget = CollapsibleLogWidget(self)
        main_layout.addWidget(self.log_widget)

    def _connect_signals(self):
        """Connect signals from the logic handler to UI update slots."""
        self.server_logic.log_message.connect(self.log_widget.log_message)
        self.server_logic.server_status_update.connect(self.log_widget.set_status)
        self.server_logic.order_list_updated.connect(self.refresh_order_list)
        self.server_logic.ui_notification.connect(self.flash_main_window)

    def open_item_management_dialog(self):
        """Opens the modal dialog for managing items."""
        self.log_widget.log_message("Opening item management dialog...")
        dialog = ItemManagementDialog(self)
        dialog.items_changed.connect(self.server_logic.on_items_changed)
        dialog.exec_()
        self.log_widget.log_message("Item management dialog closed.")

    @pyqtSlot()
    def refresh_order_list(self):
        """Refreshes the pending orders list by querying the logic handler."""
        self.pending_orders_list.clear()
        for order in self.server_logic.order_manager.get_pending_orders():
            quantity = order.get("sender_stats", {}).get("quantity", 1)
            customer = order.get("sender_stats", {}).get("customer_name", "N/A")
            text = f"[{quantity}x] {order['item_name']} for {customer} (from: {order['sender_hostname']}) (ID: ...{order['order_id'][-12:]})"
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, order['order_id'])
            self.pending_orders_list.addItem(item)
    
    @pyqtSlot()
    def complete_selected_order(self):
        """Handles the 'Complete' button click by delegating to the logic handler."""
        selected_item = self.pending_orders_list.currentItem()
        if not selected_item:
            QMessageBox.warning(self, "No Order Selected", "Please select an order from the list to complete.")
            return
        order_id = selected_item.data(Qt.UserRole)
        self.server_logic.order_manager.complete_order(order_id)
        
    @pyqtSlot()
    def flash_main_window(self):
        """Flashes the entire window background to provide a clear visual cue for new orders."""
        main_widget = self.centralWidget()
        if not main_widget: return

        original_style = main_widget.styleSheet()
        
        # --- MODIFIED --- Use the specific object name for a reliable style change
        flash_style_addon = "#mainContentWidget { background-color: #fff3cd; }"

        def apply_flash():
            main_widget.setStyleSheet(original_style + flash_style_addon)
        
        def revert_style():
            main_widget.setStyleSheet(original_style)

        # Create a blinking effect: on, off, on, off
        apply_flash()
        QTimer.singleShot(250, revert_style)
        QTimer.singleShot(500, apply_flash)
        QTimer.singleShot(750, revert_style)

    def closeEvent(self, event):
        """Ensures the server logic is stopped cleanly on application exit."""
        self.server_logic.stop()
        event.accept()