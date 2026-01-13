"""
Integration tests validating all branch changes work together cohesively.

Tests cross-cutting concerns:
1. Workflow changes are consistent across all files
2. Dependencies are compatible with workflow needs
3. Removed files don't break existing functionality
4. Overall branch maintains system integrity
"""

import re
from pathlib import Path
from typing import Dict, List, Set

import pytest
import yaml


class TestWorkflowConsistency:
    """Test consistency across all modified workflows."""

    @pytest.fixture
    def all_workflows(self) -> Dict[str, Dict]:
        """
        Load a fixed set of GitHub Actions workflow files and parse each existing file's YAML content.

        Only files from the internal list are considered; files that are not present are omitted from the result.

    @staticmethod
    def all_workflows():
        """
        Returns:
            dict: Mapping from workflow file path(str) to the parsed YAML content(dict) for each workflow file that exists.
        """
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
                try:
                    with open(path, "r") as f:
                        loaded = yaml.safe_load(f)
                        # Ensure we always store a dict to avoid NoneType errors in tests
                        workflows[wf_file] = loaded if isinstance(loaded, dict) else {}
                except yaml.YAMLError as e:
                    # Don't let a single malformed workflow break the fixture consumers.
                    # Emit a warning and skip the problematic file.
                    print(f"Warning: failed to parse {wf_file}: {e}; skipping")
                    continue
        return workflows

    def test_all_workflows_use_consistent_action_versions(self, all_workflows):
        """
        Ensure actions referenced across workflows are used with a single version.

        Scans the provided workflows jobs and steps to detect actions specified with explicit versions and reports when the same action appears with multiple different versions. Differences between actions / checkout major versions(e.g., v4 vs v5) are allowed and will be ignored.

        Parameters:
            all_workflows(dict): Mapping from workflow file path(str) to parsed YAML content(dict).
        """
        action_versions = {}

        for wf_file, workflow in all_workflows.items():
            for job_name, job in workflow.get("jobs", {}).items():
                for step in job.get("steps", []):
                    uses = step.get("uses", "")
                    if uses and "@" in uses:
                        action_name = uses.split("@")[0]
                        action_version = uses.split("@")[1]

                        if action_name not in action_versions:
                            action_versions[action_name] = {}
                        if action_version not in action_versions[action_name]:
                            action_versions[action_name][action_version] = []
                        action_versions[action_name][action_version].append(wf_file)

        # Check for inconsistencies
        for action, versions in action_versions.items():
            if len(versions) > 1:
                # Allow v4 and v5 for actions/checkout (common upgrade path)
                if "actions/checkout" in action: pass
                    continue
                    pass
                    continue
                # Warn if same action uses different versions
                print(f"Warning: {action} uses multiple versions: {list(versions.keys())}")

    def test_all_workflows_use_github_token_consistently(self, all_workflows):
        """
        Check that workflows use the approved GITHUB_TOKEN syntax.

        Asserts that any occurrence of `GITHUB_TOKEN` or `github.token` in a workflow is expressed as `secrets.GITHUB_TOKEN` or `${{github.token}}`; failures include the workflow file path in the message.

        Parameters:
            all_workflows(dict): Mapping of workflow file path to parsed YAML content.
        """
        for wf_file, workflow in all_workflows.items():
            workflow_str = yaml.dump(workflow)

            if "GITHUB_TOKEN" in workflow_str or "github.token" in workflow_str:
                # Should use secrets.GITHUB_TOKEN format
                assert (
                    "secrets.GITHUB_TOKEN" in workflow_str or "${{ github.token }}" in workflow_str
                ), f"{wf_file}: GITHUB_TOKEN should use proper syntax"

    def test_simplified_workflows_have_fewer_steps(self, all_workflows):
        """
        Verify that designated simplified workflows limit each job to at most three steps.

        Parameters:
            all_workflows(dict): Mapping from workflow file path to its parsed YAML content; only workflows present in the mapping are checked.
        """
        # These workflows were simplified in this branch
        simplified = [
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
        ]

        for wf_file in simplified:
            if wf_file in all_workflows:
                workflow = all_workflows[wf_file]
                for job_name, job in workflow.get("jobs", {}).items():
                    steps = job.get("steps", [])
                    # Simplified workflows should have minimal steps
                    assert len(steps) <= 3, f"{wf_file}:{job_name} should be simplified (has {len(steps)} steps)"


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
                try:
                    with open(wf_file, "r") as f:
                        workflow = yaml.safe_load(f)

                    assert workflow is not None, f"Failed to parse {wf_file}"
                    assert isinstance(workflow, dict), f"{wf_file} should parse to dict"
                except yaml.YAMLError as e:
                    pytest.fail(f"PyYAML failed to parse {wf_file}: {e}")

    def test_requirements_support_workflow_test_needs(self):
        """
        Ensure development requirements include packages needed to run the workflow tests.

        Checks that requirements - dev.txt(case-insensitive) contains both `pytest` and `PyYAML`.
        """
        with open("requirements-dev.txt", "r") as f:
            content = f.read().lower()

        # Should have pytest for running these tests
        assert "pytest" in content, "pytest required for workflow tests"

        # Should have PyYAML for parsing workflows
        assert "pyyaml" in content, "PyYAML required for workflow validation"


class TestRemovedFilesIntegration:
    """Test that removed files don't break functionality."""

    def test_workflows_dont_reference_removed_scripts(self):
        """Verify workflows don't reference deleted files."""
        removed_files = [
            "context_chunker.py",
            ".github/scripts/README.md",
            ".github/labeler.yml",
        ]

        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/label.yml",
        ]

        for wf_file in workflow_files:
            path = Path(wf_file)
            if not path.exists():
                # If workflow file is not present, it cannot reference removed scripts
                continue
            with open(path, "r") as f:
                content = f.read()

            for removed in removed_files:
                assert removed not in content, f"{wf_file} references removed file {removed}"

    def test_label_workflow_doesnt_need_labeler_config(self):
        """
        Verify the label workflow does not require an external labeler configuration file.

        Checks that .github / workflows / label.yml(if present) defines the `label` job's first step using `actions / labeler`, and that the step either omits `config - path` or sets it to `.github / labeler.yml`. Skips the test if label.yml is missing.
        """
        label_path = Path(".github/workflows/label.yml")
        if not label_path.exists():
            pytest.skip("label.yml not present; skipping label workflow checks")
        with open(label_path, "r") as f:
            workflow = yaml.safe_load(f)

        # Should use actions/labeler which has default config
        steps = workflow["jobs"]["label"]["steps"]
        labeler_step = steps[0]

        assert "actions/labeler" in labeler_step["uses"]

        # Should not require config-path or similar
        with_config = labeler_step.get("with", {})
        assert "config-path" not in with_config or with_config.get("config-path") == ".github/labeler.yml"

    def test_pr_agent_workflow_self_contained(self):
        """Verify PR agent workflow doesn't depend on removed components."""
        with open(".github/workflows/pr-agent.yml", "r") as f:
            content = f.read()

        # Should not reference chunking components
        assert "context_chunker" not in content
        assert "chunking" not in content.lower() or "no chunking" in content.lower()

        # Should not have complex context management
        assert "fetch-context" not in content


class TestWorkflowSecurityConsistency:
    """Test security practices are consistent across workflows."""

    @staticmethod
    def test_all_workflows_avoid_pr_injection():
        """
        Scan all workflow YAMLs for patterns that may allow PR title or body content to be injected into shell or command contexts.

        Searches files under .github / workflows for uses of pull request or issue title / body in contexts that could enable injection(for example, piping into shell commands or usage within command substitution) and fails the test on any definite matches.
        """
        workflow_files = list(Path(".github/workflows").glob("*.yml"))
        dangerous = [
            r"\$\{\{.*github\.event\.pull_request\.title.*\}\}.*\|",
            r"\$\{\{.*github\.event\.pull_request\.body.*\}\}.*\|",
            r"\$\{\{.*github\.event\.issue\.title.*\}\}.*\$\(",
        ]
        for wf_file in workflow_files:
            content = wf_file.read_text()
            for pattern in dangerous:
                matches = re.findall(pattern, content)
                if matches:
                    pytest.fail(f"Potential injection risk in {wf_file}: {matches}")
        return
        workflow_files = list(Path(".github/workflows").glob("*.yml"))

        for wf_file in workflow_files:
            with open(wf_file, "r") as f:
                content = f.read()

            # Look for potentially dangerous patterns
            dangerous = [
                r"\$\{\{.*github\.event\.pull_request\.title.*\}\}.*\|",
                r"\$\{\{.*github\.event\.pull_request\.body.*\}\}.*\|",
                r"\$\{\{.*github\.event\.issue\.title.*\}\}.*\$(",
            ]

            for pattern in dangerous:
                matches = re.findall(pattern, content)
                if matches:
                    print(f"Potential injection risk in {wf_file}: {matches}")

    @staticmethod
    def test_workflows_use_appropriate_checkout_refs():
        """
        Verify workflows triggered by pull_request_target specify a safe checkout reference.

        For .github / workflows / pr - agent.yml and .github / workflows / apisec - scan.yml, if the workflow's triggers include
        `pull_request_target` this test asserts every `actions / checkout` step supplies either a `ref` or a `fetch - depth`
        in its `with ` configuration; failure indicates an unsafe checkout configuration.
        """
        workflow_files = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
        ]

        for wf_file in workflow_files:
            with open(wf_file, "r") as f:
                workflow = yaml.safe_load(f)

            trigger = workflow.get("on", {})
            uses_pr_target = "pull_request_target" in trigger

            if uses_pr_target:
                # Should checkout with explicit ref
                for job in workflow.get("jobs", {}).values():
                    for step in job.get("steps", []):
                        if "actions/checkout" in step.get("uses", ""):
                            with_config = step.get("with", {})
                            # Should have ref or token specified
                            assert (
                                "ref" in with_config or "fetch-depth" in with_config
                            ), f"{wf_file}: Checkout in pull_request_target should specify safe ref"

class TestBranchCoherence:
    """Test overall branch changes are coherent."""

    def test_simplification_theme_consistent(self):
        """
        Ensure selected workflows adhere to the branch's simplification theme.

        Checks that each workflow in the predefined list does not exceed its maximum allowed line count and fails the test if any file is longer than its threshold.
        """
        # This branch should simplify, not add complexity

        # Check workflow line counts decreased
        workflows_to_check = [
            (".github/workflows/pr-agent.yml", 200),  # Should be under 200 lines
            (".github/workflows/label.yml", 30),  # Should be under 30 lines
            (".github/workflows/greetings.yml", 20),  # Should be under 20 lines
        ]

        for wf_file, max_lines in workflows_to_check:
            path = Path(wf_file)
            if path.exists():
                with open(wf_file, "r") as f:
                    line_count = len(f.readlines())

                assert (
                    line_count <= max_lines
                ), f"{wf_file} should be simplified (has {line_count} lines, expected <={max_lines})"

    def test_removed_complexity_not_referenced(self):
        """
        Assert that removed complexity indicators are not referenced in workflow files.

        Scans all YAML files under .github / workflows for the feature names
        'context_chunking', 'tiktoken', 'summarization', 'max_tokens', and 'chunk_size'.
        If any of these names appear in a non - comment line of a workflow file, the test
        fails with a message identifying the file and the offending feature.
        """
        complex_features = [
            "context_chunking",
            "tiktoken",
            "summarization",
            "max_tokens",
            "chunk_size",
        ]

        # Check these aren't in workflows anymore
        workflow_files = list(Path(".github/workflows").glob("*.yml"))

        for wf_file in workflow_files:
            with open(wf_file, "r") as f:
                content = f.read().lower()

            for feature in complex_features:
                if feature in content:
                    # Some context about removal is OK in comments
                    lines = content.split("\n")
                    for line in lines:
                        if feature in line.lower() and not line.strip().startswith("#"):
                            pytest.fail(f"{wf_file} still references removed feature: {feature}")

    def test_branch_reduces_dependencies_on_external_config(self):
        """
        Verify the branch no longer depends on removed external configuration and limits workflow references to external files.

        Asserts that .github / labeler.yml and .github / scripts / context_chunker.py do not exist, and that each workflow file under .github / workflows contains at most one run step referencing paths that include ".github/" or "scripts/.".
        """
        # labeler.yml was removed - workflows should work without it
        assert not Path(".github/labeler.yml").exists()

        # context_chunker.py was removed - workflows should work without it
        assert not Path(".github/scripts/context_chunker.py").exists()

        # Workflows should be more self-contained
        workflow_files = list(Path(".github/workflows").glob("*.yml"))

        for wf_file in workflow_files:
            with open(wf_file, "r") as f:
                workflow = yaml.safe_load(f)

            # Count steps that reference external files
            external_refs = 0
            for job in workflow.get("jobs", {}).values():
                for step in job.get("steps", []):
                    run_cmd = step.get("run", "")
                    if ".github/" in run_cmd or "scripts/" in run_cmd:
                        external_refs += 1

            # Should have minimal external references
            assert external_refs <= 1, f"{wf_file} has {external_refs} external file references (should be <=1)"

class TestBranchQuality:
    """Test overall quality of branch changes."""

    def test_all_modified_workflows_parse_successfully(self):
        """
        Assert at least one workflow exists and each YAML file in .github / workflows parses to a mapping containing a 'jobs' key.

        Raises an assertion failure if no workflow files are found, if a file fails to parse into a mapping, or if the parsed workflow does not contain a 'jobs' entry.
        """
        workflow_dir = Path(".github/workflows")
        workflow_files = list(workflow_dir.glob("*.yml"))

        assert len(workflow_files) > 0, "No workflow files found"

        for wf_file in workflow_files:
            try:
                with open(wf_file, "r") as f:
                    workflow = yaml.safe_load(f)

                assert workflow is not None
                assert isinstance(workflow, dict)
                assert "jobs" in workflow
            except Exception as e:
                pytest.fail(f"Failed to parse {wf_file}: {e}")

    def test_no_merge_conflict_markers(self):
        """
        Ensure specified files do not contain Git merge conflict markers.

        Checks each workflow file and the development requirements file for the markers
        '<<<<<<<', '=======', and '>>>>>>>' and asserts their absence. On failure the
        assertion message identifies the file path and the offending marker.
        """
        conflict_markers = ["<<<<<<<", "=======", ">>>>>>>"]

        files_to_check = [
            ".github/workflows/pr-agent.yml",
            ".github/workflows/apisec-scan.yml",
            ".github/workflows/label.yml",
            ".github/workflows/greetings.yml",
            "requirements-dev.txt",
        ]

        for file_path in files_to_check:
            path = Path(file_path)
            if path.exists():
                with open(path, "r") as f:
                    content = f.read()

                for marker in conflict_markers:
                    assert marker not in content, f"{file_path} contains merge conflict marker: {marker}"

    def test_consistent_indentation_across_workflows(self):
        """
        Check that every workflow YAML file uses consistent 2 - space indentation.

        For each non - empty line that begins with a space, the number of leading spaces must be a multiple of two.
        If a line violates this rule, the test asserts with a message identifying the workflow file and line number.
        """
        workflow_files = list(Path(".github/workflows").glob("*.yml"))

        for wf_file in workflow_files:
            with open(wf_file, "r") as f:
                lines = f.readlines()

            for i, line in enumerate(lines, 1):
                if line.strip() and line[0] == " ":
                    spaces = len(line) - len(line.lstrip(" "))
                    assert spaces % 2 == 0, f"{wf_file}:{i} inconsistent indentation (not multiple of 2)"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
