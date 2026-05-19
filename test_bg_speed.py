import time
from moviepy import VideoFileClip, VideoClip

t0 = time.time()
bg_clip = VideoFileClip('static/template_media/Back_Pink Wedding Invitation Mobile Video.mp4', audio=False)
clip = VideoClip(lambda t: bg_clip.get_frame(t), duration=26.07)
clip.write_videofile('static/output/speed_test2.mp4', fps=30, codec='libx264', preset='ultrafast', threads=1)
print(f'Time taken: {time.time()-t0:.2f}s')
