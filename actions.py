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
    r"C:\$Recycle.Bin",
    r"C:\System Volume Information"
]

def get_default_path():
    """Returns the user's home directory."""
    return os.path.expanduser("~")

def resolve_path(path_str):
    """
    Resolves a path string to an absolute path.
    Handles '~' expansion and relative paths.
    """
    if not path_str:
        return get_default_path()
        
    # Handle specific short names if needed, or just let shell expansion handle it?
    # For now, standard expansion:
    expanded = os.path.expanduser(path_str)
    return os.path.abspath(expanded)

def is_safe_path(path_str):
    """
    Checks if a path is safe to operate on.
    STRICTLY BLOCKS system directories.
    """
    if not path_str:
        return True # Default path is safe (User Home)
    
    try:
        path = Path(resolve_path(path_str)).resolve()
        path_str_lower = str(path).lower()
        
        for sys_dir in SYSTEM_DIRS:
            sys_path = Path(os.path.expandvars(sys_dir)).resolve()
            sys_path_str = str(sys_path).lower()
            
            # Check if path is inside a system directory
            # We use string check to ensure we catch subdirectories
            if path_str_lower.startswith(sys_path_str):
                return False
                
        return True
    except Exception:
        # If we can't resolve it, it's unsafe
        return False

def list_files(path=None):
    """
    Lists files and directories in the given path.
    """
    target_path = resolve_path(path)
    
    if not is_safe_path(target_path):
        return f"Error: Access to '{target_path}' is RESTRICTED (System Directory)."
        
    if not os.path.exists(target_path):
        return f"Error: Path '{target_path}' does not exist."
        
    if not os.path.isdir(target_path):
        return f"Error: '{target_path}' is not a directory."

    items = []
    try:
        with os.scandir(target_path) as it:
            for entry in it:
                type_str = "DIR " if entry.is_dir() else "FILE"
                size_str = f"{entry.stat().st_size}b" if entry.is_file() else "-"
                items.append(f"[{type_str}] {entry.name} ({size_str})")
                
        # Sort directories first, then files
        items.sort(key=lambda x: (x.startswith("[FILE]"), x.lower()))
        return items[:100] # Limit to 100 items for display sanity
    except PermissionError:
        return f"Error: Permission denied accessing '{target_path}'."
    except Exception as e:
        return f"Error listing files: {e}"

def find_files(file_type=None, source_path=None):
    """
    Finds files matching a type in a source path.
    Defaults to User Home if no source provided.
    """
    start_dir = resolve_path(source_path)
    
    if not is_safe_path(start_dir):
        return f"Error: Access to '{start_dir}' is RESTRICTED."
    
    results = []
    
    if not os.path.exists(start_dir):
        return f"Error: Source path '{start_dir}' does not exist."

    print(f"Searching in: {start_dir}")
    
    # We limit recursion depth or count to avoid hanging on entire C: drive
    count = 0
    max_count = 50
    
    for root, dirnames, filenames in os.walk(start_dir):
        # Safety check for every directory we enter
        if not is_safe_path(root):
            # distinct safe path check failed (e.g. symlink to system dir)
            dirnames[:] = [] # Stop recursing here
            continue
            
        for filename in filenames:
            if file_type:
                if filename.lower().endswith(f".{file_type.lower()}"):
                     results.append(os.path.join(root, filename))
                     count += 1
            else:
                results.append(os.path.join(root, filename))
                count += 1
                
            if count >= max_count:
                return results
                
    return results

def move_files(file_type, destination_path, source_path=None):
    """
    Moves files of a certain type to a destination.
    """
    if not destination_path:
        return "Error: Destination path required for move."
        
    src_dir = resolve_path(source_path)
    dest_dir = resolve_path(destination_path)
    
    if not is_safe_path(src_dir) or not is_safe_path(dest_dir):
        return "Error: unsafe path detected (System Directory)."

    if not os.path.exists(dest_dir):
        try:
            os.makedirs(dest_dir)
        except OSError as e:
            return f"Error creating destination: {e}"

    moved_count = 0
    errors = []
    
    # Use find_files logic but customized to not recurse too deep if unexpected
    files_to_move = find_files(file_type, source_path)
    if isinstance(files_to_move, str): # Error message
        return files_to_move
        
    for file_path in files_to_move:
        # Double check each file
        if not is_safe_path(file_path):
            continue
            
        try:
            shutil.move(file_path, dest_dir)
            moved_count += 1
        except Exception as e:
            errors.append(f"Failed to move {file_path}: {e}")
            
    return f"Moved {moved_count} files to {dest_dir}. Errors: {len(errors)}"

def delete_files(file_type, source_path=None):
    """
    Deletes files of a certain type.
    """
    src_dir = resolve_path(source_path)
    
    if not is_safe_path(src_dir):
        return "Error: unsafe path detected (System Directory)."
        
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
            
    return f"Deleted {deleted_count} files from {src_dir}. Errors: {len(errors)}"

def execute_python_file(path):
    """
    Executes a python file.
    """
    if not path:
        return "Error: No file specified to execute."
        
    target_path = resolve_path(path)
        
    if not str(target_path).lower().endswith(".py"):
        return "Error: Only .py files can be executed."
        
    if not is_safe_path(target_path):
        return "Error: Unsafe path (System Directory)."
        
    if not os.path.exists(target_path):
        return f"Error: File '{target_path}' not found."

    try:
        # Use a timeout to prevent infinite loops blocked the CLI
        result = subprocess.run(
            ["python", target_path], 
            capture_output=True, 
            text=True, 
            timeout=30,
            cwd=os.path.dirname(target_path) # Run in the script's directory
        )
        return f"Output:\n{result.stdout}\nErrors:\n{result.stderr}"
    except Exception as e:
        return f"Execution failed: {e}"
