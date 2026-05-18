import json
import os
from moviepy_video_renderer import render_video_with_moviepy

template_path = "static/template/1009_green_pink.json"
data = {
    "bride_name": "Ayesha",
    "groom_name": "Rahul",
    "event_date": "2026-02-14",
    "event_day": "Saturday",
    "event_time": "7:00 PM onwards",
    "venue_name": "The Royal Palace",
    "venue_address": "Lake View, Udaipur"
}

with open(template_path, 'r', encoding='utf-8') as f:
    template = json.load(f)

output_file = "static/output/1009_green_pink_test.mp4"
render_video_with_moviepy(template, data, output_override=output_file)
print(f"Rendered video to {output_file}")
