import socket
import json
from threading import Thread

class NetworkBroadcastHandler:
    def __init__(self, app):
        self.app = app
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('', 12345))
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Create separate socket for reboot signals
            self.reboot_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as e:
            print(f"Network Error: {e}")
            print("This might be because:")
            print("1. Another program is using port 12345")
            print("2. You need to run as administrator")
            raise
            
        self.listen_thread = None
        
        # Room to IP mapping for reboot functionality
        self.room_ips = {
            6: "192.168.0.67",  # Atlantis
            1: "192.168.0.33",  # Casino
            2: "192.168.0.33",  # Morning After (same as Casino)
            5: "192.168.0.31",  # Haunted
            7: "192.168.0.32",  # Time Machine
            3: "192.168.0.35",  # Wizard
            4: "192.168.0.30"   # Zombie
        }
        self.REBOOT_PORT = 5005
        
    def start(self):
        self.listen_thread = Thread(target=self.listen_for_messages, daemon=True)
        self.listen_thread.start()
        
    def listen_for_messages(self):
            print("Started listening for kiosks...")
            while True:
                try:
                    data, addr = self.socket.recvfrom(1024)
                    msg = json.loads(data.decode())
                    print(f"\nReceived message from {addr}:")
                    print(f"Message content: {msg}")
                    
                    if msg['type'] == 'kiosk_announce':
                        computer_name = msg['computer_name']
                        room = msg.get('room')
                        print(f"Processing kiosk announcement:")
                        print(f"Computer: {computer_name}")
                        print(f"Room: {room}")
                        print(f"Current assignments: {self.app.kiosk_tracker.kiosk_assignments}")
                        
                        if room is not None:
                            print(f"Setting room assignment: {computer_name} -> {room}")
                            self.app.kiosk_tracker.kiosk_assignments[computer_name] = room
                            if hasattr(self.app.interface_builder, 'update_kiosk_display'):
                                print("Updating kiosk display...")
                                self.app.interface_builder.update_kiosk_display(computer_name)
                        
                        self.app.kiosk_tracker.update_kiosk_stats(computer_name, msg)
                        self.app.root.after(0, lambda cn=computer_name: 
                            self.app.interface_builder.add_kiosk_to_ui(cn))
                    
                    elif msg['type'] == 'help_request':
                        computer_name = msg['computer_name']
                        if computer_name in self.app.interface_builder.connected_kiosks:
                            self.app.kiosk_tracker.add_help_request(computer_name)
                            def mark_help():
                                if computer_name in self.app.interface_builder.connected_kiosks:
                                    self.app.interface_builder.mark_help_requested(computer_name)
                            self.app.root.after(0, mark_help)
                    
                    elif msg['type'] == 'kiosk_disconnect':
                        computer_name = msg['computer_name']
                        self.app.root.after(0, lambda n=computer_name: 
                            self.app.interface_builder.remove_kiosk(n))
                            
                except Exception as e:
                    print(f"Error in listen_for_messages: {e}")
                
    def send_hint(self, room_number, hint_text):
        message = {
            'type': 'hint',
            'room': room_number,
            'text': hint_text
        }
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))
        
    def send_room_assignment(self, computer_name, room_number):
        message = {
            'type': 'room_assignment',
            'room': room_number,
            'computer_name': computer_name
        }
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))

    def send_timer_command(self, computer_name, command, minutes=None):
        message = {
            'type': 'timer_command',
            'computer_name': computer_name,
            'command': command
        }
        if minutes is not None:
            message['minutes'] = minutes
        print(f"Sending timer command: {message}")  # Debug
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))

    # Add to NetworkBroadcastHandler class
    def send_video_command(self, computer_name, video_type, minutes):
        message = {
            'type': 'video_command',
            'computer_name': computer_name,
            'video_type': video_type,
            'minutes': minutes
        }
        print(f"Sending video command: {message}")  # Debug line
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))
    
    def send_reboot_signal(self, computer_name):
        """Send reboot signal to specific kiosk"""
        if computer_name not in self.app.kiosk_tracker.kiosk_assignments:
            print(f"Cannot reboot {computer_name}: no room assigned")
            return
            
        room_number = self.app.kiosk_tracker.kiosk_assignments[computer_name]
        if room_number not in self.room_ips:
            print(f"No IP configured for room {room_number}")
            return
            
        target_ip = self.room_ips[room_number]
        try:
            self.reboot_socket.sendto(b"reboot", (target_ip, self.REBOOT_PORT))
            print(f"Reboot signal sent to {computer_name} (Room {room_number}, IP: {target_ip})")
        except Exception as e:
            print(f"Failed to send reboot signal: {e}")