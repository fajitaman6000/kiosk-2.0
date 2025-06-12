import tkinter as tk
from tkinter import ttk
import paho.mqtt.client as mqtt
from admin_audio_manager import AdminAudioManager
import json
from pathlib import Path
import time
from datetime import datetime, timedelta
import random
import threading
from PIL import Image, ImageTk
import os
import traceback
import uuid
from prop_control_popout import PropControlPopout

class PropControl:
    ROOM_MAP = {
        3: "wizard",
        1: "casino",
        2: "ma",
        5: "haunted",
        4: "zombie",
        6: "atlantis",
        7: "time"  # Time Machine room
    }

    FULLNAME_ROOM_MAP = {
        3: "Wizard Trials",
        1: "Casino Heist",
        2: "Morning After",
        5: "Haunted Manor",
        4: "Zombie Outbreak",
        6: "Atlantis Rising",
        7: "Time Machine"  # Time Machine room
    }

    # Room-specific MQTT configurations
    ROOM_CONFIGS = {
        4: {  # Zombie Outbreak
            'ip': '192.168.0.12',
            'special_buttons': [
                ('KITCHEN', 'kitchen'),  # Will map to pnevmo1
                ('BARREL', 'barrel'),    # Will map to pnevmo2
                ('CAGE', 'cage'),        # Will map to pnevmo3
                ('DOOR', 'door')         # Will map to pnevmo4
            ]
        },
        1: {  # Casino Heist
            'ip': '192.168.0.49',
            'special_buttons': [
                ('CASINO', 'quest/robbery'),
                ('MA', 'quest/stag')
            ]
        },
        2: {  # Morning After
            'ip': '192.168.0.49',
            'special_buttons': [
                ('MA', 'quest/stag'),
                ('CASINO', 'quest/robbery')
            ]
        },
        6: {  # Atlantis Rising
            'ip': '192.168.0.14',
            'special_buttons': []
        },
        5: {  # Haunted Manor
            'ip': '192.168.0.13',
            'special_buttons': []
        },
        3: {  # Wizard Trials
            'ip': '192.168.0.11',
            'special_buttons': []
        },
        7: {  # Time Machine
            'ip': '192.168.0.15',
            'special_buttons': []
        }
    }

    STALE_THRESHOLD = 600  # 10 minutes in seconds

    FATE_COOLDOWN_SECONDS = 15

    def __init__(self, app):
        self.app = app
        self.props = {}  # strId -> prop info (for currently selected room's UI)
        # Use locks for thread-safe access to shared data
        self._mqtt_clients_lock = threading.Lock() # Protects self.mqtt_clients dictionary
        self._mqtt_data_lock = threading.Lock()    # Protects other MQTT-related shared data (last_mqtt_updates, disconnect_rc7_history)

        self.mqtt_clients = {}  # room_number -> mqtt client
        self.current_room = None
        self.connection_states = {}  # room_number -> connection state
        self.all_props = {}  # room_number -> {prop_id -> prop_info} (stores all props for all rooms)
        self.prop_update_intervals = {}  # room_number -> last_update_time
        self.UPDATE_INTERVAL = 1000  # Base update interval in ms
        self.INACTIVE_UPDATE_INTERVAL = 2000  # Update interval for non-selected rooms
        self.last_progress_times = {} # last progress events for rooms
        self.last_mqtt_updates = {} # room_number -> {prop_id -> last_mqtt_update_time}
        self.retry_timer_ids = {}  # Tracks pending retry timers for each room
        self.disconnect_rc7_history = {}  # room_number -> list of timestamps for rc=7 disconnects
        self.last_prop_finished = {} # prop status strings
        self.flagged_props = {}  # room_number -> {prop_id: True/False}
        self.fate_sent = {}  # room_number -> bool
        self.finish_sound_played = {}  # room_number -> bool ADDED FINISH TRACKING
        self.standby_played = {} #standby tracking
        self.stale_sound_played = {}
        self.popout_windows = {}
        self.audio_manager = AdminAudioManager()

        self.last_fate_message_time = {} # computer_name -> timestamp

        self.MQTT_PORT = 8080
        self.MQTT_USER = "indestroom"
        self.MQTT_PASS = "indestroom"

        # Create left side panel for prop controls using parent's left_panel
        self.frame = app.interface_builder.left_panel

        # Create custom styles for circuit highlighting
        style = ttk.Style()
        style.configure('Circuit.TFrame', background='#ffe6e6', borderwidth=2, relief='solid')
        style.configure('Circuit.TLabel', background='#ffe6e6', font=('Arial', 8, 'bold'))
        style.configure('Cousin.TFrame', background='#e6ffe6', borderwidth=2, relief='solid')
        style.configure('Cousin.TLabel', background='#e6ffe6', font=('Arial', 8, 'bold'))

        # Title label
        self.title_label = ttk.Label(self.frame, text="Prop Controls", font=('Arial', 14, 'bold'), justify="center")
        self.title_label.pack(fill='x', pady=(0, 2), anchor="center")

        # 1. Global controls section (TOP SECTION)
        self.global_controls = ttk.Frame(self.frame)
        self.global_controls.pack(fill='x', pady=(0, 10))

        self.start_button = tk.Button(
            self.global_controls,
            text="START PROPS",
            command=self.start_game,
            bg="#2898ED",
            fg='white',
            cursor="hand2"
        )
        self.start_button.pack(fill='x', pady=2)

        self.reset_buttons_container = tk.Frame(self.global_controls)
        self.reset_buttons_container.pack(fill='x', pady=2)

        reset_props_only_bg = '#DB4260'
        reset_props_and_kiosk_bg = '#a356ba'

        self.reset_props_only_button = tk.Button(
            self.reset_buttons_container,
            text="RESET PROPS",
            command=self._handle_reset_props_only_click,
            bg=reset_props_only_bg,
            fg='white',
            cursor="hand2"
        )
        self.reset_props_only_button.confirmation_pending = False
        self.reset_props_only_button.after_id = None
        self.reset_props_only_button.original_text = "RESET PROPS"
        self.reset_props_only_button.pack(side='left', fill='x', expand=True, padx=(0, 1))

        self.reset_props_and_kiosk_button = tk.Button(
            self.reset_buttons_container,
            text="RESET PROPS & KIOSK",
            command=self._handle_reset_props_and_kiosk_click,
            bg=reset_props_and_kiosk_bg,
            fg='white',
            cursor="hand2"
        )
        self.reset_props_and_kiosk_button.confirmation_pending = False
        self.reset_props_and_kiosk_button.after_id = None
        self.reset_props_and_kiosk_button.original_text = "RESET PROPS & KIOSK"
        self.reset_props_and_kiosk_button.pack(side='right', fill='x', expand=True, padx=(1, 0))

        # 2. Special buttons section (MIDDLE-TOP SECTION)
        self.special_frame = ttk.LabelFrame(self.frame, text="Room-Specific")
        self.special_frame.pack(fill='x', pady=5)

        # 3. Scrollable props section (FILLS REMAINING MIDDLE SPACE, expands)
        self.canvas = tk.Canvas(self.frame)
        self.props_frame = ttk.Frame(self.canvas)
        self.canvas.pack(fill="both", expand=True) # CRITICAL: No 'side' argument to fill vertically

        self.canvas_frame = self.canvas.create_window((0,0), window=self.props_frame, anchor="nw")
        self.props_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # 4. Status message label (BOTTOM SECTION - above popout button)
        self.status_label = tk.Label(self.frame, text="", font=('Arial', 10))
        self.status_label.pack(side='bottom', fill='x', pady=5)

        # 5. Popout Button (VERY BOTTOM SECTION)
        self.popout_button = tk.Button(
            self.frame,
            text="◱",
            command=self.create_popout_window,
            bg='#5AC8CD',
            fg='white',
            cursor="hand2",
            font=('Arial', 8, 'bold'),
            width=1
        )
        self.popout_button.pack(side='bottom', fill='x', pady=(0, 5))
        self.popout_button.pack_forget() # Initially hidden

        # Load icons *after* all UI elements have been defined and assigned to self
        self.status_icons = {}
        try:
            icon_dir = os.path.join("admin_icons")
            self.status_icons['not_activated'] = ImageTk.PhotoImage(
                Image.open(os.path.join(icon_dir, "not_activated.png")).resize((16, 16), Image.Resampling.LANCZOS)
            )
            self.status_icons['activated'] = ImageTk.PhotoImage(
                Image.open(os.path.join(icon_dir, "activated.png")).resize((16, 16), Image.Resampling.LANCZOS)
            )
            self.status_icons['finished'] = ImageTk.PhotoImage(
                Image.open(os.path.join(icon_dir, "finished.png")).resize((16, 16), Image.Resampling.LANCZOS)
            )
            self.status_icons['offline'] = ImageTk.PhotoImage(
                Image.open(os.path.join(icon_dir, "offline.png")).resize((16, 16), Image.Resampling.LANCZOS)
            )
            self.flagged_prop_image = ImageTk.PhotoImage(
                Image.open(os.path.join(icon_dir, "flagged_prop.png")).resize((16, 16), Image.Resampling.LANCZOS)
            )
        except Exception as e:
            print(f"[prop control]Error loading status icons or flagged prop image during initialization: {e}")
            self.status_icons = {} # Ensure it's an empty dict if load fails
            self.flagged_prop_image = None # Set to None if image fails to load

        self.load_prop_name_mappings()

        # Initialize MQTT clients for all rooms
        for room_number in self.ROOM_CONFIGS:
            self.last_progress_times[room_number] = time.time()
            self.all_props[room_number] = {}
            self.last_mqtt_updates[room_number] = {}
            self.flagged_props[room_number] = {}
            self.stale_sound_played[room_number] = False
            self.fate_sent.setdefault(room_number, False)
            self.finish_sound_played.setdefault(room_number, False)
            self.standby_played.setdefault(room_number, False)
            self.initialize_mqtt_client(room_number)

    def _reset_confirmable_button(self, button_widget):
        """
        Resets a confirmable button to its original state (text, confirmation flag, timer).
        Args:
            button_widget (tk.Button): The button widget to reset.
        """
        if button_widget.after_id:
            self.app.root.after_cancel(button_widget.after_id)
            button_widget.after_id = None
        button_widget.confirmation_pending = False
        button_widget.config(text=button_widget.original_text)

    def _handle_confirmable_click(self, button_widget, action_callback):
        """
        Generic handler for buttons that require a confirmation click.
        On first click, changes text to "Confirm". On second click within 2 seconds,
        executes `action_callback`.
        Args:
            button_widget (tk.Button): The button that was clicked.
            action_callback (callable): The function to execute on confirmation.
        """
        if button_widget.confirmation_pending:
            # Second click - perform the action
            action_callback()
            self._reset_confirmable_button(button_widget) # Reset button state
        else:
            # First click - show confirmation text
            button_widget.confirmation_pending = True
            button_widget.config(text="Confirm")

            # Cancel any existing timeout timer for this button
            if button_widget.after_id:
                self.app.root.after_cancel(button_widget.after_id)

            # Schedule a reset if no second click occurs within 2 seconds
            button_widget.after_id = self.app.root.after(
                2000, lambda: self._reset_confirmable_button(button_widget)
            )

    def _perform_reset_props_only(self):
        """
        Action method to reset only the props for the currently selected room.
        This calls the existing `reset_all` method.
        """
        print("[prop control] Executing 'Reset All Props' (props only).")
        self.reset_all() # This method already handles only prop-related resets.

    def _perform_reset_props_and_kiosk(self):
        """
        Action method to reset props AND the currently selected kiosk.
        It first calls `reset_all` (for props) and then `reset_kiosk` on the
        AdminInterfaceBuilder for the `selected_kiosk`.
        """
        print("[prop control] Executing 'Reset Props & Kiosk'.")
        self.reset_all() # Reset props first

        # Check if a kiosk is currently selected in the UI
        if self.app.interface_builder.selected_kiosk:
            kiosk_name = self.app.interface_builder.selected_kiosk
            # print(f"[prop control] Also resetting kiosk '{kiosk_name}' via AdminInterfaceBuilder.")
            # Call the reset_kiosk method from AdminInterfaceBuilder
            self.app.interface_builder.reset_kiosk(kiosk_name)
        else:
            print("[prop control] No kiosk selected in UI, only props were reset.")

    def _handle_reset_props_only_click(self):
        """Entry point for the 'RESET ALL PROPS' button click."""
        self._handle_confirmable_click(self.reset_props_only_button, self._perform_reset_props_only)

    def _handle_reset_props_and_kiosk_click(self):
        """Entry point for the 'RESET PROPS & KIOSK' button click."""
        self._handle_confirmable_click(self.reset_props_and_kiosk_button, self._perform_reset_props_and_kiosk)

    def update_prop_status(self, prop_id):
        """Update the status display, including flagged status."""
        if prop_id not in self.props:
            return

        prop = self.props[prop_id]
        if 'status_label' not in prop:
            return

        try:
            # Verify widget still exists
            if not prop['status_label'].winfo_exists():
                # print(f"[prop control]Status label for {prop_id} no longer exists, removing reference.")
                del prop['status_label']
                return

            current_time = time.time()

            is_offline = False
            with self._mqtt_data_lock: # Protect access to self.last_mqtt_updates
                is_offline = (self.current_room not in self.last_mqtt_updates or
                            prop_id not in self.last_mqtt_updates[self.current_room] or
                            current_time - self.last_mqtt_updates[self.current_room].get(prop_id, 0) > 3)

            # Ensure status_icons is available and has 'offline' before proceeding
            if not hasattr(self, 'status_icons') or 'offline' not in self.status_icons:
                print("[prop control]Status icons or 'offline' icon not properly initialized. Skipping icon update.")
                return # Can't update status without icons, so exit


            if is_offline:
                icon = self.status_icons['offline']
            else:
                # Ensure 'info' key exists before accessing
                status_text = prop.get('info', {}).get('strStatus')
                if status_text == "Not activated" or status_text == "Not Activated":
                    icon = self.status_icons['not_activated']
                elif status_text == "Activated":
                    icon = self.status_icons['activated']
                elif status_text == "Finished":
                    icon = self.status_icons['finished']
                else:
                    icon = self.status_icons['not_activated'] # Default if status is unknown or missing

            # Check if prop is flagged and overlay the flag image if it is
            if (self.current_room in self.flagged_props and
                prop_id in self.flagged_props[self.current_room] and
                self.flagged_props[self.current_room][prop_id]):

                if self.flagged_prop_image:
                    # Create a new PhotoImage for the composite image
                    # Convert to RGBA to ensure transparency blending works
                    composite_image = Image.new('RGBA', (16, 16), (0, 0, 0, 0))  # Transparent background
                    background_image = ImageTk.getimage(icon).convert("RGBA")
                    flag_image = ImageTk.getimage(self.flagged_prop_image).convert("RGBA")

                    # Paste flag_image FIRST then background to ensure background shows through transparent parts of flag
                    composite_image.paste(flag_image, (0, 0), flag_image)
                    composite_image.paste(background_image, (0, 0), background_image) # Use flag as mask if needed

                    combined_icon = ImageTk.PhotoImage(composite_image)
                    prop['status_label'].config(image=combined_icon)
                    prop['status_label'].image = combined_icon  # Keep reference
                else:  #fallback if image is bad
                     prop['status_label'].config(image=icon)
                     prop['status_label'].image = icon
            else:
                # Update the label with the appropriate icon
                prop['status_label'].config(image=icon)
                prop['status_label'].image = icon  # Keep a reference


            # Bind click event to toggle flag (only if not offline)
            if not is_offline:
                prop['status_label'].bind("<Button-1>", lambda event, pid=prop_id: self.toggle_prop_flag(pid))
                prop['status_label'].config(cursor="hand2")
            else:
                prop['status_label'].unbind("<Button-1>")  # Remove binding if offline
                prop['status_label'].config(cursor="")


        except tk.TclError:
            # Widget was destroyed, remove the reference
            # print(f"[prop control]TclError during update_prop_status for {prop_id}. Widget likely destroyed.")
            if 'status_label' in prop:
                del prop['status_label']
        except Exception as e:
            print(f"[prop control]Error updating prop status for {prop_id}: {e}")

    def load_flagged_prop_image(self):
        """Loads the flagged_prop image."""
        try:
            icon_dir = os.path.join("admin_icons")
            self.flagged_prop_image = ImageTk.PhotoImage(
                Image.open(os.path.join(icon_dir, "flagged_prop.png")).resize((16, 16), Image.Resampling.LANCZOS)
            )
        except Exception as e:
            print(f"[prop control] Error loading flagged prop image: {e}")
            self.flagged_prop_image = None

    def toggle_prop_flag(self, prop_id):
        """Toggles the flagged status of a prop."""
        if self.current_room is None:
            return

        if self.current_room not in self.flagged_props:
            self.flagged_props[self.current_room] = {}

        # Toggle the flag
        current_flag = self.flagged_props[self.current_room].get(prop_id, False)
        self.flagged_props[self.current_room][prop_id] = not current_flag

        self.update_prop_status(prop_id)  # Update the visual display

        if self.current_room in self.popout_windows and self.popout_windows[self.current_room]['toplevel'].winfo_exists():
            popout_controller = self.popout_windows[self.current_room]['controller']
            # Re-call update_prop_display, which will internally call _update_prop_status_icon
            # This ensures the flag icon is updated in the popout.
            # We need to pass the *current* info, which is stored in self.all_props.
            if self.current_room in self.all_props and prop_id in self.all_props[self.current_room]:
                popout_controller.update_prop_display(prop_id, self.all_props[self.current_room][prop_id]['info'])

    def load_prop_name_mappings(self):
        """Load prop name mappings from JSON file"""
        try:
            mapping_file = Path("prop_name_mapping.json")
            if mapping_file.exists():
                with open(mapping_file, 'r') as f:
                    self.prop_name_mappings = json.load(f)
                #print("[prop control]Loaded prop name mappings successfully")
            else:
                self.prop_name_mappings = {}
                print("[prop control]No prop name mapping file found")
        except Exception as e:
            print(f"[prop control]Error loading prop name mappings: {e}")
            self.prop_name_mappings = {}

    def get_mapped_prop_name(self, original_name, room_number):
        """Get the mapped name for a prop if it exists"""
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
        
        if room_number not in self.ROOM_MAP:
            return original_name
            
        room_key = self.ROOM_MAP[room_number]
        room_mappings = self.prop_name_mappings.get(room_key, {}).get('mappings', {})
        
        # Get the mapping info for this prop
        prop_info = room_mappings.get(original_name, {})
        
        # Return mapped display name if it exists and isn't empty, otherwise return original
        mapped_name = prop_info.get('display', '')
        return mapped_name if mapped_name else original_name

    def initialize_mqtt_client(self, room_number):
        """Create and connect MQTT client for a room"""
        if room_number not in self.ROOM_CONFIGS:
            return

        config = self.ROOM_CONFIGS[room_number]
        client_id = f"admin_prop_control_{room_number}_{uuid.uuid4()}"
        client = mqtt.Client(
            client_id=client_id,
            transport="websockets",
            protocol=mqtt.MQTTv31,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1
        )
        
        client.username_pw_set(self.MQTT_USER, self.MQTT_PASS)
        client.on_connect = lambda c, u, f, rc: self.on_connect(c, u, f, rc, room_number)
        client.on_message = lambda c, u, msg: self.on_message(c, u, msg, room_number)
        client.on_disconnect = lambda c, u, rc: self.on_disconnect(c, u, rc, room_number)
        
        def connect_async():
            try:
                client.ws_set_options(path="/mqtt")
                client.connect_async(config['ip'], self.MQTT_PORT, keepalive=30)
                client.loop_start() # Starts a new thread for MQTT operations

                with self._mqtt_clients_lock: # Protect modification of self.mqtt_clients
                    self.mqtt_clients[room_number] = client
                
                # Schedule timeout check on the main thread
                self._schedule_retry(room_number, 5000, lambda: self._check_connection_timeout_callback(room_number))
                
            except Exception as e:
                print(f"[prop control]Failed to connect to room {room_number}: {e}")
                error_msg = f"Connection failed. Retrying in 10 seconds..."
                self.connection_states[room_number] = error_msg
                
                # Update UI on the main thread
                if room_number == self.current_room and hasattr(self, 'status_label') and self.status_label.winfo_exists():
                    self.app.root.after(0, lambda: self.status_label.config(text=error_msg, fg='red'))
                
                # Schedule retry using after() on the main thread
                self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))
        
        # Start connection attempt in separate thread (must be created on main thread, but target runs in new thread)
        self.app.root.after(0, lambda: threading.Thread(target=connect_async, daemon=True).start())

    def check_connection_timeout(self, room_number):
        """Check if connection attempt has timed out"""
        # This function is called on the main thread via app.root.after
        
        client_to_check = None
        with self._mqtt_clients_lock: # Protect access to self.mqtt_clients
            client_to_check = self.mqtt_clients.get(room_number)

        if client_to_check and not client_to_check.is_connected():
            print(f"[prop control]Connection to room {room_number} timed out")
            room_name = self.app.rooms.get(room_number, f"Room {room_number}")
            timeout_msg = f"{room_name} props timed out;\n is the room powered on?"
            self.connection_states[room_number] = timeout_msg
            
            # Only update UI if this is the current room
            if room_number == self.current_room:
                self.app.root.after(0, lambda: self.update_connection_state(room_number, timeout_msg))
            
            # Clean up failed connection in a separate thread to avoid blocking main thread
            def cleanup():
                try:
                    with self._mqtt_clients_lock: # Protect client operations during cleanup
                        if room_number in self.mqtt_clients:
                            client_to_stop = self.mqtt_clients[room_number]
                            client_to_stop.loop_stop() # Stop the MQTT thread
                            client_to_stop.disconnect() # Attempt a clean disconnect
                            del self.mqtt_clients[room_number]
                            print(f"[prop control]Cleaned up client for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' after timeout.")
                except Exception as e:
                    print(f"[prop control]Error cleaning up client for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}': {e}")
            
            threading.Thread(target=cleanup, daemon=True).start()
            
            # Schedule retry using after() on the main thread
            self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))

    def _check_connection_timeout_callback(self, room_number): # new helper method
         # Ensures this runs on the main thread implicitly if scheduled via after
         self.check_connection_timeout(room_number)

    def restore_prop_ui(self, prop_id, prop_data):
        """Recreate UI elements for a saved prop"""
        # This method is not called anywhere in the provided code, but if it were,
        # it should ensure it's called on the main thread or marshals UI calls.
        print("[prop control]Restoring prop UI")
        if not prop_data or 'info' not in prop_data:
            return False
            
        try:
            # handle_prop_update already marshals to UI thread
            self.handle_prop_update(prop_data['info'], self.current_room)
            return True
        except Exception as e:
            print(f"[prop control]Error restoring prop UI: {e}")
            return False

    def retry_connection(self, room_number):
        """Retry connecting to a room's MQTT server without blocking"""
        # This function is called on the main thread via app.root.after
        # print(f"[prop control]Retrying connection to room {room_number}")
        
        # Start a new connection attempt in a separate thread
        def do_retry():
            # Clean up any existing client first in a thread-safe manner
            with self._mqtt_clients_lock:
                if room_number in self.mqtt_clients:
                    try:
                        old_client = self.mqtt_clients[room_number]
                        old_client.loop_stop()
                        old_client.disconnect()
                        del self.mqtt_clients[room_number]
                        print(f"[prop control]Cleaned up old client for room {room_number} before retry.")
                    except Exception as e:
                        print(f"[prop control]Error cleaning up old client for room {room_number} during retry: {e}")
            
            # Initialize new connection (this call itself will be marshaled to the main thread)
            self.app.root.after(0, lambda: self.initialize_mqtt_client(room_number))
        
        # Run the retry logic (especially cleanup) in a separate thread
        self.app.root.after(0, lambda: threading.Thread(target=do_retry, daemon=True).start())

    def connect_to_room(self, room_number):
        """Switch to controlling a different room with proper cleanup and initialize prop states."""
        # This method is called from the main thread
        if room_number == self.current_room:
            # If the popout window is already open for this room, bring it to front
            if room_number in self.popout_windows and self.popout_windows[room_number]['toplevel'].winfo_exists():
                self.popout_windows[room_number]['toplevel'].lift()
            return

        # Before clearing UI and self.props, explicitly dereference widgets for the old room
        if self.current_room is not None and self.current_room in self.all_props:
            for prop_id in self.all_props[self.current_room]:
                if prop_id in self.props: # Only dereference if it was in the active UI
                    prop_data = self.props[prop_id]
                    if 'frame' in prop_data and prop_data['frame'].winfo_exists():
                        prop_data['frame'].destroy() # Destroy the frame to clean up all its children
                    # Explicitly remove references from self.props
                    self.props.pop(prop_id, None)

        # Clear the active UI prop dictionary for the new room
        self.props = {}

        # Clear UI by destroying children of props_frame if it exists
        if hasattr(self, 'props_frame') and self.props_frame.winfo_exists():
            for widget in self.props_frame.winfo_children():
                try:
                    widget.destroy()
                except tk.TclError:
                    pass # Widget might have been destroyed already by other means or by parent destroy

        # Restore props for new room
        if room_number in self.all_props:
            for prop_id, prop_data in self.all_props[room_number].items():
                if 'last_status' not in prop_data:
                    prop_data['last_status'] = None
                # Pass the new room number
                self.handle_prop_update(prop_data['info'], room_number)
        else:
            self.all_props[room_number] = {}

        old_room = self.current_room
        self.current_room = room_number

        if room_number not in self.last_progress_times:
            self.last_progress_times[room_number] = time.time()

        self.setup_special_buttons(room_number)

        if old_room:
            self.update_prop_tracking_interval(old_room, is_selected=False)
        self.update_prop_tracking_interval(room_number, is_selected=True)

        self.fate_sent[room_number] = False
        print(f"[prop control] set fate_sent false for room {room_number}")

        if room_number not in self.standby_played:
            self.standby_played[room_number] = False
        if room_number not in self.finish_sound_played:
            self.finish_sound_played[room_number] = False

        if room_number in self.connection_states and hasattr(self, 'status_label') and self.status_label.winfo_exists():
            try:
                self.status_label.config(
                    text=self.connection_states[room_number],
                    fg='black' if "Connected" in self.connection_states[room_number] else 'red'
                )
            except tk.TclError:
                print("[prop control]Status label was destroyed, skipping update in connect_to_room")
        else:
            # If no existing connection state, try to initialize client.
            # This handles cases where client might not have been initialized due to previous errors.
            print(f"[prop control]No existing connection state for room {room_number}, attempting initialize_mqtt_client.")
            self.initialize_mqtt_client(room_number)
        
        if self.current_room is not None:
            if hasattr(self, 'popout_button') and self.popout_button.winfo_exists():
                self.popout_button.pack(side='bottom', pady=(0, 5), anchor="se")
        else:
            if hasattr(self, 'popout_button') and self.popout_button.winfo_exists():
                self.popout_button.pack_forget() # Hide if no room selected

        if(self.current_room is not None):
            self.title_label.config(text=f"{self.FULLNAME_ROOM_MAP.get(room_number, f'number {room_number}')}")

    def sort_and_repack_props(self):
        """Sorts props based on their 'order' for the *current* room and repacks them."""
        # This method is called from the main thread
        if not self.current_room or not self.props:
            return

        # Sort props based on 'order' attribute, *using the current room number*
        sorted_props = sorted(
            self.props.items(),
            key=lambda item: self.get_prop_order(item[1]['info']['strName'], self.current_room)
        )

        # Re-pack the prop frames in the sorted order
        for prop_id, prop_data in sorted_props:
            if 'frame' in prop_data and prop_data['frame'].winfo_exists():
                try:
                    prop_data['frame'].pack_forget()  # Remove from current position
                    prop_data['frame'].pack(fill='x', pady=1)  # Add back in sorted order
                except tk.TclError as e:
                    print(f"[prop control]Error repacking prop {prop_id} for room {self.current_room}: Widget destroyed? {e}")
                    # Remove the prop from self.props if its frame is destroyed
                    if prop_id in self.props:
                        del self.props[prop_id]

    def get_prop_order(self, prop_name, room_number):
        """Get the order for a prop for a specific room."""
        if room_number not in self.ROOM_MAP:
            return 999  # Default order

        room_key = self.ROOM_MAP[room_number]
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
        
        if room_key not in self.prop_name_mappings:
            return 999  # Default order

        prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_name, {})
        return prop_info.get('order', 999)

    def is_standby_prop(self, room_number, prop_name):
        """Check if a prop is marked as a standby prop"""
        if room_number not in self.ROOM_MAP:
            return False

        room_key = self.ROOM_MAP[room_number]
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()

        if room_key not in self.prop_name_mappings:
            return False

        prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_name, {})
        return prop_info.get('standby_prop', False)

    def update_prop_ui_elements(self, prop_id, prop_data):
        """Updates prop name label based on the selected room without creating a new prop UI element"""
        # This method is called from the main thread
        if prop_id not in self.props:
            return
        
        mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)
        
        # Update the name label
        name_label_widget = self.props[prop_id].get('name_label')
        if not name_label_widget or not name_label_widget.winfo_exists():
            # print(f"[prop control] Name label for prop {prop_id} not found or destroyed in update_prop_ui_elements.")
            if prop_id in self.props and 'name_label' in self.props[prop_id]:
                del self.props[prop_id]['name_label']
            return

        try:
            name_label_widget.config(text = mapped_name)
            
            # Update name label formatting
            if self.is_finishing_prop(self.current_room, prop_data['strName']):
                name_label_widget.config(font=('Arial', 8, 'bold', 'italic', 'underline'))
            elif self.is_standby_prop(self.current_room, prop_data['strName']):
                name_label_widget.config(font=('Arial', 8, 'bold', 'italic'))
            else:
                name_label_widget.config(font=('Arial', 8, 'bold'))

            # Ensure hover events for cousin highlighting are set
            name_label_widget.bind('<Enter>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, True))
            name_label_widget.bind('<Leave>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, False))
        except tk.TclError:
            # print(f"[prop control] TclError configuring name_label for prop {prop_id} in update_prop_ui_elements.")
            if prop_id in self.props and 'name_label' in self.props[prop_id]:
                del self.props[prop_id]['name_label']
        except Exception as e:
            print(f"[prop control]Unexpected error in update_prop_ui_elements for {prop_id}: {e}")

    def clean_up_room_props(self, room_number):
        """
        Safely clean up all prop widgets for a room and prepare for room switch.
        This should be called before switching rooms or clearing props.
        """
        # This method is called from the main thread
        if room_number in self.all_props:
            # Remove widget references but keep prop data (prop data is in self.all_props)
            # The actual widget destruction is handled in connect_to_room for the current room
            # For non-current rooms, their widgets don't exist in self.props anyway.
            pass # No direct action here, as self.props handles active UI, and self.all_props stores data

    def update_prop_tracking_interval(self, room_number, is_selected=False):
        """Update the tracking interval for a room's props. The periodic update loop is started on connect."""
        # This method is called from the main thread
        self.prop_update_intervals[room_number] = self.UPDATE_INTERVAL if is_selected else self.INACTIVE_UPDATE_INTERVAL
        # The update_all_props_status method will use this interval for the next scheduled call.

    def check_prop_status(self, room_number, prop_id, prop_info):
        # This method is called from the main thread
        if not prop_info or 'info' not in prop_info:
            return

        try:
            status = prop_info['info'].get('strStatus')
            last_status = self.all_props[room_number][prop_id].get('last_status')

            # --- MODIFIED PROGRESS CHECK ---
            if (last_status is not None and
                status != last_status and
                status != "offline" and
                not self.should_ignore_progress(room_number, prop_info['info'].get('strName', ''))):

                # Progress detected! Reset the stale sound flag.
                if room_number in self.stale_sound_played:
                    self.stale_sound_played[room_number] = False

                self.last_progress_times[room_number] = time.time()
            # --- END MODIFIED PROGRESS CHECK ---

            self.all_props[room_number][prop_id]['last_status'] = status

            if (status == "finished" or status == "finish" or status == "Finished" or status == "Finish"):
                if room_number not in self.last_prop_finished:
                    self.last_prop_finished[room_number] = "N/A"
                if last_status is not None and status != last_status:
                    prop_name = prop_info['info'].get('strName', 'unknown')

                    mapped_name = self.get_mapped_prop_name(prop_name, room_number)

                    self.last_prop_finished[room_number] = mapped_name

            # Check if the prop is flagged AND finished
            if (room_number in self.flagged_props and
                prop_id in self.flagged_props[room_number] and
                self.flagged_props[room_number][prop_id] and
                status == "Finished"):

                if(self.audio_manager is not None):
                    self.audio_manager.play_flagged_finish_notification()
                    print(f"[prop control] flagged prop {prop_id} finished")

                self.flagged_props[room_number][prop_id] = False
            
            # --- STANDBY PROP HANDLING --- (logic removed as per original comment in update_all_props_status, but sound calls remain)

            if room_number == self.current_room and prop_id in self.props: # Check if prop is in active UI
                # check if 'status_label' key exists and then if the widget exists
                if 'status_label' in self.props[prop_id] and self.props[prop_id]['status_label'].winfo_exists():
                    try:
                        self.update_prop_status(prop_id)
                    except tk.TclError:
                        # Widget destroyed, remove reference from active UI dict
                        del self.props[prop_id]['status_label']
                    except Exception as e:
                        print(f"[prop control]Error updating prop UI for {prop_id}: {e}")

        except Exception as e:
            prop_name = prop_info['info'].get('strName', 'unknown') if 'info' in prop_info else 'unknown'
            error_type = type(e).__name__
            trace_str = traceback.format_exc()
            print(f"[prop control]Error in check_prop_status: Room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}', Prop '{prop_name}' (ID: {prop_id})")
            print(f"[prop control]Exception type: {error_type}, Error: {str(e)}")
            print(f"[prop control]Traceback: {trace_str}")

    def play_standby_sound(self, room_number):
        """Plays the room-specific standby sound."""
        #print(f"[prop_control] Playing standby sound for room {room_number}")
        if room_number not in self.ROOM_MAP:
            return

        room_name = self.ROOM_MAP[room_number]
        sound_file = f"{room_name}_standby.mp3"
        if not self.audio_manager:
            self.audio_manager = AdminAudioManager()
        self.audio_manager._load_sound(f"{room_name}_standby", sound_file)
        self.audio_manager.play_sound(f"{room_name}_standby")

    def play_stale_sound(self, room_number):
        """Plays the room-specific stale sound."""
        #print(f"[prop_control] Playing stale sound for room {room_number}")
        if room_number not in self.ROOM_MAP:
            return

        room_name = self.ROOM_MAP[room_number]
        sound_file = f"{room_name}_stale.mp3"
        if self.audio_manager is not None:
            self.audio_manager = AdminAudioManager()
        self.audio_manager._load_sound(f"{room_name}_stale", sound_file)
        self.audio_manager.play_sound(f"{room_name}_stale")

    def play_finish_sound(self, room_number):
        """Plays the room-specific finish sound."""
        #print(f"[prop_control] Playing finish sound for room {room_number}")
        if self.audio_manager is not None:
            self.audio_manager = AdminAudioManager()
        self.audio_manager.play_sound("game_finish")

    def play_loss_sound(self, room_number):
        """Plays the room-specific loss sound."""
        if self.audio_manager is not None:
            self.audio_manager = AdminAudioManager()
        self.audio_manager.play_sound("game_fail")

    def update_all_props_status(self, room_number):
        # This method is called from the main thread
        if room_number not in self.all_props:
            return

        current_time = time.time()

        is_activated = False
        is_finished = False
        timer_expired = False
        finishing_prop_offline = False
        is_standby = False
        standby_prop_offline = False

        if room_number not in self.standby_played:
            self.standby_played[room_number] = False
        if room_number not in self.finish_sound_played:
            self.finish_sound_played[room_number] = False

        for prop_id, prop_info in list(self.all_props[room_number].items()): # Iterate over copy for safety
            if 'info' not in prop_info:
                continue

            # Access last_mqtt_updates safely with a lock
            prop_last_mqtt_update = 0
            with self._mqtt_data_lock:
                prop_last_mqtt_update = self.last_mqtt_updates.get(room_number, {}).get(prop_id, 0)

            is_offline = (current_time - prop_last_mqtt_update > 3)

            # Ensure prop_info['info'] exists before modification or access
            if 'info' not in prop_info:
                continue

            if is_offline:
                prop_info['info']['strStatus'] = "offline"
                if self.is_finishing_prop(room_number, prop_info['info'].get('strName', '')):
                    finishing_prop_offline = True
                if self.is_standby_prop(room_number, prop_info['info'].get('strName', '')):
                    standby_prop_offline = True

            status = prop_info['info'].get('strStatus')
            if status == "Activated":
                is_activated = True

            if (self.is_finishing_prop(room_number, prop_info['info'].get('strName', '')) and
                not finishing_prop_offline and
                status == "Finished"):
                is_finished = True

            if (self.is_standby_prop(room_number, prop_info['info'].get('strName', '')) and
                not standby_prop_offline and
                status == "Finished"):
                is_standby = True


            # Handle prop entering non-finished status after finish
            if (self.is_finishing_prop(room_number, prop_info['info'].get('strName', ''))
                and not finishing_prop_offline
                and status != "Finished"):
                if (room_number in self.fate_sent and self.fate_sent[room_number] == True) or \
                (room_number in self.finish_sound_played and self.finish_sound_played[room_number] == True):
                    print("[prop_control] previously finished finishing prop entered state other than offline/finished, resetting game finish status")
                    self.reset_game_finish_state(room_number)


        # Handle finishing prop going offline: implies game finish status is lost
        if finishing_prop_offline:
            is_finished = False
            if (room_number in self.fate_sent and self.fate_sent[room_number] == True) or \
            (room_number in self.finish_sound_played and self.finish_sound_played[room_number] == True):
                    self.reset_game_finish_state(room_number)

        if standby_prop_offline:
            is_standby = False
            self.reset_standby_state(room_number)


        # --- KIOSK-RELATED CHECKS (for victory message and auto-reset) ---
        assigned_kiosk = None
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                kiosk_stat_data = self.app.kiosk_tracker.kiosk_stats.get(computer_name)
                if kiosk_stat_data:
                    timer_time = kiosk_stat_data.get('timer_time', 2700)
                    timer_expired = timer_time <= 0
                assigned_kiosk = computer_name
                break

        # Update kiosk highlight (this should always run, regardless of victory status)
        self.update_kiosk_highlight(room_number, is_finished, is_activated, timer_expired)

        # --- VICTORY MESSAGE DECISION LOGIC ---
        if is_finished and not self.fate_sent.get(room_number, False):
            if assigned_kiosk and assigned_kiosk in self.app.interface_builder.connected_kiosks:
                if assigned_kiosk not in self.app.interface_builder.auto_reset_timer_ids:
                    last_sent = self.last_fate_message_time.get(assigned_kiosk)
                    if last_sent is None or (current_time - last_sent) >= self.FATE_COOLDOWN_SECONDS:
                        self._send_victory_message(room_number, assigned_kiosk)
                        # Uncomment to re-enable auto reset functionality after victory message
                        # self.app.interface_builder.start_auto_reset_timer(assigned_kiosk)
                    else:
                        cooldown_remaining = self.FATE_COOLDOWN_SECONDS - (current_time - last_sent)
                        # print(f"[prop control]Skipping victory message send for room {room_number} (kiosk {assigned_kiosk}). Cooldown active. Remaining: {cooldown_remaining:.1f}s.")
            else:
                pass # No kiosk to send victory to

        # --- AUTO-RESET TIMER FOR TIME EXPIRED (separate from victory) ---
        if timer_expired:
            if assigned_kiosk and assigned_kiosk in self.app.interface_builder.connected_kiosks:
                if assigned_kiosk not in self.app.interface_builder.auto_reset_timer_ids:
                    # Uncomment to re-enable auto reset functionality after timer expires
                    # self.app.interface_builder.start_auto_reset_timer(assigned_kiosk)
                    pass


        # --- STANDBY SOUND HANDLING ---
        if is_standby and not self.standby_played[room_number]:
            self.standby(room_number)
            self.standby_played[room_number] = True
        # --- END MODIFIED STANDBY HANDLING ---

        # --- FINISH SOUND HANDLING ---
        if is_finished and not self.finish_sound_played[room_number]:
            self.play_finish_sound(room_number)
            self.finish_sound_played[room_number] = True
        elif not is_finished:
            self.finish_sound_played[room_number] = False


        # --- UI UPDATES FOR CURRENTLY SELECTED ROOM ---
        if room_number == self.current_room:
            for prop_id, prop_info in list(self.all_props[room_number].items()): # Iterate over copy
                if prop_id in self.props: # Only update if the UI element exists
                    status_label = self.props[prop_id].get('status_label')
                    if status_label and status_label.winfo_exists():
                        self.update_prop_status(prop_id)

        # --- STALE GAME CHECK ---
        if room_number in self.last_progress_times:
            time_since_last_progress = time.time() - self.last_progress_times[room_number]
            if (is_activated and not is_finished and not timer_expired and
                time_since_last_progress >= self.STALE_THRESHOLD and
                not self.stale_sound_played.get(room_number, False)):
                room_key = self.ROOM_MAP.get(room_number)
                if room_key:
                    print(f"[prop_control] Room {room_number} ({room_key}) has been stale for {int(time_since_last_progress)}s. Playing sound.")
                    self.play_stale_sound(room_number)
                    self.stale_sound_played[room_number] = True

        # --- SCHEDULE NEXT UPDATE (ALWAYS RUNS) ---
        if room_number in self.prop_update_intervals:
            interval = self.prop_update_intervals[room_number]
            self.app.root.after(interval, lambda rn=room_number: self.update_all_props_status(rn))

    def standby(self, room_number):
        """Plays the room-specific standby sound."""
        print(f"[prop control] standby for room {room_number}")
        self.play_standby_sound(room_number)

    def reset_standby_state(self, room_number):
        """Reset the standby state for a room"""
        if room_number in self.standby_played:
            self.standby_played[room_number] = False

    def update_timer_status(self, room_number):
        """Update room status when timer changes"""
        # This method is called from the main thread
        if room_number not in self.all_props:
            return
                
        is_activated = False
        is_finished = False
        timer_expired = False
            
        # Check prop states
        for prop_id, prop_info in list(self.all_props[room_number].items()): # Iterate over copy
            if 'info' not in prop_info:
                continue
                    
            status = prop_info['info'].get('strStatus')
            if status == "Activated":
                is_activated = True
                    
            if self.is_finishing_prop(room_number, prop_info['info'].get('strName', '')):
                if status == "Finished":
                    is_finished = True
            
        # Check timer state
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    timer_time = self.app.kiosk_tracker.kiosk_stats[computer_name].get('timer_time', 2700)
                    timer_expired = timer_time <= 0
                break
            
        # Update highlighting
        self.update_kiosk_highlight(room_number, is_finished, is_activated, timer_expired)

    def on_connect(self, client, userdata, flags, rc, room_number):
        """Handle connection for a specific room's client"""
        # This callback runs in the MQTT client's background thread
        if rc == 0:
            print(f"[prop control]Room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' connected.")
            
            # Update UI on the main thread
            self.app.root.after(0, lambda:
                self.update_connection_state(room_number, "Connected")
            )

            # Cancel the timeout check timer on successful connection (on main thread)
            if room_number in self.retry_timer_ids and self.retry_timer_ids[room_number] is not None:
                self.app.root.after_cancel(self.retry_timer_ids[room_number])
                self.retry_timer_ids[room_number] = None

            # Ensure interval is set for periodic updates before scheduling the first one.
            if room_number not in self.prop_update_intervals:
                self.prop_update_intervals[room_number] = self.INACTIVE_UPDATE_INTERVAL

            # Schedule the first periodic status update call on the main thread.
            self.app.root.after(0, lambda rn=room_number: self.update_all_props_status(rn))

            # Subscribe to topics
            topics = [
                "/er/ping", "/er/name", "/er/cmd", "/er/riddles/info",
                "/er/music/info", "/er/music/soundlist", "/game/period",
                "/unixts", "/stat/games/count"
            ]
            for topic in topics:
                try:
                    result, mid = client.subscribe(topic)
                    if result != mqtt.MQTT_ERR_SUCCESS:
                        print(f"[prop control]Failed to subscribe to topic '{topic}' for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}'. Result code: {result}")
                except Exception as e:
                    print(f"[prop control]Exception while subscribing to topic '{topic}' for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' on connect: {e}")

            # Clear the disconnect history after 5 seconds of stable connection (on main thread)
            def clear_disconnect_history_main_thread():
                with self._mqtt_data_lock: # Protect shared history list
                    if room_number in self.disconnect_rc7_history:
                        print(f"[prop control] Connection to room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' stable for 5s. Clearing rc=7 history.")
                        del self.disconnect_rc7_history[room_number]
            
            self.app.root.after(10000, clear_disconnect_history_main_thread)

        else:
            status = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }.get(rc, f"Unknown error (code {rc})")
            
            error_msg = f"Connection failed: {status}. Retrying in 10 seconds..."
            # Update UI on the main thread
            self.app.root.after(0, lambda: self.update_connection_state(room_number, error_msg))

            # Schedule retry (on main thread)
            self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))

    def update_connection_state(self, room_number, state):
        """Update the connection state display - only shows error states"""
        # This method is called from the main thread
        self.connection_states[room_number] = state

        if room_number == self.current_room and hasattr(self, 'status_label') and self.status_label.winfo_exists():
            self.app.root.after(0, lambda:
                self._update_connection_state_ui(room_number, state)
            )

    def _update_connection_state_ui(self, room_number, state):
        # This method is called from the main thread
        if room_number == self.current_room and hasattr(self, 'status_label') and self.status_label.winfo_exists():
            try:
                if any(error in state.lower() for error in ["failed", "timed out", "connecting", "lost"]):
                    self.status_label.config(
                        text=state,
                        fg='red'
                    )
                    # Clear props display on connection issues
                    if hasattr(self, 'props_frame') and self.props_frame.winfo_exists():
                        for widget in self.props_frame.winfo_children():
                            try:
                                widget.destroy()
                            except tk.TclError:
                                pass
                    self.props = {} # Explicitly clear the active UI dictionary
                else:
                    self.status_label.config(text="") # Clear status text for non-error states
            except tk.TclError:
                print(f"[prop control]Status label widget was destroyed while trying to update for room {room_number}.")
            except Exception as e:
                print(f"[prop control]Unexpected error updating connection state UI for room {room_number}: {e}")

    def setup_special_buttons(self, room_number):
        # This method is called from the main thread
        for widget in self.special_frame.winfo_children():
            try: # Ensure widgets are destroyed safely
                widget.destroy()
            except tk.TclError:
                pass
            
        if room_number not in self.ROOM_CONFIGS:
            return
            
        buttons_grid = ttk.Frame(self.special_frame)
        buttons_grid.pack(fill='x', padx=1, pady=1)
        
        buttons_grid.columnconfigure(0, weight=1)
        buttons_grid.columnconfigure(1, weight=1)
        
        button_style = {
            'background': '#ffcccc',
            'font': ('Arial', 7),
            'wraplength': 60,
            'height': 1,
            'width': 8,
            'relief': 'raised',
            'padx': 1,
            'pady': 1
        }
        
        buttons = self.ROOM_CONFIGS[room_number]['special_buttons']
        for i, (button_text, command_name) in enumerate(buttons):
            row = i // 2
            col = i % 2
            
            if command_name.startswith('quest/'):
                quest_type = command_name.split('/')[1]
                btn = tk.Button(
                    buttons_grid, 
                    text=button_text,
                    command=lambda qt=quest_type: self.send_quest_command(qt),
                    **button_style,
                    cursor="hand2"
                )
            else:
                btn = tk.Button(
                    buttons_grid, 
                    text=button_text,
                    command=lambda pn=command_name: self.send_special_command(pn, "on"),
                    **button_style,
                    cursor="hand2"
                )
                
            btn.grid(row=row, column=col, padx=1, pady=1, sticky='nsew')

    def should_ignore_progress(self, room_number, prop_name):
        """Check if a prop should be ignored for progress tracking"""
        if room_number not in self.ROOM_MAP:
            return False
            
        room_key = self.ROOM_MAP[room_number]
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
            
        if room_key not in self.prop_name_mappings:
            return False
            
        prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_name, {})
        return prop_info.get('ignore_progress', False)

    def on_message(self, client, userdata, msg, room_number):
        """Handle messages for all rooms, including tracking prop status changes."""
        # This callback runs in the MQTT client's background thread
        try:
            if msg.topic == "/er/riddles/info":
                payload = json.loads(msg.payload.decode())
                
                if room_number not in self.all_props:
                    self.all_props[room_number] = {}
                    
                prop_id = payload.get("strId")
                if prop_id:
                    # Update MQTT last update time, protected by a lock
                    with self._mqtt_data_lock:
                        if room_number not in self.last_mqtt_updates:
                            self.last_mqtt_updates[room_number] = {}
                        self.last_mqtt_updates[room_number][prop_id] = time.time()
                    
                    if prop_id not in self.all_props[room_number]:
                        self.all_props[room_number][prop_id] = {
                            'info': payload.copy(),
                            'last_update': time.time(),
                            'last_status': None
                        }
                    else:
                        self.all_props[room_number][prop_id]['info'] = payload.copy()

                    _payload_copy = payload.copy()
                    # Marshal calls to handle_prop_update and check_prop_status to the main thread
                    self.app.root.after(0, lambda pdata=_payload_copy, rn=room_number: self.handle_prop_update(pdata, rn))
                    self.app.root.after(0, lambda pid=prop_id, rn=room_number: self.check_prop_status(
                        rn, pid, self.all_props[rn].get(pid, {}) # Pass a copy or safely get data
                    ))
                        
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"[prop control]Failed to decode or parse message from room {room_number}: {e}. Payload: {msg.payload}")
        except Exception as e:
            print(f"[prop control]Error handling message from room {room_number}: {e}. Traceback:\n{traceback.format_exc()}")

    def on_disconnect(self, client, userdata, rc, room_number):
        """Handle disconnection for a specific room's client, with aggressive retry for rc=7."""
        # This callback runs in the MQTT client's background thread
        room_name = self.app.rooms.get(room_number, f"Room {room_number}")
        current_time = time.time()
        print(f"[prop control]Room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' disconnected with code: {rc} at {current_time}")

        with self._mqtt_data_lock: # Protect access to disconnect_rc7_history
            if rc == 7:
                if room_number not in self.disconnect_rc7_history:
                    self.disconnect_rc7_history[room_number] = []

                self.disconnect_rc7_history[room_number].append(current_time)
                
                self.disconnect_rc7_history[room_number] = [
                    ts for ts in self.disconnect_rc7_history[room_number]
                    if current_time - ts <= 10
                ]
                disconnect_count = len(self.disconnect_rc7_history[room_number])

                if disconnect_count >= 2:
                    print(f"[prop control]Detected {disconnect_count} rc=7 disconnects in <=10s for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}'. Triggering aggressive retry.")
                    # Trigger the aggressive retry (marshaled to main thread as it involves UI updates and threading)
                    self.app.root.after(0, lambda: self.aggressive_retry(room_number))
                    self.disconnect_rc7_history[room_number] = [] # Clear history after triggering
                    return
            else:
                if room_number in self.disconnect_rc7_history:
                    del self.disconnect_rc7_history[room_number]

        # Standard retry logic (for non-zero rc OR rc=7 below threshold)
        if rc != 0:
            status_msg = ""
            if rc == 7:
                count_info = f" (Count: {disconnect_count})" if 'disconnect_count' in locals() else ""
                status_msg = f"Connection to {room_name} props lost (Code 7{count_info}). Retrying in 10 seconds..."
            else:
                status_msg = f"Connection to {room_name} props lost (Code {rc}). Retrying in 10 seconds..."

            # Update UI and schedule retry on the main thread
            self.app.root.after(0, lambda: self.update_connection_state(room_number, status_msg))
            self.app.root.after(0, lambda: self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number)))

    def aggressive_retry(self, room_number):
        """Performs a more aggressive retry for a room after repeated failures."""
        # This method is called from the main thread
        print(f"[prop control]Triggering aggressive retry for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}'")
        room_name = self.app.rooms.get(room_number, f"Room {room_number}")

        # Update UI status immediately
        self.update_connection_state(room_number, f"Room {room_name}: Repeated disconnects (code 7). Waiting 5s before aggressive retry...")

        def do_aggressive_retry_thread():
            # Clean up current client immediately in a thread-safe manner
            with self._mqtt_clients_lock:
                if room_number in self.mqtt_clients:
                    try:
                        old_client = self.mqtt_clients[room_number]
                        old_client.loop_stop()
                        old_client.disconnect()
                        del self.mqtt_clients[room_number]
                        print(f"[prop control]Cleaned up old client for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' during aggressive retry.")
                    except Exception as e:
                        print(f"[prop control]Error cleaning up old client during aggressive retry for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}': {e}")

            # Wait for 5 seconds (blocking part)
            time.sleep(5)

            # Schedule the reconnection on the main thread
            print(f"[prop control]Aggressive retry: Scheduling new connection initialization for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}'")
            self.app.root.after(0, lambda: self.initialize_mqtt_client(room_number))

        # Start the aggressive retry process in a new thread
        threading.Thread(target=do_aggressive_retry_thread, daemon=True).start()

    def handle_prop_update(self, prop_data, originating_room_number):
        """Marshal prop update processing to the main Tkinter thread."""
        self.app.root.after(0, lambda pdata=prop_data, rn=originating_room_number: self._handle_prop_update_ui(pdata, rn))

    def _handle_prop_update_ui(self, prop_data, originating_room_number):
        """Actual implementation of handle_prop_update, running on the main thread."""
        prop_id = prop_data.get("strId")
        if not prop_id:
            return

        if originating_room_number != self.current_room:
            # If there's a popout window for this non-current room, update it.
            if originating_room_number in self.popout_windows and self.popout_windows[originating_room_number]['toplevel'].winfo_exists():
                popout_controller = self.popout_windows[originating_room_number]['controller']
                popout_controller.update_prop_display(prop_id, prop_data)
            return

        order = self.get_prop_order(prop_data["strName"], self.current_room)
        current_status = prop_data.get("strStatus", "")

        # Check for status changes and update last_progress_times
        if self.current_room is not None and self.current_room in self.all_props:
            previous_status = self.all_props[self.current_room].get(prop_id, {}).get('last_status')
            if (previous_status is not None and
                current_status != previous_status and
                current_status != "offline" and
                not self.should_ignore_progress(self.current_room, prop_data["strName"])):
                self.last_progress_times[self.current_room] = time.time()

            if current_status in ("finished", "finish", "Finished", "Finish"):
                if self.current_room not in self.last_prop_finished:
                    self.last_prop_finished[self.current_room] = ""
                if previous_status is not None and current_status != previous_status:
                    prop_name = prop_data.get("strName", "unknown")
                    mapped_name = self.get_mapped_prop_name(prop_name, self.current_room)
                    self.last_prop_finished[self.current_room] = mapped_name

        try:
            if prop_id not in self.props:
                # Create new prop widgets
                prop_frame = ttk.Frame(self.props_frame)
                button_frame = ttk.Frame(prop_frame)
                button_frame.pack(side='left', padx=(0, 5))

                # Buttons (these are correctly packed inside button_frame)
                reset_btn = tk.Button(button_frame, text="R", font=('Arial', 5, 'bold'),
                                      command=lambda: self.send_command(prop_id, "reset"),
                                      bg='#cc362b', width=2, height=5, cursor="hand2")
                prop_name = prop_data.get("strName", "")
                if prop_name:
                    reset_btn.bind('<Enter>', lambda e, name=prop_name: self.highlight_circuit_props(name, True))
                    reset_btn.bind('<Leave>', lambda e, name=prop_name: self.highlight_circuit_props(name, False))
                reset_btn.pack(side='left', padx=1)

                activate_btn = tk.Button(button_frame, text="A", font=('Arial', 5, 'bold'),
                                         command=lambda: self.send_command(prop_id, "activate"),
                                         bg='#ff8c00', width=2, height=5, cursor="hand2")
                activate_btn.pack(side='left', padx=1)

                finish_btn = tk.Button(button_frame, text="F", font=('Arial', 5, 'bold'),
                                       command=lambda: self.send_command(prop_id, "finish"),
                                       bg='#28a745', width=2, height=5, cursor="hand2")
                finish_btn.pack(side='left', padx=1)

                # --- LAYOUT FIX: Pack Status Label THEN Name Label, both from the left ---

                # Status Label: Pack this first, immediately to the right of the buttons
                status_label = tk.Label(prop_frame)
                status_label.pack(side='left', padx=5) # Changed from 'right' to 'left'

                mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)

                # Name Label: Pack this second, immediately to the right of the status icon
                name_label = ttk.Label(prop_frame, font=('Arial', 8, 'bold'), text=mapped_name)
                if self.is_finishing_prop(self.current_room, prop_data['strName']):
                    name_label.config(font=('Arial', 8, 'bold', 'italic', 'underline'))
                elif self.is_standby_prop(self.current_room, prop_data['strName']):
                    name_label.config(font=('Arial', 8, 'bold', 'italic'))
                name_label.pack(side='right', padx=5)

                name_label.bind('<Button-1>', lambda e, name=prop_data["strName"]: self.notify_prop_select(name))
                name_label.config(cursor="hand2")
                name_label.bind('<Enter>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, True))
                name_label.bind('<Leave>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, False))

                self.props[prop_id] = {
                    'frame': prop_frame,
                    'status_label': status_label,
                    'info': prop_data,
                    'last_update': time.time(),
                    'order': order,
                    'name_label': name_label,
                }
                
                # Set initial last status
                if self.current_room not in self.all_props:
                    self.all_props[self.current_room] = {}
                if prop_id not in self.all_props[self.current_room]:
                    self.all_props[self.current_room][prop_id] = {}
                self.all_props[self.current_room][prop_id]['last_status'] = current_status

                self.sort_and_repack_props()

            else: # Prop exists, update its info
                current_prop_data = self.props[prop_id]
                name_label = current_prop_data.get('name_label')
                status_label = current_prop_data.get('status_label')

                if name_label and name_label.winfo_exists():
                    current_prop_data['info'] = prop_data
                    current_prop_data['last_update'] = time.time()
                    current_prop_data['order'] = order
                    mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)
                    name_label.config(text=mapped_name)

                    if self.current_room not in self.all_props:
                        self.all_props[self.current_room] = {}
                    if prop_id not in self.all_props[self.current_room]:
                        self.all_props[self.current_room][prop_id] = {}
                    self.all_props[self.current_room][prop_id]['last_status'] = current_status

                    if self.is_finishing_prop(self.current_room, prop_data['strName']):
                        name_label.config(font=('Arial', 9, 'bold', 'italic', 'underline'))
                    elif self.is_standby_prop(self.current_room, prop_data['strName']):
                        name_label.config(font=('Arial', 9, 'italic'))
                    else:
                        name_label.config(font=('Arial', 8, 'bold'))
                else:
                    if 'name_label' in current_prop_data:
                        del current_prop_data['name_label']
                        # Consider destroying the whole prop entry if critical widgets are gone
                        # print(f"[prop control]name_label for {prop_id} gone, considering prop as invalid.")
                        # del self.props[prop_id] # Might be too aggressive, depends on desired behavior

                if status_label and status_label.winfo_exists():
                    self.update_prop_status(prop_id)

            self.check_finishing_prop_status(prop_id, prop_data)

        except tk.TclError as e:
            print(f"[prop control]Widget error in _handle_prop_update_ui for prop {prop_id} in room {originating_room_number}: {e}")
            if prop_id in self.props:
                # Attempt to destroy any lingering sub-widgets and then remove the main entry
                for key in ['frame', 'status_label', 'name_label']:
                    if key in self.props[prop_id] and self.props[prop_id][key] and self.props[prop_id][key].winfo_exists():
                        try:
                            self.props[prop_id][key].destroy()
                        except tk.TclError:
                            pass
                del self.props[prop_id]
        except Exception as e:
            print(f"[prop control]Unexpected error in _handle_prop_update_ui for {prop_id}: {e}. Traceback:\n{traceback.format_exc()}")


    def get_prop_circuit(self, prop_name):
        """Get the circuit value for a prop if it exists"""
        if self.current_room not in self.ROOM_MAP:
            return None
            
        room_key = self.ROOM_MAP[self.current_room]
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
            
        if room_key not in self.prop_name_mappings:
            return None
            
        prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_name, {})
        return prop_info.get('circuit')

    def get_prop_cousin(self, prop_name):
        """Get the cousin value for a prop if it exists"""
        if self.current_room not in self.ROOM_MAP:
            return None
            
        room_key = self.ROOM_MAP[self.current_room]
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
            
        if room_key not in self.prop_name_mappings:
            return None
            
        prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_name, {})
        return prop_info.get('cousin')

    def highlight_circuit_props(self, prop_name, highlight):
        """Highlight or unhighlight props that share the same circuit"""
        # This method is called from the main thread (Tkinter event binding)
        circuit = self.get_prop_circuit(prop_name)
        if not circuit:
             return
             
        if self.current_room not in self.ROOM_MAP:
            return
        room_key = self.ROOM_MAP[self.current_room]
        
        if not hasattr(self, 'prop_name_mappings') or room_key not in self.prop_name_mappings or \
           'mappings' not in self.prop_name_mappings[room_key]:
            return
            
        circuit_props = []
        
        for name, info in self.prop_name_mappings[room_key]['mappings'].items():
             if info.get('circuit') == circuit:
                 circuit_props.append(name)
                
        for prop_id, prop_data in list(self.props.items()): # Iterate over a copy
            if prop_data['info']['strName'] in circuit_props:
                try:
                    prop_frame = prop_data.get('frame')
                    name_label = prop_data.get('name_label')
                    if prop_frame and prop_frame.winfo_exists() and name_label and name_label.winfo_exists():
                        if highlight:
                            prop_frame.configure(style='Circuit.TFrame')
                            name_label.configure(style='Circuit.TLabel')
                        else:
                            prop_frame.configure(style='TFrame')
                            name_label.configure(style='TLabel')
                except tk.TclError:
                    # Widget destroyed, remove reference
                    if prop_id in self.props:
                        del self.props[prop_id] # Remove the whole prop entry if its widgets are gone
                except Exception as e:
                    print(f"[prop control]Error highlighting circuit prop {prop_id}: {e}")

    def highlight_cousin_props(self, prop_name, highlight):
        """Highlight or unhighlight props that are cousins"""
        # This method is called from the main thread (Tkinter event binding)
        cousin = self.get_prop_cousin(prop_name)
        if not cousin:
             return
             
        if self.current_room not in self.ROOM_MAP:
            return
        room_key = self.ROOM_MAP[self.current_room]

        if not hasattr(self, 'prop_name_mappings') or room_key not in self.prop_name_mappings or \
           'mappings' not in self.prop_name_mappings[room_key]:
            return

        cousin_props = []
        
        for name, info in self.prop_name_mappings[room_key]['mappings'].items():
             if info.get('cousin') == cousin:
                 cousin_props.append(name)
                
        for prop_id, prop_data in list(self.props.items()): # Iterate over a copy
            if prop_data['info']['strName'] in cousin_props:
                try:
                    prop_frame = prop_data.get('frame')
                    name_label = prop_data.get('name_label')
                    if prop_frame and prop_frame.winfo_exists() and name_label and name_label.winfo_exists():
                        if highlight:
                            prop_frame.configure(style='Cousin.TFrame')
                            name_label.configure(style='Cousin.TLabel')
                        else:
                            prop_frame.configure(style='TFrame')
                            name_label.configure(style='TLabel')
                except tk.TclError:
                    # Widget destroyed, remove reference
                    if prop_id in self.props:
                        del self.props[prop_id]
                except Exception as e:
                    print(f"[prop control]Error highlighting cousin prop {prop_id}: {e}")

    def is_finishing_prop(self, room_number, prop_name):
        """Check if a prop is marked as a finishing prop"""
        if room_number not in self.ROOM_MAP:
            return False
            
        room_key = self.ROOM_MAP[room_number]
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
            
        if room_key not in self.prop_name_mappings:
            return False
            
        prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_name, {})
        return prop_info.get('finishing_prop', False)

    def check_finishing_prop_status(self, prop_id, prop_data):
        # This method is called from the main thread
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()

        prop_name = prop_data.get("strName")
        if not prop_name:
            return

        if self.current_room not in self.ROOM_MAP:
            return

        room_key = self.ROOM_MAP[self.current_room]

        # This method is purely for internal logic and doesn't directly interact with kiosks or network
        # The kiosk interaction logic is handled in update_all_props_status.
        pass

    def reset_game_finish_state(self, room_number):
        # This method is called from the main thread
        print(f"[prop control]reset game finish state for room {room_number}")
        if room_number in self.fate_sent:
            self.fate_sent[room_number] = False

        if room_number in self.finish_sound_played:
            self.finish_sound_played[room_number] = False

    def update_kiosk_highlight(self, room_number, is_finished, is_activated, timer_expired=False):
        # This method is called from the main thread
        assigned_kiosk = None
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                assigned_kiosk = computer_name
                break

        if not assigned_kiosk:
            return

        kiosk_data = self.app.interface_builder.connected_kiosks.get(assigned_kiosk)
        if not kiosk_data:
            return

        kiosk_frame = kiosk_data.get('frame')
        if not kiosk_frame or not kiosk_frame.winfo_exists():
            return

        try:
            if timer_expired:
                if not self.audio_manager.loss_sound_played.get(room_number, False):
                    #print(f"[interface builder] Timer expired for room {room_number}. Playing loss sound.")
                    self.play_loss_sound(room_number)
                    if(self.audio_manager is not None):
                        self.audio_manager.loss_sound_played[room_number] = True
                    else:
                        self.audio_manager = AdminAudioManager()
                new_color = '#FFB6C1' # Light Pink
            elif is_finished:
                new_color = '#90EE90' # Light Green
            elif is_activated:
                new_color = '#faf8ca' # Pale Yellow
            else:
                try:
                    new_color = kiosk_frame.winfo_toplevel().option_get('background', '') or ttk.Style().lookup('TFrame', 'background') or "#F0F0F0"
                except tk.TclError:
                    new_color = "#F0F0F0"

            kiosk_frame.configure(bg=new_color)
            for widget in kiosk_frame.winfo_children():
                if widget.winfo_exists():
                    if not isinstance(widget, (tk.Button, ttk.Combobox, ttk.Menubutton)):
                        try:
                            widget.configure(bg=new_color)
                        except tk.TclError:
                            pass
        except tk.TclError:
            print(f"[prop control]TclError: Widget for kiosk {assigned_kiosk} was (likely) destroyed during update_kiosk_highlight")
        except Exception as e:
            print(f"[prop control]Error updating kiosk highlight for {assigned_kiosk}: {e}. Traceback:\n{traceback.format_exc()}")

    def _send_victory_message(self, room_number, computer_name):
        """Sends a victory message to the kiosk (internal use) with a cooldown."""
        # This method is called from the main thread
        current_time = time.time()

        if hasattr(self.app, 'network_handler') and self.app.network_handler:
            try:
                self.app.network_handler.send_victory_message(room_number, computer_name)
                self.fate_sent[room_number] = True
                self.last_fate_message_time[computer_name] = current_time
            except Exception as e:
                print(f"[prop control]Error sending victory message for room {room_number} to kiosk {computer_name}: {e}. Traceback:\n{traceback.format_exc()}")
        else:
            print("[prop control]Network handler not available, cannot send victory message.")

    def send_command(self, prop_id, command):
        """Send command to standard props"""
        # This method is called from the main thread
        target_room = self.current_room
        if target_room is None:
            print("[prop control]No active room selected to send command.")
            return
            
        with self._mqtt_clients_lock: # Protect access to self.mqtt_clients
            client = self.mqtt_clients.get(target_room)

        if not client:
            print(f"[prop control]MQTT client not available for room {target_room}.")
            return
        
        if not client.is_connected():
            print(f"[prop control]MQTT client for room {target_room} is not connected, command '{command}' to {prop_id} aborted.")
            self.update_connection_state(target_room, f"Not connected to {self.ROOM_MAP.get(target_room, f'Room {target_room}')}")
            return

        topic = f"/er/{prop_id}/cmd"
        try:
            client.publish(topic, command)
            print(f"[prop control]Command '{command}' sent successfully to prop '{prop_id}' in room {target_room}.")
        except Exception as e:
            print(f"[prop control]Failed to send command '{command}' to prop '{prop_id}' in room {target_room}: {e}. Traceback:\n{traceback.format_exc()}")

    def send_special_command(self, prop_name, command):
        """Send command to special pneumatic props"""
        # This method is called from the main thread
        target_room = self.current_room
        if target_room is None:
            print(f"[prop control]No active room selected to send special command.")
            return
            
        prop_map = {
            'barrel': 'pnevmo2',
            'kitchen': 'pnevmo1',
            'cage': 'pnevmo3',
            'door': 'pnevmo4'
        }
        
        if prop_name not in prop_map:
            print(f"[prop control]Unknown special prop: {prop_name}")
            return
            
        with self._mqtt_clients_lock: # Protect access to self.mqtt_clients
            client = self.mqtt_clients.get(target_room)
        
        if not client:
            print(f"[prop control]MQTT client not available for room {target_room} for special command.")
            return

        if not client.is_connected():
            print(f"[prop control]MQTT client for room {target_room} is not connected, special command '{command}' to {prop_name} aborted.")
            self.update_connection_state(target_room, f"Not connected to {self.ROOM_MAP.get(target_room, f'Room {target_room}')}")
            return

        topic = f"/er/{prop_map[prop_name]}"
        
        try:
            print(f"[prop control]Sending pneumatic prop command: Room: {target_room}, Prop: {prop_name}, Topic: {topic}")
            client.publish(topic, "trigger", qos=0, retain=False)
            print(f"[prop control]Command sent successfully to special prop {prop_name}.")
        except Exception as e:
            print(f"[prop control]Failed to send special command to {prop_name} in room {target_room}: {e}. Traceback:\n{traceback.format_exc()}")

    def on_frame_configure(self, event=None):
        """Reconfigure the canvas scrolling region"""
        # This method is called from the main thread (Tkinter event binding)
        try:
            if self.canvas.winfo_exists() and self.props_frame.winfo_exists():
                self.canvas.configure(scrollregion=self.canvas.bbox("all"))
                width = self.canvas.winfo_width()
                self.canvas.itemconfig(self.canvas_frame, width=width)
        except tk.TclError:
            print("[prop control]TclError in on_frame_configure, likely widget destroyed.")
            pass # Safely ignore if widgets are gone
        except Exception as e:
            print(f"[prop control]Error in on_frame_configure: {e}. Traceback:\n{traceback.format_exc()}")

    def notify_prop_select(self, prop_name):
        """Notify all registered callbacks about prop selection"""
        # This method is called from the main thread (Tkinter event binding)
        if hasattr(self, 'prop_select_callbacks'):
            for callback in list(self.prop_select_callbacks): # Iterate over a copy for safety
                try:
                    callback(prop_name)
                except Exception as e:
                    print(f"[prop control]Error in prop_select_callback for {prop_name}: {e}. Traceback:\n{traceback.format_exc()}")

    def add_prop_select_callback(self, callback):
        """Add a callback to be called when a prop is selected"""
        # This method is called from the main thread
        if not hasattr(self, 'prop_select_callbacks'):
            self.prop_select_callbacks = []
        self.prop_select_callbacks.append(callback)

    def on_canvas_configure(self, event):
        """Handle canvas resize"""
        # This method is called from the main thread (Tkinter event binding)
        try:
            if self.canvas.winfo_exists() and self.props_frame.winfo_exists():
                width = event.width
                self.canvas.itemconfig(self.canvas_frame, width=width)
        except tk.TclError:
            print("[prop control]TclError in on_canvas_configure, likely widget destroyed.")
            pass
        except Exception as e:
            print(f"[prop control]Error in on_canvas_configure: {e}. Traceback:\n{traceback.format_exc()}")
        
    def create_popout_window(self):
        """Creates a new popout window for the currently selected room's props."""
        # This method is called from the main thread
        if self.current_room is None:
            print("[prop control]Cannot popout: No room currently selected.")
            return

        if self.current_room in self.popout_windows and self.popout_windows[self.current_room]['toplevel'].winfo_exists():
            print(f"[prop control]Popout for room {self.current_room} already open. Bringing to front.")
            self.popout_windows[self.current_room]['toplevel'].lift()
            return

        room_name = self.ROOM_MAP.get(self.current_room, f"Room {self.current_room}")
        print(f"[prop control]Creating popout window for room {room_name} (ID: {self.current_room}).")

        try:
            toplevel = tk.Toplevel(self.app.root)
            toplevel.transient(self.app.root)
            toplevel.geometry("300x500")

            popout_controller = PropControlPopout(toplevel, self, self.current_room)

            self.popout_windows[self.current_room] = {
                'toplevel': toplevel,
                'controller': popout_controller
            }

        except Exception as e:
            print(f"[prop control]Error creating popout window for room {self.current_room}: {e}. Traceback:\n{traceback.format_exc()}")
            if self.current_room in self.popout_windows:
                if 'toplevel' in self.popout_windows[self.current_room] and \
                   self.popout_windows[self.current_room]['toplevel'].winfo_exists():
                    self.popout_windows[self.current_room]['toplevel'].destroy()
                del self.popout_windows[self.current_room]

    def popout_closed(self, room_number):
        """Callback from PropControlPopout when it is closed."""
        # This method is called from the main thread (via popout window's protocol handler)
        if room_number in self.popout_windows:
            print(f"[prop control]Popout for room {room_number} closed.")
            del self.popout_windows[room_number]

    def shutdown(self):
        """Performs a graceful shutdown of all MQTT clients and popout windows."""
        # This method is called from the main thread during app shutdown
        with self._mqtt_clients_lock: # Ensure no other threads are accessing/modifying clients
            for room_num in list(self.mqtt_clients.keys()): # Iterate over copy of keys
                client = self.mqtt_clients.get(room_num)
                if client:
                    try:
                        client.loop_stop()
                        print(f"[prop control]Stopped MQTT loop for room {room_num}.")
                    except Exception as e:
                        print(f"[prop control]Error stopping MQTT loop for client for room {room_num}: {e}")
                    try:
                        client.disconnect()
                        print(f"[prop control]Disconnected MQTT client for room {room_num}.")
                    except Exception as e:
                        print(f"[prop control]Error disconnecting MQTT client for room {room_num}: {e}")
                    del self.mqtt_clients[room_num] # Remove from tracking after shutdown

        for room_num in list(self.popout_windows.keys()):
            popout_info = self.popout_windows.get(room_num)
            if popout_info and popout_info['toplevel'].winfo_exists():
                try:
                    popout_info['toplevel'].destroy()
                    print(f"[prop control]Closed popout window for room {room_num}.")
                except tk.TclError:
                    pass # Already destroyed, ignore
            if room_num in self.popout_windows: # Double check in case already removed by popout_closed
                del self.popout_windows[room_num]
        print("[prop control]All popout windows closed during shutdown.")

    def start_game(self, room_number=None):
        """Send start game command to the specified room or current room if None."""
        # This method is called from the main thread
        target_room = room_number if room_number is not None else self.current_room

        if target_room is None:
            print("[prop control]Start game: No target room specified or selected.")
            return
        
        with self._mqtt_clients_lock: # Protect access to self.mqtt_clients
            client = self.mqtt_clients.get(target_room)

        if not client:
            room_name_for_log = self.app.rooms.get(target_room, f"number {target_room}")
            print(f"[prop control]Start game: MQTT client not available for room '{room_name_for_log}' (ID: {target_room}).")
            return

        if not client.is_connected():
            print(f"[prop control]MQTT client for room {target_room} is not connected, start game command aborted.")
            self.update_connection_state(target_room, f"Not connected to {self.ROOM_MAP.get(target_room, f'Room {target_room}')}")
            return
            
        try:
            client.publish("/er/cmd", "start")
            room_name_for_log = self.app.rooms.get(target_room, f"number {target_room}")
            print(f"[prop control]Start game command sent to room '{room_name_for_log}' (ID: {target_room}).")
            
            # Reset progress/state tracking for the started room
            self.last_progress_times[target_room] = time.time()
            self.stale_sound_played[target_room] = False
            self.fate_sent[target_room] = False
                 
        except Exception as e:
            room_name_for_log = self.app.rooms.get(target_room, f"number {target_room}")
            print(f"[prop control]Failed to send start game command to room '{room_name_for_log}' (ID: {target_room}): {e}. Traceback:\n{traceback.format_exc()}")

    def reset_all(self):
        """Send reset all command to current room"""
        # This method is called from the main thread
        target_room = self.current_room
        if target_room is None:
            print("[prop control]No active room selected to reset.")
            return
            
        with self._mqtt_clients_lock: # Protect access to self.mqtt_clients
            client = self.mqtt_clients.get(target_room)

        if not client:
            print(f"[prop control]MQTT client not available for room {target_room} to reset.")
            return

        if not client.is_connected():
            print(f"[prop control]MQTT client for room {target_room} is not connected, reset command aborted.")
            self.update_connection_state(target_room, f"Not connected to {self.ROOM_MAP.get(target_room, f'Room {target_room}')}")
            return
        
        try:
            client.publish("/er/cmd", "reset")
            print(f"[prop control]Reset all command sent to room {target_room}")
        except Exception as e:
            print(f"[prop control]Failed to send reset all command to room {target_room}: {e}. Traceback:\n{traceback.format_exc()}")
            
            
        self.app.root.after(5000,lambda: self._status_reset_upon_reset(target_room))

    def _status_reset_upon_reset(self, target_room):
        try:
            # Also reset progress/state tracking for the reset room
            self.last_progress_times[target_room] = time.time()
            self.stale_sound_played[target_room] = False
            self.fate_sent[target_room] = False # Reset fate_sent on game reset
            self.finish_sound_played[target_room] = False # Reset finish_sound_played on game reset
            self.standby_played[target_room] = False # Reset standby_played on game reset
            
            # Clear status label after successful reset
            if self.current_room == target_room:
                self.status_label.config(text="Props reset successfully.", fg='black')

        except Exception as e:
            print(f"[prop control]Failed to send reset all command to room {target_room}: {e}. Traceback:\n{traceback.format_exc()}")
            if self.current_room == target_room:
                self.status_label.config(text=f"Failed to reset props: {e}", fg='red')

    def send_quest_command(self, quest_type):
        """Send quest command to the current room."""
        # This method is called from the main thread
        target_room = self.current_room
        if target_room is None:
            print("[prop control]No active room selected to send quest command.")
            return
            
        with self._mqtt_clients_lock: # Protect access to self.mqtt_clients
            client = self.mqtt_clients.get(target_room)

        if not client:
            print(f"[prop control]MQTT client not available for room {target_room} to send quest command.")
            return

        if not client.is_connected():
            print(f"[prop control]MQTT client for room {target_room} is not connected, quest command '{quest_type}' aborted.")
            self.update_connection_state(target_room, f"Not connected to {self.ROOM_MAP.get(target_room, f'Room {target_room}')}")
            return

        topic = "/er/quest"
        try:
            client.publish(topic, quest_type)
            print(f"[prop control]Quest command '{quest_type}' sent successfully to room {target_room}")
        except Exception as e:
            print(f"[prop control]Failed to send quest command '{quest_type}' to room {target_room}: {e}. Traceback:\n{traceback.format_exc()}")

    def _schedule_retry(self, room_number, delay, callback):
        """Cancels any pending retry for the room and schedules a new one."""
        # This method is called from the main thread
        if room_number in self.retry_timer_ids and self.retry_timer_ids[room_number] is not None:
            try:
                self.app.root.after_cancel(self.retry_timer_ids[room_number])
            except ValueError:
                # Timer might have already fired or been cancelled
                pass
            self.retry_timer_ids[room_number] = None

        timer_id = self.app.root.after(delay, callback)
        self.retry_timer_ids[room_number] = timer_id