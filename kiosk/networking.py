# networking.py
import socket
import json
import time
from threading import Thread

class KioskNetwork:
    def __init__(self, computer_name, message_handler):
        self.computer_name = computer_name
        self.message_handler = message_handler
        self.running = True
        self.socket = None
        self.setup_socket()
        
    def setup_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(('', 12346))
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        
    def start_threads(self):
        self.announce_thread = Thread(target=self.announce_presence, daemon=True)
        self.listen_thread = Thread(target=self.listen_for_messages, daemon=True)
        self.announce_thread.start()
        self.listen_thread.start()
        
    def send_message(self, message):
        if message.get('type') == 'kiosk_announce':
            # Ensure we send complete stats
            complete_stats = self.message_handler.get_stats()
            message.update(complete_stats)
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12345))
        
    def announce_presence(self):
        while self.running:
            try:
                stats = self.message_handler.get_stats()
                message = {
                    'type': 'kiosk_announce',
                    **stats
                }
                self.send_message(message)
                time.sleep(1)  # Update every second
            except:
                break
                
    def listen_for_messages(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                msg = json.loads(data.decode())
                self.message_handler.handle_message(msg)
            except:
                break
                
    def shutdown(self):
        self.running = False
        try:
            message = {
                'type': 'kiosk_disconnect',
                'computer_name': self.computer_name
            }
            self.send_message(message)
        finally:
            self.socket.close()