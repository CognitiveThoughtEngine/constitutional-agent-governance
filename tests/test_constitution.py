"""
Tests for Constitution — YAML loading, dry_run, amendment protocol.
"""
import pathlib
import tempfile

import pytest
import yaml

from constitutional_agent import Constitution
from constitutional_agent.schema import SystemState


HEALTHY = {
    "failing_tests": 0,
    "hours_since_last_execution": 4,
    "proposed_spend": 100,
    "approved_budget": 500,
    "verification_pass_rate": 0.90,
    "runway_months": 10.0,
    "stage": "pre_revenue",
    "dli_completion_rate": 0.08,
    "user_return_rate": 0.20,
    "value_demo_count": 5,
    "lessons_learned_weekly": 3,
    "amendments_per_month": 2,
}


# ---------------------------------------------------------------------------
# from_defaults
# ---------------------------------------------------------------------------

def test_from_defaults_evaluates():
    c = Constitution.from_defaults()
    result = c.evaluate(HEALTHY)
    assert result.system_state in (
        SystemState.RUN, SystemState.THROTTLE, SystemState.COMPOUND
    )


def test_from_defaults_has_12_hard_constraints():
    c = Constitution.from_defaults()
    result = c.evaluate(HEALTHY)
    # No violations in clean context
    assert result.hard_constraint_violations == []


def test_evaluate_records_history():
    c = Constitution.from_defaults()
    assert c.evaluation_count == 0
    c.evaluate(HEALTHY)
    assert c.evaluation_count == 1
    c.evaluate(HEALTHY)
    assert c.evaluation_count == 2


# ---------------------------------------------------------------------------
# Hard constraint short-circuit → STOP
# ---------------------------------------------------------------------------

def test_failing_tests_triggers_stop():
    c = Constitution.from_defaults()
    result = c.evaluate({**HEALTHY, "failing_tests": 3})
    assert result.system_state == SystemState.STOP
    assert any(v.constraint_id == "HC-1" for v in result.hard_constraint_violations)


def test_stop_state_has_no_gate_results():
    c = Constitution.from_defaults()
    result = c.evaluate({**HEALTHY, "failing_tests": 1})
    assert result.system_state == SystemState.STOP
    assert result.gate_results == []


def test_raise_on_hc_violation():
    from constitutional_agent.constitution import ConstitutionalViolation
    c = Constitution.from_defaults()
    with pytest.raises(ConstitutionalViolation):
        c.evaluate({**HEALTHY, "failing_tests": 2}, raise_on_hc_violation=True)


# ---------------------------------------------------------------------------
# dry_run mode
# ---------------------------------------------------------------------------

def test_dry_run_does_not_short_circuit_on_hc_violation():
    """dry_run=True: see all gate results even when HC is violated."""
    c = Constitution.from_defaults()
    result = c.evaluate(
        {**HEALTHY, "failing_tests": 5},
        dry_run=True,
    )
    # HC-1 violated, but gate results still populated in dry_run
    assert len(result.gate_results) == 6
    assert any(v.constraint_id == "HC-1" for v in result.hard_constraint_violations)


def test_dry_run_does_not_record_history():
    c = Constitution.from_defaults()
    c.evaluate(HEALTHY, dry_run=True)
    assert c.evaluation_count == 0  # dry_run skips history


def test_dry_run_returns_correct_gate_states():
    c = Constitution.from_defaults()
    # Force a gate FAIL via dry_run with failing tests
    result = c.evaluate(
        {**HEALTHY, "failing_tests": 1, "runway_months": 2.0},
        dry_run=True,
    )
    epg = next(r for r in result.gate_results if r.gate == "EconomicGate")
    assert epg.state.value == "FAIL"


# ---------------------------------------------------------------------------
# YAML threshold configuration
# ---------------------------------------------------------------------------

def test_yaml_load_applies_custom_thresholds():
    """YAML-configured thresholds should override defaults."""
    config = {
        "version": "1.0",
        "organization": "TestOrg",
        "gates": {
            "epistemic": {
                # Lower the verification hold threshold to 0.60
                "hold_threshold": 0.60,
                "fail_threshold": 0.50,
            }
        }
    }
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump(config, f)
        path = f.name

    c = Constitution.load(path)
    # 0.65 is below default hold (0.70) but above custom hold (0.60) → should PASS
    result = c.evaluate({**HEALTHY, "verification_pass_rate": 0.65})
    eg = next(r for r in result.gate_results if r.gate == "EpistemicGate")
    assert eg.state.value == "PASS"


def test_yaml_load_missing_gate_uses_defaults():
    """Gates not configured in YAML use production defaults."""
    config = {"version": "1.0", "organization": "TestOrg", "gates": {}}
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        yaml.dump(config, f)
        path = f.name

    c = Constitution.load(path)
    result = c.evaluate(HEALTHY)
    assert result.system_state != SystemState.STOP


def test_yaml_load_file_not_found():
    with pytest.raises(FileNotFoundError):
        Constitution.load("/nonexistent/path/governance.yaml")


def test_yaml_load_invalid_content():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        f.write("- this\n- is\n- a list\n")
        path = f.name

    with pytest.raises(ValueError):
        Constitution.load(path)


# ---------------------------------------------------------------------------
# Amendment protocol
# ---------------------------------------------------------------------------

def test_propose_amendment_returns_id():
    c = Constitution.from_defaults()
    aid = c.propose_amendment(
        description="Lower EpistemicGate verification hold to 0.65",
        rationale="External verification latency increased. 0.65 still safe.",
        affected_sections=["EpistemicGate"],
        proposed_by="test_agent",
    )
    assert aid.startswith("AMEND-")


def test_amendment_starts_as_pending():
    c = Constitution.from_defaults()
    aid = c.propose_amendment(
        description="Test amendment",
        rationale="Test",
        affected_sections=["EpistemicGate"],
    )
    log = c.amendment_log
    entry = next(a for a in log if a["id"] == aid)
    assert entry["status"] == "PENDING"


def test_ratify_amendment_changes_status():
    c = Constitution.from_defaults()
    aid = c.propose_amendment(
        description="Test amendment",
        rationale="Test",
        affected_sections=["EpistemicGate"],
    )
    result = c.ratify_amendment(aid, ratified_by="ceo@testorg.com")
    assert result is True
    log = c.amendment_log
    entry = next(a for a in log if a["id"] == aid)
    assert entry["status"] == "RATIFIED"
    assert entry["ratified_by"] == "ceo@testorg.com"


def test_ratify_nonexistent_amendment_returns_false():
    c = Constitution.from_defaults()
    result = c.ratify_amendment("AMEND-DOESNOTEXIST", ratified_by="ceo@test.com")
    assert result is False


def test_ratify_already_ratified_returns_false():
    c = Constitution.from_defaults()
    aid = c.propose_amendment("Test", "Test", ["EpistemicGate"])
    c.ratify_amendment(aid, ratified_by="ceo@test.com")
    result = c.ratify_amendment(aid, ratified_by="ceo@test.com")  # second ratify
    assert result is False


# ---------------------------------------------------------------------------
# summary_report
# ---------------------------------------------------------------------------

def test_summary_report_structure():
    c = Constitution.from_defaults()
    c.evaluate(HEALTHY)
    report = c.summary_report()
    assert "total_evaluations" in report
    assert "freeze_events" in report
    assert "stop_events" in report
    assert "amendments_pending" in report
    assert "amendments_ratified" in report
    assert report["total_evaluations"] == 1


def test_summary_report_counts_freeze():
    c = Constitution.from_defaults()
    # Use lessons=0 to trigger CGG FAIL → FREEZE (not STOP — no HC for zero lessons)
    c.evaluate({**HEALTHY, "lessons_learned_weekly": 0})
    c.evaluate(HEALTHY)
    report = c.summary_report()
    assert report["freeze_events"] == 1
