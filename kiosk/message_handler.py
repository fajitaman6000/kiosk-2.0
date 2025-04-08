print("[message_handler] Beginning imports ...")
from video_manager import VideoManager
from file_sync_config import SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE
import traceback
import time
import os
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
from qt_overlay import Overlay
from kiosk_file_downloader import KioskFileDownloader
import base64
print("[message_handler] Ending imports ...")

class MessageHandler:
    # How long to remember processed command IDs (in seconds)
    COMMAND_ID_TIMEOUT = 120

    def __init__(self, kiosk_app, video_manager):
        self.kiosk_app = kiosk_app
        self.video_manager = video_manager
        self.file_downloader = None  # Initialize later when we have the admin IP
        self.last_sync_id = None  # Track last sync ID
        self._last_admin_ip = None  # Track last admin IP to detect changes
        # Store recently processed command IDs to prevent duplicate execution
        self.processed_command_ids = {} # {command_id: timestamp}

    def _ensure_file_downloader(self, admin_ip):
        """Ensure we have a properly initialized file downloader with the correct admin IP."""
        try:
            if not admin_ip:
                print("[message handler] Error: No admin IP provided")
                return False

            # If IP changed or downloader not initialized, create new one
            if self.file_downloader is None or self._last_admin_ip != admin_ip:
                # Clean up old downloader if it exists
                if self.file_downloader:
                    print(f"[message handler] Stopping old file downloader (admin IP changed from {self._last_admin_ip} to {admin_ip})")
                    self.file_downloader.stop()
                    self.file_downloader = None

                print(f"[message handler] Creating new file downloader for admin IP: {admin_ip}")
                self.file_downloader = KioskFileDownloader(self.kiosk_app, admin_ip)
                self.file_downloader.start()
                self._last_admin_ip = admin_ip

            return True
        except Exception as e:
            print(f"[message handler] Error initializing file downloader: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _prune_processed_ids(self):
        """Removes old command IDs from the tracking dictionary."""
        now = time.time()
        ids_to_remove = [
            cmd_id for cmd_id, timestamp in self.processed_command_ids.items()
            if now - timestamp > self.COMMAND_ID_TIMEOUT
        ]
        for cmd_id in ids_to_remove:
            del self.processed_command_ids[cmd_id]
        # Optional: print(f"[message handler] Pruned {len(ids_to_remove)} old command IDs.")

    def handle_message(self, msg):
        """Handles incoming messages and delegates to specific methods."""

        # --- Idempotency Check ---
        command_id = msg.get('command_id')
        if command_id:
            self._prune_processed_ids() # Clean up old IDs periodically
            if command_id in self.processed_command_ids:
                print(f"[message handler] Ignoring duplicate command (ID: {command_id}, Type: {msg.get('type')})")
                # Still send ACK for the specific request_hash to stop server resends
                request_hash = msg.get('request_hash')
                if request_hash:
                    self.send_acknowledgment(request_hash)
                return # Stop processing this duplicate command
            else:
                # Record this command ID as processed
                self.processed_command_ids[command_id] = time.time()
        # --- End Idempotency Check ---

        if (msg['type'] != 'request_screenshot'):
            # Log only if it's not a duplicate we're ignoring (handled above)
            print(f"[message handler] Received message: {msg}")

        # Acknowledge the specific transmission attempt
        request_hash = msg.get('request_hash')
        if request_hash:
            self.send_acknowledgment(request_hash)

        try:
            # --- Message Type Handling (Logic remains largely the same) ---
            if msg['type'] == SYNC_MESSAGE_TYPE:
                target_computer = msg.get('computer_name')
                if target_computer not in ('all', self.kiosk_app.computer_name):
                    print(f"[message handler] Ignoring sync message intended for: {target_computer}")
                    return

                admin_ip = msg.get('admin_ip')
                sync_id = msg.get('sync_id') # Note: sync_id is separate from command_id

                if admin_ip:
                    if self._ensure_file_downloader(admin_ip):
                        print(f"[message handler] Initiating sync with admin at {admin_ip} (Sync ID: {sync_id}, Command ID: {command_id})")
                        self.last_sync_id = sync_id
                        self.file_downloader.request_sync()

                        confirm_msg = {
                            'type': 'sync_confirmation',
                            'computer_name': self.kiosk_app.computer_name,
                            'sync_id': sync_id,
                            'status': 'received'
                        }
                        self.kiosk_app.network.send_message(confirm_msg) # Use Kiosk's send, doesn't need command_id tracking

            elif msg['type'] == 'room_assignment' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Processing room assignment: {msg['room']} (Command ID: {command_id})")
                self.kiosk_app.assigned_room = msg['room']
                print("[message handler][DEBUG] Saving room assignment...")
                save_result = self.kiosk_app.room_persistence.save_room_assignment(msg['room'])
                print(f"[message handler][DEBUG] Save result: {save_result}")
                self.kiosk_app.start_time = time.time()
                self.kiosk_app.ui.hint_cooldown = False
                self.kiosk_app.ui.current_hint = None

                if hasattr(self.kiosk_app.ui, 'status_frame') and self.kiosk_app.ui.status_frame:
                    self.kiosk_app.ui.status_frame.delete('all')
                self.kiosk_app.ui.clear_all_labels()

                self.kiosk_app.audio_manager.current_music = None
                self.kiosk_app.root.after(0, lambda: self.kiosk_app.ui.setup_room_interface(msg['room']))

            elif msg['type'] == 'hint' and self.kiosk_app.assigned_room:
                if msg.get('room') == self.kiosk_app.assigned_room:
                    print(f"[message handler][DEBUG] Processing hint (Command ID: {command_id})")
                    if msg.get('has_image') and 'image_path' in msg:
                        image_path = os.path.join(os.path.dirname(__file__), msg['image_path'])
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as f:
                                image_data = f.read()
                                hint_data = {
                                    'text': msg.get('text', ''),
                                    'image': base64.b64encode(image_data).decode()
                                }
                        else:
                            print(f"[message handler] Error: Image file not found at {image_path}")
                            hint_data = msg.get('text', '')
                    else:
                        hint_data = msg.get('text', '')

                    self.kiosk_app.hints_received += 1
                    self.kiosk_app.hint_requested_flag = False
                    print(f"[message handler][Kiosk] handle_message: Received hint, clearing hint_requested_flag for room {self.kiosk_app.assigned_room}")
                    self.kiosk_app.root.after(0, lambda d=hint_data: self.kiosk_app.show_hint(d))

            elif msg['type'] == 'timer_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Processing timer command (Command ID: {command_id})")
                minutes = msg.get('minutes')
                command = msg['command']

                if minutes is not None:
                    minutes = float(minutes)
                    print(f"[message handler][DEBUG] Setting timer to {minutes} minutes")
                    if minutes > 45:
                        print("[message handler][DEBUG] New time exceeds 45 minutes - setting flag")
                        self.kiosk_app.time_exceeded_45 = True

                if command == "start" and not self.kiosk_app.room_started:
                    self.kiosk_app.room_started = True
                    print(f"[message handler][Kiosk] handle_message: Timer started, setting room_started to True for room {self.kiosk_app.assigned_room}")
                    if self.kiosk_app.assigned_room:
                        print(f"[message handler][DEBUG] Timer starting - playing background music for room: {self.kiosk_app.assigned_room}")
                        self.kiosk_app.audio_manager.play_background_music(self.kiosk_app.assigned_room)

                self.kiosk_app.timer.handle_command(command, minutes)

                if command == "start":
                    self.kiosk_app.hint_requested_flag = False
                    print(f"[message handler][Kiosk] handle_message: Timer started, clearing hint_requested_flag for room {self.kiosk_app.assigned_room}")

                self.kiosk_app._actual_help_button_update()

            elif msg['type'] == 'video_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Processing video command (Command ID: {command_id})")
                self.kiosk_app.play_video(msg['video_type'], msg['minutes'])

            elif msg['type'] == 'soundcheck' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler] soundcheck command received (Command ID: {command_id})")
                # Potentially add soundcheck logic here if needed

            elif msg['type'] == 'clear_hints' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Processing clear hints command (Command ID: {command_id})")
                self.kiosk_app.clear_hints()

            elif msg['type'] == 'play_sound' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Received play sound command (Command ID: {command_id})")
                sound_name = msg.get('sound_name')
                if sound_name:
                    self.kiosk_app.audio_manager.play_sound(sound_name)

            elif msg['type'] == 'audio_hint' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Received audio hint command (Command ID: {command_id})")
                audio_path = msg.get('audio_path')
                if audio_path:
                    self.kiosk_app.audio_manager.play_hint_audio(audio_path)

            elif msg['type'] == 'solution_video' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Received solution video command (Command ID: {command_id})")
                try:
                    room_folder = msg.get('room_folder')
                    video_filename = msg.get('video_filename')

                    if not room_folder or not video_filename:
                        print("[message handler] Error: Missing room_folder or video_filename in message")
                        return

                    video_path = os.path.join("video_solutions", room_folder, f"{video_filename}.mp4")
                    print(f"[message handler][DEBUG] Looking for solution video at: {video_path}")

                    if os.path.exists(video_path):
                        self.kiosk_app.hints_received += 1
                        print(f"[message handler][DEBUG] Setting up solution video interface: {video_path}")

                        hint_data = { 'text': 'Video Solution Received' }

                        self.kiosk_app.root.after(0, lambda d=hint_data: self.kiosk_app.show_hint(d, start_cooldown=False))
                        self.kiosk_app.root.after(0, lambda: self.kiosk_app.ui.show_video_solution(room_folder, video_filename))

                    else:
                        print(f"[message handler] Error: Solution video not found at {video_path}")

                except Exception as e:
                    print(f"[message handler] Error processing solution video command: {e}")
                    traceback.print_exc()

            elif msg['type'] == 'reset_kiosk' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Processing kiosk reset (Command ID: {command_id})")

                self.video_manager.force_stop()
                self.kiosk_app.timer.game_lost = False
                self.kiosk_app.timer.game_won = False
                self.kiosk_app.audio_manager.stop_all_audio()

                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    pygame.mixer.stop()

                if hasattr(self.kiosk_app.ui, 'video_solution_button') and self.kiosk_app.ui.video_solution_button:
                    self.kiosk_app.ui.video_solution_button.destroy()
                    self.kiosk_app.ui.video_solution_button = None
                if hasattr(self.kiosk_app.ui, 'stored_video_info'):
                    self.kiosk_app.ui.stored_video_info = None
                if hasattr(self.kiosk_app.ui, 'video_is_playing'):
                    self.kiosk_app.ui.video_is_playing = False

                print("[message handler][DEBUG] Resetting application state...")
                self.kiosk_app.time_exceeded_45 = False
                self.kiosk_app.hints_requested = 0
                self.kiosk_app.hints_received = 0
                self.kiosk_app.times_touched_screen = 0

                print("[message handler][DEBUG] Resetting UI hint state...")
                self.kiosk_app.ui.hint_cooldown = False
                self.kiosk_app.ui.current_hint = None
                self.kiosk_app.ui.stored_image_data = None
                if hasattr(self.kiosk_app.ui, 'image_button') and self.kiosk_app.ui.image_button:
                    self.kiosk_app.ui.image_button.destroy()
                    self.kiosk_app.ui.image_button = None
                if hasattr(self.kiosk_app.ui, 'fullscreen_image') and self.kiosk_app.ui.fullscreen_image:
                    self.kiosk_app.ui.fullscreen_image.destroy()
                    self.kiosk_app.ui.fullscreen_image = None

                print("[message handler][DEBUG] Clearing cooldown state...")
                if self.kiosk_app.ui.cooldown_after_id:
                    self.kiosk_app.root.after_cancel(self.kiosk_app.ui.cooldown_after_id)
                    self.kiosk_app.ui.cooldown_after_id = None

                self.kiosk_app.root.after(0, lambda: Overlay.hide())
                self.kiosk_app.root.after(0, lambda: Overlay.hide_gm_assistance())

                print("[message handler][DEBUG] Clearing UI elements...")
                if hasattr(self.kiosk_app.ui, 'status_frame') and self.kiosk_app.ui.status_frame:
                    self.kiosk_app.ui.status_frame.delete('all')
                    self.kiosk_app.ui.hide_status_frame()
                self.kiosk_app.ui.clear_all_labels()

                self.kiosk_app.root.after(0, lambda: self.kiosk_app.timer._delayed_qt_init())
                self.kiosk_app.room_started = False
                self.kiosk_app.auto_start = False

                def restore_ui():
                    if self.kiosk_app.assigned_room:
                        print("[message handler][DEBUG] Restoring room interface")
                        self.kiosk_app.ui.setup_room_interface(self.kiosk_app.assigned_room)
                        self.kiosk_app._actual_help_button_update()
                        print("[message handler][DEBUG] Kiosk reset complete")

                    self.kiosk_app.root.after(0, lambda: Overlay._check_game_loss_visibility(self.kiosk_app.timer.game_lost))
                    self.kiosk_app.root.after(0, lambda: Overlay._check_game_win_visibility(self.kiosk_app.timer.game_won))

                self.kiosk_app.root.after(100, restore_ui)

            elif msg['type'] == 'toggle_music_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Received toggle music command (Command ID: {command_id})")
                self.kiosk_app.audio_manager.toggle_music()

            elif msg['type'] == 'stop_video_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Received stop video command (Command ID: {command_id})")
                self.handle_stop_video_command() # Delegate to keep handle_message cleaner

            elif msg['type'] == 'toggle_auto_start' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler] Toggling auto start (Command ID: {command_id})")
                self.toggle_auto_start()

            elif msg['type'] == 'offer_assistance' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler] Received offer assistance command (Command ID: {command_id})")
                self.kiosk_app.audio_manager.play_sound("hint_received.mp3")
                self.kiosk_app.root.after(0, lambda: Overlay.show_gm_assistance())

            elif msg['type'] == 'victory' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler] Victory detected (Command ID: {command_id})")
                self.kiosk_app.timer.game_won = True
                self.kiosk_app.handle_game_win()

            elif msg['type'] == 'request_screenshot' and msg['computer_name'] == self.kiosk_app.computer_name:
                # This message likely doesn't need idempotency as much, but we'll process it
                # The command_id check already happened
                print(f"[message handler] Received request_screenshot command (Command ID: {command_id})")
                self.kiosk_app.take_screenshot_requested = True
                # Note: The ACK was already sent earlier.

        except Exception as e:
            print("[message handler][CRITICAL ERROR] Critical error in handle_message:")
            print(f"[message handler][CRITICAL ERROR] Error type: {type(e)}")
            print(f"[message handler][CRITICAL ERROR] Error message: {str(e)}")
            print(f"[message handler][CRITICAL ERROR] Failed message (if available): {msg}")
            traceback.print_exc()

    def send_acknowledgment(self, request_hash):
        """Sends an acknowledgment message for a specific transmission attempt."""
        ack_message = {
            'type': 'ack',
            'request_hash': request_hash
            # No command_id needed for an ACK message itself
        }
        # Use the kiosk's network send method, which doesn't add command_id or track ACKs for ACKs
        self.kiosk_app.network.send_message(ack_message)
        # print(f"[message handler] Sent acknowledgment for transmission hash: {request_hash}")

    def handle_stop_video_command(self):
        """Handles the 'stop_video_command' logic."""
        if self.video_manager:
            self.video_manager.stop_video()

    def toggle_auto_start(self):
        """Toggles the auto-start flag on the kiosk. Does not broadcast."""
        self.kiosk_app.auto_start = not self.kiosk_app.auto_start
        status = "enabled" if self.kiosk_app.auto_start else "disabled"
        print(f"[message handler] Auto-start {status}")