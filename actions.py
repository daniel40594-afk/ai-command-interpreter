import os
import shutil
import subprocess
import fnmatch
from pathlib import Path

# Blocklist of system directories to protect
# (Even with home-containment, these provide an extra layer of safety if paths are malformed)
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

def get_home_dir():
    """Returns the absolute path to the user's home directory."""
    return Path.home().resolve()

def resolve_path(path_str):
    """
    Resolves a path string to an absolute path.
    - If None/Empty: Returns Home Directory.
    - If Absolute: Returns it (will be checked by is_safe_path).
    - If Relative: Resolves Relative to Home Directory.
    """
    home = get_home_dir()
    
    if not path_str:
        return home
        
    # If the user says "Downloads", we want Home/Downloads
    # If the user says "actions.py" (current dir), we might need to be careful.
    # The prompt says "natural language path mapping" -> 'this folder' is null.
    # If null -> Home. 
    # But if the user is in the project folder, they might expect '.' to be the project folder.
    # However, strict instructions say "assume the tool is only allowed to operate inside the user's home directory".
    # And "If no path is explicitly mentioned, use null."
    # Let's adhere to: Relative paths are relative to HOME, unless they start with ./ which might imply CWD?
    # Actually, for a file manager style usage, assuming Home as root is safest/most logical.
    
    path = Path(path_str)
    if path.is_absolute():
        return path.resolve()
    else:
        return (home / path).resolve()

def is_safe_path(path_str):
    """
    Checks if a path is safe to operate on.
    STRICTLY ENFORCES: Path must be inside User Home Directory.
    """
    if not path_str:
        return True
    
    try:
        if isinstance(path_str, Path):
            path = path_str.resolve()
        else:
            path = resolve_path(path_str)
            
        home = get_home_dir()
        
        # 1. Strict Containment Check
        # is_relative_to returns True if path is inside home
        if not path.is_relative_to(home):
            print(f"DEBUG: Blocked path '{path}' - Not inside Home '{home}'")
            return False
            
        # 2. explicit defined system blocklist (redundant but safe)
        path_str_lower = str(path).lower()
        for sys_dir in SYSTEM_DIRS:
            sys_path = Path(os.path.expandvars(sys_dir)).resolve()
            if path_str_lower.startswith(str(sys_path).lower()):
                 return False

        return True
    except Exception as e:
        print(f"DEBUG: Path check error: {e}")
        return False

def list_files(path=None):
    """
    Lists files and directories in the given path.
    """
    target_path = resolve_path(path)
    
    if not is_safe_path(target_path):
        return f"Error: Access to '{target_path}' is RESTRICTED (Outside User Home)."
        
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
        return items[:100]
    except PermissionError:
        return f"Error: Permission denied accessing '{target_path}'."
    except Exception as e:
        return f"Error listing files: {e}"

def find_files(file_type=None, source_path=None):
    """
    Finds files matching a type in a source path.
    """
    start_dir = resolve_path(source_path)
    
    if not is_safe_path(source_path): # Check original string too just in case
         if not is_safe_path(start_dir):
            return f"Error: Access to '{start_dir}' is RESTRICTED."
    
    results = []
    
    if not os.path.exists(start_dir):
        return f"Error: Source path '{start_dir}' does not exist."

    print(f"Searching in: {start_dir}")
    
    count = 0
    max_count = 50
    
    for root, dirnames, filenames in os.walk(start_dir):
        # Prevent recursing into unsafe directories (though they shouldn't be under Home)
        # But 'AppData' might be large or sensitive.
        if not is_safe_path(root):
            dirnames[:] = []
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
        return "Error: unsafe path detected (Outside User Home)."

    if not os.path.exists(dest_dir):
        try:
            os.makedirs(dest_dir)
        except OSError as e:
            return f"Error creating destination: {e}"

    moved_count = 0
    errors = []
    
    files_to_move = find_files(file_type, source_path)
    if isinstance(files_to_move, str):
        return files_to_move
        
    for file_path in files_to_move:
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
        return "Error: unsafe path detected (Outside User Home)."
        
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
        return "Error: Unsafe path (Outside User Home)."
        
    if not os.path.exists(target_path):
        return f"Error: File '{target_path}' not found."

    try:
        # We assume the user wants to run relative to the script's dir usually
        # But for this tool, let's keep it simple.
        cwd = os.path.dirname(target_path)
        
        result = subprocess.run(
            ["python", target_path], 
            capture_output=True, 
            text=True, 
            timeout=30,
            cwd=cwd
        )
        return f"Output:\n{result.stdout}\nErrors:\n{result.stderr}"
    except Exception as e:
        return f"Execution failed: {e}"
