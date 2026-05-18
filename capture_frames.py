from moviepy import VideoFileClip
from PIL import Image

clip = VideoFileClip("static/template_media/Back_Green and Pink Illustrated Ring Ceremony Mobile Video.mp4")
frame_5 = clip.get_frame(5)
frame_10 = clip.get_frame(10)

Image.fromarray(frame_5).save("frame_5.png")
Image.fromarray(frame_10).save("frame_10.png")
print("Saved frame_5.png and frame_10.png")
