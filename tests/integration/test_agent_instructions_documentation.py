"""
Integration tests for the agent instruction documentation updated in this PR.

Covers:
- .github/copilot-instructions.md (modified - production architecture declaration,
  updated quick start, key files, integration deps, and editing guidelines)
- AGENTS.md (modified - production architecture declaration, labelled run
  commands, updated architecture section, and current-reality guidance)
"""

import re
from pathlib import Path
from typing import List

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent

COPILOT_INSTRUCTIONS = REPO_ROOT / ".github" / "copilot-instructions.md"
AGENTS_MD = REPO_ROOT / "AGENTS.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load(path: Path) -> str:
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(content: str) -> List[str]:
    return content.splitlines()


def _lines_outside_code_fences(lines: List[str]) -> List[str]:
    outside: List[str] = []
    in_fence = False
    for line in lines:
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            outside.append(line)
    return outside


# ---------------------------------------------------------------------------
# .github/copilot-instructions.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCopilotInstructionsProductionArchitecture:
    """Validate the production architecture declaration added to .github/copilot-instructions.md."""

    @pytest.fixture
    def content(self) -> str:
        return _load(COPILOT_INSTRUCTIONS)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert COPILOT_INSTRUCTIONS.exists(), ".github/copilot-instructions.md must exist"
        assert COPILOT_INSTRUCTIONS.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0, ".github/copilot-instructions.md must not be empty"

    def test_has_production_architecture_declaration_section(self, content: str) -> None:
        assert "IMPORTANT: Production Architecture Declaration" in content

    def test_declares_fastapi_nextjs_as_production(self, content: str) -> None:
        decl_section = content.split("IMPORTANT: Production Architecture Declaration")[1].split("##")[0]
        assert "FastAPI" in decl_section
        assert "Next.js" in decl_section
        assert "Production" in decl_section

    def test_declares_gradio_as_non_production(self, content: str) -> None:
        decl_section = content.split("IMPORTANT: Production Architecture Declaration")[1].split("##")[0]
        assert "Gradio" in decl_section
        assert "Non-Production" in decl_section or "non-production" in decl_section.lower()

    def test_references_automation_scope_policy(self, content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in content

    def test_references_adr_0001(self, content: str) -> None:
        assert "0001-production-architecture.md" in content

    def test_all_development_should_prioritize_production_architecture(self, content: str) -> None:
        assert "prioritize the production architecture" in content.lower()

    def test_has_production_quick_start_path(self, content: str) -> None:
        assert "Production path" in content or "production path" in content.lower()

    def test_production_quick_start_mentions_uvicorn(self, content: str) -> None:
        assert "uvicorn" in content
        assert "api.main:app" in content

    def test_production_quick_start_mentions_required_env_vars(self, content: str) -> None:
        assert "DATABASE_URL" in content
        assert "SECRET_KEY" in content

    def test_production_quick_start_mentions_npm_run_dev(self, content: str) -> None:
        assert "npm run dev" in content

    def test_has_non_production_quick_start_path(self, content: str) -> None:
        assert "Non-production path" in content or "non-production path" in content.lower()

    def test_non_production_path_uses_app_py(self, content: str) -> None:
        assert "python app.py" in content

    def test_production_stack_lists_api_main_py(self, content: str) -> None:
        assert "api/main.py" in content

    def test_production_stack_lists_frontend_page_tsx(self, content: str) -> None:
        assert "frontend/app/page.tsx" in content

    def test_production_stack_lists_frontend_lib_api_ts(self, content: str) -> None:
        assert "frontend/app/lib/api.ts" in content

    def test_production_stack_lists_src_config_settings_py(self, content: str) -> None:
        assert "src/config/settings.py" in content

    def test_runtime_configuration_mentions_get_settings_and_os_getenv(self, content: str) -> None:
        assert "get_settings()" in content
        assert "os.getenv()" in content

    def test_integration_section_has_production_ui_entry(self, content: str) -> None:
        assert "Production UI" in content or "production UI" in content.lower()

    def test_integration_section_has_non_production_ui_entry(self, content: str) -> None:
        assert "Non-production UI" in content or "non-production UI" in content.lower()

    def test_pr_scope_guardrails_mentioned_in_editing_guidelines(self, content: str) -> None:
        assert "scope guardrails" in content.lower() or "AUTOMATION_SCOPE_POLICY.md" in content

    def test_editing_guidelines_prioritize_production_architecture(self, content: str) -> None:
        assert "Prioritize production architecture" in content or "prioritize production" in content.lower()

    def test_env_var_guidelines_reference_settings_model(self, content: str) -> None:
        assert "src/config/settings.py" in content
        assert "settings" in content.lower()

    def test_env_var_guidelines_do_not_assume_full_migration(self, content: str) -> None:
        assert "do not assume full migration" in content.lower() or "partial coverage" in content.lower()

    def test_requirements_txt_lists_fastapi(self, content: str) -> None:
        assert "FastAPI" in content

    def test_non_production_gradio_ui_section_still_documented(self, content: str) -> None:
        assert "app.py" in content
        assert "Gradio" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in _lines_outside_code_fences(lines):
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_file_is_utf8_clean(self) -> None:
        content = COPILOT_INSTRUCTIONS.read_text(encoding="utf-8")
        assert "�" not in content, "File must not contain UTF-8 replacement characters"

    def test_no_hardcoded_secrets(self, content: str) -> None:
        for pattern in [r"ghp_[a-zA-Z0-9]{36}", r"gho_[a-zA-Z0-9]{36}"]:
            assert not re.search(pattern, content), (
                f".github/copilot-instructions.md must not contain hardcoded tokens (pattern: {pattern})"
            )

    def test_code_blocks_are_balanced(self, content: str) -> None:
        fence_count = len(re.findall(r"(?<!`)```(?!`)", content))
        assert fence_count % 2 == 0, f"Unbalanced code fences: {fence_count} triple-backtick groups"

    def test_pwsh_code_blocks_present_for_quick_start(self, content: str) -> None:
        assert "```pwsh" in content

    def test_agent_triggers_section_is_present(self, content: str) -> None:
        assert "Agent Triggers" in content

    def test_copilot_fix_trigger_present(self, content: str) -> None:
        assert "@copilot fix this" in content

    def test_copilot_address_review_trigger_present(self, content: str) -> None:
        assert "@copilot address review" in content

    def test_copilot_update_tests_trigger_present(self, content: str) -> None:
        assert "@copilot update tests" in content

    def test_production_declaration_appears_before_mandatory_branch_section(self, content: str) -> None:
        decl_pos = content.find("IMPORTANT: Production Architecture Declaration")
        branch_pos = content.find("Mandatory branch/ref verification")
        assert decl_pos != -1
        assert branch_pos != -1
        assert decl_pos < branch_pos

    def test_src_config_settings_in_integration_section(self, content: str) -> None:
        """
        Asserts the "Integration & external deps" section references the runtime settings module or accessor.
        
        Checks that the text under the "Integration & external deps" header contains either `src/config/settings.py` or `get_settings()`.
        
        Parameters:
            content (str): Full text of the markdown file being tested.
        """
        integration_block = content.split("Integration & external deps")[1].split("##")[0]
        assert "src/config/settings.py" in integration_block or "get_settings()" in integration_block

    def test_pip_install_requirements_txt_present_in_both_paths(self, content: str) -> None:
        """
        Asserts that the repository documentation contains the `pip install -r requirements.txt` install command in at least two places.
        
        Parameters:
            content (str): The full text content of the file under test.
        """
        occurrences = content.count("pip install -r requirements.txt")
        assert occurrences >= 2


# ---------------------------------------------------------------------------
# AGENTS.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAgentsMdProductionArchitecture:
    """Validate the production architecture changes added to AGENTS.md in this PR."""

    @pytest.fixture
    def content(self) -> str:
        return _load(AGENTS_MD)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert AGENTS_MD.exists(), "AGENTS.md must exist"
        assert AGENTS_MD.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0, "AGENTS.md must not be empty"

    def test_has_production_architecture_declaration_section(self, content: str) -> None:
        assert "IMPORTANT: Production Architecture Declaration" in content

    def test_declares_fastapi_nextjs_as_production(self, content: str) -> None:
        decl_section = content.split("IMPORTANT: Production Architecture Declaration")[1].split("##")[0]
        assert "FastAPI" in decl_section
        assert "Next.js" in decl_section
        assert "Production" in decl_section

    def test_declares_gradio_as_non_production(self, content: str) -> None:
        decl_section = content.split("IMPORTANT: Production Architecture Declaration")[1].split("##")[0]
        assert "Gradio" in decl_section
        assert "Non-Production" in decl_section or "non-production" in decl_section.lower()

    def test_references_automation_scope_policy(self, content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in content

    def test_references_adr_0001(self, content: str) -> None:
        assert "0001-production-architecture.md" in content

    def test_all_development_should_prioritize_production_architecture(self, content: str) -> None:
        assert "prioritize the production architecture" in content.lower()

    def test_branch_ref_verification_section_is_present(self, content: str) -> None:
        assert "Mandatory branch/ref verification" in content

    def test_quick_orientation_labels_fastapi_nextjs_as_production(self, content: str) -> None:
        orientation_section = content.split("## Quick orientation")[1].split("##")[0]
        assert "PRODUCTION" in orientation_section
        assert "FastAPI" in orientation_section
        assert "Next.js" in orientation_section

    def test_quick_orientation_labels_gradio_as_non_production(self, content: str) -> None:
        orientation_section = content.split("## Quick orientation")[1].split("##")[0]
        assert "NON-PRODUCTION" in orientation_section
        assert "Gradio" in orientation_section

    def test_fastapi_backend_section_labeled_production(self, content: str) -> None:
        assert "Run the FastAPI backend" in content
        fastapi_heading_pos = content.find("Run the FastAPI backend")
        heading_text = content[fastapi_heading_pos : fastapi_heading_pos + 80]
        assert "PRODUCTION" in heading_text

    def test_nextjs_frontend_section_labeled_production(self, content: str) -> None:
        assert "Run the Next.js frontend" in content
        nextjs_pos = content.find("Run the Next.js frontend")
        heading_text = content[nextjs_pos : nextjs_pos + 60]
        assert "PRODUCTION" in heading_text

    def test_run_both_section_labeled_production(self, content: str) -> None:
        assert "Run both API + frontend together" in content
        pos = content.find("Run both API + frontend together")
        heading_text = content[pos : pos + 80]
        assert "PRODUCTION" in heading_text

    def test_gradio_run_section_labeled_non_production(self, content: str) -> None:
        assert "### Run the Gradio app (NON-PRODUCTION)" in content

    def test_docker_section_labeled_non_production(self, content: str) -> None:
        match = re.search(r"^### Docker .*NON-PRODUCTION", content, re.MULTILINE)
        assert match is not None, "Docker heading must be explicitly labelled NON-PRODUCTION"

    def test_docker_note_references_adr_0001(self, content: str) -> None:
        match = re.search(r"^### Docker .*NON-PRODUCTION", content, re.MULTILINE)
        assert match is not None
        after_docker = content[match.start() : match.start() + 300]
        assert "ADR 0001" in after_docker or "0001" in after_docker

    def test_architecture_lists_src_config_settings_py(self, content: str) -> None:
        assert "src/config/settings.py" in content

    def test_gradio_ui_architecture_labeled_non_production(self, content: str) -> None:
        assert "Gradio UI (Non-Production)" in content or "Non-Production" in content

    def test_gradio_architecture_note_says_not_production_path(self, content: str) -> None:
        assert "not the production deployment path" in content.lower() or "not the production" in content.lower()

    def test_conventions_mention_production_architecture(self, content: str) -> None:
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "FastAPI" in conventions_section or "production" in conventions_section.lower()

    def test_conventions_mention_pr_scope_guardrails(self, content: str) -> None:
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "PR scope guardrails" in conventions_section or "scope guardrails" in conventions_section.lower()

    def test_conventions_mention_runtime_configuration(self, content: str) -> None:
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "get_settings()" in conventions_section or "src/config/settings.py" in conventions_section

    def test_fastapi_port_8000_mentioned(self, content: str) -> None:
        assert "8000" in content

    def test_nextjs_port_3000_mentioned(self, content: str) -> None:
        assert "3000" in content

    def test_uvicorn_command_present(self, content: str) -> None:
        assert "uvicorn api.main:app" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        for line in _lines_outside_code_fences(lines):
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_file_is_utf8_clean(self) -> None:
        content = AGENTS_MD.read_text(encoding="utf-8")
        assert "�" not in content, "AGENTS.md must not contain UTF-8 replacement characters"

    def test_no_hardcoded_secrets(self, content: str) -> None:
        for pattern in [r"ghp_[a-zA-Z0-9]{36}", r"gho_[a-zA-Z0-9]{36}"]:
            assert not re.search(pattern, content), f"AGENTS.md must not contain hardcoded tokens (pattern: {pattern})"

    def test_env_vars_section_lists_database_url(self, content: str) -> None:
        assert "DATABASE_URL" in content

    def test_env_vars_section_lists_secret_key(self, content: str) -> None:
        assert "SECRET_KEY" in content

    def test_run_dev_scripts_mentioned(self, content: str) -> None:
        assert "run-dev.bat" in content
        assert "run-dev.sh" in content

    def test_production_declaration_section_appears_at_top(self, content: str) -> None:
        """
        Asserts that the "IMPORTANT: Production Architecture Declaration" header appears before the "## Quick orientation" section in the provided document.
        
        Parameters:
            content (str): Full text of the markdown file to inspect.
        
        Raises:
            AssertionError: If either header is missing or the production declaration does not appear before the quick orientation section.
        """
        decl_pos = content.find("IMPORTANT: Production Architecture Declaration")
        orient_pos = content.find("## Quick orientation")
        assert decl_pos != -1
        assert orient_pos != -1
        assert decl_pos < orient_pos

    def test_branch_ref_section_advises_not_to_assume_merged(self, content: str) -> None:
        # The Mandatory branch/ref verification section intentionally preserves guidance
        # that agents should not assume work is merged; verify the section is intact.
        """
        Validates that the "Mandatory branch/ref verification" section advises not to assume merged work.
        
        Checks the provided document content for the "## Mandatory branch/ref verification" section and asserts it contains guidance to "do not assume" and either "clean working tree" or "local working-tree state alone".
        
        Parameters:
            content (str): Full text of the markdown document to inspect.
        """
        branch_section = content.split("## Mandatory branch/ref verification")[1].split("##")[0]
        branch_section_lower = branch_section.lower()
        assert "do not assume" in branch_section_lower
        assert "clean working tree" in branch_section_lower or "local working-tree state alone" in branch_section_lower

    def test_branch_ref_section_advises_stop_and_verify(self, content: str) -> None:
        # The Mandatory branch/ref verification section intentionally instructs agents
        # to stop and verify when branch/ref identity is unclear.
        branch_section = content.split("## Mandatory branch/ref verification")[1].split("##")[0]
        assert "stop and verify" in branch_section.lower()

    def test_gradio_section_dedicated_label_demos_testing_only(self, content: str) -> None:
        """
        Asserts the Gradio section is labeled for both demos and testing.
        
        Parameters:
            content (str): Full text of the markdown file to verify; the test checks that both "demos" and "testing" appear (case-insensitive).
        """
        assert "demos" in content.lower() and "testing" in content.lower()


# ---------------------------------------------------------------------------
# Cross-file consistency tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAgentInstructionsConsistency:
    """Cross-file consistency tests for .github/copilot-instructions.md and AGENTS.md."""

    @pytest.fixture
    def copilot_content(self) -> str:
        return _load(COPILOT_INSTRUCTIONS)

    @pytest.fixture
    def agents_content(self) -> str:
        return _load(AGENTS_MD)

    def test_both_files_declare_fastapi_nextjs_as_production(self, copilot_content: str, agents_content: str) -> None:
        for name, content in [
            (".github/copilot-instructions.md", copilot_content),
            ("AGENTS.md", agents_content),
        ]:
            assert "FastAPI" in content, f"{name} must reference FastAPI"
            assert "Next.js" in content, f"{name} must reference Next.js"

    def test_both_files_declare_gradio_as_non_production(self, copilot_content: str, agents_content: str) -> None:
        for name, content in [
            (".github/copilot-instructions.md", copilot_content),
            ("AGENTS.md", agents_content),
        ]:
            assert "Gradio" in content, f"{name} must reference Gradio"
            assert "non-production" in content.lower() or "NON-PRODUCTION" in content, (
                f"{name} must label Gradio as non-production"
            )

    def test_both_files_reference_automation_scope_policy(self, copilot_content: str, agents_content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in copilot_content
        assert "AUTOMATION_SCOPE_POLICY.md" in agents_content

    def test_both_files_reference_adr_0001(self, copilot_content: str, agents_content: str) -> None:
        assert "0001-production-architecture.md" in copilot_content
        assert "0001-production-architecture.md" in agents_content

    def test_both_files_reference_src_config_settings_py(self, copilot_content: str, agents_content: str) -> None:
        assert "src/config/settings.py" in copilot_content
        assert "src/config/settings.py" in agents_content

    def test_both_files_agree_prioritize_production_architecture(
        self, copilot_content: str, agents_content: str
    ) -> None:
        assert "prioritize the production architecture" in copilot_content.lower()
        assert "prioritize the production architecture" in agents_content.lower()

    def test_both_files_present_gradio_as_demos_or_testing(self, copilot_content: str, agents_content: str) -> None:
        for name, content in [
            (".github/copilot-instructions.md", copilot_content),
            ("AGENTS.md", agents_content),
        ]:
            assert "demo" in content.lower() or "testing" in content.lower(), (
                f"{name} must describe Gradio as for demos/testing"
            )

    def test_agents_md_has_ci_reference_section(self, agents_content: str) -> None:
        assert "## CI reference" in agents_content
        assert "CircleCI" in agents_content
