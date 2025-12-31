# pr-copilot GitHub App

Automated Pull Request agent for DashFin/financial-asset-relationship-db

## Features

- Responds to `@pr-copilot` mention and `help wanted` PR label
- Keeps PR scope tight and warns on scope creep
- Provides progress/status updates on command
- Attends to review comments and auto-commits (see notes)
- Handles/solves merge conflicts (permission required)
- Attempts automerge upon completion

## Usage

- Mention `@pr-copilot` in a PR description, review, or comment for help, or type `@pr-copilot status update`.
- Add `help wanted` label to a PR to summon the agent.
- For reviewer comments that request code updates, the agent will acknowledge and (if permitted) push fixes.

## Extending

- To enable true auto-fixes from code reviews, connect the agent with repo write access. Extending the suggestion-patch logic is required (see TODOs in `pr-copilot.ts`).
- For persistence, plug in a Redis/mongo/DB adapter for PR status tracking.

## Deploy

This bot is ready for use with Probot (https://probot.github.io/docs/deployment/).
