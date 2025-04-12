import tkinter as tk
from tkinter import filedialog
import os
import re
import subprocess
import tempfile

def select_folder():
    """Opens a dialog to select a folder."""
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    folder_path = filedialog.askdirectory(title="Select Folder Containing Videos")
    root.destroy()
    return folder_path

def get_next_output_filename(target_dir):
    """Determines the next output filename based on existing files in the target directory."""
    # No need to create the directory, as it's the user-selected input folder which must exist.
    # We just need to check its contents.


    existing_files = [f for f in os.listdir(target_dir) if re.match(r"\d+_output\.mp4", f)]
    if not existing_files:
        return os.path.join(target_dir, "001_output.mp4")

    # Find the highest existing number
    max_num = 0
    for f in existing_files:
        match = re.match(r"(\d+)_output\.mp4", f)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    next_num = max_num + 1
    # Ensure the output path is absolute for ffmpeg if needed, though relative should work from CWD
    # Use the original target_dir path provided by the user
    return os.path.join(target_dir, f"{next_num:03d}_output.mp4")

def stitch_videos_ffmpeg(folder_path, output_filename):
    """Finds video files, creates a list file, and uses ffmpeg to concatenate."""
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.ts') # Added .ts common for segments
    video_files = []
    absolute_folder_path = os.path.abspath(folder_path) # Use absolute paths for ffmpeg list

    # Ensure files are sorted correctly (e.g., numerically or alphabetically)
    try:
        # Attempt natural sort if possible (requires natsort package, optional)
        import natsort
        file_list = natsort.natsorted(os.listdir(absolute_folder_path))
    except ImportError:
        # Fallback to standard sort
        file_list = sorted(os.listdir(absolute_folder_path))

    for filename in file_list:
        if filename.lower().endswith(video_extensions):
            full_path = os.path.join(absolute_folder_path, filename)
            # Ffmpeg concat demuxer requires specific formatting in the list file
            # Need to escape special characters if any in filenames for the list file
            escaped_path = full_path.replace("'", "'\\''")
            video_files.append(f"file '{escaped_path}'")


    if not video_files:
        print("No video files found in the selected folder.")
        return False

    print(f"Found {len(video_files)} video files to stitch:")
    for vf_line in video_files:
         # Extract filename for printing
         match = re.search(r"file '(.*?)'", vf_line)
         if match:
             print(f"- {os.path.basename(match.group(1))}")


    # Create a temporary file to list the videos for ffmpeg's concat demuxer
    list_file_content = "\n".join(video_files)
    temp_list_file = None
    try:
        # Using NamedTemporaryFile to ensure it's cleaned up
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt', encoding='utf-8') as temp_f:
            temp_list_file = temp_f.name
            temp_f.write(list_file_content)
            print(f"\nTemporary list file created at: {temp_list_file}") # For debugging

        # Construct the ffmpeg command
        # -f concat: Use the concat demuxer
        # -safe 0: Allow unsafe file paths (needed if paths are complex, though absolute paths help)
        # -i temp_list_file: Input is the list file
        # -c copy: Copy codecs without re-encoding (fastest, but requires compatible streams)
        # output_filename: The final output file
        command = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', temp_list_file,
            '-c', 'copy',
            output_filename
        ]

        print(f"\nExecuting ffmpeg command:")
        print(" ".join(command)) # Print the command for clarity

        # Execute the command
        result = subprocess.run(command, capture_output=True, text=True, check=False) # check=False to handle errors manually

        if result.returncode == 0:
            print(f"\nSuccessfully stitched videos to: {output_filename}")
            return True
        else:
            print(f"\nError during ffmpeg execution (return code: {result.returncode}):")
            print("ffmpeg stdout:")
            print(result.stdout)
            print("ffmpeg stderr:")
            print(result.stderr)
            return False

    except FileNotFoundError:
        print("\nError: 'ffmpeg' command not found. Please ensure ffmpeg is installed and in your system's PATH.")
        return False
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
        return False
    finally:
        # Clean up the temporary list file
        if temp_list_file and os.path.exists(temp_list_file):
            try:
                os.remove(temp_list_file)
                # print(f"Temporary list file {temp_list_file} removed.") # Optional: confirmation
            except OSError as e:
                print(f"Warning: Could not remove temporary file {temp_list_file}: {e}")


if __name__ == "__main__":
    input_folder = select_folder()
    if input_folder:
        print(f"Selected folder: {input_folder}")
        # Define the path for the OUTPUT subdirectory within the selected folder
        output_subdir = "OUTPUT"
        output_directory_path = os.path.join(input_folder, output_subdir)

        # Create the OUTPUT subdirectory if it doesn't exist
        os.makedirs(output_directory_path, exist_ok=True)

        # Get the next output filename within the OUTPUT subdirectory
        output_file = get_next_output_filename(output_directory_path)
        print(f"Output file will be: {output_file}")
        stitch_videos_ffmpeg(input_folder, output_file)
    else:
        print("No folder selected.")