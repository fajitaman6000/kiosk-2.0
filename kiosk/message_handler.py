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

    def handle_message(self, msg):
        """Handles incoming messages and delegates to specific methods."""
        print(f"[message handler]\n[DEBUG] Received message: {msg}")
        try:
            if msg['type'] == SYNC_MESSAGE_TYPE:
                admin_ip = msg.get('admin_ip')
                sync_id = msg.get('sync_id')
                
                if admin_ip:
                    if self.file_downloader is None:
                        self.file_downloader = KioskFileDownloader(self.kiosk_app, admin_ip)
                        self.file_downloader.start()
                    elif self.file_downloader.admin_ip != admin_ip:
                        self.file_downloader.stop()
                        self.file_downloader = KioskFileDownloader(self.kiosk_app, admin_ip)
                        self.file_downloader.start()
                    
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
                print("[message handler]\n[DEBUG] Processing timer command")
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

            elif msg['type'] == 'clear_hints' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler]\n[DEBUG] Processing clear hints command")
                self.kiosk_app.clear_hints()

            elif msg['type'] == 'play_sound' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler]\n[DEBUG] Received play sound command")
                sound_name = msg.get('sound_name')
                if sound_name:
                    self.kiosk_app.audio_manager.play_sound(sound_name)

            elif msg['type'] == 'audio_hint' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler]\n[DEBUG] Received audio hint command")
                audio_path = msg.get('audio_path')
                if audio_path:
                    self.kiosk_app.audio_manager.play_hint_audio(audio_path)

            elif msg['type'] == 'solution_video' and msg['computer_name'] == self.kiosk_app.computer_name:
                print("[message handler]\n[DEBUG] Received solution video command")
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
                print("[message handler]\n[DEBUG] Processing kiosk reset")

                # First, stop all audio and video playback
                print("[message handler][DEBUG] Stopping all media playback...")

                # Stop background music
                self.kiosk_app.audio_manager.stop_background_music()

                # Stop video manager (which handles both video and its audio)
                self.kiosk_app.video_manager.stop_video()

                # Ensure pygame mixer is fully reset
                if pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    pygame.mixer.stop()  # Stop all sound channels

                # Kill any remaining video process
                if self.kiosk_app.current_video_process:
                    print("[message handler][DEBUG] Terminating external video process")
                    self.kiosk_app.current_video_process.terminate()
                    self.kiosk_app.current_video_process = None
                    self.kiosk_app.root.deiconify()

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
                if hasattr(self.kiosk_app.ui, 'stored_video_info'):
                    self.kiosk_app.ui.stored_video_info = None
                if hasattr(self.kiosk_app.ui, 'video_is_playing'):
                    self.kiosk_app.ui.video_is_playing = False

                # Cancel any existing cooldown timer and hide overlay
                print("[message handler][DEBUG] Clearing cooldown state...")
                if self.kiosk_app.ui.cooldown_after_id:
                    self.kiosk_app.root.after_cancel(self.kiosk_app.ui.cooldown_after_id)
                    self.kiosk_app.ui.cooldown_after_id = None

                # Hide and Clear Overlay
                self.kiosk_app.root.after(0, lambda: Overlay.hide())

                # Clear UI elements safely
                print("[message handler][DEBUG] Clearing UI elements...")
                if hasattr(self.kiosk_app.ui, 'status_frame') and self.kiosk_app.ui.status_frame:
                    self.kiosk_app.ui.status_frame.delete('all')
                    self.kiosk_app.ui.hide_status_frame()
                self.kiosk_app.ui.clear_all_labels()

                # Clear specific hint-related elements
                if hasattr(self.kiosk_app.ui, 'image_button') and self.kiosk_app.ui.image_button:
                    self.kiosk_app.ui.image_button.destroy()
                    self.kiosk_app.ui.image_button = None
                if hasattr(self.kiosk_app.ui, 'video_solution_button') and self.kiosk_app.ui.video_solution_button:
                    self.kiosk_app.ui.video_solution_button.destroy()
                    self.kiosk_app.ui.video_solution_button = None
                if hasattr(self.kiosk_app.ui, 'fullscreen_image') and self.kiosk_app.ui.fullscreen_image:
                    self.kiosk_app.ui.fullscreen_image.destroy()
                    self.kiosk_app.ui.fullscreen_image = None

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

        except Exception as e:
            print("[message handler]\n[CRITICAL ERROR] Critical error in handle_message:")
            print(f"[message handler][CRITICAL ERROR] Error type: {type(e)}")
            print(f"[message handler][CRITICAL ERROR] Error message: {str(e)}")
            traceback.print_exc()

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