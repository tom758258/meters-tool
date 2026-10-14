"""Check committed whitespace only across a trustworthy event range."""

from __future__ import annotations

import os
import re
import subprocess
import sys


ZERO_SHA_PATTERN = re.compile(r"^0+$")


def _git(*args: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        text=True,
        capture_output=capture_output,
        check=False,
    )


def _resolve_commit(value: str) -> str | None:
    if not value:
        return None
    result = _git("rev-parse", "--verify", f"{value}^{{commit}}", capture_output=True)
    if result.returncode != 0:
        return None
    commit = result.stdout.strip()
    return commit or None


def _fail(reason: str) -> int:
    print(
        "Whitespace validation could not establish a trustworthy changed range: " + reason,
        file=sys.stderr,
    )
    return 1


def _check_target_fallback(target: str, context: str) -> int:
    ancestry = _git("rev-list", "--parents", "--max-count=1", target, capture_output=True)
    if ancestry.returncode != 0:
        return _fail(f"could not inspect the {context} target commit {target}")

    commits = ancestry.stdout.split()
    if not commits or commits[0] != target:
        return _fail(f"could not verify the {context} target ancestry for {target}")

    if len(commits) > 1:
        print(f"Checking {context} parent-to-target fallback: {target}^..{target}", file=sys.stderr)
        return _git("diff", "--check", f"{target}^", target).returncode

    print(f"Checking {context} root-commit fallback: {target}", file=sys.stderr)
    return _git("diff-tree", "--check", "--root", "-r", target).returncode


def _check_pull_request() -> int:
    base_value = os.environ.get("PR_BASE_SHA", "")
    head_value = os.environ.get("PR_HEAD_SHA", "")
    base = _resolve_commit(base_value)
    head = _resolve_commit(head_value)
    if base is None:
        return _fail(f"PR base SHA is unavailable or invalid: {base_value or '<empty>'}")
    if head is None:
        return _fail(f"PR head SHA is unavailable or invalid: {head_value or '<empty>'}")

    merge_base_result = _git("merge-base", base, head, capture_output=True)
    merge_base = merge_base_result.stdout.strip()
    if merge_base_result.returncode != 0 or _resolve_commit(merge_base) is None:
        return _fail(f"no PR merge base exists for {base} and {head}")

    print(f"Checking PR merge-base range: {merge_base}..{head}", file=sys.stderr)
    return _git("diff", "--check", merge_base, head).returncode


def _check_push() -> int:
    before_value = os.environ.get("PUSH_BEFORE", "")
    target_value = os.environ.get("PUSH_SHA", "")
    target = _resolve_commit(target_value)
    if target is None:
        return _fail(f"push target SHA is unavailable or invalid: {target_value or '<empty>'}")

    before = None if ZERO_SHA_PATTERN.fullmatch(before_value) else _resolve_commit(before_value)
    if before is not None:
        print(f"Checking push changed range: {before}..{target}", file=sys.stderr)
        return _git("diff", "--check", before, target).returncode

    return _check_target_fallback(target, "push")


def main() -> int:
    event_name = os.environ.get("EVENT_NAME", "")
    if event_name == "pull_request":
        return _check_pull_request()
    if event_name == "push":
        return _check_push()
    return _fail(f"unsupported event: {event_name or '<empty>'}")


if __name__ == "__main__":
    raise SystemExit(main())
