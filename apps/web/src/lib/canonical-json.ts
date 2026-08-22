const MAX_SAFE_INTEGER = 9_007_199_254_740_991;
const encoder = new TextEncoder();
const SHA256_PATTERN = /^[0-9a-f]{64}$/;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

export type CanonicalValue =
  | null
  | boolean
  | number
  | string
  | readonly CanonicalValue[]
  | { readonly [key: string]: CanonicalValue };

function normalizeUnicode(value: string): string {
  const normalized = value.normalize("NFC");
  for (let index = 0; index < normalized.length; index += 1) {
    const unit = normalized.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = normalized.charCodeAt(index + 1);
      if (!(next >= 0xdc00 && next <= 0xdfff)) {
        throw new Error("Unicode surrogate code points are not supported");
      }
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new Error("Unicode surrogate code points are not supported");
    }
  }
  return normalized;
}

function compareUtf8(left: string, right: string): number {
  const leftBytes = encoder.encode(left);
  const rightBytes = encoder.encode(right);
  const length = Math.min(leftBytes.length, rightBytes.length);
  for (let index = 0; index < length; index += 1) {
    const difference = leftBytes[index]! - rightBytes[index]!;
    if (difference !== 0) return difference;
  }
  return leftBytes.length - rightBytes.length;
}

function canonicalText(value: unknown): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value) || Math.abs(value) > MAX_SAFE_INTEGER) {
      throw new Error("numbers must be IEEE-754 safe integers");
    }
    return String(value);
  }
  if (typeof value === "string") return JSON.stringify(normalizeUnicode(value));
  if (Array.isArray(value)) return `[${value.map(canonicalText).join(",")}]`;
  if (typeof value === "object") {
    const prototype = Object.getPrototypeOf(value);
    if (prototype !== Object.prototype && prototype !== null) {
      throw new Error("canonical objects must be plain records");
    }
    const normalized = new Map<string, unknown>();
    for (const [key, item] of Object.entries(value)) {
      const normalizedKey = normalizeUnicode(key);
      if (normalized.has(normalizedKey)) {
        throw new Error("object keys collide after Unicode NFC normalization");
      }
      normalized.set(normalizedKey, item);
    }
    const keys = [...normalized.keys()].sort(compareUtf8);
    return `{${keys
      .map((key) => `${JSON.stringify(key)}:${canonicalText(normalized.get(key))}`)
      .join(",")}}`;
  }
  throw new Error(`unsupported canonical JSON type: ${typeof value}`);
}

export function canonicalJson(value: CanonicalValue): string {
  return canonicalText(value);
}

export async function hashCanonicalJson(
  value: CanonicalValue,
): Promise<{ canonicalJson: string; sha256: string }> {
  const text = canonicalJson(value);
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(text));
  const sha256 = [...new Uint8Array(digest)]
    .map((item) => item.toString(16).padStart(2, "0"))
    .join("");
  return { canonicalJson: text, sha256 };
}

function requireNonBlank(value: string, field: string): string {
  if (!value.trim()) throw new Error(`${field} must not be blank`);
  return value;
}

function canonicalUuid(value: string): string {
  const normalized = value.toLowerCase();
  if (!UUID_PATTERN.test(normalized)) throw new Error("invalid UUID");
  return normalized;
}

function canonicalSha256(value: string): string {
  if (!SHA256_PATTERN.test(value)) throw new Error("invalid SHA-256 value");
  return value;
}

export function normalizeSortedTags(tags: readonly string[]): string[] {
  const normalized = new Set<string>();
  for (const tag of tags) {
    const candidate = normalizeUnicode(tag).trim();
    if (!candidate) throw new Error("candidate tags must not be blank");
    normalized.add(candidate);
  }
  return [...normalized].sort(compareUtf8);
}

export interface CandidateHashInputV1 {
  readonly title: string;
  readonly caption: string;
  readonly tags: readonly string[];
  readonly ordered_asset_hashes: readonly string[];
  readonly ai_disclosure: string;
  readonly platform: string;
  readonly account_id: string;
  readonly policy_version: string;
}

export function candidatePayload(value: CandidateHashInputV1): CanonicalValue {
  if (value.ordered_asset_hashes.length === 0) {
    throw new Error("candidate requires at least one ordered asset hash");
  }
  return {
    account_id: canonicalUuid(value.account_id),
    ai_disclosure: requireNonBlank(value.ai_disclosure, "ai_disclosure"),
    caption: value.caption,
    ordered_asset_hashes: value.ordered_asset_hashes.map(canonicalSha256),
    platform: requireNonBlank(value.platform, "platform"),
    policy_version: requireNonBlank(value.policy_version, "policy_version"),
    sorted_tags: normalizeSortedTags(value.tags),
    title: requireNonBlank(value.title, "title"),
  };
}

export function canonicalUtcMilliseconds(value: string | Date): string {
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) throw new Error("invalid timestamp");
  return date.toISOString();
}

export interface ApprovalSnapshotHashInputV1 {
  readonly project_id: string;
  readonly approval_request_id: string;
  readonly candidate_id: string;
  readonly account_id: string;
  readonly decision: "APPROVED" | "REJECTED" | "REVISION_REQUESTED";
  readonly candidate_hash: string;
  readonly fact_report_hash: string;
  readonly rights_manifest_hash: string;
  readonly risk_report_hash: string;
  readonly account_hash: string;
  readonly policy_version: string;
  readonly approved_action: string;
  readonly approver_subject_ids: readonly string[];
  readonly expires_at: string | Date;
  readonly decided_at: string | Date;
}

export function approvalSnapshotPayload(value: ApprovalSnapshotHashInputV1): CanonicalValue {
  if (value.approver_subject_ids.length < 1 || value.approver_subject_ids.length > 2) {
    throw new Error("approval snapshots require one or two approvers");
  }
  const approvers = value.approver_subject_ids.map(canonicalUuid).sort(compareUtf8);
  if (new Set(approvers).size !== approvers.length) {
    throw new Error("approval snapshots require distinct approvers");
  }
  return {
    account_hash: canonicalSha256(value.account_hash),
    account_id: canonicalUuid(value.account_id),
    approval_request_id: canonicalUuid(value.approval_request_id),
    approved_action: requireNonBlank(value.approved_action, "approved_action"),
    approver_subject_ids: approvers,
    candidate_hash: canonicalSha256(value.candidate_hash),
    candidate_id: canonicalUuid(value.candidate_id),
    decided_at: canonicalUtcMilliseconds(value.decided_at),
    decision: value.decision,
    expires_at: canonicalUtcMilliseconds(value.expires_at),
    fact_report_hash: canonicalSha256(value.fact_report_hash),
    policy_version: requireNonBlank(value.policy_version, "policy_version"),
    project_id: canonicalUuid(value.project_id),
    rights_manifest_hash: canonicalSha256(value.rights_manifest_hash),
    risk_report_hash: canonicalSha256(value.risk_report_hash),
    schema_version: 1,
  };
}
