import whisper
import librosa
FILLER_WORDS = [
    "um",
    "uh",
    "like",
    "you know",
    "actually",
    "basically",
    "so"
]
print("Loading Whisper Model...")
model = whisper.load_model("base")
def analyze_audio(audio_file):
    print(f"Transcribing audio: {audio_file}")
    result = model.transcribe(audio_file)
    transcript = result["text"].strip()
    print("\n===== TRANSCRIPT =====")
    print(transcript)
    text_lower = transcript.lower()
    filler_count = 0
    for word in FILLER_WORDS:
        filler_count += text_lower.count(word)
    audio, sr = librosa.load(audio_file, sr=None)
    duration = librosa.get_duration(
        y=audio,
        sr=sr
    )
    word_count = len(transcript.split())
    if duration > 0:
        wpm = word_count / (duration / 60)
    else:
        wpm = 0
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
  
    if pause_count > 0:
        average_pause = (
            total_pause_duration / pause_count
        )
    else:
        average_pause = 0
   
    if wpm < 100:
        speed_feedback = "Speaking speed is slow."
    elif wpm <= 160:
        speed_feedback = "Speaking speed is good."
    else:
        speed_feedback = "Speaking speed is too fast."
        
    if filler_count <= 3:
        filler_feedback = "Filler word usage is low."
    elif filler_count <= 8:
        filler_feedback = "Moderate filler word usage."
    else:
        filler_feedback = "Too many filler words detected."
        
    if average_pause < 1:
        pause_feedback = "Pause control is good."
    elif average_pause < 3:
        pause_feedback = "Moderate pauses detected."
    else:
        pause_feedback = "Long pauses detected. Practice smoother delivery."
        
    analysis = {
        "transcript": transcript,
        "duration": round(duration, 2),
        "word_count": word_count,
        "speaking_rate": round(wpm, 2),
        "filler_count": filler_count,
        "pause_count": pause_count,
        "total_pause_duration": round(total_pause_duration, 2),
        "average_pause": round(average_pause, 2),
        "feedback": {
            "speaking_speed": speed_feedback,
            "filler_words": filler_feedback,
            "pause_control": pause_feedback
        }
    }
    return analysis
