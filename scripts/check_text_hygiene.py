"""Check committed text for encoding damage; range whitespace uses its own gate."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys


TEXT_SUFFIXES = frozenset(
    {".cfg", ".css", ".html", ".ini", ".js", ".json", ".lock", ".md", ".ps1", ".py", ".sh", ".toml", ".txt", ".yaml", ".yml"}
)
SPECIAL_NAMES = frozenset({".gitattributes", ".gitignore", "LICENSE"})
MOJIBAKE_PATTERNS = (
    re.compile("\u00c2[\u0080-\u00bf\u00a0-\u00ff]"),
    re.compile("\u00c3[\u0080-\u00bf\u00a0-\u00ff]"),
    re.compile("\u00e2\u20ac"),
)


def check_text(path: Path) -> list[str]:
    """Return stable error strings for this tracked text file."""
    raw = path.read_bytes()
    errors: list[str] = []
    if raw.startswith(b"\xef\xbb\xbf"):
        errors.append("UTF-8 BOM")
    if b"\0" in raw:
        errors.append("NUL byte")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        errors.append("invalid UTF-8")
        return errors
    if "\ufffd" in content:
        errors.append("U+FFFD replacement character")
    if any(pattern.search(content) for pattern in MOJIBAKE_PATTERNS):
        errors.append("likely mojibake")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=False
    )
    if listed.returncode:
        print("Cannot list tracked repository files", file=sys.stderr)
        return 1
    bad: list[str] = []
    for name in (x for x in listed.stdout.decode("utf-8").split("\0") if x):
        relative = Path(name)
        if relative.suffix.lower() not in TEXT_SUFFIXES and relative.name not in SPECIAL_NAMES:
            continue
        try:
            for error in check_text(root / relative):
                bad.append(f"{name}: {error}")
        except OSError as exc:
            bad.append(f"{name}: {exc}")
    if bad:
        print("Tracked text hygiene errors:", file=sys.stderr)
        print(*bad, sep="\n", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
