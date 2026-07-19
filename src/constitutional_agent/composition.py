"""
Constitutional Agent — Cross-Session Risk Composition
=====================================================

The six gates in :mod:`constitutional_agent.gates` are *memoryless*: each
``evaluate()`` call scores a single decision in isolation and forgets it. This
per-intervention pattern is common across the field: in a July 2026 review of
four vendor-neutral governance products (Microsoft Agent Governance Toolkit,
Galileo Agent Control, Runlayer, NVIDIA NeMo Guardrails / OpenShell), a durable
cross-session decision-risk accumulation primitive was *not surfaced in the
documentation reviewed* — a bounded review of public docs, not a claim of global
novelty.

Stateless gating has a blind spot: **an agent can pass every individual gate
and still be dangerous over a sequence.** Ten actions that are each 0.5 on a
0-1 risk scale — all comfortably below any per-call HOLD threshold — compose
into a trajectory no single evaluation flags. This is the failure mode the
per-call gate cannot see, because it never remembers the last decision when it
scores the next one.

This module adds the layer that remembers. It accumulates a scalar *risk
weight* per evaluation, keyed by subject (an agent id, a session, an actor),
composes those weights across a rolling window — optionally with time decay —
and escalates the system state when the **accumulation** crosses a threshold,
even though each contributing decision passed on its own.

Because the accumulator reads and writes through a pluggable
:class:`RiskStore`, composition survives process restarts and spans sessions:
point it at :class:`SqliteRiskStore` (or your own Postgres adapter) and the
risk an agent built up yesterday still counts today.

Two detectors run together:

1. **Accumulated magnitude** — the (optionally decayed) sum of risk weights in
   the window crosses ``hold_threshold`` / ``fail_threshold``. Many small risks
   add up.
2. **Sustained elevation** — the most recent ``sustained_count`` events are each
   at or above ``sustained_floor`` (individually sub-HOLD, but persistently
   elevated). A slow burn that never spikes.

Every :class:`CompositionResult` carries the exact events that drove it, so the
decision is auditable after the fact — the risk trajectory *is* the evidence.

Usage::

    from constitutional_agent.composition import ComposedEvaluator

    evaluator = ComposedEvaluator()
    for decision_metrics in stream:
        result = evaluator.evaluate(decision_metrics, subject="pricing-agent")
        if result.system_state.value in ("FREEZE", "THROTTLE"):
            # May trip even when all six per-call gates PASS.
            print(result.composition.reason)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol, runtime_checkable

from constitutional_agent.gates import SixGateEvaluator
from constitutional_agent.schema import GateResult, GateState, SystemState

__all__ = [
    "RiskEvent",
    "RiskStore",
    "InMemoryRiskStore",
    "SqliteRiskStore",
    "CompositionResult",
    "AccumulatedRiskComposer",
    "ComposedEvaluator",
    "ComposedSystemResult",
    "default_risk_weight",
]


# ---------------------------------------------------------------------------
# Risk event + storage
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskEvent:
    """
    A single risk contribution recorded against a subject.

    Attributes:
        subject:   Identity the risk accrues to (agent id, session, actor).
        weight:    Risk contribution in [0, 1]. 0 = no risk, 1 = maximal.
        timestamp: Unix seconds when the event was recorded.
        source:    What produced the weight (e.g. "RiskGate", "manual"), for audit.
        context:   Optional extra key-value pairs for the audit trail.
    """

    subject: str
    weight: float
    timestamp: float
    source: str = ""
    context: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class RiskStore(Protocol):
    """
    Pluggable persistence for risk events.

    The default :class:`InMemoryRiskStore` keeps events in a dict and is lost on
    restart. Supply a persistent implementation (:class:`SqliteRiskStore`, or a
    Postgres adapter) to make composition span sessions — the whole point of the
    layer. Any object with these three methods satisfies the protocol.
    """

    def record(self, event: RiskEvent) -> None:
        """Persist one risk event."""
        ...

    def recent(self, subject: str, since: float) -> list[RiskEvent]:
        """Return events for ``subject`` with ``timestamp >= since``, oldest first."""
        ...

    def prune(self, before: float) -> int:
        """Delete events with ``timestamp < before``. Returns the number removed."""
        ...


class InMemoryRiskStore:
    """
    Default in-process risk store. Fast, zero-dependency, **not** persistent.

    Use for single-session composition or tests. For cross-session composition
    (the differentiating use case) use :class:`SqliteRiskStore` or your own
    durable adapter.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[RiskEvent]] = {}

    def record(self, event: RiskEvent) -> None:
        self._events.setdefault(event.subject, []).append(event)

    def recent(self, subject: str, since: float) -> list[RiskEvent]:
        events = [e for e in self._events.get(subject, []) if e.timestamp >= since]
        events.sort(key=lambda e: e.timestamp)
        return events

    def prune(self, before: float) -> int:
        removed = 0
        for subject, events in list(self._events.items()):
            kept = [e for e in events if e.timestamp >= before]
            removed += len(events) - len(kept)
            if kept:
                self._events[subject] = kept
            else:
                del self._events[subject]
        return removed


class SqliteRiskStore:
    """
    Durable risk store backed by SQLite (stdlib, no dependencies).

    This is what makes cross-session composition real rather than a claim: risk
    events written in one process are visible to the next. Point two
    :class:`AccumulatedRiskComposer` instances (separate runs, separate days) at
    the same database file and the accumulated risk carries across.

        store = SqliteRiskStore("risk.db")
        composer = AccumulatedRiskComposer(store=store)

    Pass ``":memory:"`` for an ephemeral database (useful in tests).
    """

    def __init__(self, path: str = ":memory:") -> None:
        import json
        import sqlite3

        self._json = json
        # check_same_thread=False so a caller may share the store across threads;
        # writes are serialized by SQLite's own locking.
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS risk_events (
                subject   TEXT    NOT NULL,
                weight    REAL    NOT NULL,
                timestamp REAL    NOT NULL,
                source    TEXT    NOT NULL DEFAULT '',
                context   TEXT    NOT NULL DEFAULT '{}'
            )
            """
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_risk_subject_ts "
            "ON risk_events (subject, timestamp)"
        )
        self._conn.commit()

    def record(self, event: RiskEvent) -> None:
        self._conn.execute(
            "INSERT INTO risk_events (subject, weight, timestamp, source, context) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event.subject,
                float(event.weight),
                float(event.timestamp),
                event.source,
                self._json.dumps(event.context),
            ),
        )
        self._conn.commit()

    def recent(self, subject: str, since: float) -> list[RiskEvent]:
        rows = self._conn.execute(
            "SELECT subject, weight, timestamp, source, context FROM risk_events "
            "WHERE subject = ? AND timestamp >= ? ORDER BY timestamp ASC",
            (subject, float(since)),
        ).fetchall()
        return [
            RiskEvent(
                subject=row[0],
                weight=row[1],
                timestamp=row[2],
                source=row[3],
                context=self._json.loads(row[4]),
            )
            for row in rows
        ]

    def prune(self, before: float) -> int:
        cur = self._conn.execute(
            "DELETE FROM risk_events WHERE timestamp < ?", (float(before),)
        )
        self._conn.commit()
        return cur.rowcount if cur.rowcount is not None else 0

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()


# ---------------------------------------------------------------------------
# Composition result
# ---------------------------------------------------------------------------

@dataclass
class CompositionResult:
    """
    Outcome of composing a subject's accumulated risk.

    Attributes:
        subject:          The identity evaluated.
        state:            PASS | HOLD | FAIL from the *accumulation* (not any
                          single decision).
        accumulated_risk: The (optionally decayed) sum of risk weights in-window.
        event_count:      Number of contributing events in-window.
        reason:           Human-readable explanation citing the detector that fired.
        contributing:     The exact events that drove the result — the audit trail.
        window_seconds:   The rolling window used.
    """

    subject: str
    state: GateState
    accumulated_risk: float
    event_count: int
    reason: str
    contributing: list[RiskEvent] = field(default_factory=list)
    window_seconds: float = 0.0


# ---------------------------------------------------------------------------
# Accumulated risk composer
# ---------------------------------------------------------------------------

class AccumulatedRiskComposer:
    """
    Composes per-decision risk weights into a stateful, cross-session signal.

    Args:
        store:            Where risk events live. Default: in-memory (not
                          persistent). Use :class:`SqliteRiskStore` for
                          cross-session composition.
        window_seconds:   Rolling window over which risk accumulates (default 24h).
        half_life_seconds: If set, older events decay: an event's effective
                          weight is ``weight * 0.5 ** (age / half_life)``. If
                          None (default), all in-window events count at full
                          weight (pure rolling sum).
        hold_threshold:   Accumulated risk at or above this -> HOLD (default 2.0).
        fail_threshold:   Accumulated risk at or above this -> FAIL (default 3.5).
        sustained_count:  Number of recent consecutive elevated events that trip
                          the sustained-elevation detector (default 5).
        sustained_floor:  Per-event weight that counts as "elevated" for the
                          sustained detector (default 0.4).
        clock:            Callable returning Unix seconds. Injected for
                          determinism in tests. Default: ``time.time``.
    """

    def __init__(
        self,
        *,
        store: Optional[RiskStore] = None,
        window_seconds: float = 86_400.0,
        half_life_seconds: Optional[float] = None,
        hold_threshold: float = 2.0,
        fail_threshold: float = 3.5,
        sustained_count: int = 5,
        sustained_floor: float = 0.4,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if fail_threshold <= hold_threshold:
            raise ValueError("fail_threshold must be greater than hold_threshold")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if half_life_seconds is not None and half_life_seconds <= 0:
            raise ValueError("half_life_seconds must be positive or None")

        self.store: RiskStore = store if store is not None else InMemoryRiskStore()
        self.window_seconds = window_seconds
        self.half_life_seconds = half_life_seconds
        self.hold_threshold = hold_threshold
        self.fail_threshold = fail_threshold
        self.sustained_count = sustained_count
        self.sustained_floor = sustained_floor
        self._clock = clock

    def record(
        self,
        subject: str,
        weight: float,
        *,
        source: str = "",
        context: Optional[dict[str, Any]] = None,
    ) -> RiskEvent:
        """
        Record a risk contribution for ``subject`` and return the stored event.

        ``weight`` is clamped to [0, 1]. The event is stamped with the composer's
        clock, so tests can drive time deterministically.
        """
        clamped = max(0.0, min(1.0, float(weight)))
        event = RiskEvent(
            subject=subject,
            weight=clamped,
            timestamp=self._clock(),
            source=source,
            context=dict(context or {}),
        )
        self.store.record(event)
        return event

    def _effective_weight(self, event: RiskEvent, now: float) -> float:
        if self.half_life_seconds is None:
            return event.weight
        age = max(0.0, now - event.timestamp)
        return float(event.weight * (0.5 ** (age / self.half_life_seconds)))

    def accumulated(self, subject: str) -> float:
        """Return the current accumulated (optionally decayed) risk for ``subject``."""
        now = self._clock()
        events = self.store.recent(subject, since=now - self.window_seconds)
        return sum(self._effective_weight(e, now) for e in events)

    def compose(self, subject: str) -> CompositionResult:
        """
        Compose ``subject``'s in-window risk events into a single state.

        Returns the most severe of the two detectors (accumulated magnitude and
        sustained elevation), with the contributing events attached as evidence.
        """
        now = self._clock()
        window_start = now - self.window_seconds
        events = self.store.recent(subject, since=window_start)
        accumulated = sum(self._effective_weight(e, now) for e in events)

        # Detector 1 — accumulated magnitude.
        if accumulated >= self.fail_threshold:
            return CompositionResult(
                subject=subject,
                state=GateState.FAIL,
                accumulated_risk=accumulated,
                event_count=len(events),
                reason=(
                    f"Accumulated risk {accumulated:.2f} >= FAIL threshold "
                    f"{self.fail_threshold:.2f} across {len(events)} decision(s) in the "
                    f"last {self._window_label()}. Every decision may have passed on its "
                    "own; the trajectory did not."
                ),
                contributing=events,
                window_seconds=self.window_seconds,
            )

        # Detector 2 — sustained elevation (slow burn that never spikes).
        recent_run = events[-self.sustained_count:] if self.sustained_count > 0 else []
        sustained = (
            len(recent_run) >= self.sustained_count
            and all(e.weight >= self.sustained_floor for e in recent_run)
        )
        if sustained:
            return CompositionResult(
                subject=subject,
                state=GateState.HOLD,
                accumulated_risk=accumulated,
                event_count=len(events),
                reason=(
                    f"Sustained elevation: the last {self.sustained_count} decisions were "
                    f"each >= {self.sustained_floor:.2f} risk (individually sub-threshold) "
                    "but persistently elevated. Throttle before the trend compounds."
                ),
                contributing=recent_run,
                window_seconds=self.window_seconds,
            )

        if accumulated >= self.hold_threshold:
            return CompositionResult(
                subject=subject,
                state=GateState.HOLD,
                accumulated_risk=accumulated,
                event_count=len(events),
                reason=(
                    f"Accumulated risk {accumulated:.2f} >= HOLD threshold "
                    f"{self.hold_threshold:.2f} across {len(events)} decision(s) in the "
                    f"last {self._window_label()}. Composed risk is climbing even though "
                    "individual decisions passed."
                ),
                contributing=events,
                window_seconds=self.window_seconds,
            )

        return CompositionResult(
            subject=subject,
            state=GateState.PASS,
            accumulated_risk=accumulated,
            event_count=len(events),
            reason=(
                f"Composed risk acceptable ({accumulated:.2f} < HOLD "
                f"{self.hold_threshold:.2f}) across {len(events)} decision(s) in the last "
                f"{self._window_label()}."
            ),
            contributing=events,
            window_seconds=self.window_seconds,
        )

    def prune(self) -> int:
        """Drop events older than the window. Returns the number removed."""
        return self.store.prune(before=self._clock() - self.window_seconds)

    def _window_label(self) -> str:
        hours = self.window_seconds / 3600.0
        if hours >= 1:
            return f"{hours:.0f}h"
        return f"{self.window_seconds:.0f}s"


# ---------------------------------------------------------------------------
# Deriving a risk weight from six-gate metrics
# ---------------------------------------------------------------------------

def default_risk_weight(metrics: dict[str, Any]) -> float:
    """
    Derive a [0, 1] risk weight from a standard six-gate metrics dict.

    The weight is the strongest of the Risk Gate's continuous signals plus a
    security-event contribution — precisely the sub-threshold-but-elevated risk
    that per-call gating waves through. A decision that trips no gate on its own
    can still carry, say, ``misuse_risk_index = 0.5``; that 0.5 is what
    accumulates.
    """
    mri = float(metrics.get("misuse_risk_index", 0.0))
    ips = float(metrics.get("irreversibility_score", 0.0))
    channel_deficit = 1.0 - float(metrics.get("channel_health", 1.0))
    # Each HIGH security event contributes 0.2, capped at 1.0.
    high = int(metrics.get("security_high_events", 0))
    security = min(1.0, 0.2 * high)
    return max(0.0, min(1.0, max(mri, ips, channel_deficit, security)))


# ---------------------------------------------------------------------------
# Composed evaluator — six gates + cross-session composition
# ---------------------------------------------------------------------------

@dataclass
class ComposedSystemResult:
    """
    Result of a :class:`ComposedEvaluator` evaluation.

    Attributes:
        system_state:   The final state, escalated by composition when needed.
        per_call_state: What the six memoryless gates alone returned — kept so
                        callers can see when composition changed the verdict.
        gate_results:   The six individual gate results.
        composition:    The cross-session composition result (the new signal).
        escalated:      True if composition made the final state more severe than
                        the per-call state — i.e. the sequence tripped what no
                        single decision did.
    """

    system_state: SystemState
    per_call_state: SystemState
    gate_results: list[GateResult]
    composition: CompositionResult
    escalated: bool


# System-state severity ordering for taking the worse of two verdicts.
_SEVERITY: dict[SystemState, int] = {
    SystemState.COMPOUND: 0,
    SystemState.RUN: 1,
    SystemState.THROTTLE: 2,
    SystemState.FREEZE: 3,
    SystemState.STOP: 4,
}

# How a composition gate state maps onto a system state contribution.
_COMPOSITION_TO_SYSTEM: dict[GateState, SystemState] = {
    GateState.PASS: SystemState.RUN,
    GateState.HOLD: SystemState.THROTTLE,
    GateState.FAIL: SystemState.FREEZE,
}


class ComposedEvaluator:
    """
    Wraps :class:`SixGateEvaluator` with cross-session risk composition.

    Each ``evaluate()`` runs the six memoryless gates, derives a risk weight for
    the decision, records it against the subject, and returns the **more severe**
    of the per-call verdict and the composed verdict. The composition can push a
    system that every individual gate rated RUN into THROTTLE or FREEZE — the
    binding property no stateless engine has.

    Args:
        evaluator:      The six-gate evaluator. Default: a fresh SixGateEvaluator.
        composer:       The risk composer (holds the store). Default: in-memory.
        risk_weight_fn: Maps a metrics dict to a [0, 1] weight. Default:
                        :func:`default_risk_weight`.
    """

    def __init__(
        self,
        *,
        evaluator: Optional[SixGateEvaluator] = None,
        composer: Optional[AccumulatedRiskComposer] = None,
        risk_weight_fn: Callable[[dict[str, Any]], float] = default_risk_weight,
    ) -> None:
        self.evaluator = evaluator if evaluator is not None else SixGateEvaluator()
        self.composer = composer if composer is not None else AccumulatedRiskComposer()
        self.risk_weight_fn = risk_weight_fn

    def evaluate(
        self,
        metrics: dict[str, Any],
        *,
        subject: str = "default",
        targets_met: bool = False,
        risk_weight: Optional[float] = None,
    ) -> ComposedSystemResult:
        """
        Evaluate a decision through the six gates and the composition layer.

        Args:
            metrics:      Standard six-gate metrics dict.
            subject:      Identity the risk accrues to. Compose per agent/session/actor.
            targets_met:  Passed through to the six-gate COMPOUND rule.
            risk_weight:  Override the derived weight for this decision (0-1). If
                          None, ``risk_weight_fn(metrics)`` is used.

        Returns:
            ComposedSystemResult with both the per-call and composed verdicts.
        """
        per_call_state, gate_results = self.evaluator.evaluate(metrics, targets_met=targets_met)

        weight = risk_weight if risk_weight is not None else self.risk_weight_fn(metrics)
        self.composer.record(subject, weight, source="ComposedEvaluator")
        composition = self.composer.compose(subject)

        composed_state = _COMPOSITION_TO_SYSTEM[composition.state]
        if _SEVERITY[composed_state] >= _SEVERITY[per_call_state]:
            final_state = composed_state
        else:
            final_state = per_call_state
        # Never downgrade below the per-call verdict.
        if _SEVERITY[final_state] < _SEVERITY[per_call_state]:
            final_state = per_call_state

        escalated = _SEVERITY[final_state] > _SEVERITY[per_call_state]

        return ComposedSystemResult(
            system_state=final_state,
            per_call_state=per_call_state,
            gate_results=gate_results,
            composition=composition,
            escalated=escalated,
        )
