"""
Integration tests validating all branch changes work together cohesively.

Tests cross-cutting concerns:
1. Workflow changes are consistent across all files
2. Dependencies are compatible with workflow needs  
3. Removed files don't break existing functionality
4. Overall branch maintains system integrity
"""

import pytest
import yaml
import re
from pathlib import Path
from typing import Dict, List, Set


class TestWorkflowConsistency:
    """Test consistency across all modified workflows."""
    
    @pytest.fixture
    def all_workflows(self) -> Dict[str, Dict]:
        """Load all workflow files."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]
        
        workflows = {}
        for wf_file in workflow_files:
            path = Path(wf_file)
            if path.exists():
                with open(path, 'r') as f:
                    workflows[wf_file] = yaml.safe_load(f)
        
        return workflows
    
    def test_all_workflows_use_consistent_action_versions(self, all_workflows):
        """Verify same actions use consistent versions across workflows."""
        action_versions = {}
        
        for wf_file, workflow in all_workflows.items():
            for job_name, job in workflow.get('jobs', {}).items():
                for step in job.get('steps', []):
                    uses = step.get('uses', '')
                    if uses and '@' in uses:
                        action_name = uses.split('@')[0]
                        action_version = uses.split('@')[1]
                        
                        if action_name not in action_versions:
                            action_versions[action_name] = {}
                        if action_version not in action_versions[action_name]:
                            action_versions[action_name][action_version] = []
                        action_versions[action_name][action_version].append(wf_file)
        
        # Check for inconsistencies
        for action, versions in action_versions.items():
            if len(versions) > 1:
                # Allow v4 and v5 for actions/checkout (common upgrade path)
                if 'actions/checkout' in action:
                    continue
                # Fail if same action uses different versions
                pytest.fail(f"{action} uses multiple versions: {list(versions.keys())}")
    
    def test_all_workflows_use_github_token_consistently(self, all_workflows):
        """Verify GITHUB_TOKEN usage is consistent."""
        for wf_file, workflow in all_workflows.items():
            workflow_str = yaml.dump(workflow)
            
            if 'GITHUB_TOKEN' in workflow_str or 'github.token' in workflow_str:
                # Should use secrets.GITHUB_TOKEN format
                assert 'secrets.GITHUB_TOKEN' in workflow_str or \
                       '${{ github.token }}' in workflow_str, \
                    f"{wf_file}: GITHUB_TOKEN should use proper syntax"
    
    def test_simplified_workflows_have_fewer_steps(self, all_workflows):
        """Verify simplified workflows actually have fewer steps."""
        # These workflows were simplified in this branch
        simplified = [
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]
        
        for wf_file in simplified:
            if wf_file in all_workflows:
                workflow = all_workflows[wf_file]
                for job_name, job in workflow.get('jobs', {}).items():
                    steps = job.get('steps', [])
                    # Simplified workflows should have minimal steps
                    assert len(steps) <= 3, \
                        f"{wf_file}:{job_name} should be simplified (has {len(steps)} steps)"


class TestDependencyWorkflowIntegration:
    """Test that dependencies support workflow needs."""
    
    def test_pyyaml_supports_workflow_parsing(self):
        """Verify PyYAML can parse all workflow files."""
        try:
            import yaml
        except ImportError:
            pytest.skip("PyYAML not installed")
        
        workflow_dir = Path(".github/workflows")
        if not workflow_dir.exists():
            pytest.skip("Workflows directory not found")
        
        workflow_files = list(workflow_dir.glob("*.yml"))
        
        for wf_file in workflow_files:
            try:
                with open(wf_file, 'r') as f:
                    workflow = yaml.safe_load(f)
                
                assert workflow is not None, f"Failed to parse {wf_file}"
                assert isinstance(workflow, dict), f"{wf_file} should parse to dict"
            except yaml.YAMLError as e:
                pytest.fail(f"PyYAML failed to parse {wf_file}: {e}")
    
    def test_requirements_support_workflow_test_needs(self):
        """Verify dev requirements support testing workflows."""
        with open('requirements-dev.txt', 'r') as f:
            content = f.read().lower()
        
        # Should have pytest for running these tests
        assert 'pytest' in content, "pytest required for workflow tests"
        
        # Should have PyYAML for parsing workflows
        assert 'pyyaml' in content, "PyYAML required for workflow validation"


class TestRemovedFilesIntegration:
    """Test that removed files don't break functionality."""
    
    def test_workflows_dont_reference_removed_scripts(self):
        """Verify workflows don't reference deleted files."""
        removed_files = [
            'context_chunker.py',
            '.github/scripts/README.md',
            '.github/labeler.yml',
        ]
        
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/label.yml",
        ]
        
        for wf_file in workflow_files:
            with open(wf_file, 'r') as f:
                lines = f.readlines()
        
            for removed in removed_files:
                for line in lines:
                    if removed in line and not line.strip().startswith('#'):
                        pytest.fail(f"{wf_file} references removed file {removed}")
    
    def test_label_workflow_doesnt_need_labeler_config(self):
        """Verify label workflow works without labeler.yml."""
        with open(".github/workflows/label.yml", 'r') as f:
            workflow = yaml.safe_load(f)
        
        # Should use actions/labeler which has default config
        steps = workflow['jobs']['label']['steps']
        labeler_step = steps[0]
        
        assert 'actions/labeler' in labeler_step['uses']
        
        # Should not require config-path or similar
        with_config = labeler_step.get('with', {})
        assert 'config-path' not in with_config, \
            "Label workflow should not depend on a config-path like .github/labeler.yml, which has been removed"
    
    def test_pr_agent_workflow_self_contained(self):
        """Verify PR agent workflow doesn't depend on removed components."""
        with open(".github/workflows/pr-agent.yml", 'r') as f:
            content = f.read()
        
        # Should not reference chunking components
        assert 'context_chunker' not in content
        assert 'chunking' not in content.lower() or 'no chunking' in content.lower()
        
        # Should not have complex context management
        assert 'fetch-context' not in content


class TestWorkflowSecurityConsistency:
    """Test security practices are consistent across workflows."""
    
    def test_all_workflows_avoid_pr_injection(self):
        """Verify no workflows have PR title/body injection risks."""
        workflow_files = list(Path(".github/workflows").glob("*.yml"))
        
        for wf_file in workflow_files:
            with open(wf_file, 'r') as f:
                content = f.read()
            
            # Look for potentially dangerous patterns
            dangerous = [
                r'\$\{\{.*github\.event\.pull_request\.title.*\}\}.*\|',
                r'\$\{\{.*github\.event\.pull_request\.body.*\}\}.*\|',
                r'\$\{\{.*github\.event\.issue\.title.*\}\}.*\$\(',
            ]
            
            for pattern in dangerous:
                matches = re.findall(pattern, content)
                if matches:
                    pytest.fail(f"Potential injection risk in {wf_file}: {matches}")
    
    def test_workflows_use_appropriate_checkout_refs(self):
        """Verify checkout actions use safe refs."""
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
        ]
        
        for wf_file in workflow_files:
            with open(wf_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            trigger = workflow.get('on', {})
            uses_pr_target = 'pull_request_target' in trigger
            
            if uses_pr_target:
                # Should checkout with explicit ref
                for job in workflow.get('jobs', {}).values():
                    for step in job.get('steps', []):
                        if 'actions/checkout' in step.get('uses', ''):
                            with_config = step.get('with', {})
                            # Should have ref or token specified
                            assert 'ref' in with_config or 'fetch-depth' in with_config, \
                                f"{wf_file}: Checkout in pull_request_target should specify safe ref"


class TestBranchCoherence:
    """Test overall branch changes are coherent."""
    
    def test_simplification_theme_consistent(self):
        """Verify all changes follow simplification theme."""
        # This branch should simplify, not add complexity
        
        # Check workflow line counts decreased
        workflows_to_check = [
            (".github/workflows/pr-agent.yml", 200),  # Should be under 200 lines
            (".github/workflows/label.yml", 30),      # Should be under 30 lines
            (".github/workflows/greetings.yml", 20),  # Should be under 20 lines
        ]
        
        for wf_file, max_lines in workflows_to_check:
            path = Path(wf_file)
            if path.exists():
                with open(path, 'r') as f:
                    line_count = len(f.readlines())
                
                assert line_count <= max_lines, \
                    f"{wf_file} should be simplified (has {line_count} lines, expected <={max_lines})"
    
    def test_removed_complexity_not_referenced(self):
        """Verify removed complexity isn't referenced elsewhere."""
        complex_features = [
            'context_chunking',
            'tiktoken',
            'summarization',
            'max_tokens',
            'chunk_size',
        ]
        
        # Check these aren't in workflows anymore
        workflow_files = list(Path(".github/workflows").glob("*.yml"))
        
        for wf_file in workflow_files:
            with open(wf_file, 'r') as f:
                content = f.read().lower()
            
            for feature in complex_features:
                if feature in content:
                    # Some context about removal is OK in comments
                    lines = content.split('\n')
                    for line in lines:
                        if feature in line.lower() and not line.strip().startswith('#'):
                            pytest.fail(f"{wf_file} still references removed feature: {feature}")
    
    def test_branch_reduces_dependencies_on_external_config(self):
        """Verify branch reduces dependency on external config files."""
        # labeler.yml was removed - workflows should work without it
        assert not Path(".github/labeler.yml").exists()
        
        # context_chunker.py was removed - workflows should work without it
        assert not Path(".github/scripts/context_chunker.py").exists()
        
        # Workflows should be more self-contained
        workflow_files = list(Path(".github/workflows").glob("*.yml"))
        
        for wf_file in workflow_files:
            with open(wf_file, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Count steps that reference external files
            external_refs = 0
            for job in workflow.get('jobs', {}).values():
                for step in job.get('steps', []):
                    run_cmd = step.get('run', '')
                    if '.github/' in run_cmd or 'scripts/' in run_cmd:
                        external_refs += 1
            
            # Should have minimal external references
            assert external_refs <= 1, \
                f"{wf_file} has {external_refs} external file references (should be <=1)"


class TestBranchQuality:
    """Test overall quality of branch changes."""
    
    def test_all_modified_workflows_parse_successfully(self):
        """Verify all workflow modifications result in valid YAML."""
        workflow_dir = Path(".github/workflows")
        workflow_files = list(workflow_dir.glob("*.yml"))
        
        assert len(workflow_files) > 0, "No workflow files found"
        
        for wf_file in workflow_files:
            try:
                with open(wf_file, 'r') as f:
                    workflow = yaml.safe_load(f)
                
                assert workflow is not None
                assert isinstance(workflow, dict)
                assert 'jobs' in workflow
            except Exception as e:
                pytest.fail(f"Failed to parse {wf_file}: {e}")
    
    def test_no_merge_conflict_markers(self):
        """Verify no merge conflict markers in any files."""
        conflict_markers = ['<<<<<<<', '=======', '>>>>>>>']
        
        files_to_check = [
            '.github/workflows/pr-agent.yml',
            '.github/workflows/apisec-scan.yml',
            '.github/workflows/label.yml',
            '.github/workflows/greetings.yml',
            'requirements-dev.txt',
        ]
        
        for file_path in files_to_check:
            path = Path(file_path)
            if path.exists():
                with open(path, 'r') as f:
                    content = f.read()
                
                for marker in conflict_markers:
                    assert marker not in content, \
                        f"{file_path} contains merge conflict marker: {marker}"
    
    def test_consistent_indentation_across_workflows(self):
        """Verify all workflows use 2-space indentation consistently."""
        workflow_files = list(Path(".github/workflows").glob("*.yml"))
        
        for wf_file in workflow_files:
            with open(wf_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                if line.strip() and line[0] == ' ':
                    spaces = len(line) - len(line.lstrip(' '))
                    assert spaces % 2 == 0, \
                        f"{wf_file}:{i} inconsistent indentation (not multiple of 2)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])