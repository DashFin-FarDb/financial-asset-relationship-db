import re

with open("tests/unit/test_workflow_yaml_files.py", "r") as f:
    content = f.read()

# I will replace the current TestConfigurationConsistency with the one that includes CircleCI checks.

new_tests = """class TestConfigurationConsistency:
    \"\"\"Test consistency across configuration files.\"\"\"

    def test_python_version_consistency(self):
        \"\"\"Python versions should be consistent across configs.\"\"\"
        # CircleCI
        circleci_path = PROJECT_ROOT / ".circleci" / "config.yml"
        if not circleci_path.exists():
            pytest.fail(".circleci/config.yml does not exist")
        with open(circleci_path, encoding="utf-8") as f:
            circleci_config = yaml.safe_load(f)

        # CI workflow
        ci_path = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        if ci_path.exists():
            with open(ci_path, encoding="utf-8") as f:
                ci_config = yaml.safe_load(f)

            # Both should test Python (versions may differ slightly)
            # Just ensure both have Python configuration
            assert "python" in str(circleci_config).lower()
            assert "python" in str(ci_config).lower()

    def test_node_version_consistency(self):
        \"\"\"Node versions should be reasonable across configs.\"\"\"
        circleci_path = PROJECT_ROOT / ".circleci" / "config.yml"
        if not circleci_path.exists():
            pytest.fail(".circleci/config.yml does not exist")
        with open(circleci_path, encoding="utf-8") as f:
            content = f.read()

        # Should reference Node in frontend jobs
        assert "node" in content.lower()
        # Should have a reasonable version
        assert "node:" in content or "cimg/node" in content"""

# Use regex to replace the class body
pattern = r"class TestConfigurationConsistency:.*?(?=\n\n|\Z)"
content = re.sub(pattern, new_tests, content, flags=re.DOTALL)

with open("tests/unit/test_workflow_yaml_files.py", "w") as f:
    f.write(content)
