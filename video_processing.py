"""
video_processing.py — pango/cairo multilingual text + generic animation engine

Supported animation properties (per-layer `animations` array):
  opacity        → FFmpeg fade filter (fade-in 0→1, fade-out 1→0 only)
  scale          → FFmpeg scale filter (zoom in, zoom out, pulse, luxury)
  x              → FFmpeg overlay x position (slide left, slide right, center-aware)
  y              → FFmpeg overlay y position (slide up, slide down, drift)
  rotation       → FFmpeg rotate filter (tilt, spin, wobble)
  blur           → boxblur filter on overlay (cinematic reveal)
  letter_spacing → ⚠ NOT supported; silently ignored

Opacity animations:
  ⚠ IMPORTANT: Opacity animations only support standard fade-in (0→1) and
  fade-out (1→0) animations using FFmpeg's fade filter.
  
  For arbitrary opacity ranges (e.g., 0.2→0.8), the animation is applied
  as static opacity starting from the "from" value, and a warning is logged.
  
  To use opacity animations:
    {"property": "opacity", "from": 0, "to": 1, "start": 0.5, "duration": 0.5}
    → Fades in from 0.5s to 1.0s
    
    {"property": "opacity", "from": 1, "to": 0, "start": 4.5, "duration": 0.5}
    → Fades out from 4.5s to 5.0s

Opacity shorthand (per-layer `opacity` dict):
  Layers can declare a top-level "opacity" object with the following keys:
    initial   (float, 0–1) — starting opacity before any animation (default: 1)
    animate   (bool)       — whether to animate opacity (default: false)
    from      (float)      — opacity at animation start (0 or 1 for fade animations)
    to        (float)      — opacity at animation end (0 or 1 for fade animations)
    start     (float)      — animation start time in seconds
    duration  (float)      — animation duration in seconds
    easing    (str)        — ⚠ NOT used for opacity (fade filter is always linear)

  Rules:
    - "initial" overrides the default opacity of 1.
    - If animate=false or omitted, only static "initial" opacity is used.
    - Opacity fade animations use FFmpeg's fade filter (linear only).
    - All opacity values are clamped to [0, 1].

Text rendering:
  Uses pango/cairo for multilingual text with proper text shaping (BiDi, Arabic, Devanagari, etc).
  Falls back to Pillow if pango is unavailable or doesn't know the font.

Animation presets:
  Supports both 1007.json schema (explicit animations) and 1008.json schema (animation_presets + presets).
  Presets are expanded to full animation blocks before animation engine processes them.

Global animations:
  Supports both dict format (1007) and array format (1008 with preset refs).
"""

import argparse
import io
import json
import logging
import re
import subprocess
import tempfile
import warnings
from pathlib import Path

from utils.date_utils import expand_event_date
from utils.path_utils import load_json
from utils.text_utils import resolve_text, should_skip_layer

try:
    from PIL import Image as _PILImage, ImageDraw as _PILDraw, ImageFilter as _PILFilter, ImageFont as _PILFont  # type: ignore
    _PIL_AVAILABLE = True
except ImportError:
    _PIL_AVAILABLE = False

try:
    import gi   #type: ignore
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo  # type: ignore
    import cairo  # type: ignore
    _PANGO_AVAILABLE = True
except (ImportError, ValueError):
    _PANGO_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "static" / "output"

logger = logging.getLogger(__name__)

FONT_FAMILY_CACHE = {}
PANGO_FONT_FAMILY_CACHE = None


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _resolve_path(path_value: str | None) -> Path | None:
    if not path_value:
        return None
    candidate = Path(path_value)
    if candidate.is_absolute():
        return candidate
    candidates = [
        (PROJECT_ROOT / candidate).resolve(),
        (PROJECT_ROOT / "static" / candidate).resolve(),
        (PROJECT_ROOT / "assets" / candidate.name).resolve(),
        (PROJECT_ROOT / "static" / "fonts" / candidate.name).resolve(),
    ]
    for resolved in candidates:
        if resolved.exists():
            return resolved
    return candidates[0]


# ---------------------------------------------------------------------------
# Filter value helper
# ---------------------------------------------------------------------------

def _to_float(value, default: float) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp_opacity_blocks(blocks: list[dict]) -> None:
    """
    Clamp all opacity from/to values to [0.0, 1.0] at Python level,
    before any FFmpeg expression is built. This avoids needing max()/min()
    in the FFmpeg expression, which colorchannelmixer does NOT support.
    """
    for block in blocks:
        if block.get("property") == "opacity":
            if "from" in block:
                block["from"] = max(0.0, min(1.0, float(block["from"])))
            if "to" in block:
                block["to"] = max(0.0, min(1.0, float(block["to"])))


# ---------------------------------------------------------------------------
# Pango/Cairo font helpers
# ---------------------------------------------------------------------------

def _get_pango_font_families() -> set:
    """Return and cache the set of font families available to Pango."""
    global PANGO_FONT_FAMILY_CACHE
    if PANGO_FONT_FAMILY_CACHE is not None:
        return PANGO_FONT_FAMILY_CACHE
    if not _PANGO_AVAILABLE:
        return set()
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    layout = PangoCairo.create_layout(ctx)
    families = layout.get_context().get_font_map().list_families()
    PANGO_FONT_FAMILY_CACHE = {family.get_name() for family in families}
    return PANGO_FONT_FAMILY_CACHE


def _font_family_from_file(path: Path) -> str:
    """Read and cache the font family name from a font file using Pillow."""
    if not _PIL_AVAILABLE:
        return "Monospace"
    resolved = path.resolve()
    cache_key = str(resolved).lower()
    if cache_key in FONT_FAMILY_CACHE:
        return FONT_FAMILY_CACHE[cache_key]
    try:
        family = _PILFont.truetype(str(resolved), size=16).getname()[0]
        FONT_FAMILY_CACHE[cache_key] = family
        return family
    except:
        return "Monospace"


def _resolve_video_font_spec(layer: dict, template: dict) -> tuple[str, Path | None]:
    """Resolve a layer's font config into a family name and optional file path."""
    font_ref = layer.get("font")
    if not font_ref:
        return "Sans", None

    assets = template.get("assets") or {}
    fonts = assets.get("fonts") or {}

    if font_ref in fonts:
        font_config = fonts[font_ref]
        if isinstance(font_config, str):
            resolved_path = _resolve_path(font_config)
            if resolved_path and resolved_path.exists():
                family = _font_family_from_file(resolved_path)
                return family, resolved_path
            return font_ref, None
        elif isinstance(font_config, dict):
            font_file = font_config.get("file")
            font_family = font_config.get("family")
            if font_file:
                resolved_path = _resolve_path(font_file)
                if resolved_path and resolved_path.exists():
                    family = _font_family_from_file(resolved_path)
                    return family, resolved_path
            return font_family or "Sans", None

    resolved_path = _resolve_path(font_ref)
    if resolved_path and resolved_path.exists() and resolved_path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        family = _font_family_from_file(resolved_path)
        return family, resolved_path

    return font_ref, None


# ---------------------------------------------------------------------------
# ─────────────────────────  ANIMATION ENGINE  ──────────────────────────
# ---------------------------------------------------------------------------

def _progress_expression(start: float, duration: float, loop: bool = False) -> str:
    """
    Build a 0→1 progress ramp in FFmpeg timeline math.

    If loop=True the ramp repeats every `duration` seconds after `start`.
    """
    safe_dur = max(duration, 0.001)
    if loop:
        return (
            f"if(lt(t,{start:.3f}),0,"
            f"mod(t-{start:.3f},{safe_dur:.3f})/{safe_dur:.3f})"
        )
    end = start + safe_dur
    return (
        f"if(lt(t,{start:.3f}),0,"
        f"if(lt(t,{end:.3f}),(t-{start:.3f})/{safe_dur:.3f},1))"
    )


def _apply_easing(expr: str, easing: str) -> str:
    name = str(easing or "linear").strip().lower().replace("-", "_")
    if name in {"ease_out", "easeout", "out"}:
        return f"(1-pow(1-({expr}),2))"
    if name in {"ease_in", "easein", "in"}:
        return f"pow(({expr}),2)"
    if name in {"ease_in_out", "easeinout", "in_out"}:
        return f"if(lt(({expr}),0.5),2*pow(({expr}),2),1-pow(-2*({expr})+2,2)/2)"
    return expr  # linear


def _interpolate(from_val: float, to_val: float, eased_expr: str) -> str:
    """
    Linear interpolation expression: from + (to - from) * eased_progress
    """
    diff = to_val - from_val
    if diff == 0:
        return f"{from_val:.6f}"
    return f"({from_val:.6f}+({diff:.6f})*({eased_expr}))"


def _combine_animation_blocks(blocks: list[dict], prop: str, default_value: str) -> str:
    """
    Combine all animation blocks for a given property into one FFmpeg expression.
    Blocks are applied in order; later blocks override earlier ones via nested if().
    """
    prop_blocks = [b for b in blocks if b.get("property") == prop]
    if not prop_blocks:
        return default_value

    expr = default_value
    for block in prop_blocks:
        from_val = _to_float(block.get("from"), _to_float(default_value, 0.0))
        to_val   = _to_float(block.get("to"),   from_val)
        start    = _to_float(block.get("start"), 0.0)
        duration = _to_float(block.get("duration"), 0.5)
        loop     = bool(block.get("loop", False))
        easing   = str(block.get("easing") or "linear")

        end = start + max(duration, 0.001)
        progress = _progress_expression(start, duration, loop=loop)
        eased    = _apply_easing(progress, easing)
        interp   = _interpolate(from_val, to_val, eased)

        if loop:
            expr = f"if(lt(t,{start:.3f}),{expr},{interp})"
        else:
            expr = (
                f"if(lt(t,{start:.3f}),{expr},"
                f"if(lt(t,{end:.3f}),{interp},"
                f"{to_val:.6f}))"
            )

    return expr


# ---------------------------------------------------------------------------
# Opacity shorthand → animation blocks converter
# ---------------------------------------------------------------------------

def _expand_opacity_shorthand(layer: dict) -> None:
    """
    Expand a top-level "opacity" dict into the layer's animations list.

    Supports:
        { "opacity": { "initial": 0, "animate": true,
                       "from": 0, "to": 1, "start": 0.0,
                       "duration": 0.5, "easing": "easeOut" } }

    Rules:
      - "initial" sets the pre-animation opacity (default 1).
      - If animate=false or missing, only static initial opacity is used.
      - Opacity values are always clamped to [0, 1].
      - The generated animation block is prepended so explicit animations still win.
    """
    opacity_cfg = layer.get("opacity")
    if not isinstance(opacity_cfg, dict):
        return  # No shorthand to expand

    initial  = max(0.0, min(1.0, _to_float(opacity_cfg.get("initial"), 1.0)))
    animate  = bool(opacity_cfg.get("animate", False))

    animations = layer.setdefault("animations", [])

    if not animate:
        # Static opacity — inject a constant block spanning the entire video
        # (start=0, long duration, from=initial, to=initial)
        block = {
            "property": "opacity",
            "from": initial,
            "to": initial,
            "start": 0.0,
            "duration": 3600.0,  # effectively infinite
            "easing": "linear",
        }
        animations.insert(0, block)
        return

    # Animated opacity — clamp all values at Python level
    from_val = max(0.0, min(1.0, _to_float(opacity_cfg.get("from"), initial)))
    to_val   = max(0.0, min(1.0, _to_float(opacity_cfg.get("to"),   from_val)))
    start    = _to_float(opacity_cfg.get("start"),    0.0)
    duration = _to_float(opacity_cfg.get("duration"), 0.5)
    easing   = str(opacity_cfg.get("easing") or "linear")

    # If initial differs from from_val, inject a pre-animation static block
    if abs(initial - from_val) > 1e-6:
        pre_block = {
            "property": "opacity",
            "from": initial,
            "to": initial,
            "start": 0.0,
            "duration": max(start, 0.001),
            "easing": "linear",
        }
        animations.insert(0, pre_block)

    anim_block = {
        "property": "opacity",
        "from": from_val,
        "to": to_val,
        "start": start,
        "duration": max(duration, 0.001),
        "easing": easing,
    }
    # Insert after any pre-block (at index 1 if pre_block exists, else 0)
    insert_pos = 1 if abs(initial - from_val) > 1e-6 else 0
    animations.insert(insert_pos, anim_block)


# ---------------------------------------------------------------------------
# Global fade-out multiplier
# ---------------------------------------------------------------------------

def _global_fade_out_multiplier(template: dict) -> str:
    """Return global fade-out multiplier expression."""
    global_anims = template.get("global_animations")
    if isinstance(global_anims, list):
        return "1"  # Array format handled in _expand_animation_presets
    if not isinstance(global_anims, dict):
        return "1"
    fade_out = global_anims.get("fade_out") or {}
    start    = _to_float(fade_out.get("start"),    -1.0)
    duration = _to_float(fade_out.get("duration"),  0.0)
    end      = start + duration
    if start < 0 or duration <= 0:
        return "1"
    safe_dur = max(duration, 0.001)
    return (
        f"if(lt(t,{start:.3f}),1,"
        f"if(lt(t,{end:.3f}),({end:.3f}-t)/{safe_dur:.3f},0))"
    )


# ---------------------------------------------------------------------------
# Build layer animation expressions
# ---------------------------------------------------------------------------

def _build_layer_anim_exprs(layer: dict, template: dict) -> dict:
    """Build animation expressions for a pango-rendered layer."""
    blocks = layer.get("animations") or []

    # ── Opacity ─────────────────────────────────────────────────────────────
    # Clamp all opacity from/to values at Python level BEFORE building expressions.
    # colorchannelmixer's eval does NOT support max()/min(), so we never emit those.
    _clamp_opacity_blocks(blocks)

    # Determine layer's default/initial opacity (1.0 unless shorthand says otherwise)
    opacity_cfg = layer.get("opacity")
    if isinstance(opacity_cfg, dict):
        default_alpha = f"{max(0.0, min(1.0, _to_float(opacity_cfg.get('initial'), 1.0))):.6f}"
    elif isinstance(opacity_cfg, (int, float)):
        default_alpha = f"{max(0.0, min(1.0, float(opacity_cfg))):.6f}"
    else:
        default_alpha = "1.0"

    alpha = _combine_animation_blocks(blocks, "opacity", default_alpha)

    # Only apply global fade-out multiplier if this layer has NO explicit opacity animations.
    # If the layer already defines its own opacity timeline (fade in + fade out blocks),
    # the global multiplier would double-apply the fade and produce invalid expressions.
    has_explicit_opacity = any(b.get("property") == "opacity" for b in blocks)
    global_fo = _global_fade_out_multiplier(template)
    if global_fo != "1" and not has_explicit_opacity:
        alpha = f"({alpha})*({global_fo})"

    # ── Scale ────────────────────────────────────────────────────────────────
    scale_expr = _combine_animation_blocks(blocks, "scale", "1.0")

    # ── Position ─────────────────────────────────────────────────────────────
    base_x = str(layer.get("x", "0"))
    base_y = str(layer.get("y", "0"))

    x_blocks = [b for b in blocks if b.get("property") == "x"]
    y_blocks = [b for b in blocks if b.get("property") == "y"]

    x_expr = _combine_animation_blocks(blocks, "x", base_x) if x_blocks else base_x
    y_expr = _combine_animation_blocks(blocks, "y", base_y) if y_blocks else base_y

    # ── Rotation ─────────────────────────────────────────────────────────────
    rot_blocks = [b for b in blocks if b.get("property") == "rotation"]
    if rot_blocks:
        rotation_expr = _combine_animation_blocks(blocks, "rotation", "0.0")
        has_rotation = True
    else:
        rotation_expr = "0"
        has_rotation = False

    # ── Unsupported: letter_spacing ──────────────────────────────────────────
    ls_blocks = [b for b in blocks if b.get("property") == "letter_spacing"]
    if ls_blocks:
        warnings.warn(
            "letter_spacing animation is not supported. "
            "Opacity/scale/position will animate; letter spacing is ignored.",
            UserWarning,
            stacklevel=4,
        )

    return {
        "alpha":          alpha,
        "scale_expr":     scale_expr,
        "x_expr":         x_expr,
        "y_expr":         y_expr,
        "rotation_expr":  rotation_expr,
        "has_rotation":   has_rotation,
    }


# ---------------------------------------------------------------------------
# Template preprocessing: animation presets & global animations
# ---------------------------------------------------------------------------

def _expand_animation_presets(template: dict) -> None:
    """
    Expand preset references and apply global animations to all layers.
    Also expands opacity shorthands per layer before other processing.
    """
    presets = template.get("animation_presets") or {}
    global_anims = template.get("global_animations")
    layers = template.get("layers") or template.get("texts", [])

    global_blocks = []
    if isinstance(global_anims, list):
        for anim in global_anims:
            if anim.get("targets") == "all" and "preset" in anim:
                preset_name = anim["preset"]
                if preset_name in presets:
                    block = dict(presets[preset_name])
                    block["start"] = anim.get("start", 0)
                    global_blocks.append(block)

    for layer in layers:
        # ── Expand opacity shorthand first ────────────────────────────────
        _expand_opacity_shorthand(layer)

        # ── Expand preset references in animations array ──────────────────
        animations = layer.get("animations") or []
        expanded = []
        for block in animations:
            if "preset" in block and block["preset"] in presets:
                merged = dict(presets[block["preset"]])
                merged.update({k: v for k, v in block.items() if k != "preset"})
                expanded.append(merged)
            else:
                expanded.append(block)

        expanded.extend(global_blocks)
        layer["animations"] = expanded


# ---------------------------------------------------------------------------
# Pango/Cairo text rendering
# ---------------------------------------------------------------------------

def _render_text_to_pil(text: str, layer: dict, font_family: str, font_path: Path | None) -> "_PILImage.Image | None":
    """Render text to PIL Image using pango/cairo or Pillow."""
    if not font_family:
        font_family = "Sans"

    if not _PANGO_AVAILABLE or (font_path and font_family not in _get_pango_font_families()):
        return _render_text_with_pillow(text, layer, font_path)

    if not _PANGO_AVAILABLE:
        return _render_text_with_pillow(text, layer, font_path)

    padding = int(layer.get("padding", 6))
    color = _parse_color(layer.get("color", "#000000"))

    measure_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    measure_ctx = cairo.Context(measure_surface)
    measure_layout = _configure_pango_layout(measure_ctx, layer, text, font_family)

    ink, logical = measure_layout.get_pixel_extents()
    left   = min(logical.x, ink.x)
    top    = min(logical.y, ink.y)
    right  = max(logical.x + logical.width,  ink.x + ink.width)
    bottom = max(logical.y + logical.height, ink.y + ink.height)
    width  = max(1, right  - left + padding * 2)
    height = max(1, bottom - top  + padding * 2)

    draw_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw_ctx = cairo.Context(draw_surface)
    draw_layout = _configure_pango_layout(draw_ctx, layer, text, font_family)

    draw_ctx.set_source_rgba(color[0] / 255, color[1] / 255, color[2] / 255, 1)
    draw_ctx.move_to(padding - left, padding - top)
    PangoCairo.show_layout(draw_ctx, draw_layout)

    return _PILImage.frombuffer(
        "RGBA", (width, height), draw_surface.get_data(),
        "raw", "BGRA", 0, 1,
    )


def _configure_pango_layout(ctx, layer: dict, text: str, font_family: str):
    """Build a Pango layout for the given text layer."""
    layout = PangoCairo.create_layout(ctx)
    layout.set_text(text, -1)

    direction = layer.get("direction", "auto")
    if direction == "ltr":
        layout.get_context().set_base_dir(Pango.Direction.LTR)
        layout.set_auto_dir(False)
    elif direction == "rtl":
        layout.get_context().set_base_dir(Pango.Direction.RTL)
        layout.set_auto_dir(False)
    else:
        layout.set_auto_dir(True)

    if layer.get("max_width"):
        layout.set_width(int(layer["max_width"]) * Pango.SCALE)
        layout.set_wrap(Pango.WrapMode.WORD_CHAR)

    alignment = layer.get("align", "left").lower()
    if alignment == "center":
        layout.set_alignment(Pango.Alignment.CENTER)
    elif alignment == "right":
        layout.set_alignment(Pango.Alignment.RIGHT)
    else:
        layout.set_alignment(Pango.Alignment.LEFT)

    description = Pango.FontDescription()
    description.set_family(font_family)
    description.set_size(int(layer.get("font_size") or 18) * Pango.SCALE)
    layout.set_font_description(description)

    line_spacing = layer.get("line_spacing")
    if line_spacing is not None:
        layout.set_spacing(int(line_spacing) * Pango.SCALE)

    return layout


def _parse_color(value: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    color = str(value or "#000000").lstrip("#")
    if len(color) == 6:
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    return (0, 0, 0)


def _render_text_with_pillow(text: str, layer: dict, font_path: Path | None) -> "_PILImage.Image | None":
    """Fallback text rendering using Pillow."""
    if not _PIL_AVAILABLE or not font_path:
        return None

    padding = int(layer.get("padding", 6))
    color = _parse_color(layer.get("color", "#000000"))

    try:
        font = _PILFont.truetype(str(font_path), size=int(layer.get("font_size", 18)))
    except:
        return None

    lines = text.split("\n")
    bboxes = [font.getbbox(line) if line else (0, 0, 0, 0) for line in lines]
    line_heights = [box[3] - box[1] if (box[3] - box[1]) > 0 else 20 for box in bboxes]
    line_widths  = [box[2] - box[0] if line else 0 for line, box in zip(lines, bboxes)]
    text_width   = max(line_widths, default=0)
    line_spacing = int(layer.get("line_spacing", 0))
    text_height  = sum(line_heights) + max(0, len(lines) - 1) * line_spacing

    width  = max(1, text_width  + padding * 2)
    height = max(1, text_height + padding * 2)

    image = _PILImage.new("RGBA", (width, height), (0, 0, 0, 0))
    draw  = _PILDraw.Draw(image)

    align = layer.get("align", "left").lower()
    y = padding
    for line, line_width, line_height, bbox in zip(lines, line_widths, line_heights, bboxes):
        if align == "center":
            x = padding + (text_width - line_width) // 2
        elif align == "right":
            x = padding + (text_width - line_width)
        else:
            x = padding
        draw.text((x - bbox[0], y - bbox[1]), line, font=font, fill=(*color, 255))
        y += line_height + line_spacing

    return image


def _render_text_to_png_bytes(text: str, layer: dict, font_family: str, font_path: Path | None) -> bytes | None:
    """Render text to PNG bytes for FFmpeg input."""
    img = _render_text_to_pil(text, layer, font_family, font_path)
    if not img:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Position translation: drawtext → overlay
# ---------------------------------------------------------------------------

def _translate_pos_expr(expr: str | int | float, video_w: int, video_h: int, png_w: int, png_h: int, axis: str = 'x') -> str:
    """Translate a drawtext position expression to FFmpeg overlay context."""
    if isinstance(expr, (int, float)):
        return str(int(expr))

    s = str(expr).strip()

    if "text_w" in s or "text_h" in s:
        # Variable translation: text_w/text_h → overlay w/h ; w/h → main_w/main_h
        s_temp = s.replace("text_w", "__TW__").replace("text_h", "__TH__")
        s_temp = re.sub(r'\bw\b', 'W', s_temp)
        s_temp = re.sub(r'\bh\b', 'H', s_temp)
        s_temp = s_temp.replace("__TW__", "w").replace("__TH__", "h")
        return s_temp

    try:
        result = eval(s, {}, {'w': video_w, 'h': video_h, 'text_w': png_w, 'text_h': png_h})
        return str(int(result))
    except:
        return s


# ---------------------------------------------------------------------------
# Per-layer FFmpeg filter builder
# ---------------------------------------------------------------------------

def _build_pango_layer_filter(
    layer_idx: int, input_idx: int, png_w: int, png_h: int,
    layer: dict, template: dict, video_w: int, video_h: int
) -> tuple[list[str], str, str, str]:
    """
    Build FFmpeg filter steps for one pango-rendered text layer.

    Key fixes vs original:
      - colorchannelmixer is applied BEFORE format=rgba to avoid filter ordering issues.
      - scale uses a separate named output label to avoid label collisions.
      - All alpha expressions are clamped to [0,1].
      - overlay x/y expressions with 'W'/'H' variable refs are safe for FFmpeg eval.

    Returns: (filter_steps, out_label, overlay_x, overlay_y)
    """
    blocks = layer.get("animations") or []
    exprs = _build_layer_anim_exprs(layer, template)
    steps: list[str] = []

    # Each intermediate label must be unique to avoid FFmpeg graph conflicts.
    current = f"[{input_idx}:v]"

    # ── Step 1: convert to RGBA immediately so subsequent filters see alpha ──
    rgba_label = f"rgba{layer_idx}"
    steps.append(f"{current}format=rgba[{rgba_label}]")
    current = f"[{rgba_label}]"

    # ── Step 2: scale (if animated or non-unit) ───────────────────────────
    scale_is_static_one = exprs["scale_expr"].strip() == "1.0"
    if not scale_is_static_one:
        scaled_label = f"sc{layer_idx}"
        steps.append(
            f"{current}scale="
            f"w='iw*({exprs['scale_expr']})':"
            f"h='ih*({exprs['scale_expr']})':"
            f"eval=frame[{scaled_label}]"
        )
        current = f"[{scaled_label}]"

    # ── Step 3: rotation ─────────────────────────────────────────────────
    if exprs["has_rotation"]:
        rot_label = f"rt{layer_idx}"
        rot_rad = f"({exprs['rotation_expr']})*PI/180"
        steps.append(
            f"{current}rotate="
            f"angle='{rot_rad}':"
            f"fillcolor=none:"
            f"ow={video_w}:oh={video_h}:"
            f"eval=frame[{rot_label}]"
        )
        current = f"[{rot_label}]"

    # ── Step 4: opacity via fade filter ─────────────────────────────────
    # NOTE: colorchannelmixer's aa parameter only accepts static float values.
    # Use FFmpeg's fade filter for opacity animations (linear fades only).
    # WARNING: fade filter fades between 0→1 or 1→0. For arbitrary from/to values,
    # we apply the "from" value statically and use fade to transition.
    opacity_blocks = [b for b in blocks if b.get("property") == "opacity"]
    if opacity_blocks:
        for block_num, block in enumerate(opacity_blocks):
            from_val = _to_float(block.get("from"), _to_float(exprs["alpha"], 0.0))
            to_val   = _to_float(block.get("to"),   from_val)
            start    = _to_float(block.get("start"), 0.0)
            duration = _to_float(block.get("duration"), 0.5)
            
            alpha_label = f"al{layer_idx}_{block_num}"
            
            # Check if this is a standard fade-in or fade-out
            is_fade_in = (from_val < 0.1 and to_val > 0.9)
            is_fade_out = (from_val > 0.9 and to_val < 0.1)
            
            if is_fade_in:
                # Standard fade-in: use fade filter with linear progression
                steps.append(
                    f"{current}fade=t=in:st={start:.3f}:d={duration:.3f}[{alpha_label}]"
                )
            elif is_fade_out:
                # Standard fade-out: use fade filter with linear progression
                steps.append(
                    f"{current}fade=t=out:st={start:.3f}:d={duration:.3f}[{alpha_label}]"
                )
            else:
                # Non-standard fade: apply from_val statically, skip animation
                # (colorchannelmixer doesn't support expressions, fade only does 0/1)
                logger.warning(
                    f"Layer {layer_idx} opacity animation (from {from_val:.2f} to {to_val:.2f}) "
                    f"is not a standard fade-in (0→1) or fade-out (1→0). "
                    f"Applying static opacity {from_val:.2f}. "
                    f"Use fade-in/fade-out presets for animated opacity."
                )
                steps.append(
                    f"{current}colorchannelmixer=aa={from_val:.6f}[{alpha_label}]"
                )
            
            current = f"[{alpha_label}]"
    else:
        # No opacity animations, apply default static opacity
        alpha_label = f"al{layer_idx}"
        opacity_val = exprs["alpha"]
        steps.append(
            f"{current}colorchannelmixer=aa={opacity_val}[{alpha_label}]"
        )
        current = f"[{alpha_label}]"

    # Final output label for this layer (used in overlay)
    out_label = f"txt{layer_idx}"
    steps.append(f"{current}copy[{out_label}]")

    # ── Overlay position ─────────────────────────────────────────────────
    if exprs["has_rotation"]:
        ov_x, ov_y = "0", "0"
    else:
        ov_x = _translate_pos_expr(exprs["x_expr"], video_w, video_h, png_w, png_h, 'x')
        ov_y = _translate_pos_expr(exprs["y_expr"], video_w, video_h, png_h, png_h, 'y')

    return steps, out_label, ov_x, ov_y


# ---------------------------------------------------------------------------
# Public API: render from timed JSON template
# ---------------------------------------------------------------------------

def render_timed_json_video_template(
    template: dict,
    input_data: dict,
    output_override: str | None = None,
    fmt: str = "png"
) -> Path:
    """
    Render a timed JSON video invitation template with pango/cairo multilingual text.

    Supports:
      - animation presets (1008 schema) and explicit animations (1007 schema)
      - global animations (dict or array format)
      - per-layer animations
      - top-level "opacity" shorthand per layer

    Text is rendered to PNG using pango/cairo for proper multilingual/BiDi support.
    Animations are expressed via FFmpeg filter expressions (scale, opacity, position, rotation).
    All opacity expressions are clamped to [0,1] to prevent FFmpeg filter errors.
    """
    template = dict(template)
    _expand_animation_presets(template)  # also calls _expand_opacity_shorthand per layer

    data = expand_event_date({**template.get("data", {}), **input_data})
    base_video = (_resolve_path(template.get("background")) or _resolve_path(template.get("video")))
    if not base_video or not base_video.exists():
        raise FileNotFoundError(
            f"Base video not found: {template.get('background') or template.get('video')}"
        )

    width    = int(template.get("width")    or 396)
    height   = int(template.get("height")   or 558)
    fps      = int(template.get("fps")      or 30)
    duration = float(template.get("duration") or 5)
    output_path = (
        _resolve_path(output_override or template.get("output"))
        or (DEFAULT_OUTPUT_DIR / "output.mp4")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    layers = template.get("layers") or template.get("texts", [])

    # ── Render each text layer to PNG ────────────────────────────────────────
    layer_pngs: dict[int, tuple[bytes, int, int]] = {}

    for idx, layer in enumerate(layers):
        text = resolve_text(layer, data)
        if should_skip_layer(layer, text, data):
            continue
        text = text.strip()
        if not text:
            continue

        font_family, font_path = _resolve_video_font_spec(layer, template)
        png_bytes = _render_text_to_png_bytes(text, layer, font_family, font_path)
        if png_bytes:
            try:
                img = _PILImage.open(io.BytesIO(png_bytes))
                layer_pngs[idx] = (png_bytes, img.width, img.height)
            except:
                pass

    # ── Build FFmpeg command ──────────────────────────────────────────────────
    temp_files: list[Path] = []
    try:
        cmd = ["ffmpeg", "-y", "-i", str(base_video)]
        input_offset = 1

        layer_input_map: dict[int, int] = {}
        for layer_idx, (png_bytes, png_w, png_h) in layer_pngs.items():
            ttmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            ttmp.write(png_bytes)
            ttmp.close()
            temp_files.append(Path(ttmp.name))
            cmd.extend(["-loop", "1", "-i", ttmp.name])
            layer_input_map[layer_idx] = input_offset
            input_offset += 1

        # ── Build filter_complex ─────────────────────────────────────────
        filter_parts: list[str] = [
            f"[0:v]fps={fps},scale={width}:{height},setsar=1,format=yuv420p[base]"
        ]
        current_label = "base"

        for layer_idx, layer in enumerate(layers):
            if layer_idx not in layer_input_map:
                continue
            input_idx = layer_input_map[layer_idx]
            png_w, png_h = layer_pngs[layer_idx][1], layer_pngs[layer_idx][2]

            steps, label, ov_x, ov_y = _build_pango_layer_filter(
                layer_idx, input_idx, png_w, png_h, layer, template, width, height
            )
            filter_parts.extend(steps)

            next_label = f"mix{layer_idx}"
            filter_parts.append(
                f"[{current_label}][{label}]overlay="
                f"x='{ov_x}':y='{ov_y}':"
                f"format=auto:"
                f"shortest=1[{next_label}]"
            )
            current_label = next_label

        # Final output: convert back to yuv420p for H.264 compatibility
        filter_parts.append(f"[{current_label}]format=yuv420p[v]")

        filter_complex = ";".join(filter_parts)
        logger.debug("filter_complex:\n%s", filter_complex)

        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", "[v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "18",
            "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            "-t", str(duration),
            str(output_path),
        ])

        logger.debug("FFmpeg command: %s", " ".join(cmd))
        result = subprocess.run(cmd, check=False, capture_output=True, text=True)

        if result.returncode != 0:
            logger.error("FFmpeg stderr:\n%s", result.stderr)
            raise RuntimeError(
                result.stderr.strip() or "ffmpeg failed to render the invitation video."
            )

    finally:
        for tmp in temp_files:
            tmp.unlink(missing_ok=True)

    return output_path