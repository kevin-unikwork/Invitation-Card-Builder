import json
from moviepy_video_renderer import render_video_with_moviepy

with open('static/template/1011.json') as f:
    template = json.load(f)

with open('request_1011.json') as f:
    request = json.load(f)

template['output'] = 'static/output/video_1011_test.mp4'

render_video_with_moviepy(template, request['filled_data'])
print('Done!')
