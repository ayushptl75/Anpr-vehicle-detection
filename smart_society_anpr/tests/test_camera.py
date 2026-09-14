import unittest
import os
import sys
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import parse_camera_source
from anpr.camera import CameraService

class TestCameraService(unittest.TestCase):

    def test_parse_camera_source(self):
        self.assertEqual(parse_camera_source("0"), 0)
        self.assertEqual(parse_camera_source("1"), 1)
        self.assertEqual(parse_camera_source("rtsp://192.168.1.100:554/live"), "rtsp://192.168.1.100:554/live")
        self.assertEqual(parse_camera_source("http://192.168.1.101:8080/video"), "http://192.168.1.101:8080/video")

    def test_camera_service_lifecycle(self):
        cam = CameraService(camera_url=0, name="Test Entry Camera")
        cam.start()
        
        frame = cam.read_frame()
        self.assertIsNotNone(frame)
        self.assertIsInstance(frame, np.ndarray)
        self.assertEqual(frame.shape[2], 3)  # BGR 3-channel image

        cam.stop()
        self.assertFalse(cam.is_connected)

    def test_offline_frame_generation(self):
        cam = CameraService(camera_url="invalid_non_existent_source_999", name="Offline Cam")
        cam.start()
        
        frame = cam.read_frame()
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, (480, 640, 3))
        
        cam.release()

if __name__ == '__main__':
    unittest.main()
