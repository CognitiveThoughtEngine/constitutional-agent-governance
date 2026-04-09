"""
Constitutional Agent — Six Gate Architecture
Pre-execution constitutional evaluation for autonomous AI agents.

Based on HRAO-E Constitutional Framework (cognitivethoughtengine.com)
Section 8: Gate Architecture

The six gates evaluate every decision before it is executed. They are not
a policy lookup table — they evaluate decisions against constitutional
principles, and can reason about novel scenarios that no specific policy
addresses.

Gate state transitions:
    ALL PASS + targets met  -> COMPOUND (maximum growth)
    ALL PASS                -> RUN      (normal operation)
    ANY HOLD                -> THROTTLE (conserve resources)
    ANY FAIL                -> FREEZE   (stop all discretionary spend)
    FREEZE > 24h            -> STOP     (human intervention required)

Usage:
    from constitutional_agent.gates import SixGateEvaluator

    evaluator = SixGateEvaluator()
    system_state, results = evaluator.evaluate(metrics)
"""

from __future__ import annotations

from typing import Any, Optional

from constitutional_agent.schema import GateResult, GateState, SystemState


# ---------------------------------------------------------------------------
# Epistemic Gate (EG)
# ---------------------------------------------------------------------------

class EpistemicGate:
    """
    Prevents false certainty.

    An agent that acts on unverified assumptions, never discloses uncertainty,
    or repeatedly ignores disagreement signals is epistemically unsound. This
    gate enforces reasoning quality before execution — not just "is this action
    permitted" but "has the agent earned confidence in its reasoning?"

    Metrics evaluated:
        verification_pass_rate: Fraction of recent decisions externally
            verified as correct (not self-reported). HOLD < 0.70, FAIL < 0.50.
        uncertainty_disclosure_rate: Fraction of decisions that appropriately
            disclosed uncertainty. FAIL < 0.30.
        assumption_volatility: How often core assumptions changed without new
            evidence. HOLD > 0.25.
        disagreement_persistence: Ongoing signals contradicting agent
            conclusions that have not been resolved. HOLD >= 0.35, FAIL >= 0.55.

    agenthustler case study (dev.to, 200-run experiment):
        The agent mispriced Lightning actors at $0.00005 — a foundational
        assumption never verified against actual invoices. EG would have blocked
        execution until the cost basis was confirmed externally, not assumed.
    """

    VERIFICATION_FAIL = 0.50
    VERIFICATION_HOLD = 0.70
    UNCERTAINTY_FAIL = 0.30
    ASSUMPTION_VOLATILITY_HOLD = 0.25
    DISAGREEMENT_FAIL = 0.55
    DISAGREEMENT_HOLD = 0.35

    def __init__(
        self,
        *,
        verification_fail: float = 0.50,
        verification_hold: float = 0.70,
        uncertainty_fail: float = 0.30,
        assumption_volatility_hold: float = 0.25,
        disagreement_fail: float = 0.55,
        disagreement_hold: float = 0.35,
    ) -> None:
        self.VERIFICATION_FAIL = verification_fail
        self.VERIFICATION_HOLD = verification_hold
        self.UNCERTAINTY_FAIL = uncertainty_fail
        self.ASSUMPTION_VOLATILITY_HOLD = assumption_volatility_hold
        self.DISAGREEMENT_FAIL = disagreement_fail
        self.DISAGREEMENT_HOLD = disagreement_hold

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        """
        Evaluate epistemic health from the provided metrics dict.

        Expected keys (all optional — missing keys use safe defaults):
            verification_pass_rate (float, 0-1): External verification success.
            uncertainty_disclosure_rate (float, 0-1): Uncertainty disclosed.
            assumption_volatility (float, 0-1): Core assumption churn.
            disagreement_persistence (float, 0-1): Unresolved contradictions.

        Returns:
            GateResult with state PASS | HOLD | FAIL.
        """
        vpr = float(metrics.get("verification_pass_rate", 1.0))
        udr = float(metrics.get("uncertainty_disclosure_rate", 1.0))
        avi = float(metrics.get("assumption_volatility", 0.0))
        dps = float(metrics.get("disagreement_persistence", 0.0))

        # FAIL conditions — hard stops
        if dps >= self.DISAGREEMENT_FAIL:
            return GateResult(
                gate="EpistemicGate",
                state=GateState.FAIL,
                reason=(
                    f"Persistent unresolved disagreement (disagreement_persistence "
                    f"{dps:.2f} >= {self.DISAGREEMENT_FAIL}). "
                    "Agent must resolve contradicting signals before proceeding."
                ),
                metric=dps,
            )

        if udr < self.UNCERTAINTY_FAIL:
            return GateResult(
                gate="EpistemicGate",
                state=GateState.FAIL,
                reason=(
                    f"Insufficient uncertainty disclosure "
                    f"(uncertainty_disclosure_rate {udr:.2f} < {self.UNCERTAINTY_FAIL}). "
                    "Agent is projecting false confidence."
                ),
                metric=udr,
            )

        if vpr < self.VERIFICATION_FAIL:
            return GateResult(
                gate="EpistemicGate",
                state=GateState.FAIL,
                reason=(
                    f"Low external verification rate "
                    f"(verification_pass_rate {vpr:.2f} < {self.VERIFICATION_FAIL}). "
                    "Agent decisions are not being confirmed by external sources."
                ),
                metric=vpr,
            )

        # HOLD conditions — throttle
        if dps >= self.DISAGREEMENT_HOLD:
            return GateResult(
                gate="EpistemicGate",
                state=GateState.HOLD,
                reason=(
                    f"Elevated disagreement signals "
                    f"(disagreement_persistence {dps:.2f} >= {self.DISAGREEMENT_HOLD}). "
                    "Throttle until contradictions are resolved."
                ),
                metric=dps,
            )

        if avi > self.ASSUMPTION_VOLATILITY_HOLD:
            return GateResult(
                gate="EpistemicGate",
                state=GateState.HOLD,
                reason=(
                    f"High assumption volatility "
                    f"(assumption_volatility {avi:.2f} > {self.ASSUMPTION_VOLATILITY_HOLD}). "
                    "Core beliefs are unstable — verify before acting."
                ),
                metric=avi,
            )

        if vpr < self.VERIFICATION_HOLD:
            return GateResult(
                gate="EpistemicGate",
                state=GateState.HOLD,
                reason=(
                    f"Marginal external verification "
                    f"(verification_pass_rate {vpr:.2f} < {self.VERIFICATION_HOLD}). "
                    "Increase external validation before expanding action scope."
                ),
                metric=vpr,
            )

        return GateResult(
            gate="EpistemicGate",
            state=GateState.PASS,
            reason=(
                f"Epistemic health confirmed (verification {vpr:.2f}, "
                f"uncertainty disclosure {udr:.2f}, "
                f"assumption volatility {avi:.2f}, "
                f"disagreement {dps:.2f})."
            ),
            metric=vpr,
        )


# ---------------------------------------------------------------------------
# Risk Gate (RG)
# ---------------------------------------------------------------------------

class RiskGate:
    """
    Prevents trust damage.

    An agent that takes irreversible actions, exposes users to harm, or
    continues operating in compromised channels (shadow-banned, rate-limited,
    or error-returning endpoints) is creating trust debt that is harder to
    repay than any short-term gain is worth.

    Metrics evaluated:
        misuse_risk_index (float, 0-1): Probability outbound actions cause harm
            to users or third parties. HOLD >= 0.65, FAIL >= 0.80.
        irreversibility_score (float, 0-1): How hard to undo pending actions.
            HOLD >= 0.60, FAIL >= 0.80.
        channel_health (float, 0-1): Health of outbound channels
            (API success rate, platform standing). HOLD < 0.70, FAIL < 0.50.
        security_critical_events (int): CRITICAL security events in last 24h.
            Any value >= 1 -> FAIL immediately.
        security_high_events (int): HIGH security events in last 24h.
            >= 3 -> HOLD.

    agenthustler case study (dev.to, 200-run experiment):
        The agent was shadow-banned by Hacker News after week 2 but kept
        posting for 30 more runs. Zero posts were visible. The RG
        channel_health check would have detected the 0% success rate on HN
        posts and blocked further spend on that channel.
    """

    MISUSE_FAIL = 0.80
    MISUSE_HOLD = 0.65
    IRREVERSIBILITY_FAIL = 0.80
    IRREVERSIBILITY_HOLD = 0.60
    CHANNEL_FAIL = 0.50
    CHANNEL_HOLD = 0.70

    def __init__(
        self,
        *,
        misuse_fail: float = 0.80,
        misuse_hold: float = 0.65,
        irreversibility_fail: float = 0.80,
        irreversibility_hold: float = 0.60,
        channel_fail: float = 0.50,
        channel_hold: float = 0.70,
    ) -> None:
        self.MISUSE_FAIL = misuse_fail
        self.MISUSE_HOLD = misuse_hold
        self.IRREVERSIBILITY_FAIL = irreversibility_fail
        self.IRREVERSIBILITY_HOLD = irreversibility_hold
        self.CHANNEL_FAIL = channel_fail
        self.CHANNEL_HOLD = channel_hold

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        """
        Evaluate risk posture from the provided metrics dict.

        Expected keys (all optional — missing keys use safe defaults):
            misuse_risk_index (float, 0-1): Outbound harm probability.
            irreversibility_score (float, 0-1): Action reversibility.
            channel_health (float, 0-1): Outbound channel health.
            security_critical_events (int): CRITICAL security events (24h).
            security_high_events (int): HIGH security events (24h).

        Returns:
            GateResult with state PASS | HOLD | FAIL.
        """
        mri = float(metrics.get("misuse_risk_index", 0.0))
        ips = float(metrics.get("irreversibility_score", 0.0))
        channel = float(metrics.get("channel_health", 1.0))
        critical = int(metrics.get("security_critical_events", 0))
        high = int(metrics.get("security_high_events", 0))

        # FAIL conditions — security events take absolute priority
        if critical >= 1:
            return GateResult(
                gate="RiskGate",
                state=GateState.FAIL,
                reason=(
                    f"CRITICAL security events detected in last 24h "
                    f"({critical} event(s)). Freeze until investigated."
                ),
                metric=float(critical),
                context={"security_critical_events": critical},
            )

        if mri >= self.MISUSE_FAIL:
            return GateResult(
                gate="RiskGate",
                state=GateState.FAIL,
                reason=(
                    f"Critical misuse risk (misuse_risk_index {mri:.2f} >= {self.MISUSE_FAIL}). "
                    "Outbound actions have unacceptable harm probability."
                ),
                metric=mri,
            )

        if ips >= self.IRREVERSIBILITY_FAIL:
            return GateResult(
                gate="RiskGate",
                state=GateState.FAIL,
                reason=(
                    f"Critical irreversibility (irreversibility_score {ips:.2f} >= "
                    f"{self.IRREVERSIBILITY_FAIL}). Pending actions cannot be undone."
                ),
                metric=ips,
            )

        if channel < self.CHANNEL_FAIL:
            return GateResult(
                gate="RiskGate",
                state=GateState.FAIL,
                reason=(
                    f"Channel health critical (channel_health {channel:.2f} < "
                    f"{self.CHANNEL_FAIL}). Outbound channels are failing or blocked. "
                    "Stop spending on dead channels."
                ),
                metric=channel,
            )

        # HOLD conditions
        if high >= 3:
            return GateResult(
                gate="RiskGate",
                state=GateState.HOLD,
                reason=(
                    f"Multiple HIGH security events in 24h ({high} events). "
                    "Throttle until security posture improves."
                ),
                metric=float(high),
                context={"security_high_events": high},
            )

        if mri >= self.MISUSE_HOLD:
            return GateResult(
                gate="RiskGate",
                state=GateState.HOLD,
                reason=(
                    f"Elevated misuse risk (misuse_risk_index {mri:.2f} >= "
                    f"{self.MISUSE_HOLD}). Throttle high-exposure actions."
                ),
                metric=mri,
            )

        if ips >= self.IRREVERSIBILITY_HOLD:
            return GateResult(
                gate="RiskGate",
                state=GateState.HOLD,
                reason=(
                    f"Elevated irreversibility (irreversibility_score {ips:.2f} >= "
                    f"{self.IRREVERSIBILITY_HOLD}). Prefer reversible actions."
                ),
                metric=ips,
            )

        if channel < self.CHANNEL_HOLD:
            return GateResult(
                gate="RiskGate",
                state=GateState.HOLD,
                reason=(
                    f"Degraded channel health (channel_health {channel:.2f} < "
                    f"{self.CHANNEL_HOLD}). Investigate channel failures before expanding."
                ),
                metric=channel,
            )

        return GateResult(
            gate="RiskGate",
            state=GateState.PASS,
            reason=(
                f"Risk levels acceptable (misuse_risk {mri:.2f}, "
                f"irreversibility {ips:.2f}, channel_health {channel:.2f})."
            ),
            metric=mri,
        )


# ---------------------------------------------------------------------------
# Governance Gate (GG)
# ---------------------------------------------------------------------------

class GovernanceGate:
    """
    Prevents gaming.

    An agent optimizing for metrics can defeat its own governance by gaming
    the metrics used to evaluate it. This gate detects when audit coverage
    drops, when control bypass is attempted, or when metric patterns suggest
    self-serving manipulation rather than genuine performance improvement.

    Metrics evaluated:
        control_bypass_attempts (int): Any attempt to circumvent governance
            controls. Any value >= 1 -> FAIL immediately (zero tolerance).
        audit_coverage (float, 0-1): Fraction of expected events that are
            logged. FAIL < 0.95 (high bar — gaps in audit coverage hide problems).
        metric_anomaly_score (float, 0-1): Statistical indicator of gaming
            (metrics improving while downstream outcomes do not).
            HOLD >= 0.60, FAIL >= 0.80.
        test_pass_rate (float, 0-1): Fraction of governance tests passing.
            HOLD < 0.90, FAIL < 0.70.
    """

    AUDIT_FAIL = 0.95
    METRIC_ANOMALY_FAIL = 0.80
    METRIC_ANOMALY_HOLD = 0.60
    TEST_PASS_HOLD = 0.90
    TEST_PASS_FAIL = 0.70

    def __init__(
        self,
        *,
        audit_fail: float = 0.95,
        metric_anomaly_fail: float = 0.80,
        metric_anomaly_hold: float = 0.60,
        test_pass_hold: float = 0.90,
        test_pass_fail: float = 0.70,
    ) -> None:
        self.AUDIT_FAIL = audit_fail
        self.METRIC_ANOMALY_FAIL = metric_anomaly_fail
        self.METRIC_ANOMALY_HOLD = metric_anomaly_hold
        self.TEST_PASS_HOLD = test_pass_hold
        self.TEST_PASS_FAIL = test_pass_fail

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        """
        Evaluate governance integrity from the provided metrics dict.

        Expected keys (all optional — missing keys use safe defaults):
            control_bypass_attempts (int): Governance bypass attempts.
            audit_coverage (float, 0-1): Event logging completeness.
            metric_anomaly_score (float, 0-1): Gaming detection score.
            test_pass_rate (float, 0-1): Governance test pass rate.

        Returns:
            GateResult with state PASS | HOLD | FAIL.
        """
        cba = int(metrics.get("control_bypass_attempts", 0))
        audit = float(metrics.get("audit_coverage", 1.0))
        anomaly = float(metrics.get("metric_anomaly_score", 0.0))
        test_rate = float(metrics.get("test_pass_rate", 1.0))

        # FAIL — zero tolerance for control bypass
        if cba >= 1:
            return GateResult(
                gate="GovernanceGate",
                state=GateState.FAIL,
                reason=(
                    f"Control bypass attempted ({cba} attempt(s)). "
                    "No agent action can authorize bypassing governance controls. "
                    "Human intervention required."
                ),
                metric=float(cba),
            )

        if audit < self.AUDIT_FAIL:
            return GateResult(
                gate="GovernanceGate",
                state=GateState.FAIL,
                reason=(
                    f"Insufficient audit coverage ({audit:.1%} < {self.AUDIT_FAIL:.0%}). "
                    "Events are not being logged. Governance is blind."
                ),
                metric=audit,
            )

        if anomaly >= self.METRIC_ANOMALY_FAIL:
            return GateResult(
                gate="GovernanceGate",
                state=GateState.FAIL,
                reason=(
                    f"Metric gaming detected (anomaly_score {anomaly:.2f} >= "
                    f"{self.METRIC_ANOMALY_FAIL}). "
                    "Metrics are improving while outcomes are not. Investigate."
                ),
                metric=anomaly,
            )

        if test_rate < self.TEST_PASS_FAIL:
            return GateResult(
                gate="GovernanceGate",
                state=GateState.FAIL,
                reason=(
                    f"Governance tests failing (test_pass_rate {test_rate:.1%} < "
                    f"{self.TEST_PASS_FAIL:.0%}). "
                    "Governance framework has broken constraints."
                ),
                metric=test_rate,
            )

        # HOLD conditions
        if anomaly >= self.METRIC_ANOMALY_HOLD:
            return GateResult(
                gate="GovernanceGate",
                state=GateState.HOLD,
                reason=(
                    f"Possible metric anomaly (anomaly_score {anomaly:.2f} >= "
                    f"{self.METRIC_ANOMALY_HOLD}). "
                    "Monitor for metric gaming. Throttle until clear."
                ),
                metric=anomaly,
            )

        if test_rate < self.TEST_PASS_HOLD:
            return GateResult(
                gate="GovernanceGate",
                state=GateState.HOLD,
                reason=(
                    f"Governance tests degraded (test_pass_rate {test_rate:.1%} < "
                    f"{self.TEST_PASS_HOLD:.0%}). Fix failing tests before expanding."
                ),
                metric=test_rate,
            )

        return GateResult(
            gate="GovernanceGate",
            state=GateState.PASS,
            reason=(
                f"Governance integrity confirmed (bypass attempts {cba}, "
                f"audit coverage {audit:.1%}, anomaly score {anomaly:.2f}, "
                f"test pass rate {test_rate:.1%})."
            ),
            metric=audit,
        )


# ---------------------------------------------------------------------------
# Economic Gate (EPG)
# ---------------------------------------------------------------------------

class EconomicGate:
    """
    Prevents economic ruin.

    An agent can be epistemically sound, low-risk, and well-governed while
    systematically destroying the organization's financial viability. The
    Economic Gate enforces that agents cannot take actions that threaten
    runway, sacrifice sustainable margin, or ignore cost basis.

    Two evaluation modes:
        PRE_REVENUE: Evaluates value creation metrics (engagement, return rate,
            runway) before revenue exists. Avoids penalizing agents for not
            having revenue when the product is still finding its footing.
        POST_REVENUE: Evaluates unit economics (margin, CAC, churn, LTV:CAC).

    Metrics evaluated (PRE_REVENUE mode):
        runway_months (float): Months of runway remaining.
            FAIL < 3.0, HOLD < 6.0.
        dli_completion_rate (float, 0-1): Core value delivery completion.
            FAIL < 0.01, HOLD < 0.05.
        user_return_rate (float, 0-1): 7-day return rate.
            FAIL < 0.05, HOLD < 0.15.
        value_demo_count (int): Documented value demonstration artifacts.
            FAIL = 0, HOLD < 3.

    Metrics evaluated (POST_REVENUE mode):
        gross_margin (float, 0-1): Gross margin. FAIL < 0.45, HOLD < 0.65.
        cac (float): Customer acquisition cost. FAIL > 350, HOLD > 200.
        churn_rate (float, 0-1): Monthly churn. FAIL > 0.15, HOLD > 0.08.
        ltv_cac_ratio (float): LTV:CAC ratio. FAIL < 2.0, HOLD < 3.0.

    agenthustler case study (dev.to, 200-run experiment):
        The agent's broken Lightning wallet went undetected for weeks — it
        accepted payments but never settled. EPG runway monitoring would have
        detected cash not arriving despite apparent revenue, triggering a HOLD
        until the settlement pipeline was verified.
    """

    # Runway thresholds (apply in both modes)
    RUNWAY_FAIL = 3.0
    RUNWAY_HOLD = 6.0

    # PRE_REVENUE value creation thresholds
    DLI_FAIL = 0.01
    DLI_HOLD = 0.05
    RETURN_RATE_FAIL = 0.05
    RETURN_RATE_HOLD = 0.15
    VALUE_DEMO_FAIL = 0
    VALUE_DEMO_HOLD = 3

    # POST_REVENUE unit economics thresholds
    MARGIN_FAIL = 0.45
    MARGIN_HOLD = 0.65
    CAC_FAIL = 350.0
    CAC_HOLD = 200.0
    CHURN_FAIL = 0.15
    CHURN_HOLD = 0.08
    LTV_CAC_FAIL = 2.0
    LTV_CAC_HOLD = 3.0

    def __init__(
        self,
        *,
        runway_fail: float = 3.0,
        runway_hold: float = 6.0,
        dli_fail: float = 0.01,
        dli_hold: float = 0.05,
        return_rate_fail: float = 0.05,
        return_rate_hold: float = 0.15,
        value_demo_fail: int = 0,
        value_demo_hold: int = 3,
        margin_fail: float = 0.45,
        margin_hold: float = 0.65,
        cac_fail: float = 350.0,
        cac_hold: float = 200.0,
        churn_fail: float = 0.15,
        churn_hold: float = 0.08,
        ltv_cac_fail: float = 2.0,
        ltv_cac_hold: float = 3.0,
    ) -> None:
        self.RUNWAY_FAIL = runway_fail
        self.RUNWAY_HOLD = runway_hold
        self.DLI_FAIL = dli_fail
        self.DLI_HOLD = dli_hold
        self.RETURN_RATE_FAIL = return_rate_fail
        self.RETURN_RATE_HOLD = return_rate_hold
        self.VALUE_DEMO_FAIL = value_demo_fail
        self.VALUE_DEMO_HOLD = value_demo_hold
        self.MARGIN_FAIL = margin_fail
        self.MARGIN_HOLD = margin_hold
        self.CAC_FAIL = cac_fail
        self.CAC_HOLD = cac_hold
        self.CHURN_FAIL = churn_fail
        self.CHURN_HOLD = churn_hold
        self.LTV_CAC_FAIL = ltv_cac_fail
        self.LTV_CAC_HOLD = ltv_cac_hold

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        """
        Evaluate economic health from the provided metrics dict.

        The gate automatically selects PRE_REVENUE or POST_REVENUE mode based
        on the 'stage' key (default: 'pre_revenue').

        Expected keys:
            stage (str): 'pre_revenue' | 'post_revenue'. Defaults to 'pre_revenue'.
            runway_months (float): Months of runway. Evaluated in both modes.

            PRE_REVENUE keys:
                dli_completion_rate (float, 0-1): Core value delivery rate.
                user_return_rate (float, 0-1): 7-day user return rate.
                value_demo_count (int): Value demonstration artifacts.

            POST_REVENUE keys:
                gross_margin (float, 0-1): Gross margin.
                cac (float): Customer acquisition cost in dollars.
                churn_rate (float, 0-1): Monthly churn rate.
                ltv_cac_ratio (float): LTV:CAC ratio.

        Returns:
            GateResult with state PASS | HOLD | FAIL.
        """
        stage = metrics.get("stage", "pre_revenue")
        runway = float(metrics.get("runway_months", 12.0))

        # Runway check applies in ALL modes — it is a hard survival floor
        if runway < self.RUNWAY_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"Critical runway shortage ({runway:.1f} months < {self.RUNWAY_FAIL} months). "
                    "Organization may not survive. All discretionary spend frozen."
                ),
                metric=runway,
            )

        if runway < self.RUNWAY_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"Low runway ({runway:.1f} months < {self.RUNWAY_HOLD} months). "
                    "Throttle discretionary spend. Focus on revenue or cost reduction."
                ),
                metric=runway,
            )

        if stage == "post_revenue":
            return self._evaluate_post_revenue(metrics, runway)

        return self._evaluate_pre_revenue(metrics, runway)

    def _evaluate_pre_revenue(
        self, metrics: dict[str, Any], runway: float
    ) -> GateResult:
        """Evaluate value creation metrics for PRE_REVENUE stage."""
        dli = float(metrics.get("dli_completion_rate", 0.0))
        return_rate = float(metrics.get("user_return_rate", 0.0))
        value_demos = int(metrics.get("value_demo_count", 0))

        if value_demos <= self.VALUE_DEMO_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    "No value demonstration artifacts (value_demo_count = 0). "
                    "The agent must demonstrate value creation before expanding spend."
                ),
                metric=float(value_demos),
            )

        if dli < self.DLI_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"Core value delivery failing (dli_completion_rate "
                    f"{dli:.1%} < {self.DLI_FAIL:.0%}). "
                    "Users are not completing the core value experience."
                ),
                metric=dli,
            )

        if return_rate < self.RETURN_RATE_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"No user retention (user_return_rate "
                    f"{return_rate:.1%} < {self.RETURN_RATE_FAIL:.0%}). "
                    "Users are not returning. Value proposition is not sticking."
                ),
                metric=return_rate,
            )

        # HOLD conditions
        if value_demos < self.VALUE_DEMO_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"Insufficient value demonstrations ({value_demos} < "
                    f"{self.VALUE_DEMO_HOLD}). Build more documented proof points."
                ),
                metric=float(value_demos),
            )

        if dli < self.DLI_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"Core value delivery marginal (dli_completion_rate "
                    f"{dli:.1%} < {self.DLI_HOLD:.0%}). Improve completion before scaling."
                ),
                metric=dli,
            )

        if return_rate < self.RETURN_RATE_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"Low user retention (user_return_rate "
                    f"{return_rate:.1%} < {self.RETURN_RATE_HOLD:.0%}). "
                    "Retention must improve before spend increases."
                ),
                metric=return_rate,
            )

        return GateResult(
            gate="EconomicGate",
            state=GateState.PASS,
            reason=(
                f"PRE_REVENUE value creation healthy (runway {runway:.1f}mo, "
                f"DLI completion {dli:.1%}, return rate {return_rate:.1%}, "
                f"value demos {value_demos})."
            ),
            metric=runway,
        )

    def _evaluate_post_revenue(
        self, metrics: dict[str, Any], runway: float
    ) -> GateResult:
        """Evaluate unit economics for POST_REVENUE stage."""
        margin = float(metrics.get("gross_margin", 0.0))
        cac = float(metrics.get("cac", 0.0))
        churn = float(metrics.get("churn_rate", 0.0))
        ltv_cac = float(metrics.get("ltv_cac_ratio", 0.0))

        # FAIL conditions
        if margin < self.MARGIN_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"Unsustainable margin (gross_margin {margin:.1%} < "
                    f"{self.MARGIN_FAIL:.0%}). Business is structurally unprofitable."
                ),
                metric=margin,
            )

        if cac > self.CAC_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"Customer acquisition cost critical (CAC ${cac:.0f} > "
                    f"${self.CAC_FAIL:.0f}). Unit economics are broken."
                ),
                metric=cac,
            )

        if churn > self.CHURN_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"Critical churn (churn_rate {churn:.1%} > "
                    f"{self.CHURN_FAIL:.0%}). Customers are leaving faster than acquired."
                ),
                metric=churn,
            )

        if ltv_cac > 0 and ltv_cac < self.LTV_CAC_FAIL:
            return GateResult(
                gate="EconomicGate",
                state=GateState.FAIL,
                reason=(
                    f"LTV:CAC ratio below viability floor "
                    f"({ltv_cac:.1f} < {self.LTV_CAC_FAIL:.1f}). "
                    "Customer lifetime value does not justify acquisition cost."
                ),
                metric=ltv_cac,
            )

        # HOLD conditions
        if margin < self.MARGIN_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"Margin below target (gross_margin {margin:.1%} < "
                    f"{self.MARGIN_HOLD:.0%}). Reduce costs or raise prices."
                ),
                metric=margin,
            )

        if cac > self.CAC_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"High customer acquisition cost (CAC ${cac:.0f} > "
                    f"${self.CAC_HOLD:.0f}). Optimize acquisition before scaling spend."
                ),
                metric=cac,
            )

        if churn > self.CHURN_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"Elevated churn (churn_rate {churn:.1%} > "
                    f"{self.CHURN_HOLD:.0%}). Fix retention before acquiring more customers."
                ),
                metric=churn,
            )

        if ltv_cac > 0 and ltv_cac < self.LTV_CAC_HOLD:
            return GateResult(
                gate="EconomicGate",
                state=GateState.HOLD,
                reason=(
                    f"LTV:CAC below target ({ltv_cac:.1f} < {self.LTV_CAC_HOLD:.1f}). "
                    "Improve retention or reduce CAC before scaling."
                ),
                metric=ltv_cac,
            )

        return GateResult(
            gate="EconomicGate",
            state=GateState.PASS,
            reason=(
                f"POST_REVENUE economics healthy (runway {runway:.1f}mo, "
                f"margin {margin:.1%}, CAC ${cac:.0f}, "
                f"churn {churn:.1%}, LTV:CAC {ltv_cac:.1f})."
            ),
            metric=margin,
        )


# ---------------------------------------------------------------------------
# Autonomy Gate (AAG)
# ---------------------------------------------------------------------------

class AutonomyGate:
    """
    Ensures Level 4+ autonomous operation.

    An autonomous agent that requires constant human intervention is not
    autonomous — it is a semi-automated workflow with a human in the loop.
    This gate measures whether agents are actually deciding and executing
    independently, and flags when human involvement has become a crutch.

    The gate also prevents the inverse: agents that never escalate and make
    decisions that should require human review. The target is the minimum
    viable escalation rate — not zero, and not excessive.

    Metrics evaluated:
        human_minutes_per_day (float): CEO/operator time spent on agent work.
            HOLD > 60, FAIL > 120 minutes per day.
        decisions_per_day (int): Autonomous decisions made without human input.
            HOLD < 50, FAIL < 10.
        agent_activation_rate (float, 0-1): Fraction of agents executing on
            each cycle. HOLD < 0.50, FAIL < 0.25.
        escalations_per_day (int): Human escalations triggered.
            HOLD > 5, FAIL > 10 (too many = not autonomous).
        auto_recovery_rate (float, 0-1): Agent self-recovery from failures.
            HOLD < 0.70, FAIL < 0.50.
    """

    HUMAN_MINUTES_FAIL = 120.0
    HUMAN_MINUTES_HOLD = 60.0
    DECISIONS_FAIL = 10
    DECISIONS_HOLD = 50
    ACTIVATION_FAIL = 0.25
    ACTIVATION_HOLD = 0.50
    ESCALATIONS_FAIL = 10
    ESCALATIONS_HOLD = 5
    AUTO_RECOVERY_FAIL = 0.50
    AUTO_RECOVERY_HOLD = 0.70

    def __init__(
        self,
        *,
        human_minutes_fail: float = 120.0,
        human_minutes_hold: float = 60.0,
        decisions_fail: int = 10,
        decisions_hold: int = 50,
        activation_fail: float = 0.25,
        activation_hold: float = 0.50,
        escalations_fail: int = 10,
        escalations_hold: int = 5,
        auto_recovery_fail: float = 0.50,
        auto_recovery_hold: float = 0.70,
    ) -> None:
        self.HUMAN_MINUTES_FAIL = human_minutes_fail
        self.HUMAN_MINUTES_HOLD = human_minutes_hold
        self.DECISIONS_FAIL = decisions_fail
        self.DECISIONS_HOLD = decisions_hold
        self.ACTIVATION_FAIL = activation_fail
        self.ACTIVATION_HOLD = activation_hold
        self.ESCALATIONS_FAIL = escalations_fail
        self.ESCALATIONS_HOLD = escalations_hold
        self.AUTO_RECOVERY_FAIL = auto_recovery_fail
        self.AUTO_RECOVERY_HOLD = auto_recovery_hold

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        """
        Evaluate autonomy health from the provided metrics dict.

        Expected keys (all optional — missing keys use safe defaults):
            human_minutes_per_day (float): Operator time on agent work.
            decisions_per_day (int): Autonomous decisions per day.
            agent_activation_rate (float, 0-1): Agents executing per cycle.
            escalations_per_day (int): Human escalations per day.
            auto_recovery_rate (float, 0-1): Self-recovery from failures.

        Returns:
            GateResult with state PASS | HOLD | FAIL.
        """
        human_min = float(metrics.get("human_minutes_per_day", 0.0))
        decisions = int(metrics.get("decisions_per_day", 200))
        activation = float(metrics.get("agent_activation_rate", 0.75))
        escalations = int(metrics.get("escalations_per_day", 0))
        recovery = float(metrics.get("auto_recovery_rate", 0.85))

        # FAIL conditions
        if human_min > self.HUMAN_MINUTES_FAIL:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.FAIL,
                reason=(
                    f"Excessive operator involvement ({human_min:.0f} min/day > "
                    f"{self.HUMAN_MINUTES_FAIL:.0f}). System is not autonomous."
                ),
                metric=human_min,
            )

        if decisions < self.DECISIONS_FAIL:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.FAIL,
                reason=(
                    f"Near-zero autonomous decisions ({decisions}/day < "
                    f"{self.DECISIONS_FAIL}). Agents are not executing."
                ),
                metric=float(decisions),
            )

        if activation < self.ACTIVATION_FAIL:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.FAIL,
                reason=(
                    f"Critical agent dormancy (activation_rate {activation:.1%} < "
                    f"{self.ACTIVATION_FAIL:.0%}). Most agents are not running."
                ),
                metric=activation,
            )

        if escalations > self.ESCALATIONS_FAIL:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.FAIL,
                reason=(
                    f"Excessive escalations ({escalations}/day > "
                    f"{self.ESCALATIONS_FAIL}). Agents cannot decide without humans."
                ),
                metric=float(escalations),
            )

        if recovery < self.AUTO_RECOVERY_FAIL:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.FAIL,
                reason=(
                    f"Low self-recovery (auto_recovery_rate {recovery:.1%} < "
                    f"{self.AUTO_RECOVERY_FAIL:.0%}). Agents require constant human repair."
                ),
                metric=recovery,
            )

        # HOLD conditions
        if human_min > self.HUMAN_MINUTES_HOLD:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.HOLD,
                reason=(
                    f"High operator involvement ({human_min:.0f} min/day > "
                    f"{self.HUMAN_MINUTES_HOLD:.0f}). Reduce manual intervention."
                ),
                metric=human_min,
            )

        if decisions < self.DECISIONS_HOLD:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.HOLD,
                reason=(
                    f"Low autonomous decision rate ({decisions}/day < "
                    f"{self.DECISIONS_HOLD}). Agents are underutilized."
                ),
                metric=float(decisions),
            )

        if activation < self.ACTIVATION_HOLD:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.HOLD,
                reason=(
                    f"Low agent activation ({activation:.1%} < "
                    f"{self.ACTIVATION_HOLD:.0%}). Investigate dormant agents."
                ),
                metric=activation,
            )

        if escalations > self.ESCALATIONS_HOLD:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.HOLD,
                reason=(
                    f"Elevated escalations ({escalations}/day > "
                    f"{self.ESCALATIONS_HOLD}). Improve agent decision coverage."
                ),
                metric=float(escalations),
            )

        if recovery < self.AUTO_RECOVERY_HOLD:
            return GateResult(
                gate="AutonomyGate",
                state=GateState.HOLD,
                reason=(
                    f"Marginal self-recovery ({recovery:.1%} < "
                    f"{self.AUTO_RECOVERY_HOLD:.0%}). Improve failure handling."
                ),
                metric=recovery,
            )

        return GateResult(
            gate="AutonomyGate",
            state=GateState.PASS,
            reason=(
                f"Autonomy healthy (operator time {human_min:.0f}min/day, "
                f"decisions {decisions}/day, "
                f"activation {activation:.1%}, recovery {recovery:.1%})."
            ),
            metric=float(decisions),
        )


# ---------------------------------------------------------------------------
# Constitutional Gate (CGG)
# ---------------------------------------------------------------------------

class ConstitutionalGate:
    """
    Ensures self-improvement and constitutional vitality.

    A governance system that never changes is a brittle one. An agent that
    repeats the same failures is not learning. This gate enforces that the
    constitutional system is alive: lessons are being extracted, governance
    rules are evolving through formal amendment, and the agent's capabilities
    are expanding rather than stagnating.

    Metrics evaluated:
        lessons_learned_weekly (int): Documented lessons per week.
            HOLD < 1, FAIL = 0.
        bug_recurrence_rate (float, 0-1): Fraction of bugs that re-appear
            after fix. HOLD > 0.15, FAIL > 0.30.
        amendments_per_month (int): Constitutional amendments ratified.
            HOLD < 1, FAIL = 0.
        knowledge_freshness (float, 0-1): Fraction of docs updated in 30d.
            HOLD < 0.50, FAIL < 0.30.
        enforcement_coverage (float, 0-1): Fraction of hard constraints with
            automated enforcement. HOLD < 0.70, FAIL < 0.50.

    agenthustler case study (dev.to, 200-run experiment):
        The agent locked on MCP servers as its strategy for 30+ consecutive
        runs despite zero conversion. CGG's learning velocity check would have
        flagged zero lessons learned from the failure pattern, triggering a
        HOLD until the agent documented what it had learned and proposed an
        alternative approach.
    """

    LESSONS_HOLD = 1
    BUG_RECURRENCE_HOLD = 0.15
    BUG_RECURRENCE_FAIL = 0.30
    AMENDMENTS_HOLD = 1
    KNOWLEDGE_HOLD = 0.50
    KNOWLEDGE_FAIL = 0.30
    ENFORCEMENT_HOLD = 0.70
    ENFORCEMENT_FAIL = 0.50

    def __init__(
        self,
        *,
        lessons_hold: int = 1,
        bug_recurrence_hold: float = 0.15,
        bug_recurrence_fail: float = 0.30,
        amendments_hold: int = 1,
        knowledge_hold: float = 0.50,
        knowledge_fail: float = 0.30,
        enforcement_hold: float = 0.70,
        enforcement_fail: float = 0.50,
    ) -> None:
        self.LESSONS_HOLD = lessons_hold
        self.BUG_RECURRENCE_HOLD = bug_recurrence_hold
        self.BUG_RECURRENCE_FAIL = bug_recurrence_fail
        self.AMENDMENTS_HOLD = amendments_hold
        self.KNOWLEDGE_HOLD = knowledge_hold
        self.KNOWLEDGE_FAIL = knowledge_fail
        self.ENFORCEMENT_HOLD = enforcement_hold
        self.ENFORCEMENT_FAIL = enforcement_fail

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        """
        Evaluate constitutional health from the provided metrics dict.

        Expected keys (all optional — missing keys use safe defaults):
            lessons_learned_weekly (int): Lessons documented this week.
            bug_recurrence_rate (float, 0-1): Re-appearing bug fraction.
            amendments_per_month (int): Amendments ratified this month.
            knowledge_freshness (float, 0-1): Docs updated in 30d fraction.
            enforcement_coverage (float, 0-1): Automated constraint coverage.

        Returns:
            GateResult with state PASS | HOLD | FAIL.
        """
        lessons = int(metrics.get("lessons_learned_weekly", 3))
        recurrence = float(metrics.get("bug_recurrence_rate", 0.0))
        amendments = int(metrics.get("amendments_per_month", 2))
        freshness = float(metrics.get("knowledge_freshness", 0.70))
        enforcement = float(metrics.get("enforcement_coverage", 0.85))

        # FAIL conditions
        if lessons == 0:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.FAIL,
                reason=(
                    "Zero lessons documented this week. The agent is not learning. "
                    "A system that repeats failures without extracting lessons is "
                    "constitutionally dead."
                ),
                metric=float(lessons),
            )

        if recurrence > self.BUG_RECURRENCE_FAIL:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.FAIL,
                reason=(
                    f"High bug recurrence ({recurrence:.0%} > {self.BUG_RECURRENCE_FAIL:.0%}). "
                    "Fixes are not holding. Constitutional learning has broken down."
                ),
                metric=recurrence,
            )

        if amendments == 0:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.FAIL,
                reason=(
                    "No constitutional amendments this month. Governance is frozen. "
                    "A constitution that never evolves cannot adapt to new conditions."
                ),
                metric=float(amendments),
            )

        if freshness < self.KNOWLEDGE_FAIL:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.FAIL,
                reason=(
                    f"Knowledge base stale ({freshness:.0%} < {self.KNOWLEDGE_FAIL:.0%} "
                    "docs updated in 30d). Governance documentation is unreliable."
                ),
                metric=freshness,
            )

        if enforcement < self.ENFORCEMENT_FAIL:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.FAIL,
                reason=(
                    f"Constitutional enforcement gaps ({enforcement:.0%} < "
                    f"{self.ENFORCEMENT_FAIL:.0%} of constraints automated). "
                    "Hard constraints exist on paper but not in code."
                ),
                metric=enforcement,
            )

        # HOLD conditions
        if lessons < self.LESSONS_HOLD:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.HOLD,
                reason=(
                    f"Low lesson velocity ({lessons} lessons this week < "
                    f"{self.LESSONS_HOLD} minimum). Document failures before proceeding."
                ),
                metric=float(lessons),
            )

        if recurrence > self.BUG_RECURRENCE_HOLD:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.HOLD,
                reason=(
                    f"Elevated bug recurrence ({recurrence:.0%} > "
                    f"{self.BUG_RECURRENCE_HOLD:.0%}). Root causes are not being fixed."
                ),
                metric=recurrence,
            )

        if amendments < self.AMENDMENTS_HOLD:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.HOLD,
                reason=(
                    f"Low amendment rate ({amendments} this month < "
                    f"{self.AMENDMENTS_HOLD} minimum). Governance is not adapting."
                ),
                metric=float(amendments),
            )

        if freshness < self.KNOWLEDGE_HOLD:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.HOLD,
                reason=(
                    f"Knowledge freshness marginal ({freshness:.0%} < "
                    f"{self.KNOWLEDGE_HOLD:.0%}). Update documentation before expanding."
                ),
                metric=freshness,
            )

        if enforcement < self.ENFORCEMENT_HOLD:
            return GateResult(
                gate="ConstitutionalGate",
                state=GateState.HOLD,
                reason=(
                    f"Enforcement coverage marginal ({enforcement:.0%} < "
                    f"{self.ENFORCEMENT_HOLD:.0%}). Automate more constraints."
                ),
                metric=enforcement,
            )

        return GateResult(
            gate="ConstitutionalGate",
            state=GateState.PASS,
            reason=(
                f"Constitutional health confirmed (lessons {lessons}/week, "
                f"bug recurrence {recurrence:.0%}, amendments {amendments}/month, "
                f"freshness {freshness:.0%}, enforcement {enforcement:.0%})."
            ),
            metric=float(lessons),
        )


# ---------------------------------------------------------------------------
# Six Gate Evaluator (composite)
# ---------------------------------------------------------------------------

class SixGateEvaluator:
    """
    Evaluates all six constitutional gates and returns the composite system state.

    Usage:
        evaluator = SixGateEvaluator()
        system_state, gate_results = evaluator.evaluate(metrics)

    The gates are evaluated in this order (intentional — security-first):
        1. EpistemicGate    (EG)  — reasoning quality
        2. RiskGate         (RG)  — trust and safety
        3. GovernanceGate   (GG)  — audit and control integrity
        4. EconomicGate     (EPG) — financial sustainability
        5. AutonomyGate     (AAG) — autonomous operation health
        6. ConstitutionalGate (CGG) — learning and self-improvement

    Composite state rules:
        ANY gate FAIL       -> FREEZE
        ANY gate HOLD       -> THROTTLE
        ALL gates PASS      -> RUN
        ALL PASS + targets  -> COMPOUND
    """

    def __init__(
        self,
        epistemic: Any = None,
        risk: Any = None,
        governance: Any = None,
        economic: Any = None,
        autonomy: Any = None,
        constitutional: Any = None,
    ) -> None:
        self.epistemic = epistemic if epistemic is not None else EpistemicGate()
        self.risk = risk if risk is not None else RiskGate()
        self.governance = governance if governance is not None else GovernanceGate()
        self.economic = economic if economic is not None else EconomicGate()
        self.autonomy = autonomy if autonomy is not None else AutonomyGate()
        self.constitutional = constitutional if constitutional is not None else ConstitutionalGate()

    def evaluate(
        self,
        metrics: dict[str, Any],
        targets_met: bool = False,
    ) -> tuple[SystemState, list[GateResult]]:
        """
        Evaluate all six gates against the provided metrics.

        Args:
            metrics:     Dict of metric keys and values. Each gate documents
                         its expected keys. Unknown keys are ignored.
            targets_met: True if all stretch targets are satisfied. Required
                         for COMPOUND state. Defaults to False.

        Returns:
            Tuple of (SystemState, list[GateResult]).
            SystemState: COMPOUND | RUN | THROTTLE | FREEZE
            list[GateResult]: Individual gate results in evaluation order.
        """
        results: list[GateResult] = [
            self.epistemic.evaluate(metrics),
            self.risk.evaluate(metrics),
            self.governance.evaluate(metrics),
            self.economic.evaluate(metrics),
            self.autonomy.evaluate(metrics),
            self.constitutional.evaluate(metrics),
        ]

        states = {r.state for r in results}

        if GateState.FAIL in states:
            return SystemState.FREEZE, results

        if GateState.HOLD in states:
            return SystemState.THROTTLE, results

        # All PASS
        if targets_met:
            return SystemState.COMPOUND, results

        return SystemState.RUN, results
