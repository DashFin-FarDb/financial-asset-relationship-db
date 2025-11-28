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
        """Return path to requirements-dev.txt."""
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
        """Parse requirements into a dictionary."""
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
        """Test that types-PyYAML requires version 6.0.0 or higher."""
        version_spec = requirements_dict['types-PyYAML']
        
        assert '>=6.0' in version_spec, \
            "types-PyYAML should require version >=6.0.0"
    
    def test_types_pyyaml_not_unpinned(self, requirements_dict: Dict[str, str]):
        """Test that types-PyYAML is not unpinned."""
        version_spec = requirements_dict.get('types-PyYAML', '')
        
        assert version_spec and version_spec.strip(), \
            "types-PyYAML should have a version constraint (not unpinned)"
    
    def test_types_pyyaml_matches_pyyaml_major_version(self, requirements_dict: Dict[str, str]):
        """Test that types-PyYAML major version matches PyYAML major version."""
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
        """Parse requirements into a dictionary."""
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
        """Get requirement lines."""
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
        """Test that all version specifiers are valid."""
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
        """Test that lines don't have trailing whitespace."""
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