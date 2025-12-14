"""Unit tests for validating .openhands/microagents configuration files.
# NOTE: One test (test_proper_grammar_and_punctuation) currently fails because it correctly
# identified a typo in the source file .openhands/microagents/repo_engineer_lead.md:
# There is a double period ("code..") at the end of one sentence. This demonstrates that
# the validation tests are working as intended. The typo should be fixed in the source file.


This module tests microagent markdown files to ensure:
- Valid YAML frontmatter structure and syntax
- Required metadata fields are present and valid
- Content structure follows microagent conventions
- Semantic consistency and correctness
- Compatibility with OpenHands agent framework
"""

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml


class TestMicroagentValidation:
    """Base test class for microagent validation."""

    @pytest.fixture
    def microagents_dir(self) -> Path:
        """Return the path to the microagents directory."""
        return Path(".openhands/microagents")

    @pytest.fixture
    def microagent_files(self, microagents_dir: Path) -> List[Path]:
        """Get all microagent markdown files."""
        assert microagents_dir.exists(), "Microagents directory does not exist"
        files = list(microagents_dir.glob("*.md"))
        assert len(files) > 0, "No microagent files found"
        return files

    def parse_frontmatter(self, content: str) -> tuple[Dict[str, Any], str]:
        """
        Parse YAML frontmatter from markdown content.

        Args:
            content: Full markdown file content

        Returns:
            Tuple of (frontmatter_dict, body_content)

        Raises:
            ValueError: If frontmatter is missing or invalid
        """
        # Strip leading whitespace/newlines and match YAML frontmatter
        content = content.lstrip()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        if not match:
            raise ValueError("No valid frontmatter found")

        frontmatter_text = match.group(1)
        body = match.group(2)

        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in frontmatter: {e}")

        return frontmatter, body


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
        with open(repo_engineer_path, encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def repo_engineer_frontmatter(self, repo_engineer_content: str) -> Dict[str, Any]:
        """Parse and return frontmatter from repo_engineer_lead.md."""
        frontmatter, _ = self.parse_frontmatter(repo_engineer_content)
        return frontmatter

    @pytest.fixture
    def repo_engineer_body(self, repo_engineer_content: str) -> str:
        """Return body content from repo_engineer_lead.md."""
        _, body = self.parse_frontmatter(repo_engineer_content)
        return body

    def test_file_exists(self, repo_engineer_path: Path):
        """Test that repo_engineer_lead.md exists."""
        assert repo_engineer_path.exists()
        assert repo_engineer_path.is_file()

    def test_file_not_empty(self, repo_engineer_content: str):
        """Test that repo_engineer_lead.md is not empty."""
        assert len(repo_engineer_content.strip()) > 0

    def test_has_valid_frontmatter(self, repo_engineer_content: str):
        """Test that file has valid YAML frontmatter."""
        # Should not raise ValueError
        frontmatter, body = self.parse_frontmatter(repo_engineer_content)
        assert isinstance(frontmatter, dict)
        assert len(body) > 0

    def test_frontmatter_has_required_fields(self, repo_engineer_frontmatter: Dict[str, Any]):
        """Test that frontmatter contains all required fields."""
        required_fields = ["name", "type", "version", "agent"]
        for field in required_fields:
            assert field in repo_engineer_frontmatter, f"Missing required field: {field}"

    def test_frontmatter_name_field(self, repo_engineer_frontmatter: Dict[str, Any]):
        """Test that name field is valid."""
        assert "name" in repo_engineer_frontmatter
        name = repo_engineer_frontmatter["name"]
        assert isinstance(name, str)
        assert len(name) > 0
        assert name == "repo_engineer_lead", "Name should match filename convention"

    def test_frontmatter_type_field(self, repo_engineer_frontmatter: Dict[str, Any]):
        """Test that type field is valid."""
        assert "type" in repo_engineer_frontmatter
        agent_type = repo_engineer_frontmatter["type"]
        assert isinstance(agent_type, str)
        assert agent_type in ["knowledge", "action", "hybrid"], "Type must be valid microagent type"
        assert agent_type == "knowledge", "Expected knowledge type for repo_engineer_lead"

    def test_frontmatter_version_field(self, repo_engineer_frontmatter: Dict[str, Any]):
        """Test that version field is valid."""
        assert "version" in repo_engineer_frontmatter
        version = repo_engineer_frontmatter["version"]
        assert isinstance(version, str)
        # Should match semantic versioning pattern
        assert re.match(r"^\d+\.\d+\.\d+$", version), "Version should follow semver format (x.y.z)"

    def test_frontmatter_agent_field(self, repo_engineer_frontmatter: Dict[str, Any]):
        """Test that agent field is valid."""
        assert "agent" in repo_engineer_frontmatter
        agent = repo_engineer_frontmatter["agent"]
        assert isinstance(agent, str)
        assert len(agent) > 0
        # Common OpenHands agent types
        valid_agents = ["CodeActAgent", "PlannerAgent", "BrowsingAgent"]
        assert agent in valid_agents, f"Agent should be one of {valid_agents}"

    def test_frontmatter_no_triggers(self, repo_engineer_frontmatter: Dict[str, Any]):
        """Test that triggers field is absent (as documented in the content)."""
        # The content states "the microagent doesn't have any triggers"
        # So triggers should either be absent or empty
        if "triggers" in repo_engineer_frontmatter:
            triggers = repo_engineer_frontmatter["triggers"]
            assert (
                triggers is None or triggers == [] or triggers == ""
            ), "repo_engineer_lead should not have triggers as per documentation"

    def test_body_content_not_empty(self, repo_engineer_body: str):
        """Test that body content is not empty."""
        assert len(repo_engineer_body.strip()) > 0

    def test_body_describes_purpose(self, repo_engineer_body: str):
        """Test that body describes the microagent's purpose."""
        body_lower = repo_engineer_body.lower()
        # Should mention key responsibilities
        assert any(
            keyword in body_lower for keyword in ["repository engineer", "issues", "prs", "pull requests"]
        ), "Body should describe repository engineering responsibilities"

    def test_body_mentions_issue_review(self, repo_engineer_body: str):
        """Test that body mentions issue review functionality."""
        body_lower = repo_engineer_body.lower()
        assert "issues" in body_lower, "Should mention issue handling"
        assert "review" in body_lower, "Should mention review process"

    def test_body_mentions_pr_handling(self, repo_engineer_body: str):
        """Test that body mentions PR handling functionality."""
        body_lower = repo_engineer_body.lower()
        assert any(term in body_lower for term in ["pr", "pull request"]), "Should mention PR handling"

    def test_body_mentions_code_changes(self, repo_engineer_body: str):
        """Test that body mentions code change capabilities."""
        body_lower = repo_engineer_body.lower()
        assert "code changes" in body_lower or "changes" in body_lower, "Should mention code change capabilities"

    def test_body_mentions_documentation(self, repo_engineer_body: str):
        """Test that body mentions documentation responsibilities."""
        body_lower = repo_engineer_body.lower()
        assert "documentation" in body_lower, "Should mention documentation responsibilities"

    def test_body_mentions_merge_conflicts(self, repo_engineer_body: str):
        """Test that body mentions merge conflict resolution."""
        body_lower = repo_engineer_body.lower()
        assert "merge conflict" in body_lower, "Should mention merge conflict handling"

    def test_body_mentions_branch_hygiene(self, repo_engineer_body: str):
        """Test that body mentions branch hygiene maintenance."""
        body_lower = repo_engineer_body.lower()
        assert "branch hygiene" in body_lower, "Should mention branch hygiene"

    def test_body_mentions_commit_responsibility(self, repo_engineer_body: str):
        """Test that body mentions commit responsibilities."""
        body_lower = repo_engineer_body.lower()
        assert "commit" in body_lower, "Should mention commit responsibilities"

    def test_body_no_malformed_sentences(self, repo_engineer_body: str):
        """Test that body doesn't have obviously malformed sentences."""
        # Check for multiple spaces in a row (except after periods)
        assert not re.search(
            r"[^\.]  +", repo_engineer_body
        ), "Should not have multiple consecutive spaces (except after periods)"

    def test_content_appropriate_length(self, repo_engineer_body: str):
        """Test that content has appropriate length for a microagent description."""
        word_count = len(repo_engineer_body.split())
        assert word_count >= 30, "Content should be at least 30 words"
        assert word_count <= 1000, "Content should be concise (under 1000 words)"

    def test_yaml_frontmatter_syntax_valid(self, repo_engineer_content: str):
        """Test that YAML frontmatter has valid syntax."""
        content = repo_engineer_content.lstrip()
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        assert match is not None, "Frontmatter should be enclosed in --- delimiters"

        frontmatter_text = match.group(1)
        # Should parse without errors
        try:
            parsed = yaml.safe_load(frontmatter_text)
            assert parsed is not None
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax: {e}")

    def test_no_trailing_whitespace(self, repo_engineer_content: str):
        """Test that file doesn't have excessive trailing whitespace."""
        lines = repo_engineer_content.split("\n")
        for i, line in enumerate(lines[:-1], 1):  # Check all but last line
            assert not line.endswith("  "), f"Line {i} has trailing spaces"

    def test_proper_line_endings(self, repo_engineer_path: Path):
        """Test that file uses Unix line endings."""
        with open(repo_engineer_path, "rb") as f:
            content = f.read()
        # Should not contain Windows line endings
        assert b"\r\n" not in content, "File should use Unix line endings (LF, not CRLF)"

    def test_encoding_is_utf8(self, repo_engineer_path: Path):
        """Test that file is UTF-8 encoded."""
        try:
            with open(repo_engineer_path, encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("File should be UTF-8 encoded")


class TestAllMicroagents(TestMicroagentValidation):
    """Test cases for all microagent files in the directory."""

    def test_all_microagents_have_valid_structure(self, microagent_files: List[Path]):
        """Test that all microagent files have valid structure."""
        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            # Should have frontmatter (after stripping leading whitespace)
            content = content.lstrip()
            assert re.match(
                r"^---\s*\n.*?\n---\s*\n", content, re.DOTALL
            ), f"{file_path.name} should have valid frontmatter"

    def test_all_microagents_have_required_fields(self, microagent_files: List[Path]):
        """Test that all microagent files have required frontmatter fields."""
        required_fields = ["name", "type", "version", "agent"]

        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, _ = self.parse_frontmatter(content)

            for field in required_fields:
                assert field in frontmatter, f"{file_path.name} is missing required field: {field}"

    def test_all_microagents_have_unique_names(self, microagent_files: List[Path]):
        """Test that all microagent names are unique."""
        names = []
        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, _ = self.parse_frontmatter(content)
            names.append(frontmatter["name"])

        # Check for duplicates
        assert len(names) == len(set(names)), "All microagent names should be unique"

    def test_all_microagents_valid_versions(self, microagent_files: List[Path]):
        """Test that all microagents have valid semantic versions."""
        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, _ = self.parse_frontmatter(content)
            version = frontmatter["version"]

            assert re.match(
                r"^\d+\.\d+\.\d+$", version
            ), f"{file_path.name} should have valid semver version, got: {version}"

    def test_all_microagents_valid_types(self, microagent_files: List[Path]):
        """Test that all microagents have valid type values."""
        valid_types = ["knowledge", "action", "hybrid"]

        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, _ = self.parse_frontmatter(content)
            agent_type = frontmatter["type"]

            assert (
                agent_type in valid_types
            ), f"{file_path.name} has invalid type: {agent_type}, must be one of {valid_types}"

    def test_all_microagents_valid_agents(self, microagent_files: List[Path]):
        """Test that all microagents have valid agent values."""
        valid_agents = ["CodeActAgent", "PlannerAgent", "BrowsingAgent"]

        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, _ = self.parse_frontmatter(content)
            agent = frontmatter["agent"]

            assert agent in valid_agents, f"{file_path.name} has invalid agent: {agent}, must be one of {valid_agents}"

    def test_triggers_field_is_optional(self, microagent_files: List[Path]):
        """Test that triggers field is optional and properly formatted when present."""
        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            frontmatter, _ = self.parse_frontmatter(content)

            # Triggers is optional
            if "triggers" in frontmatter:
                triggers = frontmatter["triggers"]
                # If present, should be a list of strings or None/empty
                if triggers:
                    assert isinstance(triggers, list), f"{file_path.name} triggers should be a list"
                    for trigger in triggers:
                        assert isinstance(trigger, str), f"{file_path.name} each trigger should be a string"
                        assert len(trigger.strip()) > 0, f"{file_path.name} triggers should not be empty strings"


class TestMicroagentSemantic:
    """Semantic validation tests for microagent content."""

    @pytest.fixture
    def repo_engineer_path(self) -> Path:
        """Return the path to repo_engineer_lead.md."""
        return Path(".openhands/microagents/repo_engineer_lead.md")

    @pytest.fixture
    def repo_engineer_content(self, repo_engineer_path: Path) -> str:
        """Load repo_engineer_lead.md content."""
        with open(repo_engineer_path, encoding="utf-8") as f:
            return f.read()

    def test_autonomous_nature_described(self, repo_engineer_content: str):
        """Test that autonomous nature is described."""
        body_lower = repo_engineer_content.lower()
        assert "autonomous" in body_lower or "automated" in body_lower, "Should describe autonomous/automated nature"

    def test_describes_summary_and_plan(self, repo_engineer_content: str):
        """Test that summary and planning is described."""
        body_lower = repo_engineer_content.lower()
        assert "summary" in body_lower and "plan" in body_lower, "Should mention creating summaries and plans"

    def test_describes_reviewer_interaction(self, repo_engineer_content: str):
        """Test that reviewer interaction is described."""
        body_lower = repo_engineer_content.lower()
        assert any(
            term in body_lower for term in ["reviewer", "contributor", "comment"]
        ), "Should describe interaction with reviewers and contributors"

    def test_describes_commit_process(self, repo_engineer_content: str):
        """Test that commit process is described."""
        body_lower = repo_engineer_content.lower()
        assert "commit" in body_lower, "Should describe commit process"
        # Should explain what is done in commits
        assert any(
            term in body_lower for term in ["commit any changes", "commit changes"]
        ), "Should explain committing changes"

    def test_describes_post_explanation(self, repo_engineer_content: str):
        """Test that posting explanations is described."""
        body_lower = repo_engineer_content.lower()
        assert "post" in body_lower or "explain" in body_lower, "Should mention posting explanations"

    def test_describes_efficiency_focus(self, repo_engineer_content: str):
        """Test that efficiency focus is described."""
        body_lower = repo_engineer_content.lower()
        assert "efficiency" in body_lower, "Should mention efficiency in code fixes"

    def test_proper_grammar_and_punctuation(self, repo_engineer_content: str):
        """Test basic grammar and punctuation."""
        # Extract body after frontmatter
        content = repo_engineer_content.lstrip()
        match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", content, re.DOTALL)
        assert match, "Should have valid structure"
        body = match.group(1)

        # Sentences should end with punctuation
        sentences = [s.strip() for s in body.split(".") if s.strip()]
        for sentence in sentences[:-1]:  # Check all but last
            # Should have reasonable length (not just a word)
            if len(sentence.split()) >= 3:
                # Next sentence should start with capital or be end of string
                continue  # Grammar is subjective, just verify basic structure

        # Should not have obvious typos like double periods
        assert ".." not in body, "Should not have double periods"
        assert "  ." not in body, "Should not have space before period"

    def test_consistent_terminology(self, repo_engineer_content: str):
        """Test that terminology is used consistently."""
        body = repo_engineer_content.lower()

        # If mentions "pull requests", should be consistent
        if "pull requests" in body or "pull request" in body:
            # Should consistently use either "PR" or "pull request"
            # Both are acceptable, just checking presence
            assert "pr" in body or "pull request" in body

        # Issue handling should be mentioned
        assert "issue" in body


class TestMicroagentEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    def repo_engineer_path(self) -> Path:
        """Return the path to repo_engineer_lead.md."""
        return Path(".openhands/microagents/repo_engineer_lead.md")

    def test_file_size_reasonable(self, repo_engineer_path: Path):
        """Test that file size is reasonable."""
        file_size = repo_engineer_path.stat().st_size
        assert file_size > 100, "File should have meaningful content"
        assert file_size < 50000, "File should be concise (under 50KB)"

    def test_no_binary_content(self, repo_engineer_path: Path):
        """Test that file contains only text (no binary data)."""
        with open(repo_engineer_path, "rb") as f:
            content = f.read()

        # Should be decodable as UTF-8
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            pytest.fail("File should contain only UTF-8 text")

    def test_no_control_characters(self, repo_engineer_path: Path):
        """Test that file doesn't contain unexpected control characters."""
        with open(repo_engineer_path, encoding="utf-8") as f:
            content = f.read()

        # Allow: newline, tab, carriage return
        # Disallow: other control characters
        for char in content:
            code = ord(char)
            if code < 32:  # Control character
                assert char in ["\n", "\t", "\r"], f"File should not contain control character: {repr(char)}"

    def test_consistent_newlines(self, repo_engineer_path: Path):
        """Test that newlines are used consistently."""
        with open(repo_engineer_path, "rb") as f:
            content = f.read()

        # Count different newline types
        lf_count = content.count(b"\n")
        crlf_count = content.count(b"\r\n")

        # If any CRLF exist, they should all be CRLF
        # If any LF exist (not part of CRLF), they should all be LF
        if crlf_count > 0:
            # Windows style
            assert lf_count == crlf_count, "Should use consistent line endings"
        # Otherwise it's all LF (Unix style), which is preferred
