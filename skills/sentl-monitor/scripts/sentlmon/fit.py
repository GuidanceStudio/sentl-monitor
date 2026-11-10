"""How tall a slide of the deck prints, estimated from its HTML and the deck's style sheet, before any PDF.

The estimate lays the slide out as the browser does, with the sizes, gaps, paddings and widths the style sheet gives:
blocks stack, flex rows and grid rows take the height of their tallest item, table rows that of their tallest cell, and
text wraps word by word at the width of its box. A character takes its width in Arial, whose metrics Liberation Sans
and Helvetica share: the face the deck's font stack falls to where Inter, SF and Segoe UI are missing, and narrower than
those. A wider face can run over where the estimate fits, so `pdf --deck` keeps the page count as the final word.
"""

import re
import unicodedata
from html.parser import HTMLParser

# The deck's @page is 13.333in x 7.5in at 96 px an inch: a slide taller than 720 px prints on two pages.
PAGE_WIDTH, PAGE_HEIGHT = 1280, 720


def _widths(groups):
    return {ch: units for units, chars in groups.items() for ch in chars}


# Advance widths in thousandths of an em (Arial, Helvetica, Liberation Sans).
REGULAR = _widths({191: "'", 222: "ijl’‘", 260: "|", 278: "  ftI!,./:;[]\\·", 333: "r()-`{}“”", 355: '"', 389: "*",
                   469: "^", 500: "cksvxyzJ", 556: "abdeghnopqu0123456789L_$?#€«»–", 584: "+<=>~×", 611: "FTZ",
                   667: "ABEKPSVXY&", 722: "CDHNRUw", 778: "GOQ", 833: "mM", 889: "%", 944: "W", 1000: "—…@"})
BOLD = _widths({238: "'", 278: "  ijl,./\\I·’‘", 333: "!ft():;[]-", 389: "r*", 474: '"', 500: "z“”",
                556: "acesvxykJ0123456789#$_«»–€", 584: "+<=>^~×", 611: "bdghnopquFLTZ?", 667: "EPSVXY",
                722: "ABCDHKNRU&", 778: "wGOQ", 833: "M", 889: "m%", 944: "W", 975: "@", 1000: "—…"})
VOID = {"br", "img", "link", "meta", "hr"}
INLINE = {"span", "b", "strong", "i", "em", "small", "a", "img", "br"}
# The browser's own style for the elements the deck uses, under every rule of the deck's sheet.
AGENT = """p { margin: 1em 0; } ul { margin: 1em 0; padding-left: 40px; } figure, blockquote { margin: 1em 40px; }
h1, h2, b, strong, th { font-weight: 700; } td, th { padding: 1px; }"""


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.parent, self.kids, self.style = tag, parent, [], None
        self.classes = set((dict(attrs).get("class") or "").split())
        if parent:
            parent.kids.append(self)

    def elements(self):
        return [k for k in self.kids if isinstance(k, Node)]


class _Tree(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = self.at = Node("body", [], None)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.at)
        if tag not in VOID:
            self.at = node

    def handle_endtag(self, tag):
        up = self.at
        while up.parent and up.tag != tag:
            up = up.parent
        if up.parent:
            self.at = up.parent

    def handle_data(self, data):
        self.at.kids.append(data)


# --- the style sheet --------------------------------------------------------

SIMPLE = re.compile(r"([a-z][a-z0-9]*)?((?:\.[\w-]+)*)((?::[\w-]+(?:\(\d+\))?)*)$")


def rules(css):
    """(specificity, order, parts, declarations) of each selector of `css`, the browser's own rules first and lowest."""
    out = []
    for order, (selectors, body) in enumerate(re.findall(r"([^{}]+)\{([^{}]*)\}", re.sub(r"/\*.*?\*/", "", AGENT + css, flags=re.S))):
        props = {k.strip(): v.strip() for k, v in (d.split(":", 1) for d in body.split(";") if ":" in d)}
        for selector in (s.strip() for s in selectors.split(",")):
            parts = re.findall(r">|[^\s>]+", selector)
            if not parts or not all(p == ">" or SIMPLE.match(p) for p in parts):
                continue  # @page, :root and other selectors the slides do not need
            weight = (sum(p.count(".") + p.count(":") for p in parts), sum(p[0].isalpha() for p in parts if p != ">"))
            out.append(((order >= AGENT.count("}"),) + weight, order, parts, props))
    return sorted(out, key=lambda r: (r[0], r[1]))


def _simple(part, node):
    tag, classes, pseudos = SIMPLE.match(part).groups()
    if (tag and tag != node.tag) or not set(classes.split(".")[1:]) <= node.classes:
        return False
    siblings = node.parent.elements() if node.parent else [node]
    for name, n in re.findall(r":([\w-]+)(?:\((\d+)\))?", pseudos):
        held = {"nth-child": lambda: siblings.index(node) + 1 == int(n or 0), "first-child": lambda: siblings[0] is node,
                "last-child": lambda: siblings[-1] is node, "only-child": lambda: len(siblings) == 1,
                "last-of-type": lambda: [s for s in siblings if s.tag == node.tag][-1] is node}.get(name)
        if not held or not held():
            return False
    return True


def _matches(parts, node):
    if node is None or not _simple(parts[-1], node):
        return False
    rest = parts[:-1]
    if not rest:
        return True
    if rest[-1] == ">":
        return _matches(rest[:-1], node.parent)
    up = node.parent
    while up:
        if _matches(rest, up):
            return True
        up = up.parent
    return False


class Style:
    """What the estimate reads of a node's computed style."""

    def __init__(self, props, size, height, bold):
        self.props, self.size, self.line, self.bold = props, size, height, bold

    def length(self, name, of=0.0):
        return _length(self.props.get(name), self.size, of)

    def sides(self, name):
        """(top, right, bottom, left) of margin or padding, shorthand and longhands."""
        values = (self.props.get(name) or "0").split()
        values = (values * 4)[:4] if len(values) == 1 else values + values[1:2] if len(values) == 3 else (values * 2)[:4]
        sides = [_length(v, self.size) for v in values]
        for i, side in enumerate(("top", "right", "bottom", "left")):
            if f"{name}-{side}" in self.props:
                sides[i] = _length(self.props[f"{name}-{side}"], self.size)
        return sides

    def border(self, side):
        value = self.props.get(f"border-{side}") or ""
        found = re.match(r"([\d.]+)px", value)
        return float(found.group(1)) if found else 0.0

    @property
    def display(self):
        return self.props.get("display") or ""


def _length(value, size, of=0.0):
    if not value:
        return 0.0
    found = re.match(r"(-?[\d.]+)(px|em|%)?$", value.strip())
    if not found:
        return 0.0
    number, unit = float(found.group(1)), found.group(2)
    return number * size if unit == "em" else number * of / 100 if unit == "%" else number


# A shorthand resets the longhands an earlier rule set: `padding: 0` after the agent's `padding-left: 40px`.
LONGHANDS = {**{box: tuple(f"{box}-{side}" for side in ("top", "right", "bottom", "left")) for box in ("margin", "padding")},
             "gap": ("row-gap", "column-gap"), "flex": ("flex-grow", "flex-shrink", "flex-basis"),
             "font": ("font-size", "line-height", "font-weight")}


def _style(node, sheet):
    if node.style:
        return node.style
    props = {}
    for _, _, parts, declared in sheet:
        if _matches(parts, node):
            for name, value in declared.items():
                for longhand in LONGHANDS.get(name, ()):
                    props.pop(longhand, None)
                props[name] = value
    parent = _style(node.parent, sheet) if node.parent else Style({}, 16.0, 1.2, False)
    if "white-space" in parent.props:
        props.setdefault("white-space", parent.props["white-space"])
    size, line, bold = parent.size, parent.line, parent.bold
    font = re.match(r"(?:(\d+)\s+)?([\d.]+)px(?:/([\d.]+))?", props.get("font", ""))
    if font:
        size, line, bold = float(font.group(2)), float(font.group(3) or line), int(font.group(1) or 400) >= 600
    if "font-size" in props:
        size = _length(props["font-size"], parent.size)
    if "line-height" in props:
        value = props["line-height"]
        line = _length(value, size) / size if value.endswith("px") else float(value)
    if "font-weight" in props:
        bold = props["font-weight"] in ("bold", "bolder") or props["font-weight"].isdigit() and int(props["font-weight"]) >= 600
    node.style = Style(props, size, line, bold)
    return node.style


# --- the layout -------------------------------------------------------------

class Layout:
    def __init__(self, css):
        self.sheet = rules(css)

    def style(self, node):
        return _style(node, self.sheet)

    def inline(self, node):
        style = self.style(node)
        return (node.tag in INLINE and style.display != "block") or style.display in ("inline", "inline-block")

    def outer(self, node, width):
        """The height a block takes in its parent, its vertical margins included."""
        top, right, bottom, left = self.style(node).sides("margin")
        return top + bottom + self.box(node, width - right - left)

    def box(self, node, width):
        """The height of a node's border box at `width`."""
        s = self.style(node)
        if "height" in s.props:
            return s.length("height")
        top, right, bottom, left = s.sides("padding")
        inner = width - right - left - s.border("left") - s.border("right")
        if "max-width" in s.props:
            inner = min(inner, s.length("max-width", width))
        return top + bottom + s.border("top") + s.border("bottom") + self.content(node, inner)

    def content(self, node, width):
        s = self.style(node)
        kids = node.elements()
        if s.display == "flex" and kids:
            if s.props.get("flex-direction") == "column":
                return self.column(kids, width, s.length("row-gap") or self.gaps(s)[0])
            return self.row(kids, width, self.gaps(s)[1], "wrap" in s.props.get("flex-wrap", ""))
        if s.display == "grid":
            return self.grid(node, kids, width)
        if node.tag == "table":
            return self.table(node, width)
        if s.props.get("columns") and kids:
            return self.columns(kids, width, int(s.props["columns"]), s.length("column-gap"))
        return self.flow(node, width)

    def gaps(self, s):
        """(row gap, column gap)."""
        values = [_length(v, s.size) for v in (s.props.get("gap") or "0").split()]
        row, column = values[0], values[-1]
        return s.length("row-gap") if "row-gap" in s.props else row, s.length("column-gap") if "column-gap" in s.props else column

    def flow(self, node, width):
        """Blocks stacked, adjacent margins collapsed; a run of text and inline elements is one block of lines."""
        total, below, run = 0.0, 0.0, []
        for kid in node.kids + [None]:
            if kid is not None and (not isinstance(kid, Node) or self.inline(kid)):
                run.append(kid)
                continue
            if run and "".join(_text(k) for k in run).strip():
                total += max(below, 0) + self.lines(node, run, width) * self.style(node).size * self.style(node).line
                below = 0.0
            run = []
            if kid is None:
                break
            top, right, bottom, left = self.style(kid).sides("margin")
            total += max(below, top) + self.box(kid, width - right - left)
            below = bottom
        return total + max(below, 0)

    def lines(self, node, run, width):
        """The lines a run of inline content takes at `width`, words wrapped as the browser wraps them."""
        count, x, space, start = 1, 0.0, 0.0, True
        for kind, w in self.tokens(run, node):
            if kind == "break":
                count, x, space, start = count + 1, 0.0, 0.0, True
            elif kind == "space":
                space = 0.0 if start else w
            else:
                if not start and x + space + w > width:
                    count, x = count + 1, w
                else:
                    x += space + w
                space, start = 0.0, False
        return count

    def tokens(self, run, parent):
        """("word", width), ("space", width) and ("break", 0) of a run of inline content, in reading order."""
        word = 0.0
        for kind, w in self.atoms(run, parent):
            if kind == "ink":
                word += w
                continue
            if word:
                yield "word", word
                word = 0.0
            yield kind, w
        if word:
            yield "word", word

    def atoms(self, run, parent):
        """("ink", width) of each character, ("space", width) where a line may break, ("break", 0) at a <br>."""
        s = self.style(parent)
        nowrap = s.props.get("white-space") == "nowrap"
        for kid in run:
            if isinstance(kid, str):
                table = BOLD if s.bold else REGULAR
                for ch in kid:
                    space = ch in " \t\r\n"
                    yield ("space" if space and not nowrap else "ink", _advance(" " if space else ch, table) * s.size / 1000)
            elif kid.tag == "br":
                yield "break", 0.0
            elif self.style(kid).display == "inline-block" and "width" in self.style(kid).props:
                yield "ink", self.style(kid).length("width") + self.style(kid).sides("margin")[1]
            else:
                yield from self.atoms(kid.kids, kid)

    def column(self, kids, width, gap):
        return sum(self.outer(k, width) for k in kids) + gap * (len(kids) - 1)

    def row(self, kids, width, gap, wrap):
        grows = [self.grow(k) for k in kids]
        fixed = [self.style(k).length("width", width) if "width" in self.style(k).props else None if g else self.widest(k)
                 for k, g in zip(kids, grows)]
        free = width - gap * (len(kids) - 1) - sum(f for f in fixed if f is not None)
        if any(grows):
            widths = [f if f is not None else max(free, 0) * g / sum(grows) for f, g in zip(fixed, grows)]
        elif sum(fixed) + gap * (len(kids) - 1) > width and wrap:
            return self.wrapped(kids, fixed, width, gap)
        else:
            scale = min(1.0, (width - gap * (len(kids) - 1)) / sum(fixed)) if sum(fixed) else 1.0
            widths = [f * scale for f in fixed]
        return max(self.outer(k, w) for k, w in zip(kids, widths))

    def wrapped(self, kids, widths, width, gap):
        heights, line, used = [], [], 0.0
        for kid, w in zip(kids, widths):
            if line and used + gap + w > width:
                heights.append(max(line))
                line, used = [], 0.0
            line.append(self.outer(kid, w))
            used += (gap if used else 0) + w
        heights.append(max(line))
        return sum(heights) + gap * (len(heights) - 1)

    def grow(self, node):
        props = self.style(node).props
        value = props.get("flex-grow") or (props.get("flex") or "0").split()[0]
        try:
            return float(value)
        except ValueError:
            return 0.0

    def widest(self, node):
        """The width a node takes with no line wrapped: its max-content width."""
        s = self.style(node)
        if "width" in s.props:
            return s.length("width")
        pad = sum(s.sides("padding")[1::2]) + s.border("left") + s.border("right")
        kids = node.elements()
        if kids and not all(self.inline(k) for k in kids):
            return pad + max(self.widest(k) + sum(self.style(k).sides("margin")[1::2]) for k in kids)
        most, x, space = 0.0, 0.0, 0.0
        for kind, w in self.tokens(node.kids, node):
            if kind == "break":
                most, x, space = max(most, x), 0.0, 0.0
            elif kind == "space":
                space = w if x else 0.0
            else:
                x, space = x + space + w, 0.0
        return pad + max(most, x)

    def narrowest(self, node):
        """The width of its longest word: its min-content width."""
        s = self.style(node)
        words = [w for kind, w in self.tokens(node.kids, node) if kind == "word"]
        return sum(s.sides("padding")[1::2]) + max(words, default=0.0)

    def grid(self, node, kids, width):
        s = self.style(node)
        template = (s.props.get("grid-template-columns") or "1fr").split()
        row_gap, column_gap = self.gaps(s)
        rows, row = [], []
        for kid in kids:
            if "grid-column" in self.style(kid).props:
                rows += [row] * bool(row) + [[kid]]
                row = []
                continue
            row.append(kid)
            if len(row) == len(template):
                rows.append(row)
                row = []
        rows += [row] * bool(row)
        widths = []
        for i, track in enumerate(template):
            if track.endswith("px"):
                widths.append(float(track[:-2]))
            elif track == "auto":
                widths.append(max((self.widest(r[i]) for r in rows if len(r) == len(template)), default=0.0))
            else:
                widths.append(None)
        fr = [float(t[:-2]) if t.endswith("fr") else 0.0 for t in template]
        free = width - column_gap * (len(template) - 1) - sum(w for w in widths if w is not None)
        widths = [w if w is not None else max(free, 0) * f / (sum(fr) or 1) for w, f in zip(widths, fr)]
        heights = [max(self.outer(k, width if len(r) == 1 and len(template) > 1 else w) for k, w in zip(r, widths)) for r in rows]
        return sum(heights) + row_gap * (len(heights) - 1)

    def table(self, node, width):
        rows = [r for r in _descendants(node) if r.tag == "tr"]
        cells = [[c for c in r.elements() if c.tag in ("td", "th")] for r in rows]
        n = max((len(r) for r in cells), default=0)
        if not n:
            return 0.0
        if self.style(node).props.get("table-layout") == "fixed":
            set_widths = [self.style(c).length("width", width) if "width" in self.style(c).props else None for c in cells[0]]
            set_widths += [None] * (n - len(set_widths))
            left = width - sum(w for w in set_widths if w is not None)
            share = left / max(1, sum(w is None for w in set_widths))
            widths = [w if w is not None else share for w in set_widths]
        else:
            widths = _auto_columns([[self.narrowest(c) for c in r] for r in cells],
                                   [[self.widest(c) for c in r] for r in cells], n, width)
        return sum(max(self.box(c, w) for c, w in zip(r, widths)) for r in cells if r)

    def columns(self, kids, width, count, gap):
        """Items flowed into `count` balanced columns, none split; the margin under a column's last item is cut."""
        each = (width - gap * (count - 1)) / count
        heights = [self.outer(k, each) for k in kids]
        cut = [self.style(k).sides("margin")[2] for k in kids]
        targets = {sum(heights[i:j]) - cut[j - 1] for i in range(len(kids)) for j in range(i + 1, len(kids) + 1)}
        for target in sorted(targets):
            used, column = 0.0, 1
            for h, c in zip(heights, cut):
                if used and used + h - c > target + 0.01:
                    column, used = column + 1, 0.0
                used += h
            if column <= count:
                return target
        return sum(heights)


def _auto_columns(narrow, wide, n, width):
    """The browser's automatic table layout: each column its min-content width, then the room left shared by max-content."""
    least = [max((r[i] for r in narrow if i < len(r)), default=0.0) for i in range(n)]
    most = [max((r[i] for r in wide if i < len(r)), default=0.0) for i in range(n)]
    if sum(most) <= width:
        return [m + (width - sum(most)) * m / (sum(most) or 1) for m in most]
    room = max(width - sum(least), 0)
    spread = sum(m - l for m, l in zip(most, least)) or 1
    return [l + room * (m - l) / spread for m, l in zip(most, least)]


def _descendants(node):
    for kid in node.elements():
        yield kid
        yield from _descendants(kid)


def _text(kid):
    return kid if isinstance(kid, str) else "".join(_text(k) for k in kid.kids)


def _advance(ch, table):
    units = table.get(ch)
    if units is None:
        units = table.get(unicodedata.normalize("NFD", ch)[:1], 556)
    return units


def heights(page, css):
    """The height each <section> of `page` takes when nothing stretches it, in CSS px."""
    tree = _Tree()
    tree.feed(page)
    layout = Layout(css)
    return [layout.box(s, PAGE_WIDTH) for s in tree.root.elements() if s.tag == "section"]
