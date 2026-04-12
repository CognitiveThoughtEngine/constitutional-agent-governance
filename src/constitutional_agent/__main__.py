"""CLI demo: python -m constitutional_agent"""

from constitutional_agent import Constitution


def main() -> None:
    c = Constitution.from_defaults()
    result = c.evaluate({
        "failing_tests": 0, "hours_since_last_execution": 4,
        "proposed_spend": 100, "approved_budget": 500,
        "gate_override_without_amendment": False,
        "verification_pass_rate": 0.85, "uncertainty_disclosure_rate": 0.90,
        "assumption_volatility": 0.10, "disagreement_persistence": 0.05,
        "misuse_risk_index": 0.05, "irreversibility_score": 0.10,
        "channel_health": 0.92, "security_critical_events": 0,
        "security_high_events": 0, "control_bypass_attempts": 0,
        "audit_coverage": 0.97, "test_pass_rate": 0.98,
        "stage": "pre_revenue", "runway_months": 8.5,
        "dli_completion_rate": 0.12, "user_return_rate": 0.22,
        "value_demo_count": 4, "human_minutes_per_day": 25.0,
        "decisions_per_day": 153, "agent_activation_rate": 0.78,
        "escalations_per_day": 2, "auto_recovery_rate": 0.88,
        "lessons_learned_weekly": 3, "bug_recurrence_rate": 0.04,
        "amendments_per_month": 2, "knowledge_freshness": 0.75,
        "enforcement_coverage": 0.88,
    })

    G = "\033[32m"; Y = "\033[33m"; R = "\033[31m"; B = "\033[1m"; Z = "\033[0m"
    COLOR = {"PASS": G, "HOLD": Y, "FAIL": R}

    state = result.system_state.value
    sc = {
        "COMPOUND": G, "RUN": G, "THROTTLE": Y, "FREEZE": R, "STOP": R,
    }.get(state, "")
    print(f"\n{B}System state:{Z} {sc}{state}{Z}\n")

    for gr in result.gate_results:
        c_ = COLOR.get(gr.state.value, "")
        print(f"  {c_}{gr.state.value:4}{Z}  {gr.gate:20} {gr.reason}")

    if result.hard_constraint_violations:
        print(f"\n{R}{B}Hard-constraint violations:{Z}")
        for v in result.hard_constraint_violations:
            print(f"  {R}{v.constraint_id}{Z}: {v.description}  -> {v.remedy}")

    # Propose an amendment to show the workflow
    aid = c.propose_amendment(
        description="Lower verification_pass_rate HOLD threshold to 0.65",
        rationale="API latency increased; 0.65 still safe.",
        affected_sections=["EpistemicGate"],
        proposed_by="cli_demo",
    )
    print(f"\n{B}Amendment proposed:{Z} {aid}")
    print("Pending ratification — not applied until ratified.\n")


if __name__ == "__main__":
    main()
