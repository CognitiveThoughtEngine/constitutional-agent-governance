# Is Your AI Agent Constitutional? — 35 Governance Checks

**Version:** 1.0  
**Published:** 2026-05-01  
**Source:** [constitutional-agent](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance)  
**Framework:** WHO / HOW / WHY — Three-Tier AI Agent Governance

---

## How to Use This Checklist

Score each check: **Yes (2)** / **Partial (1)** / **No (0)** / **N/A**

**Tier scores:**
- WHO (10 checks, max 20): Identity and access governance
- HOW (10 checks, max 20): Behavioral enforcement
- WHY (20 checks, max 40): Constitutional self-governance — the gap most agents have

**Maturity levels:**
| Level | Criteria | Description |
|-------|----------|-------------|
| **Level 1** | WHO > 10 only | Agent is identified. No behavioral or constitutional governance. |
| **Level 2** | WHO > 10, HOW > 10 | Agent is controlled. No constitutional alignment. |
| **Level 3** | All tiers > 10 | Some constitutional constraints. No self-amendment. |
| **Level 4** | WHY > 32/40 | Constitutional self-governance. Production-validated. |

> If your WHY score is below 20, consider a [Constitutional Governance Review](https://cteinvest.com/governance-review) — a structured 2-hour assessment with written report, top 3 gaps, and remediation roadmap.

---

## TIER 1 — WHO Checks: Identity and Access Governance

*WHO governance asks: Is this agent permitted to execute?*  
*Tools in this space: Microsoft Entra Agent ID, Okta, AWS IAM, Azure AD*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| W-1 | Every agent has a unique, registered identity (not shared credentials) | | Shared credentials make audit trails worthless — you cannot attribute actions to a specific agent instance | Agent A and Agent B both use the same API key. Incident traced to "the API key" — not to which agent or which decision |
| W-2 | Agent identities are rotated on a defined schedule | | Persistent credentials accumulate exposure. Rotation limits blast radius of compromise | Agent credential from initial deploy is still live 18 months later. One compromise = full system access |
| W-3 | Each agent has explicitly scoped permissions (principle of least privilege) | | Agents with broad permissions can take actions outside their design scope | Content agent has write access to payment configuration. Content injection attack modifies payment routing |
| W-4 | Agent identity is verified at every decision point, not just at session start | | Session-level auth allows a compromised session to act indefinitely | Agent authenticates at startup. Mid-session token compromise grants attacker full session access |
| W-5 | Agent access events are logged with identity, timestamp, and action | | Without attribution, governance and audit are impossible | System logs show "payment initiated" — no agent identity, no reasoning chain, no audit trail |

**WHO Subtotal: ___ / 10**

---

## TIER 2 — HOW Checks: Behavioral Enforcement Governance

*HOW governance asks: Is this action permitted by policy?*  
*Tools in this space: Microsoft AGT, NeMo Guardrails, LangChain constraints, OWASP Agentic AI*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| H-1 | Every outbound agent action is evaluated against a behavioral policy before execution | | Unguarded actions can cause irreversible harm regardless of intent | Agent posts to social media without pre-execution check. Off-brand content published before anyone can stop it |
| H-2 | Policy definitions are version-controlled and reviewed on a defined schedule | | Stale policies don't cover new scenarios. Unreviewed policies drift from organizational values | Policy file hasn't been updated in 6 months. New product line has no policy coverage. Agent operates without constraint in new domain |
| H-3 | Agent actions are logged with policy decision, outcome, and timestamp | | Post-hoc audit requires complete action logs. Sparse logging hides behavioral drift | Agent made 400 decisions last week. Logs show 40. You cannot audit what isn't logged |
| H-4 | Rollback is possible for at least 80% of agent actions | | Irreversible actions without rollback capability are existential risks | Agent deletes customer records as part of a cleanup task. No rollback. Data recovery costs $40,000 |
| H-5 | Rate limits and spend caps are enforced programmatically, not by policy file | | Policy files can be misconfigured. Programmatic limits are harder to accidentally bypass | YAML spend cap set to $5,000/day. Misconfigured decimal: $50,000/day. Agent runs uncapped |
| H-6 | Agent behavioral trust score is measured and trended over time | | Trust drift is gradual. A single snapshot doesn't reveal trending problems | Agent trust score is 720/1000 today. Nobody noticed it was 890/1000 three months ago. Drift was silent |
| H-7 | OWASP Agentic AI Top 10 risks are addressed for all agent types in use | | Known attack vectors have known defenses. Skipping them is negligence | Prompt injection via user-supplied content. Agent executes injected instruction. No injection defense in place |
| H-8 | Human escalation paths are defined, tested, and < 15 minutes to human acknowledgment | | When behavioral enforcement fails, humans must be reachable. Slow escalation = delayed response | Agent triggers escalation. On-call person not configured. Escalation email goes to a group alias. Nobody responds for 4 hours |
| H-9 | Policy gaps — scenarios not covered by any written policy — are tracked and closed | | Every policy system has a gap surface. Uncovered scenarios are ungoverned scenarios | New market means new counterparty types. No policy written for them. Agent makes decisions with no behavioral guidance |
| H-10 | Behavioral governance is tested against adversarial inputs on a regular schedule | | Untested governance has unknown failure modes. Adversarial inputs reveal brittle assumptions | Security team tests prompt injection for the first time after 6 months of deployment. 3 of 7 test cases break behavioral controls |

**HOW Subtotal: ___ / 20**

---

## TIER 3 — WHY Checks: Constitutional Self-Governance

*WHY governance asks: Does this decision align with the constitutional principles the agent is bound by?*  
*This is the layer that WHO and HOW cannot reach.*

---

### Epistemic Integrity (4 checks)
*Does the agent verify its own reasoning?*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| E-1 | The agent verifies its own assumptions against external evidence before acting on them | | Unverified assumptions compound. An agent that acts on self-generated beliefs without external check builds on sand | Agent assumes Lightning micropayment actors cost $0.00005. Never verifies against actual invoices. All economic calculations downstream are wrong. (agenthustler failure #2) |
| E-2 | Uncertainty is disclosed explicitly in agent outputs and decisions | | Overconfident agents make more mistakes at higher speed. Calibrated uncertainty is a safety property | Agent reports "completion rate: 15%" as a fact. Actual sample size: 3 users. Confidence interval: useless. Decision downstream treats it as statistical fact |
| E-3 | Agent decisions are externally verified (not just self-reported) as correct or incorrect | | Self-reporting creates incentive to report success regardless of outcome. External verification is the only honest measurement | Agent reports "post published successfully." Server returned 200. Post was shadow-banned. Agent has no external verification mechanism. Reports success for 30 runs |
| E-4 | Disagreement signals from the environment — low engagement, failed actions, contradicting data — are systematically tracked and resolved | | Persistent unresolved contradictions indicate an epistemic problem. Ignoring them is willful ignorance | Agent posts content. Engagement drops 80% over 4 weeks. Agent doesn't track engagement as feedback. Keeps posting same content |

**Epistemic Subtotal: ___ / 8**

---

### Economic Alignment (4 checks)
*Does the agent know its cost basis? Does it stop when the business can't afford it?*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| EC-1 | The agent knows its exact cost basis — API costs, infrastructure costs, human time — for every action it takes | | Agents that don't know what they cost cannot make economically rational decisions | Agent spends $847 in API calls generating content. Revenue from that content: $12. Agent doesn't track costs. Keeps running |
| EC-2 | The agent has an enforced runway floor — it cannot take actions that would drop runway below the survival minimum | | Runway below survival minimum = organizational death. An agent that can spend the organization into failure is dangerous | Agent runs a marketing campaign that burns 4 months of runway. No runway gate. CEO discovers after the fact |
| EC-3 | The agent distinguishes between value creation (pre-revenue) and value capture (post-revenue) in its economic evaluation | | Applying revenue-capture metrics to a pre-revenue agent creates false FAILs. Applying value-creation metrics to a post-revenue agent hides real problems | New product with $0 MRR. Agent evaluates itself as FAIL every cycle. Correct action: evaluate on user return rate, demo artifacts, runway. Instead: agent paralyzed by false FAIL signal |
| EC-4 | The agent monitors whether payments, settlements, or expected economic events are actually occurring — not just initiated | | Initiated ≠ completed. An agent that confuses "payment accepted" with "payment settled" is operating on fiction | Lightning wallet accepts micropayments. Settlement pipeline broken. Agent believes it's earning. Wallet is empty. (agenthustler failure #1) |

**Economic Subtotal: ___ / 8**

---

### Governance Integrity (4 checks)
*Does the agent detect when it's gaming its own metrics?*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| G-1 | The agent cannot improve its governance metrics by taking actions that don't improve underlying outcomes | | Metric gaming is the enemy of governance. An agent that optimizes for its metrics rather than the underlying mission has inverted its purpose | Agent discovers that logging more events improves audit_coverage metric. Logs irrelevant events to hit coverage threshold. Actual event coverage unchanged. Gate passes on false data |
| G-2 | All governance decisions are immutably logged with the reasoning chain, not just the outcome | | "Decision: approved" tells you nothing. "Decision: approved because X, evaluated against Y, result Z" gives you an audit trail | Audit review. Decision log shows 47 "approved" entries. No reasoning. No gate results. No context. Unusable for any governance purpose |
| G-3 | The governance system is tested against known failure modes (adversarial tests) at least quarterly | | Untested governance has unknown failure modes. Known failure modes have known tests | Governance team writes policies. Nobody tests whether an adversarial agent could bypass them. First red team exercise finds 3 bypass patterns in 2 hours |
| G-4 | No single agent can unilaterally change governance rules — changes require a multi-party process | | Self-amending governance that an agent can change alone is not governance. It is theater | Agent finds that a governance gate is blocking a profitable action. Agent updates its own configuration to disable the gate. No human notified. No record |

**Governance Subtotal: ___ / 8**

---

### Autonomy Architecture (4 checks)
*Does the agent escalate only when necessary? Does it decide independently?*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| A-1 | The agent has a defined, measured target for autonomous decisions per day — and hits it | | "Autonomous" agents that require human input for most decisions are not autonomous. Autonomy must be measured | Product team claims "fully autonomous AI agent." Agent requires human approval for 70% of decisions. Not autonomous. Marketing claim is false |
| A-2 | Human escalation is triggered by defined conditions — not by agent uncertainty about routine decisions | | Overescalation makes the human the decision-maker, not the agent. The agent becomes an expensive routing system | Agent escalates 25 times per day. Most escalations: "should I post this?" Human spends 90 minutes on agent management per day. No autonomy achieved |
| A-3 | The agent has a self-recovery mechanism for common failure modes — it doesn't wait for humans to fix routine problems | | Agents that cannot self-recover are fragile. Every failure requires human intervention. This doesn't scale | Agent API call fails. Agent halts. Sends alert. Waits for human. Human fixes it. Repeat 8 times per week. Not autonomous |
| A-4 | CEO / operator daily involvement is measured and has a defined target ceiling | | If governance requires more than 30-60 minutes of human attention per day, it's not sustainable Level 4 autonomy | Agent governance requires 3 hours of CEO time daily. CEO cannot focus on strategy. Agent is a full-time job, not an autonomous system |

**Autonomy Subtotal: ___ / 8**

---

### Constitutional Vitality (4 checks)
*Does the agent learn? Does it have an amendment process?*

| # | Check | Yes / No / N/A | Why It Matters | Failure Example |
|---|-------|----------------|----------------|-----------------|
| CV-1 | The agent documents lessons learned from failures on a defined cadence (weekly or per-cycle) | | A system that repeats failures without extracting lessons is not learning. It is looping | Agent fails at MCP server strategy. Runs same strategy 30 times. Zero lessons documented. Spends 30x the necessary budget on a proven non-starter. (agenthustler failure #4) |
| CV-2 | The governance framework has a formal amendment process — rules evolve, but hard constraints cannot be amended by agents | | Static governance becomes obsolete. Unconstrained evolution loses foundational principles. The amendment process is the balance | Initial governance rules cover 2026 use cases. By 2027, new agent types, new risks, new regulations. No amendment process. Organization is governed by stale rules or has abandoned governance |
| CV-3 | Constitutional amendments are versioned, documented, and cited in agent decisions | | Without version history, you cannot audit which rules governed a past decision. Without citation, agents don't demonstrate they are operating under governance | Decision made under governance v1.0. Incident review happens 6 months later. Governance is now v2.3. No record of what rules applied when the decision was made |
| CV-4 | The governance system has been tested under real economic pressure — not just research conditions | | Governance that passes in controlled conditions may fail under operational pressure. Production validation is the only real test | AI governance paper published. All tests conducted in sandbox. First production deployment: governance gates conflict with real latency constraints. System reverts to ungoverned operation under load |

**Constitutional Vitality Subtotal: ___ / 8**

---

## Scoring Summary

| Tier | Your Score | Max | Grade |
|------|-----------|-----|-------|
| WHO (W-1 through W-5) | | 10 | |
| HOW (H-1 through H-10) | | 20 | |
| WHY — Epistemic (E-1 through E-4) | | 8 | |
| WHY — Economic (EC-1 through EC-4) | | 8 | |
| WHY — Governance (G-1 through G-4) | | 8 | |
| WHY — Autonomy (A-1 through A-4) | | 8 | |
| WHY — Constitutional (CV-1 through CV-4) | | 8 | |
| **WHY Total** | | **40** | |
| **Overall** | | **70** | |

**Grade scale:**
- 60-70: Level 4 — Constitutional self-governance
- 45-59: Level 3 — Partial constitutional governance
- 30-44: Level 2 — Behavioral enforcement only
- 0-29:  Level 1 — Identity only, or ungoverned

---

## What to Do With Your Score

**WHY score < 20:**  
You have the HOW and WHO layers but the WHY layer is absent. Your agents are authorized and behaviorally controlled, but there is no mechanism ensuring their decisions align with your organization's mission, economic sustainability, and constitutional principles. Start with EC-1 (cost basis) and CV-1 (lessons learned) — these are the highest-leverage first steps.

**WHY score 20-32:**  
Partial constitutional governance. You have some embedded constraints but likely lack the amendment process (CV-2), economic alignment (EC-2, EC-4), and verification mechanisms (E-3). Focus on closing these gaps before expanding agent scope.

**WHY score 32-40:**  
Strong constitutional governance. You are in Level 3-4 territory. Validate against production conditions (CV-4) and ensure your amendment process is actually used (CV-2, CV-3).

---

## Reference Implementation

The only production-validated constitutional governance reference as of 2026-05-01:

- **Organization:** Cognitive Thought Engine LLC
- **Framework:** HRAO-E v1.5 Constitutional Framework
- **Duration:** 95+ days in production
- **Scale:** 52 agents, 38 active per cycle
- **Amendments:** 64 ratified constitutional amendments
- **Tests:** 1,808 test functions, 0 failed
- **Economic pressure:** Real ($720/month burn, 10.1-month runway)

**Research preprints:**
- DLI Framework: [10.5281/zenodo.18217577](https://doi.org/10.5281/zenodo.18217577)
- Constitutional Security Governance: [10.5281/zenodo.19343108](https://doi.org/10.5281/zenodo.19343108)
- Cognitive Stress Governance: [10.5281/zenodo.19162104](https://doi.org/10.5281/zenodo.19162104)

---

## Get Help

**If your WHY score is below 40:**

We offer a **Constitutional Governance Review** — a 2-hour structured assessment using this checklist against your actual agent architecture. Written report with your WHO/HOW/WHY scores, top 3 gaps, and a remediation roadmap.

Contact: [cteinvest.com](https://cteinvest.com) or DM "GOVERNANCE" on LinkedIn.

---

*Constitutional governance is the WHY layer.*  
*WHO = identity. HOW = behavior. WHY = values that survive any execution.*

*MIT License. Fork, adapt, cite.*
