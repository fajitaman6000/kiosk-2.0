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
        self.last_message = {}  # Initialize the last_message cache here
        
    def setup_socket(self):
        print("[networking.py]\n=== Setting up network socket ===")
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('', 12346))
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Set larger buffer size (16MB)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16 * 1024 * 1024)
            
            # Get actual buffer size
            buf_size = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)
            print(f"[networking.py]Receive buffer size set to: {buf_size / 1024 / 1024:.2f}MB")
            
        except Exception as e:
            print(f"[networking.py]Socket setup error: {e}")
            raise
        
    def start_threads(self):
        self.announce_thread = Thread(target=self.announce_presence, daemon=True)
        self.listen_thread = Thread(target=self.listen_for_messages, daemon=True)
        self.announce_thread.start()
        self.listen_thread.start()
        
    def send_message(self, message):
        try:
            encoded = json.dumps(message).encode()
            msg_size = len(encoded) / 1024  # Size in KB
            #print(f"[networking.py]\nSending message: {message['type']}")
            #print(f"[networking.py]Message size: {msg_size:.2f}KB")
            
            if msg_size > 60000:  # UDP practical limit ~64KB
                print("[networking.py]WARNING: Message exceeds UDP size limit!")
                return
                
            self.socket.sendto(encoded, ('255.255.255.255', 12345))
            
        except Exception as e:
            print(f"[networking.py]Error sending message: {e}")
        
    def announce_presence(self):
        while self.running:
            try:
                stats = self.message_handler.get_stats()
                message = {
                    'type': 'kiosk_announce',
                    **stats
                }
                self.send_message(message)
                time.sleep(1)
            except Exception as e:
                print(f"[networking.py]Error in announce_presence: {e}")
                break
                
    def listen_for_messages(self):
        print("[networking.py]\n=== Starting message listener ===")
        while self.running:
            try:
                # Use larger buffer for receiving
                data, addr = self.socket.recvfrom(16 * 1024 * 1024)  # 16MB buffer
                msg_size = len(data) / 1024  # Size in KB
                
                print(f"[networking.py]\nReceived data from {addr}")
                print(f"[networking.py]Data size: {msg_size:.2f}KB")
                
                try:
                    msg = json.loads(data.decode())
                    print(f"[networking.py]Message type: {msg.get('type')}")
                    
                    # Special handling for hint messages
                    if msg.get('type') == 'hint':
                        print(f"[networking.py]Hint message received:")
                        print(f"[networking.py]Has text: {bool(msg.get('text'))}")
                        print(f"[networking.py]Has image: {msg.get('has_image', False)}")
                        if msg.get('has_image'):
                            img_data = msg.get('image', '')
                            img_size = len(img_data) / 1024 if img_data else 0
                            print(f"[networking.py]Image data size: {img_size:.2f}KB")
                    
                    self.message_handler.handle_message(msg)
                    
                except json.JSONDecodeError as e:
                    print(f"[networking.py]Failed to decode message: {e}")
                except Exception as e:
                    print(f"[networking.py]Error processing message: {e}")
                    import traceback
                    traceback.print_exc()
                    
            except socket.error as e:
                if self.running:
                    print(f"[networking.py]Socket error in listen_for_messages: {e}")
                    import traceback
                    traceback.print_exc()
                    # Try to recover the socket
                    try:
                        self.socket.close()
                        time.sleep(1)  # Brief pause before reconnecting
                        self.setup_socket()
                        print("[networking.py]Successfully recovered socket after error")
                    except Exception as setup_error:
                        print(f"[networking.py]Failed to recover socket: {setup_error}")
                        if self.running:
                            time.sleep(5)  # Wait longer before next attempt
            except Exception as e:
                if self.running:
                    print(f"[networking.py]Unexpected error in listen_for_messages: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(1)  # Brief pause before next iteration
                
    def shutdown(self):
        print("[networking.py]\nShutting down network...")
        self.running = False
        try:
            message = {
                'type': 'kiosk_disconnect',
                'computer_name': self.computer_name
            }
            self.send_message(message)
        finally:
            try:
                self.socket.close()
            except:
                pass
        print("[networking.py]Network shutdown complete")