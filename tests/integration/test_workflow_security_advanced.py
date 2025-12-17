"""
Advanced security tests for GitHub workflows.

Focus areas:
1. Injection vulnerability prevention
2. Secret exposure prevention  
3. Permissions and least privilege
4. Supply chain security
5. Workflow isolation and sandboxing
"""

import os
import pytest
import yaml
import re
from pathlib import Path
from typing import Dict, Any, List, Set


class TestWorkflowInjectionPrevention:
    """Tests for preventing injection attacks in workflows."""
    
    @pytest.fixture
    def all_workflows(self) -> List[Dict[str, Any]]:
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
                workflows.append({
                    'path': workflow_file,
                    'content': yaml.safe_load(content),
                    'raw': content
                })
        return workflows
    
    def test_no_unquoted_github_context_in_run_commands(self, all_workflows):
        """Verify github context variables are properly quoted in run commands."""
        dangerous_patterns = [
            r'\$\{\{\s*github\.event\.[\w.]+\s*\}\}',  # ${{ github.event.* }}
            r'\$\{\{\s*github\.head_ref\s*\}\}',        # ${{ github.head_ref }}
            r'\$\{\{\s*github\.base_ref\s*\}\}',        # ${{ github.base_ref }}
        ]
        
        for workflow in all_workflows:
                        for pattern in dangerous_patterns:
                            matches = re.findall(pattern, run_command)
                            for match in matches:
                                # Ensure the specific context variable occurrence is within quotes
                                quoted = re.search(r'(["\']).*?' + re.escape(match) + r'.*?\1', run_command, flags=re.DOTALL)
                                assert quoted, (
                                    f"Unquoted context variable in {workflow['path']} "
                                    f"job '{job_name}' step {step_idx}: {match}"
                                )
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'run' in step:
                        run_command = step['run']
                        # Check if unquoted context variables are used
                        for pattern in dangerous_patterns:
                            for pattern in dangerous_patterns:
                                matches = re.findall(pattern, run_command)
                                for match in matches:
                                    # Only enforce quoting when the command is passed through a shell
                                    shell_invocation = re.search(r'\b(sh|bash)\b\s+-c\b', run_command)
                                    if shell_invocation:
                                        quoted = re.search(r'(["\']).*?' + re.escape(match) + r'.*?\1', run_command, flags=re.DOTALL)
                                        assert quoted, (
                                            f"Potential unquoted context variable reaching shell in {workflow['path']} "
                                            f"job '{job_name}' step {step_idx}: {match}"
                                        )
                            for match in matches:
                                # Should be within quotes
                                for match in matches:
                                    # Ensure the specific context variable occurrence is within quotes
                                    quoted = re.search(r'(["\']).*?' + re.escape(match) + r'.*?\1', run_command, flags=re.DOTALL)
                                    assert quoted, (
                                        f"Unquoted context variable in {workflow['path']} "
                                        f"job '{job_name}' step {step_idx}: {match}"
                                    )
    
    def test_no_eval_with_user_input(self, all_workflows):
        """Verify workflows don't use eval with user-controllable input."""
        dangerous_commands = ['eval', 'exec', 'source']
        
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'run' in step:
                        run_command = step['run'].lower()
                        for dangerous_cmd in dangerous_commands:
                            if dangerous_cmd in run_command:
                                # If found, ensure it's not with github context
                                assert 'github.event' not in run_command, \
                                    f"Dangerous {dangerous_cmd} with user input in " \
                                    f"{workflow['path']} job '{job_name}' step {step_idx}"
    
    def test_script_injection_prevention_in_pr_title_body(self, all_workflows):
        """Verify PR title/body are not directly interpolated in scripts."""
        dangerous_refs = [
            'github.event.pull_request.title',
            'github.event.pull_request.body',
            'github.event.issue.title',
            'github.event.issue.body',
            'github.event.comment.body',
        ]
        
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'run' in step:
                        run_command = step['run']
                        for dangerous_ref in dangerous_refs:
                            if dangerous_ref in run_command:
                                # Should use environment variables instead
                                assert 'env:' in str(step) or 'ENV' in run_command, \
                                    f"Direct interpolation of {dangerous_ref} in " \
                                    f"{workflow['path']} job '{job_name}' step {step_idx}. " \
                                    f"Use environment variables instead."
    
    def test_no_curl_with_unvalidated_input(self, all_workflows):
        """Verify curl commands don't use unvalidated user input."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'run' in step:
                        run_command = step['run']
                        if 'curl' in run_command.lower():
                            # Should not use github.event directly in URL
                            assert 'github.event' not in run_command or \
                                   ('validate' in run_command.lower() or 'sanitize' in run_command.lower()), \
                                f"Curl with unvalidated input in {workflow['path']} " \
                                f"job '{job_name}' step {step_idx}"


class TestWorkflowSecretHandling:
    """Tests for proper secret handling in workflows."""
    
    @pytest.fixture
    def all_workflows(self) -> List[Dict[str, Any]]:
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                content = f.read()
                workflows.append({
                    'path': workflow_file,
                    'content': yaml.safe_load(content),
                    'raw': content
                })
        return workflows
    
    def test_secrets_not_echoed_in_logs(self, all_workflows):
        """Verify secrets are not echoed or printed in logs."""
        for workflow in all_workflows:
            raw_content = workflow['raw']
            
            # Find all references to secrets
            secret_refs = re.findall(r'secrets\.([A-Za-z0-9_\-]+)', raw_content)
            
            for secret_ref in secret_refs:
                # Check if this secret is used in echo/print commands
                lines = raw_content.split('\n')
                for line_no, line in enumerate(lines, 1):
                    if secret_ref in line:
                        # Should not be in echo, print, or printf
                        assert not re.search(r'(echo|print|printf)\s+.*' + re.escape(secret_ref), line, re.IGNORECASE), \
                            f"Secret {secret_ref} may be logged in {workflow['path']} line {line_no}"
    
    def test_secrets_not_in_artifact_uploads(self, all_workflows):
        """Verify secrets are not uploaded as artifacts."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'actions/upload-artifact' in step.get('uses', ''):
                        # Check if any secret reference in this step
                        step_str = str(step)
                        assert 'secrets.' not in step_str, \
                            f"Secret reference in artifact upload: {workflow['path']} " \
                            f"job '{job_name}' step {step_idx}"
    
    def test_secrets_not_in_pr_comments(self, all_workflows):
        """Verify secrets are not posted in PR comments."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'github-script' in step.get('uses', '') or 'script' in step:
                        script_content = str(step.get('with', {}).get('script', ''))
                        if 'createComment' in script_content or 'create_comment' in script_content:
                            assert 'secrets.' not in script_content, \
                                f"Secret may be exposed in PR comment: {workflow['path']} " \
                                f"job '{job_name}' step {step_idx}"
    
    def test_sensitive_env_vars_marked_as_secrets(self, all_workflows):
        """Verify sensitive environment variable names use secrets."""
        sensitive_patterns = [
            'PASSWORD', 'TOKEN', 'API_KEY', 'SECRET', 
            'PRIVATE_KEY', 'CREDENTIALS', 'AUTH'
        ]
        
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                # Check job-level env
                job_env = job_config.get('env', {})
                for env_name, env_value in job_env.items():
                    if any(pattern in env_name.upper() for pattern in sensitive_patterns):
                        # Value should reference secrets
                        assert 'secrets.' in str(env_value), \
                            f"Sensitive env var {env_name} should use secrets in " \
                            f"{workflow['path']} job '{job_name}'"
                
                # Check step-level env
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    step_env = step.get('env', {})
                    for env_name, env_value in step_env.items():
                        if any(pattern in env_name.upper() for pattern in sensitive_patterns):
                            assert 'secrets.' in str(env_value), \
                                f"Sensitive env var {env_name} should use secrets in " \
                                f"{workflow['path']} job '{job_name}' step {step_idx}"


class TestWorkflowPermissionsHardening:
    """Tests for workflow permissions and least privilege."""
    
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
    
    def test_workflows_define_explicit_permissions(self, all_workflows):
        """Verify workflows explicitly define permissions."""
        for workflow in all_workflows:
            assert 'permissions' in workflow['content'], \
                f"Workflow {workflow['path']} should explicitly define permissions"
    
    def test_default_permissions_are_restrictive(self, all_workflows):
        """Verify default permissions follow least privilege."""
        for workflow in all_workflows:
            permissions = workflow['content'].get('permissions', {})
            
            # If permissions is a string, it should be 'read-all' or 'none'
            if isinstance(permissions, str):
                assert permissions in ['read-all', 'none'], \
                    f"Workflow {workflow['path']} has overly permissive default: {permissions}"
            
            # If permissions is a dict, check defaults
            elif isinstance(permissions, dict):
                # Most permissions should be read or none by default
                default_write_perms = []
                for perm_name, perm_value in permissions.items():
                    if perm_value == 'write':
                        default_write_perms.append(perm_name)
                
                # Only specific permissions should have write by default
                allowed_write_perms = {'contents', 'pull-requests', 'issues', 'checks'}
                unexpected_write = set(default_write_perms) - allowed_write_perms
                
                assert len(unexpected_write) == 0, \
                    f"Workflow {workflow['path']} has unexpected write permissions: {unexpected_write}"
    
    def test_no_workflows_with_write_all_permission(self, all_workflows):
        """Verify no workflow uses 'write-all' permission."""
        for workflow in all_workflows:
            permissions = workflow['content'].get('permissions', {})
            
            if isinstance(permissions, str):
                assert permissions != 'write-all', \
                    f"Workflow {workflow['path']} uses dangerous 'write-all' permission"
    
                        # Third-party actions must use full commit SHA
                        if '@' in action:
                            version = action.split('@')[1]
                            # Enforce 40-character hex string (commit SHA)
                            assert re.match(r'^[a-f0-9]{40}$', version), \
                                def test_third_party_actions_pinned_to_sha(self, all_workflows):
                                    """Verify third-party actions are pinned to a full commit SHA."""
                                    for workflow in all_workflows:
                                        jobs = workflow['content'].get('jobs', {})
                                        for job_name, job_config in jobs.items():
                                            steps = job_config.get('steps', [])
                                            for step in steps:
                                                action = step.get('uses', '')
                                                if not action:
                                                    continue
                                                # Skip local actions
                                                if action.startswith('./') or action.startswith('.\\'):
                        def test_third_party_actions_pinned_to_commit_sha(self, all_workflows):
                            """Verify third-party actions are pinned to full commit SHAs."""
                            for workflow in all_workflows:
                                jobs = workflow['content'].get('jobs', {})
                                for job_name, job_config in jobs.items():
                                    steps = job_config.get('steps', [])
                                    for step in steps:
                                        action = step.get('uses', '')
                                        if not action:
                                            continue
                                        # Skip local actions and official actions pinned by ref without '@'
                                        if '@' in action:
                                            version = action.split('@', 1)[1]
                                            # Enforce 40-character hex string (commit SHA)
                                            assert re.match(r'^[a-f0-9]{40}$', version), (
                                                f"Third-party action {action} in {workflow['path']} "
                                                f"job '{job_name}' must be pinned to a commit SHA for security"
                                            )

class TestWorkflowSupplyChainSecurity:
    """Tests for supply chain security in workflows."""
    
    @pytest.fixture
    def all_workflows(self) -> List[Dict[str, Any]]:
        """Load all workflow files."""
        workflow_dir = Path(".github/workflows")
        workflows = []
        for workflow_file in workflow_dir.glob("*.yml"):
            with open(workflow_file, 'r') as f:
                workflows.append({
                    'path': workflow_file,
                    'content': yaml.safe_load(f),
                    'raw': f.read()
                })
        return workflows
    
    def test_no_arbitrary_code_execution_from_artifacts(self, all_workflows):
        """Verify workflows don't execute code from downloaded artifacts."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                
                has_download_artifact = False
                for step_idx, step in enumerate(steps):
                    if 'actions/download-artifact' in step.get('uses', ''):
                        has_download_artifact = True
                    
                    # If we've downloaded artifacts, check subsequent steps
                    if has_download_artifact and 'run' in step:
                        run_command = step['run']
                        # Should not directly execute downloaded files
                        dangerous_patterns = [
                            r'bash\s+\$\{', r'sh\s+\$\{', r'python\s+\$\{',
                            r'\./\$\{', r'source\s+\$\{'
                        ]
                        for pattern in dangerous_patterns:
                            assert not re.search(pattern, run_command), \
                                f"Potential code execution from artifact in {workflow['path']} " \
                                f"job '{job_name}' step {step_idx}"
    
    def test_no_insecure_downloads(self, all_workflows):
        """Verify no insecure HTTP downloads in workflows."""
        for workflow in all_workflows:
            raw_content = workflow['raw']
            
            # Check for http:// (not https://) downloads
            insecure_downloads = re.findall(r'(curl|wget|download)\s+[^\s]*http://[^\s]+', raw_content, re.IGNORECASE)
            
            assert len(insecure_downloads) == 0, \
                f"Insecure HTTP download found in {workflow['path']}: {insecure_downloads}"
    
    def test_pip_installs_use_hash_verification(self, all_workflows):
        """Verify pip installations can use hash verification for critical packages."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'run' in step:
                        run_command = step['run']
                        
                        # If installing requirements file, suggest hash mode
                        if 'pip install' in run_command and 'requirements' in run_command:
                            # This is informational - hash mode is optional but recommended
                            # Just ensure it's not installing from untrusted sources
                            assert not re.search(r'--extra-index-url\s+http://', run_command), \
                                f"Pip installing from insecure index in {workflow['path']} " \
                                f"job '{job_name}' step {step_idx}"


class TestWorkflowIsolationAndSandboxing:
    """Tests for workflow isolation and sandboxing."""
    
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
    
    def test_pull_request_workflows_use_safe_checkout(self, all_workflows):
        """Verify PR workflows use safe checkout strategies."""
        for workflow in all_workflows:
            triggers = workflow['content'].get('on', {}) or workflow['content'].get(True, {})
            
            # If triggered by pull_request_target, must use explicit ref
            if 'pull_request_target' in triggers:
                jobs = workflow['content'].get('jobs', {})
                for job_name, job_config in jobs.items():
                    steps = job_config.get('steps', [])
                    checkout_steps = [s for s in steps if 'actions/checkout' in s.get('uses', '')]
                    
                    for checkout_step in checkout_steps:
                        # Must explicitly set ref for pull_request_target
                        assert 'with' in checkout_step and 'ref' in checkout_step.get('with', {}), \
                            f"pull_request_target must use explicit checkout ref in {workflow['path']} job '{job_name}'"
    def test_third_party_actions_pinned_to_sha(self, all_workflows):
        """Verify third-party actions are pinned to full commit SHAs."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step in steps:
                    action = step.get('uses', '')
                    if not action:
                        continue
                    # Allow local and docker actions without pin
                    if action.startswith('./') or action.startswith('docker://'):
                        continue
                    if '@' in action:
                        version = action.split('@', 1)[1]
                        assert re.match(r'^[a-f0-9]{40}$', version), (
                            f"Third-party action {action} in {workflow['path']} "
                            f"job '{job_name}' must be pinned to a commit SHA for security"
                        )
    def test_workflows_dont_persist_credentials(self, all_workflows):
        """Verify workflows don't persist git credentials."""
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                steps = job_config.get('steps', [])
                for step_idx, step in enumerate(steps):
                    if 'actions/checkout' in step.get('uses', ''):
                        with_config = step.get('with', {})
                        # persist-credentials should be false for security
                        if 'persist-credentials' in with_config:
                            assert with_config['persist-credentials'] is False, \
                                f"Credentials should not persist in {workflow['path']} " \
                                f"job '{job_name}' step {step_idx}"
    
    def test_container_jobs_use_trusted_images(self, all_workflows):
        """Verify container jobs use trusted/official images."""
        trusted_registries = [
            'docker.io/library/',  # Docker official images
            'ghcr.io/',            # GitHub Container Registry
            'mcr.microsoft.com/',  # Microsoft Container Registry
        ]
        
        for workflow in all_workflows:
            jobs = workflow['content'].get('jobs', {})
            for job_name, job_config in jobs.items():
                if 'container' in job_config:
                    container_image = job_config['container']
                    if isinstance(container_image, dict):
                        container_image = container_image.get('image', '')
                    
                    # Should use a trusted registry or official image
                    # Use a whitelist of official Docker images
                    official_images = ['python', 'node', 'ubuntu', 'alpine', 'debian', 'centos', 'nginx', 'postgres', 'mysql', 'redis']
                    is_official = ':' in container_image and '/' not in container_image.split(':')[0] and container_image.split(':')[0] in official_images
                    assert is_trusted or is_official, \
                        f"Untrusted container image in {workflow['path']} job '{job_name}': {container_image}"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])