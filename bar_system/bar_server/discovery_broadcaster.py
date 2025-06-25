# bar_server/discovery_broadcaster.py
import socket
import json
import time
from PyQt5.QtCore import QObject, pyqtSlot

import config
from network_protocol import DISCOVERY_PORT, DISCOVERY_MESSAGE_HEADER, BROADCAST_INTERVAL_S

class DiscoveryBroadcaster(QObject):
    """
    Runs in a dedicated thread to broadcast the server's presence
    over the local network using UDP.
    """
    def __init__(self):
        super().__init__()
        self._is_running = False
        self.udp_socket = None

    def _get_local_ip(self):
        """Finds the local IP address of the machine."""
        # This is a reliable way to get the primary IP on most systems
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # Doesn't have to be reachable
            s.connect(('10.255.255.255', 1))
            ip = s.getsockname()[0]
        except Exception:
            # Fallback
            ip = socket.gethostbyname(socket.gethostname())
        finally:
            s.close()
        return ip

    @pyqtSlot()
    def run(self):
        self._is_running = True

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        # Enable broadcasting mode
        self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        server_ip = self._get_local_ip()
        message_payload = {
            "header": DISCOVERY_MESSAGE_HEADER,
            "host": server_ip,
            "port": config.PORT # The TCP port clients should connect to
        }
        message_bytes = json.dumps(message_payload).encode('utf-8')

        print(f"Starting UDP broadcast on port {DISCOVERY_PORT}")
        print(f"Broadcasting connection info: {server_ip}:{config.PORT}")

        while self._is_running:
            # '<broadcast>' sends to 255.255.255.255
            self.udp_socket.sendto(message_bytes, ('<broadcast>', DISCOVERY_PORT))
            # Use a variable sleep to allow the stop() method to interrupt it
            for _ in range(BROADCAST_INTERVAL_S):
                if not self._is_running:
                    break
                time.sleep(1)

        print("UDP broadcast stopped.")
        if self.udp_socket:
            self.udp_socket.close()

    @pyqtSlot()
    def stop(self):
        print("Stopping UDP broadcaster...")
        self._is_running = False