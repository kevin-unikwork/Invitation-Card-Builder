import json

with open('static/template/1009.json', 'r') as f:
    data = json.load(f)

# Correct the background file name to the one with spaces
data["background"] = "static/template_media/Back_Pink Wedding Invitation Mobile Video.mp4"

with open('static/template/1009_final.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("Created 1009_final.json")
