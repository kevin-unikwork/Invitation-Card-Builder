import subprocess

# Extract one frame from each animation's active moment
animations = [
    ("00:00:01", "anim_01_fade_in"),
    ("00:00:04", "anim_02_fade_out"),
    ("00:00:07", "anim_03_zoom_in"),
    ("00:00:10", "anim_04_zoom_out"),
    ("00:00:13", "anim_05_slide_up"),
    ("00:00:16", "anim_06_slide_down"),
    ("00:00:19", "anim_07_slide_left"),
    ("00:00:22", "anim_08_slide_right"),
    ("00:00:25", "anim_09_blur_reveal"),
    ("00:00:28", "anim_10_brightness"),
    ("00:00:31", "anim_11_grayscale"),
    ("00:00:34", "anim_12_spin"),
    ("00:00:37", "anim_13_typewriter"),
    ("00:00:40", "anim_14_word_bounce"),
    ("00:00:43", "anim_15_skew_x"),
    ("00:00:46", "anim_16_skew_y"),
    ("00:00:49", "anim_17_letter_space"),
    ("00:00:52", "anim_18_combined"),
]

for ts, name in animations:
    subprocess.run([
        "ffmpeg", "-y", "-i", "static/output/animation_test_bench_ultimate.mp4",
        "-ss", ts, "-vframes", "1", "-update", "1",
        f"static/output/{name}.png"
    ], capture_output=True)
    print(f"Extracted {name} at {ts}")

print("\nAll frames extracted!")
