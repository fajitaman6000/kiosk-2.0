import tkinter as tk
from tkinter import ttk
import paho.mqtt.client as mqtt
import json
import time
import random

class PropControl:
    def __init__(self, app):
        self.app = app
        self.props = {}  # strId -> prop info
        self.mqtt_clients = {}  # room_number -> mqtt client
        self.current_room = None
        
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
                'special_buttons': []
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
        
        # Add status label for connection state
        self.status_label = ttk.Label(app.root, text="Waiting for room selection...")
        self.status_label.pack()

        # Create prop control panel
        self.frame = ttk.LabelFrame(app.root, text="Prop Controls")
        self.frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        # Add global control buttons at the top
        self.global_controls = ttk.Frame(self.frame)
        self.global_controls.pack(fill='x', padx=5, pady=5)
        
        # Create Start Game and Reset All buttons
        self.start_button = ttk.Button(
            self.global_controls,
            text="START GAME",
            command=self.start_game
        )
        self.start_button.pack(side='left', padx=5)
        
        self.reset_button = ttk.Button(
            self.global_controls,
            text="RESET ALL",
            command=self.reset_all
        )
        self.reset_button.pack(side='left', padx=5)
        
        # Special buttons frame (will be populated based on room)
        self.special_frame = ttk.LabelFrame(self.frame, text="Room-Specific Controls")
        self.special_frame.pack(fill='x', padx=5, pady=5)
        
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

        # Initialize MQTT clients for each room
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
        
        try:
            client.ws_set_options(path="/mqtt")
            client.connect(config['ip'], self.MQTT_PORT, 60)
            client.loop_start()
            self.mqtt_clients[room_number] = client
        except Exception as e:
            print(f"Failed to connect to room {room_number}: {e}")

    def connect_to_room(self, room_number):
        """Switch to controlling a different room"""
        print(f"\nSwitching to room {room_number}")
        
        if room_number == self.current_room:
            return
            
        self.current_room = room_number
        
        # Clear existing props display
        self.props = {}
        for widget in self.props_frame.winfo_children():
            widget.destroy()
            
        # Update status
        room_name = self.app.rooms.get(room_number, "Unknown Room")
        self.status_label.config(text=f"Connected to {room_name} props")
        
        # Set up special buttons for this room
        self.setup_special_buttons(room_number)

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
            topics = [
                "/er/ping", "/er/name", "/er/cmd", "/er/riddles/info",
                "/er/music/info", "/er/music/soundlist", "/game/period",
                "/unixts", "/stat/games/count"
            ]
            for topic in topics:
                client.subscribe(topic)

    def setup_special_buttons(self, room_number):
        """Set up special buttons for the selected room"""
        for widget in self.special_frame.winfo_children():
            widget.destroy()
            
        if room_number not in self.room_configs:
            return
            
        buttons_frame = ttk.Frame(self.special_frame)
        buttons_frame.pack(fill='x', padx=5, pady=5)
        
        for button_text, prop_name in self.room_configs[room_number]['special_buttons']:
            ttk.Button(
                buttons_frame, 
                text=button_text,
                command=lambda pn=prop_name: self.send_special_command(pn, "on")
            ).pack(side='left', padx=5)

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
        if room_number == self.current_room:
            self.status_label.config(text=f"Disconnected from {self.app.rooms[room_number]} props")

    def handle_prop_update(self, prop_data):
        prop_id = prop_data.get("strId")
        if not prop_id:
            return

        if prop_id not in self.props:
            # Create new prop display
            prop_frame = ttk.Frame(self.props_frame)
            prop_frame.pack(fill='x', pady=2, padx=5)
            
            header_frame = ttk.Frame(prop_frame)
            header_frame.pack(fill='x', pady=2)
            
            name_label = ttk.Label(header_frame, text=prop_data["strName"])
            name_label.pack(side='left')
            
            status_frame = ttk.Frame(prop_frame)
            status_frame.pack(fill='x', pady=2)
            
            status_label = ttk.Label(status_frame, text=prop_data["strStatus"])
            status_label.pack(side='left')
            
            button_frame = ttk.Frame(prop_frame)
            button_frame.pack(fill='x', pady=2)
            
            reset_btn = ttk.Button(
                button_frame,
                text="RESET",
                command=lambda: self.send_command(prop_id, "reset")
            )
            reset_btn.pack(side='left', padx=5)
            
            activate_btn = ttk.Button(
                button_frame,
                text="ACTIVATE",
                command=lambda: self.send_command(prop_id, "activate")
            )
            activate_btn.pack(side='left', padx=5)
            
            finish_btn = ttk.Button(
                button_frame,
                text="FINISH",
                command=lambda: self.send_command(prop_id, "finish")
            )
            finish_btn.pack(side='left', padx=5)
            
            self.props[prop_id] = {
                'frame': prop_frame,
                'status_label': status_label,
                'info': prop_data
            }
        else:
            # Update existing prop
            current_status = self.props[prop_id]['info']['strStatus']
            new_status = prop_data['strStatus']
            if current_status != new_status:
                self.props[prop_id]['status_label'].config(text=new_status)
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
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        
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