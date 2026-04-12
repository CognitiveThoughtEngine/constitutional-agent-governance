# constitutional-agent

[![Tests](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance/actions/workflows/tests.yml/badge.svg)](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/badge/pypi-v0.4.0-blue)](https://pypi.org/project/constitutional-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**The governance layer your AI agent is missing.**

Extracted from HRAO-E: 98 days in production, 52 agents, 1,929 governance evaluations. Cited in NIST AI 800-2 submissions.

> **Note:** PyPI badge above shows v0.4.0; the current published version is 0.3.2.

### Quick Start

```bash
pip install constitutional-agent
```

```python
from constitutional_agent import Constitution

constitution = Constitution.from_defaults()
result = constitution.evaluate({
    # Safety gate
    "failing_tests": 0, "hours_since_last_execution": 4,
    # Economic gate
    "proposed_spend": 100, "approved_budget": 500,
    "stage": "pre_revenue", "runway_months": 8.5,
    # Governance gate
    "gate_override_without_amendment": False,
    "audit_coverage": 0.97, "test_pass_rate": 0.98,
    "enforcement_coverage": 0.88, "amendments_per_month": 2,
    # Epistemic gate
    "verification_pass_rate": 0.85, "uncertainty_disclosure_rate": 0.90,
    "assumption_volatility": 0.10, "disagreement_persistence": 0.05,
    "knowledge_freshness": 0.75,
    # Risk gate
    "misuse_risk_index": 0.05, "irreversibility_score": 0.10,
    # Security gate
    "channel_health": 0.92, "security_critical_events": 0,
    "security_high_events": 0, "control_bypass_attempts": 0,
    # Autonomy metrics
    "dli_completion_rate": 0.12, "user_return_rate": 0.22,
    "value_demo_count": 4, "human_minutes_per_day": 25.0,
    "decisions_per_day": 153, "agent_activation_rate": 0.78,
    "escalations_per_day": 2, "auto_recovery_rate": 0.88,
    "lessons_learned_weekly": 3, "bug_recurrence_rate": 0.04,
})

print(result.system_state.value)  # -> RUN
```

---

## Who This Is For

- **Platform teams** embedding agents into production systems that make autonomous decisions affecting real outcomes
- **Agent framework builders** who need a governance layer above identity and policy enforcement
- **Enterprise architects** evaluating autonomous AI deployment risk and liability exposure
- **Teams that need EU AI Act Article 27 FRIA evidence** generated programmatically from live evaluation data

If your agent answers questions only, with no economic or operational authority, this library is likely more than you need. If your agent executes, spends, publishes, or decides — read on.

---

## Architecture: Where This Fits

```
┌─────────────────────────────────────────────────────┐
│                   Your AI Agent                      │
└────────────────────────┬────────────────────────────┘
                         │ wants to act
                         ▼
┌─────────────────────────────────────────────────────┐
│  WHY Layer — constitutional-agent (this library)     │
│                                                      │
│  EpistemicGate   RiskGate   GovernanceGate           │
│  EconomicGate    AutonomyGate   ConstitutionalGate   │
│                                                      │
│  Evaluates: Is this decision sound?                  │
│  Output: COMPOUND / RUN / THROTTLE / FREEZE / STOP   │
└────────────────────────┬────────────────────────────┘
                         │ decision quality passed
                         ▼
┌─────────────────────────────────────────────────────┐
│  HOW Layer — OPA · Cedar · Microsoft AGT             │
│  Evaluates: Is this action permitted by policy?      │
└────────────────────────┬────────────────────────────┘
                         │ policy compliant
                         ▼
┌─────────────────────────────────────────────────────┐
│  WHO Layer — Okta · Entra · AWS IAM · Glasswing      │
│  Evaluates: Is this agent authorized to act?         │
└─────────────────────────────────────────────────────┘
```

Each layer addresses a structurally different governance question. `constitutional-agent` is the top layer — evaluating decision quality *after* identity and policy have already passed.

---

## The Problem: WHO and HOW Are Solved. WHY Is Not.

AI agent governance has three structurally distinct layers. Most organizations have the first two. Almost none have the third.

| Tier | Question | Tools | What the layer can't address alone |
|------|----------|-------|-------------------------------------|
| **WHO** | Is this agent authorized to act? | Microsoft Entra Agent ID, Okta, AWS IAM, Glasswing | Authorization doesn't evaluate whether an authorized agent's decision is sound |
| **HOW** | Is this action permitted by policy? | Microsoft AGT, NeMo Guardrails, LangChain, OWASP Agentic AI | Policy enforcement covers scenarios administrators wrote rules for — not novel ones |
| **WHY** | Does this decision align with our constitutional principles? | **This library** | — |

WHO governance gets the agent through the door. HOW governance enforces the rules written by administrators. Neither asks whether the agent's decision is *right* — aligned with the organization's mission, economic survival, and constitutional values. That's the WHY layer. `constitutional-agent` complements identity and policy tools — it does not replace them.

## Works Alongside Your Stack

`constitutional-agent` is the third governance layer, not a replacement for the first two. Use Okta or Microsoft Entra for identity (WHO), OPA or Cedar or Microsoft AGT for policy enforcement (HOW), and `constitutional-agent` for decision quality governance at the top of that stack. The gates evaluate constitutional soundness after the agent is authorized and the action is policy-compliant — covering the scenarios your policy writers haven't written rules for yet.

---

## When to Use / When Not to Use

**Use this when:**
- Your agent makes autonomous decisions that affect real economic, operational, or reputational outcomes
- You need governance evidence for compliance (EU AI Act, NIST AI RMF, internal audit)
- You need a principled FREEZE/STOP mechanism, not just a policy lookup
- You want gates to cover scenarios your policy writers haven't written rules for yet

**Not the right fit when:**
- You need real-time guardrails on LLM output tokens — use NeMo Guardrails, Lakera, or similar
- You need identity and access management — use Okta, Entra, or Glasswing
- Your agent has no economic or operational authority and only answers questions

---

## Case Study: Four Failures Constitutional Governance Would Have Caught

On April 7, 2026, a developer published one of the most honest accounts of autonomous agent failure on the internet: [My AI agent finally made money. It took 200 runs and 41 days.](https://dev.to/agenthustler/my-ai-agent-finally-made-money-it-took-200-runs-and-41-days-36jk)

$6.74 earned. 200 runs. 41 days. Four failure modes that constitutional governance would have caught.

| Failure | Duration | Constitutional Gate | Caught By |
|---------|---------|-------------------|-----------|
| Broken Lightning wallet — accepted payments, never settled | Weeks | HC-11 + EpistemicGate | `hours_since_settlement_confirmation > 24` → STOP |
| Mispriced Lightning actors at $0.00005 (wrong by orders of magnitude) | ~30 runs | EpistemicGate | `assumption_volatility` high — external verification required before execution |
| Shadow-banned by HN, kept posting for 30 runs | 30+ runs | RiskGate | `channel_health = 0%` → FAIL — stop spending on dead channels |
| Strategy locked on MCP servers for 30 runs, zero conversion | 30+ runs | ConstitutionalGate | `lessons_learned_weekly = 0` → FAIL — document what you learned or stop |

Constitutional governance doesn't guarantee faster revenue. It guarantees you don't spend 30 runs posting into a shadow-banned account after week 2.

**Full audit:** [examples/agenthustler_audit.md](examples/agenthustler_audit.md)

---

## Quick Start

```python
from constitutional_agent import Constitution

constitution = Constitution.from_defaults()

result = constitution.evaluate({
    # Hard constraint context
    "failing_tests": 0,
    "hours_since_last_execution": 4,
    "gate_override_without_amendment": False,

    # Epistemic: is the agent's reasoning sound?
    "verification_pass_rate": 0.85,
    "uncertainty_disclosure_rate": 0.90,

    # Risk: are outbound actions safe?
    "channel_health": 0.92,
    "security_critical_events": 0,

    # Economic: is the business healthy?
    "stage": "pre_revenue",
    "runway_months": 8.5,
    "user_return_rate": 0.22,

    # Constitutional: is the agent learning?
    "lessons_learned_weekly": 3,
    "amendments_per_month": 2,
})

if result.system_state.value == "FREEZE":
    print(f"BLOCKED: {result.blocking_gate.reason}")
elif result.system_state.value == "THROTTLE":
    print(f"THROTTLE: {[g.gate for g in result.hold_gates]}")
else:
    print(f"State: {result.system_state.value}")  # RUN or COMPOUND
```

---

## EU AI Act Article 27 — FRIA Output (v0.4.0)

`constitution.fria_evidence(context)` maps all six gates to the six FRIA categories required by EU AI Act Article 27. Deployments subject to the Act must complete a Fundamental Rights Impact Assessment before going live; this method generates structured evidence directly from live evaluation data.

```python
from constitutional_agent.fria import fria_summary, fria_narrative

evidence = constitution.fria_evidence(context)  # list[FRIAEvidence]
summary  = fria_summary(evidence)               # {overall_status, covered, flagged, gaps}
report   = fria_narrative(evidence)             # human-readable markdown

# Six categories automatically populated:
# Safety & robustness      -> RiskGate + HC-1/7
# Non-discrimination       -> EpistemicGate
# Human oversight          -> AutonomyGate + HC-12
# Privacy & data governance -> RiskGate
# Transparency             -> GovernanceGate + HC-4/15
# Accountability           -> GovernanceGate + HC-11/12

if summary["overall_status"] != "compliant":
    gaps = [k for k, v in summary["categories"].items() if v["status"] != "covered"]
    print("FRIA gaps:", gaps)
```

## Core Concepts

### Gates

Gates are pre-execution constitutional checks. They evaluate every decision against first principles — not a policy lookup table. When no policy covers a scenario, a policy system passes it. When no policy covers a scenario, a gate evaluates it against constitutional intent and decides.

**Gate states:**
- `PASS` — Decision is constitutionally sound. Proceed.
- `HOLD` — Conditions are marginal. **THROTTLE** — conserve resources, skip discretionary actions.
- `FAIL` — Conditions are violated. **FREEZE** — stop all discretionary spend until resolved.

**System states (composite from all gate results):**
- `COMPOUND` — All gates PASS + all stretch targets met. Maximum growth mode.
- `RUN` — All gates PASS. Normal autonomous operation.
- `THROTTLE` — Any gate HOLD. Conserve resources.
- `FREEZE` — Any gate FAIL. Stop all discretionary spend.
- `STOP` — Hard constraint violated. Human intervention required immediately.

### Hard Constraints

Hard constraints are absolute prohibitions. Unlike gates (which can be amended through a governance process), hard constraints **cannot be overridden by any agent action, amendment, or human instruction** — only by the highest authority (CEO/board) through a formal ratification process.

Hard constraint violations short-circuit to `STOP` state — not FREEZE. The difference: FREEZE is a recoverable system state. STOP requires a human to acknowledge and clear the violation before any execution resumes.

**Built-in hard constraints:**

| ID | Prohibition |
|----|-------------|
| HC-1 | No deploy or promotion when automated tests fail |
| HC-2 | No spend exceeding approved budget without human authorization |
| HC-3 | Runway must never drop below the hard survival floor |
| HC-4 | No fabricated or estimated data presented as measured fact |
| HC-5 | No irreversible action without explicit confirmation |
| HC-6 | No SQL built by string concatenation with user input |
| HC-7 | No timing-unsafe secret comparisons |
| HC-8 | No unauthenticated email sender domains |
| HC-9 | No false time claims in user-facing communications |
| HC-10 | No bare exception handlers in governance or safety code |
| HC-11 | No agent outage exceeding 24 hours without human notification |
| HC-12 | No manual override of constitutional gates without ratified amendment |

### Amendments

Constitutional governance is not static. Rules must evolve as context changes. The amendment process enables formal evolution without losing foundational constraints.

**Key properties:**
- Agents can **propose** amendments — they cannot **ratify** them
- Ratification requires the designated authority (not the proposing agent)
- Hard constraint (HC-*) amendments require the highest authority
- All amendments are versioned and logged

```python
# Propose (agent can do this)
amendment_id = constitution.propose_amendment(
    description="Reduce EpistemicGate hold threshold from 0.70 to 0.65",
    rationale="External verification latency increased. 0.65 still provides adequate safety.",
    affected_sections=["EpistemicGate"],
    proposed_by="my_agent_v2",
)

# Ratify (requires designated human authority — not the proposing agent)
constitution.ratify_amendment(
    amendment_id=amendment_id,
    ratified_by="cto@yourorg.com",
    evidence={"latency_data": "p99 verification latency: 4.2s"}
)
```

---

## The Six Gates

| Gate | Prevents | Key Metrics | Example Failure Without It |
|------|----------|-------------|---------------------------|
| **EpistemicGate** | False certainty | `verification_pass_rate`, `uncertainty_disclosure_rate`, `assumption_volatility` | Agent acts on unverified cost assumption. All downstream economics are wrong for 30 cycles |
| **RiskGate** | Trust damage | `misuse_risk_index`, `channel_health`, `irreversibility_score` | Agent posts to shadow-banned channel for 30 runs. Zero visibility. Full spend wasted |
| **GovernanceGate** | Metric gaming | `control_bypass_attempts`, `audit_coverage`, `metric_anomaly_score` | Agent optimizes audit metric without improving actual audit coverage. Governance is theater |
| **EconomicGate** | Financial ruin | `runway_months`, `gross_margin`, `cac`, `user_return_rate` | Agent burns 4 months of runway on a campaign. No runway gate. CEO discovers afterward |
| **AutonomyGate** | Human dependency | `human_minutes_per_day`, `decisions_per_day`, `agent_activation_rate` | "Autonomous" agent requires CEO approval for 70% of decisions. 3 hours of human time daily |
| **ConstitutionalGate** | Stagnation | `lessons_learned_weekly`, `amendments_per_month`, `bug_recurrence_rate` | Agent repeats same failed strategy 30 times. Zero lessons documented. Zero strategy change |

### Gate Details

**EpistemicGate** — Prevents false certainty

Evaluates whether the agent has earned confidence in its reasoning. An agent that acts on self-generated beliefs without external verification, never discloses uncertainty, or ignores disagreement signals is epistemically unsound. The EG gate enforces reasoning quality before execution.

```python
from constitutional_agent import EpistemicGate

gate = EpistemicGate()
result = gate.evaluate({
    "verification_pass_rate": 0.45,       # FAIL — below 0.50
    "uncertainty_disclosure_rate": 0.90,
    "assumption_volatility": 0.10,
    "disagreement_persistence": 0.05,
})
# GateResult(gate="EpistemicGate", state=FAIL,
#   reason="Low external verification rate (0.45 < 0.50)...")
```

**RiskGate** — Prevents trust damage

Evaluates the safety of outbound actions. Critically: it monitors `channel_health` — the fraction of actions on a given channel that produce the expected outcome. An agent posting to a shadow-banned platform has 0% channel health. The RiskGate blocks further spend on dead channels.

**GovernanceGate** — Prevents gaming

Detects when an agent is optimizing for governance metrics rather than underlying outcomes. Zero tolerance for control bypass attempts. High bar for audit coverage (95%) — gaps in logging hide problems.

**EconomicGate** — Prevents financial ruin

The only open-source governance gate that evaluates financial sustainability. Two modes: `pre_revenue` (value creation metrics: return rate, completion rate, runway) and `post_revenue` (unit economics: margin, CAC, churn, LTV:CAC). Runway floor is enforced in both modes.

**AutonomyGate** — Ensures Level 4+ operation

Measures whether agents are actually deciding and executing independently. Flags both extremes: agents that require too much human input (not autonomous) and agents that never escalate when they should. The target is minimum viable escalation rate.

**ConstitutionalGate** — Ensures self-improvement

A governance system that never changes is brittle. An agent that repeats failures without learning is not improving. This gate enforces that the constitutional system is alive: lessons are being extracted, amendments are being ratified, and the agent's knowledge base is staying fresh.

---

## Hard Constraints vs. Policies

This distinction matters more than any other architectural decision in governance.

| | Policies (HOW layer) | Hard Constraints (WHY layer) |
|--|---------------------|------------------------------|
| **Defined by** | Administrators in YAML/OPA/Cedar | Constitutional law in code |
| **Coverage** | Scenarios explicitly written | All scenarios (evaluated against intent) |
| **Override** | Possible by updating policy file | Impossible by any agent action |
| **Gap surface** | Every unwritten scenario is ungoverned | Constitutional intent covers novel scenarios |
| **Amendment** | Change the YAML | Formal ratification by highest authority |
| **Failure mode** | "No policy for this" → passes | "Check errored" → treated as violated (fail-CLOSED) |

```python
# HOW layer (policy enforcement — external):
if action in blocked_actions:
    raise PolicyViolation("blocked by policy")
# Novel scenario: no entry in blocked_actions → passes ungoverned

# WHY layer (constitutional enforcement — embedded):
result = epistemic_gate.evaluate(action_context)
if result.state == GateState.FAIL:
    raise ConstitutionalViolation(result.reason)
# Novel scenario: evaluated against epistemic soundness principles → gate decides
```

---

## Installation

```bash
pip install constitutional-agent
```

**Requirements:** Python 3.11+, pydantic >= 2.6, pyyaml >= 6.0

**From source:**
```bash
git clone https://github.com/CognitiveThoughtEngine/constitutional-agent-governance
cd constitutional-agent-governance
pip install -e ".[dev]"
```

---

## Configuration

Load from a `governance.yaml` file:

```python
constitution = Constitution.load("governance.yaml")
```

Or use production-validated defaults:

```python
constitution = Constitution.from_defaults()
```

See [governance.yaml](governance.yaml) for the full schema with all configurable thresholds. See [examples/governance.yaml](examples/governance.yaml) for an annotated example with a content-publishing agent.

---

## Links

**This library:**
- **35-Check Governance Checklist:** [checklist/CONSTITUTIONAL_GOVERNANCE_CHECKLIST.md](checklist/CONSTITUTIONAL_GOVERNANCE_CHECKLIST.md)
- **agenthustler case study audit:** [examples/agenthustler_audit.md](examples/agenthustler_audit.md)
- **Working example:** [examples/basic_agent.py](examples/basic_agent.py)
- **Full configuration schema:** [governance.yaml](governance.yaml)
- **Roadmap:** [ROADMAP.md](ROADMAP.md)

**Background reading:**
- **Introducing constitutional-agent** — the WHY layer, what it covers, and the agenthustler audit: [cteinvest.com/blog/constitutional-agent-open-source-why-layer-governance.html](https://www.cteinvest.com/blog/constitutional-agent-open-source-why-layer-governance.html)
- **WHO vs HOW: the AI agent governance gap** — why identity + policy enforcement is not enough: [cteinvest.com/blog/who-vs-how-ai-agent-governance-gap.html](https://www.cteinvest.com/blog/who-vs-how-ai-agent-governance-gap.html)
- **The Six-Gate Architecture** — how the gate system works and why the ordering matters: [cteinvest.com/blog/six-gate-architecture.html](https://www.cteinvest.com/blog/six-gate-architecture.html)
- **Why AI safety code must fail-closed** — the principle behind hard constraint design: [cteinvest.com/blog/why-ai-safety-code-must-fail-closed.html](https://www.cteinvest.com/blog/why-ai-safety-code-must-fail-closed.html)
- **Constitutional vs behavioral governance** — the structural difference between a gate and a policy rule: [cteinvest.com/blog/constitutional-vs-behavioral-agent-governance.html](https://www.cteinvest.com/blog/constitutional-vs-behavioral-agent-governance.html)

**Professional assessment:**
- **Constitutional Governance Review** (2-hour assessment, written report, top 3 gaps + remediation roadmap): [cteinvest.com/blog/constitutional-agent-open-source-why-layer-governance.html#assessment](https://www.cteinvest.com/blog/constitutional-agent-open-source-why-layer-governance.html)

**Research preprints (DOI):**
- DLI Framework: [10.5281/zenodo.18217577](https://doi.org/10.5281/zenodo.18217577)
- Harness Design: [10.5281/zenodo.19343034](https://doi.org/10.5281/zenodo.19343034)
- Community Security Governance: [10.5281/zenodo.19343108](https://doi.org/10.5281/zenodo.19343108)

---

## The Reference Implementation

This library is a portable extract from the HRAO-E Constitutional Framework — a production autonomous organization that has operated under constitutional governance for 98 days.

**This library:**
- **77 test functions** across 2 test modules, 0 failed
- **12 hard constraints** (HC-1 through HC-12) enforced in code
- **6 constitutional gates** (EG, RG, GG, EPG, AAG, CGG)
- `fria_evidence()` generates EU AI Act Article 27 FRIA evidence programmatically

**The production system this was extracted from (HRAO-E):**
- **52 agents** operating under constitutional governance per cycle
- **64 constitutional amendments** ratified through formal process
- **1,929 test functions**, 0 failed
- **17 hard constraints** (HC-1 through HC-17, including 5 additional production constraints)

The library ships HC-1 through HC-12 — the portable, organization-agnostic core. HC-13 through HC-17 are HRAO-E-specific operational constraints not included in the library.

The framework has been cited in NIST submissions (800-2, Agent Identity) and acknowledged by CAISI. Five preprints published on Zenodo.

**Self-assessment:** We ran the Constitutional AI Governance Stress Test (CGST) on this library before offering it as a service. Score: **63/100 (Governance Draft)**. Ungoverned baseline: 6/100. [Full report](https://www.cteinvest.com/blog/cgst-self-assessment-constitutional-agent.html).

---

## Contributing

Constitutional governance improves through formal amendment — not unilateral change. The same principle applies here.

Submit a PR with:
1. What you're changing and why
2. Which gate or constraint is affected
3. Evidence that the threshold change improves constitutional soundness

Hard constraint changes require a comment from a maintainer before merge. Gate threshold changes require evidence (test results, production data, or cited research).

---

## License

MIT — fork it, adapt it, cite it.

---

*Constitutional governance is the WHY layer.*
*WHO = identity. HOW = behavior. WHY = values that survive any execution.*
