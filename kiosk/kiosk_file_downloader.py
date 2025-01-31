# kiosk_file_downloader.py
import time
import requests
import os
from threading import Thread
import hashlib
from file_sync_config import ADMIN_SERVER_PORT, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE

class KioskFileDownloader:
    ADMIN_IP = "192.168.0.110"

    def __init__(self, kiosk_app):
        self.kiosk_app = kiosk_app
        self.running = True
        self.download_thread = None

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


    def _check_for_updates(self):
        """Check for updates from admin server based on content hash."""
        try:
            print("[kiosk_file_downloader] Checking for updates...")
            sync_url = f"http://{self.ADMIN_IP}:{ADMIN_SERVER_PORT}/sync_info"  # Changed URL
            response = requests.get(sync_url, timeout=10)
            response.raise_for_status()
            
            server_file_info = response.json() # Expecting JSON now
            
            print(f"[kiosk_file_downloader] Server file info: {server_file_info}")
            
            local_files = {}
            for root, _, filenames in os.walk("."):
                for filename in filenames:
                    file_path = os.path.relpath(os.path.join(root, filename), ".")
                    if not file_path.startswith("sync_directory") and not file_path.endswith(".py") and not "__pycache__" in file_path:
                       local_files[file_path] = self._calculate_file_hash(file_path)

            print(f"[kiosk_file_downloader] Local file hashes: {local_files}")

            files_to_download = {}
            for file, server_hash in server_file_info.items():
                if file not in local_files or local_files[file] != server_hash:
                    files_to_download[file] = {'action': 'update', 'server_hash': server_hash}
                    

            for file, local_hash in local_files.items():
              if file not in server_file_info:
                 files_to_download[file] = {'action': 'delete'}


            if not files_to_download:
                print("[kiosk_file_downloader] No updates required.")
                return False

            for file, details in files_to_download.items():
                if details['action'] == 'update':
                    print(f"[kiosk_file_downloader] Downloading file: {file}")
                    self._download_file(file)
                elif details['action'] == 'delete':
                    target_path = os.path.join(".", file)
                    if os.path.exists(target_path):
                        os.remove(target_path)
                    print(f"[kiosk_file_downloader] Removed file: {target_path}")
                else:
                    print(f"[kiosk_file_downloader] Unknown file action {details['action']}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"[kiosk_file_downloader] Error checking for updates: {e}")
            return False


    def _download_file(self, file_path):
        """Download a single file from the admin server."""
        try:
            url = f"http://{self.ADMIN_IP}:{ADMIN_SERVER_PORT}/{file_path}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            target_path = os.path.join(".", file_path)
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
        print("[kiosk_file_downloader] Sending reset message to kiosk")
        message = {
           'type': RESET_MESSAGE_TYPE,
           'computer_name': self.kiosk_app.computer_name
        }
        self.kiosk_app.network.send_message(message)

    def _background_download_handler(self):
        """ This method no longer executes automatically, and is only called when it is specifically asked to sync. """
        while self.running:
            try:
                time.sleep(1) # check every 1 second
            except Exception as e:
                print(f"[kiosk_file_downloader] An error occured: {e}")
                import traceback
                traceback.print_exc()