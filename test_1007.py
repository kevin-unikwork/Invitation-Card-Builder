import json
import os
from moviepy_video_renderer import render_video_with_moviepy

# Sample data for template 1007
with open("static/template/1007.json", "r", encoding="utf-8") as f:
    template = json.load(f)

data = {
    "personName": "આર્યન",
    "partnerName": "અદિતિ",
    "event_date": "2024-12-25",
    "time": "સાંજે ૭:૦૦ કલાકે",
    "venue": "ગોકુલધામ પાર્ટી પ્લોટ",
    "venueAddress": "એસ.જી. હાઈવે, અમદાવાદ",
    "phone": "+91 98765 43210"
}

output_path = "static/output/test_1007_elegant.mp4"
template["output"] = output_path

render_video_with_moviepy(template, data)
print(f"Done! Saved to {output_path}")
