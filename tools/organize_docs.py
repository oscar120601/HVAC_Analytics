import os
import re
import shutil
from pathlib import Path
from packaging import version

DOCS_DIR = r"D:\12.任務\HVAC-1\docs"

def get_version_from_filename(filename):
    """
    Extracts version from filename like 'Name_v1.2.md' or 'Name_v1.2-Approved.md'.
    Returns a packaging.version.Version object or None.
    Handles 'v1.0', 'v1.1', 'v2.0' etc.
    """
    # Regex to find _v followed by digits and dots, excluding further text
    match = re.search(r'v(\d+\.\d+)', filename)
    if match:
        try:
            return version.parse(match.group(1))
        except version.InvalidVersion:
            return None
    return None

def organize_directory(directory_path):
    print(f"Scanning directory: {directory_path}")
    
    try:
        files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]
    except PermissionError:
        print(f"  Permission denied: {directory_path}")
        return
    
    # Identify versions
    files_with_version = []
    versions = []
    
    for f in files:
        # Skip migration scripts or non-doc files if necessary, but request was general
        ver = get_version_from_filename(f)
        if ver:
            files_with_version.append((f, ver))
            versions.append(ver)
            
    if not versions:
        print(f"  No versioned files found in {directory_path}")
        return

    max_version = max(versions)
    print(f"  Max version identified: {max_version}")
    
    archive_dir = os.path.join(directory_path, "_archive")
    
    for filename, ver in files_with_version:
        if ver < max_version:
            # Prepare archive directory
            if not os.path.exists(archive_dir):
                os.makedirs(archive_dir)
                print(f"  Created archive directory: {archive_dir}")
            
            src = os.path.join(directory_path, filename)
            dst = os.path.join(archive_dir, filename)
            
            print(f"  Moving {filename} (v{ver}) -> _archive/")
            try:
                shutil.move(src, dst)
            except Exception as e:
                print(f"  Error moving {filename}: {e}")
        else:
            print(f"  Keeping {filename} (v{ver}) [Current]")

def main():
    if not os.path.exists(DOCS_DIR):
        print(f"Directory not found: {DOCS_DIR}")
        return

    # Iterate primarily over immediate subdirectories of docs
    for entry in os.listdir(DOCS_DIR):
        full_path = os.path.join(DOCS_DIR, entry)
        if os.path.isdir(full_path):
            organize_directory(full_path)

if __name__ == "__main__":
    main()
