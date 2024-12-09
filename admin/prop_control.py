import tkinter as tk
from tkinter import ttk
import paho.mqtt.client as mqtt
import json
import time
import random
import threading

class PropControl:
    def __init__(self, app):
        self.app = app
        self.props = {}  # strId -> prop info
        self.mqtt_clients = {}  # room_number -> mqtt client
        self.current_room = None
        self.connection_states = {}  # room_number -> connection state
        
        # Room-specific MQTT configurations
        self.room_configs = {
            4: {  # Zombie Outbreak
                'ip': '192.168.0.12',
                'special_buttons': [
                    ('KITCHEN', 'kitchen'),
                    ('BARREL', 'barrel'),
                    ('CAGE', 'cage'),
                    ('DOOR', 'door')
                ]
            },
            1: {  # Casino Heist
                'ip': '192.168.0.49',
                'special_buttons': [
                    ('SWITCH TO MORNING AFTER', 'quest/stag'),
                    ('SWITCH TO CASINO', 'quest/robbery')
                ]
            },
            2: {  # Morning After
                'ip': '192.168.0.49',
                'special_buttons': [
                    ('SWITCH TO MORNING AFTER', 'quest/stag'),
                    ('SWITCH TO CASINO', 'quest/robbery')
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
        
        self.MQTT_PORT = 8080
        self.MQTT_USER = "indestroom"
        self.MQTT_PASS = "indestroom"
        
        # Create prop control panel
        self.frame = ttk.LabelFrame(app.root, text="Prop Controls")
        self.frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Add global control buttons at the top
        self.global_controls = ttk.Frame(self.frame)
        self.global_controls.pack(fill='x', padx=5, pady=5)
        
        # Create Start Game and Reset All buttons
        self.start_button = tk.Button(
            self.global_controls,
            text="START GAME",
            command=self.start_game,
            bg='#285aed',   # Blue
            fg='white'
        )
        self.start_button.pack(side='left', padx=5)

        self.reset_button = tk.Button(
            self.global_controls,
            text="RESET ALL",
            command=self.reset_all,
            bg='#db42ad',   # Pink
            fg='white'
        )
        self.reset_button.pack(side='left', padx=5)
        
        # Special buttons frame (will be populated based on room)
        self.special_frame = ttk.LabelFrame(self.frame, text="Room-Specific Controls")
        self.special_frame.pack(fill='x', padx=5, pady=10)
        
        # Props display area with scrolling
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

        # Create a separate frame for the status label
        self.status_frame = ttk.Frame(self.props_frame)
        self.status_frame.grid(row=0, column=0, columnspan=3, sticky='ew')
        
        # Status message label for connection state
        self.status_label = tk.Label(self.status_frame, text="", font=('Arial', 12))
        self.status_label.pack(fill='x', padx=5, pady=5)

        # Configure grid columns for props
        for i in range(3):
            self.props_frame.grid_columnconfigure(i, weight=1)

        # Initialize MQTT clients for all rooms
        for room_number in self.room_configs:
            self.initialize_mqtt_client(room_number)

    def initialize_mqtt_client(self, room_number):
        """Create and connect MQTT client for a room"""
        if room_number not in self.room_configs:
            return

        config = self.room_configs[room_number]
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
                self.connection_states[room_number] = "Connecting..."
                
                # Only update UI if this is the current room and status_label exists
                if room_number == self.current_room and hasattr(self, 'status_label'):
                    self.status_label.config(text="Connecting...", fg='black')
                
                # Schedule timeout check
                self.app.root.after(5000, lambda: self.check_connection_timeout(room_number))
                
            except Exception as e:
                print(f"Failed to connect to room {room_number}: {e}")
                error_msg = f"Connection failed. Retrying in 10 seconds..."
                self.connection_states[room_number] = error_msg
                
                # Only update UI if this is the current room and status_label exists
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
                print(f"Connection to room {room_number} timed out")
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
                        print(f"Error cleaning up client for room {room_number}: {e}")
                
                threading.Thread(target=cleanup, daemon=True).start()
                
                # Schedule retry using after()
                self.app.root.after(10000, lambda: self.retry_connection(room_number))

    def retry_connection(self, room_number):
        """Retry connecting to a room's MQTT server without blocking"""
        print(f"Retrying connection to room {room_number}")
        
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
                    print(f"Error cleaning up old client for room {room_number}: {e}")
            
            # Initialize new connection
            self.initialize_mqtt_client(room_number)
        
        threading.Thread(target=do_retry, daemon=True).start()

    def connect_to_room(self, room_number):
        """Switch to controlling a different room"""
        print(f"\nSwitching to room {room_number}")
        
        if room_number == self.current_room:
            return
            
        self.current_room = room_number
        
        # Clear existing props display
        self.props = {}
        for widget in self.props_frame.winfo_children():
            if widget != self.status_frame:  # Keep the status frame
                widget.destroy()
                
        # Set up special buttons for this room
        self.setup_special_buttons(room_number)
        
        # Display current connection state or initialize new connection
        if room_number in self.connection_states and hasattr(self, 'status_label'):
            try:
                self.status_label.config(
                    text=self.connection_states[room_number],
                    fg='black' if "Connected" in self.connection_states[room_number] else 'red'
                )
            except tk.TclError:
                print("Status label was destroyed, skipping update")
        else:
            self.initialize_mqtt_client(room_number)

    def on_connect(self, client, userdata, flags, rc, room_number):
        """Handle connection for a specific room's client"""
        status = {
            0: "Connected successfully",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }.get(rc, f"Unknown error (code {rc})")
        
        print(f"Room {room_number} MQTT status: {status}")
        
        if rc == 0:
            self.update_connection_state(room_number, "Connected")
            topics = [
                "/er/ping", "/er/name", "/er/cmd", "/er/riddles/info",
                "/er/music/info", "/er/music/soundlist", "/game/period",
                "/unixts", "/stat/games/count"
            ]
            for topic in topics:
                client.subscribe(topic)
        else:
            self.update_connection_state(room_number, f"Connection failed: {status}. Retrying in 10 seconds...")
            # Schedule retry
            self.app.root.after(10000, lambda: self.retry_connection(room_number))

    def update_connection_state(self, room_number, state):
        """Update the connection state display"""
        self.connection_states[room_number] = state
        if room_number == self.current_room and hasattr(self, 'status_label'):
            # Determine text color based on state
            if "failed" in state.lower() or "timed out" in state.lower():
                text_color = 'red'
                # Clear props display
                for widget in self.props_frame.winfo_children():
                    if widget != self.status_frame:  # Keep the status frame
                        widget.destroy()
                self.props = {}
            elif "connecting" in state.lower():
                text_color = 'black'
            else:
                text_color = 'black'

            self.status_label.config(
                text=state,
                fg=text_color
            )

    def setup_special_buttons(self, room_number):
        for widget in self.special_frame.winfo_children():
            widget.destroy()
            
        if room_number not in self.room_configs:
            return
            
        buttons_frame = ttk.Frame(self.special_frame)
        buttons_frame.pack(fill='x', padx=5, pady=5)
        
        button_style = {'background': '#ffcccc'}  # Pale red background
        
        for button_text, command_name in self.room_configs[room_number]['special_buttons']:
            if command_name.startswith('quest/'):
                quest_type = command_name.split('/')[1]
                btn = tk.Button(
                    buttons_frame, 
                    text=button_text,
                    command=lambda qt=quest_type: self.send_quest_command(qt),
                    **button_style
                )
                btn.pack(side='left', padx=5)
            else:
                btn = tk.Button(
                    buttons_frame, 
                    text=button_text,
                    command=lambda pn=command_name: self.send_special_command(pn, "on"),
                    **button_style
                )
                btn.pack(side='left', padx=5)

    def on_message(self, client, userdata, msg, room_number):
        """Handle message from a specific room's client"""
        if room_number != self.current_room:
            return  # Ignore messages from non-active rooms
            
        try:
            if msg.topic == "/er/riddles/info":
                payload = json.loads(msg.payload.decode())
                self.app.root.after(0, lambda: self.handle_prop_update(payload))
        except json.JSONDecodeError:
            print(f"Failed to decode message from room {room_number}: {msg.payload}")
        except Exception as e:
            print(f"Error handling message from room {room_number}: {e}")

    def on_disconnect(self, client, userdata, rc, room_number):
        """Handle disconnection for a specific room's client"""
        print(f"Room {room_number} disconnected with code: {rc}")
        room_name = self.app.rooms.get(room_number, f"Room {room_number}")
        if rc != 0:  # Unexpected disconnect
            self.update_connection_state(room_number, 
                f"Connection to {room_name} props lost. Retrying in 10 seconds...")
            # Schedule retry
            self.app.root.after(10000, lambda: self.retry_connection(room_number))

    def handle_prop_update(self, prop_data):
        """Handle updates to prop status and create/update the UI elements"""
        prop_id = prop_data.get("strId")
        if not prop_id:
            return

        if prop_id not in self.props:
            # Calculate column position (3 columns)
            num_props = len(self.props)
            row = (num_props // 3) + 1  # +1 to account for status_frame at row 0
            col = num_props % 3

            # Create new prop display
            prop_frame = ttk.Frame(self.props_frame)
            prop_frame.grid(row=row, column=col, padx=0, pady=0, sticky='nsew')
            
            # Create prop card with border and padding
            card_frame = ttk.Frame(prop_frame, relief="solid", borderwidth=2)
            card_frame.pack(fill='both', expand=True, padx=2, pady=2)
            
            # Prop name in bold
            name_label = ttk.Label(card_frame, text=prop_data["strName"], 
                                font=('TkDefaultFont', 10, 'bold'))
            name_label.pack(fill='x', padx=5, pady=1)
            
            # Status with color
            status_text = prop_data["strStatus"]
            status_color = {
                "Not activated": "#808080",  # Grey
                "Not Activated": "#808080",  # Grey
                "Activated": "#ff0000",      # Red
                "Finished": "#0000ff"        # Blue
            }.get(status_text, "black")
            
            status_label = ttk.Label(card_frame, text=status_text, foreground=status_color)
            status_label.pack(fill='x', padx=5)
            
            # Control buttons in a horizontal frame
            button_frame = ttk.Frame(card_frame)
            button_frame.pack(fill='x', padx=5, pady=5)
            
            # Control buttons with improved spacing
            reset_btn = tk.Button(
                button_frame,
                text="RESET",
                command=lambda: self.send_command(prop_id, "reset"),
                bg='#cc362b',
                fg='white',
                width=8
            )
            reset_btn.pack(side='left', padx=2)
            
            activate_btn = tk.Button(
                button_frame,
                text="ACTIVATE",
                command=lambda: self.send_command(prop_id, "activate"),
                bg='#ff8c00',
                fg='white',
                width=8
            )
            activate_btn.pack(side='left', padx=2)
            
            finish_btn = tk.Button(
                button_frame,
                text="FINISH",
                command=lambda: self.send_command(prop_id, "finish"),
                bg='#28a745',
                fg='white',
                width=8
            )
            finish_btn.pack(side='left', padx=2)
            
            # Store references to UI elements
            self.props[prop_id] = {
                'frame': prop_frame,
                'card_frame': card_frame,
                'status_label': status_label,
                'info': prop_data
            }
        else:
            # Update existing prop status
            current_status = self.props[prop_id]['info']['strStatus']
            new_status = prop_data['strStatus']
            if current_status != new_status:
                status_color = {
                    "Not activated": "#808080",
                    "Activated": "#ff0000",
                    "Finished": "#0000ff"
                }.get(new_status, "black")
                
                self.props[prop_id]['status_label'].config(
                    text=new_status, 
                    foreground=status_color
                )
                self.props[prop_id]['info'] = prop_data

        self.on_frame_configure()

    def send_command(self, prop_id, command):
        """Send command to standard props"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = f"/er/{prop_id}/cmd"
        try:
            client.publish(topic, command)
            print(f"Command sent successfully to room {self.current_room}")
        except Exception as e:
            print(f"Failed to send command: {e}")

    def send_special_command(self, prop_name, command):
        """Send command to special props"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = f"/er/{prop_name}/cmd"
        try:
            client.publish(topic, command)
            print(f"Special command sent successfully to room {self.current_room}")
        except Exception as e:
            print(f"Failed to send special command: {e}")

    def on_frame_configure(self, event=None):
        """Reconfigure the canvas scrolling region"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        
        # Ensure props_frame spans the full width
        width = self.canvas.winfo_width()
        self.canvas.itemconfig(self.canvas_frame, width=width)

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
            print("No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        try:
            client.publish("/er/cmd", "start")
            print(f"Start game command sent to room {self.current_room}")
            # Log the action
            if hasattr(self.app, 'kiosk_tracker'):
                self.app.kiosk_tracker.log_action(f"Started game in room {self.current_room}")
        except Exception as e:
            print(f"Failed to send start game command: {e}")

    def reset_all(self):
        """Send reset all command to current room"""
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        try:
            client.publish("/er/cmd", "reset")
            print(f"Reset all command sent to room {self.current_room}")
            # Log the action
            if hasattr(self.app, 'kiosk_tracker'):
                self.app.kiosk_tracker.log_action(f"Reset all props in room {self.current_room}")
        except Exception as e:
            print(f"Failed to send reset all command: {e}")

    def send_quest_command(self, quest_type):
        if self.current_room is None or self.current_room not in self.mqtt_clients:
            print("No active room selected")
            return
            
        client = self.mqtt_clients[self.current_room]
        topic = "/er/quest"
        try:
            client.publish(topic, quest_type)
            print(f"Quest command '{quest_type}' sent successfully to room {self.current_room}")
            if hasattr(self.app, 'kiosk_tracker'):
                self.app.kiosk_tracker.log_action(f"Sent quest command '{quest_type}' to room {self.current_room}")
        except Exception as e:
            print(f"Failed to send quest command: {e}")
