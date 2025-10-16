import os
import subprocess

VIDEO_DIR = "/home/singsong/Desktop/flight_instructor/asr-pipeline/videos"
THUMB_DIR = (
    "/home/singsong/Desktop/flight_instructor/asr-pipeline/web/assets/img/thumbnails"
)
os.makedirs(THUMB_DIR, exist_ok=True)

for filename in os.listdir(VIDEO_DIR):
    if filename.lower().endswith(".mp4"):
        video_path = os.path.join(VIDEO_DIR, filename)
        thumb_path = os.path.join(THUMB_DIR, os.path.splitext(filename)[0] + ".jpg")

        # Extract frame at 5 seconds
        cmd = [
            "ffmpeg",
            "-ss",
            "00:00:05",
            "-i",
            video_path,
            "-frames:v",
            "1",
            "-q:v",
            "2",
            thumb_path,
            "-y",
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

print("✅ Thumbnails created in:", THUMB_DIR)
