"""
basic_agent.py — Constitutional Agent Quick Start
--------------------------------------------------
Shows any autonomous agent integrating constitutional governance.

Run:
    pip install constitutional-agent
    python examples/basic_agent.py
"""

from constitutional_agent import Constitution

# Load constitution from governance.yaml (or use Constitution.from_defaults())
constitution = Constitution.from_defaults()

# Evaluate before any significant action
result = constitution.evaluate({
    # Hard constraint context
    "failing_tests": 0,
    "hours_since_last_execution": 4,
    "proposed_spend": 100,
    "approved_budget": 500,
    "gate_override_without_amendment": False,

    # Epistemic: are we reasoning soundly?
    "verification_pass_rate": 0.85,
    "uncertainty_disclosure_rate": 0.90,
    "assumption_volatility": 0.10,
    "disagreement_persistence": 0.05,

    # Risk: are outbound actions safe?
    "misuse_risk_index": 0.05,
    "irreversibility_score": 0.10,
    "channel_health": 0.92,
    "security_critical_events": 0,
    "security_high_events": 0,

    # Governance: is the control system intact?
    "control_bypass_attempts": 0,
    "audit_coverage": 0.97,
    "test_pass_rate": 0.98,

    # Economic: is the business healthy?
    "stage": "pre_revenue",
    "runway_months": 8.5,
    "dli_completion_rate": 0.12,
    "user_return_rate": 0.22,
    "value_demo_count": 4,

    # Autonomy: are agents actually deciding?
    "human_minutes_per_day": 25.0,
    "decisions_per_day": 153,
    "agent_activation_rate": 0.78,
    "escalations_per_day": 2,
    "auto_recovery_rate": 0.88,

    # Constitutional: is the system learning?
    "lessons_learned_weekly": 3,
    "bug_recurrence_rate": 0.04,
    "amendments_per_month": 2,
    "knowledge_freshness": 0.75,
    "enforcement_coverage": 0.88,
})

# Act on the result
if result.system_state.value == "STOP":
    for violation in result.hard_constraint_violations:
        print(f"HARD CONSTRAINT VIOLATED — {violation.constraint_id}: {violation.description}")
        print(f"  Remedy: {violation.remedy}")

elif result.system_state.value == "FREEZE":
    print(f"FREEZE — All discretionary spend halted.")
    print(f"Blocking gate: {result.blocking_gate.gate}")
    print(f"Reason: {result.blocking_gate.reason}")

elif result.system_state.value == "THROTTLE":
    print(f"THROTTLE — Conserving resources. Skip non-essential actions.")
    for gate in result.hold_gates:
        print(f"  HOLD — {gate.gate}: {gate.reason}")
    # Continue with essential tasks only

elif result.system_state.value == "RUN":
    print("RUN — All gates PASS. Normal autonomous operation.")
    # Execute planned tasks

elif result.system_state.value == "COMPOUND":
    print("COMPOUND — All gates PASS + targets met. Maximum growth mode.")
    # Execute planned tasks + growth initiatives

# Proposing an amendment (agent cannot ratify its own proposals)
amendment_id = constitution.propose_amendment(
    description="Reduce hold threshold for verification_pass_rate from 0.70 to 0.65",
    rationale=(
        "External verification latency increased due to API rate limits. "
        "0.65 still provides adequate epistemic safety while avoiding false HOLDs."
    ),
    affected_sections=["EpistemicGate"],
    proposed_by="basic_agent_v1",
)
print(f"\nAmendment proposed: {amendment_id}")
print("Pending ratification by designated authority — not applied until ratified.")

# Print summary report
report = constitution.summary_report()
print(f"\nConstitutional summary: {report}")
