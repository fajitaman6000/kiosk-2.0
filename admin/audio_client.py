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
        self.stream = None
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
            
            # Start playback stream
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Start receiving thread
            threading.Thread(target=self.receive_audio, daemon=True).start()
            return True
        except Exception as e:
            print(f"Audio connection failed: {e}")
            self.disconnect()
            return False
            
    def receive_audio(self):
        try:
            print("Starting audio reception")
            while self.running and not self.speaking:
                try:
                    # Get chunk size
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
                        
                    # Play audio - convert bytearray to bytes
                    if self.stream and self.stream.is_active():
                        try:
                            self.stream.write(bytes(audio_data))
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
        except Exception as e:
            print(f"Receive audio error: {e}")
        finally:
            print("Audio reception ended")
            self.disconnect()
                
    def start_speaking(self):
        """Start capturing and sending audio from admin to kiosk"""
        if not self.running:
            return False
            
        self.speaking = True
        
        # Create recording stream
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        # Start sending thread
        threading.Thread(target=self.send_audio, daemon=True).start()
        return True
        
    def stop_speaking(self):
        """Stop capturing and sending audio"""
        self.speaking = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        
        # Restart receiving stream
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            output=True,
            frames_per_buffer=self.CHUNK
        )
        threading.Thread(target=self.receive_audio, daemon=True).start()
        
    def send_audio(self):
        """Send audio data to kiosk"""
        print("Starting audio transmission")
        try:
            while self.running and self.speaking:
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
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
        finally:
            print("Audio transmission ended")
            self.stop_speaking()
    
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
        
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except:
                pass
            self.stream = None
                
        if self.current_socket:
            try:
                self.current_socket.shutdown(socket.SHUT_RDWR)
                self.current_socket.close()
            except:
                pass
            self.current_socket = None
            
    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
        self.audio.terminate()