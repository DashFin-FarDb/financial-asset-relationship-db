# Governance Policy

## Scope

This policy applies to repository changes, release work, CI/CD configuration, security automation, and AI-assisted
contributions for the Financial Asset Relationship Database.

The production architecture remains FastAPI backend plus Next.js frontend. Non-production Gradio paths are not the
release target unless explicitly scoped.

For current rebuild, recovery, persistence, state-machine, operator ownership, and exception-handling interpretation, see the canonical [State Machine and Operating Authority](governance/state-machine-and-operating-authority.md). ADRs remain historical decision records for this area.

## Pull Request Approval Requirements

Non-draft pull requests require maintainer review before merge unless an existing automation rule explicitly allows
merge.

The repository's Mergify configuration already requests maintainer review for non-draft PRs that do not have an assigned
reviewer. It also dismisses stale approvals when new commits are pushed, requiring reviewers to re-approve updated
changes.

Automated merge rules are intentionally narrow and must remain tied to passing CI. Any expansion of auto-merge behavior
is a security-sensitive change.

## Security-Sensitive Changes

The following changes require explicit maintainer review:

- authentication or authorization logic;
- secret handling;
- release workflows;
- signing or provenance;
- CI security gates;
- dependency security policy;
- monitoring or alerting for security events;
- permission changes;
- GitHub Actions token or OIDC configuration.

## Release Procedure

The Docker workflow publishes on semver tags matching `v*.*.*`, uses pinned GitHub Actions, logs into GHCR outside pull
requests, builds and pushes images, and signs published images with Cosign outside pull requests.

Release procedure:

1. Maintainer opens release PR.
2. Required CI gates pass.
3. Maintainer approval is recorded.
4. Semver tag `vX.Y.Z` is created.
5. Docker publish workflow builds and publishes the GHCR image.
6. Published image is signed with Cosign.
7. PyPI release uses trusted publishing where configured.
8. Release notes link to artifacts, SBOM, and verification instructions.

## Artifact Integrity

Release artifacts must be traceable to the repository workflow that produced them.

Docker images published from release tags must be signed with Cosign using Sigstore keyless signing. Docker publish runs
outside pull requests must upload an SPDX JSON SBOM artifact.

Consumers deploying production images should verify the Cosign signature and inspect the release SBOM before promotion.

## CI Gate Exceptions

CI or security gate bypass requires an explicit PR description section titled `Exception Request`.

The exception request must include:

- affected gate name;
- reason for bypass;
- risk assessment;
- expiry or follow-up issue;
- explicit maintainer approval.

Exceptions must be narrow, time-bound, and visible in the PR record. Permanent policy changes must be implemented as a
normal reviewed PR rather than repeated exceptions.

## Automation and AI Agent Boundaries

Automated contributions must follow `.github/AUTOMATION_SCOPE_POLICY.md`, including its required PR sections and
prohibited scope expansion rules.

Automation must not:

- expand PR scope without explicit approval;
- weaken authentication, authorization, signing, secret, or CI gate behavior;
- bypass required maintainer review;
- treat generated text as policy unless the repository commits it through normal review.
