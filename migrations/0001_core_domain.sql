CREATE TABLE ip_projects (
    id uuid PRIMARY KEY,
    slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,62}$'),
    name text NOT NULL CHECK (btrim(name) <> ''),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE content_units (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    state text NOT NULL CHECK (
        state IN (
            'PLANNED', 'RESEARCHING', 'BRIEF_READY', 'DRAFTING', 'CREATIVE_QA',
            'ASSET_GENERATION', 'MEDIA_ASSEMBLY', 'PLATFORM_ADAPTATION',
            'CANDIDATES_ACTIVE', 'LEARNING', 'ARCHIVED', 'RETRY_WAIT', 'FAILED',
            'QUARANTINED', 'CANCELLED'
        )
    ),
    state_version bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    current_content_version integer NOT NULL DEFAULT 0 CHECK (current_content_version >= 0),
    trace_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id)
);

CREATE TABLE content_versions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    content_unit_id uuid NOT NULL,
    version integer NOT NULL CHECK (version > 0),
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    content_hash bytea NOT NULL CHECK (octet_length(content_hash) = 32),
    created_by_subject_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, content_unit_id, version),
    FOREIGN KEY (project_id, content_unit_id)
        REFERENCES content_units(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE artifacts (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    content_unit_id uuid,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    object_key text NOT NULL CHECK (btrim(object_key) <> ''),
    object_version text NOT NULL CHECK (btrim(object_version) <> ''),
    media_type text NOT NULL CHECK (btrim(media_type) <> ''),
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    sha256_digest bytea NOT NULL CHECK (octet_length(sha256_digest) = 32),
    rights_status text NOT NULL CHECK (
        rights_status IN ('PENDING', 'APPROVED', 'REVOKED', 'EXPIRED', 'REJECTED')
    ),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, object_key, object_version),
    UNIQUE (project_id, id, sha256_digest),
    FOREIGN KEY (project_id, content_unit_id)
        REFERENCES content_units(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE consent_grants (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    subject_id uuid NOT NULL,
    status text NOT NULL CHECK (status IN ('ACTIVE', 'REVOKED', 'EXPIRED', 'SUPERSEDED')),
    purpose text NOT NULL CHECK (btrim(purpose) <> ''),
    platforms text[] NOT NULL CHECK (cardinality(platforms) > 0),
    territory text NOT NULL CHECK (btrim(territory) <> ''),
    provider text NOT NULL CHECK (btrim(provider) <> ''),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz NOT NULL,
    derivative_rights boolean NOT NULL DEFAULT false,
    commercial_use boolean NOT NULL DEFAULT false,
    sublicensing boolean NOT NULL DEFAULT false,
    evidence_artifact_id uuid NOT NULL,
    revoked_at timestamptz,
    revocation_reason text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    CHECK (valid_until > valid_from),
    CHECK ((status = 'REVOKED') = (revoked_at IS NOT NULL)),
    CHECK (revocation_reason IS NULL OR btrim(revocation_reason) <> ''),
    FOREIGN KEY (project_id, evidence_artifact_id)
        REFERENCES artifacts(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE asset_rights (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    artifact_id uuid NOT NULL,
    consent_grant_id uuid,
    status text NOT NULL CHECK (
        status IN ('PENDING', 'APPROVED', 'REVOKED', 'EXPIRED', 'REJECTED')
    ),
    rights_type text NOT NULL CHECK (btrim(rights_type) <> ''),
    scope jsonb NOT NULL CHECK (jsonb_typeof(scope) = 'object'),
    valid_from timestamptz NOT NULL,
    valid_until timestamptz NOT NULL,
    evidence_artifact_id uuid NOT NULL,
    revoked_at timestamptz,
    revocation_reason text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, artifact_id, id),
    CHECK (valid_until > valid_from),
    CHECK ((status = 'REVOKED') = (revoked_at IS NOT NULL)),
    CHECK (revocation_reason IS NULL OR btrim(revocation_reason) <> ''),
    FOREIGN KEY (project_id, artifact_id)
        REFERENCES artifacts(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, consent_grant_id)
        REFERENCES consent_grants(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, evidence_artifact_id)
        REFERENCES artifacts(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE platform_accounts (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    platform text NOT NULL CHECK (btrim(platform) <> ''),
    environment text NOT NULL CHECK (environment IN ('MOCK', 'TEST', 'PACKAGE', 'PRODUCTION')),
    status text NOT NULL CHECK (status IN ('UNCONFIGURED', 'ACTIVE', 'PAUSED', 'REVOKED')),
    capabilities_version text NOT NULL CHECK (btrim(capabilities_version) <> ''),
    account_fingerprint bytea NOT NULL CHECK (octet_length(account_fingerprint) = 32),
    credential_reference text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, id, platform),
    UNIQUE (project_id, id, account_fingerprint),
    CHECK (credential_reference IS NULL OR btrim(credential_reference) <> '')
);

CREATE TABLE platform_candidates (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    content_unit_id uuid NOT NULL,
    account_id uuid NOT NULL,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    platform text NOT NULL CHECK (btrim(platform) <> ''),
    title text NOT NULL CHECK (btrim(title) <> ''),
    caption text NOT NULL,
    normalized_tags text[] NOT NULL,
    ai_disclosure text NOT NULL CHECK (btrim(ai_disclosure) <> ''),
    scheduled_at timestamptz,
    schedule_time_zone text,
    policy_version text NOT NULL CHECK (btrim(policy_version) <> ''),
    canonical_payload jsonb NOT NULL CHECK (jsonb_typeof(canonical_payload) = 'object'),
    candidate_hash bytea NOT NULL CHECK (octet_length(candidate_hash) = 32),
    supersedes_candidate_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, candidate_hash),
    UNIQUE (project_id, id, candidate_hash, policy_version, account_id),
    CHECK ((scheduled_at IS NULL) = (schedule_time_zone IS NULL)),
    CHECK (schedule_time_zone IS NULL OR btrim(schedule_time_zone) <> ''),
    FOREIGN KEY (project_id, content_unit_id)
        REFERENCES content_units(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, account_id, platform)
        REFERENCES platform_accounts(project_id, id, platform) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, supersedes_candidate_id)
        REFERENCES platform_candidates(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE platform_candidate_states (
    candidate_id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    state text NOT NULL CHECK (
        state IN (
            'CANDIDATE_FROZEN', 'FACT_CHECK', 'RIGHTS_CHECK', 'COMPLIANCE_CHECK',
            'RISK_ROUTING', 'WAITING_APPROVAL', 'APPROVED', 'REVISION_REQUESTED',
            'REJECTED', 'APPROVAL_EXPIRED', 'SUPERSEDED', 'READY_TO_INTENT',
            'SCHEDULED', 'PUBLISHING', 'PUBLISHED', 'RECONCILIATION_REQUIRED',
            'PUBLISH_FAILED', 'PACKAGE_READY', 'PACKAGE_DELIVERED',
            'MANUAL_RECONCILIATION', 'CLOSED_UNPUBLISHED', 'MONITORING',
            'QUARANTINED', 'TAKEDOWN_PENDING', 'REMOVED', 'TAKEDOWN_FAILED', 'APPEALED'
        )
    ),
    state_version bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, candidate_id),
    FOREIGN KEY (project_id, candidate_id)
        REFERENCES platform_candidates(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE candidate_artifacts (
    project_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    position integer NOT NULL CHECK (position >= 0),
    artifact_id uuid NOT NULL,
    artifact_hash bytea NOT NULL CHECK (octet_length(artifact_hash) = 32),
    PRIMARY KEY (project_id, candidate_id, position),
    UNIQUE (project_id, candidate_id, artifact_id),
    FOREIGN KEY (project_id, candidate_id)
        REFERENCES platform_candidates(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, artifact_id, artifact_hash)
        REFERENCES artifacts(project_id, id, sha256_digest) ON DELETE RESTRICT
);

CREATE TABLE approval_requests (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    risk_level text NOT NULL CHECK (risk_level IN ('R0', 'R1', 'R2', 'R3', 'R4')),
    requested_action text NOT NULL CHECK (btrim(requested_action) <> ''),
    required_approvals smallint NOT NULL CHECK (required_approvals BETWEEN 1 AND 2),
    status text NOT NULL CHECK (
        status IN ('PENDING', 'APPROVED', 'REJECTED', 'REVISION_REQUESTED', 'EXPIRED', 'CANCELLED')
    ),
    requested_by_subject_id uuid NOT NULL,
    expires_at timestamptz NOT NULL,
    resolved_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, id, candidate_id),
    CHECK ((status = 'PENDING') = (resolved_at IS NULL)),
    CHECK (expires_at > created_at),
    FOREIGN KEY (project_id, candidate_id)
        REFERENCES platform_candidates(project_id, id) ON DELETE RESTRICT
);

CREATE TABLE approval_snapshots (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    approval_request_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    account_id uuid NOT NULL,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    decision text NOT NULL CHECK (decision IN ('APPROVED', 'REJECTED', 'REVISION_REQUESTED')),
    candidate_hash bytea NOT NULL CHECK (octet_length(candidate_hash) = 32),
    fact_report_hash bytea NOT NULL CHECK (octet_length(fact_report_hash) = 32),
    rights_manifest_hash bytea NOT NULL CHECK (octet_length(rights_manifest_hash) = 32),
    risk_report_hash bytea NOT NULL CHECK (octet_length(risk_report_hash) = 32),
    policy_version text NOT NULL CHECK (btrim(policy_version) <> ''),
    account_hash bytea NOT NULL CHECK (octet_length(account_hash) = 32),
    approved_action text NOT NULL CHECK (btrim(approved_action) <> ''),
    approver_subject_ids uuid[] NOT NULL CHECK (cardinality(approver_subject_ids) BETWEEN 1 AND 2),
    expires_at timestamptz NOT NULL,
    decided_at timestamptz NOT NULL,
    snapshot_hash bytea NOT NULL CHECK (octet_length(snapshot_hash) = 32),
    UNIQUE (project_id, id),
    UNIQUE (project_id, approval_request_id),
    UNIQUE (project_id, id, candidate_id, account_id),
    CHECK (expires_at > decided_at),
    FOREIGN KEY (project_id, approval_request_id, candidate_id)
        REFERENCES approval_requests(project_id, id, candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, candidate_id, candidate_hash, policy_version, account_id)
        REFERENCES platform_candidates(project_id, id, candidate_hash, policy_version, account_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (project_id, account_id, account_hash)
        REFERENCES platform_accounts(project_id, id, account_fingerprint) ON DELETE RESTRICT
);

CREATE TABLE outbox_messages (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    publish_intent_id uuid NOT NULL,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    topic text NOT NULL CHECK (btrim(topic) <> ''),
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    occurred_at timestamptz NOT NULL,
    available_at timestamptz NOT NULL,
    claimed_at timestamptz,
    delivered_at timestamptz,
    attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error text,
    UNIQUE (project_id, id),
    UNIQUE (project_id, publish_intent_id),
    CHECK (available_at >= occurred_at),
    CHECK (last_error IS NULL OR btrim(last_error) <> '')
);

CREATE TABLE publish_intents (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    candidate_id uuid NOT NULL,
    approval_snapshot_id uuid NOT NULL,
    account_id uuid NOT NULL,
    outbox_message_id uuid NOT NULL,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    request_fingerprint bytea NOT NULL CHECK (octet_length(request_fingerprint) = 32),
    normalized_schedule_slot timestamptz NOT NULL,
    repost_of_intent_id uuid,
    repost_reason text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, id),
    UNIQUE (project_id, request_fingerprint),
    UNIQUE (project_id, outbox_message_id),
    CHECK ((repost_of_intent_id IS NULL) = (repost_reason IS NULL)),
    CHECK (repost_reason IS NULL OR btrim(repost_reason) <> ''),
    FOREIGN KEY (project_id, candidate_id)
        REFERENCES platform_candidates(project_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, approval_snapshot_id, candidate_id, account_id)
        REFERENCES approval_snapshots(project_id, id, candidate_id, account_id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, repost_of_intent_id)
        REFERENCES publish_intents(project_id, id) ON DELETE RESTRICT
);

ALTER TABLE outbox_messages
    ADD CONSTRAINT outbox_publish_intent_fk
    FOREIGN KEY (project_id, publish_intent_id)
    REFERENCES publish_intents(project_id, id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

ALTER TABLE publish_intents
    ADD CONSTRAINT publish_intent_outbox_fk
    FOREIGN KEY (project_id, outbox_message_id)
    REFERENCES outbox_messages(project_id, id)
    ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED;

CREATE TABLE audit_events (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES ip_projects(id) ON DELETE RESTRICT,
    schema_version smallint NOT NULL DEFAULT 1 CHECK (schema_version = 1),
    actor_type text NOT NULL CHECK (actor_type IN ('HUMAN', 'SERVICE', 'AGENT')),
    actor_id uuid NOT NULL,
    action text NOT NULL CHECK (btrim(action) <> ''),
    resource_type text NOT NULL CHECK (btrim(resource_type) <> ''),
    resource_id uuid,
    trace_id uuid NOT NULL,
    payload jsonb NOT NULL CHECK (jsonb_typeof(payload) = 'object'),
    previous_event_hash bytea CHECK (
        previous_event_hash IS NULL OR octet_length(previous_event_hash) = 32
    ),
    event_hash bytea NOT NULL CHECK (octet_length(event_hash) = 32),
    occurred_at timestamptz NOT NULL,
    UNIQUE (project_id, id),
    UNIQUE (project_id, event_hash),
    FOREIGN KEY (project_id, previous_event_hash)
        REFERENCES audit_events(project_id, event_hash)
        ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED
);

CREATE UNIQUE INDEX audit_events_one_genesis_per_project
    ON audit_events(project_id)
    WHERE previous_event_hash IS NULL;

CREATE UNIQUE INDEX audit_events_no_chain_fork
    ON audit_events(project_id, previous_event_hash)
    WHERE previous_event_hash IS NOT NULL;

CREATE INDEX content_units_project_state_idx ON content_units(project_id, state);
CREATE INDEX artifacts_project_content_idx ON artifacts(project_id, content_unit_id);
CREATE INDEX approval_requests_project_status_idx ON approval_requests(project_id, status);
CREATE INDEX outbox_messages_dispatch_idx
    ON outbox_messages(available_at, occurred_at)
    WHERE delivered_at IS NULL;
