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

# Function to open a file dialog and select an input file (audio or video)
def select_input_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(
        initialdir=os.getcwd(),
        title="Select Audio or Video File",
        filetypes=(
            ("Media files", "*.mp4;*.avi;*.mov;*.mp3;*.wav;*.m4a"),
            ("Video files", "*.mp4;*.avi;*.mov"),
            ("Audio files", "*.mp3;*.wav;*.m4a"),
            ("All files", "*.*")
        )
    )
    if not file_path:
        print("No file selected.")
        return None, None, None

    file_dir, file_name_ext = os.path.split(file_path)
    file_name, file_ext = os.path.splitext(file_name_ext)
    file_ext = file_ext.lower()

    # Determine file type
    video_extensions = ['.mp4', '.avi', '.mov']
    audio_extensions = ['.mp3', '.wav', '.m4a']
    
    file_type = None
    if file_ext in video_extensions:
        file_type = 'video'
    elif file_ext in audio_extensions:
        file_type = 'audio'
    else:
        print(f"Unsupported file type: {file_ext}")
        return None, None, None

    # Create output directory structure
    output_base_dir = Path("OUTPUT") / "AUDIO_TRANSLATED"
    output_folder_path = output_base_dir / file_name
    output_folder_path.mkdir(parents=True, exist_ok=True)

    return file_path, file_type, output_folder_path


# Function to transcribe audio using Open AI
def transcribe_audio(audio_path, output_text_file):
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print("Transcribing using OpenAI...")

    with open(audio_path, "rb") as audio_file:
        # response = client.audio.transcriptions.create(model="whisper-1", file=audio_file, response_format="text")
        # response = client.audio.transcriptions.create(model="gpt-4o-transcribe", file=audio_file, response_format="text")
        response = client.audio.transcriptions.create(model="gpt-4o-mini-transcribe", file=audio_file, response_format="text")

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

# Function to generate audio using Open AI
def generate_audio_with_openai_tts(input_text_file, output_audio_file, voice):
    with open(input_text_file, "r", encoding="utf-8") as f:
        text = f.read()

    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    print("Generating English audio using OpenAI...")

    # Generate speech using OpenAI's TTS API
    response = client.audio.speech.create(
        # model="tts-1",
        model="gpt-4o-mini-tts",
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
    input_file_path, file_type, output_folder_path = select_input_file()
    if not input_file_path:
        return

    # Define output file paths
    audio_org_path = output_folder_path / "audio_org.mp3"
    script_org_path = output_folder_path / "script_org.txt"
    script_trans_path = output_folder_path / "script_trans.txt"
    audio_trans_path = output_folder_path / "audio_trans.mp3"

    if file_type == 'video':
        print(f"Processing video file: {input_file_path}")
        video_org_path = output_folder_path / "video_org.mp4"
        video_org_muted_path = output_folder_path / "video_org_muted.mp4"
        
        # Copy original video
        print(f"Copying video to {video_org_path}")
        shutil.copy(input_file_path, video_org_path)

        # Create muted video
        print(f"Creating muted video {video_org_muted_path}")
        try:
             subprocess.run(['ffmpeg', '-i', str(input_file_path), '-an', '-c:v', 'copy', '-y', str(video_org_muted_path)],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error creating muted video with ffmpeg: {e}")
            print(f"Stderr: {e.stderr.decode()}")
            # Decide if we should stop or continue if muting fails
            # return # Uncomment to stop if muting fails
        except FileNotFoundError:
            print("Error: ffmpeg not found. Please ensure ffmpeg is installed and in your system's PATH.")
            return

        # Extract audio from video
        print(f"Extracting audio to {audio_org_path}")
        try:
            subprocess.run(['ffmpeg', '-i', str(input_file_path), '-vn', '-acodec', 'libmp3lame', '-y', str(audio_org_path)],
                           check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting audio with ffmpeg: {e}")
            print(f"Stderr: {e.stderr.decode()}")
            return
        except FileNotFoundError:
            print("Error: ffmpeg not found. Please ensure ffmpeg is installed and in your system's PATH.")
            return
            
        audio_path_for_transcription = audio_org_path

    elif file_type == 'audio':
        print(f"Processing audio file: {input_file_path}")
        # Copy original audio
        print(f"Copying audio to {audio_org_path}")
        shutil.copy(input_file_path, audio_org_path)
        audio_path_for_transcription = audio_org_path
        
    else:
        # This case should ideally not be reached due to checks in select_input_file
        print("Invalid file type determined.")
        return

    # Transcribe
    transcribe_audio(str(audio_path_for_transcription), str(script_org_path))
    
    # Translate
    translate_text(str(script_org_path), str(script_trans_path))
    
    # Generate Translated Audio
    generate_audio_with_openai_tts(str(script_trans_path), str(audio_trans_path), voice=OPENAI_TTS_VOICE_ID)
    
    # Or use ElevenLabs:
    # generate_audio_with_elevenlabs(str(script_trans_path), str(audio_trans_path))

    print("\nProcessing complete.")
    print(f"Output files are located in: {output_folder_path}")


if __name__ == "__main__":
    main()
