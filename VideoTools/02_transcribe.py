import os
import shutil
from pathlib import Path
import openai
import tkinter as tk
from tkinter import filedialog
import subprocess
from dotenv import load_dotenv
import sys

# Load environment variables
load_dotenv()

# Get API keys from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    print("Error: OPENAI_API_KEY not found in environment variables.")
    sys.exit(1)

# --- Constants ---
OUTPUT_BASE_DIR = "OUTPUT/TRANSCRIPTIONS"
VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
COPIED_VIDEO_FILENAME = "video_org.mp4"
COPIED_AUDIO_FILENAME = "audio_org.mp3"
TRANSCRIPT_FILENAME = "audio_script.txt"

# --- Functions ---

def select_media_file():
    """Opens a file dialog to select an audio or video file."""
    root = tk.Tk()
    root.withdraw()  # Hide the main tkinter window
    file_path = filedialog.askopenfilename(
        title="Select Audio or Video File",
        filetypes=(
            ("Media files", "*.mp4;*.avi;*.mov;*.mkv;*.wmv;*.flv;*.mp3;*.wav;*.m4a;*.aac;*.ogg;*.flac"),
            ("Video files", "*.mp4;*.avi;*.mov;*.mkv;*.wmv;*.flv"),
            ("Audio files", "*.mp3;*.wav;*.m4a;*.aac;*.ogg;*.flac"),
            ("All files", "*.*")
        )
    )
    if not file_path:
        print("No file selected.")
        return None
    return file_path

def transcribe_audio(audio_path, output_text_file):
    """Transcribes the audio file using OpenAI Whisper API."""
    try:
        client = openai.OpenAI(api_key=OPENAI_API_KEY)
        print(f"Transcribing '{audio_path}' using OpenAI...")

        with open(audio_path, "rb") as audio_file:
            # Use response_format="text" for plain text output
            response = client.audio.transcriptions.create(
                # model="whisper-1",
                # model="gpt-4o-transcribe",
                model="gpt-4o-mini-transcribe",
                file=audio_file,
                response_format="text"
            )

        # The response itself is the transcribed text when response_format="text"
        transcribed_text = response

        with open(output_text_file, "w", encoding="utf-8") as f:
            f.write(transcribed_text)

        print(f"Transcription saved successfully as '{output_text_file}'")
        return True
    except openai.APIError as e:
        print(f"OpenAI API returned an API Error: {e}")
    except openai.APIConnectionError as e:
        print(f"Failed to connect to OpenAI API: {e}")
    except openai.RateLimitError as e:
        print(f"OpenAI API request exceeded rate limit: {e}")
    except FileNotFoundError:
        print(f"Error: Audio file not found at '{audio_path}'")
    except Exception as e:
        print(f"An unexpected error occurred during transcription: {e}")
    return False

def extract_audio_from_video(video_path, output_audio_path):
    """Extracts audio from a video file using ffmpeg."""
    print(f"Extracting audio from '{video_path}' to '{output_audio_path}'...")
    try:
        # Use -y to overwrite output file without asking
        # Use -vn to disable video recording
        # Use -acodec libmp3lame for MP3 output
        # capture_output=True to suppress ffmpeg logs in console unless there's an error
        result = subprocess.run(
            ['ffmpeg', '-i', video_path, '-vn', '-acodec', 'libmp3lame', '-y', output_audio_path],
            check=True,  # Raise CalledProcessError on failure
            capture_output=True,
            text=True
        )
        print("Audio extraction successful.")
        return True
    except FileNotFoundError:
        print("Error: ffmpeg command not found. Make sure ffmpeg is installed and in your system's PATH.")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error during ffmpeg execution:")
        print(f"Command: {' '.join(e.cmd)}")
        print(f"Return code: {e.returncode}")
        print(f"Stderr: {e.stderr}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during audio extraction: {e}")
        return False

# --- Main Logic ---

def main():
    input_file_path = select_media_file()
    if not input_file_path:
        return # Exit if no file was selected

    file_dir, file_name_with_ext = os.path.split(input_file_path)
    file_name_no_ext, file_ext = os.path.splitext(file_name_with_ext)
    file_ext_lower = file_ext.lower()

    # Create output directory
    output_dir = os.path.join(OUTPUT_BASE_DIR, file_name_no_ext)
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory created/exists: '{output_dir}'")

    output_audio_path = os.path.join(output_dir, COPIED_AUDIO_FILENAME)
    output_script_path = os.path.join(output_dir, TRANSCRIPT_FILENAME)
    audio_source_for_transcription = None

    # Process based on file type
    if file_ext_lower in VIDEO_EXTENSIONS:
        print(f"Processing video file: '{file_name_with_ext}'")
        output_video_path = os.path.join(output_dir, COPIED_VIDEO_FILENAME)

        # 1. Copy original video
        try:
            shutil.copy2(input_file_path, output_video_path) # copy2 preserves metadata
            print(f"Video copied to '{output_video_path}'")
        except Exception as e:
            print(f"Error copying video file: {e}")
            return # Stop processing if copy fails

        # 2. Extract audio
        if extract_audio_from_video(input_file_path, output_audio_path):
            audio_source_for_transcription = output_audio_path
        else:
            print("Failed to extract audio. Cannot proceed with transcription.")
            return # Stop if audio extraction fails

    elif file_ext_lower in AUDIO_EXTENSIONS:
        print(f"Processing audio file: '{file_name_with_ext}'")
        # 1. Copy original audio
        try:
            shutil.copy2(input_file_path, output_audio_path) # copy2 preserves metadata
            print(f"Audio copied to '{output_audio_path}'")
            audio_source_for_transcription = output_audio_path
        except Exception as e:
            print(f"Error copying audio file: {e}")
            return # Stop processing if copy fails

    else:
        print(f"Error: Unsupported file type '{file_ext}'. Please select a valid video or audio file.")
        return

    # 3. Transcribe the audio (if source is determined)
    if audio_source_for_transcription:
        transcribe_audio(audio_source_for_transcription, output_script_path)
    else:
        print("Error: Could not determine audio source for transcription.")


if __name__ == "__main__":
    main()