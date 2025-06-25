# Server/config.py
import socket
import os

# --- General ---
# This ensures paths are relative to this file's location, fixing the file path issue.
APP_ROOT = os.path.dirname(os.path.abspath(__file__))

# --- Network ---
HOST = '0.0.0.0'  # Listen on all available network interfaces
PORT = 50888
SERVER_HOSTNAME = socket.gethostname()

# --- Files & Directories ---
IMAGE_DIR_NAME = "images"
IMAGE_DIR = os.path.join(APP_ROOT, IMAGE_DIR_NAME)
ITEMS_CONFIG_FILE = os.path.join(APP_ROOT, "items_config.json")
ORDER_LOG_FILE = os.path.join(APP_ROOT, "order_history.json")

# --- UI ---
MAX_TILE_COLUMNS = 4