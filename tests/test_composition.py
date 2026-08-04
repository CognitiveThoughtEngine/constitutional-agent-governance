"""
Tests for cross-session risk composition — the stateful layer that catches
what the memoryless six gates miss.
"""
import pytest

from constitutional_agent.composition import (
    AccumulatedRiskComposer,
    ComposedEvaluator,
    InMemoryRiskStore,
    SqliteRiskStore,
    default_risk_weight,
)
from constitutional_agent.gates import SixGateEvaluator
from constitutional_agent.schema import GateState, SystemState

# A metrics dict that every per-call gate rates healthy (RUN/COMPOUND).
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


class FakeClock:
    """Deterministic monotonic clock; advance() moves virtual time forward."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.t = start

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


# ---------------------------------------------------------------------------
# The marquee property: sub-threshold decisions compose to a state the
# per-call gates never reach.
# ---------------------------------------------------------------------------

def test_subthreshold_sequence_composes_to_throttle_then_freeze():
    """
    Every individual decision carries misuse_risk_index 0.5 — below the RiskGate
    HOLD (0.65). Per-call the system is RUN on each one. But the sequence
    accumulates: it must reach THROTTLE and then FREEZE, which stateless gating
    can never do.
    """
    clock = FakeClock()
    evaluator = ComposedEvaluator(
        composer=AccumulatedRiskComposer(clock=clock),  # hold 2.0, fail 3.5
    )
    metrics = {**HEALTHY, "misuse_risk_index": 0.5}  # weight 0.5 each

    states = []
    for _ in range(8):
        result = evaluator.evaluate(metrics, subject="pricing-agent")
        # The six memoryless gates never see a problem.
        assert result.per_call_state == SystemState.RUN
        states.append(result.system_state)
        clock.advance(60)  # one minute between decisions, all inside the 24h window

    # 4 * 0.5 = 2.0 -> HOLD threshold -> THROTTLE by the 4th decision.
    assert states[3] == SystemState.THROTTLE
    # 7 * 0.5 = 3.5 -> FAIL threshold -> FREEZE by the 7th decision.
    assert states[6] == SystemState.FREEZE
    # And the final result is flagged as escalated by composition, not per-call.
    final = evaluator.evaluate(metrics, subject="pricing-agent")
    assert final.escalated is True
    assert final.per_call_state == SystemState.RUN
    assert final.system_state == SystemState.FREEZE


def test_per_call_gate_alone_never_freezes_on_subthreshold_risk():
    """Control: the stateless evaluator stays out of FREEZE for the same input."""
    metrics = {**HEALTHY, "misuse_risk_index": 0.5}
    for _ in range(20):
        state, _ = SixGateEvaluator().evaluate(metrics)
        assert state != SystemState.FREEZE


def test_low_risk_sequence_stays_run():
    clock = FakeClock()
    evaluator = ComposedEvaluator(composer=AccumulatedRiskComposer(clock=clock))
    metrics = {**HEALTHY, "misuse_risk_index": 0.05}  # tiny weight
    for _ in range(10):
        result = evaluator.evaluate(metrics, subject="calm-agent")
        clock.advance(60)
        assert result.system_state == SystemState.RUN
        assert result.escalated is False


# ---------------------------------------------------------------------------
# Sustained-elevation detector (slow burn that never spikes in magnitude).
# ---------------------------------------------------------------------------

def test_sustained_elevation_holds_before_magnitude_threshold():
    clock = FakeClock()
    composer = AccumulatedRiskComposer(
        clock=clock,
        hold_threshold=100.0,   # disable the magnitude detector
        fail_threshold=200.0,
        sustained_count=5,
        sustained_floor=0.4,
    )
    for _ in range(4):
        composer.record("burn", 0.45)
        clock.advance(60)
        assert composer.compose("burn").state == GateState.PASS
    composer.record("burn", 0.45)  # the 5th consecutive elevated event
    result = composer.compose("burn")
    assert result.state == GateState.HOLD
    assert "Sustained elevation" in result.reason


# ---------------------------------------------------------------------------
# Windowing and decay.
# ---------------------------------------------------------------------------

def test_events_age_out_of_window():
    clock = FakeClock()
    composer = AccumulatedRiskComposer(clock=clock, window_seconds=3600)
    for _ in range(6):
        composer.record("w", 0.5)  # 6 * 0.5 = 3.0 accumulated
    assert composer.compose("w").state == GateState.HOLD
    clock.advance(3601)  # everything falls out of the 1h window
    result = composer.compose("w")
    assert result.state == GateState.PASS
    assert result.event_count == 0
    assert result.accumulated_risk == pytest.approx(0.0)


def test_half_life_decays_old_risk():
    clock = FakeClock()
    composer = AccumulatedRiskComposer(
        clock=clock, window_seconds=100_000, half_life_seconds=3600
    )
    composer.record("d", 1.0)
    assert composer.accumulated("d") == pytest.approx(1.0)
    clock.advance(3600)  # one half-life later
    assert composer.accumulated("d") == pytest.approx(0.5, abs=1e-6)
    clock.advance(3600)  # two half-lives
    assert composer.accumulated("d") == pytest.approx(0.25, abs=1e-6)


# ---------------------------------------------------------------------------
# Cross-session persistence — the differentiating claim, made real.
# ---------------------------------------------------------------------------

def test_sqlite_store_persists_risk_across_composer_instances(tmp_path):
    """
    Risk built up by one composer is visible to a second composer that only
    shares the database file — i.e. it survives a process/session boundary.
    """
    db = str(tmp_path / "risk.db")
    clock = FakeClock()

    # "Session 1": accumulate risk, then the composer goes away.
    store1 = SqliteRiskStore(db)
    session1 = AccumulatedRiskComposer(store=store1, clock=clock)
    for _ in range(6):
        session1.record("agent-x", 0.5)  # 3.0 accumulated -> HOLD
    assert session1.compose("agent-x").state == GateState.HOLD
    store1.close()

    # "Session 2": brand-new composer + store object, same file, same window.
    store2 = SqliteRiskStore(db)
    session2 = AccumulatedRiskComposer(store=store2, clock=clock)
    result = session2.compose("agent-x")
    assert result.event_count == 6
    assert result.state == GateState.HOLD  # yesterday's risk still counts today
    store2.close()


def test_inmemory_store_isolated_per_instance():
    """In-memory store is the non-persistent default (contrast with sqlite)."""
    c1 = AccumulatedRiskComposer(store=InMemoryRiskStore())
    for _ in range(6):
        c1.record("a", 0.5)
    assert c1.compose("a").state == GateState.HOLD
    c2 = AccumulatedRiskComposer(store=InMemoryRiskStore())
    assert c2.compose("a").state == GateState.PASS  # fresh store, no history


# ---------------------------------------------------------------------------
# Evidence trail + weight derivation + guards.
# ---------------------------------------------------------------------------

def test_composition_result_carries_contributing_events():
    clock = FakeClock()
    composer = AccumulatedRiskComposer(clock=clock)
    for _ in range(8):
        composer.record("e", 0.5, source="unit-test")
    result = composer.compose("e")
    assert result.state == GateState.FAIL
    assert len(result.contributing) == 8
    assert all(ev.source == "unit-test" for ev in result.contributing)


def test_default_risk_weight_takes_strongest_signal():
    assert default_risk_weight({"misuse_risk_index": 0.6}) == pytest.approx(0.6)
    assert default_risk_weight({"channel_health": 0.3}) == pytest.approx(0.7)
    assert default_risk_weight({"security_high_events": 2}) == pytest.approx(0.4)
    assert default_risk_weight({}) == pytest.approx(0.0)
    # clamped to [0, 1]
    assert default_risk_weight({"security_high_events": 99}) == pytest.approx(1.0)


def test_weight_is_clamped_on_record():
    composer = AccumulatedRiskComposer()
    ev_hi = composer.record("c", 5.0)
    ev_lo = composer.record("c", -3.0)
    assert ev_hi.weight == 1.0
    assert ev_lo.weight == 0.0


def test_invalid_thresholds_raise():
    with pytest.raises(ValueError):
        AccumulatedRiskComposer(hold_threshold=3.0, fail_threshold=2.0)
    with pytest.raises(ValueError):
        AccumulatedRiskComposer(window_seconds=0)
    with pytest.raises(ValueError):
        AccumulatedRiskComposer(half_life_seconds=0)


def test_explicit_risk_weight_overrides_derivation():
    clock = FakeClock()
    evaluator = ComposedEvaluator(composer=AccumulatedRiskComposer(clock=clock))
    # HEALTHY derives weight 0.0, but we force high risk explicitly.
    for _ in range(4):
        result = evaluator.evaluate(HEALTHY, subject="forced", risk_weight=0.9)
        clock.advance(60)
    assert result.system_state == SystemState.FREEZE
    assert result.escalated is True


def test_subjects_compose_independently():
    clock = FakeClock()
    composer = AccumulatedRiskComposer(clock=clock)
    for _ in range(8):
        composer.record("noisy", 0.5)
    composer.record("quiet", 0.1)
    assert composer.compose("noisy").state == GateState.FAIL
    assert composer.compose("quiet").state == GateState.PASS
