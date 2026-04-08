"""
Tests for constitutional-agent gates and hard constraints.
Section: constitutional governance verification
"""
import pytest
from constitutional_agent import Constitution, GateState, SystemState
from constitutional_agent.gates import SixGateEvaluator
from constitutional_agent.hard_constraints import check_hard_constraints


# --- Healthy system ---

def test_healthy_system_returns_run():
    evaluator = SixGateEvaluator()
    results = evaluator.evaluate({
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
    })
    states = [r.state for r in results]
    assert GateState.FAIL not in states


def test_low_runway_triggers_economic_fail():
    evaluator = SixGateEvaluator()
    results = evaluator.evaluate({
        "verification_pass_rate": 0.95,
        "external_channel_health": 0.9,
        "metric_anomaly_score": 0.05,
        "runway_months": 2.0,   # Below 3-month FAIL threshold
        "decisions_per_day": 150,
        "lessons_learned_weekly": 3,
        "mrr": 0,
        "stage": "pre_revenue",
    })
    epg = next((r for r in results if r.gate == "economic"), None)
    assert epg is not None
    assert epg.state == GateState.FAIL


def test_low_verification_triggers_epistemic_hold():
    evaluator = SixGateEvaluator()
    results = evaluator.evaluate({
        "verification_pass_rate": 0.65,   # Below HOLD threshold
        "external_channel_health": 0.9,
        "metric_anomaly_score": 0.05,
        "runway_months": 10.0,
        "decisions_per_day": 150,
        "lessons_learned_weekly": 3,
        "mrr": 0,
        "stage": "pre_revenue",
    })
    eg = next((r for r in results if r.gate == "epistemic"), None)
    assert eg is not None
    assert eg.state in (GateState.HOLD, GateState.FAIL)


def test_zero_learning_triggers_constitutional_fail():
    evaluator = SixGateEvaluator()
    results = evaluator.evaluate({
        "verification_pass_rate": 0.95,
        "external_channel_health": 0.9,
        "metric_anomaly_score": 0.05,
        "runway_months": 10.0,
        "decisions_per_day": 150,
        "lessons_learned_weekly": 0,   # FAIL threshold
        "mrr": 0,
        "stage": "pre_revenue",
    })
    cgg = next((r for r in results if r.gate == "constitutional"), None)
    assert cgg is not None
    assert cgg.state == GateState.FAIL


# --- Hard constraints ---

def test_hc12_silent_outage_detected():
    violations = check_hard_constraints({
        "hours_since_last_execution": 30,   # Exceeds 24h limit
        "failing_tests": 0,
        "spend_amount": 0,
        "approved_limit": 500,
    })
    hc12 = next((v for v in violations if v.id == "HC-12"), None)
    assert hc12 is not None


def test_hc1_failing_tests_detected():
    violations = check_hard_constraints({
        "failing_tests": 3,
        "hours_since_last_execution": 1,
        "spend_amount": 0,
        "approved_limit": 500,
    })
    hc1 = next((v for v in violations if v.id == "HC-1"), None)
    assert hc1 is not None


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
        "hours_since_last_execution": 336,  # 2 weeks undetected
        "failing_tests": 0,
        "spend_amount": 0,
        "approved_limit": 500,
    })
    assert any(v.id == "HC-12" for v in violations)


def test_agenthustler_strategy_spiral_caught_by_cgg():
    """CGG: zero learning velocity catches the 30-run MCP death spiral."""
    evaluator = SixGateEvaluator()
    results = evaluator.evaluate({
        "verification_pass_rate": 0.9,
        "external_channel_health": 0.5,
        "metric_anomaly_score": 0.1,
        "runway_months": 8.0,
        "decisions_per_day": 12,
        "lessons_learned_weekly": 0,
        "mrr": 0,
        "stage": "pre_revenue",
    })
    cgg = next((r for r in results if r.gate == "constitutional"), None)
    assert cgg.state == GateState.FAIL
