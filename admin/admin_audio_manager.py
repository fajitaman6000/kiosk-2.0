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
            #print("Audio manager initialized successfully")
        except Exception as e:
            print(f"Failed to initialize audio manager: {e}")
            return
            
        # Sound file paths
        self.sound_dir = Path("app_sounds")
        self.sounds = {}
        
        # Track sound play states
        self.sound_states = {
            'game_finish': False,  # True if finish sound has played and game is still finished
            'game_fail': False,    # True if fail sound has played and timer is still at 0
        }
        
        # Predefined sound mappings
        self._load_sound("hint_notification", "hint_notification.mp3")
        self._load_sound("game_finish", "game_finish.mp3")
        self._load_sound("game_fail", "game_fail.mp3")
        
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
                #print(f"Loaded sound: {sound_id} from {filename}")
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
    
    def handle_game_finish(self, is_finished):
        """Handle game finish state change and play sound if needed"""
        if is_finished and not self.sound_states['game_finish']:
            self.play_sound('game_finish')
            self.sound_states['game_finish'] = True
            print("admin_audio_manager.py calling finish")
        elif not is_finished:
            self.sound_states['game_finish'] = False
    
    def handle_timer_expired(self, is_expired):
        """Handle timer expiration state change and play sound if needed"""
        if is_expired and not self.sound_states['game_fail']:
            self.play_sound('game_fail')
            self.sound_states['game_fail'] = True
        elif not is_expired:
            self.sound_states['game_fail'] = False
    
    def cleanup(self):
        """Clean up pygame mixer resources"""
        if self._initialized:
            pygame.mixer.quit()
            self._initialized = False