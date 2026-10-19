"""`pack` and `unpack`: the state the next report needs, carried as one zip between web
conversations, whose sandbox deletes every file when the conversation ends (ARCHITECTURE.md
§The pack).

The zip is deterministic, by the rules of tools/build_zip.py: entries sorted, dated
1980-01-01, 0644 for a file and 0755 for a folder. `unpack` checks the whole pack before it
writes a file.
"""

import hashlib
import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
from pathlib import Path

from .common import Refused, Study, load_json, parse_time, read_gz
from .compare import K
from .period import previous_cut

SCHEMA = "sentl-monitor/pack@1"
MANIFEST = "manifest.json"
SUFFIX = ".sentl-pack.zip"
DATE = (1980, 1, 1, 0, 0, 0)
# The files of a study's state, packed whenever they exist.
STATE = ("study.json", "sentl.json", "search-demand.json", "history/reports.json", "history/unavailable.json",
         "history/last-report.json")
PERIOD = re.compile(r"\d{4}-\d{2}-\d{2}(\.(first|second))?\.json")
DAY_FILE = re.compile(r"\d{4}-\d{2}-\d{2}\.json")
RUN_FILE = re.compile(r"(\d+)\.json\.gz")
SHA256 = re.compile(r"[0-9a-f]{64}")
CHUNK = 1 << 20
# Far above a study's state (a year of daily runs of a 39-answer project is about 30 MB), and low
# enough that a damaged or hostile manifest cannot fill the disk.
MAX_FILE = 50 * 1024 * 1024
MAX_TOTAL = 200 * 1024 * 1024
MB = 1024 * 1024
# The hidden folder inside the target that unpack stages its files in, removed when it ends.
STAGING = ".sentl-unpack-"


class Unknown(Exception):
    """A pack whose manifest has a schema this version does not read; exit code 5."""


# --- pack -------------------------------------------------------------------

def _finals(reports):
    return [e for e in reports if e.get("status") == "final"]


def _periods(folder, reports, full):
    """The period files a pack holds: every one with --full; else those the next report compares
    with (the latest K among the reports' dates and the rebuilt periods, as `period` picks them)
    and the halves of the latest report."""
    folder_path = folder.path("history", "periods")
    if not folder_path.is_dir():
        return []
    if full:
        return sorted(p.name for p in folder_path.iterdir() if p.is_file() and PERIOD.fullmatch(p.name))
    dates = {e["date"] for e in reports}
    dates |= {p.stem for p in folder_path.glob("*.json")
              if DAY_FILE.fullmatch(p.name) and p.stem not in dates and load_json(p).get("rebuilt")}
    names = [f"{d}.json" for d in sorted(dates, reverse=True)[:K] if (folder_path / f"{d}.json").is_file()]
    if reports:
        names += [n for n in (f"{reports[-1]['date']}.{h}.json" for h in ("first", "second"))
                  if (folder_path / n).is_file()]
    return sorted(names)


def _latest_runs(folder, reports):
    """{project: run ids} the latest report's period read: the runs reports.json lists, those its
    period file lists (the file is newer when the period was built again after a late run), and
    those it left out under the judged floor, which building that period again reads too."""
    if not reports:
        return {}
    latest = reports[-1]
    ids = {k: set(v) for k, v in latest["runs"].items()}
    path = folder.path("history", "periods", f"{latest['date']}.json")
    if path.is_file():
        period = load_json(path)
        for k, pooled in (period.get("runs") or {}).items():
            ids.setdefault(k, set()).update(pooled)
        for k, left in (period.get("excluded") or {}).items():
            ids.setdefault(k, set()).update(e["run_id"] for e in left)
    return ids


def _runs(folder, key, reports, latest_ids, full):
    """A project's run files a pack holds: every one with --full or before a first final report;
    else the runs of the latest report's period, those it left out included, and those started
    after its last run, which the next report reads."""
    files = {}
    folder_path = folder.path("history", "runs", key)
    if folder_path.is_dir():
        for p in folder_path.iterdir():
            m = RUN_FILE.fullmatch(p.name)
            if m and p.is_file():
                files[int(m.group(1))] = p.name
    if full or not _finals(reports):
        return [files[i] for i in sorted(files)]
    latest = reports[-1]
    started = {}
    for run_id, name in files.items():
        at = read_gz(folder_path / name).get("started_at")
        started[run_id] = parse_time(at) if at else None
    cut = previous_cut(latest, key, {i: at for i, at in started.items() if at is not None})
    mine = latest_ids.get(key, set())
    # A run with no start time cannot be placed, so it is kept.
    return [files[i] for i in sorted(files) if i in mine or started[i] is None or started[i] > cut]


def select(folder, full=False):
    """The study-relative paths a pack holds, sorted."""
    keys = [p["key"] for p in folder.study["projects"]]
    reports = folder.reports()
    latest_ids = _latest_runs(folder, reports)
    paths = [n for n in STATE if folder.path(n).is_file()]
    for key in keys:
        paths += [f"history/versions/{p.name}"
                  for p in sorted(folder.path("history", "versions").glob(f"{key}-[0-9][0-9][0-9].json"))]
        paths += [f"history/runs/{key}/{name}" for name in _runs(folder, key, reports, latest_ids, full)]
    paths += [f"history/periods/{name}" for name in _periods(folder, reports, full)]
    return sorted(set(paths))


def _caps(folder, paths):
    """Refuse a state `unpack` would refuse: a file over 50 MB, more than 200 MB in all."""
    sizes = {rel: folder.path(rel).stat().st_size for rel in paths}
    largest = sorted(sizes, key=lambda rel: (-sizes[rel], rel))
    show = lambda names: ", ".join(f"{rel} ({sizes[rel] / MB:.1f} MB)" for rel in names)  # noqa: E731
    big = [rel for rel in largest if sizes[rel] > MAX_FILE]
    if big:
        raise Refused(f"files over the 50 MB a pack file may hold, which unpack would refuse: {show(big[:5])}")
    total = sum(sizes.values())
    if total > MAX_TOTAL:
        raise Refused(f"the files to pack hold {total / MB:.1f} MB, over the 200 MB a pack may hold, which unpack "
                      f"would refuse; the largest: {show(largest[:5])}")


def _digest(path):
    h, size = hashlib.sha256(), 0
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
            size += len(chunk)
    return size, h.hexdigest()


def _target(folder, out, last):
    name = folder.root.resolve().name + (f"-{last}" if last else "") + SUFFIX
    if out is None:
        return folder.root.resolve().parent / name
    out = Path(out)
    if out.is_dir() or out.suffix.lower() != ".zip":
        return out / name
    return out


def _info(name, mode):
    info = zipfile.ZipInfo(name, date_time=DATE)
    info.create_system = 3
    if name.endswith("/"):
        info.external_attr = (stat.S_IFDIR | mode) << 16 | 0x10
    else:
        info.external_attr = (stat.S_IFREG | mode) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
    return info


def _held(paths, keys):
    """'brand 6 runs, market 30 runs' for the run files among `paths`."""
    counts = {k: sum(1 for p in paths if p.startswith(f"history/runs/{k}/")) for k in keys}
    return ", ".join(f"{k} {n} run{'s' if n != 1 else ''}" for k, n in counts.items())


def pack(root, out=None, full=False, skill_version="unknown"):
    folder = Study(root)
    binding = folder.binding
    paths = select(folder, full)
    _caps(folder, paths)
    finals = _finals(folder.reports())
    last = finals[-1]["date"] if finals else None
    files = []
    for rel in paths:
        size, digest = _digest(folder.path(rel))
        files.append({"path": rel, "size": size, "sha256": digest})
    manifest = {
        "schema": SCHEMA, "skill_version": skill_version, "full": bool(full),
        "last_report": last, "final_reports": len(finals),
        "projects": [{"key": k, "project_id": v.get("project_id")} for k, v in binding["projects"].items()],
        "files": files,
    }
    dirs = sorted({"/".join(rel.split("/")[:i]) + "/" for rel in paths for i in range(1, rel.count("/") + 1)})
    entries = sorted([(d, None) for d in dirs] + [(rel, folder.path(rel)) for rel in paths]
                     + [(MANIFEST, json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n")],
                     key=lambda e: e[0])

    target = _target(folder, out, last)
    target.parent.mkdir(parents=True, exist_ok=True)
    # A new file of its own beside the target, so an existing file or link there is never written through.
    fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
    tmp = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as fh, zipfile.ZipFile(fh, "w") as zf:
            for name, source in entries:
                if name.endswith("/"):
                    zf.writestr(_info(name, 0o755), b"")
                else:
                    data = source if isinstance(source, bytes) else source.read_bytes()
                    zf.writestr(_info(name, 0o644), data, compresslevel=9)
        os.chmod(tmp, 0o666 & ~_umask())
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
    size, digest = _digest(target)
    keys = [p["key"] for p in folder.study["projects"]]
    kind = "every run and period (--full)" if full else "the state the next report needs"
    lines = [f"Packed {len(paths)} files of {folder.root.resolve().name} into {target} ({size:,} bytes, "
             f"sha256 {digest}): {kind}.",
             (f"Last final report: {last}. " if last else "No final report yet. ") + f"Runs held: {_held(paths, keys)}.",
             "Give the user this file to download and keep: the next conversation unpacks it before its first "
             "command."]
    return "\n".join(lines)


# --- unpack -----------------------------------------------------------------

def _unsafe(info):
    """Why the entry `info` cannot be written into a study folder, or None."""
    name = info.filename
    if stat.S_ISLNK(info.external_attr >> 16):
        return "is a link"
    if name.startswith(("/", "\\")) or re.match(r"[A-Za-z]:", name):
        return "is an absolute path"
    if "\\" in name:
        return "holds a backslash"
    parts = name.rstrip("/").split("/")
    if ".." in parts:
        return "holds '..'"
    if any(p in ("", ".") for p in parts):
        return "holds an empty or '.' part"
    return None


def _allowed(path, keys):
    """True when `path` is a file a pack writes: the state files, a version or the runs of one of
    the pack's projects, a period file."""
    if path in STATE:
        return True
    parts = path.split("/")
    if len(parts) == 3 and parts[:2] == ["history", "versions"]:
        m = re.fullmatch(r"(.+)-\d{3}\.json", parts[2])
        return bool(m) and m.group(1) in keys
    if len(parts) == 3 and parts[:2] == ["history", "periods"]:
        return bool(PERIOD.fullmatch(parts[2]))
    if path.startswith("history/runs/"):
        key, _, name = path[len("history/runs/"):].rpartition("/")
        return key in keys and bool(RUN_FILE.fullmatch(name))
    return False


def _manifest(zf, pack_path):
    try:
        data = json.loads(zf.read(MANIFEST).decode("utf-8"))
    except KeyError:
        raise Refused(f"{pack_path} holds no {MANIFEST}: it is not a sentl-monitor pack") from None
    except (ValueError, zipfile.BadZipFile, OSError) as exc:
        raise Refused(f"the {MANIFEST} of {pack_path} cannot be read ({exc}): the pack is damaged") from None
    if not isinstance(data, dict):
        raise Refused(f"the {MANIFEST} of {pack_path} is not an object: the pack is damaged")
    if data.get("schema") != SCHEMA:
        raise Unknown(f"the pack {pack_path} has manifest schema {data.get('schema')!r}, which this version of "
                      f"sentl-monitor does not read (it reads {SCHEMA}): stop, and tell the operator the skill "
                      "needs an update to read it")
    problems = []
    files, projects, last = data.get("files"), data.get("projects"), data.get("last_report")
    if not isinstance(files, list) or not all(
            isinstance(f, dict) and isinstance(f.get("path"), str) and isinstance(f.get("size"), int)
            and f["size"] >= 0 and isinstance(f.get("sha256"), str) and SHA256.fullmatch(f["sha256"]) for f in files):
        problems.append("files is not a list of {path, size, sha256}")
    if not isinstance(projects, list) or not projects or not all(
            isinstance(p, dict) and isinstance(p.get("key"), str) and p["key"]
            and isinstance(p.get("project_id"), int) for p in projects):
        problems.append("projects is not a list of {key, project_id}")
    if last is not None and not (isinstance(last, str) and DAY_FILE.fullmatch(last + ".json")):
        problems.append("last_report is not a date or null")
    if problems:
        raise Refused(f"the {MANIFEST} of {pack_path} is damaged: " + "; ".join(problems))
    paths = [f["path"] for f in files]
    if len(set(paths)) != len(paths):
        raise Refused(f"the {MANIFEST} of {pack_path} lists a file twice: the pack is damaged")
    return data


def _sizes(listed, held, pack_path):
    """Refuse a file declared over MAX_FILE, a pack declared over MAX_TOTAL in all, and an entry
    whose size in the zip differs from the manifest's."""
    big = sorted(p for p, f in listed.items() if f["size"] > MAX_FILE)
    if big:
        raise Refused(f"{pack_path} declares files over 50 MB, more than a study's state holds: {', '.join(big)}")
    total = sum(f["size"] for f in listed.values())
    if total > MAX_TOTAL:
        raise Refused(f"{pack_path} declares {total:,} bytes in all, over the 200 MB a pack may hold")
    differ = sorted(p for p, f in listed.items() if held[p].file_size != f["size"])
    if differ:
        raise Refused(f"{pack_path} holds files whose size differs from the size its manifest lists: "
                      f"{', '.join(differ)}; the pack was changed or damaged after it was written")


def _chunks(zf, info, entry, pack_path):
    """The bytes of `info`, chunk by chunk; refused at the end unless they have the size and sha256
    the manifest lists."""
    damaged = f"{entry['path']} in {pack_path} cannot be read"
    h, size = hashlib.sha256(), 0
    try:
        fh = zf.open(info)
    except (zipfile.BadZipFile, OSError, EOFError) as exc:
        raise Refused(f"{damaged} ({exc}): the pack is damaged") from None
    with fh:
        while size <= entry["size"]:
            try:
                chunk = fh.read(CHUNK)
            except (zipfile.BadZipFile, OSError, EOFError) as exc:
                raise Refused(f"{damaged} ({exc}): the pack is damaged") from None
            if not chunk:
                break
            size += len(chunk)
            h.update(chunk)
            yield chunk
    if size != entry["size"] or h.hexdigest() != entry["sha256"]:
        raise Refused(f"{entry['path']} in {pack_path} differs from the sha256 its manifest lists: the pack was "
                      "changed or damaged after it was written; unpack the pack as it was downloaded")


def _check_target(target, paths):
    """Refuse a target that is not a folder, and a path on which an existing part is a link, a file
    stands where a folder goes, or a folder where a file goes: a write there would fail half way or
    leave the study folder."""
    if target.exists() and not target.is_dir():
        raise Refused(f"{target} exists and is not a folder: choose an empty folder for the study")
    for rel in paths:
        here = target
        parts = rel.split("/")
        for n, part in enumerate(parts):
            here = here / part
            last = n == len(parts) - 1
            if here.is_symlink():
                raise Refused(f"{here} is a link: the pack writes only inside the study folder")
            if last and here.is_dir():
                raise Refused(f"{here} is a folder where the pack writes a file")
            if not last and here.exists() and not here.is_dir():
                raise Refused(f"{here} is a file where the pack needs a folder")


def _study_or_empty(target):
    """Refuse a folder that holds files and no sentl.json: it is not a study folder."""
    if target.is_dir() and not (target / "sentl.json").is_file() and any(
            not p.name.startswith(STAGING) for p in target.iterdir()):
        raise Refused(f"{target} holds files and no sentl.json, so it is not a study folder: unpack into an "
                      "empty folder, or into the folder of the pack's own study")


def _bound(folder, manifest, pack_path):
    path = folder.path("sentl.json")
    if not path.is_file():
        return
    try:
        bound = load_json(path)["projects"]
        theirs = {(k, v.get("project_id")) for k, v in bound.items()}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        raise Refused(f"{path} cannot be read: unpack into an empty folder") from None
    ours = {(p["key"], p["project_id"]) for p in manifest["projects"]}
    other = sorted(theirs - ours, key=str)
    if other:
        show = lambda pairs: ", ".join(f"{k} {i}" for k, i in sorted(pairs, key=str))  # noqa: E731
        raise Refused(f"{folder.root} is bound to other Sentl projects ({show(other)}), and {pack_path} holds "
                      f"{show(ours)}: unpack it into an empty folder, or into the folder of its own study")


def _stale(folder, manifest, pack_path):
    finals = _finals(folder.reports())
    if not finals:
        return
    here, packed = finals[-1]["date"], manifest["last_report"]
    if packed is None or packed < here:
        raise Refused(f"{pack_path} is older than {folder.root}: its last final report is "
                      f"{packed or 'none'}, the folder's is {here}. Unpack the latest pack, the one written "
                      f"after the report of {here}")


def _write_new(path, chunks):
    """Create the file `path`, which must not exist yet, without following a link, and write
    `chunks` into it."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    with os.fdopen(os.open(path, flags, 0o666), "wb") as fh:
        for chunk in chunks:
            fh.write(chunk)


def _umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def _move(src, dst):
    """One rename; staging and destination share the target's file system."""
    os.replace(src, dst)


def _nearest(folder):
    """`folder`, or its nearest ancestor that exists."""
    while not os.path.lexists(folder) and folder != folder.parent:
        folder = folder.parent
    return folder


def _writable(target, paths):
    """Refuse when a folder the pack writes into, or the nearest existing folder above one it
    creates, cannot be written: found before a file moves, not half way."""
    folders = {target} | {target.joinpath(*p.split("/")[:-1]) for p in paths}
    for folder in sorted({_nearest(f) for f in folders}, key=str):
        if not (folder.is_dir() and os.access(folder, os.W_OK | os.X_OK)):
            raise Refused(f"{folder} cannot be written, and the pack writes there: nothing was written. Give the "
                          "folder write permission, or choose another study folder")


def _makedirs(folder, made):
    """Create `folder` and the folders above it that do not exist, recording each in `made`."""
    missing = []
    while not os.path.lexists(folder):
        missing.append(folder)
        folder = folder.parent
    for folder in reversed(missing):
        os.mkdir(folder)
        made.append(folder)


def _write_all(zf, target, paths, held, listed, pack_path):
    """Write the pack's files into `target`, all or nothing. They are written to a hidden staging
    folder inside the target, on its file system; then each file is moved into place, a file it
    replaces moved aside first. On any failure the files are put back, the new files and folders
    removed, and the staging folder removed, so the target is as it was."""
    made, undo, staging = [], [], None
    try:
        _makedirs(target, made)
        staging = Path(tempfile.mkdtemp(prefix=STAGING, dir=target))
        new, aside = staging / "new", staging / "replaced"
        for path in paths:
            dest = new.joinpath(*path.split("/"))
            dest.parent.mkdir(parents=True, exist_ok=True)
            _write_new(dest, _chunks(zf, held[path], listed[path], pack_path))
        for path in paths:
            parts = path.split("/")
            dest = target.joinpath(*parts)
            _makedirs(dest.parent, made)
            if os.path.lexists(dest):
                backup = aside.joinpath(*parts)
                backup.parent.mkdir(parents=True, exist_ok=True)
                _move(dest, backup)
                undo.append((backup, dest))
            _move(new.joinpath(*parts), dest)
            undo.append((None, dest))
    except BaseException:
        for backup, dest in reversed(undo):
            try:
                if backup is None:
                    os.unlink(dest)
                else:
                    os.replace(backup, dest)
            except OSError:
                pass
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        for folder in reversed(made):
            try:
                os.rmdir(folder)
            except OSError:
                pass
        raise
    shutil.rmtree(staging, ignore_errors=True)


def unpack(root, pack_path, skill_version="unknown"):
    pack_path = Path(pack_path)
    target = Path(os.path.abspath(root))
    try:
        zf = zipfile.ZipFile(pack_path)
    except (OSError, zipfile.BadZipFile) as exc:
        raise Refused(f"{pack_path} cannot be read as a zip ({exc}): attach the pack as it was downloaded") from None
    with zf:
        infos = zf.infolist()
        for info in infos:
            why = _unsafe(info)
            if why:
                raise Refused(f"{pack_path} holds {info.filename!r}, which {why}: a pack never does; "
                              "nothing was written")
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise Refused(f"{pack_path} holds an entry twice: the pack is damaged")
        manifest = _manifest(zf, pack_path)
        keys = {p["key"] for p in manifest["projects"]}
        listed = {f["path"]: f for f in manifest["files"]}
        held = {i.filename: i for i in infos if not i.is_dir() and i.filename != MANIFEST}
        extra, missing = sorted(held.keys() - listed.keys()), sorted(listed.keys() - held.keys())
        if extra:
            raise Refused(f"{pack_path} holds files its manifest does not list: {', '.join(extra)}")
        if missing:
            raise Refused(f"{pack_path} lacks files its manifest lists: {', '.join(missing)}")
        never = sorted(p for p in listed if not _allowed(p, keys))
        if never:
            raise Refused(f"{pack_path} holds files a pack never holds: {', '.join(never)}")
        _sizes(listed, held, pack_path)
        paths = sorted(listed)
        for path in paths:
            for _ in _chunks(zf, held[path], listed[path], pack_path):
                pass

        folder = Study(target)
        _check_target(target, paths)
        _study_or_empty(target)
        _bound(folder, manifest, pack_path)
        _stale(folder, manifest, pack_path)

        _writable(target, paths)
        _write_all(zf, target, paths, held, listed, pack_path)

    order = [p["key"] for p in manifest["projects"]]
    last = manifest["last_report"]
    lines = [f"Unpacked {len(listed)} files from {pack_path} into {target}, written by sentl-monitor "
             f"{manifest.get('skill_version') or 'unknown'}."]
    if manifest.get("skill_version") not in (None, skill_version):
        lines.append(f"This is sentl-monitor {skill_version}: the pack's files are read as they are.")
    lines.append((f"Last final report: {last}. " if last else "No final report yet. ")
                 + f"Runs held: {_held(list(listed), order)}.")
    if last:
        lines.append(f"The next report covers the runs started after the last run of the report of {last}.")
    else:
        lines.append("The first report covers the last report_every interval and the four before it.")
    return "\n".join(lines)
