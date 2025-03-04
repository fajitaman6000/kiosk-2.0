import pygame
import os
from pathlib import Path
from threading import Lock

class AdminAudioManager:
    """
    Manages sound effects for the admin interface.
    Uses singleton pattern to ensure only one instance handles audio playback.
    """
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(AdminAudioManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        """Initialize the audio manager if not already initialized"""
        if self._initialized:
            return
            
        # Initialize pygame mixer
        try:
            pygame.mixer.init()
            #print("[audio manager]Audio manager initialized successfully")
        except Exception as e:
            print(f"[audio manager]Failed to initialize audio manager: {e}")
            return
            
        # Sound file paths
        self.sound_dir = Path("app_sounds")
        self.sounds = {}
        
        # Track sound play states
        self.sound_states = {}  # Changed from dict to empty dict
        
        # Predefined sound mappings
        self._load_sound("hint_notification", "hint_notification.mp3")
        self._load_sound("game_finish", "game_finish.mp3")
        self._load_sound("game_fail", "game_fail.mp3")
        
        self._initialized = True
    
    def play_hint_notification(self):
        """Plays the hint notification sound."""
        self.play_sound("hint_notification")

    def play_flagged_finish_notification(self):
        """Plays the hint notification sound."""
        self.play_sound("flagged_finish")

    def _load_sound(self, sound_id, filename):
        """
        Load a sound file into memory
        
        Args:
            sound_id (str): Identifier for the sound
            filename (str): Name of the sound file
        """
        try:
            filepath = self.sound_dir / filename
            if filepath.exists():
                self.sounds[sound_id] = pygame.mixer.Sound(str(filepath))
                #print(f"[audio manager]Loaded sound: {sound_id} from {filename}")
            else:
                print(f"[audio manager]Sound file not found: {filepath}")
        except Exception as e:
            print(f"[audio manager]Error loading sound {filename}: {e}")
    
    def play_sound(self, sound_id):
        """
        Play a loaded sound by its identifier
        
        Args:
            sound_id (str): Identifier for the sound to play
        """
        if not self._initialized:
            print("[audio manager]Audio manager not initialized")
            return
            
        if sound_id in self.sounds:
            try:
                self.sounds[sound_id].play()
            except Exception as e:
                print(f"[audio manager]Error playing sound {sound_id}: {e}")
        else:
            print(f"[audio manager]Sound not found: {sound_id}")
    
    def handle_game_finish(self, is_finished, room_number):  # Added room_number parameter
        # Initialize state for this room if needed
        if room_number not in self.sound_states:
            self.sound_states[room_number] = {
                'game_finish': False,
                'game_fail': False
            }
        
        if is_finished and not self.sound_states[room_number]['game_finish']:
            self.play_sound('game_finish')
            self.sound_states[room_number]['game_finish'] = True
        elif not is_finished:
            self.sound_states[room_number]['game_finish'] = False
    
    def handle_timer_expired(self, is_expired, room_number):  # Added room_number parameter
        # Initialize state for this room if needed
        if room_number not in self.sound_states:
            self.sound_states[room_number] = {
                'game_finish': False,
                'game_fail': False
            }
        
        if is_expired and not self.sound_states[room_number]['game_fail']:
            self.play_sound('game_fail')
            self.sound_states[room_number]['game_fail'] = True
        elif not is_expired:
            self.sound_states[room_number]['game_fail'] = False
    
    def cleanup(self):
        """Clean up pygame mixer resources"""
        if self._initialized:
            pygame.mixer.quit()
            self._initialized = False