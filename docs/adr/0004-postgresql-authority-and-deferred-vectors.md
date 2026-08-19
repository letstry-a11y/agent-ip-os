# ADR-0004: PostgreSQL is authoritative; vectors are deferred

- Status: Accepted
- Date: 2026-08-19
- Source authority: approved technical and execution baselines

## Context

Rights, consent, approval, budget, stop state, policy version, platform account, and publish result require transactional, queryable truth. Vector retrieval is useful for semantic memory but approximate retrieval cannot prove authorization or state. The MVP does not need vector search to prove its vertical slice.

## Decision

Use PostgreSQL for transactional domain truth and outbox/audit metadata; object storage holds large immutable/versioned artifacts and evidence bytes. Keep an `EmbeddingProvider` interface for later work but do not implement vector retrieval in the MVP critical path. Redis, if later introduced, is cache/rate-limit/lock support only.

Authorization and release checks query authoritative relational records, never prompts, vector hits, filenames, or caches.

## Consequences

- Positive: simpler MVP, strong constraints/transactions, explicit evidence and revocation queries.
- Cost: semantic discovery is limited initially; later vector indexing needs provenance and deletion synchronization.
- Constraint: no module may treat vector/index/cache state as proof of rights, approval, budget, or publication.
- Verification: M1 migrations encode relational constraints; M3 rights closure and M4 approval/outbox read authoritative records.

## Rejected alternatives

- Vector database as universal memory: approximate and unsuitable for legal/transactional truth.
- Redis as workflow/business truth: persistence and consistency semantics do not meet the stated requirements.
