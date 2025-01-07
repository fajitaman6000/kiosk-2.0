#!/usr/bin/env python3
# kiosk.py - PyQt5 Version
# This is the main application file that handles the kiosk interface

import sys
import os
import socket
import time
from pathlib import Path
import traceback
import pygame
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, 
                            QVBoxLayout, QLabel, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QPoint
from PyQt5.QtGui import QCursor, QPixmap, QPainter, QTransform

# Custom widget imports
from rotated_widget import RotatedWidget, RotatedLabel, RotatedButton

# These imports will be updated as their respective files are converted
from networking import KioskNetwork
from config import ROOM_CONFIG
from video_server import VideoServer
from video_manager import VideoManager
from audio_server import AudioServer
from room_persistence import RoomPersistence
from audio_manager import AudioManager
from kiosk_timer import KioskTimer

class SignalManager(QObject):
    """
    Central signal manager for the application.
    Replaces Tkinter's event system with Qt's signal/slot mechanism.
    """
    timer_update = pyqtSignal()
    help_button_update = pyqtSignal()
    room_interface_update = pyqtSignal(int)  # room number as parameter
    hint_received = pyqtSignal(object)  # Can be str or dict for text/image hints
    video_complete = pyqtSignal()
    cooldown_started = pyqtSignal()
    cooldown_complete = pyqtSignal()

class StatusFrame(QFrame):
    """
    Replaces Tkinter Canvas-based status frame.
    Handles rotated text display for status messages.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 1079)  # Match original dimensions
        self.setStyleSheet("background-color: black;")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # Status message displays
        self.pending_text = RotatedLabel(self)
        self.pending_text.setVisible(False)
        
        self.cooldown_text = RotatedLabel(self)
        self.cooldown_text.setVisible(False)
        
    def show_pending(self, text):
        """Display pending request message"""
        self.pending_text.setRotatedText(text)
        self.pending_text.setVisible(True)
        self.cooldown_text.setVisible(False)
        
    def show_cooldown(self, text):
        """Display cooldown status message"""
        self.cooldown_text.setRotatedText(text)
        self.cooldown_text.setVisible(True)
        self.pending_text.setVisible(False)
        
    def clear(self):
        """Clear all status messages"""
        self.pending_text.setVisible(False)
        self.cooldown_text.setVisible(False)

class KioskApp(QMainWindow):
    def __init__(self):
        super().__init__()
        print("\nStarting KioskApp initialization...")
        
        # Initialize signal manager
        self.signals = SignalManager()
        self.setup_connections()  # Add this line
        
        # Basic window setup
        self.computer_name = socket.gethostname()
        self.setWindowTitle(f"Kiosk: {self.computer_name}")
        
        # Configure window properties
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.showFullScreen()
        self.setCursor(Qt.BlankCursor)
        
        # State variables
        self.assigned_room = None
        self.hints_requested = 0
        self.start_time = None
        self.current_video_process = None
        self.time_exceeded_45 = False
        
        # Initialize managers
        self.audio_manager = AudioManager()
        self.video_manager = VideoManager(self)
        
        # Initialize network components
        self.network = KioskNetwork(self.computer_name, self)
        self.video_server = VideoServer()
        self.video_server.start()
        
        # Initialize timer
        self.timer = KioskTimer(self)
        
        # Create central widget and UI
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Initialize UI from ui.py
        from ui import KioskUI  # Import at top of file in practice
        self.ui = KioskUI(self.central_widget, self.computer_name, 
                         ROOM_CONFIG, self)
        self.layout.addWidget(self.ui)
        
        # Start network threads
        self.network.start_threads()
        
        # Initialize audio server
        self.audio_server = AudioServer()
        print("Starting audio server...")
        self.audio_server.start()
        
        # Load room persistence
        print("Creating RoomPersistence...")
        self.room_persistence = RoomPersistence()
        self.assigned_room = self.room_persistence.load_room_assignment()
        print(f"Loaded room assignment: {self.assigned_room}")
        
        # Setup room interface if room is assigned
        if self.assigned_room:
            QTimer.singleShot(100, lambda: self.setup_room_interface(self.assigned_room))
        
        # Connect signal handlers
        self.signals.timer_update.connect(self.update_help_button_state)
        self.signals.help_button_update.connect(self.update_help_button_state)
        self.signals.room_interface_update.connect(self.setup_room_interface)
        self.signals.hint_received.connect(self.show_hint)
        self.signals.video_complete.connect(self.handle_video_completion)

        def setup_waiting_screen(self):
            """Create the initial waiting screen"""
            # Clear any existing widgets from layout
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            
            # Create waiting message
            waiting_label = RotatedLabel(
                text=f"Waiting for room assignment...\nComputer Name: {self.computer_name}",
                color="white",
                background="black"
            )
            waiting_label.setMinimumSize(400, 100)  # Ensure visibility
            self.layout.addWidget(waiting_label, 0, Qt.AlignCenter)

    def update_help_button_state(self):
        """Check timer and update help button state"""
        current_minutes = self.timer.time_remaining / 60
        
        # Check if we've exceeded 45 minutes
        if current_minutes > 45 and not self.time_exceeded_45:
            print("Timer has exceeded 45 minutes - setting flag")
            self.time_exceeded_45 = True
        
        # Refresh help button through UI
        self.ui.create_help_button()

    def get_stats(self):
        """Get current application statistics"""
        stats = {
            'computer_name': self.computer_name,
            'room': self.assigned_room,
            'total_hints': self.hints_requested,
            'timer_time': self.timer.time_remaining,
            'timer_running': self.timer.is_running
        }
        if not hasattr(self, '_last_stats') or self._last_stats != stats:
            self._last_stats = stats.copy()
        return stats

    def setup_connections(self):
        """Set up all signal-slot connections for the application"""
        # Timer connections
        self.timer.threshold_crossed.connect(self._handle_timer_threshold)
        self.signals.timer_update.connect(self.update_help_button_state)
        
        # Help button connections
        self.signals.help_button_update.connect(self.update_help_button_state)
        
        # Room interface connections
        self.signals.room_interface_update.connect(self.setup_room_interface)
        
        # Hint system connections
        self.signals.hint_received.connect(self.show_hint)
        self.signals.cooldown_started.connect(self._handle_cooldown_start)
        self.signals.cooldown_complete.connect(self._handle_cooldown_complete)
        
        # Video system connections
        self.video_manager.video_started.connect(self._handle_video_start)
        self.video_manager.video_stopped.connect(self._handle_video_stop)
        self.video_manager.video_completed.connect(self.handle_video_completion)

    def handle_message(self, msg):
        """Handle incoming network messages"""
        print(f"\nReceived message: {msg}")
        try:
            if msg['type'] == 'room_assignment' and msg['computer_name'] == self.computer_name:
                print(f"Processing room assignment: {msg['room']}")            
                self.assigned_room = msg['room']
                print("Saving room assignment...")
                save_result = self.room_persistence.save_room_assignment(msg['room'])
                print(f"Save result: {save_result}")
                self.start_time = time.time()
                
                # Reset UI state
                self.ui.hint_cooldown = False
                self.ui.current_hint = None
                self.ui.clear_all()
                
                # Use signal to update room interface
                self.signals.room_interface_update.emit(msg['room'])
                
            elif msg['type'] == 'hint' and self.assigned_room:
                if msg.get('room') == self.assigned_room:
                    print("\nProcessing hint message:")
                    print(f"Has image flag: {msg.get('has_image')}")
                    print(f"Message keys: {msg.keys()}")
                    
                    # Prepare hint data
                    if msg.get('has_image') and 'image' in msg:
                        hint_data = {
                            'text': msg.get('text', ''),
                            'image': msg['image']
                        }
                    else:
                        hint_data = msg.get('text', '')
                    
                    # Emit signal to show hint
                    self.signals.hint_received.emit(hint_data)
                    
            elif msg['type'] == 'timer_command' and msg['computer_name'] == self.computer_name:
                print("\nProcessing timer command")
                minutes = msg.get('minutes')
                command = msg['command']
                
                # Update time_exceeded_45 flag if timer is being set above 45
                if minutes is not None:
                    minutes = float(minutes)
                    print(f"Setting timer to {minutes} minutes")
                    if minutes > 45:
                        print("New time exceeds 45 minutes - setting flag")
                        self.time_exceeded_45 = True
                
                # Start background music when timer starts
                room_names = {
                    2: "morning_after",
                    1: "casino_heist", 
                    5: "haunted_manor",
                    4: "zombie_outbreak",
                    6: "time_machine",
                    5: "atlantis_rising",
                    3: "wizard_trials"
                }

                if command == "start":
                    if self.assigned_room and isinstance(self.assigned_room, int):
                        room_name = room_names.get(self.assigned_room)
                        if room_name:
                            print(f"Timer starting - playing background music for room: {room_name}")
                            self.audio_manager.play_background_music(room_name)
                
                # Handle the timer command
                self.timer.handle_command(command, minutes)
                
                # Update help button state
                QTimer.singleShot(100, self.update_help_button_state)
                
            elif msg['type'] == 'video_command' and msg['computer_name'] == self.computer_name:
                self.play_video(msg['video_type'], msg['minutes'])

            elif msg['type'] == 'clear_hints' and msg['computer_name'] == self.computer_name:
                print("\nProcessing clear hints command")
                self.clear_hints()

            elif msg['type'] == 'play_sound' and msg['computer_name'] == self.computer_name:
                print("\nReceived play sound command")
                sound_name = msg.get('sound_name')
                if sound_name:
                    self.audio_manager.play_sound(sound_name)
                    
            elif msg['type'] == 'solution_video' and msg['computer_name'] == self.computer_name:
                print("\nReceived solution video command")
                try:
                    room_folder = msg.get('room_folder')
                    video_filename = msg.get('video_filename')
                    
                    if not room_folder or not video_filename:
                        print("Error: Missing room_folder or video_filename in message")
                        return
                        
                    video_path = os.path.join("video_solutions", room_folder, f"{video_filename}.mp4")
                    print(f"Looking for solution video at: {video_path}")
                    
                    if os.path.exists(video_path):
                        print(f"Setting up solution video interface: {video_path}")
                        
                        # Create hint-style message for video solution
                        hint_data = {
                            'text': 'Video Solution Received',
                            'video_path': video_path
                        }
                        
                        # Show hint and video interface
                        self.signals.hint_received.emit(hint_data)
                        
                    else:
                        print(f"Error: Solution video not found at {video_path}")
                        
                except Exception as e:
                    print(f"Error processing solution video command: {e}")
                    traceback.print_exc()

            elif msg['type'] == 'reset_kiosk' and msg['computer_name'] == self.computer_name:
                print("\nProcessing kiosk reset")
                self.reset_kiosk()
                
        except Exception as e:
            print("\nCritical error in handle_message:")
            print(f"Error type: {type(e)}")
            print(f"Error message: {str(e)}")
            traceback.print_exc()

    def reset_kiosk(self):
        """Reset the kiosk to its initial state"""
        # Stop all media playback
        print("Stopping all media playback...")
        self.audio_manager.stop_background_music()
        self.video_manager.stop_video()
        
        # Reset pygame mixer
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
            pygame.mixer.stop()
        
        # Reset application state
        print("Resetting application state...")
        self.time_exceeded_45 = False
        self.hints_requested = 0
        
        # Reset UI
        print("Resetting UI state...")
        self.ui.reset_state()
        
        # Restore room interface if assigned
        if self.assigned_room:
            print("Restoring room interface")
            self.signals.room_interface_update.emit(self.assigned_room)
        
        # Update help button state
        QTimer.singleShot(100, self.update_help_button_state)
        
        print("Kiosk reset complete")

    def play_video(self, video_type, minutes):
        """Play intro or game video sequence"""
        print(f"\n=== Video Playback Sequence Start ===")
        print(f"Starting play_video with type: {video_type}")
        print(f"Current room assignment: {self.assigned_room}")
        
        # Define video paths
        video_dir = Path("intro_videos")
        video_file = video_dir / f"{video_type}.mp4" if video_type != 'game' else None
        game_video = None
        
        # Get room-specific game video
        if self.assigned_room is not None and self.assigned_room in ROOM_CONFIG['backgrounds']:
            game_video_name = ROOM_CONFIG['backgrounds'][self.assigned_room].replace('.png', '.mp4')
            game_video = video_dir / game_video_name
            print(f"Found room-specific game video path: {game_video}")
            print(f"Game video exists? {game_video.exists() if game_video else False}")

        def finish_video_sequence():
            """Final callback after videos complete"""
            print("\n=== Video Sequence Completion ===")
            print(f"Setting timer to {minutes} minutes")
            self.timer.handle_command("set", minutes)
            self.timer.handle_command("start")
            
            # Start background music
            if self.assigned_room:
                print(f"Starting background music for room: {self.assigned_room}")
                self.audio_manager.play_background_music(self.assigned_room)
            
            # Reset UI state
            print("Resetting UI state...")
            self.ui.hint_cooldown = False
            self.ui.clear_all()
            
            # Restore room interface
            if self.assigned_room:
                print(f"Restoring room interface for: {self.assigned_room}")
                self.signals.room_interface_update.emit(self.assigned_room)
            
            print("=== Video Sequence Complete ===\n")

        def play_game_video():
            """Play game-specific video"""
            print("\n=== Starting Game Video Sequence ===")
            if game_video and game_video.exists():
                print(f"Starting playback of game video: {game_video}")
                self.video_manager.play_video(str(game_video), on_complete=finish_video_sequence)
            else:
                print("No valid game video found, proceeding to finish sequence")
                finish_video_sequence()
            print("=== Game Video Sequence Initiated ===\n")

        # Start video sequence
        if video_type != 'game':
            print("\n=== Starting Intro Video Sequence ===")
            if video_file.exists():
                print(f"Found intro video at: {video_file}")
                self.video_manager.play_video(str(video_file), on_complete=play_game_video)
            else:
                print(f"Intro video not found at: {video_file}")
                play_game_video()
        else:
            print("\n=== Skipping Intro, Playing Game Video ===")
            play_game_video()

    def clear_hints(self):
        """Clear all visible hints without resetting other kiosk state"""
        print("\nClearing visible hints...")
        
        # Reset UI hint state
        self.ui.clear_hints()
        
        # Update help button state
        QTimer.singleShot(100, self.update_help_button_state)
        
        print("Hint clearing complete")

    def show_hint(self, hint_data):
        """Display a new hint"""
        # Play hint received sound
        self.audio_manager.play_sound("hint_received.mp3")
        
        # Show hint through UI
        self.ui.show_hint(hint_data)
        
        # Start cooldown
        self.ui.start_cooldown()

    def handle_video_completion(self):
        """Handle cleanup after video playback"""
        self.ui.video_is_playing = False
        
        # Restore room interface if assigned
        if self.assigned_room:
            self.signals.room_interface_update.emit(self.assigned_room)

    def closeEvent(self, event):
        """Handle application shutdown"""
        print("Shutting down kiosk...")
        if self.current_video_process:
            self.current_video_process.terminate()
        self.network.shutdown()
        self.video_server.stop()
        self.audio_server.stop()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Set application-wide stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: black;
        }
    """)
    
    # Create and show main window
    kiosk = KioskApp()
    kiosk.show()
    
    # Start event loop
    sys.exit(app.exec_())