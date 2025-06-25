# network_protocol.py
# (This file should exist in BOTH the server and client directories)

# --- Discovery Protocol ---
# The UDP port for broadcasting and listening.
DISCOVERY_PORT = 50889

# A unique "magic" message to ensure we only listen to our own app's broadcasts.
DISCOVERY_MESSAGE_HEADER = "BAR_SYSTEM_DISCOVERY_V1"

# The time in seconds between server broadcasts.
BROADCAST_INTERVAL_S = 3