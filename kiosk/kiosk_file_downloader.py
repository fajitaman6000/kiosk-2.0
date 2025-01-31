# kiosk_file_downloader.py
import time
import requests
import json
import os
from threading import Thread
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
    def _check_for_updates(self):
        """Check for updates from admin server."""
        try:
            print("[kiosk_file_downloader] Checking for updates...")
            sync_url = f"http://{self.ADMIN_IP}:{ADMIN_SERVER_PORT}" # Gets the root directory, which is the list of files
            response = requests.get(sync_url, timeout=10)
            response.raise_for_status()
            
            server_file_list = {}
            for file in response.text.split("\n"):
                if file and not file.endswith(".py"):
                    server_file_list[file] = 'exists'
            
            print(f"[kiosk_file_downloader] Files found: {server_file_list}")

            local_files = {}
            for root, _, filenames in os.walk("."):
              for filename in filenames:
                  file_path = os.path.relpath(os.path.join(root, filename), ".")
                  if not file_path.startswith("sync_directory"):
                      local_files[file_path] = 'exists'

            print(f"[kiosk_file_downloader] Local files: {local_files}")

            files_to_download = {}
            for file, _ in server_file_list.items():
               if file not in local_files:
                 files_to_download[file] = 'new'

            for file, _ in local_files.items():
               if file not in server_file_list:
                 files_to_download[file] = 'delete'


            if not files_to_download:
                print("[kiosk_file_downloader] No updates found.")
                return False

            for file, action in files_to_download.items():
                 if action == 'new':
                     print(f"[kiosk_file_downloader] Downloading file: {file}")
                     self._download_file(file)
                 elif action == 'delete':
                     target_path = os.path.join(".", file)
                     if os.path.exists(target_path):
                         os.remove(target_path)
                     print(f"[kiosk_file_downloader] Removed file: {target_path}")
                 else:
                   print(f"[kiosk_file_downloader] Unknown file action {action}")
            return True

        except requests.exceptions.RequestException as e:
            print(f"[kiosk_file_downloader] Error checking for updates: {e}")
            return False
    def _download_file(self, file_path):
        """Download a single file from the admin server."""
        try:
            url = f"http://{self.ADMIN_IP}:{ADMIN_SERVER_PORT}/{file_path}" # Get the specific file
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