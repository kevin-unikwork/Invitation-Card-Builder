import json
from video_processing import render_timed_json_video_template

template = json.load(open("static/template/1013.json"))
data = {
    "bride_name": "Eleanor",
    "groom_name": "Alexander",
    "date": "Saturday, October 24th, 2026",
    "time": "at 4:00 PM in the afternoon",
    "venue_name": "The Grand Hotel",
    "venue_address": "123 Elegance Boulevard, Paris"
}

output_path = render_timed_json_video_template(template, data, output_override="static/output/1013_rendered.mp4")
print("Rendered:", output_path)
