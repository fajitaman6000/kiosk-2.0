# network_broadcast_handler.py
import socket
import json
from threading import Thread
import uuid
import time
# --- ADDED IMPORT ---
from file_sync_config import SYNC_MESSAGE_TYPE

class NetworkBroadcastHandler:
    def __init__(self, app):
        self.app = app
        self.last_message = {}  # Cache kiosk status messages
        self.running = True     # Flag to control listening thread
        # Tracks pending ACKs for specific transmission attempts
        # Structure: {(computer_name, message_type): {'hashes': {request_hash1, ...}, 'message': full_message_payload, 'timestamp': last_send_time, 'resend_count': count}}
        self.pending_acknowledgments = {}
        self.ACK_TIMEOUT = 6  # seconds before resend
        self.MAX_RESEND_ATTEMPTS = 3 # Max resends before giving up

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536) # Increase buffer
            self.socket.bind(('', 12345)) # Port for receiving from kiosks
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            self.reboot_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) # Separate socket for reboot signals
        except Exception as e:
            print(f"[network broadcast handler] Network Error: {e}")
            print("[network broadcast handler] This might be because:")
            print("[network broadcast handler] 1. Another program is using port 12345")
            print("[network broadcast handler] 2. You need to run as administrator")
            raise

        self.listen_thread = None

        # Room to IP mapping for reboot
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
        self.KIOSK_LISTEN_PORT = 12346 # Port kiosks listen on

    def start(self):
        """Starts the listening thread."""
        self.listen_thread = Thread(target=self.listen_for_messages, daemon=True)
        self.listen_thread.start()
        # Start the periodic resend check
        self.app.root.after(int(self.ACK_TIMEOUT * 1000 / 2), self.check_and_resend_loop) # Check every half-timeout interval

    def check_and_resend_loop(self):
        """Periodically checks for and resends unacknowledged messages."""
        if not self.running:
            return
        try:
            self.resend_unacknowledged_messages()
        except Exception as e:
            print(f"[network broadcast handler] Error during resend check: {e}")
        finally:
            # Schedule the next check
            self.app.root.after(int(self.ACK_TIMEOUT * 1000 / 2), self.check_and_resend_loop)


    def _send_tracked_message(self, message, computer_name):
        """Internal method to send a message, add tracking IDs, and manage ACKs."""
        # Ensure message has a command_id (should be added by the calling method)
        if 'command_id' not in message:
             print(f"[network broadcast handler] [WARNING] Message type {message.get('type')} sent without command_id!")
             # Optionally, add a default one here, though it's better if the caller does it
             # message['command_id'] = str(uuid.uuid4()) + "-autogen"

        # Generate a unique hash for THIS transmission attempt
        request_hash = str(uuid.uuid4())
        message['request_hash'] = request_hash

        message_type = message['type']
        key = (computer_name, message_type) # Key for tracking pending ACKs

        # Store or update the pending acknowledgment entry
        if key in self.pending_acknowledgments:
            # Add the hash for this new attempt to the existing entry
            self.pending_acknowledgments[key]['hashes'].add(request_hash)
            # Update the message payload in case details changed (though command_id should be stable)
            self.pending_acknowledgments[key]['message'] = message.copy() # Store the latest version
            self.pending_acknowledgments[key]['timestamp'] = time.time()
            # Reset resend_count if we're explicitly sending a *new* logical command of the same type
            # This logic might need refinement depending on how commands are issued.
            # For simplicity now, let's assume a new call to a send_ method implies a new logical command,
            # even if the type and target are the same. We rely on command_id for idempotency.
            # self.pending_acknowledgments[key]['resend_count'] = 0 # Reconsider this - might prematurely stop resends
        else:
            # Create a new entry for this computer/message_type combo
            self.pending_acknowledgments[key] = {
                'hashes': {request_hash},          # Store all active request_hashes for this command
                'message': message.copy(),         # Store the full message (includes command_id)
                'timestamp': time.time(),          # Timestamp of the *last* transmission attempt
                'resend_count': 0                  # Initialize resend counter
            }

        # Send the message
        try:
            self.socket.sendto(json.dumps(message).encode(), ('255.255.255.255', self.KIOSK_LISTEN_PORT))
            # Debug log for initial send
            # print(f"[network broadcast handler] Sent message (CmdID: {message.get('command_id')}, ReqHash: {request_hash}): {message['type']} to {computer_name}")
        except Exception as e:
            print(f"[network broadcast handler] Error sending message: {e}")
            # Consider removing from pending if send fails immediately? Or let resend handle it?
            # For now, let resend try again.

    def resend_unacknowledged_messages(self):
        """Checks for and resends messages whose ACK hasn't been received."""
        now = time.time()
        # Iterate over a copy of keys because we might modify the dict during iteration
        for key in list(self.pending_acknowledgments.keys()):
            if key not in self.pending_acknowledgments: # Check if it was removed by an ACK in the meantime
                continue

            data = self.pending_acknowledgments[key]
            computer_name, message_type = key

            if now - data['timestamp'] > self.ACK_TIMEOUT:
                if data['resend_count'] < self.MAX_RESEND_ATTEMPTS:
                    data['resend_count'] += 1 # Increment resend counter

                    # --- Resend Logic ---
                    # Use the *original* command_id stored in the message
                    original_message = data['message']
                    original_command_id = original_message.get('command_id')

                    # Generate a *NEW* request_hash for this specific resend attempt
                    new_request_hash = str(uuid.uuid4())

                    # Update the message payload ONLY with the new request_hash
                    message_to_resend = original_message.copy()
                    message_to_resend['request_hash'] = new_request_hash

                    # Update the tracking data
                    data['hashes'].add(new_request_hash) # Add the new hash to the set we're waiting for
                    data['timestamp'] = now # Update timestamp for the next timeout check

                    print(f"[network broadcast handler] Resending message (CmdID: {original_command_id}, Type: {message_type}, Attempt {data['resend_count']}/{self.MAX_RESEND_ATTEMPTS}) to {computer_name}. New ReqHash: {new_request_hash}")

                    try:
                        # Send the updated message
                        self.socket.sendto(json.dumps(message_to_resend).encode(), ('255.255.255.255', self.KIOSK_LISTEN_PORT))
                    except Exception as e:
                         print(f"[network broadcast handler] Error resending message: {e}")
                         # Keep it in pending, maybe the network will recover

                else:
                    # Max resend attempts reached
                    original_command_id = data['message'].get('command_id')
                    print(f"[network broadcast handler] Giving up on message (CmdID: {original_command_id}, Type: {message_type}) to {computer_name} after {self.MAX_RESEND_ATTEMPTS} resend attempts. Unacked ReqHashes: {data['hashes']}")
                    # Remove from pending acknowledgments
                    del self.pending_acknowledgments[key]
                    # Optionally: Add UI notification or logging about the failure

    def listen_for_messages(self):
        """Listens for incoming messages from kiosks."""
        print("[network broadcast handler] Started listening for kiosks...")
        while self.running:
            try:
                data, addr = self.socket.recvfrom(65536) # Use large buffer size
                msg = json.loads(data.decode())

                # Store sender address (useful for potential direct replies, though not used currently)
                msg['_sender_addr'] = addr

                # Process based on message type
                msg_type = msg.get('type')

                # --- Handle ACKs ---
                if msg_type == 'ack':
                    received_hash = msg.get('request_hash')
                    if received_hash:
                        ack_handled = False
                        # Iterate through ALL pending acknowledgments to find the matching hash
                        for key, data in list(self.pending_acknowledgments.items()):
                             # Check if the received hash is in the set of hashes for this command
                            if received_hash in data['hashes']:
                                # print(f"[network broadcast handler] Acknowledgment received for ReqHash: {received_hash} (CmdID: {data['message'].get('command_id')}, Type: {key[1]}, Kiosk: {key[0]})")
                                data['hashes'].remove(received_hash) # Remove the specific hash that was acknowledged
                                # If ALL hashes for this logical command instance are now acknowledged, remove the whole entry
                                if not data['hashes']:
                                    # print(f"[network broadcast handler] All attempts for CmdID {data['message'].get('command_id')} acknowledged. Removing entry for {key}.")
                                    del self.pending_acknowledgments[key]
                                ack_handled = True
                                break # Stop searching once the hash is found and handled
                        # if not ack_handled:
                        #     # This can happen if the ACK arrives very late, after we've given up resending
                        #     print(f"[network broadcast handler] Received ack for unknown/expired ReqHash: {received_hash}")
                    else:
                        print("[network broadcast handler] Received ACK message without request_hash")

                # --- Handle Kiosk Status Updates ---
                elif msg_type == 'kiosk_announce':
                    computer_name = msg.get('computer_name')
                    if computer_name:
                        # Cache the latest status message to reduce redundant processing/logging if needed
                        last_msg = self.last_message.get(computer_name, {})
                        if msg != last_msg: # Basic check if content changed
                            self.last_message[computer_name] = msg.copy()
                            # Log room changes
                            room = msg.get('room')
                            current_room = self.app.kiosk_tracker.kiosk_assignments.get(computer_name)
                            if room != current_room:
                                print(f"[network broadcast handler] Processing room change for {computer_name}, Previous room: {current_room}, New room: {room}")

                        # Update kiosk tracker and UI
                        self.app.kiosk_tracker.update_kiosk_stats(computer_name, msg)
                        self.app.root.after(0, lambda cn=computer_name:
                            self.app.interface_builder.add_kiosk_to_ui(cn)) # Ensure UI element exists
                        if msg.get('room') is not None:
                           self.app.kiosk_tracker.kiosk_assignments[computer_name] = msg['room']
                           if hasattr(self.app.interface_builder, 'update_kiosk_display'):
                                self.app.interface_builder.update_kiosk_display(computer_name) # Update display details


                # --- Handle Sync Confirmations/Completions/Failures (Sent by Kiosk Downloader) ---
                # These are informational, no ACK/resend needed *from here* for these specific messages
                elif msg_type == 'sync_confirmation':
                    computer_name = msg.get('computer_name')
                    sync_id = msg.get('sync_id')
                    status = msg.get('status')
                    print(f"[network broadcast handler] Received sync_confirmation from {computer_name} - SyncID: {sync_id}, Status: {status}")
                    # Update UI or logs if needed

                elif msg_type == 'sync_complete':
                    computer_name = msg.get('computer_name')
                    sync_id = msg.get('sync_id') # Kiosk should include this
                    print(f"[network broadcast handler] Received sync_complete from {computer_name} - SyncID: {sync_id}")
                    # Update UI or logs

                elif msg_type == 'sync_failed':
                    computer_name = msg.get('computer_name')
                    sync_id = msg.get('sync_id') # Kiosk should include this
                    reason = msg.get('reason', 'Unknown')
                    print(f"[network broadcast handler] Received sync_failed from {computer_name} - SyncID: {sync_id}, Reason: {reason}")
                    # Update UI or logs

                # --- Handle Help Requests ---
                elif msg_type == 'help_request':
                    computer_name = msg.get('computer_name')
                    if computer_name in self.app.interface_builder.connected_kiosks:
                        self.app.kiosk_tracker.add_help_request(computer_name)
                        def mark_help(): # Closure to capture computer_name
                            if computer_name in self.app.interface_builder.connected_kiosks:
                                self.app.interface_builder.mark_help_requested(computer_name)
                        self.app.root.after(0, mark_help) # Schedule UI update on main thread

                # --- Handle Intro Video Completion ---
                elif msg_type == 'intro_video_completed':
                    computer_name = msg['computer_name']
                    print(f"[network broadcast handler] Received intro video complete signal from: {computer_name}")
                    self.app.root.after(0, lambda cn=computer_name: self.app.interface_builder.handle_intro_video_complete(cn))

                # --- Handle GM Assistance Acceptance ---
                elif msg_type == 'gm_assistance_accepted':
                    computer_name = msg['computer_name']
                    room = self.app.kiosk_tracker.kiosk_assignments.get(computer_name, "Unknown Room")
                    print(f"[network broadcast handler] GM assistance accepted by: {computer_name} (Room {room})")
                    self.app.root.after(0, lambda cn=computer_name: self.app.interface_builder.handle_gm_assistance_accepted(cn))

                # --- Handle Kiosk Disconnect ---
                elif msg_type == 'kiosk_disconnect':
                    computer_name = msg['computer_name']
                    print(f"[network broadcast handler] Kiosk disconnected: {computer_name}")
                    if computer_name in self.last_message:
                        del self.last_message[computer_name]
                    # Remove any pending ACKs for this kiosk
                    keys_to_remove = [k for k in self.pending_acknowledgments if k[0] == computer_name]
                    for k in keys_to_remove:
                         print(f"[network broadcast handler] Clearing pending ACKs for disconnected kiosk {computer_name} (Type: {k[1]})")
                         del self.pending_acknowledgments[k]
                    # Update UI
                    self.app.root.after(0, lambda n=computer_name:
                        self.app.interface_builder.remove_kiosk(n))

                # --- Handle Screenshots ---
                elif msg_type == 'screenshot':
                    computer_name = msg['computer_name']
                    image_data = msg.get('image_data')
                    if computer_name and image_data:
                        if hasattr(self.app, 'screenshot_handler'):
                            self.app.screenshot_handler.handle_screenshot(computer_name, image_data)

                # --- Other message types can be added here ---

            except json.JSONDecodeError:
                print(f"[network broadcast handler] Received invalid JSON data from {addr}")
            except Exception as e:
                if self.running: # Avoid errors during shutdown
                    print(f"[network broadcast handler] Error in listen_for_messages: {e}")
                    import traceback
                    traceback.print_exc() # Print full traceback for debugging

    def stop(self):
        """Stops the listening thread and closes sockets."""
        self.running = False
        # Send a dummy message to self to unblock recvfrom
        try:
            self.socket.sendto(b'{}', ('127.0.0.1', 12345))
        except Exception:
            pass # Ignore errors during shutdown
        if self.listen_thread:
            self.listen_thread.join(timeout=1.0) # Wait briefly for thread to exit
        if self.socket:
            self.socket.close()
        if self.reboot_socket:
            self.reboot_socket.close()
        print("[network broadcast handler] Network handler stopped.")


    # --- Command Sending Methods ---
    # All these methods now generate a command_id and call _send_tracked_message

    def send_hint(self, room_number, hint_data):
        """Sends a hint message to the appropriate kiosk."""
        computer_name = None
        for k, v in self.app.kiosk_tracker.kiosk_assignments.items():
            if v == room_number:
                computer_name = k
                break
        if computer_name:
            message = {
                'type': 'hint',
                'command_id': str(uuid.uuid4()), # Generate unique ID for this command instance
                'room': room_number,
                'text': hint_data.get('text', ''),
                'has_image': bool(hint_data.get('image_path')),
                'image_path': hint_data.get('image_path'),
                'computer_name': computer_name # Target specific computer
            }
            self._send_tracked_message(message, computer_name)
        else:
            print(f"[network broadcast handler] Could not find computer for room {room_number} to send hint.")

    def send_room_assignment(self, computer_name, room_number):
        """Assigns a room to a specific kiosk."""
        message = {
            'type': 'room_assignment',
            'command_id': str(uuid.uuid4()),
            'room': room_number,
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_timer_command(self, computer_name, command, minutes=None):
        """Sends a timer command (start, stop, pause, set) to a kiosk."""
        message = {
            'type': 'timer_command',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name,
            'command': command
        }
        if minutes is not None:
            message['minutes'] = minutes
        self._send_tracked_message(message, computer_name)

    def send_victory_message(self, room_number, computer_name):
        """Sends a victory message to a kiosk."""
        message = {
            'type': 'victory',
            'command_id': str(uuid.uuid4()),
            'room_number': room_number, # Keep for context if needed
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_video_command(self, computer_name, video_type, minutes):
        """Sends a command to play a specific video (intro, outro)."""
        message = {
            'type': 'video_command',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name,
            'video_type': video_type,
            'minutes': minutes
        }
        self._send_tracked_message(message, computer_name)

    def send_soundcheck_command(self, computer_name):
        """Sends a soundcheck command to a kiosk."""
        message = {
            'type': 'soundcheck',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_clear_hints_command(self, computer_name):
        """Sends a command to clear hints on the kiosk."""
        message = {
            'type': 'clear_hints',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_play_sound_command(self, computer_name, sound_name):
        """Sends a command to play a specific sound effect."""
        message = {
            'type': 'play_sound',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name,
            'sound_name': sound_name
        }
        self._send_tracked_message(message, computer_name)

    def send_audio_hint_command(self, computer_name, audio_path):
        """Sends a command to play an audio hint."""
        message = {
            'type': 'audio_hint',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name,
            'audio_path': audio_path
        }
        self._send_tracked_message(message, computer_name)

    def send_solution_video_command(self, computer_name, room_folder, video_filename):
        """Sends a command to display a solution video."""
        message = {
            'type': 'solution_video',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name,
            'room_folder': room_folder,
            'video_filename': video_filename
        }
        self._send_tracked_message(message, computer_name)

    def send_reset_kiosk_command(self, computer_name):
        """Sends a command to reset the kiosk state."""
        message = {
            'type': 'reset_kiosk',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_toggle_music_command(self, computer_name):
        """Sends a command to toggle background music."""
        message = {
            'type': 'toggle_music_command',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_stop_video_command(self, computer_name):
        """Sends a command to stop any currently playing video."""
        message = {
            'type': 'stop_video_command',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_toggle_auto_start_command(self, computer_name):
        """Sends a command to toggle the auto-start feature on the kiosk."""
        message = {
            'type': 'toggle_auto_start',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_offer_assistance_command(self, computer_name):
        """Sends a command offering GM assistance to the kiosk."""
        message = {
            'type': 'offer_assistance',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    def send_request_screenshot_command(self, computer_name):
        """Sends a command requesting a screenshot from the kiosk."""
        message = {
            'type': 'request_screenshot',
            'command_id': str(uuid.uuid4()),
            'computer_name': computer_name
        }
        self._send_tracked_message(message, computer_name)

    # --- Non-Tracked Commands (like Reboot) ---
    # Reboot uses a different mechanism (direct UDP, no ACK needed/expected)
    def send_reboot_signal(self, computer_name):
        """Sends a direct UDP reboot signal (no ACK tracking)."""
        if computer_name not in self.app.kiosk_tracker.kiosk_assignments:
            print(f"[network broadcast handler] Cannot reboot {computer_name}: no room assigned")
            return

        room_number = self.app.kiosk_tracker.kiosk_assignments[computer_name]
        if room_number not in self.room_ips:
            print(f"[network broadcast handler] No IP configured for room {room_number} to send reboot signal.")
            return

        target_ip = self.room_ips[room_number]
        try:
            # Send via the dedicated reboot socket
            self.reboot_socket.sendto(b"reboot", (target_ip, self.REBOOT_PORT))
            print(f"[network broadcast handler] Reboot signal sent to {computer_name} (Room {room_number}, IP: {target_ip})")
        except Exception as e:
            print(f"[network broadcast handler] Failed to send reboot signal to {target_ip}:{self.REBOOT_PORT}: {e}")

    # --- File Sync Initiation ---
    # This sends a SYNC message which is also tracked for ACK/Resend
    def send_sync_command(self, computer_name, admin_ip):
        """Sends a command to initiate file sync with the admin server."""
        sync_id = str(uuid.uuid4()) # Unique ID for this sync operation
        message = {
            'type': SYNC_MESSAGE_TYPE, # Use constant from config
            'command_id': str(uuid.uuid4()), # Unique ID for this command message
            'computer_name': computer_name, # Can be 'all' or specific name
            'admin_ip': admin_ip,
            'sync_id': sync_id # Specific ID for the sync process itself
        }
        # Target 'all' means broadcast, otherwise target specific computer
        # Track based on the intended recipient ('all' or specific name)
        target_recipient = 'all' if computer_name == 'all' else computer_name
        print(f"[network broadcast handler] Sending SYNC command to {target_recipient} (Admin IP: {admin_ip}, SyncID: {sync_id})")
        # Even if sending to 'all', we track it under the key ('all', SYNC_MESSAGE_TYPE)
        self._send_tracked_message(message, target_recipient)