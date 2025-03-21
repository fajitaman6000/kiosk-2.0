# audio_manager.py
print("[audio_manager] Beginning imports ...")
import os
from os import environ
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame # type: ignore
import time
print("[audio_manager] Ending imports ...")

class AudioManager:
    def __init__(self, kiosk_app):
        pygame.mixer.init()
        self.sound_dir = "kiosk_sounds"
        self.music_dir = "music"
        self._last_played = None
        self._last_played_time = 0
        self.MIN_REPLAY_DELAY = .05
        self.current_music = None
        self.is_playing = False
        self.kiosk_app = kiosk_app  # Keep the reference to KioskApp
        self.hint_audio_dir = "hint_audio_files"
        self.loss_audio_dir = "loss_audio"

        # Room to music mapping (moved INSIDE AudioManager)
        self.room_music_map = {
            1: "casino_heist.mp3",
            2: "morning_after.mp3",
            3: "wizard_trials.mp3",
            4: "zombie_outbreak.mp3",
            5: "haunted_manor.mp3",
            6: "atlantis_rising.mp3",
            7: "time_machine.mp3",
        }

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
                print(f"[audio manager]Skipping sound {sound_name} - too soon since last play")
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
                print(f"[audio manager]Playing sound {sound_name} on channel 1")
        except Exception as e:
            print(f"[audio manager]Error playing sound {sound_name}: {e}")

    def play_hint_audio(self, audio_name):
        """Plays a sound file from the hint_audio_files directory."""
        try:
            audio_path = os.path.join(self.hint_audio_dir, audio_name)
            if os.path.exists(audio_path):
                sound = pygame.mixer.Sound(audio_path)
                #Use channel 2 for audio hints (channel 0 is reserved for video and 1 for sfx)
                sound_channel = pygame.mixer.Channel(2)
                sound_channel.play(sound)
                print(f"[audio manager]Playing audio hint {audio_name} on channel 2")

            else:
                    print(f"[audio manager]Audio hint file not found: {audio_path}")
        except Exception as e:
            print(f"[audio manager]Error playing audio hint {audio_name}: {e}")

    def play_background_music(self, room_number):
        """
        Plays background music for the given room number.
        """
        try:
            music_file = self.room_music_map.get(room_number)
            if music_file:
                music_path = os.path.join(self.music_dir, music_file)
                print(f"[audio manager]Attempting to play background music: {music_path}")

                if os.path.exists(music_path):
                    self.stop_background_music()  # Stop any existing music
                    pygame.mixer.music.load(music_path)
                    pygame.mixer.music.play(-1)  # Loop indefinitely
                    self.current_music = music_file
                    self.is_playing = True
                    print(f"[audio manager]Started playing background music: {music_file}")
                else:
                    print(f"[audio manager]Background music file not found: {music_path}")
            else:
                print(f"[audio manager]No music defined for room number: {room_number}")

        except Exception as e:
            print(f"[audio manager]Error playing background music: {e}")

    def stop_background_music(self):
        """
        Stops any currently playing background music.
        """
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
                self.current_music = None
                self.is_playing = False
                print("[audio manager]Stopped background music")
        except Exception as e:
            print(f"[audio manager]Error stopping background music: {e}")
    def toggle_music(self):
        """
        Toggles the music on or off.  If off, turns on based on assigned room.
        """
        try:
            if self.is_playing:
                self.stop_background_music()
            else:
                # Try to play based on the assigned room
                if self.kiosk_app.assigned_room:
                    self.play_background_music(self.kiosk_app.assigned_room)
                else:
                    print("[audio manager]No room assigned, cannot start music.")
        except Exception as e:
            print(f"[audio manager]Error toggling music: {e}")


    def set_music_volume(self, volume):
        """
        Sets the volume of currently playing background music.
        Volume should be between 0.0 and 1.0
        """
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(volume)
        except Exception as e:
            print(f"[audio manager]Error setting music volume: {e}")

    def play_loss_audio(self, room_number):
        """Plays the loss audio for the given room."""
        try:
            # Use the same mapping for loss audio (assuming same filenames)
            audio_file = self.room_music_map.get(room_number)
            if audio_file:
                audio_path = os.path.join(self.loss_audio_dir, audio_file)
                if os.path.exists(audio_path):
                    self.stop_all_audio()
                    sound = pygame.mixer.Sound(audio_path)
                    sound_channel = pygame.mixer.Channel(3)  # Dedicated channel
                    sound_channel.play(sound)
                    print(f"[audio manager]Playing loss audio {audio_file} on channel 3")
                else:
                    print(f"[audio manager]Loss audio not found: {audio_path}")
            else:
                print(f"[audio manager]No loss audio defined for room number: {room_number}")
        except Exception as e:
            print(f"[audio manager]Error playing loss audio: {e}")

    def stop_all_audio(self):
        """Stops all currently playing audio, including music and sound effects."""
        try:
            self.stop_background_music()  # Stop music if playing

            # Stop all active channels
            for channel_id in range(pygame.mixer.get_num_channels()):
                channel = pygame.mixer.Channel(channel_id)
                if channel.get_busy():
                    channel.stop()
            print("[audio manager] Stopped all audio.")
        except Exception as e:
            print(f"[audio manager] Error stopping all audio: {e}")