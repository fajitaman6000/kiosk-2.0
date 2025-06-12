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
        """Receive and play audio from admin. Uses lazy initialization for the output stream."""
        print("[audio server]Starting audio reception from admin (waiting for first packet)...", flush=True)
        # We will initialize self.output_stream ONLY when we first receive data.
        
        try:
            # --- LAZY INITIALIZATION STAGE ---
            # Wait for the first packet before opening the audio device.
            # Use a longer timeout or no timeout for this first read, as we don't know
            # when the admin will start talking. Here we remove the timeout temporarily.
            client.settimeout(None) # Block indefinitely until data arrives or connection closes
            
            # 1. Receive the first chunk size
            size_data = self._recv_exactly(client, struct.calcsize("Q"))
            if not size_data:
                print("[audio server] ERROR: Did not receive initial packet from admin.", flush=True)

            chunk_size = struct.unpack("Q", size_data)[0]

            # Sanity check the size before proceeding
            if chunk_size <= 0 or chunk_size > self.CHUNK * 4 * 20: # 4 is for paFloat32
                print(f"[audio server] ERROR: Invalid initial chunk size received ({chunk_size}).", flush=True)

            # 2. Receive the first audio data chunk
            audio_data = self._recv_exactly(client, chunk_size)
            if not audio_data:
                print("[audio server] ERROR: Did not receive initial audio data.", flush=True)

            # --- DATA IS ARRIVING - INITIALIZE AND PLAY ---
            print("[audio server] First audio packet received. Opening audio output stream...", flush=True)
            self.output_stream = self.audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                output=True,
                frames_per_buffer=self.CHUNK
            )
            print("[audio server] Audio output stream opened. Playing initial packet.", flush=True)
            
            # Play the first chunk we already received
            if self.output_stream.is_active():
                self.output_stream.write(bytes(audio_data))

            # --- REGULAR RECEIVE LOOP ---
            # Now that we are active, we can use a shorter timeout for subsequent reads.
            client.settimeout(2.0)

            while self.running:
                try:
                    # Get chunk size
                    size_data = self._recv_exactly(client, struct.calcsize("Q"))
                    if not size_data:
                        print("[audio server]No more size data received, stream likely ended.", flush=True)
                        break
                    chunk_size = struct.unpack("Q", size_data)[0]
                    
                    # Get audio data
                    audio_data = self._recv_exactly(client, chunk_size)
                    if not audio_data:
                        print("[audio server]No more audio data received, stream likely ended.", flush=True)
                        break
                    
                    # Play the audio
                    if self.output_stream and self.output_stream.is_active():
                        self.output_stream.write(bytes(audio_data))
                        
                except socket.error as e:
                    print(f"[audio server]Socket error in receive loop: {e}", flush=True)
                    break # Exit on socket errors
                except Exception as e:
                    # Catching generic exception here is broad, but okay for this context
                    print(f"[audio server]Error in receive loop: {e}", flush=True)
                    if not self.running:
                        break # Exit if server is stopping
                    continue # Otherwise, try to continue
                        
        except Exception as e:
            # This will catch errors during the initial blocking read
            if self.running:
                print(f"[audio server]Audio receiving error (initial setup or loop): {e}", flush=True)
        finally:
            print("[audio server]Audio reception ended", flush=True)
            if self.output_stream:
                try:
                    if self.output_stream.is_active():
                        self.output_stream.stop_stream()
                    self.output_stream.close()
                    self.output_stream = None # Clear reference
                    print("[audio server] Output stream closed.", flush=True)
                except Exception as e:
                    print(f"[audio server] Error closing output stream: {e}", flush=True)

    def _recv_exactly(self, client, size):
        """Helper to receive exact number of bytes"""
        # Note: The timeout is now set by the calling function (receive_audio)
        data = bytearray()
        while len(data) < size:
            try:
                # We expect the socket to be in blocking mode or have a timeout set externally
                packet = client.recv(min(size - len(data), 4096))
                if not packet:
                    # Connection closed by peer
                    return None
                data.extend(packet)
            except socket.timeout:
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