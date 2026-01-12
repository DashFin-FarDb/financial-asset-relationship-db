"""
Tests to verify that context_chunker.py and related functionality
were properly removed from the codebase.

This ensures that the removal was complete and no dangling references remain.
"""

import pytest
from pathlib import Path
import re
yaml = pytest.importorskip("yaml")


REPO_ROOT = Path(__file__).parent.parent.parent
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"
SCRIPTS_DIR = REPO_ROOT / ".github" / "scripts"


class TestContextChunkerRemoval:
    """Verify context_chunker.py was completely removed."""
    
    def test_context_chunker_file_does_not_exist(self):
        """context_chunker.py should no longer exist."""
        context_chunker = SCRIPTS_DIR / "context_chunker.py"
        assert not context_chunker.exists(), \
            "context_chunker.py should have been removed"
    
    def test_scripts_readme_does_not_exist(self):
        """Scripts README documenting chunker should be removed."""
        scripts_readme = SCRIPTS_DIR / "README.md"
        assert not scripts_readme.exists(), \
            "Scripts README should have been removed"
    
    def test_no_imports_of_context_chunker(self):
        """No Python files should import context_chunker."""
        python_files = list(REPO_ROOT.rglob("*.py"))
        
        for py_file in python_files:
            # Skip test files and cache
            if '__pycache__' in str(py_file) or 'test_context_chunker_removal' in str(py_file):
                continue
            
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                
                # Check for imports
                import_pattern = re.compile(r'^\s*(?:from\s+context_chunker\b|import\s+context_chunker\b)', re.MULTILINE)
                assert not import_pattern.search(content), f"{py_file} imports context_chunker"
            except (IOError, OSError):
                # Skip files that can't be read due to I/O issues
                pass
            except Exception as e:
                pytest.fail(f"Unexpected error reading {py_file}: {e}")
                # Skip files that can't be read
    
    def test_no_references_in_workflows(self):
        """Workflow files should not reference context_chunker.py."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            assert 'context_chunker.py' not in content, \
                f"{workflow_file.name} references context_chunker.py"
            assert 'context_chunker' not in content.lower() and 'context chunker' not in content.lower(), \
                f"{workflow_file.name} may reference context chunking functionality"
            assert 'context_chunker' not in content.lower() and 'context chunker' not in content.lower(), \
                f"{workflow_file.name} may reference context chunking functionality"

class TestConfigurationCleanup:
class TestConfigurationCleanup:
    """Verify configuration was updated to remove chunking references."""
    
    def test_pr_agent_config_no_chunking_section(self):
        """PR agent config should not reference the removed context_chunker script."""
        config_file = REPO_ROOT / ".github" / "pr-agent-config.yml"
    
        if not config_file.exists():
            pytest.skip("PR agent config not found")
    
        with open(config_file, 'r') as f:
            content = f.read()
    
        # Check that there are no dangling references to the removed script
        lower_content = content.lower()
        assert 'context_chunker' not in lower_content, \
            "PR agent config still references context_chunker script"
    
    def test_pr_agent_config_version_updated(self):
        """PR agent config version should match the expected agent version."""
        config_file = REPO_ROOT / ".github" / "pr-agent-config.yml"
    
        if not config_file.exists():
            pytest.skip("PR agent config not found")
    
        with open(config_file, 'r') as f:
            content = f.read()
    
        # Version should match the configured agent version (currently 1.1.0)
        import yaml
        config = yaml.safe_load(content)
    
        assert 'agent' in config and 'version' in config['agent'], \
            "PR agent config must define agent.version"
        version = config['agent']['version']
        assert version == "1.1.0", \
            f"PR agent config version should be 1.1.0, found {version}"


class TestWorkflowSimplification:
    """Verify workflows were simplified to remove chunking logic."""
    
    def test_pr_agent_workflow_simplified(self):
        """PR agent workflow should be simplified."""
        pr_agent_workflow = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not pr_agent_workflow.exists():
            pytest.skip("PR agent workflow not found")
        
        with open(pr_agent_workflow, 'r') as f:
            content = f.read()
        
        # Should not have chunking-related steps
        assert 'Fetch PR Context with Chunking' not in content, \
            "PR agent workflow still has chunking step"
        assert 'context_chunker' not in content, \
            "PR agent workflow still references context_chunker"
    
    def test_pr_agent_workflow_no_duplicate_setup(self):
        """PR agent workflow should not have duplicate setup steps."""
        pr_agent_workflow = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not pr_agent_workflow.exists():
            pytest.skip("PR agent workflow not found")
        
        with open(pr_agent_workflow, 'r') as f:
            content = f.read()
        
        # Count occurrences of "Setup Python"
        setup_python_count = content.count('name: Setup Python')
        assert setup_python_count == 1, \
            f"PR agent workflow has {setup_python_count} 'Setup Python' steps (should be 1)"
    
    def test_no_pyyaml_installation_for_chunking(self):
        """Workflows should not install PyYAML for chunking purposes."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                content = f.read()
            
            # If PyYAML is installed, it shouldn't be for context chunking
            if 'pyyaml' in content.lower():
                assert 'context chunker' not in content.lower(), \
                    f"{workflow_file.name} installs PyYAML for context chunking"


class TestDependenciesCleanup:
    """Verify dependencies were cleaned up."""
    
    def test_requirements_dev_appropriate(self):
        """requirements-dev.txt should have appropriate dependencies."""
        req_file = REPO_ROOT / "requirements-dev.txt"
        
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        with open(req_file, 'r') as f:
            content = f.read()
        
        # PyYAML should be present (for other purposes)
        assert 'PyYAML' in content or 'pyyaml' in content.lower(), \
            "PyYAML should still be in requirements-dev.txt"
        
        # tiktoken should not be present (was only for chunking)
        assert 'tiktoken' not in content.lower(), \
            "tiktoken should be removed from requirements-dev.txt"


class TestDocumentationUpdates:
    """Verify documentation was updated."""
    
    def test_no_chunking_documentation(self):
        """Documentation should not describe chunking functionality."""
        doc_files = [
            REPO_ROOT / "README.md",
            REPO_ROOT / ".github" / "copilot-pr-agent.md",
        ]
        
        for doc_file in doc_files:
            if not doc_file.exists():
                continue
            
            with open(doc_file, 'r') as f:
                content = f.read()
            
            # Should not have extensive chunking documentation
            chunking_mentions = content.lower().count('chunk')
            assert chunking_mentions < 5, \
                f"{doc_file.name} still has extensive chunking documentation"


class TestNoRegressionOfFixes:
    """Ensure fixes made in this branch are preserved."""
    
    def test_no_duplicate_yaml_keys_in_pr_agent(self):
        """PR agent workflow should not have duplicate YAML keys."""
        pr_agent_workflow = WORKFLOWS_DIR / "pr-agent.yml"
        
        if not pr_agent_workflow.exists():
            pytest.skip("PR agent workflow not found")
        
        import yaml
        
        class DuplicateKeyLoader(yaml.SafeLoader):
            def construct_mapping(self, node, deep=False):
                if not isinstance(node, yaml.MappingNode):
                    raise yaml.constructor.ConstructorError(
                        None, None,
                        f"expected a mapping node, but found {node.id}",
                        node.start_mark
                    )
                
                mapping = {}
                for key_node, value_node in node.value:
                    key = self.construct_object(key_node, deep=deep)
                    
                    if key in mapping:
                        raise yaml.constructor.ConstructorError(
                            f"while constructing a mapping",
                            node.start_mark,
                            f"found duplicate key: {key}",
                            key_node.start_mark
                        )
                    
                    value = self.construct_object(value_node, deep=deep)
                    mapping[key] = value
                
                return mapping
        
        with open(pr_agent_workflow, 'r') as f:
            try:
                yaml.load(f.read(), Loader=DuplicateKeyLoader)
            except yaml.constructor.ConstructorError as e:
                pytest.fail(f"PR agent workflow has duplicate keys: {e}")
    
    def test_workflow_indentation_fixed(self):
        """All workflows should have proper YAML indentation."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + list(WORKFLOWS_DIR.glob("*.yaml"))
        
        for workflow_file in workflow_files:
            with open(workflow_file, 'r') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines, 1):
                if line.strip() and not line.strip().startswith('#'):
                    # Check for tabs
                    assert '\t' not in line, \
                        f"{workflow_file.name}:{i} uses tabs instead of spaces"
                    
                    # Check indentation
                    leading_spaces = len(line) - len(line.lstrip(' '))
                    if leading_spaces > 0:
                        assert leading_spaces % 2 == 0, \
                            f"{workflow_file.name}:{i} has odd indentation"


class TestCleanCodebase:
    """Verify codebase is clean after removal."""
    
    def test_no_orphaned_comments_about_chunking(self):
        """Code should not have orphaned comments about chunking."""
        # This is informational - we'll check key files
        files_to_check = [
            WORKFLOWS_DIR / "pr-agent.yml",
            REPO_ROOT / ".github" / "pr-agent-config.yml",
        ]
        
        for file_path in files_to_check:
            if not file_path.exists():
                continue
            
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Look for comment lines mentioning chunking
            comment_lines = [line for line in content.split('\n') if line.strip().startswith('#')]
            chunking_comments = [line for line in comment_lines if 'chunk' in line.lower()]
            
            # Should have minimal or no chunking comments
            assert len(chunking_comments) == 0, \
                f"{file_path.name} has {len(chunking_comments)} comment(s) about chunking"
    
    def test_labeler_yml_removed(self):
        """labeler.yml should be removed."""
        labeler_file = REPO_ROOT / ".github" / "labeler.yml"
        assert not labeler_file.exists(), \
            "labeler.yml should have been removed"
    
    def test_workflow_checks_simplified(self):
        """Workflow checks should be simplified."""
        # Check that apisec-scan doesn't have credential checks
        apisec_workflow = WORKFLOWS_DIR / "apisec-scan.yml"
        
        if apisec_workflow.exists():
            with open(apisec_workflow, 'r') as f:
                content = f.read()
            
            # Should not have the credential check step
            assert 'Check for APIsec credentials' not in content, \
                "apisec-scan workflow still has credential check"
        
        # Check that label workflow is simplified
        label_workflow = WORKFLOWS_DIR / "label.yml"
        
        if label_workflow.exists():
            with open(label_workflow, 'r') as f:
                content = f.read()
            
            # Should not have config check steps
            assert 'Check for labeler config' not in content, \
                "label workflow still has config check"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
