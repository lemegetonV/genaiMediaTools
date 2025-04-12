import tkinter as tk
from tkinter import filedialog, simpledialog, messagebox
import os
import shutil
# MoviePy imports are still needed for get_video_duration
from moviepy import VideoFileClip 
# Removed ImageClip, CompositeVideoClip, ColorClip as they are no longer used for image->video
from PIL import Image
import logging
import time
import traceback
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess # Re-added for FFmpeg

# --- Configuration ---
TARGET_VIDEO_WIDTH = 1920
TARGET_VIDEO_HEIGHT = 1080
TARGET_ASPECT_RATIO = TARGET_VIDEO_WIDTH / TARGET_VIDEO_HEIGHT
IMAGE_VIDEO_DURATION = 7  # seconds
WORKING_SUBDIR = "WORKING"
IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff')
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv')
# Number of parallel processes to use (0 = auto-detect based on CPU cores)
PARALLEL_PROCESSES = 0 
# Video encoding settings for FFmpeg
VIDEO_FPS = 25 # Use 25 FPS for smoother Ken Burns effect
VIDEO_PRESET = "veryfast" # FFmpeg preset (ultrafast might reduce quality too much with zoom)
ZOOM_SPEED = 0.001 # Speed factor for Ken Burns zoom (smaller is slower)
MAX_ZOOM = 1.2 # Maximum zoom factor (e.g., 1.2 means zoom in by 20%)

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler_file = logging.FileHandler("media_organizer.log", mode='a')
log_handler_file.setFormatter(log_formatter)
log_handler_console = logging.StreamHandler()
log_handler_console.setFormatter(log_formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
# Clear existing handlers to avoid duplicates
if logger.handlers:
    for handler in logger.handlers:
        logger.removeHandler(handler)
logger.addHandler(log_handler_file)
logger.addHandler(log_handler_console)


# --- Helper Functions ---

def get_video_duration(filepath):
    """Gets the duration of a video file."""
    clip = None
    try:
        clip = VideoFileClip(filepath)
        duration = clip.duration
        return duration
    except Exception as e:
        logger.error(f"Error getting duration for {filepath}: {e}\n{traceback.format_exc()}")
        return None
    finally:
        if clip:
            try:
                clip.close()
            except Exception as close_e:
                logger.error(f"Error closing video clip for {filepath}: {close_e}")


def create_folder_if_not_exists(folder_path):
    """Creates a folder if it doesn't exist."""
    if not os.path.exists(folder_path):
        try:
            os.makedirs(folder_path)
            logger.info(f"Created folder: {folder_path}")
        except OSError as e:
            logger.error(f"Error creating folder {folder_path}: {e}")
            return False
    return True

# Removed create_video_from_image_optimized function

def create_video_with_ffmpeg_kenburns(image_path, output_path):
    """Creates a video from an image using direct FFmpeg command with Ken Burns effect."""
    try:
        # Calculate zoom duration in frames
        duration_frames = int(IMAGE_VIDEO_DURATION * VIDEO_FPS)

        # Build the complex filter string for scaling, padding, and zoompan
        # 1. Scale the image slightly larger than the target to allow zooming in without black borders appearing at edges
        #    We need to maintain aspect ratio while ensuring it covers the MAX_ZOOM area.
        #    Scale to fit within TARGET_WIDTH*MAX_ZOOM x TARGET_HEIGHT*MAX_ZOOM, then pad to that size.
        # 2. Apply zoompan
        # Build the complex filter string for scaling, padding, intermediate scaling (for smoothness), and zoompan
        # 1. Scale the image slightly larger than the target to allow zooming in without black borders appearing at edges
        # 2. Pad to the max zoom dimensions
        # 3. Intermediate upscale significantly to improve zoompan smoothness
        # 4. Apply zoompan
        filter_complex = (
            f"[0:v]scale=w='if(gte(iw/ih,{TARGET_ASPECT_RATIO}),{TARGET_VIDEO_WIDTH}*{MAX_ZOOM},-2)':h='if(lt(iw/ih,{TARGET_ASPECT_RATIO}),{TARGET_VIDEO_HEIGHT}*{MAX_ZOOM},-2)'," # Scale maintaining aspect ratio to cover zoomed area
            f"pad=w={TARGET_VIDEO_WIDTH}*{MAX_ZOOM}:h={TARGET_VIDEO_HEIGHT}*{MAX_ZOOM}:x='(ow-iw)/2':y='(oh-ih)/2':color=black," # Pad to the max zoom dimensions
            f"setsar=1," # Ensure square pixels
            f"scale=8000:-1," # Intermediate upscale for smoothness
            f"zoompan=z='min(zoom+{ZOOM_SPEED},{MAX_ZOOM})':" # Zoom expression
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':" # Center the zoom
            f"d={duration_frames}:" # Duration in frames
            f"s={TARGET_VIDEO_WIDTH}x{TARGET_VIDEO_HEIGHT}:" # Output size
            f"fps={VIDEO_FPS}[v]" # Output frame rate
        )

        # Build the full ffmpeg command
        cmd = [
            'ffmpeg',
            '-y',  # Overwrite output file if it exists
            '-loop', '1',  # Loop the input image
            '-i', image_path,  # Input image path
            '-filter_complex', filter_complex, # Apply the Ken Burns effect
            '-map', '[v]', # Map the video stream from the filter complex
            '-t', str(IMAGE_VIDEO_DURATION),  # Set the exact duration
            '-c:v', 'libx264',  # Video codec
            '-preset', VIDEO_PRESET,  # Encoding speed/quality preset
            '-tune', 'stillimage', # Optimize for static source
            '-pix_fmt', 'yuv420p',  # Pixel format for compatibility
            '-r', str(VIDEO_FPS), # Set output frame rate again (belt and suspenders)
            '-movflags', '+faststart', # Optimize for web streaming
            '-an',  # No audio
            output_path  # Output file path
        ]

        logger.info(f"Running FFmpeg for {image_path}: {' '.join(cmd)}")

        # Run the command
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0 # Hide console window on Windows
        )
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg error creating video for {image_path}. Return code: {process.returncode}")
            logger.error(f"FFmpeg stderr:\n{stderr.decode(errors='ignore')}")
            # Attempt to log stdout as well, might contain useful info
            if stdout:
                 logger.error(f"FFmpeg stdout:\n{stdout.decode(errors='ignore')}")
            return False
        else:
            logger.info(f"Successfully created video with Ken Burns effect: {output_path}")
            return True

    except FileNotFoundError:
         logger.critical("FFmpeg command not found. Please ensure FFmpeg is installed and in your system's PATH.")
         # We should probably stop the whole process here if ffmpeg isn't found
         raise # Re-raise the exception to stop the script
    except Exception as e:
        logger.error(f"Error creating video from {image_path} with FFmpeg Ken Burns: {e}\n{traceback.format_exc()}")
        return False


def process_image_to_video(args):
    """Process a single image to video using FFmpeg Ken Burns (for parallel processing)."""
    img_path, output_path = args
    try:
        # Use the FFmpeg Ken Burns method
        success = create_video_with_ffmpeg_kenburns(img_path, output_path)
        return img_path, success
    except Exception as e:
        # Log error from the worker process
        # Note: Logging setup might need adjustments for multiprocessing if issues arise
        logger.error(f"Error in worker process for {img_path}: {e}\n{traceback.format_exc()}")
        return img_path, False


# --- Main Logic ---

def main():
    root = tk.Tk()
    root.withdraw()  # Hide the main tkinter window

    logger.info("Script started.")

    # Check for FFmpeg before starting
    try:
        subprocess.run(['ffmpeg', '-version'], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        logger.info("FFmpeg found.")
    except (FileNotFoundError, subprocess.CalledProcessError):
        logger.critical("FFmpeg command not found or failed to execute. Please ensure FFmpeg is installed and in your system's PATH.")
        messagebox.showerror("Error", "FFmpeg not found. Please install FFmpeg and ensure it's in your system's PATH to use the image-to-video feature.")
        return # Exit if FFmpeg is not available

    # 1. Select Source Folder
    source_folder = filedialog.askdirectory(title="Select Folder Containing Media")
    if not source_folder:
        messagebox.showinfo("Cancelled", "Operation cancelled.")
        logger.info("Operation cancelled by user (folder selection).")
        return
    logger.info(f"Selected source folder: {source_folder}")

    # Check if WORKING subfolder exists, create if not
    working_folder_base = os.path.join(source_folder, WORKING_SUBDIR)
    if not os.path.isdir(working_folder_base):
        logger.warning(f"'{WORKING_SUBDIR}' not found in source. Attempting to create.")
        if not create_folder_if_not_exists(working_folder_base):
            messagebox.showerror("Error", f"Could not create subfolder '{WORKING_SUBDIR}' in '{source_folder}'. Please check permissions.")
            logger.error(f"Failed to create '{WORKING_SUBDIR}' folder.")
            return
        else:
            logger.info(f"Successfully created missing '{WORKING_SUBDIR}' folder.")

    # 2. Get Destination Folder Name
    dest_folder_name = simpledialog.askstring("Input", f"Enter a name for the new folder inside '{WORKING_SUBDIR}':", parent=root)
    if not dest_folder_name:
        messagebox.showinfo("Cancelled", "Operation cancelled.")
        logger.info("Operation cancelled by user (folder name input).")
        return

    # Sanitize folder name
    original_name = dest_folder_name
    dest_folder_name = "".join(c for c in dest_folder_name if c.isalnum() or c in (' ', '_', '-')).strip()
    if not dest_folder_name:
        messagebox.showerror("Error", f"Invalid folder name entered: '{original_name}'. Please use letters, numbers, spaces, underscores, or hyphens.")
        logger.error(f"Invalid destination folder name provided: '{original_name}'")
        return
    logger.info(f"User entered destination folder name: {dest_folder_name}")

    # 3. Create Destination Folders
    dest_base_path = os.path.join(working_folder_base, dest_folder_name)
    folders_to_create = {
        "images": os.path.join(dest_base_path, "00_IMAGES"),
        "img_vids": os.path.join(dest_base_path, "01_IMAGES_VIDS"),
        "vids_10s": os.path.join(dest_base_path, "02_VIDS_10s"),
        "vids_20s": os.path.join(dest_base_path, "03_VIDS_20s"),
        "vids_30s": os.path.join(dest_base_path, "04_VIDS_30s"),
        "vids_long": os.path.join(dest_base_path, "05_VIDS_LONG"),
    }

    # Create base destination folder first
    if os.path.exists(dest_base_path):
        logger.warning(f"Destination base folder '{dest_base_path}' already exists. Files might be overwritten or added.")
    elif not create_folder_if_not_exists(dest_base_path):
        messagebox.showerror("Error", f"Failed to create base destination folder: {dest_base_path}. Check permissions.")
        logger.error(f"Failed to create base destination folder: {dest_base_path}")
        return

    # Create subfolders
    all_folders_created = True
    for key, path in folders_to_create.items():
        if not create_folder_if_not_exists(path):
            all_folders_created = False
            logger.error(f"Failed to create subfolder: {path}")

    if not all_folders_created:
        messagebox.showerror("Error", "Failed to create some necessary subfolders. Check logs (media_organizer.log) and permissions.")
        return

    # 4. Process Files
    moved_images = []
    processed_files = 0
    errors_occurred = False
    start_time = time.time()

    logger.info(f"Scanning source folder for files: {source_folder}")
    try:
        items_in_source = os.listdir(source_folder)
    except Exception as e:
        messagebox.showerror("Error", f"Could not read source folder: {source_folder}\n{e}")
        logger.error(f"Failed to list directory: {source_folder}: {e}")
        return

    items_to_process = [
        item for item in items_in_source
        if os.path.isfile(os.path.join(source_folder, item))
    ]
    logger.info(f"Found {len(items_to_process)} files to process in the source folder.")

    for item in items_to_process:
        source_item_path = os.path.join(source_folder, item)
        _, ext = os.path.splitext(item)
        ext = ext.lower()

        # --- Move Images ---
        if ext in IMAGE_EXTENSIONS:
            dest_img_path = os.path.join(folders_to_create["images"], item)
            try:
                logger.info(f"Moving image: {source_item_path} -> {dest_img_path}")
                shutil.move(source_item_path, dest_img_path)
                logger.info(f"Moved image: {item} to {folders_to_create['images']}")
                moved_images.append(dest_img_path)
                processed_files += 1
            except Exception as e:
                logger.error(f"Error moving image {item}: {e}\n{traceback.format_exc()}")
                errors_occurred = True

        # --- Move Videos ---
        elif ext in VIDEO_EXTENSIONS:
            duration = get_video_duration(source_item_path)
            if duration is None:
                logger.warning(f"Could not get duration for video {item}. Skipping move.")
                errors_occurred = True
                continue

            target_folder_key = None
            if duration <= 10:
                target_folder_key = "vids_10s"
            elif duration <= 20:
                target_folder_key = "vids_20s"
            elif duration <= 30:
                target_folder_key = "vids_30s"
            else:
                target_folder_key = "vids_long"

            dest_vid_path = os.path.join(folders_to_create[target_folder_key], item)
            try:
                logger.info(f"Moving video: {source_item_path} -> {dest_vid_path}")
                shutil.move(source_item_path, dest_vid_path)
                logger.info(f"Moved video: {item} (Duration: {duration:.2f}s) to {folders_to_create[target_folder_key]}")
                processed_files += 1
            except Exception as e:
                logger.error(f"Error moving video {item}: {e}\n{traceback.format_exc()}")
                errors_occurred = True

    # 5. Convert Moved Images to Videos using parallel processing with FFmpeg
    if moved_images:
        logger.info(f"Starting parallel image-to-video conversion for {len(moved_images)} images using FFmpeg...")

        # Prepare the tasks
        conversion_tasks = []
        for img_path in moved_images:
            base_name, _ = os.path.splitext(os.path.basename(img_path))
            output_video_name = f"{base_name}.mp4"
            output_video_path = os.path.join(folders_to_create["img_vids"], output_video_name)

            # Skip if video already exists
            if os.path.exists(output_video_path):
                logger.warning(f"Output video already exists, skipping: {output_video_path}")
                continue

            conversion_tasks.append((img_path, output_video_path))

        if not conversion_tasks:
             logger.info("No new images to convert.")
        else:
            # Determine the number of processes to use
            num_processes = PARALLEL_PROCESSES
            if num_processes <= 0:
                # Auto-detect: Use CPU count - 1 (leave one core free for system)
                num_processes = max(1, multiprocessing.cpu_count() - 1)
            logger.info(f"Using {num_processes} parallel processes for FFmpeg video conversion")

            # Process the images in parallel
            img_video_count = 0
            conversion_errors = 0

            # Show a progress dialog
            progress_window = tk.Toplevel(root)
            progress_window.title("Converting Images to Videos (FFmpeg)")
            progress_window.geometry("400x150")
            progress_window.resizable(False, False)

            # Add progress label
            progress_label = tk.Label(progress_window, text=f"Converting 0/{len(conversion_tasks)} images...")
            progress_label.pack(pady=10)

            # Add progress bar
            progress_var = tk.DoubleVar()
            progress_bar = tk.Scale(progress_window, variable=progress_var, orient="horizontal",
                                   length=350, from_=0, to=100, state="disabled")
            progress_bar.pack(pady=10)

            # Add status label
            status_label = tk.Label(progress_window, text="Starting conversion...")
            status_label.pack(pady=10)

            # Update the UI
            progress_window.update()

            # Process the images in parallel
            with ProcessPoolExecutor(max_workers=num_processes) as executor:
                # Submit all tasks
                future_to_path = {executor.submit(process_image_to_video, task): task[0] for task in conversion_tasks}

                # Process results as they complete
                for i, future in enumerate(as_completed(future_to_path)):
                    try:
                        img_path, success = future.result()
                        if success:
                            img_video_count += 1
                        else:
                            conversion_errors += 1
                            errors_occurred = True
                    except Exception as exc:
                         # Catch errors from the future itself (e.g., if the worker process died)
                         logger.error(f"Error processing future for task {future_to_path[future]}: {exc}")
                         conversion_errors += 1
                         errors_occurred = True
                         img_path = future_to_path[future] # Get path for status update

                    # Update progress
                    progress_percent = (i + 1) / len(conversion_tasks) * 100
                    progress_var.set(progress_percent)
                    progress_label.config(text=f"Converting {i+1}/{len(conversion_tasks)} images...")
                    status_label.config(text=f"Processed: {os.path.basename(img_path)}")
                    progress_window.update()

            # Close progress window
            progress_window.destroy()
    else:
        img_video_count = 0
        conversion_errors = 0
        logger.info("No images to convert to videos.")

    end_time = time.time()
    duration_secs = end_time - start_time

    logger.info("Processing complete.")
    completion_message = (
        f"Processing finished.\n\n"
        f"Files processed/moved: {processed_files}\n"
        f"Videos created from images: {img_video_count}\n"
    )

    if conversion_errors > 0:
        completion_message += f"Failed conversions: {conversion_errors}\n\n"

    completion_message += (
        f"Results saved in:\n{dest_base_path}\n\n"
        f"Total time: {duration_secs:.2f} seconds."
    )

    if errors_occurred:
        completion_message += "\n\nNOTE: Some errors occurred. Please check the log file 'media_organizer.log' in the project directory for details."
        messagebox.showwarning("Completed with Errors", completion_message)
        logger.warning("Processing completed with errors.")
    else:
        messagebox.showinfo("Success", completion_message)
        logger.info("Processing completed successfully.")


if __name__ == "__main__":
    # Ensure multiprocessing works correctly when packaged (e.g., with PyInstaller)
    multiprocessing.freeze_support()
    try:
        main()
    except Exception as e:
        # Catch potential critical errors like FFmpeg not found after the initial check
        if isinstance(e, FileNotFoundError):
             logger.critical(f"FFmpeg command failed during execution. Ensure it's correctly installed and in PATH.")
             messagebox.showerror("Critical Error", f"FFmpeg failed during execution. Please check installation and PATH.\nError: {e}")
        else:
             logger.critical(f"An unexpected critical error occurred: {e}\n{traceback.format_exc()}")
             messagebox.showerror("Critical Error", f"A critical error occurred:\n{e}\n\nPlease check 'media_organizer.log'.")