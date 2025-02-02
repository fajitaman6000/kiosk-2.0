# admin_sync_manager.py
import os
import json
import requests
import socket
import time
import hashlib
from threading import Thread
from file_sync_config import ADMIN_SYNC_DIR, ADMIN_SERVER_PORT, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE

class AdminSyncManager:
    def __init__(self, app):
        self.app = app
        self.kiosk_ips = {}  # Store kiosk computer_name -> IP
        self.running = True
        self.sync_thread = None

    def start(self):
        """Start the sync manager thread."""
        self.sync_thread = Thread(target=self._background_sync_handler, daemon=True)
        self.sync_thread.start()

    def stop(self):
        """Stop the sync manager thread."""
        self.running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join()

    def _discover_kiosks(self):
        """Discover kiosks on the network using the existing broadcast."""
        print("[admin_sync_manager] Discovering Kiosks...")
        self.kiosk_ips = {}  # Clear existing IPs
        start_time = time.time()
        max_retries = 3 # Try 3 times
        while time.time() - start_time < 5 and max_retries > 0:
            if not self.running:
                return False
            for computer_name, data in self.app.interface_builder.connected_kiosks.items():
                if data.get('ip'):
                    self.kiosk_ips[computer_name] = data.get('ip')
            if self.kiosk_ips:
                break # Found at least 1 device
            time.sleep(0.5) # Sleep for a 0.5 seconds
            max_retries -=1
        
        print(f"[admin_sync_manager] Kiosks Discovered: {self.kiosk_ips}")
        return True

    def _calculate_file_hash(self, file_path):
        """Calculate the SHA256 hash of a file."""
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(4096)
                    if not chunk:
                        break
                    hasher.update(chunk)
            return hasher.hexdigest()
        except Exception as e:
            print(f"[admin_sync_manager] Error calculating hash for {file_path}: {e}")
            return None

    def _scan_sync_directory(self):
        """Scan the admin's sync directory and calculate file hashes."""
        print("[admin_sync_manager] Scanning sync directory...")
        files = {}
        for root, _, filenames in os.walk(ADMIN_SYNC_DIR):
            for filename in filenames:
                file_path = os.path.relpath(os.path.join(root, filename), ADMIN_SYNC_DIR)
                if not file_path.endswith(".py") and not "__pycache__" in file_path:
                    files[file_path] = self._calculate_file_hash(os.path.join(ADMIN_SYNC_DIR, file_path))
        print(f"[admin_sync_manager] File hashes: {files}")
        return files
        
    def _encode_file(self, path):
        """Encode a file's content to a string using latin1 to avoid encoding errors."""
        try:
            with open(path, 'rb') as file:
                 return file.read().decode('latin1')
        except Exception as e:
             print(f"[admin_sync_manager] Error encoding file: {e}")
             import traceback
             traceback.print_exc()
             return None
    def _send_sync_request(self, files):
        """Send a sync request to the server."""
        if not files:
          print("[admin_sync_manager] No file changes to synchronize")
          return False
        try:
            print(f"[admin_sync_manager] Sending sync request with {len(files)} files")
            sync_url = f"http://127.0.0.1:{ADMIN_SERVER_PORT}/sync" # Changed this line
            files_to_send = {}
            for path, hash in files.items():
                 files_to_send[path] = {'type': 'upload',
                                        'data': self._encode_file(os.path.join(ADMIN_SYNC_DIR, path)) }
            response = requests.post(sync_url, json={'files': files_to_send}, timeout=60)
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
            print(f"[admin_sync_manager] Sync request successful: {response.text}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[admin_sync_manager] Sync request failed: {e}")
            return False
        except Exception as e:
            print(f"[admin_sync_manager] An error occured during sync: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _send_message_to_kiosks(self):
        """Send a message to kiosks to initiate update."""
        print("[admin_sync_manager] Sending update messages to kiosks...")
        # Get the local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't need to be reachable, just used to get local IP
            s.connect(('10.255.255.255', 1))
            local_ip = s.getsockname()[0]
        except Exception:
            local_ip = '127.0.0.1'
        finally:
            s.close()

        if local_ip == '127.0.0.1':
            print("[admin_sync_manager] Warning: Could not determine non-localhost IP address")
            return

        message = {
            'type': SYNC_MESSAGE_TYPE,
            'computer_name': "all",
            'admin_ip': local_ip
        }
        self.app.network_handler.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))
        print(f"[admin_sync_manager] Message sent to all devices with admin IP: {local_ip}")

    def _background_sync_handler(self):
        """This is now an empty thread. It does nothing"""
        while self.running:
           time.sleep(1)

    def handle_sync_button(self):
        """Handle the button click to start the sync process."""
        if not self.sync_thread or not self.sync_thread.is_alive():
            self.start()
        
        if not self._discover_kiosks():
            print("[admin_sync_manager] No kiosks found")
            return
        
        files_to_sync = self._scan_sync_directory()
        
        if not files_to_sync:
            print("[admin_sync_manager] No local files to sync")
            return
            
        if not self._send_sync_request(files_to_sync):
            print("[admin_sync_manager] Sync failed to server")
            return

        self._send_message_to_kiosks()