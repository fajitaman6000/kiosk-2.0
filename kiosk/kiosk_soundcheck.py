# kiosk_soundcheck.py
import time
import threading
import io
import base64
import pyaudio
import os
import pygame # Import pygame directly for sound playback here
import traceback # Ensure traceback is imported
import wave # <<< ADDED
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QApplication,
                             QSizePolicy, QFrame, QSpacerItem, QHBoxLayout)
# --- MODIFIED IMPORT ---
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread, pyqtSlot
# --- END MODIFIED IMPORT ---
from PyQt5.QtGui import QFont

# --- Constants ---
STATE_IDLE = 0
STATE_WAITING_TOUCH = 1
STATE_WAITING_AUDIO_CONFIRM = 2
STATE_WAITING_MIC_START = 3
STATE_RECORDING = 4
STATE_SENDING = 5
STATE_COMPLETE = 6
STATE_CANCELED = 7

# --- Audio Parameters ---
RECORD_SECONDS = 2  # Reduced recording duration
CHUNK = 1024
# --- IMPROVED AUDIO FORMAT PARAMETERS ---
FORMAT = pyaudio.paInt16  # Use 16-bit signed integer format (better quality than 8-bit)
CHANNELS = 1  # Mono recording (saves space compared to stereo)
RATE = 11025  # 11kHz sample rate (better balance between quality and file size)
# --- END IMPROVED AUDIO FORMAT PARAMETERS ---

# --- Recorder Thread ---
class RecorderThread(QThread):
    recording_complete = pyqtSignal(bytes)
    recording_error = pyqtSignal(str)

    def __init__(self, duration):
        super().__init__()
        self.duration = duration
        self._is_running = True
        self._lock = threading.Lock()  # Add thread safety

    def run(self):
        print("[Kiosk Soundcheck] RecorderThread started")
        audio = pyaudio.PyAudio()
        stream = None
        frames = []
        try:
            # Add a check for available input devices
            input_device_index = None
            default_input_device_info = audio.get_default_input_device_info()
            input_device_index = default_input_device_info['index']
            print(f"[Kiosk Soundcheck] Using default input device: {default_input_device_info['name']} (Index {input_device_index})")
            # Fallback scan if default fails (less common now)
            # info = audio.get_host_api_info_by_index(0)
            # numdevices = info.get('deviceCount')
            # for i in range(0, numdevices):
            #     dev_info = audio.get_device_info_by_host_api_device_index(0, i)
            #     if (dev_info.get('maxInputChannels')) > 0:
            #         print(f"[Kiosk Soundcheck] Found input device: {dev_info.get('name')} (Index {i})")
            #         input_device_index = i # Use the first available input device
            #         # break # Option: break here, or let it find the last one

            if input_device_index is None:
                 raise IOError("No suitable input audio device found.")

            print(f"[Kiosk Soundcheck] Opening audio stream with device index {input_device_index}")
            stream = audio.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK,
                                input_device_index=input_device_index) # Specify device
            print("[Kiosk Soundcheck] Audio stream opened for recording.")

            for i in range(0, int(RATE / CHUNK * self.duration)):
                with self._lock:
                    if not self._is_running:
                        print("[Kiosk Soundcheck] Recording cancelled.")
                        break
                try:
                    # Increase buffer read timeout slightly if needed, but usually default is fine
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    # print(f"[Kiosk Soundcheck] Read {len(data)} bytes (Loop {i+1})") # Debug: uncomment if needed
                    frames.append(data)
                except IOError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        print("[Kiosk Soundcheck] Input overflowed, continuing...")
                        continue # Ignore overflow errors if possible
                    else:
                        print(f"[Kiosk Soundcheck] Recording IOError: {e} (errno={e.errno})")
                        # Optionally add a small sleep if overflow is persistent
                        # time.sleep(0.01)
                        # raise # Reraise other IOErrors
                        self.recording_error.emit(f"IOError during recording: {e}")
                        with self._lock:
                            self._is_running = False  # Stop recording on significant IO error
                        break

            print("[Kiosk Soundcheck] Recording finished loop.")

        except Exception as e:
            error_msg = f"Recording failed: {e}"
            print(f"[Kiosk Soundcheck] {error_msg}")
            traceback.print_exc() # Print full traceback for debugging
            self.recording_error.emit(error_msg)
            with self._lock:
                self._is_running = False # Ensure flag is set
        finally:
            if stream:
                try:
                    if stream.is_active():
                       stream.stop_stream()
                       print("[Kiosk Soundcheck] Recording stream stopped.")
                    stream.close()
                    print("[Kiosk Soundcheck] Recording stream closed.")
                except Exception as e:
                     print(f"[Kiosk Soundcheck] Error closing recording stream: {e}")
            if audio: # Ensure PyAudio terminates only if initialized
                try:
                    audio.terminate()
                    print("[Kiosk Soundcheck] PyAudio terminated in recorder thread.")
                except Exception as e:
                    print(f"[Kiosk Soundcheck] Error terminating PyAudio: {e}")

        # Process the recording result
        with self._lock:
            is_running = self._is_running
        
        if is_running and frames: # Only emit if not cancelled and data exists
            # Create a proper WAV file in memory
            try:
                wave_buffer = io.BytesIO()
                sample_width = pyaudio.get_sample_size(FORMAT)  # Should be 2 for paInt16
                
                with wave.open(wave_buffer, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(sample_width)
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))
                
                # Get the complete WAV data
                wave_data = wave_buffer.getvalue()
                print(f"[Kiosk Soundcheck] Created WAV file in memory: {len(wave_data)} bytes")
                self.recording_complete.emit(wave_data)
            except Exception as e:
                print(f"[Kiosk Soundcheck] Error creating WAV file: {e}")
                self.recording_error.emit(f"Error creating WAV file: {e}")
        elif is_running and not frames:
             print("[Kiosk Soundcheck] No audio data recorded, emitting error.")
             self.recording_error.emit("No audio data recorded (frames list is empty).")
        else:
            print("[Kiosk Soundcheck] Recording was stopped or failed, not emitting complete signal.")

    def stop(self):
        print("[Kiosk Soundcheck] Stop called on RecorderThread.")
        with self._lock:
            self._is_running = False

# --- Soundcheck Widget ---
class KioskSoundcheckWidget(QWidget):
    # Signal to indicate completion or cancellation
    finished = pyqtSignal()

    def __init__(self, kiosk_app, parent_widget):
        super().__init__(parent_widget) # Parent to the main content widget
        self.kiosk_app = kiosk_app
        self.state = STATE_IDLE
        self.recorder_thread = None
        # Use the specific sound file path directly
        self.audio_file_path = os.path.join("kiosk_sounds", "hint_received.mp3")
        self._sound_object = None # To hold the loaded pygame sound

        # Ensure pygame mixer is initialized (might be redundant if main app does it)
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init(frequency=RATE, channels=CHANNELS) # Init with parameters matching recording
                print("[Kiosk Soundcheck] Pygame mixer initialized.")
            except Exception as e:
                print(f"[Kiosk Soundcheck] Pygame mixer init error: {e}")
                # Handle error - perhaps disable audio test?

        self._init_ui()
        self.hide() # Initially hidden

    def _init_ui(self):
        self.setWindowTitle("Soundcheck")
        # Make it cover a good portion, centered, but not full screen initially
        parent_size = self.parent().size() if self.parent() else QApplication.primaryScreen().size()
        width = 600
        height = 400
        x = (parent_size.width() - width) // 2
        y = (parent_size.height() - height) // 2
        self.setGeometry(x, y, width, height)

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setStyleSheet("""
            KioskSoundcheckWidget {
                background-color: rgba(0, 0, 0, 190);
                border: 2px solid white;
                border-radius: 15px;
            }
            QLabel {
                color: white;
                font-size: 28px;
                alignment: 'AlignCenter';
            }
            QPushButton {
                background-color: #4CAF50; /* Green */
                border: none;
                color: white;
                padding: 15px 32px;
                text-align: center;
                text-decoration: none;
                font-size: 20px;
                margin: 4px 2px;
                border-radius: 8px;
                min-height: 50px; /* Ensure buttons have a decent height */
            }
            QPushButton:hover {
                background-color: #45a049;
            }
             QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
            QPushButton#replayButton {
                background-color: #008CBA; /* Blue */
            }
            QPushButton#replayButton:hover {
                background-color: #007ba7;
            }
             QPushButton#noButton {
                background-color: #f44336; /* Red */
            }
            QPushButton#noButton:hover {
                background-color: #da190b;
            }
        """)

        self.layout = QVBoxLayout(self)
        self.layout.setAlignment(Qt.AlignCenter)
        self.layout.setContentsMargins(30, 30, 30, 30)
        self.layout.setSpacing(20)

        self.message_label = QLabel("", self)
        self.message_label.setWordWrap(True)
        self.message_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.message_label)

        # --- Button Container Frame ---
        # This frame will hold the different button layouts
        self.button_container = QFrame(self)
        self.button_container.setObjectName("buttonContainer")
        self.button_container_layout = QVBoxLayout(self.button_container)
        self.button_container_layout.setAlignment(Qt.AlignCenter)
        self.button_container_layout.setContentsMargins(0,0,0,0)
        self.button_container_layout.setSpacing(15)
        self.layout.addWidget(self.button_container)

        # Buttons (created once, shown/hidden as needed)
        self.touch_button = QPushButton("Touch Here", self)
        self.yes_button = QPushButton("Yes", self)
        self.no_button = QPushButton("No", self)
        self.replay_button = QPushButton("Replay Sound", self)
        self.record_button = QPushButton("Start Recording", self)

        # Set object names for specific styling/identification
        self.replay_button.setObjectName("replayButton")
        self.no_button.setObjectName("noButton")

        # Connect signals
        self.touch_button.clicked.connect(self.handle_touch)
        self.yes_button.clicked.connect(lambda: self.handle_audio_confirm(True))
        self.no_button.clicked.connect(lambda: self.handle_audio_confirm(False))
        self.replay_button.clicked.connect(self.handle_replay)
        self.record_button.clicked.connect(self.handle_start_recording)

        # Initially hide all buttons (they will be added to layout in _update_ui)
        self.touch_button.hide()
        self.yes_button.hide()
        self.no_button.hide()
        self.replay_button.hide()
        self.record_button.hide()

    def start_soundcheck(self):
        print("[Kiosk Soundcheck] Starting soundcheck process.")
        if self.state != STATE_IDLE and self.state != STATE_CANCELED and self.state != STATE_COMPLETE:
            print("[Kiosk Soundcheck] Soundcheck already in progress.")
            return
        self.state = STATE_WAITING_TOUCH

        # Preload the sound
        self._load_sound()

        self._update_ui()
        self.show()
        self.raise_()

    def _clear_buttons(self):
        """Helper to remove all widgets from the button container layout."""
        # print("[Kiosk Soundcheck] Clearing buttons...")
        while self.button_container_layout.count():
            item = self.button_container_layout.takeAt(0)
            widget = item.widget()
            if widget:
                # print(f"[Kiosk Soundcheck] Removing and deleting widget: {widget.objectName()}")
                widget.hide()
                widget.setParent(None) # Remove from layout management
                widget.deleteLater()   # Schedule deletion
            else:
                # If it's a layout, clear it recursively
                layout = item.layout()
                if layout:
                    # print("[Kiosk Soundcheck] Removing and deleting layout...")
                    while layout.count():
                        sub_item = layout.takeAt(0)
                        sub_widget = sub_item.widget()
                        if sub_widget:
                            sub_widget.hide()
                            sub_widget.setParent(None)
                            sub_widget.deleteLater()
                    # Request deletion of the layout itself
                    layout.deleteLater()


    def _update_ui(self):
        print(f"[Kiosk Soundcheck] Updating UI for state: {self.state}")
        # Clear previous buttons more robustly
        self._clear_buttons()

        # Re-create buttons needed for the current state and add them
        if self.state == STATE_WAITING_TOUCH:
            self.message_label.setText("Soundcheck requested.\n\nTouch the button below to test audio.")
            self.touch_button = QPushButton("Touch Here", self) # Recreate
            self.touch_button.clicked.connect(self.handle_touch)
            self.button_container_layout.addWidget(self.touch_button)
            self.touch_button.show()
        elif self.state == STATE_WAITING_AUDIO_CONFIRM:
            self.message_label.setText("Did you hear the sound play?")
            # Recreate buttons
            self.yes_button = QPushButton("Yes", self)
            self.no_button = QPushButton("No", self)
            self.replay_button = QPushButton("Replay Sound", self)
            self.yes_button.clicked.connect(lambda: self.handle_audio_confirm(True))
            self.no_button.clicked.connect(lambda: self.handle_audio_confirm(False))
            self.replay_button.clicked.connect(self.handle_replay)
            self.replay_button.setObjectName("replayButton")
            self.no_button.setObjectName("noButton")

            # Add buttons horizontally
            h_layout = QHBoxLayout() # Create new layout
            h_layout.addStretch(1)
            h_layout.addWidget(self.yes_button)
            h_layout.addWidget(self.no_button)
            h_layout.addWidget(self.replay_button)
            h_layout.addStretch(1)
            self.button_container_layout.addLayout(h_layout) # Add layout to container
            self.yes_button.show()
            self.no_button.show()
            self.replay_button.show()
        elif self.state == STATE_WAITING_MIC_START:
             self.message_label.setText("Prepare to record a short audio sample.\n\nPress 'Start Recording' and speak clearly.")
             self.record_button = QPushButton("Start Recording", self) # Recreate
             self.record_button.clicked.connect(self.handle_start_recording)
             self.record_button.setEnabled(True)
             self.button_container_layout.addWidget(self.record_button)
             self.record_button.show()
        elif self.state == STATE_RECORDING:
             self.message_label.setText(f"Recording audio for {RECORD_SECONDS} seconds...\nSpeak now!")
             # Keep the button visible but disabled
             self.record_button = QPushButton("Recording...", self) # Recreate as disabled text
             self.record_button.setEnabled(False)
             self.button_container_layout.addWidget(self.record_button)
             self.record_button.show()
        elif self.state == STATE_SENDING:
             self.message_label.setText("Sending audio sample to admin...")
             # No buttons needed here
        elif self.state == STATE_COMPLETE:
             self.message_label.setText("Soundcheck step complete.\nResults uploaded to admin.")
             # No buttons needed, wait for cancel command
        elif self.state == STATE_CANCELED:
             self.message_label.setText("Soundcheck cancelled by admin.")
             # Auto-close after 3s
             QTimer.singleShot(3000, self.close_widget)

    def send_status(self, test_type, result, audio_data_b64=None):
        """Sends status update back to the admin."""
        print(f"[Kiosk Soundcheck] Sending status: Test={test_type}, Result={result}")
        status_data = {
            'type': 'soundcheck_status',
            'computer_name': self.kiosk_app.computer_name,
            'test_type': test_type,
            'result': result,
        }
        # Estimate size before adding audio data
        base_size = len(str(status_data)) # Rough estimate
        if audio_data_b64:
            print(f"[Kiosk Soundcheck] Encoded audio data size: {len(audio_data_b64)} bytes")
            if base_size + len(audio_data_b64) > 128000: # Increased limit for larger UDP packets
                 print("[Kiosk Soundcheck] WARNING: Audio data too large, sending mic fail status instead.")
                 # Send mic fail explicitly instead of the large data
                 # Create a separate dictionary for the mic fail status
                 mic_fail_status = {
                     'type': 'soundcheck_status',
                     'computer_name': self.kiosk_app.computer_name,
                     'test_type': 'mic', # Explicitly 'mic'
                     'result': False,
                 }
                 self.kiosk_app.network.send_message(mic_fail_status)
                 
                 # Close the widget immediately after sending the mic fail status
                 print("[Kiosk Soundcheck] Mic fail status sent due to large audio data, closing widget.")
                 QTimer.singleShot(0, self.close_widget)
                 return # Don't send the message with oversized audio
            else:
                status_data['audio_data'] = audio_data_b64

        # Send the message (potentially without audio data if it was too large)
        self.kiosk_app.network.send_message(status_data)

    def _load_sound(self):
        """Loads the sound file into a pygame Sound object."""
        if not self._sound_object:
            if not os.path.exists(self.audio_file_path):
                print(f"[Kiosk Soundcheck] Error: Test sound file not found at {self.audio_file_path}")
                self.message_label.setText("Error: Test sound file missing.\nPlease inform admin.")
                # Consider sending fail status immediately?
                self.send_status('audio', False)
                return False
            try:
                print(f"[Kiosk Soundcheck] Loading sound file: {self.audio_file_path}")
                self._sound_object = pygame.mixer.Sound(self.audio_file_path)
                print("[Kiosk Soundcheck] Sound file loaded successfully.")
                return True
            except Exception as e:
                print(f"[Kiosk Soundcheck] Error loading sound file: {e}")
                self.message_label.setText("Error loading test sound.\nPlease inform admin.")
                self.send_status('audio', False)
                self._sound_object = None
                return False
        return True # Already loaded

    def play_test_sound(self):
        """Plays the designated test sound using pygame."""
        print(f"[Kiosk Soundcheck] Attempting to play test sound...")
        if not pygame.mixer.get_init():
            print("[Kiosk Soundcheck] Error: Pygame mixer not initialized.")
            self.message_label.setText("Audio system error (mixer).\nPlease inform admin.")
            return False

        if not self._sound_object:
             print("[Kiosk Soundcheck] Error: Sound object not loaded.")
             # Attempt to load it again
             if not self._load_sound():
                 # Loading failed, error message already set
                 return False

        try:
            # Stop any previous instance of this sound, just in case
            self._sound_object.stop()
            # Play the sound
            self._sound_object.play()
            print(f"[Kiosk Soundcheck] Playing sound: {self.audio_file_path}")
            return True
        except Exception as e:
            print(f"[Kiosk Soundcheck] Error playing sound: {e}")
            self.message_label.setText("Error playing audio.\nPlease inform admin.")
            # Send fail status immediately on playback error
            self.send_status('audio', False)
            return False

    # --- Event Handlers ---
    def handle_touch(self):
        if self.state != STATE_WAITING_TOUCH: return
        print("[Kiosk Soundcheck] Touch detected.")
        self.send_status('touch', True)
        if self.play_test_sound():
            self.state = STATE_WAITING_AUDIO_CONFIRM
        else:
            # Failed to play sound, status already sent by play_test_sound
            print("[Kiosk Soundcheck] Sound playback failed, skipping to mic test.")
            self.state = STATE_WAITING_MIC_START # Skip to mic test
        self._update_ui()


    def handle_audio_confirm(self, heard_sound):
        if self.state != STATE_WAITING_AUDIO_CONFIRM: return
        print(f"[Kiosk Soundcheck] Audio confirmation: Heard={heard_sound}")
        self.send_status('audio', heard_sound)
        self.state = STATE_WAITING_MIC_START
        self._update_ui()

    def handle_replay(self):
        if self.state != STATE_WAITING_AUDIO_CONFIRM: return
        print("[Kiosk Soundcheck] Replaying sound.")
        self.play_test_sound()
        # Stay in the same state

    def handle_start_recording(self):
        if self.state != STATE_WAITING_MIC_START: return
        print("[Kiosk Soundcheck] Start recording pressed.")

        # --- Permissions Check Placeholder (Concept) ---
        # On some systems, you might need to explicitly check/request mic permissions.
        # This is complex and OS-dependent, often involving external libraries or system calls.
        # For now, we assume permissions are granted or handle errors during stream opening.
        # print("[Kiosk Soundcheck] Note: Assuming microphone permissions are granted.")
        # ---

        self.state = STATE_RECORDING
        self._update_ui()

        # Stop any lingering sound playback
        if self._sound_object:
            self._sound_object.stop()

        # Start recorder thread
        print("[Kiosk Soundcheck] Creating and starting RecorderThread.")
        self.recorder_thread = RecorderThread(RECORD_SECONDS)
        self.recorder_thread.recording_complete.connect(self.on_recording_complete)
        self.recorder_thread.recording_error.connect(self.on_recording_error)
        # Ensure thread cleanup when finished
        self.recorder_thread.finished.connect(self.recorder_thread.deleteLater)
        self.recorder_thread.start()

    # @pyqtSlot(bytes)
    def on_recording_complete(self, audio_data):
        print(f"[Kiosk Soundcheck] Recording complete signal received with {len(audio_data)} bytes.")
        if self.state != STATE_RECORDING:
            print("[Kiosk Soundcheck] Warning: Recording completed but state is not RECORDING.")
            # Clean up thread reference if it exists
            if self.recorder_thread:
                self.recorder_thread = None
            return # Avoid sending if state changed (e.g., cancelled)

        active_thread = self.recorder_thread # Keep ref for cleanup
        self.recorder_thread = None # Clear instance variable now

        self.state = STATE_SENDING
        self._update_ui()

        try:
            # Ensure audio_data is bytes and not empty
            if not isinstance(audio_data, bytes):
                print("[Kiosk Soundcheck] Error: Recorded data is not bytes.")
                raise TypeError("Recorded data is not bytes")

            if not audio_data:
                print("[Kiosk Soundcheck] Error: Recorded data is empty.")
                raise ValueError("Recorded data is empty")

            # We already have a complete WAV file in audio_data
            print(f"[Kiosk Soundcheck] Processing WAV file of {len(audio_data)} bytes.")
            
            # Encode the WAV data to Base64
            encoded_data = base64.b64encode(audio_data).decode('utf-8')
            print(f"[Kiosk Soundcheck] Audio encoded to Base64: {len(encoded_data)} bytes")

            # send_status checks size internally now before adding 'audio_data'
            self.send_status('audio_sample', True, encoded_data)
            
            # Close the widget immediately after sending the audio sample
            print("[Kiosk Soundcheck] Audio sample sent, closing widget.")
            QTimer.singleShot(0, self.close_widget)

        except Exception as e:
            print(f"[Kiosk Soundcheck] Error processing/encoding/sending audio sample: {e}")
            import traceback
            traceback.print_exc()
            self.send_status('mic', False) # Send mic fail if processing/encoding fails
            # Close the widget even on error
            QTimer.singleShot(0, self.close_widget)
        finally:
             # Thread cleanup is handled by the finished signal connection
             pass


    # Make slot connection explicit if needed
    # @pyqtSlot(str)
    def on_recording_error(self, error_message):
        print(f"[Kiosk Soundcheck] Recording error signal received: {error_message}")
        active_thread = self.recorder_thread # Keep ref for cleanup
        self.recorder_thread = None # Clear instance variable now

        # Make sure we are on the main thread before updating UI
        # Use QTimer.singleShot which guarantees execution on the event loop's thread
        QTimer.singleShot(0, lambda: self._handle_recording_error_ui(error_message))


    def _handle_recording_error_ui(self, error_message):
        """Handles UI updates for recording errors on the main thread."""
        print("[Kiosk Soundcheck] Handling recording error UI update.")
        if self.state != STATE_RECORDING and self.state != STATE_WAITING_MIC_START:
            print(f"[Kiosk Soundcheck] Ignoring recording error UI update in state {self.state}")
            return # Avoid acting if state changed (e.g., cancelled or already moved on)

        # Mark mic test as failed
        self.send_status('mic', False)
        
        # Close the widget immediately after sending the mic fail status
        print(f"[Kiosk Soundcheck] Mic test failed due to recording error, closing widget: {error_message}")
        QTimer.singleShot(0, self.close_widget)


    # --- ADDED DECORATOR ---
    @pyqtSlot()
    # --- END ADDED DECORATOR ---
    def cancel_soundcheck(self):
        print("[Kiosk Soundcheck] Cancel command received (Slot).")

        initial_state = self.state
        self.state = STATE_CANCELED

        if self.recorder_thread and self.recorder_thread.isRunning():
            print("[Kiosk Soundcheck] Stopping recorder thread...")
            self.recorder_thread.stop()
            # Don't wait here, let it finish naturally or be killed by app exit
            self.recorder_thread = None # Clear reference

        # Stop sound playback
        if self._sound_object:
            self._sound_object.stop()

        # If the UI hasn't updated yet (e.g., still in recording state visually)
        # ensure the UI update runs, which will show "Cancelled"
        # Use QTimer to ensure it runs after current event processing
        QTimer.singleShot(0, self._update_ui)
        # Widget will close automatically after delay in _update_ui for CANCELED state

    def close_widget(self):
        print("[Kiosk Soundcheck] Closing widget.")
        # Check if already closing or closed
        if self.state == STATE_IDLE:
            return
        self.state = STATE_IDLE

        # Stop recorder thread if somehow still running
        if self.recorder_thread and self.recorder_thread.isRunning():
            print("[Kiosk Soundcheck] Forcing stop on recorder thread during close.")
            self.recorder_thread.stop()
            self.recorder_thread = None

        # Stop sound
        if self._sound_object:
            self._sound_object.stop()
            self._sound_object = None

        self.hide()
        try:
            self.finished.emit() # Emit signal *before* deleting
        except Exception as e:
             print(f"[Kiosk Soundcheck] Error emitting finished signal: {e}")
        # Use QTimer for deleteLater to avoid issues during signal emission
        QTimer.singleShot(0, self.deleteLater) # Schedule deletion

    def closeEvent(self, event):
        """Ensure cleanup on manual close if ever implemented."""
        print("[Kiosk Soundcheck] closeEvent called.")
        # Initiate cancel sequence, which will eventually call close_widget
        self.cancel_soundcheck()
        event.ignore() # Let cancel_soundcheck manage the actual close