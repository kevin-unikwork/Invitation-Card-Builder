import os
import math
import logging
from pathlib import Path
import numpy as np
import skia
from moviepy import VideoFileClip, ColorClip, VideoClip, concatenate_videoclips
from PIL import Image

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("moviepy_video_renderer")

PROJECT_ROOT = Path(__file__).parent.resolve()

def _resolve_path(path_str):
    if not path_str: return None
    p = Path(path_str)
    if p.is_absolute(): return p
    return (PROJECT_ROOT / path_str).resolve()

def resolve_text(layer, data):
    val = str(layer.get("value", ""))
    key = layer.get("key")
    if key and key in data: return str(data[key])
    import re
    def replace_match(match):
        k = match.group(1)
        return str(data.get(k, match.group(0)))
    return re.sub(r"\{([^}]+)\}", replace_match, val)

def _to_float(val, default=0.0):
    try: return float(val)
    except: return default

def _get_easing(name):
    # --- Back ---
    if name == "easeOutBack":
        return lambda t: 1 + 2.70158 * pow(t - 1, 3) + 1.70158 * pow(t - 1, 2)
    if name == "easeInBack":
        c1 = 1.70158
        return lambda t: (c1 + 1) * t * t * t - c1 * t * t
    if name == "easeInOutBack":
        c2 = 1.70158 * 1.525
        return lambda t: (pow(2 * t, 2) * ((c2 + 1) * 2 * t - c2)) / 2 if t < 0.5 else (pow(2 * t - 2, 2) * ((c2 + 1) * (t * 2 - 2) + c2) + 2) / 2
    # --- Cubic ---
    if name == "easeInCubic":
        return lambda t: t * t * t
    if name == "easeOutCubic":
        return lambda t: 1 - pow(1 - t, 3)
    if name == "easeInOutCubic":
        return lambda t: 4 * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 3) / 2
    # --- Quad ---
    if name == "easeInQuad":
        return lambda t: t * t
    if name == "easeOutQuad":
        return lambda t: 1 - (1 - t) * (1 - t)
    if name == "easeInOutQuad":
        return lambda t: 2 * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 2) / 2
    # --- Quart ---
    if name == "easeInQuart":
        return lambda t: t * t * t * t
    if name == "easeOutQuart":
        return lambda t: 1 - pow(1 - t, 4)
    if name == "easeInOutQuart":
        return lambda t: 8 * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 4) / 2
    # --- Quint ---
    if name == "easeInQuint":
        return lambda t: t * t * t * t * t
    if name == "easeOutQuint":
        return lambda t: 1 - pow(1 - t, 5)
    if name == "easeInOutQuint":
        return lambda t: 16 * t * t * t * t * t if t < 0.5 else 1 - pow(-2 * t + 2, 5) / 2
    # --- Expo ---
    if name == "easeInExpo":
        return lambda t: 0 if t == 0 else pow(2, 10 * t - 10)
    if name == "easeOutExpo":
        return lambda t: 1 if t == 1 else 1 - pow(2, -10 * t)
    if name == "easeInOutExpo":
        return lambda t: 0 if t == 0 else (1 if t == 1 else (pow(2, 20 * t - 10) / 2 if t < 0.5 else (2 - pow(2, -20 * t + 10)) / 2))
    # --- Sine ---
    if name == "easeInSine":
        return lambda t: 1 - math.cos((t * math.pi) / 2)
    if name == "easeOutSine":
        return lambda t: math.sin((t * math.pi) / 2)
    if name == "easeInOutSine":
        return lambda t: -(math.cos(math.pi * t) - 1) / 2
    # --- Circ ---
    if name == "easeInCirc":
        return lambda t: 1 - math.sqrt(1 - pow(t, 2))
    if name == "easeOutCirc":
        return lambda t: math.sqrt(1 - pow(t - 1, 2))
    if name == "easeInOutCirc":
        return lambda t: (1 - math.sqrt(1 - pow(2 * t, 2))) / 2 if t < 0.5 else (math.sqrt(1 - pow(-2 * t + 2, 2)) + 1) / 2
    # --- Elastic ---
    if name == "easeOutElastic":
        c4 = (2 * math.pi) / 3
        return lambda t: 0 if t == 0 else (1 if t == 1 else pow(2, -10 * t) * math.sin((t * 10 - 0.75) * c4) + 1)
    if name == "easeInElastic":
        c4 = (2 * math.pi) / 3
        return lambda t: 0 if t == 0 else (1 if t == 1 else -pow(2, 10 * t - 10) * math.sin((t * 10 - 10.75) * c4))
    if name == "easeInOutElastic":
        c5 = (2 * math.pi) / 4.5
        return lambda t: 0 if t == 0 else (1 if t == 1 else (-(pow(2, 20 * t - 10) * math.sin((20 * t - 11.125) * c5)) / 2 if t < 0.5 else (pow(2, -20 * t + 10) * math.sin((20 * t - 11.125) * c5)) / 2 + 1))
    # --- Bounce ---
    if name in ["easeOutBounce", "easeInBounce", "easeInOutBounce"]:
        def bounce_out(t):
            n1, d1 = 7.5625, 2.75
            if t < 1 / d1: return n1 * t * t
            elif t < 2 / d1: t -= 1.5 / d1; return n1 * t * t + 0.75
            elif t < 2.5 / d1: t -= 2.25 / d1; return n1 * t * t + 0.9375
            else: t -= 2.625 / d1; return n1 * t * t + 0.984375
        if name == "easeOutBounce": return bounce_out
        if name == "easeInBounce": return lambda t: 1 - bounce_out(1 - t)
        return lambda t: (1 - bounce_out(1 - 2 * t)) / 2 if t < 0.5 else (1 + bounce_out(2 * t - 1)) / 2
    # --- Default: linear ---
    return lambda t: t

from video_processing import _render_text_to_pil

def render_video_with_moviepy(template, data, output_override=None):
    # BACK TO STABLE 1080p CANVAS
    width, height = 1080, 1920
    duration = float(template.get("duration") or 5)
    fps = int(template.get("fps") or 60)
    
    # Resolve background early to get accurate dimensions for scaling
    bg_spec = str(template.get("background") or template.get("video") or "")
    if bg_spec.startswith("#") or bg_spec in ["white", "black"]:
        # Fallback to default 1080p for solid colors
        v_w, v_h = width, height
        color_map = {"white": (255, 255, 255), "black": (0, 0, 0)}
        color_rgb = color_map.get(bg_spec, (255, 255, 255))
        if not bg_spec in color_map:
            h_code = bg_spec.lstrip("#")
            color_rgb = tuple(int(h_code[i:i+2], 16) for i in (0, 2, 4))
        bg_clip = ColorClip(size=(v_w, v_h), color=color_rgb, duration=duration)
    else:
        base_video = _resolve_path(bg_spec)
        bg_str = str(base_video).lower()
        if bg_str.endswith(('.png', '.jpg', '.jpeg', '.webp')):
            from moviepy import ImageClip
            bg_clip = ImageClip(str(base_video)).with_duration(duration)
        else:
            bg_clip = VideoFileClip(str(base_video), audio=False)
        # ENORMOUS OPTIMIZATION: Only resize if the video is NOT already 1080x1920.
        # MoviePy's .resized() applies a heavy image transformation on EVERY single frame sequentially.
        if bg_clip.w != width or bg_clip.h != height:
            bg_clip = bg_clip.resized(width=width, height=height)
            
        v_h, v_w = bg_clip.get_frame(0).shape[:2]
        if duration > bg_clip.duration:
            bg_clip = concatenate_videoclips([bg_clip] * int(math.ceil(duration / bg_clip.duration))).subclipped(0, duration)
        else:
            bg_clip = bg_clip.subclipped(0, duration)

    out_val = output_override or template.get("output") or "static/output/video_output.mp4"
    output_path = (PROJECT_ROOT / out_val).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    def expand_animations(anims, p_dict):
        res = []
        for a in anims:
            if "preset" in a:
                p_val = p_dict.get(a["preset"], [])
                p_blocks = p_val if isinstance(p_val, list) else [p_val]
                for pb in p_blocks:
                    nb = dict(pb)
                    if "start" in a: nb["start"] = _to_float(a["start"])
                    if "duration" in a: nb["duration"] = _to_float(a["duration"])
                    res.append(nb)
            else:
                res.append(a)
        return res

    presets_dict = template.get("animation_presets", {})
    fonts_dict = template.get("assets", {}).get("fonts", {})
    
    # Use ACTUAL video width (v_w) for scaling
    tpl_w = _to_float(template.get("width"), width)
    tpl_h = _to_float(template.get("height"), height)
    s_fac = v_w / tpl_w

    layers = template.get("layers", [])
    parsed_layers = []

    # ===== GROUP 7: STAGGER SYSTEM =====
    # Process layer_groups to add automatic stagger delays before layer parsing
    layer_groups = template.get("layer_groups", [])
    for group in layer_groups:
        stagger_s = _to_float(group.get("stagger"), 0.1)
        layer_ids = group.get("layers", [])
        for i, layer_id in enumerate(layer_ids):
            target = next((l for l in layers if l.get("id") == layer_id), None)
            if not target: continue
            delay = i * stagger_s
            for block in target.get("animations", []):
                block["start"] = _to_float(block.get("start"), 0) + delay

    # Also support per-layer stagger_delay
    for layer in layers:
        sd = _to_float(layer.get("stagger_delay"), 0)
        if sd > 0:
            for block in layer.get("animations", []):
                block["start"] = _to_float(block.get("start"), 0) + sd

    for idx, layer in enumerate(layers):
        layer_type = layer.get("type", "text")

        # ===== GROUP 4: IMAGE LAYER TYPE =====
        if layer_type == "image":
            src_path = _resolve_path(layer.get("src"))
            if not src_path or not src_path.exists():
                logger.warning("Image layer %d: src not found: %s", idx, layer.get("src"))
                continue
            pil_img = Image.open(str(src_path)).convert("RGBA")
            # Resize if width/height specified in layer
            target_w = int(_to_float(layer.get("width"), pil_img.width) * s_fac)
            target_h = int(_to_float(layer.get("height"), pil_img.height) * s_fac)
            if target_w != pil_img.width or target_h != pil_img.height:
                pil_img = pil_img.resize((target_w, target_h), Image.LANCZOS)
            text = ""
            char_widths = []
        else:
            # Standard text layer
            text = resolve_text(layer, data).strip()
            if not text: continue

            layer_copy = dict(layer)
            layer_copy["font_size"] = int(_to_float(layer.get("font_size", 40)) * s_fac)

            # Check if shimmer is active — render white text for gradient masking (Group 6)
            if layer.get("shimmer"):
                layer_copy["_shimmer_active"] = True

            # Resolve Font Path
            font_alias = layer.get("font", "sans-serif")
            font_file = fonts_dict.get(font_alias, font_alias)
            font_path = _resolve_path(font_file)

            pil_img = _render_text_to_pil(text, layer_copy, font_alias, font_path)
            if not pil_img: continue
            char_widths = pil_img.info.get("char_widths", [])

        arr = np.array(pil_img)
        if arr.shape[2] == 3:
            arr = np.concatenate([arr, np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)], axis=-1)

        skia_img = skia.Image.fromarray(arr, colorType=skia.ColorType.kRGBA_8888_ColorType)
        l_w, l_h = skia_img.width(), skia_img.height()

        # Base Coordinates (Scaled)
        bx = _to_float(layer.get("x", 0)) * s_fac
        by = _to_float(layer.get("y", 100)) * s_fac

        anims = expand_animations(layer.get("animations", []), presets_dict)
        def make_filter(prop, base):
            raw_blocks = sorted([b for b in anims if b.get("property") == prop], key=lambda x: _to_float(x.get("start"), 0))

            # Pre-parse blocks to eliminate slow string/dict lookups and lambda generation in the hot loop
            parsed_blocks = []
            for b in raw_blocks:
                s = _to_float(b.get("start"), 0)
                d = max(_to_float(b.get("duration"), 1), 0.001) # prevent div by zero
                f_v = _to_float(b.get("from"), base)
                t_v = _to_float(b.get("to"), base)
                if prop in ["slide_x", "slide_y"]:
                    f_v *= s_fac
                    t_v *= s_fac
                ease_func = _get_easing(b.get("easing", "linear"))
                parsed_blocks.append((s, d, f_v, t_v, ease_func))

            # Special case for opacity: if there's a typewriter reveal, hide before it starts
            if prop == "opacity" and not parsed_blocks:
                tw_blocks = [b for b in anims if b.get("property") in ["typewriter", "typewriter_bounce"]]
                if tw_blocks:
                    ts = _to_float(tw_blocks[0].get("start"), 0)
                    return lambda t: 1.0 if t >= ts else 0.0

            if not parsed_blocks:
                return base # Return raw float instead of lambda to eliminate python function call overhead

            first_start = parsed_blocks[0][0]
            first_from = parsed_blocks[0][2]

            def f(t):
                if t < first_start:
                    return first_from
                v = base
                for (s, d, f_v, t_v, ease) in parsed_blocks:
                    if t < s: continue
                    v = f_v + (t_v - f_v) * ease(min((t - s) / d, 1.0))
                return v
            return f

        # ===== GROUP 1: MASK CONFIG =====
        mask_cfg = layer.get("mask")
        parsed_mask = None
        if mask_cfg:
            mask_type = mask_cfg.get("type", "linear_wipe")
            feather = _to_float(mask_cfg.get("feather"), 0)
            # Parse animated mask params using the same make_filter pattern
            if mask_type == "linear_wipe":
                pos_cfg = mask_cfg.get("position", {})
                # Create a temporary animation block for position
                pos_anims = [{
                    "property": "_mask_pos",
                    "from": _to_float(pos_cfg.get("from"), 0),
                    "to": _to_float(pos_cfg.get("to"), 1),
                    "start": _to_float(pos_cfg.get("start"), 0),
                    "duration": _to_float(pos_cfg.get("duration"), 1),
                    "easing": pos_cfg.get("easing", "linear")
                }]
                old_anims = anims
                anims = pos_anims
                mask_pos_filter = make_filter("_mask_pos", 0.0)
                anims = old_anims
                parsed_mask = {
                    "type": "linear_wipe",
                    "direction": mask_cfg.get("direction", "left"),
                    "position": mask_pos_filter,
                    "feather": feather
                }
            elif mask_type == "radial":
                rad_cfg = mask_cfg.get("radius", {})
                rad_anims = [{
                    "property": "_mask_rad",
                    "from": _to_float(rad_cfg.get("from"), 0),
                    "to": _to_float(rad_cfg.get("to"), 1),
                    "start": _to_float(rad_cfg.get("start"), 0),
                    "duration": _to_float(rad_cfg.get("duration"), 1),
                    "easing": rad_cfg.get("easing", "linear")
                }]
                old_anims = anims
                anims = rad_anims
                mask_rad_filter = make_filter("_mask_rad", 0.0)
                anims = old_anims
                parsed_mask = {
                    "type": "radial",
                    "center_x": _to_float(mask_cfg.get("center_x"), 0.5),
                    "center_y": _to_float(mask_cfg.get("center_y"), 0.5),
                    "radius": mask_rad_filter,
                    "feather": feather
                }

        # ===== GROUP 6: SHIMMER CONFIG =====
        shimmer_cfg = layer.get("shimmer")
        parsed_shimmer = None
        if shimmer_cfg:
            shimmer_colors = shimmer_cfg.get("colors", ["#B8860B", "#FFD700", "#B8860B"])
            # Parse hex colors to RGB tuples
            parsed_colors = []
            for c in shimmer_colors:
                c_hex = c.lstrip("#")
                parsed_colors.append(tuple(int(c_hex[i:i+2], 16) for i in (0, 2, 4)))
            
            # PRECOMPUTE WIDE GRADIENT
            grad_w = l_w
            n_colors = len(parsed_colors)
            x_coords = np.linspace(0, 1, grad_w * 2) % 1.0
            pos_f = x_coords * (n_colors - 1)
            idx_lo = np.floor(pos_f).astype(int) % n_colors
            idx_hi = (idx_lo + 1) % n_colors
            frac = (pos_f - np.floor(pos_f))[:, np.newaxis]
            c_arr = np.array(parsed_colors)
            grad_row = np.zeros((grad_w * 2, 4), dtype=np.uint8)
            grad_row[:, :3] = c_arr[idx_lo] * (1 - frac) + c_arr[idx_hi] * frac
            grad_row[:, 3] = 255
            
            parsed_shimmer = {
                "colors": parsed_colors,
                "speed": _to_float(shimmer_cfg.get("speed"), 1.5),
                "angle": _to_float(shimmer_cfg.get("angle"), 0),
                "grad_row": grad_row
            }

        # ===== GROUP 2: DROP SHADOW =====
        shadow_color_hex = layer.get("shadow_color", "#000000").lstrip("#")
        shadow_color_rgb = tuple(int(shadow_color_hex[i:i+2], 16) for i in (0, 2, 4)) if len(shadow_color_hex) == 6 else (0, 0, 0)

        parsed_layers.append({
            "img": skia_img, "bx": bx, "by": by, "w": l_w, "h": l_h,
            "op": make_filter("opacity", 1.0),
            "sc": make_filter("scale", 1.0),
            "rx": make_filter("slide_x", 0.0), "ry": make_filter("slide_y", 0.0),
            "rot": make_filter("rotation", 0.0), "sx": make_filter("skew_x", 0.0),
            "sy": make_filter("skew_y", 0.0), "text": text,
            "cw": char_widths,
            "anims": anims,
            "layer_raw": layer,
            "s_fac": s_fac,
            "img_array": arr,  # Keep numpy array for chromatic/shimmer effects
            # Existing animation properties
            "blur": make_filter("blur", 0.0),
            "flip_x": make_filter("flip_x", 0.0),
            "flip_y": make_filter("flip_y", 0.0),
            "glow": make_filter("glow", 0.0),
            "shadow_grow": make_filter("shadow_grow", 0.0),
            "bounce_y": make_filter("bounce_y", 0.0),
            "wave": make_filter("wave", 0.0),
            "scale_x": make_filter("scale_x", 1.0),
            "scale_y": make_filter("scale_y", 1.0),
            # Group 2: Drop Shadow
            "shadow_x": make_filter("shadow_x", 0.0),
            "shadow_y": make_filter("shadow_y", 4.0),
            "shadow_blur": make_filter("shadow_blur", 8.0),
            "shadow_opacity": make_filter("shadow_opacity", 0.0),
            "shadow_color": shadow_color_rgb,
            # Group 1: Mask
            "mask": parsed_mask,
            # Group 6: Shimmer
            "shimmer": parsed_shimmer,
        })

    # --- Optimizations: Pre-compute static values for performance ---
    # Get actual frame dimensions
    first_frame = bg_clip.get_frame(0)
    h_f, w_f = first_frame.shape[:2]
    
    # Pre-allocate alpha channel to avoid creating it inside the hot loop (saves huge memory allocations)
    if first_frame.shape[2] == 3:
        # Pre-allocate the entire 4-channel RGBA frame buffer ONCE.
        # This prevents allocating 8.2MB per frame (6.4 GB total across the video).
        global_frame_buffer = np.full((h_f, w_f, 4), 255, dtype=np.uint8)
    else:
        global_frame_buffer = None

    # Pre-create Skia ImageInfo
    curr_skia_info = skia.ImageInfo.Make(w_f, h_f, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
    
    # Pre-evaluate coordinates for all layers to avoid calling eval() 30 times a second
    def eval_coord(expr, base_val, current_dim, text_dim, scale):
        if not isinstance(expr, str): return _to_float(expr, base_val)
        if not any(k in expr for k in ["w", "text_w", "h", "text_h"]):
            try: return float(expr) * scale
            except: return base_val
        try:
            s = expr.replace("text_w", str(text_dim)).replace("w", str(current_dim))
            s = s.replace("text_h", str(text_dim)).replace("h", str(current_dim))
            import re
            clean = re.sub(r"[^0-9\.\+\-\*\/\(\)\ ]", "", s)
            return float(eval(clean))
        except:
            return base_val

    for L in parsed_layers:
        x_expr = L["layer_raw"].get("x", "(w-text_w)/2")
        L["fx_base"] = eval_coord(x_expr, L["bx"], w_f, L["w"], L["s_fac"])
        
        y_expr = L["layer_raw"].get("y", 100)
        L["fy_base"] = eval_coord(y_expr, L["by"], h_f, L["h"], L["s_fac"])
        
        # Pre-compute special animation blocks to prevent doing list comprehensions on every single frame!
        L["tw_list"] = [b for b in L["anims"] if b.get("property") in ["typewriter", "typewriter_bounce"]]
        L["wave_list"] = [b for b in L["anims"] if b.get("property") == "wave"]
        L["elastic_list"] = [b for b in L["anims"] if b.get("property") == "elastic"]
        L["bounce_list"] = [b for b in L["anims"] if b.get("property") == "bounce_in"]

    # ===== GROUP 3: POST-EFFECTS PRE-COMPUTATION =====
    post_effects_cfg = template.get("post_effects", [])
    post_caches = {}
    for pe in post_effects_cfg:
        if pe.get("type") == "vignette":
            intensity = _to_float(pe.get("intensity"), 0.5)
            feather_v = _to_float(pe.get("feather"), 0.4)
            cy_v, cx_v = h_f / 2.0, w_f / 2.0
            Y, X = np.ogrid[:h_f, :w_f]
            dist = np.sqrt(((X - cx_v) / cx_v) ** 2 + ((Y - cy_v) / cy_v) ** 2)
            dist = np.clip(dist, 0, 1)
            vignette_mask = (1.0 - intensity * np.power(dist, feather_v)).astype(np.float32)
            post_caches["vignette_mask"] = vignette_mask[:, :, np.newaxis]
        elif pe.get("type") == "film_grain" and not pe.get("animated", True):
            grain_i = _to_float(pe.get("intensity"), 0.03)
            post_caches["static_grain"] = np.random.normal(0, grain_i * 255, (h_f, w_f, 3)).astype(np.float32)

    def apply_post_effects(rgb, effects, t):
        result = rgb.astype(np.float32)
        for pe in effects:
            etype = pe.get("type")
            if etype == "vignette" and "vignette_mask" in post_caches:
                result *= post_caches["vignette_mask"]
            elif etype == "film_grain":
                if pe.get("animated", True):
                    grain_i = _to_float(pe.get("intensity"), 0.03)
                    noise = np.random.normal(0, grain_i * 255, result.shape).astype(np.float32)
                else:
                    noise = post_caches.get("static_grain", 0)
                result += noise
            elif etype == "color_grade":
                br = _to_float(pe.get("brightness"), 1.0)
                ct = _to_float(pe.get("contrast"), 1.0)
                sat = _to_float(pe.get("saturation"), 1.0)
                if br != 1.0: result *= br
                if ct != 1.0: result = (result - 128) * ct + 128
                if sat != 1.0:
                    gray = 0.299 * result[:,:,0] + 0.587 * result[:,:,1] + 0.114 * result[:,:,2]
                    for c in range(3):
                        result[:,:,c] = gray + (result[:,:,c] - gray) * sat
        return np.clip(result, 0, 255).astype(np.uint8)

    sampling = skia.SamplingOptions(skia.FilterMode.kLinear)

    def make_frame(t):
        bg_rgb = bg_clip.get_frame(t)
        
        if global_frame_buffer is not None:
            # VERY FAST: In-place copy into the pre-allocated buffer
            global_frame_buffer[:, :, :3] = bg_rgb
            frame_arr = global_frame_buffer
        else:
            frame_arr = bg_rgb.copy()
        
        # Use pre-created skia info
        surface = skia.Surface.MakeRasterDirect(curr_skia_info, frame_arr)
        
        with surface as canvas:
            for L in parsed_layers:
                op_prop = L["op"]
                op = op_prop(t) if callable(op_prop) else op_prop
                if op <= 0: continue
                
                sc_p, rot_p, sx_p, sy_p = L["sc"], L["rot"], L["sx"], L["sy"]
                sc = sc_p(t) if callable(sc_p) else sc_p
                rot = rot_p(t) if callable(rot_p) else rot_p
                sx = sx_p(t) if callable(sx_p) else sx_p
                sy = sy_p(t) if callable(sy_p) else sy_p
                
                # Use pre-evaluated coordinates, just add the dynamic animation translation
                rx_p, ry_p = L["rx"], L["ry"]
                fx = L["fx_base"] + (rx_p(t) if callable(rx_p) else rx_p)
                fy = L["fy_base"] + (ry_p(t) if callable(ry_p) else ry_p)
                
                cx, cy = fx + L["w"] / 2, fy + L["h"] / 2
                
                paint = skia.Paint(AntiAlias=True, Alphaf=op)
                
                # High-End Smooth Typewriter / Character Bounce Logic
                tw_list = L["tw_list"]
                if tw_list and L["cw"]:
                    b = tw_list[0]
                    prop = b.get("property")
                    s, dur = _to_float(b.get("start"), 0), _to_float(b.get("duration"), 1)
                    ease = _get_easing(b.get("easing", "easeOutBack"))
                    
                    if t >= s:
                        chars = list(L["text"])
                        stagger = (dur * 0.7) / max(len(chars), 1)
                        char_dur = max(dur * 0.3, 0.4)
                        
                        for i, char in enumerate(chars):
                            ct = s + i * stagger
                            if t < ct: continue
                            
                            c_progress = min((t - ct) / char_dur, 1.0)
                            c_sc = ease(c_progress) if prop == "typewriter_bounce" else 1.0
                            c_op = min(c_progress * 2, 1.0) # Smooth opacity ramp per char
                            
                            p_w = L["cw"][i] 
                            p_start = L["cw"][i-1] if i > 0 else 0
                            char_w = p_w - p_start
                            
                            if char_w <= 0: continue
                            
                            canvas.save()
                            ccx, ccy = fx + p_start + char_w/2, fy + L["h"]/2
                            canvas.translate(ccx, ccy)
                            canvas.scale(c_sc * sc, c_sc * sc)
                            canvas.translate(-ccx, -ccy)
                            
                            canvas.clipRect(skia.Rect.MakeXYWH(fx + p_start, fy, char_w, L["h"]))
                            
                            c_paint = skia.Paint(AntiAlias=True, Alphaf=op * c_op)
                            canvas.drawImage(L["img"], fx, fy, sampling, c_paint)
                            canvas.restore()
                        continue
                
                # ===== NEW ANIMATION: Wave (per-character vertical wave) =====
                wave_list = L["wave_list"]
                if wave_list and L["cw"]:
                    b = wave_list[0]
                    ws, wdur = _to_float(b.get("start"), 0), _to_float(b.get("duration"), 2)
                    amp = _to_float(b.get("amplitude"), 15) * L["s_fac"]
                    freq = _to_float(b.get("frequency"), 0.3)
                    if t >= ws:
                        chars = list(L["text"])
                        for i, char in enumerate(chars):
                            p_w = L["cw"][i]
                            p_start = L["cw"][i-1] if i > 0 else 0
                            char_w = p_w - p_start
                            if char_w <= 0: continue
                            wave_offset = amp * math.sin(2 * math.pi * freq * (t - ws) + i * 0.5)
                            canvas.save()
                            canvas.translate(0, wave_offset)
                            canvas.clipRect(skia.Rect.MakeXYWH(fx + p_start, fy - abs(amp), char_w, L["h"] + 2 * abs(amp)))
                            canvas.drawImage(L["img"], fx, fy, sampling, paint)
                            canvas.restore()
                        continue

                # ===== NEW ANIMATION: Elastic entrance (scale overshoot + settle) =====
                elastic_list = L["elastic_list"]
                if elastic_list:
                    b = elastic_list[0]
                    es, edur = _to_float(b.get("start"), 0), _to_float(b.get("duration"), 1)
                    if t >= es:
                        ease_el = _get_easing("easeOutElastic")
                        progress = min((t - es) / edur, 1.0)
                        el_sc = ease_el(progress)
                        canvas.save()
                        canvas.translate(cx, cy)
                        canvas.scale(el_sc * sc, el_sc * sc)
                        canvas.rotate(rot)
                        canvas.translate(-cx, -cy)
                        canvas.drawImage(L["img"], fx, fy, sampling, paint)
                        canvas.restore()
                        continue
                    else:
                        continue  # Hidden before elastic starts

                # ===== NEW ANIMATION: Bounce entrance =====
                bounce_list = L["bounce_list"]
                if bounce_list:
                    b = bounce_list[0]
                    bs, bdur = _to_float(b.get("start"), 0), _to_float(b.get("duration"), 1)
                    if t >= bs:
                        ease_b = _get_easing("easeOutBounce")
                        progress = min((t - bs) / bdur, 1.0)
                        b_sc = ease_b(progress)
                        canvas.save()
                        canvas.translate(cx, cy)
                        canvas.scale(b_sc * sc, b_sc * sc)
                        canvas.translate(-cx, -cy)
                        canvas.drawImage(L["img"], fx, fy, sampling, paint)
                        canvas.restore()
                        continue
                    else:
                        continue

                # Default render (enhanced with new properties)
                canvas.save()

                # ===== GROUP 1: MASK — Apply clip BEFORE drawing =====
                mask = L["mask"]
                if mask:
                    mtype = mask["type"]
                    if mtype == "linear_wipe":
                        pos_p = mask["position"]
                        pos = pos_p(t) if callable(pos_p) else pos_p
                        direction = mask["direction"]
                        if direction == "left":
                            clip_w = pos * L["w"]
                            canvas.clipRect(skia.Rect.MakeXYWH(fx, fy, clip_w, L["h"]), doAntiAlias=True)
                        elif direction == "right":
                            clip_x = fx + L["w"] * (1 - pos)
                            canvas.clipRect(skia.Rect.MakeXYWH(clip_x, fy, L["w"] * pos, L["h"]), doAntiAlias=True)
                        elif direction == "up":
                            clip_h = pos * L["h"]
                            canvas.clipRect(skia.Rect.MakeXYWH(fx, fy, L["w"], clip_h), doAntiAlias=True)
                        elif direction == "down":
                            clip_y = fy + L["h"] * (1 - pos)
                            canvas.clipRect(skia.Rect.MakeXYWH(fx, clip_y, L["w"], L["h"] * pos), doAntiAlias=True)
                    elif mtype == "radial":
                        rad_p = mask["radius"]
                        rad = rad_p(t) if callable(rad_p) else rad_p
                        max_r = math.sqrt(L["w"]**2 + L["h"]**2) / 2
                        r_px = rad * max_r
                        mcx = fx + mask["center_x"] * L["w"]
                        mcy = fy + mask["center_y"] * L["h"]
                        path = skia.Path()
                        path.addCircle(mcx, mcy, r_px)
                        canvas.clipPath(path, doAntiAlias=True)

                canvas.translate(cx, cy)

                # Apply per-axis scaling if defined, otherwise use uniform scale
                sx_val_p, sy_val_p = L["scale_x"], L["scale_y"]
                sx_val = sx_val_p(t) if callable(sx_val_p) else sx_val_p
                sy_val = sy_val_p(t) if callable(sy_val_p) else sy_val_p
                if sx_val != 1.0 or sy_val != 1.0:
                    canvas.scale(sx_val * sc, sy_val * sc)
                else:
                    canvas.scale(sc, sc)

                # Apply rotation
                canvas.rotate(rot)

                # Apply flip transforms
                flip_x_p, flip_y_p = L["flip_x"], L["flip_y"]
                flip_x_val = flip_x_p(t) if callable(flip_x_p) else flip_x_p
                flip_y_val = flip_y_p(t) if callable(flip_y_p) else flip_y_p
                if flip_x_val > 0:
                    angle = flip_x_val * 180
                    perspective = math.cos(math.radians(angle))
                    canvas.scale(perspective, 1.0)
                if flip_y_val > 0:
                    angle = flip_y_val * 180
                    perspective = math.cos(math.radians(angle))
                    canvas.scale(1.0, perspective)

                canvas.skew(sx, sy)
                canvas.translate(-cx, -cy)

                # ===== GROUP 2: DROP SHADOW — draw BEFORE main image =====
                sh_op_p = L["shadow_opacity"]
                sh_op = sh_op_p(t) if callable(sh_op_p) else sh_op_p
                if sh_op > 0:
                    sh_x_p = L["shadow_x"]
                    sh_x = sh_x_p(t) if callable(sh_x_p) else sh_x_p
                    sh_y_p = L["shadow_y"]
                    sh_y = sh_y_p(t) if callable(sh_y_p) else sh_y_p
                    sh_bl_p = L["shadow_blur"]
                    sh_bl = sh_bl_p(t) if callable(sh_bl_p) else sh_bl_p
                    sc_r, sc_g, sc_b = L["shadow_color"]
                    shadow_filter = skia.ImageFilters.Blur(max(sh_bl, 0.1), max(sh_bl, 0.1))
                    color_filter = skia.ColorFilters.Blend(
                        skia.Color4f(sc_r / 255.0, sc_g / 255.0, sc_b / 255.0, sh_op),
                        skia.BlendMode.kSrcIn)
                    shadow_paint = skia.Paint(AntiAlias=True, ImageFilter=shadow_filter, ColorFilter=color_filter)
                    canvas.drawImage(L["img"], fx + sh_x, fy + sh_y, sampling, shadow_paint)

                # Evaluate blur and glow
                blur_p = L["blur"]
                blur_val = blur_p(t) if callable(blur_p) else blur_p
                glow_p = L["glow"]
                glow_val = glow_p(t) if callable(glow_p) else glow_p

                # ===== GROUP 6: SHIMMER — gradient fill through text alpha =====
                shimmer = L["shimmer"]
                if shimmer:
                    speed = shimmer["speed"]
                    grad_w = L["w"]
                    
                    # Use precomputed double-width gradient to slide a window over
                    offset_px = int(((t * speed) % 1.0) * grad_w)
                    grad_row_slice = shimmer["grad_row"][offset_px : offset_px + grad_w]
                    
                    # Tile vertically
                    grad_arr = np.tile(grad_row_slice, (L["h"], 1, 1))
                    
                    # Mask by text alpha channel
                    text_alpha = L["img_array"][:, :, 3:4].astype(np.float32) / 255.0
                    grad_arr = (grad_arr.astype(np.float32) * text_alpha).astype(np.uint8)
                    shimmer_img = skia.Image.fromarray(grad_arr, colorType=skia.ColorType.kRGBA_8888_ColorType)
                    canvas.drawImage(shimmer_img, fx, fy, sampling, paint)
                elif blur_val > 0.1:
                    blur_filter = skia.ImageFilters.Blur(blur_val, blur_val)
                    blur_paint = skia.Paint(AntiAlias=True, Alphaf=op, ImageFilter=blur_filter)
                    canvas.drawImage(L["img"], fx, fy, sampling, blur_paint)
                elif glow_val > 0:
                    glow_sigma = glow_val * 8
                    glow_filter = skia.ImageFilters.Blur(glow_sigma, glow_sigma)
                    glow_paint = skia.Paint(AntiAlias=True, Alphaf=op * 0.4, ImageFilter=glow_filter)
                    canvas.drawImage(L["img"], fx, fy, sampling, glow_paint)
                    canvas.drawImage(L["img"], fx, fy, sampling, paint)
                else:
                    canvas.drawImage(L["img"], fx, fy, sampling, paint)

                canvas.restore()

        # ===== GROUP 3: POST-EFFECTS — apply AFTER all layers =====
        rgb_out = frame_arr[:, :, :3]
        if post_effects_cfg:
            rgb_out = apply_post_effects(rgb_out, post_effects_cfg, t)
        return rgb_out

    clip = VideoClip(make_frame, duration=duration)
    # Optimization: Use 'ultrafast' preset and threads=1.
    # We MUST use threads=1 when reading from VideoFileClip, otherwise the internal FFmpeg reader
    # seeks back and forth constantly, destroying performance and dropping speed to ~9it/s.
    # We use logger=None to completely disable tqdm I/O overhead which blocks FastAPI servers.
    import time
    t0 = time.time()
    clip.write_videofile(str(output_path), fps=fps, codec="libx264", preset="ultrafast", threads=1, bitrate="5000k", logger=None)
    generation_time = time.time() - t0
    logger.info(f"===== VIDEO GENERATION COMPLETE: {generation_time:.2f} seconds =====")
    print(f"===== VIDEO GENERATION COMPLETE: {generation_time:.2f} seconds =====")
    
    return output_path
