# M2-01 Provider interfaces and primary Mock acceptance

- Result: **PASS**
- Scope: four Provider interfaces, versioned contracts, and deterministic primary Mock
- Branch: `feature/m2-01-provider-interfaces`
- External effects: none

## Delivered behavior

- `ProviderRequestV1`, `ProviderJobV1`, usage, provenance, rate-limit, and failure schemas cover
  request, asynchronous status, cancellation, cost, provenance, error taxonomy, and limits.
- Text, image, video, and audio Protocols share one portable lifecycle.
- Four primary Mock implementations provide deterministic, network-free, zero-cost structured
  results and artifact metadata.
- Exact request replay is idempotent; changed input under the same request ID fails closed.
- Cancellation and terminal polling are idempotent; unknown jobs and cross-kind requests fail.
- Success/failure/non-terminal evidence and rate-limit contradictions are rejected by strict,
  immutable Pydantic boundaries.

## Verification

- Focused Provider contract tests: **8 passed**.
- Strict mypy for Agent runtime and data models: **passed, 8 source files**.
- Canonical `npm run check`: **81 tests passed**, with **100% measured statement/branch
  coverage**; repository integrity/secret/migration/link checks, Ruff format/lint, strict mypy
  across 23 source files, Prettier, ESLint, TypeScript, and **8 Vitest tests** passed.
- `npm run build`: **passed**; the Next.js production build compiled and generated all routes.

## Safety evidence

Tests replace Python's network connection entry point with a fail-closed guard. All four Provider
Mocks still complete. No Provider SDK, URL, key name, account identifier, media bytes, paid call,
or external request is present. Returned provenance is explicitly marked `synthetic=true`, and
the acceptance record does not claim a real Provider integration.
