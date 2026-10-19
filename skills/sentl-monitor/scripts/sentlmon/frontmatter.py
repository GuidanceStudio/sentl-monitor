"""SKILL.md's frontmatter, read with the standard library.

It reads the subset of YAML the file uses: plain, single- and double-quoted scalars, folded
(`>`, `>-`) and literal (`|`, `|-`) blocks, and one level of nested mapping (`metadata`).
SKILL.md's `metadata.version` is the skill's one version: `monitor.py --version` prints it
and `tools/build_zip.py` checks it.
"""

import json
from pathlib import Path

SKILL_MD = Path(__file__).resolve().parents[2] / "SKILL.md"


class Malformed(ValueError):
    """A frontmatter this reader cannot read."""


def _scalar(value):
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return json.loads(value)
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _block(style, lines):
    while lines and not lines[-1]:
        lines.pop()
    if style.startswith("|"):
        text = "\n".join(lines)
    else:
        paragraphs, current = [], []
        for line in lines:
            if line:
                current.append(line)
            else:
                paragraphs.append(" ".join(current))
                current = []
        paragraphs.append(" ".join(current))
        text = "\n".join(p for p in paragraphs if p)
    return text if style.endswith("-") else text + "\n"


def parse(text):
    """The frontmatter of `text` as a dict; a nested mapping is a dict of strings."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0] != "---":
        raise Malformed("SKILL.md does not open with a '---' line")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise Malformed("SKILL.md's frontmatter has no closing '---' line") from None
    data, block, block_key, block_style, nested = {}, None, None, None, None

    def close_block():
        if block is not None:
            data[block_key] = _block(block_style, block)

    for number, line in enumerate(lines[1:end], 2):
        if block is not None and (line.startswith(" ") or not line.strip()):
            block.append(line.strip())
            continue
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" "):
            if nested is None or ":" not in line:
                raise Malformed(f"SKILL.md line {number}: an indented line outside a block or a mapping")
            key, value = line.strip().split(":", 1)
            nested[key.strip()] = _scalar(value)
            continue
        close_block()
        block = nested = None
        if ":" not in line:
            raise Malformed(f"SKILL.md line {number}: expected 'key: value'")
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if value in (">", ">-", "|", "|-"):
            block, block_key, block_style = [], key, value
        elif value == "":
            nested = data[key] = {}
        else:
            data[key] = _scalar(value)
    close_block()
    return data


def read(path=SKILL_MD):
    return parse(Path(path).read_text(encoding="utf-8"))


def version(path=SKILL_MD):
    """The skill's version, from SKILL.md's `metadata.version`."""
    meta = read(path).get("metadata")
    if not isinstance(meta, dict) or not meta.get("version"):
        raise Malformed("SKILL.md declares no metadata.version")
    return meta["version"]
