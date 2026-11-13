"""The PDF engines `doctor` probes and the deck prints with (`monitor.py pdf`, deck.render), and the name of the copy
to send.

The deck's engine is whichever of chromium, google-chrome or weasyprint is installed and writes the file (deck.ENGINES);
the skill installs none. A browser prints with its sandbox or not at all.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .i18n import DECK

ENGINES = (
    ("weasyprint", ["{html}", "{pdf}"]),
    ("chromium", ["--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("chromium-browser", ["--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("google-chrome", ["--headless", "--disable-gpu", "--no-pdf-header-footer", "--print-to-pdf={pdf}", "{url}"]),
    ("wkhtmltopdf", ["{html}", "{pdf}"]),
)
BROWSERS = ("chromium", "chromium-browser", "google-chrome")
# What Chromium prints when it cannot start its sandbox: on Ubuntu 23.10 and later AppArmor restricts unprivileged user
# namespaces, and a build without an AppArmor profile of its own (Playwright's, a snap's copy run from elsewhere) fails.
NO_SANDBOX = re.compile(r"No usable sandbox", re.I)
FIX = ("Install a browser whose sandbox works here, such as Google Chrome from Google's .deb package, which brings its "
       "AppArmor profile, or install weasyprint")


class NoSandbox(Exception):
    """Every engine that could print failed, and a browser among them could not start its sandbox; exit code 1."""


def share_name(folder, study, date, kind=None):
    """`<Subject> + Sentl.ai - monitoring deck (<start> to <end>)`, in the study's `report_language`: what the recipient
    sees of the file. `kind` names another kind of file in place of the deck, such as the quick deck's summary."""
    t = DECK.get(study.get("report_language") or "en", DECK["en"])
    kind = kind or t["share_kind"]
    subject = ((study.get("subject") or {}).get("label") or "").strip()
    entry = next((e for e in folder.reports() if e["date"] == date), None)
    period = entry.get("period") if entry else None
    span = date
    if period:
        start, end = period["from"][:10], period["to"][:10]
        span = start if start == end else t["share_span"].format(start=start, end=end)
    name = f"{subject} + Sentl.ai - {kind} ({span})" if subject else f"Sentl.ai - {kind} ({span})"
    return " ".join(re.sub(r'[/\\:*?"<>|]', " ", name).split())


def _no_sandbox(failures):
    return [f.split(":", 1)[0] for f in failures if NO_SANDBOX.search(f)]


def print_pdf(target, pdf, engines):
    """The page at `target` printed to `pdf` by the first engine that writes it: (engine, failures). A browser runs
    with its sandbox only: when none prints and one could not start its sandbox, NoSandbox says why and what to install."""
    engine, failures = _print(target, pdf, engines)
    stuck = _no_sandbox(failures)
    if not engine and stuck:
        raise NoSandbox(f"{' and '.join(dict.fromkeys(stuck))} cannot start its sandbox on this machine: the system restricts "
                        "unprivileged user namespaces (AppArmor, on Ubuntu 23.10 and later), and this browser build has no "
                        f"profile that allows them. The skill never prints without the sandbox. Wrote {target}, and no PDF. "
                        f"{FIX}, then run this command again.")
    return engine, failures


def _print(target, pdf, engines):
    failures = []
    for name, template in engines:
        exe = shutil.which(name)
        if not exe:
            continue
        cmd = [exe] + [a.format(html=str(target), pdf=str(pdf), url=target.resolve().as_uri()) for a in template]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        except subprocess.TimeoutExpired:
            failures.append(f"{name} took more than 3 minutes")
            continue
        if done.returncode == 0 and pdf.exists():
            return name, failures
        pdf.unlink(missing_ok=True)
        failures.append(f"{name}: {' '.join((done.stderr or done.stdout).split())[:160]}")
    return None, failures


def _test_page(folder):
    page_path = Path(folder) / "test.html"
    page_path.write_text("<!doctype html><html><body><p>sentl-monitor</p></body></html>", encoding="utf-8")
    return page_path


def sandboxed_browser():
    """The first browser on this machine that prints a test page with its sandbox, or None."""
    with tempfile.TemporaryDirectory(prefix="sentl-pdf-") as folder:
        target = _test_page(folder)
        for name, template in ENGINES:
            if name in BROWSERS and shutil.which(name):
                engine, _ = _print(target, Path(folder) / f"{name}.pdf", [(name, template)])
                if engine:
                    return engine
    return None


def probe():
    """One line for `doctor`: which engine prints a test page here, a browser first, and with its sandbox."""
    order = [e for e in ENGINES if e[0] in BROWSERS] + [e for e in ENGINES if e[0] not in BROWSERS]
    installed = [e for e in order if shutil.which(e[0])]
    if not installed:
        return ("PDF: no PDF engine is installed (chromium, google-chrome, weasyprint, wkhtmltopdf): pdf writes the page "
                "only. Install Google Chrome or weasyprint to print it.")
    with tempfile.TemporaryDirectory(prefix="sentl-pdf-") as folder:
        target = _test_page(folder)
        failures = []
        for name, template in installed:
            engine, failed = _print(target, Path(folder) / f"{name}.pdf", [(name, template)])
            failures += failed
            if engine:
                stuck = _no_sandbox(failures)
                after = f"; {' and '.join(stuck)} cannot start its sandbox here" if stuck else ""
                kind = "prints with its sandbox" if name in BROWSERS else "prints"
                return f"PDF: {name} {kind}{after}."
    stuck = _no_sandbox(failures)
    if stuck:
        return (f"PDF: {' and '.join(stuck)} cannot start its sandbox here (AppArmor restricts unprivileged user namespaces), "
                f"and the skill never prints without it. {FIX}.")
    return f"PDF: no installed engine printed a test page ({'; '.join(failures)})."
