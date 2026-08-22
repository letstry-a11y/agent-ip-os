# M1-05 deterministic Mock boundary evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **PASS / ACCEPTED**
- Safety boundary: synthetic, non-identifying fixtures with no Provider, platform, network,
  asset bytes, credentials, portrait, or voice input

## Implemented

- Versioned strict request, result, and integer cost schemas for Agent, media, and platform
  Mock boundaries.
- Deterministic Agent proposal, synthetic media metadata, and synthetic platform result
  adapters. Equal requests produce equal output, hash, usage, and cost.
- Typed invalid-schema, timeout, transient failure, permanent failure, cancellation, and
  platform lost-response behavior.
- Platform lost response is non-retryable, records that the request may have been accepted,
  and requires reconciliation. Agent/media reject that platform-only scenario.
- The existing Mock publish Activity now passes through the validated Mock platform adapter.

## Local verification

1. The focused Mock plus workflow-Activity suite passed all 16 tests.
2. New Mock schemas, adapters, and the updated Activity module reached 100% statement and
   branch coverage in the focused run.
3. The complete unit and isolated PostgreSQL integration set passed all 50 tests using a
   fresh operating-system temporary directory.
4. Ruff format, Ruff lint, and strict mypy passed for the full Python source tree.
5. Repository integrity checks passed with migrations, baseline hashes, links, and secret
   patterns verified.
6. Web formatting, ESLint, TypeScript, five Vitest tests, and the Next.js production build
   passed.
7. [PR #8 hosted CI](https://github.com/letstry-a11y/agent-ip-os/actions/runs/32571682107)
   passed the complete Linux quality gate in 1 minute 51 seconds, including the persistent
   Temporal restart, full unit/workflow/PostgreSQL integration set, 100% workspace coverage,
   repository and web checks, Compose validation, and the production build.

The persistent Temporal restart test was stopped after the known Windows development-server
startup wait reproduced. It changes no M1-05 behavior; the required scenario passed in the
hosted Linux CI evidence above.

## Human acceptance

On 2026-08-22 the founder confirmed that timeout/failure injection should remain immediate
and deterministic rather than sleeping, integer USD microunits are adequate for Mock-only
cost evidence, and `LOST_RESPONSE` must remain platform-only, non-retryable, and
reconciliation-required.

Acceptance does not authorize a real Provider, media generation, portrait processing,
platform login, or publication.
