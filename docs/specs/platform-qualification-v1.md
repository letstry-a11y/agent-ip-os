# Platform qualification record v1

- Status: implemented for M1-07
- Platform: Xiaohongshu
- External effects: none

## Purpose

M1-07 records whether an official, account-specific platform capability is actually available
before any adapter work claims that content can be published. The probe is evidence-first: a
public capability description is not an account grant, a client share flow is not a server-side
publish API, and an absent grant selects the publish-package fallback.

This specification derives from [ADR-0003](../adr/0003-official-platform-api-or-publish-package.md),
[D-001 and D-007](../../DECISIONS.md), and the immutable
[execution baseline](../baseline/AI超级IP系统_Codex开发执行计划_v1.md).

## Official capability findings

Captured on 2026-08-22 from official Xiaohongshu properties:

- The [Share Open Platform](https://agora.xiaohongshu.com/) documents client SDKs that move
  image/video material into Xiaohongshu App's built-in publishing flow. This remains a
  user-operated app flow, not evidence of a generic server-side note-publishing API.
- The official [iOS integration guide](https://agora.xiaohongshu.com/doc/ios) requires an
  application registration, AppKey, requested permission, review, matching application
  identity, and Universal Link configuration.
- The official [Android integration guide](https://agora.xiaohongshu.com/doc/android) requires
  an AppKey obtained after providing application/package information.
- The official [Share SDK FAQ](https://agora.xiaohongshu.com/doc/qa) states that automatic
  title and caption filling through the SDK is restricted and describes the SDK as a way for a
  user to reach Xiaohongshu App's quick note-publishing flow.
- The [Mini Program certification rules](https://miniapp.xiaohongshu.com/doc/DC356986) apply to
  certified enterprises and other registered organizations operating mini programs. They do
  not evidence a generic creator note-publishing Scope for this project.

No official public document located in this qualification pass evidenced a server-side generic
note-publishing API or an account grant for this project. This is an absence-of-evidence result,
not a claim that Xiaohongshu can never grant a private or future capability.

## Versioned evidence record

`config/platforms/xiaohongshu-qualification-v1.json` is the machine-readable snapshot. It
records:

- capture time and official source URLs;
- test-account, developer-app, callback-domain, exact-Scope, API-approval, and explicit probe
  authorization evidence;
- documented client-share and server-publish observations;
- minimal probe mode, result, and external request count;
- the selected M5 delivery branch.

The record must contain no token, cookie, password, secret, credential value, personal account
identifier, or private application identifier.

## Branch selection

M5A is eligible only when all of the following are evidenced together:

1. an allowlisted test account;
2. an approved developer application;
3. an approved callback domain where the capability requires one;
4. the exact `generic_note_publish` Scope;
5. account/API approval;
6. explicit human authorization for the named minimal test action; and
7. a successful official minimal probe.

Any missing item selects M5B: complete Xiaohongshu publish packages, a Mock adapter contract,
and honest manual post/metric reconciliation. The official client Share SDK may be reconsidered
later as a human-operated convenience bridge, but it is not treated as automated publication.

## Safe probe procedure

The checked-in probe is documentation-only and network-free. It validates the evidence record
and fails if the declared branch overstates the recorded grant. A future account probe requires
new explicit authorization naming the test account, app, exact Scope, endpoint/action, and
environment. Cookie automation, simulated publishing clicks, undocumented endpoints, and
production-account experiments remain prohibited.
