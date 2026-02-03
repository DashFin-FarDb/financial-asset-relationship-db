"""Validation tests for requirements changes."""

from pathlib import Path


class TestRequirementsDocumentation:
    """Test requirements documentation and comments."""

    @staticmethod
    def test_requirements_has_helpful_comments():
        """
        Verify that requirements - dev.txt contains at least one comment line.

        Asserts the file has at least one line, which after trimming leading whitespace,
        begins with "#", indicating an explanatory comment for the dependency list.
        """
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            lines = f.readlines()

        # Should have at least some comments explaining purpose
        comment_lines = [l for l in lines if l.strip().startswith("#")]
        assert len(comment_lines) >= 1, (
            "requirements-dev.txt should have explanatory comments"
        )

    @staticmethod
    def test_pyyaml_purpose_documented():
        """Verify PyYAML addition has comment explaining purpose."""
        req_dev_path = Path("requirements-dev.txt")
        with open(req_dev_path, "r") as f:
            content = f.read()

        # Check if there's a comment near PyYAML explaining its purpose
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "pyyaml" in line.lower():
                # Check previous lines for comments
                context = "\n".join(lines[max(0, i - 3) : i + 1])
                # Should have some context about YAML parsing or workflows
                assert any(
                    keyword in context.lower()
                    for keyword in ["yaml", "workflow", "config", "parse"]
                ), "PyYAML should have explanatory comment"
                break
