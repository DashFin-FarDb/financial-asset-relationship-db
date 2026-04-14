"""Unit tests for analyze_pr.py.

This module covers the functions added or changed in this PR:
- _format_list_items(): new extracted helper
- _format_file_categories(): new extracted helper
- _format_large_files(): new extracted helper
- _format_related_issues(): new extracted helper
- _get_recommendations(): new extracted helper
- find_related_issues(): bug-fix for None lastindex handling
- write_output(): security fix – GITHUB_STEP_SUMMARY path validation
"""

from __future__ import annotations

import os
import sys
import tempfile
from typing import Any, Dict
from unittest.mock import patch

# Add the pr-copilot scripts directory to sys.path so analyze_pr can be
# imported directly (same pattern used by test_generate_status.py).
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), "../../.github/pr-copilot/scripts"),
)

import analyze_pr  # noqa: E402

# ---------------------------------------------------------------------------
# _format_list_items
# ---------------------------------------------------------------------------


class TestFormatListItems:
    """Tests for _format_list_items helper."""

    def test_empty_items_returns_empty_string(self):
        """Empty list produces an empty string with no header."""
        result = analyze_pr._format_list_items([], "Header")
        assert result == ""

    def test_single_item_produces_bullet_with_header(self):
        """A single item list produces bold header and one bullet."""
        result = analyze_pr._format_list_items(["item one"], "My Header")
        assert "**My Header**" in result
        assert "- item one" in result

    def test_multiple_items_each_on_own_bullet(self):
        """Multiple items are each rendered as a separate bullet."""
        items = ["alpha", "beta", "gamma"]
        result = analyze_pr._format_list_items(items, "Title")
        for item in items:
            assert f"- {item}" in result

    def test_header_is_bold_markdown(self):
        """The header is wrapped in double-asterisks (bold Markdown)."""
        result = analyze_pr._format_list_items(["x"], "SomeTitle")
        assert "**SomeTitle**" in result

    def test_empty_string_item_is_included(self):
        """An empty-string item still produces a bullet."""
        result = analyze_pr._format_list_items([""], "H")
        assert "- \n" in result

    def test_leading_newline_present(self):
        """The returned string starts with a newline so it visually separates."""
        result = analyze_pr._format_list_items(["item"], "H")
        assert result.startswith("\n")


# ---------------------------------------------------------------------------
# _format_file_categories
# ---------------------------------------------------------------------------


class TestFormatFileCategories:
    """Tests for _format_file_categories helper."""

    def test_single_category(self):
        """One category produces one bullet line."""
        file_analysis: Dict[str, Any] = {"file_categories": {"python": 3}}
        result = analyze_pr._format_file_categories(file_analysis)
        assert "- Python: 3" in result

    def test_multiple_categories(self):
        """Multiple categories each produce a bullet with title-cased name."""
        file_analysis = {"file_categories": {"python": 5, "javascript": 2}}
        result = analyze_pr._format_file_categories(file_analysis)
        assert "- Python: 5" in result
        assert "- Javascript: 2" in result

    def test_category_names_are_title_cased(self):
        """Category names are title-cased in output."""
        file_analysis = {"file_categories": {"workflow": 1}}
        result = analyze_pr._format_file_categories(file_analysis)
        assert "- Workflow: 1" in result

    def test_empty_categories(self):
        """Empty dict produces an empty string."""
        file_analysis: Dict[str, Any] = {"file_categories": {}}
        result = analyze_pr._format_file_categories(file_analysis)
        assert result == ""

    def test_zero_count_category_is_included(self):
        """A category with zero count is still shown."""
        file_analysis = {"file_categories": {"test": 0}}
        result = analyze_pr._format_file_categories(file_analysis)
        assert "- Test: 0" in result


# ---------------------------------------------------------------------------
# _format_large_files
# ---------------------------------------------------------------------------


class TestFormatLargeFiles:
    """Tests for _format_large_files helper."""

    def test_no_large_files_returns_empty_string(self):
        """No large files yields an empty string."""
        file_analysis: Dict[str, Any] = {"large_files": []}
        result = analyze_pr._format_large_files(file_analysis)
        assert result == ""

    def test_single_large_file_produces_section(self):
        """A single large file produces the section header and one bullet."""
        file_analysis = {
            "large_files": [{"filename": "src/big.py", "changes": 600, "additions": 400, "deletions": 200}]
        }
        result = analyze_pr._format_large_files(file_analysis)
        assert "**Large Files (>500 lines):**" in result
        assert "`src/big.py`" in result
        assert "600 lines" in result

    def test_multiple_large_files_each_appear(self):
        """Multiple large files each appear as a bullet."""
        file_analysis = {
            "large_files": [
                {"filename": "a.py", "changes": 700, "additions": 500, "deletions": 200},
                {"filename": "b.py", "changes": 900, "additions": 800, "deletions": 100},
            ]
        }
        result = analyze_pr._format_large_files(file_analysis)
        assert "`a.py`" in result
        assert "`b.py`" in result
        assert "700 lines" in result
        assert "900 lines" in result

    def test_filename_is_code_formatted(self):
        """Filenames are wrapped in backticks for inline code formatting."""
        file_analysis = {
            "large_files": [{"filename": "path/to/file.py", "changes": 501, "additions": 301, "deletions": 200}]
        }
        result = analyze_pr._format_large_files(file_analysis)
        assert "`path/to/file.py`" in result

    def test_section_ends_with_newline(self):
        """The section string ends with a newline."""
        file_analysis = {"large_files": [{"filename": "f.py", "changes": 600, "additions": 500, "deletions": 100}]}
        result = analyze_pr._format_large_files(file_analysis)
        assert result.endswith("\n")


# ---------------------------------------------------------------------------
# _format_related_issues
# ---------------------------------------------------------------------------


class TestFormatRelatedIssues:
    """Tests for _format_related_issues helper."""

    def test_empty_list_returns_empty_string(self):
        """Empty related issues list returns an empty string."""
        result = analyze_pr._format_related_issues([])
        assert result == ""

    def test_single_issue_produces_bullet(self):
        """A single issue produces one bullet with '#number'."""
        issues = [{"number": "42", "url": "https://example.com/issues/42"}]
        result = analyze_pr._format_related_issues(issues)
        assert "**Related Issues:**" in result
        assert "- #42" in result

    def test_multiple_issues_each_appear(self):
        """Multiple issues each appear as a separate bullet."""
        issues = [
            {"number": "10", "url": "https://example.com/issues/10"},
            {"number": "20", "url": "https://example.com/issues/20"},
        ]
        result = analyze_pr._format_related_issues(issues)
        assert "- #10" in result
        assert "- #20" in result

    def test_header_is_bold_markdown(self):
        """The 'Related Issues:' header is bold."""
        issues = [{"number": "1", "url": "https://example.com/issues/1"}]
        result = analyze_pr._format_related_issues(issues)
        assert "**Related Issues:**" in result

    def test_number_format_in_bullet(self):
        """Each bullet is formatted as '- #<number>'."""
        issues = [{"number": "99", "url": "url"}]
        result = analyze_pr._format_related_issues(issues)
        assert "- #99\n" in result


# ---------------------------------------------------------------------------
# _get_recommendations
# ---------------------------------------------------------------------------


class TestGetRecommendations:
    """Tests for _get_recommendations helper."""

    def test_high_risk_returns_three_items(self):
        """High risk level returns exactly three recommendation strings."""
        recs = analyze_pr._get_recommendations("High")
        assert len(recs) == 3

    def test_high_risk_contains_split_recommendation(self):
        """High risk recommendations include 'Split into smaller changes'."""
        recs = analyze_pr._get_recommendations("High")
        assert any("Split" in r for r in recs)

    def test_high_risk_contains_testing_recommendation(self):
        """High risk recommendations include testing language."""
        recs = analyze_pr._get_recommendations("High")
        assert any("testing" in r.lower() for r in recs)

    def test_high_risk_contains_reviewer_recommendation(self):
        """High risk recommendations include reviewer language."""
        recs = analyze_pr._get_recommendations("High")
        assert any("reviewer" in r.lower() or "review" in r.lower() for r in recs)

    def test_medium_risk_returns_two_items(self):
        """Medium risk level returns exactly two recommendation strings."""
        recs = analyze_pr._get_recommendations("Medium")
        assert len(recs) == 2

    def test_medium_risk_manageable_complexity(self):
        """Medium risk recommendations include 'manageable' language."""
        recs = analyze_pr._get_recommendations("Medium")
        assert any("manageable" in r.lower() or "complexity" in r.lower() for r in recs)

    def test_low_risk_returns_two_items(self):
        """Low risk (default) level returns exactly two recommendation strings."""
        recs = analyze_pr._get_recommendations("Low")
        assert len(recs) == 2

    def test_low_risk_fast_merge_candidate(self):
        """Low risk recommendations include 'Fast merge candidate'."""
        recs = analyze_pr._get_recommendations("Low")
        assert any("merge candidate" in r.lower() or "fast" in r.lower() for r in recs)

    def test_unknown_risk_falls_back_to_low_defaults(self):
        """An unrecognised risk level falls back to the low-risk defaults."""
        recs = analyze_pr._get_recommendations("Unknown")
        # Should be same as "Low" fallback (2 items with low-complexity language)
        assert len(recs) == 2
        assert any("Low complexity" in r for r in recs)

    def test_returns_list_of_strings(self):
        """All return values are lists of strings."""
        for level in ("High", "Medium", "Low", "Other"):
            recs = analyze_pr._get_recommendations(level)
            assert isinstance(recs, list)
            assert all(isinstance(r, str) for r in recs)


# ---------------------------------------------------------------------------
# find_related_issues – bug fix: group_index None handling
# ---------------------------------------------------------------------------


class TestFindRelatedIssues:
    """Tests for find_related_issues, focusing on the PR bug-fix for group_index."""

    def test_empty_body_returns_empty_list(self):
        """None body returns an empty list."""
        result = analyze_pr.find_related_issues(None, "https://github.com/owner/repo")
        assert result == []

    def test_empty_string_body_returns_empty_list(self):
        """Empty string body returns an empty list."""
        result = analyze_pr.find_related_issues("", "https://github.com/owner/repo")
        assert result == []

    def test_bare_issue_reference(self):
        """A bare '#123' reference is detected."""
        body = "This fixes #123."
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        assert len(result) >= 1
        numbers = [r["number"] for r in result]
        assert "123" in numbers

    def test_fix_keyword_reference(self):
        """'fix #456' is detected."""
        body = "fix #456"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert "456" in numbers

    def test_closes_keyword_reference(self):
        """'closes #789' is detected."""
        body = "closes #789"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert "789" in numbers

    def test_resolves_keyword_reference(self):
        """'resolves #321' is detected."""
        body = "resolves #321"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert "321" in numbers

    def test_case_insensitive_keyword(self):
        """Keywords are matched case-insensitively."""
        body = "Closes #100 and RESOLVES #200"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert "100" in numbers
        assert "200" in numbers

    def test_deduplication_of_issue_references(self):
        """The same issue number mentioned multiple times appears only once."""
        body = "#50 and fix #50 and also closes #50"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert numbers.count("50") == 1

    def test_url_constructed_correctly(self):
        """Each result's URL is formed as repo_url/issues/number."""
        body = "#7"
        repo_url = "https://github.com/acme/myrepo"
        result = analyze_pr.find_related_issues(body, repo_url)
        assert result[0]["url"] == "https://github.com/acme/myrepo/issues/7"

    def test_result_contains_number_and_url_keys(self):
        """Each result dict has both 'number' and 'url' keys."""
        body = "#1"
        result = analyze_pr.find_related_issues(body, "https://github.com/o/r")
        assert "number" in result[0]
        assert "url" in result[0]

    def test_multiple_different_issues(self):
        """Multiple different issue numbers are all captured."""
        body = "Closes #10, fixes #20, see also #30"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert "10" in numbers
        assert "20" in numbers
        assert "30" in numbers

    def test_fix_with_plural_keyword(self):
        """'fixes #101' (plural) is also detected."""
        body = "fixes #101"
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        numbers = [r["number"] for r in result]
        assert "101" in numbers

    def test_body_with_no_issue_refs(self):
        """Body with no issue references returns empty list."""
        body = "Improved logging and fixed whitespace."
        result = analyze_pr.find_related_issues(body, "https://github.com/owner/repo")
        assert result == []


# ---------------------------------------------------------------------------
# write_output – GITHUB_STEP_SUMMARY path validation security fix
# ---------------------------------------------------------------------------


class TestWriteOutput:
    """Tests for write_output, focusing on the GITHUB_STEP_SUMMARY security fix."""

    def test_no_summary_env_writes_temp_file_and_stdout(self, capsys, tmp_path):
        """Without GITHUB_STEP_SUMMARY, report goes to a temp file and stdout."""
        report = "Test report content"
        with patch.dict(os.environ, {}, clear=True):
            analyze_pr.write_output(report)

        captured = capsys.readouterr()
        assert report in captured.out

    def test_summary_inside_temp_dir_is_written(self, capsys, tmp_path):
        """A GITHUB_STEP_SUMMARY path inside the system temp dir is accepted."""
        summary_file = tmp_path / "step_summary.md"
        summary_file.touch()

        # Confirm the path resolves inside tempdir
        temp_root = os.path.realpath(tempfile.gettempdir())
        summary_real = os.path.realpath(str(summary_file))
        # tmp_path is under the system temp dir in pytest
        assert os.path.commonpath([summary_real, temp_root]) == temp_root

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            analyze_pr.write_output("hello")

        assert "hello" in summary_file.read_text(encoding="utf-8")

    def test_summary_outside_temp_dir_is_skipped(self, capsys, tmp_path, monkeypatch):
        """A GITHUB_STEP_SUMMARY path outside the system temp dir is rejected with a warning."""
        # Point to a real file outside tmp_path / tempdir
        safe_file = tmp_path / "outside.md"
        safe_file.touch()

        # Make tempdir return something that does NOT cover tmp_path
        # by overriding with a different path
        unrelated_dir = tmp_path / "fake_temp"
        unrelated_dir.mkdir()
        monkeypatch.setattr(tempfile, "gettempdir", lambda: str(unrelated_dir))

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(safe_file)}):
            analyze_pr.write_output("content")

        captured = capsys.readouterr()
        assert "Warning" in captured.err
        # The outside file should NOT have been written to
        assert safe_file.read_text(encoding="utf-8") == ""

    def test_io_error_on_summary_write_prints_warning(self, capsys, tmp_path, monkeypatch):
        """An IOError while writing the summary is caught and printed as a warning."""
        summary_file = tmp_path / "step_summary.md"
        summary_file.touch()

        def _raise(*args, **kwargs):
            """
            Always raise an IOError indicating the disk is full.

            Raises:
                IOError: always raised with the message "disk full".
            """
            raise IOError("disk full")

        monkeypatch.setattr("builtins.open", _raise)

        with patch.dict(os.environ, {"GITHUB_STEP_SUMMARY": str(summary_file)}):
            analyze_pr.write_output("report")

        captured = capsys.readouterr()
        assert "Warning" in captured.err

    def test_report_written_to_stdout(self, capsys):
        """The report is always printed to stdout regardless of other outputs."""
        report = "unique-content-12345"
        with patch.dict(os.environ, {}, clear=True):
            analyze_pr.write_output(report)

        captured = capsys.readouterr()
        assert report in captured.out

    def test_temp_file_is_created_with_correct_prefix_and_suffix(self, tmp_path):
        """The secure temp file is created with prefix 'pr_analysis_' and suffix '.md'."""
        created_names = []
        original_ntf = tempfile.NamedTemporaryFile

        def spy_ntf(**kwargs):
            """
            Wraps a NamedTemporaryFile factory to record the `prefix` and `suffix` kwargs for each created file.

            Records a tuple (prefix, suffix) in the module-level `created_names` list and forwards all keyword arguments to the wrapped NamedTemporaryFile factory, returning its result.

            Parameters:
                **kwargs: Keyword arguments accepted by tempfile.NamedTemporaryFile (e.g., `prefix`, `suffix`).

            Returns:
                The temporary file object returned by the underlying NamedTemporaryFile factory.
            """
            created_names.append((kwargs.get("prefix"), kwargs.get("suffix")))
            return original_ntf(**kwargs)

        with patch.dict(os.environ, {}, clear=True):
            with patch("tempfile.NamedTemporaryFile", side_effect=spy_ntf):
                analyze_pr.write_output("data")

        assert any(prefix == "pr_analysis_" and suffix == ".md" for prefix, suffix in created_names)
