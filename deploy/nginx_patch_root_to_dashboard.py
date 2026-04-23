#!/usr/bin/env python3
"""
Patch an nginx site config: in each server block with listen 443 and brimit.de,
remove location / blocks whose proxy_pass targets port 8000, then add
  include /etc/nginx/snippets/watchmatch-root-dashboard.conf;
if missing. Backup: <path>.bak.<timestamp>
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

INCLUDE_LINE = "    include /etc/nginx/snippets/watchmatch-root-dashboard.conf;\n"
MARKER = "watchmatch-root-dashboard.conf"


def find_server_blocks(text: str) -> list[tuple[int, int]]:
    """Return (start, end) indices with end exclusive, for each `server { ... }` at file level."""
    blocks: list[tuple[int, int]] = []
    pos = 0
    while True:
        m = re.search(r"\bserver\s*\{", text[pos:])
        if not m:
            break
        start = pos + m.start()
        brace = text.find("{", start)
        if brace == -1:
            break
        i = brace + 1
        depth = 1
        while i < len(text) and depth > 0:
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
            i += 1
        if depth != 0:
            raise SystemExit("unbalanced braces while parsing server blocks")
        blocks.append((start, i))
        pos = i
    return blocks


def remove_root_locations_proxy_8000(inner: str) -> str:
    """Remove `location /` or `location = /` blocks that proxy to port 8000."""

    def scan() -> str:
        s = inner
        changed = True
        while changed:
            changed = False
            for m in re.finditer(r"(?m)^[ \t]*location\s*(?:=\s*)?/\s*\{", s):
                start = m.start()
                brace = s.find("{", m.start())
                if brace == -1:
                    continue
                i = brace + 1
                depth = 1
                while i < len(s) and depth > 0:
                    if s[i] == "{":
                        depth += 1
                    elif s[i] == "}":
                        depth -= 1
                    i += 1
                if depth != 0:
                    continue
                block = s[start:i]
                if "proxy_pass" not in block or "8000" not in block:
                    continue
                s = s[:start] + s[i:]
                changed = True
                break
        return s

    return scan()


def patch_server_inner(inner: str) -> str | None:
    """
    Return patched inner body, or None if this server{} should not be touched.
    """
    if not re.search(r"listen\s+443", inner):
        return None
    if "brimit.de" not in inner:
        return None
    inner2 = remove_root_locations_proxy_8000(inner)
    if MARKER in inner2:
        return inner2 if inner2 != inner else inner
    return inner2.rstrip() + "\n" + INCLUDE_LINE


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} /etc/nginx/sites-available/YOUR_SITE")

    path = Path(sys.argv[1])
    if not path.is_file():
        raise SystemExit(f"not a file: {path}")

    text = path.read_text(encoding="utf-8")
    blocks = find_server_blocks(text)
    if not blocks:
        raise SystemExit("no server { } blocks found")

    out_parts: list[str] = []
    last = 0
    modified = False
    for start, end in blocks:
        out_parts.append(text[last:start])
        block = text[start:end]
        inner_start = block.find("{") + 1
        prefix = block[:inner_start]
        inner = block[inner_start:-1]
        suffix = block[-1:]
        patched = patch_server_inner(inner)
        if patched is None:
            out_parts.append(block)
        elif patched != inner:
            modified = True
            out_parts.append(prefix + patched + suffix)
        else:
            out_parts.append(block)
        last = end
    out_parts.append(text[last:])
    new_text = "".join(out_parts)

    if not modified:
        print("nginx_patch: no changes (already patched or no matching 443 + brimit.de server, or no root location -> 8000).")
        return

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bak = path.with_suffix(path.suffix + f".bak.{ts}")
    shutil.copy2(path, bak)
    path.write_text(new_text, encoding="utf-8")
    print(f"nginx_patch: updated {path} (backup {bak})")


if __name__ == "__main__":
    main()
