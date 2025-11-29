"""
Comprehensive tests for codecov workflow removal validation.

Tests validate that the codecov.yaml workflow was properly removed and that
coverage functionality is still available through other means.
"""

import pytest
from pathlib import Path
from typing import List


class TestCodecovWorkflowRemoval:
    """Tests validating the codecov workflow removal."""
    
    @pytest.fixture
    def workflows_dir(self) -> Path:
        """
        Path to the repository's .github/workflows directory.
        
        Returns:
            Path: Path object pointing to the repository's .github/workflows directory (computed relative to this test file).
        """
    def test_codecov_yaml_file_removed(self, workflows_dir: Path):
        """Test that codecov.yaml file was removed."""
        if not workflows_dir.exists():
            pytest.skip("Workflows directory not found")
        codecov_file = workflows_dir / "codecov.yaml"
        assert not codecov_file.exists(), \
            "codecov.yaml should have been removed from workflows"
        """Test that codecov.yaml file was removed."""
        codecov_file = workflows_dir / "codecov.yaml"
        assert not codecov_file.exists(), \
            "codecov.yaml should have been removed from workflows"
    
    def test_codecov_yml_file_removed(self, workflows_dir: Path):
        """
        Verify that a `codecov.yml` workflow file does not exist in the repository's `.github/workflows` directory.
        """
        codecov_file = workflows_dir / "codecov.yml"
        assert not codecov_file.exists(), \
            "codecov.yml should not exist in workflows"


class TestCoverageStillAvailable:
    """Tests ensuring coverage functionality is still available."""
    
    @pytest.fixture
    def requirements_dev(self) -> Path:
        """
        Path to the project's requirements-dev.txt file.
        
        Returns:
            Path: Path pointing to the repository's requirements-dev.txt file (located two directories above the test file).
        """
    def test_pytest_cov_in_dev_requirements(self, requirements_dev: Path):
        """
        Validate that `pytest-cov` is listed in the project's development requirements.
    
        Parameters:
            requirements_dev (Path): Path to the `requirements-dev.txt` file to check.
        """
        if not requirements_dev.exists():
            pytest.skip("requirements-dev.txt not found")
    
        with open(requirements_dev, 'r', encoding='utf-8') as f:
            content = f.read()
    
        assert 'pytest-cov' in content, \
            "pytest-cov should still be in requirements-dev.txt for local coverage"
        """
        Validate that `pytest-cov` is listed in the project's development requirements.
        
        Parameters:
            requirements_dev (Path): Path to the `requirements-dev.txt` file to check.
        """
        with open(requirements_dev, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'pytest-cov' in content, \
            "pytest-cov should still be in requirements-dev.txt for local coverage"
    
    def test_can_run_coverage_locally(self, requirements_dev: Path):
        """Test that coverage can still be run locally."""
        with open(requirements_dev, 'r', encoding='utf-8') as f:
            content = f.read()
        
        assert 'pytest-cov>=4.0.0' in content, \
            "pytest-cov should be available for running coverage locally"


class TestGitignoreCoveragePatterns:
    """Tests for coverage-related gitignore patterns."""
    
    def test_coverage_files_still_ignored(self):
        """Test that coverage output files are still ignored."""
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            gitignore_content = f.read()
        
        assert '.coverage' in gitignore_content
        assert 'coverage.xml' in gitignore_content
        assert 'htmlcov' in gitignore_content
    
    def test_junit_xml_not_ignored(self):
        """Test that junit.xml is not ignored (removed from .gitignore)."""
        path = Path(__file__).parent.parent.parent / ".gitignore"
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        lines = [line.strip() for line in content.split('\n')]
        assert 'junit.xml' not in lines, \
            "junit.xml should not be in .gitignore (was removed)"


class TestWorkflowCoverageAlternatives:
    """Tests for alternative coverage mechanisms."""
    
    def test_other_workflows_can_run_tests(self):
        """
        Checks that at least one GitHub Actions workflow in .github/workflows invokes pytest.
        
        Skips the test if the workflows directory is missing. Reads workflow YAML files and asserts that at least one file contains the string "pytest", failing the test if none do.
        """
        workflows_dir = Path(__file__).parent.parent.parent / ".github" / "workflows"
        
        if not workflows_dir.exists():
            pytest.skip("Workflows directory not found")
        
        workflow_files = list(workflows_dir.glob("*.yml")) + list(workflows_dir.glob("*.yaml"))
        workflows_with_pytest = []
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if 'pytest' in content:
                workflows_with_pytest.append(workflow_file.name)
        
        assert len(workflows_with_pytest) > 0, \
            "At least one workflow should run pytest"