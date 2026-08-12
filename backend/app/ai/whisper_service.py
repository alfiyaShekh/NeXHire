import whisper
import librosa
import numpy as np
AUDIO_FILE = "interview.wav"
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
print("Transcribing Audio...")
result = model.transcribe(AUDIO_FILE)
transcript = result["text"]
print("\n===== TRANSCRIPT =====")
print(transcript)
text_lower = transcript.lower()
filler_count = 0
for word in FILLER_WORDS:
    filler_count += text_lower.count(word)
audio, sr = librosa.load(AUDIO_FILE)
duration = librosa.get_duration(y=audio, sr=sr)
word_count = len(transcript.split())
wpm = word_count / (duration / 60)
intervals = librosa.effects.split(
    audio,
    top_db=25
)
pause_count = 0
total_pause_duration = 0
for i in range(len(intervals) - 1):
    current_end = intervals[i][1]
    next_start = intervals[i + 1][0]
    pause_duration = (next_start - current_end) / sr
    if pause_duration > 0.5:
        pause_count += 1
        total_pause_duration += pause_duration
average_pause = (
    total_pause_duration / pause_count
    if pause_count > 0
    else 0
)
print("\n===== INTERVIEW ANALYSIS REPORT =====")
print(f"Duration              : {duration:.2f} sec")
print(f"Total Words           : {word_count}")
print(f"Speaking Rate         : {wpm:.2f} WPM")
print(f"Filler Words Found    : {filler_count}")
print(f"Pause Count           : {pause_count}")
print(f"Total Pause Duration  : {total_pause_duration:.2f} sec")
print(f"Average Pause Length  : {average_pause:.2f} sec")
print("\n===== FEEDBACK =====")
if wpm < 100:
    print("• Speaking speed is slow.")
elif wpm <= 160:
    print("• Speaking speed is good.")
else:
    print("• Speaking speed is too fast.")
if filler_count <= 3:
    print("• Filler word usage is low.")
elif filler_count <= 8:
    print("• Moderate filler word usage.")
else:
    print("• Too many filler words detected.")
if average_pause < 1:
    print("• Pause control is good.")
elif average_pause < 3:
    print("• Moderate pauses detected.")
else:
    print("• Long pauses detected. Practice smoother delivery.")
