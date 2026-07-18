"""
Constitutional Agent — Amendment Authority & Separation of Duties
=================================================================

The amendment protocol is only meaningful if it is *enforced*. Recording an
unverified ``ratified_by`` string, letting a proposer ratify their own change, or
checking no authority at all turns constitutional governance into a suggestion.
This module supplies the primitives the :class:`~constitutional_agent.constitution.Constitution`
uses to enforce the protocol:

- :class:`AuthorityLevel` — an ordered authority ladder (PROPOSER < RATIFIER <
  CONSTITUTIONAL_AUTHORITY).
- :class:`AuthorityRegistry` — a stable ``principal_id -> AuthorityLevel`` map.
  ``principal_id`` is an opaque, stable identifier (a subject claim, a service
  account id, a key fingerprint) — **not** a human-readable display name.
- :class:`AmendmentRecord` — the durable, audit-grade record of a ratification
  or rejection decision.
- :class:`AmendmentStore` / :class:`InMemoryAmendmentStore` /
  :class:`SqliteAmendmentStore` — pluggable persistence for the amendment log,
  mirroring the ``RiskStore`` pattern in :mod:`constitutional_agent.composition`.
- :func:`scrub_evidence` — redacts secret-shaped keys and returns a safe hash so
  supporting evidence is retained *by reference* without ever storing credentials,
  raw tokens, or secrets.

**Trust boundary.** The library authorizes a *registered* principal according to
constitutional policy. It does **not** prove the caller actually controls that
identity. Deployers can supply an authentication callback (see
:class:`IdentityVerifier`) to bind the asserted principal to Entra / Okta / IAM /
mTLS / a signed token / etc. Without such a callback, an amendment decision is
recorded as ``caller_asserted`` — authorized by policy, but not externally
authenticated.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import IntEnum
from typing import Any, Callable, Optional, Protocol, runtime_checkable

__all__ = [
    "AuthorityLevel",
    "AuthorityRegistry",
    "IdentityVerifier",
    "AmendmentRecord",
    "AmendmentStore",
    "InMemoryAmendmentStore",
    "SqliteAmendmentStore",
    "scrub_evidence",
    "canonical_principal",
]


# ---------------------------------------------------------------------------
# Principal-id canonicalization
# ---------------------------------------------------------------------------

def canonical_principal(principal_id: Any) -> str:
    """
    Canonical form of a ``principal_id`` for comparison and registry lookup.

    Strips leading/trailing whitespace, collapses internal whitespace runs to a
    single space, and case-folds. This makes separation-of-duty and registry
    membership robust to trivial presentation differences — an attacker cannot
    slip past the proposer != ratifier rule by appending a space or flipping the
    case of the same identity. Principals are still treated as opaque; this is a
    normalization, not a parse of any human-readable structure.

        canonical_principal("  Alice ") == canonical_principal("alice")  # True
    """
    return " ".join(str(principal_id).split()).casefold()


# ---------------------------------------------------------------------------
# Authority ladder
# ---------------------------------------------------------------------------

class AuthorityLevel(IntEnum):
    """
    Ascending authority required to act on the constitution.

    Ordering is meaningful: a principal may perform any action requiring their
    level or lower.

        PROPOSER                 — may submit amendment proposals.
        RATIFIER                 — may ratify *ordinary* amendments (gate
                                   thresholds, documentation, config that does
                                   not touch root governance).
        CONSTITUTIONAL_AUTHORITY — required for hard-constraint changes,
                                   authority-registry changes, and any other
                                   root governance change. The highest level.
    """

    PROPOSER = 1
    RATIFIER = 2
    CONSTITUTIONAL_AUTHORITY = 3

    @classmethod
    def coerce(cls, value: Any) -> "AuthorityLevel":
        """
        Coerce a str / int / AuthorityLevel into an AuthorityLevel.

        Accepts the enum, its integer value, or its (case-insensitive) name so
        registries can be declared in YAML as human-friendly strings.
        """
        if isinstance(value, AuthorityLevel):
            return value
        if isinstance(value, bool):  # guard: bool is an int subclass
            raise ValueError(f"Invalid authority level: {value!r}")
        if isinstance(value, int):
            return cls(value)
        if isinstance(value, str):
            key = value.strip().upper()
            if key in cls.__members__:
                return cls[key]
            # Allow numeric strings.
            if key.isdigit():
                return cls(int(key))
        raise ValueError(
            f"Invalid authority level: {value!r}. "
            f"Expected one of {[m.name for m in cls]} (or their integer values)."
        )


# ---------------------------------------------------------------------------
# Authority registry
# ---------------------------------------------------------------------------

class AuthorityRegistry:
    """
    A stable ``principal_id -> AuthorityLevel`` map.

    The initial registry is *trusted deployer-supplied configuration* — it is the
    bootstrap root of trust. After construction, any change to the registry must
    flow through the amendment process and requires CONSTITUTIONAL_AUTHORITY
    (enforced by :class:`~constitutional_agent.constitution.Constitution`).

    ``principal_id`` values are opaque and stable. They are compared exactly and
    are never treated as human-readable names.
    """

    def __init__(self, mapping: Optional[dict[str, Any]] = None) -> None:
        self._levels: dict[str, AuthorityLevel] = {}
        for pid, level in (mapping or {}).items():
            if level is None:
                continue
            self._levels[canonical_principal(pid)] = AuthorityLevel.coerce(level)
        # A registry that ships with zero root authorities cannot authorize the
        # very changes (hard constraints / registry) it is meant to gate. That is
        # a fail-closed dead end; reject it at construction so the deployer fixes
        # the bootstrap config instead of discovering it at ratification time.
        if self._levels and not self._has_root():
            raise ValueError(
                "authority_registry must contain at least one "
                "CONSTITUTIONAL_AUTHORITY principal (the root of trust)."
            )

    def _has_root(self) -> bool:
        return any(
            lvl >= AuthorityLevel.CONSTITUTIONAL_AUTHORITY
            for lvl in self._levels.values()
        )

    def root_count(self) -> int:
        """Number of principals at CONSTITUTIONAL_AUTHORITY or higher."""
        return sum(
            1 for lvl in self._levels.values()
            if lvl >= AuthorityLevel.CONSTITUTIONAL_AUTHORITY
        )

    def contains(self, principal_id: str) -> bool:
        return canonical_principal(principal_id) in self._levels

    def level_of(self, principal_id: str) -> Optional[AuthorityLevel]:
        """Return the principal's level, or None if they are not registered.

        Lookup is by canonical principal id, so whitespace/case variants of the
        same registered identity resolve to the same level.
        """
        return self._levels.get(canonical_principal(principal_id))

    def snapshot(self) -> dict[str, int]:
        """Deterministic ``principal_id -> int`` view, for hashing/audit."""
        return {pid: int(lvl) for pid, lvl in sorted(self._levels.items())}

    def with_changes(self, changes: dict[str, Any]) -> "AuthorityRegistry":
        """
        Return a NEW registry with ``changes`` applied (does not mutate self).

        ``changes`` maps ``principal_id`` to a new level, or to ``None`` to
        remove the principal entirely. Used both to simulate a proposed registry
        amendment (for the last-authority guard) and to apply an approved one.
        """
        merged: dict[str, Any] = {
            pid: int(lvl) for pid, lvl in self._levels.items()
        }
        for pid, level in changes.items():
            spid = canonical_principal(pid)
            if level is None:
                merged.pop(spid, None)
            else:
                merged[spid] = level
        # Bypass __init__'s root guard here: the caller (Constitution) performs
        # the last-authority check explicitly and returns a precise reason, so a
        # simulated no-root registry must be constructable to be inspected.
        reg = AuthorityRegistry.__new__(AuthorityRegistry)
        reg._levels = {
            canonical_principal(pid): AuthorityLevel.coerce(lvl)
            for pid, lvl in merged.items()
            if lvl is not None
        }
        return reg

    def __len__(self) -> int:
        return len(self._levels)


# ---------------------------------------------------------------------------
# Identity verification callback (deployer-supplied authentication binding)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class IdentityVerifier:
    """
    A deployer-supplied hook that binds an asserted ``principal_id`` to an
    external identity system (Entra / Okta / IAM / mTLS / signed token / ...).

    Attributes:
        name:   Stable label recorded in the amendment record when verification
                passes (e.g. "entra", "okta", "mtls"). Never a secret.
        verify: ``verify(principal_id, asserted_identity) -> bool``. Returns True
                if the caller is authenticated *as* ``principal_id``. Returning
                False — or raising — rejects the ratification (fail-closed).

    The verifier may only *add* restriction. It cannot bypass separation-of-duty
    or authority-level rules: those are checked independently and a passing
    callback never overrides a policy rejection.
    """

    name: str
    verify: Callable[[str, Optional[dict[str, Any]]], bool]


# ---------------------------------------------------------------------------
# Evidence handling — retain by safe reference, never store secrets
# ---------------------------------------------------------------------------

_SECRET_KEY_MARKERS: tuple[str, ...] = (
    "password", "passwd", "secret", "token", "api_key", "apikey", "key",
    "credential", "authorization", "auth", "bearer", "private", "signature",
    "session", "cookie", "otp", "pin", "ssn",
)

_REDACTED = "[REDACTED]"


def _looks_secret(key: str) -> bool:
    k = key.lower()
    return any(marker in k for marker in _SECRET_KEY_MARKERS)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            out[k] = _REDACTED if _looks_secret(str(k)) else _redact(v)
        return out
    if isinstance(value, (list, tuple)):
        return [_redact(v) for v in value]
    return value


def scrub_evidence(
    evidence: Optional[dict[str, Any]],
) -> tuple[Optional[dict[str, Any]], Optional[str]]:
    """
    Return ``(scrubbed_evidence, evidence_hash)``.

    ``scrubbed_evidence`` has any secret-shaped keys redacted so the amendment
    record can retain useful audit context without persisting credentials, raw
    tokens, or secrets. ``evidence_hash`` is a SHA-256 over the *original*
    canonical evidence, so the full artifact can be matched by reference even
    though its sensitive values are never stored.

    Returns ``(None, None)`` when no evidence is supplied.
    """
    if evidence is None:
        return None, None
    canonical = json.dumps(evidence, sort_keys=True, default=str).encode("utf-8")
    evidence_hash = hashlib.sha256(canonical).hexdigest()
    scrubbed = _redact(evidence)
    return scrubbed, evidence_hash


# ---------------------------------------------------------------------------
# Amendment record + durable store
# ---------------------------------------------------------------------------

@dataclass
class AmendmentRecord:
    """
    Durable, audit-grade record of a single amendment decision.

    Preserves who proposed and who ratified/rejected, their authority levels *at
    the moment of decision*, how the ratifier's identity was assured, the ACTUAL
    configuration paths the change touched (derived from the change payload — not
    the proposer's self-declared label), a safe reference to the supporting
    evidence, the before/after constitution hashes, the resulting monotonic
    version, and the human-readable decision reason.

    No credentials, raw tokens, or secrets are ever stored: evidence is retained
    scrubbed + by hash (see :func:`scrub_evidence`).
    """

    amendment_id: str
    outcome: str  # "RATIFIED" | "REJECTED"
    proposer_id: str
    ratifier_id: str
    proposer_level: Optional[str]
    ratifier_level: Optional[str]
    required_authority: str
    identity_assurance: str  # "caller_asserted" | "externally_verified"
    identity_verifier: Optional[str]
    affected_paths: list[str]
    proposed_at: Optional[str]
    decided_at: str
    evidence: Optional[dict[str, Any]]
    evidence_hash: Optional[str]
    constitution_hash_before: str
    constitution_hash_after: str
    constitution_version: int
    reason: str
    description: str = ""
    changes: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "amendment_id": self.amendment_id,
            "outcome": self.outcome,
            "proposer_id": self.proposer_id,
            "ratifier_id": self.ratifier_id,
            "proposer_level": self.proposer_level,
            "ratifier_level": self.ratifier_level,
            "required_authority": self.required_authority,
            "identity_assurance": self.identity_assurance,
            "identity_verifier": self.identity_verifier,
            "affected_paths": list(self.affected_paths),
            "proposed_at": self.proposed_at,
            "decided_at": self.decided_at,
            "evidence": self.evidence,
            "evidence_hash": self.evidence_hash,
            "constitution_hash_before": self.constitution_hash_before,
            "constitution_hash_after": self.constitution_hash_after,
            "constitution_version": self.constitution_version,
            "reason": self.reason,
            "description": self.description,
            "changes": self.changes,
        }


@runtime_checkable
class AmendmentStore(Protocol):
    """
    Pluggable persistence for the amendment log.

    Mirrors the ``RiskStore`` pattern: the default store is in-memory and lost on
    restart; supply a durable implementation (:class:`SqliteAmendmentStore`, or a
    Postgres adapter) to make the amendment ledger survive process restarts. Both
    RATIFIED and REJECTED decisions are recorded — the rejection trail is itself
    governance evidence.
    """

    def record(self, record: dict[str, Any]) -> None:
        """Persist one amendment decision record."""
        ...

    def all(self) -> list[dict[str, Any]]:
        """Return every recorded decision, oldest first."""
        ...


class InMemoryAmendmentStore:
    """Default in-process amendment store. Fast, zero-dependency, non-persistent."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def record(self, record: dict[str, Any]) -> None:
        self._records.append(dict(record))

    def all(self) -> list[dict[str, Any]]:
        return list(self._records)


class SqliteAmendmentStore:
    """
    Durable amendment store backed by SQLite (stdlib, no dependencies).

    Makes the amendment ledger cross-session: decisions written in one process
    are visible to the next. Pass ``":memory:"`` for an ephemeral database.

        store = SqliteAmendmentStore("amendments.db")
        c = Constitution(config, amendment_store=store, authority_registry=reg)
    """

    def __init__(self, path: str = ":memory:") -> None:
        import sqlite3

        self._json = json
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS amendment_log (
                seq          INTEGER PRIMARY KEY AUTOINCREMENT,
                decided_at   TEXT NOT NULL,
                amendment_id TEXT NOT NULL,
                outcome      TEXT NOT NULL,
                version      INTEGER NOT NULL,
                record       TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def record(self, record: dict[str, Any]) -> None:
        self._conn.execute(
            "INSERT INTO amendment_log "
            "(decided_at, amendment_id, outcome, version, record) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                str(record.get("decided_at", "")),
                str(record.get("amendment_id", "")),
                str(record.get("outcome", "")),
                int(record.get("constitution_version", 0)),
                self._json.dumps(record, default=str),
            ),
        )
        self._conn.commit()

    def all(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT record FROM amendment_log ORDER BY seq ASC"
        ).fetchall()
        return [self._json.loads(row[0]) for row in rows]

    def close(self) -> None:
        """Close the underlying connection."""
        self._conn.close()
