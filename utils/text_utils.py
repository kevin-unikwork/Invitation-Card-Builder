from string import Formatter

from utils.date_utils import apply_date_format


class _SafeFormatDict(dict):
    """Return empty strings for missing format keys."""

    def __missing__(self, key):
        return ""


def resolve_text(layer, data):
    """Resolve and optionally format the text for a template layer."""
    if "value" in layer:
        text = str(layer["value"])
    else:
        text = str(data.get(layer.get("key", ""), ""))

    if "{" in text and "}" in text:
        safe_data = _SafeFormatDict(
            {
                key: "" if value is None else value
                for key, value in (data or {}).items()
            }
        )
        try:
            text = Formatter().vformat(text, (), safe_data)
        except (KeyError, ValueError):
            pass

    fmt = layer.get("format")
    if fmt and fmt.get("type") == "date" and text:
        text = apply_date_format(text, fmt.get("pattern", "MMMM dd, yyyy"))

    return text.strip() if layer.get("trim", False) else text


def should_skip_layer(layer, text, data):
    """Return True when a text layer should not be rendered."""
    if layer.get("hidden"):
        return True

    if layer.get("skip_if_key_empty") and not data.get(layer["skip_if_key_empty"]):
        return True

    if not text and layer.get("skip_if_empty", True):
        return True

    return False
