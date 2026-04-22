## Primary seam / decision

<!-- State the single architectural or runtime decision this PR implements. -->
<!-- Example: Extract FastAPI app construction from api/main.py. -->

## Why this seam now

<!-- Explain why this is the next valid step in issue #1028 / roadmap sequencing. -->
<!-- Keep this repo-grounded and specific. -->

## In scope

- [ ] One clearly defined seam only

<!-- List the exact responsibilities being moved, extracted, hardened, or clarified. -->

## Out of scope

<!-- Explicitly list nearby concerns that are NOT being changed in this PR. -->
<!-- Example: auth model redesign, broad lint cleanup, deployment changes, unrelated tests/docs -->

## Backward compatibility contract

<!-- List any imports, entrypoints, globals, wrappers, public helpers, or router aliases that must remain available. -->
<!-- If compatibility is intentionally changed, state it explicitly and justify it. -->

## Behavior intentionally preserved

<!-- State which runtime/startup/API behaviors are meant to stay the same. -->
<!-- Example: eager graph initialization during startup remains unchanged -->

## Known issues intentionally deferred

<!-- Record real issues noticed during the work but intentionally not fixed here to avoid scope drift. -->
<!-- Reference issue numbers where possible. -->

## Files expected to change

<!-- Enumerate the files that should change for this seam. -->
<!-- Reviewers can use this to detect drift. -->

## Validation commands

```bash
# Add the exact focused commands run for this seam
```

## Merge criteria

- [ ] PR implements one decision only
- [ ] No unrelated cleanup has been folded in
- [ ] Compatibility surface is preserved or explicitly documented
- [ ] Production architecture assumptions remain accurate (`FastAPI + Next.js`)
- [ ] Gradio/demo paths are not treated as production architecture
- [ ] Runtime dependency source of truth remains `requirements.txt`
- [ ] Any deferred issues are explicitly recorded
