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

class PropControl:
    ROOM_MAP = {
        3: "wizard",
        1: "casino",
        2: "ma",
        5: "haunted",
        4: "zombie",
        6: "atlantis",
        7: "time"  # Note: This maps to "time_machine" in some contexts
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

    def __init__(self, app):
        self.app = app
        self.props = {}  # strId -> prop info
        self.mqtt_clients = {}  # room_number -> mqtt client
        self.current_room = None
        self.connection_states = {}  # room_number -> connection state
        self.all_props = {}  # room_number -> {prop_id -> prop_info}
        self.prop_update_intervals = {}  # room_number -> last_update_time
        self.UPDATE_INTERVAL = 1000  # Base update interval in ms
        self.INACTIVE_UPDATE_INTERVAL = 2000  # Update interval for non-selected rooms
        self.last_progress_times = {} # last progress events for rooms
        for room_number in self.ROOM_CONFIGS: # Initialize timestamps for all rooms upon starting, or when switching
            self.last_progress_times[room_number] = time.time() # initialize to now
            self.all_props[room_number] = {} # Initialize the dictionary for each room

        
        self.MQTT_PORT = 8080
        self.MQTT_USER = "indestroom"
        self.MQTT_PASS = "indestroom"
        
        # Create left side panel for prop controls using parent's left_panel
        self.frame = app.interface_builder.left_panel
        
        # Title label
        title_label = ttk.Label(self.frame, text="Prop Controls", font=('Arial', 12, 'bold'))
        title_label.pack(fill='x', pady=(0, 10))
        
        # Global controls section
        self.global_controls = ttk.Frame(self.frame)
        self.global_controls.pack(fill='x', pady=(0, 10))
        
        # Create Start Game and Reset All buttons
        self.start_button = tk.Button(
            self.global_controls,
            text="START GAME",
            command=self.start_game,
            bg='#2898ED',   # Blue
            fg='white'
        )
        self.start_button.pack(fill='x', pady=2)

        def reset_reset_button():
            """Reset the button to its original state"""
            self.reset_button.confirmation_pending = False
            self.reset_button.config(text="RESET ALL PROPS")
            self.reset_button.after_id = None
            
        def handle_reset_click():
            """Handle reset button clicks with confirmation"""
            if self.reset_button.confirmation_pending:
                # Second click - perform reset
                self.reset_all()
                reset_reset_button()
            else:
                # First click - show confirmation
                self.reset_button.confirmation_pending = True
                self.reset_button.config(text="Confirm")
                
                # Cancel any existing timer
                if self.reset_button.after_id:
                    self.reset_button.after_cancel(self.reset_button.after_id)
                    
                # Set timer to reset button after 2 seconds
                self.reset_button.after_id = self.reset_button.after(2000, reset_reset_button)

        self.reset_button = tk.Button(
            self.global_controls,
            text="RESET ALL PROPS",
            command=handle_reset_click,  # Use the new handler
            bg='#DB4260',   # Red
            fg='white'
        )
        
        # Track confirmation state
        self.reset_button.confirmation_pending = False
        self.reset_button.after_id = None
        self.reset_button.pack(fill='x', pady=2)
        
        # Special buttons section
        self.special_frame = ttk.LabelFrame(self.frame, text="Room-Specific")
        self.special_frame.pack(fill='x', pady=5)
        
        # Scrollable props section
        self.canvas = tk.Canvas(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.props_frame = ttk.Frame(self.canvas)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Pack scrolling components
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Create window in canvas for props
        self.canvas_frame = self.canvas.create_window((0,0), window=self.props_frame, anchor="nw")
        
        # Configure canvas scrolling
        self.props_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

        # Status message label for connection state
        self.status_label = tk.Label(self.frame, text="", font=('Arial', 10))
        self.status_label.pack(fill='x', pady=5)

        self.load_prop_name_mappings()

        # Initialize MQTT clients for all rooms
        for room_number in self.ROOM_CONFIGS:
            self.initialize_mqtt_client(room_number)

    def update_prop_status(self, prop_id):
        """Update the status display of a prop using icons"""
        if prop_id not in self.props:
            return
            
        prop = self.props[prop_id]
        if 'status_label' not in prop:
            return
            
        try:
            # Verify widget still exists
            if not prop['status_label'].winfo_exists():
                del prop['status_label']
                return
                
            current_time = time.time()
            last_update = prop.get('last_update', current_time)
            time_diff = current_time - last_update
            
            if not hasattr(self, 'status_icons'):
                print("[prop control]Status icons not initialized")
                return
                
            if time_diff > 3:
                # Offline status
                icon = self.status_icons['offline']
            else:
                # Get exact status string and match precisely
                status_text = prop['info']['strStatus']
                
                if status_text == "Not activated" or status_text == "Not Activated":
                    icon = self.status_icons['not_activated']
                elif status_text == "Activated":
                    icon = self.status_icons['activated']
                elif status_text == "Finished":
                    icon = self.status_icons['finished']
                else:
                    print(f"[prop control]Unknown status: '{status_text}', defaulting to not_activated")
                    icon = self.status_icons['not_activated']
            
            # Update the label with the appropriate icon
            prop['status_label'].config(image=icon)
            # Keep a reference to prevent garbage collection
            prop['status_label'].image = icon
            
        except tk.TclError:
            # Widget was destroyed, remove the reference
            del prop['status_label']
        except Exception as e:
            print(f"[prop control]Error updating prop status: {e}")

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
        client_id = f"id_{random.randint(0, 999)}_{room_number}"
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
                client.connect_async(config['ip'], self.MQTT_PORT, keepalive=5)
                client.loop_start()
                self.mqtt_clients[room_number] = client
                
                # Schedule timeout check
                self.app.root.after(5000, lambda: self.check_connection_timeout(room_number))
                
            except Exception as e:
                print(f"[prop control]Failed to connect to room {room_number}: {e}")
                error_msg = f"Connection failed. Retrying in 10 seconds..."
                self.connection_states[room_number] = error_msg
                
                if room_number == self.current_room and hasattr(self, 'status_label'):
                    self.status_label.config(text=error_msg, fg='red')
                
                # Schedule retry using after()
                self.app.root.after(10000, lambda: self.retry_connection(room_number))
        
        # Start connection attempt in separate thread
        threading.Thread(target=connect_async, daemon=True).start()

    def check_connection_timeout(self, room_number):
        """Check if connection attempt has timed out"""
        if room_number in self.mqtt_clients:
            client = self.mqtt_clients[room_number]
            if not client.is_connected():
                print(f"[prop control]Connection to room {room_number} timed out")
                room_name = self.app.rooms.get(room_number, f"Room {room_number}")
                timeout_msg = f"Connection to {room_name} props timed out; is the room powered on? Retrying in 10 seconds..."
                self.connection_states[room_number] = timeout_msg
                
                # Only update UI if this is the current room
                if room_number == self.current_room:
                    self.app.root.after(0, lambda: self.update_connection_state(room_number, timeout_msg))
                
                # Clean up failed connection in a separate thread
                def cleanup():
                    try:
                        client.loop_stop()
                        client.disconnect()
                        if room_number in self.mqtt_clients:
                            del self.mqtt_clients[room_number]
                    except Exception as e:
                        print(f"[prop control]Error cleaning up client for room {room_number}: {e}")
                
                threading.Thread(target=cleanup, daemon=True).start()
                
                # Schedule retry using after()
                self.app.root.after(10000, lambda: self.retry_connection(room_number))

    def restore_prop_ui(self, prop_id, prop_data):
        """Recreate UI elements for a saved prop"""
        if not prop_data or 'info' not in prop_data:
            return False
            
        try:
            self.handle_prop_update(prop_data['info'])
            return True
        except Exception as e:
            print(f"[prop control]Error restoring prop UI: {e}")
            return False

    def retry_connection(self, room_number):
        """Retry connecting to a room's MQTT server without blocking"""
        print(f"[prop control]Retrying connection to room {room_number}")
        
        # Start a new connection attempt in a separate thread
        def do_retry():
            # Clean up any existing client first
            if room_number in self.mqtt_clients:
                try:
                    old_client = self.mqtt_clients[room_number]
                    old_client.loop_stop()
                    old_client.disconnect()
                    del self.mqtt_clients[room_number]
                except Exception as e:
                    print(f"[prop control]Error cleaning up old client for room {room_number}: {e}")
            
            # Initialize new connection
            self.initialize_mqtt_client(room_number)
        
        threading.Thread(target=do_retry, daemon=True).start()

    def connect_to_room(self, room_number):
        """Switch to controlling a different room with proper cleanup and initialize prop states."""
        print(f"[prop control]\nSwitching to room {room_number}")

        if room_number == self.current_room:
            return

        if self.current_room is not None:
            self.all_props[self.current_room] = self.props.copy()
            self.clean_up_room_props(self.current_room)

        old_room = self.current_room
        self.current_room = room_number

        for widget in self.props_frame.winfo_children():
            widget.destroy()

        self.props = {}
        if room_number in self.all_props:
            saved_props = self.all_props[room_number]
            for prop_id, prop_data in saved_props.items():
                if 'last_status' not in prop_data:
                    prop_data['last_status'] = None
                self.handle_prop_update(prop_data['info'])

        else:
            self.all_props[room_number] = {} # Make sure the dict exists
            for prop_id, prop_data in self.all_props[room_number].items():
                    if 'last_status' not in prop_data:
                        prop_data['last_status'] = None

        if room_number not in self.last_progress_times:
            self.last_progress_times[room_number] = time.time()

        self.setup_special_buttons(room_number)

        if old_room:
            self.update_prop_tracking_interval(old_room, is_selected=False)
        self.update_prop_tracking_interval(room_number, is_selected=True)

        if room_number in self.connection_states and hasattr(self, 'status_label'):
            try:
                self.status_label.config(
                    text=self.connection_states[room_number],
                    fg='black' if "Connected" in self.connection_states[room_number] else 'red'
                )
            except tk.TclError:
                print("[prop control]Status label was destroyed, skipping update")
        else:
            self.initialize_mqtt_client(room_number)

    def clean_up_room_props(self, room_number):
        """
        Safely clean up all prop widgets for a room and prepare for room switch.
        This should be called before switching rooms or clearing props.
        """
        if room_number in self.all_props:
            # Remove widget references but keep prop data
            for prop_id in self.all_props[room_number]:
                if 'status_label' in self.all_props[room_number][prop_id]:
                    del self.all_props[room_number][prop_id]['status_label']
                if 'frame' in self.all_props[room_number][prop_id]:
                    del self.all_props[room_number][prop_id]['frame']

    def update_prop_tracking_interval(self, room_number, is_selected=False):
        """Update the tracking interval for a room's props and ensure tracking is active"""
        if room_number not in self.prop_update_intervals:
            self.prop_update_intervals[room_number] = self.UPDATE_INTERVAL if is_selected else self.INACTIVE_UPDATE_INTERVAL
            # Start tracking for this room
            self.update_all_props_status(room_number)
        else:
            # Update existing interval
            self.prop_update_intervals[room_number] = self.UPDATE_INTERVAL if is_selected else self.INACTIVE_UPDATE_INTERVAL

    def check_prop_status(self, room_number, prop_id, prop_info):
        """Check status of a single prop and update UI if needed"""
        if not prop_info or 'info' not in prop_info:
            return
            
        try:
            # Get current status
            status = prop_info['info'].get('strStatus')
            previous_status = prop_info.get('last_status')
            
            # Update last progress time if status changed meaningfully
            if previous_status != status and status != "offline":
                self.last_progress_times[room_number] = time.time()
                
            # Store current status as previous for next check
            prop_info['last_status'] = status
            
            # Check if this is a finishing prop
            is_finishing = self.is_finishing_prop(room_number, prop_info['info'].get('strName', ''))
            
            if is_finishing:
                # Get activation status for all props in this room
                is_activated = False
                if room_number in self.all_props:
                    for pid, pdata in self.all_props[room_number].items():
                        if 'info' in pdata and pdata['info'].get('strStatus') == "Activated":
                            is_activated = True
                            break

                # Get timer status for the kiosk
                timer_expired = False
                for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
                    if room_num == room_number:
                        if computer_name in self.app.kiosk_tracker.kiosk_stats:
                            timer_time = self.app.kiosk_tracker.kiosk_stats[computer_name].get('timer_time', 2700)
                            timer_expired = timer_time <= 0
                        break
                
                # Update kiosk highlighting with all states
                self.update_kiosk_highlight(room_number, status == "Finished", is_activated, timer_expired)
                
            # Only update status label if this is current room and widget exists
            if room_number == self.current_room and 'status_label' in prop_info:
                try:
                    # Verify widget still exists and is valid
                    prop_info['status_label'].winfo_exists()
                    self.update_prop_status(prop_id)
                except tk.TclError:
                    # Widget is invalid, remove the reference
                    del prop_info['status_label']
                except Exception as e:
                    print(f"[prop control]Error updating prop UI: {e}")
                        
        except Exception as e:
            print(f"[prop control]Error in check_prop_status: {e}")

    def update_all_props_status(self, room_number):
        """Update status for all props in a room, and UI if needed."""
        if room_number not in self.all_props:
            return
            
        current_time = time.time()
            
        is_activated = False
        is_finished = False
        timer_expired = False
            
        for prop_id, prop_info in self.all_props[room_number].items():
            if 'info' not in prop_info:
                continue
                    
            status = prop_info['info'].get('strStatus')
            if status == "Activated":
                is_activated = True
                
            if self.is_finishing_prop(room_number, prop_info['info'].get('strName', '')):
                if status == "Finished":
                    is_finished = True
            
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    timer_time = self.app.kiosk_tracker.kiosk_stats[computer_name].get('timer_time', 2700)
                    timer_expired = timer_time <= 0
                break
        
        self.update_kiosk_highlight(room_number, is_finished, is_activated, timer_expired)

        if room_number == self.current_room:
            for prop_id, prop_info in self.all_props[room_number].items():
                self.check_prop_status(room_number, prop_id, prop_info)
                
        if room_number in self.prop_update_intervals:
            interval = self.prop_update_intervals[room_number]
            self.app.root.after(interval, lambda: self.update_all_props_status(room_number))

    def update_timer_status(self, room_number):
        """Update room status when timer changes"""
        if room_number not in self.all_props:
            return
                
        is_activated = False
        is_finished = False
        timer_expired = False
            
        # Check prop states
        for prop_id, prop_info in self.all_props[room_number].items():
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
        if rc == 0:
            # Clear any status messages on successful connection
            if room_number == self.current_room and hasattr(self, 'status_label'):
                self.status_label.config(text="")
                
            # Subscribe to topics
            topics = [
                "/er/ping", "/er/name", "/er/cmd", "/er/riddles/info",
                "/er/music/info", "/er/music/soundlist", "/game/period",
                "/unixts", "/stat/games/count"
            ]
            for topic in topics:
                client.subscribe(topic)
        else:
            # Show error messages
            status = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }.get(rc, f"Unknown error (code {rc})")
            
            error_msg = f"Connection failed: {status}. Retrying in 10 seconds..."
            if room_number == self.current_room and hasattr(self, 'status_label'):
                self.status_label.config(text=error_msg, fg='red')
            
            # Schedule retry
            self.app.root.after(10000, lambda: self.retry_connection(room_number))

    def update_connection_state(self, room_number, state):
        """Update the connection state display - only shows error states"""
        self.connection_states[room_number] = state
        
        if room_number == self.current_room and hasattr(self, 'status_label'):
            if any(error in state.lower() for error in ["failed", "timed out", "connecting", "lost"]):
                # Show error states in red
                self.status_label.config(
                    text=state,
                    fg='red'
                )
                # Clear props display on connection issues
                for widget in self.props_frame.winfo_children():
                    if widget != self.status_frame:  # Keep the status frame
                        widget.destroy()
                self.props = {}
            else:
                # Always hide the status label for non-error states
                self.status_label.config(text="")

    def setup_special_buttons(self, room_number):
        # Clear existing buttons
        for widget in self.special_frame.winfo_children():
            widget.destroy()
            
        if room_number not in self.ROOM_CONFIGS:
            return
            
        # Create container for button grid
        buttons_grid = ttk.Frame(self.special_frame)
        buttons_grid.pack(fill='x', padx=1, pady=1)  # Reduced padding
        
        # Configure grid columns to be equal width
        buttons_grid.columnconfigure(0, weight=1)
        buttons_grid.columnconfigure(1, weight=1)
        
        button_style = {
            'background': '#ffcccc',    # Pale red background
            'font': ('Arial', 7),       # Even smaller font
            'wraplength': 60,           # Narrower text wrapping
            'height': 1,                # Reduced height
            'width': 8,                 # Reduced width
            'relief': 'raised',         # Add subtle 3D effect
            'padx': 1,                  # Minimal internal padding
            'pady': 1                   # Minimal internal padding
        }
        
        # Place buttons in a 2-column grid
        buttons = self.ROOM_CONFIGS[room_number]['special_buttons']
        for i, (button_text, command_name) in enumerate(buttons):
            row = i // 2    # Integer division for row number
            col = i % 2     # Remainder for column number
            
            if command_name.startswith('quest/'):
                quest_type = command_name.split('/')[1]
                btn = tk.Button(
                    buttons_grid, 
                    text=button_text,
                    command=lambda qt=quest_type: self.send_quest_command(qt),
                    **button_style
                )
            else:
                btn = tk.Button(
                    buttons_grid, 
                    text=button_text,
                    command=lambda pn=command_name: self.send_special_command(pn, "on"),
                    **button_style
                )
                
            # Pack button into grid with minimal padding
            btn.grid(row=row, column=col, padx=1, pady=1, sticky='nsew')

    def on_message(self, client, userdata, msg, room_number):
        """Modified to handle messages for all rooms, including tracking prop status changes."""
        try:
            if msg.topic == "/er/riddles/info":
                payload = json.loads(msg.payload.decode())
                
                if room_number not in self.all_props:
                    self.all_props[room_number] = {}
                    
                prop_id = payload.get("strId")
                if prop_id:
                    if prop_id not in self.all_props[room_number]:
                        self.all_props[room_number][prop_id] = {
                            'info': payload.copy(),
                            'last_update': time.time(),
                            'last_status': None
                        }
                    else:
                        self.all_props[room_number][prop_id]['info'] = payload.copy()

                    if room_number == self.current_room:
                        self.app.root.after(0, lambda: self.handle_prop_update(payload))
                        
                    self.app.root.after(0, lambda: self.check_prop_status(
                        room_number, prop_id, self.all_props[room_number][prop_id]
                    ))
                        
        except json.JSONDecodeError:
            print(f"[prop control]Failed to decode message from room {room_number}: {msg.payload}")
        except Exception as e:
            print(f"[prop control]Error handling message from room {room_number}: {e}")

    def on_disconnect(self, client, userdata, rc, room_number):
        """Handle disconnection for a specific room's client"""
        print(f"[prop control]Room {room_number} disconnected with code: {rc}")
        room_name = self.app.rooms.get(room_number, f"Room {room_number}")
        if rc != 0:  # Unexpected disconnect
            self.update_connection_state(room_number, 
                f"Connection to {room_name} props lost. Retrying in 10 seconds...")
            # Schedule retry
            self.app.root.after(10000, lambda: self.retry_connection(room_number))

    def handle_prop_update(self, prop_data):
        """Handle updates to prop status and create/update the UI elements."""
        prop_id = prop_data.get("strId")
        if not prop_id:
            return
            
        if not hasattr(self, 'status_icons'):
            try:
                icon_dir = os.path.join("admin_icons")
                self.status_icons = {
                    'not_activated': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "not_activated.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    ),
                    'activated': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "activated.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    ),
                    'finished': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "finished.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    ),
                    'offline': ImageTk.PhotoImage(
                        Image.open(os.path.join(icon_dir, "offline.png")).resize((16, 16), Image.Resampling.LANCZOS)
                    )
                }
            except Exception as e:
                print(f"[prop control]Error loading status icons: {e}")
                self.status_icons = None

        order = 999  
        if self.current_room in self.ROOM_MAP:
            room_key = self.ROOM_MAP[self.current_room]
            if room_key in self.prop_name_mappings:
                prop_info = self.prop_name_mappings[room_key]['mappings'].get(prop_data["strName"], {})
                order = prop_info.get('order', 999)
        
        current_status = prop_data.get("strStatus", "")
        
        if prop_id not in self.props:
            prop_frame = ttk.Frame(self.props_frame)
            button_frame = ttk.Frame(prop_frame)
            button_frame.pack(side='left', padx=(0, 5))
            
            button_size = 20
            reset_btn = tk.Button(
                button_frame,
                text="R",
                font=('Arial', 5, 'bold'),
                command=lambda: self.send_command(prop_id, "reset"),
                bg='#cc362b',
                width=2,
                height=4
            )
            reset_btn.pack(side='left', padx=1)
                
            activate_btn = tk.Button(
                button_frame,
                text="A",
                font=('Arial', 5, 'bold'),
                command=lambda: self.send_command(prop_id, "activate"),
                bg='#ff8c00',
                width=2,
                height=4
            )
            activate_btn.pack(side='left', padx=1)
                
            finish_btn = tk.Button(
                button_frame,
                text="F",
                font=('Arial', 5, 'bold'),
                command=lambda: self.send_command(prop_id, "finish"),
                bg='#28a745',
                width=2,
                height=4
            )
            finish_btn.pack(side='left', padx=1)
            
            mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)
            name_label = ttk.Label(prop_frame, font=('Arial', 8, 'bold'), text=mapped_name)
            name_label.pack(side='left', padx=5)
            
            name_label.bind('<Button-1>', lambda e, name=prop_data["strName"]: self.notify_prop_select(name))
            name_label.config(cursor="hand2")
            
            status_label = tk.Label(prop_frame)
            status_label.pack(side='right', padx=5)
            
            self.props[prop_id] = {
                'frame': prop_frame,
                'status_label': status_label,
                'info': prop_data,
                'last_update': time.time(),
                'order': order
            }
            
            # Set initial last status from newly loaded data
            if self.current_room not in self.all_props:
                self.all_props[self.current_room] = {}

            if prop_id not in self.all_props[self.current_room]:
                self.all_props[self.current_room][prop_id] = {}
            self.all_props[self.current_room][prop_id]['last_status'] = current_status
            
            sorted_props = sorted(self.props.items(), key=lambda x: x[1]['order'])
            for _, prop_info in sorted_props:
                prop_info['frame'].pack_forget()
                prop_info['frame'].pack(fill='x', pady=1)
            
        else:
            # Update existing prop info
            previous_status = self.all_props[self.current_room][prop_id].get('last_status')
            
            # Update values, including order
            self.props[prop_id]['info'] = prop_data
            self.props[prop_id]['last_update'] = time.time()
            self.props[prop_id]['order'] = order
            
            # Update the last status with the current status
            if self.current_room not in self.all_props:
                self.all_props[self.current_room] = {}
            if prop_id not in self.all_props[self.current_room]:
                self.all_props[self.current_room][prop_id] = {}
            self.all_props[self.current_room][prop_id]['last_status'] = current_status
        
        self.update_prop_status(prop_id)
        self.check_finishing_prop_status(prop_id, prop_data)

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
        """
        Check prop status and update kiosk display accordingly.
        Checks finishing props, activated states, and timer status.
        """
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()
            
        # Get prop name from data
        prop_name = prop_data.get("strName")
        if not prop_name:
            return
            
        if self.current_room not in self.ROOM_MAP:
            return
            
        room_key = self.ROOM_MAP[self.current_room]
        
        # Find the kiosk assigned to this room
        assigned_kiosk = None
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == self.current_room:
                assigned_kiosk = computer_name
                break
        
        if assigned_kiosk and assigned_kiosk in self.app.interface_builder.connected_kiosks:
            # Check if any props are activated or if finishing prop is finished
            is_activated = False
            is_finished = False
            
            # Check all props in current room for activated state
            for pid, pdata in self.props.items():
                if pdata['info']['strStatus'] == "Activated":
                    is_activated = True
                
                # Check if this is a finishing prop and it's finished
                prop_info = self.prop_name_mappings.get(room_key, {}).get('mappings', {}).get(pdata['info']['strName'], {})
                if prop_info.get('finishing_prop', False) and pdata['info']['strStatus'] == "Finished":
                    is_finished = True
            
            # Get timer status for the kiosk
            timer_expired = False
            if assigned_kiosk in self.app.kiosk_tracker.kiosk_stats:
                timer_time = self.app.kiosk_tracker.kiosk_stats[assigned_kiosk].get('timer_time', 2700)
                timer_expired = timer_time <= 0
            
            # Update the highlight state with timer status
            self.update_kiosk_highlight(self.current_room, is_finished, is_activated, timer_expired)

    def update_kiosk_highlight(self, room_number, is_finished, is_activated, timer_expired=False):
        """
        Update kiosk frame highlighting based on prop status and timer
        
        Args:
            room_number: The room number to update
            is_finished: Boolean indicating if finishing prop is finished
            is_activated: Boolean indicating if any props are activated
            timer_expired: Boolean indicating if timer has expired
        """
        # Find kiosk assigned to this room
        assigned_kiosk = None
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                assigned_kiosk = computer_name
                break
                
        if not assigned_kiosk or assigned_kiosk not in self.app.interface_builder.connected_kiosks:
            return
            
        try:
            kiosk_frame = self.app.interface_builder.connected_kiosks[assigned_kiosk]['frame']
            
            # Initialize audio manager if needed
            audio_manager = AdminAudioManager()
            
            # Handle timer expiration sound
            audio_manager.handle_timer_expired(timer_expired, room_number)
            
            # Handle game finish sound
            audio_manager.handle_game_finish(is_finished, room_number)
            
            # Update visual highlighting
            if timer_expired:
                new_color = '#FFB6C1'  # Light red for expired timer
            elif is_finished:
                new_color = '#90EE90'  # Light green for finished
            elif is_activated:
                new_color = '#faf8ca'  # Pale yellow for activated
            else:
                new_color = 'SystemButtonFace'  # Default system color
                
            # Update frame and child widgets
            kiosk_frame.configure(bg=new_color)
            for widget in kiosk_frame.winfo_children():
                if not isinstance(widget, (tk.Button, ttk.Combobox)):
                    widget.configure(bg=new_color)
                        
        except tk.TclError:
            print(f"[prop control]Widget for kiosk {assigned_kiosk} was destroyed")
        except Exception as e:
            print(f"[prop control]Error updating kiosk highlight: {e}")

    def schedule_status_update(self, prop_id):
        """Schedule periodic updates of prop status"""
        if prop_id in self.props:
            self.update_prop_status(prop_id)
            # Schedule next update in 1 second
            self.app.root.after(1000, lambda: self.schedule_status_update(prop_id))

    def send_command(self, prop_id, command):
        """Send command to standard props"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("[prop control]No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = f"/er/{prop_id}/cmd"
        try:
            client.publish(topic, command)
            print(f"[prop control]Command sent successfully to room {self.current_room}")
        except Exception as e:
            print(f"[prop control]Failed to send command: {e}")

    def send_special_command(self, prop_name, command):
        """Send command to special pneumatic props"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print(f"[prop control]\nNo active room selected")
            return
            
        # Map the friendly names to their actual MQTT topics
        prop_map = {
            'barrel': 'pnevmo2',
            'kitchen': 'pnevmo1',
            'cage': 'pnevmo3',
            'door': 'pnevmo4'
        }
        
        # Get the actual topic name for this prop
        if prop_name not in prop_map:
            print(f"[prop control]\nUnknown prop: {prop_name}")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = f"/er/{prop_map[prop_name]}"
        
        try:
            print(f"[prop control]\nSending pneumatic prop command:")
            print(f"[prop control]Room: {self.current_room}")
            print(f"[prop control]Prop: {prop_name}")
            print(f"[prop control]Topic: {topic}")
            
            # Send the exact command the props expect
            client.publish(topic, "trigger", qos=0, retain=False)
            print(f"[prop control]Command sent successfully to {prop_name}")
            
        except Exception as e:
            print(f"[prop control]\nFailed to send command: {e}")

    def on_frame_configure(self, event=None):
        """Reconfigure the canvas scrolling region"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Ensure props_frame spans the full width
        width = self.canvas.winfo_width()
        self.canvas.itemconfig(self.canvas_frame, width=width)

    def notify_prop_select(self, prop_name):
        """Notify all registered callbacks about prop selection"""
        if hasattr(self, 'prop_select_callbacks'):
            for callback in self.prop_select_callbacks:
                callback(prop_name)

    def add_prop_select_callback(self, callback):
        """Add a callback to be called when a prop is selected"""
        if not hasattr(self, 'prop_select_callbacks'):
            self.prop_select_callbacks = []
        self.prop_select_callbacks.append(callback)

    def on_canvas_configure(self, event):
        """Handle canvas resize"""
        width = event.width
        self.canvas.itemconfig(self.canvas_frame, width=width)
        
        # Recalculate column widths
        col_width = (width - 40) // 3  # Subtract padding and divide by 3 columns
        for i in range(3):
            self.props_frame.grid_columnconfigure(i, minsize=col_width)
        
    def shutdown(self):
        for client in self.mqtt_clients.values():
            client.loop_stop()
            client.disconnect()

    def start_game(self):
        """Send start game command to current room"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("[prop control]No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        try:
            client.publish("/er/cmd", "start")
            print(f"[prop control]Start game command sent to room {self.current_room}")
            # Log the action
            if hasattr(self.app, 'kiosk_tracker'):
                self.app.kiosk_tracker.log_action(f"Started game in room {self.current_room}")
        except Exception as e:
            print(f"[prop control]Failed to send start game command: {e}")

    def reset_all(self):
        """Send reset all command to current room"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("[prop control]No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        try:
            client.publish("/er/cmd", "reset")
            print(f"[prop control]Reset all command sent to room {self.current_room}")
            # Log the action
            if hasattr(self.app, 'kiosk_tracker'):
                self.app.kiosk_tracker.log_action(f"Reset all props in room {self.current_room}")
        except Exception as e:
            print(f"[prop control]Failed to send reset all command: {e}")

    

    def send_quest_command(self, quest_type):
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("[prop control]No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = "/er/quest"
        try:
            client.publish(topic, quest_type)
            print(f"[prop control]Quest command '{quest_type}' sent successfully to room {self.current_room}")
            if hasattr(self.app, 'kiosk_tracker'):
                self.app.kiosk_tracker.log_action(f"Sent quest command '{quest_type}' to room {self.current_room}")
        except Exception as e:
            print(f"[prop control]Failed to send quest command: {e}")
