# bar_server/app_widgets.py
import os  # --- NEW --- Direct import for clarity
from PyQt5.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QHBoxLayout, QLineEdit, QFileDialog,
    QDialog, QFormLayout, QPushButton, QTextEdit, QDoubleSpinBox
)
from PyQt5.QtGui import QPixmap
from PyQt5.QtCore import Qt, pyqtSignal

import config
import data_manager

class TileWidget(QFrame):
    tile_clicked = pyqtSignal(str, QFrame)
    tile_double_clicked = pyqtSignal()


    def __init__(self, item_data):
        super().__init__()
        self.item_id = item_data["id"]

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setFixedWidth(200)
        self.setMinimumHeight(280)
        self.setCursor(Qt.PointingHandCursor)

        self._original_stylesheet = self.styleSheet()
        self.set_selected(False)

        layout = QVBoxLayout(self)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignCenter)
        
        # --- MODIFIED BLOCK START ---
        image_full_path = os.path.join(config.IMAGE_DIR, item_data.get("image_file", ""))
        
        if os.path.exists(image_full_path):
            pixmap = QPixmap(image_full_path)
            image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        else:
            # Fallback to a standard placeholder image, just like the client
            placeholder_path = os.path.join(config.IMAGE_DIR, "_placeholder.png")
            pixmap = QPixmap(placeholder_path)
            if not pixmap.isNull():
                image_label.setPixmap(pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                # If even the placeholder is missing, show text.
                image_label.setText("No Image\n(placeholder missing)")
        # --- MODIFIED BLOCK END ---

        layout.addWidget(image_label)

        price = item_data.get("price", 0.0)
        name_label = QLabel(f"{item_data['name']}\n(${price:.2f})")
        name_label.setAlignment(Qt.AlignCenter)
        name_label.setStyleSheet("font-weight: bold;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)

        desc = item_data.get("description", "No description.")
        description_label = QLabel(desc)
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignCenter)
        description_label.setStyleSheet("font-size: 10px; color: #555;")
        layout.addWidget(description_label)

        layout.addStretch()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.tile_clicked.emit(self.item_id, self)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.tile_double_clicked.emit()
        super().mouseDoubleClickEvent(event)

    def set_selected(self, is_selected):
        if is_selected:
            self.setStyleSheet(f"border: 3px solid #0078d7;") # A nicer blue
        else:
            self.setStyleSheet(self._original_stylesheet)

    def indicate_order(self):
        original_style = self.styleSheet()
        self.setStyleSheet(f"background-color: #dff0d8; border: 3px solid #3c763d;")
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(750, lambda: self.setStyleSheet(original_style))

# ... ItemDialog class remains unchanged ...
class ItemDialog(QDialog):
    def __init__(self, parent=None, item_data=None):
        super().__init__(parent)
        self.setWindowTitle("Add New Item" if item_data is None else "Edit Item")
        self.item_data = item_data if item_data else {}

        layout = QFormLayout(self)

        self.id_edit = QLineEdit(self.item_data.get("id", ""))
        if item_data: self.id_edit.setReadOnly(True)
        layout.addRow("Item ID:", self.id_edit)

        self.name_edit = QLineEdit(self.item_data.get("name", ""))
        layout.addRow("Name:", self.name_edit)
        
        self.price_edit = QDoubleSpinBox()
        self.price_edit.setDecimals(2)
        self.price_edit.setMinimum(0)
        self.price_edit.setMaximum(9999.99)
        self.price_edit.setPrefix("$ ")
        self.price_edit.setValue(self.item_data.get("price", 0.0))
        layout.addRow("Price:", self.price_edit)

        self.desc_edit = QTextEdit(self.item_data.get("description", ""))
        layout.addRow("Description:", self.desc_edit)

        self.image_path_edit = QLineEdit(self.item_data.get("image_source_path", ""))
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.browse_image)
        image_layout = QHBoxLayout()
        image_layout.addWidget(self.image_path_edit)
        image_layout.addWidget(browse_button)
        layout.addRow("Image File/Color:", image_layout)

        ok_button = QPushButton("OK")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(ok_button)
        buttons.addWidget(cancel_button)
        layout.addRow(buttons)

    def browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image", "", "Image Files (*.png *.jpg)")
        if file_path: self.image_path_edit.setText(file_path)

    def get_data(self):
        return {
            "id": self.id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "price": self.price_edit.value(),
            "description": self.desc_edit.toPlainText().strip(),
            "image_source_path": self.image_path_edit.text().strip()
        }