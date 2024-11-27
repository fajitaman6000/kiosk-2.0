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
        self.MQTT_ADDR = "192.168.0.12"
        self.MQTT_PORT = 9001  # Standard WebSocket port for MQTT
        self.MQTT_USER = "indestroom"
        self.MQTT_PASS = "indestroom"
        
        # Add status label for connection state
        self.status_label = ttk.Label(app.root, text="Connecting to prop server...")
        self.status_label.pack()

        # Create prop control panel
        self.frame = ttk.LabelFrame(app.root, text="Prop Controls")
        self.frame.pack(fill='both', expand=True, padx=10, pady=5)
        
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
        
        # Connect to MQTT
        self.setup_ui()
        self.setup_mqtt()

    def on_frame_configure(self, event=None):
        """Reset the scroll region to encompass the inner frame"""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def on_canvas_configure(self, event):
        """When canvas is resized, resize the inner frame to match"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def setup_ui(self):
        self.status_label = ttk.Label(self.app.root, text="Connecting to prop server...")
        self.status_label.pack()

        self.frame = ttk.LabelFrame(self.app.root, text="Prop Controls")
        self.frame.pack(fill='both', expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.props_frame = ttk.Frame(self.canvas)
        
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        
        self.canvas_frame = self.canvas.create_window((0,0), window=self.props_frame, anchor="nw")
        
        self.props_frame.bind("<Configure>", self.on_frame_configure)
        self.canvas.bind("<Configure>", self.on_canvas_configure)

    def setup_mqtt(self):
        print(f"Attempting to connect to MQTT broker at {self.MQTT_ADDR}:{self.MQTT_PORT}")
        
        client_id = f"id_{random.randint(0, 999)}"
        print(f"Using client ID: {client_id}")
        
        self.mqtt_client = mqtt.Client(
            client_id=f"id_{random.randint(0, 999)}",
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
            self.mqtt_client.connect(self.MQTT_ADDR, 8080, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Failed to connect: {e}")
            self.status_label.config(text=f"Connection failed: {e}")

    def on_connect(self, client, userdata, flags, rc):
        try:
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
            if hasattr(self, 'status_label'):
                self.status_label.config(text=status)

            if rc == 0:
                print("Successfully connected, subscribing to topics...")
                # Subscribe to all required topics
                self.mqtt_client.subscribe("/er/ping")
                self.mqtt_client.subscribe("/er/name")
                self.mqtt_client.subscribe("/er/cmd")
                self.mqtt_client.subscribe("/er/riddles/info")
                self.mqtt_client.subscribe("/er/music/info")
                self.mqtt_client.subscribe("/er/music/soundlist")
                self.mqtt_client.subscribe("/game/period")
                self.mqtt_client.subscribe("/unixts")
                self.mqtt_client.subscribe("/stat/games/count")
                print("Subscribed to all topics")
        except Exception as e:
            error_msg = f"Error in on_connect: {e}"
            print(error_msg)
            if hasattr(self, 'status_label'):
                self.status_label.config(text=error_msg)

    def on_disconnect(self, client, userdata, rc):
        print(f"Disconnected from MQTT broker with code: {rc}")
        if hasattr(self, 'status_label'):
            self.status_label.config(text="Disconnected from prop server")

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
        print(f"Sending command {command} to prop {prop_id}")
        topic = f"/er/{prop_id}/cmd"
        try:
            self.mqtt_client.publish(topic, command)
            print(f"Command sent successfully")
        except Exception as e:
            print(f"Failed to send command: {e}")

    def shutdown(self):
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()