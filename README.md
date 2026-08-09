# constitutional-agent

[![Tests](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance/actions/workflows/tests.yml/badge.svg)](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/constitutional-agent)](https://pypi.org/project/constitutional-agent/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

**Decision governance for autonomous AI agents — the WHY layer.**

Your agent is authenticated (**WHO**) and inside its permissions (**HOW**). This library answers the question those layers can't: **is the _authorized_ action _sound_ — given its constitution, six gates, and twelve hard constraints — evaluated before it commits?**

<p align="center">
  <a href="https://youtu.be/vsNO-_HfDF8">
    <img src="https://img.youtube.com/vi/vsNO-_HfDF8/maxresdefault.jpg" alt="Three authorized actions compose past the risk budget — a 60-second proof" width="640">
  </a>
  <br><b><a href="https://youtu.be/vsNO-_HfDF8">▶ Watch the 60-second proof</a></b> — three individually-authorized actions compose to <code>HOLD</code> at the first threshold (a longer sequence escalates to <code>FREEZE</code>, as in the example below). Verified output; configured demonstration.
</p>

Extracted from HRAO-E, a live governed reference environment for constitutional governance. Informed three NIST-affiliated public comments: NIST AI 800-2, the Agent Identity RFI, and the NCCoE identity-and-authorization initiative. CAISI acknowledgment is documented for the first two. Grounded in a measured gap — a live agent-payment preview showed per-session spend caps that hold individually but [don't compose across concurrent sessions](https://dev.to/mspro3210/the-spend-cap-worked-the-risk-budget-didnt-compose-13n1) — the exact failure decision governance targets.

> **Maturity, honestly:** the six gates, execution states, and twelve hard constraints have shipped since v0.4; EU AI Act Article 27(1) FRIA-support evidence (a support package, not a complete FRIA) and an enforced amendment-authority protocol are current. Stateful _cross-session cumulative-risk composition_ — catching that specific aggregate — **shipped in v0.6.0** (the `composition` module; see below). It is new: exercised in unit tests and modeled on the measured AgentCore gap, but not yet hardened across as many production-days as the core gates.

### Where this sits

constitutional-agent is the **WHY** layer, not the **HOW**.

Policy-enforcement toolkits — zero-trust identity, execution sandboxing, runtime gates (e.g. Microsoft's Agent Governance Toolkit) — answer *can this action execute?* constitutional-agent answers a prior question: *should the agent be permitted to act at all, given its constitution, six gates, and twelve hard constraints?*

Enforcement toolkits sit at the execution boundary; the constitution sits above them, and an amendment protocol governs the constitution itself. Run both — they compose at different altitudes.

---

## What makes this different: cross-session risk composition

Most vendor-neutral governance engines score each action in isolation. That
leaves a blind spot: **an agent can pass every individual gate and still drift
into trouble over a sequence** — a series of individually acceptable actions can
exceed a separately defined *cumulative-risk budget* that no single evaluation
tracks.

**Documentation review (as of July 2026):** across the public documentation I
reviewed for the products below, I did not find an explicit mechanism that
accumulates a per-decision scalar risk weight *across sessions* and escalates
system posture when that trajectory crosses a threshold. This is a review of
published docs, not a source audit — vendors add features continuously, so treat
it as a dated snapshot, not a standing claim.

| Product | Docs reviewed (date) | Retains state? | Cross-session aggregate-risk decision? |
|---------|----------------------|----------------|----------------------------------------|
| Microsoft Agent Control / AGT | Jul 2026 | Session/policy state | Not found in reviewed docs |
| Galileo Agent Control | Jul 2026 | Traces/metrics | Not found in reviewed docs |
| Runlayer | Jul 2026 | Policy/runtime state | Not found in reviewed docs |
| NVIDIA NeMo Guardrails | Jul 2026 | Per-turn rails | Not found in reviewed docs |

`constitutional-agent` targets exactly that gap. The `ComposedEvaluator`
accumulates a risk weight per decision, composes it across a rolling window
(optionally with time decay), and escalates the system state when the
*accumulation* crosses a separately configured cumulative-risk budget — even when
every contributing decision, and all six memoryless gates, passed. Point it at
the durable `SqliteRiskStore` and the risk an agent built up yesterday still
counts today.

```python
from constitutional_agent import ComposedEvaluator, AccumulatedRiskComposer, SqliteRiskStore

# Durable store -> composition survives restarts and spans sessions.
evaluator = ComposedEvaluator(
    composer=AccumulatedRiskComposer(store=SqliteRiskStore("risk.db")),
)

# `decision` passes every one of the six gates on its own (per-call RUN) — use the
# healthy metrics dict from the Quick Start below. Each such decision still carries a
# real risk weight (here 0.6); the composer accumulates those across the session and
# escalates when the trajectory crosses the cumulative-risk budget.
for _ in range(7):
    result = evaluator.evaluate(decision, subject="pricing-agent", risk_weight=0.6)

print(result.per_call_state.value)  # RUN    — each decision passed all six gates
print(result.system_state.value)    # FREEZE — the accumulated risk crossed the budget
print(result.escalated)             # True   — composition escalated beyond the per-call verdict
print(result.composition.reason)    # "Accumulated risk 4.20 >= FAIL threshold 3.50 across 7 decisions..."
```

This is the WHY layer's stateful edge: WHO governs identity, HOW governs each
action, and only composition governs what **delegated autonomous authority**
accumulates across a whole session. See [ROADMAP.md](ROADMAP.md) (v0.6.0).

---

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
- **Teams that need EU AI Act Article 27 FRIA-support evidence** (not a complete FRIA) generated programmatically from live evaluation data

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
- You need governance evidence supporting compliance analysis (EU AI Act, NIST AI RMF, internal audit)
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
| Broken Lightning wallet — accepted payments, never settled | Weeks | HC-11 + EpistemicGate | `hours_since_last_execution > 24` → STOP |
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

## EU AI Act Article 27 — FRIA-support package

**This library does not produce a complete or legally sufficient Article 27 FRIA.**
It produces a *FRIA-support package*: operational governance evidence that a human
author — with deployer context and legal review — can fold into a real
Fundamental Rights Impact Assessment.

Two distinct artifacts:

1. **Internal governance-evidence categories** (`GovernanceEvidenceCategory`) —
   the framework's own six evidence buckets derived from gate and hard-constraint
   results. These are **not** the Article 27 categories; they are internal
   groupings of the operational evidence the framework can measure.
2. **Article 27(1) crosswalk** (`Article27Element`) — the ACTUAL elements Article
   27(1)(a)–(f) enumerates (deployment process & intended use; duration &
   frequency; affected persons/groups; specific risks of harm; human-oversight
   measures; governance/complaint arrangements). For each, the crosswalk states
   honestly whether the evidence is *auto-derived operational evidence*, *required
   deployer-supplied context*, or *missing/unverified*, plus a legal-review
   status. Operational gate telemetry cannot, on its own, establish intended use,
   duration/frequency, the affected population, or complaint arrangements — those
   require deployer input, and the crosswalk marks them as such rather than
   silently populating them.

```python
# Internal governance-evidence buckets (NOT the Article 27 categories):
evidence = constitution.fria_evidence(context)          # list[FRIAEvidence]

# Article 27(1) crosswalk + support package (honest about deployer gaps):
package  = constitution.fria_support_package(context, deployer_context={
    "deployment_process_and_intended_use": "...",
    "duration_and_frequency": "...",
    "affected_persons_and_groups": "...",
    "legal_review": {"specific_risks_of_harm": "reviewed"},
})

readiness = package["article_27_1_readiness"]
# {"elements_total": 6, "by_source": {...}, "legally_reviewed": N, "crosswalk_fields_present_and_reviewed": bool}
# `crosswalk_fields_present_and_reviewed` is true only when no element is missing
# and all elements are legally reviewed.
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

**Enforced, not merely recorded (v0.7.0).** Ratification runs an authority
protocol — all checks fail-closed:

- **Separation of duty:** the ratifier must be a *different* principal from the
  proposer (compared on a canonical principal id, so whitespace/case variants of
  the same identity cannot slip through).
- **Authority levels** (`AuthorityLevel`: `PROPOSER` < `RATIFIER` <
  `CONSTITUTIONAL_AUTHORITY`): ordinary amendments require `RATIFIER`+; any change
  touching **hard constraints or the authority registry** requires
  `CONSTITUTIONAL_AUTHORITY`. The required level is derived from the **actual
  affected configuration paths**, never from a proposer-supplied label.
- **Last-authority guard:** a registry change can never remove or demote the final
  `CONSTITUTIONAL_AUTHORITY` — the system is never left with zero root authorities.
- **Durable, audit-oriented record** for every decision (RATIFIED *and* REJECTED):
  proposer/ratifier ids + their levels, required authority, identity-assurance
  mode, actual affected paths, before/after constitution hashes, a monotonic
  version, and evidence retained scrubbed + by SHA-256 hash. Values under
  recognized secret-shaped keys are redacted before persistence (key-name
  detection — it does not guarantee that a secret value placed under a generic
  key is caught).

> **Restart recovery is version-only.** With a durable store, a new
> `Constitution` reconstructs the **monotonic version counter** from the ledger —
> fail-closed: an unreadable store or a malformed RATIFIED record raises
> `ConstitutionIntegrityError` rather than reset to 0 and risk reissuing an
> existing version number. It does **not** restore the governing configuration,
> authority registry, hard constraints, or pending proposals. Reload that governed
> state from its own source and verify it against the last record's
> `constitution_hash_after`; do not assume the amendment store recovers the full
> constitution.

> **Trust boundary.** The library authorizes a *registered* principal according to
> constitutional policy. It does **not** prove the caller controls that identity.
> Deployers can supply an authentication callback (`IdentityVerifier`) to bind the
> asserted principal to Entra / Okta / IAM / mTLS / a signed token / etc. The
> callback may only add restriction — it can never bypass separation-of-duty or
> authority-level rules.

```python
from constitutional_agent import Constitution, IdentityVerifier

# The initial registry is trusted deployer config — the bootstrap root of trust.
# After construction, registry changes flow through the SAME amendment process
# and require CONSTITUTIONAL_AUTHORITY. principal_id is an opaque, stable id.
constitution = Constitution(
    config=my_config,
    authority_registry={
        "svc-ceo-key-1a2b": "CONSTITUTIONAL_AUTHORITY",
        "svc-cto-key-9f8e": "RATIFIER",
    },
    # Optional: bind the asserted ratifier to your IdP (returns True/False).
    identity_verifier=IdentityVerifier(name="entra", verify=my_entra_check),
)

# Propose (any principal / agent may propose)
amendment_id = constitution.propose_amendment(
    description="Reduce EpistemicGate hold threshold from 0.70 to 0.65",
    rationale="External verification latency increased. 0.65 still adequate.",
    affected_sections=["EpistemicGate"],
    proposed_by="agent-pricing-v2",
    changes={"gates": {"epistemic": {"hold_threshold": 0.65}}},
)

# Ratify (must be a distinct, sufficiently-authorized, registered principal)
ok = constitution.ratify_amendment(
    amendment_id=amendment_id,
    ratified_by="svc-cto-key-9f8e",
    evidence={"latency_data": "p99 verification latency: 4.2s"},
    asserted_identity={"jwt": "<token>"},  # passed to the verifier; never stored
)
# ok is False (and a REJECTED record is written) if any check fails.
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

In our dated documentation survey, we did not identify another open-source governance gate that evaluates financial sustainability. Two modes: `pre_revenue` (value creation metrics: return rate, completion rate, runway) and `post_revenue` (unit economics: margin, CAC, churn, LTV:CAC). Runway floor is enforced in both modes.

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

**Requirements:** Python 3.11+, pyyaml >= 6.0

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

Or use reference defaults derived from HRAO-E (deployment validation required):

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
- **Introducing constitutional-agent** — the WHY layer, what it covers, and the agenthustler audit: [cognitivethoughtengine.com/blog/constitutional-agent-open-source-why-layer-governance.html](https://cognitivethoughtengine.com/blog/constitutional-agent-open-source-why-layer-governance.html)
- **WHO vs HOW: the AI agent governance gap** — why identity + policy enforcement is not enough: [cognitivethoughtengine.com/blog/who-vs-how-ai-agent-governance-gap.html](https://cognitivethoughtengine.com/blog/who-vs-how-ai-agent-governance-gap.html)
- **The Six-Gate Architecture** — how the gate system works and why the ordering matters: [cognitivethoughtengine.com/blog/six-gate-architecture.html](https://cognitivethoughtengine.com/blog/six-gate-architecture.html)
- **Why AI safety code must fail-closed** — the principle behind hard constraint design: [cognitivethoughtengine.com/blog/why-ai-safety-code-must-fail-closed.html](https://cognitivethoughtengine.com/blog/why-ai-safety-code-must-fail-closed.html)
- **Constitutional vs behavioral governance** — the structural difference between a gate and a policy rule: [cognitivethoughtengine.com/blog/constitutional-vs-behavioral-agent-governance.html](https://cognitivethoughtengine.com/blog/constitutional-vs-behavioral-agent-governance.html)

**Research preprints (DOI):**
- Constitutional Self-Governance — the six-gate model (production study): [10.5281/zenodo.19162104](https://doi.org/10.5281/zenodo.19162104)
- Beyond Identity Governance — identity is necessary but not sufficient: [10.5281/zenodo.19343034](https://doi.org/10.5281/zenodo.19343034)
- Authorized but Refused — telemetry of governance refusing authenticated agents: [10.5281/zenodo.21263262](https://doi.org/10.5281/zenodo.21263262)
- DLI Framework: [10.5281/zenodo.18217577](https://doi.org/10.5281/zenodo.18217577)
- Community Security Governance: [10.5281/zenodo.19343108](https://doi.org/10.5281/zenodo.19343108)

---

## The Reference Implementation

This library is a portable extract from the HRAO-E Constitutional Framework — a live governed reference environment for constitutional governance.

**This library (verifiable from this repo):**
- **Current test count and pass rate:** see the [Tests workflow](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance/actions/workflows/tests.yml) (badge above) — reproducible with `pytest` against this repo
- **12 hard constraints** (HC-1 through HC-12) enforced in code
- **6 constitutional gates** (EG, RG, GG, EPG, AAG, CGG)
- **Enforced amendment protocol** — separation of duties + authority levels + last-authority guard, with a durable audit record
- `fria_support_package()` generates EU AI Act Article 27(1) crosswalk evidence programmatically (a FRIA-support package, not a complete FRIA)

The library ships HC-1 through HC-12 — the portable, organization-agnostic core. Additional HRAO-E-specific operational constraints are not included in the library.

The framework has informed three NIST-affiliated public comments: NIST AI 800-2, the Agent Identity RFI, and the NCCoE identity-and-authorization initiative. CAISI acknowledgment is documented for the first two; acknowledgment of receipt is not endorsement. Multiple preprints are published on Zenodo — see [Citation](#citation).

**Self-assessment:** An April 2026 author self-assessment scored v0.4.0b3 at **63/100 (Early Implementation)** against [CGST v1.0](https://github.com/CognitiveThoughtEngine/cgst-framework). Ungoverned baseline: 6/100. This single internal assessment is illustrative, not independent validation. [Full report](https://cognitivethoughtengine.com/blog/cgst-self-assessment-constitutional-agent.html).

---

## Contributing

Constitutional governance improves through formal amendment — not unilateral change. The same principle applies here.

Submit a PR with:
1. What you're changing and why
2. Which gate or constraint is affected
3. Evidence that the threshold change improves constitutional soundness

Hard constraint changes require a comment from a maintainer before merge. Gate threshold changes require evidence (test results, production data, or cited research).

---

## Citation

If you cite this work in research:

> Saleme, M. K. (2026). *Constitutional Agent Governance* — six-gate decision governance framework with 12 hard constraints. ORCID: [0009-0003-6736-1900](https://orcid.org/0009-0003-6736-1900). https://github.com/CognitiveThoughtEngine/constitutional-agent-governance

Related Zenodo preprints: CSG ([10.5281/zenodo.19162104](https://doi.org/10.5281/zenodo.19162104)), Beyond Identity Governance ([10.5281/zenodo.19343034](https://doi.org/10.5281/zenodo.19343034)).

---

## License

MIT — fork it, adapt it, cite it.

---

*Constitutional governance is the WHY layer.*
*WHO = identity. HOW = behavior. WHY = values that survive any execution.*
