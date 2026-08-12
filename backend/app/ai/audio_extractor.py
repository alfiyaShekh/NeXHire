import os
from moviepy import VideoFileClip
def extract_audio(video_path, audio_path):
     if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video not found: {video_path}")
    print("Extracting audio from video...")
    video = VideoFileClip(video_path)
    if video.audio is None:
        video.close()
        raise ValueError("The uploaded video does not contain audio.")
    video.audio.write_audiofile(
        audio_path,
        codec="pcm_s16le",
        logger=None
    )
    video.close()
    print(f"Audio saved successfully: {audio_path}")
    return audio_path
