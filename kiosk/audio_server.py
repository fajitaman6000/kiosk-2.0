# audio_server.py
print("[audio server] Beginning imports ...", flush=True)
print("[audio server] Importing pyaudio...", flush=True)
import pyaudio
print("[audio server] Imported pyaudio.", flush=True)
print("[audio server] Importing socket...", flush=True)
import socket
print("[audio server] Imported socket.", flush=True)
print("[audio server] Importing threading...", flush=True)
import threading
print("[audio server] Imported threading.", flush=True)
print("[audio server] Importing struct...", flush=True)
import struct
print("[audio server] Imported struct.", flush=True)
print("[audio server] Importing numpy...", flush=True)
import numpy as np
print("[audio server] Imported numpy.", flush=True)
print("[audio server] Ending imports ...", flush=True)

class AudioServer:
    def __init__(self, port=8090):
        self.port = port
        self.running = False
        self.server_socket = None
        self.current_client = None
        print("[audio server] Initializing PyAudio...", flush=True)
        self.audio = pyaudio.PyAudio()
        print("[audio server] Initialized PyAudio.", flush=True)
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
                print("[audio server] Creating socket...", flush=True)
                self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.server_socket.bind(('', self.port))
                self.server_socket.listen(1)
                print("[audio server] Socket created and listening.", flush=True)
                self.running = True
                self.accept_connections()
                return True
            except Exception as e:
                print(f"[audio server]Failed to start audio server: {e}", flush=True)
                return False
        
        threading.Thread(target=startup, daemon=True).start()
        
    def accept_connections(self):
        """Accept and handle client connections"""
        print("[audio server]Audio server ready for connections", flush=True)
        self.server_socket.settimeout(1.0) # add timeout
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                print(f"[audio server]New audio connection from {addr}", flush=True)
                if self.current_client:
                    self.current_client.close()
                self.current_client = client
                client.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

                # Start input stream for microphone
                print("[audio server] Opening audio input stream...", flush=True)
                self.input_stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
                print("[audio server] Audio input stream opened.", flush=True)

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
                    print(f"[audio server]Audio connection error: {e}", flush=True)
                break
                
    def stream_audio(self, client):
        """Send audio from kiosk to admin"""
        print("[audio server]Starting audio streaming to admin", flush=True)
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
                            print(f"[audio server]Client sendall timeout", flush=True)
                            break
                        except Exception as e:
                            print(f"[audio server]Error sending audio packet: {e}", flush=True)
                            break
                except Exception as e:
                    print(f"[audio server]Error reading audio: {e}", flush=True)
                    if not self.running:
                        break
                    continue
        except Exception as e:
            print(f"[audio server]Audio streaming error: {e}", flush=True)
        finally:
            print("[audio server]Audio streaming ended", flush=True)
            
    def receive_audio(self, client):
        """Receive and play audio from admin"""
        print("[audio server]Starting audio reception from admin", flush=True)
        try:
            # Create playback stream
            print("[audio server] Opening audio output stream...", flush=True)
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            print("[audio server] Audio output stream opened.", flush=True)
            
            while self.running:
                try:
                    # Get chunk size
                    size_data = self._recv_exactly(client, struct.calcsize("Q"))
                    if not size_data:
                        print("[audio server]No size data received", flush=True)
                        break
                    chunk_size = struct.unpack("Q", size_data)[0]
                    
                    # Get audio data
                    audio_data = self._recv_exactly(client, chunk_size)
                    if not audio_data:
                        print("[audio server]No audio data received", flush=True)
                        break
                    
                    # Play the audio
                    try:
                        if self.output_stream.is_active():
                            self.output_stream.write(bytes(audio_data))
                    except Exception as e:
                        print(f"[audio server]Error playing audio: {e}", flush=True)
                        continue
                        
                except socket.error as e:
                    print(f"[audio server]Socket error in receive loop: {e}", flush=True)
                    break
                except Exception as e:
                    print(f"[audio server]Error in receive loop: {e}", flush=True)
                    if not self.running:
                        break
                    continue
                        
        except Exception as e:
            print(f"[audio server]Audio receiving error: {e}", flush=True)
        finally:
            print("[audio server]Audio reception ended", flush=True)
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
                print("[audio_server] Recv timeout in _recv_exactly", flush=True)
                return None
            except socket.error as e:
                print(f"[audio_server] Socket error in _recv_exactly: {e}", flush=True)
                return None
        return data
            
    def stop(self):
        """Stop the server and clean up"""
        print("[audio server]Stopping audio server", flush=True)
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
        print("[audio server]Starting audio stream", flush=True)
        try:
            # Initialize recording stream
            print("[audio server] Opening stream for client...", flush=True)
            self.stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                frames_per_buffer=self.CHUNK
            )
            print("[audio server] Stream opened for client.", flush=True)
            
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
            print(f"[audio server]Audio streaming error: {e}", flush=True)
        finally:
            print("[audio server]Closing audio stream", flush=True)
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            client.close()