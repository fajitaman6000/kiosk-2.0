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
        self.last_mqtt_updates = {} # room_number -> {prop_id -> last_mqtt_update_time}
        self.retry_timer_ids = {}  # Tracks pending retry timers for each room
        self.disconnect_rc7_history = {}  # room_number -> list of timestamps for rc=7 disconnects
        self.last_prop_finished = {} # prop status strings
        self.flagged_props = {}  # room_number -> {prop_id: True/False}
        self.victory_sent = {}  # room_number -> bool
        self.finish_sound_played = {}  # room_number -> bool ADDED FINISH TRACKING
        self.standby_played = {} #standby tracking
        self.stale_sound_played = {}  # <-- **ENSURE THIS LINE EXISTS HERE**

        self.MQTT_PORT = 8080
        self.MQTT_USER = "indestroom"
        self.MQTT_PASS = "indestroom"

        # Create left side panel for prop controls using parent's left_panel
        self.frame = app.interface_builder.left_panel

        # Create custom styles for circuit highlighting
        style = ttk.Style()
        style.configure('Circuit.TFrame', background='#ffe6e6', borderwidth=2, relief='solid')
        style.configure('Circuit.TLabel', background='#ffe6e6', font=('Arial', 8, 'bold'))
        # Add cousin highlighting style
        style.configure('Cousin.TFrame', background='#e6ffe6', borderwidth=2, relief='solid')
        style.configure('Cousin.TLabel', background='#e6ffe6', font=('Arial', 8, 'bold'))

        # Title label
        title_label = ttk.Label(self.frame, text="Prop Controls", font=('Arial', 12, 'bold'))
        #title_label.pack(fill='x', pady=(0, 10))

        # Global controls section
        self.global_controls = ttk.Frame(self.frame)
        self.global_controls.pack(fill='x', pady=(0, 10))

        # Create Start Game and Reset All buttons
        self.start_button = tk.Button(
            self.global_controls,
            text="START PROPS",
            command=self.start_game,
            bg='#2898ED',   # Blue
            fg='white',
            cursor="hand2"
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
            fg='white',
            cursor="hand2"
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
        #self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.props_frame = ttk.Frame(self.canvas)

        #self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Pack scrolling components
        #self.scrollbar.pack(side="right", fill="y")
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
        self.load_flagged_prop_image()

        # Initialize MQTT clients for all rooms
        for room_number in self.ROOM_CONFIGS:
            self.last_progress_times[room_number] = time.time()  # initialize to now
            self.all_props[room_number] = {}  # Initialize the dictionary for each room
            self.last_mqtt_updates[room_number] = {}  # Initialize MQTT update tracking
            self.flagged_props[room_number] = {}  # initialize the flag props dict
            self.stale_sound_played[room_number] = False  # <-- INITIALIZE FLAG (This line is fine)
            self.victory_sent.setdefault(room_number, False)  # Use setdefault for cleaner init
            self.finish_sound_played.setdefault(room_number, False)
            self.standby_played.setdefault(room_number, False)
            self.initialize_mqtt_client(room_number)  # Moved MQTT init to end of loop body

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
                del prop['status_label']
                return

            current_time = time.time()

            # Check for MQTT timeout
            is_offline = (self.current_room not in self.last_mqtt_updates or
                        prop_id not in self.last_mqtt_updates[self.current_room] or
                        current_time - self.last_mqtt_updates[self.current_room][prop_id] > 3)


            # Debug print status icon loading (This part is correct)
            if not hasattr(self, 'status_icons'):
                print("[prop control]Status icons not initialized!")
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
                    return
            elif 'offline' not in self.status_icons:
                print("[prop control]Offline icon missing from status_icons!")
                return


            if is_offline:
                icon = self.status_icons['offline']
            else:
                status_text = prop['info']['strStatus']
                if status_text == "Not activated" or status_text == "Not Activated":
                    icon = self.status_icons['not_activated']
                elif status_text == "Activated":
                    icon = self.status_icons['activated']
                elif status_text == "Finished":
                    icon = self.status_icons['finished']
                else:
                    icon = self.status_icons['not_activated']

            # Check if prop is flagged and overlay the flag image if it is
            if (self.current_room in self.flagged_props and
                prop_id in self.flagged_props[self.current_room] and
                self.flagged_props[self.current_room][prop_id]):

                if self.flagged_prop_image:
                    # Create a new PhotoImage for the composite image
                    composite_image = Image.new('RGBA', (16, 16), (0, 0, 0, 0))  # Transparent background
                    background_image = ImageTk.getimage(icon).convert("RGBA")
                    flag_image = ImageTk.getimage(self.flagged_prop_image).convert("RGBA")

                    # *** KEY CHANGE: Paste flag_image FIRST ***
                    composite_image.paste(flag_image, (0, 0), flag_image)
                    composite_image.paste(background_image, (0, 0), background_image)


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
            del prop['status_label']
        except Exception as e:
            print(f"[prop control]Error updating prop status: {e}")

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
                client.connect_async(config['ip'], self.MQTT_PORT, keepalive=10)
                client.loop_start()
                self.mqtt_clients[room_number] = client
                
                # Schedule timeout check
                self._schedule_retry(room_number, 5000, lambda: self._check_connection_timeout_callback(room_number))
                
            except Exception as e:
                print(f"[prop control]Failed to connect to room {room_number}: {e}")
                error_msg = f"Connection failed. Retrying in 10 seconds..."
                self.connection_states[room_number] = error_msg
                
                if room_number == self.current_room and hasattr(self, 'status_label'):
                    self.app.root.after(0, lambda: self.status_label.config(text=error_msg, fg='red'))
                
                # Schedule retry using after()
                self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))
        
        # Start connection attempt in separate thread
        self.app.root.after(0, lambda: threading.Thread(target=connect_async, daemon=True).start()) # wrap the thread creation in after

    def check_connection_timeout(self, room_number):
        """Check if connection attempt has timed out"""
        if room_number in self.mqtt_clients:
            client = self.mqtt_clients[room_number]
            if not client.is_connected():
                #print(f"[prop control]Connection to room {room_number} timed out")
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
                        print(f"[prop control]Error cleaning up client for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}': {e}")
                
                threading.Thread(target=cleanup, daemon=True).start()
                
                # Schedule retry using after()
                self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))

    def _check_connection_timeout_callback(self, room_number): # new helper method
         self.check_connection_timeout(room_number)

    def restore_prop_ui(self, prop_id, prop_data):
        """Recreate UI elements for a saved prop"""
        print("[prop control]Restoring prop UI")
        if not prop_data or 'info' not in prop_data:
            return False
            
        try:
            self.handle_prop_update(prop_data['info'], self.current_room)
            return True
        except Exception as e:
            print(f"[prop control]Error restoring prop UI: {e}")
            return False

    def retry_connection(self, room_number):
        """Retry connecting to a room's MQTT server without blocking"""
        #print(f"[prop control]Retrying connection to room {room_number}")
        
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
            self.app.root.after(0, lambda: self.initialize_mqtt_client(room_number)) # wrap the initial connection call
        
        self.app.root.after(0, lambda: threading.Thread(target=do_retry, daemon=True).start()) # wrap the retry in after

    def connect_to_room(self, room_number):
        """Switch to controlling a different room with proper cleanup and initialize prop states."""
        if room_number == self.current_room:
            return

        # Clear UI
        for widget in self.props_frame.winfo_children():
            widget.destroy()

        # Reset props dict
        self.props = {}

        # Restore props for new room
        if room_number in self.all_props:
            for prop_id, prop_data in self.all_props[room_number].items():
                if 'last_status' not in prop_data:
                    prop_data['last_status'] = None
                # *** MODIFY THIS CALL ***
                self.handle_prop_update(prop_data['info'], room_number)  # Pass the new room number
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

        self.victory_sent[room_number] = False
        #print(f"[prop control] set victory sent false for room {room_number}")

        # --- STANDBY STATE INITIALIZATION ---
        if room_number not in self.standby_played:
            self.standby_played[room_number] = False
        # --- END STANDBY STATE INITIALIZATION ---
        if room_number not in self.finish_sound_played:
            self.finish_sound_played[room_number] = False

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

    def sort_and_repack_props(self):
        """Sorts props based on their 'order' for the *current* room and repacks them."""
        #print("[prop control]Sorting and repacking props")
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
                prop_data['frame'].pack_forget()  # Remove from current position
                prop_data['frame'].pack(fill='x', pady=1)  # Add back in sorted order

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
        if prop_id not in self.props:
            return
        
        mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)
        
        # Update the name label
        name_label = self.props[prop_id]['name_label']
        name_label.config(text = mapped_name)
        
        # Update name label formatting
        if self.is_finishing_prop(self.current_room, prop_data['strName']):
            name_label.config(font=('Arial', 8, 'bold', 'italic', 'underline'))
        else:
            name_label.config(font=('Arial', 8, 'bold'))

        # Ensure hover events for cousin highlighting are set
        name_label.bind('<Enter>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, True))
        name_label.bind('<Leave>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, False))

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
        """Update the tracking interval for a room's props. The periodic update loop is started on connect."""
        # Update the interval setting. The periodic update loop is started by on_connect.
        self.prop_update_intervals[room_number] = self.UPDATE_INTERVAL if is_selected else self.INACTIVE_UPDATE_INTERVAL
        # The update_all_props_status method will use this interval for the next scheduled call.

    def check_prop_status(self, room_number, prop_id, prop_info):
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
                self.flagged_props[self.current_room][prop_id] and
                status == "Finished"):

                audio_manager = AdminAudioManager()
                audio_manager.play_flagged_finish_notification()
                print(f"[prop control] flagged prop {prop_id} finished")

                self.flagged_props[room_number][prop_id] = False
            
            # --- STANDBY PROP HANDLING ---
            #if (self.is_standby_prop(room_number, prop_info['info'].get('strName', '')) and
                    #status == "Finished"):
                #self.play_standby_sound(room_number)
            # --- END STANDBY PROP HANDLING ---


            if room_number == self.current_room and 'status_label' in prop_info:
                try:
                    prop_info['status_label'].winfo_exists()
                    self.update_prop_status(prop_id)
                except tk.TclError:
                    del prop_info['status_label']
                except Exception as e:
                    print(f"[prop control]Error updating prop UI: {e}")

        except Exception as e:
            prop_name = prop_info['info'].get('strName', 'unknown') if 'info' in prop_info else 'unknown'
            error_type = type(e).__name__
            trace_str = traceback.format_exc()
            print(f"[prop control]Error in check_prop_status: Room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}', Prop '{prop_name}' (ID: {prop_id})")
            print(f"[prop control]Exception type: {error_type}, Error: {str(e)}")
            print(f"[prop control]Traceback: {trace_str}")

    def play_standby_sound(self, room_number):
        """Plays the room-specific standby sound."""
        print("[prop_control].play_standby_sound")
        if room_number not in self.ROOM_MAP:
            return

        room_name = self.ROOM_MAP[room_number]
        sound_file = f"{room_name}_standby.mp3"
        audio_manager = AdminAudioManager()  # Get the singleton instance
        audio_manager._load_sound(f"{room_name}_standby", sound_file)  # Ensure sound is loaded
        audio_manager.play_sound(f"{room_name}_standby")

    def play_stale_sound(self, room_number):
        """Plays the room-specific stale sound."""
        print("[prop_control].play_stale_sound")
        if room_number not in self.ROOM_MAP:
            return

        room_name = self.ROOM_MAP[room_number]
        sound_file = f"{room_name}_stale.mp3"
        audio_manager = AdminAudioManager()  # Get the singleton instance
        audio_manager._load_sound(f"{room_name}_stale", sound_file)  # Ensure sound is loaded
        audio_manager.play_sound(f"{room_name}_stale")

    def play_finish_sound(self, room_number):
        """Plays the room-specific finish sound."""
        audio_manager = AdminAudioManager()
        audio_manager.play_sound("game_finish")

    def update_all_props_status(self, room_number):
        if room_number not in self.all_props:
            return

        current_time = time.time()

        is_activated = False
        is_finished = False  # Initialize is_finished to False
        timer_expired = False
        finishing_prop_offline = False # New flag
        is_standby = False
        standby_prop_offline = False # flag for if a standby prop goes offline

        # --- STANDBY STATE TRACKING ---
        if room_number not in self.standby_played:
            self.standby_played[room_number] = False
        # --- END STANDBY STATE TRACKING ---
        if room_number not in self.finish_sound_played:
            self.finish_sound_played[room_number] = False

        for prop_id, prop_info in self.all_props[room_number].items():
            if 'info' not in prop_info:
                continue

            is_offline = (room_number not in self.last_mqtt_updates or
                        prop_id not in self.last_mqtt_updates[room_number] or
                        current_time - self.last_mqtt_updates[room_number][prop_id] > 3)

            if is_offline:
                prop_info['info']['strStatus'] = "offline"
                if self.is_finishing_prop(room_number, prop_info['info'].get('strName', '')):
                    finishing_prop_offline = True # Set the flag
                if self.is_standby_prop(room_number, prop_info['info'].get('strName', '')):
                    standby_prop_offline = True


            status = prop_info['info'].get('strStatus')
            if status == "Activated":
                is_activated = True

            if (not finishing_prop_offline and  # Only check if no finishing prop is offline
                self.is_finishing_prop(room_number, prop_info['info'].get('strName', '')) and
                status == "Finished"):
                is_finished = True
            
            # --- STANDBY PROP CHECK ---
            if (not standby_prop_offline and self.is_standby_prop(room_number, prop_info['info'].get('strName', '')) and
                    status == "Finished"):
                is_standby = True

            # Handle prop entering non-finished status after finish
            if (self.is_finishing_prop(room_number, prop_info['info'].get('strName', ''))
                and not finishing_prop_offline
                and status != "Finished"):
                if (room_number in self.victory_sent and self.victory_sent[room_number] == True) or (room_number in self.finish_sound_played and self.finish_sound_played[room_number] == True):
                    print("[prop_control] previously finished finishing prop entered state other than offline, resetting game finish status")
                    self.reset_game_finish_state(room_number)

        # Handle finishing prop offline
        if finishing_prop_offline:
            is_finished = False  # Ensure is_finished is False
            if (room_number in self.victory_sent and self.victory_sent[room_number] == True) or (room_number in self.finish_sound_played and self.finish_sound_played[room_number] == True):
                    self.reset_game_finish_state(room_number)

        
        if standby_prop_offline:
            is_standby = False
            self.reset_standby_state(room_number) #now just resets the prop control flag


        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                if computer_name in self.app.kiosk_tracker.kiosk_stats:
                    timer_time = self.app.kiosk_tracker.kiosk_stats[computer_name].get('timer_time', 2700)
                    timer_expired = timer_time <= 0
                break

        # Update kiosk highlight *before* further UI updates
        self.update_kiosk_highlight(room_number, is_finished, is_activated, timer_expired)

        for computer_name, assigned_room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if assigned_room_num == room_number:
                # Check if timer is ALREADY running for this kiosk
                if computer_name not in self.app.interface_builder.auto_reset_timer_ids:
                    if is_finished:
                        room_name = self.app.rooms.get(room_number, f"Room {room_number}")
                        print(f"[prop control.update_all_props_status]{room_name} just won")
                        self._send_victory_message(room_number, computer_name)
                        self.app.interface_builder.start_auto_reset_timer(computer_name)
                    elif timer_expired:
                        room_name = self.app.rooms.get(room_number, f"Room {room_number}")
                        print(f"[prop control.update_all_props_status]{room_name} timer expired")
                        self.app.interface_builder.start_auto_reset_timer(computer_name)
                break  # Important: Only process for the assigned kiosk
        
        # --- MODIFIED STANDBY HANDLING ---
        if is_standby and not self.standby_played[room_number]:
            self.standby(room_number)
            self.standby_played[room_number] = True  # Mark as played
        # --- END MODIFIED STANDBY HANDLING ---

        if is_finished and not self.finish_sound_played[room_number]:
             self.play_finish_sound(room_number)
             self.finish_sound_played[room_number] = True
        elif not is_finished: # crucial to reset flag when appropriate
             self.finish_sound_played[room_number] = False

        if room_number == self.current_room:
            for prop_id, prop_info in self.all_props[room_number].items():
                if prop_id in self.props:
                    status_label = self.props[prop_id].get('status_label')
                    if status_label and status_label.winfo_exists():
                        self.update_prop_status(prop_id)

        if room_number in self.prop_update_intervals:
            interval = self.prop_update_intervals[room_number]
            self.app.root.after(interval, lambda: self.update_all_props_status(room_number))

        # --- ADDED: Check for Stale Game ---
        if room_number in self.last_progress_times:
            time_since_last_progress = time.time() - self.last_progress_times[room_number]

            if (is_activated and not is_finished and not timer_expired and
                time_since_last_progress >= self.STALE_THRESHOLD and
                not self.stale_sound_played.get(room_number, False)):

                room_key = self.ROOM_MAP.get(room_number)
                if room_key:
                    print(f"[prop_control] Room {room_number} ({room_key}) has been stale for {int(time_since_last_progress)}s. Playing sound.")
                    self.play_stale_sound(room_number)
                    self.stale_sound_played[room_number] = True  # Mark as played for this period
        # --- END ADDED: Check for Stale Game ---

    def standby(self, room_number):
        """Plays the room-specific standby sound."""
        print(f"[prop control] standby for room {room_number}")
        self.play_standby_sound(room_number)

    def reset_standby_state(self, room_number):
        """Reset the standby state for a room"""
        #audio_manager = AdminAudioManager() #removed audio manager logic
        #if room_number in audio_manager.sound_states:
             #audio_manager.sound_states[room_number]['standby'] = False
        if room_number in self.standby_played:
            self.standby_played[room_number] = False

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
            print(f"[prop control]Room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' connected.")
            # Don't clear history immediately on successful connection
            # We'll keep the history for a bit in case we quickly disconnect again

            # Clear any status messages on successful connection
            if room_number == self.current_room and hasattr(self, 'status_label'):
                try:
                    self.status_label.config(text="")
                except tk.TclError:
                    print(f"[prop control]Error clearing status label for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' on connect (widget destroyed?).")

            # Cancel the timeout check timer on successful connection
            if room_number in self.retry_timer_ids and self.retry_timer_ids[room_number] is not None:
                self.app.root.after_cancel(self.retry_timer_ids[room_number])
                self.retry_timer_ids[room_number] = None

            # --- ADD THESE LINES ---
            # Ensure interval is set for periodic updates before scheduling the first one.
            # Set default interval (inactive) if not already set by selecting the room.
            if room_number not in self.prop_update_intervals:
                self.prop_update_intervals[room_number] = self.INACTIVE_UPDATE_INTERVAL

            # Schedule the first periodic status update call on the main thread.
            # This ensures the check loop runs for all connected rooms.
            # update_all_props_status will reschedule itself using the correct interval.
            self.app.root.after(0, lambda rn=room_number: self.update_all_props_status(rn))
            # --- END ADDED LINES ---

            # Subscribe to topics (EXISTING CODE BELOW)
            topics = [
                "/er/ping", "/er/name", "/er/cmd", "/er/riddles/info",
                "/er/music/info", "/er/music/soundlist", "/game/period",
                "/unixts", "/stat/games/count"
            ]
            try:
                for topic in topics:
                    # Subscribe on the MQTT thread loop
                    client.subscribe(topic)
            except Exception as e:
                print(f"[prop control]Error subscribing to topics for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' on connect: {e}")

            # Clear the disconnect history after 5 seconds of stable connection
            def clear_disconnect_history():
                if room_number in self.disconnect_rc7_history:
                    print(f"[prop control] Connection to room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' stable for 5s. Clearing rc=7 history.")
                    del self.disconnect_rc7_history[room_number]
            
            # Schedule history clearing after a stable period
            self.app.root.after(5000, clear_disconnect_history)

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
            self.update_connection_state(room_number, error_msg)  # Use the helper

            # Schedule retry
            self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))

    def update_connection_state(self, room_number, state):
        """Update the connection state display - only shows error states"""
        self.connection_states[room_number] = state

        if room_number == self.current_room and hasattr(self, 'status_label'):
            self.app.root.after(0, lambda:
                self._update_connection_state_ui(room_number, state)
            )

    def _update_connection_state_ui(self, room_number, state):
        if room_number == self.current_room and hasattr(self, 'status_label'):
            if any(error in state.lower() for error in ["failed", "timed out", "connecting", "lost"]):
                # Show error states in red
                self.status_label.config(
                    text=state,
                    fg='red'
                )
                # Clear props display on connection issues
                for widget in self.props_frame.winfo_children():
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
                
            # Pack button into grid with minimal padding
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
        return prop_info.get('ignore_progress', False)  # Returns False if flag doesn't exist

    def on_message(self, client, userdata, msg, room_number):
        """Modified to handle messages for all rooms, including tracking prop status changes."""
        try:
            if msg.topic == "/er/riddles/info":
                payload = json.loads(msg.payload.decode())
                
                if room_number not in self.all_props:
                    self.all_props[room_number] = {}
                    
                prop_id = payload.get("strId")
                if prop_id:
                    # Update MQTT last update time
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

                    _payload_copy = payload.copy()  # Ensure we use a copy in the lambda
                    self.app.root.after(0, lambda pdata=_payload_copy, rn=room_number: self.handle_prop_update(pdata, rn))

                    self.app.root.after(0, lambda: self.check_prop_status(
                        room_number, prop_id, self.all_props[room_number][prop_id]
                    ))
                        
        except json.JSONDecodeError:
            print(f"[prop control]Failed to decode message from room {room_number}: {msg.payload}")
        except Exception as e:
            print(f"[prop control]Error handling message from room {room_number}: {e}")

    def on_disconnect(self, client, userdata, rc, room_number):
        """Handle disconnection for a specific room's client, with aggressive retry for rc=7."""
        room_name = self.app.rooms.get(room_number, f"Room {room_number}")
        current_time = time.time()
        print(f"[prop control]Room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' disconnected with code: {rc} at {current_time}")  # Added timestamp

        # --- Aggressive Retry Logic for rc=7 ---
        if rc == 7:
            # Initialize history for this room if needed
            if room_number not in self.disconnect_rc7_history:
                self.disconnect_rc7_history[room_number] = []

            # Add current disconnect timestamp
            self.disconnect_rc7_history[room_number].append(current_time)
            #print(f"[prop control] DEBUG: Added rc=7 timestamp for room {room_number}. History: {self.disconnect_rc7_history[room_number]}")  # Debug

            # Filter out timestamps older than 10 seconds
            self.disconnect_rc7_history[room_number] = [
                ts for ts in self.disconnect_rc7_history[room_number]
                if current_time - ts <= 10
            ]
            disconnect_count = len(self.disconnect_rc7_history[room_number])  # Store count
            #print(f"[prop control] DEBUG: Filtered rc=7 history for room {room_number}. Count = {disconnect_count}. History: {self.disconnect_rc7_history[room_number]}")  # Debug

            # Check if threshold is met (2 or more disconnects in the last 10 seconds)
            if disconnect_count >= 2:
                print(f"[prop control]Detected {disconnect_count} rc=7 disconnects in <=10s for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}'. Triggering aggressive retry.")  # More specific log
                # Trigger the aggressive retry
                self.aggressive_retry(room_number)
                # Clear history *after* triggering aggressive retry
                self.disconnect_rc7_history[room_number] = []
                return  # Stop here, aggressive_retry handles the next step

            else:
                # If threshold not met, proceed with standard retry logic below for rc=7
                print(f"[prop control] DEBUG: rc=7 count ({disconnect_count}) for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' is below threshold (2). Scheduling standard retry.")  # Debug log
                # Fall through to the standard retry path below

        else:  # rc is not 7
            # For any other disconnect code (not rc=7), clear the rc=7 specific history
            if room_number in self.disconnect_rc7_history:
                print(f"[prop control] DEBUG: Clearing rc=7 history for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}' due to non-rc=7 disconnect (code {rc}).")  # Debug
                del self.disconnect_rc7_history[room_number]

        # --- Standard Retry Logic (for non-zero rc OR rc=7 below threshold) ---
        if rc != 0:  # Unexpected disconnect
            if rc == 7:
                # Use the count we calculated earlier if available
                count_info = f" (Count: {disconnect_count})" if 'disconnect_count' in locals() else ""
                status_msg = f"Connection to {room_name} props lost (Code 7{count_info}). Retrying in 10 seconds..."
            else:
                status_msg = f"Connection to {room_name} props lost (Code {rc}). Retrying in 10 seconds..."

            self.update_connection_state(room_number, status_msg)  # Use helper

            # Schedule standard retry using the helper method
            self._schedule_retry(room_number, 10000, lambda: self.retry_connection(room_number))
        # else: rc == 0 (expected disconnect, e.g., client.disconnect() called) - do nothing

    def aggressive_retry(self, room_number):
        """Performs a more aggressive retry for a room after repeated failures."""
        print(f"[prop control]Triggering aggressive retry for room '{self.ROOM_MAP.get(room_number, f'number {room_number}')}'")
        room_name = self.app.rooms.get(room_number, f"Room {room_number}")

        # Update UI status immediately (must use after)
        self.app.root.after(0, lambda:
            self.update_connection_state(room_number, f"Room {room_name}: Repeated disconnects (code 7). Waiting 5s before aggressive retry...")
        )

        # Define the task to run in a separate thread
        def do_aggressive_retry():
            # Clean up current client immediately within the thread
            if room_number in self.mqtt_clients:
                try:
                    old_client = self.mqtt_clients[room_number]
                    old_client.loop_stop()  # Stop its background thread
                    old_client.disconnect()  # Attempt a clean disconnect
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
        threading.Thread(target=do_aggressive_retry, daemon=True).start()

    def handle_prop_update(self, prop_data, originating_room_number):  # <-- ADD ARGUMENT
        """Handle updates to prop data with widget safety checks"""
        prop_id = prop_data.get("strId")
        if not prop_id:
            return
        # Modify the lambda to pass the originating_room_number
        self.app.root.after(0, lambda pid=prop_id, pdata=prop_data, rn=originating_room_number:  # <-- PASS ARGUMENT
                             self._handle_prop_update_ui(pid, pdata, rn))

    def _handle_prop_update_ui(self, prop_id, prop_data, originating_room_number):  # <-- ADD ARGUMENT
        """Actual implementation of handle_prop_update, using after."""

        # *** ADD THIS CHECK AT THE BEGINNING ***
        if originating_room_number != self.current_room:
            # This update is for a room that is not currently displayed.
            return
        # *** END ADDED CHECK ***

        # Load status icons (Correct)
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

        # Get order (CORRECTLY using current_room)
        order = self.get_prop_order(prop_data["strName"], self.current_room)

        current_status = prop_data.get("strStatus", "")

        # Check for status changes and update last_progress_times (Correct)
        if self.current_room is not None:
            previous_status = (self.all_props[self.current_room][prop_id].get('last_status')
                            if prop_id in self.all_props[self.current_room] else None)
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
                    mapped_name = self.get_mapped_prop_name(prop_name, self.current_room) # Get mapped name here
                    self.last_prop_finished[self.current_room] = mapped_name

        try:
            if prop_id not in self.props:
                # Create new prop widgets (Correct)
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
                    height=5,
                    cursor="hand2"
                )
                # Store prop name for hover events
                prop_name = prop_data.get("strName", "")
                if prop_name:
                    reset_btn.bind('<Enter>', lambda e, name=prop_name: self.highlight_circuit_props(name, True))
                    reset_btn.bind('<Leave>', lambda e, name=prop_name: self.highlight_circuit_props(name, False))
                reset_btn.pack(side='left', padx=1)

                activate_btn = tk.Button(
                    button_frame,
                    text="A",
                    font=('Arial', 5, 'bold'),
                    command=lambda: self.send_command(prop_id, "activate"),
                    bg='#ff8c00',
                    width=2,
                    height=5,
                    cursor="hand2"
                )
                activate_btn.pack(side='left', padx=1)

                finish_btn = tk.Button(
                    button_frame,
                    text="F",
                    font=('Arial', 5, 'bold'),
                    command=lambda: self.send_command(prop_id, "finish"),
                    bg='#28a745',
                    width=2,
                    height=5,
                    cursor="hand2"
                )
                finish_btn.pack(side='left', padx=1)

                mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)

                # Create name label (Correct)
                name_label = ttk.Label(prop_frame, font=('Arial', 8, 'bold'), text=mapped_name)
                # --- MODIFIED NAME LABEL FORMATTING ---
                if self.is_finishing_prop(self.current_room, prop_data['strName']):
                    name_label.config(font=('Arial', 8, 'bold', 'italic', 'underline'))
                elif self.is_standby_prop(self.current_room, prop_data['strName']):
                    name_label.config(font=('Arial', 8, 'bold', 'italic'))  # Italic for standby
                else:
                    name_label.config(font=('Arial', 8, 'bold'))

                name_label.pack(side='left', padx=5)  # Pack name_label *first*

                # Add a black line underneath if it's a finishing prop
                if self.is_finishing_prop(self.current_room, prop_data['strName']):
                    line_label = tk.Frame(prop_frame, height=1, bg="black")
                    line_label.pack(fill='x', padx=(5,0), pady=(0, 2), side='bottom')  # Pack *after* name label, adjust padx
                # --- END MODIFIED NAME LABEL FORMATTING ---

                name_label.bind('<Button-1>', lambda e, name=prop_data["strName"]: self.notify_prop_select(name))
                name_label.config(cursor="hand2")

                # Add hover events for cousin highlighting
                name_label.bind('<Enter>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, True))
                name_label.bind('<Leave>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, False))

                status_label = tk.Label(prop_frame)
                status_label.pack(side='right', padx=5)


                self.props[prop_id] = {
                    'frame': prop_frame,
                    'status_label': status_label,
                    'info': prop_data,
                    'last_update': time.time(),
                    'order': order,  # Use the retrieved order
                    'name_label': name_label,
                }

                # Set initial last status (Correct)
                if self.current_room not in self.all_props:
                    self.all_props[self.current_room] = {}

                if prop_id not in self.all_props[self.current_room]:
                    self.all_props[self.current_room][prop_id] = {}
                self.all_props[self.current_room][prop_id]['last_status'] = current_status

                # Sort and repack widgets (Correct)
                self.sort_and_repack_props() # call the modified sorting


            else:
                # Update existing prop info (Correct)
                name_label = self.props[prop_id].get('name_label')
                if name_label and name_label.winfo_exists():
                    try:
                        # Update values
                        self.props[prop_id]['info'] = prop_data
                        self.props[prop_id]['last_update'] = time.time()
                        self.props[prop_id]['order'] = order #use the order retrieved at the function top

                        # Get mapped name and set it here on update
                        mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)
                        name_label.config(text = mapped_name)


                        # Update the last status
                        if self.current_room not in self.all_props:
                            self.all_props[self.current_room] = {}
                        if prop_id not in self.all_props[self.current_room]:
                            self.all_props[self.current_room][prop_id] = {}
                        self.all_props[self.current_room][prop_id]['last_status'] = current_status

                        # --- MODIFIED NAME LABEL FORMATTING ---
                        if self.is_finishing_prop(self.current_room, prop_data['strName']):
                            name_label.config(font=('Arial', 9, 'bold', 'italic', 'underline'))
                        elif self.is_standby_prop(self.current_room, prop_data['strName']):
                            name_label.config(font=('Arial', 9, 'italic'))
                        else:
                            name_label.config(font=('Arial', 8, 'bold'))
                        # --- END MODIFIED NAME LABEL FORMATTING ---

                    except tk.TclError:
                        # Widget destroyed, remove reference
                        del self.props[prop_id]['name_label']
                else:
                    # Remove invalid widget reference
                    if 'name_label' in self.props[prop_id]:
                        del self.props[prop_id]['name_label']

            # Update status displays (Correct)
            if prop_id in self.props:
                status_label = self.props[prop_id].get('status_label')
                if status_label and status_label.winfo_exists():
                    self.update_prop_status(prop_id)

            self.check_finishing_prop_status(prop_id, prop_data)


        except tk.TclError as e:
            print(f"[prop control]Widget error in handle_prop_update: {e}")
            # Clean up invalid widget references
            if prop_id in self.props:
                for key in ['name_label', 'status_label', 'frame']:
                    if key in self.props[prop_id]:
                        del self.props[prop_id][key]
        except Exception as e:
            print(f"[prop control]Error in handle_prop_update: {e}")

    def create_prop_widgets(self, prop_id, prop_data, order):
        """Create new widgets for a prop"""
        try:
            prop_frame = ttk.Frame(self.props_frame)
            button_frame = ttk.Frame(prop_frame)
            button_frame.pack(side='left', padx=(0, 5))
            
            # Create control buttons
            reset_btn = tk.Button(
                button_frame,
                text="R",
                font=('Arial', 5, 'bold'),
                command=lambda: self.send_command(prop_id, "reset"),
                bg='#cc362b',
                width=2,
                height=4,
                cursor="hand2"
            )
            # Store prop name for hover events
            prop_name = prop_data.get("strName", "")
            if prop_name:
                reset_btn.bind('<Enter>', lambda e, name=prop_name: self.highlight_circuit_props(name, True))
                reset_btn.bind('<Leave>', lambda e, name=prop_name: self.highlight_circuit_props(name, False))
                #print(f"[prop control]Bound hover events for prop: {prop_name}")  # Debug print
            reset_btn.pack(side='left', padx=1)
            
            activate_btn = tk.Button(
                button_frame,
                text="A",
                font=('Arial', 5, 'bold'),
                command=lambda: self.send_command(prop_id, "activate"),
                bg='#ff8c00',
                width=2,
                height=4,
                cursor="hand2"
            )
            activate_btn.pack(side='left', padx=1)
            
            finish_btn = tk.Button(
                button_frame,
                text="F",
                font=('Arial', 5, 'bold'),
                command=lambda: self.send_command(prop_id, "finish"),
                bg='#28a745',
                width=2,
                height=4,
                cursor="hand2"
            )
            finish_btn.pack(side='left', padx=1)
            
            mapped_name = self.get_mapped_prop_name(prop_data["strName"], self.current_room)
            
            # Create name label
            name_label = ttk.Label(prop_frame, font=('Arial', 8, 'bold'), text=mapped_name)
            if self.is_finishing_prop(self.current_room, prop_data['strName']):
                name_label.config(font=('Arial', 8, 'bold', 'italic', 'underline'))
            name_label.pack(side='left', padx=5)
            
            name_label.bind('<Button-1>', lambda e, name=prop_data["strName"]: self.notify_prop_select(name))
            name_label.config(cursor="hand2")
            
            # Add hover events for cousin highlighting
            name_label.bind('<Enter>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, True))
            name_label.bind('<Leave>', lambda e, name=prop_data["strName"]: self.highlight_cousin_props(name, False))
            
            status_label = tk.Label(prop_frame)
            status_label.pack(side='right', padx=5)
            
            # Store widget references
            self.props[prop_id] = {
                'frame': prop_frame,
                'status_label': status_label,
                'info': prop_data,
                'last_update': time.time(),
                'order': order,
                'name_label': name_label,
            }
            
            # Sort and repack widgets
            sorted_props = sorted(self.props.items(), key=lambda x: x[1]['order'])
            for _, prop_info in sorted_props:
                if 'frame' in prop_info and prop_info['frame'].winfo_exists():
                    prop_info['frame'].pack_forget()
                    prop_info['frame'].pack(fill='x', pady=1)
                    
        except tk.TclError as e:
            print(f"[prop control]Error creating prop widgets: {e}")
            # Clean up any partially created widgets
            if prop_id in self.props:
                for key in ['name_label', 'status_label', 'frame']:
                    if key in self.props[prop_id]:
                        del self.props[prop_id][key]

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
        # Get the circuit value for the hovered prop
        #print(f"[prop control]Highlighting circuit props for {prop_name}")
        circuit = self.get_prop_circuit(prop_name)
        if not circuit:
            return
            
        # Find all props with the same circuit value
        room_key = self.ROOM_MAP[self.current_room]
        circuit_props = []
        
        # Get all props that share this circuit
        for name, info in self.prop_name_mappings[room_key]['mappings'].items():
            if info.get('circuit') == circuit:
                circuit_props.append(name)
                
        # Find and highlight/unhighlight the name labels for these props
        for prop_id, prop_data in self.props.items():
            if prop_data['info']['strName'] in circuit_props:
                try:
                    prop_frame = prop_data.get('frame')
                    name_label = prop_data.get('name_label')
                    if prop_frame and prop_frame.winfo_exists() and name_label and name_label.winfo_exists():
                        if highlight:
                            # Add visual highlighting
                            prop_frame.configure(style='Circuit.TFrame')
                            name_label.configure(style='Circuit.TLabel')
                        else:
                            # Remove visual highlighting
                            prop_frame.configure(style='TFrame')
                            name_label.configure(style='TLabel')
                except tk.TclError:
                    continue

    def highlight_cousin_props(self, prop_name, highlight):
        """Highlight or unhighlight props that are cousins"""
        # Get the cousin value for the hovered prop
        cousin = self.get_prop_cousin(prop_name)
        if not cousin:
            return
            
        # Find all props with the same cousin value
        room_key = self.ROOM_MAP[self.current_room]
        cousin_props = []
        
        # Get all props that share this cousin value
        for name, info in self.prop_name_mappings[room_key]['mappings'].items():
            if info.get('cousin') == cousin:
                cousin_props.append(name)
                
        # Find and highlight/unhighlight the name labels for these props
        for prop_id, prop_data in self.props.items():
            if prop_data['info']['strName'] in cousin_props:
                try:
                    prop_frame = prop_data.get('frame')
                    name_label = prop_data.get('name_label')
                    if prop_frame and prop_frame.winfo_exists() and name_label and name_label.winfo_exists():
                        if highlight:
                            # Add visual highlighting with pale green
                            prop_frame.configure(style='Cousin.TFrame')
                            name_label.configure(style='Cousin.TLabel')
                        else:
                            # Remove visual highlighting
                            prop_frame.configure(style='TFrame')
                            name_label.configure(style='TLabel')
                except tk.TclError:
                    continue

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
        if not hasattr(self, 'prop_name_mappings'):
            self.load_prop_name_mappings()

        prop_name = prop_data.get("strName")
        if not prop_name:
            return

        if self.current_room not in self.ROOM_MAP:
            return

        room_key = self.ROOM_MAP[self.current_room]

        assigned_kiosk = None
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == self.current_room:
                assigned_kiosk = computer_name
                break

        if assigned_kiosk and assigned_kiosk in self.app.interface_builder.connected_kiosks:
            # This method no longer needs to handle game-finish state directly.
            # Its purpose is solely to check for flagged prop finishes, and to
            # call handle_prop_update.
            pass

    def reset_game_finish_state(self, room_number):
        print("[prop control]resetted game finish state")
        if room_number in self.victory_sent:
            self.victory_sent[room_number] = False

        if room_number in self.finish_sound_played: #also reset prop control finish flag
            self.finish_sound_played[room_number] = False

        # Kiosk highlight reset is now handled in update_all_props_status

        #audio_manager = AdminAudioManager() #removed audio manager logic
        #if room_number in audio_manager.sound_states:
            #audio_manager.sound_states[room_number]['game_finish'] = False

    def update_kiosk_highlight(self, room_number, is_finished, is_activated, timer_expired=False):
        assigned_kiosk = None
        for computer_name, room_num in self.app.kiosk_tracker.kiosk_assignments.items():
            if room_num == room_number:
                assigned_kiosk = computer_name
                break

        if not assigned_kiosk or assigned_kiosk not in self.app.interface_builder.connected_kiosks:
            return

        try:
            kiosk_frame = self.app.interface_builder.connected_kiosks[assigned_kiosk]['frame']
            audio_manager = AdminAudioManager()
            #audio_manager.handle_timer_expired(timer_expired, room_number)
            #audio_manager.handle_game_finish(is_finished, room_number)

            if timer_expired:
                new_color = '#FFB6C1'
            elif is_finished:
                new_color = '#90EE90'
            elif is_activated:
                new_color = '#faf8ca'
            else:
                new_color = 'SystemButtonFace'

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

    def _send_victory_message(self, room_number, computer_name):
        """Sends a victory message to the kiosk (internal use)."""
        if hasattr(self.app, 'network_handler') and self.app.network_handler:
            # Use the network handler
            self.app.network_handler.send_victory_message(room_number, computer_name) # now correctly handled
            self.victory_sent[room_number] = True # set prop control flag
        else:
            print("[prop control]Network handler not available.")

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
            print(f"[prop control]No active room selected")
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
            print(f"[prop control]Unknown prop: {prop_name}")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = f"/er/{prop_map[prop_name]}"
        
        try:
            print(f"[prop control]Sending pneumatic prop command:")
            print(f"[prop control]Room: {self.current_room}")
            print(f"[prop control]Prop: {prop_name}")
            print(f"[prop control]Topic: {topic}")
            
            # Send the exact command the props expect
            client.publish(topic, "trigger", qos=0, retain=False)
            print(f"[prop control]Command sent successfully to {prop_name}")
            
        except Exception as e:
            print(f"[prop control]Failed to send command: {e}")

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
            # Reset progress/state tracking for the started room
            self.last_progress_times[self.current_room] = time.time()
            self.stale_sound_played[self.current_room] = False  # <-- RESET FLAG
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
            # Also reset progress/state tracking for the reset room
            self.last_progress_times[self.current_room] = time.time()  # Reset progress time
            self.stale_sound_played[self.current_room] = False  # <-- RESET FLAG
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
        except Exception as e:
            print(f"[prop control]Failed to send quest command: {e}")

    def _schedule_retry(self, room_number, delay, callback):
        """Cancels any pending retry for the room and schedules a new one."""
        if room_number in self.retry_timer_ids and self.retry_timer_ids[room_number] is not None:
            # print(f"[prop control]Cancelling existing timer {self.retry_timer_ids[room_number]} for room {room_number}") # Optional debug
            self.app.root.after_cancel(self.retry_timer_ids[room_number])
            self.retry_timer_ids[room_number] = None  # Clear the old ID

        timer_id = self.app.root.after(delay, callback)
        self.retry_timer_ids[room_number] = timer_id
        # print(f"[prop control]Scheduled new timer {timer_id} for room {room_number}") # Optional debug
