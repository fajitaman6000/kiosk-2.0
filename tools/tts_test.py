# First, make sure you have run: pip install elevenlabs
from elevenlabs import play, VoiceSettings
from elevenlabs.client import ElevenLabs  # Using the class from your working example

# 1. Instantiate the client with your API key
# It's best practice to use an environment variable, but this is fine for a simple script.
client = ElevenLabs(
    api_key="sk_43baf5aee5f1ce913b22ee1f43d1cbafa873361bb2f38e2f", # Replace with your API key if needed
)

# 2. Define the hardcoded text you want to speak
text_to_speak = "This is an example of a hint. This is what guests would hear when receiving a hint."

# 3. Generate the audio stream using the settings from your working code
# This returns an audio stream generator, not the full audio file yet.
audio_stream = client.text_to_speech.convert(
    voice_id="pNInz6obpgDQGcFmaJgB",  # Adam pre-made voice
    optimize_streaming_latency="0",
    output_format="mp3_22050_32",
    text=text_to_speak,
    model_id="eleven_turbo_v2",
    voice_settings=VoiceSettings(
        stability=0.0,
        similarity_boost=1.0,
        style=0.0,
        use_speaker_boost=True,
    ),
)

# 4. Play the audio stream directly
# The play() function takes the audio stream and handles playback in real-time.
print("Generating and playing audio stream...")
play(audio_stream)
print("Playback finished.")