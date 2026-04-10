"""Tests for FRIA evidence generation module.

Tracks GitHub issue #12.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from constitutional_agent.schema import GateResult, GateState
from constitutional_agent.fria import (
    FRIACategory, FRIAEvidence, generate_fria_evidence, fria_summary, fria_narrative,
)


def _make_gate(name: str, state: GateState, reason: str = "") -> GateResult:
    return GateResult(gate=name, state=state, reason=reason)


def test_all_passing_gates():
    """All gates PASS, no HC violations → all categories 'covered'."""
    gates = [
        _make_gate("RiskGate", GateState.PASS),
        _make_gate("EpistemicGate", GateState.PASS),
        _make_gate("AutonomyGate", GateState.PASS),
        _make_gate("GovernanceGate", GateState.PASS),
    ]
    evidence = generate_fria_evidence(gates, [])
    assert len(evidence) == 6  # Always 6 categories
    covered = [e for e in evidence if e.status == "covered"]
    assert len(covered) >= 4  # At least the mapped ones


def test_failing_risk_gate_flags_safety():
    """Failing RiskGate → SAFETY category flagged."""
    gates = [
        _make_gate("RiskGate", GateState.FAIL, "Critical misuse risk"),
        _make_gate("EpistemicGate", GateState.PASS),
        _make_gate("AutonomyGate", GateState.PASS),
        _make_gate("GovernanceGate", GateState.PASS),
    ]
    evidence = generate_fria_evidence(gates, [])
    safety = next(e for e in evidence if e.category == FRIACategory.SAFETY)
    assert safety.status == "flagged"
    assert "RiskGate" in safety.narrative


def test_hc_violation_flags_category():
    """HC-5 violation → SAFETY flagged."""
    gates = [_make_gate("RiskGate", GateState.PASS)]
    hc_violations = [{"constraint_id": "HC-5", "violated": True}]
    evidence = generate_fria_evidence(gates, hc_violations)
    safety = next(e for e in evidence if e.category == FRIACategory.SAFETY)
    assert safety.status == "flagged"
    assert "HC-5" in safety.narrative


def test_low_audit_coverage_flags_transparency():
    """Failing GovernanceGate → TRANSPARENCY flagged."""
    gates = [
        _make_gate("GovernanceGate", GateState.FAIL, "Audit coverage below threshold"),
        _make_gate("RiskGate", GateState.PASS),
    ]
    evidence = generate_fria_evidence(gates, [])
    transparency = next(e for e in evidence if e.category == FRIACategory.TRANSPARENCY)
    assert transparency.status == "flagged"


def test_missing_gates_produce_gaps():
    """No gate data at all → gap or partial status (no 'covered' or 'flagged')."""
    evidence = generate_fria_evidence([], [])
    assert len(evidence) == 6
    non_actionable = [e for e in evidence if e.status in ("gap", "partial")]
    assert len(non_actionable) == 6  # None should be "covered" or "flagged" with no data


def test_always_six_categories():
    """Output always has exactly 6 categories regardless of input."""
    for gate_list in [[], [_make_gate("RiskGate", GateState.PASS)]]:
        evidence = generate_fria_evidence(gate_list, [])
        assert len(evidence) == 6
        categories = {e.category for e in evidence}
        assert categories == set(FRIACategory)


def test_fria_summary_structure():
    """Summary has expected fields."""
    gates = [_make_gate("RiskGate", GateState.PASS)]
    evidence = generate_fria_evidence(gates, [])
    summary = fria_summary(evidence)
    assert "framework" in summary
    assert "total_categories" in summary
    assert summary["total_categories"] == 6
    assert "overall_status" in summary
    assert "categories" in summary


def test_fria_narrative_nonempty():
    """Narrative produces non-empty readable output."""
    gates = [
        _make_gate("RiskGate", GateState.PASS),
        _make_gate("GovernanceGate", GateState.FAIL, "Audit gap"),
    ]
    evidence = generate_fria_evidence(gates, [])
    text = fria_narrative(evidence)
    assert len(text) > 100
    assert "FRIA" in text
    assert "Article 27" in text


def test_constitution_fria_integration():
    """Constitution.fria_evidence() returns valid FRIA data."""
    from constitutional_agent import Constitution
    c = Constitution.from_defaults()
    evidence = c.fria_evidence({
        "misuse_risk_index": 0.1,
        "verification_pass_rate": 0.9,
        "audit_coverage": 0.98,
        "human_minutes_per_day": 30,
        "decisions_per_day": 20,
        "agent_activation_rate": 0.6,
    })
    assert len(evidence) == 6
    covered = [e for e in evidence if e.status == "covered"]
    assert len(covered) >= 3


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed.")
