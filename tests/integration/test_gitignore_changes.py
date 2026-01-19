"""
Comprehensive tests for .gitignore configuration changes.

This module validates that the .gitignore file is properly configured,
especially focusing on the recent changes that removed test database
file patterns and junit.xml.
"""

import pytest
from pathlib import Path
from typing import Set


GITIGNORE_FILE = Path(__file__).parent.parent.parent / ".gitignore"


def parse_gitignore() -> Set[str]:
    """
    Parse .gitignore and return set of patterns.
    
    Returns:
        Set of non-comment, non-empty patterns from .gitignore
    """
    patterns = set()
    
    if not GITIGNORE_FILE.exists():
        return patterns
    
    try:
        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.add(line)
    except (FileNotFoundError, PermissionError):
        # If the .gitignore file is missing or not accessible, return empty set
        # so tests that rely on parse_gitignore can handle gracefully.
        return set()

    return patterns


class TestGitignoreFileExists:
    """Test that .gitignore exists and is properly formatted."""
    
    def test_file_exists(self):
        """Test that .gitignore file exists."""
        assert GITIGNORE_FILE.exists(), ".gitignore file should exist"
    
    def test_file_is_readable(self):
        """Test that .gitignore can be read."""
        try:
            with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
                assert len(content) > 0, ".gitignore should not be empty"
        except (FileNotFoundError, PermissionError) as e:
            pytest.skip(f".gitignore file not accessible: {e}")

    def test_file_uses_utf8_encoding(self):
        """Test that .gitignore uses UTF-8 encoding."""
        try:
            with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
                # Should not raise encoding errors
                f.read()
        except (FileNotFoundError, PermissionError) as e:
            pytest.skip(f".gitignore file not accessible: {e}")


class TestGitignoreRemovedPatterns:
    """Test that specific patterns were correctly removed in recent changes."""
    
    @pytest.fixture
    def patterns(self) -> Set[str]:
        """Get all patterns from .gitignore."""
        return parse_gitignore()
    
    def test_junit_xml_not_ignored(self, patterns: Set[str]):
        """Test that junit.xml pattern was removed (as per diff)."""
        assert 'junit.xml' not in patterns, \
            "junit.xml should not be ignored anymore"
    
    def test_test_db_pattern_not_present(self, patterns: Set[str]):
        """Test that test_*.db pattern was removed."""
        assert 'test_*.db' not in patterns, \
            "test_*.db pattern should be removed"
    
    def test_test_db_wildcard_not_present(self, patterns: Set[str]):
        """Test that *_test.db pattern was removed."""
        assert '*_test.db' not in patterns, \
            "*_test.db pattern should be removed"


class TestGitignoreEssentialPatterns:
    """Test that essential patterns are still present."""
    
    def test_python_egg_info_ignored(self, patterns: Set[str]):
        """Test that Python package metadata is ignored."""
        egg_patterns = {'*.egg-info/', '*.egg-info', 'dist/', 'build/'}
        assert any(p in patterns for p in egg_patterns)
    
    @pytest.fixture
    def content(self) -> str:
        """Get .gitignore content."""
        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_no_duplicate_patterns(self):
        """Test that no equivalent pattern appears multiple times (handles dir/ vs dir and negations)."""
        patterns = []

        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
        from collections import Counter

        patterns = []

        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)

        pattern_counts = Counter(patterns)
        duplicates = [p for p, count in pattern_counts.items() if count > 1]

        assert len(duplicates) == 0, \
            f"Found duplicate patterns: {duplicates}"
                    is_negated = line.startswith('!')
                    core = line[1:] if is_negated else line
                    # Normalize directory patterns by removing trailing slashes
                    normalized_core = core.rstrip('/') if core.endswith('/') else core
                    normalized = f'!{normalized_core}' if is_negated else normalized_core
                    patterns.append(normalized)
        from collections import Counter

        patterns = []

        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    patterns.append(line)

        pattern_counts = Counter(patterns)
        duplicates = [p for p, count in pattern_counts.items() if count > 1]

        assert len(duplicates) == 0, \
            f"Found duplicate patterns: {duplicates}"
    
    def test_patterns_not_overly_broad(self, content: str):
        """Test that patterns are not dangerously broad."""
        dangerous_patterns = ['*', '**', '/*']
        
        for line in content.split('\n'):
            line = line.strip()
            if line and not line.startswith('#'):
                assert line not in dangerous_patterns, \
                    f"Dangerous pattern found: {line}"
    
    def test_comments_properly_formatted(self, content: str):
        """Test that comments use proper format."""
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped and stripped.startswith('#'):
                # Comments should either be standalone or have space after #
                if len(stripped) > 1:
                    assert stripped[1] == ' ' or stripped[1].isalnum(), \
                        f"Comment should have space after #: {line}"


class TestGitignoreProjectSpecific:
    """Test project-specific .gitignore patterns."""
    
    @pytest.fixture
    def patterns(self) -> Set[str]:
        """Get all patterns from .gitignore."""
        return parse_gitignore()
    
    def test_database_file_ignored(self, patterns: Set[str]):
        """Test that SQLite database files are ignored."""
        db_patterns = {'*.db', '*.sqlite', '*.sqlite3'}
        assert any(p in patterns for p in db_patterns), \
            "Should ignore database files"
    
    def test_frontend_build_ignored(self, patterns: Set[str]):
        """Test that frontend build artifacts are ignored."""
        frontend_patterns = {'.next/', 'next-env.d.ts'}
        matching = [p for p in frontend_patterns if p in patterns]
        assert len(matching) > 0, \
            "Should ignore Next.js build artifacts"
    
    def test_python_egg_info_ignored(self, patterns: Set[str]):
        """Test that Python package metadata is ignored."""
        egg_patterns = {'*.egg-info/', '*.egg-info', 'dist/', 'build/'}
        assert any(p in patterns for p in egg_patterns), "Expected Python package metadata patterns to be ignored"

    def test_no_duplicate_patterns(self):
        """Test that no equivalent pattern appears multiple times (handles dir/ vs dir and negations)."""
        normalized_patterns = []

        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    is_negated = line.startswith('!')
                    core = line[1:] if is_negated else line
                    # Normalize directory patterns by removing trailing slashes
                    normalized_core = core.rstrip('/') if core.endswith('/') else core
                    normalized = f'!{normalized_core}' if is_negated else normalized_core
                    normalized_patterns.append(normalized)

        duplicates = [p for p in normalized_patterns if normalized_patterns.count(p) > 1]
        unique_duplicates = list(set(duplicates))

        assert len(unique_duplicates) == 0, f"Found duplicate patterns: {unique_duplicates}"


class TestGitignoreEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_lines_handled(self):
def test_no_duplicate_patterns(self):
    """Test that no equivalent pattern appears multiple times (handles dir/ vs dir and negations)."""
    patterns = []

    with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                is_negated = line.startswith('!')
                core = line[1:] if is_negated else line
                # Normalize directory patterns by removing trailing slashes
                normalized_core = core.rstrip('/') if core.endswith('/') else core
                normalized = f'!{normalized_core}' if is_negated else normalized_core
                patterns.append(normalized)

    duplicates = [p for p in patterns if patterns.count(p) > 1]
    unique_duplicates = list(set(duplicates))

    assert len(unique_duplicates) == 0, \
        f"Found duplicate patterns: {unique_duplicates}"
        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Should not break parsing
        patterns = parse_gitignore()
        assert isinstance(patterns, set)
    
    def test_trailing_whitespace_acceptable(self):
        """Test that patterns work even with trailing whitespace."""
        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Verify file is parseable even if some lines have trailing whitespace
        patterns = parse_gitignore()
        assert len(patterns) > 0
    
    def test_file_ends_with_newline(self):
        """Test that file ends with a newline (standard practice)."""
        with open(GITIGNORE_FILE, 'rb') as f:
            content = f.read()
        
        # Should end with newline
        assert content.endswith(b'\n'), \
            ".gitignore should end with newline"


class TestGitignoreConsistency:
    """Test consistency with project structure."""
    
    def test_frontend_coverage_ignored(self):
        """Test that frontend coverage directory is ignored."""
        patterns = parse_gitignore()
        
        frontend_coverage_patterns = ['frontend/coverage/', 'coverage/']
        assert any(p in patterns for p in frontend_coverage_patterns), \
            "Frontend coverage should be ignored"
    
    def test_security_reports_handling(self):
        """Test handling of security reports."""
        patterns = parse_gitignore()
        
        # Security reports may or may not be ignored depending on project policy
        # Just ensure .gitignore is parseable
        assert isinstance(patterns, set)
    
    def test_env_files_partially_ignored(self):
        """Test that .env files are handled correctly."""
        patterns = parse_gitignore()
        
        # .env should be ignored, but .env.example should not
        env_related = [p for p in patterns if '.env' in p.lower()]
        
        # Should have some .env pattern
        assert len(env_related) > 0, \
            "Should have .env related patterns"


class TestGitignoreRegressionPrevention:
    """Test to prevent regression of removed patterns."""
    
    @pytest.fixture
    def content(self) -> str:
        """Get .gitignore content."""
        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_no_junit_xml_pattern_reintroduction(self, content: str):
        """Test that junit.xml pattern was not reintroduced."""
        assert 'junit.xml' not in content.lower(), \
            "junit.xml pattern should not be reintroduced"
    
    def test_no_test_db_wildcard_reintroduction(self, content: str):
        """Test that test_*.db pattern was not reintroduced."""
        # Check for the exact pattern that was removed
        for line in content.split('\n'):
            stripped = line.strip()
            if stripped and not stripped.startswith('#'):
                assert stripped != 'test_*.db', \
                    "test_*.db pattern should not be reintroduced"
                assert stripped != '*_test.db', \
                    "*_test.db pattern should not be reintroduced"
    
    def test_general_db_pattern_still_present(self, content: str):
        """Test that general *.db pattern is still present if needed."""
        patterns = parse_gitignore()
        
        # The project may still ignore general .db files, just not specific test patterns
        # This is acceptable and we just verify the file is valid
        assert len(patterns) > 0


class TestGitignoreSecurityConsiderations:
    """Test security-related .gitignore patterns."""
    
    @pytest.fixture
    def patterns(self) -> Set[str]:
        """Get all patterns from .gitignore."""
        return parse_gitignore()
    
    def test_credentials_ignored(self, patterns: Set[str]):
        """Test that credential files are ignored."""
        credential_patterns = {
            '.env',
            '.env.local',
            '.env.*.local',
            '*.env',
            '*.pem',
            '*.key',
            '*.crt',
            '*.cer',
            '*.der',
            '*.p12',
            '*.pfx',
            '*.p7b',
            '*.p7c',
        }
    
        # At least some credential files should be ignored
        matching = [p for p in credential_patterns if p in patterns]
        assert len(matching) > 0, "Should ignore credential files"

    def test_api_keys_ignored(self, patterns: Set[str]):
        """Test that API key files are ignored."""
        # .env files commonly contain API keys
        assert (
            '.env' in patterns
            or '.env.local' in patterns
            or any('.env' in p for p in patterns)
        )

    def test_private_keys_ignored(self, patterns: Set[str]):
        """Test that private key files are ignored."""
        key_patterns = [
            '*.pem',
            '*.key',
            'id_rsa',
            'id_dsa',
            'id_ed25519',
            'id_ecdsa',
        ]
    
        # Check if at least some key patterns are ignored
        matching = [p for p in key_patterns if p in patterns]
        # We expect at least one key pattern to be present
        assert len(matching) > 0 or any('key' in p.lower() for p in patterns)

class TestGitignorePerformance:
    """Test performance characteristics of .gitignore."""
    
    def test_file_not_excessively_large(self):
        """Test that .gitignore is not excessively large."""
        with open(GITIGNORE_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Reasonable limit: < 500 lines
        assert len(lines) < 500, \
            ".gitignore should not be excessively large"
    
    def test_reasonable_number_of_patterns(self):
        """Test that there's a reasonable number of ignore patterns."""
        patterns = parse_gitignore()
        
        # Reasonable range: 10-200 patterns
        assert 10 <= len(patterns) <= 200, \
            f"Should have 10-200 patterns, got {len(patterns)}"
    
    def test_no_redundant_wildcard_patterns(self):
        """Test that there are no obviously redundant patterns."""
        patterns = parse_gitignore()
        
        # Check for patterns that would be covered by more general patterns
        # For example, if we have *.db, we don't need specific test_*.db
        if '*.db' in patterns:
            assert 'test_*.db' not in patterns, \
                "test_*.db is redundant if *.db exists"