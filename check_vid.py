from moviepy import VideoFileClip
try:
    c = VideoFileClip("static/template_media/Back_AI_Invitation.mp4")
    print(c.w, c.h, c.duration)
except Exception as e:
    print(e)
