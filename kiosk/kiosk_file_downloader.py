# kiosk_file_downloader.py
import time
import requests
import os
import json
from threading import Thread
import hashlib
import urllib.parse
import socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from file_sync_config import ADMIN_SERVER_PORT #, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE
from pathlib import Path

class KioskFileDownloader:
    def __init__(self, kiosk_app, admin_ip=None):
        self.kiosk_app = kiosk_app
        self.running = True
        self.download_thread = None
        self.admin_ip = admin_ip or "192.168.0.110"  # Fallback only if no IP provided
        self.kiosk_id = socket.gethostname()  # Use hostname as kiosk ID
        self.is_syncing = False
        self.sync_requested = False  # New flag to control sync
        self.cache_file = Path("file_hashes.json")  # Cache file in root directory
        self.max_workers = 5  # Number of concurrent downloads

    def _load_cache(self):
        """Load file hashes from cache file"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"[kiosk_file_downloader] Error loading cache: {e}")
            return {}

    def _save_cache(self, file_hashes):
        """Save file hashes to cache file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(file_hashes, f, indent=2)
        except Exception as e:
            print(f"[kiosk_file_downloader] Error saving cache: {e}")

    def _update_file_inventory(self):
        """Perform a full inventory of local files and their hashes."""
        print("[kiosk_file_downloader] Performing full file inventory...")
        local_files = {}
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            file_paths = []
            for root, _, filenames in os.walk("."):
                for filename in filenames:
                    file_path = os.path.relpath(os.path.join(root, filename), ".")
                    normalized_path = file_path.replace("\\", "/")
                    if not normalized_path.endswith(".py") and not "__pycache__" in normalized_path:
                        file_paths.append(normalized_path)

            future_to_path = {
                executor.submit(self._calculate_file_hash, path): path
                for path in file_paths
            }
            
            for future in as_completed(future_to_path):
                path = future_to_path[future]
                try:
                    file_hash = future.result()
                    if file_hash:
                        local_files[path] = file_hash
                        print(f"[kiosk_file_downloader] Local file: {path} -> {file_hash[:8]}...")
                except Exception as e:
                    print(f"[kiosk_file_downloader] Error hashing {path}: {e}")
        
        print(f"[kiosk_file_downloader] Inventory complete - found {len(local_files)} files")
        self._save_cache(local_files)
        return local_files

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
        """Request specific files from server with concurrent downloads."""
        try:
            remaining_files = file_list
            all_received_files = {}
            
            while remaining_files:
                url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/request_files"
                response = requests.post(url, json={
                    'kiosk_id': self.kiosk_id,
                    'files': remaining_files
                }, timeout=30)
                response.raise_for_status()
                
                data = response.json()
                if 'error' in data:
                    print(f"[kiosk_file_downloader] Server error: {data['error']}")
                    return None

                # Process received files concurrently
                with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                    future_to_file = {}
                    for file_path, file_info in data['files'].items():
                        future = executor.submit(self._save_file, file_path, file_info['data'])
                        future_to_file[future] = file_path

                    # Process completed downloads
                    for future in as_completed(future_to_file):
                        file_path = future_to_file[future]
                        try:
                            success = future.result()
                            if success:
                                all_received_files[file_path] = data['files'][file_path]['data']
                                print(f"[kiosk_file_downloader] Successfully saved {file_path}")
                            else:
                                print(f"[kiosk_file_downloader] Failed to save {file_path}")
                        except Exception as e:
                            print(f"[kiosk_file_downloader] Error saving {file_path}: {e}")
                
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

    def _save_file(self, file_path, file_data):
        """Save a single file to disk."""
        try:
            normalized_path = file_path.replace('\\', '/')
            target_path = os.path.join(".", normalized_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as file:
                file.write(file_data.encode('latin1'))
            return True
        except Exception as e:
            print(f"[kiosk_file_downloader] Error saving file {file_path}: {e}")
            return False

    def _check_for_updates(self):
        """Check for updates from admin server based on content hash."""
        try:
            if not self.is_syncing:
                self._request_sync_permission()
                self.is_syncing = True
                return False

            status = self._check_sync_status()
            if not status or status.get('status') != 'active':
                if status and status.get('status') == 'queued':
                    print(f"[kiosk_file_downloader] Waiting in queue position {status.get('position')}")
                return False

            print("[kiosk_file_downloader] Checking for updates...")
            sync_url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/sync_info"
            response = requests.get(sync_url, timeout=10)
            response.raise_for_status()
            
            server_file_info = {k.replace('\\', '/'): v for k, v in response.json().items()}
            print(f"[kiosk_file_downloader] Server has {len(server_file_info)} files")
            
            local_files = self._load_cache()
            cache_valid = True
            
            # Verify cache validity concurrently
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_path = {
                    executor.submit(self._verify_file, path, cached_hash): path
                    for path, cached_hash in local_files.items()
                }
                
                for future in as_completed(future_to_path):
                    path = future_to_path[future]
                    try:
                        is_valid, current_hash = future.result()
                        if not is_valid:
                            del local_files[path]
                            cache_valid = False
                    except Exception as e:
                        print(f"[kiosk_file_downloader] Error verifying {path}: {e}")
                        del local_files[path]
                        cache_valid = False

            if not cache_valid or not local_files:
                print("[kiosk_file_downloader] Cache invalid or empty, performing full inventory...")
                local_files = self._update_file_inventory()

            print(f"[kiosk_file_downloader] Found {len(local_files)} local files to check")

            files_to_update = []
            for file_path, server_hash in server_file_info.items():
                if file_path in local_files:
                    if local_files[file_path] != server_hash:
                        files_to_update.append(file_path)
                else:
                    files_to_update.append(file_path)

            if files_to_update:
                print(f"[kiosk_file_downloader] Updating {len(files_to_update)} files")
                response_data = self._request_files(files_to_update)
                if response_data:
                    print("[kiosk_file_downloader] All files updated successfully")
            else:
                print("[kiosk_file_downloader] All files are up to date")

            # Always perform a full inventory after checking files, regardless of updates
            print("[kiosk_file_downloader] Performing final inventory update...")
            self._update_file_inventory()
            
            self._finish_sync()
            return True

        except Exception as e:
            print(f"[kiosk_file_downloader] Error checking for updates: {e}")
            self._finish_sync()
            return False

    def _verify_file(self, path, cached_hash):
        """Verify if a file exists and its hash matches the cache."""
        if not os.path.exists(path):
            return False, None
        current_hash = self._calculate_file_hash(path)
        return (current_hash == cached_hash), current_hash

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