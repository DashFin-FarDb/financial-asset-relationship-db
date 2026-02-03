"""Unit tests for validating .elastic-copilot documentation files.

This module tests markdown documentation files to ensure:
- Valid markdown structure and formatting
- Required sections are present
- Data consistency (file counts, timestamps, etc.)
- Dependency listings are properly formatted
- Cross-references and internal consistency
- Content accuracy relative to actual codebase
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest


class TestDependencyMatrix:
    """Test cases for .elastic-copilot/memory/dependencyMatrix.md."""

    @pytest.fixture
    def dependency_matrix_path(self) -> Path:
        """
        Return the filesystem path to the repository's dependency matrix markdown file.

        Returns:
            Path: Path to .elastic-copilot/memory/dependencyMatrix.md
        """
        return Path(".elastic-copilot/memory/dependencyMatrix.md")

    @staticmethod
    @pytest.fixture
    def dependency_matrix_content(dependency_matrix_path: Path) -> str:
        """
        Load the dependency matrix markdown content from disk.

        Returns:
            str: Contents of the dependencyMatrix.md file.

        Raises:
            AssertionError: If dependencyMatrix.md does not exist.
        """
        assert dependency_matrix_path.exists(), "dependencyMatrix.md not found"
        with dependency_matrix_path.open(encoding="utf-8") as file:
            return file.read()

    @staticmethod
    @pytest.fixture
    def dependency_matrix_lines(dependency_matrix_content: str) -> list[str]:
        """
        Split dependency matrix content into individual lines.

        Returns:
            list[str]: Lines of the markdown file.
        """
        return dependency_matrix_content.split("\n")

    def test_dependency_matrix_exists(self, dependency_matrix_path: Path) -> None:
        """Test that dependencyMatrix.md exists."""
        assert dependency_matrix_path.exists()
        assert dependency_matrix_path.is_file()

    def test_dependency_matrix_not_empty(self, dependency_matrix_content: str) -> None:
        """Test that dependencyMatrix.md is not empty."""
        assert dependency_matrix_content.strip()

    def test_dependency_matrix_has_title(
        self, dependency_matrix_lines: list[str]
    ) -> None:
        """Test that dependencyMatrix.md has proper title."""
        assert dependency_matrix_lines[0] == "# Dependency Matrix"

    def test_dependency_matrix_has_generated_timestamp(
        self, dependency_matrix_content: str
    ) -> None:
        """
        Verify that dependencyMatrix.md contains a valid ISO 8601 generated timestamp.
        """
        pattern = r"\*Generated: " r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\*"
        match = re.search(pattern, dependency_matrix_content)
        assert match is not None, "Generated timestamp not found"

        timestamp = match.group(1)
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AssertionError(f"Invalid timestamp format: {timestamp}") from exc

    def test_dependency_matrix_has_summary_section(
        self, dependency_matrix_content: str
    ) -> None:
        """Test that dependencyMatrix.md has Summary section."""
        assert "## Summary" in dependency_matrix_content

    def test_dependency_matrix_has_file_count(
        self, dependency_matrix_content: str
    ) -> None:
        """Test that dependencyMatrix.md specifies files analyzed count."""
        match = re.search(r"- Files analyzed: (\d+)", dependency_matrix_content)
        assert match is not None, "Files analyzed count not found"

        count = int(match.group(1))
        assert count > 0, "Files analyzed count should be positive"

    def test_dependency_matrix_has_file_types(
        self, dependency_matrix_content: str
    ) -> None:
        """Validate that declared file types are recognised."""
        match = re.search(r"- File types: (.+)", dependency_matrix_content)
        assert match is not None, "File types not found"

        file_types = set(match.group(1).split(", "))
        assert file_types, "At least one file type should be listed"

        allowed_types = {"py", "js", "ts", "tsx", "jsx", "json", "md"}
        assert file_types.issubset(allowed_types), (
            f"Unexpected file types: {file_types - allowed_types}"
        )

    def test_dependency_matrix_has_file_type_distribution(
        self, dependency_matrix_content: str
    ) -> None:
        """Test that File Type Distribution section exists."""
        assert "## File Type Distribution" in dependency_matrix_content

    def test_dependency_matrix_file_counts_match(
        self, dependency_matrix_content: str
    ) -> None:
        """Verify total file count equals sum of per-type counts."""
        total_match = re.search(r"- Files analyzed: (\d+)", dependency_matrix_content)
        assert total_match is not None
        total_count = int(total_match.group(1))

        distribution = re.findall(r"- (\d+) (\w+) files", dependency_matrix_content)
        summed = sum(int(count) for count, _ in distribution)

        assert summed == total_count, (
            f"Sum of file type counts ({summed}) does not match total ({total_count})"
        )

    def test_dependency_matrix_has_key_dependencies_section(
        self, dependency_matrix_content: str
    ) -> None:
        """Test that Key Dependencies by Type section exists."""
        assert "## Key Dependencies by Type" in dependency_matrix_content

    def test_dependency_matrix_language_sections_exist(
        self, dependency_matrix_content: str
    ) -> None:
        """Ensure at least one language dependency section exists."""
        sections = {"### PY", "### JS", "### TS", "### TSX"}
        assert any(section in dependency_matrix_content for section in sections)

    def test_dependency_matrix_dependency_format(
        self, dependency_matrix_content: str
    ) -> None:
        """Validate dependency lists are properly bullet-formatted."""
        sections = dependency_matrix_content.split("Top dependencies:")

        for section in sections[1:]:
            content = section.split("###")[0].strip()
            if content and "No common dependencies found" not in content:
                for line in content.split("\n"):
                    if line.strip():
                        assert line.strip().startswith("-"), (
                            f"Dependency line should start with '-': {line}"
                        )

    def test_dependency_matrix_no_empty_dependency_sections(
        self, dependency_matrix_content: str
    ) -> None:
        """Ensure no empty dependency sections exist."""
        sections = dependency_matrix_content.split("Top dependencies:")

        for section in sections[1:]:
            content = section.split("###")[0].strip()
            assert content, "Empty dependency section found"

    def test_dependency_matrix_markdown_formatting(
        self, dependency_matrix_lines: list[str]
    ) -> None:
        """Verify markdown headings include a space after '#'."""
        for index, line in enumerate(dependency_matrix_lines, start=1):
            if line.startswith("#"):
                match = re.match(r"^(#+)(.*)", line)
                if match:
                    _, text = match.groups()
                    if text:
                        assert text.startswith(" "), (
                            f"Line {index}: Heading should have space after #: {line}"
                        )


class TestSystemManifest:
    """Test cases for .elastic-copilot/memory/systemManifest.md."""

    @pytest.fixture
    def system_manifest_path(self) -> Path:
        """
        Return the filesystem path to the system manifest Markdown file.

        Returns:
            Path: Path pointing to .elastic-copilot/memory/systemManifest.md
        """
        return Path(".elastic-copilot/memory/systemManifest.md")

    @pytest.fixture
    def system_manifest_content(self, system_manifest_path: Path) -> str:
        """
        Load and return the contents of the system manifest file.

        Returns:
            str: UTF-8 decoded file contents.

        Raises:
            AssertionError: If system_manifest_path does not exist.
        """
        assert system_manifest_path.exists(), "systemManifest.md not found"
        with system_manifest_path.open(encoding="utf-8") as file_handle:
            return file_handle.read()

    @pytest.fixture
    def system_manifest_lines(self, system_manifest_content: str) -> list[str]:
        """
        Split system manifest content into lines.

        Returns:
            list[str]: Lines split on newline characters.
        """
        return system_manifest_content.split("\n")

    def test_system_manifest_exists(self, system_manifest_path: Path) -> None:
        """Test that systemManifest.md exists."""
        assert system_manifest_path.exists()
        assert system_manifest_path.is_file()

    def test_system_manifest_not_empty(self, system_manifest_content: str) -> None:
        """Test that systemManifest.md is not empty."""
        assert system_manifest_content.strip()

    def test_system_manifest_has_title(
        self, system_manifest_lines: list[str]
    ) -> None:
        """Assert that the first line is the System Manifest title."""
        assert system_manifest_lines[0] == "# System Manifest"

    def test_system_manifest_has_project_overview(
        self, system_manifest_content: str
    ) -> None:
        """Assert presence of Project Overview section."""
        assert "## Project Overview" in system_manifest_content

    def test_system_manifest_has_project_name(
        self, system_manifest_content: str
    ) -> None:
        """Test that project name is specified."""
        match = re.search(r"- Name: (.+)", system_manifest_content)
        assert match is not None, "Project name not found"
        assert match.group(1).strip(), "Project name should not be empty"

    def test_system_manifest_has_project_description(
        self, system_manifest_content: str
    ) -> None:
        """Verify project description entry exists and is non-empty."""
        match = re.search(r"- Description: (.+)", system_manifest_content)
        assert match is not None, "Project description not found"
        assert match.group(1).strip(), "Project description should not be empty"

    def test_system_manifest_has_created_timestamp(
        self, system_manifest_content: str
    ) -> None:
        """Test that Created timestamp exists and is valid ISO 8601."""
        match = re.search(
            r"- Created: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)",
            system_manifest_content,
        )
        assert match is not None, "Created timestamp not found"

        timestamp_str = match.group(1)
        datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

    def test_system_manifest_has_current_phase(
        self, system_manifest_content: str
    ) -> None:
        """Test that Current Phase section exists."""
        assert "## Current Phase" in system_manifest_content

    def test_system_manifest_has_last_updated(
        self, system_manifest_content: str
    ) -> None:
        """Test that Last Updated timestamp is valid ISO 8601."""
        match = re.search(
            r"- Last Updated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)",
            system_manifest_content,
        )
        assert match is not None, "Last Updated timestamp not found"

        timestamp_str = match.group(1)
        datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

    def test_system_manifest_has_project_structure(
        self, system_manifest_content: str
    ) -> None:
        """Test that Project Structure section exists."""
        assert "## Project Structure" in system_manifest_content

    def test_system_manifest_file_counts(
        self, system_manifest_content: str
    ) -> None:
        """Verify file counts are present and non-negative."""
        matches = re.findall(r"- (\d+) (\w+) files", system_manifest_content)
        assert matches, "No file counts found"

        for count_str, file_type in matches:
            assert int(count_str) >= 0, (
                f"File count for {file_type} should be non-negative"
            )

    def test_system_manifest_has_dependencies_section(
        self, system_manifest_content: str
    ) -> None:
        """Verify Dependencies section exists."""
        assert "## Dependencies" in system_manifest_content

    def test_system_manifest_has_directory_structure(
        self, system_manifest_content: str
    ) -> None:
        """Verify Project Directory Structure section exists."""
        assert "## Project Directory Structure" in system_manifest_content

    def test_system_manifest_directory_structure_format(
        self, system_manifest_content: str
    ) -> None:
        """Ensure directory structure uses emoji formatting."""
        if "## Project Directory Structure" not in system_manifest_content:
            pytest.skip("Directory structure section not present")

        section = system_manifest_content.split(
            "## Project Directory Structure", 1
        )[1].split("##", 1)[0]

        assert "📂" in section, "Directory entries should include 📂 emoji"
        assert "📄" in section, "File entries should include 📄 emoji"

    def test_system_manifest_has_language_dependency_sections(
        self, system_manifest_content: str
    ) -> None:
        """Ensure at least one language-specific dependency section exists."""
        expected = {
            "## PY Dependencies",
            "## JS Dependencies",
            "## TS Dependencies",
            "## TSX Dependencies",
        }
        assert any(section in system_manifest_content for section in expected)

    def test_system_manifest_markdown_formatting(
        self, system_manifest_lines: list[str]
    ) -> None:
        """Verify markdown headings include space after hash."""
        for index, line in enumerate(system_manifest_lines[:500], start=1):
            if line.startswith("#"):
                match = re.match(r"^(#+)(.*)", line)
                if match:
                    content = match.group(2)
                    assert content.startswith(" "), (
                        f"Line {index}: Heading should have space after #: {line}"
                    )


class TestDocumentationConsistency:
    """Test cases for consistency between documentation files."""

    @staticmethod
    @pytest.fixture
    def dependency_matrix_content():
        """
        Load and return the contents of the dependency matrix file from .elastic - copilot / memory.

        Returns:
            content(str): The UTF - 8 text of dependencyMatrix.md.
        """
        path = Path(".elastic-copilot/memory/dependencyMatrix.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    @pytest.fixture
    def system_manifest_content():
        """
        Load the contents of the system manifest file located at .elastic - copilot / memory / systemManifest.md.

        Returns:
            content(str): The full text of the system manifest file.
        """
        path = Path(".elastic-copilot/memory/systemManifest.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_file_counts_match_between_documents(
        self, dependency_matrix_content, system_manifest_content
    ):
        """
        Verify that per - type file counts are equal between dependencyMatrix.md and the System Manifest's Project Structure section.

        Parses patterns of the form "- N <type> files" from dependency_matrix_content and from the first "## Project Structure" section of system_manifest_content, then asserts that counts match for each file type present in both documents.

        Parameters:
                dependency_matrix_content(str): Full markdown content of dependencyMatrix.md.
                system_manifest_content(str): Full markdown content of systemManifest.md.

        Raises:
                AssertionError: If the "## Project Structure" section is missing or if any file - type counts differ between the two documents.
        """
        # Extract file counts from dependency matrix
        dm_pattern = r"- (\d+) (\w+) files"
        dm_counts = {
            file_type: int(count)
            for count, file_type in re.findall(dm_pattern, dependency_matrix_content)
        }

        # Extract file counts from system manifest (first occurrence in Project Structure)
        # Extract file counts from system manifest (first occurrence in Project Structure)
        assert "## Project Structure" in system_manifest_content, (
            "## Project Structure section not found in system manifest"
        )
        sm_content = system_manifest_content.split("## Project Structure")[1].split(
            "##"
        )[0]
        sm_counts = {
            file_type: int(count)
            for count, file_type in re.findall(dm_pattern, sm_content)
        }

        # Compare counts for each file type
        for file_type in dm_counts:
            if file_type in sm_counts:
                assert dm_counts[file_type] == sm_counts[file_type], (
                    f"File count mismatch for {file_type}: "
                    f"dependencyMatrix={dm_counts[file_type]}, "
                    f"systemManifest={sm_counts[file_type]}"
                )

    def test_file_types_match_between_documents(
        self, dependency_matrix_content, system_manifest_content
    ):
        """
        Verify that the set of file types listed in the dependency matrix matches the set reported in the system manifest.

        This test compares the "File types" entry from dependencyMatrix.md with the file type names extracted from the "Project Structure" section of systemManifest.md and fails if the two sets differ.
        """
        # Extract file types from dependency matrix
        dm_types_match = re.search(r"- File types: (.+)", dependency_matrix_content)
        assert dm_types_match is not None
        dm_types = set(dm_types_match.group(1).split(", "))

        # Extract file types from system manifest Project Structure
        sm_pattern = r"- \d+ (\w+) files"
        sm_content = system_manifest_content.split("## Project Structure")[1].split(
            "##"
        )[0]
        sm_types = set(re.findall(sm_pattern, sm_content))

        # Types should match
        assert dm_types == sm_types, (
            f"File types mismatch: dependencyMatrix={dm_types}, systemManifest={sm_types}"
        )

    def test_timestamps_are_recent(
        self, dependency_matrix_content, system_manifest_content
    ):
        """
        Ensure timestamps in dependencyMatrix.md and systemManifest.md are not older than one year.

        Checks the dependency matrix "Generated" timestamp and the system manifest "Last Updated" timestamp(expected as ISO 8601 with milliseconds and a trailing "Z"); if either timestamp is present and is more than one year old the test fails.
        """
        now = datetime.now(timezone.utc)
        one_year_ago = now - timedelta(days=365)

        # Check dependency matrix timestamp
        dm_pattern = r"\*Generated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\*"
        dm_match = re.search(dm_pattern, dependency_matrix_content)
        if dm_match:
            dm_time = datetime.fromisoformat(dm_match.group(1).replace("Z", "+00:00"))
            assert dm_time > one_year_ago, "dependencyMatrix timestamp is too old"

        # Check system manifest timestamp
        sm_pattern = r"- Last Updated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)"
        sm_match = re.search(sm_pattern, system_manifest_content)
        if sm_match:
            sm_time = datetime.fromisoformat(sm_match.group(1).replace("Z", "+00:00"))
            assert sm_time > one_year_ago, "systemManifest timestamp is too old"

    def test_common_dependencies_consistency(
        self, dependency_matrix_content, system_manifest_content
    ):
        """Test that common dependencies mentioned in both files are consistent."""
        # Extract common dependencies from dependency matrix
        dm_deps = set()
        for match in re.finditer(r"^- (.+)$", dependency_matrix_content, re.MULTILINE):
            dep = match.group(1).strip()
            if (
                dep
                and not dep.startswith("Files analyzed")
                and not dep.startswith("File types")
            ):
                dm_deps.add(dep)

        # Extract dependencies from system manifest
        sm_deps = set()
        for match in re.finditer(r"^- (.+)$", system_manifest_content, re.MULTILINE):
            dep = match.group(1).strip()
            if dep and not any(
                x in dep for x in ["files", "Created:", "Last Updated:"]
            ):
                sm_deps.add(dep)

        # Check for common popular dependencies
        common_deps = ["react", "axios", "@testing-library/jest-dom"]
        for dep in common_deps:
            dm_has = any(dep in d for d in dm_deps)
            sm_has = any(dep in d for d in sm_deps)
            # If one has it, both should (or neither)
            if dm_has or sm_has:
                assert dm_has == sm_has, (
                    f"Dependency '{dep}' inconsistently present: "
                    f"dependencyMatrix={dm_has}, systemManifest={sm_has}"
                )


class TestDocumentationRealisticContent:
    """Test that documentation content matches reality of the codebase."""
                        f"Dependency '{dep}' doesn't look like a valid package name"
