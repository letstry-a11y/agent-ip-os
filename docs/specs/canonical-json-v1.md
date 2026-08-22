# Canonical JSON and approval binding v1

- Status: M1-03 implemented; founder review pending
- Version: 1.0
- Normative for: candidate hashes, report hashes, approval snapshots, and later request fingerprints
- Related: [content lifecycle](content-lifecycle.md), [core data model](../architecture/data-model.md)

## Purpose and boundary

Canonical JSON v1 converts the same supported logical value into the same UTF-8 bytes in
Python and TypeScript. SHA-256 is calculated over those exact bytes, with no BOM, trailing
newline, domain prefix, or platform-local encoding. A hash identifies bytes; it does not
grant authority or replace project/resource authorization.

M1-03 does not publish, create an outbox record, call a Provider, or change risk levels. It
only freezes deterministic identities and evaluates whether an immutable approval still
matches current authoritative bindings.

## Byte-level canonical JSON rules

1. Output is compact JSON encoded as UTF-8 without a BOM or trailing newline.
2. Every object key and string value is normalized to Unicode NFC. Lone UTF-16 surrogate
   code points are rejected. If two source keys become equal after NFC, the object is
   rejected rather than silently dropping one value.
3. Object keys are sorted by the unsigned lexicographic order of their normalized UTF-8
   bytes. JSON insertion order is never authoritative.
4. Arrays preserve order. Generic canonicalization never sorts or deduplicates an array.
5. `null`, `true`, and `false` use the JSON lowercase literals.
6. JSON numbers are restricted to integers in the inclusive IEEE-754 safe range
   `[-9007199254740991, 9007199254740991]`. Fractional, non-finite, and unsafe integers are
   rejected. Money, confidence, and measurements that need decimal precision use an
   explicitly specified string or scaled-integer field in their own schema.
7. An absent object member is omitted and differs from a present member whose value is
   `null`. `undefined` and implicit omission are not supported canonical values.
8. Times bound into a hash use UTC RFC 3339 with exactly millisecond precision:
   `YYYY-MM-DDTHH:mm:ss.SSSZ`. Aware inputs are converted to UTC; sub-millisecond precision
   is rejected rather than truncated. Schedule time-zone intent is stored separately as an
   IANA name when the owning schema requires it.
9. UUIDs use lowercase hyphenated text. SHA-256 values use 64 lowercase hexadecimal
   characters.

## Candidate hash

Candidate tags are NFC-normalized, trimmed at their outer boundary, empty values removed by
rejection, deduplicated case-sensitively, and sorted by UTF-8 bytes. Asset hashes remain in
render/publish order. The candidate payload is:

```json
{
  "account_id": "lowercase UUID",
  "ai_disclosure": "final disclosure text",
  "caption": "final caption text",
  "ordered_asset_hashes": ["sha256", "sha256"],
  "platform": "platform capability key",
  "policy_version": "effective policy version",
  "sorted_tags": ["tag-a", "tag-b"],
  "title": "final title text"
}
```

`candidate_hash = sha256(canonical_json(candidate_payload))`.

The schedule is deliberately excluded from `candidate_hash`; M1-04 binds the normalized
schedule slot into `request_fingerprint`. Changing title, caption, normalized tags, ordered
asset hashes, disclosure, platform, account, or policy version produces a different
candidate hash and requires a new immutable candidate.

## Approval snapshot hash

The approval snapshot hash binds:

- project, approval request, candidate, account, and schema identity;
- decision and approved action;
- candidate, fact-report, rights-manifest, risk-report, and account hashes;
- policy version;
- at least one human approver subject ID (one is sufficient in early/MVP operation); the
  schema can preserve an optional second distinct ID for a future production policy;
- decision time and expiry in canonical UTC milliseconds.

`snapshot_hash = sha256(canonical_json(approval_snapshot_payload))`.

An approval is usable only when its stored snapshot hash recomputes exactly, the decision is
`APPROVED`, the check time is earlier than expiry, and every current candidate/report/policy/
account/action binding equals the snapshot. Any mismatch returns explicit invalidation
reasons and fails closed. Current MVP authorization requires one authorized human approval,
not two. Reordering a future two-person set does not change the hash; adding, removing, or
duplicating an approver is not equivalent.

## Golden vectors and compatibility

Versioned vectors live in `tests/fixtures/canonical-json-v1.json`. Python and TypeScript run
the same vectors for key ordering, Unicode NFC, safe integers, null versus absence, tags,
ordered assets, time-zone conversion, candidate hash, and approval snapshot hash.

This specification is append-only by version. A future rule change creates canonical JSON
v2 and a new public schema version; it must not reinterpret stored v1 hashes.
