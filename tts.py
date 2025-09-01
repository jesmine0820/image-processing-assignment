import pyttsx3
import pandas as pd
from utility import graduation_level

# Initialize engine once
engine = pyttsx3.init()
engine.setProperty("rate", 150)   # speed (words per minute)
engine.setProperty("volume", 1.0) # volume (0.0 - 1.0)

voices = engine.getProperty("voices")
for voice in voices:
    if "female" in voice.name.lower() or "zira" in voice.name.lower():
        engine.setProperty("voice", voice.id)
        print(f"Using voice: {voice.name}")
        break

def speak(student_id: str):
    if not student_id:
        return
    try:
        dataset = pd.read_csv("dataset/dataset.csv")
        student = dataset[dataset["StudentID"] == student_id]

        if student.empty:
            print(f"No student found with ID {student_id}")
            return

        name = student.iloc[0]["Name"]
        course = student.iloc[0]["Course"]
        cgpa = float(student.iloc[0]["CGPA"])

        grad_level = graduation_level(cgpa)

        message = f"{course}, {name}, graduates with {grad_level}."
        print("Speaking:", message)

        engine.say(message)
        engine.runAndWait()

    except Exception as e:
        print(f"TTS error: {e}")
