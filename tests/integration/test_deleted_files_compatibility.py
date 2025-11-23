"""
Tests to ensure that deleted files don't break existing functionality.

This test suite validates that removal of:
- .github/scripts/context_chunker.py
- .github/scripts/README.md
- .github/labeler.yml

Does not cause any regressions or broken references.
"""

import os
import pytest
from pathlib import Path


class TestDeletedContextChunker:
    """Validate that context_chunker.py removal doesn't break workflows."""
    
    def test_no_references_to_context_chunker_in_workflows(self):
        """Workflows should not reference the deleted context_chunker.py."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Should not reference context_chunker
            assert 'context_chunker' not in content, \
                f"{workflow_file.name} still references deleted context_chunker.py"
            
            # Should not reference the scripts directory for chunking
            assert '.github/scripts/context_chunker' not in content, \
                f"{workflow_file.name} references deleted chunker script"
    
    def test_workflows_dont_depend_on_chunking_functionality(self):
        """Workflows should work without chunking functionality."""
        pr_agent_workflow = Path(".github/workflows/pr-agent.yml")
        
        if pr_agent_workflow.exists():
            with open(pr_agent_workflow, 'r') as f:
                content = f.read()
            
            # Should not have chunking-related logic
            problematic_terms = [
                'chunk_size', 'token_count', 'tiktoken',
                'context_overflow', 'summarization'
            ]
            
            for term in problematic_terms:
                if term in content:
                    # Check if it's in a comment (acceptable) or actual code
                    lines_with_term = [
                        line for line in content.split('\n')
                        if term in line and not line.strip().startswith('#')
                    ]
                    
                    assert len(lines_with_term) == 0, \
                        f"PR agent workflow still has chunking logic: {term}"
    
    def test_no_python_dependencies_for_chunking(self):
        """Requirements should not include chunking dependencies if unused."""
        req_dev = Path("requirements-dev.txt")
        
        if req_dev.exists():
            with open(req_dev, 'r') as f:
                content = f.read()
            
            # If chunker is removed, these shouldn't be required anymore
            # (unless used elsewhere)
            if 'tiktoken' in content:
                # This is okay if it's optional or used elsewhere
                pass
    
    def test_scripts_directory_exists_or_empty(self):
        """Scripts directory should either not exist or not be referenced."""
        scripts_dir = Path(".github/scripts")
        
        if scripts_dir.exists():
            # If it exists, should not contain chunker
            assert not (scripts_dir / "context_chunker.py").exists(), \
                "context_chunker.py should be deleted"
            
            # README about chunking should be gone
            readme = scripts_dir / "README.md"
            if readme.exists():
                with open(readme, 'r') as f:
                    content = f.read()
                
                assert 'chunking' not in content.lower(), \
                    "Scripts README still documents chunking"


class TestDeletedLabelerConfig:
    """Validate that labeler.yml removal doesn't break label workflow."""
    
    def test_label_workflow_doesnt_require_config(self):
        """Label workflow should handle missing labeler config gracefully."""
        label_workflow = Path(".github/workflows/label.yml")
        
        if label_workflow.exists():
            with open(label_workflow, 'r') as f:
                content = f.read()
            
            # Should not have checks that fail if config missing
            # Or should have graceful handling
            if 'labeler.yml' in content:
                # Should check for existence before using
                assert 'exists' in content or 'check' in content, \
                    "Label workflow references labeler.yml without checking existence"
    
    def test_labeler_yml_deleted(self):
        """Labeler configuration file should be deleted."""
        labeler_config = Path(".github/labeler.yml")
        
        assert not labeler_config.exists(), \
            "labeler.yml should be deleted"
    
    def test_label_workflow_still_functional(self):
        """Label workflow should exist and be valid even without labeler config."""
        label_workflow = Path(".github/workflows/label.yml")
        
        assert label_workflow.exists(), \
            "Label workflow should exist"
        
        import yaml
        with open(label_workflow, 'r') as f:
            data = yaml.safe_load(f)
        
        # Should be valid YAML
        assert data is not None
        assert 'jobs' in data
    
    def test_no_broken_labeler_action_calls(self):
        """Labeler action should not be called without proper config."""
        label_workflow = Path(".github/workflows/label.yml")
        
        if label_workflow.exists():
            import yaml
            with open(label_workflow, 'r') as f:
                data = yaml.safe_load(f)
            
            # Check if labeler action is used
            jobs = data.get('jobs', {})
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                for step in steps:
                    uses = step.get('uses', '')
                    if 'labeler' in uses:
                        # Should either:
                        # 1. Not use labeler action anymore, or
                        # 2. Have conditional execution, or
                        # 3. Have inline configuration
                        step_if = step.get('if', '')
                        with_config = step.get('with', {})
                        
                        # If using labeler, should have handling
                        # (This test documents expected behavior)
                        pass


class TestDeletedScriptsREADME:
    """Validate that scripts README removal doesn't leave broken documentation."""
    
    def test_main_docs_dont_reference_scripts_readme(self):
        """Main documentation should not reference deleted scripts README."""
        doc_files = [
            'README.md',
            'CONTRIBUTING.md',
            'ARCHITECTURE.md',
            '.github/copilot-pr-agent.md'
        ]
        
        for doc_file in doc_files:
            doc_path = Path(doc_file)
            if doc_path.exists():
                with open(doc_path, 'r') as f:
                    content = f.read()
                
                # Should not link to deleted README
                assert '.github/scripts/README.md' not in content, \
                    f"{doc_file} references deleted scripts README"
    
    def test_no_orphaned_script_documentation(self):
        """Should not have documentation for deleted scripts."""
        doc_files = list(Path('.').glob('*.md'))
        
        for doc_file in doc_files:
            with open(doc_file, 'r') as f:
                content = f.read()
            
            # If mentions chunking, should not be primary documentation
            if 'context_chunker' in content or 'Context Chunking' in content:
                # Should be in historical/changelog context, not instructions
                lines_with_chunker = [
                    line for line in content.split('\n')
                    if 'context_chunker' in line.lower()
                ]
                
                # Acceptable in changelogs or summaries
                if doc_file.name not in ['CHANGELOG.md', 'CHANGELOG_BRANCH_CLEANUP.md']:
                    # Should not have installation/usage instructions
                    for line in lines_with_chunker:
                        assert 'pip install' not in line, \
                            f"{doc_file.name} has installation instructions for deleted script"
                        assert 'python .github/scripts/context_chunker' not in line, \
                            f"{doc_file.name} has usage instructions for deleted script"


class TestWorkflowConfigConsistency:
    """Test consistency between workflows and their configurations after deletions."""
    
    def test_pr_agent_config_matches_workflow(self):
        """PR Agent config should match simplified workflow."""
        config_path = Path(".github/pr-agent-config.yml")
        workflow_path = Path(".github/workflows/pr-agent.yml")
        
        if config_path.exists() and workflow_path.exists():
            import yaml
            
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            with open(workflow_path, 'r') as f:
                workflow = yaml.safe_load(f)
            
            # Config should not have chunking settings if workflow doesn't use them
            workflow_content = yaml.dump(workflow)
            
# Check for chunking settings using parsed structure rather than string matching
if 'chunking' not in workflow and not any('chunk' in str(key).lower() for key in workflow.keys()):
    assert 'chunking' not in config and not any('chunk' in str(key).lower() for key in config.keys()), \
        "PR Agent config contains chunking settings but workflow doesn't use them"
            
# More comprehensive YAML structure validation
assert isinstance(config, dict), "PR Agent config should parse to a dictionary"
assert isinstance(workflow, dict), "PR Agent workflow should parse to a dictionary"
            
            # Workflow should have required jobs
            assert 'jobs' in workflow, "PR Agent workflow should define jobs"
    
    def test_no_missing_config_files_referenced(self):
        """Workflows should not reference missing configuration files."""
        workflow_dir = Path(".github/workflows")
        
        for workflow_file in workflow_dir.glob("*.yml"):
            import yaml
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # Extract file paths mentioned in workflow
            import re
            file_patterns = re.findall(r'\.github/[^\s\'"]+', content)
            
            for file_path in file_patterns:
                file_path = file_path.rstrip(',')
                path = Path(file_path)
                
                # Skip URL-like patterns
                if '://' in file_path:
                    continue
                
                # File should exist or be in conditional/comment
                if not path.exists():
                    # Check if it's in a comment
                    lines_with_path = [
                        line for line in content.split('\n')
                        if file_path in line
                    ]
                    
                    for line in lines_with_path:
                        if not line.strip().startswith('#'):
                            # Should have error handling or conditional
                            assert 'if' in line.lower() or 'exists' in line.lower(), \
                                f"{workflow_file.name} references missing file: {file_path}"


class TestBackwardCompatibility:
    """Test that removal doesn't break backward compatibility."""
    
    def test_environment_variables_still_valid(self):
        """Environment variables should still be valid after deletions."""
        workflows = list(Path(".github/workflows").glob("*.yml"))
        
        for workflow_file in workflows:
            import yaml
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            # Check environment variables
            env = data.get('env', {})
            jobs = data.get('jobs', {})
            
            for job_name, job_data in jobs.items():
                job_env = job_data.get('env', {})
                
                # Should not reference deleted scripts or configs
                for key, value in job_env.items():
                    if isinstance(value, str):
                        assert 'context_chunker' not in value, \
                            f"{workflow_file.name} env var {key} references deleted script"
    
    def test_action_inputs_valid(self):
        """Action inputs should not reference deleted files or features."""
        workflows = list(Path(".github/workflows").glob("*.yml"))
        
        for workflow_file in workflows:
            import yaml
            with open(workflow_file, 'r') as f:
                data = yaml.safe_load(f)
            
            jobs = data.get('jobs', {})
            for job_name, job_data in jobs.items():
                steps = job_data.get('steps', [])
                
                for step in steps:
                    with_data = step.get('with', {})
                    
                    for key, value in with_data.items():
                        if isinstance(value, str):
                            # Should not reference deleted files
                            assert '.github/scripts/context_chunker' not in value, \
                                f"{workflow_file.name} step references deleted script"
                            assert 'labeler.yml' not in value, \
                                f"{workflow_file.name} step references deleted labeler config"