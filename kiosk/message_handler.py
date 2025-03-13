from video_manager import VideoManager
from file_sync_config import SYNC_MESSAGE_TYPE, RESET_MESSAGE_TYPE
import traceback
import time
import os
import pygame
from qt_overlay import Overlay
from kiosk_file_downloader import KioskFileDownloader
import base64

class MessageHandler:
    def __init__(self, kiosk_app, video_manager):
        self.kiosk_app = kiosk_app
        self.video_manager = video_manager
        self.file_downloader = None  # Initialize later when we have the admin IP
        self.last_sync_id = None  # Track last sync ID
        self._last_admin_ip = None  # Track last admin IP to detect changes

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

    def handle_message(self, msg):
        """Handles incoming messages and delegates to specific methods."""

        if (msg['type'] != 'request_screenshot'):
            print(f"[message handler]Received message: {msg}")

        request_hash = msg.get('request_hash')
        if request_hash:
            self.send_acknowledgment(request_hash)

        try:
            if msg['type'] == SYNC_MESSAGE_TYPE:
                # Only process sync message if it's meant for this kiosk or is a broadcast message
                target_computer = msg.get('computer_name')
                if target_computer not in ('all', self.kiosk_app.computer_name):
                    print(f"[message handler] Ignoring sync message intended for: {target_computer}")
                    return

                admin_ip = msg.get('admin_ip')
                sync_id = msg.get('sync_id')

                if admin_ip:
                    if self._ensure_file_downloader(admin_ip):
                        # Request sync and store sync ID
                        print(f"[message handler] Initiating sync with admin at {admin_ip}")
                        self.last_sync_id = sync_id
                        self.file_downloader.request_sync()

                        # Send confirmation immediately that we received the sync request
                        confirm_msg = {
                            'type': 'sync_confirmation',
                            'computer_name': self.kiosk_app.computer_name,
                            'sync_id': sync_id,
                            'status': 'received'
                        }
                        self.kiosk_app.network.send_message(confirm_msg)

            if msg['type'] == 'room_assignment' and msg['computer_name'] == self.kiosk_app.computer_name:
                print(f"[message handler][DEBUG] Processing room assignment: {msg['room']}")
                self.kiosk_app.assigned_room = msg['room']
                print("[message handler][DEBUG] Saving room assignment...")
                save_result = self.kiosk_app.room_persistence.save_room_assignment(msg['room'])
                print(f"[message handler][DEBUG] Save result: {save_result}")
                self.kiosk_app.start_time = time.time()
                self.kiosk_app.ui.hint_cooldown = False
                self.kiosk_app.ui.current_hint = None

                # Safely clear UI elements
                if hasattr(self.kiosk_app.ui, 'status_frame') and self.kiosk_app.ui.status_frame:
                    self.kiosk_app.ui.status_frame.delete('all')
                self.kiosk_app.ui.clear_all_labels()

                # --- MUSIC RELOADING LOGIC ---
                if self.kiosk_app.assigned_room:
                    room_name = self.kiosk_app.audio_manager.get_room_music_name(self.kiosk_app.assigned_room)
                    if room_name:
                        music_name = room_name.lower().replace(" ", "_") + ".mp3"
                        music_path = os.path.join(self.kiosk_app.audio_manager.music_dir, music_name)
                        if os.path.exists(music_path):
                            self.kiosk_app.audio_manager.current_music = music_name
                            print(f"[message handler] Updated current_music to: {music_name}")
                        else:
                            print(f"[message handler] Music file not found: {music_path}")
                            self.kiosk_app.audio_manager.current_music = None  # Clear if not found
                    else:
                        print(f"[message handler] Could not determine music for room: {self.kiosk_app.assigned_room}")
                        self.kiosk_app.audio_manager.current_music = None #Clear if not found
                else:
                    print("[message handler] No room assigned, cannot load music.")
                    self.kiosk_app.audio_manager.current_music = None #Clear if not found

                self.kiosk_app.root.after(0, lambda: self.kiosk_app.ui.setup_room_interface(msg['room']))

            elif msg['type'] == 'hint' and self.kiosk_app.assigned_room:
                if msg.get('room') == self.kiosk_app.assigned_room:
                    # Prepare hint data
                    if msg.get('has_image') and 'image_path' in msg:
                        # Construct full path from kiosk directory
                        image_path = os.path.join(os.path.dirname(__file__), msg['image_path'])
                        if os.path.exists(image_path):
                            with open(image_path, 'rb') as f:
                                image_data = f.read()
                                hint_data = {
                                    'text': msg.get('text', ''),
                                    'image': base64.b64encode(image_data).decode()
                                }
                        else:
                            print(f"[message handler]Error: Image file not found at {image_path}")
                            hint_data = msg.get('text', '')
                    else:
                        hint_data = msg.get('text', '')

                    self.kiosk_app.hints_received += 1

                    # Clear hint flag after hint is received
                    self.kiosk_app.hint_requested_flag = False
                    print(f"[message handler][Kiosk] handle_message: Received hint, clearing hint_requested_flag for room {self.kiosk_app.assigned_room}")
                    self.kiosk_app.root.after(0, lambda d=hint_data: self.kiosk_app.show_hint(d))

            elif msg['type'] == 'timer_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Processing timer command")
                minutes = msg.get('minutes')
                command = msg['command']

                # Update time_exceeded_45 flag if timer is being set above 45
                if minutes is not None:
                    minutes = float(minutes)
                    print(f"[message handler][DEBUG] Setting timer to {minutes} minutes")
                    if minutes > 45:
                        print("[message handler][DEBUG] New time exceeds 45 minutes - setting flag")
                        self.kiosk_app.time_exceeded_45 = True

                # Start background music when timer starts
                room_names = {
                    2: "morning_after",
                    1: "casino_heist",
                    5: "haunted_manor",
                    4: "zombie_outbreak",
                    6: "time_machine",
                    5: "atlantis_rising",
                    3: "wizard_trials"
                }

                # Start playing background music when timer starts, only if room has NOT started
                if command == "start" and not self.kiosk_app.room_started:  # Correctly check if room is NOT started
                    self.kiosk_app.room_started = True  # Set the flag to true immediately when the room starts
                    print(f"[message handler][Kiosk] handle_message: Timer started, setting room_started to True for room {self.kiosk_app.assigned_room}")
                    if self.kiosk_app.assigned_room and isinstance(self.kiosk_app.assigned_room, int):
                        room_name = room_names.get(self.kiosk_app.assigned_room)
                        if room_name:
                            print(f"[message handler][DEBUG] Timer starting - playing background music for room: {room_name}")
                            self.kiosk_app.audio_manager.play_background_music(room_name)

                # Handle the timer command
                self.kiosk_app.timer.handle_command(command, minutes)

                # Set hint_requested_flag to False when timer starts
                if command == "start":
                    self.kiosk_app.hint_requested_flag = False
                    print(f"[message handler][Kiosk] handle_message: Timer started, clearing hint_requested_flag for room {self.kiosk_app.assigned_room}")

                # Update help button state directly after command
                self.kiosk_app._actual_help_button_update()

            elif msg['type'] == 'video_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                self.kiosk_app.play_video(msg['video_type'], msg['minutes'])

            elif msg['type'] == 'soundcheck' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler]soundcheck command received")

            elif msg['type'] == 'clear_hints' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Processing clear hints command")
                self.kiosk_app.clear_hints()

            elif msg['type'] == 'play_sound' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Received play sound command")
                sound_name = msg.get('sound_name')
                if sound_name:
                    self.kiosk_app.audio_manager.play_sound(sound_name)

            elif msg['type'] == 'audio_hint' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Received audio hint command")
                audio_path = msg.get('audio_path')
                if audio_path:
                    self.kiosk_app.audio_manager.play_hint_audio(audio_path)

            elif msg['type'] == 'solution_video' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Received solution video command")
                try:
                    room_folder = msg.get('room_folder')
                    video_filename = msg.get('video_filename')

                    if not room_folder or not video_filename:
                        print("[message handler]Error: Missing room_folder or video_filename in message")
                        return

                    video_path = os.path.join("video_solutions", room_folder, f"{video_filename}.mp4")
                    print(f"[message handler][DEBUG] Looking for solution video at: {video_path}")

                    if os.path.exists(video_path):
                        self.kiosk_app.hints_received += 1
                        print(f"[message handler][DEBUG] Setting up solution video interface: {video_path}")

                        # Create hint-style message for video solution
                        hint_data = {
                            'text': 'Video Solution Received',  # This will show in the hint text box
                        }

                        # Show hint first, then show video interface
                        self.kiosk_app.root.after(0, lambda d=hint_data: self.kiosk_app.show_hint(d, start_cooldown=False))
                        self.kiosk_app.root.after(0, lambda: self.kiosk_app.ui.show_video_solution(room_folder, video_filename))  # Call this after the hint

                    else:
                        print(f"[message handler]Error: Solution video not found at {video_path}")

                except Exception as e:
                    print(f"[message handler]Error processing solution video command: {e}")
                    traceback.print_exc()

            elif msg['type'] == 'reset_kiosk' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Processing kiosk reset")

                # --- Use force_stop ---
                self.video_manager.force_stop()

                # Reset game_lost flag:
                self.kiosk_app.timer.game_lost = False
                # Reset game_won flag:
                self.kiosk_app.timer.game_won = False

                # Stop background music and any other audio
                self.kiosk_app.audio_manager.stop_all_audio()

                # Ensure pygame mixer is fully reset
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    pygame.mixer.stop()  # Stop all sound channels

                # Reset video-related UI state in the kiosk app's UI
                if hasattr(self.kiosk_app.ui, 'video_solution_button') and self.kiosk_app.ui.video_solution_button:
                    self.kiosk_app.ui.video_solution_button.destroy()
                    self.kiosk_app.ui.video_solution_button = None
                if hasattr(self.kiosk_app.ui, 'stored_video_info'):
                    self.kiosk_app.ui.stored_video_info = None
                if hasattr(self.kiosk_app.ui, 'video_is_playing'):
                    self.kiosk_app.ui.video_is_playing = False

                # Reset application state
                print("[message handler][DEBUG] Resetting application state...")
                self.kiosk_app.time_exceeded_45 = False
                self.kiosk_app.hints_requested = 0
                self.kiosk_app.hints_received = 0
                self.kiosk_app.times_touched_screen = 0

                # Reset UI hint-related state
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

                # Cancel any existing cooldown timer and hide overlay
                print("[message handler][DEBUG] Clearing cooldown state...")
                if self.kiosk_app.ui.cooldown_after_id:
                    self.kiosk_app.root.after_cancel(self.kiosk_app.ui.cooldown_after_id)
                    self.kiosk_app.ui.cooldown_after_id = None

                # Hide and Clear Overlay
                self.kiosk_app.root.after(0, lambda: Overlay.hide())

                # Hide GM assistance overlay specifically
                self.kiosk_app.root.after(0, lambda: Overlay.hide_gm_assistance())

                # Clear UI elements safely
                print("[message handler][DEBUG] Clearing UI elements...")
                if hasattr(self.kiosk_app.ui, 'status_frame') and self.kiosk_app.ui.status_frame:
                    self.kiosk_app.ui.status_frame.delete('all')
                    self.kiosk_app.ui.hide_status_frame()
                self.kiosk_app.ui.clear_all_labels()

                # Schedule timer reset on main thread
                self.kiosk_app.root.after(0, lambda: self.kiosk_app.timer._delayed_init())

                # Reset room started state
                self.kiosk_app.room_started = False

                # Disable Auto Start
                self.kiosk_app.auto_start = False

                # Restore UI after timer reinitialization
                def restore_ui():
                    if self.kiosk_app.assigned_room:
                        print("[message handler][DEBUG] Restoring room interface")
                        self.kiosk_app.ui.setup_room_interface(self.kiosk_app.assigned_room)

                        # Update help button state after reset
                        self.kiosk_app._actual_help_button_update()
                        print("[message handler][DEBUG] Kiosk reset complete")

                    # Check game loss status *after* setup
                    self.kiosk_app.root.after(0, lambda: Overlay._check_game_loss_visibility(self.kiosk_app.timer.game_lost))
                    self.kiosk_app.root.after(0, lambda: Overlay._check_game_win_visibility(self.kiosk_app.timer.game_won))

                # Schedule UI restoration after timer reset
                self.kiosk_app.root.after(100, restore_ui)

            elif msg['type'] == 'toggle_music_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler][DEBUG] Received toggle music command")
                self.kiosk_app.audio_manager.toggle_music()

            elif msg['type'] == 'stop_video_command' and msg['computer_name'] == self.kiosk_app.computer_name:
                self.handle_stop_video_command()

            elif msg['type'] == 'toggle_auto_start' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("toggling auto start")
                self.toggle_auto_start()

            elif msg['type'] == 'offer_assistance' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler] Received offer assistance command")
                # Play the hint received sound
                self.kiosk_app.audio_manager.play_sound("hint_received.mp3")
                # Call the Overlay's method to show the assistance offered message
                self.kiosk_app.root.after(0, lambda: Overlay.show_gm_assistance())

            elif msg['type'] == 'victory' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler]Victory detected")
                self.kiosk_app.timer.game_won = True # set the flag
                self.kiosk_app.handle_game_win()  # Call handle_game_win
            
            # Kiosk side of screenshot request
            elif msg['type'] == 'request_screenshot' and msg['computer_name'] == self.kiosk_app.computer_name:
                self.kiosk_app.take_screenshot_requested = True
                #print("[message handler] Kiosk received screenshot request - will send on next stats update")

        except Exception as e:
            print("[message handler][CRITICAL ERROR] Critical error in handle_message:")
            print(f"[message handler][CRITICAL ERROR] Error type: {type(e)}")
            print(f"[message handler][CRITICAL ERROR] Error message: {str(e)}")
            traceback.print_exc()

    def send_acknowledgment(self, request_hash):
        """Sends an acknowledgment message."""
        ack_message = {
            'type': 'ack',
            'request_hash': request_hash
        }
        self.kiosk_app.network.send_message(ack_message)  # Use the kiosk's network
        print(f"[message handler]Sent acknowledgment for hash: {request_hash}")

    def handle_stop_video_command(self):
        """Handles the 'stop_video_command'."""
        print("[message handler][DEBUG] Received stop video command")
        if self.video_manager:
            self.video_manager.stop_video()

    def toggle_auto_start(self):
        """Toggles the auto-start flag on the kiosk. Does not broadcast."""
        if (self.kiosk_app.auto_start == False):
            self.kiosk_app.auto_start = True
            print(f"[message handler] Auto-start enabled")
        else:
            self.kiosk_app.auto_start = False
            print(f"[message handler] Auto-start disabled")