# Human decision register

This file records product, legal, account, budget, and external-authorization decisions that Codex must not make. Accepted technical architecture decisions live in `docs/adr/`.

Status values: `OPEN`, `DECIDED`, `DEFERRED`, `BLOCKED`. An open decision uses the documented safe fallback and does not silently stop Mock/local work.

| ID | Gate | Decision required | Needed by | Safe fallback while open | Status | Owner / evidence |
|---|---|---|---|---|---|---|
| D-001 | G0 project boundary | Confirm the first content platform and its technical delivery branch. | Before M1-07 platform qualification probe; hard gate before M5 branch | Generate platform-neutral core plus complete publish packages; perform no real upload. | DECIDED | Xiaohongshu is the first content platform; package/manual publishing is the default until official generic note-publishing Scope is evidenced. |
| D-002 | G0 project boundary | Confirm the launch column and whether/when to add a second column; keep the source-content MVP within image/text plus one 30-second vertical video. | Before M3-01 | Use synthetic fixtures; do not introduce an unapproved second public column. | DECIDED | Fixed launch column: `她写给世界的信`; second column remains unapproved pending later confirmation or first-round evidence. |
| D-003 | G0 rights boundary | Authorize identity-derived virtual portrait use with the specific rights holder and written purpose/platform/term/provider/training/derivative/commercial/revocation scope. | Before any reference-image intake or generation; hard gate before M3-06 | Use synthetic, non-identifying test assets; keep real face/voice storage disabled. | BLOCKED | Founder reports the portrait subject agrees in principle. Activation still requires the subject's signed [scope checklist](docs/rights/身份衍生虚拟AI肖像授权与撤回清单_v1.md) plus approved Provider/storage details. |
| D-004 | G1 deployment | Identify deployment主体 and actual service region. | End of week 1 / before M2-00 | Run locally with Mock Providers; no region-sensitive external service. | OPEN | Founders |
| D-005 | G1 Provider | Approve legally usable text, image, video, and audio Provider candidates for that deployment region. | Before M2-00 | Choose M2B and implement two behavioral Mock/contract Providers only. | OPEN | Founders, with terms/privacy evidence |
| D-006 | G1 budget | Set monthly infrastructure/model/media budget and per-content video-generation ceiling. | Before any paid Provider or cloud task | Paid calls disabled; local Mock-only. | OPEN | Founders |
| D-007 | G2 platform qualification | Record whether the chosen platform supplied a test account, app, OAuth callback domain, exact Scope, and API approval. | End of week 2 / before M5-00 | Choose M5B publish-package + manual reconciliation. | OPEN | Platform account holder |
| D-008 | T3 governance | Register two distinct human approvers with MFA and confirm the initiator cannot self-approve. | Before enabling any T3 production action | Keep every T3 production action disabled. | OPEN | Both founders |
| D-009 | Repository operations | Decide whether to create a private remote repository and branch protection. | After local M0 acceptance | Keep local Git only; do not transmit repository content. | OPEN | Founder |
| D-010 | M0 acceptance | Review PRD, lifecycle specification, system context, data model, and ADRs; accept or request changes. | Before M0-04 is treated as downstream implementation | Specifications stay `ready for review`; no application setup is claimed complete. | DECIDED | Founder instructed Codex to continue the plan on 2026-08-19; M0-03 is accepted and M0-04 may proceed under recorded safe fallbacks. |

### D-001 — Xiaohongshu is the first content platform

- Status: DECIDED
- Date: 2026-08-19
- Decision maker: Founder
- Decision: Prioritize Xiaohongshu for the first content experiment and platform packages.
- Evidence / authorization reference: Founder instruction in the Codex project task.
- Effective scope and expiry: MVP content strategy; remains effective until superseded by a dated founder decision.
- Impact: Adapt M1-07 qualification research and M3 packages to Xiaohongshu first. Unless an official, account-specific generic note-publishing API/Scope is verified, select the package/manual-publishing path rather than claiming automated publication. Douyin/Bilibili may remain later adapter candidates but are not the first content platform.

### D-002 — fixed launch column: 她写给世界的信

- Status: DECIDED
- Date: 2026-08-19
- Decision maker: Founder
- Decision: Use `她写给世界的信` as the fixed first Xiaohongshu column. The column name remains stable across posts; each post uses a concrete topic/title beneath it.
- Evidence / authorization reference: Founder instruction in the Codex project task.
- Effective scope and expiry: First Xiaohongshu content experiment; remains effective until superseded by a dated founder decision.
- Impact: Initial content schemas, templates, fixtures, and packages may reference this column. Do not add or imply a second public column without later confirmation. Continue to use only non-identifying photography, typography, screen/process material, and licensed or synthetic assets under D-003.

### D-003 revision 1 — no real portrait or voice in the MVP

- Status: SUPERSEDED on 2026-08-19 by D-003 revision 2
- Date: 2026-08-19
- Decision maker: Founder / rights holder instruction
- Decision: Do not use real portrait, real voice, voice clone, or identity-derived AI avatar assets in the MVP.
- Evidence / authorization reference: Founder instruction in the Codex project task.
- Effective scope and expiry: Entire MVP until a new written, purpose/platform/term/provider/derivative/revocation-scoped decision supersedes it.
- Impact: Use non-identifying original photography, typography, screen/process capture, licensed or synthetic assets, and non-identity-derived illustrations. Keep sensitive face/voice ingestion and storage disabled; D-003 must be reopened before any such implementation or asset intake.

### D-003 revision 2 — intended identity-derived virtual AI portrait

- Status: BLOCKED
- Date: 2026-08-19
- Direction selected by: Founder
- Intended decision: Use a virtual AI portrait derived from a specific real person's identity for `她写给世界的信`, while continuing to exclude real voice and voice cloning.
- Evidence / authorization reference: Founder direction in the Codex project task. This is product intent only and is not evidence of the portrait subject's consent.
- Activation requirements: Identify the portrait subject; obtain that person's signed, withdrawable authorization covering input photos, Xiaohongshu/other platforms, purpose, term, territory, named Provider, Provider retention/training, derivative formats, commercial use, sublicensing, security, revocation, existing-post treatment, and deletion proof; record the approved storage/access path.
- Safe state while blocked: Do not upload, ingest, transform, generate from, or publish any identity reference. Use non-identifying synthetic fixtures only.
- Impact: D-003 revision 1 is superseded as product direction but remains the enforced technical fallback until all activation requirements pass. Identity-derived generation is R3, requires per-use evidence and human approval, must be clearly marked as AI-generated, and cannot be presented as a real photograph.
- Consent progress update (2026-08-19): Founder reports that the portrait subject agrees in principle. This narrows the open issue but does not replace the subject's completed signature, named Provider/data terms, or secure storage verification. Draft authorization: [身份衍生虚拟AI肖像授权与撤回清单（V1）](docs/rights/身份衍生虚拟AI肖像授权与撤回清单_v1.md).

### D-010 — M0-03 specifications accepted

- Status: DECIDED
- Date: 2026-08-19
- Decision maker: Founder
- Decision: Accept the M0-03 PRD, lifecycle, system context, data model, and ADR baseline; continue with M0-04.
- Evidence / authorization reference: Founder instruction “继续计划” in the Codex project task after the M0 review and product-decision sequence.
- Effective scope and expiry: Authorizes local M0-04 engineering work only; it does not authorize real Provider/platform calls, production deployment, portrait processing, or M0-05 machine changes.
- Impact: M0-03 becomes `DONE`. M0-04 may establish the local/CI toolchain using Mock-only and non-identifying fixtures. D-003 and external gates retain their documented safe fallbacks.

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
