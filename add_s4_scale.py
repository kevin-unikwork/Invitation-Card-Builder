import json

with open("static/template/1009.json", "r", encoding="utf-8") as f:
    data = json.load(f)

# The global fade out starts at 25.4.
# Screen 4 elements finish loading around 21.75.
# Let's add a slow synchronized scale-up starting at 22.0 and lasting 3.4 seconds until fade out.
scale_animation = {
    "property": "scale",
    "from": 1.0,
    "to": 1.08,
    "start": 22.0,
    "duration": 3.4,
    "easing": "linear"
}

for layer in data["layers"]:
    if layer["id"].startswith("s4_"):
        # Append the scale animation
        layer["animations"].append(scale_animation.copy())

with open("static/template/1009.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Added synchronized scale-up animation to all Screen 4 elements.")
