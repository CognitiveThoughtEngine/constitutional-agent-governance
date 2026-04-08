"""
Constitutional Agent — Schema
Shared data contracts for the constitutional governance library.

Based on HRAO-E Constitutional Framework (cognitivethoughtengine.com)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class GateState(str, Enum):
    """
    Gate evaluation states.

    State machine:
        PASS  — Gate conditions satisfied. Normal operation.
        HOLD  — Gate conditions marginal. Throttle: conserve resources,
                skip discretionary actions.
        FAIL  — Gate conditions violated. Freeze: stop all discretionary
                spend and actions until resolved.
    """

    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"


class SystemState(str, Enum):
    """
    Composite system state derived from all gate evaluations.

    Transition rules:
        ALL gates PASS + all stretch targets met  -> COMPOUND
        ALL gates PASS                            -> RUN
        ANY gate HOLD (no FAILs)                  -> THROTTLE
        ANY gate FAIL                             -> FREEZE
        FREEZE > 24 hours without resolution      -> STOP (human required)
    """

    COMPOUND = "COMPOUND"   # Maximum growth mode
    RUN = "RUN"             # Normal autonomous operation
    THROTTLE = "THROTTLE"   # Conserve resources, skip discretionary spend
    FREEZE = "FREEZE"       # All discretionary spend halted
    STOP = "STOP"           # Human intervention required


@dataclass
class GateResult:
    """
    Result of a single gate evaluation.

    Attributes:
        gate:    Gate identifier (e.g. "EpistemicGate", "EconomicGate").
        state:   PASS | HOLD | FAIL.
        reason:  Human-readable explanation, must cite the principle violated.
        metric:  Optional numeric value that drove the decision (for audit).
        context: Optional extra key-value pairs for debugging.
    """

    gate: str
    state: GateState
    reason: str
    metric: Optional[float] = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class HardConstraintViolation:
    """
    Records a hard constraint violation (never ignorable).

    Hard constraints are absolute prohibitions. Unlike gates (which produce
    HOLD/FAIL states that can potentially be amended), hard constraint
    violations are STOP-level events. No agent action, amendment, or human
    instruction can authorize proceeding while a hard constraint is violated.
    """

    constraint_id: str    # e.g. "HC-1", "HC-12"
    description: str
    violated: bool
    remedy: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConstitutionResult:
    """
    Full result of a Constitution.evaluate() call.

    Attributes:
        system_state:       Composite state derived from all gate results.
        gate_results:       Ordered list of individual gate evaluations.
        hard_constraint_violations: Any HC violations found (STOP-level).
        blocking_gate:      First FAIL gate, if any.
        hold_gates:         All HOLD gates, if any.
        targets_met:        True if all stretch targets are satisfied
                            (required for COMPOUND state).
        summary:            One-line human-readable summary.
    """

    system_state: SystemState
    gate_results: list[GateResult]
    hard_constraint_violations: list[HardConstraintViolation]
    blocking_gate: Optional[GateResult]
    hold_gates: list[GateResult]
    targets_met: bool
    summary: str
