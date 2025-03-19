print("[video server] Beginning imports ...")
import cv2
import socket
import struct
import threading
import numpy as np
import time
print("[video server] Ending imports ...")

class VideoServer:
    def __init__(self, port=8089):
        self.port = port
        self.running = False
        self.server_socket = None
        self.clients = {}  # Dictionary to store clients: {socket: address}
        self.clients_lock = threading.Lock()  # Lock for thread-safe client management
        self.fps_limit = 15
        self.frame_time = 1/self.fps_limit
        self.camera = None
        self.camera_lock = threading.Lock()  # Lock for camera access

    def check_camera(self):
        """Non-blocking camera check (remains largely the same)"""
        print("[video server]Checking camera availability...")
        try:
            with self.camera_lock:  # Acquire lock for camera operations
                print("[video_server.check_camera] thread lock here")
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Try DirectShow first
                if not cap.isOpened():
                    cap.release()
                    print("[video server]DirectShow failed, trying default")
                    cap = cv2.VideoCapture(0)  # Fallback to default
                    if not cap.isOpened():
                        print("[video server]Failed to open camera")
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
                        print("[video server]Camera check successful")
                        return True

                cap.release()
                print("[video server]Camera frame capture timed out")
                return False

        except Exception as e:
            print(f"[video server]Camera check error: {e}")
            return False
        finally:  #Ensure cap is released
            if 'cap' in locals() and cap.isOpened():
                cap.release()

    def start(self):
        """Non-blocking server start (remains largely the same)"""
        def startup():
            if not self.check_camera():
                print("[video server]Camera check failed")
                return False

            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('', self.port))
                self.server_socket.listen(5)  # Increase backlog for multiple connections
                self.running = True
                self.accept_connections()  # Start accepting connections
                return True
            except Exception as e:
                print(f"[video server]Failed to start video server: {e}")
                return False

        threading.Thread(target=startup, daemon=True).start()

    def accept_connections(self):
        """Accepts client connections and spawns streaming threads"""
        print("[video server]Video server ready for connections")
        self.server_socket.settimeout(1.0)  # Add a timeout to accept
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"[video server]New video connection from {addr}")
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                with self.clients_lock:
                    print("[video_server.accept_connections] thread lock here")
                    self.clients[client] = addr  # Add client to the dictionary
                    if len(self.clients) == 1:  # First client - open the camera
                        self._open_camera()

                threading.Thread(target=self.stream_video, args=(client, addr), daemon=True).start()

            except socket.timeout: # Catch the timeout
                pass
            except Exception as e:
                if self.running:
                    print(f"[video server]Connection error: {e}")
                break

    def _open_camera(self):
        """Opens the camera resource, protected by a lock"""
        with self.camera_lock:
            print("[video_server._open_camera] thread lock here")
            if self.camera is None or not self.camera.isOpened():
                self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                if not self.camera.isOpened():
                    self.camera = cv2.VideoCapture(0)
                if self.camera.isOpened():
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.camera.set(cv2.CAP_PROP_FPS, self.fps_limit)
                else:
                    print("[video server]Failed to open camera for streaming")

    def _release_camera(self):
        """Releases the camera resource, protected by a lock"""
        with self.camera_lock:
            print("[video_server._release_camera] thread lock here")
            if self.camera is not None and self.camera.isOpened():
                self.camera.release()
                self.camera = None

    def stream_video(self, client, addr):
        """Streams video to a single client"""
        print(f"[video server]Starting video stream to {addr}")
        client.settimeout(2.0)  # Add a timeout to the client socket
        try:
            while self.running:
                with self.camera_lock:
                    print("[video_server.stream_video] thread lock here")
                    if self.camera is None or not self.camera.isOpened():
                        # Camera might be closed if all clients disconnected, reopen it
                        self._open_camera()
                        if self.camera is None or not self.camera.isOpened():  # Still failed to open.
                            break  # Exit this client's thread

                    ret, frame = self.camera.read()

                if ret:
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                    _, buffer = cv2.imencode('.jpg', frame, encode_param)
                    size = len(buffer)
                    try:
                        client.sendall(struct.pack("Q", size))
                        client.sendall(buffer)
                    except socket.timeout: # Catch Timeout
                        print(f"[video server] Client {addr} sendall timeout")
                        break
                    except socket.error as e: # Catch more specific exception.
                        print(f"[video server]Client {addr} disconnected: {e}")
                        break  # Exit the loop, client disconnected
                else:
                    print("[video server]Failed to get frame")
                    break  # Exit the loop if frame read fails

        except Exception as e:
            print(f"[video server]Streaming error to {addr}: {e}")
        finally:
            print(f"[video server]Closing video stream to {addr}")
            try:
                client.close()
            except:
                pass

            with self.clients_lock:
                print("[video_server.stream_video] thread lock here")
                if client in self.clients:
                    del self.clients[client]
                    if not self.clients:  # Last client - close camera
                        self._release_camera()

    def stop(self):
        """Stops the server and all client threads"""
        print("[video server]Stopping video server")
        self.running = False

        with self.clients_lock:
            print("[video_server.stop] thread lock here")
            for client in self.clients:
                try:
                    client.close()
                except:
                    pass
            self.clients.clear()
            self._release_camera()  # Ensure camera is released

        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass