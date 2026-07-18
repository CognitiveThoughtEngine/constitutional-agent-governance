"""
constitutional-agent
====================
WHY-layer constitutional governance for autonomous AI agents.

Extracted from the HRAO-E Constitutional Framework, a production reference
implementation of constitutional governance. The library ships the portable
core: six gates, twelve hard constraints (HC-1..HC-12), an enforced amendment
protocol with separation of duties, and EU AI Act Article 27(1) FRIA-support
evidence.

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

from constitutional_agent.composition import (
    AccumulatedRiskComposer,
    ComposedEvaluator,
    ComposedSystemResult,
    CompositionResult,
    InMemoryRiskStore,
    RiskEvent,
    RiskStore,
    SqliteRiskStore,
    default_risk_weight,
)
from constitutional_agent.authority import (
    AmendmentRecord,
    AmendmentStore,
    AuthorityLevel,
    AuthorityRegistry,
    IdentityVerifier,
    InMemoryAmendmentStore,
    SqliteAmendmentStore,
    bounded_verifier,
    canonical_principal,
    redact_secrets,
    scrub_evidence,
)
from constitutional_agent.constitution import Constitution, ConstitutionalViolation
from constitutional_agent.fria import (
    Article27Applicability,
    Article27Crosswalk,
    Article27Element,
    EvidenceSource,
    FRIAEvidence,
    GovernanceEvidenceCategory,
    LegalReviewStatus,
    fria_support_package,
    generate_article27_crosswalk,
    generate_fria_evidence,
)
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

__version__ = "0.7.0"
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
    # Cross-session risk composition — the stateful layer
    "ComposedEvaluator",
    "ComposedSystemResult",
    "AccumulatedRiskComposer",
    "CompositionResult",
    "RiskEvent",
    "RiskStore",
    "InMemoryRiskStore",
    "SqliteRiskStore",
    "default_risk_weight",
    # Amendment authority & separation of duties (v0.7.0)
    "AuthorityLevel",
    "AuthorityRegistry",
    "IdentityVerifier",
    "AmendmentRecord",
    "AmendmentStore",
    "InMemoryAmendmentStore",
    "SqliteAmendmentStore",
    "canonical_principal",
    "scrub_evidence",
    "redact_secrets",
    "bounded_verifier",
    # FRIA-support: internal evidence + Article 27(1) crosswalk (v0.7.0)
    "GovernanceEvidenceCategory",
    "FRIAEvidence",
    "Article27Element",
    "Article27Crosswalk",
    "Article27Applicability",
    "EvidenceSource",
    "LegalReviewStatus",
    "generate_fria_evidence",
    "generate_article27_crosswalk",
    "fria_support_package",
    # Schema / types
    "GateState",
    "GateResult",
    "SystemState",
    "ConstitutionResult",
    "HardConstraintViolation",
]
