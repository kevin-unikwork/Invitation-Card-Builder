import json

def update_1007():
    path = "/home/kevin/Invitation_research/static/template/1007.json"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    # Global Animations
    data["global_animations"] = [
        {
            "preset": "fade_out",
            "start": 4.5,
            "targets": "all"
        }
    ]
    
    # Factor to speed up entry animations
    speed_factor = 0.5
    
    # Layer processing
    max_end_time = 0
    
    # First pass: Update entry animations and find the overall end time
    for layer in data.get("layers", []):
        if "animations" not in layer:
            continue
            
        new_anims = []
        for anim in layer["animations"]:
            # If it's the settle scale (starts at 3.5), we'll handle it in second pass
            if anim.get("property") == "scale" and anim.get("start") >= 3.0:
                continue
                
            # Speed up entry animations
            anim["start"] = round(anim.get("start", 0) * speed_factor, 2)
            # Optionally shorten duration too? User said "increase speed of text loading"
            # Let's shorten duration slightly to make it feel snappier
            anim["duration"] = round(anim.get("duration", 0) * 0.8, 2)
            
            end_time = anim["start"] + anim["duration"]
            if end_time > max_end_time:
                max_end_time = end_time
            
            new_anims.append(anim)
        layer["animations"] = new_anims

    # Second pass: Add settle scale starting exactly after all entries finish
    settle_start = round(max_end_time, 2)
    video_dur = data.get("duration", 5.0)
    settle_dur = round(video_dur - settle_start, 2)
    
    for layer in data.get("layers", []):
        if "animations" not in layer:
            layer["animations"] = []
            
        layer["animations"].append({
            "property": "scale",
            "from": 1.0,
            "to": 1.08, # Make it slightly more prominent
            "duration": settle_dur,
            "easing": "linear",
            "start": settle_start
        })

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

if __name__ == "__main__":
    update_1007()
