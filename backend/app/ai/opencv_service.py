import cv2
import numpy as np


class OpenCVService:
    def __init__(self):
        pass

    def decode_frame(self, frame_bytes: bytes) -> np.ndarray:
        """Decode image bytes into an OpenCV BGR image array."""
        np_arr = np.frombuffer(frame_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return image

    def encode_frame(self, image: np.ndarray, format: str = ".jpg") -> bytes:
        """Encode an OpenCV BGR image array into bytes."""
        success, buffer = cv2.imencode(format, image)
        if not success:
            raise ValueError("Failed to encode frame")
        return buffer.tobytes()


opencv_service = OpenCVService()

if __name__ == "__main__":
    print(f"OpenCV Version: {cv2.__version__}")
    # Create a dummy black image 100x100
    dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
    encoded = opencv_service.encode_frame(dummy_img)
    decoded = opencv_service.decode_frame(encoded)
    print(f"Test Frame Encoded Size: {len(encoded)} bytes, Decoded Shape: {decoded.shape}")
    print("OpenCV Service initialized and verified successfully!")
