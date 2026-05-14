import json
from pathlib import Path
from moviepy_video_renderer import render_video_with_moviepy

template_path = Path("static/template/1009.json")
with open(template_path, "r", encoding="utf-8") as f:
    template = json.load(f)

data = {}
output_path = "static/output/test_1009_shadow.mp4"
template["output"] = output_path

print(f"Rendering template 1009 with shadow test...")
render_video_with_moviepy(template, data)
print(f"Done! Saved to {output_path}")
