# ADR-0001: deterministic durable workflows own progression

- Status: Accepted
- Date: 2026-08-19
- Source authority: approved technical baseline V1.1

## Context

Content work spans hours/days, human approval, retries, cancellation, scheduled release, platform uncertainty, and restart recovery. A model conversation is probabilistic and cannot reliably own timers, concurrency, durable waits, idempotency, or transactional state.

## Decision

Use Temporal as the durable workflow mechanism and deterministic application code as the transition authority. Agents are invoked as bounded activities/tools that return versioned structured outputs. PostgreSQL stores transactional domain records; Temporal history coordinates progress but is not the only representation of business evidence.

Platform candidates use independent child lifecycles. Side effects require transactional intent/outbox creation plus worker lease revalidation.

## Consequences

- Positive: restart recovery, explicit retry/cancel/wait behavior, testable state transitions, and human signals.
- Cost: Temporal is an additional local/production dependency and workflows require determinism/versioning discipline.
- Constraint: model conversation IDs may be metadata, never the only durable business reference.
- Verification: M1-02 must demonstrate restart recovery; M1-04 must demonstrate stop/idempotency races.

## Rejected alternatives

- Agent-to-Agent chat as the core state machine: nondeterministic, weak recovery and authorization semantics.
- Ad-hoc cron plus background tasks: insufficient durable wait/replay and concurrency evidence for approval/publishing.
