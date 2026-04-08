# What Constitutional Governance Would Have Caught in agenthustler's 200-Run Experiment

**Reference:** [My AI agent finally made money. It took 200 runs and 41 days.](https://dev.to/agenthustler/my-ai-agent-finally-made-money-it-took-200-runs-and-41-days-36jk)

**Result:** $6.74 earned after 200 runs and 41 days.

agenthustler's post is one of the most honest accounts of autonomous agent failure published in 2026. The agent earned money — eventually. But four failure modes burned most of those 200 runs on avoidable problems. Each maps directly to a constitutional governance gate.

---

## The Four Failures and What Would Have Caught Them

| # | Failure Mode | How Long | Constitutional Gate | Specific Check |
|---|-------------|---------|-------------------|----------------|
| 1 | Broken Lightning wallet — accepted payments, never settled | Weeks | **HC-11** (Silent Outage) + **EpistemicGate** | `hours_since_settlement_confirmation > 24` → STOP; `verification_pass_rate` of payment pipeline < 0.50 → FAIL |
| 2 | Mispriced Lightning actors at $0.00005 — wrong by orders of magnitude | ~30 runs | **EpistemicGate** | `assumption_volatility` high (cost assumptions not externally verified) → HOLD; external verification against actual invoices required before execution |
| 3 | Shadow-banned by Hacker News, kept posting for 30 runs | 30+ runs | **RiskGate** | `channel_health` for HN posts at 0% (zero visibility) → FAIL; outbound channel failure triggers FREEZE on that channel |
| 4 | Strategy locked on MCP servers for 30 runs despite zero conversion | 30+ runs | **ConstitutionalGate** | `lessons_learned_weekly = 0` → FAIL; zero documented lessons from repeated failure triggers constitutional FREEZE until lessons are extracted |

---

## Failure 1: The Broken Lightning Wallet

**What happened:** The agent accepted micropayments through a Lightning wallet but the settlement pipeline was broken. Payments came in, but the wallet never actually settled. The agent thought it was earning; it wasn't.

**How long it persisted:** Weeks.

**Constitutional response:**

HC-11 (Silent Outage): Any process that goes 24 hours without a successful completion triggers an immediate STOP. The settlement pipeline had gone days without confirmation. HC-11 would have triggered an alert and stopped all payment-dependent actions.

EpistemicGate: The `verification_pass_rate` for the payment pipeline — measured as "payments accepted that successfully settled / payments accepted" — would have dropped to near zero. A verification rate below 0.50 triggers EG FAIL → FREEZE.

```python
result = constitution.evaluate({
    "verification_pass_rate": 0.02,  # 2% of payments actually settled
    "hours_since_last_execution": 36,  # Settlement pipeline silent for 36h
    ...
})
# Result: STOP (HC-11 violation) + FREEZE (EpistemicGate FAIL)
# Blocking: "HC-11: No silent outage exceeding 24 hours"
```

**What the agent would have done differently:** Verified that accepted payments were settling before running any more payment-dependent cycles. Three runs, not thirty.

---

## Failure 2: Mispriced Lightning Actors

**What happened:** The agent was pricing Lightning network actors at $0.00005 — wrong by at least one to two orders of magnitude based on actual market rates. This meant every economic calculation downstream was built on a false assumption.

**How long it persisted:** The post implies this was embedded in the initial model and took many runs to surface.

**Constitutional response:**

EpistemicGate: The `assumption_volatility` metric tracks how often foundational assumptions are revised without new evidence — or conversely, how often they *should* be revised but aren't. Cost basis assumptions that have never been externally verified contribute to high assumption volatility.

The EG gate requires external verification of foundational assumptions before they drive execution. A cost assumption that came from model inference rather than actual market data would be flagged as unverified.

```python
result = constitution.evaluate({
    "verification_pass_rate": 0.55,  # Core cost assumptions not externally verified
    "assumption_volatility": 0.40,   # Cost model never cross-checked against actuals
    ...
})
# Result: THROTTLE (EpistemicGate HOLD)
# Reason: "High assumption volatility (0.40 > 0.25). Verify core assumptions
#          against external sources before expanding execution scope."
```

**What the agent would have done differently:** Required one externally verified data point (an actual Lightning actor invoice) before running pricing-dependent logic. One verification run, not thirty cycles on a broken cost model.

---

## Failure 3: Shadow-Banned by Hacker News

**What happened:** After several weeks, the agent's Hacker News posts were invisible (shadow-banned). It had no mechanism to detect this. It kept posting. For 30+ runs, it was spending time and API budget on content that no one could see.

**How long it persisted:** Approximately 30 runs after the shadow ban.

**Constitutional response:**

RiskGate: The `channel_health` metric tracks the success rate of outbound channels — what fraction of actions on a given channel produce the expected outcome (in this case, visibility and engagement). After a shadow ban, channel_health for HN drops to near zero.

Channel health below 0.50 triggers RG FAIL → FREEZE on that channel. The agent cannot post to channels where its output is invisible.

```python
result = constitution.evaluate({
    "channel_health": 0.03,  # 3% of HN posts getting any engagement
    ...
})
# Result: FREEZE (RiskGate FAIL)
# Reason: "Channel health critical (0.03 < 0.50). Outbound channels are failing
#          or blocked. Stop spending on dead channels."
```

**What the agent would have done differently:** Detected zero-engagement HN posts after run 2-3 post-ban, flagged the channel as unhealthy, redirected effort to working channels. Thirty wasted runs → two.

---

## Failure 4: Strategy Death Spiral on MCP Servers

**What happened:** The agent decided that publishing MCP servers was the path to revenue. It ran this strategy for 30+ consecutive cycles. Zero conversion. It kept trying the same strategy anyway.

**How long it persisted:** 30+ runs.

**Constitutional response:**

ConstitutionalGate: The `lessons_learned_weekly` metric tracks whether the agent is actually extracting lessons from failure. An agent that runs the same failed strategy 30 times without documenting a lesson has `lessons_learned_weekly = 0`.

Zero lessons documented in a week triggers CGG FAIL → FREEZE. The agent cannot proceed until it documents what it has learned and proposes a different approach.

```python
result = constitution.evaluate({
    "lessons_learned_weekly": 0,   # Zero lessons from 15+ MCP failures
    "bug_recurrence_rate": 0.95,   # Same failure pattern repeating
    "amendments_per_month": 0,     # No strategy updates proposed
    ...
})
# Result: FREEZE (ConstitutionalGate FAIL)
# Reason: "Zero lessons documented this week. The agent is not learning.
#          A system that repeats failures without extracting lessons
#          is constitutionally dead."
```

**What the agent would have done differently:** After 5 MCP runs with zero conversion, CGG HOLD triggers. The agent must document why MCP hasn't worked and propose an alternative approach before running another cycle. After 7 runs with zero improvement, CGG FAIL → FREEZE. Strategy pivot required.

---

## The Bottom Line

> The agent earned $6.74 after 200 runs. Constitutional governance doesn't guarantee faster revenue. It guarantees you don't spend 30 runs posting into a shadow-banned account after week 2.

The four failures consumed roughly 80-90 of those 200 runs. Constitutional governance would not have prevented all of them — some iteration is necessary. But it would have:

1. **Caught the broken wallet in 1-2 runs** (HC-11 silent outage detection)
2. **Forced cost model verification before run 5** (EpistemicGate assumption verification)
3. **Stopped HN posting 2-3 runs after shadow ban** (RiskGate channel health)
4. **Forced a strategy pivot after 7 MCP failures** (ConstitutionalGate learning velocity)

A rough estimate: 200 runs → 60-80 runs with constitutional governance. Same outcome, 60-70% fewer wasted cycles.

---

## Running the Constitutional Audit on Your Agent

```python
from constitutional_agent import Constitution

constitution = Constitution.from_defaults()

# After each agent cycle, evaluate constitutional health
result = constitution.evaluate({
    # Track your agent's actual metrics — not estimates
    "verification_pass_rate": your_agent.get_verification_rate(),
    "channel_health": your_agent.get_channel_health("hacker_news"),
    "lessons_learned_weekly": your_agent.lessons_this_week,
    "hours_since_last_execution": your_agent.hours_since_last_success,
    # ... other metrics
})

if result.system_state.value in ("FREEZE", "STOP"):
    your_agent.halt()
    your_agent.escalate(result.summary)
elif result.system_state.value == "THROTTLE":
    your_agent.skip_discretionary_actions()
    # But keep running essential cycles
```

---

*agenthustler's experiment is cited with respect — the willingness to publish 200 runs of honest failure data is exactly the kind of epistemic transparency that constitutional governance is designed to reward.*

*Reference: dev.to/agenthustler/my-ai-agent-finally-made-money-it-took-200-runs-and-41-days-36jk*
