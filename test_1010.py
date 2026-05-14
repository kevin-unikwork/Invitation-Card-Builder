import json
import os
from moviepy_video_renderer import render_video_with_moviepy

template_path = "static/template/1010.json"
data = {
    "bride_name": "Virat",
    "groom_name": "Anushka",
    "wedding_date": "2026-02-14",
    "venue_line1": "Surat, Gujarat"
}

with open(template_path, 'r', encoding='utf-8') as f:
    template = json.load(f)

output_file = "static/output/1010_test_render.mp4"
render_video_with_moviepy(template, data, output_override=output_file)
print(f"Rendered video to {output_file}")
