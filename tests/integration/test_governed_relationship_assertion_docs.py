"""Structural gates for GRAC v1 ADR 0008, frozen contract, and continuity links.

Patterned on ``tests/integration/test_production_architecture_documentation.py`` and
ADR 0007 documentation wiring tests: assert file presence, Accepted status, claim
discipline (capability remains NEXT), and required contract anchors.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ADR_0008 = REPO_ROOT / "docs" / "adr" / "0008-governed-relationship-assertion-contract.md"
CONTRACT_V1 = REPO_ROOT / "docs" / "governance" / "governed-relationship-assertion-contract-v1.md"
CONTINUITY = REPO_ROOT / "docs" / "strategy" / "fardb-project-continuity.md"
STRATEGY_README = REPO_ROOT / "docs" / "strategy" / "README.md"

BASELINE_SHA = "5e45753705c10c2c4f50e0e9bc4d07b823d752ab"
REQUIRED_CONTRACT_SECTIONS = (
    "## 1. Purpose and boundaries",
    "## 2. Vocabulary",
    "## 3. Lifecycle and authority matrix",
    "## 4. Evidence and confidence",
    "## 5. Bitemporal rules",
    "## 6. Supersession",
    "## 7. Deterministic projection algorithm",
    "## 8. Additive persistence model (seven tables)",
    "## 9. Financial vertical slice: `financial.bond.issuer_reference@1`",
    "## 10. Threat model (v1)",
    "## 11. Control-plane disposition",
    "## 12. Programme completion test",
    "## 13. Amendment rule",
)
SEVEN_TABLES = (
    "relationship_evidence",
    "relationship_assertions",
    "relationship_assertion_evidence",
    "relationship_assertion_events",
    "relationship_projection_revisions",
    "relationship_projection_edges",
    "relationship_projection_publications",
)
GOVERNED_DOCUMENTS = (
    ("adr_0008", ADR_0008),
    ("contract_v1", CONTRACT_V1),
    ("continuity", CONTINUITY),
    ("strategy_readme", STRATEGY_README),
)


def _load(path: Path) -> str:
    """Read UTF-8 text from ``path``."""
    return path.read_text(encoding="utf-8")


def _heading_line_matches(stripped: str, heading: str) -> bool:
    """Return True when ``stripped`` is the target markdown heading line (exact or prefixed)."""
    if not stripped.startswith("#"):
        return False
    if stripped == heading:
        return True
    if not stripped.startswith(heading):
        return False
    rest = stripped[len(heading) :]
    return rest[:1] in {"", " ", "\t", "—", "–", "-"}


def _find_heading_line_index(lines: list[str], heading: str) -> int:
    """Return the index of ``heading`` outside fenced code blocks."""
    in_fence = False
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if _heading_line_matches(stripped, heading):
            return idx
    raise AssertionError(f"missing heading {heading!r}")


def _section_body_after(lines: list[str], start_idx: int, level: int) -> str:
    """Collect section body lines until the next same-or-higher-level heading."""
    body: list[str] = []
    in_fence = False
    next_heading = re.compile(rf"^#{{1,{level}}} ")
    for line in lines[start_idx + 1 :]:
        stripped = line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            body.append(line)
            continue
        if in_fence or not next_heading.match(stripped):
            body.append(line)
            continue
        break
    return "".join(body)


def _section_after(content: str, heading: str) -> str:
    """Return text after a markdown heading until the next same-or-higher-level heading.

    Matches ``heading`` only as a full heading line (or a heading line that starts with
    ``heading``). Ignores heading-like lines inside fenced code blocks.
    """
    level = len(heading) - len(heading.lstrip("#"))
    assert level >= 1, f"expected a markdown heading, got {heading!r}"
    lines = content.splitlines(keepends=True)
    return _section_body_after(lines, _find_heading_line_index(lines, heading), level)


def _assert_document_hygiene(content: str, path: Path) -> None:
    """Shared heading/fence/whitespace/mojibake gates for governed documents."""
    for line in content.splitlines():
        if line.startswith("#"):
            assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r} ({path})"
    fence_count = content.count("```")
    assert fence_count % 2 == 0, f"Unbalanced code fences: {fence_count} ({path})"
    bad = [i + 1 for i, line in enumerate(content.splitlines()) if line.rstrip() != line and line.strip()]
    assert not bad, f"Trailing whitespace on lines: {bad} ({path})"
    # U+FFFD can appear in valid UTF-8 after a bad copy-paste; catch it without re-reading.
    assert "\ufffd" not in content, f"UTF-8 replacement character (U+FFFD) found ({path})"


@pytest.fixture(scope="module")
def adr_content() -> str:
    """ADR 0008 file contents."""
    return _load(ADR_0008)


@pytest.fixture(scope="module")
def contract_content() -> str:
    """Frozen contract v1 file contents."""
    return _load(CONTRACT_V1)


@pytest.fixture(scope="module")
def continuity_content() -> str:
    """Continuity ledger file contents."""
    return _load(CONTINUITY)


@pytest.fixture(scope="module")
def strategy_readme_content() -> str:
    """Strategy README file contents."""
    return _load(STRATEGY_README)


@pytest.mark.parametrize(("doc_id", "path"), GOVERNED_DOCUMENTS, ids=[doc_id for doc_id, _ in GOVERNED_DOCUMENTS])
def test_governed_document_hygiene(doc_id: str, path: Path) -> None:
    """Each governed document must pass shared markdown hygiene gates."""
    assert path.is_file(), doc_id
    _assert_document_hygiene(_load(path), path)


class TestGovernedRelationshipAssertionADR:
    """Validate docs/adr/0008-governed-relationship-assertion-contract.md."""

    def test_file_exists(self) -> None:
        """ADR 0008 must exist as a regular file."""
        assert ADR_0008.is_file()

    def test_file_is_not_empty(self, adr_content: str) -> None:
        """ADR 0008 must not be empty."""
        assert adr_content.strip()

    def test_title_is_level_one_heading(self, adr_content: str) -> None:
        """Title must be a level-one heading naming ADR 0008."""
        first = adr_content.splitlines()[0]
        assert first.startswith("# ")
        assert "ADR 0008" in first
        assert "Governed Relationship Assertion" in first

    def test_has_status_section(self, adr_content: str) -> None:
        """ADR must declare a Status section."""
        assert "## Status" in adr_content

    def test_status_is_accepted(self, adr_content: str) -> None:
        """Contract decision status must be Accepted."""
        status = _section_after(adr_content, "## Status").strip()
        first_nonempty = next(line for line in status.splitlines() if line.strip())
        assert first_nonempty.strip() == "Accepted"

    def test_has_date_section(self, adr_content: str) -> None:
        """ADR must declare a Date section."""
        assert "## Date" in adr_content

    def test_date_is_2026_07_25(self, adr_content: str) -> None:
        """ADR date must be 2026-07-25."""
        date_section = _section_after(adr_content, "## Date").strip()
        first_nonempty = next(line for line in date_section.splitlines() if line.strip())
        assert first_nonempty.strip() == "2026-07-25"

    def test_has_context_decision_consequences(self, adr_content: str) -> None:
        """ADR must include Context, Decision, and Consequences."""
        assert "## Context" in adr_content
        assert "## Decision" in adr_content
        assert "## Consequences" in adr_content

    def test_consequences_has_positive_negative_neutral(self, adr_content: str) -> None:
        """Consequences must include Positive, Negative, and Neutral subsections."""
        consequences = _section_after(adr_content, "## Consequences")
        assert "### Positive" in consequences
        assert "### Negative" in consequences
        assert "### Neutral" in consequences

    def test_has_alternatives_considered(self, adr_content: str) -> None:
        """ADR must record rejected alternatives."""
        assert "## Alternatives considered" in adr_content

    def test_has_implementation_plan(self, adr_content: str) -> None:
        """ADR must outline immediate and deferred programme work."""
        assert "## Implementation plan" in adr_content

    def test_has_references(self, adr_content: str) -> None:
        """ADR must list references including the frozen contract."""
        assert "## References" in adr_content
        assert "governed-relationship-assertion-contract-v1.md" in adr_content

    def test_claim_discipline_keeps_capability_next(self, adr_content: str) -> None:
        """Runtime capability claim-discipline row must remain NEXT and deny CURRENT."""
        claim = _section_after(adr_content, "### Claim discipline")
        rows = [
            line
            for line in claim.splitlines()
            if "runtime capability" in line.lower() and line.lstrip().startswith("|")
        ]
        assert rows, "missing runtime capability claim-discipline row"
        row = rows[0]
        assert "Remains **NEXT**" in row
        assert "not CURRENT" in row

    def test_states_empty_store_zero_behavioural_change(self, adr_content: str) -> None:
        """Empty assertion store must imply zero behavioural change."""
        assert "Empty assertion store" in adr_content or "empty assertion store" in adr_content.lower()
        assert "zero behavioural change" in adr_content.lower()

    def test_lists_non_negotiable_invariants(self, adr_content: str) -> None:
        """ADR must enumerate the programme non-negotiables."""
        assert "Assertions are truth" in adr_content
        assert "Append-only history" in adr_content
        assert "Bitemporal" in adr_content
        assert "fail closed" in adr_content.lower()
        assert "SUCCEEDED" in adr_content

    def test_bitemporal_recorded_at_vs_known_at(self, adr_content: str) -> None:
        """ADR must distinguish stored recorded_at from query known_at."""
        invariants = _section_after(adr_content, "### Non-negotiable invariants")
        assert "recorded_at" in invariants
        assert "known_at" in invariants
        assert "query/as-of" in invariants.lower() or "query/as-of parameter" in invariants.lower()
        assert "not a persisted" in invariants.lower() or "not a persisted column" in invariants.lower()

    def test_control_plane_reference_only(self, adr_content: str) -> None:
        """control-plane-platform must remain reference-only."""
        assert "control-plane-platform" in adr_content
        assert "reference-only" in adr_content.lower() or "reference-only" in adr_content

    def test_first_slice_predicate(self, adr_content: str) -> None:
        """ADR must name the financial vertical-slice predicate."""
        assert "financial.bond.issuer_reference@1" in adr_content
        assert "AAPL_BOND_2030" in adr_content

    def test_references_baseline_sha(self, adr_content: str) -> None:
        """ADR context must cite the programme baseline SHA."""
        assert BASELINE_SHA in adr_content


class TestGovernedRelationshipAssertionContractV1:
    """Validate the frozen normative contract document."""

    def test_file_exists(self) -> None:
        """Contract v1 must exist as a regular file."""
        assert CONTRACT_V1.is_file()

    def test_file_is_not_empty(self, contract_content: str) -> None:
        """Contract v1 must not be empty."""
        assert contract_content.strip()

    def test_title_is_level_one_heading(self, contract_content: str) -> None:
        """Title must name the governed relationship assertion contract v1."""
        first = contract_content.splitlines()[0]
        assert first.startswith("# ")
        assert "Governed Relationship Assertion Contract v1" in first

    def test_declares_frozen_normative_status(self, contract_content: str) -> None:
        """Contract must declare frozen normative status tied to ADR 0008."""
        header = "\n".join(contract_content.splitlines()[:12])
        assert "Frozen" in header or "frozen" in header
        assert "0008" in header or "ADR 0008" in contract_content[:500]

    def test_capability_claim_is_next(self, contract_content: str) -> None:
        """Runtime capability claim class must remain NEXT."""
        header = "\n".join(contract_content.splitlines()[:20])
        claim_line = next(
            (
                line
                for line in header.splitlines()
                if "Claim class for runtime capability:" in line or "Capability claim class:" in line
            ),
            "",
        )
        assert claim_line, "missing capability claim class header line"
        assert "`NEXT`" in claim_line
        assert "CURRENT" not in claim_line

    def test_required_sections_present(self, contract_content: str) -> None:
        """All normative numbered sections must be present."""
        for section in REQUIRED_CONTRACT_SECTIONS:
            assert section in contract_content, f"missing section {section!r}"

    def test_vocabulary_defines_core_terms(self, contract_content: str) -> None:
        """Vocabulary section must define assertion, evidence, projection, and supersession."""
        vocab = _section_after(contract_content, "## 2. Vocabulary")
        for term in ("Proposition", "Evidence", "Assertion", "Projection", "Supersession", "Confidence"):
            assert term in vocab
        assert "supersession pointer" not in vocab.lower()

    def test_lifecycle_states_and_terminal(self, contract_content: str) -> None:
        """Lifecycle must name Proposed/Accepted and terminal states."""
        lifecycle = _section_after(contract_content, "## 3. Lifecycle and authority matrix")
        for state in ("Proposed", "Accepted", "Rejected", "Withdrawn", "Disputed", "Retracted", "Superseded"):
            assert state in lifecycle
        assert "Terminal" in lifecycle or "terminal" in lifecycle

    def test_authority_matrix_present(self, contract_content: str) -> None:
        """Authority matrix must list propose/accept transitions."""
        lifecycle = _section_after(contract_content, "## 3. Lifecycle and authority matrix")
        assert "Propose" in lifecycle
        assert "Accept" in lifecycle
        assert "acceptor" in lifecycle

    def test_evidence_forbids_bodies(self, contract_content: str) -> None:
        """Evidence model must forbid storing evidence bodies."""
        evidence = _section_after(contract_content, "## 4. Evidence and confidence")
        assert "SHA-256" in evidence
        assert "not_assessed" in evidence
        lower = evidence.lower()
        assert "bodies" in lower or "no evidence body" in lower
        assert "no evidence bodies" in contract_content.lower() or "out of v1" in lower
        assert "recorded_at" in evidence
        assert "known_at" in evidence

    def test_confidence_not_projection_strength(self, contract_content: str) -> None:
        """Confidence must be separated from projection strength."""
        assert (
            "Confidence vs projection strength" in contract_content
            or "confidence ≠ projection" in contract_content.lower()
        )
        assert "projection strength" in contract_content.lower()

    def test_bitemporal_fields(self, contract_content: str) -> None:
        """Bitemporal rules must name effective and known/recorded coordinates."""
        bitemporal = _section_after(contract_content, "## 5. Bitemporal rules")
        assert "effective_from" in bitemporal
        assert "effective_to" in bitemporal
        assert "recorded_at" in bitemporal
        assert "known_at" in bitemporal
        assert "effective_at" in bitemporal
        assert "evidence links" in bitemporal.lower() or "evidence link" in bitemporal.lower()
        assert "not a persisted column" in bitemporal.lower()

    def test_supersession_append_only(self, contract_content: str) -> None:
        """Supersession must be append-only via successor events only."""
        supersession = _section_after(contract_content, "## 6. Supersession")
        assert "append-only" in supersession.lower() or "Append-only" in supersession
        assert "successor" in supersession.lower()
        normalized = re.sub(r"\s+", " ", supersession.lower())
        assert "sole authoritative" in normalized or "do not store a supersession pointer" in normalized
        assert "same atomic transaction" in normalized

    def test_projection_is_deterministic_and_fail_closed(self, contract_content: str) -> None:
        """Projector must be pure, hashed, and fail closed on conflicts."""
        projection = _section_after(contract_content, "## 7. Deterministic projection algorithm")
        assert "SHA-256" in projection
        assert "fail closed" in projection.lower() or "projection error" in projection.lower()
        assert "SUCCEEDED" in projection
        assert "project(assertions," in projection
        assert "accepted_assertions" not in projection
        assert "same atomic transaction" in projection.lower()
        assert "publication row is authoritative" in projection.lower()

    def test_seven_tables_named(self, contract_content: str) -> None:
        """Persistence model must name all seven additive tables."""
        persistence = _section_after(contract_content, "## 8. Additive persistence model (seven tables)")
        for table in SEVEN_TABLES:
            assert table in persistence
        assert "supersession pointer" not in persistence.lower()

    def test_financial_slice_fields(self, contract_content: str) -> None:
        """Vertical slice must pin subject, object, method, and legacy edge type."""
        slice_section = _section_after(
            contract_content,
            "## 9. Financial vertical slice: `financial.bond.issuer_reference@1`",
        )
        assert "AAPL_BOND_2030" in slice_section
        assert "AAPL" in slice_section
        assert "bond.issuer_id.resolution@1" in slice_section
        assert "corporate_link" in slice_section
        assert "0.8" in slice_section
        assert "financial_graph_current_view" in slice_section

    def test_threat_model_present(self, contract_content: str) -> None:
        """Threat model section must list mitigations."""
        threats = _section_after(contract_content, "## 10. Threat model (v1)")
        assert "Append-only" in threats or "append-only" in threats.lower()
        assert "fail-closed" in threats.lower() or "Fail-closed" in threats

    def test_control_plane_disposition(self, contract_content: str) -> None:
        """Contract must keep control-plane-platform reference-only in section 11."""
        disposition = _section_after(contract_content, "## 11. Control-plane disposition")
        assert "control-plane-platform" in disposition
        assert "reference" in disposition.lower()

    def test_amendment_rule_forbids_silent_rewrite(self, contract_content: str) -> None:
        """Amendment rule must forbid silent v1 rewrites in implementation PRs."""
        amendment = _section_after(contract_content, "## 13. Amendment rule")
        assert "contract-amendment" in amendment.lower() or "amendment" in amendment.lower()
        assert "silently" in amendment.lower() or "silent" in amendment.lower()

    def test_baseline_sha(self, contract_content: str) -> None:
        """Contract header must cite the programme baseline SHA."""
        assert BASELINE_SHA in contract_content


class TestGovernedRelationshipAssertionContinuityAndStrategy:
    """Validate continuity ledger and strategy README programme wiring."""

    def test_continuity_exists(self) -> None:
        """Continuity ledger must exist."""
        assert CONTINUITY.is_file()

    def test_evidence_cutoff_is_baseline_sha(self, continuity_content: str) -> None:
        """Continuity evidence cutoff must be the GRAC baseline SHA."""
        header = "\n".join(continuity_content.splitlines()[:8])
        assert BASELINE_SHA in header

    def test_fardb_grac_v1_ledger_entry(self, continuity_content: str) -> None:
        """FARDB-GRAC-V1 must be recorded as Agreed."""
        assert "### FARDB-GRAC-V1" in continuity_content
        entry = _section_after(continuity_content, "### FARDB-GRAC-V1")
        assert "**Status:** Agreed" in entry
        assert "financial.bond.issuer_reference@1" in entry
        assert BASELINE_SHA in entry

    def test_fpc_04_next_action_advanced(self, continuity_content: str) -> None:
        """FPC-2026-07-21-04 next-action must advance to conformance + vertical slice."""
        assert "### FPC-2026-07-21-04" in continuity_content
        entry = _section_after(continuity_content, "### FPC-2026-07-21-04")
        assert "land executable conformance + vertical slice" in entry.lower()
        assert "Agreed" in entry

    def test_cutoff_does_not_claim_pr_1510_open(self, continuity_content: str) -> None:
        """H-P1-03 / PR #1510 must not be described as open after the refreshed cutoff."""
        assert "Open PR #1510" not in continuity_content
        assert "H-P1-03 is open as PR #1510" not in continuity_content
        assert "PR #1510 (H-P1-03 post-recovery re-smoke) is open" not in continuity_content
        assert "open PR #1510" not in continuity_content
        assert "H-P1-03" in continuity_content

    def test_strategy_readme_links_grac_as_next(self, strategy_readme_content: str) -> None:
        """Strategy README must present GRAC links as NEXT programme documents."""
        assert STRATEGY_README.is_file()
        assert "## Programme documents (NEXT)" in strategy_readme_content
        programme = _section_after(strategy_readme_content, "## Programme documents (NEXT)")
        assert "0008-governed-relationship-assertion-contract.md" in programme
        assert "governed-relationship-assertion-contract-v1.md" in programme
        header = "\n".join(strategy_readme_content.splitlines()[:10])
        assert "GRAC v1 programme **NEXT**" in header or "runtime capability remains **NEXT**" in header
        publication = _section_after(strategy_readme_content, "## Publication rule")
        assert "MUST NOT be restated as CURRENT" in publication

    def test_strategy_readme_has_programme_documents_section(self, strategy_readme_content: str) -> None:
        """README must expose a programme documents section for ADR 0008 and contract v1."""
        assert "## Programme documents (NEXT)" in strategy_readme_content
