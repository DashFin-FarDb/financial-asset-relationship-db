"""
Integration tests validating that workflow files and requirements work together.

This test suite ensures that the dependencies specified in requirements-dev.txt
are appropriate for the workflows defined in .github/workflows/, and that
workflows can successfully use the installed dependencies.
"""

import pytest
import yaml
from pathlib import Path
from typing import List, Tuple


WORKFLOWS_DIR = Path(__file__).parent.parent.parent / ".github" / "workflows"
REQUIREMENTS_FILE = Path(__file__).parent.parent.parent / "requirements-dev.txt"


from packaging.requirements import Requirement


def parse_requirements(file_path: Path) -> List[Tuple[str, str]]:
    """
    Read a pip-style requirements file and produce a list of package name and version-specifier pairs.
    
    Parses each non-empty, non-comment line with packaging.Requirement and returns a list of tuples (package_name, version_specifier). Lines that are blank or start with '#' are ignored. The version_specifier is an empty string when no specifier is present.
    
    Parameters:
        file_path (Path): Path to the requirements file to parse.
    
    Returns:
        List[Tuple[str, str]]: Tuples of (package_name, version_specifier).
    
    Raises:
        ValueError: If any requirement line cannot be parsed; the error message includes the offending line.
    """
    requirements: List[Tuple[str, str]] = []

    with open(file_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()

            if not line or line.startswith('#'):
                continue

            try:
                req = Requirement(line)
                # Only include the name and version specifier; ignore extras and markers for matching
                requirements.append((req.name, str(req.specifier)))
            except Exception as e:
                # Surface unparseable requirement lines to avoid masking issues
                raise ValueError(f"Failed to parse requirement line: '{line}'. Error: {e}") from e
    return requirements


class TestWorkflowCanInstallRequirements:
    """Test that workflows have steps to install the dependencies from requirements-dev.txt."""
    
    def test_pr_agent_workflow_has_install_dependencies_step(self):
        """Test that pr-agent workflow has a step to install Python dependencies."""
        pr_agent_file = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not pr_agent_file.exists():
            pytest.skip("pr-agent.yml not found")
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Check that at least one job has a step to install dependencies
        has_install_step = False
        
        for job_name, job in workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                run_cmd = step.get('run', '')
                step_name = step.get('name', '').lower()
                
                # Look for pip install or requirements file installation
                if ('pip install' in run_cmd.lower() or 
                    'requirements' in run_cmd.lower() or
                    'requirements' in step_name):
                    has_install_step = True
                    break
            
            if has_install_step:
                break
        
        assert has_install_step, (
            "pr-agent workflow should have a step to install Python dependencies "
            "(e.g., 'pip install -r requirements-dev.txt')"
        )
    
    def test_workflow_installs_before_running_tests(self):
        """Test that dependency installation happens before test execution in workflows."""
        pr_agent_file = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not pr_agent_file.exists():
            pytest.skip("pr-agent.yml not found")
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        for job_name, job in workflow.get('jobs', {}).items():
            steps = job.get('steps', [])
            
            install_idx = None
            test_idx = None
            
            for i, step in enumerate(steps):
                run_cmd = step.get('run', '').lower()
                step_name = step.get('name', '').lower()
                
                if 'pip install' in run_cmd or 'requirements' in run_cmd:
                    if install_idx is None:
                        install_idx = i
                
                if 'pytest' in run_cmd or 'test' in step_name:
                    if test_idx is None:
                        test_idx = i
            
            # If both exist, install should come before test
            if install_idx is not None and test_idx is not None:
                assert install_idx < test_idx, (
                    f"In job '{job_name}', dependency installation (step {install_idx}) "
                    f"should come before test execution (step {test_idx})"
                )


class TestPyYAMLAvailability:
    """Test that PyYAML is properly configured for use in workflow tests."""
    
    def test_pyyaml_in_requirements_for_workflow_validation(self):
        """Test that PyYAML is in requirements-dev.txt for workflow validation tests."""
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        requirements = parse_requirements(REQUIREMENTS_FILE)
        package_names = [pkg.lower() for pkg, _ in requirements]
        assert 'PyYAML' in package_names, (
            "PyYAML must be in requirements-dev.txt because test_github_workflows.py "
            "uses it to parse and validate workflow YAML files"
        )
    
    def test_pyyaml_can_parse_workflow_files(self):
        """Test that installed PyYAML can successfully parse workflow files."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed in test environment")
        
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
        
        assert len(workflow_files) > 0, "No workflow files found to test"
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                try:
                    content = yaml.safe_load(f)
                    assert isinstance(content, dict), (
                        f"{workflow_file.name} should parse to a dictionary"
                    )
                except yaml.YAMLError as e:
                    pytest.fail(f"PyYAML failed to parse {workflow_file.name}: {e}")
    
    def test_types_pyyaml_provides_type_hints(self):
        """Test that types-PyYAML is available for type checking."""
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        requirements = parse_requirements(REQUIREMENTS_FILE)
        package_names = [pkg for pkg, _ in requirements]
        
        assert 'types-PyYAML' in package_names, (
            "types-PyYAML should be in requirements-dev.txt for static type checking "
            "of code that uses PyYAML"
        )


class TestRequirementsMatchWorkflowNeeds:
    """Test that requirements-dev.txt contains packages needed by workflows."""
    
    def test_has_pytest_for_testing(self):
        """
        Verify that `pytest` is listed in the development requirements.
        
        Asserts that the `requirements-dev.txt` file exists and contains the package name `pytest` (case-insensitive), as workflows rely on pytest to run tests.
        """
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        requirements = parse_requirements(REQUIREMENTS_FILE)
        package_names = [pkg.lower() for pkg, _ in requirements]
        
        assert 'pytest' in package_names, (
            "pytest must be in requirements-dev.txt as workflows run pytest for testing"
        )
    
    def test_has_required_dev_tools(self):
        """Test that essential development tools are in requirements."""
        assert REQUIREMENTS_FILE.exists(), "requirements-dev.txt not found"
        
        requirements = parse_requirements(REQUIREMENTS_FILE)
        package_names = [pkg.lower() for pkg, _ in requirements]
        
        # Essential dev tools that should be present
        essential_tools = ['pytest', 'flake8', 'black', 'mypy']
        
        for tool in essential_tools:
            assert tool in package_names, (
                f"{tool} should be in requirements-dev.txt for code quality and testing"
            )
    
    def test_requirements_support_python_version_in_workflow(self):
        """
        Check that the pr-agent workflow's declared Python version (from a `setup-python` step) is at least Python 3.8.
        
        If the pr-agent workflow file is missing the test is skipped. The test locates the first `setup-python` step, reads its `python-version` value (if present) and asserts the major/minor version is 3.8 or greater; if no `python-version` is found the test makes no assertion.
        """
        pr_agent_file = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not pr_agent_file.exists():
            pytest.skip("pr-agent.yml not found")
        
        with open(pr_agent_file, 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Extract Python version from workflow
        python_version = None
        for job_name, job in workflow.get('jobs', {}).items():
            for step in job.get('steps', []):
                if 'setup-python' in step.get('uses', '').lower():
                    python_version = step.get('with', {}).get('python-version')
                    break
            if python_version:
                break
        
        if python_version:
            # Verify it's a supported version (3.8+)
            version_parts = str(python_version).split('.')
            if len(version_parts) >= 2:
                major = int(version_parts[0])
                minor = int(version_parts[1])
                
                assert (major > 3) or (major == 3 and minor >= 8), (
                    f"Workflow uses Python {python_version}, but requires 3.8+ for modern tooling"
                )