import json
import os
import time
import random
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException ## type: ignore
from utils.date_utils import expand_event_date, _parse_date
import video_processing


router = APIRouter(prefix="/user-templates", tags=["User Templates"])


@router.post("/submit")
def submit_template_data(
    payload: dict
):
    template_id = payload.get("template_id")
    filled_data = payload.get("filled_data") or {}
    if not isinstance(filled_data, dict):
        raise HTTPException(status_code=400, detail="filled_data must be an object")

    extra_data = {
        key: value
        for key, value in payload.items()
        if key not in {"template_id", "filled_data"}
    }
    if extra_data:
        filled_data = {**filled_data, **extra_data}

    filled_data = expand_event_date(filled_data)

    if not template_id:
        raise HTTPException(status_code=400, detail="template_id is required")

    template_path = f"static/template/{template_id}.json"
    if not os.path.exists(template_path):
        raise HTTPException(status_code=404, detail="Template not found")

    with open(template_path) as f:
        template = json.load(f)

    # Validate required fields
    required_fields = [
        layer["key"]
        for layer in template.get("layers", [])
        if layer.get("type") == "text"
        and layer.get("key")
        and layer.get("required", False)
    ]
    missing_fields = [f for f in required_fields if not filled_data.get(f)]
    if missing_fields:
        raise HTTPException(status_code=400, detail=f"Missing required fields: {missing_fields}")
    
    # Check if it's a video template
    background_path = str(template.get("background") or "").lower()
    is_video_template = bool(template.get("video")) or background_path.endswith(
        (".mp4", ".mov", ".mkv", ".webm", ".avi")
    )

    fmt = template.get("format", "png")  # "png", "jpeg", or "pdf"  or "video"
    
    if is_video_template:
        try:
            # Render video
            output_path = video_processing.render_timed_json_video_template(template, filled_data,fmt=fmt
)

            # Read generated file
            with open(output_path, 'rb') as f:
                media_bytes = f.read()

            # Clean up temp file
            os.unlink(output_path)

            # Ensure directory exists
            output_dir = os.path.join("static", "output")
            os.makedirs(output_dir, exist_ok=True)

            # Create unique filename
            filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
            file_path = os.path.join(output_dir, filename)

            # Save video to static/output
            with open(file_path, "wb") as f:
                f.write(media_bytes)

            # URL path (used by frontend)
            file_url = f"/static/output/{filename}"

        except Exception as e:
         
            raise HTTPException(status_code=500, detail=str(e))

    return {
        "status": "success",
        "template_id": template_id,
        "output": {
            "url": file_url,
        },
    }