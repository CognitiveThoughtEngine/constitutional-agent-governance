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
import threading
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
from constitutional_agent.authority import (
    AmendmentRecord,
    AmendmentStore,
    AuthorityLevel,
    AuthorityRegistry,
    IdentityVerifier,
    InMemoryAmendmentStore,
    canonical_principal,
    redact_secrets,
    scrub_evidence,
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


class ConstitutionIntegrityError(Exception):
    """
    Raised when the durable amendment ledger cannot be trusted for a safety-
    critical reconstruction — e.g. a *configured* store is unreadable, or a
    persisted RATIFIED record is internally inconsistent (a malformed version).

    Deliberately fail-CLOSED: rather than silently reset the monotonic version
    counter to 0 (which could reissue existing version numbers), the Constitution
    refuses to start until the ledger is repaired or replaced.
    """


class AmendmentProposal:
    """
    A proposed constitutional amendment.

    Amendments must be ratified by the designated authority before taking
    effect. Agents can propose amendments but cannot ratify their own proposals.
    Hard constraints (HC-*) and authority-registry changes require the highest
    authority (CONSTITUTIONAL_AUTHORITY) to ratify.

    ``proposed_by`` is the proposer's opaque, stable ``principal_id`` — not a
    display name. At ratification the constitution enforces that the ratifier is
    a *different* registered principal with sufficient authority for the ACTUAL
    configuration paths the change touches.
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
        # Populated once a ratify/reject decision is made (audit-grade record).
        self.decision: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "rationale": self.rationale,
            "affected_sections": self.affected_sections,
            # proposer_id is the canonical field; proposed_by kept for compat.
            "proposed_by": self.proposed_by,
            "proposer_id": self.proposed_by,
            "proposed_at": self.proposed_at,
            "status": self.status,
            "ratified_at": self.ratified_at,
            "ratified_by": self.ratified_by,
            "ratifier_id": self.ratified_by,
            "changes": self.changes,
            "decision": self.decision,
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

    Amendment authority (trust boundary):
        Ratification is *enforced*, not merely recorded. Configure an
        ``authority_registry`` (``principal_id -> authority level``) to require
        separation of duty and sufficient authority for each change. The library
        authorizes a *registered* principal according to constitutional policy;
        it does **not** prove the caller controls that identity. Supply an
        ``identity_verifier`` to bind the asserted principal to an external
        system (Entra / Okta / IAM / mTLS / a signed token). Without a registry
        the constitution runs in a legacy amendment mode: separation of duty is
        still enforced, but changes touching hard constraints or the registry are
        refused fail-closed.

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
        authority_registry: Optional[dict[str, Any] | AuthorityRegistry] = None,
        identity_verifier: Optional[IdentityVerifier] = None,
        amendment_store: Optional[AmendmentStore] = None,
    ) -> None:
        self._config = config
        self._evaluator = evaluator or self._build_evaluator(config)
        # Keep the base list separate so hard-constraint amendments can rebuild
        # the effective set (base builtins + YAML/amendment-defined layer).
        self._base_hard_constraints = list(
            hard_constraints
            if hard_constraints is not None
            else BUILTIN_HARD_CONSTRAINTS
        )
        self._hard_constraints = list(self._base_hard_constraints)
        yaml_hcs = self._parse_yaml_hard_constraints(
            config.get("hard_constraints", [])
        )
        self._hard_constraints.extend(yaml_hcs)
        self._amendments: list[AmendmentProposal] = []
        self._evaluation_history: list[dict[str, Any]] = []
        self._strict_mode = strict_mode
        self._on_evaluate = on_evaluate
        self._on_amendment_ratified = on_amendment_ratified

        # --- Amendment authority / separation of duties ---
        # The initial registry is trusted deployer-supplied config (the bootstrap
        # root of trust). After construction, changes to it flow through the same
        # amendment process and require CONSTITUTIONAL_AUTHORITY. If no registry
        # is configured, the constitution runs in a legacy (unauthenticated)
        # amendment mode — separation of duty is still enforced, but any change
        # touching hard constraints or the registry itself is refused fail-closed.
        reg_source: Optional[dict[str, Any] | AuthorityRegistry]
        reg_source = (
            authority_registry
            if authority_registry is not None
            else config.get("authority_registry")
        )
        if reg_source is None:
            self._authority: Optional[AuthorityRegistry] = None
        elif isinstance(reg_source, AuthorityRegistry):
            self._authority = reg_source
        else:
            self._authority = AuthorityRegistry(reg_source)

        self._identity_verifier = identity_verifier
        self._amendment_store: AmendmentStore = (
            amendment_store if amendment_store is not None else InMemoryAmendmentStore()
        )
        # Restore the monotonic version from the durable store so it survives a
        # process restart (a fresh InMemoryAmendmentStore yields 0). Without this
        # a restarted process would reset to 0 and re-mint versions that collide
        # with already-persisted records.
        self._constitution_version = self._reconstruct_version()
        # Serializes ratification so the check-then-apply of the last-authority
        # guard (and version bump) is atomic under concurrent ratifiers WITHIN
        # ONE Constitution instance in ONE process. Without it, two interleaved
        # ratifiers could each pass a guard evaluated against a stale registry
        # and together strand the system with zero root authorities. Reentrant so
        # nested internal calls do not deadlock. NOTE: this lock is instance-
        # local — it does NOT coordinate multiple Constitution instances or
        # multiple processes sharing one durable store. Cross-process ratification
        # requires a durable compare-and-swap / transaction in the store and is
        # the deployer's responsibility (out of scope for this library).
        self._ratify_lock = threading.RLock()

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

        Uses all six gates with reference defaults derived from HRAO-E;
        deployment validation required. Suitable for getting started
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
        *,
        asserted_identity: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Ratify a pending constitutional amendment, enforcing the authority
        protocol (separation of duty + authority levels + last-authority guard).

        **BREAKING (0.7.0):** ratification is now *enforced*, not merely recorded.
        A call that violates separation of duty, is made by an unregistered or
        under-privileged ratifier, or would strand the system with zero root
        authorities now returns ``False`` and records a REJECTED decision — where
        earlier versions recorded the string and returned ``True`` unconditionally.

        Enforcement (all fail-closed):
          - the ratifier's ``principal_id`` must differ from the proposer's
            (separation of duty) — enforced even with no registry configured;
          - the ratifier must be present in the authority registry;
          - ordinary amendments require ``RATIFIER`` or higher;
          - any change touching **hard constraints or the authority registry**
            requires ``CONSTITUTIONAL_AUTHORITY``. The required level is derived
            from the ACTUAL affected configuration paths, not from the proposer's
            ``affected_sections`` label;
          - a registry change may not remove or demote the final
            ``CONSTITUTIONAL_AUTHORITY`` (the system is never left with zero root
            authorities);
          - if an identity-verification callback is configured, it must
            authenticate the asserted ratifier; a callback that returns ``False``
            or raises rejects the ratification.

        **Trust boundary.** The library authorizes a *registered* principal per
        constitutional policy. It does **not** prove the caller controls that
        identity. Supply ``identity_verifier`` (see ``Constitution.__init__``) to
        bind the asserted principal to Entra / Okta / IAM / mTLS / a signed token.

        **Concurrency scope.** The atomicity and last-authority guarantees are
        **instance-local**: they hold across concurrent ratifiers sharing a
        single Constitution instance within one process. They do NOT protect
        multiple Constitution instances or multiple processes sharing one durable
        store — cross-process ratification requires a durable compare-and-swap /
        transaction in the store and is the deployer's responsibility.

        Args:
            amendment_id:      ID returned by ``propose_amendment()``.
            ratified_by:       The ratifier's opaque, stable ``principal_id``.
            evidence:          Optional supporting evidence. Retained scrubbed +
                               by SHA-256 hash; secrets/tokens are never stored.
            asserted_identity: Optional claims/token passed to the identity
                               verifier. Never stored (only the pass/fail result
                               and verifier name are recorded).

        Returns:
            True if ratified; False if not found, already decided, or rejected by
            the authority protocol. On rejection the reason is recorded in the
            amendment's ``decision`` (see ``amendment_log`` / ``amendment_records``).
        """
        with self._ratify_lock:
            return self._ratify_locked(
                amendment_id,
                ratified_by,
                evidence,
                asserted_identity=asserted_identity,
            )

    def _ratify_locked(
        self,
        amendment_id: str,
        ratified_by: str,
        evidence: Optional[dict[str, Any]] = None,
        *,
        asserted_identity: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Ratification body, executed while holding ``_ratify_lock``.

        Serialization makes the last-authority guard's check-then-apply atomic:
        the registry it simulates against is the one it will actually mutate, so
        interleaved ratifiers cannot together drop the system below one root
        authority.

        **Scope: instance-local.** ``_ratify_lock`` only serializes ratifiers
        that share THIS Constitution instance in THIS process. It does not
        coordinate separate Constitution instances or separate processes sharing
        one durable store — for that, the deployer must provide a durable
        compare-and-swap / transaction in the store (out of scope here).
        """
        amendment = next(
            (a for a in self._amendments
             if a.id == amendment_id and a.status == "PENDING"),
            None,
        )
        if amendment is None:
            return False

        proposer_id = amendment.proposed_by
        ratifier_id = ratified_by
        hash_before = self._constitution_hash()
        affected_paths = self._affected_paths(amendment.changes)
        required = self._required_authority(affected_paths)
        legacy = self._authority is None

        proposer_level = (
            self._authority.level_of(proposer_id) if self._authority else None
        )
        ratifier_level = (
            self._authority.level_of(ratifier_id) if self._authority else None
        )

        # --- Authorization checks (fail-closed) -----------------------------
        reject: Optional[str] = None

        # 1. Separation of duty — always enforced, even in legacy mode. Compared
        #    on the canonical principal id so whitespace/case variants of the same
        #    identity cannot slip past the proposer != ratifier rule.
        if canonical_principal(proposer_id) == canonical_principal(ratifier_id):
            reject = (
                f"Separation of duty: proposer and ratifier must be distinct "
                f"principals (both resolve to '{canonical_principal(ratifier_id)}'). "
                "A proposer cannot ratify their own amendment."
            )
        elif legacy:
            # 2. Legacy mode: no registry to verify root authority against. Root
            #    governance changes cannot be authorized — refuse fail-closed.
            if required >= AuthorityLevel.CONSTITUTIONAL_AUTHORITY:
                reject = (
                    "Change touches hard constraints or the authority registry "
                    f"(paths: {', '.join(affected_paths) or '<root>'}), which "
                    "requires CONSTITUTIONAL_AUTHORITY, but no authority registry "
                    "is configured. Configure authority_registry to authorize "
                    "root governance changes."
                )
        else:
            assert self._authority is not None  # narrow for type-checkers
            # 3. Ratifier must be registered.
            if ratifier_level is None:
                reject = (
                    f"Ratifier '{ratifier_id}' is not in the authority registry. "
                    "Only registered principals may ratify."
                )
            # 4. Authority level sufficient for the ACTUAL affected paths.
            elif ratifier_level < required:
                reject = (
                    f"Insufficient authority: ratifying a change to "
                    f"{', '.join(affected_paths) or '<config>'} requires "
                    f"{required.name}, but '{ratifier_id}' holds "
                    f"{ratifier_level.name}."
                )
            # 5. Registry changes may not strand the system without a root.
            elif self._touches_registry(affected_paths):
                simulated = self._authority.with_changes(
                    amendment.changes.get("authority_registry", {})  # type: ignore[union-attr]
                )
                if simulated.root_count() < 1:
                    reject = (
                        "Registry change would remove or demote the final "
                        "CONSTITUTIONAL_AUTHORITY, leaving the system with zero "
                        "root authorities. Refused — the constitution must always "
                        "retain at least one root authority."
                    )

        # 6. Identity verification callback (only reached if policy passed).
        identity_assurance = "caller_asserted"
        identity_verifier_name: Optional[str] = None
        if reject is None and self._identity_verifier is not None:
            try:
                raw = self._identity_verifier.verify(ratifier_id, asserted_identity)
                # Strict: only an explicit boolean True authenticates. A malformed
                # response (None, a truthy non-bool, a dict, a numeric 1, a string)
                # fails closed rather than being coerced to a pass.
                verified = raw is True
            except Exception:
                # Fail-closed when the verifier RAISES (including a TimeoutError
                # it raises itself). NOTE: this cannot interrupt a callback that
                # blocks/hangs — Python cannot preempt a running call. A verifier
                # that may block must enforce its own wall-clock timeout (see
                # authority.bounded_verifier, best-effort).
                verified = False
            if verified:
                identity_assurance = "externally_verified"
                identity_verifier_name = self._identity_verifier.name
            else:
                reject = (
                    f"Identity verification failed for ratifier '{ratifier_id}' "
                    f"(verifier '{self._identity_verifier.name}'). The asserted "
                    "principal could not be authenticated."
                )

        scrubbed_evidence, evidence_hash = scrub_evidence(evidence)

        # --- Rejection path -------------------------------------------------
        if reject is not None:
            # PENDING -> REJECTED is terminal, but the transition is only durable
            # once the decision record is persisted. Mirror the ratified path's
            # atomic-rollback discipline: if _finalize_amendment (the ledger write)
            # raises, undo the in-memory terminal transition so the proposal stays
            # PENDING for a later retry. A rejected proposal must never be terminal
            # in memory with no durable decision record. (Nothing governing changes
            # on rejection, so only the amendment lifecycle fields need restoring.)
            prior_status = amendment.status
            prior_decision = amendment.decision
            amendment.status = "REJECTED"
            try:
                self._finalize_amendment(
                    amendment,
                    outcome="REJECTED",
                    ratifier_id=ratifier_id,
                    proposer_level=proposer_level,
                    ratifier_level=ratifier_level,
                    required=required,
                    affected_paths=affected_paths,
                    identity_assurance=identity_assurance,
                    identity_verifier_name=identity_verifier_name,
                    scrubbed_evidence=scrubbed_evidence,
                    evidence_hash=evidence_hash,
                    hash_before=hash_before,
                    hash_after=hash_before,  # nothing changed
                    version=self._constitution_version,
                    reason=reject,
                )
            except Exception:
                amendment.status = prior_status
                amendment.decision = prior_decision
                raise
            return False

        # --- Apply changes AND persist the ledger record atomically ---------
        # Capture the exact governing state and version BEFORE any mutation. If
        # applying the change OR writing the durable ledger record raises, we
        # restore the system to precisely its pre-ratify state: no live
        # governance change is ever left without durable evidence, and no
        # half-applied change survives a store-write failure. Net: a failed
        # ratify leaves the system exactly as it was before the call.
        prior_version = self._constitution_version
        backup = self._snapshot_state()
        try:
            if amendment.changes:
                self._apply_amendment_changes(amendment.changes)

            # Bump monotonic version only after changes succeed.
            self._constitution_version += 1
            amendment.status = "RATIFIED"
            amendment.ratified_at = datetime.now(timezone.utc).isoformat()
            amendment.ratified_by = ratifier_id
            hash_after = self._constitution_hash()

            self._finalize_amendment(
                amendment,
                outcome="RATIFIED",
                ratifier_id=ratifier_id,
                proposer_level=proposer_level,
                ratifier_level=ratifier_level,
                required=required,
                affected_paths=affected_paths,
                identity_assurance=identity_assurance,
                identity_verifier_name=identity_verifier_name,
                scrubbed_evidence=scrubbed_evidence,
                evidence_hash=evidence_hash,
                hash_before=hash_before,
                hash_after=hash_after,
                version=self._constitution_version,
                reason=(
                    f"Ratified by '{ratifier_id}' "
                    f"({ratifier_level.name if ratifier_level else 'unregistered'}); "
                    f"required {required.name}; identity {identity_assurance}."
                ),
            )
        except Exception:
            # Roll back state, version, and the amendment lifecycle fields so a
            # ledger-write (or apply) failure is fully undone and the proposal
            # stays PENDING for a later retry.
            self._restore_state(backup)
            self._constitution_version = prior_version
            amendment.status = "PENDING"
            amendment.ratified_at = None
            amendment.ratified_by = None
            amendment.decision = None
            raise

        if self._on_amendment_ratified is not None:
            self._on_amendment_ratified(amendment.to_dict())
        return True

    @property
    def amendment_log(self) -> list[dict[str, Any]]:
        """Full history of all proposed amendments (with their decision record)."""
        return [a.to_dict() for a in self._amendments]

    @property
    def amendment_records(self) -> list[dict[str, Any]]:
        """
        Durable, audit-grade decision records (RATIFIED and REJECTED), oldest
        first. Sourced from the pluggable amendment store, so this survives
        process restarts when a durable store (e.g. ``SqliteAmendmentStore``) is
        configured.
        """
        return self._amendment_store.all()

    def _reconstruct_version(self) -> int:
        """
        Reconstruct the monotonic version from the durable amendment store.

        Returns the maximum ``constitution_version`` across all persisted
        RATIFIED records. An empty / never-written store legitimately yields 0
        (a fresh constitution starts at version 0), so the version survives a
        process restart when a durable store is configured: a new Constitution
        built on the same store resumes where the last one left off.

        This is fail-CLOSED for integrity, NOT fail-open. If a *configured* store
        is unreadable, or a persisted RATIFIED record carries a malformed
        ``constitution_version``, this raises :class:`ConstitutionIntegrityError`
        rather than reset the counter to 0 — resetting could reissue an existing
        version number. A corrupt/unreadable ledger must stop startup until it is
        repaired or replaced.

        NOTE: this restores ONLY the monotonic version counter. It does NOT
        restore the governing configuration, authority registry, hard
        constraints, or pending proposals — those must be reloaded from their own
        source and verified against the last ``constitution_hash_after``.
        """
        try:
            records = self._amendment_store.all()
        except Exception as exc:
            raise ConstitutionIntegrityError(
                "Amendment store is configured but unreadable; refusing to reset "
                "the monotonic version counter to 0 (that would risk reissuing "
                "existing version numbers). Repair or replace the store first."
            ) from exc
        best = 0
        for rec in records or []:
            if str(rec.get("outcome", "")).upper() != "RATIFIED":
                continue
            raw: Any = rec.get("constitution_version")
            try:
                v = int(raw)
            except (TypeError, ValueError) as exc:
                raise ConstitutionIntegrityError(
                    f"RATIFIED amendment record "
                    f"{rec.get('amendment_id', '<unknown>')!r} has a malformed "
                    f"constitution_version ({raw!r}); the durable ledger is "
                    "internally inconsistent. Refusing to reconstruct the version "
                    "counter from a corrupt record."
                ) from exc
            if v > best:
                best = v
        return best

    @property
    def constitution_version(self) -> int:
        """Monotonic version, incremented on each successful ratification.

        Restored from the durable amendment store at construction (the max
        version across persisted RATIFIED records), so it survives process
        restarts when a durable store (e.g. ``SqliteAmendmentStore``) is
        configured; with the default in-memory store it starts at 0.

        Restart recovery restores ONLY this monotonic counter — NOT the governing
        configuration, authority registry, hard constraints, or pending
        proposals. Deployers must reload that governed state from its own source
        and verify it against the last record's ``constitution_hash_after``; do
        not assume the amendment store recovers the full constitution.
        """
        return self._constitution_version

    @property
    def authority_registry(self) -> Optional[dict[str, int]]:
        """Current authority registry snapshot, or None in legacy mode."""
        return self._authority.snapshot() if self._authority else None

    @property
    def evaluation_count(self) -> int:
        """Number of evaluate() calls made with this constitution."""
        return len(self._evaluation_history)

    # ------------------------------------------------------------------
    # Amendment authority helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _affected_paths(changes: Optional[dict[str, Any]]) -> list[str]:
        """
        Derive the dotted configuration paths a change payload actually touches.

        This is the ground truth used to decide the required authority — the
        proposer's ``affected_sections`` label is descriptive only and is never
        trusted for authorization.
        """
        if not changes:
            return []
        paths: list[str] = []

        def _walk(prefix: str, obj: Any) -> None:
            if isinstance(obj, dict) and obj:
                for key, val in obj.items():
                    child = f"{prefix}.{key}" if prefix else str(key)
                    _walk(child, val)
            else:
                # Leaf (scalar, list, or empty dict) — record the path.
                if prefix:
                    paths.append(prefix)

        _walk("", changes)
        return sorted(set(paths))

    @staticmethod
    def _touches_registry(affected_paths: list[str]) -> bool:
        return any(p.split(".")[0] == "authority_registry" for p in affected_paths)

    @staticmethod
    def _touches_hard_constraints(affected_paths: list[str]) -> bool:
        return any(p.split(".")[0] == "hard_constraints" for p in affected_paths)

    @classmethod
    def _required_authority(cls, affected_paths: list[str]) -> AuthorityLevel:
        """
        The minimum authority required to ratify a change to these paths.

        Hard-constraint or authority-registry changes require the highest level;
        everything else is an ordinary amendment.
        """
        if cls._touches_hard_constraints(affected_paths) or cls._touches_registry(
            affected_paths
        ):
            return AuthorityLevel.CONSTITUTIONAL_AUTHORITY
        return AuthorityLevel.RATIFIER

    def _constitution_hash(self) -> str:
        """
        Content hash of the governing configuration (excludes the monotonic
        version, so a document-only amendment leaves the hash unchanged while a
        real config change alters it).
        """
        snapshot = {
            "config": {
                k: v for k, v in self._config.items() if k != "authority_registry"
            },
            "hard_constraints": sorted(hc.id for hc in self._hard_constraints),
            "authority_registry": (
                self._authority.snapshot() if self._authority else None
            ),
        }
        payload = json.dumps(snapshot, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]

    def _snapshot_state(self) -> dict[str, Any]:
        """Capture mutable governing state for atomic rollback."""
        return {
            "config": copy.deepcopy(self._config),
            "hard_constraints": list(self._hard_constraints),
            "authority": self._authority,
            "evaluator": self._evaluator,
        }

    def _restore_state(self, backup: dict[str, Any]) -> None:
        self._config = backup["config"]
        self._hard_constraints = backup["hard_constraints"]
        self._authority = backup["authority"]
        self._evaluator = backup["evaluator"]

    def _apply_amendment_changes(self, changes: dict[str, Any]) -> None:
        """
        Apply a ratified change payload to the live constitution.

        Authority-registry and hard-constraint sections are applied through their
        dedicated paths; all other keys deep-merge into the config and rebuild the
        evaluator.
        """
        registry_change = changes.get("authority_registry")
        hc_change = changes.get("hard_constraints")
        other = {
            k: v
            for k, v in changes.items()
            if k not in ("authority_registry", "hard_constraints")
        }

        if other:
            self._deep_merge(self._config, other)
            self._evaluator = self._build_evaluator(self._config)

        if hc_change is not None:
            # Replace the YAML/amendment-defined layer; builtins always remain.
            self._config["hard_constraints"] = hc_change
            self._hard_constraints = list(self._base_hard_constraints)
            self._hard_constraints.extend(
                self._parse_yaml_hard_constraints(hc_change)
            )

        if registry_change is not None:
            base = self._authority or AuthorityRegistry({})
            self._authority = base.with_changes(registry_change)

    def _finalize_amendment(
        self,
        amendment: AmendmentProposal,
        *,
        outcome: str,
        ratifier_id: str,
        proposer_level: Optional[AuthorityLevel],
        ratifier_level: Optional[AuthorityLevel],
        required: AuthorityLevel,
        affected_paths: list[str],
        identity_assurance: str,
        identity_verifier_name: Optional[str],
        scrubbed_evidence: Optional[dict[str, Any]],
        evidence_hash: Optional[str],
        hash_before: str,
        hash_after: str,
        version: int,
        reason: str,
    ) -> None:
        """Build the durable AmendmentRecord, attach it, and persist it."""
        record = AmendmentRecord(
            amendment_id=amendment.id,
            outcome=outcome,
            proposer_id=amendment.proposed_by,
            ratifier_id=ratifier_id,
            proposer_level=proposer_level.name if proposer_level else None,
            ratifier_level=ratifier_level.name if ratifier_level else None,
            required_authority=required.name,
            identity_assurance=identity_assurance,
            identity_verifier=identity_verifier_name,
            affected_paths=affected_paths,
            proposed_at=amendment.proposed_at,
            decided_at=datetime.now(timezone.utc).isoformat(),
            evidence=scrubbed_evidence,
            evidence_hash=evidence_hash,
            constitution_hash_before=hash_before,
            constitution_hash_after=hash_after,
            constitution_version=version,
            reason=reason,
            description=amendment.description,
            # Redact secret-shaped values from the STORED/audit copy of the
            # change payload. The live ``amendment.changes`` used by
            # ``_apply_amendment_changes`` is left intact — only this durable
            # record (and ``amendment.decision``) is redacted, so credentials
            # embedded in a config change never persist to the ledger.
            changes=redact_secrets(amendment.changes),
        )
        amendment.decision = record.to_dict()
        self._amendment_store.record(record.to_dict())

    def _fria_inputs(
        self, context: dict[str, Any]
    ) -> tuple[list[GateResult], list[dict[str, Any]]]:
        """Evaluate gates + hard constraints and shape them for FRIA generation."""
        targets_met = bool(context.get("targets_met", False))
        _, gate_results = self._evaluator.evaluate(context, targets_met)
        hc_results = check_hard_constraints(context, self._hard_constraints)
        hc_violations = [
            {"constraint_id": r.id, "description": r.description, "violated": True}
            for r in hc_results if r.violated
        ]
        return gate_results, hc_violations

    def fria_evidence(self, context: dict[str, Any]) -> "list[Any]":
        """Generate the internal governance-evidence categories from an evaluation.

        Evaluates all gates and hard constraints against the provided context,
        then maps results to the framework's six *internal governance-evidence
        categories* — these are NOT the EU AI Act Article 27 categories. For the
        actual Article 27(1) crosswalk (which honestly separates auto-derived
        evidence from required deployer context) use
        :meth:`fria_support_package`.

        Args:
            context: Dict of metric values (same as evaluate()).

        Returns:
            List of FRIAEvidence, one per internal category (always 6).
        """
        from constitutional_agent.fria import generate_fria_evidence

        gate_results, hc_violations = self._fria_inputs(context)
        return generate_fria_evidence(gate_results, hc_violations)

    def fria_support_package(
        self,
        context: dict[str, Any],
        deployer_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Generate a FRIA-support package (NOT a complete Article 27 FRIA).

        Combines the internal governance-evidence categories with the EU AI Act
        Article 27(1) crosswalk. Operational gate evidence is auto-derived where
        it legitimately can be; elements that require deployer context (intended
        use, duration/frequency, affected groups, complaint arrangements) are
        marked as such rather than silently populated.

        Args:
            context:          Metric values (same as evaluate()).
            deployer_context: Optional Article 27(1) deployer-supplied context and
                              legal-review status (see
                              ``fria.generate_article27_crosswalk``).

        Returns:
            The structured FRIA-support package dict.
        """
        from constitutional_agent.fria import fria_support_package

        gate_results, hc_violations = self._fria_inputs(context)
        return fria_support_package(gate_results, hc_violations, deployer_context)

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
        fall back to reference defaults derived from HRAO-E (deployment
        validation required). All threshold overrides are additive — you only
        need to specify values you want to change.

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
