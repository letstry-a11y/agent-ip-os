# M2B-01 and M2-03 Mock switching / Agent contract acceptance

- Result: **PASS**
- Branch: `feature/m2b-01-agent-contracts`
- G1 path: **M2B explicit safe fallback**
- External effects: none

## Delivered behavior

- A second text/image/video/audio Mock uses two-poll completion, alternate valid output shapes,
  and typed rate-limit/transient/invalid-output samples.
- Explicit Provider routing switches primary/secondary implementations without changing the
  request/job contract; duplicate or unknown registrations fail closed.
- One versioned JSON set defines exactly six MVP runtime units and every required tool, scope,
  forbidden action, budget, timeout, retry, escalation, schema, and prompt field.
- Contract validation rejects duplicate/missing units, duplicate declarations, missing global
  forbidden actions, unsafe retry codes, unknown fields, and contradictory limits.
- All configured cost limits are zero; no real Provider, account, SDK, URL, credential, or paid
  capability is claimed.

## Verification

- Focused M2B/M2-03 tests: **14 passed**.
- Strict mypy across Agent runtime and data models: **10 source files passed**.
- Canonical `npm run check`: **95 tests passed** with **100% measured statement/branch
  coverage**; repository integrity/secret/migration/link checks, Ruff format/lint, strict mypy
  across **25 source files**, Prettier, ESLint, TypeScript, and **8 Vitest tests** passed.
- `npm run build`: **passed**; the Next.js production build compiled and generated every route.

## Decision evidence

Deployment region, legally approved Provider candidates, and paid budget remain unapproved under
D-004 through D-006. The founder's unattended-work instruction explicitly limits work to local
Mock and safe engineering. Per the recorded G1 fallback, M2B is therefore selected for this MVP
iteration; it can later be superseded by dated M2A evidence without changing business semantics.
