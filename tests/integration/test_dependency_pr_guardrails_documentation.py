"""
Validation tests for dependency-change PR and dependency-policy documentation.

Covers:
- .github/PULL_REQUEST_TEMPLATE/dependency-change.md
- docs/DEPENDENCY_POLICY.md
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


DEPENDENCY_CHANGE_TEMPLATE = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE" / "dependency-change.md"
DEPENDENCY_POLICY_FILE = REPO_ROOT / "docs" / "DEPENDENCY_POLICY.md"


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
    def lines(self, content: str) -> list[str]:
        return _lines(content)

    @staticmethod
    def _checkbox_commands(section: str) -> list[str]:
        """Return, in order, the command strings from markdown checkbox lines."""
        commands = []
        for line in section.splitlines():
            m = re.match(r"^\s*-\s*\[\s*[xX ]?\s*\]\s*`(.+?)`\s*$", line)
            if m:
                commands.append(m.group(1).strip())
        return commands

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

    def test_validation_section_includes_full_dev_install_command(self, content: str) -> None:
        """Validation section must contain the exact full dev install command from the policy doc."""
        validation_section = markdown_section(content, "## Validation run locally")
        assert "pip install -r requirements.txt -r requirements-dev.txt" in validation_section, (
            "Validation section must include the canonical full dev command: "
            "'pip install -r requirements.txt -r requirements-dev.txt'"
        )

    def test_validation_section_lists_canonical_core_dev_tools(self, content: str) -> None:
        """Template lists every canonical core-dev tool check in policy order."""
        validation_section = markdown_section(content, "## Validation run locally")
        commands = self._checkbox_commands(validation_section)
        expected = [
            "pytest --version",
            "flake8 --version",
            "pylint --version",
            "mypy --version",
            "black --version",
            "isort --version",
            "ruff --version",
        ]
        assert commands[-len(expected) :] == expected

    def test_validation_section_pip_check_paired_after_each_install(self, content: str) -> None:
        """Every install command must be immediately followed by a pip check line."""
        validation_section = content.split("## Validation run locally")[1].split("##")[0]
        commands = self._checkbox_commands(validation_section)

        install_prefixes = ("pip install -r", "pip install -e")
        for i, cmd in enumerate(commands):
            if any(cmd.startswith(prefix) for prefix in install_prefixes):
                assert i + 1 < len(commands), f"Install command '{cmd}' has no following command in the checklist"
                next_cmd = commands[i + 1]
                assert (
                    next_cmd == "pip check"
                ), f"Install command '{cmd}' must be immediately followed by 'pip check', but got '{next_cmd}'"

    def test_validation_section_editable_install_present_and_not_duplicated(self, content: str) -> None:
        """'pip install -e .' and 'pip install -e ".[dev]"' must each appear exactly once."""
        validation_section = content.split("## Validation run locally")[1].split("##")[0]
        commands = self._checkbox_commands(validation_section)

        bare_editable = [c for c in commands if c == "pip install -e ."]
        dev_editable = [c for c in commands if c == 'pip install -e ".[dev]"']

        assert len(bare_editable) >= 1, "Validation section must include 'pip install -e .'"
        assert (
            len(bare_editable) == 1
        ), f"'pip install -e .' must appear exactly once; found {len(bare_editable)} occurrences"
        assert (
            len(dev_editable) == 1
        ), f"'pip install -e \".[dev]\"' must appear exactly once; found {len(dev_editable)} occurrences"

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

    def test_headings_have_space_after_hash(self, lines: list[str]) -> None:
        for line in lines:
            if line.startswith("#"):
                assert re.match(r"^#{1,6} .+", line), f"Heading must have space after #: {line!r}"

    def test_no_trailing_whitespace(self, lines: list[str]) -> None:
        bad = [(i + 1, line) for i, line in enumerate(lines) if line.rstrip() != line and line.strip()]
        assert not bad, f"Trailing whitespace on lines: {[n for n, _ in bad]}"

    def test_template_has_html_comment_placeholders(self, content: str) -> None:
        """PR template should include HTML comment instructions for authors."""
        assert "<!--" in content and "-->" in content


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
    def lines(self, content: str) -> list[str]:
        return _lines(content)

    def test_file_exists(self) -> None:
        assert DEPENDENCY_POLICY_FILE.exists()
        assert DEPENDENCY_POLICY_FILE.is_file()

    def test_file_is_not_empty(self, content: str) -> None:
        assert len(content.strip()) > 0

    def test_title_is_level_one_heading(self, lines: list[str]) -> None:
        first_heading = next((line for line in lines if line.startswith("#")), None)
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

    def test_order_of_operations_has_exact_canonical_steps(self, content: str) -> None:
        """Dependency operations retain their exact order, uniqueness, and meaning."""
        order_section = markdown_section(content, "## Dependency change order of operations")
        numbered = re.findall(r"^(\d+)\.\s+(.+)$", order_section, re.MULTILINE)
        assert numbered == [
            ("1", "Update `requirements.txt`"),
            ("2", "Align `pyproject.toml` to the intended runtime policy"),
            ("3", "Adjust `requirements-dev.txt` only if dev/test tooling is affected"),
            ("4", "Update validators, workflows, and docs to match"),
            ("5", "Run the validation commands below"),
        ]

    def test_order_of_operations_step_one_is_requirements_txt(self, content: str) -> None:
        order_section = markdown_section(content, "## Dependency change order of operations")
        lines = [line.strip() for line in order_section.splitlines() if line.strip().startswith("1.")]
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
        content = DEPENDENCY_POLICY_FILE.read_text(encoding="utf-8")
        assert "�" not in content

    def test_pyproject_toml_must_not_contradict_requirements_txt(self, content: str) -> None:
        """Policy must explicitly state pyproject.toml must not override requirements.txt."""
        assert "requirements.txt" in content
        # Confirm the subordination relationship is stated
        pyproject_section = content.split("### `pyproject.toml`")[1].split("###")[0]
        assert "requirements.txt" in pyproject_section

    def test_requirements_dev_txt_is_not_runtime_source_of_truth(self, content: str) -> None:
        dev_section = markdown_section(content, "### `requirements-dev.txt`")
        assert "`requirements-dev.txt` is not the runtime source of truth" in dev_section
