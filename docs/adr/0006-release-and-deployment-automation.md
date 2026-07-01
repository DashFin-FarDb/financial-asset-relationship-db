# 0006: Release and Deployment Automation

## Status

Accepted

## Date

2026-07-01

## Context

As the project approaches enterprise readiness, the manual overhead of executing release-evidence gate tests, hosted-readiness checks, and staging baseline verification has become a bottleneck. We need a reproducible, automated layer to capture evidence and govern promotions. Currently, heavy security scanners and container builds run on every PR, increasing CI duration and noise. Additionally, the existing Docker setup bundles the Gradio demo image rather than serving the FastAPI backend and Next.js frontend separately for production.

## Decision

1. **GitHub Actions as the Canonical PR Gate:** We designate GitHub Actions as the canonical platform for PR gates.
2. **Heavyweight Job Scheduling:** Heavyweight scanner jobs (e.g., CodeQL, Trivy) and container publishing jobs will no longer run on every PR. Instead, they will run on scheduled intervals or within specific release-gate contexts.
3. **Production Container Split:** Production containers (FastAPI backend and Next.js frontend) will be split from the existing Gradio demo image. Dedicated Dockerfiles (`Dockerfile.api`, `Dockerfile.frontend`) and a `docker-compose.production.yml` will manage the production stack.
4. **Governed Automation:** The automation layer will be strictly bound to the constraints in `docs/GOVERNANCE.md`.

## Consequences

- Faster PR feedback cycles due to offloaded heavyweight scans.
- Clear separation between the demo environment (Gradio) and the production stack (FastAPI + Next.js).
- Reproducible, automated evidence generation for release gates and staging promotion.
