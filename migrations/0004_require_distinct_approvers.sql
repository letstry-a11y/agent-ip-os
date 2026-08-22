ALTER TABLE approval_snapshots
    ADD CONSTRAINT approval_snapshots_distinct_approvers
    CHECK (
        cardinality(approver_subject_ids) = 1
        OR approver_subject_ids[1] <> approver_subject_ids[2]
    );
