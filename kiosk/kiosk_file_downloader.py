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
            
            # Normalize server paths to use forward slashes
            server_file_info = {k.replace('\\', '/'): v for k, v in response.json().items()}
            print(f"[kiosk_file_downloader] Server has {len(server_file_info)} files")
            
            # First, get all local files that could be synced (non-py files)
            local_files = {}
            for root, _, filenames in os.walk("."):
                for filename in filenames:
                    file_path = os.path.relpath(os.path.join(root, filename), ".")
                    normalized_path = file_path.replace("\\", "/")
                    # Only include files that could exist in admin's sync directory
                    if not normalized_path.endswith(".py") and not "__pycache__" in normalized_path:
                        file_hash = self._calculate_file_hash(file_path)
                        if file_hash:  # Only add if hash calculation succeeded
                            local_files[normalized_path] = file_hash
                            print(f"[kiosk_file_downloader] Local file: {normalized_path} -> {file_hash[:8]}...")

            print(f"[kiosk_file_downloader] Found {len(local_files)} local files to check")

            files_to_update = []

            # Check which server files need to be updated locally
            for file_path, server_hash in server_file_info.items():
                if file_path in local_files:
                    local_hash = local_files[file_path]
                    print(f"[kiosk_file_downloader] Comparing {file_path}:")
                    print(f"  Local:  {local_hash[:8]}...")
                    print(f"  Server: {server_hash[:8]}...")
                    if local_hash != server_hash:
                        print(f"  -> Hash mismatch, will update")
                        files_to_update.append(file_path)
                else:
                    print(f"[kiosk_file_downloader] File missing locally: {file_path}")
                    files_to_update.append(file_path)

            # Request and update files in batches
            if files_to_update:
                print(f"[kiosk_file_downloader] Updating {len(files_to_update)} files")
                response_data = self._request_files(files_to_update)
                if response_data:
                    for file_path, file_data in response_data.items():
                        # Normalize path before writing
                        normalized_path = file_path.replace('\\', '/')
                        target_path = os.path.join(".", normalized_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, "wb") as file:
                            file.write(file_data.encode('latin1'))
                        print(f"[kiosk_file_downloader] Updated file: {normalized_path}")
            else:
                print("[kiosk_file_downloader] All files are up to date")

            # Mark sync as complete
            if files_to_update:
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