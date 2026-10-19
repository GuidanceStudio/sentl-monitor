"""What the host offers the scripts: the Python version, the system, and whether a study
folder can be written and lasts.

This module is imported before the others, so it parses on any Python 3 and names an older
version instead of failing on syntax it does not know.
"""

import os
import platform
import sys
import tempfile

MIN_PYTHON = (3, 10)
# Web clients run the scripts in a sandbox whose files are deleted when the conversation ends:
# /mnt/user-data on claude.ai, /mnt/data on ChatGPT. Where one of them exists, the whole host
# is such a sandbox, so no folder on it lasts.
SANDBOX_ROOTS = ("/mnt/user-data", "/mnt/data")


def _dotted(version_info):
    return ".".join(str(n) for n in tuple(version_info)[:3])


def python_problem(version_info=None):
    """A one-line message when `version_info` is older than the scripts need, else None."""
    version_info = sys.version_info if version_info is None else version_info
    if tuple(version_info)[:2] >= MIN_PYTHON:
        return None
    return (f"Python {_dotted(version_info)} is too old: sentl-monitor needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} "
            "or later; run the script with a newer python3")


def host_sandbox(roots=SANDBOX_ROOTS):
    """The web-sandbox folders that exist on this host; empty when it is not a sandbox."""
    return [root for root in roots if os.path.isdir(root)]


def sandbox_root(path, roots=SANDBOX_ROOTS):
    """The web-sandbox folder `path` lies in, or None."""
    absolute = os.path.normpath(os.path.abspath(str(path))).replace("\\", "/")
    for root in roots:
        root = os.path.normpath(root).replace("\\", "/")
        if absolute == root or absolute.startswith(root + "/"):
            return root
    return None


def _writable(folder):
    """True when a file can be created and removed in `folder`."""
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".doctor-", delete=True):
            return True
    except OSError:
        return False


def _study_lines(study, roots, host_roots):
    path = os.path.abspath(str(study))
    label = f"Study folder {path}"
    if os.path.isdir(path):
        if _writable(path):
            lines, ok = [f"{label}: writable"], True
        else:
            lines, ok = [f"{label}: not writable; choose a folder you can write to"], False
    elif os.path.exists(path):
        lines, ok = [f"{label}: not a folder"], False
    else:
        parent = os.path.dirname(path)
        while parent and not os.path.isdir(parent) and parent != os.path.dirname(parent):
            parent = os.path.dirname(parent)
        if os.path.isdir(parent) and _writable(parent):
            lines, ok = [f"{label}: does not exist yet; it can be created under {parent}"], True
        else:
            lines, ok = [f"{label}: does not exist and cannot be created under {parent}"], False
    root = sandbox_root(path, roots)
    if root:
        lines.append(f"{label}: under {root}, a sandbox folder whose files are deleted when the "
                     "conversation ends")
    elif host_roots:
        lines.append(f"{label}: on a web sandbox, so its files are deleted when the conversation ends")
    return lines, ok


def report(study=None, version_info=None, skill_version=None, roots=SANDBOX_ROOTS):
    """The doctor's lines and whether the scripts can run here. A sandbox host is reported, not
    counted as a problem: on a web client the study is carried between conversations instead."""
    version_info = sys.version_info if version_info is None else version_info
    lines, ok = [], True
    if skill_version:
        lines.append(f"sentl-monitor {skill_version}")
    problem = python_problem(version_info)
    if problem:
        lines.append(f"Python {_dotted(version_info)}: needs {MIN_PYTHON[0]}.{MIN_PYTHON[1]} or later")
        ok = False
    else:
        lines.append(f"Python {_dotted(version_info)} ({sys.executable or 'python3'}): OK, the scripts need "
                     f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]} or later")
    lines.append(f"System: {platform.system() or 'unknown'} {platform.release()} ({platform.machine() or 'unknown'})")
    host_roots = host_sandbox(roots)
    if host_roots:
        lines.append(f"Host: a web sandbox ({' and '.join(host_roots)} exists); files written anywhere on it are "
                     "deleted when the conversation ends")
    if study is not None:
        study_lines, study_ok = _study_lines(study, roots, host_roots)
        lines += study_lines
        ok = ok and study_ok
    return lines, ok
