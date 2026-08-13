import time
import cv2

try:
    from app.ai.mediapipe_service import detect_face
    from app.ai.whisper_service import transcribe_video
except ImportError:
    from mediapipe_service import detect_face
    from whisper_service import transcribe_video


def run_face_detection():

    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam")
        return

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    video_writer = cv2.VideoWriter(
        "interview.mp4",
        fourcc,
        20.0,
        (width, height)
    )

    print("Recording started...")
    print("Press q to stop.")

    try:

        while True:

            success, frame = cap.read()

            if not success:
                break

            frame = cv2.flip(frame, 1)

            video_writer.write(frame)

            resized_frame = cv2.resize(
                frame,
                (800, 600)
            )

            rgb_frame = cv2.cvtColor(
                resized_frame,
                cv2.COLOR_BGR2RGB
            )

            timestamp = int(time.time() * 1000)

            face_landmarks = detect_face(
                rgb_frame,
                timestamp
            )

            if face_landmarks:

                face = face_landmarks[0]

                h, w, _ = resized_frame.shape

                for landmark in face:

                    x = int(landmark.x * w)
                    y = int(landmark.y * h)

                    if 0 <= x < w and 0 <= y < h:

                        cv2.circle(
                            resized_frame,
                            (x, y),
                            1,
                            (0, 255, 0),
                            -1
                        )

            cv2.imshow(
                "NexHire - Face Landmarks",
                resized_frame
            )

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    finally:

        cap.release()
        video_writer.release()
        cv2.destroyAllWindows()

    print("\nGenerating Transcript...\n")

    transcript = transcribe_video(
        "interview.mp4"
    )

    print("===== TRANSCRIPT =====\n")
    print(transcript)


if __name__ == "__main__":
    run_face_detection()
