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
        self.sync_status = {}  # Track sync status for each kiosk

    def start(self):
        """Start the sync manager thread."""
        self.sync_thread = Thread(target=self._background_sync_handler, daemon=True)
        self.sync_thread.start()

    def stop(self):
        """Stop the sync manager thread."""
        self.running = False
        if self.sync_thread and self.sync_thread.is_alive():
            self.sync_thread.join()

    def _get_kiosk_ips(self):
        """Get kiosk IPs from interface builder and last messages."""
        self.kiosk_ips = {}
        
        # First check connected kiosks from interface builder
        for computer_name, data in self.app.interface_builder.connected_kiosks.items():
            if data.get('ip'):
                self.kiosk_ips[computer_name] = data.get('ip')
            # If no IP in connected_kiosks data, check last_message from network handler
            elif hasattr(self.app, 'network_handler') and computer_name in self.app.network_handler.last_message:
                msg = self.app.network_handler.last_message[computer_name]
                if msg.get('ip'):
                    self.kiosk_ips[computer_name] = msg.get('ip')
                # If still no IP but we have the sender's address
                elif msg.get('_sender_addr'):
                    self.kiosk_ips[computer_name] = msg['_sender_addr'][0]  # Use the sender's IP

        if not self.kiosk_ips:
            print("[admin_sync_manager] Warning: No kiosk IPs found, but kiosks are connected")
            print("[admin_sync_manager] Connected kiosks:", list(self.app.interface_builder.connected_kiosks.keys()))
            # If we have connected kiosks but no IPs, we'll proceed anyway
            # The broadcast message will reach all kiosks on the network
            return bool(self.app.interface_builder.connected_kiosks)
            
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
        print(f"[admin_sync_manager] Found {len(files)} files")
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
        """Send a sync request to the server with only file hashes."""
        if not files:
            print("[admin_sync_manager] No file changes to synchronize")
            return False
        try:
            print(f"[admin_sync_manager] Sending sync request with {len(files)} file hashes")
            sync_url = f"http://127.0.0.1:{ADMIN_SERVER_PORT}/sync_info"
            
            # Send only the file hashes
            response = requests.post(sync_url, json={'files': files}, timeout=30)
            response.raise_for_status()
            print(f"[admin_sync_manager] Sync request successful: {response.text}")
            return True
        except requests.exceptions.RequestException as e:
            print(f"[admin_sync_manager] Sync request failed: {e}")
            return False
        except Exception as e:
            print(f"[admin_sync_manager] An error occurred during sync: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _send_message_to_kiosk(self, computer_name):
        """Send a sync message to a specific kiosk."""
        if computer_name not in self.kiosk_ips:
            print(f"[admin_sync_manager] Warning: No IP found for {computer_name}")
            return False

        message = {
            'type': SYNC_MESSAGE_TYPE,
            'computer_name': computer_name,  # Target specific kiosk
            'admin_ip': self.app.network_handler.socket.getsockname()[0],
            'sync_id': str(time.time())  # Add unique sync ID
        }
        self.app.network_handler.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))
        print(f"[admin_sync_manager] Message sent to kiosk: {computer_name}")
        return True

    def _send_message_to_kiosks(self, target_kiosk=None):
        """Send sync messages to kiosks. If target_kiosk is specified, only send to that kiosk."""
        print("[admin_sync_manager] Sending update messages to kiosks...")
        
        if not self._get_kiosk_ips():
            print("[admin_sync_manager] No kiosks found")
            return False

        if target_kiosk:
            return self._send_message_to_kiosk(target_kiosk)
        
        # If no target specified, send to all kiosks
        success = False
        for computer_name in self.kiosk_ips.keys():
            if self._send_message_to_kiosk(computer_name):
                success = True
        return success

    def handle_sync_button(self):
        """Handle the button click to start the sync process."""
        if not self.sync_thread or not self.sync_thread.is_alive():
            self.start()
        
        if not self._get_kiosk_ips():
            print("[admin_sync_manager] No kiosks found")
            return
        
        files_to_sync = self._scan_sync_directory()
        
        if not files_to_sync:
            print("[admin_sync_manager] No local files to sync")
            return
            
        if not self._send_sync_request(files_to_sync):
            print("[admin_sync_manager] Failed to send file hashes to server")
            return

        # Initialize sync status for all connected kiosks, not just ones with IPs
        self.sync_status = {name: {'sent': time.time(), 'confirmed': False} 
                           for name in self.app.interface_builder.connected_kiosks.keys()}
        self._send_message_to_kiosks()

    def handle_sync_confirmation(self, computer_name, sync_id):
        """Handle sync confirmation from a kiosk."""
        if computer_name in self.sync_status:
            self.sync_status[computer_name]['confirmed'] = True
            print(f"[admin_sync_manager] Sync confirmed for kiosk: {computer_name}")

    def _background_sync_handler(self):
        """Monitor sync status and resend if needed."""
        while self.running:
            current_time = time.time()
            for computer_name, status in self.sync_status.items():
                if not status['confirmed'] and (current_time - status['sent']) > 10:  # 10 second timeout
                    print(f"[admin_sync_manager] Resending sync message to {computer_name}")
                    status['sent'] = current_time
                    self._send_message_to_kiosks(target_kiosk=computer_name)  # Only send to this specific kiosk
            time.sleep(1)