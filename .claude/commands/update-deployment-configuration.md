---
name: update-deployment-configuration
description: Workflow command scaffold for update-deployment-configuration in financial-asset-relationship-db.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /update-deployment-configuration

Use this workflow when working on **update-deployment-configuration** in `financial-asset-relationship-db`.

## Goal

Update deployment-related configuration files such as Dockerfiles or docker-compose files to adjust build, environment, or runtime settings.

## Common Files

- `Dockerfile.api`
- `Dockerfile.frontend`
- `docker-compose.production.yml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit one or more deployment configuration files (e.g., Dockerfile.api, Dockerfile.frontend, docker-compose.production.yml)
- Commit the changes with a message referencing the file and possibly co-authors or cherry-picks

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.