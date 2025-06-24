# audio_manager.py
print("[audio_manager] Beginning imports ...", flush=True)
print("[audio_manager] Importing os...", flush=True)
import os
print("[audio_manager] Imported os.", flush=True)
from os import environ
print("[audio_manager] Importing pygame...", flush=True)
environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
import pygame # type: ignore
print("[audio_manager] Imported pygame.", flush=True)
print("[audio_manager] Importing time...", flush=True)
import time
print("[audio_manager] Imported time.", flush=True)
print("[audio_manager] Ending imports ...", flush=True)

class AudioManager:
    def __init__(self, kiosk_app):
        print("[audio_manager] Initializing pygame.mixer...", flush=True)
        # Check if mixer is already initialized (useful if multiple parts of app use pygame)
        if not pygame.mixer.get_init():
             pygame.mixer.init(frequency=44100, buffer=4096)
             print("[audio_manager] Initialized pygame.mixer.", flush=True)
        else:
             print("[audio_manager] pygame.mixer already initialized.", flush=True)


        self.sound_dir = "kiosk_sounds"
        self.music_dir = "music"
        self._last_played = None
        self._last_played_time = 0
        self.MIN_REPLAY_DELAY = .05
        self.current_music = None
        # is_playing now reflects pygame.mixer.music.get_busy() state,
        # but we keep it as it might be useful for UI state tracking etc.
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

        # Default volume levels (0.0 to 1.0 for pygame)
        self.music_volume_actual = 0.7  # Default 70%
        self.hint_volume_actual = 0.7   # Default 70%
        # Apply initial music volume if mixer is ready
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.music_volume_actual) 


    def play_sound(self, sound_name):
        """
        Plays a sound file from the kiosk_sounds directory.
        Allows replaying the same sound after MIN_REPLAY_DELAY seconds.
        """
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot play sound.", flush=True)
                 return

            current_time = time.time()

            # Only block if it's the same sound AND not enough time has passed
            if (sound_name == self._last_played and
                current_time - self._last_played_time < self.MIN_REPLAY_DELAY):
                print(f"[audio manager]Skipping sound {sound_name} - too soon since last play", flush=True)
                return

            sound_path = os.path.join(self.sound_dir, sound_name)
            if os.path.exists(sound_path):
                sound = pygame.mixer.Sound(sound_path)
                
                sound_channel = None  # Start with no channel assigned
                preferred_channel_id = 1 # Use channel 1 for sound effects
                channel_id_str = "any" # Default log message for a found channel

                # First, check if the preferred channel ID is valid before trying to use it.
                if preferred_channel_id < pygame.mixer.get_num_channels():
                    ch = pygame.mixer.Channel(preferred_channel_id)
                    if not ch.get_busy():
                        # It's valid and not busy, so we'll use it.
                        sound_channel = ch
                        channel_id_str = str(preferred_channel_id) # We know the ID, so we can log it.
                
                # If we couldn't get our preferred channel, try to find any other free channel.
                if sound_channel is None:
                    sound_channel = pygame.mixer.find_channel()
                    # channel_id_str remains "any" as we can't get the ID from find_channel()

                # Now, we must check if we successfully secured ANY channel before playing.
                if not sound_channel:
                    print("[audio manager] No free audio channels available to play sound.", flush=True)
                    return  # Cannot play sound

                # We have a valid channel, now we can safely play the sound.
                sound_channel.play(sound)
                self._last_played = sound_name
                self._last_played_time = current_time
                print(f"[audio manager]Playing sound {sound_name} on channel {channel_id_str}", flush=True)
            else:
                    print(f"[audio manager]Sound file not found: {sound_path}", flush=True)
        except pygame.error as pe:
             print(f"[audio manager]Pygame error playing sound {sound_name}: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager]Error playing sound {sound_name}: {e}", flush=True)

    def play_hint_audio(self, audio_name):
        """Plays a sound file from the hint_audio_files directory."""
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot play hint audio.", flush=True)
                 return

            audio_path = os.path.join(self.hint_audio_dir, audio_name)
            if os.path.exists(audio_path):
                sound = pygame.mixer.Sound(audio_path)
                sound.set_volume(self.hint_volume_actual) # Apply current hint volume
                
                sound_channel = None  # Start with no channel assigned
                preferred_channel_id = 2 # Use channel 2 for audio hints
                channel_id_str = "any" # Default log message for a found channel

                # First, check if the preferred channel ID is valid before trying to use it.
                if preferred_channel_id < pygame.mixer.get_num_channels():
                    ch = pygame.mixer.Channel(preferred_channel_id)
                    if not ch.get_busy():
                        # It's valid and not busy, so we'll use it.
                        sound_channel = ch
                        channel_id_str = str(preferred_channel_id) # We know the ID.
                
                # If we couldn't get our preferred channel, try to find any other free channel.
                if sound_channel is None:
                    sound_channel = pygame.mixer.find_channel()
                    # channel_id_str remains "any".

                # Now, we must check if we successfully secured ANY channel before playing.
                if not sound_channel:
                    print("[audio manager] No free audio channels available to play hint audio.", flush=True)
                    return  # Cannot play hint

                # We have a valid channel, now we can safely play the sound.
                sound_channel.play(sound)
                print(f"[audio manager]Playing audio hint {audio_name} on channel {channel_id_str} at volume {self.hint_volume_actual:.2f}", flush=True)

            else:
                    print(f"[audio manager]Audio hint file not found: {audio_path}", flush=True)
        except pygame.error as pe:
             print(f"[audio manager]Pygame error playing audio hint {audio_name}: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager]Error playing audio hint {audio_name}: {e}", flush=True)

    def play_background_music(self, room_number, start_time_seconds=0.0):
        """
        Plays background music for the given room number.
        Optionally starts from a specific time in seconds.
        """
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot play music.", flush=True)
                 return

            music_file = self.room_music_map.get(room_number)
            if music_file:
                music_path = os.path.join(self.music_dir, music_file)
                # Ensure start_time_seconds is treated as float and is non-negative
                start_time_seconds = max(0.0, float(start_time_seconds))
                print(f"[audio manager]Attempting to play background music: {music_path} starting at {start_time_seconds:.2f}s", flush=True)

                if os.path.exists(music_path):
                    self.stop_background_music()  # Stop any existing music first
                    pygame.mixer.music.load(music_path)
                    pygame.mixer.music.set_volume(self.music_volume_actual) # Apply current music volume
                    # Use the start parameter in play()
                    pygame.mixer.music.play(-1, start=start_time_seconds)  # Loop indefinitely
                    self.current_music = music_file
                    self.is_playing = True # Reflect that music is playing
                    print(f"[audio manager]Started playing background music: {music_file} from {start_time_seconds:.2f}s at volume {self.music_volume_actual:.2f}", flush=True)
                else:
                    print(f"[audio manager]Background music file not found: {music_path}", flush=True)
            else:
                print(f"[audio manager]No music defined for room number: {room_number}", flush=True)

        except pygame.error as pe:
             print(f"[audio manager]Pygame error playing background music: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager]Error playing background music: {e}", flush=True)

    def stop_background_music(self):
        """
        Stops any currently playing background music.
        """
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot stop music.", flush=True)
                 return

            # If mixer is initialized, calling pygame.mixer.music.stop() is safe
            # whether music is playing, paused, or not loaded. It simply ensures it's stopped.
            if pygame.mixer.music.get_busy() or self.current_music: # Check if busy OR if we *think* something is loaded
                pygame.mixer.music.stop()
                self.current_music = None
                self.is_playing = False
                print("[audio manager]Stopped background music", flush=True)
            else:
                 print("[audio manager]No background music playing or was loaded.", flush=True)
        except pygame.error as pe:
             print(f"[audio manager]Pygame error stopping background music: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager]Error stopping background music: {e}", flush=True)

    def toggle_music(self):
        """
        Toggles the music on or off. If off, turns on based on assigned room.
        This method now simply stops/starts based on get_busy().
        More complex pause/resume logic would need separate methods.
        """
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot toggle music.", flush=True)
                 return

            if pygame.mixer.music.get_busy(): # Check the actual busy state
                self.stop_background_music()
            else:
                # Try to play based on the assigned room, from the beginning
                if self.kiosk_app.assigned_room:
                    self.play_background_music(self.kiosk_app.assigned_room)
                else:
                    print("[audio manager]No room assigned, cannot start music.", flush=True)
        except Exception as e:
            print(f"[audio manager]Error toggling music: {e}", flush=True)


    def set_music_volume_float(self, volume_float):
        """
        Sets the music channel volume.
        volume_float should be between 0.0 and 1.0.
        This method updates the internal actual volume and applies it to pygame.
        """
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot set music volume.", flush=True)
                 return

            # Clamp value
            volume_float = max(0.0, min(1.0, volume_float))
            self.music_volume_actual = volume_float # Store the actual float value
            pygame.mixer.music.set_volume(self.music_volume_actual)
            # Update is_playing status based on whether music is busy
            self.is_playing = pygame.mixer.music.get_busy()
            print(f"[audio manager] Set music volume to {self.music_volume_actual:.2f}", flush=True)
        except pygame.error as pe:
             print(f"[audio manager]Pygame error setting music volume: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager] Error setting music volume: {e}", flush=True)

    def set_music_volume_level(self, level_int):
        """
        Sets the music volume based on an integer level (0-10).
        Converts level to float and calls set_music_volume_float.
        """
        if not (0 <= level_int <= 10):
            print(f"[audio manager] Invalid music volume level: {level_int}. Must be 0-10.", flush=True)
            level_int = max(0, min(10, level_int)) # Clamp

        volume_float = level_int / 10.0
        self.set_music_volume_float(volume_float)
        # The KioskApp's corresponding integer level (e.g., self.kiosk_app.music_volume_level)
        # will be updated by the MessageHandler.

    def set_hint_volume_level(self, level_int):
        """
        Sets the hint audio volume based on an integer level (0-10).
        This volume (as a float) will be stored and applied to individual hint sounds when they are played.
        """
        if not (0 <= level_int <= 10):
            print(f"[audio manager] Invalid hint volume level: {level_int}. Must be 0-10.", flush=True)
            level_int = max(0, min(10, level_int)) # Clamp

        volume_float = level_int / 10.0
        self.hint_volume_actual = max(0.0, min(1.0, volume_float)) # Store as float
        print(f"[audio manager] Set hint audio master volume to {self.hint_volume_actual:.2f}", flush=True)
        # This new hint volume will be applied the *next* time a hint sound is played.
        # It does *not* affect hint sounds currently playing.

    def play_loss_audio(self, room_number):
        """Plays the loss audio for the given room."""
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot play loss audio.", flush=True)
                 return

            # Use the same mapping for loss audio (assuming same filenames)
            audio_file = self.room_music_map.get(room_number)
            if audio_file:
                audio_path = os.path.join(self.loss_audio_dir, audio_file)
                if os.path.exists(audio_path):
                    self.stop_all_audio() # Stop everything else
                    sound = pygame.mixer.Sound(audio_path)
                    sound.set_volume(self.hint_volume_actual) # Apply hint volume to loss audio? Or should it have its own? Using hint for now.
                    
                    sound_channel = None  # Start with no channel assigned
                    preferred_channel_id = 3
                    channel_id_str = "any" # Default log message for a found channel

                    # First, check if the preferred channel ID is valid before trying to use it.
                    if preferred_channel_id < pygame.mixer.get_num_channels():
                        ch = pygame.mixer.Channel(preferred_channel_id)
                        if not ch.get_busy():
                            # It's valid and not busy, so we'll use it.
                            sound_channel = ch
                            channel_id_str = str(preferred_channel_id) # We know the ID.
                    
                    # If we couldn't get our preferred channel, try to find any other free channel.
                    if sound_channel is None:
                        sound_channel = pygame.mixer.find_channel()
                        # channel_id_str remains "any".

                    # Now, we must check if we successfully secured ANY channel before playing.
                    if not sound_channel:
                        print("[audio manager] No free audio channels available to play loss audio.", flush=True)
                        return  # Cannot play loss audio

                    # We have a valid channel, now we can safely play the sound.
                    sound_channel.play(sound) # Play once
                    
                    print(f"[audio manager]Playing loss audio {audio_file} on channel {channel_id_str} at volume {self.hint_volume_actual:.2f}", flush=True)

                else:
                    print(f"[audio manager]Loss audio not found: {audio_path}", flush=True)
            else:
                print(f"[audio manager]No loss audio defined for room number: {room_number}", flush=True)
        except pygame.error as pe:
             print(f"[audio manager]Pygame error playing loss audio: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager]Error playing loss audio: {e}", flush=True)

    def stop_all_audio(self):
        """Stops all currently playing audio, including music and sound effects."""
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot stop all audio.", flush=True)
                 return

            self.stop_background_music()  # Stop music if playing

            # Stop all active channels (channels 0 and up)
            # pygame.mixer.stop() stops all sounds on all channels
            pygame.mixer.stop()

            # Re-initialize channels if necessary after stopping all
            # (Pygame usually manages this, but explicit stop() can sometimes be thorough)
            # Check if any channels are still reported busy (unlikely after mixer.stop)
            channels_busy = any(pygame.mixer.Channel(i).get_busy() for i in range(pygame.mixer.get_num_channels()))
            if channels_busy:
                 print("[audio manager] Warning: Some channels still reported busy after mixer.stop()", flush=True)


            print("[audio manager] Stopped all audio.", flush=True)
        except pygame.error as pe:
             print(f"[audio manager]Pygame error stopping all audio: {pe}", flush=True)
        except Exception as e:
            print(f"[audio manager] Error stopping all audio: {e}", flush=True)

    def get_music_position_ms(self):
        """
        Gets the current playback position of the background music in milliseconds.
        Returns -1 if no music is currently playing or loaded, or if mixer is not initialized.
        """
        try:
            if not pygame.mixer.get_init():
                 print("[audio manager] pygame.mixer not initialized, cannot get music position.", flush=True)
                 return -1 # Indicate error or no position

            position = pygame.mixer.music.get_pos()
            # get_pos returns -1 if no music is playing/loaded
            if position != -1:
                 #print(f"[audio manager] Got music position: {position} ms", flush=True)
                 pass
            else:
                 #print("[audio manager] No music playing, position not available.", flush=True)
                 pass
            return position
        except pygame.error as pe:
             print(f"[audio manager]Pygame error getting music position: {pe}", flush=True)
             return -1 # Indicate error
        except Exception as e:
            print(f"[audio manager] Error getting music position: {e}", flush=True)
            return -1 # Indicate error