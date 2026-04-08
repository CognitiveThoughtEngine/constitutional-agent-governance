---
name: Bug report
about: Something is broken or behaving unexpectedly
title: "[BUG] "
labels: bug
assignees: ''
---

**What happened?**
<!-- A clear description of the bug -->

**What did you expect to happen?**

**Minimal reproduction**
```python
from constitutional_agent import ...

# paste the smallest code that triggers the bug
```

**Gate or constraint affected**
<!-- e.g. EpistemicGate, HC-3, SixGateEvaluator -->

**Error output**
```
paste the full traceback here
```

**Environment**
- constitutional-agent version:
- Python version:
- OS:

**Fail-CLOSED check**
<!-- Did the bug cause the library to pass when it should have blocked? If so, mark this CRITICAL. -->
- [ ] The bug causes a safety check to pass when it should block (CRITICAL — label this `fail-open-violation`)
- [ ] The bug causes a false positive (blocks when it should not)
- [ ] Other
