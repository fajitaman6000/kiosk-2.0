# =========================================================================
# IMPORTANT: COMPLETE FILE REPLACEMENT INSTRUCTIONS
# =========================================================================
# 1. SELECT *EVERYTHING* IN YOUR CURRENT FILE AND DELETE IT
# 2. COPY *EVERYTHING* BETWEEN THESE MARKERS (FROM # === START === TO # === END ===)
# 3. PASTE THE COPIED CODE AS THE *ENTIRE* NEW FILE CONTENT
# =========================================================================
# === START OF COMPLETE FILE REPLACEMENT === START === START === START === 
# =========================================================================

import json
import time
import tkinter as tk
from tkinter import ttk
import threading
import socket
import paho.mqtt.client as mqtt
from queue import Queue

class PropEmulator:
    def __init__(self):
        # Basic prop configuration
        self.prop_id = "test_prop_1"  # Simple test prop identifier
        self.prop_name = "Test Puzzle 1"
        self.room_number = 4  # Zombie Outbreak room
        self.mqtt_port = 8080
        self.mqtt_ip = "192.168.0.12"
        
        # MQTT credentials
        self.mqtt_user = "indestroom"
        self.mqtt_pass = "indestroom"
        
        # State management
        self.status = "Not activated"
        self.should_run = True
        self.client = None
        self.broadcast_thread = None
        self.connection_queue = Queue()
        
        # Initialize GUI and MQTT
        self.setup_gui()
        self.setup_mqtt_client()
        
    def setup_gui(self):
        self.root = tk.Tk()
        self.root.title(f"Prop Emulator - {self.prop_name}")
        self.root.geometry("400x500")
        
        # Status section
        status_frame = ttk.LabelFrame(self.root, text="Connection Status")
        status_frame.pack(padx=10, pady=5, fill='x')
        
        self.server_label = ttk.Label(
            status_frame, 
            text="Starting up...", 
            foreground='blue',
            font=('Arial', 10, 'bold')
        )
        self.server_label.pack(pady=5)
        
        # Reconnect button
        self.reconnect_btn = tk.Button(
            status_frame,
            text="Reconnect",
            command=self.reconnect,
            bg='light blue',
            font=('Arial', 10, 'bold')
        )
        self.reconnect_btn.pack(pady=5)
        
        # Prop status
        prop_frame = ttk.LabelFrame(self.root, text="Prop Status")
        prop_frame.pack(padx=10, pady=5, fill='x')
        
        self.status_label = ttk.Label(
            prop_frame,
            text=f"Status: {self.status}",
            font=('Arial', 12, 'bold')
        )
        self.status_label.pack(pady=5)
        
        # Control buttons
        control_frame = ttk.LabelFrame(self.root, text="Controls")
        control_frame.pack(padx=10, pady=5, fill='x')
        
        buttons = [
            ("Not activated", "gray"),
            ("Activated", "orange"),
            ("Finished", "green")
        ]
        
        for status, color in buttons:
            btn = tk.Button(
                control_frame,
                text=status,
                command=lambda s=status: self.set_status(s),
                bg=color,
                fg='white',
                font=('Arial', 10, 'bold'),
                width=15,
                height=2
            )
            btn.pack(pady=5)
        
        # Debug log
        log_frame = ttk.LabelFrame(self.root, text="Debug Log")
        log_frame.pack(padx=10, pady=5, fill='both', expand=True)
        
        self.log_text = tk.Text(log_frame, height=10, width=40)
        self.log_text.pack(padx=5, pady=5, fill='both', expand=True)
        
        # Add scrollbar to log
        scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scrollbar.pack(side='right', fill='y')
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def log_debug(self, message):
        """Add message to debug log with timestamp"""
        if hasattr(self, 'log_text'):
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            self.root.after(0, lambda: self.log_text.insert('end', f"[{timestamp}] {message}\n"))
            self.root.after(0, self.log_text.see, 'end')

    def setup_mqtt_client(self):
        """Set up MQTT client"""
        try:
            # Create new client
            client_id = f"prop_{int(time.time())}"
            self.client = mqtt.Client(
                client_id=client_id,
                transport="websockets",
                protocol=mqtt.MQTTv31
            )
            
            # Set up callbacks
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_message = self.on_message
            
            # Set credentials
            self.client.username_pw_set(self.mqtt_user, self.mqtt_pass)
            
            # Set websocket options
            self.client.ws_set_options(path="/mqtt")
            
            # Connect to broker
            self.client.connect(self.mqtt_ip, self.mqtt_port, 60)
            self.client.loop_start()
            
            # Start broadcasting thread
            self.broadcast_thread = threading.Thread(target=self.broadcast_status, daemon=True)
            self.broadcast_thread.start()
            
            self.log_debug(f"Attempting connection to {self.mqtt_ip}:{self.mqtt_port}")
            
        except Exception as e:
            error_msg = f"Failed to setup MQTT client: {str(e)}"
            self.server_label.config(text=error_msg, foreground='red')
            self.log_debug(error_msg)

    def reconnect(self):
        """Reconnect to MQTT broker"""
        self.log_debug("Attempting reconnection...")
        self.server_label.config(text="Reconnecting...", foreground='blue')
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self.setup_mqtt_client()

    def on_connect(self, client, userdata, flags, rc):
        """Handle connection result"""
        status_codes = {
            0: "Connected successfully",
            1: "Incorrect protocol version",
            2: "Invalid client identifier",
            3: "Server unavailable",
            4: "Bad username or password",
            5: "Not authorized"
        }
        
        if rc == 0:
            self.server_label.config(
                text="Connected to MQTT broker",
                foreground='green'
            )
            client.subscribe(f"/er/{self.prop_id}/cmd")
            client.subscribe("/er/cmd")
            self.connection_queue.put(True)
        else:
            error_msg = f"Connection failed: {status_codes.get(rc, f'Unknown error {rc}')}"
            self.server_label.config(text=error_msg, foreground='red')
            self.connection_queue.put(False)
            
        self.log_debug(status_codes.get(rc, f"Connection result: {rc}"))

    def on_disconnect(self, client, userdata, rc):
        """Handle disconnection"""
        if rc != 0:
            self.log_debug("Unexpected disconnection")
            self.server_label.config(text="Disconnected from broker", foreground='red')
        else:
            self.log_debug("Disconnected successfully")

    def on_message(self, client, userdata, msg):
        """Handle incoming messages"""
        try:
            if msg.topic == f"/er/{self.prop_id}/cmd":
                command = msg.payload.decode()
                self.log_debug(f"Received command: {command}")
                if command == "activate":
                    self.set_status("Activated")
                elif command == "finish":
                    self.set_status("Finished")
                elif command == "reset":
                    self.set_status("Not activated")
            elif msg.topic == "/er/cmd":
                command = msg.payload.decode()
                self.log_debug(f"Received global command: {command}")
                if command == "reset":
                    self.set_status("Not activated")
        except Exception as e:
            self.log_debug(f"Error handling message: {e}")

    def set_status(self, new_status):
        """Update prop status"""
        self.status = new_status
        self.status_label.config(text=f"Status: {self.status}")
        self.log_debug(f"Status changed to: {new_status}")

    def broadcast_status(self):
        """Broadcast prop status periodically"""
        while self.should_run:
            try:
                if self.client and self.client.is_connected():
                    status_data = {
                        "strId": self.prop_id,
                        "strName": self.prop_name,
                        "strStatus": self.status
                    }
                    self.client.publish("/er/riddles/info", json.dumps(status_data))
                    time.sleep(1)
                else:
                    time.sleep(5)
            except Exception as e:
                self.log_debug(f"Error broadcasting status: {e}")
                time.sleep(5)

    def on_closing(self):
        """Clean shutdown"""
        self.log_debug("Shutting down prop emulator")
        self.should_run = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self.root.destroy()

    def run(self):
        """Start the emulator"""
        self.root.mainloop()

# =========================================================================
# PROGRAM ENTRY POINT - STARTS THE PROP EMULATOR
# =========================================================================

if __name__ == "__main__":
    emulator = PropEmulator()
    emulator.run()

# =========================================================================
# === END OF COMPLETE FILE REPLACEMENT === END === END === END === END ===
# =========================================================================