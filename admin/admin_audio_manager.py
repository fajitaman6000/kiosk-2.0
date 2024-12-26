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
            print("Audio manager initialized successfully")
        except Exception as e:
            print(f"Failed to initialize audio manager: {e}")
            return
            
        # Sound file paths
        self.sound_dir = Path("app_sounds")
        self.sounds = {}
        
        # Predefined sound mappings
        self._load_sound("hint_notification", "hint_notification.mp3")
        
        self._initialized = True
    
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
                print(f"Loaded sound: {sound_id} from {filename}")
            else:
                print(f"Sound file not found: {filepath}")
        except Exception as e:
            print(f"Error loading sound {filename}: {e}")
    
    def play_sound(self, sound_id):
        """
        Play a loaded sound by its identifier
        
        Args:
            sound_id (str): Identifier for the sound to play
        """
        if not self._initialized:
            print("Audio manager not initialized")
            return
            
        if sound_id in self.sounds:
            try:
                self.sounds[sound_id].play()
            except Exception as e:
                print(f"Error playing sound {sound_id}: {e}")
        else:
            print(f"Sound not found: {sound_id}")
    
    def cleanup(self):
        """Clean up pygame mixer resources"""
        if self._initialized:
            pygame.mixer.quit()
            self._initialized = False