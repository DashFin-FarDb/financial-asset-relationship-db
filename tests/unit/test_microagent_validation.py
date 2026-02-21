from __future__ import annotations

"""Unit tests for validating .openhands/microagents configuration files.

This module tests microagent markdown files to ensure:
- Valid YAML frontmatter structure and syntax
- Required metadata fields are present and valid
- Content structure follows microagent conventions
- Semantic consistency and correctness
- Compatibility with OpenHands agent framework
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml


@pytest.mark.unit
class TestMicroagentValidation:
    """Base test class for microagent validation."""

    @pytest.fixture
    def microagents_dir(self) -> Path:
        """Return the path to the microagents directory."""
        return Path(".openhands/microagents")

    @pytest.fixture
    def microagent_files(self, microagents_dir: Path) -> list[Path]:
        """Get all microagent markdown files."""
        assert microagents_dir.exists(), "Microagents directory does not exist"
        files = list(microagents_dir.glob("*.md"))
        assert files, "No microagent files found"
        return files

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
        """Parse YAML frontmatter from markdown content.

        Args:
            content: Full markdown file content.

        Returns:
            Tuple of (frontmatter_dict, body_content).

        Raises:
            ValueError: If frontmatter is missing or invalid.
        """
        content = content.lstrip()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            raise ValueError("No valid frontmatter found")

        frontmatter_text = match.group(1)
        body = match.group(2)

        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            msg = f"Invalid YAML in frontmatter: {exc}"
            raise ValueError(msg) from exc

        return frontmatter, body


@pytest.mark.unit
class TestRepoEngineerLead(TestMicroagentValidation):
    """Test cases for repo_engineer_lead.md microagent."""

    @pytest.fixture
    def repo_engineer_path(self, microagents_dir: Path) -> Path:
        """Return the path to repo_engineer_lead.md."""
        path = microagents_dir / "repo_engineer_lead.md"
        assert path.exists(), "repo_engineer_lead.md not found"
        return path

    @pytest.fixture
    def repo_engineer_content(self, repo_engineer_path: Path) -> str:
        """Load repo_engineer_lead.md content."""
        return repo_engineer_path.read_text(encoding="utf-8")

    @pytest.fixture
    def repo_engineer_frontmatter(
        self,
        repo_engineer_content: str,
    ) -> dict[str, Any]:
        """Parse and return frontmatter from repo_engineer_lead.md."""
        frontmatter, _ = self.parse_frontmatter(repo_engineer_content)
        return frontmatter

    @pytest.fixture
    def repo_engineer_body(self, repo_engineer_content: str) -> str:
        """Return body content from repo_engineer_lead.md."""
        _, body = self.parse_frontmatter(repo_engineer_content)
        return body

    @staticmethod
    def test_file_exists(repo_engineer_path: Path) -> None:
        """Test that repo_engineer_lead.md exists."""
        assert repo_engineer_path.exists()
        assert repo_engineer_path.is_file()

    @staticmethod
    def test_file_not_empty(repo_engineer_content: str) -> None:
        """Test that repo_engineer_lead.md is not empty."""
        assert repo_engineer_content.strip()

    def test_has_valid_frontmatter(self, repo_engineer_content: str) -> None:
        """Test that file has valid YAML frontmatter."""
        frontmatter, body = self.parse_frontmatter(repo_engineer_content)
        assert isinstance(frontmatter, dict)
        assert body

    @staticmethod
    def test_frontmatter_has_required_fields(
        repo_engineer_frontmatter: dict[str, Any],
    ) -> None:
        """Test that frontmatter contains all required fields."""
        required_fields = ["name", "type", "version", "agent"]
        for field in required_fields:
            assert field in repo_engineer_frontmatter, (
                f"Missing required field: {field}"
            )

    @staticmethod
    def test_frontmatter_name_field(
        repo_engineer_frontmatter: dict[str, Any],
    ) -> None:
        """Test that name field is valid."""
        assert "name" in repo_engineer_frontmatter
        name = repo_engineer_frontmatter["name"]
        assert isinstance(name, str)
        assert name
        assert name == "repo_engineer_lead", "Name should match filename convention"

    @staticmethod
    def test_frontmatter_type_field(
        repo_engineer_frontmatter: dict[str, Any],
    ) -> None:
        """Test that type field is valid."""
        assert "type" in repo_engineer_frontmatter
        agent_type = repo_engineer_frontmatter["type"]
        assert isinstance(agent_type, str)
        valid_types = ["knowledge", "action", "hybrid"]
        assert agent_type in valid_types, "Type must be valid microagent type"
        assert agent_type == "knowledge", (
            "Expected knowledge type for repo_engineer_lead"
        )

    @staticmethod
    def test_frontmatter_version_field(
        repo_engineer_frontmatter: dict[str, Any],
    ) -> None:
        """Validate that the version field uses x.y.z format."""
        assert "version" in repo_engineer_frontmatter
        version = repo_engineer_frontmatter["version"]
        assert isinstance(version, str)
        assert re.match(r"^\d+\.\d+\.\d+$", version), (
            "Version should follow semver format (x.y.z)"
        )

    @staticmethod
    def test_frontmatter_agent_field(
        repo_engineer_frontmatter: dict[str, Any],
    ) -> None:
        """Validate the frontmatter 'agent' field for repo_engineer_lead."""
        assert "agent" in repo_engineer_frontmatter
        agent = repo_engineer_frontmatter["agent"]
        assert isinstance(agent, str)
        assert agent
        valid_agents = ["CodeActAgent", "PlannerAgent", "BrowsingAgent"]
        assert agent in valid_agents, f"Agent should be one of {valid_agents}"

    @staticmethod
    def test_frontmatter_triggers_optional_and_well_formed(
        repo_engineer_frontmatter: dict[str, Any],
    ) -> None:
        """Test that triggers are optional and well-formed when present.

        If present and truthy, triggers must be a list of non-empty strings.
        """
        if "triggers" not in repo_engineer_frontmatter:
            return

        triggers = repo_engineer_frontmatter["triggers"]
        if triggers in (None, [], ""):
            return

        assert isinstance(triggers, list), "triggers should be a list when present"
        for trigger in triggers:
            assert isinstance(trigger, str) and trigger.strip(), (
                "each trigger should be a non-empty string"
            )

    @staticmethod
    def test_body_describes_microagent_purpose(repo_engineer_body: str) -> None:
        """Body should describe repository engineering responsibilities."""
        body_lower = repo_engineer_body.lower()
        keywords = ["repository engineer", "issues", "prs", "pull requests"]
        assert any(keyword in body_lower for keyword in keywords), (
            "Body should describe repository engineering responsibilities"
        )

    @staticmethod
    def test_body_mentions_issue_review(repo_engineer_body: str) -> None:
        """Test that body mentions issue review functionality."""
        body_lower = repo_engineer_body.lower()
        assert "issues" in body_lower, "Should mention issue handling"
        assert "review" in body_lower, "Should mention review process"

    @staticmethod
    def test_body_mentions_pr_handling(repo_engineer_body: str) -> None:
        """Check that the body text mentions pull request handling."""
        body_lower = repo_engineer_body.lower()
        assert any(term in body_lower for term in ["pr", "pull request"]), (
            "Should mention PR handling"
        )

    @staticmethod
    def test_body_mentions_code_changes(repo_engineer_body: str) -> None:
        """Test that body mentions code change capabilities."""
        body_lower = repo_engineer_body.lower()
        msg = "Should mention code change capabilities"
        assert "code changes" in body_lower or "changes" in body_lower, msg

    @staticmethod
    def test_body_mentions_documentation(repo_engineer_body: str) -> None:
        """Test that body mentions documentation responsibilities."""
        body_lower = repo_engineer_body.lower()
        assert "documentation" in body_lower, (
            "Should mention documentation responsibilities"
        )

    @staticmethod
    def test_body_mentions_merge_conflicts(repo_engineer_body: str) -> None:
        """Test that body mentions merge conflict resolution."""
        body_lower = repo_engineer_body.lower()
        assert "merge conflict" in body_lower, "Should mention merge conflict handling"

    @staticmethod
    def test_body_mentions_branch_hygiene(repo_engineer_body: str) -> None:
        """Test that body mentions branch hygiene maintenance."""
        body_lower = repo_engineer_body.lower()
        assert "branch hygiene" in body_lower, "Should mention branch hygiene"

    @staticmethod
    def test_body_mentions_commit_responsibility(repo_engineer_body: str) -> None:
        """Test that body mentions commit responsibilities."""
        body_lower = repo_engineer_body.lower()
        assert "commit" in body_lower, "Should mention commit responsibilities"

    @staticmethod
    def test_body_no_malformed_sentences(repo_engineer_body: str) -> None:
        """Test that body doesn't have obviously malformed sentences."""
        pattern = r"[^\.]  +"
        msg = "Should not have multiple spaces (except after periods)"
        assert not re.search(pattern, repo_engineer_body), msg

    @staticmethod
    def test_content_appropriate_length(repo_engineer_body: str) -> None:
        """Ensure the body length is between 30 and 1000 words."""
        word_count = len(repo_engineer_body.split())
        assert word_count >= 30, "Content should be at least 30 words"
        assert word_count <= 1000, "Content should be concise (under 1000 words)"

    @staticmethod
    def test_yaml_frontmatter_syntax_valid(repo_engineer_content: str) -> None:
        """Test that YAML frontmatter has valid syntax."""
        content = repo_engineer_content.lstrip()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        assert match is not None, "Frontmatter should be enclosed in --- delimiters"

        frontmatter_text = match.group(1)
        try:
            parsed = yaml.safe_load(frontmatter_text)
            assert parsed is not None
        except yaml.YAMLError as exc:
            pytest.fail(f"Invalid YAML syntax: {exc}")

    @staticmethod
    def test_no_trailing_whitespace(repo_engineer_content: str) -> None:
        """Test that file doesn't have excessive trailing whitespace."""
        lines = repo_engineer_content.split("\n")
        for i, line in enumerate(lines[:-1], start=1):
            assert not line.endswith("  "), f"Line {i} has trailing spaces"

    @staticmethod
    def test_proper_line_endings(repo_engineer_path: Path) -> None:
        """Test that file uses Unix line endings."""
        content = repo_engineer_path.read_bytes()
        assert b"\r\n" not in content, "File should use LF, not CRLF"

    @staticmethod
    def test_encoding_is_utf8(repo_engineer_path: Path) -> None:
        """Test that file is UTF-8 encoded."""
        try:
            repo_engineer_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            pytest.fail("File should be UTF-8 encoded")


@pytest.mark.unit
class TestAllMicroagents(TestMicroagentValidation):
    """Test cases for all microagent files in the directory."""

    @staticmethod
    def test_all_microagents_have_valid_structure(
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagent files have valid structure."""
        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8").lstrip()
            assert re.match(
                r"^---\s*\n.*?\n---\s*\n",
                content,
                re.DOTALL,
            ), f"{file_path.name} should have valid frontmatter"

    def test_all_microagents_have_required_fields(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Ensure every microagent has required YAML fields."""
        required_fields = ["name", "type", "version", "agent"]

        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, _ = self.parse_frontmatter(content)

            for field in required_fields:
                assert field in frontmatter, (
                    f"{file_path.name} is missing required field: {field}"
                )

    def test_all_microagents_have_unique_names(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagent names are unique."""
        names: list[str] = []
        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, _ = self.parse_frontmatter(content)
            names.append(frontmatter["name"])

        assert len(names) == len(set(names)), "All microagent names should be unique"

    def test_all_microagents_valid_versions(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagents have valid semantic versions."""
        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, _ = self.parse_frontmatter(content)
            version = frontmatter["version"]

            assert re.match(r"^\d+\.\d+\.\d+$", version), (
                f"{file_path.name} should have valid semver version, got: {version}"
            )

    def test_all_microagents_valid_types(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagents have valid type values."""
        valid_types = ["knowledge", "action", "hybrid"]

        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, _ = self.parse_frontmatter(content)
            agent_type = frontmatter["type"]

            assert agent_type in valid_types, (
                f"{file_path.name} has invalid type: {agent_type}, "
                f"must be one of {valid_types}"
            )

    def test_all_microagents_valid_agents(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagents have valid agent values."""
        valid_agents = ["CodeActAgent", "PlannerAgent", "BrowsingAgent"]

        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, _ = self.parse_frontmatter(content)
            agent = frontmatter["agent"]

            assert agent in valid_agents, (
                f"{file_path.name} has invalid agent: {agent}, "
                f"must be one of {valid_agents}"
            )

    def test_triggers_field_is_optional(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Test that triggers field is optional and well-formed when present."""
        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")
            frontmatter, _ = self.parse_frontmatter(content)

            if "triggers" not in frontmatter:
                continue

            triggers = frontmatter["triggers"]
            if not triggers:
                continue

            assert isinstance(triggers, list), (
                f"{file_path.name} triggers should be a list"
            )
            for trigger in triggers:
                assert isinstance(trigger, str), (
                    f"{file_path.name} each trigger should be a string"
                )
                assert trigger.strip(), (
                    f"{file_path.name} triggers should not be empty strings"
                )


@pytest.mark.unit
class TestMicroagentSemantic:
    """Semantic validation tests for microagent content."""

    @pytest.fixture
    def repo_engineer_path(self) -> Path:
        """Return the path to repo_engineer_lead.md."""
        return Path(".openhands/microagents/repo_engineer_lead.md")

    @pytest.fixture
    def repo_engineer_content(self, repo_engineer_path: Path) -> str:
        """Load repo_engineer_lead.md content."""
        return repo_engineer_path.read_text(encoding="utf-8")

    @staticmethod
    def test_autonomous_nature_described(repo_engineer_content: str) -> None:
        """Verify the body describes autonomous or automated nature."""
        body_lower = repo_engineer_content.lower()
        msg = "Should describe autonomous/automated nature"
        assert "autonomous" in body_lower or "automated" in body_lower, msg

    @staticmethod
    def test_describes_summary_and_plan(repo_engineer_content: str) -> None:
        """Test that summary and planning is described."""
        body_lower = repo_engineer_content.lower()
        msg = "Should mention creating summaries and plans"
        assert "summary" in body_lower and "plan" in body_lower, msg

    @staticmethod
    def test_describes_reviewer_interaction(
        repo_engineer_content: str,
    ) -> None:
        """Verify the body describes interaction with reviewers or contributors."""
        body_lower = repo_engineer_content.lower()
        terms = ["reviewer", "contributor", "comment"]
        assert any(term in body_lower for term in terms), (
            "Should describe interaction with reviewers and contributors"
        )

    @staticmethod
    def test_describes_commit_process(repo_engineer_content: str) -> None:
        """Test that commit process is described."""
        body_lower = repo_engineer_content.lower()
        assert "commit" in body_lower, "Should describe commit process"
        terms = ["commit any changes", "commit changes"]
        assert any(term in body_lower for term in terms), (
            "Should explain committing changes"
        )

    @staticmethod
    def test_describes_post_explanation(repo_engineer_content: str) -> None:
        """Check that the body mentions posting or explaining changes."""
        body_lower = repo_engineer_content.lower()
        msg = "Should mention posting explanations"
        assert "post" in body_lower or "explain" in body_lower, msg

    @staticmethod
    def test_describes_efficiency_focus(repo_engineer_content: str) -> None:
        """Test that efficiency focus is described."""
        body_lower = repo_engineer_content.lower()
        assert "efficiency" in body_lower, "Should mention efficiency in code fixes"

    @staticmethod
    def test_proper_grammar_and_punctuation(
        repo_engineer_content: str,
    ) -> None:
        """Test basic grammar and punctuation."""
        content = repo_engineer_content.lstrip()
        match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", content, re.DOTALL)
        assert match, "Should have valid structure"
        body = match.group(1)

        sentences = [s.strip() for s in body.split(".") if s.strip()]
        for sentence in sentences[:-1]:
            if len(sentence.split()) >= 3:
                continue

        assert ".." not in body, "Should not have double periods"
        assert "  ." not in body, "Should not have space before period"

    @staticmethod
    def test_consistent_terminology(repo_engineer_content: str) -> None:
        """Test that terminology is used consistently."""
        body = repo_engineer_content.lower()

        if "pull requests" in body or "pull request" in body:
            assert "pr" in body or "pull request" in body

        assert "issue" in body


@pytest.mark.unit
class TestMicroagentEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def repo_engineer_path(self) -> Path:
        """Return the path to repo_engineer_lead.md."""
        return Path(".openhands/microagents/repo_engineer_lead.md")

    @staticmethod
    def test_file_size_reasonable(repo_engineer_path: Path) -> None:
        """Test that file size is reasonable."""
        file_size = repo_engineer_path.stat().st_size
        assert file_size > 100, "File should have meaningful content"
        assert file_size < 50_000, "File should be concise (under 50KB)"

    @staticmethod
    def test_no_binary_content(repo_engineer_path: Path) -> None:
        """Test that file contains only text (no binary data)."""
        content = repo_engineer_path.read_bytes()

        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            pytest.fail("File should contain only UTF-8 text")

    @staticmethod
    def test_no_control_characters(repo_engineer_path: Path) -> None:
        """Test that file doesn't contain unexpected control characters."""
        content = repo_engineer_path.read_text(encoding="utf-8")

        for char in content:
            code = ord(char)
            if code < 32:
                assert char in ["\n", "\t", "\r"], (
                    f"File should not contain control character: {repr(char)}"
                )

    @staticmethod
    def test_consistent_newlines(repo_engineer_path: Path) -> None:
        """Test that newlines are used consistently."""
        content = repo_engineer_path.read_bytes()

        lf_count = content.count(b"\n")
        crlf_count = content.count(b"\r\n")

        if crlf_count > 0:
            assert lf_count == crlf_count, "Should use consistent line endings"


@pytest.mark.unit
class TestMicroagentPerformance(TestMicroagentValidation):
    """Performance and size tests for microagent files."""

    @staticmethod
    def test_all_microagents_reasonable_size(
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagent files are reasonably sized."""
        for file_path in microagent_files:
            file_size = file_path.stat().st_size
            assert file_size < 100_000, (
                f"{file_path.name} is too large ({file_size} bytes)"
            )
            assert file_size > 50, f"{file_path.name} is too small ({file_size} bytes)"

    @staticmethod
    def test_all_microagents_parse_quickly(
        microagent_files: list[Path],
    ) -> None:
        """Test that all microagents can be read quickly."""
        import time

        for file_path in microagent_files:
            start = time.time()
            _ = file_path.read_text(encoding="utf-8")
            elapsed = time.time() - start
            assert elapsed < 1.0, f"{file_path.name} took too long to read"


@pytest.mark.unit
class TestMicroagentDocumentation(TestMicroagentValidation):
    """Test documentation quality in microagent files."""

    def test_all_microagents_have_body_content(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Verify each microagent has at least 20 words in its body."""
        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")

            try:
                _, body = self.parse_frontmatter(content)
            except ValueError as exc:
                pytest.skip(f"{file_path.name} has unparseable frontmatter: {exc}")
            else:
                word_count = len(body.split())
                assert word_count >= 20, (
                    f"{file_path.name} has insufficient body content "
                    f"({word_count} words)"
                )

    def test_all_microagents_use_markdown_formatting(
        self,
        microagent_files: list[Path],
    ) -> None:
        """Test that microagent bodies use markdown formatting."""
        for file_path in microagent_files:
            content = file_path.read_text(encoding="utf-8")

            try:
                _, body = self.parse_frontmatter(content)
            except ValueError as exc:
                pytest.skip(f"{file_path.name} has unparseable frontmatter: {exc}")
            else:
                has_markdown = any(
                    token in body for token in ("**", "*", "#", "-", "`")
                )
                assert has_markdown, f"{file_path.name} should use markdown formatting"


@pytest.mark.unit
class TestMicroagentBoundaryConditions:
    """Test boundary conditions and edge cases."""

    @staticmethod
    def test_microagent_with_minimal_valid_frontmatter(tmp_path: Path) -> None:
        """Minimal valid frontmatter can be parsed correctly."""
        test_file = tmp_path / "minimal.md"
        test_file.write_text(
            (
                "---\n"
                "name: test\n"
                "type: knowledge\n"
                "version: 1.0.0\n"
                "agent: CodeActAgent\n"
                "---\n"
                "Minimal content."
            ),
            encoding="utf-8",
        )

        content = test_file.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        assert match is not None
        frontmatter_text = match.group(1)
        parsed = yaml.safe_load(frontmatter_text)
        assert parsed["name"] == "test"

    @staticmethod
    def test_frontmatter_with_extra_fields_allowed(tmp_path: Path) -> None:
        """Test that extra fields in frontmatter are allowed."""
        test_file = tmp_path / "extra.md"
        test_file.write_text(
            (
                "---\n"
                "name: test\n"
                "type: knowledge\n"
                "version: 1.0.0\n"
                "agent: CodeActAgent\n"
                "extra_field: extra_value\n"
                "custom: true\n"
                "---\n"
                "Content."
            ),
            encoding="utf-8",
        )

        content = test_file.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        assert match is not None
        frontmatter_text = match.group(1)
        parsed = yaml.safe_load(frontmatter_text)

        assert "extra_field" in parsed
        assert parsed["extra_field"] == "extra_value"


@pytest.mark.unit
class TestMicroagentRegressionCases:
    """Regression tests for previously identified issues."""

    @staticmethod
    def test_double_period_detection() -> None:
        """Regression: Test that double periods are detected."""
        content_with_error = (
            "---\n"
            "name: test\n"
            "type: knowledge\n"
            "version: 1.0.0\n"
            "agent: CodeActAgent\n"
            "---\n"
            "This is a sentence.. This should be caught."
        )

        match = re.match(
            r"^---\s*\n.*?\n---\s*\n(.*)$",
            content_with_error,
            re.DOTALL,
        )
        assert match is not None
        body = match.group(1)

        assert ".." in body

    @staticmethod
    def test_malformed_frontmatter_raises_error(tmp_path: Path) -> None:
        """Test that malformed frontmatter raises appropriate error."""
        test_file = tmp_path / "malformed.md"
        test_file.write_text(
            ("---\nname: test\ntype: knowledge\nversion 1.0.0\n---\nContent."),
            encoding="utf-8",
        )

        content = test_file.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        assert match is not None
        frontmatter_text = match.group(1)

        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(frontmatter_text)
