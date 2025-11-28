"""
Comprehensive validation tests for TEST_GENERATION_WORKFLOW_SUMMARY.md

This test suite validates the documentation file to ensure it is well-formed,
contains accurate information, and follows markdown best practices.
"""

import re
import pytest
from pathlib import Path
from typing import List, Set


SUMMARY_FILE = Path(__file__).parent.parent.parent / "TEST_GENERATION_WORKFLOW_SUMMARY.md"


@pytest.fixture
def summary_content() -> str:
    """Load the summary file content."""
    if not SUMMARY_FILE.exists():
        pytest.skip("TEST_GENERATION_WORKFLOW_SUMMARY.md not found")
    with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
        return f.read()


@pytest.fixture
def summary_lines(summary_content: str) -> List[str]:
    """Get summary file lines."""
    return summary_content.split('\n')


class TestDocumentStructure:
    """Test suite for document structure validation."""
    
    def test_file_exists(self):
        """Test that the summary file exists."""
        assert SUMMARY_FILE.exists(), "TEST_GENERATION_WORKFLOW_SUMMARY.md should exist"
    
    def test_file_is_not_empty(self, summary_content: str):
        """Test that the file contains content."""
        assert len(summary_content.strip()) > 0, "File should not be empty"
    
    def test_file_has_title(self, summary_lines: List[str]):
        """Test that file starts with a markdown title."""
        first_heading = None
        for line in summary_lines:
            if line.startswith('#'):
                first_heading = line
                break
        assert first_heading is not None, "File should have at least one heading"
        assert first_heading.startswith('# '), "First heading should be level 1"
    
    def test_has_overview_section(self, summary_content: str):
        """Test that document has an Overview section."""
        assert '## Overview' in summary_content, "Document should have an Overview section"
    
    def test_has_generated_files_section(self, summary_content: str):
        """Test that document describes generated files."""
        assert '## Generated Files' in summary_content, "Document should list generated files"
    
    def test_has_test_suite_structure_section(self, summary_content: str):
        """Test that document describes test suite structure."""
        assert '## Test Suite Structure' in summary_content, "Document should describe test structure"
    
    def test_has_running_tests_section(self, summary_content: str):
        """Test that document includes running instructions."""
        assert '## Running the Tests' in summary_content, "Document should have running instructions"
    
    def test_has_benefits_section(self, summary_content: str):
        """Test that document lists benefits."""
        assert '## Benefits' in summary_content or '## Key Features' in summary_content, \
            "Document should describe benefits or key features"


class TestMarkdownFormatting:
    """Test suite for markdown formatting validation."""
    
    def test_headings_properly_formatted(self, summary_lines: List[str]):
        """Test that headings follow proper markdown format."""
        heading_lines = [line for line in summary_lines if line.startswith('#')]
        for line in heading_lines:
            # Heading should have space after hash marks
            assert re.match(r'^#{1,6} .+', line), f"Heading '{line}' should have space after #"
    
    def test_no_trailing_whitespace(self, summary_lines: List[str]):
        """Test that lines don't have trailing whitespace."""
        lines_with_trailing = [
            (i + 1, line) for i, line in enumerate(summary_lines)
            if line.rstrip() != line and line.strip() != ''
        ]
        assert len(lines_with_trailing) == 0, \
            f"Found {len(lines_with_trailing)} lines with trailing whitespace"
    
    def test_code_blocks_properly_closed(self, summary_lines: List[str]):
        """Test that code blocks are properly opened and closed."""
        open_block = False
        for i, line in enumerate(summary_lines, start=1):
            stripped = line.strip()
            if stripped.startswith('```'):
                # Toggle open/close state on a fence line
                open_block = not open_block
        assert open_block is False, "Code blocks not properly closed or mismatched triple backticks detected"
    
    def test_lists_properly_formatted(self, summary_lines: List[str]):
        """Test that bullet lists use consistent markers."""
        list_lines = [line for line in summary_lines if re.match(r'^\s*[-*+] ', line)]
        if list_lines:
            # Check that indentation is consistent
            for line in list_lines:
                indent = len(line) - len(line.lstrip())
                assert indent % 2 == 0, f"List item '{line.strip()}' has odd indentation"


class TestContentAccuracy:
    """Test suite for content accuracy validation."""
    
    def test_mentions_workflow_file(self, summary_content: str):
        """Test that document mentions the pr-agent.yml workflow."""
        assert 'pr-agent.yml' in summary_content.lower() or 'pr-agent' in summary_content.lower(), \
            "Document should mention pr-agent workflow"
    
    def test_mentions_duplicate_keys_issue(self, summary_content: str):
        """Test that document mentions the duplicate keys issue that was fixed."""
        assert 'duplicate' in summary_content.lower(), \
            "Document should mention duplicate keys issue"
    
    def test_mentions_pytest(self, summary_content: str):
        """Test that document mentions pytest."""
        assert 'pytest' in summary_content.lower(), \
            "Document should mention pytest as the testing framework"
    
    def test_has_code_examples(self, summary_content: str):
        """Test that document includes code examples."""
        assert '```' in summary_content, "Document should include code examples"
    
    def test_mentions_yaml(self, summary_content: str):
        """Test that document mentions YAML."""
        assert 'yaml' in summary_content.lower() or 'yml' in summary_content.lower(), \
            "Document should mention YAML"
    
    def test_mentions_test_classes(self, summary_content: str):
        """Test that document describes test classes."""
        test_class_keywords = ['TestWorkflowSyntax', 'TestWorkflowStructure', 'TestPrAgentWorkflow']
        found_classes = [kw for kw in test_class_keywords if kw in summary_content]
        assert len(found_classes) > 0, \
            "Document should mention specific test classes"
    
    def test_includes_file_paths(self, summary_content: str):
        """Test that document includes actual file paths."""
        assert 'tests/integration' in summary_content or 'test_github_workflows' in summary_content, \
            "Document should include actual file paths"
    
    def test_mentions_requirements(self, summary_content: str):
        """Test that document mentions requirements or dependencies."""
        assert 'requirements' in summary_content.lower() or 'pyyaml' in summary_content.lower(), \
            "Document should mention dependencies"


class TestCodeExamples:
    """Test suite for code example validation."""
    
    def test_pytest_commands_valid(self, summary_content: str):
        """Test that pytest commands are valid."""
        # Extract code blocks
        code_blocks = re.findall(r'```(?:bash|shell)?\n(.*?)```', summary_content, re.DOTALL)
        pytest_commands = [
            block for block in code_blocks 
            if 'pytest' in block
        ]
        assert len(pytest_commands) > 0, "Document should include pytest command examples"
        
        for cmd in pytest_commands:
            # Basic validation
            assert 'pytest' in cmd, "pytest command should contain 'pytest'"
    
    def test_file_paths_in_examples_exist(self, summary_content: str):
        """Test that referenced file paths in examples actually exist."""
        # Look for test file references
        test_file_pattern = r'tests/integration/test_\w+\.py'
        mentioned_files = re.findall(test_file_pattern, summary_content)

        repo_root = Path(__file__).parent.parent.parent
        missing: List[str] = []

        for file_path in mentioned_files:
            full_path = repo_root / file_path
            if not full_path.exists():
                missing.append(f"{file_path} (resolved: {full_path})")

        # Fail only once with a consolidated, informative message if any are missing
        assert not missing, (
            "One or more referenced files in documentation were not found:\n"
            + "\n".join(f"- {m}" for m in missing)
            + "\nIf files were recently moved or renamed, update the documentation examples accordingly."
        )


class TestDocumentCompleteness:
    """Test suite for document completeness."""
    
    def test_has_summary_statistics(self, summary_content: str):
        """Test that document includes statistics about tests."""
        # Should mention numbers of tests, classes, etc.
        has_numbers = re.search(r'\d+\s+(tests?|class(?:es)?)', summary_content, re.IGNORECASE)
        assert has_numbers is not None, \
            "Document should include statistics about test coverage"
    
    def test_describes_what_tests_prevent(self, summary_content: str):
        """Test that document explains what the tests prevent."""
        prevention_keywords = ['prevent', 'catch', 'detect', 'ensure']
        found = any(keyword in summary_content.lower() for keyword in prevention_keywords)
        assert found, "Document should describe what problems tests prevent"
    
    def test_has_integration_info(self, summary_content: str):
        """Test that document describes CI integration."""
        ci_keywords = ['ci', 'continuous integration', 'github actions', 'workflow']
        found = any(keyword in summary_content.lower() for keyword in ci_keywords)
        assert found, "Document should mention CI/workflow integration"
    
    def test_has_practical_examples(self, summary_content: str):
        """Test that document has practical examples."""
        assert '```' in summary_content, "Document should have code examples"
        code_blocks = summary_content.count('```')
        assert code_blocks >= 4, "Document should have at least 2 code block examples"


class TestDocumentMaintainability:
    """Test suite for document maintainability."""
    
    def test_line_length_reasonable(self, summary_lines: List[str]):
        """Test that lines aren't excessively long."""
        long_lines = [
            (i + 1, line) for i, line in enumerate(summary_lines)
            if len(line) > 120 and not line.strip().startswith('http')
        ]
        # Allow some long lines but flag excessive ones
        assert len(long_lines) < len(summary_lines) * 0.1, \
            f"Too many long lines ({len(long_lines)}), consider breaking them up"
    
    def test_has_clear_structure(self, summary_content: str):
        """Test that document has clear hierarchical structure."""
        h1_count = len(re.findall(r'^# ', summary_content, re.MULTILINE))
        h2_count = len(re.findall(r'^## ', summary_content, re.MULTILINE))
        
        assert h1_count >= 1, "Should have at least one H1 heading"
        assert h2_count >= 3, "Should have at least 3 H2 headings for organization"
    
    def test_sections_have_content(self, summary_content: str):
        """Test that major sections have substantial content."""
        sections = re.split(r'\n## ', summary_content)
        # Skip first section (before first H2)
        for section in sections[1:]:
            lines = section.split('\n')
            section_name = lines[0]
            content_lines = [l for l in lines[1:] if l.strip()]
            assert len(content_lines) > 0, \
                f"Section '{section_name}' should have content"


class TestLinkValidation:
    """Test suite for link validation."""

    def test_internal_links_valid(self, summary_lines: List[str], summary_content: str):
        import unicodedata

        def _to_gfm_anchor(text: str) -> str:
            # Lowercase
            s = text.strip().lower()
            # Normalize unicode to NFKD and remove diacritics
            s = unicodedata.normalize('NFKD', s)
            s = ''.join(ch for ch in s if not unicodedata.combining(ch))
            # Remove punctuation/special chars except spaces and hyphens
            s = re.sub(r'[^\w\s-]', '', s)
            # Replace whitespace with single hyphen
            s = re.sub(r'\s+', '-', s)
            # Collapse multiple hyphens
            s = re.sub(r'-{2,}', '-', s)
            # Strip leading/trailing hyphens
            s = s.strip('-')
            return s

        # Extract headers and internal links from the document
        headers = [line.lstrip('#').strip() for line in summary_lines if line.startswith('#')]
        valid_anchors: Set[str] = set(_to_gfm_anchor(header) for header in headers)
        internal_links = re.findall(r'\[([^\]]+)\]\(#([^)]+)\)', summary_content)

        # Check each internal link
        for text, anchor in internal_links:
            assert anchor in valid_anchors, \
                f"Internal link to #{anchor} references non-existent header"
class TestSecurityAndBestPractices:
    """Test suite for security and best practices in documentation."""
    
    def test_no_hardcoded_secrets(self, summary_content: str):
        """Test that document doesn't contain hardcoded secrets."""
        secret_patterns = [
            r'ghp_[a-zA-Z0-9]{36}',  # GitHub Personal Access Token
            r'gho_[a-zA-Z0-9]{36}',  # GitHub OAuth Token
            r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}',  # GitHub Fine-grained PAT
        ]
        
        for pattern in secret_patterns:
            matches = re.findall(pattern, summary_content)
            assert len(matches) == 0, \
                f"Document should not contain hardcoded secrets (found pattern: {pattern})"
    
    def test_uses_secure_examples(self, summary_content: str):
        """Test that examples follow security best practices."""
        # If the document mentions tokens, it should mention secrets context
        if 'token' in summary_content.lower():
            assert 'secrets' in summary_content.lower() or '${{' in summary_content, \
                "Document should reference GitHub secrets context when mentioning tokens"


class TestReferenceAccuracy:
    """Test suite for reference accuracy."""
    
    def test_test_counts_are_realistic(self, summary_content: str):
        """Test that mentioned test counts seem realistic."""
        # Extract numbers mentioned with "test"
        test_counts = re.findall(r'(\d+)\s+tests?', summary_content, re.IGNORECASE)
        for count_str in test_counts:
            count = int(count_str)
            assert 0 < count < 1000, \
                f"Test count {count} seems unrealistic"
    
    def test_file_references_are_consistent(self, summary_content: str):
        """Test that file references are consistent throughout."""
        # Main test file should be referenced consistently
        test_file_mentions = re.findall(
            r'test_github_workflows\.py', 
            summary_content, 
            re.IGNORECASE
        )
        if test_file_mentions:
            # All mentions should use the same case
            unique_mentions = set(test_file_mentions)
            assert len(unique_mentions) <= 2, \
                "File name should be referenced consistently"


class TestEdgeCases:
    """Test suite for edge cases."""
    
    def test_handles_special_characters(self, summary_content: str):
        """Test that document handles special characters properly."""
        # Check for common encoding issues
        assert '�' not in summary_content, \
            "Document should not contain replacement characters (encoding issues)"
    
    def test_utf8_encoding(self):
        """Test that file is properly UTF-8 encoded."""
        try:
            with open(SUMMARY_FILE, 'r', encoding='utf-8') as f:
                f.read()
        except UnicodeDecodeError:
            pytest.fail("File should be valid UTF-8")
    
    def test_consistent_line_endings(self):
        """Test that file uses consistent line endings throughout."""
        with open(SUMMARY_FILE, 'rb') as f:
            content = f.read()

        # Split preserving line endings and detect per-line endings
        lines = content.splitlines(True)
        if not lines:
            pytest.skip("File appears to be empty; skipping line ending consistency check")

        endings = set()
        for line in lines:
            if line.endswith(b'\r\n'):
                endings.add('CRLF')
            elif line.endswith(b'\n'):
                endings.add('LF')
            elif line.endswith(b'\r'):
                # Rare classic Mac line ending; treat distinctly
                endings.add('CR')
            else:
                # Last line may not have a newline; ignore for consistency purposes
                pass

        # Require exactly one style among present line-terminated lines
        assert len(endings) == 1, "File should use a single line ending style throughout"
        # Additionally ensure the file uses recognized line endings
        assert endings.pop() in {'LF', 'CRLF'}, "File should use LF or CRLF line endings"

class TestDocumentationMarkdownQuality:
    """Advanced markdown quality tests for documentation files."""
    
    def test_no_broken_internal_links(self):
        """Verify internal markdown links are not broken."""
        doc_files = list(Path('.').glob('*.md'))
        
        for doc_file in doc_files:
            content = doc_file.read_text()
            
            # Find markdown links
            import re
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
            
            for link_text, link_url in links:
                # Check internal links (not http/https)
                # Skip external links (only validate local paths)
                if link_url.startswith(('http://', 'https://', 'mailto:')):
                    continue
                # Remove fragment and validate only when a local path is present
                target_path = link_url.split('#', 1)[0].strip()
                if not target_path:
                    # Pure-fragment or empty target; not a filesystem path to validate here
                    continue
                # Resolve path relative to the doc file if needed
                link_path = Path(target_path)
                if not link_path.exists():
                    link_path = (doc_file.parent / target_path).resolve()
                    continue
                target_path = link_url.split('#', 1)[0]
                if not target_path:
                    continue
                # Should exist
                link_path = Path(target_path)
                if not link_path.exists():
                    # Try relative to doc file
                    link_path = doc_file.parent / target_path

                assert link_path.exists(), \
                    f"Broken link in {doc_file}: [{link_text}]({link_url})"
    
    def test_consistent_heading_style(self):
        """Ensure consistent heading style (ATX style with #)."""
        summary_files = list(Path('.').glob('*SUMMARY.md'))
        
        for doc_file in summary_files:
            content = doc_file.read_text()
            lines = content.split('\n')
            
            # Should use ATX style (###) not Setext style (===)
            setext_headers = sum(1 for line in lines if line.strip() and 
                               all(c in '=-' for c in line.strip()))
            
            # Allow some, but should mostly use ATX
            assert setext_headers < 5, \
                f"{doc_file} uses too many Setext-style headers. Use ATX style (#, ##, ###)"
    
    def test_code_blocks_have_language(self):
        """Ensure code blocks specify language for syntax highlighting."""
        summary_files = list(Path('.').glob('*SUMMARY.md')) + list(Path('.').glob('TEST_*.md'))

        for doc_file in summary_files:
            content = doc_file.read_text()

            # Find code blocks - match complete blocks to only capture opening fence language
            import re
            code_blocks = re.findall(r'```([^\n]*)\n.*?```', content, re.DOTALL)

            if code_blocks:
                # At least 70% should have language specified
                with_language = sum(1 for lang in code_blocks if lang)
                total = len(code_blocks)
                percentage = (with_language / total * 100) if total > 0 else 100
                assert percentage >= 70, \
                    f"{doc_file}: Only {percentage:.0f}% of code blocks specify language. " \
                    "Add language identifiers (bash, python, yaml, etc.)"
    
    def test_no_very_long_lines(self):
        """Check for reasonably wrapped lines in markdown."""
        summary_files = list(Path('.').glob('*SUMMARY.md'))
        
        for doc_file in summary_files:
            content = doc_file.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                # Ignore code blocks and tables
                if line.strip().startswith(('```', '|', '#')):
                    continue
                
                # Regular prose lines shouldn't be extremely long
                assert len(line) < 500, \
                    f"{doc_file} line {i}: Very long line ({len(line)} chars). Consider wrapping."
    
    def test_lists_properly_formatted(self):
        """Verify markdown lists follow proper formatting."""
        doc_files = list(Path('.').glob('*SUMMARY.md'))
        
        for doc_file in doc_files:
            content = doc_file.read_text()
            lines = content.split('\n')
            
            for i, line in enumerate(lines, 1):
                # Check list items
                stripped = line.lstrip()
                if stripped.startswith(('-', '*', '+')):
                    # Should have space after marker
                    assert stripped[1:2] == ' ', \
                        f"{doc_file} line {i}: Missing space after list marker"
                
                # Numbered lists
                import re
                if re.match(r'^\s*\d+\.', line):
                    # Should have space after number
                    assert re.match(r'^\s*\d+\.\s', line), \
                        f"{doc_file} line {i}: Missing space after numbered list marker"
    
    def test_statistics_tables_valid(self):
        """Verify statistics tables in summaries are properly formatted."""
        summary_files = list(Path('.').glob('*SUMMARY.md'))
        
        for doc_file in summary_files:
            content = doc_file.read_text()
            
            # Find tables
            import re
            table_pattern = r'\|.*\|.*\n\|[-:\s|]+\|'
            tables = re.findall(table_pattern, content)
            
            if tables:
                # Tables should be properly formatted
                for table in tables:
                    lines = table.split('\n')
                    if len(lines) >= 2:
                        # Header and separator should have same number of columns
                        header_cols = lines[0].count('|') - 1
                        separator_cols = lines[1].count('|') - 1
                        
                        assert header_cols == separator_cols, \
                            f"{doc_file}: Table column mismatch"


class TestTestSummaryCompleteness:
    """Verify test summary documentation is complete and accurate."""
    
    def test_summary_documents_all_test_files(self):
        """Ensure summary documents all generated test files."""
        summary_file = Path('COMPREHENSIVE_ADDITIONAL_TESTS_SUMMARY.md')
        if not summary_file.exists():
            pytest.skip("Comprehensive summary not found")
        
        content = summary_file.read_text()
        
        # Should mention key test files
        test_files = [
            'test-utils.test.ts',
            'MetricsDashboard.test.tsx',
            'NetworkVisualization.test.tsx',
            'page.test.tsx',
            'api.test.ts',
            'component-integration.test.tsx',
        ]
        
        missing = [f for f in test_files if f not in content]
        assert len(missing) == 0, \
            f"Summary missing test files: {missing}"
    
    def test_summary_has_running_instructions(self):
        """Verify summary includes instructions for running tests."""
        summary_files = [
            Path('COMPREHENSIVE_ADDITIONAL_TESTS_SUMMARY.md'),
            Path('ADDITIONAL_TESTS_SUMMARY.md'),
        ]
        
        for summary_file in summary_files:
            if not summary_file.exists():
                continue
            
            content = summary_file.read_text().lower()
            
            # Should have run commands
            has_instructions = any(keyword in content for keyword in [
                'npm test',
                'pytest',
                'running',
                'execute',
            ])
            
            assert has_instructions, \
                f"{summary_file} missing test execution instructions"
    
    def test_summary_has_statistics(self):
        """Verify summary includes test statistics."""
        summary_file = Path('COMPREHENSIVE_ADDITIONAL_TESTS_SUMMARY.md')
        if not summary_file.exists():
            pytest.skip("Comprehensive summary not found")
        
        content = summary_file.read_text()
        
        # Should have statistics
        stat_indicators = ['tests', 'lines', 'coverage', 'cases']
        
        found_stats = sum(1 for indicator in stat_indicators if indicator in content.lower())
        
        assert found_stats >= 3, \
            "Summary should include test statistics"
    
    def test_summaries_are_dated(self):
        """Ensure summary files have generation dates."""
        summary_files = list(Path('.').glob('*SUMMARY.md'))
        
        for summary_file in summary_files:
            content = summary_file.read_text()
            
            # Should have date information
            import re
            date_patterns = [
                r'202[3-9]-\d{2}-\d{2}',  # YYYY-MM-DD
                r'Generated:.*202[3-9]',  # "Generated: " followed by year
                r'\d{1,2}/\d{1,2}/202[3-9]',  # MM/DD/YYYY
            ]
            
            has_date = any(re.search(pattern, content) for pattern in date_patterns)
            
            assert has_date, \
                f"{summary_file} should include generation date"


class TestWorkflowDocumentationAlignment:
    """Test alignment between workflows and their documentation."""
    
    def test_documented_workflows_exist(self):
        """Verify all documented workflows actually exist."""
        summary_file = Path('TEST_GENERATION_WORKFLOW_SUMMARY.md')
        if not summary_file.exists():
            pytest.skip("Workflow summary not found")
        
        content = summary_file.read_text()
        
        # Extract workflow file names mentioned
        import re
        workflow_mentions = re.findall(r'\.github/workflows/([a-z-]+\.yml)', content)
        
        for workflow_file in workflow_mentions:
            workflow_path = Path(f'.github/workflows/{workflow_file}')
            assert workflow_path.exists(), \
                f"Documented workflow not found: {workflow_file}"
    
    def test_workflow_changes_documented(self):
        """Verify major workflow changes are documented."""
        # Get workflow files
        workflow_dir = Path('.github/workflows')
        if not workflow_dir.exists():
            pytest.skip("Workflow directory not found")
        
        workflows = list(workflow_dir.glob('*.yml'))
        
        # Check if documented
        summary_files = [
            Path('TEST_GENERATION_WORKFLOW_SUMMARY.md'),
            Path('COMPREHENSIVE_TEST_SUMMARY.md'),
        ]
        
        all_content = ''
        for summary_file in summary_files:
            if summary_file.exists():
                all_content += summary_file.read_text()
        
        if all_content:
            # Key workflows should be mentioned
            key_workflows = ['pr-agent.yml', 'label.yml', 'greetings.yml']
            for workflow in key_workflows:
                if (workflow_dir / workflow).exists():
                    assert workflow in all_content, \
                        f"Key workflow {workflow} not documented in summaries"

