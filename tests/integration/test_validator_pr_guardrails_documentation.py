"""
Validation tests for validator-follow-up PR and PR-scope documentation.

Covers:
- .github/PULL_REQUEST_TEMPLATE/validator-follow-up.md
- docs/PR_SCOPE_GUARDRAILS.md
"""

import re
from pathlib import Path

import pytest

from tests.integration.pr_guardrails_test_support import markdown_section

REPO_ROOT = Path(__file__).parent.parent.parent


def _load(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(content: str) -> list[str]:
    return content.splitlines()


VALIDATOR_FOLLOWUP_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "validator-follow-up.md"
PR_SCOPE_GUARDRAILS_FILE = REPO_ROOT / "docs" / "PR_SCOPE_GUARDRAILS.md"


@pytest.mark.integration
class TestMarkdownSectionHelper:
    """Prove shared section extraction fails closed on ambiguous documents."""

    def test_returns_target_body_with_nested_subheading(self) -> None:
        """Nested headings remain inside the requested section."""
        content = "# Document\n## Target\nalpha\n### Nested\nbeta\n## Next\ngamma\n"
        assert markdown_section(content, "## Target") == "alpha\n### Nested\nbeta"

    @pytest.mark.parametrize(("opening", "closing"), [("```markdown", "```"), ("~~~markdown", "~~~")])
    def test_ignores_heading_like_lines_inside_fenced_code(self, opening: str, closing: str) -> None:
        """Fenced examples cannot duplicate or truncate a live section."""
        content = f"# Document\n## Target\nbefore\n{opening}\n## Target\n## Next\n{closing}\nafter\n## Next\nend\n"
        expected = f"before\n{opening}\n## Target\n## Next\n{closing}\nafter"
        assert markdown_section(content, "## Target") == expected

    @pytest.mark.parametrize(
        "content",
        [
            "# Document\n## Other\nbody\n",
            "# Document\n## Target\none\n## Target\ntwo\n",
        ],
        ids=["missing", "duplicate"],
    )
    def test_rejects_missing_or_duplicate_heading(self, content: str) -> None:
        """A missing or duplicate exact heading cannot silently select content."""
        with pytest.raises(AssertionError, match="must appear exactly once"):
            markdown_section(content, "## Target")


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
    def lines(self, content: str) -> list[str]:
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

    def test_headings_have_space_after_hash(self, lines: list[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_no_trailing_whitespace(self, lines: list[str]) -> None:
        bad = [(i + 1, line) for i, line in enumerate(lines) if line.rstrip() != line and line.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_template_has_html_comment_placeholders(self, content: str) -> None:
        assert "<!--" in content and "-->" in content

    def test_reference_policy_placeholder_present(self, content: str) -> None:
        """Template must prompt authors to cite the reference policy or PR."""
        assert "Reference policy or prior PR" in content


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
    def lines(self, content: str) -> list[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert PR_SCOPE_GUARDRAILS_FILE.exists()
        assert PR_SCOPE_GUARDRAILS_FILE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_title_is_level_one_heading(self, lines: list[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
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
        default_section = markdown_section(content, "## Default rule")
        assert "One PR should carry one primary decision." in default_section

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

    def test_required_pr_description_sections_lists_six_canonical_items(self, content: str) -> None:
        automated_section = markdown_section(content, "### Automated and agent-authored PRs")
        numbered = re.findall(r"^(\d+)\. \*\*([^*]+)\*\*:", automated_section, re.MULTILINE)
        assert numbered == [
            ("1", "Primary Objective"),
            ("2", "In Scope"),
            ("3", "Out of Scope"),
            ("4", "Files Expected to Change"),
            ("5", "Validation Commands"),
            ("6", "Merge Criteria"),
        ]

    def test_required_pr_sections_preserve_actor_strength_and_local_evidence(self, content: str) -> None:
        pr_desc_section = content.split("## Required PR description sections")[1].split("\n## ", maxsplit=1)[0]
        assert "### Automated and agent-authored PRs" in pr_desc_section
        assert "All automated and agent-authored PRs must complete" in pr_desc_section
        assert "### General non-trivial PRs" in pr_desc_section
        assert "Every non-trivial PR should state" in pr_desc_section
        assert "what commands were run locally" in pr_desc_section

    def test_reviewer_checklist_has_bullet_items(self, content: str) -> None:
        reviewer_section = content.split("## Reviewer checklist")[1]
        bullets = [line for line in reviewer_section.splitlines() if line.strip().startswith("- ")]
        assert len(bullets) >= 3, "Reviewer checklist must have at least 3 items"

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

    def test_utf8_encoding(self) -> None:
        content = PR_SCOPE_GUARDRAILS_FILE.read_text(encoding="utf-8")
        assert "�" not in content

    def test_four_scope_classes_present(self, content: str) -> None:
        """All four scope classes must be defined."""
        for class_num in range(1, 5):
            assert f"### {class_num}." in content, f"Scope class {class_num} must be present"

    def test_stop_and_split_conditions_listed(self, content: str) -> None:
        split_section = content.split("### Stop and split")[1].split("##")[0]
        bullets = [line for line in split_section.splitlines() if line.strip().startswith("- ")]
        assert len(bullets) >= 3, "Stop and split section must list at least 3 conditions"
