import os
import shutil
import subprocess
import fnmatch
from pathlib import Path

# Blocklist of system directories to protect
SYSTEM_DIRS = [
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    "/bin",
    "/usr",
    "/etc",
]

def is_safe_path(path_str):
    """
    Checks if a path is safe to operate on.
    Returns True if safe, False if it targets a system directory.
    """
    if not path_str:
        return True
    
    try:
        path = Path(path_str).resolve()
        for sys_dir in SYSTEM_DIRS:
            # Check if likely a system path (simple string check + resolve)
            # On Windows, drive letters matter, so we accept case-insensitivity
            if str(path).lower().startswith(str(Path(sys_dir).resolve()).lower()):
                return False
                
        # Additional check: Do not allow operations on the script itself or parent dirs generally
        # But for this playground, we just strictly block defined system dirs.
        return True
    except Exception:
        return False

def find_files(file_type=None, source_path="."):
    """
    Finds files matching a type in a source path.
    """
    results = []
    source_path = source_path or "."
    
    if not os.path.exists(source_path):
        return f"Error: Source path '{source_path}' does not exist."

    print(f"Searching in: {os.path.abspath(source_path)}")
    
    for root, dirnames, filenames in os.walk(source_path):
        for filename in filenames:
            if file_type:
                if filename.lower().endswith(f".{file_type.lower()}"):
                     results.append(os.path.join(root, filename))
            else:
                results.append(os.path.join(root, filename))
                
    return results[:50] # Return top 50 to avoid flooding

def move_files(file_type, destination_path, source_path="."):
    """
    Moves files of a certain type to a destination.
    """
    if not destination_path:
        return "Error: Destination path required for move."
        
    source_path = source_path or "." 
    
    if not is_safe_path(source_path) or not is_safe_path(destination_path):
        return "Error: unsafe path detected."

    if not os.path.exists(destination_path):
        try:
            os.makedirs(destination_path)
        except OSError as e:
            return f"Error creating destination: {e}"

    moved_count = 0
    errors = []
    
    files_to_move = find_files(file_type, source_path)
    if isinstance(files_to_move, str): # Error message
        return files_to_move
        
    for file_path in files_to_move:
        if not is_safe_path(file_path):
            continue
            
        try:
            shutil.move(file_path, destination_path)
            moved_count += 1
        except Exception as e:
            errors.append(f"Failed to move {file_path}: {e}")
            
    return f"Moved {moved_count} files. Errors: {len(errors)}"

def delete_files(file_type, source_path="."):
    """
    Deletes files of a certain type.
    """
    source_path = source_path or "."
    
    if not is_safe_path(source_path):
        return "Error: unsafe path detected."
        
    deleted_count = 0
    errors = []
    
    files_to_delete = find_files(file_type, source_path)
    if isinstance(files_to_delete, str):
        return files_to_delete
        
    for file_path in files_to_delete:
        if not is_safe_path(file_path):
            continue
            
        try:
            os.remove(file_path)
            deleted_count += 1
        except Exception as e:
            errors.append(f"Failed to delete {file_path}: {e}")
            
    return f"Deleted {deleted_count} files. Errors: {len(errors)}"

def execute_python_file(path):
    """
    Executes a python file.
    """
    if not path:
        return "Error: No file specified to execute."
        
    if not path.endswith(".py"):
        return "Error: Only .py files can be executed."
        
    if not is_safe_path(path):
        return "Error: Unsafe path."
        
    if not os.path.exists(path):
        return f"Error: File '{path}' not found."

    try:
        result = subprocess.run(["python", path], capture_output=True, text=True, timeout=30)
        return f"Output:\n{result.stdout}\nErrors:\n{result.stderr}"
    except Exception as e:
        return f"Execution failed: {e}"
