# Contributing to constitutional-agent

Constitutional governance improves through formal amendment — not unilateral change. The same principle applies here.

---

## What We're Looking For

- **Gate threshold evidence** — data showing a threshold should change (production traces, research citations, A/B results)
- **New hard constraints** — HC-* additions with clear prohibition rationale and check implementation
- **New gate metrics** — additional signals that improve constitutional evaluation quality
- **Bug fixes** — especially fail-CLOSED violations (safety checks that pass on error instead of blocking)
- **Examples and case studies** — real-world agent failures this library would have caught

We are **not** looking for:
- Gate threshold changes without evidence
- Features that make it easier to bypass gates
- New dependencies (the library is intentionally dependency-light)

---

## Gate Threshold Changes Require Evidence

A gate threshold change without evidence is a constitutional violation, not a contribution.

**Acceptable evidence:**
- Production data from a deployed agent (aggregated, anonymized)
- Cited academic or industry research
- A/B test results with statistical significance noted
- Incident post-mortems showing the threshold caused a false positive/negative

Include evidence in the PR description. No evidence = no merge, regardless of how reasonable the change seems.

---

## Hard Constraint Changes Require Maintainer Sign-Off

HC-* changes require a comment from a maintainer before merge. Hard constraints are the floor below which no agent can go — they must not drift through casual PRs.

If you believe a hard constraint is wrong, open a Discussion first. Make the case. Get alignment. Then submit the PR.

---

## How to Submit

1. **Open an issue** (or Discussion) describing what you're changing and why
2. **Fork and branch** — name your branch `gate/<gate-name>`, `hc/<id>`, or `fix/<description>`
3. **Write tests** — every gate change needs a test that would have caught the regression
4. **Submit a PR** with:
   - What you're changing and why
   - Which gate or constraint is affected
   - Evidence that the change improves constitutional soundness

---

## Development Setup

```bash
git clone https://github.com/CognitiveThoughtEngine/constitutional-agent-governance
cd constitutional-agent-governance
pip install -e ".[dev]"
pytest tests/ -v
```

All tests must pass. No exceptions.

---

## Code Style

- `ruff` for linting (`ruff check src/`)
- `mypy` for type checking (`mypy src/`)
- Line length: 100 characters
- All gate `evaluate()` methods must document their expected metrics keys

---

## The Fail-CLOSED Principle

If you touch safety code: **fail-CLOSED**.

```python
# Wrong — passes on error
def is_violated(self, context):
    try:
        return bool(self.check(context))
    except Exception:
        return False  # silently passes — constitutional violation

# Correct — blocks on error
def is_violated(self, context):
    try:
        return bool(self.check(context))
    except Exception:
        return True  # fail-CLOSED: if the check errors, treat as violated
```

A safety check that passes on error is not a safety check.

---

## License

By submitting a PR, you agree your contribution will be licensed under MIT.
