"""
Fundamental Rights Impact Assessment (FRIA) evidence generation.

EU AI Act Article 27 mandates FRIA before deploying high-risk AI systems.
This module maps constitutional governance gate and hard constraint results
to FRIA categories, generating structured evidence for compliance.

Tracks GitHub issue #12.

Usage:
    from constitutional_agent.fria import generate_fria_evidence, fria_summary

    evidence = generate_fria_evidence(gate_results, hc_violations)
    summary = fria_summary(evidence)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from constitutional_agent.schema import GateResult, GateState


class FRIACategory(Enum):
    """EU AI Act Fundamental Rights Impact Assessment categories."""
    SAFETY = "safety"
    NON_DISCRIMINATION = "non_discrimination"
    PRIVACY = "privacy"
    HUMAN_OVERSIGHT = "human_oversight"
    TRANSPARENCY = "transparency"
    ACCOUNTABILITY = "accountability"


@dataclass
class FRIAEvidence:
    """Evidence for a single FRIA category."""
    category: FRIACategory
    description: str
    gate_results: list[dict] = field(default_factory=list)
    hc_results: list[dict] = field(default_factory=list)
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


# Mapping from FRIA categories to gates and hard constraints
FRIA_MAPPING: dict[FRIACategory, dict[str, Any]] = {
    FRIACategory.SAFETY: {
        "description": "Impact on safety and physical integrity of natural persons",
        "gates": ["RiskGate"],
        "gate_metrics": ["misuse_risk_index", "security_critical_events"],
        "hard_constraints": ["HC-5", "HC-9"],
        "pass_condition": "RiskGate PASS and no HC-5/HC-9 violations",
    },
    FRIACategory.NON_DISCRIMINATION: {
        "description": "Impact on non-discrimination and equality",
        "gates": ["EpistemicGate"],
        "gate_metrics": ["verification_pass_rate"],
        "hard_constraints": ["HC-4"],
        "pass_condition": "EpistemicGate PASS and no HC-4 violations",
    },
    FRIACategory.PRIVACY: {
        "description": "Impact on privacy and data protection",
        "gates": ["RiskGate"],
        "gate_metrics": ["misuse_risk_index"],
        "hard_constraints": ["HC-6"],
        "pass_condition": "RiskGate PASS with low misuse_risk_index",
    },
    FRIACategory.HUMAN_OVERSIGHT: {
        "description": "Impact on human oversight and agency",
        "gates": ["AutonomyGate"],
        "gate_metrics": ["human_minutes_per_day", "decisions_per_day", "agent_activation_rate"],
        "hard_constraints": ["HC-12"],
        "pass_condition": "AutonomyGate PASS and no HC-12 violations",
    },
    FRIACategory.TRANSPARENCY: {
        "description": "Impact on transparency and explainability",
        "gates": ["GovernanceGate"],
        "gate_metrics": ["audit_coverage"],
        "hard_constraints": ["HC-4", "HC-11"],
        "pass_condition": "GovernanceGate PASS with audit_coverage >= 0.95",
    },
    FRIACategory.ACCOUNTABILITY: {
        "description": "Impact on accountability and redress",
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
    """Generate FRIA evidence from gate and hard constraint evaluation results.

    Args:
        gate_results: List of GateResult from constitution.evaluate()
        hc_violations: List of HC violation dicts (with 'constraint_id' key)

    Returns:
        List of FRIAEvidence, one per FRIA category (always 6).
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
            gr = gate_index.get(gate_name)
            if gr:
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
                f"FRIA category '{category.value}' has active issues: {'; '.join(issues)}. "
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
    """Generate a structured FRIA summary suitable for JSON output.

    Args:
        evidence: List of FRIAEvidence from generate_fria_evidence()

    Returns:
        Dict with category-level summaries and overall status.
    """
    categories: dict[str, dict] = {}
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
        "framework": "EU AI Act Article 27 — FRIA",
        "total_categories": total,
        "covered": covered,
        "flagged": flagged,
        "gaps": gaps,
        "overall_status": overall,
        "categories": categories,
    }


def fria_narrative(evidence: list[FRIAEvidence]) -> str:
    """Generate a human-readable FRIA report narrative.

    Args:
        evidence: List of FRIAEvidence from generate_fria_evidence()

    Returns:
        Multi-paragraph narrative suitable for compliance documentation.
    """
    lines: list[str] = []
    lines.append("# Fundamental Rights Impact Assessment (FRIA)")
    lines.append("## EU AI Act Article 27 Compliance Evidence\n")

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
