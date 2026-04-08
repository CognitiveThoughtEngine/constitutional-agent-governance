# ROADMAP — constitutional-agent

> **The WHY layer for autonomous AI agents.**  
> WHO governs identity. HOW governs behavior. WHY governs values.

**Current version:** v0.1.0 (April 2026)  
**Status:** Public, production-extracted, pre-revenue  
**License:** MIT

---

## Vision

Every organization deploying autonomous agents will eventually face an incident that a policy file didn't cover — an agent that was authorized, behaviorally compliant, and constitutionally wrong. `constitutional-agent` exists to make that incident preventable: a governance layer, enforced in code rather than YAML, that evaluates *why* a decision aligns or violates the organization's foundational principles before any action executes. The goal over 18 months is to make "constitutional governance" a recognized category, to own the WHY-layer niche before a large vendor fills it with a closed product, and to build the community, evidence base, and commercial infrastructure that turns a well-positioned open-source library into a durable business.

---

## Market Opportunity

Agentic AI is moving from experimental to operational faster than governance infrastructure is following. The WHO layer (identity: which agent is this?) and the HOW layer (behavior: what is this agent permitted to do?) have attracted tooling from Microsoft, Okta, AWS, LangChain, and OWASP. None of them address the structural gap that remains: an agent can be fully authenticated, fully policy-compliant, and still make decisions that are epistemically unsound, economically reckless, or strategically incoherent.

The evidence is not theoretical. On April 7, 2026, a developer published 41 days and 200 runs of autonomous agent data: $6.74 earned, four failure modes, roughly 80–90 wasted cycles attributable to broken payment settlement, false cost assumptions, a shadow-banned channel, and a strategy death spiral — none caught by WHO or HOW governance. That experiment is a leading indicator of a category-level problem: as agents are handed real economic authority (spending budgets, publishing content, managing customer relationships), the absence of constitutional governance becomes a measurable liability.

The governance gap is being noticed. NIST 800-2 is addressing agentic AI risk frameworks. CAISI has acknowledged the WHY-layer problem. Enterprise compliance teams are beginning to ask for governance documentation before approving agent deployment. The category is forming. The question is whether it will be defined by an open, community-built standard or by a closed vendor API.

---

## Strategic Phases

### Phase 1 — Establish the Standard (Months 1–4)
**April – July 2026**

**Theme:** Earn credibility with the developer community. Make "constitutional governance" a searchable, citable, referenced term. Do this through intellectual honesty, not marketing.

**Deliverables:**

1. **Expand test coverage from 13 to 100+ tests.** The current test suite validates the happy path. Add adversarial tests: gate failures that are intentionally gamed, hard constraints that are tested against malformed inputs, YAML configs that are structurally invalid. A library governing autonomous agents must itself be constitutionally sound.

2. **Publish the governance checklist as a standalone resource.** The 35-check WHO/HOW/WHY checklist in `checklist/CONSTITUTIONAL_GOVERNANCE_CHECKLIST.md` is already written. Syndicate it: GitHub Gist, dev.to, LinkedIn article, OWASP Agentic AI community. The checklist is the top-of-funnel artifact — it introduces the WHY layer without requiring a code commitment.

3. **Add two additional case study audits** in the `examples/` directory. The agenthustler audit is strong. Add at least two more real-world agent failure analyses (publicly documented incidents or community-contributed experiments) using the same format: failure mode, which gate, which metric, what the agent would have done differently. Case studies are the proof of concept that PRs and docs cannot replace.

4. **v0.2.0: YAML-driven threshold configuration.** The `Constitution._build_evaluator()` method currently ignores YAML-configured thresholds and uses hardcoded defaults. Implement threshold loading from `governance.yaml` so organizations can tune gates without forking the library. This is a prerequisite for enterprise adoption — no organization will deploy a governance library with untunable thresholds.

5. **Community infrastructure.** GitHub Discussions enabled (done), issue templates written (bug report, gate threshold proposal, new hard constraint proposal). A community that cannot contribute in a structured way does not compound.

**Success Metrics:**

| Metric | Target |
|--------|--------|
| GitHub stars | 100+ |
| PyPI downloads/month | 500+ (organic) |
| External citations (non-CTE) | 3+ |
| Inbound pull requests | 1+ |
| Checklist shares outside CTE channels | 5+ |

**Strategic Rationale:** Credibility in the governance space is earned by being right about hard things in public, not by marketing. The agenthustler case study, the NIST citations, the CAISI acknowledgment — these are assets. Phase 1 is about converting those assets into community traction before the narrative window closes. The WHY-layer framing is novel now; it will not be novel in 18 months.

---

### Phase 2 — Build the Evidence Base (Months 3–8)
**June – November 2026**

**Theme:** Turn early adopters into case study authors. Every organization that deploys the library is a potential proof point. Collect that evidence systematically.

**Deliverables:**

1. **Async/callback support.** The current `Constitution.evaluate()` is synchronous. Most production agent frameworks (LangGraph, CrewAI, AutoGen) are async-native. Add `async def evaluate_async()` to make integration idiomatic rather than requiring workarounds. This is the single highest-friction integration barrier for the target developer profile.

2. **Framework integration guides.** Dedicated `examples/` entries for LangChain, LangGraph, CrewAI, and AutoGen. Each guide shows constitutional evaluation integrated at the decision point — not bolted on at the end. Integrations are the proof of composability that the "complementary, not competing" narrative requires.

3. **Governance report export.** Extend `Constitution.summary_report()` to produce structured JSON and Markdown reports suitable for compliance documentation. Enterprise ML teams need artifacts they can attach to risk assessments — not just Python objects. This also enables the consulting offer to produce a standardized deliverable.

4. **Amendment audit trail persistence.** The current amendment log is in-memory. Add optional file-based persistence (append-only JSONL) so the amendment history survives restarts and can be audited externally. 64 amendments ratified in 95 days is a meaningful governance record — organizations need to preserve that record.

5. **"Constitutional Governance Review" commercial offer launched.** The consulting offer (2-hour assessment, written report, top 3 gaps, remediation roadmap) is listed on cteinvest.com but not systematically generated by the library. Build the intake form, report template, and delivery process. The first 10 reviews should be conducted at reduced rate or free in exchange for a publishable case study. These become the Phase 3 social proof assets.

**Success Metrics:**

| Metric | Target |
|--------|--------|
| PyPI downloads/month | 1,000+ |
| Organizations citing the library publicly | 3+ |
| Paid governance reviews completed | 2+ |
| Async evaluate shipped | Yes |
| Framework integration guides | 2+ frameworks |
| Amendment persistence merged | 90%+ test coverage |

**Strategic Rationale:** Phase 2 is about converting initial awareness into institutional adoption. The governance consulting offer is not just revenue — it is structured intelligence gathering. Each review surfaces a new organizational failure mode, which feeds back into new hard constraints, new gate thresholds, and new case studies. The commercial activity and the open-source roadmap are the same feedback loop.

---

### Phase 3 — Own the Category (Months 7–14)
**October 2026 – May 2027**

**Theme:** The WHY layer is a recognized category. `constitutional-agent` is the reference implementation. This phase builds the institutional relationships and technical depth that make displacement difficult.

**Deliverables:**

1. **v1.0.0 stable release.** Semantic versioning commitment: no breaking API changes without a major version increment. Deprecation warnings for any change that affects `Constitution.evaluate()`, `propose_amendment()`, or `ratify_amendment()`. Enterprise adopters require API stability guarantees before embedding a library in critical infrastructure.

2. **Custom gate registration.** Allow organizations to register domain-specific gates (`constitution.register_gate(MyComplianceGate())`) that participate in the system state calculation alongside the six built-in gates. This is the extensibility primitive that converts `constitutional-agent` from a library into a platform. The six built-in gates remain opinionated defaults; custom gates handle organization-specific requirements (HIPAA, SOX, financial regulation).

3. **Academic engagement.** Submit or co-author a paper to a venue covering AI safety, AI governance, or multi-agent systems (NeurIPS, FAccT, IEEE S&P, AIES). The five Zenodo preprints are the foundation. A peer-reviewed publication changes the citation landscape — enterprise legal and compliance teams weight peer review differently than preprints.

4. **Governance API (hosted, beta).** A REST wrapper around `Constitution.evaluate()` that enterprise teams can call without embedding Python. Provides audit log storage, amendment history, and a dashboard. Priced per-evaluation above a free tier. This is the first step toward enterprise licensing — it does not require the enterprise to manage a Python dependency in their infrastructure.

5. **Policy integration connectors.** Lightweight adapters that pull policy state from common HOW-layer tools (NeMo Guardrails, OPA) and feed it into the WHY-layer context dict. This makes the "complementary, not competing" narrative concrete: organizations running NeMo can feed NeMo's output into constitutional evaluation without duplication.

**Success Metrics:**

| Metric | Target |
|--------|--------|
| PyPI downloads/month | 5,000+ |
| v1.0.0 shipped | API stability commitment public |
| Enterprise adopters (500+ employees) | 1+ publicly confirmed |
| Governance API beta paying customers | 10+ |
| Paid governance reviews | 10+ |
| Peer-reviewed publication | Accepted or in review |
| Custom gate registration | Shipped |

**Strategic Rationale:** Category ownership is established by being the thing people point to when explaining the concept. That requires technical depth (custom gates, API stability), institutional credibility (peer review, enterprise reference customers), and commercial validation (paid reviews, hosted API revenue). Phase 3 is where "interesting open-source project" becomes "the standard for WHY-layer governance."

---

### Phase 4 — Scale the Commercial Layer (Months 13–18)
**April – September 2027**

**Theme:** The open-source library is the distribution channel. The commercial layer is the business. This phase separates the two structurally while keeping them strategically aligned.

**Deliverables:**

1. **Enterprise licensing tier.** Formal SLA, dedicated support, private amendment audit log retention, SOC 2 Type I report for the hosted API. Priced per-agent or per-seat. The open-source library remains MIT — the enterprise tier licenses infrastructure and support, not the core governance logic.

2. **Governance dashboard (GA).** The hosted API's audit log UI reaches general availability: amendment history, gate state trends over time, hard constraint violation alerts, exportable compliance reports. This is the artifact that justifies the enterprise license conversation.

3. **Certification program.** A structured "Constitutional Governance Certified" designation for organizations that complete an assessment and maintain minimum WHY-layer scores. Modeled on SOC 2 but specific to agentic AI governance. Creates recurring revenue (annual recertification), recurring customer contact, and a sales asset (prospects can see certified organizations).

4. **Partner ecosystem.** Formal integrations with at least two agentic platform vendors where `constitutional-agent` is listed as a recommended governance layer. Partner relationships reduce customer acquisition cost and increase perceived legitimacy.

5. **Governance-as-Code specification.** Publish a formal specification for the `governance.yaml` schema, versioned and documented, with a validator tool. A spec that third parties adopt is a moat.

**Success Metrics:**

| Metric | Target |
|--------|--------|
| Revenue (reviews + API + licenses)/month | $10,000 MRR |
| Enterprise license agreements | 3+ signed |
| PyPI downloads/month | 20,000+ |
| Certified organizations | 5+ |
| Formal partner relationships | 1+ major agentic AI vendor |
| Governance-as-Code spec adoption | 2+ third-party tools |

**Strategic Rationale:** Phase 4 is a test of whether the category leadership built in Phase 3 converts to commercial durability. The open-source library never becomes the revenue vehicle — it remains free, MIT-licensed, and community-governed. The commercial layer sells what enterprises actually buy: infrastructure, SLAs, audit artifacts, and certification. This structure protects community trust while building a business.

---

## Competitive Moat Analysis

### What Makes This Defensible

**First-mover framing.** "WHO, HOW, WHY" is a clarifying frame for a problem the field has not named clearly. Frames are sticky. When practitioners start using this vocabulary — when a CISO asks "what's your WHY layer?" — the library that named the concept has a durable advantage.

**Production extraction, not research projection.** v0.1.0 is extracted from a system that has run 52 agents, processed 64 ratified amendments, and operated under real economic pressure for 95 days. That production pedigree is genuinely difficult to replicate. A vendor building a competing product starts from zero operational data; `constitutional-agent` starts from 95 days of real governance decisions.

**The amendment protocol as institutional lock-in.** An organization that has ratified 20 amendments against their governance configuration has an amendment history — a documented record of how their governance evolved. That record lives in the library's data model. Migrating to a different library means losing or migrating that institutional memory. This is not artificial lock-in; it is a natural artifact of meaningful governance adoption.

**Community-built case study corpus.** If Phase 2 executes correctly, the case study library will contain real organizational failure modes contributed by real adopters. That corpus is not replicable by a vendor building a closed product — it requires community trust and open contribution norms.

**NIST and regulatory positioning.** Early citation in standards processes creates a reference that subsequent standards documents cite. That self-reinforcing citation graph is difficult for a late entrant to replicate.

### What Could Erode It

**A major agentic platform vendor ships a built-in governance layer.** This is the primary displacement risk. A built-in governance layer in Azure AI Studio, the Anthropic API, or Vertex AI would reach every enterprise customer of those platforms. *Mitigation:* Ship the Governance-as-Code specification and partner relationships in Phase 4 before this happens. The MIT license also means a vendor can adopt the library directly — which would be a success, not a defeat.

**The WHY-layer framing is adopted but the library is not.** Someone publishes a competing library under the same conceptual frame with better marketing, async support from day one, or a VC-funded team. *Mitigation:* Move fast on v1.0.0 API stability, async support, and the case study corpus in Phases 1–2. First-mover advantage in open-source requires sustained execution to maintain.

**Community trust is damaged by commercialization.** Open-source communities have long memories about projects that shifted from "community-first" to "enterprise-first." *Mitigation:* The MIT license is permanent and non-negotiable. The commercial tier sells infrastructure and support, never the core library. All gate logic and hard constraint definitions remain open.

**The governance problem is solved at the LLM layer.** Foundation model providers ship constitutional AI natively, making external governance libraries redundant. *Mitigation:* If this happens, the library's value shifts to the organizational amendment protocol and audit trail rather than the gate logic itself. This is a positioning adjustment, not an extinction event.

---

## Monetization Path

The library remains MIT. It always will. The monetization path runs parallel to the open-source project, not through it.

**Tier 1 — Constitutional Governance Review** (now)  
A 2-hour structured assessment of an organization's agent governance posture against the 35-check WHO/HOW/WHY checklist. Deliverable: written report, top 3 gaps, remediation roadmap with specific `constitutional-agent` configuration. Price: $2,000–$5,000 depending on complexity. No technical dependency required — the conversation starts from the checklist.

*Why this works without killing trust:* It is a consulting service. The library is the credential. No one feels their open-source tool has been taken from them.

**Tier 2 — Hosted Governance API** (Phase 3)  
A REST API wrapper around `Constitution.evaluate()` with audit log persistence, amendment history, and a dashboard. Free tier: 1,000 evaluations/month. Paid tier: $0.01–$0.05 per evaluation above the free tier, with volume discounts.

*Why this works without killing trust:* Organizations pay for infrastructure, not the algorithm. The algorithm is free to self-host. The hosted version is convenience + reliability + audit storage.

**Tier 3 — Enterprise License** (Phase 4)  
SLA, dedicated support, SOC 2 report, private audit log retention, governance dashboard, certification support. Annual contract at $24,000–$120,000/year depending on agent count and support tier.

*Why this works without killing trust:* Enterprise buyers are not the same population as open-source developers. The former need SLAs and audit artifacts; the latter need a working library. These are different products.

**The line that must not blur:** Any change to the library that advantages paying customers over open-source users will damage community trust permanently. The commercial tier sells infrastructure. The open-source library gets all functionality. If that line ever blurs, fix it publicly and immediately.

---

## Key Risks and Mitigations

**Risk 1: No organic traction despite strong launch positioning**

Most open-source libraries with good technical foundations fail to build communities because they optimize for code quality rather than developer experience. The gap between "this is correct" and "developers find this" is distribution, not technical merit.

*Mitigation:* Treat the first 60 days as a distribution experiment. Publish in three places that are not GitHub: dev.to (the agenthustler response thread is already there), r/MachineLearning or r/LLM, and LinkedIn (enterprise ML audience). Respond personally to every GitHub issue and Discussion within 24 hours. Track download source.

**Risk 2: Gate thresholds are wrong for the general case**

The built-in thresholds were calibrated on one specific operational context. Applied to a different organization's agents, they may generate systematic false positives (blocking healthy agents), giving the library a reputation as "too aggressive."

*Mitigation:* The Phase 1 YAML threshold configuration work (v0.2.0) addresses this. More importantly: add a `dry_run=True` mode that returns what would have happened without blocking execution. Let new adopters calibrate against their real data before enabling enforcement.

**Risk 3: The consulting offer fails to convert despite inbound interest**

The primary adopter persona (solo developer) is not the same as the buyer persona for a $2,000 consulting engagement. There is a persona gap between "interested" and "can buy."

*Mitigation:* Add a lower-priced entry point: a 30-minute "Constitutional Health Score" session at $300–$500, report-only. Removes the persona gap — a developer with a company card can approve $300. Sessions also surface which organizations are serious enough to pursue for enterprise sales.

**Risk 4: HRAO-E's specific context is too visible in the library**

The library is extracted from HRAO-E, and traces of that context may make it feel like a single-organization export rather than a general standard. Enterprise adopters may hesitate to build on something that feels bespoke.

*Mitigation:* In v0.2.0, audit all public-facing documentation for HRAO-E-specific references and generalize them or move them to `docs/case-studies/hrao-e.md`. The production pedigree should read as "extracted from a 95-day, 52-agent production deployment" — not as a require-the-reader-to-understand-HRAO-E dependency.

---

## Metrics Dashboard

### Weekly

| Metric | Source | What to Watch |
|--------|--------|---------------|
| PyPI weekly downloads | pypistats.org | Absolute + week-over-week change |
| GitHub stars | GitHub Insights | Spikes indicate external mention |
| Open issues / PRs | GitHub | Time-to-first-response (target: <24h) |
| Inbound mentions | Google Alerts, X, LinkedIn | External citations of the library or WHY-layer framing |
| Governance Review inquiries | cteinvest.com | Pipeline for commercial tier |

### Monthly

| Metric | Month 6 Target | Month 12 Target | Month 18 Target |
|--------|----------------|-----------------|-----------------|
| PyPI downloads/month | 500 | 5,000 | 20,000 |
| GitHub stars | 200 | 1,000 | 3,000 |
| External case studies / citations | 1 | 5 | 15 |
| Paid governance reviews | 1 | 10 | 30 |
| Revenue (reviews + API) | $2,000 | $20,000 | $100,000 |
| Non-CTE contributors (PRs merged) | 1 | 5 | 20 |
| Framework integration guides | 1 | 3 | 6 |

### Lagging Indicators (Quarterly)

- Enterprise pipeline: organizations in active conversation about licensing or governance review
- Academic citations: papers citing the Zenodo preprints or the library directly
- Regulatory citations: references in NIST, CAISI, OWASP, or equivalent standards documents
- Customer amendment rate: average amendments ratified per month across known deployments (proxy for active governance adoption, not just installation)

---

## Decision Gates

These are the specific thresholds that trigger phase advancement, strategic pivot, or shutdown evaluation. They are not aspirational — they are decision points with defined responses.

### Phase 1 → Phase 2 Advancement

**Advance when ALL of the following are true:**
- PyPI downloads ≥ 400/month for two consecutive months
- At least 1 external contributor PR merged
- v0.2.0 (YAML threshold configuration) shipped
- At least 1 Constitutional Governance Review inquiry received (paid or free)

**If not achieved by Month 4:** Do not advance. Diagnose the gap — distribution, developer experience, or product fit? Run a focused 30-day experiment addressing the diagnosed gap before re-evaluating.

### Phase 2 → Phase 3 Advancement

**Advance when ALL of the following are true:**
- PyPI downloads ≥ 1,000/month for two consecutive months
- At least 2 paid Constitutional Governance Reviews completed
- `evaluate_async()` shipped
- At least 1 external organization references the library in public documentation
- Amendment persistence feature merged

**If not achieved by Month 8:** Reassess the commercial offer. If technical milestones are met but commercial milestones are not, the product may have distribution without commercial intent match. Reposition the consulting offer before building the hosted API.

### Phase 3 → Phase 4 Advancement

**Advance when ALL of the following are true:**
- v1.0.0 shipped with API stability commitment
- Hosted Governance API has ≥ 10 paying customers
- At least 1 enterprise organization (500+ employees) publicly using the library
- Revenue ≥ $5,000/month for two consecutive months

**If not achieved by Month 14:** Do not launch enterprise licensing. Enterprise licensing without reference customers is a sales process that cannot close. Extend Phase 3 with focus on the specific gap.

### Pivot Trigger

**Evaluate a strategic pivot if:**
- Month 6: PyPI downloads < 200/month AND external mentions < 2 (product-market fit signal)
- Month 9: revenue = $0 despite adequate download volume (commercial model signal)
- Before Month 12: a major platform vendor ships a directly competing WHY-layer product (competitive positioning must shift to complementary or specification layer)

A pivot is not a failure declaration. It is a decision to update the strategy based on evidence — which is exactly what constitutional governance is designed to force.

### Shutdown Evaluation

**Evaluate sunsetting the commercial activity (not the library) if by Month 18:**
- Revenue < $2,000/month AND no enterprise pipeline after two pricing experiments

In this scenario: the library continues as a community project under MIT. The commercial infrastructure is sunset or handed to a community maintainer. The library itself does not go away — the community does not get abandoned because the commercial layer failed.

---

## Current State Acknowledgment

This document is a strategic plan, not a results report. As of April 2026:

- v0.1.0 is live on PyPI with 13 tests and a CI-green build
- Downloads are attributable to the CTE team and a small number of early adopters
- Zero revenue has been generated from the commercial offer
- The NIST citations, CAISI acknowledgment, and Zenodo preprints are credibility assets, not traction metrics
- HRAO-E's 95-day production pedigree validates the underlying framework, not the library's fit for the general market

The 18-month roadmap above is directionally correct if the WHY-layer framing resonates with the target developer community and if execution against Phase 1 milestones is disciplined. It will be wrong in specific ways that are not yet known. The amendment protocol that governs agents also governs this document: when evidence contradicts the plan, update the plan.

---

## Links

- **GitHub:** [CognitiveThoughtEngine/constitutional-agent-governance](https://github.com/CognitiveThoughtEngine/constitutional-agent-governance)
- **PyPI:** [pypi.org/project/constitutional-agent](https://pypi.org/project/constitutional-agent/)
- **35-Check Governance Checklist:** [checklist/CONSTITUTIONAL_GOVERNANCE_CHECKLIST.md](checklist/CONSTITUTIONAL_GOVERNANCE_CHECKLIST.md)
- **agenthustler Case Study Audit:** [examples/agenthustler_audit.md](examples/agenthustler_audit.md)
- **Research Preprints:** [zenodo.18217577](https://doi.org/10.5281/zenodo.18217577) · [zenodo.19343034](https://doi.org/10.5281/zenodo.19343034) · [zenodo.19343108](https://doi.org/10.5281/zenodo.19343108)
- **Constitutional Governance Review:** [cteinvest.com](https://cteinvest.com)

---

*This roadmap is a living document. It will be amended through the same formal process that governs the library itself: evidence-backed proposals, explicit rationale, and documented ratification. The version history in git is the amendment log.*

*Last updated: April 2026 — v0.1.0 launch*
