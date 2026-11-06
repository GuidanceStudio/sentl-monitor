"""A web page as its HTML holds it, for the writer of a deck.

A web tool hands over the text a reader sees at first. What a site keeps in tooltips and closed answers is not in it, and an
action saying a page lacks what it shows embarrasses whoever presents the deck. The HTML holds all of that, with the title and
the description search engines index, which assistants often repeat. No script of the site runs: the page is only parsed."""
import re
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit

from .common import Refused

AGENT = "Mozilla/5.0 (X11; Linux x86_64) sentl-monitor"
TIMEOUT = 30
MOST = 8_000_000
SKIP = {"script", "style", "noscript", "svg", "template"}
BREAK = {"p", "div", "li", "tr", "td", "th", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "summary", "details",
         "dt", "dd", "button", "label", "br", "option"}
SAID = re.compile(r"^(?:title|alt|aria-label|placeholder|data-(?:[\w-]*tooltip[\w-]*|[\w-]*tip|[\w-]*title|[\w-]*content))$")


class _Text(HTMLParser):
    """The text of a page, closed or hidden parts included, and what its attributes say to whoever hovers."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines, self.line, self.skipping, self.in_title = [], [], 0, False
        self.title, self.description = "", ""

    def flush(self):
        text = " ".join(" ".join(self.line).split())
        if text:
            self.lines.append(text)
        self.line = []

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self.skipping += 1
            return
        if tag == "title":
            self.in_title = True
            return
        said = dict(attrs)
        if tag == "meta":
            if (said.get("name") or said.get("property") or "").lower() in ("description", "og:description"):
                self.description = self.description or (said.get("content") or "")
            return
        if tag in BREAK:
            self.flush()
        for name, value in attrs:
            if value and SAID.match(name) and not value.lstrip().startswith(("<", "{", "[")):
                self.line.append(f"[{value}]")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skipping = max(self.skipping - 1, 0)
        elif tag == "title":
            self.in_title = False
        elif tag in BREAK:
            self.flush()

    def handle_data(self, data):
        if self.in_title:
            self.title = self.title or " ".join(data.split())
        elif not self.skipping:
            self.line.append(data)


def text_of(html):
    """Title, description and text of a page's HTML, a line per block, each line once."""
    parser = _Text()
    parser.feed(html)
    parser.close()
    parser.flush()
    seen, lines = set(), []
    for line in parser.lines:
        if line not in seen:
            seen.add(line)
            lines.append(line)
    return "\n".join([f"Title: {parser.title}", f"Description: {parser.description}", "", *lines])


def read(url, opener=urllib.request.urlopen):
    """What the HTML at `url` holds. Only http and https: the addresses come from what assistants cite."""
    url = url if "://" in url else f"https://{url}"
    if urlsplit(url).scheme not in ("http", "https"):
        raise Refused(f"{url} is not a web address")
    try:
        with opener(urllib.request.Request(url, headers={"User-Agent": AGENT}), timeout=TIMEOUT) as response:  # noqa: S310 - scheme checked above
            charset = response.headers.get_content_charset() or "utf-8"
            html = response.read(MOST).decode(charset, "replace")
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise Refused(f"could not read {url}: {e}. Use your web tool, and treat what it does not show as not known") from e
    text = text_of(html)
    if len(text.split()) < 40:
        raise Refused(f"{url} holds almost no text: its page is built by scripts. Use your web tool, and treat what it does "
                      "not show as not known")
    return text
