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
    ROOM_MAP = {
        3: "wizard",
        1: "casino",
        2: "ma",
        5: "haunted",
        4: "zombie",
        6: "atlantis",
        7: "time"  # Time Machine room
    }
    
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
    
    def play_finish_sound(self, room_number=None):
        """
        Plays the finish sound. Always plays the generic finish sound,
        and also plays a room-specific one if it exists.
        
        Args:
            room_number (int, optional): The room number to play a specific sound for. Defaults to None.
        """
        # Always play the generic, pre-loaded game finish sound
        self.play_sound("game_finish")

        # Try to find and play a room-specific sound
        room_name = self.ROOM_MAP.get(room_number)
        if room_name:
            # Construct the sound ID and filename
            sound_id = f"{room_name}_finish"
            filename = f"{room_name}-finish.mp3"
            
            # Dynamically load the sound if it's not already in memory
            # The _load_sound method checks for file existence.
            if sound_id not in self.sounds:
                self._load_sound(sound_id, filename)
            
            # If the sound was successfully loaded, play it
            if sound_id in self.sounds:
                self.play_sound(sound_id)
        elif room_number is not None:
            print(f"[audio manager] Room number {room_number} not in ROOM_MAP. Cannot play specific finish sound.")

    def play_finish_sound(self, room_number=None):
        """
        Plays the finish sound. Always plays the generic finish sound,
        and also plays a room-specific one if it exists.
        
        Args:
            room_number (int, optional): The room number to play a specific sound for. Defaults to None.
        """
        # Always play the generic, pre-loaded game finish sound
        self.play_sound("game_finish")

        # Try to find and play a room-specific sound
        room_name = self.ROOM_MAP.get(room_number)
        if room_name:
            # Construct the sound ID and filename
            sound_id = f"{room_name}_finish"
            filename = f"{room_name}-finish.mp3"
            
            # Dynamically load the sound if it's not already in memory
            # The _load_sound method checks for file existence.
            if sound_id not in self.sounds:
                self._load_sound(sound_id, filename)
            
            # If the sound was successfully loaded, play it
            if sound_id in self.sounds:
                self.play_sound(sound_id)
        elif room_number is not None:
            print(f"[audio manager] Room number {room_number} not in ROOM_MAP. Cannot play specific finish sound.")

    def play_loss_sound(self, room_number=None):
        """
        Plays the loss sound. Always plays the generic loss sound,
        and also plays a room-specific one if it exists.
        
        Args:
            room_number (int, optional): The room number to play a specific sound for. Defaults to None.
        """
        # Always play the generic, pre-loaded game finish sound
        self.play_sound("game_fail")

        # Try to find and play a room-specific sound
        room_name = self.ROOM_MAP.get(room_number)
        if room_name:
            # Construct the sound ID and filename
            sound_id = f"{room_name}_fail"
            filename = f"{room_name}-fail.mp3"
            
            # Dynamically load the sound if it's not already in memory
            # The _load_sound method checks for file existence.
            if sound_id not in self.sounds:
                self._load_sound(sound_id, filename)
            
            # If the sound was successfully loaded, play it
            if sound_id in self.sounds:
                self.play_sound(sound_id)
        elif room_number is not None:
            print(f"[audio manager] Room number {room_number} not in ROOM_MAP. Cannot play specific loss sound.")

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