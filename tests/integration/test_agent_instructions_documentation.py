"""
Integration tests for the agent instruction documentation updated in this PR.

Covers:
- .github/copilot-instructions.md (modified - production architecture declaration,
  updated quick start, key files, integration deps, and editing guidelines)
- AGENTS.md (modified - replaced branch/ref verification section with production
  architecture declaration, labelled run commands, updated architecture section)
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
    """
    Load and return the UTF-8 text contents of the file at the given path.
    
    Parameters:
        path (Path): Filesystem path to the file to read.
    
    Returns:
        str: The file contents decoded as UTF-8.
    
    Raises:
        AssertionError: If the file does not exist.
    """
    assert path.exists(), f"Required file not found: {path}"
    return path.read_text(encoding="utf-8")


def _lines(content: str) -> List[str]:
    """
    Split the given text into a list of lines.
    
    Returns:
        A list of strings, each element is a line from `content` split at line boundaries (no trailing newline characters).
    """
    return content.splitlines()


# ---------------------------------------------------------------------------
# .github/copilot-instructions.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestCopilotInstructionsProductionArchitecture:
    """Validate the production architecture declaration added to .github/copilot-instructions.md."""

    @pytest.fixture
    def content(self) -> str:
        """
        Load and return the contents of the repository's .github/copilot-instructions.md file.
        
        Returns:
            str: The UTF-8 text content of .github/copilot-instructions.md.
        """
        return _load(COPILOT_INSTRUCTIONS)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        """
        Split the given text into a list of lines.
        
        Parameters:
            content (str): The text to split.
        
        Returns:
            List[str]: A list of lines obtained from the input text.
        """
        return _lines(content)

    def test_file_exists(self) -> None:
        """
        Assert that the repository contains a regular file at .github/copilot-instructions.md.
        
        Raises:
            AssertionError: If the file does not exist or is not a regular file.
        """
        assert COPILOT_INSTRUCTIONS.exists(), ".github/copilot-instructions.md must exist"
        assert COPILOT_INSTRUCTIONS.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0, ".github/copilot-instructions.md must not be empty"

    def test_has_production_architecture_declaration_section(self, content: str) -> None:
        assert "IMPORTANT: Production Architecture Declaration" in content

    def test_declares_fastapi_nextjs_as_production(self, content: str) -> None:
        """The production architecture declaration must name FastAPI + Next.js."""
        decl_section = content.split("IMPORTANT: Production Architecture Declaration")[1].split("##")[0]
        assert "FastAPI" in decl_section
        assert "Next.js" in decl_section
        assert "Production" in decl_section

    def test_declares_gradio_as_non_production(self, content: str) -> None:
        """The production architecture declaration must label Gradio as non-production."""
        decl_section = content.split("IMPORTANT: Production Architecture Declaration")[1].split("##")[0]
        assert "Gradio" in decl_section
        assert "Non-Production" in decl_section or "non-production" in decl_section.lower()

    def test_references_automation_scope_policy(self, content: str) -> None:
        """
        Assert that the document content references the repository's automation scope policy.
        
        Parameters:
            content (str): Text content of the file under test; must include "AUTOMATION_SCOPE_POLICY.md".
        """
        assert "AUTOMATION_SCOPE_POLICY.md" in content

    def test_references_adr_0001(self, content: str) -> None:
        """
        Asserts the document content references the production architecture ADR `0001-production-architecture.md`.
        
        Parameters:
            content (str): Full text content of the documentation file to check.
        """
        assert "0001-production-architecture.md" in content

    def test_all_development_should_prioritize_production_architecture(self, content: str) -> None:
        """
        Assert the documentation explicitly prioritizes the production architecture.
        
        Parameters:
            content (str): The document text to search for the required phrase.
        """
        assert "prioritize the production architecture" in content.lower()

    def test_has_production_quick_start_path(self, content: str) -> None:
        """Quick start must document the production path (FastAPI + Next.js)."""
        assert "Production path" in content or "production path" in content.lower()

    def test_production_quick_start_mentions_uvicorn(self, content: str) -> None:
        """
        Check that the production quick-start includes the FastAPI startup invocation.
        
        Asserts that the content contains "uvicorn" and the ASGI application reference "api.main:app".
        """
        assert "uvicorn" in content
        assert "api.main:app" in content

    def test_production_quick_start_mentions_npm_run_dev(self, content: str) -> None:
        """Production startup must include Next.js frontend start command."""
        assert "npm run dev" in content

    def test_has_non_production_quick_start_path(self, content: str) -> None:
        """
        Ensure the quick-start section documents the non-production Gradio path.
        
        Checks that the provided markdown `content` contains the phrase "Non-production path" (case-insensitive).
        
        Parameters:
            content (str): Full text of the markdown file to inspect.
        """
        assert "Non-production path" in content or "non-production path" in content.lower()

    def test_non_production_path_uses_app_py(self, content: str) -> None:
        """Non-production path must reference app.py (Gradio entry point)."""
        assert "python app.py" in content

    def test_production_stack_lists_api_main_py(self, content: str) -> None:
        """
        Check that the production backend entrypoint file "api/main.py" is referenced in the given document content.
        
        Parameters:
            content (str): The document text to inspect.
        
        Raises:
            AssertionError: If "api/main.py" is not present in content.
        """
        assert "api/main.py" in content

    def test_production_stack_lists_api_routers(self, content: str) -> None:
        """
        Verify the documentation content references the API routers path "api/routers/".
        
        Parameters:
            content (str): The documentation file content to check.
        """
        assert "api/routers/" in content

    def test_production_stack_lists_api_models_py(self, content: str) -> None:
        """
        Verify the documentation includes a reference to `api/models.py`.
        
        Parameters:
            content (str): The markdown file content to inspect for the architecture reference.
        """
        assert "api/models.py" in content

    def test_production_stack_lists_api_cors_utils_py(self, content: str) -> None:
        assert "api/cors_utils.py" in content

    def test_production_stack_lists_api_graph_lifecycle_py(self, content: str) -> None:
        assert "api/graph_lifecycle.py" in content

    def test_production_stack_lists_frontend_page_tsx(self, content: str) -> None:
        assert "frontend/app/page.tsx" in content

    def test_production_stack_lists_frontend_lib_api_ts(self, content: str) -> None:
        assert "frontend/app/lib/api.ts" in content

    def test_production_stack_lists_src_config_settings_py(self, content: str) -> None:
        """
        Check that the production architecture documentation references `src/config/settings.py`.
        
        Parameters:
            content (str): The full text of the documentation file to inspect.
        
        Raises:
            AssertionError: If the string `src/config/settings.py` is not found in `content`.
        """
        assert "src/config/settings.py" in content

    def test_runtime_configuration_mandates_get_settings(self, content: str) -> None:
        """
        Verify the integration/runtime guidance mentions both `get_settings()` and `os.getenv()`.
        
        Asserts that the provided document content contains the substring "get_settings()" and the substring "os.getenv()".
        """
        assert "get_settings()" in content
        assert "os.getenv()" in content

    def test_integration_section_has_production_ui_entry(self, content: str) -> None:
        """Integration section must describe the production UI stack."""
        assert "Production UI" in content or "production UI" in content.lower()

    def test_integration_section_has_non_production_ui_entry(self, content: str) -> None:
        """Integration section must describe the non-production Gradio UI."""
        assert "Non-production UI" in content or "non-production UI" in content.lower()

    def test_pr_scope_guardrails_mentioned_in_editing_guidelines(self, content: str) -> None:
        """Editing guidelines must reference PR scope guardrail requirements."""
        assert "scope guardrails" in content.lower() or "AUTOMATION_SCOPE_POLICY.md" in content

    def test_editing_guidelines_prioritize_production_architecture(self, content: str) -> None:
        assert "Prioritize production architecture" in content or "prioritize production" in content.lower()

    def test_env_var_guidelines_reference_settings_model(self, content: str) -> None:
        """
        Ensure environment variable guidance points to the project's Settings model.
        
        Checks that the documentation content references the settings module path and the `Settings` identifier.
        
        Parameters:
            content (str): Text content of the documentation file to check.
        """
        assert "src/config/settings.py" in content
        assert "Settings" in content or "settings" in content

    def test_env_var_guidelines_forbid_direct_os_getenv(self, content: str) -> None:
        """Environment variable guidelines must say not to use os.getenv() directly."""
        assert "os.getenv()" in content
        assert "never" in content.lower() or "not" in content.lower()

    def test_env_var_guidelines_mention_cache_clear(self, content: str) -> None:
        """Test helpers for env vars must mention cache_clear."""
        assert "cache_clear" in content

    def test_api_endpoint_changes_must_update_routers_and_api_ts(self, content: str) -> None:
        """Editing guidelines must say to update both api/routers/ and frontend/app/lib/api.ts."""
        assert "api/routers/" in content
        assert "frontend/app/lib/api.ts" in content

    def test_requirements_txt_lists_fastapi_and_pydantic(self, content: str) -> None:
        """requirements.txt description must include FastAPI and Pydantic."""
        assert "FastAPI" in content
        assert "Pydantic" in content

    def test_non_production_gradio_ui_section_still_documented(self, content: str) -> None:
        """Gradio UI description must still be present for demos/testing reference."""
        assert "app.py" in content
        assert "Gradio" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        """
        Asserts that every Markdown heading line uses a space after the leading `#` characters.
        
        Checks each line that begins with `#` to ensure there is a space following the leading 1–6 `#` characters; raises an AssertionError identifying the offending line if a heading is not formatted correctly.
        
        Parameters:
            lines (List[str]): Lines of the Markdown file to validate.
        """
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_file_is_utf8_clean(self) -> None:
        """
        Check that the Copilot instructions file contains no UTF-8 replacement characters.
        
        Asserts the file is UTF-8 clean by ensuring the Unicode replacement character ("�") does not appear in the file content.
        """
        content = COPILOT_INSTRUCTIONS.read_text(encoding="utf-8")
        assert "�" not in content, "File must not contain UTF-8 replacement characters"

    def test_no_hardcoded_secrets(self, content: str) -> None:
        """
        Asserts the given file content does not contain hardcoded GitHub token-like secrets.
        
        Scans the content for occurrences matching the `ghp_` or `gho_` token patterns and fails the test if any are found.
        
        Parameters:
            content (str): The file content to scan for hardcoded token patterns.
        """
        for pattern in [r"ghp_[a-zA-Z0-9]{36}", r"gho_[a-zA-Z0-9]{36}"]:
            assert not re.search(pattern, content), (
                f".github/copilot-instructions.md must not contain hardcoded tokens (pattern: {pattern})"
            )

    def test_code_blocks_are_balanced(self, content: str) -> None:
        """
        Ensure the content contains an even number of exact triple-backtick code fences.
        
        Counts only code fence markers made of exactly three backticks (ignores longer backtick groups)
        and asserts the total number of such triple-backtick groups is even.
        """
        # Count only exactly-three-backtick fences (not four-backtick outer fences)
        fence_count = len(re.findall(r"(?<![`])```(?!`)", content))
        assert fence_count % 2 == 0, f"Unbalanced code fences: {fence_count} triple-backtick groups"

    def test_pwsh_code_blocks_present_for_quick_start(self, content: str) -> None:
        """Quick start section must contain PowerShell code blocks."""
        assert "```pwsh" in content

    def test_agent_triggers_section_is_present(self, content: str) -> None:
        """
        Verify the 'Agent Triggers' section exists in the provided document content.
        
        Parameters:
            content (str): Full text of the file to inspect.
        """
        assert "Agent Triggers" in content

    def test_copilot_fix_trigger_present(self, content: str) -> None:
        """
        Check that the Copilot "fix this" trigger string is present in the provided file content.
        
        Parameters:
            content (str): The text content of the file to inspect.
        
        Raises:
            AssertionError: If the trigger string "@copilot fix this" is not found.
        """
        assert "@copilot fix this" in content

    def test_copilot_address_review_trigger_present(self, content: str) -> None:
        assert "@copilot address review" in content

    def test_copilot_update_tests_trigger_present(self, content: str) -> None:
        assert "@copilot update tests" in content

    # Boundary / regression tests
    def test_production_declaration_appears_before_mandatory_branch_section(self, content: str) -> None:
        """Production Architecture Declaration must appear before the branch verification section."""
        decl_pos = content.find("IMPORTANT: Production Architecture Declaration")
        branch_pos = content.find("Mandatory branch/ref verification")
        assert decl_pos != -1, "Production Architecture Declaration section must exist"
        assert branch_pos != -1, "Mandatory branch/ref verification section must exist"
        assert decl_pos < branch_pos, (
            "Production Architecture Declaration must appear before Mandatory branch/ref verification"
        )

    def test_src_config_settings_in_integration_section(self, content: str) -> None:
        """Runtime configuration guidance belongs in Integration & external deps section."""
        integration_block = content.split("Integration & external deps")[1].split("##")[0]
        assert "src/config/settings.py" in integration_block

    def test_pip_install_requirements_txt_present_in_both_paths(self, content: str) -> None:
        """Both production and non-production paths must run pip install -r requirements.txt."""
        occurrences = content.count("pip install -r requirements.txt")
        assert occurrences >= 2, (
            "requirements.txt install must appear in both production and non-production quick start paths"
        )


# ---------------------------------------------------------------------------
# AGENTS.md
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAgentsMdProductionArchitecture:
    """Validate the production architecture changes added to AGENTS.md in this PR."""

    @pytest.fixture
    def content(self) -> str:
        """
        Return the contents of the repository's AGENTS.md file.
        
        Returns:
            content (str): UTF-8 decoded text of AGENTS.md.
        """
        return _load(AGENTS_MD)

    @pytest.fixture
    def lines(self, content: str) -> List[str]:
        """
        Split the given text into a list of lines.
        
        Parameters:
            content (str): The text to split.
        
        Returns:
            List[str]: A list of lines obtained from the input text.
        """
        return _lines(content)

    def test_file_exists(self) -> None:
        """
        Verify AGENTS.md exists at the repository root and is a regular file.
        
        Raises:
            AssertionError: If AGENTS.md does not exist or is not a file.
        """
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
        """
        Assert that the document content references the repository's automation scope policy.
        
        Parameters:
            content (str): Text content of the file under test; must include "AUTOMATION_SCOPE_POLICY.md".
        """
        assert "AUTOMATION_SCOPE_POLICY.md" in content

    def test_references_adr_0001(self, content: str) -> None:
        """
        Asserts the document content references the production architecture ADR `0001-production-architecture.md`.
        
        Parameters:
            content (str): Full text content of the documentation file to check.
        """
        assert "0001-production-architecture.md" in content

    def test_all_development_should_prioritize_production_architecture(self, content: str) -> None:
        """
        Assert the documentation explicitly prioritizes the production architecture.
        
        Parameters:
            content (str): The document text to search for the required phrase.
        """
        assert "prioritize the production architecture" in content.lower()

    def test_branch_ref_verification_section_removed(self, content: str) -> None:
        """The old Mandatory branch/ref verification section must not be present (replaced by arch declaration)."""
        assert "Mandatory branch/ref verification" not in content

    def test_quick_orientation_labels_fastapi_nextjs_as_production(self, content: str) -> None:
        """
        Verify the "## Quick orientation" section of the document labels FastAPI and Next.js as PRODUCTION.
        
        Parameters:
        	content (str): The full text of the AGENTS.md file to inspect.
        """
        orientation_section = content.split("## Quick orientation")[1].split("##")[0]
        assert "PRODUCTION" in orientation_section
        assert "FastAPI" in orientation_section
        assert "Next.js" in orientation_section

    def test_quick_orientation_labels_gradio_as_non_production(self, content: str) -> None:
        """Quick orientation section must label Gradio as NON-PRODUCTION."""
        orientation_section = content.split("## Quick orientation")[1].split("##")[0]
        assert "NON-PRODUCTION" in orientation_section
        assert "Gradio" in orientation_section

    def test_fastapi_backend_section_labeled_production(self, content: str) -> None:
        """FastAPI backend run section must be labelled as PRODUCTION."""
        assert "Run the FastAPI backend" in content
        fastapi_heading_pos = content.find("Run the FastAPI backend")
        heading_text = content[fastapi_heading_pos : fastapi_heading_pos + 80]
        assert "PRODUCTION" in heading_text

    def test_nextjs_frontend_section_labeled_production(self, content: str) -> None:
        """Next.js frontend run section must be labelled as PRODUCTION."""
        assert "Run the Next.js frontend" in content
        nextjs_pos = content.find("Run the Next.js frontend")
        heading_text = content[nextjs_pos : nextjs_pos + 60]
        assert "PRODUCTION" in heading_text

    def test_run_both_section_labeled_production(self, content: str) -> None:
        """Combined run section must be labelled as PRODUCTION."""
        assert "Run both API + frontend together" in content
        pos = content.find("Run both API + frontend together")
        heading_text = content[pos : pos + 80]
        assert "PRODUCTION" in heading_text

    def test_gradio_run_section_labeled_non_production(self, content: str) -> None:
        """
        Ensure the 'Run the Gradio app' section is labeled 'NON-PRODUCTION' near its header.
        
        Asserts that the document contains the 'Run the Gradio app' heading and that a 'NON-PRODUCTION' label appears within 100 characters of that heading.
        """
        assert "Run the Gradio app" in content
        # Find the section header that labels Gradio as non-production
        pos = content.find("NON-PRODUCTION")
        assert pos != -1, "NON-PRODUCTION label must appear in AGENTS.md"
        # It should be near the Gradio run section header
        gradio_pos = content.find("Run the Gradio app")
        # Both should exist and the NON-PRODUCTION label for Gradio should be within 100 chars of its section
        gradio_run_pos = content.find("NON-PRODUCTION", gradio_pos)
        assert gradio_run_pos != -1 and gradio_run_pos < gradio_pos + 100, (
            "NON-PRODUCTION label must appear in the Gradio run section heading"
        )

    def test_docker_section_labeled_non_production(self, content: str) -> None:
        """Docker section must be labelled as NON-PRODUCTION."""
        assert "Docker" in content
        docker_pos = content.find("Docker")
        docker_heading = content[docker_pos : docker_pos + 60]
        assert "NON-PRODUCTION" in docker_heading

    def test_docker_note_references_adr_0001(self, content: str) -> None:
        """Docker section note must reference ADR 0001 for deferred work."""
        docker_pos = content.find("Docker")
        after_docker = content[docker_pos : docker_pos + 300]
        assert "ADR 0001" in after_docker or "0001" in after_docker

    def test_fastapi_backend_architecture_section_references_routers(self, content: str) -> None:
        """FastAPI backend architecture entry must reference api/routers/."""
        assert "api/routers/" in content

    def test_fastapi_backend_architecture_section_references_models_py(self, content: str) -> None:
        assert "api/models.py" in content

    def test_fastapi_backend_architecture_section_references_cors_utils(self, content: str) -> None:
        assert "api/cors_utils.py" in content

    def test_fastapi_backend_architecture_section_references_graph_lifecycle(self, content: str) -> None:
        assert "api/graph_lifecycle.py" in content

    def test_architecture_lists_src_config_settings_py(self, content: str) -> None:
        """
        Asserts that the provided documentation content references the repository settings module at `src/config/settings.py`.
        
        Parameters:
            content (str): The text content of a documentation file to inspect.
        """
        assert "src/config/settings.py" in content

    def test_gradio_ui_architecture_labeled_non_production(self, content: str) -> None:
        """Gradio UI architecture section must be labelled Non-Production."""
        assert "Gradio UI (Non-Production)" in content or "Non-Production" in content

    def test_gradio_architecture_note_says_not_production_path(self, content: str) -> None:
        """Gradio architecture description must note it is not the production path."""
        assert "not the production deployment path" in content.lower() or "not the production" in content.lower()

    def test_conventions_mention_production_architecture(self, content: str) -> None:
        """Repo-specific conventions section must reference the production architecture."""
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "FastAPI" in conventions_section or "production" in conventions_section.lower()

    def test_conventions_mention_pr_scope_guardrails(self, content: str) -> None:
        """
        Verify that the "Repo-specific conventions" section references PR scope guardrails.
        
        Parameters:
            content (str): Full text content of the markdown file (used to extract the "Repo-specific conventions" section).
        
        Raises:
            AssertionError: If the "Repo-specific conventions" section does not contain either the exact phrase "PR scope guardrails" or a case-insensitive occurrence of "scope guardrails".
        """
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "PR scope guardrails" in conventions_section or "scope guardrails" in conventions_section.lower()

    def test_conventions_mention_runtime_configuration(self, content: str) -> None:
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "get_settings()" in conventions_section or "src/config/settings.py" in conventions_section

    def test_conventions_mention_cache_clear_for_tests(self, content: str) -> None:
        """Conventions must note that tests mutating env vars must call get_settings.cache_clear()."""
        conventions_section = content.split("## Repo-specific conventions")[1].split("##")[0]
        assert "cache_clear" in conventions_section

    def test_fastapi_port_8000_mentioned(self, content: str) -> None:
        """
        Asserts that the provided documentation content mentions the backend port 8000.
        """
        assert "8000" in content

    def test_nextjs_port_3000_mentioned(self, content: str) -> None:
        """
        Asserts the documentation content mentions port 3000 for the Next.js frontend.
        
        Parameters:
            content (str): The markdown file content to search.
        """
        assert "3000" in content

    def test_uvicorn_command_present(self, content: str) -> None:
        assert "uvicorn api.main:app" in content

    def test_headings_have_space_after_hash(self, lines: List[str]) -> None:
        """
        Asserts that every Markdown heading line uses a space after the leading `#` characters.
        
        Checks each line that begins with `#` to ensure there is a space following the leading 1–6 `#` characters; raises an AssertionError identifying the offending line if a heading is not formatted correctly.
        
        Parameters:
            lines (List[str]): Lines of the Markdown file to validate.
        """
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_file_is_utf8_clean(self) -> None:
        content = AGENTS_MD.read_text(encoding="utf-8")
        assert "�" not in content, "AGENTS.md must not contain UTF-8 replacement characters"

    def test_no_hardcoded_secrets(self, content: str) -> None:
        """
        Check that the provided file content does not contain hardcoded GitHub token patterns.
        
        Parameters:
            content (str): The text content of the file to scan.
        
        Raises:
            AssertionError: If a hardcoded token matching `ghp_[A-Za-z0-9]{36}` or `gho_[A-Za-z0-9]{36}` is found.
        """
        for pattern in [r"ghp_[a-zA-Z0-9]{36}", r"gho_[a-zA-Z0-9]{36}"]:
            assert not re.search(pattern, content), f"AGENTS.md must not contain hardcoded tokens (pattern: {pattern})"

    def test_api_models_py_describes_pydantic_response_models(self, content: str) -> None:
        """The api/models.py entry must describe Pydantic response models."""
        assert "Pydantic" in content or "pydantic" in content.lower()
        assert "api/models.py" in content

    def test_env_vars_section_lists_database_url(self, content: str) -> None:
        """
        Verify the document includes DATABASE_URL in its environment variables section.
        
        Asserts that the provided file content contains the literal "DATABASE_URL".
        
        Parameters:
            content (str): Full text of the document to inspect.
        """
        assert "DATABASE_URL" in content

    def test_env_vars_section_lists_secret_key(self, content: str) -> None:
        assert "SECRET_KEY" in content

    def test_run_dev_scripts_mentioned(self, content: str) -> None:
        """Combined dev run scripts (run-dev.bat / run-dev.sh) must still be mentioned."""
        assert "run-dev.bat" in content
        assert "run-dev.sh" in content

    # Boundary / regression tests
    def test_production_declaration_section_appears_at_top(self, content: str) -> None:
        """Architecture declaration must appear before Quick orientation."""
        decl_pos = content.find("IMPORTANT: Production Architecture Declaration")
        orient_pos = content.find("## Quick orientation")
        assert decl_pos != -1
        assert orient_pos != -1
        assert decl_pos < orient_pos, "Production Architecture Declaration must appear before Quick orientation"

    def test_no_old_do_not_assume_work_is_merged_text(self, content: str) -> None:
        """Old branch verification content must not appear after replacement."""
        assert "Do not assume work is merged or complete" not in content

    def test_no_old_branch_ref_identity_unclear_text(self, content: str) -> None:
        """Old branch verification content must not appear after replacement."""
        assert "branch/ref identity is unclear, stop and verify" not in content

    def test_gradio_section_dedicated_label_demos_testing_only(self, content: str) -> None:
        """Gradio sections must be qualified as demos/testing only."""
        assert "demos" in content.lower() and "testing" in content.lower()


# ---------------------------------------------------------------------------
# Cross-file consistency tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAgentInstructionsConsistency:
    """Cross-file consistency tests for .github/copilot-instructions.md and AGENTS.md."""

    @pytest.fixture
    def copilot_content(self) -> str:
        """
        Load and return the repository's .github/copilot-instructions.md content.
        
        Returns:
            content (str): The file contents decoded as UTF-8.
        """
        return _load(COPILOT_INSTRUCTIONS)

    @pytest.fixture
    def agents_content(self) -> str:
        """
        Load the repository's AGENTS.md and return its text.
        
        Returns:
            content (str): UTF-8-decoded contents of AGENTS.md
        """
        return _load(AGENTS_MD)

    def test_both_files_declare_fastapi_nextjs_as_production(self, copilot_content: str, agents_content: str) -> None:
        """
        Assert that both the Copilot instructions and AGENTS.md content reference the production stack components FastAPI and Next.js.
        
        Parameters:
            copilot_content (str): The full text content of .github/copilot-instructions.md.
            agents_content (str): The full text content of AGENTS.md.
        """
        for name, content in [
            (".github/copilot-instructions.md", copilot_content),
            ("AGENTS.md", agents_content),
        ]:
            assert "FastAPI" in content, f"{name} must reference FastAPI"
            assert "Next.js" in content, f"{name} must reference Next.js"

    def test_both_files_declare_gradio_as_non_production(self, copilot_content: str, agents_content: str) -> None:
        """
        Assert that both `.github/copilot-instructions.md` and `AGENTS.md` reference Gradio and label it as non-production.
        
        Parameters:
            copilot_content (str): Content of `.github/copilot-instructions.md`.
            agents_content (str): Content of `AGENTS.md`.
        """
        for name, content in [
            (".github/copilot-instructions.md", copilot_content),
            ("AGENTS.md", agents_content),
        ]:
            assert "Gradio" in content, f"{name} must reference Gradio"
            assert "non-production" in content.lower() or "NON-PRODUCTION" in content, (
                f"{name} must label Gradio as non-production"
            )

    def test_both_files_reference_automation_scope_policy(self, copilot_content: str, agents_content: str) -> None:
        assert "AUTOMATION_SCOPE_POLICY.md" in copilot_content, (
            ".github/copilot-instructions.md must reference AUTOMATION_SCOPE_POLICY.md"
        )
        assert "AUTOMATION_SCOPE_POLICY.md" in agents_content, "AGENTS.md must reference AUTOMATION_SCOPE_POLICY.md"

    def test_both_files_reference_adr_0001(self, copilot_content: str, agents_content: str) -> None:
        """
        Verify that both Copilot instructions and AGENTS documentation reference the ADR for production architecture (0001).
        
        Parameters:
            copilot_content (str): Text content of .github/copilot-instructions.md.
            agents_content (str): Text content of AGENTS.md.
        
        Notes:
            The test fails if either file does not contain "0001-production-architecture.md".
        """
        assert "0001-production-architecture.md" in copilot_content, (
            ".github/copilot-instructions.md must reference ADR 0001"
        )
        assert "0001-production-architecture.md" in agents_content, "AGENTS.md must reference ADR 0001"

    def test_both_files_reference_src_config_settings_py(self, copilot_content: str, agents_content: str) -> None:
        assert "src/config/settings.py" in copilot_content
        assert "src/config/settings.py" in agents_content

    def test_both_files_mention_api_models_py(self, copilot_content: str, agents_content: str) -> None:
        """
        Verify that both `.github/copilot-instructions.md` and `AGENTS.md` mention the repository's `api/models.py` file.
        
        Parameters:
            copilot_content (str): Full text content of `.github/copilot-instructions.md`.
            agents_content (str): Full text content of `AGENTS.md`.
        """
        assert "api/models.py" in copilot_content
        assert "api/models.py" in agents_content

    def test_both_files_mention_api_routers(self, copilot_content: str, agents_content: str) -> None:
        assert "api/routers/" in copilot_content
        assert "api/routers/" in agents_content

    def test_both_files_agree_prioritize_production_architecture(
        self, copilot_content: str, agents_content: str
    ) -> None:
        """
        Asserts that both Copilot instructions and AGENTS.md emphasize prioritizing the production architecture.
        
        Performs a case-insensitive check that the exact phrase "prioritize the production architecture" appears in each provided file content.
        
        Parameters:
            copilot_content (str): Full text content of `.github/copilot-instructions.md`.
            agents_content (str): Full text content of `AGENTS.md`.
        """
        assert "prioritize the production architecture" in copilot_content.lower()
        assert "prioritize the production architecture" in agents_content.lower()

    def test_both_files_present_gradio_as_demos_or_testing(self, copilot_content: str, agents_content: str) -> None:
        """Both files must present Gradio as suitable only for demos/testing."""
        for name, content in [
            (".github/copilot-instructions.md", copilot_content),
            ("AGENTS.md", agents_content),
        ]:
            assert "demo" in content.lower() or "testing" in content.lower(), (
                f"{name} must describe Gradio as for demos/testing"
            )

    def test_both_files_reference_graph_lifecycle(self, copilot_content: str, agents_content: str) -> None:
        assert "graph_lifecycle" in copilot_content or "api/graph_lifecycle.py" in copilot_content
        assert "graph_lifecycle" in agents_content or "api/graph_lifecycle.py" in agents_content

    def test_copilot_instructions_has_env_var_guidelines_not_in_agents(self, copilot_content: str) -> None:
        """copilot-instructions.md adds detailed env var guidelines absent from AGENTS.md."""
        # The step-by-step env var guidelines appear in copilot-instructions.md
        assert "When adding environment variables" in copilot_content

    def test_agents_md_has_ci_reference_section(self, agents_content: str) -> None:
        """AGENTS.md must retain its CI reference section."""
        assert "## CI reference" in agents_content
        assert "CircleCI" in agents_content
