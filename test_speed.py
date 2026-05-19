import time, json
from moviepy_video_renderer import render_video_with_moviepy
with open('static/template/1009.json', 'r') as f:
    template = json.load(f)
data = {'bride_name':'A','groom_name':'B','event_date':'C'}
t0 = time.time()
render_video_with_moviepy(template, data, 'static/output/speed_test.mp4')
print(f'Time taken: {time.time()-t0:.2f}s')
