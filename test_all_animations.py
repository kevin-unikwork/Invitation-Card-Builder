import json
import logging
from pathlib import Path
from moviepy_video_renderer import render_video_with_moviepy

# Setup logging
logging.basicConfig(level=logging.INFO)

def test_animations():
    template_path = "static/template/test_animations_ultimate.json"
    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)
        
    data = {} # No dynamic data needed for this test
    
    output_path = "static/output/animation_test_bench_ultimate.mp4"
    template["output"] = output_path
    
    print(f"Starting render of {output_path}...")
    render_video_with_moviepy(template, data)
    print(f"Render complete: {output_path}")

if __name__ == "__main__":
    test_animations()
