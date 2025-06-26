# bar_server/bar_audio_manager.py
import os
from PyQt5.QtCore import QUrl
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent

import config

class AudioManager:
    """
    Manages loading and playing sound effects for the application.
    Uses QMediaPlayer for broad codec support (MP3, WAV, etc.).
    """
    def __init__(self):
        super().__init__()
        self._media_players = {}
        self._preload_sounds()

    def _preload_sounds(self):
        """
        Loads sound files specified in the config into memory for quick playback.
        Creates the sound directory if it doesn't exist.
        """
        if not os.path.exists(config.SOUNDS_DIR):
            try:
                os.makedirs(config.SOUNDS_DIR)
                print(f"AudioManager: Created sound directory at {config.SOUNDS_DIR}")
            except OSError as e:
                print(f"AudioManager: CRITICAL - Could not create sound directory: {e}")
                return

        notification_sound_path = os.path.join(config.SOUNDS_DIR, config.DEFAULT_NOTIFICATION_SOUND)
        
        if os.path.exists(notification_sound_path):
            player = QMediaPlayer()
            # Set the media content for the player
            player.setMedia(QMediaContent(QUrl.fromLocalFile(notification_sound_path)))
            # Set volume (0-100 for QMediaPlayer)
            player.setVolume(90)
            self._media_players['notification'] = player
            print(f"AudioManager: Preloaded sound '{config.DEFAULT_NOTIFICATION_SOUND}'")
        else:
            print(f"AudioManager: WARNING - Notification sound not found at '{notification_sound_path}'. No sound will be played for new orders.")

    def play_order_notification(self):
        """Plays the pre-loaded order notification sound."""
        if 'notification' in self._media_players:
            player = self._media_players['notification']
            # Stop the sound if it's currently playing and restart from the beginning.
            # This handles rapid re-triggering correctly.
            player.stop()
            player.play()