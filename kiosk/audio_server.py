# audio_server.py
print("[audio server] Beginning imports ...")
import pyaudio
import socket
import threading
import struct
import numpy as np
print("[audio server] Ending imports ...")

class AudioServer:
    def __init__(self, port=8090):
        self.port = port
        self.running = False
        self.server_socket = None
        self.current_client = None
        self.audio = pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None
        self.receiving_audio = False
        
        # Audio parameters
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paFloat32
        self.CHANNELS = 1
        self.RATE = 44100
        
    def start(self):
        """Non-blocking server start"""
        def startup():
            try:
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('', self.port))
                self.server_socket.listen(1)
                self.running = True
                self.accept_connections()
                return True
            except Exception as e:
                print(f"[audio server]Failed to start audio server: {e}")
                return False
        
        threading.Thread(target=startup, daemon=True).start()
        
    def accept_connections(self):
        """Accept and handle client connections"""
        print("[audio server]Audio server ready for connections")
        self.server_socket.settimeout(1.0) # add timeout
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"[audio server]New audio connection from {addr}")
                if self.current_client:
                    self.current_client.close()
                self.current_client = client
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # Start input stream for microphone
                self.input_stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )

                # Start sending thread
                threading.Thread(target=self.stream_audio,
                                args=(client,), daemon=True).start()

                # Start receiving thread
                threading.Thread(target=self.receive_audio,
                                args=(client,), daemon=True).start()
            except socket.timeout: # catch timeout
                pass
            except Exception as e:
                if self.running:
                    print(f"[audio server]Audio connection error: {e}")
                break
                
    def stream_audio(self, client):
        """Send audio from kiosk to admin"""
        print("[audio server]Starting audio streaming to admin")
        client.settimeout(2.0) # Add timeout
        try:
            while self.running:  # Always stream while running
                try:
                    data = self.input_stream.read(self.CHUNK, exception_on_overflow=False)
                    if data:
                        size = len(data)
                        try:
                            client.sendall(struct.pack("Q", size))
                            client.sendall(data)
                        except socket.timeout: # Catch Timeout
                            print(f"[audio server]Client sendall timeout")
                            break
                        except Exception as e:
                            print(f"[audio server]Error sending audio packet: {e}")
                            break
                except Exception as e:
                    print(f"[audio server]Error reading audio: {e}")
                    if not self.running:
                        break
                    continue
        except Exception as e:
            print(f"[audio server]Audio streaming error: {e}")
        finally:
            print("[audio server]Audio streaming ended")
            
    def receive_audio(self, client):
        """Receive and play audio from admin"""
        print("[audio server]Starting audio reception from admin")
        try:
            # Create playback stream
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            
            while self.running:
                try:
                    # Get chunk size
                    size_data = self._recv_exactly(client, struct.calcsize("Q"))
                    if not size_data:
                        print("[audio server]No size data received")
                        break
                    chunk_size = struct.unpack("Q", size_data)[0]
                    
                    # Get audio data
                    audio_data = self._recv_exactly(client, chunk_size)
                    if not audio_data:
                        print("[audio server]No audio data received")
                        break
                    
                    # Play the audio
                    try:
                        if self.output_stream.is_active():
                            self.output_stream.write(bytes(audio_data))
                    except Exception as e:
                        print(f"[audio server]Error playing audio: {e}")
                        continue
                        
                except socket.error as e:
                    print(f"[audio server]Socket error in receive loop: {e}")
                    break
                except Exception as e:
                    print(f"[audio server]Error in receive loop: {e}")
                    if not self.running:
                        break
                    continue
                        
        except Exception as e:
            print(f"[audio server]Audio receiving error: {e}")
        finally:
            print("[audio server]Audio reception ended")
            if self.output_stream:
                try:
                    self.output_stream.stop_stream()
                    self.output_stream.close()
                except:
                    pass
                
    def _recv_exactly(self, client, size):
        """Helper to receive exact number of bytes"""
        client.settimeout(2.0) # add timeout
        data = bytearray()
        while len(data) < size:
            try:
                packet = client.recv(min(size - len(data), 4096))
                if not packet:
                    return None
                data.extend(packet)
            except socket.timeout: # Catch timeout
                print("[audio_server] Recv timeout in _recv_exactly")
                return None
            except socket.error as e:
                print(f"[audio_server] Socket error in _recv_exactly: {e}")
                return None
        return data
            
    def stop(self):
        """Stop the server and clean up"""
        print("[audio server]Stopping audio server")
        self.running = False
        
        if self.current_client:
            try:
                self.current_client.shutdown(socket.SHUT_RDWR)
                self.current_client.close()
            except:
                pass
                
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
                
        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except:
                pass
                
        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass

    def __del__(self):
        """Cleanup on deletion"""
        self.stop()
        if hasattr(self, 'audio'):
            try:
                self.audio.terminate()
            except:
                pass

    def handle_client(self, client):
        """Handle audio streaming for a client"""
        print("[audio server]Starting audio stream")
        try:
            # Initialize recording stream
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            
            # Start sending thread
            send_thread = threading.Thread(
                target=self.stream_audio,
                args=(client,),
                daemon=True
            )
            send_thread.start()
            
            # Start receiving thread
            receive_thread = threading.Thread(
                target=self.receive_audio,
                args=(client,),
                daemon=True
            )
            receive_thread.start()
            
            # Wait for threads to complete
            send_thread.join()
            receive_thread.join()
            
        except Exception as e:
            print(f"[audio server]Audio streaming error: {e}")
        finally:
            print("[audio server]Closing audio stream")
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            client.close()