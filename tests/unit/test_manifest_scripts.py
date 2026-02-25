"""Unit tests for manifest deduplication and validation scripts."""

from pathlib import Path

import pytest


class TestManifestScripts:
    """Test cases for manifest deduplication and validation scripts."""

    @pytest.fixture
    def sample_manifest_with_duplicates(self):
        """Create a sample manifest with duplicate sections."""
        return """# System Manifest

## Project Overview

- Name: test-project
- Description: Test project

## Current Status

- Current Phase: Testing
- Last Updated: 2026-02-24

## Project Structure

- 10 py files
- 5 js files

## Dependencies

## Project Directory Structure

First occurrence of directory structure.

## PY Dependencies

First occurrence of PY dependencies.

## Project Directory Structure

Second occurrence of directory structure (should be removed).

## PY Dependencies

Second occurrence of PY dependencies (should be removed).

## TS Dependencies

First and only occurrence of TS dependencies.
"""

    @pytest.fixture
    def sample_manifest_clean(self):
        """Create a clean sample manifest without duplicates."""
        return """# System Manifest

## Project Overview

- Name: test-project
- Description: Test project

## Current Status

- Current Phase: Testing
- Last Updated: 2026-02-24

## Project Structure

- 10 py files
- 5 js files

## Dependencies

## Project Directory Structure

First occurrence of directory structure.

## PY Dependencies

First occurrence of PY dependencies.

## TS Dependencies

First and only occurrence of TS dependencies.
"""

    def test_validate_manifest_detects_duplicates(self, sample_manifest_with_duplicates):
        """Test that duplicate headings are detected in the manifest."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from validate_manifest import _collect_headings

        lines = sample_manifest_with_duplicates.splitlines(keepends=True)
        occurrences = _collect_headings(lines)
        duplicates = {h: nums for h, nums in occurrences.items() if len(nums) > 1}

        assert len(duplicates) > 0, "Expected duplicate headings to be detected"

    def test_validate_manifest_accepts_clean_file(self, sample_manifest_clean):
        """Test that a clean manifest has no duplicate headings."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from validate_manifest import _collect_headings

        lines = sample_manifest_clean.splitlines(keepends=True)
        heading_occurrences = _collect_headings(lines)
        duplicates = {
            heading: positions
            for heading, positions in heading_occurrences.items()
            if len(positions) > 1
        }

        assert duplicates == {}

    def test_deduplicate_removes_duplicates(self, sample_manifest_with_duplicates, tmp_path):
        """Test that the deduplication script removes duplicate sections."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from deduplicate_manifest import (
            deduplicate_sections,
            parse_manifest,
            reconstruct_manifest,
        )

        # Parse preamble and sections
        preamble, sections = parse_manifest(sample_manifest_with_duplicates)

        # Verify preamble is preserved
        assert "# System Manifest" in preamble

        # Count sections
        heading_counts = {}
        for heading, _ in sections:
            heading_counts[heading] = heading_counts.get(heading, 0) + 1

        # Verify duplicates exist
        assert heading_counts["Project Directory Structure"] == 2
        assert heading_counts["PY Dependencies"] == 2

        # Deduplicate
        deduplicated = deduplicate_sections(sections)

        # Count deduplicated sections
        dedup_heading_counts = {}
        for heading, _ in deduplicated:
            dedup_heading_counts[heading] = dedup_heading_counts.get(heading, 0) + 1

        # Verify duplicates removed
        assert dedup_heading_counts["Project Directory Structure"] == 1
        assert dedup_heading_counts["PY Dependencies"] == 1
        assert dedup_heading_counts["TS Dependencies"] == 1

        # Verify content is from last occurrence (not first)
        content_dict = dict(deduplicated)
        assert "Second occurrence" in content_dict["Project Directory Structure"]
        assert "First occurrence" not in content_dict["Project Directory Structure"]
        assert "Second occurrence" in content_dict["PY Dependencies"]
        assert "First occurrence" not in content_dict["PY Dependencies"]

        # Reconstruct and verify preamble is included
        reconstructed = reconstruct_manifest(preamble, deduplicated)
        assert "# System Manifest" in reconstructed

    def test_deduplicate_preserves_order(self, sample_manifest_with_duplicates):
        """Test that deduplication preserves the order of first occurrence."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from deduplicate_manifest import deduplicate_sections, parse_manifest

        # Parse and deduplicate
        _, sections = parse_manifest(sample_manifest_with_duplicates)
        deduplicated = deduplicate_sections(sections)

        # Extract headings in order
        headings = [h for h, _ in deduplicated]

        # Verify order: Project Overview should come before Project Structure, etc.
        assert headings.index("Project Overview") < headings.index("Current Status")
        assert headings.index("Current Status") < headings.index("Project Structure")
        assert headings.index("Project Directory Structure") < headings.index("PY Dependencies")
        assert headings.index("PY Dependencies") < headings.index("TS Dependencies")

    def test_preamble_preservation(self, sample_manifest_with_duplicates):
        """Test that the preamble is preserved in the reconstructed manifest."""
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from deduplicate_manifest import (
            deduplicate_sections,
            parse_manifest,
            reconstruct_manifest,
        )

        # Parse
        preamble, sections = parse_manifest(sample_manifest_with_duplicates)

        # Verify preamble contains the # System Manifest header
        assert "# System Manifest" in preamble
        assert preamble.strip().startswith("# System Manifest")

        # Deduplicate
        deduplicated = deduplicate_sections(sections)

        # Reconstruct
        reconstructed = reconstruct_manifest(preamble, deduplicated)

        # Verify preamble is at the beginning of reconstructed content
        assert reconstructed.strip().startswith("# System Manifest")
        # Verify sections follow the preamble
        assert "## Project Overview" in reconstructed

    def test_system_manifest_is_clean(self):
        """Test that systemManifest.md has no duplicate sections."""
        manifest_path = Path(".elastic-copilot/memory/systemManifest.md")

        if not manifest_path.exists():
            pytest.skip("systemManifest.md not found")

        # Import here to avoid circular imports
        import sys

        sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
        from validate_manifest import check_duplicate_headings

        # Should return 0 (no duplicates)
        exit_code = check_duplicate_headings(manifest_path)
        assert exit_code == 0, (
            "systemManifest.md contains duplicate sections. Run 'python scripts/deduplicate_manifest.py' to fix."
        )
