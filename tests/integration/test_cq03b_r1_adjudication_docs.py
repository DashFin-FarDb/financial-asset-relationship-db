"""Structural gates for the ratified CQ-03B-R1 ledger adjudication."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_0009 = REPO_ROOT / "docs" / "adr" / "0009-postgresql-migration-ledger-and-drift-contract.md"
ADR_0010 = REPO_ROOT / "docs" / "adr" / "0010-historical-receipt-evidence-and-target-ledger-profiles.md"
CONTINUITY = REPO_ROOT / "docs" / "strategy" / "fardb-project-continuity.md"
MIGRATION_RUNBOOK = REPO_ROOT / "docs" / "runbooks" / "database-migration-authority.md"
SETUP_BASELINE = "76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae"  # DevSkim: ignore all
CQ03C_MERGE = "784d092f1204b59e612efd4ff3949f3e3fed12cf"  # DevSkim: ignore all


def _load(path: Path) -> str:
    """Return ``path`` as UTF-8 text."""
    return path.read_text(encoding="utf-8")


def _compact(content: str) -> str:
    """Collapse Markdown wrapping so assertions test wording rather than line layout."""
    return " ".join(content.split())


@pytest.fixture(scope="module")
def adjudication() -> str:
    """Return the ADR 0010 decision text."""
    return _load(ADR_0010)


def test_adjudication_is_accepted_against_exact_main(adjudication: str) -> None:
    """ADR 0010 must bind ratification to the exact setup baseline."""
    assert ADR_0010.is_file()
    assert adjudication.startswith("# ADR 0010: Historical receipt evidence and target-ledger profiles")
    assert "**Accepted — ratified on 2026-08-17" in adjudication
    assert SETUP_BASELINE in adjudication
    assert "GitHub #1633" in adjudication
    assert "Linear DAS-62" in adjudication


def test_receipts_preserve_exact_evidence_without_claiming_original_files(adjudication: str) -> None:
    """Receipt fidelity must distinguish provider payload evidence from original file bytes."""
    decision = _compact(adjudication)
    assert "ordered `statements[]` payload" in decision
    assert "not proof of the original migration file" in decision
    assert "must not be reformatted, reparsed, reordered, combined, split, or normalized" in decision
    assert "deterministic SHA-256 digest" in decision
    assert "`fardb-provider-statements-v1`" in decision
    assert "unsigned 64-bit big-endian integer" in decision
    assert "serialized as exactly 64 lowercase hexadecimal ASCII characters" in decision
    assert "with no prefix or separators" in decision
    assert "wherever recorded in evidence, manifests, or adoption permits" in decision
    assert "protected evidence store" in decision
    assert "never staged into an executable migration directory" in decision


def test_reconstructions_are_forward_dated_and_dependency_complete(adjudication: str) -> None:
    """Clean builds must use reviewed forward baselines rather than backdated receipt substitutes."""
    decision = _compact(adjudication)
    assert "new forward UTC timestamp" in decision
    assert "must never reuse or backdate a provider timestamp" in decision
    assert "complete, reviewed, dependency-ordered state" in decision
    assert "historical receipt markers may not" in decision
    assert "Any actual schema delta stops adoption" in decision


def test_component_ledgers_are_composed_by_one_manifest(adjudication: str) -> None:
    """Target separation must come from one manifest-governed repository authority."""
    decision = _compact(adjudication)
    for component in ("auth", "graph", "coordination"):
        assert f"`{component}`" in decision
    assert "`supabase/ledgers/<component>/migrations/`" in decision
    assert "`supabase/ledger-profiles.json`" in decision
    assert "globally unique and strictly increasing across all component ledgers" in decision
    assert "`combined` selects the deterministic union" in decision
    assert "`fresh-v1`" in decision
    assert "`hosted-legacy-v1`" in decision
    assert "must not infer or silently expand a profile" in decision
    assert "no target-selection SQL" in decision


def test_target_fingerprint_contract_fails_closed(adjudication: str) -> None:
    """Target identity must be canonical, versioned, collision-aware, and fail closed."""
    decision = _compact(adjudication)
    assert "SHA-256 algorithm version `fardb-target-fingerprint-v1`" in decision
    assert "adapter ID, an immutable authority-namespace ID, and an immutable database ID" in decision
    assert "Unicode-normalized to NFC and encoded as UTF-8 with case preserved" in decision
    assert "algorithm version is stored with the fingerprint" in decision
    assert "observed collision between distinct protected canonical inputs" in decision
    assert "`TARGET_IDENTITY_INDETERMINATE` and a non-zero result" in decision
    assert "before profile selection or SQL execution" in decision


def test_pre_cq03d_barrier_is_credential_and_command_enforced(adjudication: str) -> None:
    """CQ-03B/C must be unable to mutate hosted schema or history accidentally."""
    decision = _compact(adjudication)
    assert "technically unable to write managed schemas or `supabase_migrations`" in decision
    for forbidden_command in (
        "`supabase db pull`",
        "`supabase migration repair`",
        "`supabase db push`",
        "`supabase db reset --linked`",
        "`supabase db reset --db-url <connection-string>`",
    ):
        assert forbidden_command in decision
    assert "retained or committed Supabase link state" in decision
    assert "fail-closed command barrier and negative tests" in decision
    assert "including both hosted reset variants" in decision


def test_cq03d_permit_binds_identity_and_one_timestamp(adjudication: str) -> None:
    """Hosted adoption must require one exact, protected, single-use permit."""
    marker = "CQ-03D is a separate manual workflow."
    end_marker = "### 5. Drift is evaluated against the target's explicit profile and lineage"
    assert marker in adjudication
    assert end_marker in adjudication
    permit = _compact(adjudication.split(marker, maxsplit=1)[1].split(end_marker, maxsplit=1)[0])
    assert "single-use adoption permit" in permit
    assert "exact reviewed repository SHA" in permit
    assert "build-profile ID" in permit
    assert "manifest digest" in permit
    assert "lineage-profile ID" in permit
    assert "opaque target fingerprint" in permit
    assert "one allowlisted canonical migration timestamp" in permit
    assert "passing CQ-03B/C evidence" in permit
    assert "normalized catalog digests" in permit
    assert "ratifier" in permit
    assert "approval time" in permit
    assert "expiry" in permit
    assert "CQ-03D never applies DDL" in permit


def test_adr_0009_declares_the_narrow_amendment() -> None:
    """ADR 0009 must route conflicting historical-replay clauses to ADR 0010."""
    original = _compact(_load(ADR_0009))
    assert "amended by ADR 0010" in original
    assert "0010-historical-receipt-evidence-and-target-ledger-profiles.md" in original
    assert "`supabase db pull` is forbidden in CQ-03B/C" in original
    assert "`supabase db push --dry-run` and `supabase migration repair --status applied <timestamp>`" in original
    assert "non-executable `hosted-legacy-v1` lineage evidence" in original
    assert "supabase/ledgers/<component>/migrations/" in original


def test_continuity_records_merged_r2_without_claiming_provider_delivery() -> None:
    """The durable handoff must record merged R2 and keep CQ-03D separately authorized."""
    continuity = _load(CONTINUITY)
    header = "\n".join(continuity.splitlines()[:8])
    assert SETUP_BASELINE in header
    assert "CQ-03B-R1 ratified on 2026-08-17" in header
    assert "ADR 0010" in continuity
    assert "CQ-03B-R1, CQ-03B-R2, and CQ-03C are merged" in header
    assert "R2 then merged through PR #1641" in continuity
    assert "The provider was not mutated" in continuity
    assert "unavailable higher-priority evaluation" in continuity
    assert "return `EVALUATION_INCOMPLETE`" in continuity
    assert "startup and readiness prove they cannot mutate schema or migration history" in _compact(continuity)
    assert "credential-bootstrap authority" in continuity
    assert "CQ-03D retains separate human approval" in continuity
    assert "No hosted schema, migration history, credential, provider link state" in continuity
    assert "CQ-03B-R1 merged through PR #1640" in continuity


def test_continuity_records_merged_cq03c_without_claiming_hosted_adoption() -> None:
    """The handoff must advance CQ-03C but retain CQ-03D's separate authority."""
    continuity = _load(CONTINUITY)
    header = "\n".join(continuity.splitlines()[:8])
    assert CQ03C_MERGE in header
    assert "CQ-03C is implemented in draft PR #1643" not in continuity
    assert "CQ-03C was human-ratified" in continuity
    assert "CQ-03D has no approved target, permit, or hosted preflight evidence" in _compact(continuity)
    assert "CQ-03D remains unapproved and unexecuted" in header


def test_cq03d_runbook_is_preparation_not_connected_execution() -> None:
    """The approval package must bind future adoption while withholding an ad hoc executor."""
    runbook = _compact(_load(MIGRATION_RUNBOOK))
    assert "CQ-03D is not an extension of the normal PostgreSQL migration command" in runbook
    assert "protected, single-use permit" in runbook
    assert "exact reviewed repository SHA" in runbook
    assert "opaque `fardb-target-fingerprint-v1` target fingerprint" in runbook
    assert "exactly one allowlisted canonical migration timestamp" in runbook
    assert "python -m scripts.postgresql_ledger validate" in runbook
    assert "TARGET_IDENTITY_INDETERMINATE" in runbook
    assert "The repository currently exposes the tested `evaluate_profile_drift()` API" in runbook
    assert "No database-connected command is approved by this preparation package" in runbook
    assert "It must immediately repeat migration-list parity, normalized drift" in runbook
    assert "never applies DDL" in runbook
