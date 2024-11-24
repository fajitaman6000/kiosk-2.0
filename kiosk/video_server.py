# video_server.py (add to kiosk side)
from PIL import Image, ImageTk
# video_server.py
import cv2 # type: ignore
import socket
import struct
import threading
import numpy as np # type: ignore
import time

class VideoServer:
    def __init__(self, port=8089):
        self.port = port
        self.running = False
        self.server_socket = None
        self.current_client = None
        self.fps_limit = 15
        self.frame_time = 1/self.fps_limit
        self.camera = None
        
    def check_camera(self):
        """Non-blocking camera check"""
        print("Checking camera availability...")
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Try DirectShow first
            if not cap.isOpened():
                cap.release()
                print("DirectShow failed, trying default")
                cap = cv2.VideoCapture(0)  # Fallback to default
                if not cap.isOpened():
                    print("Failed to open camera")
                    return False
            
            # Set camera properties
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, self.fps_limit)
            
            # Try to get a frame with timeout
            start_time = time.time()
            while time.time() - start_time < 2:  # 2 second timeout
                ret, frame = cap.read()
                if ret and frame is not None:
                    cap.release()
                    print("Camera check successful")
                    return True
            
            cap.release()
            print("Camera frame capture timed out")
            return False
            
        except Exception as e:
            print(f"Camera check error: {e}")
            if cap:
                cap.release()
            return False

    def start(self):
        """Non-blocking server start"""
        def startup():
            if not self.check_camera():
                print("Camera check failed")
                return False
                
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('', self.port))
                self.server_socket.listen(1)
                self.running = True
                self.accept_connections()  # Start accepting connections
                return True
            except Exception as e:
                print(f"Failed to start video server: {e}")
                return False
        
        # Run startup in separate thread
        threading.Thread(target=startup, daemon=True).start()
        
    def accept_connections(self):
        print("Video server ready for connections")
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"New video connection from {addr}")
                if self.current_client:
                    self.current_client.close()
                self.current_client = client
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                threading.Thread(target=self.stream_video, args=(client,), daemon=True).start()
            except Exception as e:
                if self.running:
                    print(f"Connection error: {e}")
                break
                
    def stream_video(self, client):
        print("Starting video stream")
        try:
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Try DirectShow first
            if not cap.isOpened():
                cap = cv2.VideoCapture(0)  # Fallback to default
                if not cap.isOpened():
                    print("Failed to open camera for streaming")
                    return
                    
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_FPS, self.fps_limit)
            
            while self.running and cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                    _, buffer = cv2.imencode('.jpg', frame, encode_param)
                    size = len(buffer)
                    try:
                        client.sendall(struct.pack("Q", size))
                        client.sendall(buffer)
                    except:
                        break
                else:
                    print("Failed to get frame")
                    break
                    
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            print("Closing video stream")
            cap.release()
            client.close()
            
    def stop(self):
        print("Stopping video server")
        self.running = False
        if self.current_client:
            try:
                self.current_client.close()
            except:
                pass
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass