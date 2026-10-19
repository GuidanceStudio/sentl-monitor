"""No real name, no token and no home-directory path in any file of the repository.

The repository is public. Each check reads every file git tracks plus the
untracked files .gitignore does not exclude, and skips files that are not
UTF-8 text. A hit is reported as `path:line` with what was found, never with
the matched text, so a failing run prints no name and no secret.

The denied names are not in the repository in any form: a list of names, or of
their unsalted digests, would disclose them to anyone who guesses one. The
list is read from a file outside it, named by the SKILL_DENYLIST variable or,
when unset, ~/.config/skill-denylist/digests.txt. Each line holds a name, or
the sha256 digest of a name lowercased with accents stripped and words joined
by one space; `#` starts a comment. Without the file the name check is
skipped; the token and path checks still run.
"""

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DENYLIST_ENV = "SKILL_DENYLIST"
DIGEST = re.compile(r"[0-9a-fA-F]{64}")

# The value must start with a letter or digit, so `<REPLACE_WITH_TOKEN>` and
# `$SENTL_TOKEN` pass, and so does prose where a backtick follows the scheme.
TOKEN_PATTERNS = (
    ("bearer header", re.compile(
        r"authorization['\"]?\s*[:=]\s*['\"]?bearer[ \t]+['\"`]?[A-Za-z0-9][A-Za-z0-9._~+/=-]{7,}", re.I)),
    ("sk key", re.compile(r"(?<![A-Za-z0-9])sk[-_][A-Za-z0-9_-]{20,}")),
    ("github token", re.compile(r"(?<![A-Za-z0-9])(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})")),
)
HEX_RUN = re.compile(r"(?<![0-9A-Za-z])[0-9a-fA-F]{40,}(?![0-9A-Za-z])")
B64URL_RUN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z0-9_-]{40,}(?![A-Za-z0-9_-])")

# A path segment before the slash means a URL or a deeper path, not a home directory.
HOME_PATH_PATTERNS = (
    re.compile(r"(?<![\w.-])/home/[A-Za-z0-9._-]+"),
    re.compile(r"(?<![\w.-])/Users/[A-Za-z0-9._-]+"),
    re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]+Users[\\/]+[A-Za-z0-9._-]+"),
)


def digest(name):
    return hashlib.sha256(name.encode()).hexdigest()


def normalised(name):
    """`name` lowercased, without accents, its words joined by one space."""
    return " ".join(tok for tok, _ in tokens_with_lines(name))


def denylist_path(environ=os.environ):
    return environ.get(DENYLIST_ENV) or os.path.join(os.path.expanduser("~"), ".config", "skill-denylist",
                                                     "digests.txt")


def load_denylist(path):
    """The digests the file at `path` lists, a name hashed in its normalised form; None when it is missing."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return None
    entries = (line.split("#", 1)[0].strip() for line in lines)
    return frozenset(e.lower() if DIGEST.fullmatch(e) else digest(normalised(e)) for e in entries if e)


def tokens_with_lines(text):
    """Word tokens of `text`, lowercased and without accents, each with its line number."""
    text = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()
    return [(tok, n) for n, line in enumerate(text.split("\n"), 1) for tok in re.findall(r"[a-z0-9]+", line)]


def deny_listed(text, deny, seen, longest=3):
    """(line, phrase) for every run of 1..`longest` consecutive tokens whose digest is in `deny`.

    A name of several words matches across a line break, the way prose wraps it.
    `seen` caches the verdict per phrase across files.
    """
    toks = tokens_with_lines(text)
    hits = []
    for i, (_, line) in enumerate(toks):
        for n in range(1, min(longest, len(toks) - i) + 1):
            phrase = " ".join(t for t, _ in toks[i:i + n])
            if phrase not in seen:
                seen[phrase] = digest(phrase) in deny
            if seen[phrase]:
                hits.append((line, phrase))
    return hits


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def token_shaped(text):
    """(line, kind) for every string in `text` shaped like a credential."""
    hits = [(line_of(text, m.start()), kind) for kind, rx in TOKEN_PATTERNS for m in rx.finditer(text)]
    hits += [(line_of(text, m.start()), "hex run") for m in HEX_RUN.finditer(text)]
    # Requiring upper case, lower case and a digit keeps long snake_case identifiers out.
    hits += [(line_of(text, m.start()), "base64url run") for m in B64URL_RUN.finditer(text)
             if not HEX_RUN.fullmatch(m.group(0))
             and re.search(r"[A-Z]", m.group(0)) and re.search(r"[a-z]", m.group(0))
             and re.search(r"[0-9]", m.group(0))]
    return sorted(set(hits))


def home_paths(text):
    """(line, kind) for every home-directory path in `text`."""
    return sorted({(line_of(text, m.start()), "home directory path")
                   for rx in HOME_PATH_PATTERNS for m in rx.finditer(text)})


def repo_files(root):
    """Paths relative to `root` of the files git tracks and the untracked files it does not ignore."""
    paths = set()
    for extra in ([], ["--others", "--exclude-standard"]):
        out = subprocess.run(["git", "-C", root, "ls-files", "-z", *extra],
                             capture_output=True, check=True).stdout
        paths.update(p for p in out.decode("utf-8", "surrogateescape").split("\0") if p)
    return sorted(paths)


def read_text(path):
    """The file's text, or None when it is missing, a directory, binary, or not UTF-8."""
    try:
        with open(path, "rb") as fh:
            data = fh.read()
    except (FileNotFoundError, IsADirectoryError):
        return None
    if b"\0" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def scan(root, files, find):
    """`path:line: what` for every (line, what) that `find` returns on a readable file."""
    found = []
    for rel in files:
        text = read_text(os.path.join(root, rel))
        if text is not None:
            found += [f"{rel}:{line}: {what}" for line, what in find(text)]
    return found


def names_finder(deny):
    seen = {}
    return lambda text: [(line, digest(phrase)[:8]) for line, phrase in deny_listed(text, deny, seen)]


class RepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = repo_files(REPO_ROOT)

    def test_no_deny_listed_name(self):
        deny = load_denylist(denylist_path())
        if deny is None:
            self.skipTest(f"no deny-list file; set {DENYLIST_ENV} to check names")
        found = scan(REPO_ROOT, self.files, names_finder(deny))
        self.assertEqual(found, [], "deny-listed names (digest prefix shown); replace them with fictional ones:\n"
                         + "\n".join(found))

    def test_no_token_shaped_string(self):
        found = scan(REPO_ROOT, self.files, token_shaped)
        self.assertEqual(found, [], "token-shaped strings; use an angle-bracket placeholder such as "
                         "<REPLACE_WITH_TOKEN>:\n" + "\n".join(found))

    def test_no_home_directory_path(self):
        found = scan(REPO_ROOT, self.files, home_paths)
        self.assertEqual(found, [], "home-directory paths; use a relative path or ~:\n" + "\n".join(found))


class NamesFinderTest(unittest.TestCase):
    """The name check on planted, invented names, so it is proven without naming anyone real."""

    DENY = frozenset({digest("zorblax"), digest("casa velbrun")})

    def test_a_name_is_found_in_any_case_and_with_accents(self):
        find = names_finder(self.DENY)
        self.assertEqual(find('{"label": "Zorblàx"}\nsee ZORBLAX.example\n'),
                         [(1, digest("zorblax")[:8]), (2, digest("zorblax")[:8])])

    def test_a_name_of_two_words_is_found_across_a_line_break(self):
        self.assertEqual(names_finder(self.DENY)("brands such as Casa\nVelbrun and others\n"),
                         [(1, digest("casa velbrun")[:8])])

    def test_a_name_inside_a_longer_word_is_not_a_match(self):
        self.assertEqual(names_finder(self.DENY)("zorblaxes and prezorblax\n"), [])

    def test_the_report_carries_the_digest_prefix_and_not_the_name(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        with open(os.path.join(root, "doc.md"), "w", encoding="utf-8") as fh:
            fh.write("intro\nmade by Zorblax\n")
        found = scan(root, ["doc.md"], names_finder(self.DENY))
        self.assertEqual(found, [f"doc.md:2: {digest('zorblax')[:8]}"])
        self.assertNotIn("zorblax", found[0].lower())


class DenylistFileTest(unittest.TestCase):
    """The list is read from a file outside the repository, so the repository holds no name in any form."""

    def write(self, text):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        path = os.path.join(root, "digests.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_digests_and_names_are_read_and_comments_skipped(self):
        path = self.write(f"# planted names\n{digest('zorblax').upper()}\n\n  Casa   Velbrùn  \n")
        self.assertEqual(load_denylist(path), frozenset({digest("zorblax"), digest("casa velbrun")}))

    def test_a_missing_file_gives_no_list(self):
        self.assertIsNone(load_denylist(os.path.join(tempfile.gettempdir(), "no-such-dir-x7", "digests.txt")))

    def test_the_variable_names_the_file_and_the_default_is_under_the_user_config(self):
        path = self.write("zorblax\n")
        self.assertEqual(denylist_path({DENYLIST_ENV: path}), path)
        self.assertEqual(denylist_path({}),
                         os.path.join(os.path.expanduser("~"), ".config", "skill-denylist", "digests.txt"))

    def test_this_file_holds_no_digest(self):
        with open(os.path.abspath(__file__), encoding="utf-8") as fh:
            self.assertIsNone(re.search(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", fh.read()))


class TokenShapedTest(unittest.TestCase):
    # Built at run time so this file holds no string the check would flag.
    SK = "sk" + "-" + "a1B2c3D4" * 3
    GH = "gh" + "p_" + "a1B2c3D4" * 3
    PAT = "github" + "_pat_" + "a1B2c3D4" * 3
    HEX = "0123456789abcdef" * 3
    B64 = "aB3dE6gH9-" * 5
    BEARER = "Authorization: " + "Bearer "

    def kinds(self, text):
        return [kind for _, kind in token_shaped(text)]

    def test_each_shape_is_found_with_its_line(self):
        text = "\n".join([f"key = {self.SK}", f"token: {self.GH}", self.PAT, f"id {self.HEX}", f"x {self.B64}",
                          f"curl -H '{self.BEARER}abcdef123456'"])
        self.assertEqual(token_shaped(text), [(1, "sk key"), (2, "github token"), (3, "github token"),
                                              (4, "hex run"), (5, "base64url run"), (6, "bearer header")])

    def test_a_json_header_with_a_literal_value_is_found(self):
        self.assertEqual(self.kinds('{"Authorization": "' + "Bear" + 'er abcdef123456"}'), ["bearer header"])

    def test_placeholders_and_variables_pass(self):
        for text in ["Authorization: Bearer <REPLACE_WITH_TOKEN>", "-H 'Authorization: Bearer $SENTL_TOKEN'",
                     "pass it as an `Authorization: Bearer` header", "Authorization: Bearer ${SENTL_TOKEN}"]:
            self.assertEqual(self.kinds(text), [], text)

    def test_long_identifiers_and_rules_pass(self):
        for text in ["def test_a_name_of_two_words_is_found_across_a_line_break(self):", "-" * 60,
                     "NoRealNamesTestCaseWithAVeryLongCamelCaseIdentifierName",
                     "risk_assessment_dimension_with_a_long_key_name", "sk-short"]:
            self.assertEqual(self.kinds(text), [], text)


class HomePathTest(unittest.TestCase):
    # Built at run time so this file holds no path the check would flag.
    LINUX = "/" + "home/alice/notes.md"
    MAC = "/" + "Users/alice/Desktop"
    WINDOWS = "C:" + "\\" + "Users\\alice\\study"

    def test_each_platform_is_found_with_its_line(self):
        text = f"open {self.LINUX}\n`{self.MAC}`\n\"{self.WINDOWS}\"\n"
        self.assertEqual(home_paths(text), [(1, "home directory path"), (2, "home directory path"),
                                            (3, "home directory path")])

    def test_home_relative_paths_placeholders_and_urls_pass(self):
        for text in ["~/.claude/skills/sentl-monitor", "/" + "home/<you>/studies",
                     "https://example.com/" + "home/page", "studies/" + "home/x"]:
            self.assertEqual(home_paths(text), [], text)


class RepoFilesTest(unittest.TestCase):
    def test_tracked_and_untracked_files_are_listed_and_ignored_ones_are_not(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        subprocess.run(["git", "init", "-q", root], check=True)
        files = {".gitignore": "/studies/\n", "tracked.md": "a\n", "untracked.md": "b\n", "studies/s.md": "c\n"}
        for rel, text in files.items():
            os.makedirs(os.path.dirname(os.path.join(root, rel)), exist_ok=True)
            with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                fh.write(text)
        subprocess.run(["git", "-C", root, "add", ".gitignore", "tracked.md"], check=True)
        self.assertEqual(repo_files(root), [".gitignore", "tracked.md", "untracked.md"])

    def test_binary_and_non_utf8_files_are_skipped(self):
        root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, root)
        for rel, data in {"a.bin": b"x\0" + self.hex_bytes(), "b.txt": b"\xff\xfe" + self.hex_bytes()}.items():
            with open(os.path.join(root, rel), "wb") as fh:
                fh.write(data)
        self.assertEqual(scan(root, ["a.bin", "b.txt", "missing.md"], token_shaped), [])

    @staticmethod
    def hex_bytes():
        return ("0123456789abcdef" * 3).encode()


if __name__ == "__main__":
    unittest.main()
