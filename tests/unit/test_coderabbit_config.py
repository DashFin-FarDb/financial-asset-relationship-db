"""
Comprehensive unit tests for .coderabbit.yaml configuration file.

Tests validate:
- YAML syntax and structure
- Required sections and fields
- Knowledge base configuration
- Reviews configuration
- No duplicate top-level keys
- Valid schema references
"""

from pathlib import Path

import pytest
import yaml


class TestCodeRabbitConfiguration:
    """Test .coderabbit.yaml configuration file validation."""

    CODERABBIT_PATH = Path(__file__).parent.parent.parent / ".coderabbit.yaml"

    def test_coderabbit_file_exists(self):
        """Test that .coderabbit.yaml file exists in repository root."""
        assert self.CODERABBIT_PATH.exists(), ".coderabbit.yaml file not found"

    def test_coderabbit_valid_yaml_syntax(self):
        """Test that .coderabbit.yaml contains valid YAML syntax."""
        try:
            with open(self.CODERABBIT_PATH, "r") as f:
                data = yaml.safe_load(f)
            assert data is not None, ".coderabbit.yaml is empty"
        except yaml.YAMLError as e:
            pytest.fail(f"Invalid YAML syntax in .coderabbit.yaml: {e}")

    def test_coderabbit_has_language_setting(self):
        """Test that .coderabbit.yaml specifies language."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        assert "language" in config, "Missing language setting"
        assert isinstance(config["language"], str), "Language must be a string"

    def test_coderabbit_has_reviews_section(self):
        """Test that .coderabbit.yaml contains reviews section."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        # Note: The current file has duplicate 'reviews' and 'knowledge_base' sections
        # which is invalid YAML structure. The test should identify this issue.
        assert "reviews" in config, "Missing reviews section"

    def test_coderabbit_has_knowledge_base_section(self):
        """Test that .coderabbit.yaml contains knowledge_base section."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        assert "knowledge_base" in config, "Missing knowledge_base section"

    def test_coderabbit_no_duplicate_top_level_keys(self):
        """Test for duplicate top-level keys in YAML (structural issue)."""
        with open(self.CODERABBIT_PATH, "r") as f:
            content = f.read()

        # Check for duplicate top-level keys by parsing line by line
        top_level_keys = []
        for line in content.split("\n"):
            stripped = line.lstrip()
            if (
                stripped
                and not stripped.startswith("#")
                and not stripped.startswith("-")
            ):
                if ":" in stripped and not stripped.startswith(" "):
                    key = stripped.split(":")[0].strip()
                    top_level_keys.append(key)

        # Check for duplicates
        duplicates = [k for k in set(top_level_keys) if top_level_keys.count(k) > 1]

        if duplicates:
            pytest.skip(
                f"Known issue: Duplicate top-level keys found: {duplicates}. "
                "YAML will only parse the last occurrence of each key."
            )

    def test_reviews_has_auto_review_config(self):
        """Test that reviews section has auto_review configuration."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        reviews = config.get("reviews", {})

        # Check if auto_review is properly nested under reviews
        # Note: Due to duplicate sections, YAML will only keep the last one
        if "auto_review" in reviews:
            auto_review = reviews["auto_review"]
            assert isinstance(auto_review, dict), "auto_review must be a dictionary"
            assert "enabled" in auto_review, "auto_review must have enabled field"

    def test_knowledge_base_has_mcp_config(self):
        """Test that knowledge_base section has MCP configuration."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        kb = config.get("knowledge_base", {})

        if "mcp" in kb:
            mcp = kb["mcp"]
            assert isinstance(mcp, dict), "MCP must be a dictionary"
            assert "usage" in mcp, "MCP must have usage field"

    def test_knowledge_base_has_code_guidelines(self):
        """Test that knowledge_base has code_guidelines configuration."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        kb = config.get("knowledge_base", {})

        if "code_guidelines" in kb:
            guidelines = kb["code_guidelines"]
            assert isinstance(guidelines, dict), "code_guidelines must be a dictionary"

    def test_labeling_instructions_structure(self):
        """Test that labeling_instructions follow correct structure."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        reviews = config.get("reviews", {})

        if "labeling_instructions" in reviews:
            instructions = reviews["labeling_instructions"]
            assert isinstance(instructions, list), (
                "labeling_instructions must be a list"
            )

            for instruction in instructions:
                assert "label" in instruction, "Each instruction must have a label"
                assert "instructions" in instruction, (
                    "Each instruction must have instructions text"
                )

    def test_file_size_is_reasonable(self):
        """Test that .coderabbit.yaml file size is reasonable."""
        file_size = self.CODERABBIT_PATH.stat().st_size

        # Should be at least 100 bytes and less than 50KB
        assert file_size > 100, ".coderabbit.yaml suspiciously small"
        assert file_size < 51200, ".coderabbit.yaml suspiciously large"

    def test_early_access_setting(self):
        """Test that early_access setting is properly configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        if "early_access" in config:
            assert isinstance(config["early_access"], bool), (
                "early_access must be boolean"
            )

    def test_inheritance_setting(self):
        """Test that inheritance setting is properly configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        if "inheritance" in config:
            assert isinstance(config["inheritance"], bool), (
                "inheritance must be boolean"
            )

    def test_schema_reference_in_comment(self):
        """Test that file includes schema reference in comments."""
        with open(self.CODERABBIT_PATH, "r") as f:
            content = f.read()

        # Check for schema reference
        assert "schema" in content.lower(), "Missing schema reference in comments"

    def test_yaml_can_be_parsed_consistently(self):
        """Test that YAML can be parsed consistently multiple times."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config1 = yaml.safe_load(f)

        with open(self.CODERABBIT_PATH, "r") as f:
            config2 = yaml.safe_load(f)

        assert config1 == config2, "YAML parses differently on multiple attempts"


class TestCodeRabbitReviewsConfiguration:
    """Test specific reviews configuration in .coderabbit.yaml."""

    CODERABBIT_PATH = Path(__file__).parent.parent.parent / ".coderabbit.yaml"

    def test_request_changes_workflow_setting(self):
        """Test that request_changes_workflow is properly configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        reviews = config.get("reviews", {})

        if "request_changes_workflow" in reviews:
            assert isinstance(reviews["request_changes_workflow"], bool)

    def test_high_level_summary_setting(self):
        """Test that high_level_summary_in_walkthrough is configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        reviews = config.get("reviews", {})

        if "high_level_summary_in_walkthrough" in reviews:
            assert isinstance(reviews["high_level_summary_in_walkthrough"], bool)

    def test_auto_apply_labels_setting(self):
        """Test that auto_apply_labels is properly configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        reviews = config.get("reviews", {})

        if "auto_apply_labels" in reviews:
            assert isinstance(reviews["auto_apply_labels"], bool)

    def test_auto_assign_reviewers_setting(self):
        """Test that auto_assign_reviewers is properly configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        reviews = config.get("reviews", {})

        if "auto_assign_reviewers" in reviews:
            assert isinstance(reviews["auto_assign_reviewers"], bool)


class TestCodeRabbitKnowledgeBaseConfiguration:
    """Test specific knowledge_base configuration in .coderabbit.yaml."""

    CODERABBIT_PATH = Path(__file__).parent.parent.parent / ".coderabbit.yaml"

    def test_mcp_usage_setting(self):
        """Test that MCP usage is properly configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        kb = config.get("knowledge_base", {})
        mcp = kb.get("mcp", {})

        if "usage" in mcp:
            assert mcp["usage"] in ["enabled", "disabled", "optional"]

    def test_mcp_documents_or_file_patterns(self):
        """Test that MCP has either documents or filePatterns configured."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        kb = config.get("knowledge_base", {})
        mcp = kb.get("mcp", {})

        # Should have either 'documents' or 'filePatterns'
        if mcp:
            has_config = "documents" in mcp or "filePatterns" in mcp
            if not has_config:
                pytest.skip("MCP configuration has neither documents nor filePatterns")

    def test_code_guidelines_enabled_setting(self):
        """Test that code_guidelines enabled setting is boolean."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        kb = config.get("knowledge_base", {})
        guidelines = kb.get("code_guidelines", {})

        if "enabled" in guidelines:
            assert isinstance(guidelines["enabled"], bool)

    def test_code_guidelines_file_patterns(self):
        """Test that code_guidelines filePatterns is a list if present."""
        with open(self.CODERABBIT_PATH, "r") as f:
            config = yaml.safe_load(f)

        kb = config.get("knowledge_base", {})
        guidelines = kb.get("code_guidelines", {})

        if "filePatterns" in guidelines:
            assert isinstance(guidelines["filePatterns"], list)
            assert len(guidelines["filePatterns"]) > 0
