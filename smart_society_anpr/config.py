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
EXIT_CAMERA_RAW = os.environ.get("EXIT_CAMERA_URL", "0")

ENTRY_CAMERA_URL = parse_camera_source(ENTRY_CAMERA_RAW)
EXIT_CAMERA_URL = parse_camera_source(EXIT_CAMERA_RAW)

# Camera Resolution & Frame Settings
CAMERA_WIDTH = int(os.environ.get("CAMERA_WIDTH", 1280))
CAMERA_HEIGHT = int(os.environ.get("CAMERA_HEIGHT", 720))

# AI Model Inference & Detection Parameters
VEHICLE_MODEL_PATH = os.environ.get("VEHICLE_MODEL_PATH", "yolov8n.pt")
PLATE_MODEL_PATH = os.path.join(BASE_DIR, "models", "license_plate_detector.pt")

AI_INPUT_SIZE = int(os.environ.get("AI_INPUT_SIZE", 640))
VEHICLE_CONFIDENCE = float(os.environ.get("VEHICLE_CONFIDENCE", 0.45))
PLATE_CONFIDENCE_THRESHOLD = float(os.environ.get("PLATE_CONFIDENCE_THRESHOLD", 0.45))
PLATE_CONFIDENCE = PLATE_CONFIDENCE_THRESHOLD
INFERENCE_INTERVAL = float(os.environ.get("INFERENCE_INTERVAL", 0.1))
EVENT_COOLDOWN_SECONDS = float(os.environ.get("EVENT_COOLDOWN_SECONDS", 10.0))

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

# Phase 15: Optional Arduino Hardware Integration Settings
ARDUINO_PORT = os.environ.get("ARDUINO_PORT", "COM3")
ARDUINO_BAUD = int(os.environ.get("ARDUINO_BAUD", 9600))
ENABLE_HARDWARE = os.environ.get("ENABLE_HARDWARE", "true").lower() == "true"


