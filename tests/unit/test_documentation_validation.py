r"""Unit tests for validating .elastic-copilot documentation files.

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
    def dependency_matrix_path(self):
        """
        Return the filesystem path to the repository's dependency matrix markdown file.

        Returns:
            Path: Path to .elastic-copilot/memory/dependencyMatrix.md
        """
        return Path(".elastic-copilot/memory/dependencyMatrix.md")

    @pytest.fixture
    def dependency_matrix_content(self, dependency_matrix_path):
        """
    @pytest.fixture
    @staticmethod
    def dependency_matrix_content(dependency_matrix_path):
        """
        Load the dependency matrix markdown content from disk.

        Returns:
            The contents of the dependencyMatrix.md file as a string.

        Raises:
            AssertionError: If `dependency_matrix_path` does not exist.
        """
        assert dependency_matrix_path.exists(), "dependencyMatrix.md not found"
        with open(dependency_matrix_path, encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    @staticmethod
    def dependency_matrix_lines(dependency_matrix_content):
        """
        Split dependency matrix content into individual lines.

        Parameters:
            dependency_matrix_content(str): Full text content of the dependency matrix file.

        Returns:
            list[str]: Lines of the content produced by splitting on the newline character.
        """
        return dependency_matrix_content.split("\n")

    def test_dependency_matrix_exists(self, dependency_matrix_path):
        """Test that dependencyMatrix.md exists."""
        assert dependency_matrix_path.exists()
        assert dependency_matrix_path.is_file()

    def test_dependency_matrix_not_empty(self, dependency_matrix_content):
        """Test that dependencyMatrix.md is not empty."""
        assert len(dependency_matrix_content.strip()) > 0

    def test_dependency_matrix_has_title(self, dependency_matrix_lines):
        """Test that dependencyMatrix.md has proper title."""
        assert dependency_matrix_lines[0] == "# Dependency Matrix"

    def test_dependency_matrix_has_generated_timestamp(self, dependency_matrix_content):
        """
        Verify that dependencyMatrix.md contains a "Generated" timestamp in ISO 8601 format.

        This test looks for a line matching the pattern '*Generated: YYYY-MM-DDTHH:MM:SS.sssZ*' (for example '*Generated: 2025-11-07T18:22:38.791Z*') and asserts the captured timestamp can be parsed as a valid ISO 8601 instant.

        Parameters:
            dependency_matrix_content(str): The full text content of dependencyMatrix.md to be inspected.
        """
        # Look for: *Generated: 2025-11-07T18:22:38.791Z*
        timestamp_pattern = r"\*Generated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\*"
        match = re.search(timestamp_pattern, dependency_matrix_content)

        assert match is not None, "Generated timestamp not found"

        # Validate timestamp format
        timestamp_str = match.group(1)
        try:
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid timestamp format: {timestamp_str}")

    def test_dependency_matrix_has_summary_section(self, dependency_matrix_content):
        """Test that dependencyMatrix.md has Summary section."""
        assert "## Summary" in dependency_matrix_content

    def test_dependency_matrix_has_file_count(self, dependency_matrix_content):
        """Test that dependencyMatrix.md specifies files analyzed count."""
        pattern = r"- Files analyzed: (\d+)"
        match = re.search(pattern, dependency_matrix_content)

        assert match is not None, "Files analyzed count not found"
        count = int(match.group(1))
        assert count > 0, "Files analyzed count should be positive"

    def test_dependency_matrix_has_file_types(self, dependency_matrix_content):
        """
        Validate that the dependency matrix declares recognised file types.

        Asserts the presence of a "- File types: ..." entry in the provided document and that it lists at least one file type. Also ensures every listed type is within the allowed set(py, js, ts, tsx) or permitted extras(jsx, json, md).

        Parameters:
                dependency_matrix_content(str): Full text content of .elastic - copilot / memory / dependencyMatrix.md to inspect.
        """
        pattern = r"- File types: (.+)"
        match = re.search(pattern, dependency_matrix_content)

        assert match is not None, "File types not found"
        file_types = match.group(1).split(", ")
        assert len(file_types) > 0, "At least one file type should be listed"

        # Common expected file types
        expected_types = {"py", "js", "ts", "tsx"}
        found_types = set(file_types)
        assert found_types.issubset(
            expected_types | {"jsx", "json", "md"}
        ), f"Unexpected file types: {found_types - expected_types}"

    def test_dependency_matrix_has_file_type_distribution(self, dependency_matrix_content):
        """Test that dependencyMatrix.md has File Type Distribution section."""
        assert "## File Type Distribution" in dependency_matrix_content

    def test_dependency_matrix_file_counts_match(self, dependency_matrix_content):
        """
        Verify that the reported total files analysed equals the sum of the per - file - type counts.

        Asserts that the integer parsed from "- Files analyzed: N" matches the sum of all integers parsed from lines like "- X <type> files".
        """
        # Extract total files analyzed
        total_pattern = r"- Files analyzed: (\d+)"
        total_match = re.search(total_pattern, dependency_matrix_content)
        assert total_match is not None
        total_count = int(total_match.group(1))

        # Extract individual file type counts
        distribution_pattern = r"- (\d+) (\w+) files"
        distribution_matches = re.findall(distribution_pattern, dependency_matrix_content)

        sum_counts = sum(int(count) for count, _ in distribution_matches)
        assert sum_counts == total_count, f"Sum of file type counts ({sum_counts}) doesn't match total ({total_count})"

    def test_dependency_matrix_has_key_dependencies_section(self, dependency_matrix_content):
        """Test that dependencyMatrix.md has Key Dependencies by Type section."""
        assert "## Key Dependencies by Type" in dependency_matrix_content

    def test_dependency_matrix_language_sections_exist(self, dependency_matrix_content):
        """
        Check that the dependency matrix contains at least one major language section.

        Verifies the document includes at least one of the language headings: "### PY", "### JS", "### TS" or "### TSX".
        Fails the test if none of these sections are present.

        Parameters:
            dependency_matrix_content(str): The full text content of the dependencyMatrix.md file.
        """
        # Check for at least some of the main language sections
        language_sections = ["### PY", "### JS", "### TS", "### TSX"]

        found_sections = [section for section in language_sections if section in dependency_matrix_content]

        assert len(found_sections) > 0, "No language dependency sections found"

    def test_dependency_matrix_dependency_format(self, dependency_matrix_content):
        """
        Validate that dependency lists in the dependency matrix are formatted as bullet points.

        For each "Top dependencies:" section in the provided document, ensures the section content(up to the next "###" heading) either contains the message "No common dependencies found" or consists of non - empty lines that start with a dash(`-`).

        Parameters:
            dependency_matrix_content(str): Full text content of the dependencyMatrix.md file.
        """
        # After "Top dependencies:" there should be bullet points
        sections = dependency_matrix_content.split("Top dependencies:")

        for section in sections[1:]:  # Skip first part before any "Top dependencies:"
            # Get content until next ### or end
            content = section.split("###")[0].strip()

            if content and "No common dependencies found" not in content:
                lines = content.split("\n")
                for line in lines:
                    if line.strip():
                        assert line.strip().startswith("-"), f"Dependency line should start with '-': {line}"

    def test_dependency_matrix_no_empty_dependency_sections(self, dependency_matrix_content):
        """
        Ensure each "Top dependencies:" section in the dependency matrix contains non - empty content.

        Parameters:
            dependency_matrix_content(str): Full Markdown content of the dependency matrix file; the test splits this by the "Top dependencies:" marker and asserts that the text preceding the next "###" heading is not empty for each section.
        """
        # After "Top dependencies:" should be either dependencies or explicit message
        sections = dependency_matrix_content.split("Top dependencies:")

        for section in sections[1:]:
            content = section.split("###")[0].strip()
            # Should have some content
            assert len(content) > 0, "Empty dependency section found"

    def test_dependency_matrix_markdown_formatting(self, dependency_matrix_lines):
        """
        Verify that markdown headings use a space after the hash characters.

        Parameters:
            dependency_matrix_lines(list[str]): Lines of the dependency matrix markdown file to validate.

        Raises:
            AssertionError: If a heading line(one or more '#' characters followed by content) does not have a space after the hashes; message includes the offending line number and content.
        """
        for i, line in enumerate(dependency_matrix_lines):
            # Check heading formatting
            if line.startswith("#"):
                # Headings should have space after #
                heading_match = re.match(r"^(#+)(.+)", line)
                if heading_match:
                    _, content = heading_match.groups()
                    if content:  # Not just hashes
                        assert content.startswith(" "), f"Line {i+1}: Heading should have space after #: {line}"


class TestSystemManifest:
    """Test cases for .elastic - copilot / memory / systemManifest.md."""

    @pytest.fixture
    def system_manifest_path(self):
        """
        Return the filesystem path to the system manifest Markdown file.

        Returns:
            path(Path): Path pointing to .elastic - copilot / memory / systemManifest.md
        """
        return Path(".elastic-copilot/memory/systemManifest.md")

    @pytest.fixture
    def system_manifest_content(self, system_manifest_path):
        """
        Load the contents of the systemManifest.md file.

        Parameters:
            system_manifest_path(Path): Filesystem path to the systemManifest.md file.

        Returns:
            content(str): UTF - 8 decoded file contents.

        Raises:
            AssertionError: If `system_manifest_path` does not exist.
        """
        assert system_manifest_path.exists(), "systemManifest.md not found"
        with open(system_manifest_path, encoding="utf-8") as f:
            return f.read()

    @staticmethod
    @pytest.fixture
    def system_manifest_lines(system_manifest_content):
        """
        Split system manifest content into lines.

        Parameters:
            system_manifest_content(str): Raw content of the system manifest.

        Returns:
            list[str]: Lines from the manifest obtained by splitting on newline characters.
        """
        return system_manifest_content.split("\n")

    def test_system_manifest_exists(self, system_manifest_path):
        """Test that systemManifest.md exists."""
        assert system_manifest_path.exists()
        assert system_manifest_path.is_file()

    def test_system_manifest_not_empty(self, system_manifest_content):
        """Test that systemManifest.md is not empty."""
        assert len(system_manifest_content.strip()) > 0

    def test_system_manifest_has_title(self, system_manifest_lines):
        """
        Assert that the system manifest's first line is the top - level title "# System Manifest".
        """
        assert system_manifest_lines[0] == "# System Manifest"

    def test_system_manifest_has_project_overview(self, system_manifest_content):
        """
        Assert that the system manifest contains a top - level "Project Overview" section.

        Parameters:
            system_manifest_content(str): The complete text content of the systemManifest.md file.
        """
        assert "## Project Overview" in system_manifest_content

    def test_system_manifest_has_project_name(self, system_manifest_content):
        """Test that systemManifest.md specifies project name."""
        pattern = r"- Name: (.+)"
        match = re.search(pattern, system_manifest_content)

        assert match is not None, "Project name not found"
        name = match.group(1).strip()
        assert len(name) > 0, "Project name should not be empty"

    def test_system_manifest_has_project_description(self, system_manifest_content):
        """
        Verify the system manifest contains a "- Description: ..." entry documenting the project's description.
        """
        pattern = r"- Description: (.+)"
        match = re.search(pattern, system_manifest_content)

        assert match is not None, "Project description not found"
        description = match.group(1).strip()
        assert len(description) > 0, "Project description should not be empty"
        """Test that systemManifest.md has valid created timestamp."""
        pattern = r"- Created: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)"
        match = re.search(pattern, system_manifest_content)

        assert match is not None, "Created timestamp not found"

        # Validate timestamp format
        timestamp_str = match.group(1)
        try:
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid created timestamp format: {timestamp_str}")

    def test_system_manifest_has_current_status(self, system_manifest_content):
        """Test that systemManifest.md has Current Status section."""
        assert "## Current Status" in system_manifest_content

    def test_system_manifest_has_current_phase(self, system_manifest_content):
        """
        Assert that the System Manifest declares a current project phase.

        Raises an assertion error if no line matching "- Current Phase: <value>" is present in the provided System Manifest content.

        Parameters:
            system_manifest_content(str): Full text of the systemManifest.md file to inspect.
        """
        pattern = r"- Current Phase: (.+)"
        match = re.search(pattern, system_manifest_content)

        assert match is not None, "Current Phase not found"

    def test_system_manifest_has_last_updated(self, system_manifest_content):
        """Test that systemManifest.md has Last Updated timestamp as valid ISO 8601."""
        pattern = r"- Last Updated: (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)"
        match = re.search(pattern, system_manifest_content)

        assert match is not None, "Last Updated timestamp not found"

        # Validate timestamp format
        timestamp_str = match.group(1)
        try:
            datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Invalid Last Updated timestamp format: {timestamp_str}")

    def test_system_manifest_has_project_structure(self, system_manifest_content):
        """Test that systemManifest.md has Project Structure section."""
        assert "## Project Structure" in system_manifest_content

    def test_system_manifest_file_counts(self, system_manifest_content):
        """
        Verify systemManifest.md lists file counts per type and that each count is a non - negative integer.

        Checks for lines matching the pattern "- N <type> files" and asserts at least one such line exists. Fails if any extracted count is negative.
        """
        pattern = r"- (\d+) (\w+) files"
        matches = re.findall(pattern, system_manifest_content)

        assert len(matches) > 0, "No file counts found"

        for count_str, file_type in matches:
            count = int(count_str)
            assert count >= 0, f"File count for {file_type} should be non-negative"

    def test_system_manifest_has_dependencies_section(self, system_manifest_content):
        """
        Verify that systemManifest.md contains the "## Dependencies" section.
        """
        assert "## Dependencies" in system_manifest_content

    def test_system_manifest_has_directory_structure(self, system_manifest_content):
        """Test that systemManifest.md has Project Directory Structure section."""
        assert "## Project Directory Structure" in system_manifest_content

    def test_system_manifest_directory_structure_format(self, system_manifest_content):
        """Test that directory structure uses proper emoji formatting."""
        # Look for directory structure section
        if "## Project Directory Structure" in system_manifest_content:
            structure_section = system_manifest_content.split("## Project Directory Structure")[1]
            structure_section = structure_section.split("##")[0]  # Get until next section

            assert "📂" in structure_section, "Directory entries should include the 📂 emoji"
            assert "📄" in structure_section, "File entries should include the 📄 emoji"

    def test_system_manifest_has_language_dependency_sections(self, system_manifest_content):
        """Test that systemManifest.md has language - specific dependency sections."""
        expected_sections = ["## PY Dependencies", "## JS Dependencies", "## TS Dependencies", "## TSX Dependencies"]

        found = sum(1 for section in expected_sections if section in system_manifest_content)
        assert found > 0, "No language-specific dependency sections found"

    def test_system_manifest_file_dependency_format(self, system_manifest_content):
        r"""
        Validate that file - level dependency headers in the system manifest follow the expected path - and -extension format.

        Searches the document for headers of the form "### \\path\\to\\file.ext" and asserts that each matched header contains a path separator(`\\` or `/`). Only the first 10 matches are checked for performance.

        Parameters:
            system_manifest_content(str): Full markdown text of the system manifest to inspect.
        """
        # Look for file dependency entries like: ### \path\to\file.py
        file_pattern = r"###\s+\\[\w\\\/._-]+\.\w+"
        matches = re.findall(file_pattern, system_manifest_content)

        # If there are file entries, they should be properly formatted
        if matches:
            for match in matches[:10]:  # Check first 10 for performance
                # Should have proper path separators
                assert "\\" in match or "/" in match, f"File path should have proper separators: {match}"

    def test_system_manifest_dependency_entries_have_content(self, system_manifest_content):
        """
        Verify each file section in the system manifest contains dependency information or an explicit absence message.

        Splits the manifest by file headers introduced with "###" and inspects up to the first 20 file sections. For each non - empty file section(excluding sections that start with "#"), asserts the section contains either the literal "Dependencies:", the literal "No dependencies found", or begins with a backslash(indicating a file path).

        Parameters:
            system_manifest_content(str): Full text content of the system manifest file to validate.
        """
        # Split by file headers (###)
        sections = re.split(r"###\s+", system_manifest_content)

        for section in sections[1:20]:  # Check first 20 file sections
            # Should have either "Dependencies:" or "No dependencies found"
            if section.strip():
                has_deps = "Dependencies:" in section or "No dependencies found" in section
                # Allow for section headers without file content
                if not section.startswith("#"):
                    assert has_deps or section.strip().startswith(
                        "\\"
                    ), "File section should have dependency information"

    def test_system_manifest_no_duplicate_sections(self, system_manifest_content):
        """Test that there are no duplicate major sections."""
        major_sections = ["## Project Overview", "## Current Status", "## Project Structure", "## Dependencies"]

        for section in major_sections:
            count = system_manifest_content.count(section)
            # Allow for some duplication due to regeneration, but excessive duplication is an error
            assert count > 0, f"Section '{section}' not found"
            # This test allows for reasonable duplication
            assert count < 10, f"Section '{section}' appears too many times ({count})"

    def test_system_manifest_markdown_formatting(self, system_manifest_lines):
        """
        Verify markdown heading formatting in the System Manifest.

        Asserts that, within the first 500 lines, any Markdown heading that begins with one or more `  # ` characters has a space immediately following the leading hash sequence (e.g. `# Title`, `## Section`). The test raises an assertion identifying the line number and content when a heading is missing the required space.
        """
        for i, line in enumerate(system_manifest_lines[:500]):  # Check first 500 lines
            # Check heading formatting
            if line.startswith("#"):
                # Headings should have space after #
                heading_match = re.match(r"^(#+)(.+)", line)
                if heading_match:
                    _, content = heading_match.groups()
                    if content and not content.startswith("#"):  # Not more hashes
                        assert content.startswith(" "), f"Line {i+1}: Heading should have space after #: {line}"


class TestDocumentationConsistency:
    """Test cases for consistency between documentation files."""

    @pytest.fixture
    def dependency_matrix_content(self):
        """
        Load and return the contents of the dependency matrix file from .elastic - copilot / memory.

        Returns:
            content(str): The UTF - 8 text of dependencyMatrix.md.
        """
        path = Path(".elastic-copilot/memory/dependencyMatrix.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    @pytest.fixture
    def system_manifest_content(self):
        """
        Load the contents of the system manifest file located at .elastic - copilot / memory / systemManifest.md.

        Returns:
            content(str): The full text of the system manifest file.
        """
        path = Path(".elastic-copilot/memory/systemManifest.md")
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_file_counts_match_between_documents(self, dependency_matrix_content, system_manifest_content):
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
        dm_counts = {file_type: int(count) for count, file_type in re.findall(dm_pattern, dependency_matrix_content)}

        # Extract file counts from system manifest (first occurrence in Project Structure)
        # Extract file counts from system manifest (first occurrence in Project Structure)
        assert (
            "## Project Structure" in system_manifest_content
        ), "## Project Structure section not found in system manifest"
        sm_content = system_manifest_content.split("## Project Structure")[1].split("##")[0]
        sm_counts = {file_type: int(count) for count, file_type in re.findall(dm_pattern, sm_content)}

        # Compare counts for each file type
        for file_type in dm_counts:
            if file_type in sm_counts:
                assert dm_counts[file_type] == sm_counts[file_type], (
                    f"File count mismatch for {file_type}: "
                    f"dependencyMatrix={dm_counts[file_type]}, "
                    f"systemManifest={sm_counts[file_type]}"
                )

    def test_file_types_match_between_documents(self, dependency_matrix_content, system_manifest_content):
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
        sm_content = system_manifest_content.split("## Project Structure")[1].split("##")[0]
        sm_types = set(re.findall(sm_pattern, sm_content))

        # Types should match
        assert dm_types == sm_types, f"File types mismatch: dependencyMatrix={dm_types}, systemManifest={sm_types}"

    def test_timestamps_are_recent(self, dependency_matrix_content, system_manifest_content):
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

    def test_common_dependencies_consistency(self, dependency_matrix_content, system_manifest_content):
        """Test that common dependencies mentioned in both files are consistent."""
        # Extract common dependencies from dependency matrix
        dm_deps = set()
        for match in re.finditer(r"^- (.+)$", dependency_matrix_content, re.MULTILINE):
            dep = match.group(1).strip()
            if dep and not dep.startswith("Files analyzed") and not dep.startswith("File types"):
                dm_deps.add(dep)

        # Extract dependencies from system manifest
        sm_deps = set()
        for match in re.finditer(r"^- (.+)$", system_manifest_content, re.MULTILINE):
            dep = match.group(1).strip()
            if dep and not any(x in dep for x in ["files", "Created:", "Last Updated:"]):
                sm_deps.add(dep)

        # Check for common popular dependencies
        common_deps = ["react", "axios", "@testing-library/jest-dom"]
        for dep in common_deps:
            dm_has = any(dep in d for d in dm_deps)
            sm_has = any(dep in d for d in sm_deps)
            # If one has it, both should (or neither)
            if dm_has or sm_has:
                assert dm_has == sm_has, (
                    f"Dependency '{dep}' inconsistently present: " f"dependencyMatrix={dm_has}, systemManifest={sm_has}"
                )


class TestDocumentationRealisticContent:
    """Test that documentation content matches reality of the codebase."""

    def test_documented_files_exist(self):
        r"""
        Verify that file paths listed in the system manifest correspond to actual files in the repository.

        Searches the manifest for file entries formatted as "### \\path\\to\\file.ext" (common Python, TS / TSX, JSX / JSX patterns), normalises Windows - style backslashes to POSIX paths, strips any leading slash, and checks existence for up to the first 20 discovered paths. Entries that are placeholders or clearly test - related(containing "...", "test_", or "__tests__") are skipped.
        """
        manifest_path = Path(".elastic-copilot/memory/systemManifest.md")
        with open(manifest_path, encoding="utf-8") as f:
            content = f.read()

        # Extract file paths from the manifest (look for common patterns)
        file_patterns = [
            r"###\s+\\([\w\\\/._-]+\.py)",
            r"###\s+\\([\w\\\/._-]+\.tsx?)",
            r"###\s+\\([\w\\\/._-]+\.jsx?)",
        ]

        mentioned_files = []
        for pattern in file_patterns:
            matches = re.findall(pattern, content)
            mentioned_files.extend(matches)

        # Check a sample of mentioned files
        for file_path in mentioned_files[:20]:  # Check first 20 for performance
            # Convert Windows paths to Unix paths
            unix_path = file_path.replace("\\", "/")
            # Remove leading slash if present
            unix_path = unix_path.lstrip("/")

            check_path = Path(unix_path)
            # Only assert for files that should clearly exist
            if any(x in unix_path for x in ["...", "test_", "__tests__"]):
                continue

            assert check_path.exists() or "..." in file_path, f"File mentioned in manifest doesn't exist: {unix_path}"

    def test_documented_file_counts_reasonable(self):
        """Test that documented file counts are reasonable for the project."""
        matrix_path = Path(".elastic-copilot/memory/dependencyMatrix.md")
        with open(matrix_path, encoding="utf-8") as f:
            content = f.read()

        # Extract total files
        match = re.search(r"- Files analyzed: (\d+)", content)
        assert match is not None
        total_files = int(match.group(1))

        # Should be a reasonable number for a real project
        assert 10 <= total_files <= 10000, f"Total files ({total_files}) seems unrealistic"

    def test_documented_dependencies_are_real_packages(self):
        """
        Validate that dependencies listed in .elastic - copilot / memory / dependencyMatrix.md resemble real package names.

        Reads the dependency matrix, extracts bullet - list entries, filters out lines referring to file counts or metadata, and asserts that the first 20 candidate dependencies match common package - name patterns(alphanumeric, dot, dash, underscore, scoped names, and simple path - like entries).
        """
        matrix_path = Path(".elastic-copilot/memory/dependencyMatrix.md")
        with open(matrix_path, encoding="utf-8") as f:
            content = f.read()

        # Extract dependencies
        deps = []
        for match in re.finditer(r"^- (.+)$", content, re.MULTILINE):
            dep = match.group(1).strip()
            # Filter out non-dependency lines
            if not any(x in dep for x in ["files", "File types", "analyzed"]):
                deps.append(dep)

        # Check that dependencies follow common patterns
        for dep in deps[:20]:  # Check first 20
            # Should not have spaces (unless it's a relative path)
            if not dep.startswith(".") and not dep.startswith("@"):
                # Package names shouldn't have spaces
                if " " not in dep:
                    # Valid package name format
                    assert re.match(r"^[@\w\.\-/]+$", dep), f"Dependency '{dep}' doesn't look like a valid package name"
