# network_broadcast_handler.py
import socket
import json
from threading import Thread
import uuid
import time

class NetworkBroadcastHandler:
    def __init__(self, app):
        self.app = app
        self.last_message = {}  # Initialize message cache
        self.running = True     # Add running flag
        self.pending_acknowledgments = {}  # {request_hash: (message, timestamp, computer_name, message_type)}
        self.ACK_TIMEOUT = 4  # seconds
        
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Increase the receive buffer size (to 65536, the max for UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
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

    def send_message_with_ack(self, message, computer_name):
        """Sends a message and tracks its acknowledgment."""
        request_hash = str(uuid.uuid4())
        message['request_hash'] = request_hash
        self.pending_acknowledgments[request_hash] = (message, time.time(), computer_name, message['type'])
        self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', 12346))
        print(f"[network broadcast handler]Sent message with hash {request_hash}: {message}")

    def resend_unacknowledged_messages(self):
        """Checks for and resends unacknowledged messages."""
        now = time.time()
        for request_hash, (original_message, timestamp, computer_name, message_type) in list(self.pending_acknowledgments.items()):
            if now - timestamp > self.ACK_TIMEOUT:
                print(f"[network broadcast handler]Resending message (type: {message_type}) to {computer_name} due to timeout. Original hash: {request_hash}")
                # Generate a NEW request hash for the resent message
                new_request_hash = str(uuid.uuid4())
                original_message['request_hash'] = new_request_hash  # Update the message
                self.pending_acknowledgments[new_request_hash] = (original_message, time.time(), computer_name, message_type)
                del self.pending_acknowledgments[request_hash] # Remove the old entry
                self.socket.sendto(json.dumps(original_message).encode(), ('255.255.255.255', 12346))
        
    def listen_for_messages(self):
        print("[network broadcast handler]Started listening for kiosks...")
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65536)
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
                        print(f"[network broadcast handler]Processing room change for {computer_name}, Previous room: {current_room}, New room: {room}")
                    
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
                    # if hasattr(self.app, 'sync_manager'):  # sync_manager no longer handles confirmations
                    #     self.app.sync_manager.handle_sync_confirmation(computer_name, sync_id)
                elif msg['type'] == 'sync_complete':  # NEW: Handle sync completion
                    computer_name = msg['computer_name']
                    print(f"[network broadcast handler] Received sync_complete from {computer_name}")
                    # You might want to log this, update UI, etc.  No need to remove
                    # anything from pending_acknowledgments; the 'ack' already did that.

                elif msg['type'] == 'sync_failed':  # NEW: Handle sync failure
                    computer_name = msg.get('computer_name')
                    reason = msg.get('reason', 'Unknown')
                    print(f"[network broadcast handler] Received sync_failed from {computer_name}, reason: {reason}")
                    # Log this, update UI to show an error, potentially retry, etc.
                
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

                elif msg['type'] == 'screenshot':
                    computer_name = msg['computer_name']
                    image_data = msg.get('image_data')
                    if computer_name and image_data:
                        # Pass the screenshot to the handler
                        if hasattr(self.app, 'screenshot_handler'):
                            self.app.screenshot_handler.handle_screenshot(computer_name, image_data)

                elif msg['type'] == 'ack':
                    received_hash = msg.get('request_hash')
                    if received_hash in self.pending_acknowledgments:
                        del self.pending_acknowledgments[received_hash]
                        print(f"[network broadcast handler]Acknowledgment received for hash: {received_hash}")
                    else:
                        print(f"[network broadcast handler]Received ack for unknown hash: {received_hash} (likely delayed)")
                            
            except Exception as e:
                if self.running:
                    print(f"[network broadcast handler]Error in listen_for_messages: {e}")

    def send_hint(self, room_number, hint_data):
        message = {
            'type': 'hint',
            'room': room_number,
            'text': hint_data.get('text', ''),
            'has_image': bool(hint_data.get('image_path')),
            'image_path': hint_data.get('image_path')
        }
        #Find the computer name to send to
        computer_name = None
        for k, v in self.app.kiosk_tracker.kiosk_assignments.items():
            if v == room_number:
                computer_name = k
        if computer_name:
            self.send_message_with_ack(message, computer_name)
        else:
            print(f"[network broadcast handler]Could not determine computer to send to (room {room_number}).")
            #still send, just don't track
                
    def send_room_assignment(self, computer_name, room_number):
        message = {
            'type': 'room_assignment',
            'room': room_number,
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)

    def send_timer_command(self, computer_name, command, minutes=None):
        message = {
            'type': 'timer_command',
            'computer_name': computer_name,
            'command': command
        }
        if minutes is not None:
            message['minutes'] = minutes
        self.send_message_with_ack(message, computer_name)

    def send_victory_message(self, room_number, computer_name):
        """Send a victory message."""
        message = {
            'type': 'victory',
            'room_number': room_number,
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)

    def send_video_command(self, computer_name, video_type, minutes):
        message = {
            'type': 'video_command',
            'computer_name': computer_name,
            'video_type': video_type,
            'minutes': minutes
        }
        self.send_message_with_ack(message, computer_name)
    
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

    def send_soundcheck_command(self, computer_name):
        message = {
                'type': 'soundcheck',
                'computer_name': computer_name
            }
        self.send_message_with_ack(message, computer_name)
    
    def send_clear_hints_command(self, computer_name):
        message = {
            'type': 'clear_hints',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)

    def send_play_sound_command(self, computer_name, sound_name):
        message = {
            'type': 'play_sound',
            'computer_name': computer_name,
            'sound_name': sound_name
        }
        self.send_message_with_ack(message, computer_name)

    def send_audio_hint_command(self, computer_name, audio_path):
        message = {
            'type': 'audio_hint',
            'computer_name': computer_name,
            'audio_path': audio_path
        }
        self.send_message_with_ack(message, computer_name)
    
    def send_solution_video_command(self, computer_name, room_folder, video_filename):
        message = {
            'type': 'solution_video',
            'computer_name': computer_name,
            'room_folder': room_folder,
            'video_filename': video_filename
        }
        self.send_message_with_ack(message, computer_name)
    
    def send_reset_kiosk_command(self, computer_name):
        message = {
            'type': 'reset_kiosk',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)

    def send_toggle_music_command(self, computer_name):
        message = {
            'type': 'toggle_music_command',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)
    
    def send_stop_video_command(self, computer_name):
        message = {
            'type': 'stop_video_command',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)
    
    def send_toggle_auto_start_command(self, computer_name):
        message = {
            'type': 'toggle_auto_start',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)
    
    def send_offer_assistance_command(self, computer_name):
        message = {
            'type': 'offer_assistance',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)
    
    def send_request_screenshot_command(self, computer_name):
        message = {
            'type': 'request_screenshot',
            'computer_name': computer_name
        }
        self.send_message_with_ack(message, computer_name)