from html import escape


def _xml(value: str) -> str:
    return escape(value or "", quote=True)


def layout_to_svg(data: dict, width: int = 1920, height: int = 1080) -> str:
    background = data.get("background") or {}
    color = background.get("color") or "#111827"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{int(width)}" height="{int(height)}" viewBox="0 0 {int(width)} {int(height)}">',
        f'<rect width="100%" height="100%" fill="{_xml(color)}"/>',
    ]
    for element in data.get("elements") or []:
        if element.get("hidden"):
            continue
        kind = element.get("type") or "text"
        x = float(element.get("x") or 0)
        y = float(element.get("y") or 0)
        w = float(element.get("width") or 200)
        h = float(element.get("height") or 80)
        if kind == "rect":
            fill = element.get("fill") or "#057A43"
            parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="{_xml(fill)}"/>')
        elif kind == "image" and element.get("src"):
            parts.append(
                f'<image href="{_xml(element["src"])}" x="{x}" y="{y}" width="{w}" height="{h}" preserveAspectRatio="xMidYMid slice"/>'
            )
        else:
            fill = element.get("color") or "#ffffff"
            size = int(element.get("fontSize") or 48)
            text = _xml(element.get("text") or "Text")
            parts.append(
                f'<text x="{x + 16}" y="{y + h / 2 + size / 3}" font-size="{size}" font-family="Plus Jakarta Sans, Inter, sans-serif" fill="{_xml(fill)}">{text}</text>'
            )
    parts.append("</svg>")
    return "\n".join(parts)
