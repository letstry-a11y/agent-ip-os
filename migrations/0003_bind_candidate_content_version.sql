ALTER TABLE content_versions
    ADD CONSTRAINT content_versions_candidate_binding_key
    UNIQUE (project_id, id, content_unit_id);

ALTER TABLE platform_candidates
    ADD COLUMN content_version_id uuid;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM platform_candidates) THEN
        RAISE EXCEPTION
            'cannot infer immutable content_version_id for existing platform candidates'
            USING ERRCODE = '55000';
    END IF;
END;
$$;

ALTER TABLE platform_candidates
    ALTER COLUMN content_version_id SET NOT NULL,
    ADD CONSTRAINT platform_candidate_content_version_fk
    FOREIGN KEY (project_id, content_version_id, content_unit_id)
    REFERENCES content_versions(project_id, id, content_unit_id)
    ON DELETE RESTRICT;
