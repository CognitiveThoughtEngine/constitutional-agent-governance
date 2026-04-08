---
name: Gate threshold proposal
about: Propose changing a gate threshold (requires evidence)
title: "[GATE] "
labels: gate-threshold, needs-evidence
assignees: ''
---

**Which gate and threshold?**
<!-- e.g. EpistemicGate.VERIFICATION_HOLD: 0.70 → 0.65 -->

**Current value:** 
**Proposed value:** 

**Why this threshold is wrong**
<!-- Describe the specific scenario where the current threshold causes a false positive or false negative -->

**Evidence**
<!-- Gate threshold changes REQUIRE evidence. No evidence = no merge. -->
<!-- Acceptable: production traces, cited research, A/B results, incident post-mortems -->

- [ ] Production data (attach or describe — anonymized is fine)
- [ ] Academic/industry research (cite below)
- [ ] Incident post-mortem (describe the false positive/negative)
- [ ] A/B or split test results

**Citation or data:**
<!-- Paste your evidence here -->

**Which agents / use cases are affected?**
<!-- Help maintainers understand the scope. What kind of agent hits this threshold incorrectly? -->

**Proposed test**
```python
# Write a test that would pass with your proposed threshold
# and fail (correctly) with the current threshold
def test_new_threshold():
    ...
```
