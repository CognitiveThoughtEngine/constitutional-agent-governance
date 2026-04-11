# constitutional-agent Roadmap

**Current stable:** v0.4.0

---

## v0.4.0 — Persistence & Observability (stable — 2026-04-11)

The stable release locks the persistence and observability API surface. No breaking changes from v0.4.0b3.

### Included in beta

- `on_evaluate` callback hook — fire side-effects on every evaluation
- `on_amendment_ratified` callback hook — trigger downstream on governance events
- `history` property — in-memory evaluation log (timestamp, context snapshot, result)
- `Constitution.load("governance.yaml")` — file-based config with YAML hard constraints
- `required: true` on YAML HC entries — absent key treated as violation
- Full YAML operator coverage: `eq`, `ne`, `lt`, `lte`, `gt`, `gte`
- Strict mode with `_KNOWN_GATE_METRICS` overlap detection
- `fria_evidence(context)` — EU AI Act Article 27 FRIA output; `fria.py` module with `FRIAEvidence`, `fria_summary()`, `fria_narrative()`
- 160 tests, 97% coverage, mypy strict, Python 3.11–3.13

### What the beta is testing

1. **Callback API shape** — are `on_evaluate` and `on_amendment_ratified` sufficient for real integrations, or do callers need richer event metadata?
2. **YAML HC expressiveness** — do the 6 operators cover real org use cases, or is `range` / `regex` needed?
3. **History fidelity** — is a full context snapshot per evaluation the right granularity, or is it too noisy at high frequency?

Feedback on these three questions shapes what locks into v0.4.0 stable.

---

## v0.5.0 — Multi-Agent Coordination

Governance for systems of agents, not just single agents.

### Planned features

- **`Coalition` class** — evaluate a shared Constitution across N agents; aggregate gate results with configurable quorum rules (all-PASS, majority-PASS, any-FAIL)
- **Gate delegation** — agent A defers a specific gate to agent B's evaluation result (e.g., EpistemicGate from a dedicated verifier agent)
- **Shared amendment log** — ratification proposals visible and votable across a coalition
- **Cross-agent HC enforcement** — hard constraints that span agent boundaries (e.g., "no two agents may spend simultaneously")

### Research question

The core design question is whether Coalition governance should be pull-based (each agent queries a central evaluator) or push-based (agents publish gate results, coalition aggregates). Pull is simpler; push is more fault-tolerant. Production data from the HRAO-E system (54 agents) informs this choice — the current implementation uses a push-adjacent pattern via cron.

---

## v0.6.0 — Adaptive Thresholds

Gates that learn from evaluation history.

### Planned features

- **Threshold advisor** — given N evaluations, suggest threshold adjustments that would have caught the top-K misses
- **Calibration mode** — run gates in observe-only mode for M days, then propose initial thresholds based on observed distribution
- **Drift detection** — alert when a metric's rolling mean crosses a threshold band, before a gate FAIL occurs
- **Amendment auto-proposal** — when drift is detected, automatically draft an amendment for human ratification (never auto-ratify)

### Hard constraint

Amendment auto-proposal generates a draft in PENDING state. Human ratification is always required — no adaptive threshold change may be ratified autonomously. This is a hard constraint in the library's own governance model.

---

## v1.0.0 — Production Stable

Criteria for 1.0:

- [ ] Coalition API stable (v0.5.0 shipped and battle-tested)
- [ ] Adaptive thresholds validated against ≥2 real deployments
- [ ] Persistence backend pluggable (default: in-memory; adapters: SQLite, PostgreSQL)
- [ ] OpenTelemetry span export for gate evaluations
- [ ] Zero breaking changes since v0.4.0 stable
- [ ] Security audit (third-party)
- [ ] Documentation site (not just docstrings)

---

## Not Planned

Items explicitly out of scope to keep the library focused:

- **LLM integration** — constitutional-agent evaluates metrics, not LLM outputs. LLM output evaluation belongs in a separate layer.
- **UI / dashboard** — the library emits structured data; visualization is the caller's responsibility.
- **Cloud-hosted evaluation** — evaluation runs in the caller's process. No SaaS offering planned.
- **Preset governance templates** — the six-gate architecture is opinionated enough. Domain-specific presets belong in downstream packages.

---

## Versioning Policy

- **Patch (0.x.Y):** Bug fixes, test additions, docstring improvements. No API changes.
- **Minor (0.X.0):** New features, backward-compatible. Deprecation warnings for anything being removed.
- **Major (X.0.0):** Breaking API changes. Minimum 6-month deprecation window from the last minor release.

Pre-1.0, minor versions may include small breaking changes with a changelog entry and migration note.
