import pygame
import os

class AudioManager:
    def __init__(self):
        pygame.mixer.init()
        self.sound_dir = "kiosk_sounds"
        self._last_played = None  # Track last played sound to prevent duplicates
        
    def play_sound(self, sound_name):
        """
        Plays a sound file from the kiosk_sounds directory.
        Prevents the same sound from playing multiple times in quick succession.
        """
        try:
            # Don't play the same sound again if it was the last one played
            if sound_name == self._last_played:
                return
                
            sound_path = os.path.join(self.sound_dir, sound_name)
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                sound.play()
                self._last_played = sound_name
        except Exception as e:
            print(f"Error playing sound {sound_name}: {e}")