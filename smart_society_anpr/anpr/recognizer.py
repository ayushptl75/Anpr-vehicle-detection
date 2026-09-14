import time
from collections import defaultdict
from config import (
    MIN_CONSISTENT_READS, MIN_WEIGHTED_SCORE,
    TRACK_EXPIRY_SEC, IOU_MATCH_THRESHOLD
)

def calculate_iou(boxA, boxB):
    """
    Calculates Intersection over Union (IoU) of two bounding boxes (x1, y1, x2, y2).
    """
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])

    inter_width = max(0, xB - xA)
    inter_height = max(0, yB - yA)
    inter_area = inter_width * inter_height

    boxA_area = max(0, boxA[2] - boxA[0]) * max(0, boxA[3] - boxA[1])
    boxB_area = max(0, boxB[2] - boxB[0]) * max(0, boxB[3] - boxB[1])

    union_area = float(boxA_area + boxB_area - inter_area)
    if union_area <= 0:
        return 0.0

    return inter_area / union_area


class TrackedPlate:
    def __init__(self, track_id, bbox, ocr_result):
        self.track_id = track_id
        self.bbox = bbox
        self.last_updated = time.time()
        self.observations = []
        self.confirmed_plate = None
        self.add_observation(ocr_result)

    def add_observation(self, ocr_result):
        self.last_updated = time.time()
        if ocr_result and ocr_result.get("plate_number"):
            self.observations.append({
                "plate_number": ocr_result["plate_number"],
                "ocr_confidence": float(ocr_result.get("ocr_confidence", 0.0)),
                "validation_status": ocr_result.get("validation_status", "INVALID_FORMAT"),
                "timestamp": self.last_updated
            })


class MultiFrameRecognizer:
    def __init__(self, min_reads=MIN_CONSISTENT_READS, min_score=MIN_WEIGHTED_SCORE, expiry_sec=TRACK_EXPIRY_SEC, iou_thresh=IOU_MATCH_THRESHOLD):
        self.min_reads = min_reads
        self.min_score = min_score
        self.expiry_sec = expiry_sec
        self.iou_thresh = iou_thresh
        self.tracks = {}
        self.next_track_id = 1

    def purge_stale_tracks(self):
        """Removes tracked plates that haven't been updated within expiry_sec."""
        now = time.time()
        stale_ids = [tid for tid, track in self.tracks.items() if now - track.last_updated > self.expiry_sec]
        for tid in stale_ids:
            del self.tracks[tid]

    def process_observation(self, bbox, ocr_result):
        """
        Associates frame observation with an active track using IoU, appends OCR observation,
        and computes temporal confidence-weighted voting status.
        """
        self.purge_stale_tracks()

        best_track_id = None
        best_iou = 0.0

        if bbox:
            for tid, track in self.tracks.items():
                iou = calculate_iou(bbox, track.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_track_id = tid

        if best_track_id is not None and best_iou >= self.iou_thresh:
            track = self.tracks[best_track_id]
            track.bbox = bbox
            track.add_observation(ocr_result)
        else:
            best_track_id = f"T-{self.next_track_id}"
            self.next_track_id += 1
            track = TrackedPlate(best_track_id, bbox, ocr_result)
            self.tracks[best_track_id] = track

        return self.evaluate_track(track)

    def evaluate_track(self, track):
        """
        Performs confidence-weighted voting over accumulated observations.
        Returns recognition status: 'SEARCHING', 'CONFIRMING', or 'CONFIRMED'.
        """
        if not track.observations:
            return {
                "track_id": track.track_id,
                "plate_number": "",
                "ocr_confidence": 0.0,
                "validation_status": "INVALID_FORMAT",
                "status": "SEARCHING",
                "observation_count": 0,
                "weighted_score": 0.0
            }

        # Group observations by plate string
        plate_stats = defaultdict(lambda: {"count": 0, "total_score": 0.0, "max_conf": 0.0, "val_status": "INVALID_FORMAT"})
        
        for obs in track.observations:
            plate_num = obs["plate_number"]
            conf = obs["ocr_confidence"]
            val_stat = obs["validation_status"]
            
            stats = plate_stats[plate_num]
            stats["count"] += 1
            stats["total_score"] += conf
            stats["max_conf"] = max(stats["max_conf"], conf)
            if val_stat == "VALID_INDIAN_PLATE":
                stats["val_status"] = "VALID_INDIAN_PLATE"

        # Candidate ranking: VALID_INDIAN_PLATE first, then highest total weighted score, then count
        candidates = []
        for plate_num, stats in plate_stats.items():
            candidates.append({
                "plate_number": plate_num,
                "count": stats["count"],
                "weighted_score": round(stats["total_score"], 4),
                "max_confidence": stats["max_conf"],
                "validation_status": stats["val_status"]
            })

        candidates.sort(key=lambda c: (
            1 if c["validation_status"] == "VALID_INDIAN_PLATE" else 0,
            c["weighted_score"],
            c["count"]
        ), reverse=True)

        best = candidates[0]
        total_obs_count = len(track.observations)

        # Status Decision Logic
        if total_obs_count < 2:
            rec_status = "SEARCHING"
        elif best["count"] >= self.min_reads and best["weighted_score"] >= self.min_score:
            rec_status = "CONFIRMED"
            track.confirmed_plate = best["plate_number"]
        else:
            rec_status = "CONFIRMING"

        return {
            "track_id": track.track_id,
            "plate_number": best["plate_number"],
            "ocr_confidence": best["max_confidence"],
            "validation_status": best["validation_status"],
            "status": rec_status,
            "observation_count": best["count"],
            "weighted_score": best["weighted_score"]
        }


# Alias for backward compatibility
PlateRecognizer = MultiFrameRecognizer
