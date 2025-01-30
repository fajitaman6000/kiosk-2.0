# file_sync_config.py

# --- Admin Side ---
ADMIN_SYNC_DIR = "sync_directory"  # Directory containing files to sync on admin side. Create this folder in the same location as these files.
ADMIN_SERVER_PORT = 5000          # Port for the admin's HTTP server

# --- Shared ---
BROADCAST_MESSAGE_TYPE = 'kiosk_announce'   # The message type the admin will listen for.
SYNC_MESSAGE_TYPE = 'sync_files'       # Message type that triggers a sync on the kiosk.
RESET_MESSAGE_TYPE = 'reset_kiosk'   # Message type that triggers a reset on the kiosk.