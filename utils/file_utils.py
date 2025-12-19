import os
from pathlib import Path
import zipfile
import io

# base paths (relative to project root)
DATA_DIR = Path(__file__).parent.parent / "data"
ZIP_DIR = Path(__file__).parent.parent / "zip"

def ensure_dirs():
    """Ensure data/ and zip/ directories exist."""
    DATA_DIR.mkdir(exist_ok=True)
    ZIP_DIR.mkdir(exist_ok=True)

def save_image_bytes(user_folder: str, filename: str, image_bytes: bytes) -> Path:
    """
    Save image bytes to file.
    - user_folder: subfolder name inside data/ for a given user (like "user123_20251210_1015")
    - filename: name of the image file (e.g. "L1_center.png")
    - image_bytes: raw bytes (from camera_input.getvalue())
    Returns Path to saved file.
    """
    ensure_dirs()
    folder_path = DATA_DIR / user_folder
    folder_path.mkdir(parents=True, exist_ok=True)
    file_path = folder_path / filename
    with open(file_path, "wb") as f:
        f.write(image_bytes)
    return file_path

def make_zip_for_user(user_folder: str) -> Path:
    """
    Create a zip archive of all files in the user's data folder.
    Returns Path to the zip file.
    """
    ensure_dirs()
    source_dir = DATA_DIR / user_folder
    if not source_dir.exists():
        raise FileNotFoundError(f"No data folder for user: {user_folder}")

    zip_filename = f"{user_folder}.zip"
    zip_path = ZIP_DIR / zip_filename

    # optional: if zip already exists, overwrite
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                full_path = Path(root) / file
                # inside zip we want folder structure starting from user_folder
                rel_path = full_path.relative_to(DATA_DIR)
                zf.write(full_path, arcname=str(rel_path))

    return zip_path

def make_zip_in_memory(image_files: dict) -> io.BytesIO:
    """
    Alternative: If you have image files or bytes and want to build zip
    on-the-fly (memory) rather than writing to disk.
    image_files: dict mapping filename (str) -> bytes
    Returns BytesIO object with zip data (seeked to start).
    """
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname, b in image_files.items():
            zf.writestr(fname, b)
    zip_buffer.seek(0)
    return zip_buffer
