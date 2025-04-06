import os
import shutil
from pathlib import Path
import openai
import requests
import tkinter as tk
from tkinter import filedialog
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API keys and voice IDs from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")
OPENAI_TTS_VOICE_ID = os.getenv("OPEN_AI_TTS_VOICE_ID")

# import torch
# print(torch.cuda.is_available())  # Should return True
# print(torch.cuda.get_device_name(0))

# Function to open Windows Explorer and select a video file
def select_video():
    root = tk.Tk()
    root.withdraw()
    video_file_path = filedialog.askopenfilename(initialdir=os.getcwd(), title="Select Video File", filetypes=(("Video files", "*.mp4;*.avi;*.mov"), ("All files", "*.*")))
    if not video_file_path:
        print("No video file selected.")
        return None, None

    video_folder, video_file = os.path.split(video_file_path)
    video_name = os.path.splitext(video_file)[0]
    # new_folder = f"{str(1).zfill(4)}_{video_name}"
    new_folder = f"{video_name}"
    new_folder_path = os.path.join(video_folder, new_folder)
    os.makedirs(new_folder_path, exist_ok=True)
    shutil.copy(video_file_path, os.path.join(new_folder_path, "source_video.mp4"))

    # Extract audio from video as MP3 using ffmpeg
    audio_path = os.path.join(new_folder_path, "source_audio.mp3")
    subprocess.run(['ffmpeg', '-i', video_file_path, '-vn', '-acodec', 'libmp3lame', '-y', audio_path], capture_output=True)

    return new_folder_path, audio_path


# Function to transcribe audio using Open AI
def transcribe_audio(audio_path, output_text_file):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print("Transcribing using OpenAI Whisper API...")

    with open(audio_path, "rb") as audio_file:
        response = client.audio.transcriptions.create(model="whisper-1", file=audio_file, response_format="text")

    with open(output_text_file, "w", encoding="utf-8") as f:
        f.write(response)

    print(f"Transcription saved as '{output_text_file}'")


# Function to translate text using Open AI
def translate_text(input_text_file, output_text_file):
    with open(input_text_file, "r", encoding="utf-8") as f:
        original_text = f.read()

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print("Translating text using Open AI gpt-4o-mini...")

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": "You are a professional translator. Translate the following text into English."},
            {"role": "user", "content": original_text}
        ],
        temperature=0.0
    )
    translated_text = response.choices[0].message.content.strip()

    with open(output_text_file, "w", encoding="utf-8") as f:
        f.write(translated_text)

    print(f"Translation saved as '{output_text_file}'")

# Function to generate audio using Open AI TTS API
def generate_audio_with_openai_tts(input_text_file, output_audio_file, voice='onyx', model='tts-1'):
    with open(input_text_file, "r", encoding="utf-8") as f:
        text = f.read()

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print("Generating English audio using OpenAI TTS API...")

    # Generate speech using OpenAI's TTS API
    # Generate speech using OpenAI's TTS API
    response = client.audio.speech.create(
        model="tts-1",
        voice=voice,
        input=text,
    )

    # Define the path for the output audio file
    speech_file_path = Path(output_audio_file)

    # Stream the generated audio to the output file
    response.stream_to_file(speech_file_path)

    print(f"Generated English audio saved as '{output_audio_file}'")

# Function to generate audio using ElevenLabs API
def generate_audio_with_elevenlabs(text_file, output_audio_file):
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}

    print("Generating English audio using ElevenLabs API...")
    response = requests.post(url, json=data, headers=headers)
    with open(output_audio_file, "wb") as f:
        f.write(response.content)

    print(f"Generated English audio saved as '{output_audio_file}'")


# Main function
def main():
    folder_path, audio_path = select_video()
    if not folder_path or not audio_path:
        return

    original_text_file = os.path.join(folder_path, "original_text.txt")
    english_text_file = os.path.join(folder_path, "english_text.txt")
    output_audio_file = os.path.join(folder_path, "english_audio.mp3")

    transcribe_audio(audio_path, original_text_file)
    translate_text(original_text_file, english_text_file)
    generate_audio_with_openai_tts(english_text_file, output_audio_file, voice=OPENAI_TTS_VOICE_ID)
    # generate_audio_with_elevenlabs(english_text_file, output_audio_file)


if __name__ == "__main__":
    main()
