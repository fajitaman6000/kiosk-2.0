# audio_client.py
import pyaudio
import socket
import threading
import struct
import numpy as np

class AudioClient:
    def __init__(self):
        self.running = False
        self.current_socket = None
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.speaking = False
        
        # Audio parameters
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 44100
        
    def connect(self, host, port=8090):
        if self.current_socket:
            self.disconnect()
            
        try:
            self.current_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.current_socket.settimeout(3)  # 3 second timeout
            self.current_socket.connect((host, port))
            self.current_socket.settimeout(None)
            self.current_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self.running = True
            
            # Initialize output stream for receiving audio
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Start receiving thread
            def safe_receive():
                try:
                    self.receive_audio()
                except Exception as e:
                    print(f"Receive thread error: {e}")
                    self.disconnect()
            
            threading.Thread(target=safe_receive, daemon=True).start()
            return True
        except Exception as e:
            print(f"Audio connection failed: {e}")
            self.disconnect()
            return False
            
    def receive_audio(self):
        print("Starting audio reception")
        while self.running:
            try:
                # Get frame size
                size_data = self._recv_exactly(struct.calcsize("Q"))
                if not size_data:
                    print("No size data received")
                    break
                chunk_size = struct.unpack("Q", size_data)[0]
                
                # Get audio data
                audio_data = self._recv_exactly(chunk_size)
                if not audio_data:
                    print("No audio data received")
                    break
                
                # Always play received audio through output stream
                if self.output_stream and self.output_stream.is_active():
                    try:
                        self.output_stream.write(bytes(audio_data))
                    except Exception as e:
                        print(f"Error playing audio: {e}")
                        continue
                        
            except socket.error as e:
                print(f"Socket error in receive loop: {e}")
                break
            except Exception as e:
                print(f"Error in receive loop: {e}")
                if not self.running:
                    break
                continue
                
        print("Audio reception ended")
        
    def start_speaking(self):
        """Start capturing and sending audio from admin to kiosk"""
        if not self.running:
            return False
            
        try:
            # Create input stream for microphone
            self.input_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            self.speaking = True
            
            # Start sending thread
            def safe_send():
                try:
                    self.send_audio()
                except Exception as e:
                    print(f"Send thread error: {e}")
                    self.stop_speaking()
            
            threading.Thread(target=safe_send, daemon=True).start()
            return True
        except Exception as e:
            print(f"Error starting microphone: {e}")
            self.speaking = False
            return False
        
    def stop_speaking(self):
        """Stop capturing and sending audio"""
        print("Stopping microphone")
        self.speaking = False
        
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None
            except Exception as e:
                print(f"Error closing input stream: {e}")
        
    def send_audio(self):
        """Send audio data to kiosk"""
        print("Starting audio transmission")
        while self.running and self.speaking:
            try:
                data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                if data:
                    size = len(data)
                    try:
                        self.current_socket.sendall(struct.pack("Q", size))
                        self.current_socket.sendall(data)
                    except Exception as e:
                        print(f"Error sending audio packet: {e}")
                        break
            except Exception as e:
                print(f"Error reading audio: {e}")
                break
        print("Audio transmission ended")
        
    def _recv_exactly(self, size):
        """Helper to receive exact number of bytes"""
        data = bytearray()
        while len(data) < size:
            packet = self.current_socket.recv(min(size - len(data), 4096))
            if not packet:
                return None
            data.extend(packet)
        return data
        
    def disconnect(self):
        """Clean up resources"""
        print("Disconnecting audio client...")
        self.running = False
        self.speaking = False
        
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
            self.input_stream = None
            
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
            self.output_stream = None
                
        if self.current_socket:
            try:
                self.current_socket.shutdown(socket.SHUT_RDWR)
            except:
                pass
            try:
                self.current_socket.close()
            except:
                pass
            self.current_socket = None
            
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
        if hasattr(self, 'audio'):
            try:
                self.audio.terminate()
            except:
                pass

    def _recv_exactly(self, size):
        """Helper to receive exact number of bytes"""
        data = bytearray()
        while len(data) < size:
            packet = self.current_socket.recv(min(size - len(data), 4096))
            if not packet:
                return None
            data.extend(packet)
        return data