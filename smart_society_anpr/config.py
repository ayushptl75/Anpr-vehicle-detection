import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_PATH = os.path.join(BASE_DIR, "database", "society_gate.db")

STORAGE_DIR = os.path.join(BASE_DIR, "storage")
ENTRY_STORAGE_DIR = os.path.join(STORAGE_DIR, "entry")
EXIT_STORAGE_DIR = os.path.join(STORAGE_DIR, "exit")
PLATES_STORAGE_DIR = os.path.join(STORAGE_DIR, "plates")

os.makedirs(ENTRY_STORAGE_DIR, exist_ok=True)
os.makedirs(EXIT_STORAGE_DIR, exist_ok=True)
os.makedirs(PLATES_STORAGE_DIR, exist_ok=True)

# Helper to parse camera source (USB webcam index vs RTSP/HTTP URL string)
def parse_camera_source(src_str):
    if src_str is None:
        return 0
    src_str = str(src_str).strip()
    if src_str.isdigit():
        return int(src_str)
    return src_str

# Camera URL configurations (USB index 0, 1 or RTSP string URL)
ENTRY_CAMERA_RAW = os.environ.get("ENTRY_CAMERA_URL", "0")
EXIT_CAMERA_RAW = os.environ.get("EXIT_CAMERA_URL", "1")

ENTRY_CAMERA_URL = parse_camera_source(ENTRY_CAMERA_RAW)
EXIT_CAMERA_URL = parse_camera_source(EXIT_CAMERA_RAW)

# Detection Model & Filtering Parameters
PLATE_MODEL_PATH = os.path.join(BASE_DIR, "models", "license_plate_detector.pt")
PLATE_CONFIDENCE_THRESHOLD = float(os.environ.get("PLATE_CONFIDENCE_THRESHOLD", 0.25))

MIN_PLATE_WIDTH = 25
MIN_PLATE_HEIGHT = 10
MIN_PLATE_ASPECT_RATIO = 1.5
MAX_PLATE_ASPECT_RATIO = 8.0

# Multi-Frame Temporal Recognition Thresholds
MIN_CONSISTENT_READS = int(os.environ.get("MIN_CONSISTENT_READS", 3))
MIN_WEIGHTED_SCORE = float(os.environ.get("MIN_WEIGHTED_SCORE", 2.0))
TRACK_EXPIRY_SEC = float(os.environ.get("TRACK_EXPIRY_SEC", 3.0))
IOU_MATCH_THRESHOLD = float(os.environ.get("IOU_MATCH_THRESHOLD", 0.3))
MIN_OCR_CONFIDENCE = float(os.environ.get("MIN_OCR_CONFIDENCE", 0.40))
