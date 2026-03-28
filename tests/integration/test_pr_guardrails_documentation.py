"""
Comprehensive validation tests for the PR guardrails and dependency policy documentation.

Covers:
- .github/AI_AGENT_GUARDRAILS.md
- .github/PULL_REQUEST_TEMPLATE/dependency-change.md
- .github/PULL_REQUEST_TEMPLATE/validator-follow-up.md
- docs/DEPENDENCY_POLICY.md
- docs/PR_SCOPE_GUARDRAILS.md
"""

import re
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

AI_GUARDRAILS_FILE = REPO_ROOT / ".github" / "AI_AGENT_GUARDRAILS.md"
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


def _lines(content: str) -> List[str]:
    return content.split("\n")


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
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert AI_GUARDRAILS_FILE.exists(), "AI_AGENT_GUARDRAILS.md must exist"
        assert AI_GUARDRAILS_FILE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0, "AI_AGENT_GUARDRAILS.md must not be empty"

    def test_title_is_level_one_heading(self, lines: List[str]) -> None:
        first_heading = next((l for l in lines if l.startswith("#")), None)
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
        bullets = [l for l in hard_rules_section.splitlines() if l.strip().startswith("- ")]
        assert len(bullets) >= 4, "Hard rules section must have at least 4 bullet items"

    def test_stop_conditions_list_is_present(self, content: str) -> None:
        stop_section = content.split("## Stop conditions")[1].split("##")[0]
        bullets = [l for l in stop_section.splitlines() if l.strip().startswith("- ")]
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

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_no_trailing_whitespace(self, lines: List[str]) -> None:
        bad = [(i + 1, l) for i, l in enumerate(lines) if l.rstrip() != l and l.strip()]
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


# ---------------------------------------------------------------------------
# dependency-change.md (PR template)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDependencyChangePRTemplate:
    """Validate .github/PULL_REQUEST_TEMPLATE/dependency-change.md."""

    @pytest.fixture
    def content(self) -> str:
        return _load(DEPENDENCY_CHANGE_TEMPLATE)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert DEPENDENCY_CHANGE_TEMPLATE.exists()
        assert DEPENDENCY_CHANGE_TEMPLATE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_has_dependency_change_summary_section(self, content: str) -> None:
        assert "## Dependency change summary" in content

    def test_has_source_of_truth_section(self, content: str) -> None:
        assert "## Source of truth" in content

    def test_has_scope_section(self, content: str) -> None:
        assert "## Scope" in content

    def test_has_files_changed_section(self, content: str) -> None:
        assert "## Files changed and why they belong together" in content

    def test_has_compatibility_risk_notes_section(self, content: str) -> None:
        assert "## Compatibility / risk notes" in content

    def test_has_validation_run_locally_section(self, content: str) -> None:
        assert "## Validation run locally" in content

    def test_has_guardrail_checklist_section(self, content: str) -> None:
        assert "## Guardrail checklist" in content

    def test_source_of_truth_checkboxes_reference_requirements_txt(self, content: str) -> None:
        sot_section = content.split("## Source of truth")[1].split("##")[0]
        assert "requirements.txt" in sot_section
        checkboxes = re.findall(r"- \[ \]", sot_section)
        assert len(checkboxes) >= 1, "Source of truth section must have at least one checkbox"

    def test_source_of_truth_checkboxes_reference_pyproject_toml(self, content: str) -> None:
        sot_section = content.split("## Source of truth")[1].split("##")[0]
        assert "pyproject.toml" in sot_section

    def test_source_of_truth_checkboxes_reference_requirements_dev_txt(self, content: str) -> None:
        sot_section = content.split("## Source of truth")[1].split("##")[0]
        assert "requirements-dev.txt" in sot_section

    def test_validation_section_includes_pip_install(self, content: str) -> None:
        validation_section = content.split("## Validation run locally")[1].split("##")[0]
        assert "pip install" in validation_section

    def test_validation_section_includes_pip_check(self, content: str) -> None:
        validation_section = content.split("## Validation run locally")[1].split("##")[0]
        assert "pip check" in validation_section

    def test_validation_section_includes_editable_install(self, content: str) -> None:
        validation_section = content.split("## Validation run locally")[1].split("##")[0]
        assert "pip install -e" in validation_section

    def test_guardrail_checklist_has_checkboxes(self, content: str) -> None:
        guardrail_section = content.split("## Guardrail checklist")[1]
        checkboxes = re.findall(r"- \[ \]", guardrail_section)
        assert len(checkboxes) >= 4, "Guardrail checklist must have at least 4 items"

    def test_guardrail_checklist_mentions_single_decision(self, content: str) -> None:
        guardrail_section = content.split("## Guardrail checklist")[1]
        assert "one primary dependency decision" in guardrail_section.lower() or "primary" in guardrail_section.lower()

    def test_scope_section_has_does_not_do_block(self, content: str) -> None:
        scope_section = content.split("## Scope")[1].split("##")[0]
        assert "does **not** do" in scope_section or "not** do" in scope_section

    def test_files_section_references_all_three_dependency_files(self, content: str) -> None:
        files_section = content.split("## Files changed and why they belong together")[1].split("##")[0]
        assert "requirements.txt" in files_section
        assert "pyproject.toml" in files_section
        assert "requirements-dev.txt" in files_section

    def test_validation_commands_block_is_bash(self, content: str) -> None:
        """Code fence in commands/outputs section should use bash language tag."""
        assert "```bash" in content

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_no_trailing_whitespace(self, lines: List[str]) -> None:
        bad = [(i + 1, l) for i, l in enumerate(lines) if l.rstrip() != l and l.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_template_has_html_comment_placeholders(self, content: str) -> None:
        """PR template should include HTML comment instructions for authors."""
        assert "<!--" in content and "-->" in content


# ---------------------------------------------------------------------------
# validator-follow-up.md (PR template)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestValidatorFollowupPRTemplate:
    """Validate .github/PULL_REQUEST_TEMPLATE/validator-follow-up.md."""

    @pytest.fixture
    def content(self) -> str:
        return _load(VALIDATOR_FOLLOWUP_TEMPLATE)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert VALIDATOR_FOLLOWUP_TEMPLATE.exists()
        assert VALIDATOR_FOLLOWUP_TEMPLATE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_has_followup_summary_section(self, content: str) -> None:
        assert "## Validator / workflow follow-up summary" in content

    def test_has_policy_being_followed_section(self, content: str) -> None:
        assert "## Policy being followed" in content

    def test_has_scope_section(self, content: str) -> None:
        assert "## Scope" in content

    def test_has_touched_files_section(self, content: str) -> None:
        assert "## Touched files" in content

    def test_has_why_this_is_separate_section(self, content: str) -> None:
        assert "## Why this is separate" in content

    def test_has_validation_run_locally_section(self, content: str) -> None:
        assert "## Validation run locally" in content

    def test_has_guardrail_checklist_section(self, content: str) -> None:
        assert "## Guardrail checklist" in content

    def test_policy_section_has_checkboxes(self, content: str) -> None:
        policy_section = content.split("## Policy being followed")[1].split("##")[0]
        checkboxes = re.findall(r"- \[ \]", policy_section)
        assert len(checkboxes) >= 2, "Policy section must have at least 2 checkboxes"

    def test_policy_section_states_no_new_dependency_policy(self, content: str) -> None:
        policy_section = content.split("## Policy being followed")[1].split("##")[0]
        assert "does not introduce a new dependency policy" in policy_section

    def test_policy_section_references_existing_documented_policy(self, content: str) -> None:
        policy_section = content.split("## Policy being followed")[1].split("##")[0]
        assert "existing documented policy" in policy_section or "existing" in policy_section

    def test_policy_section_addresses_runtime_dependency_semantics(self, content: str) -> None:
        policy_section = content.split("## Policy being followed")[1].split("##")[0]
        assert "runtime dependency semantics" in policy_section or "separate PR" in policy_section

    def test_touched_files_section_lists_tests_workflows_docs(self, content: str) -> None:
        touched_section = content.split("## Touched files")[1].split("##")[0]
        assert "tests:" in touched_section
        assert "workflows:" in touched_section
        assert "docs:" in touched_section

    def test_guardrail_checklist_has_checkboxes(self, content: str) -> None:
        guardrail_section = content.split("## Guardrail checklist")[1]
        checkboxes = re.findall(r"- \[ \]", guardrail_section)
        assert len(checkboxes) >= 3, "Guardrail checklist must have at least 3 items"

    def test_guardrail_no_dependency_file_alteration_unless_explicit(self, content: str) -> None:
        guardrail_section = content.split("## Guardrail checklist")[1]
        assert "dependency files" in guardrail_section or "dependency file" in guardrail_section

    def test_scope_section_has_does_not_change_block(self, content: str) -> None:
        scope_section = content.split("## Scope")[1].split("##")[0]
        assert "does **not** change" in scope_section or "not** change" in scope_section

    def test_validation_commands_block_is_bash(self, content: str) -> None:
        assert "```bash" in content

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_no_trailing_whitespace(self, lines: List[str]) -> None:
        bad = [(i + 1, l) for i, l in enumerate(lines) if l.rstrip() != l and l.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_template_has_html_comment_placeholders(self, content: str) -> None:
        assert "<!--" in content and "-->" in content

    def test_reference_policy_placeholder_present(self, content: str) -> None:
        """Template must prompt authors to cite the reference policy or PR."""
        assert "Reference policy or prior PR" in content


# ---------------------------------------------------------------------------
# docs/DEPENDENCY_POLICY.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDependencyPolicyDoc:
    """Validate docs/DEPENDENCY_POLICY.md structure and content."""

    @pytest.fixture
    def content(self) -> str:
        return _load(DEPENDENCY_POLICY_FILE)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert DEPENDENCY_POLICY_FILE.exists()
        assert DEPENDENCY_POLICY_FILE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_title_is_level_one_heading(self, lines: List[str]) -> None:
        first_heading = next((l for l in lines if l.startswith("#")), None)
        assert first_heading is not None
        assert first_heading.startswith("# ")
        assert "Dependency Policy" in first_heading

    def test_has_core_rule_section(self, content: str) -> None:
        assert "## Core rule" in content

    def test_has_file_roles_section(self, content: str) -> None:
        assert "## File roles" in content

    def test_has_dependency_change_order_section(self, content: str) -> None:
        assert "## Dependency change order of operations" in content

    def test_has_allowed_dependency_pr_types_section(self, content: str) -> None:
        assert "## Allowed dependency PR types" in content

    def test_has_guardrails_section(self, content: str) -> None:
        assert "## Guardrails" in content

    def test_has_required_validation_commands_section(self, content: str) -> None:
        assert "## Required validation commands" in content

    def test_has_review_checklist_section(self, content: str) -> None:
        assert "## Review checklist for dependency PRs" in content

    def test_core_rule_names_requirements_txt_as_source_of_truth(self, content: str) -> None:
        core_section = content.split("## Core rule")[1].split("##")[0]
        assert "requirements.txt" in core_section
        assert "source of truth" in core_section.lower()

    def test_file_roles_covers_requirements_txt_subsection(self, content: str) -> None:
        assert "### `requirements.txt`" in content

    def test_file_roles_covers_pyproject_toml_subsection(self, content: str) -> None:
        assert "### `pyproject.toml`" in content

    def test_file_roles_covers_requirements_dev_txt_subsection(self, content: str) -> None:
        assert "### `requirements-dev.txt`" in content

    def test_order_of_operations_has_five_steps(self, content: str) -> None:
        order_section = content.split("## Dependency change order of operations")[1].split("##")[0]
        numbered = re.findall(r"^\d+\.", order_section, re.MULTILINE)
        assert len(numbered) == 5, f"Order of operations must have exactly 5 steps, found {len(numbered)}"

    def test_order_of_operations_step_one_is_requirements_txt(self, content: str) -> None:
        order_section = content.split("## Dependency change order of operations")[1].split("##")[0]
        lines = [l.strip() for l in order_section.splitlines() if l.strip().startswith("1.")]
        assert lines, "Step 1 must exist"
        assert "requirements.txt" in lines[0], "Step 1 must reference requirements.txt"

    def test_allowed_pr_types_has_four_items(self, content: str) -> None:
        pr_types_section = content.split("## Allowed dependency PR types")[1].split("##")[0]
        numbered = re.findall(r"^\d+\.", pr_types_section, re.MULTILINE)
        assert len(numbered) == 4, f"Allowed PR types must have exactly 4 items, found {len(numbered)}"

    def test_guardrails_has_do_subsection(self, content: str) -> None:
        assert "### Do" in content

    def test_guardrails_has_do_not_subsection(self, content: str) -> None:
        assert "### Do not" in content

    def test_validation_commands_include_runtime_validation(self, content: str) -> None:
        assert "### Runtime validation" in content

    def test_validation_commands_include_editable_install_validation(self, content: str) -> None:
        assert "### Editable install validation" in content

    def test_validation_commands_include_full_dev_tooling(self, content: str) -> None:
        assert "### Full dev tooling validation" in content

    def test_validation_commands_include_core_dev_extra(self, content: str) -> None:
        assert "### Core dev extra validation" in content

    def test_runtime_validation_block_has_pip_install(self, content: str) -> None:
        runtime_section = content.split("### Runtime validation")[1].split("###")[0]
        assert "pip install -r requirements.txt" in runtime_section

    def test_runtime_validation_block_has_pip_check(self, content: str) -> None:
        runtime_section = content.split("### Runtime validation")[1].split("###")[0]
        assert "pip check" in runtime_section

    def test_editable_install_block_has_pip_install_e(self, content: str) -> None:
        editable_section = content.split("### Editable install validation")[1].split("###")[0]
        assert "pip install -e ." in editable_section

    def test_core_dev_extra_mentions_key_tools(self, content: str) -> None:
        core_dev_section = content.split("### Core dev extra validation")[1].split("##")[0]
        for tool in ["pytest", "flake8", "pylint", "mypy", "black", "isort", "ruff"]:
            assert f"{tool} --version" in core_dev_section, f"Core dev section must mention {tool} --version"

    def test_review_checklist_requirements_txt_check(self, content: str) -> None:
        checklist = content.split("## Review checklist for dependency PRs")[1]
        assert "requirements.txt" in checklist

    def test_review_checklist_pyproject_toml_check(self, content: str) -> None:
        checklist = content.split("## Review checklist for dependency PRs")[1]
        assert "pyproject.toml" in checklist

    def test_all_code_blocks_have_language_identifiers(self, content: str) -> None:
        lines = content.splitlines()
        in_fence = False
        issues = []
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("```"):
                if not in_fence and stripped == "```":
                    issues.append(f"Line {idx + 1}: code fence missing language identifier")
                in_fence = not in_fence
        assert not issues, "Code blocks must have language identifiers:\n" + "\n".join(issues)

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_no_trailing_whitespace(self, lines: List[str]) -> None:
        bad = [(i + 1, l) for i, l in enumerate(lines) if l.rstrip() != l and l.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_utf8_encoding(self) -> None:
        content = DEPENDENCY_POLICY_FILE.read_text(encoding="utf-8")
        assert "�" not in content

    def test_pyproject_toml_must_not_contradict_requirements_txt(self, content: str) -> None:
        """Policy must explicitly state pyproject.toml must not override requirements.txt."""
        assert "requirements.txt" in content
        # Confirm the subordination relationship is stated
        pyproject_section = content.split("### `pyproject.toml`")[1].split("###")[0]
        assert "requirements.txt" in pyproject_section

    def test_requirements_dev_txt_is_not_runtime_source_of_truth(self, content: str) -> None:
        dev_section = content.split("### `requirements-dev.txt`")[1].split("###")[0]
        assert "not the runtime source of truth" in dev_section or "not" in dev_section.lower()


# ---------------------------------------------------------------------------
# docs/PR_SCOPE_GUARDRAILS.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPRScopeGuardrailsDoc:
    """Validate docs/PR_SCOPE_GUARDRAILS.md structure and content."""

    @pytest.fixture
    def content(self) -> str:
        return _load(PR_SCOPE_GUARDRAILS_FILE)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert PR_SCOPE_GUARDRAILS_FILE.exists()
        assert PR_SCOPE_GUARDRAILS_FILE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_title_is_level_one_heading(self, lines: List[str]) -> None:
        first_heading = next((l for l in lines if l.startswith("#")), None)
        assert first_heading is not None
        assert first_heading.startswith("# ")
        assert "PR Scope Guardrails" in first_heading

    def test_has_default_rule_section(self, content: str) -> None:
        assert "## Default rule" in content

    def test_has_scope_classes_section(self, content: str) -> None:
        assert "## Scope classes" in content

    def test_has_size_guidance_section(self, content: str) -> None:
        assert "## Size guidance" in content

    def test_has_anti_drift_rules_section(self, content: str) -> None:
        assert "## Anti-drift rules for AI-assisted changes" in content

    def test_has_required_pr_description_sections_section(self, content: str) -> None:
        assert "## Required PR description sections" in content

    def test_has_reviewer_checklist_section(self, content: str) -> None:
        assert "## Reviewer checklist" in content

    def test_default_rule_states_one_pr_one_decision(self, content: str) -> None:
        default_section = content.split("## Default rule")[1].split("##")[0]
        assert "one primary decision" in default_section.lower() or "one pr" in default_section.lower()

    def test_scope_classes_has_dependency_alignment_class(self, content: str) -> None:
        assert "### 1. Dependency alignment" in content

    def test_scope_classes_has_validator_workflow_followup_class(self, content: str) -> None:
        assert "### 2. Validator / workflow follow-up" in content

    def test_scope_classes_has_framework_security_upgrade_class(self, content: str) -> None:
        assert "### 3. Framework or security upgrade" in content

    def test_scope_classes_has_cleanup_only_class(self, content: str) -> None:
        assert "### 4. Cleanup-only PR" in content

    def test_dependency_alignment_class_lists_requirements_txt(self, content: str) -> None:
        dep_align_section = content.split("### 1. Dependency alignment")[1].split("###")[0]
        assert "requirements.txt" in dep_align_section

    def test_dependency_alignment_class_has_not_in_scope_block(self, content: str) -> None:
        dep_align_section = content.split("### 1. Dependency alignment")[1].split("###")[0]
        assert "Not in scope:" in dep_align_section

    def test_size_guidance_has_preferred_subsection(self, content: str) -> None:
        assert "### Preferred" in content

    def test_size_guidance_has_caution_zone_subsection(self, content: str) -> None:
        assert "### Caution zone" in content

    def test_size_guidance_has_stop_and_split_subsection(self, content: str) -> None:
        assert "### Stop and split" in content

    def test_preferred_size_specifies_file_limit(self, content: str) -> None:
        preferred_section = content.split("### Preferred")[1].split("###")[0]
        assert "8" in preferred_section, "Preferred section must mention the file count limit"

    def test_preferred_size_specifies_line_limit(self, content: str) -> None:
        preferred_section = content.split("### Preferred")[1].split("###")[0]
        assert "300" in preferred_section, "Preferred section must mention the line count limit"

    def test_anti_drift_has_ai_agent_rules_subsection(self, content: str) -> None:
        assert "### AI agent rules" in content

    def test_ai_agent_rules_prohibit_scope_broadening(self, content: str) -> None:
        ai_section = content.split("### AI agent rules")[1].split("##")[0]
        assert "broaden" in ai_section.lower() or "scope" in ai_section.lower()

    def test_ai_agent_rules_state_follow_up_pr_for_second_decision(self, content: str) -> None:
        ai_section = content.split("### AI agent rules")[1].split("##")[0]
        assert "follow-up" in ai_section.lower() or "follow up" in ai_section.lower()

    def test_required_pr_description_sections_lists_four_items(self, content: str) -> None:
        pr_desc_section = content.split("## Required PR description sections")[1].split("##")[0]
        bullets = [l for l in pr_desc_section.splitlines() if l.strip().startswith("- ")]
        assert len(bullets) >= 4, "Required PR description sections must have at least 4 bullet items"

    def test_reviewer_checklist_has_bullet_items(self, content: str) -> None:
        reviewer_section = content.split("## Reviewer checklist")[1]
        bullets = [l for l in reviewer_section.splitlines() if l.strip().startswith("- ")]
        assert len(bullets) >= 3, "Reviewer checklist must have at least 3 items"

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_no_trailing_whitespace(self, lines: List[str]) -> None:
        bad = [(i + 1, l) for i, l in enumerate(lines) if l.rstrip() != l and l.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_utf8_encoding(self) -> None:
        content = PR_SCOPE_GUARDRAILS_FILE.read_text(encoding="utf-8")
        assert "�" not in content

    def test_four_scope_classes_present(self, content: str) -> None:
        """All four scope classes must be defined."""
        for class_num in range(1, 5):
            assert f"### {class_num}." in content, f"Scope class {class_num} must be present"

    def test_stop_and_split_conditions_listed(self, content: str) -> None:
        split_section = content.split("### Stop and split")[1].split("##")[0]
        bullets = [l for l in split_section.splitlines() if l.strip().startswith("- ")]
        assert len(bullets) >= 3, "Stop and split section must list at least 3 conditions"


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
