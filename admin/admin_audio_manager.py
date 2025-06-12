from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame
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
            
        # Initialize pygame mixer (REMOVED: This is now handled in admin_main.py)
        # try:
        #     pygame.mixer.init()
        #     #print("[audio manager]Audio manager initialized successfully")
        # except Exception as e:
        #     print(f"[audio manager]Failed to initialize audio manager: {e}")
        #     return
            
        # Sound file paths
        self.sound_dir = Path("app_sounds")
        self.sounds = {}

        self.loss_sound_played = {}
        
        # Predefined sound mappings
        self._load_sound("hint_notification", "hint_notification.mp3")
        self._load_sound("game_finish", "game_finish.mp3")
        self._load_sound("game_fail", "game_fail.mp3")
        self._load_sound("flagged_finish", "flagged_finish.mp3")
        
        self._initialized = True
    
    def clear_loss_sound_played(self,room_number):
        if room_number in self.loss_sound_played:
                self.loss_sound_played[room_number] = False
        else:
            self.loss_sound_played[room_number] = False
            print(f"[audio manager] loss sound set false for room {room_number} despite no pre-existing state")

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
        # REMOVED sound_state logic
        pass
    
    def handle_timer_expired(self, is_expired, room_number):  # Added room_number parameter
        # REMOVED sound_state logic
        pass
    
    def cleanup(self):
        """Clean up pygame mixer resources"""
        if self._initialized:
            #pygame.mixer.quit()
            self._initialized = False