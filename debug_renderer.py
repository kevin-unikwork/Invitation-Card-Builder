import json
import numpy as np
from PIL import Image
from video_processing import _render_text_to_pil
import skia

# Load template
with open('static/template/test_animations_ultimate.json') as f:
    template = json.load(f)

width, height = 1080, 1920

# Render just the first layer
layer = template['layers'][0]
text = layer['value']
layer_copy = dict(layer)
layer_copy['font_size'] = int(layer.get('font_size', 40))

pil_img = _render_text_to_pil(text, layer_copy, layer.get('font', 'sans-serif'), None)
print(f'PIL image size: {pil_img.size}')
pil_img.save('static/output/debug_layer0_pil.png')

arr = np.array(pil_img)
print(f'Numpy shape: {arr.shape}, dtype: {arr.dtype}')
print(f'Channels: {arr.shape[2]}')
print(f'Alpha min/max: {arr[:,:,3].min()}/{arr[:,:,3].max()}')
print(f'Pixel [0,0]: {arr[0,0]}')

text_mask = arr[:,:,3] > 0
print(f'Non-transparent pixels: {text_mask.sum()}')

# Skia image
skia_img = skia.Image.fromarray(arr, colorType=skia.ColorType.kRGBA_8888_ColorType)
l_w, l_h = skia_img.width(), skia_img.height()
print(f'Skia image: w={l_w}, h={l_h}')

bx = (1080 - l_w) / 2
by = 100.0
print(f'Draw position: bx={bx}, by={by}')

# Test 1: Skia on a pre-allocated RGBA array
bg_arr = np.full((height, width, 4), 255, dtype=np.uint8)
info = skia.ImageInfo.Make(width, height, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
surface = skia.Surface.MakeRasterDirect(info, bg_arr)

with surface as canvas:
    paint = skia.Paint(AntiAlias=True, Alphaf=1.0)
    canvas.drawImage(skia_img, bx, by, skia.SamplingOptions(skia.FilterMode.kLinear), paint)

result_rgb = bg_arr[:, :, :3].copy()
Image.fromarray(result_rgb).save('static/output/debug_frame_simple.png')

is_not_white = np.any(result_rgb < 250, axis=2)
ys, xs = np.where(is_not_white)
if len(xs) > 0:
    print(f'[TEST1] Pre-alloc content: x=[{xs.min()},{xs.max()}], y=[{ys.min()},{ys.max()}], w={xs.max()-xs.min()}')
else:
    print('[TEST1] NO CONTENT!')

# Test 2: MoviePy ColorClip frame + concatenation (exactly like the renderer does)
from moviepy import ColorClip
bg_clip = ColorClip(size=(width, height), color=(255, 255, 255), duration=1)
bg_rgb = bg_clip.get_frame(0)
print(f'\nMoviePy frame: shape={bg_rgb.shape}, dtype={bg_rgb.dtype}')

frame_arr = np.concatenate([bg_rgb, np.full((height, width, 1), 255, dtype=np.uint8)], axis=-1)
print(f'Concatenated: shape={frame_arr.shape}, dtype={frame_arr.dtype}, contiguous={frame_arr.flags["C_CONTIGUOUS"]}')
print(f'Concatenated strides: {frame_arr.strides}')

surface2 = skia.Surface.MakeRasterDirect(info, frame_arr)
if surface2 is None:
    print('[TEST2] SURFACE IS NONE - MakeRasterDirect FAILED!')
else:
    with surface2 as canvas:
        paint = skia.Paint(AntiAlias=True, Alphaf=1.0)
        canvas.drawImage(skia_img, bx, by, skia.SamplingOptions(skia.FilterMode.kLinear), paint)

    result_rgb2 = frame_arr[:, :, :3].copy()
    Image.fromarray(result_rgb2).save('static/output/debug_frame_moviepy.png')

    is_not_white2 = np.any(result_rgb2 < 250, axis=2)
    ys2, xs2 = np.where(is_not_white2)
    if len(xs2) > 0:
        print(f'[TEST2] MoviePy content: x=[{xs2.min()},{xs2.max()}], y=[{ys2.min()},{ys2.max()}], w={xs2.max()-xs2.min()}')
    else:
        print('[TEST2] NO CONTENT IN MOVIEPY FRAME!')

# Test 3: Force contiguous copy of MoviePy frame
frame_arr3 = np.ascontiguousarray(np.concatenate([bg_rgb, np.full((height, width, 1), 255, dtype=np.uint8)], axis=-1))
print(f'\nForced contiguous: shape={frame_arr3.shape}, contiguous={frame_arr3.flags["C_CONTIGUOUS"]}, strides={frame_arr3.strides}')

surface3 = skia.Surface.MakeRasterDirect(info, frame_arr3)
if surface3 is None:
    print('[TEST3] SURFACE IS NONE!')
else:
    with surface3 as canvas:
        paint = skia.Paint(AntiAlias=True, Alphaf=1.0)
        canvas.drawImage(skia_img, bx, by, skia.SamplingOptions(skia.FilterMode.kLinear), paint)

    result_rgb3 = frame_arr3[:, :, :3].copy()
    Image.fromarray(result_rgb3).save('static/output/debug_frame_contiguous.png')

    is_not_white3 = np.any(result_rgb3 < 250, axis=2)
    ys3, xs3 = np.where(is_not_white3)
    if len(xs3) > 0:
        print(f'[TEST3] Contiguous content: x=[{xs3.min()},{xs3.max()}], y=[{ys3.min()},{ys3.max()}], w={xs3.max()-xs3.min()}')
    else:
        print('[TEST3] NO CONTENT!')

print('\n=== ALL DEBUG COMPLETE ===')
