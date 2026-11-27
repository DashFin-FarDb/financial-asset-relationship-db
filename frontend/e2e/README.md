# Full-Stack Playwright E2E Smoke Suite

End-to-end browser and API smoke tests verifying a live **Next.js frontend + FastAPI backend** stack.

## Running Locally

1. Start the FastAPI backend (`:8000`) and Next.js frontend (`:3000`) via `./run-dev.sh` or `docker compose -f docker-compose.production.yml up -d`.
2. Execute the Playwright smoke suite from `frontend/`:

```bash
cd frontend
E2E_BASE_URL=http://127.0.0.1:3000 \
E2E_API_URL=http://127.0.0.1:8000 \
npx --yes @playwright/test test
```

3. To include the authenticated `/token` -> `/api/users/me` -> `/api/auth/logout` revocation test, also export `E2E_ADMIN_USERNAME` and `E2E_ADMIN_PASSWORD`.
