# kiosk_file_downloader.py
import time
import requests
import os
import json
from threading import Thread
import hashlib
import urllib.parse
import socket
import zlib
import base64
from concurrent.futures import ThreadPoolExecutor, as_completed
from file_sync_config import ADMIN_SERVER_PORT #, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE
from pathlib import Path

class KioskFileDownloader:
    def __init__(self, kiosk_app, admin_ip=None):
        self.kiosk_app = kiosk_app
        self.running = True
        self.download_thread = None
        self.admin_ip = admin_ip or "192.168.0.110"
        self.kiosk_id = socket.gethostname()
        self.is_syncing = False
        self.sync_requested = False
        self.cache_file = Path("file_hashes.json")
        self.max_workers = 1  # Only download one file at a time
        self.chunk_size = 1 * 1024 * 1024  # 1MB chunks
        self.large_file_threshold = 10 * 1024 * 1024  # 10MB threshold for large files

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

    def _download_large_file(self, file_path, file_info):
        """Download a large file in chunks with resume capability."""
        try:
            normalized_path = file_path.replace('\\', '/')
            target_path = os.path.join(".", normalized_path)
            temp_path = f"{target_path}.temp"
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            total_size = file_info.get('size', 0)
            
            # Check if we have a partial download
            start_byte = 0
            if os.path.exists(temp_path):
                start_byte = os.path.getsize(temp_path)
                if start_byte >= total_size:
                    os.replace(temp_path, target_path)
                    return True

            headers = {'Range': f'bytes={start_byte}-'} if start_byte > 0 else {}
            
            url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/download_file"
            with requests.post(url, json={
                'file_path': normalized_path,
                'kiosk_id': self.kiosk_id
            }, headers=headers, stream=True, timeout=300) as response:  # 5 minute timeout
                
                response.raise_for_status()
                
                mode = 'ab' if start_byte > 0 else 'wb'
                with open(temp_path, mode, buffering=self.chunk_size) as f:
                    bytes_downloaded = start_byte
                    start_time = time.time()
                    last_update = time.time()
                    
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if not chunk:
                            continue
                        
                        f.write(chunk)
                        bytes_downloaded += len(chunk)
                        
                        # Update progress every second
                        current_time = time.time()
                        if current_time - last_update >= 1.0:
                            progress = (bytes_downloaded / total_size) * 100 if total_size else 0
                            speed = bytes_downloaded / (1024 * 1024 * (current_time - start_time))
                            print(f"[kiosk_file_downloader] {file_path}: {progress:.1f}% "
                                  f"({bytes_downloaded}/{total_size} bytes) {speed:.2f} MB/s")
                            last_update = current_time

            # Verify download is complete
            if os.path.getsize(temp_path) == total_size:
                os.replace(temp_path, target_path)
                return True
            else:
                print(f"[kiosk_file_downloader] Incomplete download for {file_path}")
                return False
                
        except Exception as e:
            print(f"[kiosk_file_downloader] Error downloading large file {file_path}: {e}")
            return False

    def _request_files(self, file_list):
        """Request specific files from server with conservative download settings."""
        try:
            remaining_files = file_list.copy()
            all_received_files = {}
            retry_count = 0
            max_retries = 5  # More retries but with longer pauses
            
            # Process files in small batches for stability
            batch_size = 5  # Increased from 1 to 5 for better performance
            
            while remaining_files and retry_count < max_retries:
                try:
                    current_batch = remaining_files[:batch_size]
                    
                    url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/request_files"
                    
                    print(f"[kiosk_file_downloader] Requesting info for files: {current_batch}")
                    response = requests.post(url, json={
                        'kiosk_id': self.kiosk_id,
                        'files': current_batch,
                        'info_only': True
                    }, timeout=60)  # Longer initial timeout
                    
                    response.raise_for_status()
                    data = response.json()
                    
                    if 'error' in data:
                        print(f"[kiosk_file_downloader] Server error: {data['error']}")
                        if data['error'] == 'Not your turn to sync':
                            print("[kiosk_file_downloader] Waiting for our turn...")
                            time.sleep(5)  # Wait longer when it's not our turn
                            continue
                        retry_count += 1
                        time.sleep(5)  # Longer pause on error
                        continue

                    if 'files' not in data:
                        print("[kiosk_file_downloader] Error: No files in response")
                        retry_count += 1
                        time.sleep(5)
                        continue

                    # Process files one at a time
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future_to_file = {}
                        
                        for file_path, file_info in data['files'].items():
                            if not isinstance(file_info, dict):
                                print(f"[kiosk_file_downloader] Error: Invalid file info for {file_path}")
                                continue
                                
                            size = file_info.get('size', 0)
                            if not size:
                                print(f"[kiosk_file_downloader] Error: No size info for {file_path}")
                                continue
                            
                            if size > self.large_file_threshold:
                                # For large files, first verify if we need to download
                                local_path = os.path.join(".", file_path)
                                if os.path.exists(local_path) and os.path.getsize(local_path) == size:
                                    print(f"[kiosk_file_downloader] Skipping {file_path} - already exists with correct size")
                                    all_received_files[file_path] = True
                                    if file_path in remaining_files:
                                        remaining_files.remove(file_path)
                                    continue
                                future = executor.submit(self._download_large_file, file_path, file_info)
                            else:
                                try:
                                    # Now request the actual file data
                                    file_response = requests.post(url, json={
                                        'kiosk_id': self.kiosk_id,
                                        'files': [file_path],
                                        'info_only': False
                                    }, timeout=60)
                                    
                                    file_response.raise_for_status()
                                    file_data = file_response.json()
                                    
                                    if 'files' not in file_data or file_path not in file_data['files']:
                                        print(f"[kiosk_file_downloader] Error: Invalid response for {file_path}")
                                        continue
                                        
                                    file_content = file_data['files'][file_path].get('data')
                                    if not file_content:
                                        print(f"[kiosk_file_downloader] Error: No data for {file_path}")
                                        continue
                                    
                                    if file_info.get('compressed'):
                                        try:
                                            compressed_data = base64.b64decode(file_content)
                                            file_content = zlib.decompress(compressed_data).decode('latin1')
                                        except Exception as e:
                                            print(f"[kiosk_file_downloader] Error decompressing {file_path}: {e}")
                                            continue
                                            
                                    future = executor.submit(self._save_file, file_path, file_content)
                                except Exception as e:
                                    print(f"[kiosk_file_downloader] Error requesting file data for {file_path}: {e}")
                                    continue
                                
                            future_to_file[future] = file_path

                        successful_files = []
                        
                        for future in as_completed(future_to_file):
                            file_path = future_to_file[future]
                            try:
                                success = future.result(timeout=600)  # 10 minute timeout per file
                                if success:
                                    all_received_files[file_path] = True
                                    successful_files.append(file_path)
                                    print(f"[kiosk_file_downloader] Successfully downloaded: {file_path}")
                                    time.sleep(0.5)  # Shorter pause between files
                                else:
                                    print(f"[kiosk_file_downloader] Failed to process {file_path}")
                            except Exception as e:
                                print(f"[kiosk_file_downloader] Error processing {file_path}: {e}")

                        # Remove successfully processed files
                        for file in successful_files:
                            if file in remaining_files:
                                remaining_files.remove(file)
                        
                        # Reset retry count on any success
                        if successful_files:
                            retry_count = 0
                        else:
                            retry_count += 1
                            time.sleep(5)  # Longer pause between retries
                    
                    if remaining_files:
                        print(f"[kiosk_file_downloader] {len(remaining_files)} files remaining: {remaining_files}")
                        time.sleep(1)  # Shorter pause between batches
                
                except requests.exceptions.Timeout:
                    print(f"[kiosk_file_downloader] Timeout downloading file: {current_batch}")
                    retry_count += 1
                    time.sleep(10)  # Much longer pause after timeout
                except Exception as e:
                    print(f"[kiosk_file_downloader] Error in batch: {e}")
                    retry_count += 1
                    time.sleep(10)
            
            if remaining_files:
                print(f"[kiosk_file_downloader] Failed to download {len(remaining_files)} files after {max_retries} retries")
                print(f"[kiosk_file_downloader] Failed files: {remaining_files}")
            
            return all_received_files
            
        except Exception as e:
            print(f"[kiosk_file_downloader] Fatal error in file request: {e}")
            return None

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
            
            # First try using the cache without full inventory
            local_files = self._load_cache()
            files_to_update = []
            
            # Quick check of cache entries against server
            for file_path, server_hash in server_file_info.items():
                if file_path not in local_files or local_files[file_path] != server_hash:
                    files_to_update.append(file_path)
            
            # Only do full inventory if we found files that need updating
            if files_to_update:
                print("[kiosk_file_downloader] Found differences, verifying local files...")
                local_files = self._update_file_inventory()
                
                # Recheck with verified inventory
                files_to_update = []
                for file_path, server_hash in server_file_info.items():
                    if file_path not in local_files or local_files[file_path] != server_hash:
                        files_to_update.append(file_path)

            if files_to_update:
                print(f"[kiosk_file_downloader] Updating {len(files_to_update)} files")
                response_data = self._request_files(files_to_update)
                if response_data:
                    print("[kiosk_file_downloader] All files updated successfully")
            else:
                print("[kiosk_file_downloader] All files are up to date")
            
            # Always perform final inventory after sync completes, regardless of whether files were updated
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