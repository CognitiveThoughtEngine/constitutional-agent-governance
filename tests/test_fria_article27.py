"""
FRIA model fix (v0.7.0): internal governance-evidence categories are relabeled
(not "the six Article 27 categories"), and a separate Article 27(1) crosswalk
honestly classifies each element's evidence source + legal-review status.
"""

from __future__ import annotations

from constitutional_agent import Constitution
from constitutional_agent.fria import (
    Article27Applicability,
    Article27Element,
    EvidenceSource,
    FRIACategory,
    GovernanceEvidenceCategory,
    LegalReviewStatus,
    fria_support_package,
    generate_article27_crosswalk,
)
from constitutional_agent.schema import GateResult, GateState


def _gate(name, state=GateState.PASS):
    return GateResult(gate=name, state=state, reason="ok", metric=None)


ALL_GATES = [
    _gate("EpistemicGate"), _gate("RiskGate"), _gate("GovernanceGate"),
    _gate("EconomicGate"), _gate("AutonomyGate"), _gate("ConstitutionalGate"),
]


# ---------------------------------------------------------------------------
# Relabel: internal categories are NOT the Article 27 categories
# ---------------------------------------------------------------------------

def test_internal_categories_are_six_and_relabeled():
    assert len(list(GovernanceEvidenceCategory)) == 6
    # Backwards-compatible alias still resolves.
    assert FRIACategory is GovernanceEvidenceCategory


def test_article27_elements_are_the_actual_six():
    values = {e.value for e in Article27Element}
    assert values == {
        "deployment_process_and_intended_use",
        "duration_and_frequency",
        "affected_persons_and_groups",
        "specific_risks_of_harm",
        "human_oversight_measures",
        "governance_and_complaint_arrangements",
    }


# ---------------------------------------------------------------------------
# Crosswalk classification honesty
# ---------------------------------------------------------------------------

def test_deployer_only_elements_missing_without_context():
    cw = {c.element: c for c in generate_article27_crosswalk(ALL_GATES, [])}
    # These four cannot be populated from operational evidence.
    for el in (
        Article27Element.DEPLOYMENT_PROCESS_AND_INTENDED_USE,
        Article27Element.DURATION_AND_FREQUENCY,
        Article27Element.AFFECTED_PERSONS_AND_GROUPS,
    ):
        assert cw[el].source == EvidenceSource.MISSING
        assert cw[el].operational_evidence == []


def test_deployer_supplied_context_marks_deployer_source():
    deployer_context = {
        "deployment_process_and_intended_use": "Batch triage, internal only",
        "duration_and_frequency": "8h/day, weekdays",
        "affected_persons_and_groups": "Loan applicants in the EU",
    }
    cw = {c.element: c for c in generate_article27_crosswalk(ALL_GATES, [], deployer_context)}
    assert cw[Article27Element.DEPLOYMENT_PROCESS_AND_INTENDED_USE].source == EvidenceSource.DEPLOYER_SUPPLIED
    assert cw[Article27Element.AFFECTED_PERSONS_AND_GROUPS].deployer_context == "Loan applicants in the EU"


def test_auto_derivable_elements_carry_operational_evidence():
    cw = {c.element: c for c in generate_article27_crosswalk(ALL_GATES, [])}
    risk = cw[Article27Element.SPECIFIC_RISKS_OF_HARM]
    assert risk.source == EvidenceSource.AUTO_DERIVED
    assert risk.operational_evidence  # gate + HC evidence attached
    # Even auto-derived elements recommend deployer augmentation.
    assert any("deployer" in r.lower() for r in risk.recommendations)


def test_auto_derivable_still_needs_deployer_augmentation():
    # Even with full operational evidence, an auto-derivable element is never
    # presented as self-sufficient: it recommends deployer augmentation.
    cw = {c.element: c for c in generate_article27_crosswalk(ALL_GATES, [])}
    risk = cw[Article27Element.SPECIFIC_RISKS_OF_HARM]
    assert risk.source == EvidenceSource.AUTO_DERIVED
    assert any("not sufficient" in r.lower() or "deployer" in r.lower()
               for r in risk.recommendations)


def test_legal_review_status_wired_through():
    deployer_context = {"legal_review": {"specific_risks_of_harm": "reviewed"}}
    cw = {c.element: c for c in generate_article27_crosswalk(ALL_GATES, [], deployer_context)}
    assert cw[Article27Element.SPECIFIC_RISKS_OF_HARM].legal_review == LegalReviewStatus.REVIEWED
    assert cw[Article27Element.DURATION_AND_FREQUENCY].legal_review == LegalReviewStatus.NOT_REVIEWED


# ---------------------------------------------------------------------------
# Support package: never claims a complete Article 27 FRIA
# ---------------------------------------------------------------------------

def test_support_package_is_labeled_support_not_complete_fria():
    pkg = fria_support_package(ALL_GATES, [])
    assert pkg["artifact"] == "FRIA-support package"
    assert "NOT a complete" in pkg["disclaimer"]
    assert len(pkg["article_27_1_crosswalk"]) == 6
    # Missing deployer context -> crosswalk fields not present-and-reviewed.
    assert pkg["article_27_1_readiness"]["crosswalk_fields_present_and_reviewed"] is False
    # The readiness dict must NOT carry a `complete` key (it would overclaim a
    # finished FRIA).
    assert "complete" not in pkg["article_27_1_readiness"]


def test_support_package_complete_requires_all_present_and_reviewed():
    deployer_context = {
        "deployment_process_and_intended_use": "x",
        "duration_and_frequency": "x",
        "affected_persons_and_groups": "x",
        "specific_risks_of_harm": "x",
        "human_oversight_measures": "x",
        "governance_and_complaint_arrangements": "x",
        "legal_review": {e.value: "reviewed" for e in Article27Element},
    }
    pkg = fria_support_package(ALL_GATES, [], deployer_context)
    r = pkg["article_27_1_readiness"]
    assert r["by_source"][EvidenceSource.MISSING.value] == 0
    assert r["legally_reviewed"] == 6
    assert r["crosswalk_fields_present_and_reviewed"] is True


def test_constitution_fria_support_package_integration():
    c = Constitution.from_defaults()
    pkg = c.fria_support_package({"misuse_risk_index": 0.05, "runway_months": 10})
    assert "article_27_1_crosswalk" in pkg
    assert pkg["internal_governance_evidence"]["total_categories"] == 6


# ---------------------------------------------------------------------------
# Pre-merge review corrections: readiness key rename (item 8) + Article 27
# applicability status (item 9)
# ---------------------------------------------------------------------------

def test_readiness_key_renamed_and_no_complete_key():
    # Item 8: `complete` -> `crosswalk_fields_present_and_reviewed`; no key named
    # `complete` may imply a finished FRIA.
    pkg = fria_support_package(ALL_GATES, [])
    readiness = pkg["article_27_1_readiness"]
    assert "crosswalk_fields_present_and_reviewed" in readiness
    assert "complete" not in readiness


def test_applicability_defaults_to_not_assessed():
    # Item 9: six populated elements must NOT imply applicability.
    pkg = fria_support_package(ALL_GATES, [])
    assert pkg["article_27_applicability"] == Article27Applicability.NOT_ASSESSED.value
    assert pkg["article_27_applicability"] == "not_assessed"


def test_applicability_reflects_deployer_context():
    pkg = fria_support_package(
        ALL_GATES, [], deployer_context={"applicability": "out_of_scope"}
    )
    assert pkg["article_27_applicability"] == "out_of_scope"


def test_applicability_accepts_enum_and_ignores_garbage():
    pkg_enum = fria_support_package(
        ALL_GATES, [], deployer_context={"applicability": Article27Applicability.IN_SCOPE}
    )
    assert pkg_enum["article_27_applicability"] == "in_scope"
    pkg_bad = fria_support_package(
        ALL_GATES, [], deployer_context={"applicability": "banana"}
    )
    assert pkg_bad["article_27_applicability"] == "not_assessed"
