import pygame # type: ignore
import os
import time  # Add this import

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
        self.kiosk_app = kiosk_app
        self.hint_audio_dir = "hint_audio_files"
        self.loss_audio_dir = "loss_audio"

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

    def play_background_music(self, room_name):
        """
        Starts playing background music for the specified room.
        Music will loop continuously until stopped.
        """
        try:
            # Convert room name to match music file naming convention
            music_name = room_name.lower().replace(" ", "_") + ".mp3"
            music_path = os.path.join(self.music_dir, music_name)
            
            print(f"[audio manager]Attempting to play background music: {music_path}")
            
            if os.path.exists(music_path):
                # Stop any currently playing music
                self.stop_background_music()
                
                # Load and play the new music
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.play(-1)  # -1 means loop indefinitely
                self.current_music = music_name
                self.is_playing = True
                print(f"[audio manager]Started playing background music: {music_name}")
            else:
                print(f"[audio manager]Background music file not found: {music_path}")
                
        except Exception as e:
            print(f"[audio manager]Error playing background music: {e}")
            
    def get_room_music_name(self, room_number):
        """Helper to map room number to music file name."""
        room_names = {
            2: "morning_after",
            1: "casino_heist",
            5: "haunted_manor",
            4: "zombie_outbreak",
            7: "time_machine",
            6: "atlantis_rising",
            3: "wizard_trials"
        }
        return room_names.get(room_number)

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
        """Toggles the music on or off. Loads the room's track if not already loaded."""
        try:
            if self.current_music:
                if pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                    self.is_playing = False
                    print("[audio manager]Stopped background music")
                else:
                    music_path = os.path.join(self.music_dir, self.current_music)
                    pygame.mixer.music.load(music_path)
                    pygame.mixer.music.play(-1)
                    self.is_playing = True
                    print(f"[audio manager]Started playing background music: {self.current_music}")
            else:
                # No track loaded, so try to load it based on the assigned room
                print("[audio manager]No music track loaded. Trying to load based on assigned room.")
                if self.kiosk_app.assigned_room:
                    room_name = self.get_room_music_name(self.kiosk_app.assigned_room)
                    if room_name:
                        self.play_background_music(room_name)  # Use existing method to load and play
                    else:
                        print(f"[audio manager]Could not determine music for room: {self.kiosk_app.assigned_room}")
                else:
                    print("[audio manager]No room assigned, cannot load music.")
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

    def play_loss_audio(self, room_name):
        """Plays the loss audio for the given room."""
        try:
            audio_name = room_name.lower().replace(" ", "_") + ".mp3"
            audio_path = os.path.join(self.loss_audio_dir, audio_name)
            if os.path.exists(audio_path):
                # Stop any other audio
                self.stop_all_audio()
                # Use channel 3 for loss audio
                sound = pygame.mixer.Sound(audio_path)
                sound_channel = pygame.mixer.Channel(3)
                sound_channel.play(sound)
                print(f"[audio manager] Playing loss audio {audio_name} on channel 3")
            else:
                print(f"[audio manager] Loss audio not found: {audio_path}")

        except Exception as e:
            print(f"[audio manager] Error playing loss audio: {e}")
    
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