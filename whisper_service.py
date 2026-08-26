import os
import re

import librosa
import whisper


# ============================================================
# WHISPER MODEL
# ============================================================

print("Loading Whisper model...")

model = whisper.load_model("base")

print("Whisper model loaded")


# ============================================================
# FILLER WORDS
# ============================================================

FILLER_WORDS = [
    "um",
    "uh",
    "like",
    "you know",
    "actually",
    "basically",
    "so",
]


# ============================================================
# COUNT FILLER WORDS
# ============================================================

def count_filler_words(text):
    """
    Count filler words using word boundaries so that
    words such as 'something' do not incorrectly count as 'so'.
    """

    text = text.lower()

    count = 0

    for phrase in FILLER_WORDS:
        pattern = r"\b" + re.escape(phrase) + r"\b"
        count += len(re.findall(pattern, text))

    return count


# ============================================================
# CALCULATE WPM
# ============================================================

def calculate_wpm(text, duration):
    if duration <= 0:
        return 0

    word_count = len(text.split())

    return word_count / (duration / 60)


# ============================================================
# DETECT PAUSES
# ============================================================

def detect_pauses(audio, sr):

    intervals = librosa.effects.split(
        audio,
        top_db=25
    )

    pause_count = 0
    total_pause_duration = 0.0

    for i in range(len(intervals) - 1):

        current_end = intervals[i][1]
        next_start = intervals[i + 1][0]

        pause_duration = (
            next_start - current_end
        ) / sr

        if pause_duration >= 0.5:

            pause_count += 1
            total_pause_duration += pause_duration

    average_pause = 0.0

    if pause_count > 0:
        average_pause = (
            total_pause_duration / pause_count
        )

    return (
        pause_count,
        total_pause_duration,
        average_pause
    )


# ============================================================
# GENERATE REPORT FROM AUDIO
# ============================================================

def generate_report(audio_path):

    if not os.path.exists(audio_path):
        raise FileNotFoundError(
            f"Audio file not found: {audio_path}"
        )

    if not audio_path.lower().endswith(".wav"):
        raise ValueError(
            "generate_report() expects a WAV audio file."
        )

    # --------------------------------------------------------
    # WHISPER TRANSCRIPTION
    # --------------------------------------------------------

    result = model.transcribe(
        audio_path,
        fp16=False
    )

    transcript = result.get(
        "text",
        ""
    ).strip()

    # --------------------------------------------------------
    # LOAD AUDIO
    # --------------------------------------------------------

    audio, sr = librosa.load(
        audio_path,
        sr=16000,
        mono=True
    )

    duration = librosa.get_duration(
        y=audio,
        sr=sr
    )

    # --------------------------------------------------------
    # METRICS
    # --------------------------------------------------------

    word_count = len(
        transcript.split()
    )

    filler_words = count_filler_words(
        transcript
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

    # --------------------------------------------------------
    # RETURN REPORT
    # --------------------------------------------------------

    return {
        "transcript": transcript,
        "duration": round(duration, 2),
        "word_count": word_count,
        "wpm": round(wpm, 2),
        "filler_words": filler_words,
        "pause_count": pause_count,
        "total_pause_duration": round(
            total_pause_duration,
            2
        ),
        "average_pause": round(
            average_pause,
            2
        )
    }


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    AUDIO_FILE = "interview_audio.wav"

    try:

        report = generate_report(
            AUDIO_FILE
        )

        print("\n==============================")
        print("       INTERVIEW REPORT")
        print("==============================\n")

        print(
            "Transcript:",
            report["transcript"]
        )

        print(
            "Duration:",
            report["duration"],
            "sec"
        )

        print(
            "Word Count:",
            report["word_count"]
        )

        print(
            "Speaking Rate:",
            report["wpm"],
            "WPM"
        )

        print(
            "Filler Words:",
            report["filler_words"]
        )

        print(
            "Pause Count:",
            report["pause_count"]
        )

        print(
            "Total Pause Duration:",
            report["total_pause_duration"],
            "sec"
        )

        print(
            "Average Pause:",
            report["average_pause"],
            "sec"
        )

    except Exception as error:

        print("\nERROR:")
        print(error)
