"""
constitutional-agent
====================
WHY-layer constitutional governance for autonomous AI agents.

Based on the HRAO-E Constitutional Framework, production-validated over
95 days with 52 agents, 64 constitutional amendments, and 1,808 tests.

Core concepts:
    Constitution:   The agent's governing document. Load from governance.yaml.
    SixGateEvaluator: Evaluates all six constitutional gates.
    HardConstraint: Absolute prohibition — no agent action can override.
    GateState:      PASS | HOLD | FAIL
    SystemState:    COMPOUND | RUN | THROTTLE | FREEZE | STOP

Quick start:
    from constitutional_agent import Constitution

    constitution = Constitution.load("governance.yaml")
    result = constitution.evaluate({
        "failing_tests": 0,
        "hours_since_last_execution": 4,
        "runway_months": 8.5,
        "lessons_learned_weekly": 2,
    })

    if result.system_state.value == "FREEZE":
        print(f"BLOCKED: {result.blocking_gate.reason}")
    elif result.system_state.value == "THROTTLE":
        print(f"Throttle: {[g.gate for g in result.hold_gates]}")
    else:
        print(f"State: {result.system_state.value}")

WHO governs identity. HOW governs behavior. WHY governs values.
"""

from constitutional_agent.constitution import Constitution, ConstitutionalViolation
from constitutional_agent.gates import (
    AutonomyGate,
    ConstitutionalGate,
    EconomicGate,
    EpistemicGate,
    GovernanceGate,
    RiskGate,
    SixGateEvaluator,
)
from constitutional_agent.hard_constraints import (
    BUILTIN_HARD_CONSTRAINTS,
    HardConstraint,
    HardConstraintResult,
    check_hard_constraints,
)
from constitutional_agent.schema import (
    ConstitutionResult,
    GateResult,
    GateState,
    HardConstraintViolation,
    SystemState,
)

__version__ = "0.4.0b1"
__author__ = "Cognitive Thought Engine LLC"
__license__ = "MIT"
__url__ = "https://github.com/CognitiveThoughtEngine/constitutional-agent-governance"

__all__ = [
    # Constitution — primary entry point
    "Constitution",
    "ConstitutionalViolation",
    # Gates — individual gate classes
    "SixGateEvaluator",
    "EpistemicGate",
    "RiskGate",
    "GovernanceGate",
    "EconomicGate",
    "AutonomyGate",
    "ConstitutionalGate",
    # Hard constraints
    "BUILTIN_HARD_CONSTRAINTS",
    "HardConstraint",
    "HardConstraintResult",
    "check_hard_constraints",
    # Schema / types
    "GateState",
    "GateResult",
    "SystemState",
    "ConstitutionResult",
    "HardConstraintViolation",
]
