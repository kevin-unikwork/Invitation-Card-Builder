import os
from typing import Any

import freetype
import uharfbuzz as hb
from PIL import Image, ImageColor

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def resolve_path(path: str) -> str:
    """Resolve a relative path to absolute based on project root."""
    if os.path.isabs(path):
        candidate = path
    else:
        candidate = os.path.join(BASE_DIR, path)

    if os.path.exists(candidate):
        return candidate

    # Be forgiving about accidental duplicate extensions in template JSON.
    if candidate.endswith(".ttf.ttf"):
        fixed = candidate[:-4]
        if os.path.exists(fixed):
            return fixed

    raise FileNotFoundError(f"Asset not found: {path}")


def resolve_output_path(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def wrap_text(text: str, font_path: str, font_size: int, max_width: int | None) -> list[str]:
    """Wrap text into multiple lines based on shaped text width."""
    if not text:
        return [""]

    paragraphs = str(text).splitlines() or [str(text)]
    lines: list[str] = []

    for paragraph in paragraphs:
        if not paragraph.strip():
            lines.append("")
            continue

        if not max_width:
            lines.append(paragraph)
            continue

        words = paragraph.split()
        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"
            if measure_text(candidate, font_path, font_size) <= max_width:
                current = candidate
                continue

            if current:
                lines.append(current)
                current = word
                continue

            # Fallback for a single very long token.
            chunk = ""
            for char in word:
                candidate = chunk + char
                if chunk and measure_text(candidate, font_path, font_size) > max_width:
                    lines.append(chunk)
                    chunk = char
                else:
                    chunk = candidate
            current = chunk

        if current:
            lines.append(current)

    return lines or [""]


def font_supports_text(font_path: str, text: str) -> bool:
    face = freetype.Face(font_path)
    return all(
        ch.isspace() or face.get_char_index(ord(ch)) != 0
        for ch in text
    )


def choose_font_path(
    fonts: dict[str, str],
    preferred_font_key: str,
    text: str,
) -> str:
    preferred_path = resolve_path(fonts[preferred_font_key])
    if font_supports_text(preferred_path, text):
        return preferred_path

    for font_key, font_rel_path in fonts.items():
        if font_key == preferred_font_key:
            continue
        candidate_path = resolve_path(font_rel_path)
        if font_supports_text(candidate_path, text):
            return candidate_path

    return preferred_path


def _build_fonts(font_path: str, font_size: int) -> tuple[freetype.Face, hb.Font, int]:
    face = freetype.Face(font_path)
    face.set_pixel_sizes(0, font_size)

    with open(font_path, "rb") as font_file:
        font_data = font_file.read()

    hb_face = hb.Face(font_data)
    hb_font = hb.Font(hb_face)
    hb.ot_font_set_funcs(hb_font)
    hb_font.scale = (font_size * 64, font_size * 64)

    return face, hb_font, hb_face.upem


def _shape_text(text: str, font_path: str, font_size: int) -> dict[str, Any]:
    face, hb_font, _ = _build_fonts(font_path, font_size)

    buffer = hb.Buffer()
    buffer.add_str(text)
    buffer.guess_segment_properties()
    hb.shape(hb_font, buffer)

    infos = buffer.glyph_infos
    positions = buffer.glyph_positions

    placements: list[dict[str, int]] = []
    pen_x = 0
    pen_y = 0
    min_left = 0
    min_top = 0
    max_right = 0
    max_bottom = 0

    for info, pos in zip(infos, positions):
        x_offset = pos.x_offset / 64.0
        y_offset = pos.y_offset / 64.0
        origin_x = pen_x / 64.0 + x_offset
        origin_y = pen_y / 64.0 + y_offset

        face.load_glyph(info.codepoint, freetype.FT_LOAD_DEFAULT)
        glyph = face.glyph

        left = origin_x + glyph.metrics.horiBearingX / 64.0
        top = origin_y - glyph.metrics.horiBearingY / 64.0
        right = left + glyph.metrics.width / 64.0
        bottom = top + glyph.metrics.height / 64.0

        min_left = min(min_left, int(left))
        min_top = min(min_top, int(top))
        max_right = max(max_right, int(right))
        max_bottom = max(max_bottom, int(bottom))

        placements.append(
            {
                "glyph_id": info.codepoint,
                "x": int(round(origin_x)),
                "y": int(round(origin_y)),
            }
        )

        pen_x += pos.x_advance
        pen_y += pos.y_advance

    metrics = face.size
    ascent = int(round(metrics.ascender / 64.0))
    descent = int(round(abs(metrics.descender) / 64.0))
    width = int(round(pen_x / 64.0))

    if placements:
        ascent = max(ascent, abs(min_top))
        descent = max(descent, max_bottom)

    return {
        "placements": placements,
        "width": max(width, max_right - min_left),
        "ascent": ascent,
        "descent": descent,
        "face": face,
    }


def measure_text(text: str, font_path: str, font_size: int) -> int:
    return _shape_text(text, font_path, font_size)["width"]


def _draw_shaped_text(
    image: Image.Image,
    text: str,
    font_path: str,
    font_size: int,
    color: str,
    x: int,
    y_top: int,
) -> None:
    shaped = _shape_text(text, font_path, font_size)
    face: freetype.Face = shaped["face"]
    rgba = ImageColor.getrgb(color) + (255,)
    baseline_y = y_top + shaped["ascent"]

    for placement in shaped["placements"]:
        face.load_glyph(placement["glyph_id"], freetype.FT_LOAD_RENDER)
        bitmap = face.glyph.bitmap
        if bitmap.width == 0 or bitmap.rows == 0:
            continue

        glyph_img = Image.frombytes("L", (bitmap.width, bitmap.rows), bytes(bitmap.buffer))
        glyph_rgba = Image.new("RGBA", glyph_img.size, rgba)
        glyph_rgba.putalpha(glyph_img)

        draw_x = x + placement["x"] + face.glyph.bitmap_left
        draw_y = baseline_y + placement["y"] - face.glyph.bitmap_top
        image.alpha_composite(glyph_rgba, (int(draw_x), int(draw_y)))


def _resolve_layer_x(layer: dict[str, Any], image_width: int, text_width: int) -> int:
    x = layer.get("x", "(w-text_w)/2")
    if isinstance(x, (int, float)):
        return int(x)

    if isinstance(x, str) and x.strip() == "(w-text_w)/2":
        return int((image_width - text_width) / 2)

    try:
        return int(float(x))
    except (TypeError, ValueError):
        return int((image_width - text_width) / 2)


def render_template(template, input_data, output_path="static/output/output.png"):
    """Render a template with given input data and save to output_path."""
    background_path = resolve_path(template["background"])
    output_path = resolve_output_path(output_path)

    image = Image.open(background_path).convert("RGBA")
    assets = template.get("assets", {})
    fonts = assets.get("fonts", {})

    for layer in template.get("layers", []):
        if layer.get("type") != "text":
            continue

        if "value" in layer:
            text = layer["value"]
        else:
            text = input_data.get(layer.get("key", ""), "")

        if not text and layer.get("skip_if_empty", False):
            continue

        text = str(text)
        font_path = choose_font_path(fonts, layer["font"], text)
        font_size = int(layer.get("font_size", 32))
        max_width = layer.get("max_width")
        lines = wrap_text(text, font_path, font_size, max_width)
        line_spacing = int(layer.get("line_spacing", 14))

        ascent = _shape_text("Ag", font_path, font_size)["ascent"]
        descent = _shape_text("Ag", font_path, font_size)["descent"]
        line_height = max(font_size, ascent + descent) + line_spacing
        base_y = int(layer["y"])

        for index, line in enumerate(lines):
            shaped = _shape_text(line, font_path, font_size)
            x = _resolve_layer_x(layer, image.width, shaped["width"])
            y_top = base_y + index * line_height
            _draw_shaped_text(
                image=image,
                text=line,
                font_path=font_path,
                font_size=font_size,
                color=layer["color"],
                x=x,
                y_top=y_top,
            )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    image.save(output_path)
    return output_path
