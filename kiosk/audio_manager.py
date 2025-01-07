from PyQt5.QtCore import QObject, QTimer
import pygame
import os
import time

class AudioManager(QObject):
    """
    PyQt5 version of the AudioManager class.
    Handles sound effects and background music for the kiosk application.
    
    Key differences from Tkinter version:
    - Inherits from QObject to support Qt's parent-child memory management
    - Uses QTimer for precise timing control
    - Maintains identical audio functionality
    """
    
    def __init__(self, parent=None):
        """Initialize the audio manager with optional parent for Qt memory management"""
        super().__init__(parent)
        
        # Initialize pygame mixer
        pygame.mixer.init()
        
        # Define audio directories (same as Tkinter version)
        self.sound_dir = "kiosk_sounds"
        self.music_dir = "music"
        
        # State tracking (maintained from Tkinter version)
        self._last_played = None
        self._last_played_time = 0
        self.MIN_REPLAY_DELAY = 1
        self.current_music = None
        
        # Create QTimer for timing checks
        self._replay_timer = QTimer(self)
        self._replay_timer.setSingleShot(True)
        
    def play_sound(self, sound_name):
        """
        Plays a sound file from the kiosk_sounds directory.
        Allows replaying the same sound after MIN_REPLAY_DELAY seconds.
        
        Args:
            sound_name (str): Name of the sound file to play
        """
        try:
            current_time = time.time()
            
            # Only block if it's the same sound AND not enough time has passed
            if (sound_name == self._last_played and 
                current_time - self._last_played_time < self.MIN_REPLAY_DELAY):
                print(f"Skipping sound {sound_name} - too soon since last play")
                return
                
            sound_path = os.path.join(self.sound_dir, sound_name)
            if os.path.exists(sound_path):
                # Create sound object and force it to use a different channel than video
                sound = pygame.mixer.Sound(sound_path)
                # Use channel 1 for sound effects (channel 0 is reserved for video audio)
                sound_channel = pygame.mixer.Channel(1)
                sound_channel.play(sound)
                self._last_played = sound_name
                self._last_played_time = current_time
                print(f"Playing sound {sound_name} on channel 1")
        except Exception as e:
            print(f"Error playing sound {sound_name}: {e}")
            
    def play_background_music(self, room_name):
        """
        Starts playing background music for the specified room.
        Music will loop continuously until stopped.
        
        Args:
            room_name (str): Name of the room to play music for
        """
        try:
            # Convert room name to match music file naming convention
            music_name = room_name.lower().replace(" ", "_") + ".mp3"
            music_path = os.path.join(self.music_dir, music_name)
            
            print(f"Attempting to play background music: {music_path}")
            
            if os.path.exists(music_path):
                # Stop any currently playing music
                self.stop_background_music()
                
                # Load and play the new music
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.play(-1)  # -1 means loop indefinitely
                self.current_music = music_name
                print(f"Started playing background music: {music_name}")
            else:
                print(f"Background music file not found: {music_path}")
                
        except Exception as e:
            print(f"Error playing background music: {e}")
            
    def stop_background_music(self):
        """Stops any currently playing background music."""
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                self.current_music = None
                print("Stopped background music")
        except Exception as e:
            print(f"Error stopping background music: {e}")
            
    def set_music_volume(self, volume):
        """
        Sets the volume of currently playing background music.
        
        Args:
            volume (float): Volume level between 0.0 and 1.0
        """
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(volume)
        except Exception as e:
            print(f"Error setting music volume: {e}")
            
    def __del__(self):
        """
        Cleanup when the AudioManager is destroyed.
        Ensures pygame mixer is properly shut down.
        """
        try:
            pygame.mixer.quit()
        except:
            pass