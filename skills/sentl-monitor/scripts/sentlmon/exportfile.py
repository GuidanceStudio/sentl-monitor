"""Sentl's run export and result pages: `import` and `download` turn an export into the files
the other commands read, `assemble_pages` joins the pages of one run. A download sends no
credential, and only to Sentl's own hosts."""

import gzip
import hashlib
import io
import json
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal
from pathlib import Path

from . import schema
from .common import Refused, write_json

SCHEMA_VERSIONS = (1,)
HOSTS = ("sentl.ai",)
DOWNLOAD_CAP = 64 * 1024 * 1024
UNPACKED_CAP = 512 * 1024 * 1024
TIMEOUT = 30


class Unreachable(Exception):
    """A download link that did not answer or has expired; exit code 7."""


# --- RFC 8785 canonical JSON ---------------------------------------------------------------

def _number(value):
    if isinstance(value, int):
        return str(value)
    if value != value or value in (float("inf"), float("-inf")):
        raise ValueError("JSON has no NaN or infinity")
    if value == 0:
        return "0"
    _, digit_tuple, exponent = Decimal(repr(abs(value))).as_tuple()
    digits = "".join(map(str, digit_tuple)).rstrip("0") or "0"
    # The value is 0.<digits> * 10^n, so its decimal point sits after n digits.
    n = exponent + len(digit_tuple)
    k = len(digits)
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
        body = f"{mantissa}e{'+' if e >= 0 else '-'}{abs(e)}"
    return ("-" if value < 0 else "") + body


def jcs(value):
    """The RFC 8785 canonical JSON text of a parsed JSON value."""
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, (int, float)):
        return _number(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return "[" + ",".join(jcs(v) for v in value) + "]"
    if isinstance(value, dict):
        # Keys sort by UTF-16 code units, which is the byte order of their UTF-16BE encoding.
        keys = sorted(value, key=lambda k: k.encode("utf-16-be", "surrogatepass"))
        return "{" + ",".join(json.dumps(k, ensure_ascii=False) + ":" + jcs(value[k]) for k in keys) + "}"
    raise TypeError(f"{type(value).__name__} is not JSON")


def content_sha256(response):
    """The digest Sentl puts in `content_sha256`: the canonical JSON of the response without that field."""
    body = {k: v for k, v in response.items() if k != "content_sha256"}
    return hashlib.sha256(jcs(body).encode("utf-8")).hexdigest()


# --- the export ----------------------------------------------------------------------------

def _unwrap(value, key):
    return value[key] if isinstance(value, dict) and isinstance(value.get(key), dict) else value


def _check_digest(raw, expected, where):
    if expected is None:
        return
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected.strip().lower():
        raise Refused(f"{where} has sha256 {actual}, not the {expected.strip().lower()} Sentl gave: the file changed "
                      "or is not the one the export returned; export again and use the new file")


def _unpack(raw, where):
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as fh:
            text = fh.read(UNPACKED_CAP + 1)
    except (OSError, EOFError) as exc:
        raise Refused(f"{where} is not a complete gzip file ({exc}): download the export again") from None
    if len(text) > UNPACKED_CAP:
        raise Refused(f"{where} unpacks to more than {UNPACKED_CAP // 1024 // 1024} MB: export fewer runs")
    try:
        return json.loads(text.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refused(f"{where} does not hold JSON: download the export again") from None


def import_bytes(root, raw, sha256=None, where="the export"):
    _check_digest(raw, sha256, where)
    data = _unpack(raw, where)
    if not isinstance(data, dict) or data.get("schema_version") not in SCHEMA_VERSIONS:
        found = data.get("schema_version") if isinstance(data, dict) else None
        raise schema.Mismatch(f"Sentl's export-runs-tool response in {where} has schema_version {found!r}; this skill "
                              f"reads {', '.join(map(str, SCHEMA_VERSIONS))}. Update the skill, or ask for a version it reads. "
                              "Nothing was written.")
    proj = schema.check_project(_unwrap(data.get("project"), "project"), where)
    runs = data.get("runs")
    if not isinstance(runs, list):
        raise schema.Mismatch(f"Sentl's export-runs-tool response in {where}: runs is not a list. Nothing was written.")
    listing = []
    files = {f"project-{proj['id']}.json": {"project": proj}}
    for n, item in enumerate(runs):
        run = schema.check_run(_unwrap(item, "run"), f"{where} runs[{n}]")
        if run["project_id"] != proj["id"]:
            raise Refused(f"run {run['id']} in {where} belongs to project {run['project_id']}, not to the export's "
                          f"project {proj['id']}: export the runs of one project")
        files[f"run-{run['id']}.json"] = {"run": run}
        listing.append({k: v for k, v in run.items() if k != "responses"})
    files[f"runs-{proj['id']}.json"] = {"project_id": proj["id"], "runs": listing}
    for name, body in files.items():
        write_json(Path(root) / "inbox" / name, body)
    count = len(listing)
    return (f"Imported project {proj['id']} and {count} run{'s' if count != 1 else ''} into inbox/: "
            + ", ".join(sorted(files)) + ".")


def import_export(root, path, sha256=None):
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise Refused(f"{path} cannot be read ({exc.strerror or exc}): download the export again") from None
    return import_bytes(root, raw, sha256, where=str(path))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def _open(request, timeout):
    return _OPENER.open(request, timeout=timeout)


def _allowed(url, hosts, schemes):
    parts = urllib.parse.urlsplit(url)
    host = (parts.hostname or "").lower()
    return (parts.scheme in schemes and not parts.username and not parts.password
            and any(host == h or host.endswith("." + h) for h in hosts))


def download(root, url, sha256, cap=DOWNLOAD_CAP, hosts=HOSTS, schemes=("https",), opener=None):
    """Fetch an export link with a plain GET and import it. Nothing is written unless the
    digest matches."""
    if not _allowed(url, hosts, schemes):
        raise Refused(f"{url} is not a Sentl download link: only https on {', '.join(hosts)} is fetched. "
                      "Download the export in the browser and attach the file instead")
    request = urllib.request.Request(url, headers={"Accept": "application/gzip"})
    try:
        with (opener or _open)(request, timeout=TIMEOUT) as response:
            size = response.headers.get("Content-Length")
            if size and size.isdigit() and int(size) > cap:
                raise Refused(f"the export is larger than {cap // 1024 // 1024} MB: export fewer runs")
            raw = response.read(cap + 1)
    except urllib.error.HTTPError as exc:
        raise Unreachable(f"the download link answered HTTP {exc.code}: export again to get a new link "
                          "(valid for 60 minutes)") from None
    except (urllib.error.URLError, OSError) as exc:
        raise Unreachable(f"the download link did not answer ({getattr(exc, 'reason', exc)}): export again to get "
                          "a new link (valid for 60 minutes), or download the file in the browser and attach it") from None
    if len(raw) > cap:
        raise Refused(f"the export is larger than {cap // 1024 // 1024} MB: export fewer runs")
    return import_bytes(root, raw, sha256, where="the download")


# --- pages of one run ----------------------------------------------------------------------

def assemble_pages(root, files):
    """Join the pages of one run into inbox/run-<id>.json; returns that path. A page whose
    checksum, number, header or responses do not fit the others is refused by number."""
    from .common import read_mcp
    pages = []
    for f in files:
        page = read_mcp(f)
        if not isinstance(page, dict) or not isinstance(page.get("run"), dict) or not isinstance(page.get("page"), int):
            raise Refused(f"{f} is not a page of get-run-results-tool: it needs run and page")
        if page.get("content_sha256") != content_sha256(page):
            raise Refused(f"page {page['page']} ({f}): content_sha256 does not match its content: save the page "
                          "again from the tool's response")
        pages.append(page)
    pages.sort(key=lambda p: p["page"])
    numbers = [p["page"] for p in pages]
    if len(set(numbers)) != len(numbers):
        dup = next(n for n in numbers if numbers.count(n) > 1)
        raise Refused(f"page {dup} was given twice")
    for expected, page in enumerate(pages, 1):
        if page["page"] != expected:
            raise Refused(f"page {expected} is missing: save it and run the command again with every page")
    if pages[-1].get("next_page") is not None:
        raise Refused(f"page {pages[-1]['next_page']} is missing: the last page given points to it")
    header = {k: v for k, v in pages[0]["run"].items() if k != "responses"}
    seen, responses = {}, []
    for page in pages:
        other = {k: v for k, v in page["run"].items() if k != "responses"}
        if other != header:
            diff = sorted(k for k in set(header) | set(other) if header.get(k) != other.get(k))
            raise Refused(f"page {page['page']} is of another run state than page 1: {', '.join(diff)} differ; save "
                          "every page from the same read")
        for r in page["run"].get("responses") or []:
            if r.get("id") in seen:
                raise Refused(f"page {page['page']}: response {r.get('id')} is already on page {seen[r.get('id')]}")
            seen[r.get("id")] = page["page"]
            responses.append(r)
    out = Path(root) / "inbox" / f"run-{header.get('id')}.json"
    write_json(out, {"run": {**header, "responses": responses}})
    return out
