"""Structural gates for the ratified CQ-03B-R1 ledger adjudication."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_0009 = REPO_ROOT / "docs" / "adr" / "0009-postgresql-migration-ledger-and-drift-contract.md"
ADR_0010 = REPO_ROOT / "docs" / "adr" / "0010-historical-receipt-evidence-and-target-ledger-profiles.md"
CONTINUITY = REPO_ROOT / "docs" / "strategy" / "fardb-project-continuity.md"
SETUP_BASELINE = "76f1194f1f9b83cb9ed8f0bb0083824ededbe0ae"  # DevSkim: ignore all


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
    assert "protected evidence store" in decision
    assert "never staged into an executable migration directory" in decision


def test_reconstructions_are_forward_dated_and_dependency_complete(adjudication: str) -> None:
    """Clean builds must use reviewed forward baselines rather than backdated receipt substitutes."""
    assert "new forward UTC timestamp" in adjudication
    assert "must never reuse or backdate a provider timestamp" in adjudication
    assert "complete,\nreviewed, dependency-ordered state" in adjudication
    assert "historical receipt markers may not" in adjudication
    assert "Any actual schema delta stops adoption" in adjudication


def test_component_ledgers_are_composed_by_one_manifest(adjudication: str) -> None:
    """Target separation must come from one manifest-governed repository authority."""
    for component in ("auth", "graph", "coordination"):
        assert f"`{component}`" in adjudication
    assert "`supabase/ledgers/<component>/migrations/`" in adjudication
    assert "`supabase/ledger-profiles.json`" in adjudication
    assert "globally unique and strictly increasing across all component ledgers" in adjudication
    assert "`combined` selects the deterministic union" in adjudication
    assert "`fresh-v1`" in adjudication
    assert "`hosted-legacy-v1`" in adjudication
    assert "must not infer or\nsilently expand a profile" in adjudication
    assert "no target-selection SQL" in adjudication


def test_pre_cq03d_barrier_is_credential_and_command_enforced(adjudication: str) -> None:
    """CQ-03B/C must be unable to mutate hosted schema or history accidentally."""
    assert "technically unable to write managed\nschemas or `supabase_migrations`" in adjudication
    for forbidden_command in (
        "`supabase db pull`",
        "`supabase migration repair`",
        "`supabase db push`",
        "`supabase db reset --linked`",
    ):
        assert forbidden_command in adjudication
    assert "retained or committed Supabase link state" in adjudication
    assert "fail-closed command barrier and negative tests" in adjudication


def test_cq03d_permit_binds_identity_and_one_timestamp(adjudication: str) -> None:
    """Hosted adoption must require one exact, protected, single-use permit."""
    permit = adjudication.split("CQ-03D is a separate manual workflow.", maxsplit=1)[1]
    assert "single-use adoption permit" in permit
    assert "exact reviewed repository SHA" in permit
    assert "manifest digest" in permit
    assert "opaque target fingerprint" in permit
    assert "one allowlisted canonical migration timestamp" in permit
    assert "CQ-03D never applies DDL" in permit


def test_adr_0009_declares_the_narrow_amendment() -> None:
    """ADR 0009 must route conflicting historical-replay clauses to ADR 0010."""
    original = _compact(_load(ADR_0009))
    assert "amended by ADR 0010" in original
    assert "0010-historical-receipt-evidence-and-target-ledger-profiles.md" in original
    assert "`supabase db pull` is forbidden in CQ-03B/C" in original
    assert "non-executable `hosted-legacy-v1` lineage evidence" in original
    assert "supabase/ledgers/<component>/migrations/" in original


def test_continuity_points_to_r2_without_claiming_delivery() -> None:
    """The durable handoff must identify R2 as next and keep CQ-03D separately authorized."""
    continuity = _load(CONTINUITY)
    header = "\n".join(continuity.splitlines()[:8])
    assert SETUP_BASELINE in header
    assert "CQ-03B-R1 ratified on 2026-08-17" in header
    assert "ADR 0010" in continuity
    assert "CQ-03B-R2 may start only after the R1 record merges" in continuity
    assert "CQ-03D remains separately approved" in continuity
    assert "No hosted schema, migration history, credential, provider link state" in continuity
