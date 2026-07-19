#!/usr/bin/env python3
"""
Release smoke test for constitutional-agent.

Run against an INSTALLED build (wheel) in a fresh environment — NOT the source
tree — to prove the packaged artifact imports and enforces its core guarantees:

  1. imports (top-level + every public submodule) and version == pinned
  2. CLI entry point (`python -m constitutional_agent`) runs and exits 0
  3. authority enforcement — separation of duty rejects a self-ratify; a
     distinct registered ratifier succeeds
  4. FRIA-support output — `fria_support_package` returns the labelled artifact
     with the Article 27 applicability + reviewed-readiness fields
  5. durable-store restart — a ratified amendment persists to a SqliteAmendmentStore
     and `constitution_version` is reconstructed by a fresh Constitution instance

Exits non-zero on the first failed check. Intended for CI after `pip install`
of the built wheel, and locally for release validation.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

EXPECTED_VERSION = "0.7.0"

REGISTRY = {
    "root-a": "CONSTITUTIONAL_AUTHORITY",
    "ratifier-1": "RATIFIER",
    "proposer-1": "PROPOSER",
}
ORDINARY_CHANGE = {"gates": {"epistemic": {"hold_threshold": 0.65}}}


def _check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f" — {detail}" if detail else ""))
    if not ok:
        raise SystemExit(f"smoke test failed at: {label}")


def main() -> int:
    print("constitutional-agent release smoke test")

    # 1. imports + version
    import constitutional_agent as ca
    from constitutional_agent import (  # noqa: F401  (import-surface check)
        AuthorityLevel,
        AuthorityRegistry,
        ComposedEvaluator,
        Constitution,
        ConstitutionIntegrityError,
        SixGateEvaluator,
        SqliteAmendmentStore,
        bounded_verifier,
        fria_support_package,
        redact_secrets,
    )

    _check("import + version", ca.__version__ == EXPECTED_VERSION,
           f"__version__={ca.__version__}")

    # 2. CLI entry point
    proc = subprocess.run(
        [sys.executable, "-m", "constitutional_agent"],
        capture_output=True, text=True,
    )
    _check("CLI `python -m constitutional_agent` exits 0",
           proc.returncode == 0, f"rc={proc.returncode}")
    _check("CLI emits a system state", "System state" in proc.stdout)

    # 3. authority enforcement — separation of duty (two independent proposals,
    #    because a rejected proposal is terminal and cannot be re-ratified)
    c = Constitution(config={}, authority_registry=dict(REGISTRY))

    aid_self = c.propose_amendment(
        description="self", rationale="r", affected_sections=["EpistemicGate"],
        proposed_by="proposer-1", changes=ORDINARY_CHANGE)
    self_ratify = c.ratify_amendment(aid_self, ratified_by="proposer-1")
    _check("self-ratify is rejected (separation of duty)", self_ratify is False)

    aid_ok = c.propose_amendment(
        description="ok", rationale="r", affected_sections=["EpistemicGate"],
        proposed_by="proposer-1", changes=ORDINARY_CHANGE)
    good_ratify = c.ratify_amendment(aid_ok, ratified_by="ratifier-1")
    _check("distinct registered ratifier succeeds", good_ratify is True)

    stranger = Constitution(config={}, authority_registry=dict(REGISTRY))
    aid_s = stranger.propose_amendment(
        description="s", rationale="r", affected_sections=["EpistemicGate"],
        proposed_by="proposer-1", changes=ORDINARY_CHANGE)
    _check("unregistered ratifier is rejected",
           stranger.ratify_amendment(aid_s, ratified_by="nobody") is False)

    # 4. FRIA-support output
    pkg = fria_support_package([], [])
    blob = json.dumps(pkg)
    _check("FRIA-support artifact label", pkg.get("artifact") == "FRIA-support package")
    _check("Article 27 applicability present", "article_27_applicability" in pkg)
    _check("reviewed-readiness key present",
           "crosswalk_fields_present_and_reviewed" in blob)

    # 5. durable-store restart — version reconstructed across instances
    workdir = tempfile.mkdtemp()
    db_path = os.path.join(workdir, "amendments.db")

    c1 = Constitution(config={}, authority_registry=dict(REGISTRY),
                      amendment_store=SqliteAmendmentStore(db_path))
    aid_d = c1.propose_amendment(
        description="durable", rationale="r", affected_sections=["EpistemicGate"],
        proposed_by="proposer-1", changes=ORDINARY_CHANGE)
    _check("durable amendment ratifies",
           c1.ratify_amendment(aid_d, ratified_by="ratifier-1") is True)
    version_before = c1.constitution_version
    _check("version advanced after ratification", version_before >= 1,
           f"version={version_before}")

    c2 = Constitution(config={}, authority_registry=dict(REGISTRY),
                      amendment_store=SqliteAmendmentStore(db_path))
    _check("version reconstructed on restart from durable store",
           c2.constitution_version == version_before,
           f"restart_version={c2.constitution_version}")

    print("\nAll release smoke checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
