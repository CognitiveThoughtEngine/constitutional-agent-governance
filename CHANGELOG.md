# Changelog

All notable changes to `constitutional-agent` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.7.0] - 2026-07-18

Turns the governance thesis from *recorded* into *enforced*: the amendment
protocol now authorizes ratifications instead of accepting an unverified string,
the FRIA model stops overclaiming Article 27 coverage, and the docs are
reconciled to figures traceable to this repository.

### Added — Enforced amendment authority & separation of duties (`authority` module)

- **`AuthorityRegistry`** — stable `principal_id -> AuthorityLevel` map
  (`PROPOSER` < `RATIFIER` < `CONSTITUTIONAL_AUTHORITY`). `principal_id` is an
  opaque, stable id (canonicalized for comparison), never a display name. A
  registry that ships with zero root authorities is rejected at construction.
- **`IdentityVerifier`** — optional deployer-supplied authentication callback that
  binds an asserted principal to an external IdP (Entra / Okta / IAM / mTLS / a
  signed token). It may only add restriction; it can never bypass separation of
  duty or authority-level rules. Callback failure, exception, timeout, or a
  malformed (non-`True`) response all **fail closed**.
- **`AmendmentRecord` + pluggable `AmendmentStore`** (`InMemoryAmendmentStore`,
  durable `SqliteAmendmentStore`) — an audit-grade, monotonically-versioned log of
  every RATIFIED and REJECTED decision, capturing proposer/ratifier ids and levels
  at decision time, identity-assurance mode, the ACTUAL affected paths,
  before/after constitution hashes, and evidence retained scrubbed + by SHA-256
  hash. **Credentials, tokens, and secrets are never stored** (`scrub_evidence`).

### Changed — `Constitution.ratify_amendment` is now enforced (BREAKING)

- Ratification enforces (all fail-closed): canonical `proposer_id != ratifier_id`;
  ratifier must be registered; ordinary amendments require `RATIFIER`+; changes
  touching **hard constraints or the authority registry** require
  `CONSTITUTIONAL_AUTHORITY` — determined from the **actual affected config paths,
  not** the proposer's label; a registry change can never strand the system with
  zero root authorities. Ratifications are serialized (reentrant lock) so the
  last-authority guard is atomic under concurrent ratifiers.
- New `Constitution` kwargs: `authority_registry`, `identity_verifier`,
  `amendment_store`; new `ratify_amendment(..., asserted_identity=...)` keyword.
  New properties: `amendment_records`, `constitution_version`, `authority_registry`.
- **Migration:** with **no** `authority_registry`, the constitution runs in a
  legacy mode — separation of duty is still enforced and ordinary amendments with
  distinct proposer/ratifier still ratify, but any change touching hard
  constraints or the registry is refused fail-closed. Callers that previously
  relied on `ratify_amendment` returning `True` unconditionally, that let a
  proposer ratify their own change, or that expected hard-constraint/registry
  changes to apply without a configured authority must supply an
  `authority_registry`. Existing tests and simple gate-threshold amendments are
  unaffected.

### Changed — FRIA model corrected (`fria` module)

- The six built-in categories are relabeled **internal governance-evidence
  categories** (`GovernanceEvidenceCategory`) — they were previously mislabeled as
  "the six Article 27 categories." `FRIACategory` remains as a backwards-compatible
  alias.
- Added a separate **Article 27(1) crosswalk** (`Article27Element`,
  `generate_article27_crosswalk`, `fria_support_package`) over the actual 27(1)
  elements, each classified by evidence source (auto-derived / deployer-supplied /
  missing) with a legal-review status. Operational gate evidence cannot populate
  intended use, duration/frequency, affected groups, or complaint arrangements
  without deployer input, and the crosswalk marks that honestly.
- The output is explicitly a **FRIA-support package**, not a complete or legally
  sufficient Article 27 FRIA.

### Fixed — documentation reconciled to traceable figures

- Removed the unqualified "every vendor-neutral engine is stateless" claim;
  replaced with a **dated (July 2026) documentation-review** statement plus an
  evidence matrix (product | docs reviewed | retains state? | cross-session
  aggregate-risk decision?).
- Qualified the additive risk example so it no longer implies risk sums linearly.
- Corrected the mislabeled "1,929 governance evaluations" (it was a test-function
  count, not evaluations) and dropped un-traceable production counts. Library
  figures are now the real ones from this repo: **218 test functions across 6
  modules** (223 collected), **12 hard constraints**, **6 gates**, **0** built-in
  ratified amendments.
- "Cited in NIST AI 800-2 submissions" → "informed three public-comment
  submissions concerning NIST AI 800-2 (CAISI acknowledged receipt)."

### Tests

- +44 tests: `test_amendment_authority.py` (34 functions covering every
  enforcement path + the eight reviewer edge cases) and `test_fria_article27.py`
  (10). Full suite: **223 passing**.

---

## [0.6.0] - 2026-07-16

### Added — Cross-Session Risk Composition (the stateful layer)

The six gates are memoryless: each `evaluate()` scores one decision and forgets
it. Every vendor-neutral governance engine shipped in H1 2026 (Microsoft ACS,
Galileo Agent Control, Runlayer, NVIDIA OpenShell) is stateless the same way —
and shares the same blind spot: an agent can pass every individual gate and
still be dangerous over a sequence. This release adds the layer that remembers.

- **`composition` module** — accumulates a scalar risk weight per decision,
  keyed by subject, and composes it across a rolling window. Escalates the
  system state when the *accumulation* crosses a threshold even though every
  contributing decision passed on its own.
- **`ComposedEvaluator`** — wraps `SixGateEvaluator`; returns the more severe of
  the per-call verdict and the composed verdict. Can push a system every gate
  rated RUN into THROTTLE or FREEZE. `.escalated` flags when the sequence tripped
  what no single decision did.
- **`AccumulatedRiskComposer`** — two detectors: accumulated magnitude (many
  small risks add up) and sustained elevation (a slow burn that never spikes).
  Optional exponential time-decay via `half_life_seconds`. Clock is injectable
  for deterministic evaluation.
- **Pluggable `RiskStore`** — `InMemoryRiskStore` (default, non-persistent) and
  `SqliteRiskStore` (stdlib, durable) so composition spans process restarts and
  sessions. Bring your own Postgres adapter by satisfying the protocol.
- **`CompositionResult`** carries the exact events that drove it — the risk
  trajectory is the audit evidence.
- 24 new tests (composition), including the marquee case: N sub-threshold
  decisions that per-call gating passes but composition catches, and cross-
  session persistence across composer instances sharing a SQLite file.

Backward compatible: no changes to existing gate or `Constitution` APIs.

---

## [0.5.0] - 2026-04-17

### Fixed

- Replaced hardcoded PyPI badge with dynamic shield (`img.shields.io/pypi/v`)
- Removed stale "current published version is 0.3.2" note from README
- Fixed requirements line: removed pydantic reference (removed in v0.3.0)
- Fixed test count: 150 test functions across 3 test modules (was 77/2)
- Fixed FRIA transparency mapping: HC-4/11 (HC-15 does not exist)
- Fixed case study metric key: `hours_since_last_execution` (was `hours_since_settlement_confirmation`)
- Fixed ROADMAP test count: 150 tests (was 160)
- Fixed SECURITY.md supported versions table (was 0.1.x)
- Updated HRAO-E test count in `__init__.py` docstring to 1,929 (matching README)
- Removed dead `password` line from publish.yml (OIDC trusted publishing is used)

### Added

- Python 3.13 classifier in pyproject.toml
- CHANGELOG entries for v0.4.1 and FRIA feature documentation

---

## [0.4.1] - 2026-04-14

### Added

- CLI demo entry point: `python -m constitutional_agent`
- LangGraph, CrewAI, and OpenAI Agents SDK integration quickstarts in README

### Fixed

- Ruff E702 lint errors in `__main__.py`
- Excluded CLI entry point from coverage threshold

### Changed

- README: surfaced Quick Start and social proof above the fold
- README: softened vendor framing to "complements" (reviewer feedback)

---

## [0.4.0] - 2026-04-11

Stable release — same functionality as v0.4.0b3. Production-validated: CGST self-assessment 63/100.

No breaking changes from v0.4.0b3. Promoting from beta to stable after validation period.

---

## [0.3.0] - 2026-04-09

### Fixed (critical-review issues)

- **Issue 1 (HIGH) — YAML hard constraints silently ignored.** `Constitution.__init__`
  now parses `config.get("hard_constraints", [])` and appends them to the builtin
  HC list. Supports operators `eq`, `ne`, `lt`, `lte`, `gt`, `gte`. Builtins are
  never replaced — only extended. Added `_parse_yaml_hard_constraints` static method.

- **Issue 2 (HIGH) — Amendment ratification had no actual effect.** `AmendmentProposal`
  now accepts an optional `changes: dict` parameter. `propose_amendment()` passes it
  through. `ratify_amendment()` deep-merges `changes` into `self._config` and rebuilds
  the evaluator immediately via `_build_evaluator`. Amendments now take effect the
  moment they are ratified.

- **Issue 3 (MEDIUM) — `enabled: false` gate config ignored.** `_build_evaluator` now
  reads `g.get(section, {}).get("enabled", True)` for each gate. Disabled gates are
  replaced with a `_DisabledGate` stub that always returns `GateResult(PASS, "Disabled
  via governance.yaml")`. Added `_DisabledGate` private class in `constitution.py`.
  `SixGateEvaluator.__init__` updated to accept `Any` typed gate slots.

- **Issue 4 (DESIGN) — Missing metrics default to PASS.** Added `strict_mode: bool =
  False` to `Constitution.__init__()` and an optional `strict_mode` parameter to
  `evaluate()`. When `strict_mode` is active and `context` is empty, `evaluate()`
  immediately returns `THROTTLE` with an explanatory summary. Call-site parameter
  overrides instance-level setting.

- **Issue 6 (MEDIUM) — No persistence layer.** Added `on_evaluate: Optional[Callable]`
  and `on_amendment_ratified: Optional[Callable]` parameters to `Constitution.__init__`.
  `_record_evaluation()` calls `on_evaluate(result)` if set. `ratify_amendment()` calls
  `on_amendment_ratified(amendment.to_dict())` if set.

- **Issue 7 (LOW) — Pydantic required but never used.** Removed `pydantic>=2.6,<3`
  from `[project] dependencies` in `pyproject.toml`. The library uses only stdlib
  dataclasses and PyYAML.

- **Issue 8 (LOW-MEDIUM) — No input validation on metrics.** Added `_validate_metrics`
  static method called at the start of `evaluate()`. Issues `UserWarning` for any
  known 0-1 bounded metric outside `[0.0, 1.0]` and any known positive metric below
  zero. Does not raise — warns only.

- **Issue 9 (version mismatch).** `__init__.py` updated from `0.1.0` to `0.3.0`.
  `pyproject.toml` updated from `0.2.0` to `0.3.0`.

- **Issue 10 — Multiple gate violations: only first reported.** Added
  `blocking_gates: list[GateResult]` field to `ConstitutionResult` (default empty
  list). Populated with all FAIL gates in `evaluate()`. `_build_summary` now
  mentions all failing gate names when multiple gates FAIL simultaneously.
  `blocking_gate` (singular) retained for backwards compatibility.

### Added

- `_DisabledGate` — private stub gate in `constitution.py` that always returns PASS.
  Used when a gate has `enabled: false` in governance.yaml.
- `_parse_yaml_hard_constraints(hc_list)` — static method on `Constitution`.
- `_validate_metrics(context)` — static method on `Constitution`.
- `_deep_merge(base, override)` — static method on `Constitution`.
- `AmendmentProposal.changes` attribute and `to_dict()` includes `"changes"` key.
- 26 new tests covering all fixed issues (103 total, 0 failed).

---

## [0.2.0] — 2026-04-08

### Added

- **YAML threshold configuration** — `Constitution.load("governance.yaml")` now
  applies gate threshold overrides from the YAML file. Previously all thresholds
  were hardcoded regardless of YAML content. All six gates accept keyword
  arguments to override any threshold; `_build_evaluator` maps YAML keys to
  gate constructors.

- **`dry_run=True` on `Constitution.evaluate()`** — evaluates all gates and
  hard constraints without short-circuiting on violations and without recording
  to evaluation history. Returns what *would* happen if enforcement were active.
  Use this to calibrate thresholds against real data before enabling enforcement.

- **`__init__` on all six gate classes** — `EpistemicGate`, `RiskGate`,
  `GovernanceGate`, `EconomicGate`, `AutonomyGate`, and `ConstitutionalGate`
  now accept keyword-only threshold arguments. All default to production-validated
  values. Fully backwards-compatible — existing code using `EpistemicGate()`
  with no arguments continues to work unchanged.

- **Issue templates** — three structured templates for GitHub issues: bug report
  (with fail-open severity flag), gate threshold proposal (requires evidence
  field), hard constraint proposal (requires maintainer sign-off).

- **`SECURITY.md`** — documents critical fail-open vulnerabilities (24h ack /
  72h fix SLA) vs standard bugs, and the fail-CLOSED principle.

- **`CONTRIBUTING.md`** — contribution process: gate threshold changes require
  evidence, HC changes require maintainer sign-off, fail-CLOSED principle for
  safety code.

- **`ROADMAP.md`** — 18-month strategic roadmap with four phases, competitive
  moat analysis, monetization path, key risks, metrics dashboard, and decision
  gates for phase advancement.

### Changed

- Test coverage expanded from 13 to 65+ tests across all six gates, all twelve
  hard constraints, YAML loading, `dry_run` mode, amendment protocol, and
  `summary_report`.

- CI now runs `ruff check` before tests on both Python 3.11 and 3.12.

### Fixed

- `Constitution.load()` previously loaded governance.yaml but ignored all
  threshold values — `_build_evaluator` returned hardcoded defaults regardless
  of YAML content. Now wires YAML thresholds to gate constructors.

---

## [0.1.0] — 2026-04-08

### Added

- Initial release. Six constitutional gates: `EpistemicGate`, `RiskGate`,
  `GovernanceGate`, `EconomicGate`, `AutonomyGate`, `ConstitutionalGate`.
- 12 hard constraints (HC-1 through HC-12) enforced in code, not YAML.
- `Constitution.from_defaults()` and `Constitution.load()`.
- `propose_amendment()` and `ratify_amendment()` protocol.
- `PRE_REVENUE` evaluation mode for `EconomicGate`.
- `SixGateEvaluator` composite system state: COMPOUND / RUN / THROTTLE / FREEZE.
- Production-extracted from HRAO-E Constitutional Framework (95 days, 52 agents,
  64 amendments, real economic pressure).
- MIT license.
