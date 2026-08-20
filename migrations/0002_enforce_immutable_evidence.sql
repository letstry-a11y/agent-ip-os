CREATE FUNCTION reject_immutable_row_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only; % is forbidden', TG_TABLE_NAME, TG_OP
        USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER content_versions_immutable
    BEFORE UPDATE OR DELETE ON content_versions
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

CREATE TRIGGER artifacts_immutable
    BEFORE UPDATE OR DELETE ON artifacts
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

CREATE TRIGGER platform_candidates_immutable
    BEFORE UPDATE OR DELETE ON platform_candidates
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

CREATE TRIGGER candidate_artifacts_immutable
    BEFORE UPDATE OR DELETE ON candidate_artifacts
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

CREATE TRIGGER approval_snapshots_immutable
    BEFORE UPDATE OR DELETE ON approval_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

CREATE TRIGGER publish_intents_immutable
    BEFORE UPDATE OR DELETE ON publish_intents
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();

CREATE TRIGGER audit_events_immutable
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION reject_immutable_row_mutation();
