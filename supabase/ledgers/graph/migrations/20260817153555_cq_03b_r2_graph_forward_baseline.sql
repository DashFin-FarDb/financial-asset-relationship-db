-- CQ-03B-R2 forward graph baseline; control issue: GitHub #1633 / Linear DAS-62.
-- Managed schema: public. Transaction policy: one atomic transaction.
-- Lock expectation: normal PostgreSQL catalog locks during fresh-target creation.
-- Data/backfill behavior: schema and authorization only; no application rows are copied or seeded.
-- Rollback/restore: discard the disposable database; applied migrations are otherwise forward-only.
-- Provider capability: plpgsql (built in on supported PostgreSQL/Supabase targets).
-- The fixed fardb_runtime_graph NOLOGIN role must already exist.
-- Reconstruction authority: ADR 0010 and merged PR #1640. This is not historical provider SQL.
-- Reviewed provider-statement evidence digests (ordered receipt set; non-executable provenance):
-- a0876b49e1715b5d28d1db02e8787d8137d3c8c608e0031ed183df45884d7b66
-- 1f32791a479a88f25498f2d4a0c7610c8c73fd94ca4520d0d087945900c4aacb
-- 4e6f8153401574850a3d0e41e5c1919a9d076afada6806b7f5b919f3fe62ba18
-- c0d774395ec0599048ade5309b3998795d49a0467596ad26c5728eaa373e9500
-- 7d0cb353bfac38a9077a82ad2b696941332f0ad866514828b1d8fa1a67fe3e4f

BEGIN;

CREATE TABLE public.assets (
    id VARCHAR PRIMARY KEY,
    symbol VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    asset_class VARCHAR NOT NULL,
    sector VARCHAR NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    market_cap DOUBLE PRECISION,
    currency VARCHAR(3) NOT NULL,
    pe_ratio DOUBLE PRECISION,
    dividend_yield DOUBLE PRECISION,
    earnings_per_share DOUBLE PRECISION,
    book_value DOUBLE PRECISION,
    yield_to_maturity DOUBLE PRECISION,
    coupon_rate DOUBLE PRECISION,
    maturity_date VARCHAR,
    credit_rating VARCHAR,
    issuer_id VARCHAR,
    contract_size DOUBLE PRECISION,
    delivery_date VARCHAR,
    volatility DOUBLE PRECISION,
    exchange_rate DOUBLE PRECISION,
    country VARCHAR,
    central_bank_rate DOUBLE PRECISION
);

CREATE TABLE public.rebuild_jobs (
    job_id VARCHAR PRIMARY KEY,
    requested_by VARCHAR(64) NOT NULL,
    status VARCHAR(16) NOT NULL,
    source VARCHAR(32),
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER,
    node_count INTEGER,
    edge_count INTEGER,
    sanitized_failure_category VARCHAR(64),
    sanitized_failure_message VARCHAR(512),
    execution_id VARCHAR(64),
    active_worker_id VARCHAR(64),
    last_heartbeat_at TIMESTAMP WITH TIME ZONE,
    checkpoint_data TEXT,
    cancellation_requested_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT ck_rebuild_jobs_status CHECK (
        status IN ('pending', 'running', 'succeeded', 'failed', 'cancelled', 'cancel_requested')
    )
);

CREATE INDEX ix_rebuild_jobs_created_at
    ON public.rebuild_jobs (created_at);
CREATE INDEX ix_rebuild_jobs_status_created_at
    ON public.rebuild_jobs (status, created_at);

CREATE TABLE public.relationship_assertions (
    id VARCHAR(36) PRIMARY KEY,
    predicate_id VARCHAR(256) NOT NULL,
    subject_id VARCHAR(128) NOT NULL,
    object_id VARCHAR(128) NOT NULL,
    method_id VARCHAR(256) NOT NULL,
    proposition TEXT NOT NULL,
    confidence_bp INTEGER,
    confidence_type VARCHAR(128),
    confidence_method VARCHAR(256),
    confidence_status VARCHAR(32) NOT NULL,
    effective_from TIMESTAMP WITH TIME ZONE NOT NULL,
    effective_to TIMESTAMP WITH TIME ZONE,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT ck_relationship_assertions_confidence_status
        CHECK (confidence_status IN ('assessed', 'not_assessed')),
    CONSTRAINT ck_relationship_assertions_confidence_bp
        CHECK (confidence_bp IS NULL OR (confidence_bp >= 0 AND confidence_bp <= 10000)),
    CONSTRAINT ck_relationship_assertions_confidence_assessed CHECK (
        (
            confidence_status = 'not_assessed'
            AND confidence_bp IS NULL
            AND confidence_type IS NULL
            AND confidence_method IS NULL
        )
        OR (
            confidence_status = 'assessed'
            AND confidence_bp IS NOT NULL
            AND confidence_type IS NOT NULL
            AND confidence_method IS NOT NULL
        )
    ),
    CONSTRAINT ck_relationship_assertions_effective_window
        CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

CREATE INDEX ix_relationship_assertions_predicate_subject
    ON public.relationship_assertions (predicate_id, subject_id);
CREATE INDEX ix_relationship_assertions_recorded_at
    ON public.relationship_assertions (recorded_at);
CREATE INDEX ix_relationship_assertions_effective_from
    ON public.relationship_assertions (effective_from);

CREATE TABLE public.relationship_evidence (
    id VARCHAR(36) PRIMARY KEY,
    source_ref VARCHAR(2048) NOT NULL,
    content_sha256 VARCHAR(64) NOT NULL,
    media_type VARCHAR(128) NOT NULL,
    observed_at TIMESTAMP WITH TIME ZONE,
    issued_at TIMESTAMP WITH TIME ZONE,
    visibility VARCHAR(32) NOT NULL,
    licensing VARCHAR(512),
    reuse_policy VARCHAR(512),
    custody_id VARCHAR(128) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT ck_relationship_evidence_visibility
        CHECK (visibility IN ('public', 'internal', 'restricted', 'confidential')),
    CONSTRAINT ck_relationship_evidence_sha256_hex CHECK (
        length(content_sha256) = 64
        AND content_sha256 = lower(content_sha256)
        AND translate(content_sha256, '0123456789abcdef', '') = '' -- NOSONAR: immutable CHECK stays self-contained
    )
);

CREATE INDEX ix_relationship_evidence_content_sha256
    ON public.relationship_evidence (content_sha256);
CREATE INDEX ix_relationship_evidence_recorded_at
    ON public.relationship_evidence (recorded_at);

CREATE TABLE public.relationship_projection_revisions (
    id VARCHAR(36) PRIMARY KEY,
    purpose VARCHAR(128) NOT NULL,
    effective_at TIMESTAMP WITH TIME ZONE NOT NULL,
    known_at TIMESTAMP WITH TIME ZONE NOT NULL,
    contract_version VARCHAR(64) NOT NULL,
    projector_version VARCHAR(64) NOT NULL,
    edge_set_hash VARCHAR(64) NOT NULL,
    projection_hash VARCHAR(64) NOT NULL,
    governed_scopes TEXT NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT ck_relationship_projection_revisions_edge_set_hash_hex CHECK (
        length(edge_set_hash) = 64
        AND edge_set_hash = lower(edge_set_hash)
        AND translate(edge_set_hash, '0123456789abcdef', '') = '' -- NOSONAR: immutable CHECK stays self-contained
    ),
    CONSTRAINT ck_relationship_projection_revisions_projection_hash_hex CHECK (
        length(projection_hash) = 64
        AND projection_hash = lower(projection_hash)
        AND translate(projection_hash, '0123456789abcdef', '') = '' -- NOSONAR: immutable CHECK stays self-contained
    )
);

CREATE INDEX ix_relationship_projection_revisions_purpose
    ON public.relationship_projection_revisions (purpose);
CREATE INDEX ix_relationship_projection_revisions_created_at
    ON public.relationship_projection_revisions (created_at);
CREATE INDEX ix_relationship_projection_revisions_effective_known
    ON public.relationship_projection_revisions (effective_at, known_at);

CREATE TABLE public.asset_relationships (
    id SERIAL PRIMARY KEY,
    source_asset_id VARCHAR NOT NULL REFERENCES public.assets (id) ON DELETE CASCADE,
    target_asset_id VARCHAR NOT NULL REFERENCES public.assets (id) ON DELETE CASCADE,
    relationship_type VARCHAR NOT NULL,
    strength DOUBLE PRECISION NOT NULL,
    bidirectional BOOLEAN NOT NULL DEFAULT FALSE,
    CONSTRAINT uq_relationship UNIQUE (source_asset_id, target_asset_id, relationship_type)
);

CREATE TABLE public.regulatory_events (
    id VARCHAR PRIMARY KEY,
    asset_id VARCHAR NOT NULL REFERENCES public.assets (id) ON DELETE CASCADE,
    event_type VARCHAR NOT NULL,
    date VARCHAR NOT NULL,
    description VARCHAR NOT NULL,
    impact_score DOUBLE PRECISION NOT NULL
);

CREATE TABLE public.relationship_assertion_events (
    id VARCHAR(36) PRIMARY KEY,
    assertion_id VARCHAR(36) NOT NULL
        REFERENCES public.relationship_assertions (id) ON DELETE RESTRICT,
    sequence INTEGER NOT NULL,
    from_state VARCHAR(32),
    to_state VARCHAR(32) NOT NULL,
    authority VARCHAR(64) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    rationale TEXT NOT NULL,
    policy_version VARCHAR(64) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    successor_assertion_id VARCHAR(36)
        REFERENCES public.relationship_assertions (id) ON DELETE RESTRICT,
    correlation_id VARCHAR(128),
    CONSTRAINT ck_relationship_assertion_events_from_state CHECK (
        from_state IS NULL
        OR from_state IN ('Proposed', 'Accepted', 'Rejected', 'Withdrawn', 'Disputed', 'Retracted', 'Superseded')
    ),
    CONSTRAINT ck_relationship_assertion_events_to_state CHECK (
        to_state IN ('Proposed', 'Accepted', 'Rejected', 'Withdrawn', 'Disputed', 'Retracted', 'Superseded')
    ),
    CONSTRAINT ck_relationship_assertion_events_sequence CHECK (sequence >= 1),
    CONSTRAINT uq_relationship_assertion_events_sequence UNIQUE (assertion_id, sequence)
);

CREATE INDEX ix_relationship_assertion_events_assertion_id
    ON public.relationship_assertion_events (assertion_id);
CREATE INDEX ix_relationship_assertion_events_recorded_at
    ON public.relationship_assertion_events (recorded_at);
CREATE INDEX ix_relationship_assertion_events_successor_assertion_id
    ON public.relationship_assertion_events (successor_assertion_id);

CREATE TABLE public.relationship_assertion_evidence (
    id VARCHAR(36) PRIMARY KEY,
    assertion_id VARCHAR(36) NOT NULL
        REFERENCES public.relationship_assertions (id) ON DELETE RESTRICT,
    evidence_id VARCHAR(36) NOT NULL
        REFERENCES public.relationship_evidence (id) ON DELETE RESTRICT,
    polarity VARCHAR(32) NOT NULL,
    recorded_at TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT ck_relationship_assertion_evidence_polarity
        CHECK (polarity IN ('supporting', 'opposing', 'contextual')),
    CONSTRAINT uq_relationship_assertion_evidence_link UNIQUE (assertion_id, evidence_id)
);

CREATE INDEX ix_relationship_assertion_evidence_assertion_id
    ON public.relationship_assertion_evidence (assertion_id);
CREATE INDEX ix_relationship_assertion_evidence_evidence_id
    ON public.relationship_assertion_evidence (evidence_id);
CREATE INDEX ix_relationship_assertion_evidence_recorded_at
    ON public.relationship_assertion_evidence (recorded_at);

CREATE TABLE public.relationship_projection_edges (
    id VARCHAR(36) PRIMARY KEY,
    revision_id VARCHAR(36) NOT NULL
        REFERENCES public.relationship_projection_revisions (id) ON DELETE RESTRICT,
    source_id VARCHAR(128) NOT NULL,
    target_id VARCHAR(128) NOT NULL,
    edge_type VARCHAR(128) NOT NULL,
    strength VARCHAR(64) NOT NULL,
    direction VARCHAR(32) NOT NULL,
    assertion_id VARCHAR(36) NOT NULL
        REFERENCES public.relationship_assertions (id) ON DELETE RESTRICT,
    CONSTRAINT ck_relationship_projection_edges_direction
        CHECK (direction IN ('subject_to_object', 'object_to_subject', 'bidirectional')),
    CONSTRAINT ck_relationship_projection_edges_strength CHECK (
        length(strength) BETWEEN 1 AND 32
        AND translate(strength, '0123456789.', '') = ''
        AND strength NOT LIKE '.%'
        AND strength NOT LIKE '%.'
        AND strength NOT LIKE '%..%'
        AND strength NOT LIKE '%.%.%'
        AND (
            strength = '0'
            OR strength = '1'
            OR strength LIKE '0.%'
            OR (strength LIKE '1.%' AND replace(substr(strength, 3), '0', '') = '')
        )
    )
);

CREATE INDEX ix_relationship_projection_edges_revision_id
    ON public.relationship_projection_edges (revision_id);
CREATE INDEX ix_relationship_projection_edges_assertion_id
    ON public.relationship_projection_edges (assertion_id);
CREATE INDEX ix_relationship_projection_edges_source_target
    ON public.relationship_projection_edges (source_id, target_id);

CREATE TABLE public.regulatory_event_assets (
    id SERIAL PRIMARY KEY,
    event_id VARCHAR NOT NULL REFERENCES public.regulatory_events (id) ON DELETE CASCADE,
    asset_id VARCHAR NOT NULL REFERENCES public.assets (id) ON DELETE CASCADE,
    CONSTRAINT uq_event_asset UNIQUE (event_id, asset_id)
);

CREATE TABLE public.relationship_projection_publications (
    id VARCHAR(36) PRIMARY KEY,
    revision_id VARCHAR(36) NOT NULL
        REFERENCES public.relationship_projection_revisions (id) ON DELETE RESTRICT,
    rebuild_job_id VARCHAR NOT NULL
        REFERENCES public.rebuild_jobs (job_id) ON DELETE RESTRICT,
    published_at TIMESTAMP WITH TIME ZONE NOT NULL,
    execution_id VARCHAR(64),
    CONSTRAINT uq_relationship_projection_publications_rev_job
        UNIQUE (revision_id, rebuild_job_id)
);

CREATE INDEX ix_relationship_projection_publications_revision_id
    ON public.relationship_projection_publications (revision_id);
CREATE INDEX ix_relationship_projection_publications_rebuild_job_id
    ON public.relationship_projection_publications (rebuild_job_id);
CREATE INDEX ix_relationship_projection_publications_published_at
    ON public.relationship_projection_publications (published_at);

CREATE FUNCTION public.grac_v1_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path TO pg_catalog
AS $grac$
BEGIN
    RAISE EXCEPTION 'GRAC v1 immutability: % forbidden on %', TG_OP, TG_TABLE_NAME
        USING ERRCODE = 'integrity_constraint_violation';
END;
$grac$;

REVOKE ALL PRIVILEGES ON FUNCTION public.grac_v1_reject_mutation()
    FROM PUBLIC, fardb_runtime_auth, fardb_runtime_graph, fardb_runtime_coordination;

CREATE TRIGGER grac_imm_relationship_evidence_u
    BEFORE UPDATE ON public.relationship_evidence
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_evidence_d
    BEFORE DELETE ON public.relationship_evidence
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_evidence_t
    BEFORE TRUNCATE ON public.relationship_evidence
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

CREATE TRIGGER grac_imm_relationship_assertions_u
    BEFORE UPDATE ON public.relationship_assertions
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_assertions_d
    BEFORE DELETE ON public.relationship_assertions
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_assertions_t
    BEFORE TRUNCATE ON public.relationship_assertions
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

CREATE TRIGGER grac_imm_relationship_assertion_evidence_u
    BEFORE UPDATE ON public.relationship_assertion_evidence
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_assertion_evidence_d
    BEFORE DELETE ON public.relationship_assertion_evidence
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_assertion_evidence_t
    BEFORE TRUNCATE ON public.relationship_assertion_evidence
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

CREATE TRIGGER grac_imm_relationship_assertion_events_u
    BEFORE UPDATE ON public.relationship_assertion_events
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_assertion_events_d
    BEFORE DELETE ON public.relationship_assertion_events
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_assertion_events_t
    BEFORE TRUNCATE ON public.relationship_assertion_events
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

CREATE TRIGGER grac_imm_relationship_projection_revisions_u
    BEFORE UPDATE ON public.relationship_projection_revisions
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_projection_revisions_d
    BEFORE DELETE ON public.relationship_projection_revisions
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_projection_revisions_t
    BEFORE TRUNCATE ON public.relationship_projection_revisions
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

CREATE TRIGGER grac_imm_relationship_projection_edges_u
    BEFORE UPDATE ON public.relationship_projection_edges
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_projection_edges_d
    BEFORE DELETE ON public.relationship_projection_edges
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_projection_edges_t
    BEFORE TRUNCATE ON public.relationship_projection_edges
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

CREATE TRIGGER grac_imm_relationship_projection_publications_u
    BEFORE UPDATE ON public.relationship_projection_publications
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_projection_publications_d
    BEFORE DELETE ON public.relationship_projection_publications
    FOR EACH ROW EXECUTE FUNCTION public.grac_v1_reject_mutation();
CREATE TRIGGER grac_imm_relationship_projection_publications_t
    BEFORE TRUNCATE ON public.relationship_projection_publications
    FOR EACH STATEMENT EXECUTE FUNCTION public.grac_v1_reject_mutation();

ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.asset_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regulatory_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.regulatory_event_assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rebuild_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_assertions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_assertion_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_assertion_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_projection_revisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_projection_edges ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.relationship_projection_publications ENABLE ROW LEVEL SECURITY;

REVOKE ALL PRIVILEGES ON TABLE
    public.assets,
    public.asset_relationships,
    public.regulatory_events,
    public.regulatory_event_assets,
    public.rebuild_jobs,
    public.relationship_evidence,
    public.relationship_assertions,
    public.relationship_assertion_evidence,
    public.relationship_assertion_events,
    public.relationship_projection_revisions,
    public.relationship_projection_edges,
    public.relationship_projection_publications
    FROM PUBLIC, fardb_runtime_auth, fardb_runtime_graph, fardb_runtime_coordination;

REVOKE ALL PRIVILEGES ON SEQUENCE
    public.asset_relationships_id_seq,
    public.regulatory_event_assets_id_seq
    FROM PUBLIC, fardb_runtime_auth, fardb_runtime_graph, fardb_runtime_coordination;

GRANT USAGE ON SCHEMA public TO fardb_runtime_graph;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE
    public.assets,
    public.asset_relationships,
    public.regulatory_events,
    public.regulatory_event_assets
    TO fardb_runtime_graph;
GRANT SELECT, INSERT, UPDATE ON TABLE public.rebuild_jobs TO fardb_runtime_graph;
GRANT SELECT, INSERT ON TABLE
    public.relationship_evidence,
    public.relationship_assertions,
    public.relationship_assertion_evidence,
    public.relationship_assertion_events,
    public.relationship_projection_revisions,
    public.relationship_projection_edges,
    public.relationship_projection_publications
    TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_evidence TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_assertions TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_assertion_evidence TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_assertion_events TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_projection_revisions TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_projection_edges TO fardb_runtime_graph;
GRANT UPDATE (id) ON TABLE public.relationship_projection_publications TO fardb_runtime_graph;
GRANT USAGE, SELECT ON SEQUENCE
    public.asset_relationships_id_seq,
    public.regulatory_event_assets_id_seq
    TO fardb_runtime_graph;

CREATE POLICY fardb_graph_select_v1 ON public.assets
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.assets
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_update_v1 ON public.assets
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (true);
CREATE POLICY fardb_graph_delete_v1 ON public.assets
    FOR DELETE TO fardb_runtime_graph USING (true);

CREATE POLICY fardb_graph_select_v1 ON public.asset_relationships
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.asset_relationships
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_update_v1 ON public.asset_relationships
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (true);
CREATE POLICY fardb_graph_delete_v1 ON public.asset_relationships
    FOR DELETE TO fardb_runtime_graph USING (true);

CREATE POLICY fardb_graph_select_v1 ON public.regulatory_events
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.regulatory_events
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_update_v1 ON public.regulatory_events
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (true);
CREATE POLICY fardb_graph_delete_v1 ON public.regulatory_events
    FOR DELETE TO fardb_runtime_graph USING (true);

CREATE POLICY fardb_graph_select_v1 ON public.regulatory_event_assets
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.regulatory_event_assets
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_update_v1 ON public.regulatory_event_assets
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (true);
CREATE POLICY fardb_graph_delete_v1 ON public.regulatory_event_assets
    FOR DELETE TO fardb_runtime_graph USING (true);

CREATE POLICY fardb_graph_select_v1 ON public.rebuild_jobs
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.rebuild_jobs
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_update_v1 ON public.rebuild_jobs
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (true);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_evidence
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_evidence
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_evidence
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_assertions
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_assertions
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_assertions
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_assertion_evidence
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_assertion_evidence
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_assertion_evidence
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_assertion_events
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_assertion_events
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_assertion_events
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_projection_revisions
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_projection_revisions
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_projection_revisions
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_projection_edges
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_projection_edges
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_projection_edges
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

CREATE POLICY fardb_graph_select_v1 ON public.relationship_projection_publications
    FOR SELECT TO fardb_runtime_graph USING (true);
CREATE POLICY fardb_graph_insert_v1 ON public.relationship_projection_publications
    FOR INSERT TO fardb_runtime_graph WITH CHECK (true);
CREATE POLICY fardb_graph_lock_v1 ON public.relationship_projection_publications
    FOR UPDATE TO fardb_runtime_graph USING (true) WITH CHECK (false);

COMMIT;
