import paho.mqtt.client as mqtt
import time

class MessageTracker:
    def __init__(self):
        self.seen_messages = set()
    
    def is_new_message(self, topic, payload):
        message_key = f"{topic}:{payload}"
        if message_key not in self.seen_messages:
            self.seen_messages.add(message_key)
            return True
        return False

tracker = MessageTracker()

def on_connect(client, userdata, flags, rc):
    print("[mqtt debug]Connected to MQTT broker")
    client.subscribe("#")
    print("[mqtt debug]Listening for MQTT traffic (showing only unique messages)...\n")

def on_message(client, userdata, msg):
    # Only show message if we haven't seen this topic:payload combination
    if tracker.is_new_message(msg.topic, msg.payload):
        print("[mqtt debug]====== NEW UNIQUE MQTT MESSAGE ======")
        print(f"[mqtt debug]Topic: {msg.topic}")
        print(f"[mqtt debug]Payload: {msg.payload}")
        print(f"[mqtt debug]QoS: {msg.qos}")
        print(f"[mqtt debug]Retain: {msg.retain}")
        print("[mqtt debug]===================================\n")

# Create client
client = mqtt.Client(
    client_id="mqtt_sniffer",
    transport="websockets",
    protocol=mqtt.MQTTv31,
    callback_api_version=mqtt.CallbackAPIVersion.VERSION1
)

# Set up client
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set("indestroom", "indestroom")
client.ws_set_options(path="/mqtt")

# Connect to broker
client.connect("192.168.0.49", 8080, 60)  # Use your Zombie room's IP

# Run until interrupted
try:
    client.loop_forever()
except KeyboardInterrupt:
    print("[mqtt debug]Sniffer stopped")
    client.disconnect()

# =============================== END OF FILE ===============================