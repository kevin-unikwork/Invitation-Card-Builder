import json
from moviepy_video_renderer import render_video_with_moviepy

def test_render():
    with open("static/template/1012.json", "r") as f:
        template = json.load(f)
    with open("request_1012.json", "r") as f:
        data = json.load(f)
    
    render_video_with_moviepy(template, data, output_override="static/output/1012_test_render.mp4")

if __name__ == "__main__":
    test_render()
