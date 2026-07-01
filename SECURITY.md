# Security Policy

This document defines the repository-owned security policy for the Financial Asset Relationship Database.

## Vulnerability Disclosure Policy

Security vulnerabilities must be reported privately through GitHub Security Advisories.

Do not report exploitable vulnerabilities in public issues, pull requests, discussions, or commit messages before
coordinated disclosure.

### Response Targets

| Severity | Acknowledgement | Triage Target | Remediation Target |
| --- | --- | --- | --- |
| Critical | Within 48 hours | 1 business day | 7 calendar days where practical |
| High | Within 48 hours | 3 business days | 14 calendar days |
| Medium | Within 48 hours | 5 business days | 30 calendar days |
| Low | Within 48 hours | 10 business days | Next planned maintenance window or 90 days |

### Disclosure Process

1. Reporter submits a private GitHub Security Advisory.
2. Maintainer acknowledges within 48 hours.
3. Maintainer assigns severity.
4. Fix is developed privately where required.
5. Public disclosure occurs after release or after a 90-day embargo, whichever comes first, unless a different timeline
   is mutually agreed.

## Secret Management Policy

Secrets must be stored outside the repository and injected through approved runtime or CI/CD secret mechanisms.

### Rotation Schedule

| Secret Class | Required Rotation |
| --- | --- |
| JWT signing key / `SECRET_KEY` | Every 90 days |
| CI/CD tokens | Every 90 days |
| Database credentials | Every 180 days |
| Emergency rotation | Immediately on suspected leak, unauthorized access, or maintainer departure |

### Leak Response

1. Immediately revoke or rotate the exposed secret.
2. Identify the exposure window.
3. Audit relevant access logs.
4. Check CI logs, release artifacts, Docker image history, and repository history for secret exposure.
5. Produce an incident report within 24 hours.
6. Create follow-up corrective actions.

### Current Technical Enforcement

`src/config/settings.py` is the current enforcement point for `SECRET_KEY` strength. `Settings.validate_secret_key`
raises for values shorter than 32 characters in non-development and non-test environments. Development and test
environments receive a warning instead so local workflows remain usable.

## Incident Response Framework

| Severity | Description | Acknowledgement Target |
| --- | --- | --- |
| P1 / Critical | Active exploitation, credential compromise, production data exposure, or release artifact compromise | 1 hour |
| P2 / High | High-impact vulnerability without confirmed exploitation, privilege escalation, authentication bypass | 4 hours |
| P3 / Medium | Limited-impact vulnerability, misconfiguration, non-critical dependency issue | Next business day |
| P4 / Low | Hardening issue, low-impact scanner finding, documentation/security hygiene | Next business day |

### Escalation Path

1. Repository maintainer
2. Organization security contact
3. Hosting/provider support or package registry support
4. External reporting or user notification where legally or contractually required

### Post-Incident Review

P1 and P2 incidents require a post-incident review covering timeline, root cause, detection gap, remediation, and
prevention actions.

## Artifact Provenance and Integrity

Production Docker images must be signed with Cosign using Sigstore keyless signing.

Sigstore Fulcio certificates bind the signing identity to the GitHub Actions workflow identity. Rekor transparency log
entries provide tamper-evident public signing records where supported.

PyPI publishing must use OIDC trusted publishing where configured.

Production consumers should verify image signatures before deployment. Example:

```bash
cosign verify \
  --certificate-identity-regexp 'https://github.com/DashFin-FarDb/financial-asset-relationship-db/.github/workflows/docker-publish.yml@refs/tags/v.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com \
  ghcr.io/DashFin-FarDb/financial-asset-relationship-db:<version>
```

## SBOM Policy

Docker publish runs outside pull requests must generate a Software Bill of Materials.

- SBOM format: SPDX JSON.
- Availability: GitHub Actions release artifacts for non-PR Docker publish runs.
- Future target: publish SBOM as an OCI artifact associated with the GHCR image.
- Future target: SLSA provenance attestations for Docker and Python packages.
- Recommended path: `slsa-framework/slsa-github-generator`.

This repository does not currently claim SLSA compliance.
