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
import math
import os
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

# ── Logging switch ────────────────────────────────────────────────────────────
# Set to False to silence all video_processing logs completely.
# Set to True  to see INFO-level progress in the terminal.
# To also see DEBUG detail (per-frame values, font resolution, etc.) run with:
#   logging.getLogger("video_processing").setLevel(logging.DEBUG)
VIDEO_PROCESSING_LOGGING = True

logger = logging.getLogger(__name__)
logger.propagate = False  # Don't double-print if root logger is also configured.
if VIDEO_PROCESSING_LOGGING:
    _ch = logging.StreamHandler()
    _ch.setFormatter(logging.Formatter(
        "%(asctime)s  [VP] %(levelname)-7s  %(message)s", datefmt="%H:%M:%S"
    ))
    logger.setLevel(logging.DEBUG)
    logger.addHandler(_ch)
else:
    logger.addHandler(logging.NullHandler())

FONT_FAMILY_CACHE = {}
PANGO_FONT_FAMILY_CACHE = None

FONTCONFIG_FILE = Path('/tmp/invitation-fontconfig.xml')
FONTCONFIG_CACHE = Path('/tmp/fontconfig-cache')
FONTCONFIG_CACHE.mkdir(exist_ok=True)
FONT_DIR = PROJECT_ROOT / "static" / "fonts"


fontconfig_xml = f"""<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <dir>{FONT_DIR}</dir>
  <cachedir>{FONTCONFIG_CACHE}</cachedir>
</fontconfig>
"""
FONTCONFIG_FILE.write_text(fontconfig_xml)
os.environ['FONTCONFIG_FILE'] = str(FONTCONFIG_FILE)

subprocess.run(
    ['fc-cache', '-f', str(FONT_DIR)],
    check=False,
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)


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


def _font_family_from_file(path: Path) -> str:
    """Read and cache the font family name from a font file using Pillow."""
    if not _PIL_AVAILABLE:
        return "Monospace"
    resolved = path.resolve()
    cache_key = str(resolved).lower()
    if cache_key in FONT_FAMILY_CACHE:
        logger.debug("font cache hit: %s → %r", path.name, FONT_FAMILY_CACHE[cache_key])
        return FONT_FAMILY_CACHE[cache_key]
    try:
        family = _PILFont.truetype(str(resolved), size=16).getname()[0]
        FONT_FAMILY_CACHE[cache_key] = family
        logger.debug("font loaded: %s → family %r", path.name, family)
        return family
    except Exception as exc:
        logger.warning("could not read font family from %s (%s) — using Monospace", path.name, exc)
        return "Monospace"


def _resolve_video_font_spec(layer: dict, template: dict) -> tuple[str, Path | None]:
    """Resolve a layer's font config into a family name and optional file path."""
    font_ref = layer.get("font")
    if not font_ref:
        logger.debug("layer has no font key — using Sans")
        return "Sans", None

    assets = template.get("assets") or {}
    fonts = assets.get("fonts") or {}

    if font_ref in fonts:
        font_config = fonts[font_ref]
        if isinstance(font_config, str):
            resolved_path = _resolve_path(font_config)
            if resolved_path and resolved_path.exists():
                family = _font_family_from_file(resolved_path)
                logger.debug("font %r → file %s  family=%r", font_ref, resolved_path.name, family)
                return family, resolved_path
            logger.warning("font %r → path %r not found — using ref as family name", font_ref, font_config)
            return font_ref, None
        elif isinstance(font_config, dict):
            font_file = font_config.get("file")
            font_family = font_config.get("family")
            if font_file:
                resolved_path = _resolve_path(font_file)
                if resolved_path and resolved_path.exists():
                    family = _font_family_from_file(resolved_path)
                    logger.debug("font %r → file %s  family=%r", font_ref, resolved_path.name, family)
                    return family, resolved_path
            logger.debug("font %r → no file found, using family=%r", font_ref, font_family or "Sans")
            return font_family or "Sans", None

    resolved_path = _resolve_path(font_ref)
    if resolved_path and resolved_path.exists() and resolved_path.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        family = _font_family_from_file(resolved_path)
        logger.debug("font %r resolved directly → %s  family=%r", font_ref, resolved_path.name, family)
        return family, resolved_path

    logger.debug("font %r not in assets and not a file — treating as family name", font_ref)
    return font_ref, None


# ---------------------------------------------------------------------------
# ─────────────────────────  ANIMATION ENGINE (Python - per-frame)  ──────────
#
# Flow overview:
#   render loop
#     └─ for each layer
#          └─ for each property (scale, opacity, x, y, rotation, blur)
#               └─ _compute_property(pre-filtered blocks, default, t)
#                    ├─ walks blocks in order; each block has a [start, end) window
#                    ├─ if t is before a block → hold from-value and stop
#                    ├─ if t is inside a block → interpolate via _ease_value
#                    └─ if t is past a block   → take to-value and try next block
#
# Preprocessing (runs once per render, before the frame loop):
#   _expand_animation_presets
#     ├─ expands opacity shorthand dict → animation blocks
#     ├─ replaces preset refs with full block dicts
#     └─ appends global_animations blocks to every layer
# ---------------------------------------------------------------------------

def _compute_progress(t: float, start: float, duration: float, loop: bool = False) -> float:
    # Returns a 0.0–1.0 progress value for a block window [start, start+duration].
    # Called once per active block per property per frame.
    safe_dur = max(duration, 0.001)
    if t < start:
        # Current time is before this block's window — not started yet.
        return 0.0
    elapsed = t - start
    if loop:
        # Wrap elapsed time so the animation cycles continuously.
        return (elapsed % safe_dur) / safe_dur
    # Clamp at 1.0 so the block holds its final value after it ends.
    return min(elapsed / safe_dur, 1.0)


_EASING_NAME_CACHE: dict[str, str] = {}

def _ease_value(progress: float, easing: str) -> float:
    # Normalise the easing name once and cache it — this is called every frame
    # for every active animation block, so avoiding repeated string ops matters.
    name = _EASING_NAME_CACHE.get(easing)
    if name is None:
        name = str(easing or "linear").strip().lower().replace("-", "_")
        _EASING_NAME_CACHE[easing] = name
        logger.debug("easing curve registered: %r → %r", easing, name)

    # Clamp progress to [0, 1] before applying the curve.
    p = max(0.0, min(1.0, progress))

    # Each branch maps linear progress p → curved output in [0, 1].
    if name in {"ease_out", "easeout", "out"}:
        return 1 - (1 - p) ** 2
    if name in {"ease_out_cubic", "easeoutcubic", "out_cubic"}:
        return 1 - (1 - p) ** 3
    if name in {"ease_in", "easein", "in"}:
        return p ** 2
    if name in {"ease_in_cubic", "easeincubic", "in_cubic"}:
        return p ** 3
    if name in {"ease_in_out", "easeinout", "in_out"}:
        return 2 * p**2 if p < 0.5 else 1 - (-2*p + 2)**2 / 2
    if name in {"ease_in_out_cubic", "easeinoutcubic", "in_out_cubic"}:
        return 4 * p**3 if p < 0.5 else 1 - (-2*p + 2)**3 / 2
    if name in {"bounce_out", "bounceout"}:
        if p < 1/2.75:    return 7.5625 * p * p
        if p < 2/2.75:    p -= 1.5/2.75;   return 7.5625*p*p + 0.75
        if p < 2.5/2.75:  p -= 2.25/2.75;  return 7.5625*p*p + 0.9375
        p -= 2.625/2.75;  return 7.5625*p*p + 0.984375
    if name in {"elastic_out", "elasticout"}:
        if p in (0.0, 1.0): return p
        return pow(2, -10*p) * math.sin((p*10 - 0.75) * (2*math.pi/3)) + 1
    # Unknown easing name — fall through to linear.
    if name != "linear":
        logger.warning("unknown easing %r — falling back to linear", easing)
    return p


def _compute_property(prop_blocks: list[dict], default: float, t: float) -> float:
    """Walk pre-filtered same-property blocks and return the interpolated value at time t.

    Block state machine (executed in order):
      FINISHED  → t >= block.end   : take to_val, continue to next block
      ACTIVE    → t >= block.start : interpolate, stop
      PENDING   → t < block.start  : keep current value, stop
    """
    if not prop_blocks:
        return default

    # Hold the first block's from-value before its window opens.
    # This keeps e.g. a fade-in layer invisible before its start time
    # instead of flashing at the generic default (1.0).
    value = _to_float(prop_blocks[0].get("from"), default)

    for block in prop_blocks:
        from_val = _to_float(block.get("from"), value)
        to_val   = _to_float(block.get("to"),   from_val)
        start    = _to_float(block.get("start"),    0.0)
        dur      = _to_float(block.get("duration"), 0.5)
        loop     = bool(block.get("loop", False))
        easing   = str(block.get("easing") or "linear")
        end      = start + max(dur, 0.001)

        if not loop and t >= end:
            # FINISHED: this block is done; latch its final value and check next block.
            value = to_val
        elif t >= start:
            # ACTIVE: we are inside this block's time window — interpolate.
            p     = _compute_progress(t, start, dur, loop)
            value = from_val + (to_val - from_val) * _ease_value(p, easing)
            break
        else:
            # PENDING: haven't reached this block yet — keep the accumulated value.
            break

    return value


def _eval_pos(expr, video_w: int, video_h: int, img_w: int, img_h: int) -> float:
    """Evaluate a position expression — numeric or string like '(w-text_w)/2'.

    Available variables inside the expression:
      w / W   → video width   h / H   → video height
      text_w  → layer display width   text_h  → layer display height
    """
    if isinstance(expr, (int, float)):
        return float(expr)
    try:
        result = float(eval(str(expr), {"__builtins__": {}}, {
            "w": video_w, "h": video_h,
            "W": video_w, "H": video_h,
            "text_w": img_w, "text_h": img_h,
        }))
        logger.debug("eval_pos %r → %.2f  (video=%dx%d  img=%dx%d)",
                     expr, result, video_w, video_h, img_w, img_h)
        return result
    except Exception as exc:
        logger.warning("eval_pos failed for expr %r — defaulting to 0.0 (%s)", expr, exc)
        return 0.0


def _apply_layer_opacity(img: "_PILImage.Image", opacity: float) -> "_PILImage.Image":
    """Multiply the alpha channel of every pixel by opacity in-place on a copy."""
    if opacity >= 1.0:
        return img  # Fast-path: nothing to do.
    opacity = max(0.0, min(1.0, opacity))
    # Split → scale alpha → merge back.  A point() LUT is faster than numpy here
    # because PIL's C layer processes all pixels without Python overhead.
    r, g, b, a = img.split()
    a = a.point(lambda x: round(x * opacity))
    return _PILImage.merge("RGBA", (r, g, b, a))


# ---------------------------------------------------------------------------
# Opacity shorthand → animation blocks converter
# ---------------------------------------------------------------------------

def _expand_opacity_shorthand(layer: dict) -> None:
    """Convert a top-level "opacity" dict on a layer into concrete animation blocks.

    The shorthand lets template authors write a single compact dict instead of
    manually constructing animation blocks.  This function normalises it into the
    same format that _compute_property understands.

    Input shape:
        { "opacity": { "initial": 0, "animate": true,
                       "from": 0, "to": 1, "start": 0.0,
                       "duration": 0.5, "easing": "easeOut" } }

    Output: one or two blocks prepended to layer["animations"]:
        1. (optional) static pre-block  → holds `initial` opacity until `start`
        2. animation block              → fades from→to over [start, start+duration]

    If animate=false, only a single static block at `initial` is injected.
    All opacity values are clamped to [0, 1] here so downstream code never
    needs to guard against out-of-range values.
    """
    opacity_cfg = layer.get("opacity")
    if not isinstance(opacity_cfg, dict):
        return  # No shorthand — nothing to expand.

    layer_id = layer.get("id") or layer.get("text", "?")[:20]
    initial  = max(0.0, min(1.0, _to_float(opacity_cfg.get("initial"), 1.0)))
    animate  = bool(opacity_cfg.get("animate", False))

    animations = layer.setdefault("animations", [])

    if not animate:
        # Static opacity: inject a constant block that spans the whole video duration.
        # duration=3600 acts as "infinity" — it will never finish during a normal render.
        block = {
            "property": "opacity",
            "from": initial,
            "to": initial,
            "start": 0.0,
            "duration": 3600.0,
            "easing": "linear",
        }
        animations.insert(0, block)
        logger.debug("[%s] opacity shorthand → static block initial=%.2f", layer_id, initial)
        return

    # Animated opacity: build the transition block, clamping all values at Python
    # level to avoid out-of-range values reaching FFmpeg expressions.
    from_val = max(0.0, min(1.0, _to_float(opacity_cfg.get("from"), initial)))
    to_val   = max(0.0, min(1.0, _to_float(opacity_cfg.get("to"),   from_val)))
    start    = _to_float(opacity_cfg.get("start"),    0.0)
    duration = _to_float(opacity_cfg.get("duration"), 0.5)
    easing   = str(opacity_cfg.get("easing") or "linear")

    logger.debug(
        "[%s] opacity shorthand → animate  initial=%.2f  from=%.2f→%.2f  "
        "start=%.2fs  dur=%.2fs  easing=%s",
        layer_id, initial, from_val, to_val, start, duration, easing,
    )

    # If initial opacity differs from the animation's from-value, insert a
    # static pre-block so the layer holds `initial` opacity before `start`.
    # Example: initial=0, from=0, to=1 at start=1s → layer is invisible for
    # the first second, then fades in.
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
        logger.debug("[%s] opacity shorthand → pre-block initial=%.2f until start=%.2fs",
                     layer_id, initial, start)

    anim_block = {
        "property": "opacity",
        "from": from_val,
        "to": to_val,
        "start": start,
        "duration": max(duration, 0.001),
        "easing": easing,
    }
    # Place the animation block after the optional pre-block.
    insert_pos = 1 if abs(initial - from_val) > 1e-6 else 0
    animations.insert(insert_pos, anim_block)

# ---------------------------------------------------------------------------
# Template preprocessing: animation presets & global animations
# ---------------------------------------------------------------------------

def _expand_animation_presets(template: dict) -> None:
    """Normalise all animation config on every layer into flat animation block lists.

    This runs ONCE before the frame loop.  After it returns, every layer has a
    plain list in layer["animations"] — no shorthand dicts, no preset refs.

    Processing order (matters: later steps see earlier results):
      1. Opacity shorthand  → _expand_opacity_shorthand injects blocks into animations
      2. Preset refs        → each {"preset": "name", ...} block is replaced by
                              the preset's block dict, with any overrides merged in
      3. Global animations  → blocks that target "all" layers are appended last
    """
    presets     = template.get("animation_presets") or {}
    global_anims = template.get("global_animations")
    layers      = template.get("layers") or template.get("texts", [])

    logger.debug("expand_animation_presets: %d preset(s) defined, %d layer(s)",
                 len(presets), len(layers))

    # ── Step 3 prep: collect global blocks that apply to all layers ───────────
    # These are resolved once and appended to every layer at the end.
    global_blocks: list[dict] = []
    if isinstance(global_anims, list):
        for anim in global_anims:
            if anim.get("targets") == "all" and "preset" in anim:
                preset_name = anim["preset"]
                if preset_name in presets:
                    block = dict(presets[preset_name])
                    block["start"] = anim.get("start", 0)
                    global_blocks.append(block)
                    logger.debug("global animation: preset %r resolved, start=%.2f",
                                 preset_name, block["start"])
                else:
                    logger.warning("global animation references unknown preset %r — skipped",
                                   preset_name)

    for layer in layers:
        layer_id = layer.get("id") or layer.get("text", "?")[:20]

        # ── Step 1: expand opacity shorthand → injects blocks at front of list ──
        _expand_opacity_shorthand(layer)

        # ── Step 2: inline any preset references in the animations array ─────────
        animations = layer.get("animations") or []
        expanded: list[dict] = []
        for block in animations:
            if "preset" in block and block["preset"] in presets:
                # Merge: start with preset defaults, then layer-level overrides win
                # (everything except the "preset" key itself).
                merged = dict(presets[block["preset"]])
                merged.update({k: v for k, v in block.items() if k != "preset"})
                expanded.append(merged)
                logger.debug("[%s] preset ref %r inlined → property=%s",
                             layer_id, block["preset"], merged.get("property"))
            else:
                expanded.append(block)

        # ── Step 3: append global blocks so they run after per-layer animations ──
        expanded.extend(global_blocks)

        layer["animations"] = expanded
        logger.debug("[%s] final animation blocks: %d  properties: %s",
                     layer_id,
                     len(expanded),
                     sorted({b.get("property") for b in expanded if b.get("property")}))


# ---------------------------------------------------------------------------
# Pango/Cairo text rendering
# ---------------------------------------------------------------------------

def _render_text_to_pil(text: str, layer: dict, font_family: str, font_path: Path | None) -> "_PILImage.Image | None":
    """Render text to PIL Image using pango/cairo or Pillow."""
    if not font_family:
        font_family = "Sans"

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
    logger.debug("Pango requested font: %s | resolved: %s", font_family, layout.get_font_description().get_family())

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




def _render_text_to_png_bytes(text: str, layer: dict, font_family: str, font_path: Path | None) -> bytes | None:
    """Render text to PNG bytes for FFmpeg input."""
    img = _render_text_to_pil(text, layer, font_family, font_path)
    if not img:
        return None
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _scale_text_render_layer(layer: dict, factor: int) -> dict:
    """Return a copy of a text layer rendered at higher pixel density."""
    if factor <= 1:
        return layer

    scaled = dict(layer)
    for key in ("font_size", "padding", "line_spacing", "max_width"):
        value = scaled.get(key)
        if isinstance(value, (int, float)):
            scaled[key] = int(round(value * factor))
    return scaled




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
    Render a timed JSON video invitation template.

    Python per-frame compositing loop — smooth animation for all properties:
      scale    — LANCZOS resize at render_scale resolution, no integer-grid jitter
      opacity  — per-frame alpha multiply with full easing support
      x / y    — per-frame position with expression support e.g. '(w-text_w)/2'
      rotation — per-frame PIL rotate with transparent fill
      blur     — per-frame GaussianBlur radius

    Easing curves: linear, ease_in/out, ease_in_out, *_cubic, bounce_out, elastic_out.

    Composite is done at text_render_scale× resolution (default 4×).
    A 1-pixel rounding error at render scale = 0.25px at output → imperceptible.
    Final 4× LANCZOS downscale averages sub-pixel jitter to zero.
    """
    template = dict(template)
    _expand_animation_presets(template)

    data = expand_event_date({**template.get("data", {}), **input_data})
    base_video = (_resolve_path(template.get("background")) or _resolve_path(template.get("video")))
    if not base_video or not base_video.exists():
        raise FileNotFoundError(
            f"Base video not found: {template.get('background') or template.get('video')}"
        )

    width    = int(template.get("width")    or 396)
    height   = int(template.get("height")   or 558)
    fps      = int(template.get("fps")      or 60)
    duration = float(template.get("duration") or 5)
    text_render_scale = max(1, int(template.get("text_render_scale") or 4))

    # internal_fps renders at a higher rate then decimates — but easing is already sampled
    # correctly at output fps, so this adds no smoothness and the fps filter can drift.
    # Only override if the template explicitly sets it.
    internal_fps = int(template.get("internal_fps") or fps)
    output_path = (
        _resolve_path(output_override or template.get("output"))
        or (DEFAULT_OUTPUT_DIR / "output.mp4")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    layers = template.get("layers") or template.get("texts", [])
    total_frames = int(duration * internal_fps)

    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("▶  render start")
    logger.info("   output    : %s", output_path)
    logger.info("   video     : %s", base_video.name)
    logger.info("   size      : %dx%d  fps=%d  duration=%.1fs", width, height, fps, duration)
    logger.info("   frames    : %d  render_scale=%dx", total_frames, text_render_scale)
    logger.info("   layers    : %d total", len(layers))

    # ── Render each text layer to a HQ PIL image (once, before the frame loop) ─
    # Rendered at text_render_scale× so every per-frame resize is a downscale → sharp.
    layer_images: dict[int, tuple["_PILImage.Image", int, int]] = {}

    for idx, layer in enumerate(layers):
        text = resolve_text(layer, data)
        if should_skip_layer(layer, text, data):
            logger.debug("  layer %d skipped (should_skip_layer)", idx)
            continue
        text = text.strip()
        if not text:
            logger.debug("  layer %d skipped (empty text)", idx)
            continue
        font_family, font_path = _resolve_video_font_spec(layer, template)
        render_layer = _scale_text_render_layer(layer, text_render_scale)
        png_bytes = _render_text_to_png_bytes(text, render_layer, font_family, font_path)
        if not png_bytes:
            logger.warning("  layer %d — text render failed for %r", idx, text[:40])
            continue
        img = _PILImage.open(io.BytesIO(png_bytes)).convert("RGBA")
        display_w = max(1, int(round(img.width  / text_render_scale)))
        display_h = max(1, int(round(img.height / text_render_scale)))
        layer_images[idx] = (img, display_w, display_h)
        logger.info("   layer %2d : %r  font=%s  display=%dx%d  anims=%s",
                    idx,
                    text[:30],
                    font_family,
                    display_w, display_h,
                    sorted({b.get("property") for b in (layer.get("animations") or [])
                            if b.get("property")}) or "none"
                    )

    # ── Pre-build per-layer animation block index (property → blocks) ────────
    # Avoids repeated list comprehensions inside the per-frame loop.
    layer_anim_cache: dict[int, dict[str, list]] = {}
    for layer_idx, layer in enumerate(layers):
        if layer_idx not in layer_images:
            continue
        by_prop: dict[str, list] = {}
        for b in (layer.get("animations") or []):
            p = b.get("property")
            if p:
                by_prop.setdefault(p, []).append(b)
        layer_anim_cache[layer_idx] = by_prop

    # ── Composite & output dimensions ────────────────────────────────────────
    render_w    = width  * text_render_scale
    render_h    = height * text_render_scale
    frame_bytes = width  * height * 3   # bytes per RGB24 decoded frame
    # total_frames already computed above for the startup log
    _log_every  = max(1, total_frames // 10)  # log progress every ~10 %

    # ── Decode base video ─────────────────────────────────────────────────────
    decode = subprocess.Popen([
        "ffmpeg", "-i", str(base_video),
        "-vf", f"fps={internal_fps},scale={width}:{height},setsar=1",
        "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
    ], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    # ── Encode output with optional frame rate decimation ─────────────────────
    # rawvideo avoids per-frame PNG compression — direct RGB bytes to ffmpeg.
    encode_args = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-r", str(internal_fps),
        "-video_size", f"{width}x{height}", "-i", "-",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        "-t", str(duration),
    ]
    if internal_fps > fps:
        encode_args.extend(["-vf", f"fps={fps}"])
    encode_args.append(str(output_path))
    
    encode = subprocess.Popen(encode_args, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        for frame_num in range(total_frames):
            raw = decode.stdout.read(frame_bytes)
            if len(raw) < frame_bytes:
                break

            # Time computed from internal_fps for smooth frame-to-frame interpolation
            t = frame_num / internal_fps

            # Upscale base video frame to render resolution.
            # The final 4× downscale averages these pixels back, so any softness
            # from upscaling is invisible in the output — only sharpness matters.
            canvas = (
                _PILImage.frombytes("RGB", (width, height), raw)
                         .resize((render_w, render_h), _PILImage.Resampling.LANCZOS)
                         .convert("RGBA")
            )

            for layer_idx, layer in enumerate(layers):
                if layer_idx not in layer_images:
                    continue

                img_hq, display_w, display_h = layer_images[layer_idx]
                by_prop = layer_anim_cache[layer_idx]

                # ── Animation values at time t ──────────────────────────────
                scale    = _compute_property(by_prop.get("scale",    []), 1.0, t)
                opacity  = _compute_property(by_prop.get("opacity",  []), 1.0, t)
                rotation = _compute_property(by_prop.get("rotation", []), 0.0, t)
                blur_r   = _compute_property(by_prop.get("blur",     []), 0.0, t)
                opacity  = max(0.0, min(1.0, opacity))

                if opacity < 0.004:
                    continue  # fully invisible — skip compositing

                # ── Scale (float before rounding to prevent cumulative jitter) ──
                scale_hq_w = display_w * text_render_scale * scale
                scale_hq_h = scale_hq_w * img_hq.height / img_hq.width
                target_w = max(1, round(scale_hq_w))
                target_h = max(1, round(scale_hq_h))
                img = img_hq.resize((target_w, target_h), _PILImage.Resampling.LANCZOS)

                # ── Blur ───────────────────────────────────────────────────
                if blur_r > 0.1:
                    img = img.filter(_PILFilter.GaussianBlur(radius=blur_r * text_render_scale))

                # ── Rotation ───────────────────────────────────────────────
                if abs(rotation) > 0.05:
                    img = img.rotate(
                        -rotation, expand=True,
                        resample=_PILImage.Resampling.BICUBIC,
                        fillcolor=(0, 0, 0, 0),
                    )

                # ── Opacity ────────────────────────────────────────────────
                img = _apply_layer_opacity(img, opacity)

                # ── Position ───────────────────────────────────────────────
                # Use float-precision display size derived from scale directly — NOT
                # from img.width/text_render_scale, which applies a second round() on
                # top of the already-rounded target_w.  That double-rounding causes
                # centered layers to snap by 0.5px at irregular intervals (= the jerk).
                disp_img_w = display_w * scale
                disp_img_h = display_h * img_hq.height / img_hq.width * scale

                base_x = _eval_pos(layer.get("x", 0), width, height, disp_img_w, disp_img_h)
                base_y = _eval_pos(layer.get("y", 0), width, height, disp_img_w, disp_img_h)

                x = _compute_property(by_prop["x"], base_x, t) if "x" in by_prop else base_x
                y = _compute_property(by_prop["y"], base_y, t) if "y" in by_prop else base_y

                px = round(x * text_render_scale)
                py = round(y * text_render_scale)

                # Rotation expands the canvas; shift back so the centre stays fixed
                if abs(rotation) > 0.05:
                    px -= (img.width  - target_w) // 2
                    py -= (img.height - target_h) // 2

                canvas.paste(img, (px, py), img)

            # Final downscale: 4× LANCZOS averaging makes sub-pixel errors invisible
            out = canvas.resize((width, height), _PILImage.Resampling.LANCZOS).convert("RGB")
            encode.stdin.write(out.tobytes())

            if frame_num % _log_every == 0:
                pct = frame_num / total_frames * 100
                logger.info("   encoding  frame %4d / %d  (%.0f%%)  t=%.2fs",
                            frame_num, total_frames, pct, t)

    finally:
        decode.stdout.close()
        decode.wait()
        encode.stdin.close()
        stderr = encode.stderr.read().decode()
        if encode.wait() != 0:
            logger.error("FFmpeg encode stderr:\n%s", stderr)
            raise RuntimeError(stderr.strip() or "ffmpeg failed to encode video.")

    logger.info("✓  render complete → %s", output_path)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return output_path
