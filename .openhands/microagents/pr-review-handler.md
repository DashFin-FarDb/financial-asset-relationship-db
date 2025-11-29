---
name: PR Review Handler
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers: ["review PR", "review comment", "review comments", "review all unresolved comments", "review commit", "review all commits", "fix", "make changes", "recommend change", "recommend changes", "recommend fix", "recommend fixes", "review merge conflict", "fix merge conflict", "request review from @mohavro", "request review by me", "request review from me", "request review MM", "request review mm"]
---

# PR Review Handler Microagent

This microagent is designed to handle pull request reviews and implement reviewer feedback for the financial-asset-relationship-db repository.

## Activation

### Manual Activation
To manually activate this microagent, use the reference: **@openhands-agent-prrh**

### Automatic Triggers
This microagent automatically activates when any of these keywords/phrases are mentioned:
- `review PR`
- `review comment` / `review comments`
- `review all unresolved comments`
- `review commit` / `review all commits`
- `fix`
- `make changes`
- `recommend change` / `recommend changes`
- `recommend fix` / `recommend fixes`
- `review merge conflict` / `fix merge conflict`
- `request review from @mohavro`
- `request review by me` / `request review from me`
- `request review MM` / `request review mm`

## Purpose

Review open pull requests, analyze review comments, and fix any uncommitted changes requested by reviewers. After implementing fixes, commit the changes and request review from @mohavro.

## Capabilities

### Pull Request Review Analysis
- Fetch and analyze open pull requests in the repository
- Parse review comments and feedback from reviewers
- Identify specific issues, suggestions, and requested changes
- Prioritize critical issues and security concerns

### Code Review Implementation
- Implement requested changes from reviewer feedback
- Fix code quality issues, bugs, and security vulnerabilities
- Update documentation when requested
- Ensure code follows project standards and conventions
- Handle merge conflicts if they arise

### Change Management
- Stage and commit all implemented changes with descriptive commit messages
- Follow conventional commit message format when applicable
- Ensure all changes are properly tested before committing
- Handle multiple commits if changes are logically separate

### Review Request Process
- After implementing all requested changes, request review from @mohavro
- Provide clear summary of changes made in response to feedback
- Tag appropriate reviewers based on the nature of changes
- Update PR description if significant changes were made

## Workflow

1. **Identify Open PRs**: Scan repository for open pull requests with pending reviews or requested changes
2. **Analyze Feedback**: Parse all review comments, suggestions, and change requests
3. **Implement Changes**: Make necessary code changes, fixes, and improvements
4. **Test Changes**: Ensure all changes work correctly and don't break existing functionality
5. **Commit Changes**: Stage and commit all changes with clear, descriptive messages
6. **Request Review**: Tag @mohavro and other relevant reviewers for re-review

## Best Practices

- Always read and understand the full context of review comments before implementing changes
- Make minimal, focused changes that directly address reviewer feedback
- Test changes thoroughly before committing
- Write clear commit messages that reference the specific feedback being addressed
- If unsure about a reviewer's intent, ask for clarification rather than guessing
- Maintain code quality and consistency with the existing codebase
- Update tests when functionality changes
- Update documentation when API or behavior changes

## Error Handling

- If a requested change conflicts with other requirements, document the conflict and seek clarification
- If tests fail after implementing changes, fix the issues before committing
- If merge conflicts arise, resolve them carefully while preserving the intent of both changes
- If unable to implement a specific change, document the limitation and suggest alternatives

## Security Considerations

- Pay special attention to security-related feedback and implement fixes promptly
- Ensure no sensitive information is exposed in commits or comments
- Follow secure coding practices when implementing changes
- Validate all inputs and sanitize outputs as appropriate

## Integration Notes

- Works with GitHub API for pull request management
- Integrates with git for version control operations
- Supports conventional commit message formats
- Compatible with existing CI/CD workflows in the repository

## Limitations

- Cannot automatically resolve complex architectural decisions that require human judgment
- May need human intervention for ambiguous or conflicting reviewer feedback
- Cannot perform changes that require external system access or credentials
- Limited to changes within the scope of the repository
