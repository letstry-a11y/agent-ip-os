# Human decision register

This file records product, legal, account, budget, and external-authorization decisions that Codex must not make. Accepted technical architecture decisions live in `docs/adr/`.

Status values: `OPEN`, `DECIDED`, `DEFERRED`, `BLOCKED`. An open decision uses the documented safe fallback and does not silently stop Mock/local work.

| ID | Gate | Decision required | Needed by | Safe fallback while open | Status | Owner / evidence |
|---|---|---|---|---|---|---|
| D-001 | G0 project boundary | Confirm first target platform: Douyin or Bilibili. | Before M1-07 platform qualification probe; hard gate before M5 branch | Generate platform-neutral core plus complete publish packages; perform no real upload. | OPEN | Founder |
| D-002 | G0 project boundary | Confirm first two content columns and whether the source-content MVP remains image/text plus one 30-second vertical video. | Before M3-01 | Use synthetic fixtures and generic column identifiers only. | OPEN | Creative founder |
| D-003 | G0 rights boundary | Decide whether any real portrait, voice, voice clone, or AI avatar material may enter the MVP, with written purpose/platform/term/provider/derivative/revocation scope. | Before M3-06 | Use synthetic, non-identifying test assets; keep real face/voice storage disabled. | OPEN | Rights holder + founders |
| D-004 | G1 deployment | Identify deployment主体 and actual service region. | End of week 1 / before M2-00 | Run locally with Mock Providers; no region-sensitive external service. | OPEN | Founders |
| D-005 | G1 Provider | Approve legally usable text, image, video, and audio Provider candidates for that deployment region. | Before M2-00 | Choose M2B and implement two behavioral Mock/contract Providers only. | OPEN | Founders, with terms/privacy evidence |
| D-006 | G1 budget | Set monthly infrastructure/model/media budget and per-content video-generation ceiling. | Before any paid Provider or cloud task | Paid calls disabled; local Mock-only. | OPEN | Founders |
| D-007 | G2 platform qualification | Record whether the chosen platform supplied a test account, app, OAuth callback domain, exact Scope, and API approval. | End of week 2 / before M5-00 | Choose M5B publish-package + manual reconciliation. | OPEN | Platform account holder |
| D-008 | T3 governance | Register two distinct human approvers with MFA and confirm the initiator cannot self-approve. | Before enabling any T3 production action | Keep every T3 production action disabled. | OPEN | Both founders |
| D-009 | Repository operations | Decide whether to create a private remote repository and branch protection. | After local M0 acceptance | Keep local Git only; do not transmit repository content. | OPEN | Founder |
| D-010 | M0 acceptance | Review PRD, lifecycle specification, system context, data model, and ADRs; accept or request changes. | Before M0-04 is treated as downstream implementation | Specifications stay `ready for review`; no application setup is claimed complete. | OPEN | Founder |

## Decision record template

When a decision is made, update its row and append an entry:

```text
### D-___ — title
- Status: DECIDED
- Date: YYYY-MM-DD
- Decision makers:
- Decision:
- Evidence / authorization reference:
- Effective scope and expiry:
- Impacted Backlog / specifications:
```
