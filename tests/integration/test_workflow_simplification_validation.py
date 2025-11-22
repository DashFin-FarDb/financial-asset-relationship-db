"""
Integration tests validating workflow simplification changes.

This test suite ensures that:
1. Removed context chunking functionality is completely removed
2. Simplified workflows remain functional  
3. Configuration files are valid after simplification
4. No references to removed features remain
"""

import pytest
import yaml
from pathlib import Path
class TestContextChunkingRemoval:
    """Validate that context chunking functionality has been completely removed."""
    
    def test_context_chunker_script_removed(self):
        """Verify context_chunker.py script no longer exists."""
        chunker_path = Path(".github/scripts/context_chunker.py")
        assert not chunker_path.exists(), \
            "context_chunker.py should be removed"
    
    def test_context_chunker_readme_removed(self):
        """Verify context chunking documentation removed."""
        readme_path = Path(".github/scripts/README.md")
        assert not readme_path.exists(), \
            "Context chunking README should be removed"
    
    def test_no_chunking_references_in_pr_agent_workflow(self):
        """Ensure pr-agent.yml has no references to chunking."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        assert workflow_path.exists(), "pr-agent.yml should exist"
        
        with open(workflow_path) as f:
            content = f.read()
        
        # Check for removed chunking-related terms
        forbidden_terms = [
            "context_chunker",
            "chunking",
            "chunk_size",
            "tiktoken",
            "context_size",
            "chunked=",
        ]
        
        for term in forbidden_terms:
            assert term not in content.lower(), \
                f"Removed chunking reference '{term}' found in pr-agent.yml"
    
    def test_no_chunking_config_in_pr_agent_config(self):
        """Verify pr-agent-config.yml has no chunking configuration."""
        config_path = Path(".github/pr-agent-config.yml")
        assert config_path.exists(), "pr-agent-config.yml should exist"
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        # Verify chunking configuration is removed
        agent_config = config.get("agent", {})
        assert "context" not in agent_config, \
            "Context chunking config should be removed from agent section"
        
        limits_config = config.get("limits", {})
        assert "fallback" not in limits_config, \
            "Fallback chunking config should be removed from limits section"
        
        # Check for any chunking-related keys
        config_str = yaml.dump(config)
        forbidden_keys = ["chunk", "context_overflow", "token_limit", "max_tokens", "token_count", "summarization"]
        for key in forbidden_keys:
            assert key not in config_str.lower(), \
                f"Chunking-related key '{key}' found in config"


class TestLabelerRemoval:
    """Validate labeler.yml removal."""
    
    def test_labeler_yml_removed(self):
        """Verify labeler.yml configuration file is removed."""
        labeler_path = Path(".github/labeler.yml")
        assert not labeler_path.exists(), \
            "labeler.yml should be removed"
    
    def test_label_workflow_simplified(self):
        """Ensure label.yml workflow is simplified."""
        workflow_path = Path(".github/workflows/label.yml")
        assert workflow_path.exists(), "label.yml workflow should exist"
        
        with open(workflow_path) as f:
            content = f.read()
        
        # Should not have config existence checks anymore
        assert "check-config" not in content.lower(), \
            "Config check steps should be removed"
        assert "config_exists" not in content, \
            "Config existence variable should be removed"


class TestWorkflowSimplification:
    """Validate simplified workflow configurations."""
    
    def test_pr_agent_workflow_valid_yaml(self):
        """Ensure pr-agent.yml is valid YAML after simplification."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
        
        assert workflow is not None, "Workflow should parse as valid YAML"
        assert "jobs" in workflow, "Workflow should have jobs"
    
    def test_pr_agent_workflow_has_required_jobs(self):
        """Verify essential jobs remain after simplification."""
        workflow_path = Path(".github/workflows/pr-agent.yml")
        
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        required_jobs = ["pr-agent-trigger", "auto-merge-check", "dependency-update"]
        
        for job in required_jobs:
            assert job in jobs, f"Required job '{job}' should exist"
    
    def test_pr_agent_workflow_no_duplicate_keys(self):
        """Ensure no duplicate YAML keys in pr-agent.yml."""
        from yaml.constructor import ConstructorError

        class DuplicateKeyLoader(yaml.SafeLoader):
            pass

        def construct_mapping(loader, node, deep=False):
            mapping = {}
            for key_node, value_node in node.value:
                key = loader.construct_object(key_node, deep=deep)
                if key in mapping:
                    raise ConstructorError(
                        "while constructing a mapping",
                        node.start_mark,
                        f"found duplicate key: {key!r}",
                        key_node.start_mark,
                    )
                value = loader.construct_object(value_node, deep=deep)
                mapping[key] = value
            return mapping

        DuplicateKeyLoader.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, construct_mapping
        )

        workflow_path = Path(".github/workflows/pr-agent.yml")
        with open(workflow_path, "r") as f:
            content = f.read()

        try:
            yaml.load(content, Loader=DuplicateKeyLoader)
        except ConstructorError as e:
            pytest.fail(f"Duplicate YAML key detected in pr-agent.yml: {e}")
    
    def test_apisec_scan_workflow_credentials_handling(self):
        """Verify apisec-scan.yml properly handles missing credentials."""
        workflow_path = Path(".github/workflows/apisec-scan.yml")
        
        with open(workflow_path) as f:
            workflow = yaml.safe_load(f)
        
        jobs = workflow.get("jobs", {})
        scan_job = jobs.get("Trigger_APIsec_scan", {})
        
        # Should not have conditional credential checks anymore
        steps = scan_job.get("steps", [])
        step_names = [step.get("name", "") for step in steps]
        
        assert not any("Check for APIsec credentials" in name for name in step_names), \
            "Credential check step should be removed"


class TestSimplifiedConfigurationValidity:
    """Validate configuration files are valid after simplification."""
    
    def test_pr_agent_config_valid_yaml(self):
        """Ensure pr-agent-config.yml is valid YAML."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        assert config is not None, "Config should parse as valid YAML"
        assert "agent" in config, "Config should have agent section"
    
    def test_pr_agent_config_has_essential_sections(self):
        """Verify essential configuration sections remain."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        required_sections = [
            "agent",
            "monitoring",
            "actions",
            "quality",
            "git",
            "ci",
            "notifications",
            "security",
            "repository",
            "limits",
        ]
        
        for section in required_sections:
            assert section in config, f"Required section '{section}' should exist"
    
    def test_pr_agent_config_version_downgraded(self):
        """Verify agent version was downgraded from 1.1.0 to 1.0.0."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        agent = config.get("agent", {})
        version = agent.get("version", "")
        
        assert version == "1.0.0", \
            f"Agent version should be 1.0.0 after removing chunking, got {version}"


class TestRequirementsSimplification:
    """Validate requirements-dev.txt simplification."""
    
    def test_requirements_dev_exists(self):
        """Ensure requirements-dev.txt exists."""
        req_path = Path("requirements-dev.txt")
        assert req_path.exists(), "requirements-dev.txt should exist"
    
    def test_pyyaml_version_specified(self):
        """Verify PyYAML has proper version specification."""
        req_path = Path("requirements-dev.txt")
        
        with open(req_path) as f:
            content = f.read()
        
        # Should have PyYAML with version constraint
        pyyaml_line = [line for line in content.splitlines() if "pyyaml" in line.lower()]
        assert len(pyyaml_line) > 0, "PyYAML should be in requirements-dev.txt"
        
        # Check version constraint format
        assert any(">=" in line or "==" in line for line in pyyaml_line), \
            "PyYAML should have version constraint"
    
    def test_no_tiktoken_dependency(self):
        """Verify tiktoken is not in requirements after chunking removal."""
        req_path = Path("requirements-dev.txt")
        
        with open(req_path) as f:
            content = f.read()
        
        assert "tiktoken" not in content.lower(), \
            "tiktoken dependency should be removed with chunking feature"


class TestGreetingsWorkflowSimplification:
    """Validate greetings.yml simplification."""
    
    def test_greetings_workflow_simplified(self):
        """Ensure greetings.yml uses simple placeholder messages."""
        workflow_path = Path(".github/workflows/greetings.yml")
        
        with open(workflow_path) as f:
            content = f.read()
        
        # Should have simple placeholder messages, not elaborate ones
        assert "Message that will be displayed" in content, \
            "Greetings should use simple placeholder messages"
        
        # Should not have elaborate welcome messages
        forbidden_phrases = [
            "Welcome to the Financial",
            "What happens next",
            "Congratulations on your first",
            "Resources:",
        ]
        
        for phrase in forbidden_phrases:
            assert phrase not in content, \
                f"Elaborate message '{phrase}' should be replaced with placeholder"


class TestRegressionPrevention:
    """Ensure simplification doesn't break existing functionality."""
    
    def test_all_workflow_files_valid_yaml(self):
        """Verify all GitHub workflow files are valid YAML."""
        workflow_dir = Path(".github/workflows")
        workflow_files = list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
        
        assert len(workflow_files) > 0, "Should have workflow files"
        
        for workflow_file in workflow_files:
            with open(workflow_file) as f:
                try:
                    workflow = yaml.safe_load(f)
                    assert workflow is not None, f"{workflow_file.name} should parse"
                except yaml.YAMLError as e:
                    pytest.fail(f"{workflow_file.name} has invalid YAML: {e}")
    
    def test_pr_agent_config_yml_valid(self):
        """Verify pr-agent-config.yml is valid."""
        config_path = Path(".github/pr-agent-config.yml")
        
        with open(config_path) as f:
            try:
                config = yaml.safe_load(f)
                assert config is not None
                assert isinstance(config, dict)
            except yaml.YAMLError as e:
                pytest.fail(f"pr-agent-config.yml has invalid YAML: {e}")
    


class TestDocumentationCleanup:
    """Validate documentation reflects the simplification."""
    
    def test_no_orphaned_test_summaries(self):
        """Check for test summary documentation files."""
        # This is informational - summary files should eventually be consolidated
        summary_files = list(Path(".").glob("*TEST*SUMMARY*.md"))
        summary_files.extend(list(Path(".").glob("*TEST*GENERATION*.md")))
        
        # Just document what exists, don't fail
        if summary_files:
            print(f"\nFound {len(summary_files)} test summary files:")
            for f in summary_files[:10]:
                print(f"  - {f.name}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])