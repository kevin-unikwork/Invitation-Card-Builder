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
    bg_spec = template.get("background") or template.get("video")
    if str(bg_spec).startswith("#") or bg_spec in ["white", "black"]:
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
        bg_clip = VideoFileClip(str(base_video)).resized(width=width, height=height)
        # Use actual frame size for scaling logic
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

    for idx, layer in enumerate(layers):
        text = resolve_text(layer, data).strip()
        if not text: continue
        
        layer_copy = dict(layer)
        layer_copy["font_size"] = int(_to_float(layer.get("font_size", 40)) * s_fac)
        
        # Resolve Font Path
        font_alias = layer.get("font", "sans-serif")
        font_file = fonts_dict.get(font_alias, font_alias)
        font_path = _resolve_path(font_file)
        
        pil_img = _render_text_to_pil(text, layer_copy, font_alias, font_path)
        if not pil_img: continue
        
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
            blocks = sorted([b for b in anims if b.get("property") == prop], key=lambda x: _to_float(x.get("start"), 0))
            
            # Special case for opacity: if there's a typewriter reveal, hide before it starts
            if prop == "opacity" and not blocks:
                tw_blocks = [b for b in anims if b.get("property") in ["typewriter", "typewriter_bounce"]]
                if tw_blocks:
                    def f_hidden(t):
                        return 1.0 if t >= _to_float(tw_blocks[0].get("start"), 0) else 0.0
                    return f_hidden

            def f(t):
                if blocks and t < _to_float(blocks[0].get("start"), 0):
                    v_from = _to_float(blocks[0].get("from"), base)
                    if prop in ["slide_x", "slide_y"]: v_from *= s_fac
                    return v_from
                v = base
                for b in blocks:
                    s, d = _to_float(b.get("start"), 0), _to_float(b.get("duration"), 1)
                    if t < s: continue
                    f_v, t_v = _to_float(b.get("from"), base), _to_float(b.get("to"), base)
                    if prop in ["slide_x", "slide_y"]:
                        f_v *= s_fac
                        t_v *= s_fac
                    ease = _get_easing(b.get("easing", "linear"))
                    v = f_v + (t_v - f_v) * ease(min((t - s) / d, 1.0))
                return v
            return f

        parsed_layers.append({
            "img": skia_img, "bx": bx, "by": by, "w": l_w, "h": l_h,
            "op": make_filter("opacity", 1.0),
            "sc": make_filter("scale", 1.0),
            "rx": make_filter("slide_x", 0.0), "ry": make_filter("slide_y", 0.0),
            "rot": make_filter("rotation", 0.0), "sx": make_filter("skew_x", 0.0),
            "sy": make_filter("skew_y", 0.0), "text": text,
            "cw": pil_img.info.get("char_widths", []),
            "anims": anims,
            "layer_raw": layer,
            "s_fac": s_fac,
            # New animation properties
            "blur": make_filter("blur", 0.0),
            "flip_x": make_filter("flip_x", 0.0),
            "flip_y": make_filter("flip_y", 0.0),
            "glow": make_filter("glow", 0.0),
            "shadow_grow": make_filter("shadow_grow", 0.0),
            "bounce_y": make_filter("bounce_y", 0.0),
            "wave": make_filter("wave", 0.0),
            "scale_x": make_filter("scale_x", 1.0),
            "scale_y": make_filter("scale_y", 1.0),
        })

    skia_info = skia.ImageInfo.Make(width, height, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
    sampling = skia.SamplingOptions(skia.FilterMode.kLinear)
    
    def make_frame(t):
        bg_rgb = bg_clip.get_frame(t)
        h_f, w_f = bg_rgb.shape[:2]
        
        if bg_rgb.shape[2] == 3:
            frame_arr = np.concatenate([bg_rgb, np.full((h_f, w_f, 1), 255, dtype=np.uint8)], axis=-1)
        else:
            frame_arr = bg_rgb.copy()
        
        # Dynamic skia info based on actual background frame size
        curr_skia_info = skia.ImageInfo.Make(w_f, h_f, skia.ColorType.kRGBA_8888_ColorType, skia.AlphaType.kPremul_AlphaType)
        surface = skia.Surface.MakeRasterDirect(curr_skia_info, frame_arr)
        
        with surface as canvas:
            for L in parsed_layers:
                op = L["op"](t)
                if op <= 0: continue
                
                sc, rot, sx, sy = L["sc"](t), L["rot"](t), L["sx"](t), L["sy"](t)
                # COORDINATES: Advanced Expression Evaluator
                def eval_coord(expr, base_val, current_dim, text_dim, scale):
                    if not isinstance(expr, str): return _to_float(expr, base_val)
                    if not any(k in expr for k in ["w", "text_w", "h", "text_h"]):
                        try: return float(expr) * scale
                        except: return base_val
                    
                    try:
                        # IMPORTANT: Replace longer strings FIRST to avoid partial replacement (e.g., text_w -> text_1080)
                        s = expr.replace("text_w", str(text_dim)).replace("w", str(current_dim))
                        s = s.replace("text_h", str(text_dim)).replace("h", str(current_dim))
                        
                        import re
                        clean = re.sub(r"[^0-9\.\+\-\*\/\(\)\ ]", "", s)
                        return float(eval(clean))
                    except:
                        return base_val

                x_expr = L["layer_raw"].get("x", "(w-text_w)/2")
                fx = eval_coord(x_expr, L["bx"], w_f, L["w"], L["s_fac"]) + L["rx"](t)
                
                y_expr = L["layer_raw"].get("y", 100)
                fy = eval_coord(y_expr, L["by"], h_f, L["h"], L["s_fac"]) + L["ry"](t)
                
                cx, cy = fx + L["w"] / 2, fy + L["h"] / 2
                
                paint = skia.Paint(AntiAlias=True, Alphaf=op)
                
                # High-End Smooth Typewriter / Character Bounce Logic
                tw_list = [b for b in L["anims"] if b.get("property") in ["typewriter", "typewriter_bounce"]]
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
                            # Only apply extra bounce if it's explicitly 'typewriter_bounce'
                            # otherwise just use standard linear appearance
                            c_sc = ease(c_progress) if prop == "typewriter_bounce" else 1.0
                            c_op = min(c_progress * 2, 1.0) # Smooth opacity ramp per char
                            
                            # Prefix widths from L["cw"]
                            p_w = L["cw"][i] 
                            p_start = L["cw"][i-1] if i > 0 else 0
                            char_w = p_w - p_start
                            
                            if char_w <= 0: continue
                            
                            canvas.save()
                            # Center of this specific character for bounce
                            ccx, ccy = fx + p_start + char_w/2, fy + L["h"]/2
                            canvas.translate(ccx, ccy)
                            canvas.scale(c_sc * sc, c_sc * sc)
                            canvas.translate(-ccx, -ccy)
                            
                            # CLIP to only THIS character
                            canvas.clipRect(skia.Rect.MakeXYWH(fx + p_start, fy, char_w, L["h"]))
                            
                            c_paint = skia.Paint(AntiAlias=True, Alphaf=op * c_op)
                            canvas.drawImage(L["img"], fx, fy, sampling, c_paint)
                            canvas.restore()
                        continue
                
                # ===== NEW ANIMATION: Wave (per-character vertical wave) =====
                wave_list = [b for b in L["anims"] if b.get("property") == "wave"]
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
                elastic_list = [b for b in L["anims"] if b.get("property") == "elastic"]
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
                bounce_list = [b for b in L["anims"] if b.get("property") == "bounce_in"]
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
                canvas.translate(cx, cy)
                
                # Apply per-axis scaling if defined, otherwise use uniform scale
                sx_val, sy_val = L["scale_x"](t), L["scale_y"](t)
                if sx_val != 1.0 or sy_val != 1.0:
                    canvas.scale(sx_val * sc, sy_val * sc)
                else:
                    canvas.scale(sc, sc)
                
                # Apply rotation
                canvas.rotate(rot)
                
                # Apply flip transforms
                flip_x_val = L["flip_x"](t)
                flip_y_val = L["flip_y"](t)
                if flip_x_val > 0:
                    angle = flip_x_val * 180  # 0->0°, 1->180°
                    perspective = math.cos(math.radians(angle))
                    canvas.scale(perspective, 1.0)
                if flip_y_val > 0:
                    angle = flip_y_val * 180
                    perspective = math.cos(math.radians(angle))
                    canvas.scale(1.0, perspective)
                
                canvas.skew(sx, sy)
                canvas.translate(-cx, -cy)
                
                # Apply blur effect
                blur_val = L["blur"](t)
                if blur_val > 0.1:
                    blur_filter = skia.ImageFilters.Blur(blur_val, blur_val)
                    blur_paint = skia.Paint(AntiAlias=True, Alphaf=op, ImageFilter=blur_filter)
                    canvas.drawImage(L["img"], fx, fy, sampling, blur_paint)
                # Apply glow effect
                elif L["glow"](t) > 0:
                    glow_val = L["glow"](t)
                    glow_sigma = glow_val * 8
                    glow_filter = skia.ImageFilters.Blur(glow_sigma, glow_sigma)
                    glow_paint = skia.Paint(AntiAlias=True, Alphaf=op * 0.4, ImageFilter=glow_filter)
                    canvas.drawImage(L["img"], fx, fy, sampling, glow_paint)
                    canvas.drawImage(L["img"], fx, fy, sampling, paint)
                else:
                    canvas.drawImage(L["img"], fx, fy, sampling, paint)
                
                canvas.restore()
        
        return frame_arr[:, :, :3]

    clip = VideoClip(make_frame, duration=duration)
    clip.write_videofile(str(output_path), fps=fps, codec="libx264", bitrate="5000k")
    return output_path
