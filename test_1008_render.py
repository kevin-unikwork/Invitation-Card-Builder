import logging
import sys
from pathlib import Path
import json
from moviepy_video_renderer import render_video_with_moviepy

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s  [%(levelname)-7s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("test_1008")

def test_1008():
    template_path = Path("static/template/1008.json")
    if not template_path.exists():
        logger.error(f"Template not found: {template_path}")
        return

    with open(template_path, "r", encoding="utf-8") as f:
        template = json.load(f)

    # Test data matching the template keys
    input_data = {
        "bride_name": "આયુષી",
        "groom_name": "કેવિન",
        "wedding_date": "2027-02-14",
        "venue_address": "શ્રી સ્વામિનારાયણ મંદિર, અમદાવાદ"
    }

    logger.info(f"Rendering template 1008 with data: {input_data}")
    
    try:
        output_path = render_video_with_moviepy(template, input_data, output_override="static/output/test_1008_moviepy.mp4")
        logger.info(f"Successfully rendered: {output_path}")
    except Exception as e:
        logger.exception("Failed to render video")

if __name__ == "__main__":
    test_1008()
