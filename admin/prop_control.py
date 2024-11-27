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
        self.mqtt_client = None
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

    def setup_special_buttons(self, room_number):
        """Set up special buttons for the selected room"""
        # Clear existing buttons
        for widget in self.special_frame.winfo_children():
            widget.destroy()
            
        if room_number not in self.room_configs:
            return
            
        buttons_frame = ttk.Frame(self.special_frame)
        buttons_frame.pack(fill='x', padx=5, pady=5)
        
        # Create buttons defined for this room
        for button_text, prop_name in self.room_configs[room_number]['special_buttons']:
            ttk.Button(
                buttons_frame, 
                text=button_text,
                command=lambda pn=prop_name: self.send_special_command(pn, "on")
            ).pack(side='left', padx=5)

    def connect_to_room(self, room_number):
        """Connect to the MQTT broker for the specified room"""
        if room_number not in self.room_configs:
            self.status_label.config(text="Room not configured for prop control")
            return
            
        self.current_room = room_number
        config = self.room_configs[room_number]
        
        # Disconnect existing client if any
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            
        # Clear existing props
        self.props = {}
        for widget in self.props_frame.winfo_children():
            widget.destroy()
            
        # Update status
        self.status_label.config(text=f"Connecting to {self.app.rooms[room_number]} props...")
        
        # Create new client
        client_id = f"id_{random.randint(0, 999)}"
        self.mqtt_client = mqtt.Client(
            client_id=client_id,
            transport="websockets",
            protocol=mqtt.MQTTv31,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1
        )
        
        self.mqtt_client.username_pw_set(self.MQTT_USER, self.MQTT_PASS)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        
        try:
            self.mqtt_client.ws_set_options(path="/mqtt")
            self.mqtt_client.connect(config['ip'], self.MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            
            # Set up special buttons for this room
            self.setup_special_buttons(room_number)
            
        except Exception as e:
            self.status_label.config(text=f"Connection failed: {e}")
            print(f"Failed to connect to {config['ip']}: {e}")

    def on_connect(self, client, userdata, flags, rc):
        connection_status = {
            0: "Connected successfully",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }
        status = connection_status.get(rc, f"Unknown error (code {rc})")
        print(f"MQTT connection status: {status}")
        
        if rc == 0:
            room_name = self.app.rooms.get(self.current_room, "Unknown Room")
            self.status_label.config(text=f"Connected to {room_name} props")
            
            # Subscribe to topics
            topics = [
                "/er/ping", "/er/name", "/er/cmd", "/er/riddles/info",
                "/er/music/info", "/er/music/soundlist", "/game/period",
                "/unixts", "/stat/games/count"
            ]
            for topic in topics:
                self.mqtt_client.subscribe(topic)
        else:
            self.status_label.config(text=f"Connection failed: {status}")

    def on_disconnect(self, client, userdata, rc):
        print(f"Disconnected from MQTT broker with code: {rc}")
        room_name = self.app.rooms.get(self.current_room, "Unknown Room")
        self.status_label.config(text=f"Disconnected from {room_name} props")

    def on_message(self, client, userdata, msg):
        try:
            if msg.topic == "/er/riddles/info":
                payload = json.loads(msg.payload.decode())
                self.app.root.after(0, lambda: self.handle_prop_update(payload))
        except json.JSONDecodeError:
            print(f"Failed to decode message: {msg.payload}")
        except Exception as e:
            print(f"Error handling message: {e}")

    def handle_prop_update(self, prop_data):
        prop_id = prop_data.get("strId")
        if not prop_id:
            print("No prop ID in update data")
            return

        if prop_id not in self.props:
            print(f"Creating new prop display for {prop_data['strName']}")
            # Create new prop display
            prop_frame = ttk.Frame(self.props_frame)
            prop_frame.pack(fill='x', pady=2, padx=5)
            
            # Number and name
            header_frame = ttk.Frame(prop_frame)
            header_frame.pack(fill='x', pady=2)
            
            name_label = ttk.Label(header_frame, text=prop_data["strName"])
            name_label.pack(side='left')
            
            # Status with its own frame
            status_frame = ttk.Frame(prop_frame)
            status_frame.pack(fill='x', pady=2)
            
            status_label = ttk.Label(status_frame, text=prop_data["strStatus"])
            status_label.pack(side='left')
            
            # Buttons frame
            button_frame = ttk.Frame(prop_frame)
            button_frame.pack(fill='x', pady=2)
            
            # Control buttons
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
            
            # Store references
            self.props[prop_id] = {
                'frame': prop_frame,
                'status_label': status_label,
                'info': prop_data
            }
            print(f"Created prop display for {prop_data['strName']}")
        else:
            # Only update and log if status actually changed
            current_status = self.props[prop_id]['info']['strStatus']
            new_status = prop_data['strStatus']
            if current_status != new_status:
                print(f"Status changed for {prop_data['strName']}: {new_status}")
                self.props[prop_id]['status_label'].config(text=new_status)
                self.props[prop_id]['info'] = prop_data

        # Update scroll region
        self.on_frame_configure()

    def send_command(self, prop_id, command):
        """Send command to standard props"""
        print(f"Sending command {command} to prop {prop_id}")
        topic = f"/er/{prop_id}/cmd"
        try:
            self.mqtt_client.publish(topic, command)
            print(f"Command sent successfully")
        except Exception as e:
            print(f"Failed to send command: {e}")

    def send_special_command(self, prop_name, command):
        """Send command to special props that don't need state tracking"""
        print(f"Sending {command} command to special prop: {prop_name}")
        topic = f"/er/{prop_name}/cmd"
        try:
            self.mqtt_client.publish(topic, command)
            print(f"Command sent successfully")
        except Exception as e:
            print(f"Failed to send command: {e}")

    def on_frame_configure(self, event=None):
        """Reset the scroll region to encompass the inner frame"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """When canvas is resized, resize the inner frame to match"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
        
    def shutdown(self):
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()