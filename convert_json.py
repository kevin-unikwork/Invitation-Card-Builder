import json
import re

with open('static/template/1009.json', 'r') as f:
    data = f.read()

# Change background
data = data.replace('Back_Pink_Wedding_Invitation_Mobile_Video.mp4', 'Back_Green and Pink Illustrated Ring Ceremony Mobile Video.mp4')

# Change colors to fit Green & Pink theme
data = data.replace('"#ffffff"', '"#3a533b"') # White -> Dark Green
data = data.replace('"#f7dde6"', '"#765c27"') # Light pink -> Gold
data = data.replace('"#7a1c3f"', '"#b25f6e"') # Crimson -> Dark Pink/Red
data = data.replace('"#9b3054"', '"#3a533b"') # Raspberry -> Dark Green
data = data.replace('"#c4526e"', '"#b25f6e"') # Pink -> Dark Pink/Red

with open('static/template/1009_green_pink.json', 'w') as f:
    f.write(data)

print("Created 1009_green_pink.json")
