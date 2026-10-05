-- ga Console schema (CMD-GC0). PostgreSQL 16. Applies to an empty database:
--   psql -v ON_ERROR_STOP=1 -f docs/schema.sql
-- Every CREATE TABLE is preceded by "-- owner: <domain>" (docs/domain-model.md owned_tables is the source;
-- scripts/check_docs.py checks both agree). Tokens are bigint; money is bigint micro-USD (or nano-USD on usage_calls).
-- Unknown values are NULL, never 0.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()

CREATE TYPE provenance AS ENUM ('MEASURED', 'CALCULATED', 'ESTIMATED', 'SIMULATED');
CREATE TYPE member_role AS ENUM ('admin', 'developer', 'viewer');
CREATE TYPE cost_measure AS ENUM ('list', 'cli');

-- ======================================================================== identity
-- owner: identity
CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text NOT NULL,
    display_name    text NOT NULL DEFAULT '',
    password_hash   text NOT NULL,                       -- Argon2id PHC string, never the password
    created_at      timestamptz NOT NULL DEFAULT now(),
    disabled_at     timestamptz
);
CREATE UNIQUE INDEX users_email_lower ON users (lower(email));

-- owner: identity
CREATE TABLE refresh_tokens (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      text NOT NULL UNIQUE,                -- sha256 of the opaque token
    family_id       uuid NOT NULL,                       -- rotation family: reuse of a rotated token revokes the family
    issued_at       timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz NOT NULL,
    rotated_at      timestamptz,
    revoked_at      timestamptz,
    user_agent_hash text
);
CREATE INDEX refresh_tokens_user ON refresh_tokens (user_id);

-- ======================================================================== workspace
-- owner: workspace
CREATE TABLE workspaces (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    slug            text NOT NULL UNIQUE,
    created_by      uuid NOT NULL REFERENCES users(id),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- owner: workspace
CREATE TABLE workspace_members (
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            member_role NOT NULL,
    joined_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, user_id)
);

-- owner: workspace
CREATE TABLE projects (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    name            text NOT NULL,
    repo_url        text,
    language        text,
    repo_size_loc   bigint,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, name)
);

-- ======================================================================== source
-- owner: source
CREATE TABLE sources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
    kind            text NOT NULL CHECK (kind IN ('upload', 'anthropic_api', 'openai_api', 'otel', 'ga_runner')),
    name            text NOT NULL,
    credential_id   uuid,                                -- integration.provider_credentials (later); no FK across domains
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- owner: source
CREATE TABLE uploads (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    source_id       uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    uploaded_by     uuid NOT NULL REFERENCES users(id),
    filename        text NOT NULL,
    size_bytes      bigint NOT NULL CHECK (size_bytes >= 0),
    sha256          text NOT NULL,
    declared_format text,                                -- user hint; detection is ingestion's job
    storage_path    text NOT NULL,                       -- object store key, never a public URL
    created_at      timestamptz NOT NULL DEFAULT now(),
    purge_after     timestamptz,
    purged_at       timestamptz
);
CREATE INDEX uploads_ws_sha ON uploads (workspace_id, sha256);

-- ======================================================================== ingestion
-- owner: ingestion
CREATE TABLE ingest_jobs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    upload_id       uuid NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    state           text NOT NULL DEFAULT 'queued'
                    CHECK (state IN ('queued', 'parsing', 'normalizing', 'loading', 'analyzing', 'done', 'failed')),
    source_kind     text CHECK (source_kind IN ('claude_code', 'ga_l0', 'anthropic_export', 'openai_export', 'otel')),
    parser          text,                                -- e.g. 'telemetry.collect.from_cc_jsonl@f6c7ae2'
    attempts        int NOT NULL DEFAULT 0,
    lines_total     bigint,
    inserted        bigint NOT NULL DEFAULT 0,
    duplicates      bigint NOT NULL DEFAULT 0,
    rejected        bigint NOT NULL DEFAULT 0,
    last_error_code text,
    claimed_by      text,
    claimed_at      timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    finished_at     timestamptz
);
CREATE INDEX ingest_jobs_queue ON ingest_jobs (created_at) WHERE state = 'queued';

-- owner: ingestion
CREATE TABLE ingest_job_events (
    job_id          uuid NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    seq             int NOT NULL,
    at              timestamptz NOT NULL DEFAULT now(),
    stage           text NOT NULL,
    pct             smallint NOT NULL CHECK (pct BETWEEN 0 AND 100),
    counts          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- {inserted, duplicates, rejected}; no content
    PRIMARY KEY (job_id, seq)
);

-- owner: ingestion
CREATE TABLE ingest_rejects (
    job_id          uuid NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    line_no         bigint NOT NULL,
    error_code      text NOT NULL,                       -- never the raw line
    PRIMARY KEY (job_id, line_no)
);

-- ======================================================================== usage
-- owner: usage
CREATE TABLE models (
    id              text PRIMARY KEY,                    -- provider model string, e.g. claude-haiku-4-5-20251001
    provider        text NOT NULL CHECK (provider IN ('anthropic', 'openai', 'gemini')),
    family          text NOT NULL CHECK (family IN ('claude', 'gpt', 'gemini')),
    tier            smallint NOT NULL,                   -- higher = stronger; used by advisor R4/R5
    min_cache_tokens int,
    display_name    text NOT NULL DEFAULT ''
);

-- owner: usage
CREATE TABLE model_prices (
    model_id        text NOT NULL REFERENCES models(id),
    version         int NOT NULL,
    effective_from  date NOT NULL,
    input_per_mtok_microusd          bigint NOT NULL,
    output_per_mtok_microusd         bigint NOT NULL,
    cache_read_per_mtok_microusd     bigint NOT NULL,
    cache_write_5m_per_mtok_microusd bigint NOT NULL,
    cache_write_1h_per_mtok_microusd bigint NOT NULL,
    source_note     text NOT NULL DEFAULT '',
    PRIMARY KEY (model_id, version)
);

-- owner: usage
CREATE TABLE usage_sessions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
    source_id       uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    client          text NOT NULL CHECK (client IN ('claude_code', 'codex', 'gemini_cli', 'api', 'ga')),
    external_id     text NOT NULL,
    started_at      timestamptz,
    ended_at        timestamptz,
    calls           int NOT NULL DEFAULT 0,
    input_tokens    bigint, cache_read_tokens bigint, cache_write_tokens bigint, output_tokens bigint,
    cost_list_microusd bigint,
    cost_cli_microusd  bigint,                           -- MEASURED (cost-state / run.end cost_usd)
    UNIQUE (workspace_id, source_id, external_id)
);

-- owner: usage
CREATE TABLE usage_tasks (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
    external_ref    text,                                -- ga work item id, FINAL_TASK run_id, ...
    kind            text NOT NULL DEFAULT 'other' CHECK (kind IN ('feature', 'bug', 'refactor', 'docs', 'other')),
    structure       text CHECK (structure IN ('A', 'B', 'C', 'single')),
    context_mode    text CHECK (context_mode IN ('bulk', 'selective', 'fresh')),
    context_cap_tokens bigint,
    repo_size_loc   bigint,
    language        text,
    model_primary   text REFERENCES models(id),
    node_count      int,
    outcome         text NOT NULL DEFAULT 'unknown' CHECK (outcome IN ('correct', 'incorrect', 'unknown')),
    outcome_source  text CHECK (outcome_source IN ('judge', 'user', 'fixture')),
    first_try_success boolean,
    started_at      timestamptz,
    ended_at        timestamptz,
    calls           int NOT NULL DEFAULT 0,
    input_tokens    bigint, cache_read_tokens bigint, cache_write_tokens bigint, output_tokens bigint,
    max_call_input  bigint,
    cost_list_nanousd bigint,
    cost_cli_microusd bigint,
    duration_ms     bigint
);
CREATE INDEX usage_tasks_ws ON usage_tasks (workspace_id, started_at);

-- owner: usage
CREATE TABLE usage_calls (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
    source_id       uuid NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    ingest_job_id   uuid NOT NULL REFERENCES ingest_jobs(id) ON DELETE CASCADE,
    session_id      uuid REFERENCES usage_sessions(id) ON DELETE SET NULL,
    task_id         uuid REFERENCES usage_tasks(id) ON DELETE SET NULL,
    source_kind     text NOT NULL CHECK (source_kind IN ('claude_code', 'ga_l0', 'anthropic_export', 'openai_export', 'otel')),
    provider        text NOT NULL,
    model_id        text NOT NULL REFERENCES models(id),
    occurred_at     timestamptz NOT NULL,
    time_basis      text NOT NULL DEFAULT 'reported' CHECK (time_basis IN ('reported', 'ingested')),
    call_index      int,
    role            text,
    input_tokens          bigint CHECK (input_tokens >= 0),
    cache_read_tokens     bigint CHECK (cache_read_tokens >= 0),
    cache_write_5m_tokens bigint CHECK (cache_write_5m_tokens >= 0),
    cache_write_1h_tokens bigint CHECK (cache_write_1h_tokens >= 0),
    output_tokens         bigint CHECK (output_tokens >= 0),
    thinking_tokens       bigint CHECK (thinking_tokens >= 0),
    context_tokens        bigint,
    tool_calls      int,
    latency_ms      int,
    cost_list_nanousd      bigint,                       -- CALCULATED
    price_version          int,
    cost_cli_microusd      bigint,                       -- MEASURED
    cost_provider_microusd bigint,                       -- MEASURED
    prompt_prefix_hash text,
    content_hashes  text[],
    dedupe_key      text NOT NULL,
    body_ref        text,
    UNIQUE (workspace_id, dedupe_key)
);
CREATE INDEX usage_calls_ws_time ON usage_calls (workspace_id, occurred_at);
CREATE INDEX usage_calls_task ON usage_calls (task_id);
CREATE INDEX usage_calls_session ON usage_calls (session_id, call_index);
CREATE INDEX usage_calls_prefix ON usage_calls (workspace_id, prompt_prefix_hash) WHERE prompt_prefix_hash IS NOT NULL;

-- owner: usage
CREATE TABLE usage_daily (
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid,                                -- NULL = no project; part of the key via COALESCE index
    day             date NOT NULL,
    model_id        text NOT NULL REFERENCES models(id),
    source_kind     text NOT NULL,
    calls           bigint NOT NULL,
    input_tokens    bigint NOT NULL, cache_read_tokens bigint NOT NULL,
    cache_write_tokens bigint NOT NULL, output_tokens bigint NOT NULL,
    cost_list_microusd bigint NOT NULL,
    cost_cli_microusd  bigint,                           -- NULL when no call of the bucket reported it
    cli_covered_calls  bigint NOT NULL DEFAULT 0
);
CREATE UNIQUE INDEX usage_daily_key ON usage_daily
    (workspace_id, COALESCE(project_id, '00000000-0000-0000-0000-000000000000'::uuid), day, model_id, source_kind);

-- ======================================================================== quota
-- owner: quota
CREATE TABLE budgets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid REFERENCES projects(id) ON DELETE CASCADE,
    scope           text NOT NULL CHECK (scope IN ('workspace', 'project', 'task')),
    period          text NOT NULL CHECK (period IN ('day', 'month', 'task')),
    measure         cost_measure NOT NULL,
    limit_microusd  bigint NOT NULL CHECK (limit_microusd > 0),
    thresholds      smallint[] NOT NULL DEFAULT '{50,80,100}',
    action_at_limit text NOT NULL DEFAULT 'alert' CHECK (action_at_limit IN ('alert', 'stop')),
    created_by      uuid NOT NULL REFERENCES users(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    archived_at     timestamptz
);

-- owner: quota
CREATE TABLE budget_alerts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    budget_id       uuid NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
    period_start    date NOT NULL,
    threshold       smallint NOT NULL,
    used_microusd   bigint NOT NULL,
    raised_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (budget_id, period_start, threshold)
);

-- ======================================================================== estimation
-- owner: estimation
CREATE TABLE estimator_models (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope           text NOT NULL CHECK (scope IN ('global', 'workspace', 'user')),
    scope_id        uuid,                                -- NULL for global
    version         int NOT NULL,
    params          jsonb NOT NULL,
    fitted_on_n     int NOT NULL,
    mape_permille   int,
    fitted_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope, scope_id, version)
);

-- owner: estimation
CREATE TABLE estimates (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    requested_by    uuid NOT NULL REFERENCES users(id),
    estimator_id    uuid NOT NULL REFERENCES estimator_models(id),
    request         jsonb NOT NULL,                      -- features + description hash/length; no description text
    features        jsonb NOT NULL,
    input_tokens_p10 bigint NOT NULL, input_tokens_p50 bigint NOT NULL, input_tokens_p90 bigint NOT NULL,
    cache_tokens_p10 bigint NOT NULL, cache_tokens_p50 bigint NOT NULL, cache_tokens_p90 bigint NOT NULL,
    output_tokens_p10 bigint NOT NULL, output_tokens_p50 bigint NOT NULL, output_tokens_p90 bigint NOT NULL,
    cost_list_p10_microusd bigint NOT NULL, cost_list_p50_microusd bigint NOT NULL, cost_list_p90_microusd bigint NOT NULL,
    cost_cli_p10_microusd bigint, cost_cli_p50_microusd bigint, cost_cli_p90_microusd bigint,
    calls_p10 int NOT NULL, calls_p50 int NOT NULL, calls_p90 int NOT NULL,
    duration_ms_p10 bigint, duration_ms_p50 bigint, duration_ms_p90 bigint,
    success_prob_permille smallint NOT NULL CHECK (success_prob_permille BETWEEN 0 AND 1000),
    evidence_n      int NOT NULL,
    provenance      provenance NOT NULL DEFAULT 'ESTIMATED' CHECK (provenance = 'ESTIMATED'),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- owner: estimation
CREATE TABLE estimate_evidence (
    estimate_id     uuid NOT NULL REFERENCES estimates(id) ON DELETE CASCADE,
    task_id         uuid NOT NULL REFERENCES usage_tasks(id) ON DELETE CASCADE,
    weight_permille smallint NOT NULL,
    distance_permille smallint NOT NULL,
    PRIMARY KEY (estimate_id, task_id)
);

-- owner: estimation
CREATE TABLE estimate_outcomes (
    estimate_id     uuid PRIMARY KEY REFERENCES estimates(id) ON DELETE CASCADE,
    task_id         uuid NOT NULL REFERENCES usage_tasks(id) ON DELETE CASCADE,
    actual_tokens   bigint NOT NULL,
    actual_cost_list_microusd bigint NOT NULL,
    actual_cost_cli_microusd  bigint,
    ape_tokens_permille int NOT NULL,
    ape_cost_permille   int NOT NULL,
    within_p10_p90  boolean NOT NULL,
    recorded_at     timestamptz NOT NULL DEFAULT now()
);

-- ======================================================================== advisor
-- owner: advisor
CREATE TABLE advisor_rules (
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    rule_id         text NOT NULL CHECK (rule_id IN ('R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7')),
    enabled         boolean NOT NULL DEFAULT true,
    params          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- threshold overrides; defaults in consulting.md
    PRIMARY KEY (workspace_id, rule_id)
);

-- owner: advisor
CREATE TABLE advisor_findings (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    rule_id         text NOT NULL,
    detector_version int NOT NULL,
    period_start    timestamptz NOT NULL,
    period_end      timestamptz NOT NULL,
    evidence_call_ids bigint[] NOT NULL DEFAULT '{}',
    evidence_task_ids uuid[] NOT NULL DEFAULT '{}',
    savings_p10_microusd bigint NOT NULL,
    savings_p50_microusd bigint NOT NULL,
    savings_p90_microusd bigint NOT NULL,
    savings_tokens_p50   bigint NOT NULL,
    measure         cost_measure NOT NULL,
    provenance      provenance NOT NULL DEFAULT 'ESTIMATED' CHECK (provenance = 'ESTIMATED'),
    detail          jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, rule_id, period_start, period_end)
);

-- owner: advisor
CREATE TABLE proposals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    origin          text NOT NULL CHECK (origin IN ('advisor', 'simulation', 'profile', 'run_node')),
    origin_ref      text NOT NULL,                       -- finding id, simulation id, ...
    kind            text NOT NULL CHECK (kind IN ('config_export', 'budget_change', 'router_tier', 'context_cap', 'template', 'repo_change')),
    change          jsonb NOT NULL,                      -- the exact change; applied only after decision
    expected_savings_microusd bigint,
    state           text NOT NULL DEFAULT 'proposed'
                    CHECK (state IN ('proposed', 'accepted', 'rejected', 'applied', 'expired', 'blocked')),
    blocked_reason  text,                                -- policy / budget refusal
    created_at      timestamptz NOT NULL DEFAULT now(),
    expires_at      timestamptz
);

-- owner: advisor
CREATE TABLE proposal_decisions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_id     uuid NOT NULL REFERENCES proposals(id) ON DELETE CASCADE,
    decided_by      uuid NOT NULL REFERENCES users(id),
    decision        text NOT NULL CHECK (decision IN ('accept', 'reject', 'apply')),
    policy_ok       boolean NOT NULL,
    budget_ok       boolean NOT NULL,
    note            text NOT NULL DEFAULT '',
    decided_at      timestamptz NOT NULL DEFAULT now()
);

-- ======================================================================== simulation
-- owner: simulation
CREATE TABLE simulations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    requested_by    uuid NOT NULL REFERENCES users(id),
    assumptions     jsonb NOT NULL CHECK (jsonb_typeof(assumptions) = 'array' AND jsonb_array_length(assumptions) > 0),
    basis           jsonb NOT NULL,                      -- {period, calls, tasks, price_version, stats_version}
    result          jsonb NOT NULL,                      -- ranges per metric, integers
    provenance      provenance NOT NULL DEFAULT 'SIMULATED' CHECK (provenance = 'SIMULATED'),
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ======================================================================== profile
-- owner: profile
CREATE TABLE profiles (
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    monthly_budget_microusd bigint,
    task_budget_microusd    bigint,
    quality_floor_permille  smallint CHECK (quality_floor_permille BETWEEN 0 AND 1000),
    preferred_models text[] NOT NULL DEFAULT '{}',
    preferred_providers text[] NOT NULL DEFAULT '{}',
    billing_mode    text CHECK (billing_mode IN ('subscription', 'api', 'mixed')),
    team_size       int,
    store_bodies    boolean NOT NULL DEFAULT false,      -- prompt/code bodies off by default
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, workspace_id)
);

-- owner: profile
CREATE TABLE personal_stats (
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    task_kind       text NOT NULL,
    model_id        text NOT NULL REFERENCES models(id),
    structure       text NOT NULL DEFAULT 'single',
    context_mode    text NOT NULL DEFAULT 'selective',
    tasks           int NOT NULL,
    correct         int NOT NULL,
    first_try_success int NOT NULL,
    tokens_per_correct bigint,
    cost_list_per_correct_nanousd bigint,
    cost_cli_per_correct_microusd bigint,
    version         int NOT NULL,
    updated_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, workspace_id, task_kind, model_id, structure, context_mode)
);

-- owner: profile
CREATE TABLE recommendations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    headline        text NOT NULL,                       -- "X 구성이 맞힌 작업당 Y% 싸다"
    current_config  jsonb NOT NULL,
    recommended_config jsonb NOT NULL,
    saving_permille int NOT NULL,
    evidence_n      int NOT NULL,
    stats_version   int NOT NULL,
    provenance      provenance NOT NULL DEFAULT 'ESTIMATED',
    proposal_id     uuid,                                -- advisor.proposals once the user asks to apply
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ======================================================================== report
-- owner: report
CREATE TABLE reports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    period_start    date NOT NULL,
    period_end      date NOT NULL,
    generated_by    uuid REFERENCES users(id),
    body            jsonb NOT NULL,                      -- numbers with provenance; no prompt bodies
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- ======================================================================== notification
-- owner: notification
CREATE TABLE notifications (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workspace_id    uuid REFERENCES workspaces(id) ON DELETE CASCADE,
    kind            text NOT NULL,
    ref             text,
    text            text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    read_at         timestamptz
);
CREATE INDEX notifications_unread ON notifications (user_id) WHERE read_at IS NULL;

-- owner: notification
CREATE TABLE notification_prefs (
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            text NOT NULL,
    channel         text NOT NULL CHECK (channel IN ('in_app', 'email', 'slack')),
    enabled         boolean NOT NULL DEFAULT true,
    PRIMARY KEY (user_id, kind, channel)
);

-- ======================================================================== audit
-- owner: audit
CREATE TABLE audit_log (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    at              timestamptz NOT NULL DEFAULT now(),
    workspace_id    uuid,
    actor_user_id   uuid,
    actor_kind      text NOT NULL CHECK (actor_kind IN ('user', 'system', 'worker', 'run_node')),
    action          text NOT NULL,                       -- e.g. proposal.apply, budget.update, credential.store
    target_kind     text NOT NULL,
    target_id       text NOT NULL,
    detail          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- never secrets
    request_id      text
);
CREATE INDEX audit_log_ws_at ON audit_log (workspace_id, at);

CREATE FUNCTION audit_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'audit_log is append-only';
END $$;
CREATE TRIGGER audit_log_no_update BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION audit_log_append_only();

-- ======================================================================== integration
-- owner: integration
CREATE TABLE integrations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    kind            text NOT NULL CHECK (kind IN ('github', 'slack', 'email')),
    config          jsonb NOT NULL DEFAULT '{}'::jsonb,  -- no secrets; secrets go to provider_credentials
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- owner: integration
CREATE TABLE provider_credentials (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    provider        text NOT NULL CHECK (provider IN ('anthropic', 'openai', 'gemini', 'github', 'slack')),
    ciphertext      bytea NOT NULL,                      -- AES-256-GCM(secret, DEK)
    nonce           bytea NOT NULL,
    wrapped_dek     bytea NOT NULL,                      -- DEK wrapped by the KEK named in kek_id (env/KMS)
    kek_id          text NOT NULL,
    fingerprint     text NOT NULL,                       -- HMAC of the secret, for duplicate detection
    last4           text NOT NULL,
    created_by      uuid NOT NULL REFERENCES users(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    revoked_at      timestamptz
);

-- ======================================================================== run (later)
-- owner: run
CREATE TABLE runs (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    project_id      uuid REFERENCES projects(id) ON DELETE SET NULL,
    started_by      uuid NOT NULL REFERENCES users(id),
    approved_proposal_id uuid,                           -- advisor.proposals: a run starts only after approval
    plan            jsonb NOT NULL,
    state           text NOT NULL CHECK (state IN ('queued', 'running', 'stopping', 'stopped', 'done', 'failed')),
    ga_version      text NOT NULL,
    started_at      timestamptz,
    ended_at        timestamptz
);

-- owner: run
CREATE TABLE run_nodes (
    run_id          uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    node_id         text NOT NULL,                       -- ga <role>_<n>
    role            text NOT NULL,
    started_at      timestamptz,
    retired_at      timestamptz,
    item_id         text,
    PRIMARY KEY (run_id, node_id)
);

-- owner: run
CREATE TABLE run_events (
    run_id          uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    seq             bigint NOT NULL,
    at              timestamptz NOT NULL,
    node_id         text,
    kind            text NOT NULL,                       -- node.started, turn, wait, node.retired, item.state
    data            jsonb NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (run_id, seq)
);

-- owner: run
CREATE TABLE run_messages (
    run_id          uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    msg_id          text NOT NULL,
    from_node       text NOT NULL,
    to_node         text NOT NULL,
    at              timestamptz,
    bytes           int NOT NULL,
    tokens_est      int NOT NULL,
    pi_weight_permille smallint,
    PRIMARY KEY (run_id, msg_id)
);

-- owner: run
CREATE TABLE run_verdicts (
    run_id          uuid NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    item_id         text NOT NULL,
    tests_passed    int NOT NULL,
    tests_failed    int NOT NULL,
    mutants_caught  int,
    mutants_total   int,
    preexisting_failures int NOT NULL DEFAULT 0,
    verdict         text NOT NULL CHECK (verdict IN ('pass', 'fail', 'partial')),
    PRIMARY KEY (run_id, item_id)
);

COMMIT;
