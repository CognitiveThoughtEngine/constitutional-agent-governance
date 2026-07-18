"""
FRIA-support evidence generation.

EU AI Act Article 27 requires a Fundamental Rights Impact Assessment (FRIA)
before certain deployers put a high-risk AI system into use. **This module does
not produce a complete or legally sufficient Article 27 FRIA.** It produces a
*FRIA-support package*: operational governance evidence that a human author (with
deployer context and legal review) can fold into a real FRIA.

Two distinct artifacts:

1. **Internal governance-evidence categories** (:class:`GovernanceEvidenceCategory`)
   — the library's own six evidence buckets, derived from gate and hard-constraint
   results. These are *not* the Article 27 categories; they are internal groupings
   of the operational evidence the framework can measure.

2. **EU AI Act Article 27(1) crosswalk** (:class:`Article27Element`) — the ACTUAL
   elements Article 27(1) enumerates. For each, the crosswalk states honestly
   whether the evidence is *auto-derived operational evidence*, *required
   deployer-supplied context*, or *missing/unverified*, plus a legal-review
   status. Operational gate telemetry cannot, on its own, establish the deployment
   process and intended use, the duration and frequency of use, the categories of
   affected people, or the complaint arrangements — those require deployer input.

Usage:
    from constitutional_agent.fria import (
        generate_fria_evidence, fria_summary,       # internal evidence buckets
        generate_article27_crosswalk, fria_support_package,  # Article 27(1) crosswalk
    )

    evidence   = generate_fria_evidence(gate_results, hc_violations)
    crosswalk  = generate_article27_crosswalk(gate_results, hc_violations, deployer_context)
    package    = fria_support_package(gate_results, hc_violations, deployer_context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from constitutional_agent.schema import GateResult, GateState


class GovernanceEvidenceCategory(Enum):
    """
    Internal governance-evidence categories.

    These are the framework's OWN groupings of operational evidence — not the
    EU AI Act Article 27 categories. Use :class:`Article27Element` for the actual
    Article 27(1) crosswalk.
    """
    SAFETY = "safety"
    NON_DISCRIMINATION = "non_discrimination"
    PRIVACY = "privacy"
    HUMAN_OVERSIGHT = "human_oversight"
    TRANSPARENCY = "transparency"
    ACCOUNTABILITY = "accountability"


# Backwards-compatible alias. NOTE: these were previously mislabelled as "the six
# Article 27 categories" — they are not. Retained under the old name so existing
# imports keep working; prefer ``GovernanceEvidenceCategory`` in new code.
FRIACategory = GovernanceEvidenceCategory


@dataclass
class FRIAEvidence:
    """Evidence for a single internal governance-evidence category."""
    category: GovernanceEvidenceCategory
    description: str
    gate_results: list[dict[str, Any]] = field(default_factory=list)
    hc_results: list[dict[str, Any]] = field(default_factory=list)
    status: str = "gap"  # "covered", "partial", "gap", "flagged"
    narrative: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category.value,
            "description": self.description,
            "status": self.status,
            "narrative": self.narrative,
            "gate_results": self.gate_results,
            "hc_results": self.hc_results,
            "recommendations": self.recommendations,
        }


# Mapping from internal governance-evidence categories to gates and hard constraints
FRIA_MAPPING: dict[GovernanceEvidenceCategory, dict[str, Any]] = {
    GovernanceEvidenceCategory.SAFETY: {
        "description": "Operational evidence bearing on safety and physical integrity",
        "gates": ["RiskGate"],
        "gate_metrics": ["misuse_risk_index", "security_critical_events"],
        "hard_constraints": ["HC-5", "HC-9"],
        "pass_condition": "RiskGate PASS and no HC-5/HC-9 violations",
    },
    GovernanceEvidenceCategory.NON_DISCRIMINATION: {
        "description": "Operational evidence bearing on non-discrimination and equality",
        "gates": ["EpistemicGate"],
        "gate_metrics": ["verification_pass_rate"],
        "hard_constraints": ["HC-4"],
        "pass_condition": "EpistemicGate PASS and no HC-4 violations",
    },
    GovernanceEvidenceCategory.PRIVACY: {
        "description": "Operational evidence bearing on privacy and data protection",
        "gates": ["RiskGate"],
        "gate_metrics": ["misuse_risk_index"],
        "hard_constraints": ["HC-6"],
        "pass_condition": "RiskGate PASS with low misuse_risk_index",
    },
    GovernanceEvidenceCategory.HUMAN_OVERSIGHT: {
        "description": "Operational evidence bearing on human oversight and agency",
        "gates": ["AutonomyGate"],
        "gate_metrics": ["human_minutes_per_day", "decisions_per_day", "agent_activation_rate"],
        "hard_constraints": ["HC-12"],
        "pass_condition": "AutonomyGate PASS and no HC-12 violations",
    },
    GovernanceEvidenceCategory.TRANSPARENCY: {
        "description": "Operational evidence bearing on transparency and explainability",
        "gates": ["GovernanceGate"],
        "gate_metrics": ["audit_coverage"],
        "hard_constraints": ["HC-4", "HC-11"],
        "pass_condition": "GovernanceGate PASS with audit_coverage >= 0.95",
    },
    GovernanceEvidenceCategory.ACCOUNTABILITY: {
        "description": "Operational evidence bearing on accountability and redress",
        "gates": ["GovernanceGate"],
        "gate_metrics": ["control_bypass_attempts"],
        "hard_constraints": ["HC-11"],
        "pass_condition": "GovernanceGate PASS with zero control_bypass_attempts",
    },
}


def generate_fria_evidence(
    gate_results: list[GateResult],
    hc_violations: list[dict[str, Any]],
) -> list[FRIAEvidence]:
    """Generate internal governance evidence from gate and hard-constraint results.

    These are the framework's own six evidence categories — NOT the Article 27
    categories. For the Article 27(1) crosswalk see
    :func:`generate_article27_crosswalk`.

    Args:
        gate_results: List of GateResult from constitution.evaluate()
        hc_violations: List of HC violation dicts (with 'constraint_id' key)

    Returns:
        List of FRIAEvidence, one per internal category (always 6).
    """
    # Index gate results by gate name
    gate_index: dict[str, GateResult] = {}
    for gr in gate_results:
        gate_index[gr.gate] = gr

    # Index HC violations by ID
    violated_hcs: set[str] = set()
    for v in hc_violations:
        cid = v.get("constraint_id", v.get("id", ""))
        if cid:
            violated_hcs.add(cid)

    evidence_list: list[FRIAEvidence] = []

    for category, mapping in FRIA_MAPPING.items():
        ev = FRIAEvidence(
            category=category,
            description=mapping["description"],
        )

        # Collect relevant gate results
        has_gate_data = False
        gate_passing = True
        for gate_name in mapping["gates"]:
            gr_opt: Optional[GateResult] = gate_index.get(gate_name)
            if gr_opt:
                gr = gr_opt
                has_gate_data = True
                ev.gate_results.append({
                    "gate": gr.gate,
                    "state": gr.state.value,
                    "reason": gr.reason,
                    "metric": gr.metric,
                })
                if gr.state == GateState.FAIL:
                    gate_passing = False

        # Collect relevant HC results
        has_hc_data = False
        hc_passing = True
        for hc_id in mapping["hard_constraints"]:
            has_hc_data = True
            if hc_id in violated_hcs:
                hc_passing = False
                ev.hc_results.append({
                    "constraint_id": hc_id,
                    "violated": True,
                })
            else:
                ev.hc_results.append({
                    "constraint_id": hc_id,
                    "violated": False,
                })

        # Determine status
        if not has_gate_data and not has_hc_data:
            ev.status = "gap"
            ev.narrative = (
                f"No governance data available for {category.value}. "
                f"Required gates ({', '.join(mapping['gates'])}) were not evaluated."
            )
            ev.recommendations.append(
                f"Ensure {', '.join(mapping['gates'])} are enabled and metrics are provided."
            )
        elif not gate_passing or not hc_passing:
            ev.status = "flagged"
            issues = []
            if not gate_passing:
                failed_gates = [g["gate"] for g in ev.gate_results if g["state"] == "FAIL"]
                issues.append(f"gate failure(s): {', '.join(failed_gates)}")
            if not hc_passing:
                violated = [h["constraint_id"] for h in ev.hc_results if h["violated"]]
                issues.append(f"HC violation(s): {', '.join(violated)}")
            ev.narrative = (
                f"Governance category '{category.value}' has active issues: {'; '.join(issues)}. "
                f"Deployment may pose risks to {mapping['description'].lower()}."
            )
            ev.recommendations.append(
                f"Resolve {'; '.join(issues)} before deployment."
            )
        elif has_gate_data and gate_passing and hc_passing:
            ev.status = "covered"
            ev.narrative = (
                f"All governance checks pass for {category.value}. "
                f"{mapping['pass_condition']}."
            )
        else:
            ev.status = "partial"
            ev.narrative = (
                f"Some governance data available for {category.value}, "
                f"but coverage is incomplete."
            )
            ev.recommendations.append(
                f"Provide metrics for: {', '.join(mapping['gate_metrics'])}."
            )

        evidence_list.append(ev)

    return evidence_list


def fria_summary(evidence: list[FRIAEvidence]) -> dict[str, Any]:
    """Structured summary of the internal governance-evidence categories.

    Args:
        evidence: List of FRIAEvidence from generate_fria_evidence()

    Returns:
        Dict with category-level summaries and overall status.
    """
    categories: dict[str, dict[str, Any]] = {}
    covered = 0
    flagged = 0
    gaps = 0

    for ev in evidence:
        categories[ev.category.value] = ev.to_dict()
        if ev.status == "covered":
            covered += 1
        elif ev.status == "flagged":
            flagged += 1
        elif ev.status == "gap":
            gaps += 1

    total = len(evidence)
    overall = "compliant" if flagged == 0 and gaps == 0 else (
        "non_compliant" if flagged > 0 else "incomplete"
    )

    return {
        "framework": "Internal governance-evidence categories (FRIA-support, not a complete Article 27 FRIA)",
        "total_categories": total,
        "covered": covered,
        "flagged": flagged,
        "gaps": gaps,
        "overall_status": overall,
        "categories": categories,
    }


def fria_narrative(evidence: list[FRIAEvidence]) -> str:
    """Human-readable report of the internal governance-evidence categories.

    Args:
        evidence: List of FRIAEvidence from generate_fria_evidence()

    Returns:
        Multi-paragraph narrative suitable for inclusion in a FRIA-support package.
    """
    lines: list[str] = []
    lines.append("# FRIA-Support Evidence (internal governance categories)")
    lines.append(
        "## Operational evidence for an EU AI Act Article 27 assessment\n"
        "> This is a FRIA-support package, not a complete or legally sufficient "
        "Article 27 FRIA. See the Article 27(1) crosswalk for the elements that "
        "require deployer context and legal review.\n"
    )

    for ev in evidence:
        status_icon = {
            "covered": "[PASS]",
            "flagged": "[FAIL]",
            "gap": "[GAP]",
            "partial": "[PARTIAL]",
        }.get(ev.status, "[?]")

        lines.append(f"### {status_icon} {ev.category.value.replace('_', ' ').title()}")
        lines.append(f"*{ev.description}*\n")
        lines.append(ev.narrative)

        if ev.recommendations:
            lines.append("\n**Recommendations:**")
            for rec in ev.recommendations:
                lines.append(f"- {rec}")

        lines.append("")

    # Summary
    summary = fria_summary(evidence)
    lines.append("---")
    lines.append(f"**Overall: {summary['overall_status'].upper()}** — "
                 f"{summary['covered']}/{summary['total_categories']} covered, "
                 f"{summary['flagged']} flagged, {summary['gaps']} gaps")

    return "\n".join(lines)


# ===========================================================================
# EU AI Act Article 27(1) crosswalk
# ===========================================================================

class Article27Element(Enum):
    """
    The ACTUAL elements enumerated in EU AI Act Article 27(1)(a)-(f).

    Unlike :class:`GovernanceEvidenceCategory` (the framework's internal buckets),
    these are the assessment elements the Regulation itself requires.
    """
    DEPLOYMENT_PROCESS_AND_INTENDED_USE = "deployment_process_and_intended_use"
    DURATION_AND_FREQUENCY = "duration_and_frequency"
    AFFECTED_PERSONS_AND_GROUPS = "affected_persons_and_groups"
    SPECIFIC_RISKS_OF_HARM = "specific_risks_of_harm"
    HUMAN_OVERSIGHT_MEASURES = "human_oversight_measures"
    GOVERNANCE_AND_COMPLAINT_ARRANGEMENTS = "governance_and_complaint_arrangements"


class EvidenceSource(Enum):
    """Where the evidence for an Article 27(1) element comes from."""
    AUTO_DERIVED = "auto_derived_operational_evidence"
    DEPLOYER_SUPPLIED = "required_deployer_supplied_context"
    MISSING = "missing_or_unverified"


class LegalReviewStatus(Enum):
    """Legal-review state of an Article 27(1) element's evidence."""
    NOT_REVIEWED = "not_reviewed"
    IN_REVIEW = "in_review"
    REVIEWED = "reviewed"


# Which Article 27(1) elements the framework can auto-derive operational evidence
# for, and which strictly require deployer-supplied context. Operational gate
# telemetry CANNOT establish intended use, duration/frequency, affected groups,
# or the complaint arrangements — those are deployer/legal responsibilities.
_ARTICLE_27_SPEC: dict[Article27Element, dict[str, Any]] = {
    Article27Element.DEPLOYMENT_PROCESS_AND_INTENDED_USE: {
        "reference": "Article 27(1)(a)",
        "description": (
            "A description of the deployer's processes in which the high-risk AI "
            "system will be used in line with its intended purpose."
        ),
        "auto_derivable": False,
        "deployer_key": "deployment_process_and_intended_use",
        "note": (
            "Intended purpose and deployment process are deployer facts; the "
            "framework cannot infer them from gate telemetry."
        ),
    },
    Article27Element.DURATION_AND_FREQUENCY: {
        "reference": "Article 27(1)(b)",
        "description": (
            "The period of time and frequency with which the high-risk AI system "
            "is intended to be used."
        ),
        "auto_derivable": False,
        "deployer_key": "duration_and_frequency",
        "note": (
            "Deployment duration/frequency is a deployer plan, not an operational "
            "signal the gates observe."
        ),
    },
    Article27Element.AFFECTED_PERSONS_AND_GROUPS: {
        "reference": "Article 27(1)(c)",
        "description": (
            "The categories of natural persons and groups likely to be affected "
            "by the system's use in the specific context."
        ),
        "auto_derivable": False,
        "deployer_key": "affected_persons_and_groups",
        "note": (
            "The affected population is context-specific and must be supplied by "
            "the deployer; it cannot be derived from risk metrics."
        ),
    },
    Article27Element.SPECIFIC_RISKS_OF_HARM: {
        "reference": "Article 27(1)(d)",
        "description": (
            "The specific risks of harm likely to impact the categories of "
            "affected persons or groups."
        ),
        "auto_derivable": True,
        "gates": ["RiskGate", "EpistemicGate"],
        "hard_constraints": ["HC-4", "HC-5", "HC-9"],
        "deployer_key": "specific_risks_of_harm",
        "note": (
            "The framework contributes operational risk evidence (RiskGate, "
            "EpistemicGate, safety hard constraints). Mapping those signals onto "
            "harms to specific affected groups still requires deployer context."
        ),
    },
    Article27Element.HUMAN_OVERSIGHT_MEASURES: {
        "reference": "Article 27(1)(e)",
        "description": (
            "A description of the human-oversight measures, according to the "
            "instructions for use."
        ),
        "auto_derivable": True,
        "gates": ["AutonomyGate"],
        "hard_constraints": ["HC-11", "HC-12"],
        "deployer_key": "human_oversight_measures",
        "note": (
            "The framework provides operational oversight evidence (AutonomyGate "
            "escalation/activation, gate override prohibition HC-12, outage "
            "notification HC-11). Documented oversight procedures remain a "
            "deployer artifact."
        ),
    },
    Article27Element.GOVERNANCE_AND_COMPLAINT_ARRANGEMENTS: {
        "reference": "Article 27(1)(f)",
        "description": (
            "The measures to be taken if risks materialise, including internal "
            "governance and complaint mechanisms."
        ),
        "auto_derivable": True,
        "gates": ["GovernanceGate"],
        "hard_constraints": ["HC-10"],
        "deployer_key": "governance_and_complaint_arrangements",
        "note": (
            "The framework evidences the internal-governance response (six-gate "
            "FREEZE/STOP machinery, GovernanceGate). Complaint arrangements for "
            "affected persons CANNOT be populated from operational evidence and "
            "require deployer-supplied context."
        ),
    },
}


@dataclass
class Article27Crosswalk:
    """
    One EU AI Act Article 27(1) element, honestly classified.

    Attributes:
        element:            The Article 27(1) element.
        reference:          The sub-paragraph (e.g. "Article 27(1)(d)").
        description:        The element as the Regulation frames it.
        source:             AUTO_DERIVED | DEPLOYER_SUPPLIED | MISSING.
        legal_review:       Legal-review status of this element's evidence.
        operational_evidence: Auto-derived gate/HC evidence, if any.
        deployer_context:   Deployer-supplied context for this element, if any.
        narrative:          Human-readable status, including honest gaps.
        recommendations:    What is still required to complete this element.
    """
    element: Article27Element
    reference: str
    description: str
    source: EvidenceSource
    legal_review: LegalReviewStatus = LegalReviewStatus.NOT_REVIEWED
    operational_evidence: list[dict[str, Any]] = field(default_factory=list)
    deployer_context: Optional[Any] = None
    narrative: str = ""
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "element": self.element.value,
            "reference": self.reference,
            "description": self.description,
            "source": self.source.value,
            "legal_review_status": self.legal_review.value,
            "operational_evidence": self.operational_evidence,
            "deployer_context": self.deployer_context,
            "narrative": self.narrative,
            "recommendations": self.recommendations,
        }


def _coerce_legal_status(value: Any) -> LegalReviewStatus:
    if isinstance(value, LegalReviewStatus):
        return value
    if isinstance(value, str):
        key = value.strip().upper()
        if key in LegalReviewStatus.__members__:
            return LegalReviewStatus[key]
    return LegalReviewStatus.NOT_REVIEWED


def generate_article27_crosswalk(
    gate_results: list[GateResult],
    hc_violations: list[dict[str, Any]],
    deployer_context: Optional[dict[str, Any]] = None,
) -> list[Article27Crosswalk]:
    """Build the EU AI Act Article 27(1) crosswalk.

    For each Article 27(1) element, classifies the evidence source honestly:
    auto-derived operational evidence, required deployer-supplied context, or
    missing/unverified. Operational gate evidence never silently populates an
    element it cannot actually establish (intended use, duration, affected
    groups, complaint arrangements).

    Args:
        gate_results:     Gate results from constitution.evaluate().
        hc_violations:    HC violation dicts (with 'constraint_id').
        deployer_context: Optional mapping of Article 27(1) ``deployer_key`` ->
                          deployer-supplied context. May also carry a
                          ``legal_review`` sub-mapping of element -> status.

    Returns:
        List of Article27Crosswalk, one per Article 27(1) element (always 6).
    """
    deployer_context = deployer_context or {}
    legal_review_map = deployer_context.get("legal_review", {}) or {}

    gate_index = {gr.gate: gr for gr in gate_results}
    violated_hcs: set[str] = set()
    for v in hc_violations:
        cid = v.get("constraint_id", v.get("id", ""))
        if cid:
            violated_hcs.add(cid)

    crosswalk: list[Article27Crosswalk] = []
    for element, spec in _ARTICLE_27_SPEC.items():
        deployer_key = spec["deployer_key"]
        supplied = deployer_context.get(deployer_key)
        legal_status = _coerce_legal_status(legal_review_map.get(element.value))

        operational_evidence: list[dict[str, Any]] = []
        if spec.get("auto_derivable"):
            for gate_name in spec.get("gates", []):
                gr = gate_index.get(gate_name)
                if gr is not None:
                    operational_evidence.append({
                        "gate": gr.gate,
                        "state": gr.state.value,
                        "reason": gr.reason,
                        "metric": gr.metric,
                    })
            for hc_id in spec.get("hard_constraints", []):
                operational_evidence.append({
                    "constraint_id": hc_id,
                    "violated": hc_id in violated_hcs,
                })

        recommendations: list[str] = []
        if spec.get("auto_derivable"):
            if supplied is not None:
                source = EvidenceSource.AUTO_DERIVED
                narrative = (
                    f"{spec['reference']}: operational evidence auto-derived from "
                    f"{', '.join(spec.get('gates', []))}; deployer context also "
                    f"supplied. {spec['note']}"
                )
            elif operational_evidence:
                source = EvidenceSource.AUTO_DERIVED
                narrative = (
                    f"{spec['reference']}: operational evidence auto-derived from "
                    f"{', '.join(spec.get('gates', []))}. {spec['note']}"
                )
                recommendations.append(
                    "Augment with deployer-supplied context to complete this "
                    "element; operational evidence alone is not sufficient."
                )
            else:
                source = EvidenceSource.MISSING
                narrative = (
                    f"{spec['reference']}: auto-derivable, but the required gates "
                    f"({', '.join(spec.get('gates', []))}) were not evaluated. "
                    f"{spec['note']}"
                )
                recommendations.append(
                    f"Enable {', '.join(spec.get('gates', []))} and provide their metrics."
                )
        else:
            if supplied is not None:
                source = EvidenceSource.DEPLOYER_SUPPLIED
                narrative = (
                    f"{spec['reference']}: deployer-supplied context provided. "
                    f"{spec['note']}"
                )
            else:
                source = EvidenceSource.MISSING
                narrative = (
                    f"{spec['reference']}: requires deployer-supplied context, "
                    f"which was not provided. {spec['note']}"
                )
                recommendations.append(
                    f"Provide deployer context under '{deployer_key}' — this "
                    "element cannot be populated from operational evidence."
                )

        if legal_status != LegalReviewStatus.REVIEWED:
            recommendations.append(
                "Obtain legal review of this element before relying on it in a "
                "submitted FRIA."
            )

        crosswalk.append(Article27Crosswalk(
            element=element,
            reference=spec["reference"],
            description=spec["description"],
            source=source,
            legal_review=legal_status,
            operational_evidence=operational_evidence,
            deployer_context=supplied,
            narrative=narrative,
            recommendations=recommendations,
        ))

    return crosswalk


def fria_support_package(
    gate_results: list[GateResult],
    hc_violations: list[dict[str, Any]],
    deployer_context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Assemble the complete FRIA-support package.

    Combines the internal governance-evidence categories with the Article 27(1)
    crosswalk into one structured artifact — explicitly labelled as *support*
    material, not a complete or legally sufficient Article 27 FRIA.

    Returns:
        Dict with a disclaimer, the internal evidence summary, the Article 27(1)
        crosswalk, and readiness counts.
    """
    evidence = generate_fria_evidence(gate_results, hc_violations)
    crosswalk = generate_article27_crosswalk(gate_results, hc_violations, deployer_context)

    by_source: dict[str, int] = {s.value: 0 for s in EvidenceSource}
    reviewed = 0
    for cw in crosswalk:
        by_source[cw.source.value] += 1
        if cw.legal_review == LegalReviewStatus.REVIEWED:
            reviewed += 1

    return {
        "artifact": "FRIA-support package",
        "disclaimer": (
            "This package is operational governance evidence to SUPPORT an EU AI "
            "Act Article 27 Fundamental Rights Impact Assessment. It is NOT a "
            "complete or legally sufficient FRIA. Elements requiring deployer "
            "context and legal review are marked as such in the Article 27(1) "
            "crosswalk."
        ),
        "internal_governance_evidence": fria_summary(evidence),
        "article_27_1_crosswalk": [cw.to_dict() for cw in crosswalk],
        "article_27_1_readiness": {
            "elements_total": len(crosswalk),
            "by_source": by_source,
            "legally_reviewed": reviewed,
            "complete": (
                by_source[EvidenceSource.MISSING.value] == 0
                and reviewed == len(crosswalk)
            ),
        },
    }
