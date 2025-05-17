print("[video server] Beginning imports ...", flush=True)
print("[video server] Importing cv2...", flush=True)
import cv2
print("[video server] Imported cv2.", flush=True)
print("[video server] Importing socket...", flush=True)
import socket
print("[video server] Imported socket.", flush=True)
print("[video server] Importing struct...", flush=True)
import struct
print("[video server] Imported struct.", flush=True)
print("[video server] Importing threading...", flush=True)
import threading
print("[video server] Imported threading.", flush=True)
print("[video server] Importing numpy...", flush=True)
import numpy as np
print("[video server] Imported numpy.", flush=True)
print("[video server] Importing time...", flush=True)
import time
print("[video server] Imported time.", flush=True)
print("[video server] Ending imports ...", flush=True)

class VideoServer:
    DEBUG = False
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
        print("[video server]Checking camera availability...", flush=True)
        try:
            with self.camera_lock:  # Acquire lock for camera operations
                print("[video_server.check_camera] thread lock here", flush=True)
                print("[video server] Initializing DirectShow camera...", flush=True)
                cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)  # Try DirectShow first
                if not cap.isOpened():
                    print("[video server] DirectShow camera failed to open.", flush=True)
                    cap.release()
                    print("[video server] Trying default camera...", flush=True)
                    cap = cv2.VideoCapture(0)  # Fallback to default
                    if not cap.isOpened():
                        print("[video server]Failed to open camera", flush=True)
                        return False
                    print("[video server] Default camera opened successfully.", flush=True)
                else:
                    print("[video server] DirectShow camera opened successfully.", flush=True)

                # Set camera properties
                print("[video server] Setting camera properties...", flush=True)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                cap.set(cv2.CAP_PROP_FPS, self.fps_limit)
                print("[video server] Camera properties set.", flush=True)

                # Try to get a frame with timeout
                print("[video server] Attempting to capture test frame...", flush=True)
                start_time = time.time()
                while time.time() - start_time < 2:  # 2 second timeout
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        print("[video server] Test frame captured successfully.", flush=True)
                        cap.release()
                        print("[video server]Camera check successful", flush=True)
                        return True

                cap.release()
                print("[video server]Camera frame capture timed out", flush=True)
                return False

        except Exception as e:
            print(f"[video server]Camera check error: {e}", flush=True)
            return False
        finally:  #Ensure cap is released
            if 'cap' in locals() and cap.isOpened():
                print("[video server] Releasing camera from check.", flush=True)
                cap.release()

    def start(self):
        """Non-blocking server start (remains largely the same)"""
        def startup():
            if not self.check_camera():
                print("[video server]Camera check failed", flush=True)
                return False

            try:
                print("[video server] Creating socket...", flush=True)
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('', self.port))
                self.server_socket.listen(5)  # Increase backlog for multiple connections
                print("[video server] Socket created and listening.", flush=True)
                self.running = True
                self.accept_connections()  # Start accepting connections
                return True
            except Exception as e:
                print(f"[video server]Failed to start video server: {e}", flush=True)
                return False

        threading.Thread(target=startup, daemon=True).start()

    def accept_connections(self):
        """Accepts client connections and spawns streaming threads"""
        print("[video server]Video server ready for connections", flush=True)
        self.server_socket.settimeout(1.0)  # Add a timeout to accept
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"[video server]New video connection from {addr}", flush=True)
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                with self.clients_lock:
                    print("[video_server.accept_connections] thread lock here", flush=True)
                    self.clients[client] = addr  # Add client to the dictionary
                    if len(self.clients) == 1:  # First client - open the camera
                        self._open_camera()

                threading.Thread(target=self.stream_video, args=(client, addr), daemon=True).start()

            except socket.timeout: # Catch the timeout
                pass
            except Exception as e:
                if self.running:
                    print(f"[video server]Connection error: {e}", flush=True)
                break

    def _open_camera(self):
        """Opens the camera resource, protected by a lock"""
        with self.camera_lock:
            print("[video_server._open_camera] thread lock here", flush=True)
            if self.camera is None or not self.camera.isOpened():
                print("[video server] Opening DirectShow camera for streaming...", flush=True)
                self.camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
                if not self.camera.isOpened():
                    print("[video server] DirectShow camera failed, trying default...", flush=True)
                    self.camera = cv2.VideoCapture(0)
                if self.camera.isOpened():
                    print("[video server] Camera opened successfully for streaming.", flush=True)
                    print("[video server] Setting streaming camera properties...", flush=True)
                    self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    self.camera.set(cv2.CAP_PROP_FPS, self.fps_limit)
                    print("[video server] Streaming camera properties set.", flush=True)
                else:
                    print("[video server]Failed to open camera for streaming", flush=True)

    def _release_camera(self):
        """Releases the camera resource, protected by a lock"""
        with self.camera_lock:
            print("[video_server._release_camera] thread lock here", flush=True)
            if self.camera is not None and self.camera.isOpened():
                print("[video server] Releasing camera resource...", flush=True)
                self.camera.release()
                print("[video server] Camera resource released.", flush=True)
                self.camera = None

    def stream_video(self, client, addr):
        """Streams video to a single client"""
        print(f"[video server]Starting video stream to {addr}", flush=True)
        client.settimeout(2.0)  # Add a timeout to the client socket
        try:
            while self.running:
                with self.camera_lock:
                    if(self.DEBUG): print("[video_server.stream_video] thread lock here", flush=True)
                    if self.camera is None or not self.camera.isOpened():
                        # Camera might be closed if all clients disconnected, reopen it
                        if(self.DEBUG): print("[video server] Camera not open, reopening...", flush=True)
                        self._open_camera()
                        if self.camera is None or not self.camera.isOpened():  # Still failed to open.
                            print("[video server] Failed to reopen camera, exiting stream.", flush=True)
                            break  # Exit this client's thread

                    if(self.DEBUG): print("[video server] Capturing frame...", flush=True)
                    ret, frame = self.camera.read()
                    if(self.DEBUG): print("[video server] Frame captured.", flush=True)

                if ret:
                    if(self.DEBUG): print("[video server] Encoding frame...", flush=True)
                    encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), 60]
                    _, buffer = cv2.imencode('.jpg', frame, encode_param)
                    size = len(buffer)
                    if(self.DEBUG): print("[video server] Frame encoded.", flush=True)
                    try:
                        if(self.DEBUG): print("[video server] Sending frame size...", flush=True)
                        client.sendall(struct.pack("Q", size))
                        if(self.DEBUG): print("[video server] Sending frame data...", flush=True)
                        client.sendall(buffer)
                        if(self.DEBUG): print("[video server] Frame sent successfully.", flush=True)
                    except socket.timeout: # Catch Timeout
                        if(self.DEBUG): print(f"[video server] Client {addr} sendall timeout", flush=True)
                        break
                    except socket.error as e: # Catch more specific exception.
                        if(self.DEBUG): print(f"[video server]Client {addr} disconnected: {e}", flush=True)
                        break  # Exit the loop, client disconnected
                else:
                    print("[video server]Failed to get frame", flush=True)
                    break  # Exit the loop if frame read fails

        except Exception as e:
            print(f"[video server]Streaming error to {addr}: {e}", flush=True)
        finally:
            print(f"[video server]Closing video stream to {addr}", flush=True)
            try:
                client.close()
            except:
                pass

            with self.clients_lock:
                print("[video_server.stream_video] thread lock here", flush=True)
                if client in self.clients:
                    del self.clients[client]
                    if not self.clients:  # Last client - close camera
                        self._release_camera()

    def stop(self):
        """Stops the server and all client threads"""
        print("[video server]Stopping video server", flush=True)
        self.running = False

        with self.clients_lock:
            print("[video_server.stop] thread lock here", flush=True)
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