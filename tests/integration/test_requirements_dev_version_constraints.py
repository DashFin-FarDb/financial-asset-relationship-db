"""
Comprehensive unit tests for requirements-dev.txt version constraints.

Tests validate that all development dependencies have appropriate version
constraints and that the recent changes (types-PyYAML version pinning) are correct.
"""

import pytest
import re
from pathlib import Path
from typing import List, Dict
from packaging.specifiers import SpecifierSet


class TestRequirementsDevFileStructure:
    """Tests for requirements-dev.txt file structure."""
    
    @pytest.fixture
    def req_file_path(self) -> Path:
        """
        Locate the repository's top-level requirements-dev.txt file.
        
        Returns:
            Path: Path to the requirements-dev.txt file.
        """
        return Path(__file__).parent.parent.parent / "requirements-dev.txt"
    
    def test_file_exists(self, req_file_path: Path):
        """Test that requirements-dev.txt exists."""
        assert req_file_path.exists(), "requirements-dev.txt should exist"
    
    def test_file_readable(self, req_file_path: Path):
        """Test that requirements-dev.txt is readable."""
        with open(req_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0, "requirements-dev.txt should not be empty"


class TestTypesPyYAMLVersionConstraint:
    """Regression tests for types-PyYAML version constraint change."""
    
    @pytest.fixture
    def requirements_dict(self) -> Dict[str, str]:
        """
        Return a mapping of package names to their version specification strings from requirements-dev.txt.
        
        Reads the repository's top-level requirements-dev.txt, ignores empty lines and comments, and parses each requirement line into a package name and the remainder of the line as its version specification (including operators, version numbers and extras). Package names are taken from the start of the line and may include letters, digits, underscores, hyphens and bracketed extras.
        
        Returns:
            Dict[str, str]: A dictionary where keys are package names and values are the corresponding version specification substring (may be an empty string if no specifier is present).
        """
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        reqs = {}
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)(.*)$', line)
                if match:
                    pkg_name, version_spec = match.groups()
                    reqs[pkg_name] = version_spec
        
        return reqs
    
    def test_types_pyyaml_has_version_constraint(self, requirements_dict: Dict[str, str]):
        """Test that types-PyYAML has a version constraint."""
        assert 'types-PyYAML' in requirements_dict, \
            "types-PyYAML should be present"
        
        version_spec = requirements_dict['types-PyYAML']
        assert version_spec.strip(), \
            "types-PyYAML should have a version constraint"
    
    def test_types_pyyaml_minimum_version_6(self, requirements_dict: Dict[str, str]):
        """
        Ensure the requirements entry for `types-PyYAML` specifies a minimum version of 6.0.
        
        Asserts that the version specifier for `types-PyYAML` contains the substring '`>=6.0`'.
        """
        version_spec = requirements_dict['types-PyYAML']
        
        assert '>=6.0' in version_spec, \
            "types-PyYAML should require version >=6.0.0"
    
    def test_types_pyyaml_not_unpinned(self, requirements_dict: Dict[str, str]):
        """Test that types-PyYAML is not unpinned."""
        version_spec = requirements_dict.get('types-PyYAML', '')
        
        assert version_spec and version_spec.strip(), \
            "types-PyYAML should have a version constraint (not unpinned)"
    
    def test_types_pyyaml_matches_pyyaml_major_version(self, requirements_dict: Dict[str, str]):
        """
        Check that when both PyYAML and types-PyYAML specify a minimum major version with '>=' the major versions are equal.
        
        Parameters:
            requirements_dict (Dict[str, str]): Mapping of package names to their version specifier strings as found in requirements-dev.txt.
        
        Notes:
            If both packages include a '>=' specifier for the major version, the test will fail when those major versions differ.
        """
        pyyaml_spec = requirements_dict.get('PyYAML', '')
        types_spec = requirements_dict.get('types-PyYAML', '')
        
        # Extract major versions
        pyyaml_match = re.search(r'>=(\d+)', pyyaml_spec)
        types_match = re.search(r'>=(\d+)', types_spec)
        
        if pyyaml_match and types_match:
            pyyaml_major = int(pyyaml_match.group(1))
            types_major = int(types_match.group(1))
            
            assert pyyaml_major == types_major, \
                f"types-PyYAML major version ({types_major}) should match PyYAML ({pyyaml_major})"


class TestSpecificDependencies:
    """Tests for specific required dependencies."""
    
    @pytest.fixture
    def requirements_dict(self) -> Dict[str, str]:
        """
        Return a mapping of package names to their version specification strings from requirements-dev.txt.
        
        Reads the repository's top-level requirements-dev.txt, ignores empty lines and comments, and parses each requirement line into a package name and the remainder of the line as its version specification (including operators, version numbers and extras). Package names are taken from the start of the line and may include letters, digits, underscores, hyphens and bracketed extras.
        
        Returns:
            Dict[str, str]: A dictionary where keys are package names and values are the corresponding version specification substring (may be an empty string if no specifier is present).
        """
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        reqs = {}
        
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)(.*)$', line)
                if match:
                    pkg_name, version_spec = match.groups()
                    reqs[pkg_name] = version_spec
        
        return reqs
    
    def test_pytest_present(self, requirements_dict: Dict[str, str]):
        """Test that pytest is in requirements."""
        assert 'pytest' in requirements_dict
    
    def test_pytest_cov_present(self, requirements_dict: Dict[str, str]):
        """Test that pytest-cov is in requirements."""
        assert 'pytest-cov' in requirements_dict
    
    def test_pyyaml_present(self, requirements_dict: Dict[str, str]):
        """Test that PyYAML is in requirements."""
        assert 'PyYAML' in requirements_dict
    
    def test_types_pyyaml_present(self, requirements_dict: Dict[str, str]):
        """Test that types-PyYAML is in requirements."""
        assert 'types-PyYAML' in requirements_dict
    
    def test_black_present(self, requirements_dict: Dict[str, str]):
        """Test that black formatter is in requirements."""
        assert 'black' in requirements_dict
    
    def test_flake8_present(self, requirements_dict: Dict[str, str]):
        """Test that flake8 linter is in requirements."""
        assert 'flake8' in requirements_dict
    
    def test_mypy_present(self, requirements_dict: Dict[str, str]):
        """Test that mypy type checker is in requirements."""
        assert 'mypy' in requirements_dict


class TestVersionConstraintFormat:
    """Tests for version constraint formatting and syntax."""
    
    @pytest.fixture
    def req_lines(self) -> List[str]:
        """
        Return the non-empty, non-comment lines from the repository's requirements-dev.txt with surrounding whitespace removed.
        
        Returns:
            List[str]: Requirement lines as strings, each stripped of leading and trailing whitespace; excludes empty lines and lines that start with `#`.
        """
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        with open(path, 'r', encoding='utf-8') as f:
            return [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith('#')
            ]
    
    def test_all_lines_have_version_constraints(self, req_lines: List[str]):
        """Test that all requirements specify version constraints."""
        for line in req_lines:
            assert any(op in line for op in ['>=', '==', '~=', '>', '<', '!=']), \
                f"Requirement '{line}' should have a version constraint"
    
    def test_version_constraints_parseable(self, req_lines: List[str]):
        """
        Validate that every requirement line contains a parseable version specifier.
        
        Each line is split into a package name and a version specification and the version specification is validated using packaging.specifiers.SpecifierSet; the test fails if any specifier is invalid.
        """
        for line in req_lines:
            match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)(.*)$', line)
            assert match, f"Cannot parse requirement line: {line}"
            
            pkg_name, version_spec = match.groups()
            
            try:
                SpecifierSet(version_spec)
            except Exception as e:
                pytest.fail(f"Invalid version specifier in '{line}': {e}")
    
    def test_all_use_minimum_version_operator(self, req_lines: List[str]):
        """Test that all requirements use >= operator for flexibility."""
        for line in req_lines:
            assert '>=' in line, \
                f"Package '{line}' should use >= operator for version constraint"


class TestNoDuplicateDependencies:
    """Tests for duplicate dependency declarations."""
    
    def test_no_duplicate_packages(self):
        """Test that no package is listed multiple times."""
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        
        packages = []
        with open(path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)', line)
                if match:
                    packages.append(match.group(1))
        
        duplicates = [pkg for pkg in set(packages) if packages.count(pkg) > 1]
        
        assert len(duplicates) == 0, \
            f"Found duplicate package declarations: {duplicates}"


class TestRequirementsDevEdgeCases:
    """Edge case tests for requirements-dev.txt."""
    
    def test_file_ends_with_newline(self):
        """Test that file ends with a newline."""
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert content.endswith('\n'), \
            "requirements-dev.txt should end with a newline"
    
    def test_no_trailing_whitespace(self):
        """
        Ensure no line in requirements-dev.txt contains trailing whitespace.
        
        If any offending lines are found the test fails and reports a list of tuples with the line number and the line's `repr` for each offending line.
        """
        path = Path(__file__).parent.parent.parent / "requirements-dev.txt"
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        lines_with_trailing = [
            (i + 1, repr(line))
            for i, line in enumerate(lines)
            if line and line != line.rstrip() + '\n' and line != line.rstrip()
        ]
        
        assert len(lines_with_trailing) == 0, \
            f"Found lines with trailing whitespace: {lines_with_trailing}"