"""
Tests for constitutional-agent gates and hard constraints.
"""
from constitutional_agent.gates import (
    AutonomyGate,
    ConstitutionalGate,
    EconomicGate,
    EpistemicGate,
    GovernanceGate,
    RiskGate,
    SixGateEvaluator,
)
from constitutional_agent.schema import GateState, SystemState
from constitutional_agent.hard_constraints import check_hard_constraints

# ---------------------------------------------------------------------------
# Shared fixture: a healthy pre-revenue system
# ---------------------------------------------------------------------------

HEALTHY = {
    "verification_pass_rate": 0.95,
    "metric_anomaly_score": 0.05,
    "runway_months": 10.0,
    "decisions_per_day": 150,
    "lessons_learned_weekly": 3,
    "stage": "pre_revenue",
    "dli_completion_rate": 0.08,
    "user_return_rate": 0.20,
    "value_demo_count": 5,
}


# ---------------------------------------------------------------------------
# SixGateEvaluator — composite system state
# ---------------------------------------------------------------------------

def test_healthy_system_returns_run_or_throttle():
    state, results = SixGateEvaluator().evaluate(HEALTHY)
    assert state in (SystemState.RUN, SystemState.THROTTLE, SystemState.COMPOUND)
    assert state != SystemState.FREEZE


def test_six_gate_results_returned():
    _, results = SixGateEvaluator().evaluate(HEALTHY)
    assert len(results) == 6
    gates = {r.gate for r in results}
    assert "EpistemicGate" in gates
    assert "RiskGate" in gates
    assert "GovernanceGate" in gates
    assert "EconomicGate" in gates
    assert "AutonomyGate" in gates
    assert "ConstitutionalGate" in gates


def test_any_fail_produces_freeze():
    metrics = {**HEALTHY, "runway_months": 1.0}
    state, _ = SixGateEvaluator().evaluate(metrics)
    assert state == SystemState.FREEZE


def test_any_hold_produces_throttle():
    # runway < HOLD threshold but >= FAIL threshold → EconomicGate HOLD
    metrics = {**HEALTHY, "runway_months": 4.5}
    state, results = SixGateEvaluator().evaluate(metrics)
    assert state == SystemState.THROTTLE
    epg = next(r for r in results if r.gate == "EconomicGate")
    assert epg.state == GateState.HOLD


def test_all_pass_with_targets_met_produces_compound():
    # targets_met is a parameter of evaluate(), not a metrics key
    state, _ = SixGateEvaluator().evaluate(HEALTHY, targets_met=True)
    assert state == SystemState.COMPOUND


def test_low_runway_triggers_freeze():
    metrics = {**HEALTHY, "runway_months": 2.0}
    state, results = SixGateEvaluator().evaluate(metrics)
    assert state == SystemState.FREEZE
    epg = next(r for r in results if r.gate == "EconomicGate")
    assert epg.state == GateState.FAIL


def test_zero_learning_triggers_freeze():
    metrics = {**HEALTHY, "lessons_learned_weekly": 0}
    state, results = SixGateEvaluator().evaluate(metrics)
    assert state == SystemState.FREEZE
    cgg = next(r for r in results if r.gate == "ConstitutionalGate")
    assert cgg.state == GateState.FAIL


def test_low_verification_triggers_hold_or_fail():
    metrics = {**HEALTHY, "verification_pass_rate": 0.55}
    state, results = SixGateEvaluator().evaluate(metrics)
    eg = next(r for r in results if r.gate == "EpistemicGate")
    assert eg.state in (GateState.HOLD, GateState.FAIL)


# ---------------------------------------------------------------------------
# EpistemicGate — reasoning quality
# ---------------------------------------------------------------------------

def test_epistemic_pass_all_healthy():
    result = EpistemicGate().evaluate({
        "verification_pass_rate": 0.95,
        "uncertainty_disclosure_rate": 0.90,
        "assumption_volatility": 0.05,
        "disagreement_persistence": 0.0,
    })
    assert result.state == GateState.PASS


def test_epistemic_fail_low_verification():
    result = EpistemicGate().evaluate({"verification_pass_rate": 0.40})
    assert result.state == GateState.FAIL


def test_epistemic_hold_marginal_verification():
    result = EpistemicGate().evaluate({"verification_pass_rate": 0.60})
    assert result.state == GateState.HOLD


def test_epistemic_fail_low_uncertainty_disclosure():
    result = EpistemicGate().evaluate({"uncertainty_disclosure_rate": 0.20})
    assert result.state == GateState.FAIL


def test_epistemic_fail_high_disagreement():
    result = EpistemicGate().evaluate({"disagreement_persistence": 0.60})
    assert result.state == GateState.FAIL


def test_epistemic_hold_elevated_disagreement():
    result = EpistemicGate().evaluate({"disagreement_persistence": 0.40})
    assert result.state == GateState.HOLD


def test_epistemic_hold_high_assumption_volatility():
    result = EpistemicGate().evaluate({"assumption_volatility": 0.30})
    assert result.state == GateState.HOLD


def test_epistemic_custom_threshold():
    gate = EpistemicGate(verification_hold=0.60)
    # 0.65 is below default hold (0.70) but above custom hold (0.60)
    result = gate.evaluate({"verification_pass_rate": 0.65})
    assert result.state == GateState.PASS


def test_epistemic_missing_keys_use_safe_defaults():
    # All missing → safe defaults → PASS
    result = EpistemicGate().evaluate({})
    assert result.state == GateState.PASS


# ---------------------------------------------------------------------------
# RiskGate — trust and safety
# ---------------------------------------------------------------------------

def test_risk_pass_all_healthy():
    result = RiskGate().evaluate({
        "misuse_risk_index": 0.05,
        "irreversibility_score": 0.10,
        "channel_health": 0.95,
        "security_critical_events": 0,
    })
    assert result.state == GateState.PASS


def test_risk_fail_critical_security_event():
    result = RiskGate().evaluate({"security_critical_events": 1})
    assert result.state == GateState.FAIL


def test_risk_fail_dead_channel():
    result = RiskGate().evaluate({"channel_health": 0.20})
    assert result.state == GateState.FAIL


def test_risk_hold_degraded_channel():
    result = RiskGate().evaluate({"channel_health": 0.60})
    assert result.state == GateState.HOLD


def test_risk_fail_high_misuse_risk():
    result = RiskGate().evaluate({"misuse_risk_index": 0.85})
    assert result.state == GateState.FAIL


def test_risk_hold_multiple_high_security_events():
    result = RiskGate().evaluate({"security_high_events": 3})
    assert result.state == GateState.HOLD


def test_risk_custom_channel_threshold():
    gate = RiskGate(channel_fail=0.30)
    # 0.40 is above custom fail (0.30) but below default fail (0.50)
    result = gate.evaluate({"channel_health": 0.40})
    assert result.state != GateState.FAIL


# ---------------------------------------------------------------------------
# GovernanceGate — audit and control integrity
# ---------------------------------------------------------------------------

def test_governance_pass_all_healthy():
    result = GovernanceGate().evaluate({
        "control_bypass_attempts": 0,
        "audit_coverage": 0.98,
        "metric_anomaly_score": 0.05,
        "test_pass_rate": 0.99,
    })
    assert result.state == GateState.PASS


def test_governance_fail_control_bypass():
    result = GovernanceGate().evaluate({"control_bypass_attempts": 1})
    assert result.state == GateState.FAIL


def test_governance_fail_low_audit_coverage():
    result = GovernanceGate().evaluate({"audit_coverage": 0.80})
    assert result.state == GateState.FAIL


def test_governance_fail_high_anomaly():
    result = GovernanceGate().evaluate({"metric_anomaly_score": 0.85})
    assert result.state == GateState.FAIL


def test_governance_hold_moderate_anomaly():
    result = GovernanceGate().evaluate({"metric_anomaly_score": 0.65})
    assert result.state == GateState.HOLD


# ---------------------------------------------------------------------------
# EconomicGate — financial sustainability (pre-revenue mode)
# ---------------------------------------------------------------------------

def test_economic_pass_pre_revenue():
    result = EconomicGate().evaluate({
        "stage": "pre_revenue",
        "runway_months": 10.0,
        "dli_completion_rate": 0.08,
        "user_return_rate": 0.20,
        "value_demo_count": 5,
    })
    assert result.state == GateState.PASS


def test_economic_fail_critical_runway():
    result = EconomicGate().evaluate({"runway_months": 1.5})
    assert result.state == GateState.FAIL


def test_economic_hold_low_runway():
    result = EconomicGate().evaluate({
        "runway_months": 4.5,
        "stage": "pre_revenue",
        "value_demo_count": 5,
    })
    assert result.state == GateState.HOLD


def test_economic_fail_zero_value_demos():
    result = EconomicGate().evaluate({
        "stage": "pre_revenue",
        "runway_months": 10.0,
        "value_demo_count": 0,
    })
    assert result.state == GateState.FAIL


def test_economic_hold_low_return_rate():
    result = EconomicGate().evaluate({
        "stage": "pre_revenue",
        "runway_months": 10.0,
        "value_demo_count": 5,
        "dli_completion_rate": 0.08,
        "user_return_rate": 0.10,
    })
    assert result.state == GateState.HOLD


def test_economic_pass_post_revenue():
    result = EconomicGate().evaluate({
        "stage": "post_revenue",
        "runway_months": 10.0,
        "gross_margin": 0.70,
        "cac": 150.0,
        "churn_rate": 0.05,
        "ltv_cac_ratio": 4.0,
    })
    assert result.state == GateState.PASS


def test_economic_fail_post_revenue_low_margin():
    result = EconomicGate().evaluate({
        "stage": "post_revenue",
        "runway_months": 10.0,
        "gross_margin": 0.30,
    })
    assert result.state == GateState.FAIL


def test_economic_custom_runway_threshold():
    gate = EconomicGate(runway_fail=6.0, runway_hold=9.0)
    result = gate.evaluate({
        "stage": "pre_revenue",
        "runway_months": 7.0,
        "value_demo_count": 5,
    })
    assert result.state == GateState.HOLD  # 7.0 < custom hold (9.0)


# ---------------------------------------------------------------------------
# AutonomyGate — Level 4+ autonomous operation
# ---------------------------------------------------------------------------

def test_autonomy_pass_all_healthy():
    result = AutonomyGate().evaluate({
        "human_minutes_per_day": 20.0,
        "decisions_per_day": 150,
        "agent_activation_rate": 0.80,
        "escalations_per_day": 2,
        "auto_recovery_rate": 0.90,
    })
    assert result.state == GateState.PASS


def test_autonomy_fail_excessive_human_involvement():
    result = AutonomyGate().evaluate({"human_minutes_per_day": 150.0})
    assert result.state == GateState.FAIL


def test_autonomy_fail_near_zero_decisions():
    result = AutonomyGate().evaluate({"decisions_per_day": 5})
    assert result.state == GateState.FAIL


def test_autonomy_fail_critical_dormancy():
    result = AutonomyGate().evaluate({"agent_activation_rate": 0.10})
    assert result.state == GateState.FAIL


def test_autonomy_hold_low_decisions():
    result = AutonomyGate().evaluate({"decisions_per_day": 30})
    assert result.state == GateState.HOLD


# ---------------------------------------------------------------------------
# ConstitutionalGate — self-improvement
# ---------------------------------------------------------------------------

def test_constitutional_pass_all_healthy():
    result = ConstitutionalGate().evaluate({
        "lessons_learned_weekly": 3,
        "bug_recurrence_rate": 0.05,
        "amendments_per_month": 2,
        "knowledge_freshness": 0.80,
        "enforcement_coverage": 0.90,
    })
    assert result.state == GateState.PASS


def test_constitutional_fail_zero_lessons():
    result = ConstitutionalGate().evaluate({"lessons_learned_weekly": 0})
    assert result.state == GateState.FAIL


def test_constitutional_fail_zero_amendments():
    result = ConstitutionalGate().evaluate({
        "lessons_learned_weekly": 3,
        "amendments_per_month": 0,
    })
    assert result.state == GateState.FAIL


def test_constitutional_fail_stale_knowledge():
    result = ConstitutionalGate().evaluate({
        "lessons_learned_weekly": 3,
        "amendments_per_month": 2,
        "knowledge_freshness": 0.20,
    })
    assert result.state == GateState.FAIL


def test_constitutional_hold_low_enforcement():
    result = ConstitutionalGate().evaluate({
        "lessons_learned_weekly": 3,
        "amendments_per_month": 2,
        "enforcement_coverage": 0.60,
    })
    assert result.state == GateState.HOLD


# ---------------------------------------------------------------------------
# Hard constraints
# ---------------------------------------------------------------------------

def test_hc11_silent_outage_detected():
    violations = check_hard_constraints({
        "hours_since_last_execution": 30,
        "failing_tests": 0,
    })
    assert any(v.id == "HC-11" for v in violations)


def test_hc1_failing_tests_detected():
    violations = check_hard_constraints({"failing_tests": 3})
    assert any(v.id == "HC-1" for v in violations)


def test_hc2_budget_exceeded():
    violations = check_hard_constraints({
        "proposed_spend": 600,
        "approved_budget": 500,
    })
    assert any(v.id == "HC-2" for v in violations)


def test_hc3_runway_below_floor():
    violations = check_hard_constraints({"runway_months": 2.0})
    assert any(v.id == "HC-3" for v in violations)


def test_hc12_gate_override_detected():
    violations = check_hard_constraints({
        "gate_override_without_amendment": True,
    })
    assert any(v.id == "HC-12" for v in violations)


def test_clean_system_has_no_violations():
    violations = check_hard_constraints({
        "failing_tests": 0,
        "hours_since_last_execution": 4,
        "proposed_spend": 100,
        "approved_budget": 500,
    })
    assert len(violations) == 0


def test_hc_fail_closed_on_check_error():
    """Fail-CLOSED: if a check raises, the constraint is treated as violated."""
    from constitutional_agent.hard_constraints import HardConstraint

    def bad_check(ctx):
        raise RuntimeError("check failed unexpectedly")

    hc = HardConstraint(
        id="HC-TEST",
        description="Test constraint with broken check",
        check=bad_check,
        remedy="Fix the check",
    )
    assert hc.is_violated({}) is True  # fail-CLOSED


# ---------------------------------------------------------------------------
# agenthustler failure mode tests
# ---------------------------------------------------------------------------

def test_agenthustler_broken_wallet_caught_by_hc11():
    """HC-11: no silent outage >24h catches the broken Lightning wallet."""
    violations = check_hard_constraints({
        "hours_since_last_execution": 336,  # 14 days of silence
        "failing_tests": 0,
    })
    assert any(v.id == "HC-11" for v in violations)


def test_agenthustler_strategy_spiral_caught_by_cgg():
    """CGG: zero learning velocity catches the 30-run MCP death spiral."""
    metrics = {**HEALTHY, "lessons_learned_weekly": 0}
    state, results = SixGateEvaluator().evaluate(metrics)
    cgg = next(r for r in results if r.gate == "ConstitutionalGate")
    assert cgg.state == GateState.FAIL


def test_agenthustler_dead_channel_caught_by_risk():
    """RiskGate: 0% channel health catches posting to shadow-banned HN account."""
    result = RiskGate().evaluate({"channel_health": 0.0})
    assert result.state == GateState.FAIL
