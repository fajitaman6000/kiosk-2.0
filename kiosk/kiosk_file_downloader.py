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
from concurrent.futures import ThreadPoolExecutor, as_completed, wait
from file_sync_config import ADMIN_SERVER_PORT #, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE
from pathlib import Path
import traceback

class KioskFileDownloader:
    def __init__(self, kiosk_app, admin_ip=None):
        self.kiosk_app = kiosk_app
        self.running = True
        self.download_thread = None
        self.admin_ip = admin_ip or "192.168.0.110"
        self.kiosk_id = socket.gethostname()
        self.is_syncing = False
        self.sync_requested = False
        # Store cache file in data directory
        self.data_dir = Path("data")
        self.cache_file = self.data_dir / "file_hashes.json"
        self.max_workers = 1  # Only download one file at a time
        self.chunk_size = 1 * 1024 * 1024  # 1MB chunks
        self.large_file_threshold = 10 * 1024 * 1024  # 10MB threshold for large files
        self.queue_generation = None  # Track queue generation number
        self.last_successful_operation = 0  # Track when we last successfully did anything
        self.stall_timeout = 30  # If no progress for 30 seconds, consider it stalled
        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)

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
            # Ensure data directory exists before saving
            self.data_dir.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(file_hashes, f, indent=2)
        except Exception as e:
            print(f"[kiosk_file_downloader] Error saving cache: {e}")

    def _update_file_inventory(self):
        """Perform a full inventory of local files and their hashes."""
        print("[kiosk_file_downloader] Performing full file inventory...")
        local_files = {}
        inventory_start_time = time.time()
        processed_count = 0
        
        try:
            # First collect and sort files by size
            file_info = []
            total_size = 0
            for root, _, filenames in os.walk("."):
                for filename in filenames:
                    file_path = os.path.relpath(os.path.join(root, filename), ".")
                    normalized_path = file_path.replace("\\", "/")
                    # Ignore Python cache, data directory, and other non-synced files
                    if (not normalized_path.endswith(".py") and 
                        not "__pycache__" in normalized_path and
                        not normalized_path.startswith("data/") and  # Ignore data directory
                        not "data\\" in normalized_path):  # Also ignore Windows path format
                        try:
                            size = os.path.getsize(file_path)
                            file_info.append((normalized_path, size))
                            total_size += size
                        except Exception as e:
                            print(f"[kiosk_file_downloader] Error getting size of {file_path}: {e}")

            # Sort files - process small files first
            file_info.sort(key=lambda x: x[1])
            file_paths = [f[0] for f in file_info]
            total_files = len(file_paths)
            
            print(f"[kiosk_file_downloader] Found {total_files} files to process (total {total_size / (1024*1024):.1f}MB)")

            # Process files in batches, with batch size based on total files
            batch_size = max(5, min(10, total_files // 4))  # Adaptive batch size
            for i in range(0, len(file_paths), batch_size):
                batch = file_paths[i:i + batch_size]
                batch_sizes = sum(f[1] for f in file_info[i:i + batch_size])
                print(f"[kiosk_file_downloader] Processing batch of {len(batch)} files ({batch_sizes / (1024*1024):.1f}MB)")
                
                try:
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        future_to_path = {
                            executor.submit(self._calculate_file_hash, path): path
                            for path in batch
                        }
                        
                        for future in as_completed(future_to_path):
                            path = future_to_path[future]
                            try:
                                file_hash = future.result()  # No timeout - rely on per-file progress tracking
                                if file_hash:
                                    local_files[path] = file_hash
                                    processed_count += 1
                                    if processed_count % 10 == 0:
                                        print(f"[kiosk_file_downloader] Processed {processed_count}/{total_files} files...")
                                else:
                                    print(f"[kiosk_file_downloader] Skipping {path} due to stall/error")
                            except Exception as e:
                                print(f"[kiosk_file_downloader] Error processing {path}: {e}")
                                continue
                            
                except Exception as e:
                    print(f"[kiosk_file_downloader] Batch processing error: {e}")
                    continue  # Try next batch instead of giving up
                
                # Save progress after each successful batch
                self._save_cache(local_files)

            total_time = time.time() - inventory_start_time
            processed_size = sum(f[1] for f in file_info if f[0] in local_files)
            print(f"[kiosk_file_downloader] Inventory complete - processed {processed_count}/{total_files} files "
                  f"({processed_size / (1024*1024):.1f}MB/{total_size / (1024*1024):.1f}MB) in {total_time:.1f} seconds")
            
            if processed_count < total_files * 0.5:  # If we processed less than 50% of files
                print("[kiosk_file_downloader] Too many failures, falling back to cache...")
                return self._load_cache()
                
            return local_files

        except Exception as e:
            print(f"[kiosk_file_downloader] Critical error during inventory: {e}")
            traceback.print_exc()
            return self._load_cache()  # Fall back to cache on error

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
        last_progress = time.time()
        bytes_read = 0
        timeout = 30  # seconds
        try:
            file_size = os.path.getsize(file_path)
            with open(file_path, 'rb') as file:
                while True:
                    chunk = file.read(4096)
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    hasher.update(chunk)

                    # Check for timeout every 1MB
                    if bytes_read % (1024 * 1024) == 0:
                        if time.time() - last_progress > timeout:
                            print(f"[kiosk_file_downloader] Timeout calculating hash for {file_path}")
                            return None
                        last_progress = time.time()

            return hasher.hexdigest()
        except Exception as e:
            print(f"[kiosk_file_downloader] Error calculating hash for {file_path}: {e}")
            return None

    def _is_stalled(self):
        """Check if operations have stalled."""
        return time.time() - self.last_successful_operation > self.stall_timeout

    def _update_last_operation(self):
        """Update the last successful operation timestamp."""
        self.last_successful_operation = time.time()

    def _make_request(self, method, url, **kwargs):
        """Make a network request with proper timeout and error handling."""
        try:
            # Ensure we always have timeouts set - Increased default timeout
            kwargs.setdefault('timeout', 30)  # Increased default timeout

            # Create a session with retry capability
            session = requests.Session()
            session.mount('http://', requests.adapters.HTTPAdapter(
                max_retries=3,  # Increased retries
                pool_connections=1,  # Limit connections
                pool_maxsize=1
            ))

            response = session.request(method, url, **kwargs)
            response.raise_for_status()
            self._update_last_operation()  # Mark successful network operation
            return response

        except requests.exceptions.Timeout:
            print(f"[kiosk_file_downloader] Request timed out: {url}")
            return None
        except requests.exceptions.ConnectionError:
            print(f"[kiosk_file_downloader] Connection failed: {url}")
            return None
        except Exception as e:
            print(f"[kiosk_file_downloader] Request failed: {url} - {str(e)}")
            return None
        finally:
            try:
                session.close()
            except:
                pass  # Ignore errors during cleanup

    def _request_sync_permission(self):
        """Request to be added to the sync queue."""
        url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/request_sync"
        response = self._make_request('POST', url, json={'kiosk_id': self.kiosk_id})
        
        if not response:
            return False
            
        try:
            data = response.json()
            if data.get('status') == 'active':
                self.queue_generation = data.get('generation')
                return True
            elif data.get('status') == 'queued':
                self.queue_generation = data.get('generation')
                print(f"[kiosk_file_downloader] Queued at position {data.get('position')}")
                return False
            return False
        except Exception as e:
            print(f"[kiosk_file_downloader] Error parsing sync permission response: {e}")
            return False

    def _check_sync_status(self):
        """Check if it's our turn to sync."""
        url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/sync_status"
        response = self._make_request('GET', url, params={'kiosk_id': self.kiosk_id})
        
        if not response:
            return None
        
        try:
            data = response.json()
            current_generation = data.get('generation')
            
            # If queue generation changed, we need to re-request sync permission
            if self.queue_generation is not None and current_generation != self.queue_generation:
                print(f"[kiosk_file_downloader] Queue generation changed from {self.queue_generation} to {current_generation}, re-requesting sync permission...")
                self.is_syncing = False
                self.queue_generation = None
                return {'status': 'not_queued'}
                
            # Update our generation number if we don't have one
            if self.queue_generation is None:
                self.queue_generation = current_generation
                
            return data
        except Exception as e:
            print(f"[kiosk_file_downloader] Error parsing sync status response: {e}")
            return None

    def _finish_sync(self):
        """Notify server that sync is complete."""
        url = f"http://{self.admin_ip}:{ADMIN_SERVER_PORT}/finish_sync"
        response = self._make_request('POST', url, json={'kiosk_id': self.kiosk_id})
        if response:
            try:
                data = response.json()
                self.queue_generation = data.get('generation')  # Update to new generation
                
                # Send completion confirmation via broadcast
                if hasattr(self.kiosk_app, 'network'):
                    confirm_msg = {
                        'type': 'sync_confirmation',
                        'computer_name': self.kiosk_id,
                        'sync_id': getattr(self.kiosk_app.message_handler, 'last_sync_id', None),
                        'status': 'completed'
                    }
                    self.kiosk_app.network.send_message(confirm_msg)
                    
            except Exception as e:
                print(f"[kiosk_file_downloader] Error parsing finish sync response: {e}")
            self.is_syncing = False
            return True
        return False

    def handle_sync_complete(self):
        """Handle successful file synchronization."""
        print("[kiosk_file_downloader] File sync complete!")
        if self.sync_success:
            # Send message to admin indicating sync complete
            complete_msg = {
                'type': 'sync_complete', # new message type
                'computer_name': self.kiosk_app.computer_name,
            }
            self.kiosk_app.network.send_message(complete_msg)
            self.kiosk_app.needs_restart = True
            print("[kiosk_file_downloader] Restart required after sync.")
            #self.kiosk_app.restart_kiosk()
        else:
            # Potentially handle partial syncs or errors
            print("[kiosk_file_downloader] Sync was not fully successful")
            # Send a message for sync failure
            complete_msg = {
                'type': 'sync_failed', # new message type
                'computer_name': self.kiosk_app.computer_name,
                'reason': 'unknown' # TODO: get reason from internal state
            }
            self.kiosk_app.network.send_message(complete_msg)

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
                if self._request_sync_permission():
                    self.is_syncing = True
                return False

            status = self._check_sync_status()
            if not status:
                print("[kiosk_file_downloader] Unable to get sync status, will retry...")
                if self._is_stalled():
                    print("[kiosk_file_downloader] Update check appears stalled...")
                    self._reset_sync_state()
                time.sleep(2)
                return False
                
            if status.get('status') != 'active':
                if status.get('status') == 'queued':
                    position = status.get('position', 'unknown')
                    print(f"[kiosk_file_downloader] Waiting in queue position {position}")
                elif status.get('status') == 'not_queued':
                    print("[kiosk_file_downloader] Not in queue, requesting sync permission...")
                    self.is_syncing = False  # Reset sync flag to trigger new request
                time.sleep(2)  # Add small delay between status checks
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
            
            # First notify that we're done to let next kiosk proceed
            if self._finish_sync():
                # Only start background inventory if finish_sync succeeded
                Thread(target=self._update_file_inventory, daemon=True).start()
                self.sync_requested = False  # Clear sync request flag here
                return True
            return False

        except Exception as e:
            print(f"[kiosk_file_downloader] Error checking for updates: {e}")
            self._finish_sync()
            self.sync_requested = False  # Also clear sync request flag on error
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

    def _reset_sync_state(self):
        """Reset all sync-related state."""
        self.is_syncing = False
        self.queue_generation = None
        self.last_successful_operation = time.time()  # Reset operation timer
        print("[kiosk_file_downloader] Reset sync state")

    def _background_download_handler(self):
        """Background handler that only processes sync when requested."""
        consecutive_errors = 0
        last_sync_attempt = 0
        last_status_check = 0
        last_queue_message = 0  # Track when we last printed queue position
        status_check_interval = 2  # Check status every 2 seconds
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check for stalled operations
                if self.sync_requested:
                    # If we're queued but haven't printed position in a while, we're stalled
                    if last_queue_message > 0 and current_time - last_queue_message > self.stall_timeout:
                        print("[kiosk_file_downloader] Queue position checks appear stalled, resetting state...")
                        self._reset_sync_state()
                        time.sleep(5)
                        continue
                        
                    # General stall check
                    if self._is_stalled():
                        print("[kiosk_file_downloader] Operations appear to be stalled, resetting state...")
                        self._reset_sync_state()
                        time.sleep(5)
                        continue
                
                if not self.sync_requested:
                    time.sleep(1)
                    continue
                    
                # Rate limit sync attempts
                if current_time - last_sync_attempt < 5:
                    time.sleep(1)
                    continue
                    
                # Rate limit status checks
                if current_time - last_status_check < status_check_interval:
                    time.sleep(0.5)
                    continue
                    
                last_status_check = current_time
                
                # First check if we're already syncing
                if not self.is_syncing:
                    try:
                        if not self._request_sync_permission():
                            time.sleep(2)
                            # Check if we're stalled during sync permission request
                            if self._is_stalled():
                                print("[kiosk_file_downloader] Sync permission request appears stalled...")
                                self._reset_sync_state()
                            continue
                        self.is_syncing = True
                        last_sync_attempt = current_time
                        self._update_last_operation()
                    except Exception as e:
                        print(f"[kiosk_file_downloader] Error requesting sync permission: {e}")
                        time.sleep(2)
                        continue
                
                # Check queue status
                try:
                    status = self._check_sync_status()
                    if not status:
                        consecutive_errors += 1
                        if consecutive_errors >= 3 or self._is_stalled():
                            print("[kiosk_file_downloader] Too many status check failures or stalled, resetting sync state...")
                            self._reset_sync_state()
                            consecutive_errors = 0
                        time.sleep(2)
                        continue
                    
                    consecutive_errors = 0  # Reset error counter on successful status check
                    self._update_last_operation()  # Mark successful status check
                    
                    if status.get('status') == 'active':
                        last_queue_message = 0  # Reset queue message timer when active
                        try:
                            if self._check_for_updates():
                                self.sync_requested = False
                                self._reset_sync_state()
                                print("[kiosk_file_downloader] Sync completed successfully")
                            else:
                                print("[kiosk_file_downloader] Sync failed, will retry...")
                                if self._is_stalled():
                                    print("[kiosk_file_downloader] Sync appears stalled during update...")
                                    self._reset_sync_state()
                                time.sleep(2)
                        except Exception as e:
                            print(f"[kiosk_file_downloader] Error during sync: {e}")
                            if self._is_stalled():
                                self._reset_sync_state()
                            time.sleep(2)
                    
                    elif status.get('status') == 'queued':
                        position = status.get('position', 'unknown')
                        print(f"[kiosk_file_downloader] Waiting in queue position {position}")
                        last_queue_message = current_time  # Update last queue message time
                        self._update_last_operation()  # Count queue position check as successful operation
                    
                    elif status.get('status') == 'not_queued':
                        print("[kiosk_file_downloader] Not in queue, requesting sync permission...")
                        self.is_syncing = False  # Reset sync flag to trigger new request
                        last_queue_message = 0  # Reset queue message timer
                        time.sleep(2)
                    
                except Exception as e:
                    print(f"[kiosk_file_downloader] Error checking sync status: {e}")
                    if self._is_stalled():
                        self._reset_sync_state()
                    time.sleep(2)
                
            except Exception as e:
                print(f"[kiosk_file_downloader] Critical error in background handler: {e}")
                traceback.print_exc()
                self._reset_sync_state()
                time.sleep(5)  # Longer sleep on critical errors