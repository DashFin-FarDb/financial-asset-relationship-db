# PR Management Agent

## Current operating mode

The PR Agent is now on-demand only. Automatic `check_suite` fan-out and dependency approval are disabled because repeated status comments and title/author-only dependency approvals did not provide reliable merge-readiness evidence.

Use `@copilot check ci` only when an explicit snapshot is wanted. Routine status reporting is consolidated under:

```text
@pr-copilot status update
```

PR Copilot updates one existing marker-bound comment and binds the report to the current head commit. Its report is advisory: it does not replace review-thread reconciliation, provider-failure classification, dependency-overlap checks, human approval, or explicit merge authorization.

## Historical overview

The PR Management Agent is an automated system designed to streamline the pull request workflow by automatically handling review comments, implementing fixes, and managing the PR lifecycle.

## Features

### 🤖 Automated Review Response
- Monitors PR comments and reviews in real-time
- Parses feedback and creates actionable items
- Acknowledges reviewer comments automatically
- Prioritizes issues by severity and impact

### 🔧 Intelligent Change Implementation
- Implements code fixes based on review feedback
- Maintains code quality standards
- Runs tests before committing changes
- Creates focused, logical commits

### 📊 Quality Assurance
- Enforces coding standards (Python: Black, Flake8; TypeScript: ESLint, Prettier)
- Maintains test coverage requirements (Python: 80%, TypeScript: 75%)
- Validates CI/CD pipeline success
- Prevents breaking changes without approval

### 🚀 Workflow Automation
- Auto-rebases branches when needed
- Manages merge conflicts
- Requests re-reviews after changes
- Provides status updates and progress reports

## Usage

### Basic Commands

Mention the agent in PR comments to trigger actions:

```markdown
@copilot fix this
```
Implements the specific fix suggested in the comment context.

```markdown
@copilot address review
```
Processes all outstanding review comments and implements fixes.

```markdown
@copilot update tests
```
Adds or updates test coverage for modified code.

```markdown
@copilot check ci
```
Investigates CI failures and attempts to resolve them.

### Advanced Usage

#### Bulk Operations
```markdown
@copilot address review --priority high
```
Only addresses high-priority review comments.

```markdown
@copilot fix this --with-tests
```
Implements fix and adds corresponding test coverage.

#### Status Queries
```markdown
@copilot status
```
Provides current status of PR and pending actions.

```markdown
@copilot summary
```
Generates summary of changes made by the agent.

## Configuration

### Agent Settings

The agent behavior is controlled by `.github/pr-agent-config.yml`:

```yaml
# Key settings
actions:
  auto_acknowledge: true    # Auto-respond to reviews
  auto_implement: true      # Auto-implement fixes
  auto_test: true          # Auto-run tests
  max_changes_per_pr: 10   # Safety limit

quality:
  python:
    min_coverage: 80       # Minimum test coverage
  typescript:
    min_coverage: 75
```

### Safety Limits

The agent includes several safety mechanisms:

- **File Restrictions**: Cannot modify sensitive files (secrets, configs)
- **Change Limits**: Maximum 10 changes per PR, 5 files per commit
- **Human Approval**: Required for security-related or breaking changes
- **Rollback**: Automatically reverts problematic changes

## Workflow Integration

### GitHub Actions

The agent integrates with GitHub Actions via `.github/workflows/pr-agent.yml`:

- **Trigger Events**: PR reviews, comments, status changes
- **Quality Checks**: Linting, testing, type checking
- **Status Updates**: Comments on PR with progress
- **Auto-merge**: Suggests merge when all checks pass

### CI/CD Pipeline

Works with existing CI/CD tools:

- **CircleCI**: Monitors build status and failures
- **Vercel/Netlify**: Tracks deployment status
- **CodeRabbit**: Integrates with code review tools

## Examples

### Example 1: Fixing Type Errors

**Reviewer Comment:**
> The `AssetGraph` class needs proper TypeScript interfaces for the props.

**Agent Response:**
1. ✅ Acknowledges comment
2. 🔧 Adds TypeScript interfaces
3. 🧪 Updates tests
4. 📝 Commits: `fix: add TypeScript interfaces for AssetGraph props`
5. 🔄 Requests re-review

### Example 2: Adding Test Coverage

**Reviewer Comment:**
> This function needs unit tests to cover edge cases.

**Agent Response:**
1. ✅ Acknowledges comment
2. 🧪 Analyzes function for edge cases
3. ✏️ Writes comprehensive tests
4. 📝 Commits: `test: add unit tests for edge cases in calculateMetrics`
5. 📊 Verifies coverage meets requirements

### Example 3: CI Failure Resolution

**CI Failure:**
> Python linting failed: line too long in asset_graph.py:42

**Agent Response:**
1. 🔍 Analyzes CI logs
2. 🔧 Fixes line length issue
3. ✅ Runs linter locally
4. 📝 Commits: `style: fix line length in asset_graph.py`
5. ⏳ Monitors CI for success

## Monitoring and Metrics

### Performance Tracking

The agent tracks key metrics:

- **Response Time**: Average time from review to fix
- **Success Rate**: Percentage of successful automated fixes
- **CI Pass Rate**: Build success after agent changes
- **Review Satisfaction**: Feedback from reviewers

### Weekly Reports

Automated reports include:

- PRs processed and resolved
- Common issues and patterns
- Agent performance improvements
- Recommendations for workflow optimization

## Troubleshooting

### Common Issues

#### Agent Not Responding
- Check if agent is enabled in config
- Verify GitHub Actions are running
- Ensure proper permissions are set

#### Changes Not Applied
- Review safety limits in configuration
- Check if files are in restricted list
- Verify CI checks are passing

#### Quality Checks Failing
- Review code standards in config
- Check test coverage requirements
- Verify linting rules are up to date

### Getting Help

1. **Check Logs**: Review GitHub Actions logs for errors
2. **Configuration**: Verify `.github/pr-agent-config.yml` settings
3. **Manual Override**: Use `@copilot override` for special cases
4. **Human Intervention**: Tag maintainers for complex issues

## Best Practices

### For Reviewers

- **Be Specific**: Clear, actionable feedback works best
- **Use Keywords**: Include priority indicators (critical, minor, etc.)
- **Context Matters**: Provide examples when possible
- **Trust but Verify**: Review agent changes before approving

### For Contributors

- **Monitor Agent**: Watch for agent responses to your PRs
- **Collaborate**: Work with agent suggestions
- **Override When Needed**: Use manual fixes for complex issues
- **Provide Feedback**: Help improve agent performance

## Security Considerations

### Permissions

The agent operates with limited permissions:

- ✅ Can modify source code files
- ✅ Can run tests and linting
- ✅ Can create commits and comments
- ❌ Cannot modify secrets or sensitive configs
- ❌ Cannot merge PRs without approval
- ❌ Cannot access external systems

### Data Privacy

- No sensitive data is logged or stored
- All operations are auditable via Git history
- Agent actions are transparent and reversible

---

*For technical details, see `.github/copilot-pr-agent.md`*
*For configuration options, see `.github/pr-agent-config.yml`*
