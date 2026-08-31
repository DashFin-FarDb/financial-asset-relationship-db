# GNC Phase 2 enrolled controlled-draft proof

This document is the sole inert change in the enrolled post-repair proof for
GNC Phase 2. It gives the deterministic advisory one bounded, non-runtime path
to inventory against the versioned contract approved on issue #1739.

The controlled draft does not alter application behavior, workflows,
dependencies, permissions, providers, databases, deployments, observability,
rulesets, branch protection, or merge policy. It is not intended to merge.

Completion evidence may be recorded on issue #1739 only after all of the
following observations are bound to the same exact controlled head:

- the opening evaluation reports fail-safe `needs-human` while immutable
  approval is absent;
- a new unedited approval comment binds the exact contract hash, head SHA,
  policy SHA, version, and approving actor;
- a body-only edit retriggers the advisory without changing the contract or
  Git head;
- the advisory binds the exact base, policy, target, literal changed path, and
  required prior exact-head advisory execution;
- two completed unchanged-head evaluations emit byte-identical bounded
  artifacts;
- one superseded run is cancelled or reported stale and never becomes the
  current verdict;
- the advisory remains a non-required check and creates no comment, review,
  label, commit, merge, deployment, provider, ruleset, permission, secret, or
  repository-setting mutation; and
- closing this draft unmerged and closing Phase 2 are separately authorised
  human actions, with auto-merge disabled throughout.

This proof does not authorise Phase 3 semantic analysis or enforcement.
