import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def resolve_path(path_value, base_dir, search_existing=False):
    """Resolve a relative or absolute asset path against known base paths."""
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


def load_json(path):
    """Load a JSON file from path and return its parsed object."""
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)
