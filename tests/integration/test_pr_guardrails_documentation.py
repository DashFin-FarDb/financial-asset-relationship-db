"""
Comprehensive validation tests for the PR guardrails and dependency policy documentation.

Covers:
- .github/AI_AGENT_GUARDRAILS.md
- docs/HIGH_RISK_CHANGE_GUARDRAILS.md
- .github/PULL_REQUEST_TEMPLATE/dependency-change.md
- .github/PULL_REQUEST_TEMPLATE/validator-follow-up.md
- docs/DEPENDENCY_POLICY.md
- docs/PR_SCOPE_GUARDRAILS.md
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

AI_GUARDRAILS_FILE = REPO_ROOT / ".github" / "AI_AGENT_GUARDRAILS.md"
HIGH_RISK_GUARDRAILS_FILE = REPO_ROOT / "docs" / "HIGH_RISK_CHANGE_GUARDRAILS.md"
DEPENDENCY_CHANGE_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "dependency-change.md"
VALIDATOR_FOLLOWUP_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "validator-follow-up.md"
DEPENDENCY_POLICY_FILE = REPO_ROOT / "docs" / "DEPENDENCY_POLICY.md"
PR_SCOPE_GUARDRAILS_FILE = REPO_ROOT / "docs" / "PR_SCOPE_GUARDRAILS.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(content: str) -> list[str]:
    return content.splitlines()


def _resolved_local_markdown_links(path: Path) -> set[Path]:
    """Resolve repository-local Markdown links in *path*."""
    resolved = set()
    for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", _load(path)):
        target = target.split("#", maxsplit=1)[0]
        if target and "://" not in target:
            resolved.add((path.parent / target).resolve())
    return resolved


# ---------------------------------------------------------------------------
# AI_AGENT_GUARDRAILS.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAIAgentGuardrails:
    """Validate .github/AI_AGENT_GUARDRAILS.md structure and content."""

    @pytest.fixture
    def content(self) -> str:
        return _load(AI_GUARDRAILS_FILE)

    @pytest.fixture
    def lines(self, content: str) -> list[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert AI_GUARDRAILS_FILE.exists(), "AI_AGENT_GUARDRAILS.md must exist"
        assert AI_GUARDRAILS_FILE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0, "AI_AGENT_GUARDRAILS.md must not be empty"

    def test_title_is_level_one_heading(self, lines: list[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
        assert first_heading is not None, "File must have at least one heading"
        assert first_heading.startswith("# "), "First heading must be H1"
        assert "AI Agent Guardrails" in first_heading

    def test_has_repository_rule_section(self, content: str) -> None:
        assert "## Repository rule" in content

    def test_has_mandatory_reasoning_order_section(self, content: str) -> None:
        assert "## Mandatory reasoning order for dependency work" in content

    def test_has_hard_rules_section(self, content: str) -> None:
        assert "## Hard rules" in content

    def test_has_preferred_pr_split_section(self, content: str) -> None:
        assert "## Preferred PR split" in content

    def test_has_stop_conditions_section(self, content: str) -> None:
        assert "## Stop conditions" in content

    def test_has_validation_expectations_section(self, content: str) -> None:
        assert "## Validation expectations" in content

    def test_requirements_txt_named_as_source_of_truth(self, content: str) -> None:
        assert "requirements.txt" in content, "Must reference requirements.txt"
        assert "source of truth" in content.lower(), "Must declare a source of truth"

    def test_hard_rules_list_is_present(self, content: str) -> None:
        """Hard rules section must contain bullet-list items."""
        hard_rules_section = content.split("## Hard rules")[1].split("##")[0]
        bullets = [line for line in hard_rules_section.splitlines() if line.strip().startswith("- ")]
        assert len(bullets) >= 4, "Hard rules section must have at least 4 bullet items"

    def test_stop_conditions_list_is_present(self, content: str) -> None:
        stop_section = content.split("## Stop conditions")[1].split("##")[0]
        bullets = [line for line in stop_section.splitlines() if line.strip().startswith("- ")]
        assert len(bullets) >= 3, "Stop conditions must have at least 3 bullet items"

    def test_mandatory_reasoning_order_has_numbered_steps(self, content: str) -> None:
        reasoning_section = content.split("## Mandatory reasoning order for dependency work")[1].split("##")[0]
        numbered = re.findall(r"^\d+\.", reasoning_section, re.MULTILINE)
        assert len(numbered) >= 4, "Mandatory reasoning order must have at least 4 numbered steps"

    def test_preferred_pr_split_has_dependency_alignment_subsection(self, content: str) -> None:
        assert "### Dependency alignment PR" in content

    def test_preferred_pr_split_has_validator_followup_subsection(self, content: str) -> None:
        assert "### Validator follow-up PR" in content

    def test_dependency_alignment_pr_lists_requirements_txt(self, content: str) -> None:
        dep_section = content.split("### Dependency alignment PR")[1].split("###")[0]
        assert "requirements.txt" in dep_section

    def test_dependency_alignment_pr_lists_pyproject_toml(self, content: str) -> None:
        dep_section = content.split("### Dependency alignment PR")[1].split("###")[0]
        assert "pyproject.toml" in dep_section

    def test_headings_have_space_after_hash(self, lines: list[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_no_trailing_whitespace(self, lines: list[str]) -> None:
        bad = [(i + 1, line) for i, line in enumerate(lines) if line.rstrip() != line and line.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_file_does_not_mention_secrets(self, content: str) -> None:
        secret_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",
            r"gho_[a-zA-Z0-9]{36}",
        ]
        for pattern in secret_patterns:
            assert not re.search(pattern, content), f"File must not contain hardcoded tokens (pattern: {pattern})"

    def test_utf8_encoding(self) -> None:
        content = AI_GUARDRAILS_FILE.read_text(encoding="utf-8")
        assert "�" not in content, "File must not contain UTF-8 replacement characters"

    def test_does_not_mix_dependency_alignment_with_upgrade(self, content: str) -> None:
        """Hard rules must include a rule against mixing dependency alignment and framework upgrades."""
        assert "framework upgrade" in content.lower() or "framework/security upgrade" in content.lower()

    def test_delegates_high_risk_rules_to_canonical_document(self, content: str) -> None:
        assert "../docs/HIGH_RISK_CHANGE_GUARDRAILS.md" in content
        assert "does not restate or narrow those requirements" in content


# ---------------------------------------------------------------------------
# docs/HIGH_RISK_CHANGE_GUARDRAILS.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestHighRiskChangeGuardrails:
    """Validate the canonical low-autonomy and scanner contract."""

    @pytest.fixture
    def content(self) -> str:
        return _load(HIGH_RISK_GUARDRAILS_FILE)

    def test_file_exists_with_canonical_title(self, content: str) -> None:
        assert HIGH_RISK_GUARDRAILS_FILE.is_file()
        assert content.startswith("# High-Risk Change Guardrails")
        assert "canonical source" in content

    def test_preserves_gnc_exact_head_evidence_boundary(self, content: str) -> None:
        for token in [
            "resolved",
            "deferred_out_of_scope",
            "rejected_speculative",
            "duplicate_of",
            "waived",
            "reopened_as_recurrence",
            "stale_sha",
            "wrong_target",
        ]:
            assert token in content
        assert "cannot approve or waive themselves" in content

    def test_defines_low_autonomy_technology_list_once(self, content: str) -> None:
        expected = [
            "database schema, connections, drivers, pooling",
            "authentication and authorization",
            "deployment, hosting, and containerization",
            "CI/CD pipelines and workflow configuration",
            "security scanner configuration (CodeQL, DeepSource, Snyk, Codacy, Trivy)",
            "persistence and storage backends",
            "environment-variable precedence and configuration loading",
            "migrations (schema, data, or auth)",
            "recovery and restore procedures",
            "connection pooling and async/sync driver selection",
        ]
        section = content.split("## Low-autonomy areas")[1].split("##")[0]
        bullets = [line.removeprefix("- ") for line in section.splitlines() if line.startswith("- ")]
        assert bullets == expected

        active_sources = [
            content,
            _load(AI_GUARDRAILS_FILE),
            _load(REPO_ROOT / ".github" / "AUTOMATION_SCOPE_POLICY.md"),
            _load(REPO_ROOT / "AGENTS.md"),
            _load(REPO_ROOT / "docs" / "agent-task-entry.md"),
        ]
        assert sum(source.count("## Low-autonomy areas") for source in active_sources) == 1
        for item in expected:
            assert sum(source.count(item) for source in active_sources) == 1

    def test_required_contract_preserves_all_eight_fields(self, content: str) -> None:
        contract = content.split("## Required implementation contract")[1].split("##")[0]
        for field in [
            "Allowed files",
            "Forbidden files",
            "Exact targets",
            "Exact non-targets",
            "Fixed decisions",
            "Tests to add/update",
            "Validation commands",
            "Stop conditions",
        ]:
            assert field in contract
        assert len(re.findall(r"^\d+\.", contract, re.MULTILINE)) == 8

    def test_preserves_scanner_and_false_positive_boundaries(self, content: str) -> None:
        assert "Do not suppress scanner findings globally" in content
        assert "false positive" in content
        assert "inline suppression" in content
        assert "--all-projects" in content
        assert "non-production" in content
        assert "Security scanners may automatically" in content
        assert "Suggest version bumps for vulnerable dependencies" in content
        normalized = " ".join(content.split())
        assert (
            "Scanner noise (false positives, low-priority warnings, non-production findings) should not block PRs "
            "or drive scope expansion."
        ) in normalized
        for scanner_config in [".deepsource.toml", ".github/workflows/codeql.yml", ".snyk", "codacy-config.yml"]:
            assert scanner_config in content

    def test_preserves_artifact_and_fixed_database_decisions(self, content: str) -> None:
        assert "PR_DESCRIPTION.md" in content
        assert "audit summaries" in content
        assert "SQLite vs PostgreSQL" in content
        assert "sync vs async database drivers" in content
        assert "environment-variable precedence" in content

    def test_primary_navigation_documents_link_to_canonical_contract(self) -> None:
        navigation_files = [
            REPO_ROOT / "AGENTS.md",
            REPO_ROOT / "docs" / "agent-task-entry.md",
            AI_GUARDRAILS_FILE,
            REPO_ROOT / ".github" / "AUTOMATION_SCOPE_POLICY.md",
            REPO_ROOT / ".github" / "pull_request_template.md",
        ]
        canonical = HIGH_RISK_GUARDRAILS_FILE.resolve()
        for path in navigation_files:
            assert canonical in _resolved_local_markdown_links(path), (
                f"{path.relative_to(REPO_ROOT)} must have a resolving link to the canonical high-risk contract"
            )


# ---------------------------------------------------------------------------
# Cross-file consistency tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestGuardrailsDocumentationConsistency:
    """Cross-file consistency tests across all five new guardrail/policy documents."""

    @pytest.fixture
    def guardrails_content(self) -> str:
        return _load(AI_GUARDRAILS_FILE)

    @pytest.fixture
    def dep_change_content(self) -> str:
        return _load(DEPENDENCY_CHANGE_TEMPLATE)

    @pytest.fixture
    def validator_content(self) -> str:
        return _load(VALIDATOR_FOLLOWUP_TEMPLATE)

    @pytest.fixture
    def dep_policy_content(self) -> str:
        return _load(DEPENDENCY_POLICY_FILE)

    @pytest.fixture
    def pr_scope_content(self) -> str:
        return _load(PR_SCOPE_GUARDRAILS_FILE)

    def test_all_files_agree_requirements_txt_is_source_of_truth(
        self,
        guardrails_content: str,
        dep_change_content: str,
        dep_policy_content: str,
        pr_scope_content: str,
    ) -> None:
        """Every policy document must name requirements.txt as authoritative."""
        for name, content in [
            ("AI_AGENT_GUARDRAILS.md", guardrails_content),
            ("dependency-change.md", dep_change_content),
            ("DEPENDENCY_POLICY.md", dep_policy_content),
            ("PR_SCOPE_GUARDRAILS.md", pr_scope_content),
        ]:
            assert "requirements.txt" in content, f"{name} must reference requirements.txt"

    def test_all_files_reference_pyproject_toml(
        self,
        guardrails_content: str,
        dep_change_content: str,
        dep_policy_content: str,
        pr_scope_content: str,
    ) -> None:
        for name, content in [
            ("AI_AGENT_GUARDRAILS.md", guardrails_content),
            ("dependency-change.md", dep_change_content),
            ("DEPENDENCY_POLICY.md", dep_policy_content),
            ("PR_SCOPE_GUARDRAILS.md", pr_scope_content),
        ]:
            assert "pyproject.toml" in content, f"{name} must reference pyproject.toml"

    def test_guardrails_and_pr_scope_agree_on_stop_condition(
        self, guardrails_content: str, pr_scope_content: str
    ) -> None:
        """Both files must articulate a stop/split condition for second architectural decisions."""
        assert "second architectural decision" in guardrails_content.lower() or (
            "second" in guardrails_content.lower() and "architectural" in guardrails_content.lower()
        )
        assert "second architectural decision" in pr_scope_content.lower() or (
            "second" in pr_scope_content.lower() and "decision" in pr_scope_content.lower()
        )

    def test_dep_policy_and_ai_guardrails_agree_validator_must_be_fixed(
        self, guardrails_content: str, dep_policy_content: str
    ) -> None:
        """Both files must say fix the validator, not the policy."""
        assert "update the validator" in guardrails_content.lower() or "fix the validator" in guardrails_content.lower()
        assert (
            "fix the validator" in dep_policy_content.lower() or "validator or workflow" in dep_policy_content.lower()
        )

    def test_pr_templates_both_have_guardrail_checklists(self, dep_change_content: str, validator_content: str) -> None:
        """Both PR templates must include a guardrail checklist section."""
        assert "## Guardrail checklist" in dep_change_content
        assert "## Guardrail checklist" in validator_content

    def test_pr_templates_both_have_validation_run_locally(
        self, dep_change_content: str, validator_content: str
    ) -> None:
        """Both PR templates must include a validation section."""
        assert "## Validation run locally" in dep_change_content
        assert "## Validation run locally" in validator_content

    def test_dep_policy_and_pr_scope_both_prohibit_scope_broadening(
        self, dep_policy_content: str, pr_scope_content: str
    ) -> None:
        assert "broaden" in dep_policy_content.lower()
        assert "broaden" in pr_scope_content.lower()

    def test_dep_policy_validation_commands_consistent_with_dep_change_template(
        self, dep_policy_content: str, dep_change_content: str
    ) -> None:
        """Validation commands in DEPENDENCY_POLICY.md should all appear in the PR template."""
        commands = [
            "pip install -r requirements.txt",
            "pip check",
            "pip install -e .",
        ]
        for cmd in commands:
            assert cmd in dep_policy_content, f"DEPENDENCY_POLICY.md must contain command: {cmd}"
            assert cmd in dep_change_content, f"dependency-change.md template must contain command: {cmd}"

    def test_all_files_are_utf8_without_replacement_chars(
        self,
        guardrails_content: str,
        dep_change_content: str,
        validator_content: str,
        dep_policy_content: str,
        pr_scope_content: str,
    ) -> None:
        for name, content in [
            ("AI_AGENT_GUARDRAILS.md", guardrails_content),
            ("dependency-change.md", dep_change_content),
            ("validator-follow-up.md", validator_content),
            ("DEPENDENCY_POLICY.md", dep_policy_content),
            ("PR_SCOPE_GUARDRAILS.md", pr_scope_content),
        ]:
            assert "�" not in content, f"{name} must not contain UTF-8 replacement characters"

    def test_scope_class_names_consistent_between_ai_guardrails_and_pr_scope(
        self, guardrails_content: str, pr_scope_content: str
    ) -> None:
        """The PR split types in AI_AGENT_GUARDRAILS must align with scope class names in PR_SCOPE_GUARDRAILS."""
        assert "Dependency alignment" in guardrails_content or "dependency alignment" in guardrails_content.lower()
        assert "Dependency alignment" in pr_scope_content or "dependency alignment" in pr_scope_content.lower()
        assert "validator" in guardrails_content.lower()
        assert "validator" in pr_scope_content.lower()

    def test_validator_followup_template_does_not_allow_dependency_file_changes_by_default(
        self, validator_content: str
    ) -> None:
        """The validator follow-up PR template must caution against altering dependency files."""
        guardrail_section = validator_content.split("## Guardrail checklist")[1]
        assert "dependency files" in guardrail_section or "dependency file" in guardrail_section

    def test_dep_change_template_does_not_require_scope_beyond_one_decision(self, dep_change_content: str) -> None:
        """The dependency change template must reinforce the single-decision constraint."""
        guardrail_section = dep_change_content.split("## Guardrail checklist")[1]
        assert (
            "one primary" in guardrail_section.lower()
            or "single" in guardrail_section.lower()
            or "primary dependency decision" in guardrail_section.lower()
        )
