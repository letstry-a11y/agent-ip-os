# ADR-0003: official authorized API or publish-package fallback

- Status: Accepted
- Date: 2026-08-19
- Source authority: approved technical and execution baselines

## Context

Platform publishing capabilities depend on developer qualification, exact Scope, OAuth/account authorization, review, and changing official policy. Browser/Cookie automation is fragile, exposes accounts, and may violate rules. External approval time is not controllable by the software schedule.

## Decision

Production/test publishing integration may use only documented official APIs/capabilities for an explicitly allowlisted test account and granted Scope. If G2 is absent or insufficient, select M5B: generate complete platform packages, Mock contract/error samples, and honest manual post/metric reconciliation.

No Cookie storage, simulated browser publishing, undocumented endpoint, CAPTCHA bypass, or region/platform-rule circumvention is permitted. “Package ready” is not “published.”

## Consequences

- Positive: truthful delivery, reduced credential/account risk, and schedule continues despite external review.
- Cost: manual final action and metric evidence may remain; full automation is conditional.
- Constraint: capabilities are declared per adapter/account and never assumed universal.
- Verification: M1-07/M5-00 record Scope evidence; M5A demonstrates revocation and reconciliation or M5B demonstrates package/manual evidence.

## Rejected alternatives

- Browser automation as a deadline workaround: unsupported, brittle, and outside the approved safety boundary.
- Pretending a Mock success is platform success: destroys acceptance and audit integrity.
