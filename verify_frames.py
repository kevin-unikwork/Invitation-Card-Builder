import numpy as np
from PIL import Image

# Extract frames from the video and analyze
import subprocess

for ts, name in [("00:00:01", "verify_1s"), ("00:00:05", "verify_5s"), ("00:00:12", "verify_12s"), ("00:00:20", "verify_20s")]:
    subprocess.run([
        "ffmpeg", "-y", "-i", "static/output/animation_test_bench_ultimate.mp4",
        "-ss", ts, "-vframes", "1", "-update", "1",
        f"static/output/{name}.png"
    ], capture_output=True)

# Analyze the first frame
img = Image.open("static/output/verify_1s.png").convert("RGB")
arr = np.array(img)
print(f"Frame size: {arr.shape}")

is_not_white = np.any(arr < 250, axis=2)
ys, xs = np.where(is_not_white)
if len(xs) > 0:
    print(f"Content bounding box: x=[{xs.min()}, {xs.max()}], y=[{ys.min()}, {ys.max()}]")
    print(f"Content width: {xs.max() - xs.min()}, height: {ys.max() - ys.min()}")
    x_center = (xs.min() + xs.max()) / 2
    print(f"Content center X: {x_center:.0f} (canvas center: 540)")
    print(f"Offset from center: {abs(x_center - 540):.0f} pixels")
else:
    print("Frame is completely white - no content!")
