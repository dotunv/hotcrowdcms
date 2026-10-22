"""
Allowlist HTML sanitizer for rich-text content authored in the Store CMS.

The content editor is a contenteditable div, so the browser can submit arbitrary
markup. Everything is parsed and re-serialised here: unknown tags are dropped
(their text is kept), script/style bodies are removed, and only a small set of
attributes and URL schemes survive.
"""
import re
from html import escape
from html.parser import HTMLParser

ALLOWED_TAGS = {
    'p', 'br', 'hr', 'div', 'span', 'b', 'strong', 'i', 'em', 'u', 's', 'strike', 'sub', 'sup',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'blockquote', 'a', 'img', 'font',
}
VOID_TAGS = {'br', 'hr', 'img'}
DROP_CONTENT_TAGS = {'script', 'style', 'iframe', 'object', 'embed', 'noscript', 'template', 'svg', 'math'}

ALLOWED_ATTRS = {
    'a': {'href', 'title', 'target', 'rel'},
    'img': {'src', 'alt', 'width', 'height'},
    'font': {'color', 'size', 'face'},
}
GLOBAL_ATTRS = {'style', 'class', 'align'}

ALLOWED_CSS = {
    'color', 'background-color', 'font-size', 'font-weight', 'font-style', 'font-family',
    'text-align', 'text-decoration', 'line-height', 'letter-spacing', 'margin', 'padding',
    'margin-top', 'margin-bottom', 'margin-left', 'margin-right', 'text-transform',
}
SAFE_CSS_VALUE = re.compile(r'^[\w\s#%.,()\'"-]+$')
SAFE_URL = re.compile(r'^(https?://|mailto:|/|#)', re.I)
SAFE_CLASS = re.compile(r'^[\w\s-]*$')


def _clean_style(value):
    declarations = []
    for part in value.split(';'):
        name, sep, val = part.partition(':')
        name, val = name.strip().lower(), val.strip()
        if not sep or name not in ALLOWED_CSS:
            continue
        if not SAFE_CSS_VALUE.match(val) or 'url(' in val.lower() or 'expression' in val.lower():
            continue
        declarations.append(f'{name}: {val}')
    return '; '.join(declarations)


class _Sanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.open_tags = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in DROP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in ALLOWED_TAGS:
            return
        parts = []
        for name, value in attrs:
            name, value = (name or '').lower(), value or ''
            if name not in ALLOWED_ATTRS.get(tag, set()) | GLOBAL_ATTRS:
                continue
            if name in ('href', 'src'):
                if not SAFE_URL.match(value.strip()):
                    continue
            elif name == 'style':
                value = _clean_style(value)
                if not value:
                    continue
            elif name == 'class' and not SAFE_CLASS.match(value):
                continue
            elif name == 'target':
                value = '_blank'
            parts.append(f' {name}="{escape(value, quote=True)}"')
        if tag == 'a':
            parts.append(' rel="noopener noreferrer"')
        self.out.append(f'<{tag}{"".join(parts)}>')
        if tag not in VOID_TAGS:
            self.open_tags.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS and not self._skip_depth:
            self.handle_endtag(tag)
        elif tag in DROP_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)

    def handle_endtag(self, tag):
        if tag in DROP_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth or tag not in ALLOWED_TAGS or tag in VOID_TAGS:
            return
        if tag in self.open_tags:
            while self.open_tags:
                top = self.open_tags.pop()
                self.out.append(f'</{top}>')
                if top == tag:
                    break

    def handle_data(self, data):
        if not self._skip_depth:
            self.out.append(escape(data, quote=False))

    def close_all(self):
        while self.open_tags:
            self.out.append(f'</{self.open_tags.pop()}>')


def sanitize_html(value):
    """Return a safe version of `value`. Always returns a string."""
    if not value:
        return ''
    parser = _Sanitizer()
    parser.feed(str(value))
    parser.close()
    parser.close_all()
    return ''.join(parser.out)
