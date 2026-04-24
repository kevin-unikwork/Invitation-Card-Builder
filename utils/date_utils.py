import re
from datetime import datetime as _datetime, timezone
from typing import Optional


def to_iso(dt: Optional[_datetime]) -> Optional[str]:
    """Return an ISO-8601 string from a datetime, treating naive values as UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def now_utc() -> _datetime:
    return _datetime.now(timezone.utc)


def _parse_date(value: str):
    """Parse a supported date string and return a datetime or None."""
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return _datetime.strptime(value.strip(), fmt)
        except ValueError:
            continue
    return None


def _coerce_month(month_value):
    """Convert a month name or number into a month integer."""
    if month_value in (None, ""):
        return None

    text = str(month_value).strip()
    if not text:
        return None

    if text.isdigit():
        month_number = int(text)
        return month_number if 1 <= month_number <= 12 else None

    for fmt in ("%B", "%b"):
        try:
            return _datetime.strptime(text, fmt).month
        except ValueError:
            continue

    return None


def _build_datetime_from_parts(day_value, month_value, year_value):
    """Build a datetime from separate day, month, and year values."""
    month_number = _coerce_month(month_value)
    if day_value in (None, "") or not month_number or year_value in (None, ""):
        return None

    try:
        return _datetime(
            int(str(year_value).strip()),
            month_number,
            int(str(day_value).strip()),
        )
    except ValueError:
        return None


def _date_component_keys(prefix: str):
    """Return the date-related field names for a key prefix."""
    if prefix:
        return {
            "date": f"{prefix}_date",
            "day": f"{prefix}_day",
            "month": f"{prefix}_month",
            "year": f"{prefix}_year",
        }

    return {"date": "date", "day": "day", "month": "month", "year": "year"}


def _populate_date_extras(extras: dict, data: dict, prefix: str, dt):
    """Fill derived date fields for a prefix without overriding input data."""
    keys = _date_component_keys(prefix)

    if keys["date"] not in data:
        extras[keys["date"]] = dt.strftime("%Y-%m-%d") if prefix else dt.strftime("%B %d, %Y")
    if keys["month"] not in data:
        extras[keys["month"]] = dt.strftime("%B")
    if keys["day"] not in data:
        extras[keys["day"]] = str(dt.day)
    if keys["year"] not in data:
        extras[keys["year"]] = str(dt.year)


def expand_event_date(data: dict) -> dict:
    """Normalize full and split date fields across all date key families."""
    extras = {}
    prefixes = set()

    if any(key in data for key in ("event_date", "event_day", "event_month", "event_year", "date", "day", "month", "year")):
        prefixes.add("event")

    for key in data:
        if key.endswith("_date"):
            prefixes.add(key[:-5])
        elif key.endswith("_day"):
            prefixes.add(key[:-4])
        elif key.endswith("_month"):
            prefixes.add(key[:-6])
        elif key.endswith("_year"):
            prefixes.add(key[:-5])

    for prefix in sorted(prefixes):
        keys = _date_component_keys(prefix)
        dt = None
        date_value = data.get(keys["date"])
        if date_value not in (None, ""):
            dt = _parse_date(str(date_value))

        if dt is None:
            dt = _build_datetime_from_parts(
                data.get(keys["day"]),
                data.get(keys["month"]),
                data.get(keys["year"]),
            )

        if dt is None and prefix == "event":
            dt = _build_datetime_from_parts(
                data.get("day"),
                data.get("month"),
                data.get("year"),
            )
            if dt is None:
                plain_date = data.get("date")
                if plain_date not in (None, ""):
                    dt = _parse_date(str(plain_date))

        if dt is None:
            continue

        _populate_date_extras(extras, data, prefix, dt)
        if prefix == "event":
            _populate_date_extras(extras, data, "", dt)

    return {**extras, **data}   # data values take precedence


def apply_date_format(value: str, pattern: str) -> str:
    """Format a date string with supported template date tokens."""
    dt = _parse_date(value)
    if dt is None:
        return value

    tokens = {
        "MMMM": dt.strftime("%B"),
        "MMM":  dt.strftime("%b"),
        "MM":   dt.strftime("%m"),
        "M":    str(dt.month),
        "dd":   dt.strftime("%d"),
        "d":    str(dt.day),
        "yyyy": dt.strftime("%Y"),
        "yy":   dt.strftime("%y"),
    }
    token_re = re.compile("|".join(re.escape(k) for k in tokens))
    return token_re.sub(lambda m: tokens[m.group(0)], pattern)
