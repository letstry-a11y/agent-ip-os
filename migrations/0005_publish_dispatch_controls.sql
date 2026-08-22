CREATE TABLE publish_stop_controls (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    scope text NOT NULL CHECK (scope IN ('GLOBAL', 'ACCOUNT')),
    account_id uuid,
    stopped boolean NOT NULL,
    reason text,
    state_version bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    updated_by_subject_id uuid NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    CHECK (
        (scope = 'GLOBAL' AND account_id IS NULL)
        OR (scope = 'ACCOUNT' AND account_id IS NOT NULL)
    ),
    CHECK (
        (stopped AND reason IS NOT NULL AND btrim(reason) <> '')
        OR (NOT stopped AND reason IS NULL)
    ),
    FOREIGN KEY (project_id, account_id)
        REFERENCES platform_accounts(project_id, id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX publish_stop_one_global_per_project
    ON publish_stop_controls(project_id)
    WHERE scope = 'GLOBAL';

CREATE UNIQUE INDEX publish_stop_one_per_account
    ON publish_stop_controls(project_id, account_id)
    WHERE scope = 'ACCOUNT';

CREATE INDEX publish_stop_active_gate_idx
    ON publish_stop_controls(project_id, account_id)
    WHERE stopped;

CREATE TABLE publish_jobs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    publish_intent_id uuid NOT NULL,
    outbox_message_id uuid NOT NULL,
    account_id uuid NOT NULL,
    state text NOT NULL CHECK (
        state IN (
            'READY', 'LEASED', 'SUCCEEDED', 'RECONCILIATION_REQUIRED',
            'FAILED', 'STOPPED'
        )
    ),
    lease_token uuid,
    lease_owner_id uuid,
    lease_acquired_at timestamptz,
    lease_expires_at timestamptz,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, publish_intent_id),
    UNIQUE (project_id, outbox_message_id),
    CHECK (
        (state = 'LEASED') = (
            lease_token IS NOT NULL
            AND lease_owner_id IS NOT NULL
            AND lease_acquired_at IS NOT NULL
            AND lease_expires_at IS NOT NULL
        )
    ),
    CHECK (
        lease_expires_at IS NULL
        OR lease_expires_at > lease_acquired_at
    ),
    CHECK (last_error IS NULL OR btrim(last_error) <> ''),
    FOREIGN KEY (project_id, publish_intent_id)
        REFERENCES publish_intents(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, outbox_message_id)
        REFERENCES outbox_messages(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, account_id)
        REFERENCES platform_accounts(project_id, id) ON DELETE RESTRICT
);

CREATE INDEX publish_jobs_dispatch_idx
    ON publish_jobs(project_id, state, lease_expires_at, created_at);

CREATE TABLE publish_attempts (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    publish_job_id uuid NOT NULL,
    publish_intent_id uuid NOT NULL,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    lease_token uuid NOT NULL,
    outcome text NOT NULL CHECK (
        outcome IN ('STARTED', 'SUCCEEDED', 'KNOWN_FAILED', 'UNKNOWN', 'BLOCKED_STOP')
    ),
    request_fingerprint bytea NOT NULL CHECK (octet_length(request_fingerprint) = 32),
    response_hash bytea CHECK (
        response_hash IS NULL OR octet_length(response_hash) = 32
    ),
    error_class text,
    started_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamptz,
    UNIQUE (project_id, id),
    UNIQUE (project_id, publish_job_id, attempt_number),
    CHECK ((outcome = 'STARTED') = (finished_at IS NULL)),
    CHECK (error_class IS NULL OR btrim(error_class) <> ''),
    CHECK (finished_at IS NULL OR finished_at >= started_at),
    FOREIGN KEY (project_id, publish_job_id)
        REFERENCES publish_jobs(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, publish_intent_id)
        REFERENCES publish_intents(project_id, id) ON DELETE RESTRICT
);

INSERT INTO publish_jobs (
    id, project_id, publish_intent_id, outbox_message_id, account_id, state, created_at, updated_at
)
SELECT
    i.id, i.project_id, i.id, i.outbox_message_id, i.account_id,
    CASE
        WHEN o.delivered_at IS NOT NULL THEN 'SUCCEEDED'
        ELSE 'READY'
    END,
    i.created_at,
    CURRENT_TIMESTAMP
FROM publish_intents i
JOIN outbox_messages o
  ON o.project_id = i.project_id AND o.id = i.outbox_message_id;
