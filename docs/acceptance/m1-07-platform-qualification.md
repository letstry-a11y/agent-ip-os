# M1-07 Xiaohongshu platform qualification evidence

- Captured: 2026-08-22 (Asia/Shanghai)
- Result: **PASS / M5B FALLBACK SELECTED**
- External requests: **0**
- Safety boundary: official public documentation and local evidence validation only

## Qualification result

| Required evidence | Result |
|---|---|
| Allowlisted test account | Not evidenced |
| Approved developer application / AppKey | Not evidenced |
| OAuth callback domain / approved application link | Not evidenced |
| Exact generic note-publishing Scope | Not evidenced |
| Account-specific API approval | Not evidenced |
| Explicit authorization for a named test action | Not evidenced |
| Minimal official API probe | Not run; no authorized Scope |

The official [Share Open Platform](https://agora.xiaohongshu.com/) documents a client SDK
that carries image/video material into the Xiaohongshu App publishing experience. The official
[iOS](https://agora.xiaohongshu.com/doc/ios) and
[Android](https://agora.xiaohongshu.com/doc/android) guides require an approved application and
AppKey. The official [FAQ](https://agora.xiaohongshu.com/doc/qa) describes this as a user quick
publish flow and says automatic title/caption filling is restricted. None of those pages grants
this project a generic server-side note-publishing API.

The separate [Mini Program certification rules](https://miniapp.xiaohongshu.com/doc/DC356986)
require a qualified organization and apply to mini-program operation; they do not satisfy the
generic creator-note requirement.

## Probe evidence

The machine-readable snapshot is
[`config/platforms/xiaohongshu-qualification-v1.json`](../../config/platforms/xiaohongshu-qualification-v1.json).
The local validator rejects non-official source hosts, sensitive fields, documentation-only
records that claim network requests, and any M5A declaration without every required grant plus
one successful explicitly authorized official probe.

Command:

```powershell
uv run --locked python scripts/platform_qualification.py
```

Expected result:

```json
{"platform":"xiaohongshu","probe_result":"NOT_RUN_NO_AUTHORIZED_SCOPE","selected_branch":"M5B","valid":true}
```

## Delivery decision

M1-07 is complete because the missing G2 evidence is truthfully recorded and the safe branch is
deterministic. M5 currently selects **M5B**: complete publish packages, Mock contracts, and
manual post/metric reconciliation. The client Share SDK is only a future human-operated bridge
candidate after app registration and review; it is not counted as automated publication.

D-007 remains open for the platform account holder. A later account-specific grant may replace
this snapshot through a new versioned record and a separately authorized minimal probe. No
Cookie, credential, personal account identifier, browser-publishing automation, undocumented
endpoint, upload, or publication was used.

## Verification

1. The checked-in documentation-only record validated as `M5B` with zero external requests.
2. Six focused tests passed for the current fallback, complete M5A grant requirements,
   non-official source rejection, sensitive-field rejection, overstated-branch rejection, and
   invalid JSON handling.
3. The canonical repository check passed with all baseline hashes, migrations, Markdown links,
   and secret patterns verified.
4. Ruff formatting/lint and strict mypy passed for the full Python boundary.
5. The complete unit, Temporal workflow, and PostgreSQL integration suite passed all 73 tests
   with 100% statement and branch coverage for the measured workspace packages.
6. Prettier, ESLint, TypeScript, eight Vitest tests, and the Next.js production build passed.
