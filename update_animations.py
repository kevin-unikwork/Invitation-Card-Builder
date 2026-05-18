import json

with open("static/template/1009.json", "r") as f:
    data = json.load(f)

# 1. Update presets with new high-end options
data["animation_presets"].update({
    "cinematic_typewriter": [
      { "property": "opacity", "from": 0, "to": 0, "duration": 0.01, "start": 0 },
      { "property": "opacity", "from": 0, "to": 1, "duration": 0.4, "start": 0 },
      { "property": "typewriter_bounce", "duration": 1.4, "easing": "easeOutBack", "start": 0 },
      { "property": "glow", "from": 3, "to": 0, "duration": 1.5, "easing": "easeOutQuad", "start": 0.2 }
    ],
    "blur_in_slide_up": [
      { "property": "opacity", "from": 0, "to": 0, "duration": 0.01, "start": 0 },
      { "property": "opacity", "from": 0, "to": 1, "duration": 0.8, "easing": "easeOutCubic", "start": 0 },
      { "property": "slide_y", "from": 40, "to": 0, "duration": 0.8, "easing": "easeOutCubic", "start": 0 },
      { "property": "blur", "from": 12, "to": 0, "duration": 0.8, "easing": "easeOutCubic", "start": 0 }
    ],
    "blur_zoom_in": [
      { "property": "opacity", "from": 0, "to": 0, "duration": 0.01, "start": 0 },
      { "property": "opacity", "from": 0, "to": 1, "duration": 1.0, "easing": "easeOutQuint", "start": 0 },
      { "property": "scale", "from": 0.85, "to": 1, "duration": 1.2, "easing": "easeOutQuint", "start": 0 },
      { "property": "blur", "from": 15, "to": 0, "duration": 1.0, "easing": "easeOutQuint", "start": 0 }
    ],
    "elegant_glow_in": [
      { "property": "opacity", "from": 0, "to": 0, "duration": 0.01, "start": 0 },
      { "property": "opacity", "from": 0, "to": 1, "duration": 1.5, "easing": "easeOutSine", "start": 0 },
      { "property": "glow", "from": 4, "to": 0, "duration": 1.5, "easing": "easeOutSine", "start": 0 }
    ],
    "glow_swing_pop": [
      { "property": "opacity", "from": 0, "to": 1, "duration": 0.4 },
      { "property": "scale", "from": 0, "to": 1, "duration": 0.9, "easing": "easeOutBack" },
      { "property": "rotation", "from": -15, "to": 0, "duration": 1.0, "easing": "easeOutElastic" },
      { "property": "glow", "from": 3, "to": 0, "duration": 1.0 }
    ],
    "wave_in": [
      { "property": "opacity", "from": 0, "to": 1, "duration": 0.5 },
      { "property": "wave", "from": 0, "to": 1, "duration": 1.5, "easing": "easeOutQuad" },
      { "property": "glow", "from": 2, "to": 0, "duration": 1.0 }
    ],
    "elastic_blur": [
      { "property": "opacity", "from": 0, "to": 1, "duration": 0.3 },
      { "property": "elastic", "from": 0, "to": 1, "duration": 1.0, "easing": "easeOutElastic" },
      { "property": "blur", "from": 10, "to": 0, "duration": 0.8 }
    ]
})

# Update layers mappings
preset_replacements = {
    "typewriter_bounce_smooth": "cinematic_typewriter",
    "slide_up_fade": "blur_in_slide_up",
    "swing_pop": "glow_swing_pop",
    "rubber_band_in": "wave_in",
    "bounce_drop": "elastic_blur",
    "glow_in": "elegant_glow_in",
    "slide_down_fade": "blur_zoom_in"
}

for layer in data["layers"]:
    if layer["id"] == "s3_event_date":
        layer["animations"] = [
            { "property": "opacity", "from": 0, "to": 1, "start": 13.2, "duration": 1.0, "easing": "easeOutQuint" },
            { "property": "slide_x", "from": -80, "to": 0, "start": 13.2, "duration": 1.0, "easing": "easeOutQuint" },
            { "property": "blur", "from": 12, "to": 0, "start": 13.2, "duration": 1.0, "easing": "easeOutQuint" },
            { "preset": "exit_fade_out", "start": 17.4 }
        ]
        continue

    for anim in layer["animations"]:
        if "preset" in anim and anim["preset"] in preset_replacements:
            anim["preset"] = preset_replacements[anim["preset"]]

with open("static/template/1009.json", "w", encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Updated 1009 animations successfully.")
