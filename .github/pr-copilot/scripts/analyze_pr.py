#!/usr/bin/env python3
"""
Analyze PR complexity, scope, and health.

This script evaluates a PR to determine:
- File count and types changed
- Line change magnitude
- Potential scope issues
- Related issues/PRs
- Overall complexity score
"""

import os
import sys
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

try:
    from github import Github
    import yaml
except ImportError:
    print("Error: Required packages not installed. Run: pip install PyGithub pyyaml", file=sys.stderr)
    sys.exit(1)


def load_config() -> Dict[str, Any]:
    """Load configuration from pr-copilot-config.yml."""
    config_path = ".github/pr-copilot-config.yml"
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Warning: Config file not found at {config_path}, using defaults", file=sys.stderr)
        return {}


def categorize_file(filename: str) -> str:
    """Categorize file by type."""
    # Check for test files by name pattern first
    if 'test' in filename.lower() or 'spec' in filename.lower():
        return 'test'
    
    # Check for workflow files by path
    if '.github/workflows' in filename:
        return 'workflow'
    
    # Get file extension
    if '.' not in filename:
        return 'other'
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    # Categorize by extension
    categories = {
        'python': ['py'],
        'javascript': ['js', 'jsx', 'ts', 'tsx'],
        'markup': ['html', 'xml', 'jsx', 'tsx'],
        'style': ['css', 'scss', 'sass', 'less'],
        'config': ['json', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf'],
        'documentation': ['md', 'rst', 'txt'],
        'database': ['sql', 'db', 'sqlite'],
        'shell': ['sh', 'bash', 'zsh', 'fish'],
    }
    
    for category, extensions in categories.items():
        if ext in extensions:
            return category

    
    return 'other'


def analyze_file_changes(files: List[Any]) -> Dict[str, Any]:
    """Analyze the files changed in the PR."""
    file_categories = defaultdict(int)
    total_additions = 0
    total_deletions = 0
    total_changes = 0
    large_files = []
    
    for file in files:
        # Categorize file
        category = categorize_file(file.filename)
        file_categories[category] += 1
        
        # Track changes
        additions = file.additions
        deletions = file.deletions
        changes = additions + deletions
        
        total_additions += additions
        total_deletions += deletions
        total_changes += changes
        
        # Flag large files (>500 lines changed)
        if changes > 500:
            large_files.append({
                'filename': file.filename,
                'changes': changes,
                'additions': additions,
                'deletions': deletions
            })
    
    return {
        'file_count': len(files),
        'file_categories': dict(file_categories),
        'total_additions': total_additions,
        'total_deletions': total_deletions,
        'total_changes': total_changes,
        'large_files': large_files,
        'has_large_files': len(large_files) > 0
    }


def calculate_complexity_score(file_analysis: Dict[str, Any], commit_count: int) -> Tuple[int, str]:
    """
    Calculate complexity score (0-100) and risk level.
    
    Returns:
        Tuple of (score, risk_level)
    """
    score = 0
    
    # File count factor (0-30 points)
    file_count = file_analysis['file_count']
    if file_count > 50:
        score += 30
    elif file_count > 20:
        score += 20
    elif file_count > 10:
        score += 10
    else:
        score += 5
    
    # Line changes factor (0-30 points)
    total_changes = file_analysis['total_changes']
    if total_changes > 2000:
        score += 30
    elif total_changes > 1000:
        score += 20
    elif total_changes > 500:
        score += 15
    else:
        score += 5
    
    # Large files factor (0-20 points)
    if file_analysis['has_large_files']:
        score += min(len(file_analysis['large_files']) * 5, 20)
    
    # Commit count factor (0-20 points)
    if commit_count > 50:
        score += 20
    elif commit_count > 20:
        score += 15
    elif commit_count > 10:
        score += 10
    else:
        score += 5
    
    # Determine risk level
    if score >= 70:
        risk_level = "High"
    elif score >= 40:
        risk_level = "Medium"
    else:
        risk_level = "Low"
    
    return score, risk_level


def check_scope_issues(pr: Any, file_analysis: Dict[str, Any]) -> List[str]:
    """Check for potential scope issues."""
    issues = []
    
    # Check title length
    if len(pr.title) > 72:
        issues.append(f"Long PR title ({len(pr.title)} chars, recommended <72)")
    
    # Check for multiple change indicators in title
    title_lower = pr.title.lower()
    multi_keywords = [' and ', ' & ', ' or ', ', ']
    if any(keyword in title_lower for keyword in multi_keywords):
        issues.append("PR title suggests multiple changes (contains 'and', 'or', '&', or commas)")
    
    # Check file count
    if file_analysis['file_count'] > 30:
        issues.append(f"Large number of files changed ({file_analysis['file_count']} files)")
    
    # Check for mixed concerns (code + docs + config + tests all together)
    categories = file_analysis['file_categories']
    category_count = len(categories)
    if category_count > 5:
        issues.append(f"Multiple file types changed ({category_count} different types)")
    
    # Check for large diffs
    if file_analysis['total_changes'] > 1500:
        issues.append(f"Large changeset ({file_analysis['total_changes']} lines changed)")
    
    return issues


def find_related_issues(pr: Any) -> List[Dict[str, str]]:
    """Find related issues mentioned in PR body."""
    related = []
    
    if not pr.body:
        return related
    
    # Simple pattern matching for issue references
    # Matches: #123, fixes #123, closes #123, resolves #123
    import re
    patterns = [
        r'#(\d+)',
        r'(?:fix|fixes|fixed|close|closes|closed|resolve|resolves|resolved)\s+#(\d+)',
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, pr.body, re.IGNORECASE)
        for match in matches:
            issue_num = match.group(1)
            related.append({
                'type': 'issue',
                'number': issue_num,
                'url': f"{pr.base.repo.html_url}/issues/{issue_num}"
            })
    
    # Remove duplicates
    seen = set()
    unique_related = []
    for item in related:
        key = f"{item['type']}:{item['number']}"
        if key not in seen:
            seen.add(key)
            unique_related.append(item)
    
    return unique_related


def generate_analysis_report(pr: Any, file_analysis: Dict[str, Any], 
                            complexity_score: int, risk_level: str,
                            scope_issues: List[str], related_issues: List[Dict[str, str]],
                            commit_count: int) -> str:
    """Generate comprehensive analysis report."""
    
    # Format file categories
    categories_str = '\n'.join([f"  - {cat.title()}: {count}" 
                                for cat, count in file_analysis['file_categories'].items()])
    
    # Format large files
    large_files_str = ""
    if file_analysis['large_files']:
        large_files_str = "\n**Large Files (>500 lines changed):**\n"
        for file in file_analysis['large_files']:
            large_files_str += f"  - `{file['filename']}`: {file['changes']} lines (+{file['additions']}/-{file['deletions']})\n"
    
    # Format scope issues
    scope_issues_str = ""
    if scope_issues:
        scope_issues_str = "\n**⚠️ Potential Scope Issues:**\n"
        for issue in scope_issues:
            scope_issues_str += f"  - {issue}\n"
    
    # Format related issues
    related_str = ""
    if related_issues:
        related_str = "\n**Related Issues:**\n"
        for item in related_issues:
            related_str += f"  - #{item['number']}\n"
    
    # Complexity indicator
    complexity_emoji = {
        "Low": "🟢",
        "Medium": "🟡",
        "High": "🔴"
    }
    
    report = f"""🔍 **PR Analysis Report**

**PR Overview:**
- **Title:** {pr.title}
- **Number:** #{pr.number}
- **Author:** @{pr.user.login}
- **Base:** `{pr.base.ref}` ← **Head:** `{pr.head.ref}`

**Complexity Assessment:**
- **Complexity Score:** {complexity_score}/100
- **Risk Level:** {complexity_emoji.get(risk_level, "⚪")} **{risk_level}**

**File Changes:**
- **Total Files:** {file_analysis['file_count']}
- **Lines Changed:** {file_analysis['total_changes']} (+{file_analysis['total_additions']}/-{file_analysis['total_deletions']})
- **Commits:** {commit_count}

**File Types:**
{categories_str}
{large_files_str}
{scope_issues_str}
{related_str}

**Recommendations:**
"""
    
    # Add recommendations based on analysis
    if risk_level == "High":
        report += "  - ⚠️ Consider splitting this PR into smaller, focused changes\n"
        report += "  - 📋 Ensure comprehensive testing due to high complexity\n"
        report += "  - 👥 Request review from multiple team members\n"
    elif risk_level == "Medium":
        report += "  - ✅ Complexity is manageable\n"
        report += "  - 📝 Ensure adequate test coverage\n"
        report += "  - 👀 Standard review process recommended\n"
    else:
        report += "  - ✅ Low complexity, straightforward to review\n"
        report += "  - 🚀 Should merge quickly after review\n"
    
    if file_analysis['has_large_files']:
        report += f"  - 📊 {len(file_analysis['large_files'])} large file(s) need careful review\n"
    
    if not related_issues:
        report += "  - 💡 Consider linking to related issue(s) in PR description\n"
    
    report += "\n---\n*Generated by PR Copilot Analysis Tool*"
    
    return report


def main():
    """Main execution function."""
    # Get environment variables
    github_token = os.environ.get('GITHUB_TOKEN')
    pr_number = os.environ.get('PR_NUMBER')
    repo_owner = os.environ.get('REPO_OWNER')
    repo_name = os.environ.get('REPO_NAME')
    
    if not all([github_token, pr_number, repo_owner, repo_name]):
        print("Error: Missing required environment variables", file=sys.stderr)
        print("Required: GITHUB_TOKEN, PR_NUMBER, REPO_OWNER, REPO_NAME", file=sys.stderr)
        sys.exit(1)
    
    try:
        pr_number = int(pr_number)
    except ValueError:
        print(f"Error: PR_NUMBER must be an integer, got: {pr_number}", file=sys.stderr)
        sys.exit(1)
    
    # Load configuration
    config = load_config()
    
    # Initialize GitHub client
    g = Github(github_token)
    repo_full_name = f"{repo_owner}/{repo_name}"
    
    try:
        # Fetch PR
        print(f"Analyzing PR #{pr_number}...", file=sys.stderr)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # Get files and commits
        files = list(pr.get_files())
        commits = list(pr.get_commits())
        commit_count = len(commits)
        
        # Analyze files
        file_analysis = analyze_file_changes(files)
        
        # Calculate complexity
        complexity_score, risk_level = calculate_complexity_score(file_analysis, commit_count)
        
        # Check scope issues
        scope_issues = check_scope_issues(pr, file_analysis)
        
        # Find related issues
        related_issues = find_related_issues(pr)
        
        # Generate report
        report = generate_analysis_report(
            pr, file_analysis, complexity_score, risk_level,
            scope_issues, related_issues, commit_count
        )
        
        # Write to file
        output_file = "/tmp/pr_analysis_report.md"
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"Analysis report generated successfully: {output_file}", file=sys.stderr)
        print(report)  # Also print to stdout
        
        # Return exit code based on risk level
        if risk_level == "High":
            sys.exit(2)  # Warning exit code
        else:
            sys.exit(0)
        
    except Exception as e:
        print(f"Error analyzing PR: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
