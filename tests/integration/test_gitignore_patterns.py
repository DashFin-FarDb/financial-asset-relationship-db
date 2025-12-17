"""
Comprehensive unit tests for .gitignore patterns.

Tests validate that the .gitignore file correctly excludes unwanted files
while allowing necessary test artifacts and database files.
"""

import pytest
import re
from pathlib import Path
from typing import List, Set


class TestGitignoreFileStructure:
    """Tests for .gitignore file structure and syntax."""
    
    @pytest.fixture
    def gitignore_path(self) -> Path:
        """
        Compute the path to the repository's .gitignore file.
        
        Returns:
            gitignore_path (Path): Path to the repository's .gitignore file.
        """
        return Path(__file__).parent.parent.parent / ".gitignore"
    
    @pytest.fixture
    def gitignore_content(self, gitignore_path: Path) -> str:
        """
        Read and return the contents of the .gitignore file at the given path.
        
        Parameters:
            gitignore_path (Path): Path to the .gitignore file to read.
        
        Returns:
            gitignore_content (str): The full contents of the file as a string.
        """
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    @pytest.fixture
    def gitignore_lines(self, gitignore_content: str) -> List[str]:
        """
        Extracts non-empty, non-comment lines from a .gitignore file content.
        
        Parameters:
            gitignore_content (str): The entire .gitignore file content.
        
        Returns:
            List[str]: Stripped lines that are neither empty nor start with '#' (comments).
        """
        return [
            line.strip()
            for line in gitignore_content.split('\n')
            if line.strip() and not line.strip().startswith('#')
        ]
    
    def test_gitignore_file_exists(self, gitignore_path: Path):
        """Test that .gitignore file exists in repository root."""
        assert gitignore_path.exists(), ".gitignore file should exist"
        assert gitignore_path.is_file(), ".gitignore should be a file"
    
    def test_gitignore_readable(self, gitignore_path: Path):
        """
        Ensure the repository's .gitignore file can be opened and contains content.
        
        Asserts that the file at the given path is readable with UTF-8 decoding and has length greater than zero.
        """
        with open(gitignore_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0, ".gitignore should not be empty"
    
    def test_no_invalid_pattern_syntax(self, gitignore_lines: List[str]):
        """
        Validate that each .gitignore pattern does not contain unescaped spaces or obvious syntax errors.
        
        Fails the test if any pattern line contains a space that is not inside a character class (`[...]`) and is not escaped with a backslash.
        
        Parameters:
            gitignore_lines (List[str]): Stripped, non-empty, non-comment lines from the repository's `.gitignore` file.
        """
        for line in gitignore_lines:
            # Patterns should not have spaces unless quoted or in character class
            if ' ' in line and '[' not in line and '\\' not in line:
            # Patterns should not have spaces unless quoted or in character classes
            # Valid patterns can have: spaces in character classes, quoted spaces, or escaped spaces
            if ' ' in line and not (
                '[' in line and ']' in line or  # Character class
                line.startswith('"') and line.endswith('"') or  # Quoted pattern
                '\\' in line  # Escaped characters
            ):
                pytest.fail(f"Pattern '{line}' contains unescaped space")
    
    def test_no_duplicate_patterns(self, gitignore_lines: List[str]):
        """
        Check that the repository's .gitignore contains no duplicate ignore patterns.
        
        If duplicate patterns are found the test fails with an assertion listing the duplicate entries.
        
        Parameters:
            gitignore_lines (List[str]): Sequence of .gitignore lines representing individual ignore patterns
                (typically stripped of comments and blank lines).
        """
        seen: Set[str] = set()
        duplicates = []
        
        for line in gitignore_lines:
            if line in seen:
                duplicates.append(line)
            seen.add(line)
        
        assert len(duplicates) == 0, \
            f"Found duplicate patterns: {duplicates}"


class TestPythonSpecificPatterns:
    """Tests for Python-related ignore patterns."""
    
    @pytest.fixture
    def gitignore_content(self) -> str:
        """
        Load the repository's .gitignore file content.
        
        Returns:
            content (str): The full text of the .gitignore file.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_ignores_pycache_directories(self, gitignore_content: str):
        """Test that __pycache__ directories are ignored."""
        assert '__pycache__' in gitignore_content, \
            "__pycache__ should be in .gitignore"
    
    def test_ignores_pyc_files(self, gitignore_content: str):
        """Test that .pyc files are ignored."""
        assert '*.pyc' in gitignore_content, \
            "*.pyc should be in .gitignore"
    
    def test_ignores_python_egg_info(self, gitignore_content: str):
        """Test that Python egg-info directories are ignored."""
        assert '.egg-info' in gitignore_content or '*.egg-info' in gitignore_content, \
            "egg-info should be in .gitignore"
    
    def test_ignores_virtual_environments(self, gitignore_content: str):
        """Test that virtual environment directories are ignored."""
        venv_patterns = ['venv/', '.venv/', 'env/', 'ENV/']
        found = any(pattern in gitignore_content for pattern in venv_patterns)
        assert found, "Virtual environment directories should be ignored"


class TestTestingArtifactsPatterns:
    """Tests for testing-related ignore patterns."""
    
    @pytest.fixture
    def gitignore_content(self) -> str:
        """
        Load the repository's .gitignore file content.
        
        Returns:
            content (str): The full text of the .gitignore file.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_ignores_pytest_cache(self, gitignore_content: str):
        """Test that .pytest_cache is ignored."""
        assert '.pytest_cache' in gitignore_content, \
            ".pytest_cache should be in .gitignore"
    
    def test_ignores_coverage_files(self, gitignore_content: str):
        """
        Validate that the repository's .gitignore includes coverage-related patterns: '.coverage' and 'coverage.xml'.
        """
        assert '.coverage' in gitignore_content, \
            ".coverage should be in .gitignore"
        assert 'coverage.xml' in gitignore_content, \
            "coverage.xml should be in .gitignore"
    
    def test_ignores_htmlcov_directory(self, gitignore_content: str):
        """
        Check that the repository's .gitignore contains an 'htmlcov' ignore pattern.
        
        Raises:
            AssertionError: if 'htmlcov' is not present in gitignore_content.
        """
        assert 'htmlcov' in gitignore_content, \
            "htmlcov should be in .gitignore"
    
    def test_junit_xml_not_ignored(self, gitignore_content: str):
        """
        Ensure 'junit.xml' is not listed in the repository's .gitignore.
        
        Fails if a line exactly equal to 'junit.xml' appears in the file.
        """
        # junit.xml should NOT be in the ignore patterns
        lines = [line.strip() for line in gitignore_content.split('\n')]
        junit_ignored = any('junit.xml' == line for line in lines)
        
        assert not junit_ignored, \
            "junit.xml should NOT be ignored (was removed from .gitignore)"


class TestDatabaseFilePatterns:
    """Tests for database file ignore patterns."""
    
    @pytest.fixture
    def gitignore_content(self) -> str:
        """
        Load the repository's .gitignore file content.
        
        Returns:
            content (str): The full text of the .gitignore file.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_test_databases_not_globally_ignored(self, gitignore_content: str):
        """
        Ensure test database filename patterns 'test_*.db' and '*_test.db' are not present in the repository's .gitignore.
        
        Parameters:
            gitignore_content (str): Full text of the .gitignore file to be checked.
        """
        # These patterns should NOT be in .gitignore anymore
        removed_patterns = ['test_*.db', '*_test.db']
        
        lines = [line.strip() for line in gitignore_content.split('\n')]
        
        for pattern in removed_patterns:
            assert pattern not in lines, \
                f"Pattern '{pattern}' should have been removed from .gitignore"
    
    def test_can_commit_test_databases(self, gitignore_content: str):
        """
        Ensure the repository's .gitignore does not ignore test database files.
        
        Asserts that the literal patterns 'test_*.db' and '*_test.db' are not present as lines in the provided .gitignore content.
        """
        # Verify the specific patterns are gone
        assert 'test_*.db' not in gitignore_content.split('\n'), \
            "test_*.db pattern should be removed"
        assert '*_test.db' not in gitignore_content.split('\n'), \
            "*_test.db pattern should be removed"


class TestFrontendPatterns:
    """Tests for frontend-related ignore patterns."""
    
    @pytest.fixture
    def gitignore_content(self) -> str:
        """
        Load the repository's .gitignore file content.
        
        Returns:
            content (str): The full text of the .gitignore file.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_ignores_node_modules(self, gitignore_content: str):
        """Test that node_modules is ignored."""
        assert 'node_modules' in gitignore_content, \
            "node_modules should be in .gitignore"
    
    def test_ignores_frontend_build_artifacts(self, gitignore_content: str):
        """
        Asserts that at least two common frontend build artifact directories are listed in the repository's .gitignore.
        
        Checks for presence of '.next', 'out' and 'dist' and fails the test if fewer than two are found.
        """
        patterns = ['.next', 'out', 'dist']
        found = [p for p in patterns if p in gitignore_content]
        assert len(found) >= 2, \
            f"Frontend build directories should be ignored (found: {found})"
    
    def test_ignores_frontend_coverage(self, gitignore_content: str):
        """
        Assert that the repository's .gitignore ignores frontend coverage output.
        
        Checks that either the pattern 'coverage' or 'frontend/coverage' appears in the provided .gitignore content.
        """
        assert 'coverage' in gitignore_content or 'frontend/coverage' in gitignore_content, \
            "Frontend coverage directory should be ignored"


class TestIDEAndEditorPatterns:
    """Tests for IDE and editor ignore patterns."""
    
    @pytest.fixture
    def gitignore_content(self) -> str:
        """
        Load the repository's .gitignore file content.
        
        Returns:
            content (str): The full text of the .gitignore file.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_ignores_vscode_settings(self, gitignore_content: str):
        """Test that VS Code settings are ignored."""
        assert '.vscode' in gitignore_content, \
            ".vscode should be in .gitignore"
    
    def test_ignores_idea_settings(self, gitignore_content: str):
        """Test that IntelliJ IDEA settings are ignored."""
        assert '.idea' in gitignore_content, \
            ".idea should be in .gitignore"


class TestGitignoreChangesRegression:
    """Regression tests for the specific .gitignore changes."""
    
    @pytest.fixture
    def gitignore_lines(self) -> List[str]:
        """
        Read the repository's .gitignore and return its lines with surrounding whitespace removed.
        
        Each element is a line from the .gitignore file with leading and trailing whitespace stripped.
        
        Returns:
            List[str]: Lines from the .gitignore file with whitespace removed from both ends.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f.readlines()]
    
    def test_junit_xml_was_removed(self, gitignore_lines: List[str]):
        """
        Check that 'junit.xml' is not present in the repository's .gitignore.
        
        Fails the test if any parsed .gitignore line equals 'junit.xml'.
        """
        assert 'junit.xml' not in gitignore_lines, \
            "junit.xml should have been removed from .gitignore"
    
    def test_test_db_patterns_were_removed(self, gitignore_lines: List[str]):
        """
        Assert that the repository's .gitignore no longer contains common test database ignore patterns.
        
        This test fails if either 'test_*.db' or '*_test.db' appears in the list of gitignore lines.
        """
        assert 'test_*.db' not in gitignore_lines, \
            "test_*.db should have been removed"
        assert '*_test.db' not in gitignore_lines, \
            "*_test.db should have been removed"
    
    def test_essential_ignores_still_present(self, gitignore_lines: List[str]):
        """
        Verify essential ignore patterns remain present in the .gitignore lines.
        
        For each required pattern this test asserts that at least one line contains the pattern or a close variant (a trailing slash on the pattern is ignored when matching), failing with a clear message if any essential pattern is missing.
        """
        essential = ['.coverage', 'coverage.xml', 'htmlcov/', '.pytest_cache/']
        
        for pattern in essential:
            # Check if pattern or close variant exists
            found = any(pattern.rstrip('/') in line for line in gitignore_lines)
            assert found, f"Essential pattern '{pattern}' should still be in .gitignore"


class TestGitignoreEdgeCases:
    """Edge case tests for .gitignore patterns."""
    
    @pytest.fixture
    def gitignore_content(self) -> str:
        """
        Load the repository's .gitignore file content.
        
        Returns:
            content (str): The full text of the .gitignore file.
        """
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_no_trailing_whitespace(self, gitignore_content: str):
        """
        Ensure no lines in the .gitignore content end with trailing whitespace.
        
        Parameters:
            gitignore_content (str): Full text of the .gitignore file to validate.
        """
        lines = gitignore_content.split('\n')
        lines_with_trailing = [
            (i + 1, line)
            for i, line in enumerate(lines)
            if line and line != line.rstrip()
        ]
        
        assert len(lines_with_trailing) == 0, \
            f"Found lines with trailing whitespace: {lines_with_trailing}"
    
    def test_file_ends_with_newline(self, gitignore_content: str):
        """
        Ensure the repository's .gitignore file ends with a newline character.
        """
        assert gitignore_content.endswith('\n'), \
            ".gitignore should end with a newline"
    
    def test_no_empty_pattern_lines(self, gitignore_content: str):
        """
        Check the .gitignore content contains no lines that consist solely of whitespace.
        
        If any non-empty line contains only whitespace characters, the test fails and the assertion message lists each offending line as (line_number, repr(line)).
        """
        lines = gitignore_content.split('\n')
        problematic = [
            (i + 1, repr(line))
            for i, line in enumerate(lines)
            if line and not line.strip() and line != '\n'
        ]
        
        assert len(problematic) == 0, \
            f"Found lines with only whitespace: {problematic}"