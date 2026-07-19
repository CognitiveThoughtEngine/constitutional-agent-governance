"""
Tests for the release packaging checker (``scripts/check_package.py``).

Focus on the junk / credential exclusion matcher: it must reject key material
and credential files by *basename pattern* (not just exact literal names) while
leaving ordinary source and data files alone. These are release-tooling tests,
separate from the library test suite.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_MOD = Path(__file__).resolve().parent.parent / "scripts" / "check_package.py"
_spec = importlib.util.spec_from_file_location("check_package", _MOD)
assert _spec and _spec.loader
check_package = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_package)


# Should be rejected as junk / credential material.
JUNK_POSITIVE = [
    "pkg/server.pem",
    "pkg/private.key",
    "certs/cert.p12",
    "a/b/cert.pfx",
    "keystore.jks",
    "my.keystore",
    "pkg/id_rsa",
    "pkg/id_rsa.pub",
    "pkg/id_rsa.bak",
    "home/.ssh/id_ed25519",
    "config/credentials.json",
    "svc/service-account.json",
    "svc/service_account.json",
    "gcp-credentials.json",
    "pkg/__pycache__/mod.pyc",
    ".venv/lib/site-packages/x.py",
    "build/lib/x.py",
    "dist/x.whl",
    "x.pyo",
    ".DS_Store",
    ".env.local",
    ".mypy_cache/x",
]

# Should NOT be flagged — ordinary source / data / packaging files.
JUNK_NEGATIVE = [
    "constitutional_agent/schema.py",
    "constitutional_agent/keyring.py",       # 'key' substring, but a .py module
    "src/monkey.py",                         # 'key' substring, ordinary module
    "README.md",
    "pyproject.toml",
    "governance.yaml",
    "data.json",                             # plain json, not a credential file
    "docs/keystore_design.md",               # 'keystore' substring, but .md
    "constitutional_agent-0.7.0.dist-info/METADATA",
    "constitutional_agent-0.7.0.dist-info/licenses/LICENSE",
]


@pytest.mark.parametrize("name", JUNK_POSITIVE)
def test_credential_and_junk_rejected(name: str) -> None:
    assert check_package._junk(name), f"{name!r} should be flagged as junk/credential"


@pytest.mark.parametrize("name", JUNK_NEGATIVE)
def test_clean_files_not_flagged(name: str) -> None:
    assert not check_package._junk(name), f"{name!r} should NOT be flagged"
