import math
import re
from html import escape

MAX_COORD = 20_000
SAFE_IMAGE_SRC = re.compile(r"^(https?://|/media/|stores/|media/)", re.I)


def _xml(value) -> str:
    return escape("" if value is None else str(value), quote=True)


def _num(value, default: float, minimum: float = -MAX_COORD, maximum: float = MAX_COORD) -> float:
    """A finite number clamped to a sane range; anything else (strings, NaN, inf, null) becomes `default`."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return max(minimum, min(maximum, number))


def layout_to_svg(data: dict, width: int = 1920, height: int = 1080) -> str:
    background = data.get("background") if isinstance(data, dict) else None
    color = (background.get("color") if isinstance(background, dict) else None) or "#111827"
    width, height = int(_num(width, 1920, 1, MAX_COORD)), int(_num(height, 1080, 1, MAX_COORD))
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{_xml(color)}"/>',
    ]
    elements = data.get("elements") if isinstance(data, dict) else None
    for element in elements if isinstance(elements, list) else []:
        if not isinstance(element, dict) or element.get("hidden"):
            continue
        kind = element.get("type") or "text"
        x = _num(element.get("x"), 0)
        y = _num(element.get("y"), 0)
        w = _num(element.get("width"), 200, 0)
        h = _num(element.get("height"), 80, 0)
        if kind == "rect":
            fill = element.get("fill") or "#057A43"
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{_xml(fill)}"/>')
        elif kind == "image":
            src = str(element.get("src") or "")
            if src and SAFE_IMAGE_SRC.match(src):
                parts.append(
                    f'<image href="{_xml(src)}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/>'
                )
        else:
            fill = element.get("color") or "#ffffff"
            size = _num(element.get("fontSize"), 48, 1, 1000)
            text = _xml(element.get("text") or "Text")
            parts.append(
                f'<text x="{x + 16}" y="{y + h / 2 + size / 3}" font-size="{size}" font-family="Plus Jakarta Sans, Inter, sans-serif" fill="{_xml(fill)}">{text}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)
