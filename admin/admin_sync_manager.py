# admin_sync_manager.py
import os
import json
import requests
import socket
import time
from threading import Thread
from file_sync_config import ADMIN_SYNC_DIR, ADMIN_SERVER_PORT, BROADCAST_MESSAGE_TYPE, SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE

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
        while time.time() - start_time < 5:
            if not self.running:
                return False
            for computer_name, data in self.app.interface_builder.connected_kiosks.items():
                self.kiosk_ips[computer_name] = data.get('ip')
            if self.kiosk_ips:
                break # Found at least 1 device
            time.sleep(0.1)
        print(f"[admin_sync_manager] Kiosks Discovered: {self.kiosk_ips}")
        return True
    def _scan_sync_directory(self):
       """Scan the admin's sync directory."""
       print("[admin_sync_manager] Scanning sync directory...")
       files = {}
       for root, _, filenames in os.walk(ADMIN_SYNC_DIR):
            for filename in filenames:
                file_path = os.path.relpath(os.path.join(root, filename), ADMIN_SYNC_DIR)
                files[file_path] = {
                    'type': 'upload',
                    'data': self._encode_file(os.path.join(ADMIN_SYNC_DIR, file_path))
                }
       print(f"[admin_sync_manager] Files found: {files}")
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
    def _compare_files(self):
        """Compares the files to be sent against the local file list of the kiosk."""
        print("[admin_sync_manager] Comparing files...")
        files = self._scan_sync_directory()
        if not files:
            print("[admin_sync_manager] No files found for comparison")
            return {}
        
        #Get the current list of files from server for comparison with local
        response = requests.get(f"http://0.0.0.0:{ADMIN_SERVER_PORT}", timeout=20)
        if response.status_code != 200:
            print(f"[admin_sync_manager] Could not get local server file list! Status code: {response.status_code}")
            return {}
        server_file_list = {}
        for file in response.text.split("\n"):
            if file and not file.endswith(".py"):
                 server_file_list[file] = 'exists'

        files_to_send = {}

        # Scan the directory files to update the remote server
        for file, value in files.items():
            if file not in server_file_list:
                files_to_send[file] = value
                print(f"[admin_sync_manager] New or modified file: {file}")

        # Scan the server files to delete missing local files
        for file, value in server_file_list.items():
             if file not in files:
                  files_to_send[file] = {
                        'type': 'delete'
                   }
                  print(f"[admin_sync_manager] File removed: {file}")
        
        if not files_to_send:
            print(f"[admin_sync_manager] No file changes found")
        
        return files_to_send
    def _send_sync_request(self, files):
        """Send a sync request to the server."""
        if not files:
          print("[admin_sync_manager] No file changes to synchronize")
          return False
        try:
            print(f"[admin_sync_manager] Sending sync request with {len(files)} files")
            sync_url = f"http://0.0.0.0:{ADMIN_SERVER_PORT}/sync"
            response = requests.post(sync_url, json={'files': files}, timeout=60)
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
        for computer_name, ip in self.kiosk_ips.items():
             message = {
                'type': SYNC_MESSAGE_TYPE,
                'computer_name': computer_name
                }
             self.app.network_handler.socket.sendto(json.dumps(message).encode(), (ip, 12346)) # Send to all IPs using the socket
             print(f"[admin_sync_manager] Message sent to {computer_name} at {ip}")
    def _background_sync_handler(self):
        while self.running:
            try:
               time.sleep(10)
               if self.app.interface_builder.sync_button.cget('text') != "Sync": #Check for button pressed state
                    continue
               if not self._discover_kiosks():
                  print("[admin_sync_manager] No kiosks found")
                  self.app.root.after(0, lambda: self.app.interface_builder.sync_button.config(text="Sync"))
                  continue
               files_to_sync = self._compare_files()
               if not files_to_sync:
                   self.app.root.after(0, lambda: self.app.interface_builder.sync_button.config(text="Sync"))
                   continue
               if not self._send_sync_request(files_to_sync):
                  print("[admin_sync_manager] Sync failed to server")
                  self.app.root.after(0, lambda: self.app.interface_builder.sync_button.config(text="Sync"))
                  continue
               self._send_message_to_kiosks()
               self.app.root.after(0, lambda: self.app.interface_builder.sync_button.config(text="Sync"))
            except Exception as e:
                print(f"[admin_sync_manager] An error occured: {e}")
                import traceback
                traceback.print_exc()
                self.app.root.after(0, lambda: self.app.interface_builder.sync_button.config(text="Sync"))
    def handle_sync_button(self):
        """Handle the button click to start the sync process."""
        if not self.sync_thread or not self.sync_thread.is_alive():
            self.start()