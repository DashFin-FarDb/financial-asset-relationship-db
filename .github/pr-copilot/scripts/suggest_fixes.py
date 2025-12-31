#!/usr/bin/env python3
"""
Parse review suggestions and generate fix proposals.

This script analyzes review comments to extract actionable suggestions
and generates structured fix proposals for future enhancement.
"""

import os
import sys
import re
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
        return {
            'review_handling': {
                'actionable_keywords': [
                    'please', 'should', 'could you', 'nit', 'typo',
                    'fix', 'refactor', 'change', 'update', 'add', 'remove'
                ]
            }
        }


def extract_code_suggestions(comment_body: str) -> List[Dict[str, str]]:
    """Extract code suggestions from comment body."""
    suggestions = []
    
    # Pattern 1: Code blocks with suggestion marker
    # ```suggestion
    # code here
    # ```
    suggestion_pattern = r'```suggestion\s*\n(.*?)\n```'
    matches = re.finditer(suggestion_pattern, comment_body, re.DOTALL)
    for match in matches:
        suggestions.append({
            'type': 'code_suggestion',
            'content': match.group(1).strip()
        })
    
    # Pattern 2: Inline code in quotes with suggestion words
    inline_pattern = r'(?:should be|change to|replace with|use)\s+`([^`]+)`'
    matches = re.finditer(inline_pattern, comment_body, re.IGNORECASE)
    for match in matches:
        suggestions.append({
            'type': 'inline_suggestion',
            'content': match.group(1).strip()
        })
    
    return suggestions


def categorize_comment(comment_body: str, actionable_keywords: List[str]) -> Tuple[str, int]:
    """
    Categorize comment by type and priority.
    
    Returns:
        Tuple of (category, priority)
        Categories: critical, bug, improvement, style, question
        Priority: 1 (high) to 3 (low)
    """
    body_lower = comment_body.lower()
    
    # Critical issues
    critical_keywords = ['security', 'vulnerability', 'exploit', 'critical', 'breaking']
    if any(kw in body_lower for kw in critical_keywords):
        return 'critical', 1
    
    # Bugs
    bug_keywords = ['bug', 'error', 'fails', 'broken', 'incorrect', 'wrong']
    if any(kw in body_lower for kw in bug_keywords):
        return 'bug', 1
    
    # Questions
    question_keywords = ['why', 'what', 'how', '?', 'clarify', 'explain']
    if any(kw in body_lower for kw in question_keywords):
        return 'question', 3
    
    # Style/formatting
    style_keywords = ['style', 'format', 'lint', 'naming', 'convention']
    if any(kw in body_lower for kw in style_keywords):
        return 'style', 3
    
    # Improvement/refactor
    improvement_keywords = ['refactor', 'improve', 'optimize', 'enhance', 'consider']
    if any(kw in body_lower for kw in improvement_keywords):
        return 'improvement', 2
    
    # Default to improvement with medium priority
    return 'improvement', 2


def is_actionable(comment_body: str, actionable_keywords: List[str]) -> bool:
    """Check if comment contains actionable feedback."""
    body_lower = comment_body.lower()
    return any(keyword in body_lower for keyword in actionable_keywords)


def extract_file_and_line(comment: Any) -> Tuple[Optional[str], Optional[int]]:
    """Extract file and line number from review comment."""
    if hasattr(comment, 'path') and hasattr(comment, 'original_line'):
        return comment.path, comment.original_line
    return None, None


def parse_review_comments(pr: Any, actionable_keywords: List[str]) -> List[Dict[str, Any]]:
    """Parse all review comments and extract actionable items."""
    actionable_items = []
    
    # Get review comments (file-level comments)
    review_comments = list(pr.get_review_comments())
    
    for comment in review_comments:
        body = comment.body
        
        # Check if actionable
        if not is_actionable(body, actionable_keywords):
            continue
        
        # Extract file and line
        file_path, line_num = extract_file_and_line(comment)
        
        # Categorize
        category, priority = categorize_comment(body, actionable_keywords)
        
        # Extract code suggestions
        code_suggestions = extract_code_suggestions(body)
        
        item = {
            'id': comment.id,
            'author': comment.user.login,
            'body': body,
            'category': category,
            'priority': priority,
            'file': file_path,
            'line': line_num,
            'code_suggestions': code_suggestions,
            'url': comment.html_url,
            'created_at': comment.created_at,  # Keep as datetime object for proper sorting
            'created_at_str': comment.created_at.isoformat()  # For display
        }
        
        actionable_items.append(item)
    
    # Get general review comments
    reviews = list(pr.get_reviews())
    
    for review in reviews:
        if review.state != 'CHANGES_REQUESTED' or not review.body:
            continue
        
        body = review.body
        
        # Check if actionable
        if not is_actionable(body, actionable_keywords):
            continue
        
        # Categorize
        category, priority = categorize_comment(body, actionable_keywords)
        
        # Extract code suggestions
        code_suggestions = extract_code_suggestions(body)
        
        item = {
            'id': review.id,
            'author': review.user.login,
            'body': body,
            'category': category,
            'priority': priority,
            'file': None,
            'line': None,
            'code_suggestions': code_suggestions,
            'url': review.html_url,
            'created_at': review.submitted_at,  # Keep as datetime object for proper sorting
            'created_at_str': review.submitted_at.isoformat()  # For display
        }
        
        actionable_items.append(item)
    
    # Sort by priority (highest first), then by creation date
    actionable_items.sort(key=lambda x: (x['priority'], x['created_at']))
    
    return actionable_items


def generate_fix_proposals(actionable_items: List[Dict[str, Any]]) -> str:
    """Generate structured fix proposals from actionable items."""
    
    if not actionable_items:
        return "✅ No actionable items found in review comments."
    
    # Group by category
    categorized = {}
    for item in actionable_items:
        category = item['category']
        if category not in categorized:
            categorized[category] = []
        categorized[category].append(item)
    
    report = "🔧 **Fix Proposals from Review Comments**\n\n"
    
    # Priority order
    priority_order = ['critical', 'bug', 'improvement', 'style', 'question']
    
    for category in priority_order:
        if category not in categorized:
            continue
        
        items = categorized[category]
        emoji = {
            'critical': '🚨',
            'bug': '🐛',
            'improvement': '💡',
            'style': '🎨',
            'question': '❓'
        }
        
        report += f"\n### {emoji.get(category, '📝')} {category.title()} ({len(items)} item{'s' if len(items) > 1 else ''})\n\n"
        
        for i, item in enumerate(items, 1):
            report += f"**{i}. Comment by @{item['author']}**\n"
            
            if item['file'] and item['line']:
                report += f"   - **Location:** `{item['file']}:{item['line']}`\n"
            
            report += f"   - **Priority:** {'🔴 High' if item['priority'] == 1 else '🟡 Medium' if item['priority'] == 2 else '🟢 Low'}\n"
            
            # Show excerpt of comment
            body_excerpt = item['body'][:200]
            if len(item['body']) > 200:
                body_excerpt += "..."
            report += f"   - **Feedback:** {body_excerpt}\n"
            
            # Show code suggestions if any
            if item['code_suggestions']:
                report += f"   - **Suggested Code:**\n"
                for suggestion in item['code_suggestions']:
                    if suggestion['type'] == 'code_suggestion':
                        report += f"     ```\n     {suggestion['content']}\n     ```\n"
                    else:
                        report += f"     `{suggestion['content']}`\n"
            
            report += f"   - [View Comment]({item['url']})\n\n"
    
    # Summary
    total = len(actionable_items)
    critical = len(categorized.get('critical', []))
    bugs = len(categorized.get('bug', []))
    
    report += "\n---\n\n**Summary:**\n"
    report += f"- **Total Actionable Items:** {total}\n"
    if critical > 0:
        report += f"- 🚨 **Critical Issues:** {critical}\n"
    if bugs > 0:
        report += f"- 🐛 **Bugs:** {bugs}\n"
    report += f"- 💡 **Improvements:** {len(categorized.get('improvement', []))}\n"
    report += f"- 🎨 **Style:** {len(categorized.get('style', []))}\n"
    report += f"- ❓ **Questions:** {len(categorized.get('question', []))}\n"
    
    if critical > 0 or bugs > 0:
        report += "\n⚠️ **Priority:** Address critical issues and bugs first.\n"
    
    report += "\n*Generated by PR Copilot Fix Suggestion Tool*\n"
    
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
    actionable_keywords = config.get('review_handling', {}).get('actionable_keywords', [
        'please', 'should', 'could you', 'nit', 'typo',
        'fix', 'refactor', 'change', 'update', 'add', 'remove'
    ])
    
    # Initialize GitHub client
    g = Github(github_token)
    repo_full_name = f"{repo_owner}/{repo_name}"
    
    try:
        # Fetch PR
        print(f"Parsing review comments for PR #{pr_number}...", file=sys.stderr)
        repo = g.get_repo(repo_full_name)
        pr = repo.get_pull(pr_number)
        
        # Parse review comments
        actionable_items = parse_review_comments(pr, actionable_keywords)
        
        # Generate fix proposals
        report = generate_fix_proposals(actionable_items)
        
        # Write to file
        output_file = "/tmp/pr_fix_proposals.md"
        with open(output_file, 'w') as f:
            f.write(report)
        
        print(f"Fix proposals generated successfully: {output_file}", file=sys.stderr)
        print(f"Found {len(actionable_items)} actionable items", file=sys.stderr)
        print(report)  # Also print to stdout
        
    except Exception as e:
        print(f"Error parsing review comments: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
