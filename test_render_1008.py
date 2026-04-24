#!/usr/bin/env python
import json
import video_processing

# Load template
with open("static/template/1008.json") as f:
    template = json.load(f)

# Test data
filled_data = {
    "BrideName": "Sarah",
    "GroomName": "Michael",
    "weddingDate": "2025-07-20",
    "venueAddress": "The Grand Hotel, New York"
}

# Render
try:
    output_path = video_processing.render_timed_json_video_template(template, filled_data)
    print(f"Rendered successfully to: {output_path}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
