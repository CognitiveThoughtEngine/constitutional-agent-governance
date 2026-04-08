# Changelog

All notable changes to `constitutional-agent` are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
