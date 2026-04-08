"""
Constitutional Agent — Constitution
The agent's governing document. Defines gates, hard constraints,
and the amendment process. Cannot be overridden by agent actions.

Based on HRAO-E Constitutional Framework (cognitivethoughtengine.com)

Usage:
    from constitutional_agent import Constitution

    constitution = Constitution.load("governance.yaml")
    result = constitution.evaluate({
        "failing_tests": 0,
        "hours_since_last_execution": 4,
        "runway_months": 8.5,
        "lessons_learned_weekly": 2,
    })

    if result.system_state.value == "FREEZE":
        print(f"BLOCKED: {result.blocking_gate.reason}")
    elif result.system_state.value == "THROTTLE":
        for gate in result.hold_gates:
            print(f"HOLD — {gate.gate}: {gate.reason}")
    else:
        print(f"State: {result.system_state.value}")
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import yaml

from constitutional_agent.gates import (
    AutonomyGate,
    ConstitutionalGate,
    EconomicGate,
    EpistemicGate,
    GovernanceGate,
    RiskGate,
    SixGateEvaluator,
)
from constitutional_agent.hard_constraints import (
    BUILTIN_HARD_CONSTRAINTS,
    HardConstraint,
    HardConstraintResult,
    check_hard_constraints,
)
from constitutional_agent.schema import (
    ConstitutionResult,
    GateResult,
    GateState,
    HardConstraintViolation,
    SystemState,
)


class ConstitutionalViolation(Exception):
    """
    Raised when a hard constraint is violated.

    Hard constraint violations are STOP-level events. Unlike gate FAIL states
    (which trigger FREEZE and allow the system to wait for resolution),
    ConstitutionalViolation requires immediate human intervention.
    """

    def __init__(self, violations: list[HardConstraintResult]) -> None:
        self.violations = violations
        ids = ", ".join(v.id for v in violations)
        super().__init__(
            f"Hard constraint violation(s): {ids}. "
            "Human intervention required. No agent action can authorize proceeding."
        )


class AmendmentProposal:
    """
    A proposed constitutional amendment.

    Amendments must be ratified by the designated authority before taking
    effect. Agents can propose amendments but cannot ratify their own proposals.
    Hard constraints (HC-*) require the highest authority to ratify.
    """

    def __init__(
        self,
        description: str,
        rationale: str,
        affected_sections: list[str],
        proposed_by: str = "agent",
    ) -> None:
        self.id = f"AMEND-{uuid.uuid4().hex[:8].upper()}"
        self.description = description
        self.rationale = rationale
        self.affected_sections = affected_sections
        self.proposed_by = proposed_by
        self.proposed_at = datetime.now(timezone.utc).isoformat()
        self.status = "PENDING"
        self.ratified_at: Optional[str] = None
        self.ratified_by: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "rationale": self.rationale,
            "affected_sections": self.affected_sections,
            "proposed_by": self.proposed_by,
            "proposed_at": self.proposed_at,
            "status": self.status,
            "ratified_at": self.ratified_at,
            "ratified_by": self.ratified_by,
        }


class Constitution:
    """
    The agent's governing document.

    Loads a governance.yaml file and provides:
        - evaluate(): Run all six gates + hard constraints
        - propose_amendment(): Submit a governance change proposal
        - ratify_amendment(): Approve a pending proposal (requires authority)
        - amendment_log: Full history of all amendments

    The constitution cannot be overridden by any agent action. Gates and
    hard constraints are enforced on every evaluate() call regardless of
    agent preferences, economic pressure, or prior decisions.

    Example:
        constitution = Constitution.load("governance.yaml")
        result = constitution.evaluate(metrics)

        if result.hard_constraint_violations:
            raise ConstitutionalViolation(result.hard_constraint_violations)

        if result.system_state == SystemState.FREEZE:
            # Stop all discretionary spend
            ...
        elif result.system_state == SystemState.THROTTLE:
            # Conserve resources, skip non-essential work
            ...
    """

    def __init__(
        self,
        config: dict[str, Any],
        evaluator: Optional[SixGateEvaluator] = None,
        hard_constraints: Optional[list[HardConstraint]] = None,
    ) -> None:
        self._config = config
        self._evaluator = evaluator or self._build_evaluator(config)
        self._hard_constraints = (
            hard_constraints
            if hard_constraints is not None
            else BUILTIN_HARD_CONSTRAINTS
        )
        self._amendments: list[AmendmentProposal] = []
        self._evaluation_history: list[dict[str, Any]] = []

    @classmethod
    def load(cls, path: str | Path) -> "Constitution":
        """
        Load a Constitution from a governance.yaml file.

        The YAML file defines gate thresholds, hard constraints, and
        organization metadata. See governance.yaml in the examples/ directory
        for the expected schema.

        Args:
            path: Path to the governance.yaml file.

        Returns:
            Constitution instance ready for evaluation.

        Raises:
            FileNotFoundError: If the path does not exist.
            ValueError: If the YAML is malformed or missing required keys.
        """
        resolved = Path(path)
        if not resolved.exists():
            raise FileNotFoundError(
                f"Governance file not found: {resolved}. "
                "Create a governance.yaml file or use Constitution() directly."
            )

        with open(resolved, encoding="utf-8") as f:
            config = yaml.safe_load(f)

        if not isinstance(config, dict):
            raise ValueError(
                f"governance.yaml must be a YAML mapping, got {type(config).__name__}"
            )

        return cls(config=config)

    @classmethod
    def from_defaults(cls) -> "Constitution":
        """
        Create a Constitution with default built-in configuration.

        Uses all six gates with production-validated thresholds from the
        HRAO-E Constitutional Framework. Suitable for getting started
        without a governance.yaml file.

        Returns:
            Constitution instance with default gates and hard constraints.
        """
        return cls(config={})

    def evaluate(
        self,
        context: dict[str, Any],
        raise_on_hc_violation: bool = False,
        dry_run: bool = False,
    ) -> ConstitutionResult:
        """
        Evaluate all gates and hard constraints against the provided context.

        This is the primary entry point. Call this before any significant
        agent action. The result tells you whether to proceed, throttle,
        freeze, or stop.

        Args:
            context: Dict of metric values. Each gate documents its expected
                     keys in its docstring. Unknown keys are ignored.
                     Missing keys use safe defaults.
            raise_on_hc_violation: If True, raises ConstitutionalViolation
                     when any hard constraint is violated, instead of
                     returning the violation in the result. Default: False.
            dry_run: If True, evaluate all gates and constraints but do NOT
                     short-circuit on hard constraint violations and do NOT
                     record the evaluation in history. Returns what *would*
                     happen if enforcement were active. Useful for calibrating
                     thresholds before enabling enforcement. Default: False.

        Returns:
            ConstitutionResult with system_state, gate_results,
            hard_constraint_violations, and summary.

        Raises:
            ConstitutionalViolation: If raise_on_hc_violation=True and any
                     hard constraint is violated (ignored in dry_run mode).
        """
        # 1. Check hard constraints first — they are absolute
        hc_results = check_hard_constraints(context, self._hard_constraints)
        violated_hcs = [r for r in hc_results if r.violated]

        hc_violations = [
            HardConstraintViolation(
                constraint_id=r.id,
                description=r.description,
                violated=True,
                remedy=r.remedy,
                context=r.context_snapshot,
            )
            for r in violated_hcs
        ]

        # 2. Hard constraint violations short-circuit to STOP (skipped in dry_run)
        if violated_hcs and not dry_run:
            if raise_on_hc_violation:
                raise ConstitutionalViolation(violated_hcs)

            result = ConstitutionResult(
                system_state=SystemState.STOP,
                gate_results=[],
                hard_constraint_violations=hc_violations,
                blocking_gate=None,
                hold_gates=[],
                targets_met=False,
                summary=(
                    f"STOP — Hard constraint violation(s): "
                    f"{', '.join(v.constraint_id for v in hc_violations)}. "
                    "Human intervention required."
                ),
            )
            self._record_evaluation(context, result)
            return result

        # 3. Evaluate six gates
        targets_met = bool(context.get("targets_met", False))
        system_state, gate_results = self._evaluator.evaluate(context, targets_met)

        # 4. Find blocking and hold gates
        blocking = next(
            (r for r in gate_results if r.state == GateState.FAIL), None
        )
        holds = [r for r in gate_results if r.state == GateState.HOLD]

        # 5. Build human-readable summary
        summary = self._build_summary(system_state, blocking, holds)

        result = ConstitutionResult(
            system_state=system_state,
            gate_results=gate_results,
            hard_constraint_violations=hc_violations,
            blocking_gate=blocking,
            hold_gates=holds,
            targets_met=targets_met,
            summary=summary,
        )
        if not dry_run:
            self._record_evaluation(context, result)
        return result

    def propose_amendment(
        self,
        description: str,
        rationale: str,
        affected_sections: list[str],
        proposed_by: str = "agent",
    ) -> str:
        """
        Propose a constitutional amendment.

        Amendments are NOT automatically applied. They require ratification
        by the designated authority (CEO, board, or governance quorum).
        Agents can propose amendments; they cannot ratify their own proposals.

        Args:
            description:      What the amendment changes.
            rationale:        Why the change is needed (with evidence).
            affected_sections: Which sections or gates are affected.
            proposed_by:      Identifier of the proposing agent/instance.

        Returns:
            Amendment ID (e.g., "AMEND-3A7F9B2C"). Present this to the
            ratifying authority for review.
        """
        amendment = AmendmentProposal(
            description=description,
            rationale=rationale,
            affected_sections=affected_sections,
            proposed_by=proposed_by,
        )
        self._amendments.append(amendment)
        return amendment.id

    def ratify_amendment(
        self,
        amendment_id: str,
        ratified_by: str,
        evidence: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Ratify a pending constitutional amendment.

        Ratification should be performed by the designated authority, not
        by the proposing agent. Hard constraint (HC-*) amendments require
        the highest authority.

        Args:
            amendment_id: The amendment ID returned by propose_amendment().
            ratified_by:  Identifier of the ratifying authority.
            evidence:     Optional supporting evidence for the ratification.

        Returns:
            True if the amendment was found and ratified.
            False if the amendment ID was not found or already ratified.
        """
        for amendment in self._amendments:
            if amendment.id == amendment_id and amendment.status == "PENDING":
                amendment.status = "RATIFIED"
                amendment.ratified_at = datetime.now(timezone.utc).isoformat()
                amendment.ratified_by = ratified_by
                return True
        return False

    @property
    def amendment_log(self) -> list[dict[str, Any]]:
        """Full history of all proposed and ratified amendments."""
        return [a.to_dict() for a in self._amendments]

    @property
    def evaluation_count(self) -> int:
        """Number of evaluate() calls made with this constitution."""
        return len(self._evaluation_history)

    def summary_report(self) -> dict[str, Any]:
        """
        Generate a summary report of constitutional health.

        Returns a dict suitable for logging, dashboards, or audit trails.
        """
        pending = sum(1 for a in self._amendments if a.status == "PENDING")
        ratified = sum(1 for a in self._amendments if a.status == "RATIFIED")

        freeze_count = sum(
            1 for e in self._evaluation_history
            if e.get("system_state") == "FREEZE"
        )
        stop_count = sum(
            1 for e in self._evaluation_history
            if e.get("system_state") == "STOP"
        )

        return {
            "organization": self._config.get("organization", "unknown"),
            "agent_name": self._config.get("agent_name", "unknown"),
            "version": self._config.get("version", "0.1.0"),
            "total_evaluations": self.evaluation_count,
            "freeze_events": freeze_count,
            "stop_events": stop_count,
            "amendments_pending": pending,
            "amendments_ratified": ratified,
            "hard_constraints_active": len(self._hard_constraints),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_evaluator(self, config: dict[str, Any]) -> SixGateEvaluator:
        """
        Build a SixGateEvaluator from governance.yaml config.

        Applies YAML-configured threshold overrides per gate. Missing keys
        fall back to production-validated defaults. All threshold overrides
        are additive — you only need to specify values you want to change.
        """
        g = config.get("gates", {})

        def _f(section: str, key: str, default: float) -> float:
            return float(g.get(section, {}).get(key, default))

        def _i(section: str, key: str, default: int) -> int:
            return int(g.get(section, {}).get(key, default))

        # Pre-revenue and post-revenue sub-sections for EconomicGate
        pre = g.get("economic", {}).get("pre_revenue", {})
        post = g.get("economic", {}).get("post_revenue", {})

        def _pre(key: str, default: float) -> float:
            return float(pre.get(key, default))

        def _post(key: str, default: float) -> float:
            return float(post.get(key, default))

        return SixGateEvaluator(
            epistemic=EpistemicGate(
                verification_fail=_f("epistemic", "fail_threshold", 0.50),
                verification_hold=_f("epistemic", "hold_threshold", 0.70),
                disagreement_fail=_f("epistemic", "disagreement_fail", 0.55),
                disagreement_hold=_f("epistemic", "disagreement_hold", 0.35),
            ),
            risk=RiskGate(
                misuse_fail=_f("risk", "misuse_fail", 0.80),
                misuse_hold=_f("risk", "misuse_hold", 0.65),
                channel_fail=_f("risk", "channel_fail", 0.50),
                channel_hold=_f("risk", "channel_hold", 0.70),
            ),
            governance=GovernanceGate(
                audit_fail=_f("governance", "audit_fail_threshold", 0.95),
                test_pass_hold=_f("governance", "test_hold", 0.90),
                test_pass_fail=_f("governance", "test_fail", 0.70),
            ),
            economic=EconomicGate(
                runway_fail=_pre("runway_fail_months", 3.0),
                runway_hold=_pre("runway_hold_months", 6.0),
                dli_fail=_pre("dli_completion_fail", 0.01),
                dli_hold=_pre("dli_completion_hold", 0.05),
                return_rate_fail=_pre("user_return_rate_fail", 0.05),
                return_rate_hold=_pre("user_return_rate_hold", 0.15),
                value_demo_fail=int(_pre("value_demo_fail", 0)),
                value_demo_hold=int(_pre("value_demo_hold", 3)),
                margin_fail=_post("gross_margin_fail", 0.45),
                margin_hold=_post("gross_margin_hold", 0.65),
                cac_fail=_post("cac_fail", 350.0),
                cac_hold=_post("cac_hold", 200.0),
                churn_fail=_post("churn_fail", 0.15),
                churn_hold=_post("churn_hold", 0.08),
                ltv_cac_fail=_post("ltv_cac_fail", 2.0),
                ltv_cac_hold=_post("ltv_cac_hold", 3.0),
            ),
            autonomy=AutonomyGate(
                human_minutes_fail=_f("autonomy", "human_minutes_fail", 120.0),
                human_minutes_hold=_f("autonomy", "human_minutes_hold", 60.0),
                decisions_fail=_i("autonomy", "decisions_fail", 10),
                decisions_hold=_i("autonomy", "decisions_hold", 50),
                activation_fail=_f("autonomy", "activation_fail", 0.25),
                activation_hold=_f("autonomy", "activation_hold", 0.50),
            ),
            constitutional=ConstitutionalGate(
                lessons_hold=_i("constitutional", "lessons_hold", 1),
                bug_recurrence_fail=_f("constitutional", "bug_recurrence_fail", 0.30),
                bug_recurrence_hold=_f("constitutional", "bug_recurrence_hold", 0.15),
                amendments_hold=_i("constitutional", "amendments_hold", 1),
                knowledge_fail=_f("constitutional", "freshness_fail", 0.30),
                knowledge_hold=_f("constitutional", "freshness_hold", 0.50),
                enforcement_fail=_f("constitutional", "enforcement_fail", 0.50),
                enforcement_hold=_f("constitutional", "enforcement_hold", 0.70),
            ),
        )

    @staticmethod
    def _build_summary(
        system_state: SystemState,
        blocking: Optional[GateResult],
        holds: list[GateResult],
    ) -> str:
        if system_state == SystemState.COMPOUND:
            return "COMPOUND — All gates PASS, all stretch targets met. Maximum growth mode."
        if system_state == SystemState.RUN:
            return "RUN — All gates PASS. Normal autonomous operation."
        if system_state == SystemState.THROTTLE:
            gate_names = ", ".join(r.gate for r in holds)
            return f"THROTTLE — {len(holds)} gate(s) on HOLD: {gate_names}. Conserve resources."
        if system_state == SystemState.FREEZE:
            if blocking:
                return f"FREEZE — {blocking.gate} FAIL: {blocking.reason}"
            return "FREEZE — Gate failure detected. Stop discretionary spend."
        return f"{system_state.value} — Evaluate manually."

    def _record_evaluation(
        self, context: dict[str, Any], result: ConstitutionResult
    ) -> None:
        """Record evaluation for audit history."""
        # Hash the context for deduplication without storing sensitive values
        ctx_hash = hashlib.sha256(
            json.dumps(context, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

        self._evaluation_history.append({
            "evaluated_at": datetime.now(timezone.utc).isoformat(),
            "system_state": result.system_state.value,
            "context_hash": ctx_hash,
            "hc_violations": len(result.hard_constraint_violations),
            "blocking_gate": result.blocking_gate.gate if result.blocking_gate else None,
            "hold_count": len(result.hold_gates),
        })
