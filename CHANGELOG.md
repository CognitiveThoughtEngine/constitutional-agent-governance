# Changelog

All notable changes to `constitutional-agent` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
