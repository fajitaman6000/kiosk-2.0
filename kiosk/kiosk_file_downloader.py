# kiosk_file_downloader.py
import time
import requests
import os
from threading import Thread
import hashlib
import urllib.parse
import socket
from file_sync_config import ADMIN_SERVER_PORT #, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE

class KioskFileDownloader:
    def __init__(self, kiosk_app, admin_ip=None):
        self.kiosk_app = kiosk_app
        self.running = True
        self.download_thread = None
        self.admin_ip = admin_ip or "192.168.0.110"  # Fallback only if no IP provided
        self.kiosk_id = socket.gethostname()  # Use hostname as kiosk ID
        self.is_syncing = False
        self.sync_requested = False  # New flag to control sync

    def start(self):
        """Start the file downloader thread."""
        self.download_thread = Thread(target=self._background_download_handler, daemon=True)
        self.download_thread.start()

    def stop(self):
        """Stop the file downloader thread."""
        self.running = False
        if self.download_thread and self.download_thread.is_alive():
            self.download_thread.join()

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
            print(f"[kiosk_file_downloader] Error calculating hash for {file_path}: {e}")
            return None

    def _check_sync_status(self):
        """Check if it's our turn to sync."""
        try:
            url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/sync_status"
            response = requests.get(url, params={'kiosk_id': self.kiosk_id}, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"[kiosk_file_downloader] Error checking sync status: {e}")
            return None

    def _request_sync_permission(self):
        """Request to be added to the sync queue."""
        try:
            url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/request_sync"
            response = requests.post(url, json={'kiosk_id': self.kiosk_id}, timeout=10)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"[kiosk_file_downloader] Error requesting sync permission: {e}")
            return False

    def _finish_sync(self):
        """Notify server that sync is complete."""
        try:
            url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/finish_sync"
            response = requests.post(url, json={'kiosk_id': self.kiosk_id}, timeout=10)
            response.raise_for_status()
            self.is_syncing = False
            return True
        except Exception as e:
            print(f"[kiosk_file_downloader] Error finishing sync: {e}")
            return False

    def _request_files(self, file_list):
        """Request specific files from server."""
        try:
            remaining_files = file_list
            all_received_files = {}
            
            while remaining_files:
                url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/request_files"
                response = requests.post(url, json={
                    'kiosk_id': self.kiosk_id,
                    'files': remaining_files
                }, timeout=30)  # Longer timeout for file transfer
                response.raise_for_status()
                
                data = response.json()
                if 'error' in data:
                    print(f"[kiosk_file_downloader] Server error: {data['error']}")
                    return None
                    
                # Process received files
                for file_path, file_info in data['files'].items():
                    all_received_files[file_path] = file_info['data']
                    print(f"[kiosk_file_downloader] Received {file_path} ({file_info['size']} bytes)")
                
                # Check if we need to request more files
                if data['status'] == 'partial':
                    remaining_files = data['remaining_files']
                    print(f"[kiosk_file_downloader] Partial transfer, {len(remaining_files)} files remaining")
                else:
                    remaining_files = []
                    
            return all_received_files
            
        except Exception as e:
            print(f"[kiosk_file_downloader] Error requesting files: {e}")
            return None

    def _check_for_updates(self):
        """Check for updates from admin server based on content hash."""
        try:
            if not self.is_syncing:
                # Request to be added to sync queue if not already syncing
                self._request_sync_permission()
                self.is_syncing = True  # Set syncing flag when requesting permission
                return False

            # Check if it's our turn
            status = self._check_sync_status()
            if not status or status.get('status') != 'active':
                if status and status.get('status') == 'queued':
                    print(f"[kiosk_file_downloader] Waiting in queue position {status.get('position')}")
                return False

            print("[kiosk_file_downloader] Checking for updates...")
            sync_url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/sync_info"
            response = requests.get(sync_url, timeout=10)
            response.raise_for_status()
            
            server_file_info = response.json()
            print(f"[kiosk_file_downloader] Server file info: {server_file_info}")
            
            local_files = {}
            for root, _, filenames in os.walk("."):
                for filename in filenames:
                    file_path = os.path.relpath(os.path.join(root, filename), ".")
                    normalized_path = file_path.replace("\\", "/")
                    if not normalized_path.startswith("sync_directory") and not normalized_path.endswith(".py") and not "__pycache__" in normalized_path:
                        local_files[normalized_path] = self._calculate_file_hash(file_path)

            print(f"[kiosk_file_downloader] Local file hashes: {local_files}")

            files_to_update = []
            files_to_delete = []

            for file, server_hash in server_file_info.items():
                if file not in local_files or local_files[file] != server_hash:
                    files_to_update.append(file)

            for file in local_files:
                if file not in server_file_info:
                    files_to_delete.append(file)

            # Handle deletions first
            for file in files_to_delete:
                target_path = os.path.join(".", file)
                if os.path.exists(target_path):
                    os.remove(target_path)
                print(f"[kiosk_file_downloader] Removed file: {target_path}")

            # Request and update files in batches
            if files_to_update:
                response_data = self._request_files(files_to_update)
                if response_data:
                    for file_path, file_data in response_data.items():
                        target_path = os.path.join(".", file_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "wb") as file:
                            file.write(file_data.encode('latin1'))
                        print(f"[kiosk_file_downloader] Updated file: {file_path}")

            # Mark sync as complete
            if files_to_update or files_to_delete:
                print("[kiosk_file_downloader] Sync complete")
            self._finish_sync()
            return True

        except Exception as e:
            print(f"[kiosk_file_downloader] Error checking for updates: {e}")
            self._finish_sync()  # Make sure to release sync lock on error
            return False

    def _download_file(self, file_path):
        """Download a single file from the admin server."""
        try:
            normalized_path = file_path.replace("\\", "/") # Normalise the path
            encoded_path = urllib.parse.quote(normalized_path) # Encode the whole normalized path
            print(f"[kiosk_file_downloader][DEBUG] Requesting URL: http://{self.admin_ip}:{ADMIN_SERVER_PORT}/{encoded_path}")
            url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/{encoded_path}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            target_path = os.path.join(".", file_path) # use original path here!
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            with open(target_path, "wb") as file:
                file.write(response.content)
            print(f"[kiosk_file_downloader] Downloaded: {file_path}")
        except requests.exceptions.RequestException as e:
            print(f"[kiosk_file_downloader] Error downloading {file_path}: {e}")
            import traceback
            traceback.print_exc()
    def _send_reset_message(self):
        """Send a message to trigger the kiosk to reset the UI."""
        print("[kiosk_file_downloader] [defunct] Sending reset message to kiosk")
        #message = {
           #'type': RESET_MESSAGE_TYPE,
           #'computer_name': self.kiosk_app.computer_name
        #}
        #self.kiosk_app.network.send_message(message)

    def request_sync(self):
        """Request a sync operation."""
        print("[kiosk_file_downloader] Sync requested")
        self.sync_requested = True

    def _background_download_handler(self):
        """Background handler that only processes sync when requested."""
        while self.running:
            try:
                if self.sync_requested:
                    success = self._check_for_updates()
                    if success:
                        self.sync_requested = False  # Reset flag after successful sync
                time.sleep(1)
            except Exception as e:
                print(f"[kiosk_file_downloader] An error occurred: {e}")
                import traceback
                traceback.print_exc()
                self.sync_requested = False  # Reset flag on error
                time.sleep(5)