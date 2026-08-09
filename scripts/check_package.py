#!/usr/bin/env python3
"""
Enforce package metadata and archive contents for a built distribution.

Unlike a print-only inspection, every expectation here is a hard check that
exits non-zero on violation (no `assert` — asserts are stripped under
``python -O``). Run against a freshly built ``dist/`` before publishing.

Checks:
  * wheel METADATA — Name, Version, Requires-Python, License, and all four
    Project-URLs match exactly.
  * wheel contents — allowlisted to the package tree + ``*.dist-info`` only;
    no tests, caches, build output, credentials, or other junk.
  * sdist contents — must contain the source tree + packaging metadata; must
    not contain caches, virtualenvs, build/dist output, or credentials.

Usage: python scripts/check_package.py dist/
"""
from __future__ import annotations

import email
import glob
import re
import sys
import tarfile
import zipfile

NAME = "constitutional-agent"
VERSION = "0.8.0"
DIST_INFO = f"constitutional_agent-{VERSION}.dist-info/"
PKG_PREFIX = "constitutional_agent/"
REQUIRES_PYTHON_MUST_CONTAIN = ">=3.11"
LICENSE_TOKEN = "MIT"
EXPECTED_URLS = {
    "Homepage": "https://github.com/CognitiveThoughtEngine/constitutional-agent-governance",
    "Documentation": "https://github.com/CognitiveThoughtEngine/constitutional-agent-governance#readme",
    "Repository": "https://github.com/CognitiveThoughtEngine/constitutional-agent-governance",
    "Issues": "https://github.com/CognitiveThoughtEngine/constitutional-agent-governance/issues",
}

# Any archive member matching one of these is forbidden (caches, build output,
# virtualenvs, credentials, editor/OS cruft, compiled artifacts).
JUNK_PATTERNS = [
    r"(^|/)__pycache__(/|$)",
    r"\.py[co]$",
    r"(^|/)\.venv(/|$)",
    r"(^|/)venv(/|$)",
    r"(^|/)node_modules(/|$)",
    r"(^|/)\.git(/|$)",
    r"(^|/)\.DS_Store$",
    r"(^|/)\.env($|\.)",
    # credential / key material — match the whole basename, not just exact names,
    # so server.pem / private.key / id_rsa.bak / gcp-credentials.json are caught.
    r"\.(pem|key|p12|pfx|jks|keystore)$",
    r"(^|/)id_rsa",
    r"(^|/)id_ed25519",
    r"(^|/)[^/]*(credential|credentials|service[-_]account)[^/]*\.json$",
    r"(^|/)build/",
    r"(^|/)dist/",
    r"(^|/)\.pytest_cache(/|$)",
    r"(^|/)\.mypy_cache(/|$)",
    r"(^|/)\.ruff_cache(/|$)",
]
# Case-insensitive so SERVER.PEM / Private.KEY / GCP-Credentials.JSON can't bypass.
_JUNK = [re.compile(p, re.IGNORECASE) for p in JUNK_PATTERNS]

errors: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def _find(distdir: str, pattern: str) -> str:
    hits = glob.glob(f"{distdir.rstrip('/')}/{pattern}")
    if len(hits) != 1:
        fail(f"expected exactly one {pattern} in {distdir}, found {len(hits)}: {hits}")
        return ""
    return hits[0]


def _junk(name: str) -> bool:
    return any(rx.search(name) for rx in _JUNK)


def check_wheel_metadata(whl: str) -> None:
    with zipfile.ZipFile(whl) as z:
        meta_names = [n for n in z.namelist() if n.endswith(".dist-info/METADATA")]
        if not meta_names:
            fail("wheel has no METADATA")
            return
        msg = email.message_from_bytes(z.read(meta_names[0]))

    if msg["Name"] != NAME:
        fail(f"Name: expected {NAME!r}, got {msg['Name']!r}")
    if msg["Version"] != VERSION:
        fail(f"Version: expected {VERSION!r}, got {msg['Version']!r}")
    rp = msg["Requires-Python"] or ""
    if REQUIRES_PYTHON_MUST_CONTAIN not in rp:
        fail(f"Requires-Python: expected to contain {REQUIRES_PYTHON_MUST_CONTAIN!r}, got {rp!r}")
    lic = (msg["License"] or "") + " " + (msg["License-Expression"] or "")
    if LICENSE_TOKEN not in lic:
        fail(f"License: expected to contain {LICENSE_TOKEN!r}, got {lic.strip()!r}")

    urls: dict[str, str] = {}
    for _, v in [(k, v) for k, v in msg.items() if k == "Project-URL"]:
        label, _, target = v.partition(",")
        urls[label.strip()] = target.strip()
    for label, want in EXPECTED_URLS.items():
        got = urls.get(label)
        if got != want:
            fail(f"Project-URL {label!r}: expected {want!r}, got {got!r}")


def check_wheel_contents(whl: str) -> None:
    with zipfile.ZipFile(whl) as z:
        names = z.namelist()
    for n in names:
        if n.endswith("/"):
            continue
        if not (n.startswith(PKG_PREFIX) or n.startswith(DIST_INFO)):
            fail(f"wheel: unexpected member outside package/dist-info: {n}")
        if _junk(n):
            fail(f"wheel: junk member: {n}")
        if "/tests/" in f"/{n}" or n.startswith("tests/"):
            fail(f"wheel: test file must not ship in wheel: {n}")


def check_sdist_contents(sdist: str) -> None:
    with tarfile.open(sdist) as t:
        names = t.getnames()
    root = f"constitutional_agent-{VERSION}"
    required = [f"{root}/pyproject.toml", f"{root}/PKG-INFO",
               f"{root}/src/constitutional_agent/__init__.py"]
    for r in required:
        if r not in names:
            fail(f"sdist: missing required member: {r}")
    for n in names:
        if _junk(n):
            fail(f"sdist: junk member: {n}")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: check_package.py <dist-dir>", file=sys.stderr)
        return 2
    distdir = sys.argv[1]
    whl = _find(distdir, "*.whl")
    sdist = _find(distdir, "*.tar.gz")
    if whl:
        check_wheel_metadata(whl)
        check_wheel_contents(whl)
    if sdist:
        check_sdist_contents(sdist)

    if errors:
        print("PACKAGE CHECK FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"package check PASSED: {NAME} {VERSION} — metadata, URLs, and "
          f"wheel/sdist contents all conform")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
