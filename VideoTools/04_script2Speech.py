import os
import shutil
from pathlib import Path
import openai
import requests
import tkinter as tk
from tkinter import filedialog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get API keys and voice IDs from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_TTS_VOICE_ID = os.getenv("OPEN_AI_TTS_VOICE_ID")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID")

# Function to open file dialog and select a text file
def select_text_file():
    root = tk.Tk()
    root.withdraw()
    text_file_path = filedialog.askopenfilename(initialdir=os.getcwd(), title="Select Text File", 
                                               filetypes=(("Text files", "*.txt"), ("All files", "*.*")))
    if not text_file_path:
        print("No text file selected.")
        return None, None, None
    
    # Get the base name of the txt file without extension
    text_file_name = os.path.splitext(os.path.basename(text_file_path))[0]
    
    # Define the base output directory
    base_output_dir = os.path.join("OUTPUT", "SCRIPT_2_SPEECH")
    # Create the specific folder for this file
    folder_path = os.path.join(base_output_dir, text_file_name)
    os.makedirs(folder_path, exist_ok=True)

    # Define the path for the copied original script file
    script_org_path = os.path.join(folder_path, "script_org.txt")
    # Copy the original text file to the new folder with the new name
    shutil.copy2(text_file_path, script_org_path)

    print(f"Created folder: {folder_path}")
    print(f"Copied original script to: {script_org_path}")
    
    # Define the output audio path
    output_audio_path = os.path.join(folder_path, "script_audio.mp3")
    
    # Return the folder path, the path to the copied script, and the output audio path
    return folder_path, script_org_path, output_audio_path

# Function to generate audio using Open AI TTS API
def generate_audio_with_openai(input_text_file, output_audio_file, voice):
    """
    Generate audio from text using OpenAI's TTS API
    """
    with open(input_text_file, "r", encoding="utf-8") as f:
        text = f.read()

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print(f"Generating audio using OpenAI with voice '{voice}'...")

    # Generate speech using OpenAI's TTS API
    response = client.audio.speech.create(
        # model="tts-1",
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
    )

    # Stream the generated audio to the output file
    speech_file_path = Path(output_audio_file)
    response.stream_to_file(speech_file_path)

    print(f"Generated audio saved as '{output_audio_file}'")
    return output_audio_file

# Function to generate audio using ElevenLabs API
def generate_audio_with_elevenlabs(text_file, output_audio_file, voice_id=ELEVENLABS_VOICE_ID):
    """
    Generate audio from text using ElevenLabs API
    """
    with open(text_file, "r", encoding="utf-8") as f:
        text = f.read()

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    data = {"text": text, "voice_settings": {"stability": 0.5, "similarity_boost": 0.8}}

    print(f"Generating audio using ElevenLabs API with voice ID '{voice_id}'...")
    response = requests.post(url, json=data, headers=headers)
    
    if response.status_code != 200:
        print(f"Error from ElevenLabs API: {response.text}")
        return None
        
    with open(output_audio_file, "wb") as f:
        f.write(response.content)

    print(f"Generated audio saved as '{output_audio_file}'")
    return output_audio_file

# Main function
def main():
    folder_path, script_path, output_audio_path = select_text_file()
    if not folder_path or not script_path or not output_audio_path:
        return

    # Ask user for TTS service choice
    while True:
        choice = input("Do you want to use OpenAI or ElevenLabs to generate speech? Enter 1 for OpenAI, 2 for ElevenLabs: ")
        if choice in ['1', '2']:
            break
        print("Invalid input. Please enter 1 or 2.")

    # Generate audio based on user choice
    if choice == '1':
        # Generate audio using OpenAI TTS
        generate_audio_with_openai(script_path, output_audio_path, voice=OPENAI_TTS_VOICE_ID)
    else:
        # Generate audio using ElevenLabs
        generate_audio_with_elevenlabs(script_path, output_audio_path)
    
    print(f"Process completed. Files saved in {folder_path}")

if __name__ == "__main__":
    main()
