import cv2

cap = cv2.VideoCapture(0)

if not cap.isOpened():
    print("Error: Could not open webcam")
    exit()

while True:
    success, frame = cap.read()
    frame = cv2.resize(frame, (800, 600))
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    if not success:
        print("Error: Could not read frame")
        break

    cv2.imshow("NexHire - Webcam", frame)

    if cv2.waitKey(1) & 0xFF == ord("q"):
        break

cap.release()
cv2.destroyAllWindows()