"""How tall a slide of the deck prints, estimated from its HTML and the deck's style sheet, before any PDF.

The estimate lays the slide out as the browser does, with the sizes, gaps, paddings and widths the style sheet gives:
blocks stack, flex rows and grid rows take the height of their tallest item, table rows that of their tallest cell, and
text wraps word by word at the width of its box. A character takes its width in Arial, whose metrics Liberation Sans
and Helvetica share: the face the deck's font stack falls to where Inter, SF and Segoe UI are missing, and narrower than
those. A wider face can run over where the estimate fits, so `pdf` keeps the page count as the final word.
"""

import math
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
    """What the estimate reads of a node's computed style. `line` is the line-height a child inherits: ("ratio", 1.4),
    ("px", 30.0) for a length or a percentage, which inherit as computed, or ("normal", 0)."""

    def __init__(self, props, size, line, bold):
        self.props, self.size, self.line, self.bold = props, size, line, bold

    @property
    def leading(self):
        """The height of one line of text, in px."""
        kind, value = self.line
        return value if kind == "px" else value * self.size if kind == "ratio" else _normal(self.size)

    def length(self, name, of=0.0):
        return _length(self.props.get(name), self.size, of)

    def sides(self, name):
        """(top, right, bottom, left) of margin or padding, shorthand and longhands."""
        values = (self.props.get(name) or "0").split() or ["0"]
        values = (values * 4)[:4] if len(values) == 1 else values + values[1:2] if len(values) == 3 else (values * 2)[:4]
        sides = [_length(v, self.size) for v in values]
        for i, side in enumerate(("top", "right", "bottom", "left")):
            if f"{name}-{side}" in self.props:
                sides[i] = _length(self.props[f"{name}-{side}"], self.size)
        return sides

    def border(self, side):
        value = self.props.get(f"border-{side}") or self.props.get("border") or ""
        found = re.match(r"(\d*\.?\d+)px", value)
        return float(found.group(1)) if found else 0.0

    def across(self):
        """Padding and border left and right."""
        return sum(self.sides("padding")[1::2]) + self.border("left") + self.border("right")

    @property
    def display(self):
        return self.props.get("display") or ""


# px in each absolute unit; `rem` is the html element's size, which the deck leaves at the browser's 16 px.
UNITS = {"px": 1.0, "pt": 96 / 72, "pc": 16.0, "in": 96.0, "cm": 96 / 2.54, "mm": 96 / 25.4}
ROOT_SIZE = 16.0
SIZES = {"xx-small": 9.0, "x-small": 10.0, "small": 13.0, "medium": 16.0, "large": 18.0, "x-large": 24.0, "xx-large": 32.0}
# Liberation Sans, as Arial: ascent, descent and line gap in em, each rounded to whole px for `line-height: normal`.
NORMAL = (1854 / 2048, 434 / 2048, 67 / 2048)


def _measure(value, size, of=0.0):
    """A length in px, or None for what the estimate does not read: var(), calc(), auto, a keyword."""
    found = re.fullmatch(r"(-?\d*\.?\d+)([a-z%]*)", (value or "").strip().lower())
    if not found:
        return None
    number, unit = float(found.group(1)), found.group(2)
    factor = UNITS.get(unit or "px") or {"em": size, "rem": ROOT_SIZE, "%": of / 100, "vw": PAGE_WIDTH / 100,
                                          "vh": PAGE_HEIGHT / 100}.get(unit)
    return None if factor is None else number * factor


def _length(value, size, of=0.0):
    measured = _measure(value, size, of)
    return 0.0 if measured is None else measured


def _normal(size):
    return float(sum(math.floor(part * size + 0.5) for part in NORMAL))


def _font_size(value, parent):
    value = value.strip().lower()
    if value in SIZES:
        return SIZES[value]
    if value in ("larger", "smaller"):
        return parent * 1.2 if value == "larger" else parent / 1.2
    measured = _length(value, parent, parent)
    return measured if measured > 0 else parent


def _line(value, size):
    """The line-height `value` sets at font size `size`, or None when the estimate does not read it."""
    value = value.strip().lower()
    if value == "normal":
        return "normal", 0.0
    if re.fullmatch(r"\d*\.?\d+", value):
        return "ratio", float(value)
    measured = _measure(value, size, size)
    return None if measured is None else ("px", measured)


FONT = re.compile(r"(?:^|\s)(\d*\.?\d+[a-z%]+|xx?-small|xx?-large|small|medium|large|larger|smaller)(?:\s*/\s*([^\s/]+))?(?=\s|$)")


def _font(value, parent_size):
    """(size, line, bold) of the `font` shorthand, which sets line-height to normal and the weight to 400 unless it
    names them, or None."""
    found = FONT.search(value.lower())
    if not found:
        return None
    size = _font_size(found.group(1), parent_size)
    line = (_line(found.group(2), size) if found.group(2) else None) or ("normal", 0.0)
    return size, line, _bold(value[:found.start(1)])


def _bold(weight):
    return any(w in ("bold", "bolder") or w.isdigit() and int(w) >= 600 for w in weight.lower().split())


# A shorthand resets the longhands an earlier rule set: `padding: 0` after the agent's `padding-left: 40px`.
LONGHANDS = {**{box: tuple(f"{box}-{side}" for side in ("top", "right", "bottom", "left")) for box in ("margin", "padding")},
             "border": tuple(f"border-{side}" for side in ("top", "right", "bottom", "left")),
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
    parent = _style(node.parent, sheet) if node.parent else Style({}, 16.0, ("normal", 0.0), False)
    if "white-space" in parent.props:
        props.setdefault("white-space", parent.props["white-space"])
    size, line, bold = parent.size, parent.line, parent.bold
    font = _font(props["font"], parent.size) if "font" in props else None
    if font:
        size, line, bold = font
    if "font-size" in props:
        size = _font_size(props["font-size"], parent.size)
    if "line-height" in props:
        line = _line(props["line-height"], size) or line
    if "font-weight" in props:
        bold = _bold(props["font-weight"])
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
                total += max(below, 0) + self.lines(node, run, width) * self.style(node).leading
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
        """("word", width), ("space", width) and ("break", 0) of a run of inline content, in reading order. A word also
        ends where the browser may break between two characters, after a hyphen or a dash, and on both sides of an
        inline block: there a space of no width stands between."""
        word, before, last = 0.0, " ", (" ", "space")
        for kind, w, ch in self.atoms(run, parent):
            if kind == "box":
                yield from (("word", word), ("space", 0.0)) if word else ()
                yield from (("word", w), ("space", 0.0))
                word = 0.0
            elif kind in ("ink", "glue"):
                if word and kind == last[1] == "ink" and _breaks(before, last[0], ch):
                    yield "word", word
                    yield "space", 0.0
                    word = 0.0
                word += w
            else:
                if word:
                    yield "word", word
                    word = 0.0
                yield kind, w
            before, last = last[0], (ch, kind)
        if word:
            yield "word", word

    def atoms(self, run, parent):
        """(kind, width, character) in reading order: "ink" for a character, "glue" for one where no line may break,
        "space" where one may, "break" at a <br>, "box" for an inline block."""
        s = self.style(parent)
        nowrap = s.props.get("white-space") == "nowrap"
        for kid in run:
            if isinstance(kid, str):
                table = BOLD if s.bold else REGULAR
                for ch in kid:
                    space = ch in " \t\r\n"
                    kind = "glue" if nowrap else "space" if space else "ink"
                    yield kind, _advance(" " if space else ch, table) * s.size / 1000, " " if space else ch
            elif kid.tag == "br":
                yield "break", 0.0, "\n"
            elif self.style(kid).display == "inline-block" and "width" in self.style(kid).props:
                width = self.style(kid).length("width") + self.style(kid).sides("margin")[1]
                yield "glue" if nowrap else "box", width, "\ufffc"
            else:
                yield from self.atoms(kid.kids, kid)

    def column(self, kids, width, gap):
        return sum(self.outer(k, width) for k in kids) + gap * (len(kids) - 1)

    def row(self, kids, width, gap, wrap):
        """Items side by side, each from its flex basis with its padding and margins, the growing ones sharing the room
        left; as tall as the tallest."""
        gaps = gap * (len(kids) - 1)
        grows = [self.grow(k) for k in kids]
        bases = [self.basis(k, width) for k in kids]
        if any(grows):
            free = max(width - gaps - sum(bases), 0.0)
            widths = [b + free * g / sum(grows) for b, g in zip(bases, grows)]
        elif sum(bases) + gaps > width and wrap:
            return self.wrapped(kids, bases, width, gap)
        else:
            scale = min(1.0, (width - gaps) / sum(bases)) if sum(bases) else 1.0
            widths = [b * scale for b in bases]
        return max(self.outer(k, w) for k, w in zip(kids, widths))

    def basis(self, node, width):
        """The width an item takes in its row before the room left is shared, its margins included."""
        s = self.style(node)
        basis = _flex(s.props)[1]
        if basis == "auto":
            taken = self.border_box(s, s.length("width", width)) if "width" in s.props else self.widest(node)
        else:
            taken = self.border_box(s, _length(basis, s.size, width))
        return taken + sum(s.sides("margin")[1::2])

    def border_box(self, s, width):
        """The width of the border box whose `width` is `width`; the padding and border are never squeezed out."""
        if s.props.get("box-sizing") == "border-box":
            return max(width, s.across())
        return width + s.across()

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
        return _flex(self.style(node).props)[0]

    def widest(self, node):
        """The width a node takes with no line wrapped: its max-content width."""
        s = self.style(node)
        if "width" in s.props:
            return self.border_box(s, s.length("width"))
        pad = s.across()
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
        return s.across() + max(words, default=0.0)

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
            set_widths = [self.border_box(self.style(c), self.style(c).length("width", width)) if "width" in self.style(c).props
                          else None for c in cells[0]]
            set_widths += [None] * (n - len(set_widths))
            left = width - sum(w for w in set_widths if w is not None)
            share = left / max(1, sum(w is None for w in set_widths))
            widths = [w if w is not None else share for w in set_widths]
        else:
            widths = _auto_columns([[self.narrowest(c) for c in r] for r in cells],
                                   [[self.widest(c) for c in r] for r in cells], n, width)
        return sum(max(self.box(c, w) for c, w in zip(r, widths)) for r in cells if r)

    def columns(self, kids, width, count, gap):
        """Items flowed into `count` columns, none split, balanced as the browser balances them: it starts from an even
        share of the whole height and grows the columns until they hold every item, the margin under a column's last
        item cut."""
        each = (width - gap * (count - 1)) / count
        heights = [self.outer(k, each) for k in kids]
        cut = [self.style(k).sides("margin")[2] for k in kids]
        even = sum(heights) / count

        def holds(target):
            used, column = 0.0, 1
            for h, c in zip(heights, cut):
                if h - c > target + 0.01:
                    return False
                if used and used + h - c > target + 0.01:
                    column, used = column + 1, 0.0
                used += h
            return column <= count

        targets = {even} | {sum(heights[i:j]) - cut[j - 1] for i in range(len(kids)) for j in range(i + 1, len(kids) + 1)}
        return next((t for t in sorted(targets) if t >= even and holds(t)), sum(heights))


def _auto_columns(narrow, wide, n, width):
    """The browser's automatic table layout: each column its min-content width, then the room left shared by max-content."""
    least = [max((r[i] for r in narrow if i < len(r)), default=0.0) for i in range(n)]
    most = [max((r[i] for r in wide if i < len(r)), default=0.0) for i in range(n)]
    if sum(most) <= width:
        return [m + (width - sum(most)) * m / (sum(most) or 1) for m in most]
    room = max(width - sum(least), 0)
    spread = sum(m - l for m, l in zip(most, least)) or 1
    return [l + room * (m - l) / spread for m, l in zip(most, least)]


def _flex(props):
    """(grow, basis) of a flex item: `flex: 1` grows from a basis of 0, `flex: auto` from its own width."""
    parts = (props.get("flex") or "").split()
    numbers = [float(p) for p in parts if re.fullmatch(r"\d*\.?\d+", p)]
    if parts in (["auto"], ["none"]):
        grow, basis = float(parts == ["auto"]), "auto"
    else:
        lengths = [p for p in parts if not re.fullmatch(r"\d*\.?\d+", p)]
        grow, basis = (numbers[0] if numbers else 1.0 if lengths else 0.0), (lengths[0] if lengths else "0" if numbers else "auto")
    if "flex-grow" in props:
        grow = _length(props["flex-grow"], 0.0)
    return grow, props.get("flex-basis", basis)


# Characters after which a line may break before "(", as Chrome breaks them.
BEFORE_OPENING = set(".,:;)]}%+=\"&#€|\\*~>!-–…?")


def _breaks(before, last, ch):
    """Whether the browser may end a line between `last` and `ch`, two characters with no space between them: the
    rules of UAX #14 as Chrome applies them to the characters a deck holds. `before` is the character before `last`."""
    if "—" in (last, ch):
        return True
    if ch == "(":
        return last in BEFORE_OPENING
    if last == ch == "-":
        return True
    if not ch.isalnum():
        return False
    if last == "-":  # a minus sign keeps its number
        return not (ch.isdigit() and before in " \n(")
    if last == "–":  # a dash after a space keeps its word
        return not (ch.isalpha() and before in " \n")
    if last in ("…", "?"):
        return True
    return last in ("/", "!", "}", "|") and ch.isalpha() and not ch.isascii()


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
