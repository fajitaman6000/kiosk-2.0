import pygame
import os
import time  # Add this import

class AudioManager:
    def __init__(self):
        pygame.mixer.init()
        self.sound_dir = "kiosk_sounds"
        self._last_played = None  # Track last played sound
        self._last_played_time = 0  # Track when sound was last played
        self.MIN_REPLAY_DELAY = 1  # Minimum seconds between same sound replays
        
    def play_sound(self, sound_name):
        """
        Plays a sound file from the kiosk_sounds directory.
        Allows replaying the same sound after MIN_REPLAY_DELAY seconds.
        """
        try:
            current_time = time.time()
            
            # Only block if it's the same sound AND not enough time has passed
            if (sound_name == self._last_played and 
                current_time - self._last_played_time < self.MIN_REPLAY_DELAY):
                return
                
            sound_path = os.path.join(self.sound_dir, sound_name)
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                self._last_played = sound_name
                self._last_played_time = current_time
        except Exception as e:
            print(f"Error playing sound {sound_name}: {e}")