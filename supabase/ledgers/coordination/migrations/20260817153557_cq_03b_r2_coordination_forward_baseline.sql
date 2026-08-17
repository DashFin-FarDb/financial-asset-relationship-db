-- CQ-03B-R2 forward coordination baseline; control issue: GitHub #1633 / Linear DAS-62.
-- Managed schema: public. Transaction policy: one atomic transaction.
-- Lock expectation: normal PostgreSQL catalog locks during fresh-target creation.
-- Data/backfill behavior: schema and authorization only; no coordination rows are copied or seeded.
-- Rollback/restore: discard the disposable database; applied migrations are otherwise forward-only.
-- Provider capability: none. The fixed fardb_runtime_coordination NOLOGIN role must already exist.
-- Reconstruction authority: ADR 0010 and merged PR #1640. This is not historical provider SQL.
-- Reviewed provider-statement evidence digests (ordered receipt set; non-executable provenance):
-- a0876b49e1715b5d28d1db02e8787d8137d3c8c608e0031ed183df45884d7b66
-- 1f32791a479a88f25498f2d4a0c7610c8c73fd94ca4520d0d087945900c4aacb
-- 4e6f8153401574850a3d0e41e5c1919a9d076afada6806b7f5b919f3fe62ba18
-- c0d774395ec0599048ade5309b3998795d49a0467596ad26c5728eaa373e9500
-- 7d0cb353bfac38a9077a82ad2b696941332f0ad866514828b1d8fa1a67fe3e4f

BEGIN;

CREATE TABLE public.distributed_locks (
    lock_name VARCHAR(64) PRIMARY KEY,
    holder_id VARCHAR(64) NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL
);

ALTER TABLE public.distributed_locks ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE public.distributed_locks
    FROM PUBLIC, fardb_runtime_auth, fardb_runtime_graph, fardb_runtime_coordination;

GRANT USAGE ON SCHEMA public TO fardb_runtime_coordination;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.distributed_locks
    TO fardb_runtime_coordination;

CREATE POLICY fardb_coordination_select_v1 ON public.distributed_locks
    FOR SELECT TO fardb_runtime_coordination USING (true);
CREATE POLICY fardb_coordination_insert_v1 ON public.distributed_locks
    FOR INSERT TO fardb_runtime_coordination WITH CHECK (true);
CREATE POLICY fardb_coordination_update_v1 ON public.distributed_locks
    FOR UPDATE TO fardb_runtime_coordination USING (true) WITH CHECK (true);
CREATE POLICY fardb_coordination_delete_v1 ON public.distributed_locks
    FOR DELETE TO fardb_runtime_coordination USING (true);

COMMIT;
