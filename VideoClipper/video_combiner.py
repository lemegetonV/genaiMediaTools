import tkinter as tk
from tkinter import filedialog, messagebox
import os
import random
import shutil
import subprocess
import re
import logging
import time

# --- Configuration ---
TARGET_SUBFOLDER = "01_IMAGES_VIDS"
OUTPUT_PREFIX = "combined_video_"
OUTPUT_EXTENSION = ".mp4"
TEMP_RENAME_DIR = "temp_rename_combiner"
FFMPEG_CONCAT_LIST_FILE = "ffmpeg_concat_list.txt"

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
# Use a different log file for this script
log_handler_file = logging.FileHandler("video_combiner.log", mode='a') 
log_handler_file.setFormatter(log_formatter)
log_handler_console = logging.StreamHandler()
log_handler_console.setFormatter(log_formatter)

logger = logging.getLogger(__name__) # Use specific logger name
logger.setLevel(logging.INFO)
# Clear existing handlers to avoid duplicates if script is run multiple times in same session
if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)
logger.addHandler(log_handler_file)
logger.addHandler(log_handler_console)

# --- Helper Functions ---

def check_ffmpeg():
    """Checks if ffmpeg is installed and accessible."""
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        logger.info("FFmpeg found.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.critical("FFmpeg command not found or failed to execute.")
        messagebox.showerror("Error", "FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH.")
        return False

def randomize_and_rename_videos(target_folder):
    """Randomizes and renames video files within the target folder."""
    logger.info(f"Starting randomization and renaming in: {target_folder}")
    
    # Get video files (assuming common video extensions)
    video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')
    try:
        files = [f for f in os.listdir(target_folder) 
                 if os.path.isfile(os.path.join(target_folder, f)) and f.lower().endswith(video_extensions)]
    except Exception as e:
        logger.error(f"Error reading target folder {target_folder}: {e}")
        messagebox.showerror("Error", f"Could not read files from '{TARGET_SUBFOLDER}'.\nError: {e}")
        return None # Indicate failure

    if not files:
        logger.warning(f"No video files found in {target_folder}.")
        messagebox.showwarning("Warning", f"No video files found in '{TARGET_SUBFOLDER}'.")
        return [] # Return empty list, maybe concatenation shouldn't proceed

    # Create temp directory inside the target folder
    temp_dir = os.path.join(target_folder, TEMP_RENAME_DIR)
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception as e:
        logger.error(f"Error creating temp directory {temp_dir}: {e}")
        messagebox.showerror("Error", f"Could not create temporary directory.\nError: {e}")
        return None

    # Move all files to temp directory first
    logger.info(f"Moving {len(files)} files to temporary directory: {temp_dir}")
    for filename in files:
        try:
            shutil.move(
                os.path.join(target_folder, filename),
                os.path.join(temp_dir, filename)
            )
        except Exception as e:
            logger.error(f"Error moving {filename} to temp directory: {e}")
            messagebox.showerror("Error", f"Error moving files for renaming.\nError: {e}")
            # Attempt cleanup? Maybe too risky.
            return None
            
    # Shuffle the files randomly
    random.shuffle(files)
    logger.info("Shuffled file order.")

    renamed_files_paths = []
    # Rename files with sequential numbers and move back
    logger.info("Renaming and moving files back...")
    for i, filename in enumerate(files, start=1):
        # Get file extension
        _ , ext = os.path.splitext(filename)
        
        # Create new filename with 3-digit number
        new_name = f"{i:03d}{ext}"
        
        # Construct paths
        old_path = os.path.join(temp_dir, filename)
        new_path = os.path.join(target_folder, new_name)
        
        # Rename the file by moving
        try:
            shutil.move(old_path, new_path)
            logger.debug(f"Renamed: {filename} -> {new_name}")
            renamed_files_paths.append(new_path) # Store full path of renamed file
        except Exception as e:
            logger.error(f"Error renaming {filename} to {new_name}: {e}")
            messagebox.showerror("Error", f"Error renaming file '{filename}'.\nError: {e}")
            return None # Indicate failure

    # Remove temp directory
    try:
        os.rmdir(temp_dir)
        logger.info(f"Removed temporary directory: {temp_dir}")
    except Exception as e:
        # This is not critical, just log a warning
        logger.warning(f"Could not remove temp directory {temp_dir}: {e}")
    
    logger.info(f"Successfully renamed {len(files)} files.")
    return sorted(renamed_files_paths) # Return sorted list of full paths

def get_next_output_filename(output_folder):
    """Finds the next available output filename (e.g., combined_video_00X.mp4)."""
    logger.info(f"Checking for existing output files in: {output_folder}")
    max_num = 0
    found = False
    try:
        for filename in os.listdir(output_folder):
            if filename.startswith(OUTPUT_PREFIX) and filename.endswith(OUTPUT_EXTENSION):
                match = re.search(r'(\d+)', filename)
                if match:
                    num = int(match.group(1))
                    max_num = max(max_num, num)
                    found = True
    except Exception as e:
        logger.error(f"Error scanning output folder {output_folder}: {e}")
        messagebox.showerror("Error", f"Could not scan output folder for existing files.\nError: {e}")
        return None

    next_num = max_num + 1
    next_filename = f"{OUTPUT_PREFIX}{next_num:03d}{OUTPUT_EXTENSION}"
    output_path = os.path.join(output_folder, next_filename)
    logger.info(f"Next output filename determined as: {output_path}")
    return output_path

def concatenate_videos(video_files, output_path):
    """Concatenates a list of video files using FFmpeg concat demuxer."""
    if not video_files:
        logger.warning("No video files provided for concatenation.")
        return False

    logger.info(f"Starting concatenation of {len(video_files)} videos to: {output_path}")
    
    # Create the temporary list file in the same directory as the output for simplicity
    list_file_path = os.path.join(os.path.dirname(output_path), FFMPEG_CONCAT_LIST_FILE)
    
    try:
        with open(list_file_path, 'w') as f:
            for video_path in video_files:
                # FFmpeg requires forward slashes and proper escaping
                safe_path = video_path.replace("\\", "/") 
                f.write(f"file '{safe_path}'\n")
        logger.info(f"Created FFmpeg concat list file: {list_file_path}")

        # Build the FFmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-f', 'concat', # Use the concat demuxer
            '-safe', '0', # Allow unsafe file paths (needed for absolute paths)
            '-i', list_file_path, # Input list file
            '-c', 'copy', # Copy streams without re-encoding (fast)
            output_path # Output file path
        ]

        logger.info(f"Running FFmpeg concatenation: {' '.join(cmd)}")

        # Run the command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg concatenation failed. Return code: {process.returncode}")
            logger.error(f"FFmpeg stderr:\n{stderr.decode(errors='ignore')}")
            if stdout:
                 logger.error(f"FFmpeg stdout:\n{stdout.decode(errors='ignore')}")
            messagebox.showerror("Error", f"FFmpeg failed during video concatenation.\nCheck logs for details.")
            return False
        else:
            logger.info(f"Successfully concatenated videos to: {output_path}")
            return True

    except Exception as e:
        logger.error(f"Error during video concatenation process: {e}")
        messagebox.showerror("Error", f"An error occurred during concatenation.\nError: {e}")
        return False
    finally:
        # Clean up the temporary list file
        if os.path.exists(list_file_path):
            try:
                os.remove(list_file_path)
                logger.info(f"Removed temporary list file: {list_file_path}")
            except Exception as e:
                logger.warning(f"Could not remove temporary list file {list_file_path}: {e}")

# --- Main Logic ---

def main():
    if not check_ffmpeg():
        return # Exit if FFmpeg is not available

    root = tk.Tk()
    root.withdraw()  # Hide the main tkinter window

    logger.info("Video Combiner Script started.")

    # 1. Select Root Folder
    root_folder = filedialog.askdirectory(title="Select Root Folder Containing '01_IMAGES_VIDS'")
    if not root_folder:
        messagebox.showinfo("Cancelled", "Operation cancelled.")
        logger.info("Operation cancelled by user (folder selection).")
        return
    logger.info(f"Selected root folder: {root_folder}")

    # 2. Verify and get target subfolder path
    target_folder_path = os.path.join(root_folder, TARGET_SUBFOLDER)
    if not os.path.isdir(target_folder_path):
        logger.error(f"Target subfolder '{TARGET_SUBFOLDER}' not found in '{root_folder}'.")
        messagebox.showerror("Error", f"The required subfolder '{TARGET_SUBFOLDER}' was not found in the selected directory.")
        return
    logger.info(f"Found target subfolder: {target_folder_path}")

    # 3. Randomize and Rename files in the target subfolder
    start_time = time.time()
    renamed_video_paths = randomize_and_rename_videos(target_folder_path)

    if renamed_video_paths is None:
        logger.error("Renaming process failed. Aborting concatenation.")
        # Error message already shown by the function
        return 
    elif not renamed_video_paths:
         logger.warning("No videos found or renamed. Skipping concatenation.")
         messagebox.showinfo("Finished", "No video files were found to rename or combine.")
         return

    # 4. Determine Output Path
    output_video_path = get_next_output_filename(root_folder)
    if not output_video_path:
        logger.error("Failed to determine output filename. Aborting.")
        # Error message already shown by the function
        return

    # 5. Concatenate Videos
    logger.info("Proceeding to concatenate renamed videos.")
    success = concatenate_videos(renamed_video_paths, output_video_path)

    end_time = time.time()
    duration_secs = end_time - start_time

    if success:
        logger.info(f"Successfully completed in {duration_secs:.2f} seconds.")
        messagebox.showinfo("Success", f"Successfully randomized, renamed, and combined videos.\n\nOutput saved as:\n{output_video_path}\n\nTotal time: {duration_secs:.2f} seconds.")
    else:
        logger.error(f"Video combination process failed after {duration_secs:.2f} seconds.")
        # Error messages should have been shown by concatenate_videos
        messagebox.showerror("Failed", "Video combination process failed. Please check the log file 'video_combiner.log' for details.")


if __name__ == "__main__":
    main()