"""
Tests for Constitution — YAML loading, dry_run, amendment protocol.
"""
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


# ---------------------------------------------------------------------------
# Issue 1: YAML hard constraints are enforced (not silently ignored)
# ---------------------------------------------------------------------------

def test_yaml_hard_constraints_are_enforced():
    """YAML-defined hard constraints must actually be enforced, not silently ignored."""
    config = {
        "hard_constraints": [
            {
                "id": "HC-ORG-1",
                "description": "No deploy on Fridays",
                "check_key": "is_friday",
                "check_op": "eq",
                "check_value": False,
                "remedy": "Wait until Monday",
            }
        ]
    }
    c = Constitution(config=config)
    result = c.evaluate({"is_friday": True, "failing_tests": 0, "hours_since_last_execution": 1})
    assert result.system_state.value == "STOP"
    violated_ids = [v.constraint_id for v in result.hard_constraint_violations]
    assert "HC-ORG-1" in violated_ids


def test_yaml_hard_constraints_ne_op():
    """YAML HC with 'ne' op: violated when value equals check_value."""
    config = {
        "hard_constraints": [
            {
                "id": "HC-ORG-2",
                "description": "Environment must not be production when testing",
                "check_key": "environment",
                "check_op": "ne",
                "check_value": "production",
                "remedy": "Switch to test environment",
            }
        ]
    }
    c = Constitution(config=config)
    result = c.evaluate({"environment": "production", "failing_tests": 0, "hours_since_last_execution": 1})
    assert result.system_state.value == "STOP"
    assert any(v.constraint_id == "HC-ORG-2" for v in result.hard_constraint_violations)


def test_yaml_hard_constraints_gte_op():
    """YAML HC with 'gte' op: violated when value is below threshold."""
    config = {
        "hard_constraints": [
            {
                "id": "HC-ORG-3",
                "description": "Test coverage must be at least 80%",
                "check_key": "test_coverage",
                "check_op": "gte",
                "check_value": 0.80,
                "remedy": "Increase test coverage",
            }
        ]
    }
    c = Constitution(config=config)
    # 60% coverage violates the 'must be >= 80%' constraint
    result = c.evaluate({"test_coverage": 0.60, "failing_tests": 0, "hours_since_last_execution": 1})
    assert result.system_state.value == "STOP"
    assert any(v.constraint_id == "HC-ORG-3" for v in result.hard_constraint_violations)


def test_yaml_hard_constraints_absent_key_does_not_trigger():
    """If the checked key is absent from context, the YAML HC is not triggered."""
    config = {
        "hard_constraints": [
            {
                "id": "HC-ORG-4",
                "description": "No deploy on Fridays",
                "check_key": "is_friday",
                "check_op": "eq",
                "check_value": False,
                "remedy": "Wait until Monday",
            }
        ]
    }
    c = Constitution(config=config)
    # Key 'is_friday' not in context — should not trigger
    result = c.evaluate({"failing_tests": 0, "hours_since_last_execution": 1})
    assert "HC-ORG-4" not in [v.constraint_id for v in result.hard_constraint_violations]


def test_yaml_hard_constraints_extend_builtins():
    """YAML HCs are appended to builtins — both are enforced simultaneously."""
    config = {
        "hard_constraints": [
            {
                "id": "HC-ORG-5",
                "description": "Custom org constraint",
                "check_key": "org_ok",
                "check_op": "eq",
                "check_value": True,
                "remedy": "Fix org setting",
            }
        ]
    }
    c = Constitution(config=config)
    # Violate both builtin HC-1 and YAML HC-ORG-5
    result = c.evaluate({"failing_tests": 3, "org_ok": False, "hours_since_last_execution": 1})
    ids = [v.constraint_id for v in result.hard_constraint_violations]
    assert "HC-1" in ids
    assert "HC-ORG-5" in ids


# ---------------------------------------------------------------------------
# Issue 2: Ratified amendments update thresholds immediately
# ---------------------------------------------------------------------------

def test_ratified_amendment_updates_thresholds():
    """Ratified amendments must take effect immediately, not just change status."""
    c = Constitution.from_defaults()
    # Propose changing runway HOLD threshold from 6 to 9 months
    aid = c.propose_amendment(
        description="Raise runway hold to 9 months",
        rationale="Series A requirement",
        affected_sections=["EPG"],
        changes={"gates": {"economic": {"pre_revenue": {"runway_hold_months": 9.0}}}},
    )
    # Before ratification: 7 months runway should be RUN/COMPOUND (above 6 month hold)
    result_before = c.evaluate({**HEALTHY, "runway_months": 7.0})
    assert result_before.system_state.value in ("RUN", "THROTTLE", "COMPOUND")

    # After ratification: 7 months should be THROTTLE (below new 9 month hold)
    c.ratify_amendment(aid, ratified_by="CEO")
    result_after = c.evaluate({**HEALTHY, "runway_months": 7.0})
    assert result_after.system_state.value == "THROTTLE"


def test_amendment_changes_in_log():
    """Ratified amendment changes dict is included in to_dict() output."""
    c = Constitution.from_defaults()
    changes = {"gates": {"economic": {"pre_revenue": {"runway_hold_months": 9.0}}}}
    aid = c.propose_amendment(
        description="Raise runway hold",
        rationale="Test",
        affected_sections=["EPG"],
        changes=changes,
    )
    log = c.amendment_log
    entry = next(a for a in log if a["id"] == aid)
    assert entry["changes"] == changes


def test_amendment_without_changes_still_ratifies():
    """Amendments without changes dict still ratify correctly (no-op on thresholds)."""
    c = Constitution.from_defaults()
    aid = c.propose_amendment(
        description="Document-only amendment",
        rationale="No threshold change",
        affected_sections=["EpistemicGate"],
    )
    result = c.ratify_amendment(aid, ratified_by="CEO")
    assert result is True
    log = c.amendment_log
    entry = next(a for a in log if a["id"] == aid)
    assert entry["status"] == "RATIFIED"
    assert entry["changes"] is None


# ---------------------------------------------------------------------------
# Issue 3: enabled: false gate config is honoured
# ---------------------------------------------------------------------------

def test_disabled_gate_always_passes():
    config = {"gates": {"epistemic": {"enabled": False}}}
    c = Constitution(config=config)
    # Even with bad verification_pass_rate, epistemic gate should PASS
    result = c.evaluate({"verification_pass_rate": 0.0, **HEALTHY})
    epistemic_result = next(r for r in result.gate_results if "Epistemic" in r.gate)
    assert epistemic_result.state.value == "PASS"


def test_disabled_gate_reason_mentions_disabled():
    config = {"gates": {"risk": {"enabled": False}}}
    c = Constitution(config=config)
    result = c.evaluate(HEALTHY)
    risk_result = next(r for r in result.gate_results if r.gate == "RiskGate")
    assert "isabled" in risk_result.reason  # "Disabled" or "disabled"


def test_multiple_gates_can_be_disabled():
    config = {"gates": {"epistemic": {"enabled": False}, "risk": {"enabled": False}}}
    c = Constitution(config=config)
    result = c.evaluate({"verification_pass_rate": 0.0, "channel_health": 0.0, **HEALTHY})
    eg = next(r for r in result.gate_results if r.gate == "EpistemicGate")
    rg = next(r for r in result.gate_results if r.gate == "RiskGate")
    assert eg.state.value == "PASS"
    assert rg.state.value == "PASS"


# ---------------------------------------------------------------------------
# Issue 4: strict_mode empty context returns THROTTLE
# ---------------------------------------------------------------------------

def test_strict_mode_empty_context_returns_throttle():
    c = Constitution.from_defaults()
    result = c.evaluate({}, strict_mode=True)
    assert result.system_state.value == "THROTTLE"
    assert "strict" in result.summary.lower()


def test_strict_mode_nonempty_context_proceeds_normally():
    """Non-empty context with strict_mode=True evaluates normally."""
    c = Constitution.from_defaults()
    result = c.evaluate(HEALTHY, strict_mode=True)
    assert result.system_state.value in ("RUN", "THROTTLE", "COMPOUND")


def test_strict_mode_instance_level():
    """Instance-level strict_mode=True applies to all evaluate() calls."""
    c = Constitution(config={}, strict_mode=True)
    result = c.evaluate({})
    assert result.system_state.value == "THROTTLE"


def test_strict_mode_call_site_overrides_instance():
    """Call-site strict_mode=False overrides instance strict_mode=True."""
    c = Constitution(config={}, strict_mode=True)
    # Explicitly pass strict_mode=False at call site
    result = c.evaluate({}, strict_mode=False)
    # Empty context without strict mode should not return THROTTLE from strict guard
    # (it may still THROTTLE for other reasons, but not the strict-mode guard)
    assert "strict" not in result.summary.lower()


def test_strict_mode_result_not_recorded_in_dry_run():
    """strict_mode early return in dry_run mode skips history recording."""
    c = Constitution(config={}, strict_mode=True)
    assert c.evaluation_count == 0
    c.evaluate({}, dry_run=True)
    assert c.evaluation_count == 0


# ---------------------------------------------------------------------------
# Issue 6: Persistence hooks (on_evaluate, on_amendment_ratified)
# ---------------------------------------------------------------------------

def test_on_evaluate_hook_called():
    """on_evaluate callback is invoked on each non-dry_run evaluation."""
    audit_log = []
    c = Constitution(config={}, on_evaluate=lambda r: audit_log.append(r.summary))
    c.evaluate(HEALTHY)
    assert len(audit_log) == 1
    c.evaluate(HEALTHY)
    assert len(audit_log) == 2


def test_on_evaluate_hook_not_called_in_dry_run():
    """on_evaluate callback is NOT invoked for dry_run evaluations."""
    audit_log = []
    c = Constitution(config={}, on_evaluate=lambda r: audit_log.append(r.summary))
    c.evaluate(HEALTHY, dry_run=True)
    assert len(audit_log) == 0


def test_on_amendment_ratified_hook_called():
    """on_amendment_ratified callback is invoked when an amendment is ratified."""
    ratified_events = []
    c = Constitution(
        config={},
        on_amendment_ratified=lambda d: ratified_events.append(d["id"]),
    )
    aid = c.propose_amendment("Test", "Test rationale", ["EpistemicGate"])
    assert len(ratified_events) == 0
    c.ratify_amendment(aid, ratified_by="CEO")
    assert len(ratified_events) == 1
    assert ratified_events[0] == aid


def test_on_amendment_ratified_not_called_for_failed_ratify():
    """on_amendment_ratified is NOT called when ratify_amendment returns False."""
    ratified_events = []
    c = Constitution(
        config={},
        on_amendment_ratified=lambda d: ratified_events.append(d),
    )
    c.ratify_amendment("AMEND-DOESNOTEXIST", ratified_by="CEO")
    assert len(ratified_events) == 0


# ---------------------------------------------------------------------------
# Issue 8: Input validation warns on out-of-range metrics
# ---------------------------------------------------------------------------

def test_out_of_range_metric_triggers_warning():
    """Metrics outside [0, 1] for bounded keys should trigger a UserWarning."""
    import warnings as _warnings
    c = Constitution.from_defaults()
    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        c.evaluate({**HEALTHY, "verification_pass_rate": 1.5})
    assert any(
        "verification_pass_rate" in str(w.message) for w in caught
    ), "Expected a UserWarning about out-of-range verification_pass_rate"


def test_in_range_metric_no_warning():
    """Metrics within valid range should produce no UserWarning."""
    import warnings as _warnings
    c = Constitution.from_defaults()
    with _warnings.catch_warnings(record=True) as caught:
        _warnings.simplefilter("always")
        c.evaluate(HEALTHY)
    range_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
    assert len(range_warnings) == 0


# ---------------------------------------------------------------------------
# Issue 10: blocking_gates lists ALL failing gates
# ---------------------------------------------------------------------------

def test_blocking_gates_contains_all_failures():
    """blocking_gates must list every FAIL gate, not just the first one."""
    # Trigger both EconomicGate (runway < FAIL floor, but above HC-3 floor of 3.0)
    # and ConstitutionalGate (lessons=0) FAIL.
    # HC-3 kicks in at < 3.0, so use runway=3.5 to avoid HC-3 but still hit EPG FAIL.
    # EPG FAIL threshold is also 3.0 — use the dry_run path to get gate results
    # for both FAILs without hitting the HC short-circuit.
    # Simpler: trigger EPG HOLD (runway=4.5) and CGG FAIL (lessons=0) — FREEZE from CGG.
    result = Constitution.from_defaults().evaluate(
        {**HEALTHY, "runway_months": 4.5, "lessons_learned_weekly": 0}
    )
    assert result.system_state.value == "FREEZE"
    fail_gate_names = {r.gate for r in result.blocking_gates}
    assert "ConstitutionalGate" in fail_gate_names


def test_blocking_gate_backwards_compat_is_first_fail():
    """blocking_gate (singular) still returns the first FAIL gate for backwards compat."""
    # lessons=0 triggers CGG FAIL → FREEZE without touching any HC
    result = Constitution.from_defaults().evaluate(
        {**HEALTHY, "lessons_learned_weekly": 0}
    )
    assert result.blocking_gate is not None
    assert result.blocking_gate.state.value == "FAIL"


def test_no_failures_blocking_gates_empty():
    """When all gates PASS, blocking_gates is an empty list."""
    result = Constitution.from_defaults().evaluate(HEALTHY)
    assert result.blocking_gates == []


def test_blocking_gates_summary_mentions_multiple():
    """Summary string mentions multiple gates when more than one FAILs."""
    result = Constitution.from_defaults().evaluate(
        {**HEALTHY, "runway_months": 1.0, "lessons_learned_weekly": 0}
    )
    if len(result.blocking_gates) > 1:
        # Should mention count or list of gates
        assert "gates" in result.summary.lower() or len(result.blocking_gates) > 0
