import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "anpr.db")

# Image capture storage
CAPTURES_DIR = os.path.join(BASE_DIR, "static", "captures")
ENTRY_CAPTURES_DIR = os.path.join(CAPTURES_DIR, "entry")
EXIT_CAPTURES_DIR = os.path.join(CAPTURES_DIR, "exit")

os.makedirs(ENTRY_CAPTURES_DIR, exist_ok=True)
os.makedirs(EXIT_CAPTURES_DIR, exist_ok=True)

# Camera sources (Default device index 0 for Entry camera, 1 or mock for Exit camera)
ENTRY_CAMERA_SOURCE = 0
EXIT_CAMERA_SOURCE = 1

# Tesseract executable path for Windows (if custom path needed, can be configured)
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
