# Six Agent runtime contracts v1

- Status: accepted for M2-03
- Scope: six combined logical units; no independently deployed Agent processes
- Configuration: [`runtime-units-v1.json`](../../config/agents/runtime-units-v1.json)
- Safety boundary: proposal-only, local Mock Providers, zero external side effects
- Baseline: [technical plan](../baseline/AI超级IP全Agent公司技术方案_v1.md) and
  [MVP PRD](../product/prd-mvp.md)

## Fixed unit set

The only MVP unit identities are planning/research, creation, media production, final
verification, platform candidate/package, and basic analytics. The versioned contract set must
contain each identity exactly once; adding a seventh unit or omitting one fails validation.

Each strict contract declares purpose, versioned input/output schema names, portable model tier,
tool allowlist, read/write scopes, forbidden actions, maximum tool calls, integer cost limit,
timeout, bounded retry policy, escalation conditions, and prompt version. Configuration is loaded
as UTF-8 JSON without environment interpolation or secret expansion.

## Global safety invariants

Every unit must explicitly forbid `publish`, `pay`, `sign_contract`, `delete_protected`, and
`read_secret`. Lists reject duplicates. Retries are limited to at most three attempts and may name
only `RATE_LIMIT`, `TIMEOUT`, or `TRANSIENT`; authorization, policy, invalid output, cancellation,
and internal failures cannot be silently retried.

The current G1 fallback sets every unit's Provider cost allowance to zero. Platform work can write
candidate/package proposals but cannot call a publishing action. Final verification escalates on
missing consent, unknown facts, R3/R4 risk, or policy conflicts. Media production accepts only
approved synthetic assets while D-003 remains blocked.

M2-03 defines contracts and validation, not the M2-04 execution gateway. Tool authorization,
run envelopes, trace persistence, retry execution, cancellation propagation, and state-advance
guards remain M2-04 work and must enforce these declarations server-side.
