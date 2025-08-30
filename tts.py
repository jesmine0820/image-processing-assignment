# tts.py
from gtts import gTTS
import os
import tempfile
import platform
import subprocess

def speak(text, lang="en"):
    try:
        # Create temporary mp3 file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
            filename = fp.name

        # Generate speech
        tts = gTTS(text=text, lang=lang)
        tts.save(filename)

        # Play depending on OS
        if platform.system() == "Windows":
            os.startfile(filename)

    except Exception as e:
        print(f"[TTS ERROR] {e}")
