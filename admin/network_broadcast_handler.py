# network_broadcast_handler.py
import socket
import json
from threading import Thread

class NetworkBroadcastHandler:
    def __init__(self, app):
        self.app = app
        self.last_message = {}  # Initialize message cache
        self.running = True     # Add running flag
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind(('', 12345))
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            
            # Create separate socket for reboot signals
            self.reboot_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as e:
            print(f"[network broadcast handler]Network Error: {e}")
            print("[network broadcast handler]This might be because:")
            print("[network broadcast handler]1. Another program is using port 12345")
            print("[network broadcast handler]2. You need to run as administrator")
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
        print("[network broadcast handler]Started listening for kiosks...")
        while self.running:
            try:
                data, addr = self.socket.recvfrom(1024)
                msg = json.loads(data.decode())
                
                # Store sender address with message
                msg['_sender_addr'] = addr
                
                # Only print if message content has changed
                computer_name = msg.get('computer_name')
                if computer_name:
                    last_msg = self.last_message.get(computer_name, {})
                    if msg != last_msg:
                        self.last_message[computer_name] = msg.copy()
                
                if msg['type'] == 'kiosk_announce':
                    computer_name = msg['computer_name']
                    room = msg.get('room')
                    
                    # Only print room assignment changes
                    current_room = self.app.kiosk_tracker.kiosk_assignments.get(computer_name)
                    if room != current_room:
                        print(f"[network broadcast handler]Processing room change for {computer_name}:")
                        print(f"[network broadcast handler]Previous room: {current_room}")
                        print(f"[network broadcast handler]New room: {room}")
                    
                    if room is not None:
                        self.app.kiosk_tracker.kiosk_assignments[computer_name] = room
                        if hasattr(self.app.interface_builder, 'update_kiosk_display'):
                            self.app.interface_builder.update_kiosk_display(computer_name)
                    
                    self.app.kiosk_tracker.update_kiosk_stats(computer_name, msg)
                    self.app.root.after(0, lambda cn=computer_name: 
                        self.app.interface_builder.add_kiosk_to_ui(cn))
                    
                elif msg['type'] == 'sync_confirmation':
                    computer_name = msg['computer_name']
                    sync_id = msg.get('sync_id')
                    status = msg.get('status')
                    print(f"[network broadcast handler] Received sync confirmation from {computer_name} - Status: {status}")
                    if hasattr(self.app, 'sync_manager'):
                        self.app.sync_manager.handle_sync_confirmation(computer_name, sync_id)
                
                elif msg['type'] == 'help_request':
                    computer_name = msg['computer_name']
                    if computer_name in self.app.interface_builder.connected_kiosks:
                        self.app.kiosk_tracker.add_help_request(computer_name)
                        def mark_help():
                            if computer_name in self.app.interface_builder.connected_kiosks:
                                self.app.interface_builder.mark_help_requested(computer_name)
                        self.app.root.after(0, mark_help)
                
                elif msg['type'] == 'intro_video_completed':
                    computer_name = msg['computer_name']
                    print(f"[network broadcast handler]Received intro video complete signal from: {computer_name} and passing signal to interface builder")
                    self.app.root.after(0, lambda: self.app.interface_builder.handle_intro_video_complete(computer_name))

                elif msg['type'] == 'gm_assistance_accepted':
                    computer_name = msg['computer_name']
                    print(f"[network broadcast handler]GM assistance accepted by: {computer_name}")
                    # Call the new handler method
                    self.app.interface_builder.handle_gm_assistance_accepted(computer_name)
                    print(f"[network broadcast handler]Room {self.app.kiosk_tracker.kiosk_assignments.get(computer_name)} accepted GM assistance")

                elif msg['type'] == 'kiosk_disconnect':
                    computer_name = msg['computer_name']
                    if computer_name in self.last_message:
                        del self.last_message[computer_name]
                    self.app.root.after(0, lambda n=computer_name: 
                        self.app.interface_builder.remove_kiosk(n))
                            
            except Exception as e:
                if self.running:
                    print(f"[network broadcast handler]Error in listen_for_messages: {e}")
                
    def send_hint(self, room_number, hint_data):
        """
        Send a hint to a specific room.
        
        Args:
            room_number (int): The room number to send to
            hint_data (dict): Dictionary containing 'text' and optional 'image_path' keys
        """
        print("[network broadcast handler]\n=== Sending Hint ===")
        
        # Construct the message
        message = {
            'type': 'hint',
            'room': room_number,
            'text': hint_data.get('text', ''),
            'has_image': bool(hint_data.get('image_path')),
            'image_path': hint_data.get('image_path')
        }
        
        print(f"[network broadcast handler]Sending hint message with text: {message['text']}")
        if message['has_image']:
            print(f"[network broadcast handler]Including image path: {message['image_path']}")
        
        # Convert to JSON and send
        try:
            encoded_message = json.dumps(message).encode()
            print("[network broadcast handler]Sending hint message...")
            self.socket.sendto(encoded_message, ('255.255.255.255', 12346))
            print(f"[network broadcast handler]Hint sent to room {room_number}")
            
        except Exception as e:
            print(f"[network broadcast handler]Failed to send hint: {e}")
            import traceback
            traceback.print_exc()
        
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
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))

    def send_video_command(self, computer_name, video_type, minutes):
        message = {
            'type': 'video_command',
            'computer_name': computer_name,
            'video_type': video_type,
            'minutes': minutes
        }
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))
    
    def send_reboot_signal(self, computer_name):
        if computer_name not in self.app.kiosk_tracker.kiosk_assignments:
            print(f"[network broadcast handler]Cannot reboot {computer_name}: no room assigned")
            return
            
        room_number = self.app.kiosk_tracker.kiosk_assignments[computer_name]
        if room_number not in self.room_ips:
            print(f"[network broadcast handler]No IP configured for room {room_number}")
            return
            
        target_ip = self.room_ips[room_number]
        try:
            self.reboot_socket.sendto(b"reboot", (target_ip, self.REBOOT_PORT))
            print(f"[network broadcast handler]Reboot signal sent to {computer_name} (Room {room_number}, IP: {target_ip})")
        except Exception as e:
            print(f"[network broadcast handler]Failed to send reboot signal: {e}")