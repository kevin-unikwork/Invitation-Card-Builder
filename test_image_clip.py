from moviepy import VideoFileClip
try:
    c = VideoFileClip("static/template_media/1005.png")
    print(c.duration)
except Exception as e:
    print("FAILED:", e)
