"""
Tests for constitutional-agent gates and hard constraints.
"""
import pytest
from constitutional_agent.gates import SixGateEvaluator
from constitutional_agent.schema import GateState, SystemState
from constitutional_agent.hard_constraints import check_hard_constraints

HEALTHY = {
    "verification_pass_rate": 0.95,
    "external_channel_health": 0.9,
    "metric_anomaly_score": 0.05,
    "runway_months": 10.0,
    "decisions_per_day": 150,
    "lessons_learned_weekly": 3,
    "mrr": 0,
    "stage": "pre_revenue",
    "dli_completion_rate": 0.08,
    "user_return_rate": 0.20,
}


# --- System state ---

def test_healthy_system_returns_run_or_throttle():
    state, results = SixGateEvaluator().evaluate(HEALTHY)
    assert state in (SystemState.RUN, SystemState.THROTTLE, SystemState.COMPOUND)
    assert state != SystemState.FREEZE


def test_low_runway_triggers_freeze():
    metrics = {**HEALTHY, "runway_months": 2.0}
    state, results = SixGateEvaluator().evaluate(metrics)
    assert state == SystemState.FREEZE
    epg = next(r for r in results if r.gate == "economic")
    assert epg.state == GateState.FAIL


def test_low_verification_triggers_hold_or_fail():
    metrics = {**HEALTHY, "verification_pass_rate": 0.55}
    state, results = SixGateEvaluator().evaluate(metrics)
    eg = next(r for r in results if r.gate == "epistemic")
    assert eg.state in (GateState.HOLD, GateState.FAIL)


def test_zero_learning_triggers_freeze():
    metrics = {**HEALTHY, "lessons_learned_weekly": 0}
    state, results = SixGateEvaluator().evaluate(metrics)
    assert state == SystemState.FREEZE
    cgg = next(r for r in results if r.gate == "constitutional")
    assert cgg.state == GateState.FAIL


def test_six_gate_results_returned():
    _, results = SixGateEvaluator().evaluate(HEALTHY)
    assert len(results) == 6
    gates = {r.gate for r in results}
    assert "epistemic" in gates
    assert "economic" in gates
    assert "constitutional" in gates


# --- Hard constraints ---

def test_hc12_silent_outage_detected():
    violations = check_hard_constraints({
        "hours_since_last_execution": 30,
        "failing_tests": 0,
        "spend_amount": 0,
        "approved_limit": 500,
    })
    assert any(v.id == "HC-12" for v in violations)


def test_hc1_failing_tests_detected():
    violations = check_hard_constraints({
        "failing_tests": 3,
        "hours_since_last_execution": 1,
        "spend_amount": 0,
        "approved_limit": 500,
    })
    assert any(v.id == "HC-1" for v in violations)


def test_clean_system_has_no_violations():
    violations = check_hard_constraints({
        "failing_tests": 0,
        "hours_since_last_execution": 4,
        "spend_amount": 100,
        "approved_limit": 500,
    })
    assert len(violations) == 0


# --- agenthustler failure modes ---

def test_agenthustler_broken_wallet_caught_by_hc12():
    """HC-12: no silent outage >24h catches the broken Lightning wallet."""
    violations = check_hard_constraints({
        "hours_since_last_execution": 336,
        "failing_tests": 0,
        "spend_amount": 0,
        "approved_limit": 500,
    })
    assert any(v.id == "HC-12" for v in violations)


def test_agenthustler_strategy_spiral_caught_by_cgg():
    """CGG: zero learning velocity catches the 30-run MCP death spiral."""
    metrics = {**HEALTHY, "lessons_learned_weekly": 0}
    state, results = SixGateEvaluator().evaluate(metrics)
    cgg = next(r for r in results if r.gate == "constitutional")
    assert cgg.state == GateState.FAIL
