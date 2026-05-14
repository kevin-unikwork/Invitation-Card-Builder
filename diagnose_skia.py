import numpy as np
from PIL import Image, ImageDraw, ImageFont
import skia

# =========================================
# STEP 1: Create text with PIL
# =========================================
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 80)
temp = Image.new('RGBA', (1, 1))
d = ImageDraw.Draw(temp)
bbox = d.textbbox((0, 0), 'HELLO CENTER', font=font)
tw = bbox[2] - bbox[0] + 20
th = bbox[3] - bbox[1] + 20

pil_text = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
d2 = ImageDraw.Draw(pil_text)
d2.text((10 - bbox[0], 10 - bbox[1]), 'HELLO CENTER', fill=(0, 0, 0, 255), font=font)
pil_text.save('static/output/diag_1_pil_text.png')
print(f'[DIAG] PIL image size (w,h): {pil_text.size}')

# =========================================
# STEP 2: PIL-only compositing (GOLD STANDARD)
# =========================================
canvas_pil = Image.new('RGBA', (1080, 1920), (255, 255, 255, 255))
bx = (1080 - tw) // 2
by = (1920 - th) // 2
canvas_pil.paste(pil_text, (bx, by), pil_text)
canvas_pil.convert('RGB').save('static/output/diag_2_pil_composite.png')
print(f'[DIAG] PIL composite: text at ({bx}, {by})')

# =========================================
# STEP 3: Skia compositing via fromarray
# =========================================
arr = np.array(pil_text)
print(f'[DIAG] Numpy shape: {arr.shape}, dtype: {arr.dtype}, contiguous: {arr.flags["C_CONTIGUOUS"]}')
print(f'[DIAG] Numpy strides: {arr.strides}')

skia_img_a = skia.Image.fromarray(arr, colorType=skia.ColorType.kRGBA_8888_ColorType)
print(f'[DIAG] Skia Image (fromarray) w={skia_img_a.width()}, h={skia_img_a.height()}')

info = skia.ImageInfo.Make(1080, 1920, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
canvas_arr = np.full((1920, 1080, 4), 255, dtype=np.uint8)
surface = skia.Surface.MakeRasterDirect(info, canvas_arr)

with surface as c:
    paint = skia.Paint(AntiAlias=True)
    c.drawImage(skia_img_a, float(bx), float(by), skia.SamplingOptions(), paint)

result = canvas_arr[:, :, :3].copy()
Image.fromarray(result).save('static/output/diag_3_skia_fromarray.png')

is_not_white = np.any(result < 250, axis=2)
ys, xs = np.where(is_not_white)
if len(xs) > 0:
    print(f'[DIAG] Skia fromarray content: x=[{xs.min()}, {xs.max()}], y=[{ys.min()}, {ys.max()}], w={xs.max()-xs.min()}, h={ys.max()-ys.min()}')
else:
    print('[DIAG] Skia fromarray: NO VISIBLE CONTENT!')

# =========================================
# STEP 4: Skia with explicit Image constructor
# =========================================
canvas_arr2 = np.full((1920, 1080, 4), 255, dtype=np.uint8)
surface2 = skia.Surface.MakeRasterDirect(info, canvas_arr2)

row_bytes = arr.shape[1] * 4
img_info = skia.ImageInfo.Make(arr.shape[1], arr.shape[0], skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kUnpremul_AlphaType)
try:
    skia_img_b = skia.Image(img_info, arr.tobytes(), row_bytes)
    print(f'[DIAG] Skia Image (manual) w={skia_img_b.width()}, h={skia_img_b.height()}')
    with surface2 as c:
        paint = skia.Paint(AntiAlias=True)
        c.drawImage(skia_img_b, float(bx), float(by), skia.SamplingOptions(), paint)
    result2 = canvas_arr2[:, :, :3].copy()
    Image.fromarray(result2).save('static/output/diag_4_skia_manual.png')
    is_not_white2 = np.any(result2 < 250, axis=2)
    ys2, xs2 = np.where(is_not_white2)
    if len(xs2) > 0:
        print(f'[DIAG] Manual bytes content: x=[{xs2.min()}, {xs2.max()}], y=[{ys2.min()}, {ys2.max()}], w={xs2.max()-xs2.min()}, h={ys2.max()-ys2.min()}')
    else:
        print('[DIAG] Manual bytes: NO VISIBLE CONTENT!')
except Exception as e:
    print(f'[DIAG] Manual bytes FAILED: {e}')

# =========================================
# STEP 5: Direct numpy alpha blend (NO SKIA)
# =========================================
canvas_arr3 = np.full((1920, 1080, 3), 255, dtype=np.uint8)
text_rgba = np.array(pil_text)
alpha = text_rgba[:, :, 3:4].astype(np.float32) / 255.0
text_rgb = text_rgba[:, :, :3].astype(np.float32)

y1, y2 = by, by + th
x1, x2 = bx, bx + tw
bg_region = canvas_arr3[y1:y2, x1:x2].astype(np.float32)
blended = (text_rgb * alpha + bg_region * (1 - alpha)).astype(np.uint8)
canvas_arr3[y1:y2, x1:x2] = blended
Image.fromarray(canvas_arr3).save('static/output/diag_5_numpy_blend.png')
print(f'[DIAG] Numpy blend: text at ({x1},{y1}) to ({x2},{y2})')

is_not_white3 = np.any(canvas_arr3 < 250, axis=2)
ys3, xs3 = np.where(is_not_white3)
if len(xs3) > 0:
    print(f'[DIAG] Numpy blend content: x=[{xs3.min()}, {xs3.max()}], y=[{ys3.min()}, {ys3.max()}], w={xs3.max()-xs3.min()}, h={ys3.max()-ys3.min()}')

print('\n=== ALL DIAGNOSTICS COMPLETE ===')
