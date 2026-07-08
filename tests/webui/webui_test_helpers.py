from __future__ import annotations

import re
from pathlib import Path


STATIC_DIR = Path(__file__).parents[2] / "src" / "meters_tool_webui" / "static"


def load_static_ui():
    javascript = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(STATIC_DIR.glob("*.js"))
    )
    return (
        (STATIC_DIR / "index.html").read_text(encoding="utf-8"),
        javascript,
    )


def assert_tag_with_attrs(testcase, html, tag, attrs):
    lookaheads = "".join(
        rf"(?=[^>]*\b{re.escape(name)}=\"{re.escape(value)}\")"
        for name, value in attrs.items()
    )
    testcase.assertRegex(html, rf"<{tag}\b{lookaheads}[^>]*>")
