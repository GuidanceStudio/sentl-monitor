"""The look of a report: Sentl's by default, replaced by a theme the user points at.

A theme is a small JSON file (`colors`, `font`, `font_url`, `logo`, `footer`) or a CSS file that overrides the
page's `--sl-*` variables. The page's structure uses variables only, so a theme changes colours, font, logo and
footer and nothing else. Nothing here reads the network: `font_url` is a link the user chose, written into the
page and fetched by whoever opens it.
"""

import base64
import json
import mimetypes
import os
import re
from pathlib import Path

from .common import Refused

# Values read on 2026-10-29: orange #FF850D and its deep shade #B85C00 (the text colour on white) from the
# --primary and --primary-deep variables of https://sentl.ai, text #2C2C31 from the dark background of that page,
# the mark from https://sentl.ai/brand/mark-sentl.webp (61 x 70; assets/sentl-mark.webp is the file as fetched,
# assets/sentl-mark.png is the same image as PNG, which every PDF engine reads), the font stack from the site's system sans
# with Inter, the face https://app.sentl.ai loads, used only where it is installed. Muted, line and tint are
# chosen for a white page.
COLORS = {
    "primary": "#FF850D",
    "deep": "#B85C00",
    "text": "#2C2C31",
    "muted": "#4B5563",
    "line": "#E2E5EB",
    "tint": "#FFF3E3",
}
FONT = "Inter, -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"
FOOTER = "Sentl.AI"
MARK_FILE = Path(__file__).resolve().parents[2] / "assets" / "sentl-mark.png"

SAFE = re.compile(r"^[#\w\s(),.%'\"-]+$")
NAMES = tuple(COLORS)
LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif",
              ".webp": "image/webp", ".svg": "image/svg+xml"}


def _mark():
    """Sentl's mark as a data URI, or None when the file was not installed."""
    try:
        return "data:image/png;base64," + base64.b64encode(MARK_FILE.read_bytes()).decode("ascii")
    except OSError:
        return None


def builtin():
    return {"colors": dict(COLORS), "font": FONT, "font_url": None, "logo": _mark(), "footer": FOOTER, "css": ""}


def _safe(value, what):
    if not isinstance(value, str) or not SAFE.match(value):
        raise Refused(f"theme: {what} {value!r} holds characters a colour or a font name does not")
    return value


def _logo(value, base):
    """The logo as a data URI, or None with the reason when it cannot be used."""
    if value.lstrip().startswith("<svg"):
        return "data:image/svg+xml;base64," + base64.b64encode(value.encode("utf-8")).decode("ascii"), None
    path = Path(value).expanduser()
    path = path if path.is_absolute() else base / path
    kind = LOGO_TYPES.get(path.suffix.lower())
    if not path.is_file() or not kind:
        why = "is not an image the page can hold (png, jpg, gif, webp, svg)" if path.is_file() else "was not found"
        return None, f"theme: the logo {value} {why}; the page carries Sentl's mark"
    return f"data:{kind};base64," + base64.b64encode(path.read_bytes()).decode("ascii"), None


def load(path):
    """A theme file read over the built-in one: (theme, notes). A note says what fell back."""
    path = Path(path).expanduser()
    if not path.is_file():
        raise Refused(f"theme file {path} not found")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Refused(f"theme file {path} cannot be read ({exc})") from None
    result, notes = builtin(), []
    if path.suffix.lower() == ".css":
        if "</style" in text.lower():
            raise Refused(f"theme file {path} closes the style element")
        result["css"] = text
        return result, notes
    if path.suffix.lower() != ".json":
        raise Refused(f"theme file {path} is neither .json nor .css")
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise Refused(f"theme file {path} is not valid JSON ({exc})") from None
    if not isinstance(data, dict):
        raise Refused(f"theme file {path}: the top level must be an object")
    for name, value in (data.get("colors") or {}).items():
        if name not in NAMES:
            raise Refused(f"theme file {path}: colour {name!r} is not one of {', '.join(NAMES)}")
        result["colors"][name] = _safe(value, f"colour {name}")
    if data.get("font"):
        result["font"] = _safe(data["font"], "font")
    if data.get("font_url"):
        if not re.fullmatch(r"https?://[^\s\"'<>]+", str(data["font_url"])):
            raise Refused(f"theme file {path}: font_url must be an http(s) address")
        result["font_url"] = str(data["font_url"])
    if data.get("footer") is not None:
        result["footer"] = str(data["footer"])
    if data.get("logo"):
        logo, note = _logo(str(data["logo"]), path.parent)
        if note:
            notes.append(note)
        else:
            result["logo"] = logo
    return result, notes


def resolve(folder, option=None):
    """The theme a report is written with: (theme, notes). First hit wins: the option, the `theme` key of
    study.json, theme.json or theme.css in the study folder, the user's folder, Sentl's."""
    if option:
        return load(option)
    study = folder.path("study.json")
    if study.exists():
        named = (json.loads(study.read_text(encoding="utf-8")) or {}).get("theme")
        if named:
            path = Path(named).expanduser()
            return load(path if path.is_absolute() else folder.path(named))
    for name in ("theme.json", "theme.css"):
        if folder.path(name).exists():
            return load(folder.path(name))
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "sentl-monitor"
    for name in ("theme.json", "theme.css"):
        if (config / name).exists():
            return load(config / name)
    return builtin(), []


def variables(theme):
    """The `:root` block the page's rules read."""
    rows = [f"  --sl-{name}: {value};" for name, value in theme["colors"].items()]
    rows += [f"  --sl-font: {theme['font']};", f"  --sl-mono: {MONO};"]
    return ":root {\n" + "\n".join(rows) + "\n}\n"
