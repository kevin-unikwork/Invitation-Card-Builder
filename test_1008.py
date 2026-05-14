import json
import os
from moviepy_video_renderer import render_video_with_moviepy

template_path = "static/template/1008.json"
data = {
    "bride_name": "આયેશા",
    "groom_name": "રાહુલ",
    "wedding_date": "2026-02-14",
    "wedding_day": "શનિવાર",
    "wedding_time": "સાંજે ૭:૦૦ વાગ્યે",
    "venue_line1": "રોયલ પેલેસ",
    "venue_line2": "ઉદયપુર",
    "personName": "આયેશા અને રાહુલ"
}

with open(template_path, 'r', encoding='utf-8') as f:
    template = json.load(f)

output_file = "static/output/1008_test_render.mp4"
render_video_with_moviepy(template, data, output_override=output_file)
print(f"Rendered video to {output_file}")
