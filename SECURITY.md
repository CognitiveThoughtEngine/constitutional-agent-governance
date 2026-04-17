# Security Policy

## Scope

Security vulnerabilities in `constitutional-agent` fall into two categories with different severity levels:

**CRITICAL — Fail-open violations**
Any bug that causes a safety check to pass when it should block. This includes:
- Hard constraints returning `False` (not violated) when the constraint is violated
- Gate `evaluate()` returning `PASS` or `HOLD` when it should return `FAIL`
- Exception handlers that permit execution on error instead of blocking (violates the fail-CLOSED principle)
- `check_hard_constraints()` silently swallowing exceptions and returning an empty violations list

These are treated as CRITICAL regardless of how they are triggered.

**Standard — Implementation bugs**
Logic errors, incorrect threshold comparisons, incorrect metric key names, type errors, and similar bugs that do not affect the fail-CLOSED safety behavior.

## Reporting a Vulnerability

**For CRITICAL fail-open violations:**
Email `security@cteinvest.com` with subject line `[constitutional-agent] CRITICAL: fail-open in <component>`.

Include:
- The specific gate or constraint affected
- A minimal reproduction case
- Whether this causes a safety check to pass when it should block
- constitutional-agent version

We will acknowledge within 24 hours and publish a fix within 72 hours. The fix will be released as a patch version and the vulnerability documented in `CHANGELOG.md`.

**For standard bugs:**
Open a GitHub issue using the bug report template. No embargo needed.

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.5.x (current) | Yes |
| 0.4.x | Security fixes only |
| < 0.4.0 | No |

## The Fail-CLOSED Principle

Every safety check in this library is designed to fail-CLOSED: if the check itself errors, the library treats the constraint as **violated** (blocking), not as passed. This is intentional and documented behavior.

```python
def is_violated(self, context):
    try:
        return bool(self.check(context))
    except Exception:
        return True  # fail-CLOSED: check error = treat as violated
```

Any PR that changes this behavior to fail-open (returning `False` on exception) will be rejected regardless of the stated rationale.
