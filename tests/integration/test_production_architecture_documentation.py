"""
Integration tests for the production architecture documentation introduced in this PR.

Covers:
- .github/AUTOMATION_SCOPE_POLICY.md  (new)
- .github/PULL_REQUEST_TEMPLATE/architecture-docs.md  (new)
- .github/pull_request_template.md  (modified - new sections only)
- ARCHITECTURE.md  (modified - production/non-production labelling)
- DEPLOYMENT.md  (modified - production architecture framing)
- README.md  (modified - production path framing)
- docs/adr/0001-production-architecture.md  (new)
"""

import re
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

AUTOMATION_SCOPE_POLICY = REPO_ROOT / ".github" / "AUTOMATION_SCOPE_POLICY.md"
ARCHITECTURE_DOCS_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "architecture-docs.md"
LEGACY_PULL_REQUEST_TEMPLATE = REPO_ROOT / ".github" / "pull_request_template.md"
ARCHITECTURE_MD = REPO_ROOT / "ARCHITECTURE.md"
DEPLOYMENT_MD = REPO_ROOT / "DEPLOYMENT.md"
README_MD = REPO_ROOT / "README.md"
ADR_0001 = REPO_ROOT / "docs" / "adr" / "0001-production-architecture.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(content: str) -> List[str]:
    return content.splitlines()


def _resolve_primary_pr_template() -> Path:
    """
    Resolve the repository's default PR template path.

    Preference order:
    1) legacy root-level .github/pull_request_template.md
    2) architecture-docs template under .github/PULL_REQUEST_TEMPLATE
    """
    if LEGACY_PULL_REQUEST_TEMPLATE.exists():
        return LEGACY_PULL_REQUEST_TEMPLATE
    return ARCHITECTURE_DOCS_TEMPLATE


# ---------------------------------------------------------------------------
# .github/AUTOMATION_SCOPE_POLICY.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAutomationScopePolicy:
    """Validate .github/AUTOMATION_SCOPE_POLICY.md structure and content."""

    @pytest.fixture
    def content(self) -> str:
        return _load(AUTOMATION_SCOPE_POLICY)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert AUTOMATION_SCOPE_POLICY.exists(), "AUTOMATION_SCOPE_POLICY.md must exist"
        assert AUTOMATION_SCOPE_POLICY.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0, "AUTOMATION_SCOPE_POLICY.md must not be empty"

    def test_title_is_level_one_heading(self, lines: List[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
        assert first_heading is not None, "File must have at least one heading"
        assert first_heading.startswith("# "), "First heading must be H1"
        assert "Automation Scope Policy" in first_heading

    def test_has_purpose_section(self, content: str) -> None:
        assert "## Purpose" in content

    def test_has_authority_section(self, content: str) -> None:
        assert "## Authority" in content

    def test_has_core_principle_section(self, content: str) -> None:
        assert "## Core Principle" in content

    def test_has_production_architecture_boundary_section(self, content: str) -> None:
        assert "## Production Architecture Boundary" in content

    def test_has_pr_scope_boundaries_section(self, content: str) -> None:
        assert "## PR Scope Boundaries" in content

    def test_has_dependency_management_section(self, content: str) -> None:
        assert "## Dependency Management" in content

    def test_has_security_scanning_section(self, content: str) -> None:
        assert "## Security Scanning" in content

    def test_has_testing_and_cicd_section(self, content: str) -> None:
        assert "## Testing and CI/CD" in content

    def test_has_documentation_updates_section(self, content: str) -> None:
        assert "## Documentation Updates" in content

    def test_has_escalation_path_section(self, content: str) -> None:
        assert "## Escalation Path" in content

    def test_has_enforcement_section(self, content: str) -> None:
        assert "## Enforcement" in content

    def test_has_related_documents_section(self, content: str) -> None:
        assert "## Related Documents" in content

    def test_has_version_section(self, content: str) -> None:
        assert "## Version" in content

    def test_declares_fastapi_nextjs_as_production(self, content: str) -> None:
        assert "FastAPI" in content
        assert "Next.js" in content
        # The "Production Architecture Boundary" section contains subsections (###) so
        # we search the entire block from this heading to the next top-level section (## )
        production_block = content.split("## Production Architecture Boundary")[1].split("\n## ")[0]
        assert "FastAPI" in production_block
        assert "Next.js" in production_block

    def test_declares_gradio_as_non_production(self, content: str) -> None:
        production_block = content.split("## Production Architecture Boundary")[1].split("\n## ")[0]
        assert "Gradio" in production_block
        assert "Non-Production" in production_block or "non-production" in production_block.lower()

    def test_references_adr_0001(self, content: str) -> None:
        assert "0001-production-architecture.md" in content

    def test_required_pr_sections_lists_primary_objective(self, content: str) -> None:
        pr_sections = content.split("### Required PR Sections")[1].split("###")[0]
        assert "Primary Objective" in pr_sections

    def test_required_pr_sections_lists_in_scope(self, content: str) -> None:
        pr_sections = content.split("### Required PR Sections")[1].split("###")[0]
        assert "In Scope" in pr_sections

    def test_required_pr_sections_lists_out_of_scope(self, content: str) -> None:
        pr_sections = content.split("### Required PR Sections")[1].split("###")[0]
        assert "Out of Scope" in pr_sections

    def test_required_pr_sections_lists_validation_commands(self, content: str) -> None:
        pr_sections = content.split("### Required PR Sections")[1].split("###")[0]
        assert "Validation Commands" in pr_sections

    def test_required_pr_sections_lists_merge_criteria(self, content: str) -> None:
        pr_sections = content.split("### Required PR Sections")[1].split("###")[0]
        assert "Merge Criteria" in pr_sections

    def test_required_pr_sections_has_six_items(self, content: str) -> None:
        pr_sections = content.split("### Required PR Sections")[1].split("###")[0]
        numbered_items = re.findall(r"^\d+\.", pr_sections, re.MULTILINE)
        assert len(numbered_items) == 6, f"Required PR sections must list 6 items, found {len(numbered_items)}"

    def test_prohibited_scope_expansion_has_items(self, content: str) -> None:
        prohibited_section = content.split("### Prohibited Scope Expansion")[1].split("###")[0]
        numbered = re.findall(r"^\d+\.", prohibited_section, re.MULTILINE)
        assert len(numbered) >= 3, "Prohibited scope expansion must list at least 3 items"

    def test_dependency_source_of_truth_names_requirements_txt(self, content: str) -> None:
        # The Dependency Management section has subsections (###), so search the full block
        dep_block = content.split("## Dependency Management")[1].split("\n## ")[0]
        assert "requirements.txt" in dep_block
        assert "source of truth" in dep_block.lower() or "authoritative" in dep_block.lower()

    def test_version_info_is_present(self, content: str) -> None:
        version_section = content.split("## Version")[1]
        assert "Version" in version_section
        assert "Effective Date" in version_section or "Last Updated" in version_section

    def test_version_date_matches_pr_date(self, content: str) -> None:
        version_section = content.split("## Version")[1]
        assert "2026-04-17" in version_section

    def test_core_principle_states_tools_may_not_redefine_scope(self, content: str) -> None:
        core_section = content.split("## Core Principle")[1].split("##")[0]
        assert "redefine" in core_section.lower() or "may not redefine" in core_section.lower()

    def test_authority_lists_ai_coding_agents(self, content: str) -> None:
        authority_section = content.split("## Authority")[1].split("##")[0]
        assert "AI coding agents" in authority_section or "Claude" in authority_section

    def test_authority_lists_dependency_bots(self, content: str) -> None:
        authority_section = content.split("## Authority")[1].split("##")[0]
        assert "Dependabot" in authority_section or "dependency" in authority_section.lower()

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_no_trailing_whitespace(self, lines: List[str]) -> None:
        bad = [(i + 1, line) for i, line in enumerate(lines) if line.rstrip() != line and line.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_utf8_encoding(self) -> None:
        content = AUTOMATION_SCOPE_POLICY.read_text(encoding="utf-8")
        assert "�" not in content, "File must not contain UTF-8 replacement characters"

    def test_no_hardcoded_secrets(self, content: str) -> None:
        secret_patterns = [
            r"ghp_[a-zA-Z0-9]{36}",
            r"gho_[a-zA-Z0-9]{36}",
        ]
        for pattern in secret_patterns:
            assert not re.search(pattern, content), f"File must not contain hardcoded tokens (pattern: {pattern})"

    def test_references_pr_scope_guardrails(self, content: str) -> None:
        assert "PR_SCOPE_GUARDRAILS.md" in content

    def test_references_dependency_policy(self, content: str) -> None:
        assert "DEPENDENCY_POLICY.md" in content

    def test_rules_for_automated_changes_has_four_items(self, content: str) -> None:
        rules_section = content.split("### Rules for Automated Changes")[1].split("###")[0]
        numbered = re.findall(r"^\d+\.", rules_section, re.MULTILINE)
        assert len(numbered) == 4, f"Rules for automated changes must have 4 items, found {len(numbered)}"

    def test_escalation_path_says_create_issue_not_pr(self, content: str) -> None:
        escalation_section = content.split("## Escalation Path")[1].split("##")[0]
        assert "issue" in escalation_section.lower()
        # The policy states "Create an issue (not a PR)"
        assert "not a PR" in escalation_section or "not a pr" in escalation_section.lower()


# ---------------------------------------------------------------------------
# .github/PULL_REQUEST_TEMPLATE/architecture-docs.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestArchitectureDocsPRTemplate:
    """Validate .github/PULL_REQUEST_TEMPLATE/architecture-docs.md structure and content."""

    @pytest.fixture
    def content(self) -> str:
        return _load(ARCHITECTURE_DOCS_TEMPLATE)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert ARCHITECTURE_DOCS_TEMPLATE.exists(), "architecture-docs.md template must exist"
        assert ARCHITECTURE_DOCS_TEMPLATE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_has_primary_objective_section(self, content: str) -> None:
        assert "## Primary Objective" in content

    def test_has_description_section(self, content: str) -> None:
        assert "## Description" in content

    def test_has_in_scope_section(self, content: str) -> None:
        assert "## In Scope" in content

    def test_has_out_of_scope_section(self, content: str) -> None:
        assert "## Out of Scope" in content

    def test_has_files_expected_to_change_section(self, content: str) -> None:
        assert "## Files Expected to Change" in content

    def test_has_type_of_change_section(self, content: str) -> None:
        assert "## Type of Change" in content

    def test_has_rationale_section(self, content: str) -> None:
        assert "## Rationale" in content

    def test_has_impact_assessment_section(self, content: str) -> None:
        assert "## Impact Assessment" in content

    def test_has_validation_commands_section(self, content: str) -> None:
        assert "## Validation Commands" in content

    def test_has_merge_criteria_section(self, content: str) -> None:
        assert "## Merge Criteria" in content

    def test_has_checklist_section(self, content: str) -> None:
        assert "## Checklist" in content

    def test_type_of_change_has_adr_checkbox(self, content: str) -> None:
        type_section = content.split("## Type of Change")[1].split("##")[0]
        assert "Architecture decision" in type_section or "ADR" in type_section

    def test_type_of_change_has_documentation_update_checkbox(self, content: str) -> None:
        type_section = content.split("## Type of Change")[1].split("##")[0]
        assert "Documentation update" in type_section

    def test_type_of_change_has_policy_document_checkbox(self, content: str) -> None:
        type_section = content.split("## Type of Change")[1].split("##")[0]
        assert "Policy document" in type_section

    def test_merge_criteria_has_checkboxes(self, content: str) -> None:
        merge_section = content.split("## Merge Criteria")[1].split("##")[0]
        checkboxes = re.findall(r"- \[[ x]\]", merge_section)
        assert len(checkboxes) >= 3, "Merge Criteria must have at least 3 checkboxes"

    def test_merge_criteria_mentions_architectural_consistency(self, content: str) -> None:
        merge_section = content.split("## Merge Criteria")[1].split("##")[0]
        assert "architectural" in merge_section.lower() or "architecture" in merge_section.lower()

    def test_merge_criteria_excludes_runtime_code_changes(self, content: str) -> None:
        merge_section = content.split("## Merge Criteria")[1].split("##")[0]
        assert "runtime" in merge_section.lower() or "code changes" in merge_section.lower()

    def test_checklist_has_architectural_alignment_subsection(self, content: str) -> None:
        assert "### Architectural Alignment" in content

    def test_architectural_alignment_references_fastapi_nextjs(self, content: str) -> None:
        alignment_section = content.split("### Architectural Alignment")[1].split("###")[0]
        assert "FastAPI" in alignment_section
        assert "Next.js" in alignment_section

    def test_checklist_has_scope_compliance_subsection(self, content: str) -> None:
        assert "### Scope Compliance" in content

    def test_scope_compliance_enforces_single_decision(self, content: str) -> None:
        scope_section = content.split("### Scope Compliance")[1].split("###")[0]
        assert "one primary decision" in scope_section.lower() or "primary" in scope_section.lower()

    def test_checklist_has_documentation_quality_subsection(self, content: str) -> None:
        assert "### Documentation Quality" in content

    def test_has_html_comment_placeholders(self, content: str) -> None:
        assert "<!--" in content and "-->" in content

    def test_validation_commands_has_bash_code_block(self, content: str) -> None:
        assert "```bash" in content

    def test_references_automation_scope_policy(self, content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in content

    def test_references_pr_scope_guardrails(self, content: str) -> None:
        assert "PR_SCOPE_GUARDRAILS.md" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_impact_assessment_has_positive_subsection(self, content: str) -> None:
        assert "### Positive Impacts" in content

    def test_impact_assessment_has_potential_concerns_subsection(self, content: str) -> None:
        assert "### Potential Concerns" in content

    def test_impact_assessment_has_mitigation_strategy_subsection(self, content: str) -> None:
        assert "### Mitigation Strategy" in content

    def test_has_for_reviewers_block(self, content: str) -> None:
        assert "For Reviewers" in content


# ---------------------------------------------------------------------------
# .github/pull_request_template.md  (changed sections)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPullRequestTemplateChangedSections:
    """Validate required sections on the repository's default PR template."""

    @pytest.fixture
    def content(self) -> str:
        return _load(_resolve_primary_pr_template())

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        template_path = _resolve_primary_pr_template()
        assert template_path.exists(), "A default PR template must exist"
        assert template_path.is_file()

    def test_has_primary_objective_section(self, content: str) -> None:
        assert "## Primary Objective" in content

    def test_has_scope_section(self, content: str) -> None:
        assert "## Scope" in content or ("## In Scope" in content and "## Out of Scope" in content)

    def test_has_in_scope_subsection(self, content: str) -> None:
        assert "### In Scope" in content or "## In Scope" in content

    def test_has_out_of_scope_subsection(self, content: str) -> None:
        assert "### Out of Scope" in content or "## Out of Scope" in content

    def test_has_files_expected_to_change_subsection(self, content: str) -> None:
        assert "### Files Expected to Change" in content or "## Files Expected to Change" in content

    def test_has_validation_commands_section(self, content: str) -> None:
        assert "## Validation Commands" in content

    def test_has_merge_criteria_section(self, content: str) -> None:
        assert "## Merge Criteria" in content

    def test_has_scope_compliance_checklist(self, content: str) -> None:
        assert "### Scope Compliance" in content

    def test_scope_compliance_enforces_single_decision(self, content: str) -> None:
        scope_section = content.split("### Scope Compliance")[1].split("###")[0]
        assert "one primary decision" in scope_section.lower() or "primary decision" in scope_section.lower()

    def test_scope_compliance_prohibits_mixing_unrelated_concerns(self, content: str) -> None:
        scope_section = content.split("### Scope Compliance")[1].split("###")[0]
        assert "unrelated" in scope_section.lower() or "mixed" in scope_section.lower()

    def test_scope_compliance_references_production_architecture(self, content: str) -> None:
        scope_section = content.split("### Scope Compliance")[1].split("###")[0]
        assert "FastAPI" in scope_section and "Next.js" in scope_section

    def test_scope_compliance_references_automation_scope_policy(self, content: str) -> None:
        scope_section = content.split("### Scope Compliance")[1].split("###")[0]
        assert "AUTOMATION_SCOPE_POLICY.md" in scope_section

    def test_scope_compliance_has_checkboxes(self, content: str) -> None:
        scope_section = content.split("### Scope Compliance")[1].split("###")[0]
        checkboxes = re.findall(r"- \[[ x]\]", scope_section)
        assert len(checkboxes) >= 3, "Scope Compliance must have at least 3 checkboxes"

    def test_merge_criteria_has_checkboxes(self, content: str) -> None:
        merge_section = content.split("## Merge Criteria")[1].split("##")[0]
        checkboxes = re.findall(r"- \[[ x]\]", merge_section)
        assert len(checkboxes) >= 2, "Merge Criteria must have at least 2 checkboxes"

    def test_validation_commands_has_bash_code_block(self, content: str) -> None:
        validation_section = content.split("## Validation Commands")[1].split("##")[0]
        assert "```bash" in validation_section or "```" in validation_section

    def test_primary_objective_references_automation_scope_policy(self, content: str) -> None:
        primary_section = content.split("## Primary Objective")[1].split("##")[0]
        assert "AUTOMATION_SCOPE_POLICY.md" in primary_section

    def test_scope_review_footer_references_pr_scope_guardrails(self, content: str) -> None:
        assert "PR_SCOPE_GUARDRAILS.md" in content

    def test_scope_review_footer_references_automation_scope_policy(self, content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_has_html_comment_placeholders(self, content: str) -> None:
        assert "<!--" in content and "-->" in content


# ---------------------------------------------------------------------------
# ARCHITECTURE.md  (changed sections)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestArchitectureMdProductionLabels:
    """Validate the production/non-production labelling added to ARCHITECTURE.md in this PR."""

    @pytest.fixture
    def content(self) -> str:
        return _load(ARCHITECTURE_MD)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert ARCHITECTURE_MD.exists()
        assert ARCHITECTURE_MD.is_file()

    def test_title_is_architecture_overview(self, lines: List[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
        assert first_heading is not None
        assert "Architecture" in first_heading

    def test_declares_production_architecture_at_top(self, content: str) -> None:
        """Production architecture declaration must appear before the first section."""
        # Find position of the declaration and first section
        decl_pos = content.find("FastAPI backend + Next.js frontend")
        first_section_pos = content.find("## System Architecture")
        assert decl_pos != -1, "Must declare FastAPI + Next.js as production architecture"
        assert decl_pos < first_section_pos, "Production declaration must appear before System Architecture section"

    def test_has_production_label_for_nextjs(self, content: str) -> None:
        assert "PRODUCTION" in content
        # The label should be near Next.js
        nextjs_pos = content.find("Next.js UI")
        production_label_pos = content.find("** PRODUCTION **")
        assert production_label_pos != -1, "PRODUCTION label must be present"
        # They should be close (within 200 characters of each other in the diagram)
        assert abs(nextjs_pos - production_label_pos) < 200, "PRODUCTION label should be near Next.js UI"

    def test_has_non_production_label_for_gradio(self, content: str) -> None:
        assert "NON-PRODUCTION" in content
        # Search for the diagram-specific "Gradio UI (Port 7860)" label
        gradio_diagram_pos = content.find("Gradio UI (Port 7860)")
        non_prod_pos = content.find("NON-PRODUCTION")
        assert non_prod_pos != -1, "NON-PRODUCTION label must be present"
        assert gradio_diagram_pos != -1, "Gradio UI (Port 7860) must appear in diagram"
        # Both labels appear in the diagram section within a reasonable proximity
        assert (
            abs(gradio_diagram_pos - non_prod_pos) < 500
        ), "NON-PRODUCTION label should be near Gradio UI diagram entry"

    def test_http_rest_api_is_labeled_production_path(self, content: str) -> None:
        assert "** PRODUCTION PATH **" in content or "PRODUCTION PATH" in content

    def test_direct_function_calls_labeled_demo_testing(self, content: str) -> None:
        assert "DEMO/TESTING" in content or "** DEMO/TESTING **" in content

    def test_has_production_flow_section(self, content: str) -> None:
        assert "Production Flow" in content

    def test_has_non_production_flow_section(self, content: str) -> None:
        assert "Non-Production Flow" in content

    def test_production_flow_mentions_nextjs_and_fastapi(self, content: str) -> None:
        prod_flow_section = content.split("Production Flow")[1].split("Non-Production")[0]
        assert "Next.js" in prod_flow_section or "FastAPI" in prod_flow_section

    def test_non_production_flow_mentions_gradio(self, content: str) -> None:
        non_prod_section = content.split("Non-Production Flow")[1]
        # Get the section content (up to next major section)
        non_prod_content = non_prod_section.split("##")[0]
        assert "Gradio" in non_prod_content

    def test_gradio_is_labeled_not_production_path(self, content: str) -> None:
        assert "not the production path" in content.lower() or "non-production" in content.lower()

    def test_references_adr_0001(self, content: str) -> None:
        assert "0001-production-architecture.md" in content

    def test_frontend_technologies_labels_nextjs_production(self, content: str) -> None:
        # Check that the frontend stack section labels Next.js as production
        nextjs_stack_pos = content.find("Next.js Frontend Stack")
        production_label = content.find("** PRODUCTION **", nextjs_stack_pos)
        assert nextjs_stack_pos != -1, "Next.js Frontend Stack section must exist"
        assert (
            production_label != -1 and production_label < nextjs_stack_pos + 200
        ), "PRODUCTION label must appear in Next.js stack section"

    def test_frontend_technologies_labels_gradio_non_production(self, content: str) -> None:
        gradio_stack_pos = content.find("Gradio Frontend Stack")
        non_prod_label = content.find("** NON-PRODUCTION **", gradio_stack_pos)
        assert gradio_stack_pos != -1, "Gradio Frontend Stack section must exist"
        assert (
            non_prod_label != -1 and non_prod_label < gradio_stack_pos + 200
        ), "NON-PRODUCTION label must appear in Gradio stack section"

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_utf8_encoding(self) -> None:
        content = ARCHITECTURE_MD.read_text(encoding="utf-8")
        assert "�" not in content


# ---------------------------------------------------------------------------
# DEPLOYMENT.md  (changed sections)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestDeploymentMdProductionFraming:
    """Validate the production architecture framing added to DEPLOYMENT.md in this PR."""

    @pytest.fixture
    def content(self) -> str:
        return _load(DEPLOYMENT_MD)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert DEPLOYMENT_MD.exists()
        assert DEPLOYMENT_MD.is_file()

    def test_title_mentions_production_architecture(self, lines: List[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
        assert first_heading is not None
        assert "Production" in first_heading, "Deployment guide title must mention Production Architecture"

    def test_declares_fastapi_nextjs_as_production_at_top(self, content: str) -> None:
        top_section = content[:500]
        assert "FastAPI" in top_section
        assert "Next.js" in top_section

    def test_notes_gradio_is_not_recommended_for_production(self, content: str) -> None:
        assert "not recommended for production" in content.lower()

    def test_backend_setup_section_mentions_fastapi(self, content: str) -> None:
        assert "Backend Setup" in content
        backend_section = content.split("Backend Setup")[1].split("###")[0]
        assert "FastAPI" in backend_section or "Production" in backend_section

    def test_has_gradio_non_production_alternative_section(self, content: str) -> None:
        assert "Gradio" in content
        assert "Non-Production" in content or "non-production" in content.lower()

    def test_gradio_section_says_not_for_production(self, content: str) -> None:
        gradio_pos = content.find("Gradio")
        # Find "not recommended" near the Gradio section
        after_gradio = content[gradio_pos:]
        assert "not recommended" in after_gradio.lower() or "non-production" in after_gradio.lower()

    def test_production_architecture_stated_in_overview(self, content: str) -> None:
        overview_section = content.split("## Architecture Overview")[1].split("##")[0]
        assert "FastAPI" in overview_section or "production" in overview_section.lower()

    def test_backend_and_frontend_are_two_main_components(self, content: str) -> None:
        overview_section = content.split("## Architecture Overview")[1].split("##")[0]
        assert "Backend" in overview_section and "Frontend" in overview_section

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_utf8_encoding(self) -> None:
        content = DEPLOYMENT_MD.read_text(encoding="utf-8")
        assert "�" not in content

    def test_gradio_section_is_labelled_alternative_not_primary(self, content: str) -> None:
        """Gradio must appear as an alternative, not the primary setup path."""
        gradio_section_heading = "Alternative" in content and "Gradio" in content
        assert gradio_section_heading, "Gradio must be presented as an alternative path"


# ---------------------------------------------------------------------------
# README.md  (changed sections)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestReadmeMdProductionFraming:
    """Validate the production path framing added to README.md in this PR."""

    @pytest.fixture
    def content(self) -> str:
        return _load(README_MD)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert README_MD.exists()
        assert README_MD.is_file()

    def test_has_production_setup_section(self, content: str) -> None:
        assert "Production Setup" in content

    def test_production_setup_mentions_nextjs_and_fastapi(self, content: str) -> None:
        prod_section_pos = content.find("Production Setup")
        prod_section = content[prod_section_pos : prod_section_pos + 500]
        assert "Next.js" in prod_section
        assert "FastAPI" in prod_section

    def test_production_path_is_recommended(self, content: str) -> None:
        prod_section_pos = content.find("Production Setup")
        prod_section = content[prod_section_pos : prod_section_pos + 300]
        assert "recommended" in prod_section.lower()

    def test_gradio_is_labeled_non_production(self, content: str) -> None:
        assert "Non-Production" in content or "non-production" in content.lower()

    def test_gradio_section_is_demo_or_internal(self, content: str) -> None:
        assert "demo" in content.lower() or "internal" in content.lower()

    def test_gradio_not_recommended_for_production_deployment(self, content: str) -> None:
        assert "not recommended for production deployment" in content.lower()

    def test_fastapi_port_8000_mentioned(self, content: str) -> None:
        assert "8000" in content

    def test_nextjs_port_3000_mentioned(self, content: str) -> None:
        assert "3000" in content

    def test_references_deployment_md(self, content: str) -> None:
        assert "DEPLOYMENT.md" in content

    def test_node_label_says_production_frontend(self, content: str) -> None:
        """Node.js requirement comment should indicate it's for the production frontend."""
        assert "production frontend" in content.lower() or "Node.js 18+" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_utf8_encoding(self) -> None:
        content = README_MD.read_text(encoding="utf-8")
        assert "�" not in content

    def test_gradio_setup_is_not_option_1(self, content: str) -> None:
        """Gradio must no longer be presented as 'Option 1' (primary option)."""
        assert "Option 1: Gradio" not in content and "Option 1 : Gradio" not in content


# ---------------------------------------------------------------------------
# docs/adr/0001-production-architecture.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestProductionArchitectureADR:
    """Validate docs/adr/0001-production-architecture.md structure and content."""

    @pytest.fixture
    def content(self) -> str:
        return _load(ADR_0001)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert ADR_0001.exists(), "ADR 0001 must exist"
        assert ADR_0001.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_title_is_level_one_heading(self, lines: List[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
        assert first_heading is not None
        assert first_heading.startswith("# ")
        assert "ADR 0001" in first_heading or "Production Architecture" in first_heading

    def test_title_mentions_fastapi_and_nextjs(self, lines: List[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("# ")), None)
        assert first_heading is not None
        assert "FastAPI" in first_heading and "Next.js" in first_heading

    def test_has_status_section(self, content: str) -> None:
        assert "## Status" in content

    def test_status_is_accepted(self, content: str) -> None:
        status_section = content.split("## Status")[1].split("##")[0]
        assert "Accepted" in status_section, "ADR status must be 'Accepted'"

    def test_has_date_section(self, content: str) -> None:
        assert "## Date" in content

    def test_date_is_2026_04_17(self, content: str) -> None:
        date_section = content.split("## Date")[1].split("##")[0]
        assert "2026-04-17" in date_section

    def test_has_context_section(self, content: str) -> None:
        assert "## Context" in content

    def test_has_decision_section(self, content: str) -> None:
        assert "## Decision" in content

    def test_has_consequences_section(self, content: str) -> None:
        assert "## Consequences" in content

    def test_has_alternatives_considered_section(self, content: str) -> None:
        assert "## Alternatives Considered" in content

    def test_has_implementation_plan_section(self, content: str) -> None:
        assert "## Implementation Plan" in content

    def test_has_references_section(self, content: str) -> None:
        assert "## References" in content

    def test_decision_declares_fastapi_nextjs_production(self, content: str) -> None:
        decision_section = content.split("## Decision")[1].split("##")[0]
        assert "FastAPI" in decision_section
        assert "Next.js" in decision_section
        assert "production" in decision_section.lower()

    def test_decision_demotes_gradio_to_non_production(self, content: str) -> None:
        decision_section = content.split("## Decision")[1].split("##")[0]
        assert "Gradio" in decision_section
        assert "non-production" in decision_section.lower() or "demoted" in decision_section.lower()

    def test_consequences_has_positive_subsection(self, content: str) -> None:
        assert "### Positive" in content

    def test_consequences_has_negative_subsection(self, content: str) -> None:
        assert "### Negative" in content

    def test_consequences_has_neutral_subsection(self, content: str) -> None:
        assert "### Neutral" in content

    def test_positive_consequences_has_at_least_three_items(self, content: str) -> None:
        pos_section = content.split("### Positive")[1].split("###")[0]
        numbered = re.findall(r"^\d+\.", pos_section, re.MULTILINE)
        assert len(numbered) >= 3, f"Positive consequences must have at least 3 items, found {len(numbered)}"

    def test_negative_consequences_has_at_least_one_item(self, content: str) -> None:
        neg_section = content.split("### Negative")[1].split("###")[0]
        numbered = re.findall(r"^\d+\.", neg_section, re.MULTILINE)
        assert len(numbered) >= 1, "Negative consequences must have at least 1 item"

    def test_alternatives_considered_has_three_alternatives(self, content: str) -> None:
        # Count "### Alternative N" headings in the whole document
        alt_headings = re.findall(r"### Alternative \d+", content)
        assert len(alt_headings) == 3, f"Must have exactly 3 alternatives, found {len(alt_headings)}"

    def test_all_three_alternatives_are_rejected(self, content: str) -> None:
        alts_section = content.split("## Alternatives Considered")[1].split("## Implementation")[0]
        rejected_count = alts_section.count("Rejected")
        assert rejected_count >= 3, f"All 3 alternatives must be labeled as Rejected, found {rejected_count}"

    def test_alternative_1_is_keep_both_equal(self, content: str) -> None:
        assert "Keep Both as Equal Production Paths" in content or "Equal Production" in content

    def test_alternative_2_is_delete_gradio(self, content: str) -> None:
        assert "Delete Gradio Entirely" in content or "Delete Gradio" in content

    def test_alternative_3_is_make_gradio_production(self, content: str) -> None:
        assert "Make Gradio the Production Path" in content or "Make Gradio" in content

    def test_implementation_plan_has_immediate_actions(self, content: str) -> None:
        # The Implementation Plan section has subsections (###) so split on "\n## " to get the full block
        impl_block = content.split("## Implementation Plan")[1].split("\n## ")[0]
        assert "Immediate Actions" in impl_block

    def test_implementation_plan_has_deferred_followup(self, content: str) -> None:
        impl_block = content.split("## Implementation Plan")[1].split("\n## ")[0]
        assert "Deferred" in impl_block or "out of scope" in impl_block.lower()

    def test_implementation_plan_references_readme(self, content: str) -> None:
        impl_block = content.split("## Implementation Plan")[1].split("\n## ")[0]
        assert "README.md" in impl_block

    def test_implementation_plan_references_architecture_md(self, content: str) -> None:
        impl_block = content.split("## Implementation Plan")[1].split("\n## ")[0]
        assert "ARCHITECTURE.md" in impl_block

    def test_implementation_plan_references_automation_scope_policy(self, content: str) -> None:
        impl_block = content.split("## Implementation Plan")[1].split("\n## ")[0]
        assert "AUTOMATION_SCOPE_POLICY.md" in impl_block

    def test_context_lists_dual_runtime_problems(self, content: str) -> None:
        context_section = content.split("## Context")[1].split("## Decision")[0]
        problems = re.findall(r"^\d+\.", context_section, re.MULTILINE)
        assert len(problems) >= 4, "Context must enumerate at least 4 problems with dual runtime identity"

    def test_adr_states_no_code_deletion(self, content: str) -> None:
        """ADR must state Gradio code is NOT deleted."""
        assert "No Code Deletion" in content or "remains in the repository" in content

    def test_adr_states_no_runtime_changes(self, content: str) -> None:
        """ADR must clarify it is a documentation change, not a runtime change."""
        assert "No Runtime Changes" in content or "documentation and policy change" in content.lower()

    def test_references_architecture_md(self, content: str) -> None:
        ref_section = content.split("## References")[1]
        assert "ARCHITECTURE.md" in ref_section

    def test_references_deployment_md(self, content: str) -> None:
        ref_section = content.split("## References")[1]
        assert "DEPLOYMENT.md" in ref_section

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_code_blocks_are_balanced(self, content: str) -> None:
        count = content.count("```")
        assert count % 2 == 0, f"Unbalanced code fences: {count} backtick groups"

    def test_utf8_encoding(self) -> None:
        content = ADR_0001.read_text(encoding="utf-8")
        assert "�" not in content

    def test_no_hardcoded_secrets(self, content: str) -> None:
        for pattern in [r"ghp_[a-zA-Z0-9]{36}", r"gho_[a-zA-Z0-9]{36}"]:
            assert not re.search(pattern, content), f"ADR must not contain hardcoded tokens (pattern: {pattern})"


# ---------------------------------------------------------------------------
# Cross-file consistency tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestProductionArchitectureDocumentationConsistency:
    """Cross-file consistency tests across all changed documents."""

    @pytest.fixture
    def policy_content(self) -> str:
        return _load(AUTOMATION_SCOPE_POLICY)

    @pytest.fixture
    def arch_template_content(self) -> str:
        return _load(ARCHITECTURE_DOCS_TEMPLATE)

    @pytest.fixture
    def pr_template_content(self) -> str:
        return _load(_resolve_primary_pr_template())

    @pytest.fixture
    def architecture_content(self) -> str:
        return _load(ARCHITECTURE_MD)

    @pytest.fixture
    def deployment_content(self) -> str:
        return _load(DEPLOYMENT_MD)

    @pytest.fixture
    def readme_content(self) -> str:
        return _load(README_MD)

    @pytest.fixture
    def adr_content(self) -> str:
        return _load(ADR_0001)

    def test_all_files_agree_fastapi_nextjs_is_production(
        self,
        policy_content: str,
        architecture_content: str,
        deployment_content: str,
        readme_content: str,
        adr_content: str,
    ) -> None:
        """Every document must declare FastAPI + Next.js as the production architecture."""
        files = {
            "AUTOMATION_SCOPE_POLICY.md": policy_content,
            "ARCHITECTURE.md": architecture_content,
            "DEPLOYMENT.md": deployment_content,
            "README.md": readme_content,
            "docs/adr/0001-production-architecture.md": adr_content,
        }
        for name, content in files.items():
            assert "FastAPI" in content, f"{name} must reference FastAPI"
            assert "Next.js" in content, f"{name} must reference Next.js"

    def test_all_files_agree_gradio_is_non_production(
        self,
        policy_content: str,
        architecture_content: str,
        deployment_content: str,
        readme_content: str,
        adr_content: str,
    ) -> None:
        """Every document must treat Gradio as non-production."""
        files = {
            "AUTOMATION_SCOPE_POLICY.md": policy_content,
            "ARCHITECTURE.md": architecture_content,
            "DEPLOYMENT.md": deployment_content,
            "README.md": readme_content,
            "docs/adr/0001-production-architecture.md": adr_content,
        }
        for name, content in files.items():
            assert "Gradio" in content, f"{name} must reference Gradio"
            assert (
                "non-production" in content.lower() or "NON-PRODUCTION" in content
            ), f"{name} must declare Gradio as non-production"

    def test_policy_references_adr_0001(self, policy_content: str) -> None:
        assert "0001-production-architecture.md" in policy_content

    def test_architecture_md_references_adr_0001(self, architecture_content: str) -> None:
        assert "0001-production-architecture.md" in architecture_content

    def test_adr_references_architecture_md(self, adr_content: str) -> None:
        assert "ARCHITECTURE.md" in adr_content

    def test_adr_references_deployment_md(self, adr_content: str) -> None:
        assert "DEPLOYMENT.md" in adr_content

    def test_adr_references_readme_md(self, adr_content: str) -> None:
        assert "README.md" in adr_content

    def test_pr_template_references_automation_scope_policy(self, pr_template_content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in pr_template_content

    def test_architecture_docs_template_references_automation_scope_policy(self, arch_template_content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in arch_template_content

    def test_both_pr_templates_enforce_single_decision(
        self, arch_template_content: str, pr_template_content: str
    ) -> None:
        """Both PR templates must enforce the one-primary-decision constraint."""
        assert "one primary decision" in arch_template_content.lower() or "primary" in arch_template_content.lower()
        assert (
            "one primary decision" in pr_template_content.lower() or "primary decision" in pr_template_content.lower()
        )

    def test_policy_and_adr_consistent_gradio_status(self, policy_content: str, adr_content: str) -> None:
        """Both policy and ADR must agree on Gradio's non-production status."""
        assert "non-production" in policy_content.lower()
        assert "non-production" in adr_content.lower()

    def test_deployment_and_readme_agree_on_production_stack(
        self, deployment_content: str, readme_content: str
    ) -> None:
        """DEPLOYMENT.md and README.md must both present FastAPI + Next.js as the primary path."""
        assert "FastAPI" in deployment_content and "Next.js" in deployment_content
        assert "FastAPI" in readme_content and "Next.js" in readme_content

    def test_architecture_md_next_js_comes_before_gradio_in_diagram(self, architecture_content: str) -> None:
        """In the updated diagram, Next.js (Port 3000) must appear before Gradio (Port 7860)."""
        # Use port-specific labels to match only the diagram entries, not prose references
        nextjs_pos = architecture_content.find("Next.js UI (Port 3000)")
        gradio_pos = architecture_content.find("Gradio UI (Port 7860)")
        assert nextjs_pos != -1, "Next.js UI (Port 3000) must appear in the diagram"
        assert gradio_pos != -1, "Gradio UI (Port 7860) must appear in the diagram"
        assert nextjs_pos < gradio_pos, "Next.js UI must appear before Gradio UI in the architecture diagram"

    def test_all_new_files_are_utf8_clean(
        self,
        policy_content: str,
        arch_template_content: str,
        adr_content: str,
    ) -> None:
        for name, content in [
            ("AUTOMATION_SCOPE_POLICY.md", policy_content),
            ("architecture-docs.md", arch_template_content),
            ("0001-production-architecture.md", adr_content),
        ]:
            assert "�" not in content, f"{name} must not contain UTF-8 replacement characters"

    def test_adr_implementation_plan_matches_actual_changed_files(self, adr_content: str) -> None:
        """The ADR's implementation plan must list the files that were actually changed in this PR."""
        # The Implementation Plan section has subsections (###) - split on "\n## " to get the full block
        impl_block = adr_content.split("## Implementation Plan")[1].split("\n## ")[0]
        # The ADR states these five actions
        assert "README.md" in impl_block
        assert "ARCHITECTURE.md" in impl_block
        assert "DEPLOYMENT.md" in impl_block
        assert "AUTOMATION_SCOPE_POLICY.md" in impl_block

    def test_policy_and_pr_template_agree_on_required_sections(
        self, policy_content: str, pr_template_content: str
    ) -> None:
        """Required PR sections in the policy must correspond to actual sections in the PR template."""
        # Policy says PRs must have these sections
        required_in_policy = ["Primary Objective", "In Scope", "Out of Scope", "Validation Commands", "Merge Criteria"]
        # PR template must actually contain these sections
        for section in required_in_policy:
            assert (
                section in pr_template_content
            ), f"PR template must contain the '{section}' section mandated by AUTOMATION_SCOPE_POLICY.md"
