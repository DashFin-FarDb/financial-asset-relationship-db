"""
Comprehensive tests to validate that deleted files are properly removed.

This module ensures that files deleted in recent changes (labeler.yml,
context_chunker.py, codecov.yaml, scripts/README.md) are actually gone
and that dependent functionality has been properly updated or removed.
"""

import pytest
from pathlib import Path
from typing import List
import yaml


PROJECT_ROOT = Path(__file__).parent.parent.parent
GITHUB_DIR = PROJECT_ROOT / ".github"
WORKFLOWS_DIR = GITHUB_DIR / "workflows"
SCRIPTS_DIR = GITHUB_DIR / "scripts"


class TestDeletedFilesRemoved:
    """Test that deleted files are actually removed."""
    
    def test_labeler_yml_deleted(self):
        """Test that labeler.yml was deleted."""
        labeler_path = GITHUB_DIR / "labeler.yml"
        assert not labeler_path.exists(), \
            "labeler.yml should be deleted"
    
    def test_context_chunker_py_deleted(self):
        """Test that context_chunker.py was deleted."""
        chunker_path = SCRIPTS_DIR / "context_chunker.py"
        assert not chunker_path.exists(), \
            "context_chunker.py should be deleted"
    
    def test_codecov_yaml_deleted(self):
        """Test that codecov.yaml workflow was deleted."""
        codecov_path = WORKFLOWS_DIR / "codecov.yaml"
        assert not codecov_path.exists(), \
            "codecov.yaml should be deleted"
    
    def test_scripts_readme_deleted(self):
        """Test that scripts/README.md was deleted."""
        readme_path = SCRIPTS_DIR / "README.md"
        assert not readme_path.exists(), \
            "scripts/README.md should be deleted"


class TestLabelWorkflowUpdated:
    """Test that label.yml workflow was updated to not check for labeler.yml."""
    
    @pytest.fixture
    def label_workflow(self) -> dict:
        """Load label.yml workflow."""
        label_path = WORKFLOWS_DIR / "label.yml"
        if not label_path.exists():
            pytest.skip("label.yml not found")
        
        with open(label_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    def test_no_checkout_step(self, label_workflow: dict):
        """Test that checkout step was removed."""
        jobs = label_workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        checkout_steps = [
            step for step in steps 
            if 'uses' in step and 'checkout' in step['uses'].lower()
        ]
        
        assert len(checkout_steps) == 0, \
            "Checkout step should be removed from label workflow"
    
    def test_no_config_check_step(self, label_workflow: dict):
        """Test that config check step was removed."""
        jobs = label_workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        check_steps = [
            step for step in steps 
            if 'name' in step and 'check' in step['name'].lower() 
            and 'config' in step['name'].lower()
        ]
        
        assert len(check_steps) == 0, \
            "Config check step should be removed"
    
    def test_no_conditional_labeler(self, label_workflow: dict):
        """Test that labeler is not conditionally run."""
        jobs = label_workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        labeler_steps = [
            step for step in steps 
            if 'uses' in step and 'labeler' in step['uses'].lower()
        ]
        
        for step in labeler_steps:
            assert 'if' not in step, \
                "Labeler should not have conditional execution"
    
    def test_simplified_workflow_structure(self, label_workflow: dict):
        """Test that workflow has simplified structure."""
        jobs = label_workflow.get('jobs', {})
        label_job = jobs.get('label', {})
        steps = label_job.get('steps', [])
        
        # Should have minimal steps now
        assert len(steps) <= 2, \
            "Label workflow should have minimal steps after simplification"


class TestPRAgentWorkflowCleaned:
    """Test that PR agent workflow has chunking logic removed."""
    
    @pytest.fixture
    def pr_agent_workflow(self) -> dict:
        """Load pr-agent.yml workflow."""
        pr_agent_path = WORKFLOWS_DIR / "pr-agent.yml"
        if not pr_agent_path.exists():
            pytest.skip("pr-agent.yml not found")
        
        with open(pr_agent_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @pytest.fixture
    def pr_agent_content(self) -> str:
        """Load pr-agent.yml as text."""
        pr_agent_path = WORKFLOWS_DIR / "pr-agent.yml"
        if not pr_agent_path.exists():
            pytest.skip("pr-agent.yml not found")
        
        with open(pr_agent_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_no_context_chunker_reference(self, pr_agent_content: str):
        """Test that context_chunker.py is not referenced."""
        assert 'context_chunker' not in pr_agent_content.lower(), \
            "Should not reference context_chunker.py"
    
    def test_no_tiktoken_installation(self, pr_agent_content: str):
        """Test that tiktoken installation was removed."""
        assert 'tiktoken' not in pr_agent_content.lower(), \
            "Should not reference tiktoken"
    
    def test_no_chunking_step(self, pr_agent_workflow: dict):
        """Test that context chunking step was removed."""
        jobs = pr_agent_workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            chunking_steps = [
                step for step in steps 
                if 'name' in step and 'chunk' in step['name'].lower()
            ]
            
            assert len(chunking_steps) == 0, \
                f"Job {job_name} should not have chunking steps"
    
    def test_simplified_comment_parsing(self, pr_agent_workflow: dict):
        """Test that comment parsing was simplified."""
        jobs = pr_agent_workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            parse_steps = [
                step for step in steps 
                if 'name' in step and 'parse' in step['name'].lower()
            ]
            
            for step in parse_steps:
                run_script = step.get('run', '')
                
                # Should not have complex chunking logic
                assert 'pr_context.json' not in run_script.lower(), \
                    "Should not create pr_context.json file"
                assert 'CONTEXT_SIZE' not in run_script, \
                    "Should not check context size"
    
    def test_no_pyyaml_inline_install(self, pr_agent_content: str):
        """Test that PyYAML is not installed inline."""
        # PyYAML should be in requirements-dev.txt, not installed inline
        lines = pr_agent_content.split('\n')
        
        for line in lines:
            if 'pip install' in line.lower() and 'pyyaml' in line.lower():
                # Check it's not a specific inline install command
                assert 'pip install "pyyaml' not in line.lower(), \
                    "Should not have inline PyYAML install"


class TestCodecovWorkflowRemoved:
    """Test that codecov workflow removal didn't break CI."""
    
    def test_codecov_workflow_gone(self):
        """Test that codecov.yaml is removed."""
        codecov_path = WORKFLOWS_DIR / "codecov.yaml"
        assert not codecov_path.exists()
    
    def test_other_workflows_still_exist(self):
        """Test that other critical workflows still exist."""
        critical_workflows = [
            'pr-agent.yml',
            'label.yml',
            'greetings.yml',
            'apisec-scan.yml',
        ]
        
        for workflow in critical_workflows:
            workflow_path = WORKFLOWS_DIR / workflow
            assert workflow_path.exists(), \
                f"Critical workflow {workflow} should exist"
    
    def test_no_codecov_references_in_other_workflows(self):
        """Test that codecov is not referenced in remaining workflows except the main CI workflow."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
    
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
        
            # Allow codecov token in secrets, but not active usage
            if 'codecov' in content.lower():
                # The main CI workflow is expected to use the Codecov action
                if workflow_file.name == "ci.yml":
                    continue
                # Check it's not an active step in any other workflow
                assert 'uses: codecov/' not in content.lower(), \
                    f"{workflow_file.name} should not use codecov action"


class TestGreetingsWorkflowSimplified:
    """Test that greetings workflow was simplified."""
    
    @pytest.fixture
    def greetings_workflow(self) -> dict:
        """Load greetings.yml workflow."""
        greetings_path = WORKFLOWS_DIR / "greetings.yml"
        if not greetings_path.exists():
            pytest.skip("greetings.yml not found")
        
        with open(greetings_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @pytest.fixture
    def greetings_content(self) -> str:
        """Load greetings.yml as text."""
        greetings_path = WORKFLOWS_DIR / "greetings.yml"
        if not greetings_path.exists():
            pytest.skip("greetings.yml not found")
        
        with open(greetings_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_simplified_messages(self, greetings_content: str):
        """Test that greeting messages were simplified."""
        # Should not have elaborate markdown formatting
        assert 'Welcome to the Financial Asset' not in greetings_content, \
            "Should have simplified welcome message"
        assert 'Congratulations on your first pull request' not in greetings_content, \
            "Should have simplified PR message"
    
    def test_no_resource_links(self, greetings_content: str):
        """Test that resource links were removed."""
        links = ['CONTRIBUTING.md', 'QUICK_START.md', 'TESTING_GUIDE.md']
        
        for link in links:
            assert link not in greetings_content, \
                f"Should not reference {link} in greetings"
    
    def test_concise_configuration(self, greetings_workflow: dict):
        """Test that configuration is concise."""
        jobs = greetings_workflow.get('jobs', {})
        greet_job = jobs.get('greeting', {})
        steps = greet_job.get('steps', [])
        
        # Should have minimal configuration
        assert len(steps) == 1, \
            "Greetings workflow should have single step"
        
        first_step = steps[0]
        with_config = first_step.get('with', {})
        
        # Messages should be short strings
        issue_msg = with_config.get('issue-message', '')
        pr_msg = with_config.get('pr-message', '')
        
        assert len(issue_msg) < 100, \
            "Issue message should be concise"
        assert len(pr_msg) < 100, \
            "PR message should be concise"


class TestAPISecWorkflowSimplified:
    """Test that APISec workflow was simplified."""
    
    @pytest.fixture
    def apisec_workflow(self) -> dict:
        """Load apisec-scan.yml workflow."""
        apisec_path = WORKFLOWS_DIR / "apisec-scan.yml"
        if not apisec_path.exists():
            pytest.skip("apisec-scan.yml not found")
        
        with open(apisec_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    
    @pytest.fixture
    def apisec_content(self) -> str:
        """Load apisec-scan.yml as text."""
        apisec_path = WORKFLOWS_DIR / "apisec-scan.yml"
        if not apisec_path.exists():
            pytest.skip("apisec-scan.yml not found")
        
        with open(apisec_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def test_no_job_level_conditional(self, apisec_workflow: dict):
        """Test that job-level conditional was removed."""
        jobs = apisec_workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            assert 'if' not in job_config, \
                f"Job {job_name} should not have job-level conditional"
    
    def test_no_credential_check_step(self, apisec_workflow: dict):
        """Test that credential check step was removed."""
        jobs = apisec_workflow.get('jobs', {})
        
        for job_name, job_config in jobs.items():
            steps = job_config.get('steps', [])
            
            check_steps = [
                step for step in steps 
                if 'name' in step and 'check' in step['name'].lower() 
                and 'credential' in step['name'].lower()
            ]
            
            assert len(check_steps) == 0, \
                f"Job {job_name} should not have credential check step"
    
    def test_no_skip_messages(self, apisec_content: str):
        """Test that skip messages were removed."""
        skip_phrases = [
            'APIsec credentials not configured',
            'Skipping scan',
            'To enable APIsec scanning',
        ]
        
        for phrase in skip_phrases:
            assert phrase not in apisec_content, \
                f"Should not have skip message: {phrase}"


class TestNoOrphanedReferences:
    """Test that deleted files are not referenced anywhere."""

    def test_no_labeler_references_in_docs(self):
        """Test that labeler.yml is not referenced in documentation."""
        doc_files = list(PROJECT_ROOT.glob("*.md"))
        for doc_file in doc_files:
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            if 'labeler.yml' in content:
                assert 'removed' in content.lower() or 'deleted' in content.lower(), \
                    f"{doc_file.name} references labeler.yml but doesn't indicate removal"

    def test_no_context_chunker_imports(self):
        """Test that context_chunker is not imported anywhere."""
        python_files = list(PROJECT_ROOT.rglob("*.py"))
        for py_file in python_files:
            if 'test' in py_file.name.lower():
                continue
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert 'context_chunker' not in content, \
                f"{py_file} should not import context_chunker"

    def test_no_codecov_config_files(self):
        """Test that codecov config files don't exist."""
        codecov_configs = [
            PROJECT_ROOT / ".codecov.yml",
            PROJECT_ROOT / "codecov.yml",
            PROJECT_ROOT / ".codecov.yaml",
        ]
        for config_file in codecov_configs:
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                assert 'github' not in content.lower() or 'action' not in content.lower()

    def test_no_labeler_references_in_workflows(self):
        """Ensure workflows don't reference .github/labeler.yml, even in comments."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert '.github/labeler.yml' not in content, \
                f"{workflow_file.name} should not reference deleted .github/labeler.yml"

    def test_no_context_chunker_references_anywhere(self):
        """Test that context_chunker is not referenced in any file type."""
        all_files = list(PROJECT_ROOT.rglob("*"))
        for file_path in all_files:
            if file_path.is_file() and file_path.suffix in {'.py', '.yml', '.yaml', '.md', '.sh'}:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                assert 'context_chunker' not in content, \
                    f"{file_path} should not reference context_chunker"
        """Test that labeler.yml is not referenced in documentation."""
        doc_files = list(PROJECT_ROOT.glob("*.md"))
        
        for doc_file in doc_files:
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If labeler is mentioned, it should be in past tense or removal context
            if 'labeler.yml' in content:
                # Check the context suggests it was removed
                assert 'removed' in content.lower() or 'deleted' in content.lower(), \
                    f"{doc_file.name} references labeler.yml but doesn't indicate removal"

    def test_no_context_chunker_imports(self):
        """Test that context_chunker is not imported anywhere."""
        python_files = list(PROJECT_ROOT.rglob("*.py"))
        
        for py_file in python_files:
            # Skip test files
            if 'test' in py_file.name.lower():
                continue
            
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            assert 'context_chunker' not in content, \
                f"{py_file} should not import context_chunker"

    def test_no_codecov_config_files(self):
        """Test that codecov config files don't exist."""
        codecov_configs = [
            PROJECT_ROOT / ".codecov.yml",
            PROJECT_ROOT / "codecov.yml",
            PROJECT_ROOT / ".codecov.yaml",
        ]
        
        for config_file in codecov_configs:
            if config_file.exists():
                # If it exists, it should be for a different purpose
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check it's not the GitHub Actions codecov config
                assert 'github' not in content.lower() or 'action' not in content.lower()

    def test_no_labeler_references_in_workflows(self):
        """Ensure workflows don't reference .github/labeler.yml, even in comments."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")

        for workflow_file in WORKFLOWS_DIR.glob("*.yml"):
            with open(workflow_file, 'r', encoding='utf-8') as f:
                content = f.read()
            assert '.github/labeler.yml' not in content, \
                f"{workflow_file.name} should not reference deleted .github/labeler.yml"
        """Test that labeler.yml is not referenced in documentation."""
        doc_files = list(PROJECT_ROOT.glob("*.md"))
        
        for doc_file in doc_files:
            with open(doc_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # If labeler is mentioned, it should be in past tense or removal context
            if 'labeler.yml' in content:
                # Check the context suggests it was removed
                assert 'removed' in content.lower() or 'deleted' in content.lower(), \
                    f"{doc_file.name} references labeler.yml but doesn't indicate removal"
    

        for py_file in python_files:
            # Skip test files
            if 'test' in py_file.name.lower():
                continue

        def test_no_context_chunker_references_anywhere(self):
            """Test that context_chunker is not referenced in any file type."""
            all_files = list(PROJECT_ROOT.rglob("*"))

            for file_path in all_files:
                if file_path.is_file() and file_path.suffix in {'.py', '.yml', '.yaml', '.md', '.sh'}:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    assert 'context_chunker' not in content, \
                        f"{file_path} should not reference context_chunker"
    def test_no_codecov_config_files(self):
        """Test that codecov config files don't exist."""
        codecov_configs = [
            PROJECT_ROOT / ".codecov.yml",
            PROJECT_ROOT / "codecov.yml",
            PROJECT_ROOT / ".codecov.yaml",
        ]
        
        for config_file in codecov_configs:
            if config_file.exists():
                # If it exists, it should be for a different purpose
                with open(config_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Check it's not the GitHub Actions codecov config
                assert 'github' not in content.lower() or 'action' not in content.lower()


class TestDependencyCleanup:
    """Test that dependencies related to deleted features were cleaned up."""
    
    def test_requirements_dev_updated(self):
        """Test that requirements-dev.txt was updated appropriately."""
        req_file = PROJECT_ROOT / "requirements-dev.txt"
        
        if not req_file.exists():
            pytest.skip("requirements-dev.txt not found")
        
        with open(req_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # PyYAML should be present with version
        assert 'PyYAML>=6.0' in content, \
            "PyYAML should be in requirements-dev.txt"
        
        # tiktoken should NOT be present (it was optional and removed)
        assert 'tiktoken' not in content.lower(), \
            "tiktoken should not be in requirements-dev.txt"


class TestProjectStructureIntegrity:
    """Test that project structure is intact after deletions."""
    
    def test_github_directory_exists(self):
        """Test that .github directory still exists."""
        assert GITHUB_DIR.exists()
        assert GITHUB_DIR.is_dir()
    
    def test_workflows_directory_exists(self):
        """Test that workflows directory still exists."""
        assert WORKFLOWS_DIR.exists()
        assert WORKFLOWS_DIR.is_dir()
    
    def test_sufficient_workflows_remain(self):
        """Test that sufficient workflows remain after cleanup."""
        if not WORKFLOWS_DIR.exists():
            pytest.skip("Workflows directory not found")
        
        workflow_files = list(WORKFLOWS_DIR.glob("*.yml")) + \
                        list(WORKFLOWS_DIR.glob("*.yaml"))
        
        # Should have at least 3 workflows
        assert len(workflow_files) >= 3, \
            "Should have at least 3 workflows after cleanup"
    
    def test_critical_configs_present(self):
        """Test that critical config files are still present."""
        critical_configs = [
            GITHUB_DIR / "pr-agent-config.yml",
        ]
        
        for config in critical_configs:
            if config.name == 'pr-agent-config.yml':
                # This one should definitely exist
                assert config.exists(), \
                    f"Critical config {config.name} should exist"