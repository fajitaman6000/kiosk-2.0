# Server/data_manager.py
import os
import json
import shutil
import hashlib
from PyQt5.QtGui import QImage, QColor, QPainter, QFont
from PyQt5.QtCore import Qt
import config

# --- Helper to calculate file hash for caching ---
def get_file_hash(file_path):
    """Calculates the MD5 hash of a file."""
    if not os.path.exists(file_path):
        return None
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

# --- Helper to create/copy images ---
def ensure_image_exists(source_path, item_id, size=(150, 150)):
    if not os.path.exists(config.IMAGE_DIR):
        os.makedirs(config.IMAGE_DIR)

    _, ext = os.path.splitext(source_path)
    if not ext: ext = ".png"
    target_filename = f"{item_id.replace(' ', '_').lower()}{ext}"
    target_path = os.path.join(config.IMAGE_DIR, target_filename)

    # Simplified logic: Generate if color, copy if path, otherwise placeholder.
    img_generated = False
    if source_path.startswith("#") or source_path.lower() in [c.lower() for c in QColor.colorNames()]:
        color = QColor(source_path)
        if not color.isValid(): color = QColor("lightgray")
        text = f"{item_id}\n(Color Fill)"
        img_generated = True
    elif os.path.exists(source_path):
        if os.path.abspath(source_path) != os.path.abspath(target_path):
            try:
                shutil.copy(source_path, target_path)
            except shutil.SameFileError:
                pass # Already in place
            except Exception as e:
                print(f"Error copying image {source_path}: {e}")
                return None
    elif not os.path.exists(target_path):
        color = QColor("lightgray")
        text = f"{item_id}\n(No Image)"
        img_generated = True

    if img_generated:
        img = QImage(size[0], size[1], QImage.Format.Format_RGB32)
        img.fill(color)
        painter = QPainter(img)
        painter.setFont(QFont("Arial", 10))
        painter.setPen(Qt.black)
        painter.drawText(img.rect(), Qt.AlignCenter, text)
        painter.end()
        img.save(target_path)

    return target_filename if os.path.exists(target_path) else None

# --- Main Data Functions ---
def load_items_from_config():
    """Loads item data from the JSON config file."""
    if os.path.exists(config.ITEMS_CONFIG_FILE):
        try:
            with open(config.ITEMS_CONFIG_FILE, 'r') as f:
                items_data = json.load(f)
            # Add hash to each item for client caching
            for item in items_data:
                if item.get("image_file"):
                    image_path = os.path.join(config.IMAGE_DIR, item["image_file"])
                    item["image_hash"] = get_file_hash(image_path)
            return items_data
        except Exception as e:
            print(f"Error loading {config.ITEMS_CONFIG_FILE}: {e}")
            return []
    else:
        print(f"{config.ITEMS_CONFIG_FILE} not found. Creating default items.")
        default_items = [
            {"id": "1", "name": "Red", "image_source_path": "red", "description": "A red item description", "price": 1.50},
            {"id": "2", "name": "Yellow", "image_source_path": "yellow", "description": "A yellow item description", "price": 0.75},
            {"id": "3", "name": "Orange", "image_source_path": "orange", "description": "An orange item description", "price": 1.25},
        ]
        for item in default_items:
            item["image_file"] = ensure_image_exists(item["image_source_path"], item["id"])
            if item.get("image_file"):
                image_path = os.path.join(config.IMAGE_DIR, item["image_file"])
                item["image_hash"] = get_file_hash(image_path)
        save_items_to_config(default_items)
        return default_items

def save_items_to_config(items_data):
    """Saves the list of item data to the JSON config file atomically."""
    items_to_save = []
    for item in items_data:
        item_copy = item.copy()
        item_copy.pop('image_hash', None)
        items_to_save.append(item_copy)

    temp_file_path = config.ITEMS_CONFIG_FILE + ".tmp"
    try:
        with open(temp_file_path, 'w') as f:
            json.dump(items_to_save, f, indent=4)
        # If write is successful, atomically rename the temp file to the final file
        os.replace(temp_file_path, config.ITEMS_CONFIG_FILE)
    except Exception as e:
        print(f"Error saving to {config.ITEMS_CONFIG_FILE}: {e}")
    finally:
        # Ensure the temp file is cleaned up on error
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)