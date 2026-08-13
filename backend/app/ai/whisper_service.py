import os
import tempfile
import subprocess

import whisper
import librosa


# ============================================================
# LOAD WHISPER MODEL
# ============================================================

model = whisper.load_model("base")


# ============================================================
# CONFIGURATION
# ============================================================

FILLER_WORDS = [
    "um",
    "uh",
    "like",
    "you know",
    "actually",
    "basically",
    "so"
]


# ============================================================
# EXTRACT AUDIO FROM VIDEO
# ============================================================

def extract_audio(video_path):

    temp_audio = tempfile.NamedTemporaryFile(
        suffix=".wav",
        delete=False
    )

    audio_path = temp_audio.name

    command = [
        "ffmpeg",
        "-i",
        video_path,
        "-ar",
        "16000",
        "-ac",
        "1",
        "-y",
        audio_path
    ]

    subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    return audio_path


# ============================================================
# FILLER WORD ANALYSIS
# ============================================================

def count_filler_words(text):

    text = text.lower()

    count = 0

    for word in FILLER_WORDS:
        count += text.count(word)

    return count


# ============================================================
# SPEAKING RATE
# ============================================================

def calculate_wpm(text, duration):

    words = len(text.split())

    if duration == 0:
        return 0

    return words / (duration / 60)


# ============================================================
# PAUSE DETECTION
# ============================================================

def detect_pauses(audio, sr):

    intervals = librosa.effects.split(
        audio,
        top_db=25
    )

    pause_count = 0
    total_pause_duration = 0

    for i in range(len(intervals) - 1):

        current_end = intervals[i][1]
        next_start = intervals[i + 1][0]

        pause_duration = (
            next_start - current_end
        ) / sr

        if pause_duration > 0.5:

            pause_count += 1
            total_pause_duration += pause_duration

    average_pause = 0

    if pause_count > 0:
        average_pause = (
            total_pause_duration /
            pause_count
        )

    return (
        pause_count,
        total_pause_duration,
        average_pause
    )


# ============================================================
# GENERATE REPORT
# ============================================================

def generate_report(video_path):

    audio_path = extract_audio(video_path)

    result = model.transcribe(audio_path)

    transcript = result["text"]

    audio, sr = librosa.load(
        audio_path,
        sr=None
    )

    duration = librosa.get_duration(
        y=audio,
        sr=sr
    )

    filler_count = count_filler_words(
        transcript
    )

    word_count = len(
        transcript.split()
    )

    wpm = calculate_wpm(
        transcript,
        duration
    )

    (
        pause_count,
        total_pause_duration,
        average_pause
    ) = detect_pauses(
        audio,
        sr
    )

    if os.path.exists(audio_path):
        os.remove(audio_path)

    report = {
        "transcript": transcript,
        "duration": round(duration, 2),
        "word_count": word_count,
        "wpm": round(wpm, 2),
        "filler_words": filler_count,
        "pause_count": pause_count,
        "total_pause_duration":
            round(total_pause_duration, 2),
        "average_pause":
            round(average_pause, 2)
    }

    return report


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    report = generate_report(
        "interview.mp4"
    )

    print("\n===== TRANSCRIPT =====\n")

    print(
        report["transcript"]
    )

    print(
        "\n===== INTERVIEW REPORT =====\n"
    )

    print(
        f"Duration: {report['duration']} sec"
    )

    print(
        f"Word Count: {report['word_count']}"
    )

    print(
        f"Speaking Rate: {report['wpm']} WPM"
    )

    print(
        f"Filler Words: {report['filler_words']}"
    )

    print(
        f"Pause Count: {report['pause_count']}"
    )

    print(
        f"Total Pause Duration: "
        f"{report['total_pause_duration']} sec"
    )

    print(
        f"Average Pause: "
        f"{report['average_pause']} sec"
    )

    print("\n===== FEEDBACK =====\n")

    if report["wpm"] < 100:
        print(
            "Speaking speed is slow."
        )

    elif report["wpm"] <= 160:
        print(
            "Speaking speed is good."
        )

    else:
        print(
            "Speaking speed is too fast."
        )

    if report["filler_words"] <= 3:
        print(
            "Low filler-word usage."
        )

    elif report["filler_words"] <= 8:
        print(
            "Moderate filler-word usage."
        )

    else:
        print(
            "High filler-word usage."
        )

    if report["average_pause"] < 1:
        print(
            "Pause control is good."
        )

    elif report["average_pause"] < 3:
        print(
            "Moderate pauses detected."
        )

    else:
        print(
            "Long pauses detected."
        )
