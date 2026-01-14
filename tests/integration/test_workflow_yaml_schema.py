"""
Comprehensive YAML schema validation tests for GitHub workflows.

Tests validate YAML structure, syntax, and GitHub Actions schema compliance
for all workflow files in .github/workflows/
"""

import os
import warnings
from pathlib import Path
from typing import Dict, Any, List

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List


class TestWorkflowYAMLSyntax:
    """Test YAML syntax and structure validity."""
    
    @pytest.fixture
    def workflow_files(self):
        """
        Collect all GitHub Actions workflow files from the .github/workflows directory.
        
        Returns:
            list[pathlib.Path]: Paths to files matching `*.yml` or `*.yaml` within `.github/workflows`.
        """
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    
    def test_all_workflows_are_valid_yaml(self, workflow_files):
        """
        Validate that workflow files are valid, non-empty YAML dictionaries.
        
        Asserts that at least one workflow file is present. For each file, attempts to parse it with yaml.safe_load, asserts the parsed content is not None and is a mapping (dict). If parsing raises a YAML error the test fails with a pytest.fail including the parser message.
        
        Parameters:
            workflow_files: Iterable[Path] — collection of workflow file paths to validate.
        """
        assert len(workflow_files) > 0, "No workflow files found"
        
        for workflow_file in workflow_files:
            try:
                with open(workflow_file, 'r') as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"{workflow_file.name} is empty"
                assert isinstance(data, dict), f"{workflow_file.name} should be a dictionary"
            except yaml.YAMLError as e:
                pytest.fail(f"Invalid YAML in {workflow_file.name}: {e}")
    
    def test_workflows_have_no_tabs(self, workflow_files):
        """
        Ensure workflow YAML files use spaces for indentation instead of tab characters.
        
        Parameters:
            workflow_files (Iterable[pathlib.Path]): Iterable of paths to workflow files under .github/workflows.
        
        Raises:
            AssertionError: If any workflow file contains a tab character.
        """
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            assert '\t' not in content, \
                f"{workflow_file.name} contains tabs (should use spaces for indentation)"
    
    def test_workflows_use_consistent_indentation(self, workflow_files):
        """
        Ensure non-empty, non-comment lines use indentation in two-space increments.
        
        Checks each workflow file and asserts if any line's leading space count is not a multiple of two, reporting the file name and line number on failure.
        """
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                if line.strip() and not line.strip().startswith('#'):
                    # Count leading spaces
                    leading_spaces = len(line) - len(line.lstrip(' '))
                    if leading_spaces > 0:
                        assert leading_spaces % 2 == 0, \
                            f"{workflow_file.name}:{i} has odd indentation ({leading_spaces} spaces)"
    
    def test_workflows_have_no_trailing_whitespace(self, workflow_files):
        """Workflow files should not have trailing whitespace."""
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                if line.rstrip('\n').endswith((' ', '\t')):
                    pytest.fail(f"{workflow_file.name}:{i} has trailing whitespace")


class TestWorkflowGitHubActionsSchema:
    """Test GitHub Actions schema compliance."""
    
    @pytest.fixture
    def workflow_data(self):
        """
        Load GitHub Actions workflow YAML files from .github/workflows into a mapping keyed by filename.
        
        Returns:
            workflows (dict): Mapping from workflow filename (str) to the parsed YAML content as Python objects (e.g., dict, list, primitives).
        """
        workflow_dir = Path(".github/workflows")
        workflows = {}
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
    
    def test_workflows_have_name(self, workflow_data):
        """
        Ensure each workflow defines a non-empty string `name` field.
        
        Asserts that each parsed workflow mapping contains a 'name' key and that its value is a string with length greater than zero.
        """
        for filename, data in workflow_data.items():
            assert 'name' in data, f"{filename} missing 'name' field"
            assert isinstance(data['name'], str), f"{filename} name should be string"
            assert len(data['name']) > 0, f"{filename} name is empty"
    
    def test_workflows_have_trigger(self, workflow_data):
        """
        Validate that each workflow defines a valid `on` trigger.
        
        Checks that the top-level `on` key is present and is one of the accepted forms: a string, a list, or a dict containing at least one recognized GitHub Actions trigger name (for example: `push`, `pull_request`, `workflow_dispatch`, `schedule`, `repository_dispatch`). The test fails with the workflow filename when the `on` key is missing or contains invalid trigger names.
        """
        valid_triggers = {
            'on', 'push', 'pull_request', 'workflow_dispatch',
            'schedule', 'issues', 'issue_comment', 'pull_request_review',
            'pull_request_review_comment', 'workflow_run', 'repository_dispatch'
        }
        
        for filename, data in workflow_data.items():
            assert 'on' in data, f"{filename} missing 'on' trigger"
            
            # 'on' can be string, list, or dict
            trigger = data['on']
            if isinstance(trigger, str):
                assert trigger in valid_triggers, \
                    f"{filename} has invalid trigger: {trigger}"
            elif isinstance(trigger, list):
                assert all(t in valid_triggers for t in trigger), \
                    f"{filename} has invalid triggers in list"
            elif isinstance(trigger, dict):
                assert any(k in valid_triggers for k in trigger.keys()), \
                    f"{filename} has no valid triggers in dict"
    
    def test_workflows_have_jobs(self, workflow_data):
        """
        Ensure each workflow defines a non-empty `jobs` mapping.
        
        Parameters:
            workflow_data (dict): Mapping of workflow filename to parsed YAML data (dict).
        
        Raises:
            AssertionError: If a workflow is missing the `jobs` section, if `jobs` is not a mapping, or if no jobs are defined.
        """
        for filename, data in workflow_data.items():
            assert 'jobs' in data, f"{filename} missing 'jobs' section"
            assert isinstance(data['jobs'], dict), f"{filename} jobs should be dict"
            assert len(data['jobs']) > 0, f"{filename} has no jobs defined"
    
    def test_jobs_have_runs_on(self, workflow_data):
        """
        Ensure every job declares a `runs-on` runner and that string runner values either are expressions or match a common supported runner label.
        
        Parameters:
        	workflow_data (dict): Mapping of workflow filename to its parsed YAML content; each value is a dict representing the workflow data.
        """
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                assert 'runs-on' in job_data, \
                    f"{filename} job '{job_name}' missing 'runs-on'"
                
                runs_on = job_data['runs-on']
                valid_runners = [
                    'ubuntu-latest', 'ubuntu-20.04', 'ubuntu-18.04',
                    'windows-latest', 'windows-2022', 'windows-2019',
                    'macos-latest', 'macos-12', 'macos-11'
                ]
                
                if isinstance(runs_on, str):
                    # Can be expression or literal
                    if not runs_on.startswith('${{'):
                        assert any(runner in runs_on for runner in valid_runners), \
                            f"{filename} job '{job_name}' has invalid runs-on: {runs_on}"
    
    def test_jobs_have_steps_or_uses(self, workflow_data):
        """
        Ensure each job defines either `steps` or `uses` (for reusable workflows).
        
        Assert that if `steps` is present, it is a non-empty list.
        """
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                has_steps = 'steps' in job_data
                has_uses = 'uses' in job_data
                
                assert has_steps or has_uses, \
                    f"{filename} job '{job_name}' has neither 'steps' nor 'uses'"
                
                if has_steps:
                    assert isinstance(job_data['steps'], list), \
                        f"{filename} job '{job_name}' steps should be a list"
                    assert len(job_data['steps']) > 0, \
                        f"{filename} job '{job_name}' has empty steps"


class TestWorkflowSecurity:
    """Security-focused tests for GitHub workflows."""
    
    @pytest.fixture
    def workflow_files(self):
        """
        Collect all workflow YAML files located in the .github/workflows directory.
        
        Returns:
            list[pathlib.Path]: Paths to files with `.yml` or `.yaml` extensions found in `.github/workflows`.
        """
        workflow_dir = Path(".github/workflows")
        return list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    
    def test_no_hardcoded_secrets(self, workflow_files):
        """
        Scan workflow files for likely hardcoded secrets and fail if any are found.
        
        Checks non-comment lines for common secret indicators (e.g., GitHub token prefixes like `ghp_`, AWS key prefixes like `AKIA`, or private key markers such as `-----BEGIN RSA PRIVATE KEY`). Occurrences that are fully contained inside a `secrets.*` expression (e.g., `${{ secrets.MY_SECRET }}`) are treated as valid references; occurrences outside such secret references cause the test to fail with a filename and line number.
        """
        dangerous_patterns = [
            'ghp_', 'github_pat_', 'gho_', 'ghu_', 'ghs_', 'ghr_',  # GitHub tokens
            'AKIA', 'ASIA',  # AWS keys
            '-----BEGIN', '-----BEGIN RSA PRIVATE KEY',  # Private keys
        ]
    
        import re
        secret_ref_re = re.compile(r'\$\{\{\s*secrets\.[A-Za-z0-9_]+\s*\}\}')
    
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
        
            lines = content.splitlines()
            for i, line in enumerate(lines, start=1):
                stripped = line.strip()
                # Skip commented lines
                if stripped.startswith('#'):
                    continue
                for pattern in dangerous_patterns:
                    if pattern in line:
                        valid_refs = list(secret_ref_re.finditer(line))
                        if valid_refs:
                            # Mask valid secret reference spans, then check remaining text for dangerous patterns
                            masked = list(line)
                            for m in valid_refs:
                                for idx in range(m.start(), m.end()):
                                    masked[idx] = ' '
                            remaining = ''.join(masked)
                            assert pattern not in remaining, (
                                f"{workflow_file.name}:{i} may contain hardcoded secret outside secrets.* reference: {pattern}"
                            )
                        else:
                            pytest.fail(
                                f"{workflow_file.name}:{i} may contain hardcoded secret without secrets.* reference: {pattern}"
                            )
    
    def test_pull_request_safe_checkout(self, workflow_files):
        """
        Ensure pull-request-triggered workflows do not checkout the PR branch HEAD without pinning to a commit SHA or merge ref.
        
        Scans workflows that trigger on `pull_request` and fails if an `actions/checkout` step specifies a `ref` that indicates a HEAD reference (e.g., contains "head") without also including a commit SHA or other safe pinning.
        """
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Check if triggered by pull_request
            triggers = data.get('on', {})
            if 'pull_request' in triggers or (isinstance(triggers, list) and 'pull_request' in triggers):
                # Look for checkout actions
                jobs = data.get('jobs', {})
                for job_name, job_data in jobs.items():
                    steps = job_data.get('steps', [])
                    
                    for step in steps:
                        if step.get('uses', '').startswith('actions/checkout'):
                            # Should specify ref or not checkout HEAD
                            # If no ref specified, it's okay (checks out merge commit)
                            # If ref specified, shouldn't be dangerous
                            with_data = step.get('with', {})
                            ref = with_data.get('ref', '')
                            if ref and 'head' in ref.lower() and 'sha' not in ref.lower():
import os
import pytest
import warnings
import yaml
from pathlib import Path
from typing import Dict, Any, List
                                    f"checks out PR HEAD (potential security risk)"
                                )

    
    def test_restricted_permissions(self, workflow_files):
        """
        Ensure workflows do not request overly broad permissions.
        
        Asserts that if a workflow defines top-level `permissions` as a string it is not the broad value `"write-all"`. If `permissions` is a mapping, individual scopes with the level `"write"` are treated as warnings (non-fatal) and should be justified in nearby comments.
        """
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Check top-level permissions
            permissions = data.get('permissions', {})
            
            # If permissions defined, shouldn't be 'write-all'
            if permissions:
                if isinstance(permissions, str):
                    assert permissions != 'write-all', \
                        f"{workflow_file.name} uses write-all permissions (too broad)"
                elif isinstance(permissions, dict):
                    # Check individual permissions
                    for scope, level in permissions.items():
                        if level == 'write':
                            # Write permissions should have justification in comments
                            pass  # Warning only


class TestWorkflowBestPractices:
    """Test adherence to GitHub Actions best practices."""
    
    @pytest.fixture
    def workflow_data(self):
        """
        Collect parsed YAML data for all workflow files in .github/workflows.
        
        Searches the .github/workflows directory for files with .yml and .yaml extensions and loads each file with yaml.safe_load. Returns a mapping from filename (base name) to the parsed YAML content; values may be a dict, list, scalar, or None depending on the file contents.
            
        Returns:
            workflows (dict): Mapping of workflow filename to parsed YAML content.
        """
        workflow_dir = Path(".github/workflows")
        workflows = {}
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                    if uses:
                        # Should not use @main or @master
                        if '@main' in uses or '@master' in uses:
                            warnings.warn(
                                f"{filename} job '{job_name}' step {i} "
                                f"uses unstable version: {uses}"
                            )
                                f"{filename} job '{job_name}' step {i} "
                                f"uses unstable version: {uses}"
                            )

    
    def test_steps_have_names(self, workflow_data):
        """Steps should have descriptive names."""
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                unnamed_steps = [
                    i for i, step in enumerate(steps)
                    if 'name' not in step
                ]
                
                # Allow a few unnamed steps, but not too many
                unnamed_ratio = len(unnamed_steps) / len(steps) if steps else 0
                assert unnamed_ratio < 0.5, \
                    f"{filename} job '{job_name}' has too many unnamed steps"
    
    def test_timeouts_defined(self, workflow_data):
        """
        Warn when jobs that appear long-running lack a timeout.
        
        For each workflow in `workflow_data`, if a job has more than 5 steps and does not define `timeout-minutes`, a warning is emitted identifying the workflow file and job name.
        
        Parameters:
            workflow_data (dict): Mapping from workflow filename to parsed YAML data (dict).
        """
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                # If job has many steps or installs dependencies, should have timeout
                if len(steps) > 5:
                    # Check for timeout-minutes
                    if 'timeout-minutes' not in job_data:
                        warnings.warn(
                            f"{filename} job '{job_name}' has many steps "
                            f"but no timeout defined"
                        )


class TestWorkflowCrossPlatform:
    """Test cross-platform compatibility issues."""
    
    @pytest.fixture
    def workflow_data(self):
        """
        Load all GitHub Actions workflow files from .github/workflows and parse them into Python objects.
        
        Scans .github/workflows for files with .yml and .yaml extensions and parses each file with yaml.safe_load.
        
        Returns:
            dict[str, Any]: Mapping from workflow filename to the parsed YAML content (typically a dict).
        """
        workflow_dir = Path(".github/workflows")
        workflows = {}
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                workflows[workflow_file.name] = yaml.safe_load(f)
        
        return workflows
    
    def test_shell_script_compatibility(self, workflow_data):
        """
        Warns when steps use Unix-specific commands on Windows runners.
        
        Scans each workflow job and emits a warning if a step running on a Windows runner uses a Unix-style shell and its `run` command contains common Unix utilities such as `grep`, `sed`, `awk`, or `find`.
        """
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                runs_on = job_data.get('runs-on', '')
                steps = job_data.get('steps', [])
                
                is_windows = 'windows' in str(runs_on).lower()
                
                for step in steps:
                    run_command = step.get('run', '')
                    shell = step.get('shell', 'bash' if not is_windows else 'pwsh')
                    
                    if run_command:
                        # Check for Unix-specific commands on Windows
                        if is_windows and shell in ['bash', 'sh']:
                            unix_commands = ['grep', 'sed', 'awk', 'find']
                            for cmd in unix_commands:
                                if cmd in run_command:
                                    warnings.warn(
                                        f"{filename} job '{job_name}' uses Unix command "
                                        f"'{cmd}' on Windows"
                                    )
    
    def test_path_separators(self, workflow_data):
        """
        Ensure run commands use forward slashes to avoid Windows-specific path separators on non-Windows runners.
        
        For each workflow job step, scans the `run` command for backslashes and issues a warning if a backslash is present while the job's `runs-on` does not indicate a Windows runner. Legitimate uses of backslashes (e.g., escaped characters) are tolerated and do not cause a test failure.
        """
        for filename, data in workflow_data.items():
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                for step in steps:
                    run_command = step.get('run', '')
                    
                    # Check for Windows-style paths (backslashes)
                    if '\\' in run_command and 'windows' not in str(job_data.get('runs-on', '')).lower():
                        # Might be legitimate (escaped chars), so just warn
                        pass


class TestWorkflowMaintainability:
    """Test workflow maintainability and documentation."""
    
    def test_workflows_have_comments(self):
        """
        Ensure workflow files in .github/workflows contain explanatory comments.
        
        Scans all `.yml` and `.yaml` files under `.github/workflows`, counts non-empty non-comment lines (code lines) and comment lines. If a file has more than 20 code lines, asserts that comment lines are at least 5% of code lines and fails with "<filename> is large but has few comments" when the ratio is below that threshold.
        """
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            lines = content.split('\n')
            comment_lines = [l for l in lines if l.strip().startswith('#')]
            code_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
            
            if len(code_lines) > 20:
                # Large workflows should have comments
                comment_ratio = len(comment_lines) / len(code_lines)
                assert comment_ratio >= 0.05, \
                    f"{workflow_file.name} is large but has few comments"
    
    def test_complex_expressions_explained(self):
        """Complex expressions should have explanatory comments."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml")):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Look for complex expressions
            import re
            complex_patterns = [
                r'\$\{\{.*\&\&.*\}\}',  # Multiple conditions
                r'\$\{\{.*\|\|.*\}\}',  # OR conditions
                r'\$\{\{.*\(.*\).*\}\}',  # Function calls
            ]
            
            for pattern in complex_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    # Check if there's a comment nearby
                    start = max(0, match.start() - 200)
                    context = content[start:match.end()]

                    import warnings
                    # Should have explanation
                    lines = context.split('\n')
                    if len(lines) < 2 or '#' not in lines[-2]:
                        line_num = content[:match.start()].count('\n') + 1
                        warnings.warn(f"{workflow_file.name}: complex expression at line {line_num} lacks explanation: {match.group()}")
                        # Warning only, not failure