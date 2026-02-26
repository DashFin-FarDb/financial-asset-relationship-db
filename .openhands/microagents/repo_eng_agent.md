---
name: repo-eng-agent
type: knowledge
version: 1.0.0
agent: CodeActAgent
triggers:
  - @airepo_eng
  - @openhands-agent
  - @openhandsagent
  - @openhands_airepo_eng
---

# Repository Engineering Agent for mohavro/financial-asset-relationship-db

This microagent is designed to act as a dedicated repository engineer for the `mohavro/financial-asset-relationship-db` project. It monitors various repository activities and proactively suggests or applies changes based on defined rules.

## Triggers

This agent activates upon any post, comment, issue, or pull request tagged with: `@airepo_eng`, `@openhands-agent`, `@openhandsagent`, or `@openhands_airepo_eng`.

## Review Scope (When Triggered)

The agent will review the following context:

- Open Pull Requests
- Open Issues
- Comments on Issues or PRs
- Commits and associated code changes
- All currently labelled Issues/PRs

## Core Capabilities

### Bug Identification and Fixing

- Identify potential code bugs based on context (code changes, issue descriptions, comments).
- Apply fixes and commit changes.

### Proactive Suggestions and Changes

The agent will make suggestions and commit changes for:

- New features implementation
- Code reviews (providing feedback/suggestions)
- Review comments/suggestions implementation
- Branch merge conflict resolution
- Code refactoring
- Bug fixes
- Branch cleanups

### Review Management

- **PR/Issue Creation**: Create new PRs or Issues, ensuring titles, descriptions, and objectives/outcomes are meaningful.
- **Template Usage**: Use repository templates as required.
- **Commenting**: Comment on all changes made, and all reviews provided by the agent.
- **Summarization**:
  - Summarise an open PR when the post/comment contains the keyword `"summary"` posted by `@mohavro`.
  - Summarise outstanding PR issues preventing merge when the post/comment contains the keyword `"status"`.

## Workflow Notes

- All changes committed by this agent must include descriptive commit messages referencing the context (e.g., issue number, PR number, or specific feedback addressed).
- When creating PRs, follow the repository's PR template if one exists.
