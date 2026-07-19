# Release runbook — constitutional-agent

Deterministic, human-gated release process. **The artifact validated by the release
workflow and the artifact published are the same bytes**, and the build is
**reproducible on the pinned Ubuntu/Linux release platform and toolchain**.

## Guarantees this process provides

- **Reproducible on the release platform.** Builds pin `build`/`setuptools`/`wheel`/
  `twine` exactly, set `SOURCE_DATE_EPOCH` from the tagged commit, and normalize the
  sdist (`scripts/normalize_sdist.py`). On the pinned Ubuntu/Linux runner, CI builds
  **twice in separate clean directories** and fails unless both wheel and sdist
  SHA-256 match. *(Reproducibility is platform-scoped: rebuilding on the same
  Ubuntu/Linux runner with the pinned toolchain reproduces the exact bytes; builds
  on other operating systems may differ in zip metadata such as file-mode bits.)*
- **Validated == published.** The release workflow builds once, validates *those*
  bytes (`twine check`, `scripts/check_package.py`, clean-wheel install + smoke),
  and publishes *those same* bytes — there is **no rebuild** before upload.
- **Exact-tag enforcement.** `release.yml` only proceeds for an **annotated** tag of
  the form `vX.Y.Z` that **equals the packaged version** and whose commit is exactly
  the checked-out commit. Branches, raw SHAs, and lightweight tags are rejected.
- **Human approval.** Publishing runs in the protected `pypi` GitHub environment via
  **PyPI Trusted Publishing (OIDC)** — no API token in the repo. `environment: pypi`
  only enforces approval **once required reviewers are configured** (see step 3).

## Order of operations (do NOT skip or reorder)

1. **Merge** the release-closure PR into `master`. Nothing is tagged yet; the
   CHANGELOG still says `UNRELEASED` and the notes are still `-DRAFT`.
2. **Release-prep PR (no direct commit to `master`).** Open a *small* PR that:
   - sets the CHANGELOG header `## [0.7.0] - UNRELEASED` → `## [0.7.0] - YYYY-MM-DD`
     (the actual date), and
   - renames `docs/release/v0.7.0-release-notes-DRAFT.md` →
     `docs/release/v0.7.0-release-notes.md` and drops the DRAFT banner.

   Let CI (`release-validation.yml`) validate it, review it, and **merge** it. This
   keeps the release-state change on the reviewed history, not a direct push.
3. **Verify release protections (read-only) — do this before tagging:**
   - the GitHub `pypi` environment exists **and has required reviewers**
     (`gh api repos/<owner>/<repo>/environments/pypi` → `protection_rules` must be
     non-empty); and
   - **PyPI Trusted Publishing** is configured for this repository / `release.yml` /
     `pypi` environment (PyPI project → *Publishing* → pending/active publisher).

   Do not proceed until both are confirmed.
4. **Tag the exact merge commit** of the release-prep PR:
   `git tag -a v0.7.0 <merge-commit> -m "..."` (annotated), then `git push origin v0.7.0`.
   This triggers `release.yml`: exact-tag verification → deterministic double-build →
   validate → **wait for manual approval** → Trusted-Publish the exact artifacts.
   Record the SHA-256 checksums it prints.
5. **Verify reproducibility (optional).** On a clean checkout of the tag on
   Ubuntu/Linux: `pip install build==1.5.0 setuptools==83.0.0 wheel==0.47.0`,
   `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct) python -m build --no-isolation`,
   `python scripts/normalize_sdist.py dist/*.tar.gz`, `sha256sum dist/*` — must equal
   the published hashes.
6. **Verify from PyPI.** In a fresh environment, `pip install constitutional-agent==0.7.0`
   and run `python scripts/release_smoke.py` (or `python -m constitutional_agent`).
7. **Create the GitHub release** from the tag using the finalized notes, and
   **attach the checksums + validated artifacts** so the release notes' claim
   ("the SHA-256 checksums are published with the release") is operationally true —
   `release.yml` only uploads them as *workflow artifacts*, which are not attached
   to the public release automatically:
   - From the successful tag-triggered `release.yml` run, download the
     **`release-checksums`** artifact (`SHA256SUMS.txt`) and the **`release-dist`**
     artifact (the exact validated `constitutional_agent-0.7.0-py3-none-any.whl`
     and `constitutional_agent-0.7.0.tar.gz`).
   - **Attach `SHA256SUMS.txt`** to the public GitHub v0.7.0 release, and attach the
     exact validated wheel and sdist from `release-dist` as release assets.
   - **Record the tag commit SHA and the `release.yml` workflow run ID** in the
     release notes.
8. **Apply the v0.6 correction notice** — append
   `docs/release/v0.6.0-correction-notice-DRAFT.md` (drop the DRAFT banner) to the
   live v0.6.0 GitHub release **only after** steps 4–6 confirm v0.7.0 is public and
   verified. Keep it a draft until then.
9. **Only then** proceed to any downstream promotion (e.g., Part 3).

## Never

- Never tag a commit whose CHANGELOG still says `UNRELEASED`.
- Never set the release date or finalize notes by a direct push to `master` — use the
  reviewed release-prep PR (step 2).
- Never rebuild between validation and upload — publish the validated artifacts.
- Never tag before confirming the `pypi` environment has required reviewers and PyPI
  Trusted Publishing is configured.
- Never edit the live v0.6.0 release before v0.7.0 is published and verified.
