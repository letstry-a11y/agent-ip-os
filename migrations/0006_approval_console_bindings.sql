ALTER TABLE approval_requests
    ADD COLUMN state_version bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0);

-- Snapshot hashes are historical evidence. Keeping them as a foreign key to the account's
-- current fingerprint would prevent credential/account rotation and make invalidation
-- impossible to observe. Identity remains project-scoped; validity compares the old hash to
-- the current authoritative fingerprint at read/use time.
ALTER TABLE approval_snapshots
    DROP CONSTRAINT approval_snapshots_project_id_account_id_account_hash_fkey;

ALTER TABLE approval_snapshots
    ADD CONSTRAINT approval_snapshots_project_account_fkey
    FOREIGN KEY (project_id, account_id)
    REFERENCES platform_accounts(project_id, id) ON DELETE RESTRICT;

CREATE TABLE approval_request_bindings (
    approval_request_id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    candidate_id uuid NOT NULL,
    account_id uuid NOT NULL,
    candidate_hash bytea NOT NULL CHECK (octet_length(candidate_hash) = 32),
    fact_report_hash bytea NOT NULL CHECK (octet_length(fact_report_hash) = 32),
    rights_manifest_hash bytea NOT NULL CHECK (octet_length(rights_manifest_hash) = 32),
    risk_report_hash bytea NOT NULL CHECK (octet_length(risk_report_hash) = 32),
    policy_version text NOT NULL CHECK (btrim(policy_version) <> ''),
    account_hash bytea NOT NULL CHECK (octet_length(account_hash) = 32),
    requested_action text NOT NULL CHECK (btrim(requested_action) <> ''),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (project_id, approval_request_id),
    UNIQUE (project_id, approval_request_id, candidate_id),
    FOREIGN KEY (project_id, approval_request_id, candidate_id)
        REFERENCES approval_requests(project_id, id, candidate_id) ON DELETE RESTRICT,
    FOREIGN KEY (project_id, candidate_id, candidate_hash, policy_version, account_id)
        REFERENCES platform_candidates(project_id, id, candidate_hash, policy_version, account_id)
        ON DELETE RESTRICT,
    FOREIGN KEY (project_id, account_id)
        REFERENCES platform_accounts(project_id, id) ON DELETE RESTRICT
);

CREATE TRIGGER approval_request_bindings_immutable
    BEFORE UPDATE OR DELETE ON approval_request_bindings
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
