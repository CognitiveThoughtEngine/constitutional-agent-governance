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

import copy
import hashlib
import json
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

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


class _DisabledGate:
    """
    Stub gate that always returns PASS.

    Used when a gate is disabled via ``enabled: false`` in governance.yaml.
    Disabled gates are treated as unconditionally healthy so they never
    block the system.  Disable gates only through formal governance — not
    as a workaround for noisy thresholds.
    """

    def __init__(self, name: str) -> None:
        self._name = name

    def evaluate(self, metrics: dict[str, Any]) -> GateResult:
        return GateResult(
            gate=self._name,
            state=GateState.PASS,
            reason="Disabled via governance.yaml",
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
        changes: Optional[dict[str, Any]] = None,
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
        self.changes: Optional[dict[str, Any]] = changes

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
            "changes": self.changes,
        }


# Known metric keys read by built-in gates (used by strict_mode).
# SYNC REQUIRED: when adding a new metric to any gate class in gates.py,
# add its context key here. Test: test_known_gate_metrics_coverage in test_gates.py.
_KNOWN_GATE_METRICS: frozenset[str] = frozenset({
    "uncertainty_disclosure_rate", "verification_pass_rate",
    "misuse_risk_index",
    "gaming_incidents_7d", "lessons_learned_weekly",
    "runway_months", "gross_margin", "burn_coverage",
    "agent_activation_rate", "decisions_per_day", "human_minutes_per_day",
    "sign_resolution_rate", "circuit_open_minutes_per_day",
    "failing_tests", "hours_since_last_execution",
})

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
        strict_mode: bool = False,
        on_evaluate: Optional[Callable[["ConstitutionResult"], None]] = None,
        on_amendment_ratified: Optional[Callable[[dict[str, Any]], None]] = None,
    ) -> None:
        self._config = config
        self._evaluator = evaluator or self._build_evaluator(config)
        # Start with builtins (or caller-supplied list), then append YAML-defined HCs
        self._hard_constraints = list(
            hard_constraints
            if hard_constraints is not None
            else BUILTIN_HARD_CONSTRAINTS
        )
        yaml_hcs = self._parse_yaml_hard_constraints(
            config.get("hard_constraints", [])
        )
        self._hard_constraints.extend(yaml_hcs)
        self._amendments: list[AmendmentProposal] = []
        self._evaluation_history: list[dict[str, Any]] = []
        self._strict_mode = strict_mode
        self._on_evaluate = on_evaluate
        self._on_amendment_ratified = on_amendment_ratified

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
        strict_mode: Optional[bool] = None,
    ) -> "ConstitutionResult":
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
            strict_mode: If True (or if the instance was created with
                     strict_mode=True), an empty context immediately returns
                     THROTTLE. Overrides the instance-level setting when
                     provided explicitly.

        Returns:
            ConstitutionResult with system_state, gate_results,
            hard_constraint_violations, and summary.

        Raises:
            ConstitutionalViolation: If raise_on_hc_violation=True and any
                     hard constraint is violated (ignored in dry_run mode).
        """
        # Resolve strict_mode: call-site param overrides instance default
        effective_strict = strict_mode if strict_mode is not None else self._strict_mode

        # 0. Strict mode: empty context immediately returns THROTTLE
        if effective_strict and not (set(context) & _KNOWN_GATE_METRICS):
            summary = (
                "THROTTLE — strict mode: empty context triggers HOLD — "
                "report metrics or disable strict_mode."
            )
            result = ConstitutionResult(
                system_state=SystemState.THROTTLE,
                gate_results=[],
                hard_constraint_violations=[],
                blocking_gate=None,
                blocking_gates=[],
                hold_gates=[],
                targets_met=False,
                summary=summary,
            )
            if not dry_run:
                self._record_evaluation(context, result)
            return result

        # 0b. Input validation — warn on out-of-range metric values
        self._validate_metrics(context)

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
                blocking_gates=[],
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
        all_blocking = [r for r in gate_results if r.state == GateState.FAIL]
        holds = [r for r in gate_results if r.state == GateState.HOLD]

        # 5. Build human-readable summary
        summary = self._build_summary(system_state, blocking, holds, all_blocking)

        result = ConstitutionResult(
            system_state=system_state,
            gate_results=gate_results,
            hard_constraint_violations=hc_violations,
            blocking_gate=blocking,
            blocking_gates=all_blocking,
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
        changes: Optional[dict[str, Any]] = None,
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
            changes:          Optional dict of config changes to apply on
                              ratification. Merged into the "gates" section.
                              Example: {"gates": {"economic": {"pre_revenue":
                                         {"runway_hold_months": 9.0}}}}

        Returns:
            Amendment ID (e.g., "AMEND-3A7F9B2C"). Present this to the
            ratifying authority for review.
        """
        amendment = AmendmentProposal(
            description=description,
            rationale=rationale,
            affected_sections=affected_sections,
            proposed_by=proposed_by,
            changes=changes,
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
                # Apply config changes before marking ratified so status stays
                # consistent with evaluator state on error.
                if amendment.changes:
                    config_backup = copy.deepcopy(self._config)
                    try:
                        self._deep_merge(self._config, amendment.changes)
                        self._evaluator = self._build_evaluator(self._config)
                    except Exception:
                        self._config = config_backup
                        raise
                # Mark ratified only after config changes succeed
                amendment.status = "RATIFIED"
                amendment.ratified_at = datetime.now(timezone.utc).isoformat()
                amendment.ratified_by = ratified_by
                if self._on_amendment_ratified is not None:
                    self._on_amendment_ratified(amendment.to_dict())
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


    def fria_evidence(
        self,
        result=None,
    ):
        """
        Generate Fundamental Rights Impact Assessment (FRIA) evidence.

        Maps constitutional gate results to the six categories required by
        EU AI Act Article 27 for high-risk AI systems.  Deployments subject
        to the Act MUST complete a FRIA before going live; this method
        produces structured evidence from live evaluation data that can be
        included directly in that assessment.

        Args:
            result: A ``ConstitutionResult`` from a prior ``evaluate()`` call.
                    If ``None``, uses the most recent evaluation stored in
                    ``None``.  If no evaluations have been run yet,
                    all categories are returned with status ``"GAP"``.

        Returns:
            A plain ``dict`` with the following top-level keys:

            * ``eu_ai_act_article`` -- always ``"Article 27"``
            * ``generated_at`` -- ISO-8601 UTC timestamp
            * ``system_state`` -- the system state at evaluation time
            * ``categories`` -- list of six FRIA category dicts
            * ``gaps`` -- list of category names with status ``"GAP"``
            * ``overall_covered`` -- ``True`` when no ``GAP`` entries remain

            Each category dict contains:

            * ``name`` -- human-readable category label
            * ``gate_source`` -- gate name(s) providing evidence
            * ``status`` -- ``"COVERED"`` | ``"PARTIAL"`` | ``"GAP"``
            * ``evidence`` -- list of human-readable evidence strings
            * ``gate_state`` -- raw gate state (``"PASS"`` / ``"HOLD"`` / ``"FAIL"`` / ``"N/A"``)
            * ``metric`` -- numeric metric value if available, else ``None``

        Example::

            result = constitution.evaluate(context)
            fria = constitution.fria_evidence(result)

            if not fria["overall_covered"]:
                print("Gaps:", fria["gaps"])

        Constitutional reference: Section 0.5 (citation mandate),
        Section 0.7 HC-1/4/11/12/15 (hard-constraint evidence).
        """
        from datetime import datetime, timezone
        from typing import Any

        # result is caller-supplied; if None, all categories report GAP

        gate_map = {}
        hc_violations = []
        state_str = "N/A"

        if result is not None:
            for gr in result.gate_results:
                gate_map[gr.gate] = gr
            hc_violations = result.hard_constraint_violations
            state_str = result.system_state.value

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

        def _gate_evidence(gate_name, fallback_gap):
            """Map a single gate result to FRIA status + evidence strings."""
            gr = gate_map.get(gate_name)
            if gr is None:
                return {
                    "gate_state": "N/A",
                    "metric": None,
                    "status": "GAP",
                    "evidence": [fallback_gap],
                }
            state_val = gr.state.value if hasattr(gr.state, "value") else str(gr.state)
            if state_val == "PASS":
                fria_status = "COVERED"
            elif state_val == "HOLD":
                fria_status = "PARTIAL"
            else:
                fria_status = "GAP"
            evidence_lines = [gr.reason] if gr.reason else [fallback_gap]
            return {
                "gate_state": state_val,
                "metric": gr.metric,
                "status": fria_status,
                "evidence": evidence_lines,
            }

        def _hc_evidence(hc_ids, gate_name, narrative):
            """Supplement gate evidence with HC violation status."""
            lines = [narrative]
            for hc_id in hc_ids:
                matched = [v for v in hc_violations if v.constraint_id == hc_id and v.violated]
                if matched:
                    lines.append(f"{hc_id} VIOLATED: {matched[0].description}")
                else:
                    lines.append(f"{hc_id} enforced ({gate_name})")
            return lines

        # ------------------------------------------------------------------
        # Build the six FRIA categories (EU AI Act Article 27)
        # ------------------------------------------------------------------

        safety_g = _gate_evidence(
            "RiskGate",
            "RiskGate not evaluated -- safety evidence unavailable",
        )
        safety_g["name"] = "Safety and robustness"
        safety_g["gate_source"] = "RiskGate + HC-1/7"
        safety_g["evidence"] = _hc_evidence(
            ["HC-1", "HC-7"],
            "RiskGate",
            safety_g["evidence"][0] if safety_g["evidence"] else "",
        )

        nondiscrim_g = _gate_evidence(
            "EpistemicGate",
            "EpistemicGate not evaluated -- bias evidence unavailable",
        )
        nondiscrim_g["name"] = "Non-discrimination and equal treatment"
        nondiscrim_g["gate_source"] = "EpistemicGate"

        oversight_g = _gate_evidence(
            "AutonomyGate",
            "AutonomyGate not evaluated -- human-oversight evidence unavailable",
        )
        oversight_g["name"] = "Human oversight and control"
        oversight_g["gate_source"] = "AutonomyGate + HC-12"
        oversight_g["evidence"] = _hc_evidence(
            ["HC-12"],
            "AutonomyGate",
            oversight_g["evidence"][0] if oversight_g["evidence"] else "",
        )

        privacy_g = _gate_evidence(
            "RiskGate",
            "RiskGate not evaluated -- privacy evidence unavailable",
        )
        privacy_g["name"] = "Privacy and data governance"
        privacy_g["gate_source"] = "RiskGate"

        transparency_g = _gate_evidence(
            "GovernanceGate",
            "GovernanceGate not evaluated -- transparency evidence unavailable",
        )
        transparency_g["name"] = "Transparency and explainability"
        transparency_g["gate_source"] = "GovernanceGate + HC-4/15"
        transparency_g["evidence"] = _hc_evidence(
            ["HC-4", "HC-15"],
            "GovernanceGate",
            transparency_g["evidence"][0] if transparency_g["evidence"] else "",
        )

        accountability_g = _gate_evidence(
            "GovernanceGate",
            "GovernanceGate not evaluated -- accountability evidence unavailable",
        )
        accountability_g["name"] = "Accountability and auditability"
        accountability_g["gate_source"] = "GovernanceGate + HC-11/12"
        accountability_g["evidence"] = _hc_evidence(
            ["HC-11", "HC-12"],
            "GovernanceGate",
            accountability_g["evidence"][0] if accountability_g["evidence"] else "",
        )

        categories = [
            safety_g,
            nondiscrim_g,
            oversight_g,
            privacy_g,
            transparency_g,
            accountability_g,
        ]

        gaps = [c["name"] for c in categories if c["status"] == "GAP"]

        return {
            "eu_ai_act_article": "Article 27",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "system_state": state_str,
            "categories": categories,
            "gaps": gaps,
            "overall_covered": len(gaps) == 0,
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

        Gates with ``enabled: false`` in the YAML are replaced with a
        _DisabledGate stub that always returns PASS, so they never block
        the system state machine.
        """
        g = config.get("gates", {})

        def _enabled(section: str) -> bool:
            return bool(g.get(section, {}).get("enabled", True))

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

        epistemic: Any = (
            _DisabledGate("EpistemicGate")
            if not _enabled("epistemic")
            else EpistemicGate(
                verification_fail=_f("epistemic", "fail_threshold", 0.50),
                verification_hold=_f("epistemic", "hold_threshold", 0.70),
                disagreement_fail=_f("epistemic", "disagreement_fail", 0.55),
                disagreement_hold=_f("epistemic", "disagreement_hold", 0.35),
            )
        )

        risk: Any = (
            _DisabledGate("RiskGate")
            if not _enabled("risk")
            else RiskGate(
                misuse_fail=_f("risk", "misuse_fail", 0.80),
                misuse_hold=_f("risk", "misuse_hold", 0.65),
                channel_fail=_f("risk", "channel_fail", 0.50),
                channel_hold=_f("risk", "channel_hold", 0.70),
            )
        )

        governance: Any = (
            _DisabledGate("GovernanceGate")
            if not _enabled("governance")
            else GovernanceGate(
                audit_fail=_f("governance", "audit_fail_threshold", 0.95),
                test_pass_hold=_f("governance", "test_hold", 0.90),
                test_pass_fail=_f("governance", "test_fail", 0.70),
            )
        )

        economic: Any = (
            _DisabledGate("EconomicGate")
            if not _enabled("economic")
            else EconomicGate(
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
            )
        )

        autonomy: Any = (
            _DisabledGate("AutonomyGate")
            if not _enabled("autonomy")
            else AutonomyGate(
                human_minutes_fail=_f("autonomy", "human_minutes_fail", 120.0),
                human_minutes_hold=_f("autonomy", "human_minutes_hold", 60.0),
                decisions_fail=_i("autonomy", "decisions_fail", 10),
                decisions_hold=_i("autonomy", "decisions_hold", 50),
                activation_fail=_f("autonomy", "activation_fail", 0.25),
                activation_hold=_f("autonomy", "activation_hold", 0.50),
            )
        )

        constitutional: Any = (
            _DisabledGate("ConstitutionalGate")
            if not _enabled("constitutional")
            else ConstitutionalGate(
                lessons_hold=_i("constitutional", "lessons_hold", 1),
                bug_recurrence_fail=_f("constitutional", "bug_recurrence_fail", 0.30),
                bug_recurrence_hold=_f("constitutional", "bug_recurrence_hold", 0.15),
                amendments_hold=_i("constitutional", "amendments_hold", 1),
                knowledge_fail=_f("constitutional", "freshness_fail", 0.30),
                knowledge_hold=_f("constitutional", "freshness_hold", 0.50),
                enforcement_fail=_f("constitutional", "enforcement_fail", 0.50),
                enforcement_hold=_f("constitutional", "enforcement_hold", 0.70),
            )
        )

        return SixGateEvaluator(
            epistemic=epistemic,
            risk=risk,
            governance=governance,
            economic=economic,
            autonomy=autonomy,
            constitutional=constitutional,
        )

    @staticmethod
    def _build_summary(
        system_state: SystemState,
        blocking: Optional[GateResult],
        holds: list[GateResult],
        all_blocking: Optional[list[GateResult]] = None,
    ) -> str:
        if system_state == SystemState.COMPOUND:
            return "COMPOUND — All gates PASS, all stretch targets met. Maximum growth mode."
        if system_state == SystemState.RUN:
            return "RUN — All gates PASS. Normal autonomous operation."
        if system_state == SystemState.THROTTLE:
            gate_names = ", ".join(r.gate for r in holds)
            return f"THROTTLE — {len(holds)} gate(s) on HOLD: {gate_names}. Conserve resources."
        if system_state == SystemState.FREEZE:
            if all_blocking and len(all_blocking) > 1:
                gate_names = ", ".join(r.gate for r in all_blocking)
                return (
                    f"FREEZE — {len(all_blocking)} gates FAIL: {gate_names}. "
                    "Stop discretionary spend."
                )
            if blocking:
                return f"FREEZE — {blocking.gate} FAIL: {blocking.reason}"
            return "FREEZE — Gate failure detected. Stop discretionary spend."
        return f"{system_state.value} — Evaluate manually."

    def _record_evaluation(
        self, context: dict[str, Any], result: "ConstitutionResult"
    ) -> None:
        """Record evaluation for audit history and call persistence hook if set."""
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

        if self._on_evaluate is not None:
            self._on_evaluate(result)

    @staticmethod
    def _parse_yaml_hard_constraints(hc_list: list[Any]) -> list[HardConstraint]:
        """
        Parse YAML-defined hard constraints into HardConstraint objects.

        Supports check_op values: eq, ne, lt, lte, gt, gte.
        The check function returns True when the constraint is VIOLATED.

        Args:
            hc_list: List of dicts from the "hard_constraints" YAML section.

        Returns:
            List of HardConstraint instances to append to builtins.
        """
        result: list[HardConstraint] = []
        for entry in hc_list:
            hc_id = entry.get("id", "HC-YAML-UNKNOWN")
            description = entry.get("description", "")
            check_key = entry.get("check_key", "")
            check_op = entry.get("check_op", "eq")
            check_value = entry.get("check_value")
            check_required = bool(entry.get("required", False))
            remedy = entry.get("remedy", "Review and resolve the constraint violation.")

            # Build the violation predicate based on the operator.
            # Violated = True means the constraint is broken.
            def _make_check(
                k: str, op: str, v: Any, req: bool
            ) -> Callable[[dict[str, Any]], bool]:
                def _check(ctx: dict[str, Any]) -> bool:
                    if k not in ctx:
                        return req  # Key absent → constraint not applicable
                    actual = ctx[k]
                    if op == "eq":
                        return bool(actual != v)
                    if op == "ne":
                        return bool(actual == v)
                    if op == "lt":
                        return float(actual) >= float(v)
                    if op == "lte":
                        return float(actual) > float(v)
                    if op == "gt":
                        return float(actual) <= float(v)
                    if op == "gte":
                        return float(actual) < float(v)
                    # Unknown op: fail-CLOSED
                    return True
                return _check

            result.append(
                HardConstraint(
                    id=hc_id,
                    description=description,
                    check=_make_check(check_key, check_op, check_value, check_required),
                    remedy=remedy,
                )
            )
        return result

    @staticmethod
    def _validate_metrics(context: dict[str, Any]) -> None:
        """
        Warn about out-of-range metric values before evaluation.

        Known 0-1 bounded metrics are checked for [0.0, 1.0] range.
        Known positive metrics are checked for non-negative values.
        Issues a UserWarning — does not raise.
        """
        bounded_01 = {
            "verification_pass_rate",
            "uncertainty_disclosure_rate",
            "misuse_risk_index",
            "channel_health",
            "audit_coverage",
            "test_pass_rate",
            "agent_activation_rate",
            "gross_margin",
            "churn_rate",
            "user_return_rate",
        }
        positive_metrics = {
            "runway_months",
            "decisions_per_day",
            "human_minutes_per_day",
        }

        for key, val in context.items():
            if key in bounded_01:
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    continue
                if fval < 0.0 or fval > 1.0:
                    warnings.warn(
                        f"Metric '{key}' value {val} is outside expected [0.0, 1.0] range. "
                        "Constitutional evaluation may be unreliable.",
                        UserWarning,
                        stacklevel=4,
                    )
            elif key in positive_metrics:
                try:
                    fval = float(val)
                except (TypeError, ValueError):
                    continue
                if fval < 0.0:
                    warnings.warn(
                        f"Metric '{key}' value {val} is negative, which is not expected. "
                        "Constitutional evaluation may be unreliable.",
                        UserWarning,
                        stacklevel=4,
                    )

    @staticmethod
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
        """
        Deep-merge `override` into `base` in-place.

        Nested dicts are merged recursively. Scalar values are overwritten.
        """
        for key, val in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                Constitution._deep_merge(base[key], val)
            else:
                base[key] = val
