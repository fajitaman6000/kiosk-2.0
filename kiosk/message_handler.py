# message_handler.py

print("[message_handler] Beginning imports ...")
from video_manager import VideoManager
from qt_manager import QtManager
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
import threading
from PyQt5.QtCore import QMetaObject, Qt, Q_ARG, QTimer, QObject, pyqtSlot # Import for invoking methods thread-safely
from kiosk_soundcheck import KioskSoundcheckWidget # Assuming it's in the same directory or sys.path is set
print("[message_handler] Ending imports ...")

# Create a global timer scheduler in the Qt main thread
_timer_scheduler = None

def init_timer_scheduler():
    """Initialize the timer scheduler in the Qt main thread"""
    print("[message_handler] Initializing timer scheduler...", flush=True)
    global _timer_scheduler
    if _timer_scheduler is None:
        _timer_scheduler = QTimer()
    print("[message_handler] Timer scheduler initialized.", flush=True)
    return _timer_scheduler

class TimerScheduler(QObject):
    def __init__(self):
        super().__init__()
        
    @pyqtSlot(int, object)
    def schedule_timer(self, delay_ms, callback):
        QTimer.singleShot(delay_ms, callback)

class MessageHandler:
    # How long to remember processed command IDs (in seconds)
    COMMAND_ID_TIMEOUT = 120

    def __init__(self, kiosk_app, video_manager):
        print("[message_handler] Initializing MessageHandler...", flush=True)
        self.kiosk_app = kiosk_app
        self.video_manager = video_manager
        self.file_downloader = None  # Initialize later when we have the admin IP
        self.last_sync_id = None  # Track last sync ID
        self._last_admin_ip = None  # Track last admin IP to detect changes
        # Store recently processed command IDs to prevent duplicate execution
        self.processed_command_ids = {} # {command_id: timestamp}
        self._lock = threading.Lock()
        self._message_queue = []
        self._processing = False
        self._stop_event = threading.Event()
        # Flag to track when a reset operation is in progress
        self._resetting_kiosk = False
        # Queue for victory messages that arrive during reset
        self._pending_victory_msg = None
        self.soundcheck_widget = None
        print("[message_handler] MessageHandler initialized.", flush=True)

    def schedule_timer(self, delay_ms, callback):
        """Thread-safe way to schedule a timer"""
        # Use the bridge's timer scheduling
        QMetaObject.invokeMethod(
            Overlay._bridge,
            "schedule_timer",
            Qt.QueuedConnection,
            Q_ARG(int, delay_ms),
            Q_ARG(object, callback)
        )

    def _ensure_file_downloader(self, admin_ip):
        """Ensure we have a properly initialized file downloader with the correct admin IP."""
        print(f"[message_handler] Ensuring file downloader with admin IP: {admin_ip}...", flush=True)
        try:
            if not admin_ip:
                print("[message_handler] Error: No admin IP provided", flush=True)
                return False

            # If IP changed or downloader not initialized, create new one
            if self.file_downloader is None or self._last_admin_ip != admin_ip:
                # Clean up old downloader if it exists
                if self.file_downloader:
                    print(f"[message_handler] Stopping old file downloader (admin IP changed from {self._last_admin_ip} to {admin_ip})", flush=True)
                    self.file_downloader.stop()
                    self.file_downloader = None

                print(f"[message_handler] Creating new file downloader for admin IP: {admin_ip}", flush=True)
                self.file_downloader = KioskFileDownloader(self.kiosk_app, admin_ip)
                self.file_downloader.start()
                self._last_admin_ip = admin_ip
                print(f"[message_handler] File downloader created and started.", flush=True)

            return True
        except Exception as e:
            print(f"[message_handler] Error initializing file downloader: {e}", flush=True)
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

    # --- NEW METHOD to handle GUI operations for reset ---
    def _execute_reset_gui_operations(self):
        """Executes the GUI-related parts of the reset process. MUST run on the main thread."""
        print("[message handler] Executing GUI reset operations on main thread...")
        try:
            # Set flag to indicate reset is in progress
            self._resetting_kiosk = True
            
            # Stop video (this should be safe to initiate from here if VideoManager is thread-safe)
            # but the actual Qt hiding happens via invokeMethod anyway.
            self.video_manager.force_stop()

            # Stop audio (Pygame mixer interactions should happen on the main thread)
            self.kiosk_app.audio_manager.stop_all_audio()
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                pygame.mixer.stop()

            # --- Cancel Tkinter Timers ---
            #if self.kiosk_app.ui.cooldown_after_id:
                #print("[message handler] Cancelling existing cooldown timer.")
                #self.kiosk_app.root.after_cancel(self.kiosk_app.ui.cooldown_after_id)
                #self.kiosk_app.ui.cooldown_after_id = None
            
            # --- Hide Qt Overlays ---
            print("[message handler] Hiding all Qt overlays...")
            Overlay.hide() # Hides all standard overlays including timer, buttons, hints etc.
            Overlay.hide_gm_assistance()
            # Explicitly hide win/loss screens
            Overlay.hide_victory_screen()
            Overlay.hide_loss_screen()
            # Video display should already be hidden by video_manager.force_stop()
            
            # Clear general labels managed by ui.py
            self.kiosk_app.ui.clear_all_labels() # This should only destroy Tkinter labels

            # Re-initialize Qt Timer (if needed, or ensure it's handled elsewhere)
            # self.kiosk_app.timer._delayed_qt_init() # Ensure timer visuals are ready

            # --- Restore Base UI ---
            def restore_base_ui():
                try:
                    # Check game state flags AFTER they've been reset in the network thread
                    game_lost = self.kiosk_app.timer.game_lost
                    game_won = self.kiosk_app.timer.game_won

                    if game_lost:
                        Overlay.show_loss_screen()
                    elif game_won:
                        Overlay.show_victory_screen()
                    elif self.kiosk_app.assigned_room:
                        print("[message handler][DEBUG] Restoring room interface")
                        self.kiosk_app.ui.setup_room_interface(self.kiosk_app.assigned_room) # Shows background, loads timer bg
                        Overlay.update_timer_display(self.kiosk_app.timer.get_time_str()) # Show timer value
                        self.kiosk_app._actual_help_button_update() # Show help button if needed
                        print("[message handler][DEBUG] Kiosk GUI reset complete")
                    else:
                        print("[message handler] No room assigned after reset, showing waiting screen.")
                        self.kiosk_app.ui.setup_waiting_screen() # Show waiting screen if no room
                    
                    # Reset is complete, mark flag
                    self._resetting_kiosk = False
                    
                    # Process any victory message that came in during reset
                    if self._pending_victory_msg:
                        print("[message handler] Processing pending victory message that arrived during reset")
                        pending_msg = self._pending_victory_msg
                        self._pending_victory_msg = None
                        self.handle_message(pending_msg)
                except Exception as e:
                    print(f"[message handler] Error during restore_base_ui: {e}")
                    traceback.print_exc()
                    # Make sure we reset the flag even if there's an exception
                    self._resetting_kiosk = False

            # Schedule the final UI restoration slightly later to ensure state is settled
            # Replace root.after with QTimer.singleShot
            QTimer.singleShot(200, restore_base_ui)  # Increased from 100ms to 200ms for more stability

        except Exception as e:
            print(f"[message handler] Error during GUI reset operations: {e}")
            traceback.print_exc()
            # Make sure we reset the flag even if there's an exception
            self._resetting_kiosk = False
    # --- End new method ---

    def add_message(self, message, delay=0):
        """Add a message to the queue with optional delay."""
        with self._lock:
            self._message_queue.append((message, delay))
            if not self._processing:
                self.schedule_timer(0, self._process_queue)

    def _process_queue(self):
        """Process messages in the queue."""
        if self._stop_event.is_set():
            return

        with self._lock:
            if not self._message_queue:
                self._processing = False
                return

            message, delay = self._message_queue.pop(0)
            self._processing = True

        # If there's a delay, schedule the message display
        if delay > 0:
            self.schedule_timer(delay * 1000, lambda: self._display_message(message))
        else:
            self._display_message(message)

        # Schedule next queue processing
        self.schedule_timer(0, self._process_queue)

    def _display_message(self, message):
        """Display a message using the Qt overlay."""
        if not Overlay._bridge:
            print("[message_handler] Error: Overlay Bridge not initialized.")
            return

        try:
            # Use QueuedConnection to avoid blocking
            QMetaObject.invokeMethod(
                Overlay._bridge,
                "display_message_slot",
                Qt.QueuedConnection,
                Q_ARG(str, message)
            )
        except Exception as e:
            print(f"[message_handler] Error displaying message: {e}")
            traceback.print_exc()

    def clear_messages(self):
        """Clear all pending messages."""
        with self._lock:
            self._message_queue.clear()
            self._processing = False

    def stop(self):
        """Stop message processing."""
        self._stop_event.set()
        self.clear_messages()

    def start(self):
        """Start message processing."""
        self._stop_event.clear()
        with self._lock:
            if self._message_queue and not self._processing:
                self.schedule_timer(0, self._process_queue)

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

        # --- Log received message (excluding screenshot requests) ---
        if msg.get('type') != 'request_screenshot':
             print(f"[message handler] Received message: {msg}")

        # Acknowledge the specific transmission attempt
        request_hash = msg.get('request_hash')
        if request_hash:
            self.send_acknowledgment(request_hash)

        try:
            msg_type = msg.get('type')
            target_computer = msg.get('computer_name')

            # --- Generic Checks ---
            is_targeted = target_computer == self.kiosk_app.computer_name
            is_global = target_computer == 'all' # For sync messages

            # --- Message Type Handling ---
            if msg_type == SYNC_MESSAGE_TYPE:
                if not (is_targeted or is_global):
                    # print(f"[message handler] Ignoring sync message intended for: {target_computer}")
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

            elif msg_type == 'room_assignment' and is_targeted:
                print(f"[message handler][DEBUG] Processing room assignment: {msg['room']} (Command ID: {command_id})")
                # --- State resets (safe in network thread) ---
                self.kiosk_app.assigned_room = msg['room']
                save_result = self.kiosk_app.room_persistence.save_room_assignment(msg['room'])
                print(f"[message handler][DEBUG] Save result: {save_result}")
                self.kiosk_app.start_time = time.time()
                self.kiosk_app.ui.hint_cooldown = False
                self.kiosk_app.ui.current_hint = None
                self.kiosk_app.audio_manager.current_music = None
                # --- GUI update (schedule on main thread) ---
                self.schedule_timer(0, lambda room=msg['room']: self.kiosk_app.ui.setup_room_interface(room))

            elif msg_type == 'hint' and is_targeted and self.kiosk_app.assigned_room:
                if msg.get('room') == self.kiosk_app.assigned_room:
                    print(f"[message handler][DEBUG] Processing hint (Command ID: {command_id})")
                    hint_data = None # Initialize
                    # --- Image processing (safe in network thread) ---
                    if msg.get('has_image') and 'image_path' in msg:
                        image_path = os.path.join(os.path.dirname(__file__), msg['image_path'])
                        if os.path.exists(image_path):
                            try:
                                with open(image_path, 'rb') as f:
                                    image_bytes = f.read()
                                hint_data = {
                                    'text': msg.get('text', ''),
                                    'image': base64.b64encode(image_bytes).decode()
                                }
                            except Exception as img_err:
                                print(f"[message handler] Error processing hint image {image_path}: {img_err}")
                                hint_data = msg.get('text', 'Error loading image hint') # Fallback text
                        else:
                            print(f"[message handler] Error: Image file not found at {image_path}")
                            hint_data = msg.get('text', 'Image hint file missing') # Fallback text
                    else:
                        hint_data = msg.get('text', '') # Text only hint

                    # --- State updates (safe in network thread) ---
                    self.kiosk_app.hints_received += 1
                    self.kiosk_app.hint_requested_flag = False
                    print(f"[message handler][Kiosk] handle_message: Received hint, clearing hint_requested_flag for room {self.kiosk_app.assigned_room}")

                    # --- Play hint sound (schedule on main thread) ---
                    self.schedule_timer(0, lambda: self.kiosk_app.audio_manager.play_sound("hint_received.mp3"))

                    # --- GUI update (schedule on main thread) ---
                    if hint_data is not None: # Ensure we have data before scheduling
                        self.schedule_timer(0, lambda d=hint_data: self.kiosk_app.show_hint(d))

            elif msg_type == 'timer_command' and is_targeted:
                print(f"[message handler][DEBUG] Processing timer command (Command ID: {command_id})")
                minutes = msg.get('minutes')
                command = msg['command']

                # --- State updates (safe in network thread) ---
                if minutes is not None:
                    minutes = float(minutes)
                    print(f"[message handler][DEBUG] Setting timer to {minutes} minutes")
                    if minutes > 45:
                        print("[message handler][DEBUG] New time exceeds 45 minutes - setting flag")
                        self.kiosk_app.time_exceeded_45 = True
                    # Timer state update itself should be safe if KioskTimer methods are simple assignments
                    self.kiosk_app.timer.handle_command(command, minutes)
                else:
                    # Handle commands without minutes (like 'start', 'stop')
                    self.kiosk_app.timer.handle_command(command)

                if command == "start":
                    if not self.kiosk_app.room_started:
                        self.kiosk_app.room_started = True
                        print(f"[message handler][Kiosk] handle_message: Timer started, setting room_started to True for room {self.kiosk_app.assigned_room}")
                        if self.kiosk_app.assigned_room:
                            print(f"[message handler][DEBUG] Timer starting - playing background music for room: {self.kiosk_app.assigned_room}")
                            # Schedule audio play on main thread
                            self.schedule_timer(0, lambda room=self.kiosk_app.assigned_room: self.kiosk_app.audio_manager.play_background_music(room))
                    self.kiosk_app.hint_requested_flag = False
                    print(f"[message handler][Kiosk] handle_message: Timer started, clearing hint_requested_flag for room {self.kiosk_app.assigned_room}")

                # --- GUI update (schedule on main thread) ---
                self.schedule_timer(0, self.kiosk_app._actual_help_button_update)

            elif msg_type == 'video_command' and is_targeted:
                print(f"[message handler][DEBUG] Processing video command (Command ID: {command_id})")
                # KioskApp.play_video likely interacts with VideoManager which uses Qt invokes,
                # so calling it directly might be okay, but safer to schedule.
                # Replace root.after with QTimer.singleShot
                self.schedule_timer(0, lambda vt=msg['video_type'], m=msg['minutes']: self.kiosk_app.play_video(vt, m))

            elif msg_type == 'soundcheck' and is_targeted:
                print(f"[message handler] soundcheck command received (Command ID: {command_id})")
                # Potentially add soundcheck logic here if needed - schedule if it uses Pygame mixer

            elif msg_type == 'clear_hints' and is_targeted:
                print(f"[message handler][DEBUG] Processing clear hints command (Command ID: {command_id})")
                # KioskApp.clear_hints modifies state and calls UI/Overlay methods
                self.schedule_timer(0, Overlay.hide_fullscreen_hint)
                self.schedule_timer(0, self.kiosk_app.clear_hints)

            elif msg_type == 'play_sound' and is_targeted:
                print(f"[message handler][DEBUG] Received play sound command (Command ID: {command_id})")
                sound_name = msg.get('sound_name')
                if sound_name:
                    # Schedule audio play on main thread
                    self.schedule_timer(0, lambda sn=sound_name: self.kiosk_app.audio_manager.play_sound(sn))

            elif msg_type == 'audio_hint' and is_targeted:
                print(f"[message handler][DEBUG] Received audio hint command (Command ID: {command_id})")
                audio_path = msg.get('audio_path')
                count_as_hint = msg.get('count_as_hint', True)  # Default to True for backwards compatibility
                
                if audio_path:
                    # Increment hint counter and handle hint mechanics if count_as_hint is True
                    if count_as_hint:
                        # --- State updates (safe in network thread) ---
                        self.kiosk_app.hints_received += 1
                        self.kiosk_app.hint_requested_flag = False
                        print(f"[message handler] Audio hint counting as hint, incremented hints_received to {self.kiosk_app.hints_received}")
                        
                        # Clear existing hints
                        self.schedule_timer(0, Overlay.hide_fullscreen_hint)
                        self.schedule_timer(0, self.kiosk_app.clear_hints)
                        # Start cooldown
                        self.schedule_timer(0, self.kiosk_app.ui.start_cooldown)
                    
                    # Schedule audio play on main thread (always play the audio)
                    self.schedule_timer(0, lambda ap=audio_path: self.kiosk_app.audio_manager.play_hint_audio(ap))

            elif msg_type == 'solution_video' and is_targeted:
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
                        # State update (safe)
                        self.kiosk_app.hints_received += 1
                        print(f"[message handler][DEBUG] Setting up solution video interface: {video_path}")

                        # Pass a string directly to show_hint instead of a dictionary
                        hint_text = "Video Solution Received"
                        
                        # --- Play hint sound (schedule on main thread) ---
                        self.schedule_timer(0, lambda: self.kiosk_app.audio_manager.play_sound("hint_received.mp3"))

                        # Schedule GUI updates
                        self.schedule_timer(0, lambda text=hint_text: self.kiosk_app.show_hint(text, start_cooldown=False))
                        self.schedule_timer(50, lambda rf=room_folder, vf=video_filename: self.kiosk_app.ui.show_video_solution(rf, vf)) # Slight delay for button

                    else:
                        print(f"[message handler] Error: Solution video not found at {video_path}")

                except Exception as e:
                    print(f"[message handler] Error processing solution video command: {e}")
                    traceback.print_exc()

            elif msg_type == 'reset_kiosk' and is_targeted:
                print(f"[message handler][DEBUG] Processing kiosk reset (Command ID: {command_id})")

                # --- Perform non-GUI state resets immediately (safe) ---
                print("[message handler][DEBUG] Resetting application state...")
                self.kiosk_app.timer.game_lost = False
                self.kiosk_app.timer.game_won = False
                self.kiosk_app.time_exceeded_45 = False
                self.kiosk_app.hints_requested = 0
                self.kiosk_app.hint_requested_flag = False
                self.kiosk_app.hints_received = 0
                self.kiosk_app.times_touched_screen = 0
                self.kiosk_app.room_started = False
                self.kiosk_app.auto_start = False

                # Reset UI state variables (safe as they are just flags/data)
                print("[message handler][DEBUG] Resetting UI hint state variables...")
                self.kiosk_app.ui.hint_cooldown = False
                self.kiosk_app.ui.current_hint = None
                self.kiosk_app.ui.stored_image_data = None
                self.kiosk_app.ui.stored_video_info = None
                # self.kiosk_app.ui.video_is_playing = False # Let VideoManager handle this

                # --- Schedule the GUI-related operations ---
                print("[message handler][DEBUG] Scheduling GUI reset operations...")
                self.schedule_timer(0, self._execute_reset_gui_operations)


            elif msg_type == 'toggle_music_command' and is_targeted:
                print(f"[message handler][DEBUG] Received toggle music command (Command ID: {command_id})")
                # Schedule audio toggle on main thread
                self.schedule_timer(0, self.kiosk_app.audio_manager.toggle_music)

            elif msg_type == 'stop_video_command' and is_targeted:
                print(f"[message handler][DEBUG] Received stop video command (Command ID: {command_id})")
                # VideoManager uses Qt invokes, likely safe, but scheduling is safest
                self.schedule_timer(0, self.handle_stop_video_command) # Delegate to keep handle_message cleaner

            elif msg_type == 'toggle_auto_start' and is_targeted:
                print(f"[message handler] Toggling auto start (Command ID: {command_id})")
                # Simple flag toggle, safe in network thread
                self.toggle_auto_start()

            elif msg_type == 'offer_assistance' and is_targeted:
                print(f"[message handler] Received offer assistance command (Command ID: {command_id})")
                # Schedule audio and overlay show on main thread
                self.schedule_timer(0, lambda: self.kiosk_app.audio_manager.play_sound("hint_received.mp3"))
                self.schedule_timer(50, lambda: Overlay.show_gm_assistance()) # Slight delay

            elif msg_type == 'victory' and is_targeted:
                print(f"[message handler] Victory detected (Command ID: {command_id})")
                
                # Check if we're in the middle of a reset operation
                if self._resetting_kiosk:
                    print("[message handler] Victory message received during kiosk reset - queueing for processing after reset")
                    self._pending_victory_msg = msg.copy()  # Store a copy of the message
                    return
                
                # Set state flag (safe)
                self.kiosk_app.timer.game_won = True
                # Handle game win logic (involves audio/video/overlay - schedule it)
                self.schedule_timer(0, self.kiosk_app.handle_game_win)

            elif msg_type == 'request_screenshot' and is_targeted:
                # The command_id check already happened
                # print(f"[message handler] Received request_screenshot command (Command ID: {command_id})") # Less noisy
                # Set flag (safe), screenshot happens in separate thread anyway
                self.kiosk_app.take_screenshot_requested = True
                # Note: The ACK was already sent earlier.

            elif msg_type == 'soundcheck_command' and is_targeted:
                print(f"[Message Handler] Received soundcheck command (ID: {command_id})")
                # Ensure any previous soundcheck is closed first
                if self.soundcheck_widget:
                    print("[Message Handler] Found existing soundcheck widget, cancelling it.")
                    # Use invokeMethod for thread safety
                    # Ensure cancel runs on the main thread where the widget lives
                    QMetaObject.invokeMethod(self.soundcheck_widget, "cancel_soundcheck", Qt.QueuedConnection)
                    # Note: We rely on the cancel_soundcheck to eventually clear self.soundcheck_widget via the finished signal

                # Use the OverlayBridge to schedule the creation and start
                # of the soundcheck widget on the main Qt thread.
                if Overlay._bridge:
                    print("[Message Handler] Using OverlayBridge to schedule soundcheck start.")
                    # QTimer.singleShot(200, deferred_start) # <-- REMOVE or COMMENT OUT THIS LINE

                    # Schedule deferred_start function to run on the main thread
                    QMetaObject.invokeMethod(
                        Overlay._bridge,
                        "schedule_timer", # Name of the slot in OverlayBridge
                        Qt.QueuedConnection,
                        Q_ARG(int, 200), # Delay in ms
                        Q_ARG(object, self._deferred_soundcheck_start) # The function to call
                    )
                else:
                    print("[Message Handler] Error: OverlayBridge not initialized. Cannot schedule soundcheck.")

            elif msg_type == 'soundcheck_cancel' and is_targeted:
                print(f"[Message Handler] Received soundcheck cancel command (ID: {command_id})")
                if self.soundcheck_widget:
                    # Use invokeMethod to ensure cancel runs on the main thread
                    QMetaObject.invokeMethod(self.soundcheck_widget, "cancel_soundcheck", Qt.QueuedConnection)
                else:
                    print("[Message Handler] Received cancel but no soundcheck widget found.")

            elif msg_type == 'set_music_volume_level' and is_targeted:
                level = msg.get('level')
                if level is not None and isinstance(level, int):
                    print(f"[message handler] Received set_music_volume_level: {level} (Command ID: {command_id})")
                    # Update KioskApp's integer level state
                    self.kiosk_app.music_volume_level = max(0, min(10, level)) # Clamp 0-10
                    # Schedule AudioManager call on main thread
                    self.schedule_timer(0, lambda l=self.kiosk_app.music_volume_level: self.kiosk_app.audio_manager.set_music_volume_level(l))
                else:
                    print(f"[message handler] Invalid or missing level for set_music_volume_level: {msg}")

            elif msg_type == 'set_hint_volume_level' and is_targeted:
                level = msg.get('level')
                if level is not None and isinstance(level, int):
                    print(f"[message handler] Received set_hint_volume_level: {level} (Command ID: {command_id})")
                    # Update KioskApp's integer level state
                    self.kiosk_app.hint_volume_level = max(0, min(10, level)) # Clamp 0-10
                    # Schedule AudioManager call on main thread
                    self.schedule_timer(0, lambda l=self.kiosk_app.hint_volume_level: self.kiosk_app.audio_manager.set_hint_volume_level(l))
                else:
                    print(f"[message handler] Invalid or missing level for set_hint_volume_level: {msg}")

        except Exception as e:
            print("[message handler][CRITICAL ERROR] Critical error in handle_message:")
            print(f"[message handler][CRITICAL ERROR] Error type: {type(e)}")
            print(f"[message handler][CRITICAL ERROR] Error message: {str(e)}")
            # Avoid printing the whole message if it's huge (like image data)
            safe_msg_repr = {k: v[:100] + '...' if isinstance(v, str) and len(v) > 100 else v
                             for k, v in msg.items()}
            print(f"[message handler][CRITICAL ERROR] Failed message (truncated): {safe_msg_repr}")
            traceback.print_exc()

    def send_acknowledgment(self, request_hash):
        """Sends an acknowledgment message for a specific transmission attempt."""
        if not request_hash: return # Don't send ACK if no hash provided
        ack_message = {
            'type': 'ack',
            'request_hash': request_hash,
            'computer_name': self.kiosk_app.computer_name # Include computer name in ACK
        }
        # Use the kiosk's network send method, which doesn't add command_id or track ACKs for ACKs
        self.kiosk_app.network.send_message(ack_message)
        # print(f"[message handler] Sent acknowledgment for transmission hash: {request_hash}") # Can be noisy

    def handle_stop_video_command(self):
        """Handles the 'stop_video_command' logic. Assumed to be called via root.after."""
        if self.video_manager:
            print("[message handler] Executing stop video command")
            # The video_manager.stop_video method handles the callback chain properly
            self.video_manager.stop_video() # This will trigger the completion callback

    def _deferred_soundcheck_start(self):
        """
        This method is scheduled to run on the main Qt thread via OverlayBridge.
        It handles the creation and starting of the KioskSoundcheckWidget.
        """
        print("[Message Handler] _deferred_soundcheck_start running on main thread.")
        # Check if soundcheck widget was cancelled and cleared while waiting for this callback
        if self.soundcheck_widget:
            print("[Message Handler] Warning: Soundcheck widget exists on deferred start. Likely cancelled while waiting.")
            return # Don't start a new one

        try:
            print("[Message Handler] Creating KioskSoundcheckWidget...")
            # Parent the widget to the main application's content widget
            from qt_main import QtKioskApp
            parent_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
            if not parent_widget:
                print("[Message Handler] Error: Cannot find parent widget for soundcheck.")
                parent_widget = None # Create without explicit parent if needed

            self.soundcheck_widget = KioskSoundcheckWidget(self.kiosk_app, parent_widget)
            self.soundcheck_widget.finished.connect(self._on_soundcheck_finished) # Connect signal
            self.soundcheck_widget.start_soundcheck()
            print("[Message Handler] KioskSoundcheckWidget created and started.")
        except Exception as e:
            print(f"[Message Handler] Error creating/starting soundcheck widget: {e}")
            traceback.print_exc()
            self.soundcheck_widget = None # Ensure it's None on error

    def toggle_auto_start(self):
        """Toggles the auto-start flag on the kiosk. Does not broadcast."""
        self.kiosk_app.auto_start = not self.kiosk_app.auto_start
        status = "enabled" if self.kiosk_app.auto_start else "disabled"
        print(f"[message handler] Auto-start {status}")

    def _on_soundcheck_finished(self):
        """Slot called when the soundcheck widget is closed/finished."""
        print("[Message Handler] Soundcheck widget reported finished.")
        self.soundcheck_widget = None # Clear the reference