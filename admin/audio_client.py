# audio_client.py manages microphone activity, not admin application sounds
import pyaudio
import socket
import threading
import struct
import numpy as np
import math

class AudioClient:
    def __init__(self):
        self.running = False
        self.current_socket = None
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.speaking = False
        self.current_volume = 0.0
        self.selected_input_device_index = None
        
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
                    print(f"[audio client]Receive thread error: {e}")
                    self.disconnect()
            
            threading.Thread(target=safe_receive, daemon=True).start()
            return True
        except Exception as e:
            print(f"[audio client]Audio connection failed: {e}")
            self.disconnect()
            return False
            
    def receive_audio(self):
        print("[audio client]Starting audio reception")
        while self.running:
            try:
                # Get frame size
                size_data = self._recv_exactly(struct.calcsize("Q"))
                if not size_data:
                    print("[audio client]No size data received")
                    break
                chunk_size = struct.unpack("Q", size_data)[0]
                
                # Get audio data
                audio_data = self._recv_exactly(chunk_size)
                if not audio_data:
                    print("[audio client]No audio data received")
                    break
                
                # Always play received audio through output stream
                if self.output_stream and self.output_stream.is_active():
                    try:
                        self.output_stream.write(bytes(audio_data))
                    except Exception as e:
                        print(f"[audio client]Error playing audio: {e}")
                        continue
                        
            except socket.error as e:
                print(f"[audio client]Socket error in receive loop: {e}")
                break
            except Exception as e:
                print(f"[audio client]Error in receive loop: {e}")
                if not self.running:
                    break
                continue
                
        print("[audio client]Audio reception ended")
        
    def start_speaking(self):
        """Start capturing and sending audio from admin to kiosk"""
        if not self.running:
            print("[audio client]Cannot start speaking: Not connected.")
            return False
        if self.speaking:
            print("[audio client]Already speaking.")
            return True # Already running

        # Ensure default device is selected if none is explicitly set
        if self.selected_input_device_index is None:
            self.get_input_devices() # This attempts to set a default
            if self.selected_input_device_index is None:
                 print("[audio client]Error: No input device selected or available.")
                 return False

        print(f"[audio client]Starting microphone using device index: {self.selected_input_device_index}")
        try:
            # Create input stream for microphone using selected device
            self.input_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK,
                input_device_index=self.selected_input_device_index # Use selected device
            )

            self.speaking = True
            self.current_volume = 0.0 # Reset volume on start

            # Start sending thread
            def safe_send():
                try:
                    self.send_audio()
                except Exception as e:
                    print(f"[audio client]Send thread error: {e}")
                    self.stop_speaking()
            
            threading.Thread(target=safe_send, daemon=True).start()
            return True
        except Exception as e:
            print(f"[audio client]Error starting microphone: {e}")
            self.speaking = False
            return False
        
    def stop_speaking(self):
        """Stop capturing and sending audio"""
        print("[audio client]Stopping microphone")
        self.speaking = False
        self.current_volume = 0.0 # Reset volume
        
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
                self.input_stream = None
            except Exception as e:
                print(f"[audio client]Error closing input stream: {e}")
        
    def send_audio(self):
        """Send audio data to kiosk"""
        print("[audio client]Starting audio transmission")
        while self.running and self.speaking and self.input_stream:
            try:
                # Check if stream is active before reading
                if not self.input_stream or not self.input_stream.is_active():
                    print("[audio client]Input stream is not active. Stopping send loop.")
                    break

                data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                if data:
                    # Calculate volume (RMS)
                    self.current_volume = self._calculate_volume(data)

                    # Send data
                    size = len(data)
                    try:
                        self.current_socket.sendall(struct.pack("Q", size))
                        self.current_socket.sendall(data)
                    except Exception as e:
                        print(f"[audio client]Error sending audio packet: {e}")
                        break
            except Exception as e:
                print(f"[audio client]Error reading audio: {e}")
                break
        print("[audio client]Audio transmission ended")
        self.current_volume = 0.0 # Ensure reset when loop finishes
        
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
        print("[audio client]Disconnecting audio client...")
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

    def get_input_devices(self):
        """Returns a list of available input audio devices."""
        devices = []
        try:
            for i in range(self.audio.get_device_count()):
                dev_info = self.audio.get_device_info_by_index(i)
                if dev_info['maxInputChannels'] > 0:
                    devices.append({'index': i, 'name': dev_info['name']})
            # Set default if none selected
            if self.selected_input_device_index is None and devices:
                 default_device_info = self.audio.get_default_input_device_info()
                 self.selected_input_device_index = default_device_info['index']
        except Exception as e:
            print(f"[audio client]Error getting input devices: {e}")
        return devices

    def set_input_device(self, index):
        """Sets the input device and restarts the stream if currently speaking."""
        print(f"[audio client]Setting input device to index: {index}")
        if self.selected_input_device_index == index:
            return # No change needed

        self.selected_input_device_index = index
        if self.speaking:
            print("[audio client]Restarting microphone for new device...")
            # Temporarily store speaking state
            was_speaking = self.speaking
            # Stop current stream
            self.stop_speaking()
            # Restart stream with new device if it was previously active
            if was_speaking:
                self.start_speaking() # This will now use the new index

    def get_current_volume(self):
        """Returns the current normalized microphone volume (0.0 to 1.0)."""
        return self.current_volume

    def _calculate_volume(self, data):
        """Calculates normalized volume from audio data chunk."""
        try:
            audio_data = np.frombuffer(data, dtype=np.float32)
            rms = np.sqrt(np.mean(audio_data**2))
            # Normalize volume (logarithmic scale)
            if rms > 0:
                # Reduced sensitivity: Lower amplification factor (was 30)
                scaled_rms = rms * 8 # ADJUST THIS for sensitivity (lower = less sensitive)
                db_volume = 20 * math.log10(scaled_rms + 1e-9) # Epsilon avoids log(0)
                # Normalize dB range (e.g., -60dB to 0dB mapped to 0.0 to 1.0)
                min_db = -40 # ADJUST THIS lower threshold (less negative = less sensitive)
                max_db = 0   # Upper threshold (usually 0 dBFS)
                normalized_volume = max(0.0, min(1.0, (db_volume - min_db) / (max_db - min_db)))
            else:
                normalized_volume = 0.0
            return normalized_volume
        except Exception as vol_e:
            print(f"[audio client]Error calculating volume: {vol_e}")
            return 0.0 # Return 0 on error