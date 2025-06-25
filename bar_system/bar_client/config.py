# Client/config.py
import os
import socket

# --- General ---
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
CLIENT_HOSTNAME = socket.gethostname()

# --- Network ---
# CHANGE THIS to the IP address or hostname of the server computer
# SERVER_HOST = 'localhost' 
SERVER_PORT = 50888 # Must match server's port

# --- Cache ---
CACHE_DIR_NAME = "client_cache"
IMAGE_CACHE_DIR_NAME = "images"
CACHE_DIR = os.path.join(APP_ROOT, CACHE_DIR_NAME)
IMAGE_CACHE_DIR = os.path.join(CACHE_DIR, IMAGE_CACHE_DIR_NAME)
CACHE_MANIFEST_FILE = os.path.join(CACHE_DIR, "cache_manifest.json")