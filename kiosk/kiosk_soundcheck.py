# kiosk_soundcheck.py
import time
import threading
import io
import base64
import pyaudio
import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton, QApplication,
                             QSizePolicy, QFrame, QSpacerItem, QHBoxLayout)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QThread
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

RECORD_SECONDS = 5
CHUNK = 1024
FORMAT = pyaudio.paInt16 # Using INT16 for broader compatibility
CHANNELS = 1
RATE = 44100

# --- Recorder Thread ---
class RecorderThread(QThread):
    recording_complete = pyqtSignal(bytes)
    recording_error = pyqtSignal(str)

    def __init__(self, duration):
        super().__init__()
        self.duration = duration
        self._is_running = True

    def run(self):
        print("[Kiosk Soundcheck] RecorderThread started")
        audio = pyaudio.PyAudio()
        stream = None
        frames = []
        try:
            stream = audio.open(format=FORMAT,
                                channels=CHANNELS,
                                rate=RATE,
                                input=True,
                                frames_per_buffer=CHUNK)
            print("[Kiosk Soundcheck] Audio stream opened for recording.")

            for _ in range(0, int(RATE / CHUNK * self.duration)):
                if not self._is_running:
                    print("[Kiosk Soundcheck] Recording cancelled.")
                    break
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    frames.append(data)
                except IOError as e:
                    if e.errno == pyaudio.paInputOverflowed:
                        print("[Kiosk Soundcheck] Input overflowed, continuing...")
                        continue # Ignore overflow errors if possible
                    else:
                        raise # Reraise other IOErrors

            print("[Kiosk Soundcheck] Recording finished.")

        except Exception as e:
            error_msg = f"Recording failed: {e}"
            print(f"[Kiosk Soundcheck] {error_msg}")
            self.recording_error.emit(error_msg)
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                    print("[Kiosk Soundcheck] Recording stream closed.")
                except Exception as e:
                     print(f"[Kiosk Soundcheck] Error closing recording stream: {e}")
            audio.terminate()
            print("[Kiosk Soundcheck] PyAudio terminated in recorder thread.")

        if self._is_running and frames: # Only emit if not cancelled and data exists
            audio_data = b''.join(frames)
            self.recording_complete.emit(audio_data)
        elif not frames:
             self.recording_error.emit("No audio data recorded.")


    def stop(self):
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
        self.audio_file_path = os.path.join("kiosk_sounds", "hint_received.mp3")

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
            }
            QPushButton:hover {
                background-color: #45a049;
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

        # --- Button Frame ---
        self.button_frame = QFrame(self)
        self.button_layout = QVBoxLayout(self.button_frame)
        self.button_layout.setAlignment(Qt.AlignCenter)
        self.button_layout.setSpacing(15)
        self.layout.addWidget(self.button_frame)

        # Buttons (will be added/removed dynamically)
        self.touch_button = QPushButton("Touch Here", self.button_frame)
        self.yes_button = QPushButton("Yes", self.button_frame)
        self.no_button = QPushButton("No", self.button_frame)
        self.replay_button = QPushButton("Replay Sound", self.button_frame)
        self.record_button = QPushButton("Start Recording", self.button_frame)

        # Set object names for specific styling/identification
        self.replay_button.setObjectName("replayButton")
        self.no_button.setObjectName("noButton")

        # Connect signals
        self.touch_button.clicked.connect(self.handle_touch)
        self.yes_button.clicked.connect(lambda: self.handle_audio_confirm(True))
        self.no_button.clicked.connect(lambda: self.handle_audio_confirm(False))
        self.replay_button.clicked.connect(self.handle_replay)
        self.record_button.clicked.connect(self.handle_start_recording)

        # Initially hide all buttons
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
        self._update_ui()
        self.show()
        self.raise_()

    def _update_ui(self):
        print(f"[Kiosk Soundcheck] Updating UI for state: {self.state}")
        # Clear button frame first
        while self.button_layout.count():
            child = self.button_layout.takeAt(0)
            if child.widget():
                child.widget().hide() # Hide before removing

        # Configure based on state
        if self.state == STATE_WAITING_TOUCH:
            self.message_label.setText("Soundcheck requested.\n\nTouch the button below to test audio.")
            self.button_layout.addWidget(self.touch_button)
            self.touch_button.show()
        elif self.state == STATE_WAITING_AUDIO_CONFIRM:
            self.message_label.setText("Did you hear the sound play?")
            # Add buttons horizontally for Yes/No/Replay
            h_layout = QHBoxLayout()
            h_layout.addStretch(1)
            h_layout.addWidget(self.yes_button)
            h_layout.addWidget(self.no_button)
            h_layout.addWidget(self.replay_button)
            h_layout.addStretch(1)
            self.button_layout.addLayout(h_layout)
            self.yes_button.show()
            self.no_button.show()
            self.replay_button.show()
        elif self.state == STATE_WAITING_MIC_START:
             self.message_label.setText("Prepare to record a short audio sample.\n\nPress 'Start Recording' and speak clearly.")
             self.button_layout.addWidget(self.record_button)
             self.record_button.setText("Start Recording")
             self.record_button.setEnabled(True)
             self.record_button.show()
        elif self.state == STATE_RECORDING:
             self.message_label.setText(f"Recording audio for {RECORD_SECONDS} seconds...\nSpeak now!")
             self.record_button.setText("Recording...")
             self.record_button.setEnabled(False) # Disable while recording
             self.record_button.show() # Keep it visible but disabled
        elif self.state == STATE_SENDING:
             self.message_label.setText("Sending audio sample to admin...")
             # No buttons needed here
        elif self.state == STATE_COMPLETE:
             self.message_label.setText("Soundcheck step complete.\nWaiting for admin to finish.")
             # No buttons needed, wait for cancel command
        elif self.state == STATE_CANCELED:
             self.message_label.setText("Soundcheck cancelled by admin.")
             # Optionally add an OK button to close manually after a delay
             QTimer.singleShot(3000, self.close_widget) # Auto-close after 3s

    def send_status(self, test_type, result, audio_data_b64=None):
        """Sends status update back to the admin."""
        print(f"[Kiosk Soundcheck] Sending status: Test={test_type}, Result={result}")
        status_data = {
            'type': 'soundcheck_status',
            'computer_name': self.kiosk_app.computer_name,
            'test_type': test_type,
            'result': result,
        }
        if audio_data_b64:
            status_data['audio_data'] = audio_data_b64

        self.kiosk_app.network.send_message(status_data)

    def play_test_sound(self):
        """Plays the designated test sound."""
        print(f"[Kiosk Soundcheck] Playing test sound: {self.audio_file_path}")
        if not os.path.exists(self.audio_file_path):
            print(f"[Kiosk Soundcheck] Error: Test sound file not found at {self.audio_file_path}")
            self.message_label.setText("Error: Test sound file missing.\nPlease inform admin.")
            self.state = STATE_IDLE # Reset state? Or mark as failed?
            QTimer.singleShot(3000, self.close_widget)
            return False

        try:
            # Use the main app's audio manager to play the sound
            self.kiosk_app.audio_manager.play_sound("hint_notification")
            return True
        except Exception as e:
            print(f"[Kiosk Soundcheck] Error playing sound: {e}")
            self.message_label.setText("Error playing audio.\nPlease inform admin.")
            # Consider sending a fail status?
            return False

    # --- Event Handlers ---
    def handle_touch(self):
        if self.state != STATE_WAITING_TOUCH: return
        print("[Kiosk Soundcheck] Touch detected.")
        self.send_status('touch', True)
        if self.play_test_sound():
            self.state = STATE_WAITING_AUDIO_CONFIRM
            self._update_ui()
        else:
            # Failed to play sound, maybe send fail status for audio?
            self.send_status('audio', False)
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
        self.state = STATE_RECORDING
        self._update_ui()

        # Start recorder thread
        self.recorder_thread = RecorderThread(RECORD_SECONDS)
        self.recorder_thread.recording_complete.connect(self.on_recording_complete)
        self.recorder_thread.recording_error.connect(self.on_recording_error)
        self.recorder_thread.start()

    def on_recording_complete(self, audio_data):
        print("[Kiosk Soundcheck] Recording complete signal received.")
        if self.state != STATE_RECORDING:
            print("[Kiosk Soundcheck] Warning: Recording completed but state is not RECORDING.")
            return # Avoid sending if state changed (e.g., cancelled)

        self.state = STATE_SENDING
        self._update_ui()

        try:
            encoded_data = base64.b64encode(audio_data).decode('utf-8')
            print("[Kiosk Soundcheck] Audio encoded to Base64.")
            self.send_status('audio_sample', True, encoded_data) # Send sample data
            # Note: We don't send mic=True yet, admin decides based on listening
            self.state = STATE_COMPLETE
            self._update_ui()
        except Exception as e:
            print(f"[Kiosk Soundcheck] Error encoding/sending audio sample: {e}")
            self.send_status('mic', False) # Send mic fail if encoding fails
            self.state = STATE_COMPLETE # Still go to complete state
            self._update_ui()

    def on_recording_error(self, error_message):
        print(f"[Kiosk Soundcheck] Recording error signal received: {error_message}")
        if self.state != STATE_RECORDING: return # Avoid acting if state changed

        self.state = STATE_WAITING_MIC_START # Go back to allow retry? Or mark fail?
        self.message_label.setText(f"Recording Error:\n{error_message}\n\nTry again?")
        # Enable record button again
        self.button_layout.addWidget(self.record_button)
        self.record_button.setText("Start Recording")
        self.record_button.setEnabled(True)
        self.record_button.show()

        self.send_status('mic', False) # Report mic failure

    def cancel_soundcheck(self):
        print("[Kiosk Soundcheck] Cancel command received.")
        self.state = STATE_CANCELED
        if self.recorder_thread and self.recorder_thread.isRunning():
            print("[Kiosk Soundcheck] Stopping recorder thread...")
            self.recorder_thread.stop()
            # self.recorder_thread.wait() # Don't wait here, let it finish naturally or be killed
        self._update_ui()
        # Widget will close automatically after delay in _update_ui for CANCELED state

    def close_widget(self):
        print("[Kiosk Soundcheck] Closing widget.")
        self.state = STATE_IDLE
        self.hide()
        self.deleteLater() # Clean up the widget
        self.finished.emit() # Emit signal

    def closeEvent(self, event):
        """Ensure cleanup on manual close if ever implemented."""
        self.cancel_soundcheck()
        super().closeEvent(event)

#=================================================
# Modifications in other kiosk files
#=================================================

# --- In message_handler.py ---
# Add import at the top:
# from kiosk_soundcheck import KioskSoundcheckWidget # Assuming it's in the same directory or sys.path is set

# In __init__:
# self.soundcheck_widget = None

# In handle_message, add new elif blocks:
#             elif msg_type == 'soundcheck_command' and is_targeted:
#                 print(f"[Message Handler] Received soundcheck command (ID: {command_id})")
#                 # Ensure any previous soundcheck is closed first
#                 if self.soundcheck_widget:
#                     self.soundcheck_widget.cancel_soundcheck() # Attempt graceful cancel
#                     # Wait a moment or ensure widget is deleted before creating new one
#                     # This might need a more robust mechanism if cancel is slow
#
#                 # Use QTimer to defer creation slightly to ensure previous cleanup finishes
#                 def deferred_start():
#                     try:
#                         # Parent the widget to the main application's content widget
#                         from qt_main import QtKioskApp
#                         parent_widget = QtKioskApp.instance.content_widget if QtKioskApp.instance else None
#                         if not parent_widget:
#                              print("[Message Handler] Error: Cannot find parent widget for soundcheck.")
#                              # Maybe fall back to creating it without a parent?
#                              parent_widget = None # Or handle error appropriately
#
#                         self.soundcheck_widget = KioskSoundcheckWidget(self.kiosk_app, parent_widget)
#                         self.soundcheck_widget.finished.connect(self._on_soundcheck_finished)
#                         self.soundcheck_widget.start_soundcheck()
#                     except Exception as e:
#                         print(f"[Message Handler] Error creating soundcheck widget: {e}")
#                         traceback.print_exc()
#
#                 QTimer.singleShot(100, deferred_start) # 100ms delay
#
#             elif msg_type == 'soundcheck_cancel' and is_targeted:
#                 print(f"[Message Handler] Received soundcheck cancel command (ID: {command_id})")
#                 if self.soundcheck_widget:
#                     # Use invokeMethod to ensure cancel runs on the main thread
#                     QMetaObject.invokeMethod(self.soundcheck_widget, "cancel_soundcheck", Qt.QueuedConnection)
#                 else:
#                     print("[Message Handler] Received cancel but no soundcheck widget found.")

# Add a new method to handle the finished signal:
#     def _on_soundcheck_finished(self):
#         print("[Message Handler] Soundcheck widget reported finished.")
#         self.soundcheck_widget = None # Clear the reference


# --- In audio_manager.py (if it exists, or main KioskApp) ---
# Need a method to play a sound file reliably, e.g.:
# def play_sound_file(self, file_path):
#     if not self.mixer_initialized:
#         print("[Audio Manager] Mixer not initialized, cannot play sound.")
#         return
#     try:
#         sound = pygame.mixer.Sound(file_path)
#         sound.play()
#         print(f"[Audio Manager] Playing sound: {file_path}")
#     except Exception as e:
#         print(f"[Audio Manager] Error playing sound file {file_path}: {e}")

# If AudioManager doesn't exist, add similar logic to KioskApp.

# --- In kiosk.py ---
# In __init__, initialize the soundcheck member:
# self.soundcheck_widget = None # Moved this to MessageHandler where it's used

# In on_closing:
#         # Cancel soundcheck if active
#         try:
#             if hasattr(self, 'message_handler') and self.message_handler.soundcheck_widget:
#                 print("[Kiosk Main] Closing active soundcheck window...")
#                 # Ensure cancel runs on main thread
#                 QMetaObject.invokeMethod(self.message_handler.soundcheck_widget, "cancel_soundcheck", Qt.QueuedConnection)
#         except Exception as e:
#             print(f"[Kiosk Main] Error cancelling soundcheck on close: {e}")
#             # Log exception if logger is available

# --- In qt_overlay.py ---
# Ensure Overlay.hide_all_overlays() is comprehensive enough or modify it if the soundcheck
# widget should also be hidden when other overlays are hidden (probably not desirable).
# The soundcheck widget manages its own visibility.