import sounddevice as sd
import numpy as np
import time
from collections import deque
import threading

class TapDetector:
    """
    Listens for a specific tap pattern on an audio input device and
    executes a callback function when the pattern is detected.
    """
    DEBUG = False

    # --- 1. TUNABLE PARAMETERS ---

    # The volume threshold for detecting a "tap". You'll need to adjust this.
    LOUDNESS_THRESHOLD = 100

    # The sample rate of your microphone
    SAMPLE_RATE = 44100
    # The size of the audio chunks to process at a time
    CHUNK_SIZE = 1024

    # --- Pattern Timing Parameters (in seconds) ---
    # How long a single tap sound can last. Prevents one long noise from being
    # counted as multiple taps. Also known as a "debounce" time.
    MIN_TAP_INTERVAL = 0.15

    # The maximum time between taps within a group (e.g., the two taps in "tap-tap")
    SHORT_PAUSE_MAX = 0.5

    # The time between tap groups (e.g., between "tap" and "tap-tap")
    LONG_PAUSE_MIN = 0.6
    LONG_PAUSE_MAX = 1.5

    # If no tap is detected for this long, the current pattern is reset.
    PATTERN_TIMEOUT = 2.0

    # The pattern we are looking for: 1 tap, then 2, then 3. Total of 6 taps.
    PATTERN_LENGTH = 6

    def __init__(self, pattern_callback=None):
        """
        Initializes the tap detector.
        :param pattern_callback: A function to call when the pattern is detected.
        """
        self.pattern_callback = pattern_callback
        
        # --- 2. STATE MANAGEMENT ---
        self.tap_timestamps = deque(maxlen=self.PATTERN_LENGTH)
        self.last_tap_time = 0
        self.stream = None
        self.is_running = False

    def _check_for_pattern(self):
        """Analyzes the timestamps to see if they match the desired rhythm."""
        if len(self.tap_timestamps) < self.PATTERN_LENGTH:
            return False

        deltas = [self.tap_timestamps[i] - self.tap_timestamps[i-1] for i in range(1, self.PATTERN_LENGTH)]

        # Pattern: tap... tap-tap... tap-tap-tap
        # Deltas: [long, short, long, short, short]
        is_long_pause_1 = self.LONG_PAUSE_MIN < deltas[0] < self.LONG_PAUSE_MAX
        is_short_pause_1 = deltas[1] < self.SHORT_PAUSE_MAX
        is_long_pause_2 = self.LONG_PAUSE_MIN < deltas[2] < self.LONG_PAUSE_MAX
        is_short_pause_2 = deltas[3] < self.SHORT_PAUSE_MAX
        is_short_pause_3 = deltas[4] < self.SHORT_PAUSE_MAX

        if all([is_long_pause_1, is_short_pause_1, is_long_pause_2, is_short_pause_2, is_short_pause_3]):
            return True

        return False

    def _audio_callback(self, indata, frames, time_info, status):
        """
        This function is called for each new chunk of audio from the microphone.
        """
        if status:
            if(self.DEBUG):print(f"[TapDetector] Audio Status: {status}", flush=True)

        try:
            volume_norm = np.linalg.norm(indata) * 10
            
            if volume_norm > self.LOUDNESS_THRESHOLD:
                current_time = time.time()
                
                if current_time - self.last_tap_time > self.MIN_TAP_INTERVAL:
                    self.last_tap_time = current_time
                    
                    # Reset the pattern if the new tap is too long after the previous one
                    if self.tap_timestamps and current_time - self.tap_timestamps[-1] > self.PATTERN_TIMEOUT:
                        if(self.DEBUG):print("\n--- Tap pattern timed out, starting over. ---", flush=True)
                        self.tap_timestamps.clear()

                    # Add the new tap time to our history
                    self.tap_timestamps.append(current_time)
                    if(self.DEBUG):print(f"Tap detected! ({len(self.tap_timestamps)}/{self.PATTERN_LENGTH})", flush=True)

                    if self._check_for_pattern():
                        if(self.DEBUG):print("\n*** !!! PATTERN DETECTED: Tap, Tap-Tap, Tap-Tap-Tap !!! ***\n", flush=True)
                        self.tap_timestamps.clear()
                        # Call the callback function if it was provided
                        if self.pattern_callback:
                            # Run callback in a new thread to avoid blocking the audio stream
                            threading.Thread(target=self.pattern_callback, daemon=True).start()
        except Exception as e:
            if(self.DEBUG):print(f"[TapDetector] Error in audio callback: {e}", flush=True)

    def start(self):
        """Starts listening for taps."""
        if self.is_running:
            if(self.DEBUG):print("[TapDetector] Already running.", flush=True)
            return

        if(self.DEBUG):print("[TapDetector] Starting...", flush=True)
        try:
            # Check if a microphone is available
            if not sd.query_devices(kind='input'):
                if(self.DEBUG):print("[TapDetector] WARNING: No input audio device found. Tap detector will not start.", flush=True)
                return

            self.stream = sd.InputStream(
                callback=self._audio_callback, 
                channels=1, 
                samplerate=self.SAMPLE_RATE, 
                blocksize=self.CHUNK_SIZE
            )
            self.stream.start()
            self.is_running = True
            if(self.DEBUG):print("[TapDetector] Listening for taps...", flush=True)
        except Exception as e:
            if(self.DEBUG):print(f"[TapDetector] An error occurred during start: {e}", flush=True)
            self.stream = None
            self.is_running = False

    def stop(self):
        """Stops listening for taps."""
        if not self.is_running:
            return

        if(self.DEBUG):print("[TapDetector] Stopping...", flush=True)
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                if(self.DEBUG):print("[TapDetector] Stream stopped and closed.", flush=True)
            except Exception as e:
                if(self.DEBUG):print(f"[TapDetector] Error stopping stream: {e}", flush=True)
        self.stream = None
        self.is_running = False