"""
Comprehensive YAML configuration validation tests.

Validates:
1. YAML syntax and structure
2. Schema compliance
3. Edge cases and boundary conditions
4. Configuration consistency
5. Default value handling
"""

import pytest
import yaml
from pathlib import Path
from typing import Dict, Any, List
import re


class TestYAMLSyntaxAndStructure:
    """Tests for YAML syntax and structural validity."""
    
    def test_all_yaml_files_parse_successfully(self):
        """Verify all YAML files have valid syntax."""
        yaml_files = []
        
        # Find all YAML files in .github
        for yaml_file in Path(".github").rglob("*.yml"):
            yaml_files.append(yaml_file)
        for yaml_file in Path(".github").rglob("*.yaml"):
            yaml_files.append(yaml_file)
        
        parse_errors = []
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, 'r') as f:
                    yaml.safe_load(f)
            except yaml.YAMLError as e:
                parse_errors.append(f"{yaml_file}: {str(e)}")
        
        assert len(parse_errors) == 0, f"YAML parse errors:\n" + "\n".join(parse_errors)
    
    def test_yaml_files_use_consistent_indentation(self):
        """Ensure YAML files use consistent 2-space indentation, respecting block scalars."""
        yaml_files = list(Path(".github").rglob("*.yml")) + list(Path(".github").rglob("*.yaml"))
        indentation_errors = []

        for yaml_file in yaml_files:
            try:
                content = Path(yaml_file).read_text(encoding="utf-8")
            except Exception as e:
                indentation_errors.append(f"{yaml_file}: unable to read file: {e}")
                continue

            lines = content.split('\n')
            in_block_scalar = False
            block_scalar_indent = None

            for line_no, line in enumerate(lines, 1):
                stripped = line.lstrip(' ')
                leading_spaces = len(line) - len(stripped)

                # Skip empty lines and full-line comments
                if not stripped or stripped.startswith('#'):
                    continue

                # If currently inside a block scalar, continue until indentation returns
                if in_block_scalar:
                    # Exit block scalar when indentation is less than or equal to the scalar's parent indent
                    if leading_spaces <= block_scalar_indent:
                        in_block_scalar = False
                        block_scalar_indent = None
                    else:
                        # Still inside scalar; skip indentation checks
                        continue

                # Detect start of block scalars (| or > possibly with chomping/indent indicators)
                # Example: key: |-, key: >2, key: |+
                if re.search(r':\s*[|>](?:[+-]|\d+)?', line):
                    in_block_scalar = True
                    block_scalar_indent = leading_spaces
                    continue

                # Only check indentation on lines that begin with spaces (i.e., are indented content)
                if line[0] == ' ' and not line.startswith('  ' * (leading_spaces // 2 + 1) + '- |'):
                    if leading_spaces % 2 != 0:
                        indentation_errors.append(
                            f"{yaml_file} line {line_no}: Use 2-space indentation, found {leading_spaces} spaces"
                        )

            # Reset flags per file (handled by reinitialization each loop)

        assert not indentation_errors, "Indentation errors found:\n" + "\n".join(indentation_errors)
    
    def test_no_duplicate_keys_in_yaml(self):
        """Verify no duplicate keys exist in YAML files using a parser that detects duplicates."""
        try:
            from ruamel.yaml import YAML
        except ImportError:
            pytest.skip("ruamel.yaml not installed; skip strict duplicate key detection")
    
        yaml_files = list(Path(".github").rglob("*.yml")) + list(Path(".github").rglob("*.yaml"))
        parser = YAML(typ="safe")
        parse_errors = []
    
        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r") as f:
                    parser.load(f)
            except Exception as e:
                parse_errors.append(f"{yaml_file}: {e}")
    
        assert not parse_errors, "Duplicate keys or YAML errors detected:\n" + "\n".join(parse_errors)

class TestWorkflowSchemaCompliance:
    """Tests for GitHub Actions workflow schema compliance."""
    
    @pytest.fixture
    def all_workflows(self) -> List[Dict[str, Any]]:
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflows.append({
                    'path': workflow_file,
                    'content': yaml.safe_load(f)
                })
        return workflows
    
    def test_workflows_have_required_top_level_keys(self, all_workflows):
        """Verify workflows have all required top-level keys."""
        required_keys = ['name', 'jobs']
        
        for workflow in all_workflows:
            for key in required_keys:
                assert key in workflow['content'], \
                    f"Workflow {workflow['path']} missing required key: {key}"
    
    def test_workflow_triggers_valid_format(self, all_workflows):
        """Verify workflow triggers use valid format."""
        for workflow in all_workflows:
            # Check for 'on' or '"on"' key
            has_trigger = 'on' in workflow['content']
            assert has_trigger, f"Workflow {workflow['path']} missing trigger ('on' key)"
            
            triggers = workflow['content'].get('on') or workflow['content'].get('"on"')
            
            # Triggers can be: string, list, or dict
            assert isinstance(triggers, (str, list, dict)), \
                f"Workflow {workflow['path']} has invalid trigger format"
    
    def test_job_definitions_valid(self, all_workflows):
        """Verify job definitions follow valid schema."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            
            assert len(jobs) > 0, f"Workflow {workflow['path']} has no jobs defined"
            
            for job_id, job_config in jobs.items():
                # Each job must have runs-on or uses
                has_runs_on = 'runs-on' in job_config
                has_uses = 'uses' in job_config  # For reusable workflows
                
                assert has_runs_on or has_uses, \
                    f"Job '{job_id}' in {workflow['path']} missing 'runs-on' or 'uses'"
                
                # If has steps, must be a list
                if 'steps' in job_config:
                    assert isinstance(job_config['steps'], list), \
                        f"Job '{job_id}' steps must be a list in {workflow['path']}"
    
    def test_step_definitions_valid(self, all_workflows):
        """Verify step definitions follow valid schema."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            
            for job_id, job_config in jobs.items():
                steps = job_config.get('steps', [])
                
                for step_idx, step in enumerate(steps):
                    # Each step must have 'uses' or 'run'
                    has_uses = 'uses' in step
                    has_run = 'run' in step
                    
                    assert has_uses or has_run, \
                        f"Step {step_idx} in job '{job_id}' of {workflow['path']} " \
                        f"must have 'uses' or 'run'"
                    
                    # Steps should not have both uses and run
                    assert not (has_uses and has_run), \
                        f"Step {step_idx} in job '{job_id}' of {workflow['path']} " \
                        f"cannot have both 'uses' and 'run'"


class TestConfigurationEdgeCases:
    """Tests for edge cases in configuration files."""
    
    def test_pr_agent_config_handles_missing_sections_gracefully(self):
        """Verify PR agent config has all expected sections."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Should have main sections
        expected_sections = ['agent', 'monitoring', 'limits']
        for section in expected_sections:
            assert section in config, f"Missing section: {section}"
    
    def test_numeric_values_in_config_are_valid(self):
        """Verify numeric configuration values are reasonable."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check monitoring interval
        monitoring = config.get('monitoring', {})
        if 'check_interval' in monitoring:
            interval = monitoring['check_interval']
            assert isinstance(interval, int), "check_interval should be integer"
            assert 1 <= interval <= 60, "check_interval should be 1-60 minutes"
        
        # Check rate limits
        limits = config.get('limits', {})
        if 'rate_limit_requests' in limits:
            rate_limit = limits['rate_limit_requests']
            assert isinstance(rate_limit, int), "rate_limit_requests should be integer"
            assert 1 <= rate_limit <= 1000, "rate_limit_requests should be reasonable"
    
    def test_version_strings_follow_semver(self):
        """Verify version strings follow semantic versioning."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        agent_config = config.get('agent', {})
        if 'version' in agent_config:
            version = agent_config['version']
            # Should match semver pattern: X.Y.Z
            assert re.match(r'^\d+\.\d+\.\d+$', version), \
                f"Version should follow semver (X.Y.Z): {version}"
    
    def test_empty_or_null_values_handled(self):
        """Verify configuration handles empty/null values."""
        yaml_files = list(Path(".github").rglob("*.yml"))
        
        for yaml_file in yaml_files:
            with open(yaml_file, 'r') as f:
                content = yaml.safe_load(f)
            
            # Check for null values in critical places
            def check_nulls(obj, path=""):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        current_path = f"{path}.{key}" if path else key
                        
                        # Critical keys should not be null
                        critical_keys = ['name', 'runs-on', 'uses', 'run']
                        if key in critical_keys:
                            assert value is not None, \
                                f"Critical key '{current_path}' is null in {yaml_file}"
                        
                        check_nulls(value, current_path)
                elif isinstance(obj, list):
                    for idx, item in enumerate(obj):
                        check_nulls(item, f"{path}[{idx}]")
            
            check_nulls(content)


class TestConfigurationConsistency:
    """Tests for configuration consistency across files."""
    
    def test_python_version_consistent_across_workflows(self):
        """Verify Python version is consistent across all workflows."""
        workflow_dir = Path(".github/workflows")
        python_versions = {}
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            for job_id, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step in steps:
                    if 'actions/setup-python' in step.get('uses', ''):
                        version = step.get('with', {}).get('python-version')
                        if version:
                            python_versions[workflow_file.name] = version
        
        # All should use same Python version
        if python_versions:
            unique_versions = set(python_versions.values())
            assert len(unique_versions) == 1, \
                f"Inconsistent Python versions across workflows: {python_versions}"
    
    def test_node_version_consistent_across_workflows(self):
        """Verify Node.js version is consistent across all workflows."""
        workflow_dir = Path(".github/workflows")
        node_versions = {}
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            for job_id, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step in steps:
                    if 'actions/setup-node' in step.get('uses', ''):
                        version = step.get('with', {}).get('node-version')
                        if version:
                            node_versions[workflow_file.name] = str(version)
        
        # All should use same Node version
        if node_versions:
            unique_versions = set(node_versions.values())
            assert len(unique_versions) == 1, \
                f"Inconsistent Node versions across workflows: {node_versions}"
    
    def test_checkout_action_version_consistent(self):
        """Verify checkout action version is consistent."""
        workflow_dir = Path(".github/workflows")
        checkout_versions = {}
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            for job_id, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step in steps:
                    uses = step.get('uses', '')
                    if 'actions/checkout@' in uses:
                        version = uses.split('@')[1]
                        checkout_versions[workflow_file.name] = version
        
        # Should be consistent
        if checkout_versions:
            unique_versions = set(checkout_versions.values())
            # Allow v3 and v4, but should be mostly consistent
            assert len(unique_versions) <= 2, \
                f"Too many different checkout versions: {checkout_versions}"


class TestDefaultValueHandling:
    """Tests for default value handling in configurations."""
    
    def test_missing_optional_fields_have_defaults(self):
        """Verify system handles missing optional fields gracefully."""
        config_path = Path(".github/pr-agent-config.yml")
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
        
        # These fields should have defaults if not specified
        agent_config = config.get('agent', {})
        
        # If enabled is not specified, should default to true
        if 'enabled' in agent_config:
            assert isinstance(agent_config['enabled'], bool)
    
    def test_workflow_timeout_defaults(self):
        """Verify workflow timeout settings are reasonable or use defaults."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            jobs = workflow.get('jobs', {})
            for job_id, job_config in jobs.items():
                if 'timeout-minutes' in job_config:
                    timeout = job_config['timeout-minutes']
                    assert isinstance(timeout, int), \
                        f"Timeout should be integer in {workflow_file} job '{job_id}'"
                    assert 1 <= timeout <= 360, \
                        f"Timeout should be 1-360 minutes in {workflow_file} job '{job_id}'"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])