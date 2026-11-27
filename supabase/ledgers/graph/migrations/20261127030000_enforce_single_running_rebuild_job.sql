-- H-P2-03: Enforce at most one RUNNING rebuild job at the database layer.
-- Transaction policy: one atomic transaction; partial unique index on public.rebuild_jobs.
BEGIN;

CREATE UNIQUE INDEX uq_rebuild_jobs_single_running
    ON public.rebuild_jobs (status)
    WHERE (status = 'running');

COMMIT;
