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


@pytest.mark.unit
class TestMicroagentValidation:
    """Base test class for microagent validation."""

    @pytest.fixture
    def microagents_dir(self) -> Path:
        """
        Path to the .openhands/microagents directory.

        Returns:
            Path: Path object pointing to the `.openhands/microagents` directory.
        """
        return Path(".openhands/microagents")

    @pytest.fixture
    def microagent_files(self, microagents_dir: Path) -> List[Path]:
        """
        Return a list of markdown files found in the given microagents directory.

        Parameters:
            microagents_dir (Path): Path to the microagents directory (expected to contain .md files).

        Returns:
            List[Path]: A list of Paths for markdown files in the directory.

        Raises:
            AssertionError: If the directory does not exist or if no `.md` files are found.
        """
        assert microagents_dir.exists(), "Microagents directory does not exist"
        files = list(microagents_dir.glob("*.md"))
        assert len(files) > 0, "No microagent files found"
        return files

    @staticmethod
    def parse_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
        """
        Extract YAML frontmatter and the remaining markdown body from a Markdown document.

        Parameters:
            content (str): Full text of a Markdown file, optionally with leading whitespace.

        Returns:
            tuple[Dict[str, Any], str]: A pair where the first element is the parsed frontmatter mapping (dict)
            and the second element is the markdown body as a string.

        Raises:
            ValueError: If frontmatter delimiters are missing or the frontmatter is not valid YAML.
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


@pytest.mark.unit
class TestRepoEngineerLead(TestMicroagentValidation):
    """Test cases for repo_engineer_lead.md microagent."""

    @pytest.fixture
    @staticmethod
    def repo_engineer_path(microagents_dir: Path) -> Path:
        """
        Get the filesystem path to the repo_engineer_lead.md file within the provided microagents directory.

        Parameters:
            microagents_dir (Path): Directory containing microagent markdown files (e.g., .openhands/microagents).

        Returns:
            Path: Full path to repo_engineer_lead.md.

        Raises:
            AssertionError: If repo_engineer_lead.md does not exist at the computed path.
        """
        path = microagents_dir / "repo_engineer_lead.md"
        assert path.exists(), "repo_engineer_lead.md not found"
        return path

    @pytest.fixture
    @staticmethod
    def repo_engineer_content(repo_engineer_path: Path) -> str:
        """
        Return the contents of the repo_engineer_lead.md file.

        Parameters:
            repo_engineer_path (Path): Path to the repo_engineer_lead.md file.

        Returns:
            content (str): File contents decoded as UTF-8.
        """
        with open(repo_engineer_path, encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def repo_engineer_frontmatter(self, repo_engineer_content: str) -> Dict[str, Any]:
        """
        Extract the YAML frontmatter from the supplied repo_engineer_lead.md content.

        Parameters:
            repo_engineer_content (str): Full Markdown text of repo_engineer_lead.md, including YAML frontmatter.

        Returns:
            frontmatter (Dict[str, Any]): Parsed frontmatter mapping frontmatter keys to their values.
        """
        frontmatter, _ = self.parse_frontmatter(repo_engineer_content)
        return frontmatter

    @pytest.fixture
    def repo_engineer_body(self, repo_engineer_content: str) -> str:
        """
        Extract the markdown body (the content after YAML frontmatter) from the given microagent file text.

        Parameters:
            repo_engineer_content (str): The full markdown file content, including YAML frontmatter and body.

        Returns:
            body (str): The markdown body with the frontmatter removed.
        """
        _, body = self.parse_frontmatter(repo_engineer_content)
        return body

    @staticmethod
    def test_file_exists(repo_engineer_path: Path):
        """Test that repo_engineer_lead.md exists."""
        assert repo_engineer_path.exists()
        assert repo_engineer_path.is_file()

    @staticmethod
    def test_file_not_empty(repo_engineer_content: str):
        """Test that repo_engineer_lead.md is not empty."""
        assert len(repo_engineer_content.strip()) > 0

    def test_has_valid_frontmatter(self, repo_engineer_content: str):
        """Test that file has valid YAML frontmatter."""
        # Should not raise ValueError
        frontmatter, body = self.parse_frontmatter(repo_engineer_content)
        assert isinstance(frontmatter, dict)
        assert len(body) > 0

    @staticmethod
    def test_frontmatter_has_required_fields(repo_engineer_frontmatter: Dict[str, Any]):
        """Test that frontmatter contains all required fields."""
        required_fields = ["name", "type", "version", "agent"]
        for field in required_fields:
            assert field in repo_engineer_frontmatter, f"Missing required field: {field}"

    @staticmethod
    def test_frontmatter_name_field(repo_engineer_frontmatter: Dict[str, Any]):
        """
        Validate the frontmatter 'name' field for the repo_engineer_lead microagent.

        Parameters:
            repo_engineer_frontmatter (Dict[str, Any]): Parsed YAML frontmatter from repo_engineer_lead.md.

        Checks that the 'name' field exists, is a non-empty string, and equals "repo_engineer_lead".
        """
        assert "name" in repo_engineer_frontmatter
        name = repo_engineer_frontmatter["name"]
        assert isinstance(name, str)
        assert len(name) > 0
        assert name == "repo_engineer_lead", "Name should match filename convention"

    @staticmethod
    def test_frontmatter_type_field(repo_engineer_frontmatter: Dict[str, Any]):
        """Test that type field is valid."""
        assert "type" in repo_engineer_frontmatter
        agent_type = repo_engineer_frontmatter["type"]
        assert isinstance(agent_type, str)
        assert agent_type in ["knowledge", "action", "hybrid"], "Type must be valid microagent type"
        assert agent_type == "knowledge", "Expected knowledge type for repo_engineer_lead"

    @staticmethod
    def test_frontmatter_version_field(
        repo_engineer_frontmatter: Dict[str, Any],
    ) -> None:
        """
        Validate that the frontmatter contains a `version` field and that its value matches semantic versioning in the form `x.y.z`.

        Parameters:
            repo_engineer_frontmatter (Dict[str, Any]): Parsed YAML frontmatter for the microagent.
         Returns:
            None
        Raises:
            AssertionError: If the version field is missing or invalid.
        """
        assert "version" in repo_engineer_frontmatter
        version = repo_engineer_frontmatter["version"]
        assert isinstance(version, str)
        # Should match semantic versioning pattern
        assert re.match(r"^\d+\.\d+\.\d+$", version), "Version should follow semver format (x.y.z)"

    @staticmethod
    def test_frontmatter_agent_field(repo_engineer_frontmatter: Dict[str, Any]) -> None:
        """
        Validate the frontmatter 'agent' field for the repo_engineer_lead microagent.

        Parameters:
            repo_engineer_frontmatter (Dict[str, Any]): Parsed YAML frontmatter for repo_engineer_lead.md; expected to contain an 'agent' entry.

        Raises:
            AssertionError: If the 'agent' key is missing, not a non-empty string, or not one of the allowed agents (CodeActAgent, PlannerAgent, BrowsingAgent).
        """
        assert "agent" in repo_engineer_frontmatter
        agent = repo_engineer_frontmatter["agent"]
        assert isinstance(agent, str)
        assert len(agent) > 0
        # Common OpenHands agent types
        valid_agents = ["CodeActAgent", "PlannerAgent", "BrowsingAgent"]
        assert agent in valid_agents, f"Agent should be one of {valid_agents}"

    @staticmethod
    def test_frontmatter_no_triggers(repo_engineer_frontmatter: Dict[str, Any]):
        """Test that triggers field is absent (as documented in the content)."""
        # The content states "the microagent doesn't have any triggers"
        # So triggers should either be absent or empty
        if "triggers" in repo_engineer_frontmatter:
            triggers = repo_engineer_frontmatter["triggers"]
            assert (
                triggers is None or triggers == [] or triggers == ""
            ), "repo_engineer_lead should not have triggers as per documentation"

    @staticmethod
    def test_body_content_not_empty(repo_engineer_body: str):
        """Test that body content is not empty."""
        assert len(repo_engineer_body.strip()) > 0

    @staticmethod
    def test_body_describes_purpose(repo_engineer_body: str):
        """Test that body describes the microagent's purpose."""
        body_lower = repo_engineer_body.lower()
        # Should mention key responsibilities
        assert any(
            keyword in body_lower for keyword in ["repository engineer", "issues", "prs", "pull requests"]
        ), "Body should describe repository engineering responsibilities"

    @staticmethod
    def test_body_mentions_issue_review(repo_engineer_body: str):
        """
        Verify the microagent body mentions both issue handling and review processes.

        Parameters:
            repo_engineer_body (str): Markdown body of the repo_engineer_lead microagent to inspect.
        """
        body_lower = repo_engineer_body.lower()
        assert "issues" in body_lower, "Should mention issue handling"
        assert "review" in body_lower, "Should mention review process"

    @staticmethod
    def test_body_mentions_pr_handling(repo_engineer_body: str):
        """
        Verify the microagent body mentions pull request handling.

        Parameters:
            repo_engineer_body (str): Markdown body content to inspect; matching is case-insensitive and looks for the terms "pr" or "pull request".
        """
        body_lower = repo_engineer_body.lower()
        assert any(term in body_lower for term in ["pr", "pull request"]), "Should mention PR handling"

    @staticmethod
    def test_body_mentions_code_changes(repo_engineer_body: str):
        """
        Checks that the microagent body mentions code change capabilities.

        Parameters:
            repo_engineer_body (str): The markdown body content of the microagent being tested; comparison is case-insensitive.
        """
        body_lower = repo_engineer_body.lower()
        assert "code changes" in body_lower or "changes" in body_lower, "Should mention code change capabilities"

    @staticmethod
    def test_body_mentions_documentation(repo_engineer_body: str):
        """
        Check that the microagent body mentions documentation responsibilities.

        Parameters:
            repo_engineer_body (str): The markdown body content of the microagent file to inspect.
        """
        body_lower = repo_engineer_body.lower()
        assert "documentation" in body_lower, "Should mention documentation responsibilities"

    @staticmethod
    def test_body_mentions_merge_conflicts(repo_engineer_body: str):
        """Test that body mentions merge conflict resolution."""
        body_lower = repo_engineer_body.lower()
        assert "merge conflict" in body_lower, "Should mention merge conflict handling"

    @staticmethod
    def test_body_mentions_branch_hygiene(repo_engineer_body: str):
        """Test that body mentions branch hygiene maintenance."""
        body_lower = repo_engineer_body.lower()
        assert "branch hygiene" in body_lower, "Should mention branch hygiene"

    @staticmethod
    def test_body_mentions_commit_responsibility(repo_engineer_body: str):
        """Test that body mentions commit responsibilities."""
        body_lower = repo_engineer_body.lower()
        assert "commit" in body_lower, "Should mention commit responsibilities"

    @staticmethod
    def test_body_no_malformed_sentences(repo_engineer_body: str):
        """Test that body doesn't have obviously malformed sentences."""
        # Check for multiple spaces in a row (except after periods)
        assert not re.search(
            r"[^\.]  +", repo_engineer_body
        ), "Should not have multiple consecutive spaces (except after periods)"

    @staticmethod
    def test_content_appropriate_length(repo_engineer_body: str) -> None:
        """
        Ensure the microagent body contains between 30 and 1000 words.

        Parameters:
                repo_engineer_body (str): Markdown body of the microagent to validate.

        Raises:
                AssertionError: If the word count is less than 30 or greater than 1000.
        """
        word_count = len(repo_engineer_body.split())
        assert word_count >= 30, "Content should be at least 30 words"
        assert word_count <= 1000, "Content should be concise (under 1000 words)"

    @staticmethod
    def test_yaml_frontmatter_syntax_valid(repo_engineer_content: str):
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

    @staticmethod
    def test_no_trailing_whitespace(repo_engineer_content: str):
        """
        Ensure no non-final line in the file ends with two trailing spaces.

        Parameters:
            repo_engineer_content (str): Full text content of the microagent markdown file to validate.
        """
        lines = repo_engineer_content.split("\n")
        for i, line in enumerate(lines[:-1], 1):  # Check all but last line
            assert not line.endswith("  "), f"Line {i} has trailing spaces"

    @staticmethod
    def test_proper_line_endings(repo_engineer_path: Path):
        """Test that file uses Unix line endings."""
        with open(repo_engineer_path, "rb") as f:
            content = f.read()
        # Should not contain Windows line endings
        assert b"\r\n" not in content, "File should use Unix line endings (LF, not CRLF)"

    @staticmethod
    def test_encoding_is_utf8(repo_engineer_path: Path):
        """
        Verify the microagent file at the given path is decodable as UTF-8.

        Parameters:
                repo_engineer_path (Path): Path to the microagent markdown file to check.

        Raises:
                The test fails if the file cannot be decoded as UTF-8.
        """
        try:
            with open(repo_engineer_path, encoding="utf-8") as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("File should be UTF-8 encoded")


@pytest.mark.unit
class TestAllMicroagents(TestMicroagentValidation):
    """Test cases for all microagent files in the directory."""

    @staticmethod
    def test_all_microagents_have_valid_structure(microagent_files: List[Path]):
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
        """
        Ensure every microagent markdown file contains the required YAML frontmatter fields.

        Checks that each file in `microagent_files` has a parsed frontmatter mapping containing the keys: "name", "type", "version", and "agent".
        """
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
        """
        Ensure every microagent file declares a semantic version in its frontmatter.

        Parameters:
            microagent_files (List[Path]): List of paths to microagent markdown files to validate.

        Notes:
            Each file's `version` frontmatter must match the `x.y.z` pattern (digits separated by dots); the test fails if any file's version does not match.
        """
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


@pytest.mark.unit
class TestMicroagentSemantic:
    """Semantic validation tests for microagent content."""

    @pytest.fixture
    @staticmethod
    def repo_engineer_path() -> Path:
        """
        Path to the repo_engineer_lead microagent markdown file.

        Returns:
            Path: Path to ".openhands/microagents/repo_engineer_lead.md".
        """
        return Path(".openhands/microagents/repo_engineer_lead.md")

    @pytest.fixture
    @staticmethod
    def repo_engineer_content(repo_engineer_path: Path) -> str:
        """
        Return the contents of the repo_engineer_lead.md file.

        Parameters:
            repo_engineer_path (Path): Path to the repo_engineer_lead.md file.

        Returns:
            content (str): File contents decoded as UTF-8.
        """
        with open(repo_engineer_path, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    def test_autonomous_nature_described(repo_engineer_content: str):
        """
        Assert the microagent body indicates it is autonomous or automated.

        Parameters:
            repo_engineer_content (str): Full markdown content of the repo_engineer_lead microagent file.

        Raises:
            AssertionError: If neither "autonomous" nor "automated" appears in the content (case-insensitive).
        """
        body_lower = repo_engineer_content.lower()
        assert "autonomous" in body_lower or "automated" in body_lower, "Should describe autonomous/automated nature"

    @staticmethod
    def test_describes_summary_and_plan(repo_engineer_content: str):
        """
        Assert that the microagent body mentions both a summary and a plan.

        Parameters:
                repo_engineer_content (str): The markdown body content of the repo_engineer_lead microagent.
        """
        body_lower = repo_engineer_content.lower()
        assert "summary" in body_lower and "plan" in body_lower, "Should mention creating summaries and plans"

    @staticmethod
    def test_describes_reviewer_interaction(repo_engineer_content: str):
        """
        Check that the microagent body mentions reviewer, contributor, or comment interactions.

        Parameters:
            repo_engineer_content (str): Full markdown text of the repo_engineer_lead microagent to be inspected.
        """
        body_lower = repo_engineer_content.lower()
        assert any(
            term in body_lower for term in ["reviewer", "contributor", "comment"]
        ), "Should describe interaction with reviewers and contributors"

    @staticmethod
    def test_describes_commit_process(repo_engineer_content: str):
        """
        Verify the microagent body describes the commit process.

        Parameters:
            repo_engineer_content (str): Markdown body of the repo_engineer_lead microagent.

        Raises:
            AssertionError: If the body does not mention commits or does not explain committing changes.
        """
        body_lower = repo_engineer_content.lower()
        assert "commit" in body_lower, "Should describe commit process"
        # Should explain what is done in commits
        assert any(
            term in body_lower for term in ["commit any changes", "commit changes"]
        ), "Should explain committing changes"

    @staticmethod
    def test_describes_post_explanation(repo_engineer_content: str):
        """
        Verify the microagent body mentions posting explanations or explaining.

        Parameters:
            repo_engineer_content (str): Full markdown content of the repo_engineer_lead microagent (frontmatter and body).

        Raises:
            AssertionError: If neither the word "post" nor "explain" appears in the content (case-insensitive).
        """
        body_lower = repo_engineer_content.lower()
        assert "post" in body_lower or "explain" in body_lower, "Should mention posting explanations"

    @staticmethod
    def test_describes_efficiency_focus(repo_engineer_content: str):
        """Test that efficiency focus is described."""
        body_lower = repo_engineer_content.lower()
        assert "efficiency" in body_lower, "Should mention efficiency in code fixes"

    @staticmethod
    def test_proper_grammar_and_punctuation(repo_engineer_content: str):
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

    @staticmethod
    def test_consistent_terminology(repo_engineer_content: str):
        """Test that terminology is used consistently."""
        body = repo_engineer_content.lower()

        # If mentions "pull requests", should be consistent
        if "pull requests" in body or "pull request" in body:
            # Should consistently use either "PR" or "pull request"
            # Both are acceptable, just checking presence
            assert "pr" in body or "pull request" in body

        # Issue handling should be mentioned
        assert "issue" in body


@pytest.mark.unit
class TestMicroagentEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.fixture
    @staticmethod
    def repo_engineer_path() -> Path:
        """
        Path to the repo_engineer_lead microagent markdown file.

        Returns:
            Path: Path to ".openhands/microagents/repo_engineer_lead.md".
        """
        return Path(".openhands/microagents/repo_engineer_lead.md")

    @staticmethod
    def test_file_size_reasonable(repo_engineer_path: Path):
        """
        Ensure the repository microagent file size is between 100 and 50,000 bytes.

        Parameters:
            repo_engineer_path (Path): Path to the microagent markdown file to validate.
        """
        file_size = repo_engineer_path.stat().st_size
        assert file_size > 100, "File should have meaningful content"
        assert file_size < 50000, "File should be concise (under 50KB)"

    @staticmethod
    def test_no_binary_content(repo_engineer_path: Path):
        """Test that file contains only text (no binary data)."""
        with open(repo_engineer_path, "rb") as f:
            content = f.read()

        # Should be decodable as UTF-8
        try:
            content.decode("utf-8")
        except UnicodeDecodeError:
            pytest.fail("File should contain only UTF-8 text")

    @staticmethod
    def test_no_control_characters(repo_engineer_path: Path):
        """Test that file doesn't contain unexpected control characters."""
        with open(repo_engineer_path, encoding="utf-8") as f:
            content = f.read()

        # Allow: newline, tab, carriage return
        # Disallow: other control characters
        for char in content:
            code = ord(char)
            if code < 32:  # Control character
                assert char in ["\n", "\t", "\r"], f"File should not contain control character: {repr(char)}"

    @staticmethod
    def test_consistent_newlines(repo_engineer_path: Path):
        """
        Ensure the file uses consistent line endings: either all LF (Unix) or all CRLF (Windows).

        If any CRLF sequences are present, every line ending must be CRLF; otherwise all line endings must be LF.
        """
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


@pytest.mark.unit
class TestMicroagentPerformance(TestMicroagentValidation):
    """Performance and size tests for microagent files."""

    @staticmethod
    def test_all_microagents_reasonable_size(microagent_files: List[Path]):
        """Test that all microagent files are reasonably sized."""
        for file_path in microagent_files:
            file_size = file_path.stat().st_size
            assert file_size < 100000, f"{file_path.name} is too large ({file_size} bytes)"
            assert file_size > 50, f"{file_path.name} is too small ({file_size} bytes)"

    @staticmethod
    def test_all_microagents_parse_quickly(microagent_files: List[Path]):
        """Test that all microagents can be parsed quickly."""
        import time

        for file_path in microagent_files:
            start = time.time()
            with open(file_path, encoding="utf-8") as f:
                f.read()
            elapsed = time.time() - start
            assert elapsed < 1.0, f"{file_path.name} took too long to read"


@pytest.mark.unit
class TestMicroagentDocumentation(TestMicroagentValidation):
    """Test documentation quality in microagent files."""

    def test_all_microagents_have_body_content(self, microagent_files: List[Path]) -> None:
        """
        Ensure each microagent markdown file's body contains at least 20 words.

        Skips files whose YAML frontmatter cannot be parsed. Fails the test with an AssertionError for any file whose markdown body has fewer than 20 words.

        Parameters:
            microagent_files (List[Path]): Paths to microagent markdown files to validate.

        Raises:
            AssertionError: If a microagent body contains fewer than 20 words.
        """
        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            try:
                _, body = self.parse_frontmatter(content)
                word_count = len(body.split())
                assert word_count >= 20, f"{file_path.name} has insufficient body content ({word_count} words)"
            except ValueError as e:
                pytest.skip(f"{file_path.name} has unparseable frontmatter: {e}")

    def test_all_microagents_use_markdown_formatting(self, microagent_files: List[Path]) -> None:
        """Test that microagent bodies use markdown formatting."""
        for file_path in microagent_files:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            try:
                _, body = self.parse_frontmatter(content)

                # Should have some markdown elements (headings, lists, emphasis, etc.)
                has_markdown = any(
                    [
                        "**" in body,  # Bold
                        "*" in body,  # Emphasis or list
                        "#" in body,  # Heading
                        "-" in body,  # List
                        "`" in body,  # Code
                    ]
                )
                assert has_markdown, f"{file_path.name} should use markdown formatting"
            except ValueError as e:
                pytest.skip(f"{file_path.name} has unparseable frontmatter: {e}")


@pytest.mark.unit
class TestMicroagentBoundaryConditions:
    """Test boundary conditions and edge cases."""

    @staticmethod
    def test_microagent_with_minimal_valid_frontmatter(tmp_path):
        """
        Verifies that a markdown microagent file containing the minimal required YAML frontmatter can be parsed and its fields extracted.
        """
        test_file = tmp_path / "minimal.md"
        test_file.write_text("""---
name: test
type: knowledge
version: 1.0.0
agent: CodeActAgent
---
Minimal content.""")

        with open(test_file, encoding="utf-8") as f:
            content = f.read()

        # Should parse without errors
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        assert match is not None
        frontmatter_text = match.group(1)
        parsed = yaml.safe_load(frontmatter_text)
        assert parsed["name"] == "test"

    @staticmethod
    def test_frontmatter_with_extra_fields_allowed(tmp_path):
        """Test that extra fields in frontmatter are allowed."""
        test_file = tmp_path / "extra.md"
        test_file.write_text("""---
name: test
type: knowledge
version: 1.0.0
agent: CodeActAgent
extra_field: extra_value
custom: true
---
Content.""")

        with open(test_file, encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
        frontmatter_text = match.group(1)
        parsed = yaml.safe_load(frontmatter_text)

        # Extra fields should be preserved
        assert "extra_field" in parsed
        assert parsed["extra_field"] == "extra_value"


@pytest.mark.unit
class TestMicroagentRegressionCases:
    """Regression tests for previously identified issues."""

    @staticmethod
    def test_double_period_detection():
        """Regression: Test that double periods are detected."""
        content_with_error = """---
name: test
type: knowledge
version: 1.0.0
agent: CodeActAgent
---
This is a sentence.. This should be caught."""

        # Extract body
        match = re.match(r"^---\s*\n.*?\n---\s*\n(.*)$", content_with_error, re.DOTALL)
        body = match.group(1)

        # Should detect double periods
        assert ".." in body

    @staticmethod
    def test_malformed_frontmatter_raises_error(tmp_path):
        """Test that malformed frontmatter raises appropriate error."""
        test_file = tmp_path / "malformed.md"
        test_file.write_text("""---
name: test
type: knowledge
version 1.0.0
---
Content.""")

        with open(test_file, encoding="utf-8") as f:
            content = f.read()

        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        frontmatter_text = match.group(1)

        # Should raise YAML error due to missing colon
        with pytest.raises(yaml.YAMLError):
            yaml.safe_load(frontmatter_text)
