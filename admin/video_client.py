
from PIL import Image, ImageTk
# video_client.py
import cv2
import socket
import struct
import numpy as np
import threading
from time import time

class VideoClient:
    def __init__(self):
        self.running = False
        self.current_socket = None
        self.current_frame = None
        self.frame_ready = threading.Event()
        self.connection_timeout = 3
        
    def connect(self, host, port=8089):
        if self.current_socket:
            self.disconnect()
            
        try:
            self.current_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.current_socket.settimeout(self.connection_timeout)
            self.current_socket.connect((host, port))
            self.current_socket.settimeout(None)
            self.current_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.running = True
            threading.Thread(target=self.receive_video, daemon=True).start()
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            self.disconnect()
            return False
        
    def receive_video(self):
        try:
            while self.running:
                # Get frame size
                size_data = self._recv_exactly(struct.calcsize("Q"))
                if not size_data:
                    break
                frame_size = struct.unpack("Q", size_data)[0]
                
                # Get frame data
                frame_data = self._recv_exactly(frame_size)
                if not frame_data:
                    break
                    
                # Decode frame
                frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    self.current_frame = frame
                    self.frame_ready.set()
        except:
            pass
        finally:
            self.disconnect()
    
    def _recv_exactly(self, size):
        data = bytearray()
        while len(data) < size:
            packet = self.current_socket.recv(min(size - len(data), 4096))
            if not packet:
                return None
            data.extend(packet)
        return data
                
    def get_frame(self):
        if self.frame_ready.wait(timeout=0.1):  # Reduced timeout
            self.frame_ready.clear()
            return self.current_frame.copy() if self.current_frame is not None else None
        return None
        
    def disconnect(self):
        self.running = False
        if self.current_socket:
            try:
                self.current_socket.close()
            except:
                pass
            self.current_socket = None