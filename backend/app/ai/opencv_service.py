"""
opencv_service.py

Real-time webcam loop for NexHire.

Architecture:

Webcam
   ↓
OpenCV
   ↓
Latest frame
   ↓
AI worker thread
   ↓
MediaPipe
   ↓
Candidate Tracker
   ↓
Candidate Landmarks
   ↓
Eye Contact
   ↓
Latest AI result
   ↓
Display

Important:
- Only this file opens VideoCapture.
- MediaPipe runs in the AI worker.
- Candidate identity is handled by CandidateTracker.
- Eye contact receives ONLY the verified candidate landmarks.
- The webcam display does not wait for AI processing.
"""

import time
import threading

import cv2

from app.ai import mediapipe_service
from app.ai import eye_contact

from app.ai.candidate_tracker import (
    CandidateTracker,
    CandidateStatus
)


# ============================================================
# CAMERA SETTINGS
# ============================================================

CAMERA_INDEX = 0

DISPLAY_WIDTH = 960
DISPLAY_HEIGHT = 540

# Smaller processing frame for better performance
PROCESS_WIDTH = 480
PROCESS_HEIGHT = 270


# ============================================================
# AI STATE
# ============================================================

class AIState:

    def __init__(self):

        self.lock = threading.Lock()

        # Latest frame waiting for AI
        self.latest_frame_rgb = None

        # Timestamp belonging to latest frame
        self.latest_timestamp = 0

        # Latest MediaPipe results
        self.latest_landmarks = []

        # Only locked candidate landmarks
        self.latest_candidate_landmarks = None

        # Candidate status
        self.latest_status = (
            CandidateStatus.WAITING_FOR_CANDIDATE
        )

        # Eye-contact result
        self.latest_eye_result = None

        # Thread controls
        self.new_frame = threading.Event()

        self.stop = threading.Event()


# ============================================================
# AI WORKER
# ============================================================

def ai_worker(
    state: AIState,
    tracker: CandidateTracker
):

    print("AI processing thread started.")

    last_timestamp_ms = 0

    while not state.stop.is_set():

        # ----------------------------------------------------
        # Wait for a new frame
        # ----------------------------------------------------

        state.new_frame.wait(
            timeout=0.1
        )

        if state.stop.is_set():
            break

        # ----------------------------------------------------
        # Get newest frame
        # ----------------------------------------------------

        with state.lock:

            if state.latest_frame_rgb is None:

                state.new_frame.clear()

                continue

            frame_rgb = (
                state.latest_frame_rgb.copy()
            )

            timestamp_ms = (
                state.latest_timestamp
            )

            state.new_frame.clear()

        # ====================================================
        # MEDIAPIPE
        # ====================================================

        if timestamp_ms <= last_timestamp_ms:
            timestamp_ms = last_timestamp_ms + 1
        last_timestamp_ms = timestamp_ms

        try:

            all_face_landmarks = (
                mediapipe_service.detect_face(
                    frame_rgb,
                    timestamp_ms
                )
            )

        except Exception as error:

            print(
                "MediaPipe error:",
                error
            )

            continue

        # ====================================================
        # CANDIDATE TRACKER
        # ====================================================

        try:

            status, candidate_landmarks = (
                tracker.process_frame(
                    frame_rgb,
                    all_face_landmarks
                )
            )

        except Exception as error:

            print(
                "Candidate tracker error:",
                error
            )

            continue

        # ====================================================
        # EYE CONTACT
        # ====================================================
        #
        # IMPORTANT:
        #
        # We pass candidate_landmarks, NOT
        # all_face_landmarks.
        #
        # Therefore Eye Contact only analyzes the
        # locked candidate.
        # ====================================================

        try:

            eye_result = (
                eye_contact.analyze_eye_contact(
                    candidate_landmarks
                )
            )

        except Exception as error:

            print(
                "Eye contact error:",
                error
            )

            eye_result = None

        # ====================================================
        # SAVE LATEST AI RESULT
        # ====================================================

        with state.lock:

            state.latest_landmarks = (
                all_face_landmarks
            )

            state.latest_candidate_landmarks = (
                candidate_landmarks
            )

            state.latest_status = (
                status
            )

            state.latest_eye_result = (
                eye_result
            )

    print("AI processing thread stopped.")


# ============================================================
# MAIN WEBCAM LOOP
# ============================================================

def run_face_detection():

    # --------------------------------------------------------
    # Candidate tracker
    # --------------------------------------------------------

    tracker = CandidateTracker()

    # --------------------------------------------------------
    # Shared AI state
    # --------------------------------------------------------

    state = AIState()

    # ========================================================
    # OPEN CAMERA
    # ========================================================

    cap = cv2.VideoCapture(
        CAMERA_INDEX
    )

    if not cap.isOpened():

        raise RuntimeError(
            "Could not open webcam."
        )

    # ========================================================
    # CAMERA SETTINGS
    # ========================================================

    cap.set(
        cv2.CAP_PROP_FRAME_WIDTH,
        DISPLAY_WIDTH
    )

    cap.set(
        cv2.CAP_PROP_FRAME_HEIGHT,
        DISPLAY_HEIGHT
    )

    # --------------------------------------------------------
    # Keep camera buffer small.
    # This prevents old frames from building up.
    # --------------------------------------------------------

    cap.set(
        cv2.CAP_PROP_BUFFERSIZE,
        1
    )

    # ========================================================
    # START AI THREAD
    # ========================================================

    worker = threading.Thread(
        target=ai_worker,
        args=(
            state,
            tracker
        ),
        daemon=True
    )

    worker.start()

    # ========================================================
    # FPS VARIABLES
    # ========================================================

    fps_counter = 0

    fps_start = time.perf_counter()

    current_fps = 0.0

    # ========================================================
    # MAIN LOOP
    # ========================================================

    try:

        while True:

            # =================================================
            # READ WEBCAM
            # =================================================

            success, frame_bgr = cap.read()

            if not success:

                print(
                    "Could not read webcam frame."
                )

                break

            # =================================================
            # MIRROR
            # =================================================

            frame_bgr = cv2.flip(
                frame_bgr,
                1
            )

            # =================================================
            # DISPLAY FRAME
            # =================================================

            display_frame = cv2.resize(
                frame_bgr,
                (
                    DISPLAY_WIDTH,
                    DISPLAY_HEIGHT
                ),
                interpolation=cv2.INTER_LINEAR
            )

            # =================================================
            # CREATE SMALL AI FRAME
            # =================================================

            process_bgr = cv2.resize(
                frame_bgr,
                (
                    PROCESS_WIDTH,
                    PROCESS_HEIGHT
                ),
                interpolation=cv2.INTER_AREA
            )

            # =================================================
            # BGR → RGB
            # =================================================

            process_rgb = cv2.cvtColor(
                process_bgr,
                cv2.COLOR_BGR2RGB
            )

            # =================================================
            # SEND NEWEST FRAME TO AI
            # =================================================

            timestamp_ms = int(
                time.perf_counter() * 1000
            )

            with state.lock:

                state.latest_frame_rgb = (
                    process_rgb
                )

                state.latest_timestamp = (
                    timestamp_ms
                )

                state.new_frame.set()

            # =================================================
            # READ LATEST AI RESULT
            # =================================================

            with state.lock:

                status = (
                    state.latest_status
                )

                landmarks = list(
                    state.latest_landmarks
                )

                candidate_landmarks = (
                    state.latest_candidate_landmarks
                )

                eye_result = (
                    state.latest_eye_result
                )

            # =================================================
            # DRAW FACE BOXES
            # =================================================

            _draw_face_boxes(
                display_frame,
                landmarks,
                candidate_landmarks
            )

            # =================================================
            # UPDATE FPS
            # =================================================

            fps_counter += 1

            elapsed = (
                time.perf_counter()
                -
                fps_start
            )

            if elapsed >= 0.5:

                current_fps = (
                    fps_counter /
                    elapsed
                )

                fps_counter = 0

                fps_start = (
                    time.perf_counter()
                )

            # =================================================
            # DRAW HUD & GAZE RADAR OVERLAY
            # =================================================

            _draw_hud(
                display_frame,
                status,
                current_fps,
                eye_result
            )

            # =================================================
            # KEYBOARD
            # =================================================

            key = cv2.waitKey(1) & 0xFF

            # -------------------------------------------------
            # START INTERVIEW
            # -------------------------------------------------

            if (
                key == ord("s")
                and
                status ==
                CandidateStatus.CANDIDATE_SELECTED
            ):

                with state.lock:

                    start_frame = (
                        state.latest_frame_rgb
                    )

                    start_landmarks = (
                        state.latest_candidate_landmarks
                    )

                if (
                    start_frame is not None
                    and
                    start_landmarks is not None
                ):

                    try:

                        tracker.start_interview(
                            start_frame
                        )

                        print(
                            "Interview started."
                        )

                    except RuntimeError as error:

                        print(
                            f"Could not start interview: {error}"
                        )

            # -------------------------------------------------
            # RESET CANDIDATE
            # -------------------------------------------------

            elif key == ord("r"):

                with state.lock:

                    tracker.reset_candidate()
                    eye_contact.reset_eye_tracking()

                    state.latest_status = (
                        CandidateStatus.WAITING_FOR_CANDIDATE
                    )

                    state.latest_landmarks = []

                    state.latest_candidate_landmarks = None

                    state.latest_eye_result = None

                print(
                    "Candidate reset."
                )

            # -------------------------------------------------
            # QUIT
            # -------------------------------------------------

            elif key == ord("q"):

                break

            # =================================================
            # DISPLAY
            # =================================================

            cv2.imshow(
                "NexHire Interview",
                display_frame
            )

    finally:

        # ====================================================
        # STOP AI THREAD
        # ====================================================

        state.stop.set()

        state.new_frame.set()

        worker.join(
            timeout=2.0
        )

        # ====================================================
        # CAMERA CLEANUP
        # ====================================================

        cap.release()

        cv2.destroyAllWindows()


# ============================================================
# DRAW STATUS
# ============================================================

# ============================================================
# DRAW HUD & GAZE RADAR OVERLAY
# ============================================================

def _draw_hud(
    frame,
    status,
    fps,
    eye_result
):

    height, width, _ = frame.shape

    # 1. Overlay semi-transparent dark HUD card (Top Left)
    overlay = frame.copy()
    cv2.rectangle(
        overlay,
        (12, 12),
        (375, 225),
        (16, 18, 24),
        -1
    )
    cv2.addWeighted(
        overlay,
        0.82,
        frame,
        0.18,
        0,
        frame
    )
    cv2.rectangle(
        frame,
        (12, 12),
        (375, 225),
        (60, 68, 85),
        1
    )

    # 2. Header Title & FPS
    cv2.putText(
        frame,
        "NexHire AI Monitor",
        (24, 34),
        cv2.FONT_HERSHEY_DUPLEX,
        0.52,
        (240, 240, 240),
        1
    )
    cv2.putText(
        frame,
        f"{fps:.1f} FPS",
        (315, 34),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.42,
        (140, 220, 160),
        1
    )

    # 3. Candidate Status
    labels = {
        CandidateStatus.WAITING_FOR_CANDIDATE:
            ("Waiting for Candidate", (0, 190, 255)),
        CandidateStatus.CANDIDATE_SELECTED:
            ("Selected - Press 'S' to Start", (0, 255, 120)),
        CandidateStatus.CANDIDATE_LOCKED:
            ("Candidate Locked", (0, 255, 0)),
        CandidateStatus.CANDIDATE_PRESENT:
            ("Candidate Present", (0, 255, 0)),
        CandidateStatus.CANDIDATE_NOT_DETECTED:
            ("Candidate Not Detected", (0, 0, 255)),
        CandidateStatus.DIFFERENT_PERSON_DETECTED:
            ("Unknown Person Detected", (0, 0, 255)),
        CandidateStatus.MULTIPLE_FACES_DETECTED:
            ("Multiple Faces Detected", (0, 140, 255)),
        CandidateStatus.CANDIDATE_UNCERTAIN:
            ("Candidate Uncertain", (0, 190, 255)),
    }
    status_text, status_color = labels.get(
        status,
        (str(status), (200, 200, 200))
    )
    cv2.putText(
        frame,
        f"Status: {status_text}",
        (24, 56),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        status_color,
        1
    )

    # Separator Line
    cv2.line(
        frame,
        (24, 66),
        (362, 66),
        (45, 52, 65),
        1
    )

    if eye_result is None:
        cv2.putText(
            frame,
            "Face Not Tracked...",
            (24, 98),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.46,
            (140, 140, 140),
            1
        )
        return

    # Color scheme for eye status
    if eye_result.is_blinking:
        eye_color = (0, 220, 255)   # Yellow
    elif eye_result.looking_at_screen:
        eye_color = (0, 255, 80)    # Green
    else:
        eye_color = (0, 80, 255)    # Bright Coral/Red

    # 4. Gaze Direction & Attention
    cv2.putText(
        frame,
        f"GAZE: {eye_result.status.upper()}",
        (24, 88),
        cv2.FONT_HERSHEY_DUPLEX,
        0.48,
        eye_color,
        1
    )

    # 5. Confidence Score + Progress Bar
    conf_pct = int(eye_result.confidence * 100)
    score_pct = int(eye_result.score * 100)
    cv2.putText(
        frame,
        f"Confidence: {conf_pct}%",
        (24, 114),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.43,
        (225, 225, 225),
        1
    )

    bar_w = 100
    bar_h = 7
    cv2.rectangle(
        frame,
        (135, 107),
        (135 + bar_w, 107 + bar_h),
        (40, 42, 52),
        -1
    )
    fill_w = int(bar_w * (conf_pct / 100.0))
    bar_color = (
        (0, 255, 100)
        if conf_pct >= 70
        else (
            (0, 210, 255)
            if conf_pct >= 45
            else (0, 60, 255)
        )
    )
    if fill_w > 0:
        cv2.rectangle(
            frame,
            (135, 107),
            (135 + fill_w, 107 + bar_h),
            bar_color,
            -1
        )

    # 6. Blinks & EAR
    cv2.putText(
        frame,
        f"Blinks: {eye_result.blink_count} ({eye_result.blink_rate_bpm:.1f} BPM)",
        (24, 140),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.43,
        (210, 210, 210),
        1
    )
    cv2.putText(
        frame,
        f"EAR: {eye_result.ear_avg:.2f} (L: {eye_result.ear_left:.2f}, R: {eye_result.ear_right:.2f})",
        (24, 164),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.41,
        (170, 170, 170),
        1
    )
    cv2.putText(
        frame,
        f"Focus Centrality: {score_pct}%",
        (24, 188),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.41,
        (170, 200, 255),
        1
    )

    # 7. Real-Time Visual Gaze Radar Widget (Top-Right of Card)
    radar_x = 278
    radar_y = 86
    radar_size = 78
    cx = radar_x + radar_size // 2
    cy = radar_y + radar_size // 2

    # Background box
    cv2.rectangle(
        frame,
        (radar_x, radar_y),
        (radar_x + radar_size, radar_y + radar_size),
        (26, 28, 36),
        -1
    )
    cv2.rectangle(
        frame,
        (radar_x, radar_y),
        (radar_x + radar_size, radar_y + radar_size),
        (65, 72, 88),
        1
    )

    # Crosshair grid
    cv2.line(
        frame,
        (radar_x, cy),
        (radar_x + radar_size, cy),
        (46, 50, 62),
        1
    )
    cv2.line(
        frame,
        (cx, radar_y),
        (cx, radar_y + radar_size),
        (46, 50, 62),
        1
    )

    # Safe screen attention box (Center Target)
    target_box = 13
    cv2.rectangle(
        frame,
        (cx - target_box, cy - target_box),
        (cx + target_box, cy + target_box),
        (0, 160, 70),
        1
    )

    # Gaze dot position mapped from horizontal & vertical ratios
    dot_x = int(radar_x + eye_result.horizontal_ratio * radar_size)
    dot_y = int(radar_y + eye_result.vertical_ratio * radar_size)
    dot_x = max(radar_x + 4, min(radar_x + radar_size - 4, dot_x))
    dot_y = max(radar_y + 4, min(radar_y + radar_size - 4, dot_y))

    # Draw glowing gaze dot
    cv2.circle(frame, (dot_x, dot_y), 5, eye_color, -1)
    cv2.circle(frame, (dot_x, dot_y), 7, (255, 255, 255), 1)

    cv2.putText(
        frame,
        "GAZE RADAR",
        (radar_x + 3, radar_y + radar_size + 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.33,
        (135, 140, 155),
        1
    )


# ============================================================
# DRAW FACE BOXES
# ============================================================

def _draw_face_boxes(
    frame,
    all_face_landmarks,
    candidate_landmarks
):

    if not all_face_landmarks:
        return

    height, width, _ = frame.shape

    # --------------------------------------------------------
    # AI processing resolution = 480 x 270
    # Display resolution = 960 x 540
    # --------------------------------------------------------

    scale_x = (
        width /
        PROCESS_WIDTH
    )

    scale_y = (
        height /
        PROCESS_HEIGHT
    )

    for face in all_face_landmarks:

        if not face:
            continue

        xs = [
            landmark.x
            for landmark in face
        ]

        ys = [
            landmark.y
            for landmark in face
        ]

        if not xs or not ys:
            continue

        left = int(
            min(xs)
            *
            PROCESS_WIDTH
            *
            scale_x
        )

        right = int(
            max(xs)
            *
            PROCESS_WIDTH
            *
            scale_x
        )

        top = int(
            min(ys)
            *
            PROCESS_HEIGHT
            *
            scale_y
        )

        bottom = int(
            max(ys)
            *
            PROCESS_HEIGHT
            *
            scale_y
        )

        # ----------------------------------------------------
        # Keep inside frame
        # ----------------------------------------------------

        left = max(
            0,
            min(left, width - 1)
        )

        right = max(
            0,
            min(right, width - 1)
        )

        top = max(
            0,
            min(top, height - 1)
        )

        bottom = max(
            0,
            min(bottom, height - 1)
        )

        # ----------------------------------------------------
        # Candidate box = thicker
        # Other detected faces = thinner
        # ----------------------------------------------------

        is_candidate = (
            candidate_landmarks is face
        )

        thickness = (
            3
            if is_candidate
            else 1
        )

        cv2.rectangle(
            frame,
            (left, top),
            (right, bottom),
            (0, 255, 0),
            thickness
        )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    run_face_detection()