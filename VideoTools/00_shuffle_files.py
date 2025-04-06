import os
import random
import shutil
from tkinter import Tk, filedialog

def randomize_and_rename_files():
    # Initialize tkinter
    root = Tk()
    root.withdraw()  # Hide the main window
    
    # Ask user to select a folder
    folder_path = filedialog.askdirectory(title="Select folder to randomize and rename files")
    if not folder_path:
        print("No folder selected. Exiting.")
        return
    
    # Get all files in the folder
    try:
        files = [f for f in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, f))]
    except Exception as e:
        print(f"Error reading folder: {e}")
        return
    
    if not files:
        print("No files found in selected folder.")
        return
    
    # Create temp directory
    temp_dir = os.path.join(folder_path, "temp_rename")
    try:
        os.makedirs(temp_dir, exist_ok=True)
    except Exception as e:
        print(f"Error creating temp directory: {e}")
        return
    
    # Move all files to temp directory first
    for filename in files:
        try:
            shutil.move(
                os.path.join(folder_path, filename),
                os.path.join(temp_dir, filename)
            )
        except Exception as e:
            print(f"Error moving {filename} to temp directory: {e}")
            return
    
    # Shuffle the files randomly
    random.shuffle(files)
    
    # Rename files with sequential numbers and move back
    for i, filename in enumerate(files, start=1):
        # Get file extension
        name, ext = os.path.splitext(filename)
        
        # Create new filename with 3-digit number
        new_name = f"{i:03d}{ext}"
        
        # Construct paths
        old_path = os.path.join(temp_dir, filename)
        new_path = os.path.join(folder_path, new_name)
        
        # Rename the file
        try:
            shutil.move(old_path, new_path)
            print(f"Renamed: {filename} → {new_name}")
        except Exception as e:
            print(f"Error renaming {filename}: {e}")
    
    # Remove temp directory
    try:
        os.rmdir(temp_dir)
    except Exception as e:
        print(f"Warning: Could not remove temp directory: {e}")
    
    print(f"Successfully renamed {len(files)} files.")

if __name__ == "__main__":
    randomize_and_rename_files()