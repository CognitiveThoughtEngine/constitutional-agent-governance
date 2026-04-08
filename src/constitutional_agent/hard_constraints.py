"""
Constitutional Agent — Hard Constraints
Absolute prohibitions that no agent action can override.

Based on HRAO-E Constitutional Framework (cognitivethoughtengine.com)
HC-1 through HC-12 (original set — adapted for general use)

Hard constraints are constitutional law. They are:
    - Absolute: no exception, no override, no amendment by agents
    - Immediate: violation triggers STOP-level escalation, not FREEZE
    - Programmatic: enforced in code, not YAML policy files
    - Immutable: can only be changed by the highest authority (CEO/board)
      through a formal ratification process, never unilaterally

The difference between a gate and a hard constraint:
    Gates:            HOLD/FAIL states can be amended through governance.
                      A gate that FAILs triggers FREEZE, not permanent STOP.
    Hard constraints: Violations require IMMEDIATE human intervention.
                      No agent action can authorize proceeding past an HC.

Usage:
    from constitutional_agent.hard_constraints import (
        BUILTIN_HARD_CONSTRAINTS,
        check_hard_constraints,
    )

    violations = check_hard_constraints(context, BUILTIN_HARD_CONSTRAINTS)
    if violations:
        # STOP — do not proceed, escalate immediately
        for v in violations:
            print(f"{v.constraint_id}: {v.description}")
            print(f"Remedy: {v.remedy}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class HardConstraint:
    """
    A single hard constraint.

    Attributes:
        id:          Unique identifier (e.g. "HC-1").
        description: One-line description of the prohibition.
        check:       Callable that returns True if the constraint is VIOLATED.
                     Takes a context dict and returns bool.
        remedy:      What to do immediately when violated.
        severity:    Human-readable severity label (always "STOP").
    """

    id: str
    description: str
    check: Callable[[dict[str, Any]], bool]
    remedy: str
    severity: str = "STOP"
    tags: list[str] = field(default_factory=list)

    def is_violated(self, context: dict[str, Any]) -> bool:
        """Return True if this constraint is violated in the given context."""
        try:
            return bool(self.check(context))
        except Exception:
            # Fail-CLOSED: if the check itself errors, treat as violated.
            # Safety checks must never silently pass due to implementation bugs.
            return True


@dataclass
class HardConstraintResult:
    """Result of checking a single hard constraint."""

    constraint: HardConstraint
    violated: bool
    context_snapshot: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.constraint.id

    @property
    def remedy(self) -> str:
        return self.constraint.remedy

    @property
    def description(self) -> str:
        return self.constraint.description


def check_hard_constraints(
    context: dict[str, Any],
    constraints: list[HardConstraint] | None = None,
) -> list[HardConstraintResult]:
    """
    Evaluate all hard constraints against the provided context.

    Returns only the violated constraints. Empty list means all constraints
    are satisfied and the agent may proceed.

    Args:
        context:     Dict of context values for constraint evaluation.
                     See BUILTIN_HARD_CONSTRAINTS for expected keys.
        constraints: List of constraints to check. Defaults to
                     BUILTIN_HARD_CONSTRAINTS.

    Returns:
        List of HardConstraintResult for any violated constraints.
        Empty list if none are violated.

    Example:
        violations = check_hard_constraints({
            "failing_tests": 0,
            "hours_since_last_execution": 4,
            "proposed_spend": 100,
            "approved_budget": 500,
        })
        if violations:
            raise ConstitutionalViolation(violations)
    """
    if constraints is None:
        constraints = BUILTIN_HARD_CONSTRAINTS

    return [
        HardConstraintResult(
            constraint=hc,
            violated=True,
            context_snapshot={k: v for k, v in context.items()},
        )
        for hc in constraints
        if hc.is_violated(context)
    ]


# ---------------------------------------------------------------------------
# Built-in Hard Constraints (HC-1 through HC-12)
# Adapted from HRAO-E v1.5 Constitutional Framework for general use.
# These are conservative defaults — adapt to your organization.
# ---------------------------------------------------------------------------

BUILTIN_HARD_CONSTRAINTS: list[HardConstraint] = [

    HardConstraint(
        id="HC-1",
        description="No deploy or promotion when automated tests fail.",
        check=lambda ctx: int(ctx.get("failing_tests", 0)) > 0,
        remedy=(
            "Fix all failing tests before any deployment or promotion. "
            "No exceptions — a failing test suite signals broken assumptions."
        ),
        tags=["deployment", "quality"],
    ),

    HardConstraint(
        id="HC-2",
        description=(
            "No spend exceeding approved budget ceiling without human authorization."
        ),
        check=lambda ctx: (
            float(ctx.get("proposed_spend", 0)) > float(ctx.get("approved_budget", 500))
        ),
        remedy=(
            "Escalate to the budget authority before spending. "
            "Document the request, business case, and expected return. "
            "Never spend first and justify later."
        ),
        tags=["financial", "authorization"],
    ),

    HardConstraint(
        id="HC-3",
        description="Runway must never drop below the hard survival floor.",
        check=lambda ctx: float(ctx.get("runway_months", 12.0)) < 3.0,
        remedy=(
            "Immediately halt all discretionary spend. "
            "Escalate to CEO with cash position and burn rate. "
            "Do not resume until runway is above 6 months."
        ),
        tags=["financial", "survival"],
    ),

    HardConstraint(
        id="HC-4",
        description="No fabricated or estimated data presented as measured fact.",
        check=lambda ctx: bool(ctx.get("contains_fabricated_data", False)),
        remedy=(
            "Replace fabricated values with measured data or clearly labeled estimates. "
            "All metrics must cite their source and measurement method. "
            "Confidence levels must be disclosed."
        ),
        tags=["epistemic", "integrity"],
    ),

    HardConstraint(
        id="HC-5",
        description=(
            "No irreversible action (deletion, payment, public post) without "
            "explicit confirmation."
        ),
        check=lambda ctx: (
            bool(ctx.get("irreversible_action_pending", False))
            and not bool(ctx.get("irreversible_action_confirmed", False))
        ),
        remedy=(
            "Log the pending action. Request explicit confirmation from the "
            "appropriate authority. Default to the most reversible alternative "
            "if no response within the SLA window."
        ),
        tags=["reversibility", "authorization"],
    ),

    HardConstraint(
        id="HC-6",
        description="No SQL query built by string concatenation with user input.",
        check=lambda ctx: bool(ctx.get("sql_string_concatenation_detected", False)),
        remedy=(
            "Replace with parameterized queries immediately. "
            "Audit the full codebase for all instances — not just the one flagged. "
            "String-concatenated SQL is a critical security vulnerability (SQLi)."
        ),
        tags=["security", "sql-injection"],
    ),

    HardConstraint(
        id="HC-7",
        description=(
            "No timing-unsafe secret comparisons (== or != for tokens, "
            "API keys, or passwords)."
        ),
        check=lambda ctx: bool(ctx.get("timing_unsafe_comparison_detected", False)),
        remedy=(
            "Replace with hmac.compare_digest() or equivalent constant-time "
            "comparison. Audit the entire codebase — timing vulnerabilities "
            "are often copy-pasted across files."
        ),
        tags=["security", "timing-attack"],
    ),

    HardConstraint(
        id="HC-8",
        description=(
            "No use of DMARC-blocked or unauthenticated email sender domains."
        ),
        check=lambda ctx: bool(ctx.get("unauthenticated_email_sender", False)),
        remedy=(
            "Configure DMARC, DKIM, and SPF for all sending domains before "
            "sending any email. Sending from unauthenticated domains destroys "
            "deliverability and violates anti-spam law in many jurisdictions."
        ),
        tags=["email", "security", "compliance"],
    ),

    HardConstraint(
        id="HC-9",
        description=(
            "No false time claims in user-facing communications "
            "(e.g., '2 minutes' when actual time is 15 minutes)."
        ),
        check=lambda ctx: bool(ctx.get("false_time_claim_detected", False)),
        remedy=(
            "Audit all user-facing copy for time claims. "
            "Measure actual completion time and update all claims to match. "
            "False time claims destroy trust and may violate advertising standards."
        ),
        tags=["trust", "honesty", "compliance"],
    ),

    HardConstraint(
        id="HC-10",
        description=(
            "No bare exception handlers that silently swallow errors "
            "in governance or safety code paths."
        ),
        check=lambda ctx: bool(ctx.get("bare_except_pass_in_governance", False)),
        remedy=(
            "Replace all bare 'except: pass' with specific exception types "
            "and explicit remediation. Safety code must fail-CLOSED: "
            "if the check errors, treat as violated, not permitted."
        ),
        tags=["code-quality", "safety", "error-handling"],
    ),

    HardConstraint(
        id="HC-11",
        description=(
            "No agent outage exceeding 24 hours without human notification."
        ),
        check=lambda ctx: float(ctx.get("hours_since_last_execution", 0)) > 24,
        remedy=(
            "Immediately alert the human operator with: time of last execution, "
            "suspected root cause, and recovery steps attempted. "
            "A silent outage is worse than a visible one — it erodes trust "
            "in the governance system itself."
        ),
        tags=["reliability", "monitoring", "escalation"],
    ),

    HardConstraint(
        id="HC-12",
        description=(
            "No manual override of constitutional gates by any agent "
            "without ratified amendment."
        ),
        check=lambda ctx: bool(ctx.get("gate_override_without_amendment", False)),
        remedy=(
            "Revert the override immediately. "
            "Document the business case and submit as a constitutional amendment. "
            "Gates can only be changed through formal ratification — "
            "never bypassed unilaterally. A gate override without amendment "
            "is a constitutional violation, not a feature."
        ),
        tags=["governance", "constitutional", "amendment"],
    ),
]
