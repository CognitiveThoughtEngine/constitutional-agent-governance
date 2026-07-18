"""
Amendment authority & separation-of-duties enforcement (v0.7.0).

Covers every enforcement path in ``Constitution.ratify_amendment`` plus the
reviewer-required edge cases: identity normalization, understated affected
paths, concurrent last-authority demotion, callback timeout/exception/malformed
responses, bootstrap irreversibility, replay rejection, registry-change
authority, and complete amendment-record provenance with no secrets stored.
"""

from __future__ import annotations

import json
import threading

import pytest

from constitutional_agent import Constitution
from constitutional_agent.authority import (
    AuthorityLevel,
    AuthorityRegistry,
    IdentityVerifier,
    SqliteAmendmentStore,
    canonical_principal,
    scrub_evidence,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

REGISTRY = {
    "root-a": "CONSTITUTIONAL_AUTHORITY",
    "root-b": "CONSTITUTIONAL_AUTHORITY",
    "ratifier-1": "RATIFIER",
    "proposer-1": "PROPOSER",
}


def _c(**kwargs) -> Constitution:
    """Constitution with the standard two-root authority registry."""
    return Constitution(config={}, authority_registry=dict(REGISTRY), **kwargs)


def _legacy() -> Constitution:
    """Constitution with NO authority registry (legacy amendment mode)."""
    return Constitution(config={})


_ORDINARY_CHANGE = {"gates": {"epistemic": {"hold_threshold": 0.65}}}
_HC_CHANGE = {
    "hard_constraints": [
        {
            "id": "HC-CUSTOM-1",
            "description": "Custom deployer constraint",
            "check_key": "custom_flag",
            "check_op": "eq",
            "check_value": True,
            "required": False,
        }
    ]
}


def _propose(c: Constitution, *, changes=None, proposer="proposer-1", sections=None) -> str:
    return c.propose_amendment(
        description="test amendment",
        rationale="because",
        affected_sections=sections or ["EpistemicGate"],
        proposed_by=proposer,
        changes=changes,
    )


def _last(c: Constitution) -> dict:
    return c.amendment_records[-1]


# ---------------------------------------------------------------------------
# Separation of duty
# ---------------------------------------------------------------------------

def test_proposer_cannot_ratify_own_amendment():
    c = _c()
    aid = _propose(c, proposer="root-a")
    assert c.ratify_amendment(aid, ratified_by="root-a") is False
    rec = _last(c)
    assert rec["outcome"] == "REJECTED"
    assert "separation of duty" in rec["reason"].lower()


def test_separation_of_duty_enforced_in_legacy_mode():
    c = _legacy()
    aid = _propose(c, proposer="agent-x")
    assert c.ratify_amendment(aid, ratified_by="agent-x") is False
    assert _last(c)["outcome"] == "REJECTED"


def test_identity_normalization_still_caught_by_sod():
    """Reviewer #1: whitespace/case variants of the same id still trip SoD."""
    c = _c()
    aid = _propose(c, proposer="Alice")
    # Different presentation, same canonical principal -> must be rejected.
    assert c.ratify_amendment(aid, ratified_by="  aLICE ") is False
    rec = _last(c)
    assert rec["outcome"] == "REJECTED"
    assert "separation of duty" in rec["reason"].lower()
    assert canonical_principal("Alice") == canonical_principal("  aLICE ")


# ---------------------------------------------------------------------------
# Registration + authority level
# ---------------------------------------------------------------------------

def test_ratifier_must_be_registered():
    c = _c()
    aid = _propose(c)
    assert c.ratify_amendment(aid, ratified_by="stranger") is False
    assert "not in the authority registry" in _last(c)["reason"]


def test_ordinary_amendment_requires_ratifier_level():
    c = _c()
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    # A PROPOSER-level principal cannot ratify.
    assert c.ratify_amendment(aid, ratified_by="proposer-1") is False
    rec = _last(c)
    assert rec["outcome"] == "REJECTED"
    assert rec["required_authority"] == "RATIFIER"


def test_ordinary_amendment_succeeds_for_ratifier():
    c = _c()
    aid = _propose(c, proposer="proposer-1", changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is True
    rec = _last(c)
    assert rec["outcome"] == "RATIFIED"
    assert rec["required_authority"] == "RATIFIER"
    assert rec["ratifier_level"] == "RATIFIER"
    assert c.constitution_version == 1


def test_proposer_need_not_be_registered():
    c = _c()
    aid = _propose(c, proposer="external-agent", changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is True
    assert _last(c)["proposer_level"] is None


# ---------------------------------------------------------------------------
# Required authority derived from ACTUAL affected paths
# ---------------------------------------------------------------------------

def test_hard_constraint_change_requires_constitutional_authority():
    c = _c()
    aid = _propose(c, changes=_HC_CHANGE)
    # RATIFIER is not enough for a hard-constraint change.
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert _last(c)["required_authority"] == "CONSTITUTIONAL_AUTHORITY"
    # CONSTITUTIONAL_AUTHORITY can ratify it.
    aid2 = _propose(c, changes=_HC_CHANGE)
    assert c.ratify_amendment(aid2, ratified_by="root-a") is True
    assert _last(c)["outcome"] == "RATIFIED"


def test_registry_change_requires_constitutional_authority():
    """Reviewer #7: registry modification rejected below CONSTITUTIONAL_AUTHORITY."""
    c = _c()
    change = {"authority_registry": {"newbie": "RATIFIER"}}
    aid = _propose(c, changes=change)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    rec = _last(c)
    assert rec["outcome"] == "REJECTED"
    assert rec["required_authority"] == "CONSTITUTIONAL_AUTHORITY"
    # A root can perform the registry change.
    aid2 = _propose(c, changes=change)
    assert c.ratify_amendment(aid2, ratified_by="root-a") is True
    assert c.authority_registry.get("newbie") == int(AuthorityLevel.RATIFIER)


def test_understated_affected_paths_still_escalated():
    """Reviewer #2: authority derives from the payload, not the proposer label."""
    c = _c()
    # Proposer LABELS this an ordinary documentation change...
    aid = _propose(c, changes=_HC_CHANGE, sections=["documentation", "gates.epistemic"])
    # ...but the payload actually rewrites a hard constraint -> needs CA.
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    rec = _last(c)
    assert rec["outcome"] == "REJECTED"
    assert rec["required_authority"] == "CONSTITUTIONAL_AUTHORITY"
    assert any(p.startswith("hard_constraints") for p in rec["affected_paths"])


# ---------------------------------------------------------------------------
# Last-authority guard (never strand the system with zero roots)
# ---------------------------------------------------------------------------

def test_cannot_remove_final_root_authority():
    c = Constitution(config={}, authority_registry={"root": "CONSTITUTIONAL_AUTHORITY"})
    aid = _propose(c, proposer="proposer-x", changes={"authority_registry": {"root": None}})
    # 'root' cannot self-ratify (SoD); use a second CA... but there is only one.
    # Use a distinct proposer and the same root as ratifier is blocked by SoD,
    # so removing the only root is structurally impossible. Verify directly:
    assert c.ratify_amendment(aid, ratified_by="root") is False  # SoD
    # Now add a second root, then try to remove BOTH down to zero in one change.
    c2 = _c()
    aid2 = _propose(
        c2,
        changes={"authority_registry": {"root-a": None, "root-b": None}},
    )
    assert c2.ratify_amendment(aid2, ratified_by="root-a") is False
    assert "zero root authorities" in _last(c2)["reason"]


def test_cannot_demote_final_root_authority():
    c = _c()
    # Demote both roots to RATIFIER in one change -> zero roots -> refused.
    aid = _propose(
        c,
        changes={"authority_registry": {"root-a": "RATIFIER", "root-b": "RATIFIER"}},
    )
    assert c.ratify_amendment(aid, ratified_by="root-a") is False
    assert "zero root authorities" in _last(c)["reason"]


def test_concurrent_last_authority_demotion():
    """Reviewer #3: interleaved removals of the last root cannot both succeed."""
    c = _c()  # roots: root-a, root-b
    aid_x = _propose(c, proposer="proposer-1",
                     changes={"authority_registry": {"root-a": None}})
    aid_y = _propose(c, proposer="proposer-1",
                     changes={"authority_registry": {"root-b": None}})

    results: dict[str, bool] = {}
    barrier = threading.Barrier(2)

    def run(aid, ratifier, key):
        barrier.wait()
        results[key] = c.ratify_amendment(aid, ratified_by=ratifier)

    threads = [
        threading.Thread(target=run, args=(aid_x, "root-b", "x")),
        threading.Thread(target=run, args=(aid_y, "root-a", "y")),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Exactly one may succeed; the system must retain at least one root.
    assert list(results.values()).count(True) == 1
    assert c._authority.root_count() >= 1


# ---------------------------------------------------------------------------
# Legacy mode: root governance changes refused fail-closed
# ---------------------------------------------------------------------------

def test_legacy_mode_hard_constraint_change_refused():
    c = _legacy()
    aid = _propose(c, proposer="agent", changes=_HC_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="human") is False
    assert "no authority registry" in _last(c)["reason"].lower()


def test_legacy_mode_ordinary_amendment_allowed():
    c = _legacy()
    aid = _propose(c, proposer="agent", changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="human") is True


# ---------------------------------------------------------------------------
# Identity-verification callback (Reviewer #4)
# ---------------------------------------------------------------------------

def test_no_callback_records_caller_asserted():
    c = _c()
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is True
    rec = _last(c)
    assert rec["identity_assurance"] == "caller_asserted"
    assert rec["identity_verifier"] is None


def test_callback_pass_records_externally_verified():
    verifier = IdentityVerifier(name="okta", verify=lambda pid, claims: True)
    c = _c(identity_verifier=verifier)
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1",
                              asserted_identity={"jwt": "x"}) is True
    rec = _last(c)
    assert rec["identity_assurance"] == "externally_verified"
    assert rec["identity_verifier"] == "okta"


def test_callback_reject_fails_closed():
    verifier = IdentityVerifier(name="okta", verify=lambda pid, claims: False)
    c = _c(identity_verifier=verifier)
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert "identity verification failed" in _last(c)["reason"].lower()


def test_callback_exception_fails_closed():
    def boom(pid, claims):
        raise RuntimeError("verifier backend down")
    c = _c(identity_verifier=IdentityVerifier(name="entra", verify=boom))
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert _last(c)["outcome"] == "REJECTED"


def test_callback_timeout_fails_closed():
    def slow(pid, claims):
        raise TimeoutError("verifier timed out")
    c = _c(identity_verifier=IdentityVerifier(name="iam", verify=slow))
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert _last(c)["outcome"] == "REJECTED"


@pytest.mark.parametrize("bad", [None, "yes", 1, {"ok": True}, ["true"], 1.0])
def test_callback_malformed_response_fails_closed(bad):
    c = _c(identity_verifier=IdentityVerifier(name="mtls", verify=lambda p, cl: bad))
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert _last(c)["outcome"] == "REJECTED"


def test_callback_cannot_bypass_separation_of_duty():
    """A passing callback never overrides policy: SoD still rejects."""
    verifier = IdentityVerifier(name="okta", verify=lambda pid, claims: True)
    c = _c(identity_verifier=verifier)
    aid = _propose(c, proposer="root-a")
    assert c.ratify_amendment(aid, ratified_by="root-a") is False
    assert "separation of duty" in _last(c)["reason"].lower()


def test_callback_cannot_bypass_authority_level():
    verifier = IdentityVerifier(name="okta", verify=lambda pid, claims: True)
    c = _c(identity_verifier=verifier)
    aid = _propose(c, changes=_HC_CHANGE)
    # ratifier-1 is authenticated but only a RATIFIER; HC change needs CA.
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert _last(c)["required_authority"] == "CONSTITUTIONAL_AUTHORITY"


# ---------------------------------------------------------------------------
# Bootstrap irreversibility (Reviewer #5)
# ---------------------------------------------------------------------------

def test_authority_registry_property_is_a_copy():
    c = _c()
    snap = c.authority_registry
    snap["injected"] = 99
    assert "injected" not in c.authority_registry


def test_legacy_cannot_self_bootstrap_registry_via_amendment():
    """After init, a legacy constitution cannot mint a registry by amendment."""
    c = _legacy()
    assert c.authority_registry is None
    aid = _propose(c, proposer="agent",
                   changes={"authority_registry": {"root": "CONSTITUTIONAL_AUTHORITY"}})
    # Registry change needs CA, but there is no registry/root to authorize it.
    assert c.ratify_amendment(aid, ratified_by="human") is False
    assert c.authority_registry is None


def test_registry_only_changes_through_amendment():
    c = _c()
    before = c.authority_registry
    # There is no public setter for the registry.
    assert not hasattr(c, "set_authority_registry")
    aid = _propose(c, changes={"authority_registry": {"newbie": "RATIFIER"}})
    c.ratify_amendment(aid, ratified_by="root-a")
    after = c.authority_registry
    assert "newbie" not in before and "newbie" in after


# ---------------------------------------------------------------------------
# Replay / idempotency (Reviewer #6)
# ---------------------------------------------------------------------------

def test_replayed_amendment_is_rejected_and_version_bumps_once():
    c = _c()
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is True
    assert c.constitution_version == 1
    # Replaying the same ratified amendment id is a no-op.
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is False
    assert c.constitution_version == 1


def test_version_is_monotonic_across_ratifications():
    c = _c()
    for i in range(3):
        aid = _propose(c, changes={"gates": {"epistemic": {"hold_threshold": 0.6 + i / 100}}})
        assert c.ratify_amendment(aid, ratified_by="ratifier-1") is True
    assert c.constitution_version == 3


# ---------------------------------------------------------------------------
# Provenance + no secrets (Reviewer #8)
# ---------------------------------------------------------------------------

_REQUIRED_RECORD_FIELDS = [
    "amendment_id", "outcome", "proposer_id", "ratifier_id",
    "proposer_level", "ratifier_level", "required_authority",
    "identity_assurance", "identity_verifier", "affected_paths",
    "proposed_at", "decided_at", "evidence", "evidence_hash",
    "constitution_hash_before", "constitution_hash_after",
    "constitution_version", "reason",
]


def test_amendment_record_provenance_complete_and_no_secrets():
    verifier = IdentityVerifier(name="okta", verify=lambda pid, claims: True)
    c = _c(identity_verifier=verifier)
    evidence = {
        "latency_p99": "4.2s",
        "api_token": "sk-super-secret-1234567890",
        "nested": {"password": "hunter2", "ok": "value"},
        "authorization": "Bearer abc.def.ghi",
    }
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(
        aid, ratified_by="ratifier-1",
        evidence=evidence, asserted_identity={"jwt": "TOP-SECRET-JWT"},
    ) is True

    rec = _last(c)
    # Every required provenance field present.
    for f in _REQUIRED_RECORD_FIELDS:
        assert f in rec, f"missing provenance field: {f}"
    assert rec["outcome"] == "RATIFIED"
    assert rec["constitution_hash_before"] != rec["constitution_hash_after"]
    assert rec["evidence_hash"] and len(rec["evidence_hash"]) == 64

    # Secrets scrubbed in the retained evidence.
    assert rec["evidence"]["api_token"] == "[REDACTED]"
    assert rec["evidence"]["authorization"] == "[REDACTED]"
    assert rec["evidence"]["nested"]["password"] == "[REDACTED]"
    assert rec["evidence"]["nested"]["ok"] == "value"

    # No secret value anywhere in the serialized record (incl. asserted identity).
    blob = json.dumps(rec, default=str)
    for secret in ("sk-super-secret-1234567890", "hunter2",
                   "Bearer abc.def.ghi", "TOP-SECRET-JWT"):
        assert secret not in blob


def test_rejected_decisions_are_recorded():
    c = _c()
    aid = _propose(c, proposer="root-a")
    c.ratify_amendment(aid, ratified_by="root-a")  # SoD reject
    recs = c.amendment_records
    assert recs and recs[-1]["outcome"] == "REJECTED"


# ---------------------------------------------------------------------------
# Durable amendment store
# ---------------------------------------------------------------------------

def test_sqlite_amendment_store_persists_across_instances(tmp_path):
    db = str(tmp_path / "amendments.db")
    store = SqliteAmendmentStore(db)
    c = Constitution(config={}, authority_registry=dict(REGISTRY), amendment_store=store)
    aid = _propose(c, changes=_ORDINARY_CHANGE)
    assert c.ratify_amendment(aid, ratified_by="ratifier-1") is True
    store.close()

    # Reopen the store on the same file: the log survived.
    store2 = SqliteAmendmentStore(db)
    records = store2.all()
    store2.close()
    assert len(records) == 1
    assert records[0]["outcome"] == "RATIFIED"


# ---------------------------------------------------------------------------
# Registry / helper units
# ---------------------------------------------------------------------------

def test_registry_rejects_zero_root_bootstrap():
    with pytest.raises(ValueError):
        AuthorityRegistry({"only": "RATIFIER"})


def test_scrub_evidence_hash_over_original():
    ev = {"token": "secret", "n": 1}
    scrubbed, h = scrub_evidence(ev)
    assert scrubbed["token"] == "[REDACTED]"
    assert scrubbed["n"] == 1
    assert h and len(h) == 64
    assert scrub_evidence(None) == (None, None)


def test_authority_level_coerce():
    assert AuthorityLevel.coerce("RATIFIER") is AuthorityLevel.RATIFIER
    assert AuthorityLevel.coerce(3) is AuthorityLevel.CONSTITUTIONAL_AUTHORITY
    assert AuthorityLevel.coerce("constitutional_authority") is AuthorityLevel.CONSTITUTIONAL_AUTHORITY
    with pytest.raises(ValueError):
        AuthorityLevel.coerce("nope")
    with pytest.raises(ValueError):
        AuthorityLevel.coerce(True)
