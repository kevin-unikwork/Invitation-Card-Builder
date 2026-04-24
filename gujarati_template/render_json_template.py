import argparse
import ctypes
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont # type: ignore


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


# def configure_font_environment():
#     msys_fontconfig = Path(r"C:\msys64\mingw64\etc\fonts\fonts.conf")
#     if not msys_fontconfig.exists():
#         return

#     font_dirs = []
#     for candidate in (PROJECT_ROOT / "fonts", SCRIPT_DIR / "fonts"):
#         if candidate.exists():
#             font_dirs.append(candidate.resolve())

#     if not font_dirs:
#         return

#     runtime_dir = PROJECT_ROOT / ".fontconfig-runtime"
#     runtime_dir.mkdir(parents=True, exist_ok=True)
#     runtime_config = runtime_dir / "fonts.conf"

#     dir_entries = "\n".join(f'  <dir>{path.as_posix()}</dir>' for path in font_dirs)
#     runtime_config.write_text(
#         "\n".join(
#             [
#                 '<?xml version="1.0"?>',
#                 '<!DOCTYPE fontconfig SYSTEM "urn:fontconfig:fonts.dtd">',
#                 "<fontconfig>",
#                 f'  <include ignore_missing="no">{msys_fontconfig.as_posix()}</include>',
#                 dir_entries,
#                 "</fontconfig>",
#                 "",
#             ]
#         ),
#         encoding="utf-8",
#     )

#     os.environ["FONTCONFIG_FILE"] = str(runtime_config)


# def register_private_windows_fonts():
#     if os.name != "nt":
#         return

#     try:
#         add_font_resource = ctypes.windll.gdi32.AddFontResourceExW
#     except AttributeError:
#         return

#     add_font_resource.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
#     add_font_resource.restype = ctypes.c_int

#     font_paths = []
#     for font_dir in (PROJECT_ROOT / "fonts", SCRIPT_DIR / "fonts"):
#         if not font_dir.exists():
#             continue
#         font_paths.extend(sorted(font_dir.glob("*.ttf")))
#         font_paths.extend(sorted(font_dir.glob("*.otf")))

#     for font_path in font_paths:
#         add_font_resource(str(font_path.resolve()), 0x10, None)


# configure_font_environment()
# register_private_windows_fonts()


FONT_FAMILY_CACHE = {}
PANGO_FONT_FAMILY_CACHE = None

try:
    import gi # type: ignore

    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")

    from gi.repository import Pango, PangoCairo # type: ignore
    import cairo # type: ignore
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Missing runtime dependency: PyGObject/gi. "
        "Install the Pango + Cairo bindings for your Python environment before running this renderer."
    ) from exc

def load_json(path):
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_path(path_value, base_dir, search_existing=False):
    path = Path(path_value)
    if path.is_absolute():
        return path

    candidates = []

    if path.parts and path.parts[0] == base_dir.name:
        candidates.append((base_dir.parent / path).resolve())

    candidates.append((base_dir / path).resolve())

    project_candidate = (PROJECT_ROOT / path).resolve()
    if project_candidate not in candidates:
        candidates.append(project_candidate)

    if search_existing:
        for candidate in candidates:
            if candidate.exists():
                return candidate

    return candidates[0]


def parse_color(value):
    if isinstance(value, str):
        color = value.lstrip("#")
        if len(color) != 6:
            raise ValueError(f"Unsupported color value: {value}")
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))

    if isinstance(value, list) and len(value) == 3:
        return tuple(int(channel) for channel in value)

    raise ValueError(f"Unsupported color value: {value}")


def safe_eval(expression, variables):
    allowed_builtins = {"min": min, "max": max, "round": round, "int": int}
    return eval(str(expression), {"__builtins__": allowed_builtins}, variables)


def configure_layout(ctx, layer, text, font_family):
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
    description.set_size(int(layer["font_size"]) * Pango.SCALE)
    layout.set_font_description(description)

    line_spacing = layer.get("line_spacing")
    if line_spacing is not None:
        layout.set_spacing(int(line_spacing) * Pango.SCALE)

    return layout


def get_pango_font_families():
    global PANGO_FONT_FAMILY_CACHE

    if PANGO_FONT_FAMILY_CACHE is not None:
        return PANGO_FONT_FAMILY_CACHE

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    ctx = cairo.Context(surface)
    layout = PangoCairo.create_layout(ctx)
    families = layout.get_context().get_font_map().list_families()
    PANGO_FONT_FAMILY_CACHE = {family.get_name() for family in families}
    return PANGO_FONT_FAMILY_CACHE


def wrap_text_for_pillow(text, font, max_width):
    if not max_width:
        return [text]

    lines = []
    for paragraph in text.splitlines() or [""]:
        words = paragraph.split()
        if not words:
            lines.append("")
            continue

        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            if font.getbbox(candidate)[2] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        lines.append(current)

    return lines


def render_text_layer_with_pillow(text, layer, font_path):
    padding = int(layer.get("padding", 6))
    color = parse_color(layer.get("color", "#000000"))
    font = ImageFont.truetype(str(font_path), size=int(layer["font_size"]))
    max_width = layer.get("max_width")
    lines = wrap_text_for_pillow(text, font, max_width)

    line_boxes = [font.getbbox(line) if line else (0, 0, 0, 0) for line in lines]
    bbox = font.getbbox("Ag")
    default_height = bbox[3] - bbox[1]
    line_heights = [
        (line_box[3] - line_box[1]) if (line_box[3] - line_box[1]) > 0 else default_height
        for line_box in line_boxes
    ]
    line_spacing = int(layer.get("line_spacing", 0))
    line_widths = [(line_box[2] - line_box[0]) if line else 0 for line, line_box in zip(lines, line_boxes)]
    text_width = max(line_widths, default=0)
    text_height = sum(line_heights) + max(0, len(lines) - 1) * line_spacing

    width = max(1, text_width + padding * 2)
    height = max(1, text_height + padding * 2)

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    align = layer.get("align", "left").lower()
    y = padding
    for line, line_width, line_height, line_box in zip(lines, line_widths, line_heights, line_boxes):
        if align == "center":
            x = padding + (text_width - line_width) // 2
        elif align == "right":
            x = padding + (text_width - line_width)
        else:
            x = padding

        draw.text((x - line_box[0], y - line_box[1]), line, font=font, fill=(*color, 255))
        y += line_height + line_spacing

    return image


def render_text_layer(text, layer, font_family, font_path=None):
    if font_path and font_family not in get_pango_font_families():
        return render_text_layer_with_pillow(text, layer, font_path)

    padding = int(layer.get("padding", 6))
    color = parse_color(layer.get("color", "#000000"))

    measure_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    measure_ctx = cairo.Context(measure_surface)
    measure_layout = configure_layout(measure_ctx, layer, text, font_family)

    ink, logical = measure_layout.get_pixel_extents()
    left = min(logical.x, ink.x)
    top = min(logical.y, ink.y)
    right = max(logical.x + logical.width, ink.x + ink.width)
    bottom = max(logical.y + logical.height, ink.y + ink.height)
    width = max(1, right - left + padding * 2)
    height = max(1, bottom - top + padding * 2)

    draw_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    draw_ctx = cairo.Context(draw_surface)
    draw_layout = configure_layout(draw_ctx, layer, text, font_family)

    draw_ctx.set_source_rgba(color[0] / 255, color[1] / 255, color[2] / 255, 1)
    draw_ctx.move_to(padding - left, padding - top)
    PangoCairo.show_layout(draw_ctx, draw_layout)

    return Image.frombuffer(
        "RGBA",
        (width, height),
        draw_surface.get_data(),
        "raw",
        "BGRA",
        0,
        1,
    )


def font_family_from_file(path_value):
    resolved = Path(path_value).resolve()
    cache_key = str(resolved).lower()
    if cache_key in FONT_FAMILY_CACHE:
        return FONT_FAMILY_CACHE[cache_key]

    family = ImageFont.truetype(str(resolved), size=16).getname()[0]
    FONT_FAMILY_CACHE[cache_key] = family
    return family


def normalize_font_reference(font_value):
    if not isinstance(font_value, str):
        return font_value

    candidate = resolve_path(font_value, PROJECT_ROOT, search_existing=True)
    if candidate.exists() and candidate.suffix.lower() in {".ttf", ".otf", ".ttc"}:
        return font_family_from_file(candidate)

    return font_value


def resolve_font_spec(layer, assets):
    font_ref = layer.get("font")
    if not font_ref:
        raise ValueError(f"Layer is missing a font reference: {layer}")

    font_assets = assets.get("fonts", {})
    font_config = font_assets.get(font_ref)

    if font_config is None:
        normalized = normalize_font_reference(font_ref)
        resolved_path = resolve_path(font_ref, PROJECT_ROOT, search_existing=True)
        font_path = resolved_path if resolved_path.exists() and resolved_path.suffix.lower() in {".ttf", ".otf", ".ttc"} else None
        return normalized, font_path

    if isinstance(font_config, str):
        normalized = normalize_font_reference(font_config)
        resolved_path = resolve_path(font_config, PROJECT_ROOT, search_existing=True)
        font_path = resolved_path if resolved_path.exists() and resolved_path.suffix.lower() in {".ttf", ".otf", ".ttc"} else None
        return normalized, font_path

    family = font_config.get("family")
    file_path = font_config.get("file")

    if file_path:
        resolved_path = resolve_path(file_path, PROJECT_ROOT, search_existing=True)
        return font_family_from_file(resolved_path), resolved_path

    if not family:
        raise ValueError(f"Font asset '{font_ref}' must define a family or file")

    return family, None


def resolve_text(layer, data):
    if "value" in layer:
        text = str(layer["value"])
    else:
        text = str(data.get(layer.get("key", ""), ""))

    if layer.get("prefix"):
        text = f"{layer['prefix']}{text}"

    if layer.get("suffix"):
        text = f"{text}{layer['suffix']}"

    return text.strip() if layer.get("trim", False) else text


def should_skip_layer(layer, text, data):
    if layer.get("skip_if_key_empty") and not data.get(layer["skip_if_key_empty"]):
        return True

    if not text and layer.get("skip_if_empty", True):
        return True

    return False


def resolve_coordinate(raw_value, axis, image_size, layer_size):
    image_w, image_h = image_size
    layer_w, layer_h = layer_size

    if isinstance(raw_value, (int, float)):
        return int(raw_value)

    if raw_value == "center":
        if axis == "x":
            return (image_w - layer_w) // 2
        return (image_h - layer_h) // 2

    variables = {
        "image_w": image_w,
        "image_h": image_h,
        "layer_w": layer_w,
        "layer_h": layer_h,
        "w": image_w,
        "h": image_h,
        "text_w": layer_w,
        "text_h": layer_h,
    }
    return int(safe_eval(raw_value, variables))


def get_layer_coordinate(layer, axis):
    if axis in layer:
        return layer[axis]

    if axis == "x" and layer.get("align", "left").lower() == "center":
        return "center"

    return 0


def render_template(template, template_path, output_override=None):
    base_dir = Path(template_path).resolve().parent
    background_path = resolve_path(template["background"], base_dir, search_existing=True)
    output_path = (
        Path(output_override).resolve()
        if output_override
        else resolve_path(template.get("output", "output/gujarati_render.png"), base_dir)
    )

    image = Image.open(background_path).convert("RGBA")
    assets = template.get("assets", {})
    data = template.get("data", {})

    for layer in template.get("layers", []):
        if layer.get("type") != "text":
            continue

        text = resolve_text(layer, data)
        if should_skip_layer(layer, text, data):
            continue

        font_family, font_path = resolve_font_spec(layer, assets)
        layer_image = render_text_layer(text, layer, font_family, font_path)

        x = resolve_coordinate(get_layer_coordinate(layer, "x"), "x", image.size, layer_image.size)
        y = resolve_coordinate(get_layer_coordinate(layer, "y"), "y", image.size, layer_image.size)
        image.alpha_composite(layer_image, (x, y))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def main():
    parser = argparse.ArgumentParser(
        description="Render a Gujarati-friendly invitation image from a UTF-8 JSON template."
    )
    parser.add_argument("template", help="Path to the JSON template file")
    parser.add_argument("--output", help="Optional output image path")
    args = parser.parse_args()

    template_path = resolve_path(args.template, PROJECT_ROOT)
    template = load_json(template_path)
    output_path = render_template(template, template_path, args.output)
    print(f"Rendered invitation: {output_path}")


if __name__ == "__main__":
    main()
