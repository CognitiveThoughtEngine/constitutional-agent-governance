---
name: Hard constraint proposal
about: Propose a new HC-* hard constraint (requires maintainer sign-off before merge)
title: "[HC] "
labels: hard-constraint, maintainer-review-required
assignees: ''
---

> **Note:** Hard constraint changes require a maintainer comment before any PR is merged.
> Open this issue first. Get alignment. Then submit the PR.

**Proposed constraint ID**
<!-- HC-13, HC-14, etc. — maintainers will assign the final ID -->

**One-line prohibition**
<!-- "No [action] without [condition]" format -->

**Why this needs to be a hard constraint (not a gate)**
<!-- Hard constraints are absolute — no amendment, no override. Gates can be tuned.
     Explain why this prohibition must be unconditional. -->

**Real-world failure mode this prevents**
<!-- Describe a specific incident or scenario where the absence of this constraint
     caused or would cause harm. Be concrete. -->

**Proposed check implementation**
```python
HardConstraint(
    id="HC-XX",
    description="...",
    check=lambda ctx: bool(ctx.get("your_key", False)),
    remedy="...",
    tags=["your", "tags"],
)
```

**Context key(s) required**
<!-- What key(s) must the caller provide in the context dict? -->

**Fail-CLOSED behavior**
<!-- What should happen if the check itself raises an exception? -->
- [ ] Treat as violated (recommended — fail-CLOSED)
- [ ] Treat as not violated (explain why this is safe here)

**Is this specific to a particular industry or use case?**
<!-- If yes, consider whether it belongs in the built-in set or as a domain-specific example -->
