"""Smoke the packaged CLI's bundled offline User Guide without opening a GUI."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys


def check_user_guide(executable: Path, help_root: Path, language_option: str) -> None:
    executable = executable.resolve()
    help_root = help_root.resolve()
    # Use an echo browser to observe the exact file URI from the real executable.
    browser = f'"{Path(sys.executable).as_posix()}" -c "print(__import__(\'sys\').argv[1])" %s'
    environment = {**os.environ, "BROWSER": browser}
    for options, filename in (((), "cli.html"), ((language_option, "zh-TW"), "cli.zh-TW.html")):
        expected_file = help_root / filename
        if not expected_file.is_file():
            raise AssertionError(f"Missing packaged CLI Help: {expected_file}")
        result = subprocess.run(
            [str(executable), "user-guide", *options],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
            timeout=45,
            check=False,
        )
        expected_uri = expected_file.as_uri()
        if result.returncode != 0 or result.stdout.strip() != expected_uri:
            raise AssertionError(
                f"Packaged CLI User Guide failed for {filename}: "
                f"exit={result.returncode}, expected={expected_uri!r}, "
                f"stdout={result.stdout[-1000:]!r}, stderr={result.stderr[-1000:]!r}"
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", required=True, type=Path)
    parser.add_argument("--help-root", required=True, type=Path)
    parser.add_argument("--language-option", choices=("--lang", "--language"), required=True)
    args = parser.parse_args()
    check_user_guide(args.exe, args.help_root, args.language_option)
    print("Packaged CLI User Guide smoke passed (en, zh-TW)")


if __name__ == "__main__":
    main()
