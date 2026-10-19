#!/usr/bin/env python3
"""Build dist/sentl-monitor.zip, the skill as claude.ai and ChatGPT upload it.

The zip holds the payload files git tracks under skills/sentl-monitor/, with the
sentl-monitor/ folder at its root. Entries are sorted, dated 1980-01-01 and given fixed
permissions (0755 for a file git tracks as executable, 0644 otherwise), so two builds of
one commit are identical byte for byte. Byte-compiled caches and test files are left out.
The files are read from the working tree, so the build is refused while the payload has
changes not committed (edited, staged, deleted or untracked files); --allow-dirty builds
anyway, for a local try. It is also refused when SKILL.md's frontmatter breaks a limit a
host applies, when the payload's LICENSE differs from the repository's, or when the zip
exceeds 5 MB. sentl-monitor.zip.sha256 is written next to the zip, in sha256sum's format.

Usage: python3 tools/build_zip.py [--out DIR] [--allow-dirty]   (default: dist/)
"""

import argparse
import hashlib
import io
import os
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = "sentl-monitor"
PAYLOAD = Path("skills") / SKILL
sys.path.insert(0, str(ROOT / PAYLOAD / "scripts"))

from sentlmon import frontmatter  # noqa: E402

MAX_BYTES = 5 * 1024 * 1024
DATE = (1980, 1, 1, 0, 0, 0)
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
VERSION = re.compile(r"\d+\.\d+\.\d+([-+][0-9A-Za-z.-]+)?")
RESERVED = ("anthropic", "claude")


class Refused(Exception):
    pass


def limits(meta, folder):
    """The frontmatter's breaches of the Agent Skills spec and of claude.ai's upload rules."""
    problems = []
    name = meta.get("name")
    if not isinstance(name, str) or not NAME.fullmatch(name) or len(name) > 64:
        problems.append(f"name {name!r}: lowercase letters, digits and single hyphens, at most 64 characters")
    elif name != folder:
        problems.append(f"name {name!r} differs from the folder {folder!r}")
    elif any(word in name for word in RESERVED):
        problems.append(f"name {name!r} holds a word claude.ai reserves ({', '.join(RESERVED)})")
    description = meta.get("description")
    if not isinstance(description, str) or not description.strip():
        problems.append("description is missing")
    else:
        if len(description) > 200:
            problems.append(f"description is {len(description)} characters; claude.ai accepts 200 at most")
        if "<" in description or ">" in description:
            problems.append("description holds < or >, which claude.ai refuses")
    compatibility = meta.get("compatibility")
    if compatibility is not None and (not isinstance(compatibility, str) or not 1 <= len(compatibility) <= 500):
        size = len(compatibility) if isinstance(compatibility, str) else "not a string"
        problems.append(f"compatibility is {size} characters; the spec allows 1 to 500")
    metadata = meta.get("metadata")
    if not isinstance(metadata, dict) or not metadata.get("version"):
        problems.append("metadata.version is missing; it is the skill's one version")
    else:
        if not all(isinstance(v, str) for v in metadata.values()):
            problems.append("metadata holds a value that is not a string")
        if not VERSION.fullmatch(metadata["version"]):
            problems.append(f"metadata.version {metadata['version']!r} is not a version such as 1.2.3")
    return problems


def tracked(root):
    """(path relative to the payload, mode) for each payload file git tracks, in sorted order."""
    out = subprocess.run(["git", "-C", str(root), "ls-files", "-s", "-z", "--", str(PAYLOAD)],
                         capture_output=True, check=True).stdout.decode("utf-8", "surrogateescape")
    files = []
    for record in filter(None, out.split("\0")):
        info, path = record.split("\t", 1)
        mode = info.split()[0]
        files.append((Path(path).relative_to(PAYLOAD).as_posix(), 0o755 if mode == "100755" else 0o644))
    return sorted(files)


def _git(root, *args):
    proc = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip().splitlines()
        raise Refused(f"git {args[0]} failed: {detail[-1] if detail else 'no message'}")
    return [p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


def uncommitted(root):
    """Payload paths whose working-tree state differs from HEAD, untracked files included."""
    try:
        changed = _git(root, "diff", "--name-only", "-z", "HEAD", "--", str(PAYLOAD))
    except Refused as exc:
        raise Refused(f"the payload cannot be compared with HEAD ({exc}); commit it first") from None
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z", "--", str(PAYLOAD))
    return sorted(set(changed) | set(untracked))


def left_out(rel):
    parts = rel.split("/")
    return ("__pycache__" in parts or rel.endswith((".pyc", ".pyo"))
            or any(p in ("test", "tests") for p in parts[:-1])
            or parts[-1].startswith("test_") or parts[-1].endswith("_test.py"))


def build(root, out_dir, allow_dirty=False):
    payload = root / PAYLOAD
    dirty = uncommitted(root)
    if dirty and not allow_dirty:
        raise Refused("the payload has changes not committed, and the zip is built from the working tree:\n"
                      + "\n".join(f"  - {path}" for path in dirty)
                      + "\ncommit them, or pass --allow-dirty for a local try")
    meta = frontmatter.read(payload / "SKILL.md")
    problems = limits(meta, payload.name)
    license_file = payload / "LICENSE"
    if not license_file.is_file() or license_file.read_bytes() != (root / "LICENSE").read_bytes():
        problems.append(f"{PAYLOAD.as_posix()}/LICENSE is missing or differs from the repository's LICENSE")
    if problems:
        raise Refused("SKILL.md or the payload breaks a limit:\n" + "\n".join(f"  - {p}" for p in problems))

    listed = tracked(root)
    files = [(rel, mode) for rel, mode in listed if not left_out(rel)]
    skipped = [rel for rel, _ in listed if left_out(rel)]
    missing = [rel for rel, _ in files if not (payload / rel).is_file()]
    if missing and not allow_dirty:
        raise Refused("git tracks payload files the working tree lacks: " + ", ".join(missing))
    files = [(rel, mode) for rel, mode in files if rel not in missing]
    skipped += missing
    dirs = sorted({"/".join(rel.split("/")[:i]) for rel, _ in files for i in range(1, rel.count("/") + 1)})

    entries = [(f"{SKILL}/", None, 0o755)]
    entries += [(f"{SKILL}/{d}/", None, 0o755) for d in dirs]
    entries += [(f"{SKILL}/{rel}", payload / rel, mode) for rel, mode in files]
    entries.sort(key=lambda e: e[0])

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, source, mode in entries:
            info = zipfile.ZipInfo(name, date_time=DATE)
            info.create_system = 3
            if source is None:
                info.external_attr = (0o040000 | mode) << 16 | 0x10
                zf.writestr(info, b"")
            else:
                info.external_attr = (0o100000 | mode) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                zf.writestr(info, source.read_bytes(), compresslevel=9)
    data = buffer.getvalue()
    if len(data) > MAX_BYTES:
        raise Refused(f"the zip is {len(data):,} bytes, over the 5 MB limit")

    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{SKILL}.zip"
    digest = hashlib.sha256(data).hexdigest()
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, target)
    (out_dir / f"{SKILL}.zip.sha256").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    return target, len(files), len(data), digest, skipped, meta["metadata"]["version"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build dist/sentl-monitor.zip from the tracked payload files.")
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="output folder (default: dist/)")
    parser.add_argument("--allow-dirty", action="store_true",
                        help="build although the payload has changes not committed (a local try, not a release)")
    args = parser.parse_args(argv)
    try:
        target, count, size, digest, skipped, version = build(ROOT, args.out, args.allow_dirty)
    except (Refused, frontmatter.Malformed) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(f"refused: git could not list the payload files ({exc.stderr.decode(errors='replace').strip()})",
              file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"refused: {exc.filename or 'a payload file'} cannot be read ({exc.strerror or exc})", file=sys.stderr)
        return 2
    for rel in skipped:
        print(f"left out: {rel}", file=sys.stderr)
    print(f"Built {target} (sentl-monitor {version}): {count} files, {size:,} bytes, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
