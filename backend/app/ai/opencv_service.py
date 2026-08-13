import time
import cv2

try:
    from app.ai.mediapipe_service import detect_face
except ImportError:
    from mediapipe_service import detect_face


def run_face_detection():
    # ============================================================
    # WEBCAM
    # ============================================================

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    print("Starting face landmark detection... Press 'q' to quit.")

    # ============================================================
    # MAIN LOOP
    # ============================================================

    try:
        while True:

            # --------------------------------------------------------
            # Capture frame
            # --------------------------------------------------------

            success, frame = cap.read()

            if not success:
                print("Error: Could not read frame")
                break

            # --------------------------------------------------------
            # Flip webcam horizontally
            # --------------------------------------------------------

            frame = cv2.flip(frame, 1)

            # --------------------------------------------------------
            # Resize frame
            # --------------------------------------------------------

            frame = cv2.resize(
                frame,
                (800, 600)
            )

            # --------------------------------------------------------
            # Convert BGR → RGB
            # --------------------------------------------------------

            rgb_frame = cv2.cvtColor(
                frame,
                cv2.COLOR_BGR2RGB
            )

            # --------------------------------------------------------
            # Timestamp (in milliseconds)
            # --------------------------------------------------------

            timestamp = int(time.time() * 1000)

            # --------------------------------------------------------
            # SEND RGB FRAME TO MEDIAPIPE
            # --------------------------------------------------------

            face_landmarks = detect_face(
                rgb_frame,
                timestamp
            )

            # ========================================================
            # DRAW LANDMARKS
            # ========================================================

            if face_landmarks:

                # We only requested one face
                face = face_landmarks[0]

                h, w, _ = frame.shape

                # ----------------------------------------------------
                # Draw all landmark points
                # ----------------------------------------------------

                for landmark in face:

                    x = int(landmark.x * w)
                    y = int(landmark.y * h)

                    # Make sure point is inside frame
                    if 0 <= x < w and 0 <= y < h:

                        cv2.circle(
                            frame,
                            (x, y),
                            1,
                            (0, 255, 0),
                            -1
                        )

            # ========================================================
            # DISPLAY
            # ========================================================

            cv2.imshow(
                "NexHire - Face Landmarks",
                frame
            )

            # ========================================================
            # EXIT
            # ========================================================

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:
        # ============================================================
        # CLEANUP
        # ============================================================

        cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    run_face_detection()