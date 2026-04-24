#!/usr/bin/env python
import json
import video_processing

# Load template
with open("static/template/1007.json") as f:
    template = json.load(f)

# Test data
filled_data = {
    "personName": "John",
    "partnerName": "Jane",
    "event_date": "2025-06-15",
    "time": "6:00 PM",
    "venue": "St. Mary's Church",
    "venueAddress": "123 Main Street, Hometown",
    "phone": "(555) 123-4567"
}

# Render
try:
    output_path = video_processing.render_timed_json_video_template(template, filled_data)
    print(f"✓ Rendered successfully to: {output_path}")
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
