import { describe, expect, it } from "vitest";

import fixture from "../../../../tests/fixtures/canonical-json-v1.json";
import {
  approvalSnapshotPayload,
  candidatePayload,
  canonicalJson,
  canonicalUtcMilliseconds,
  hashCanonicalJson,
  normalizeSortedTags,
  type ApprovalSnapshotHashInputV1,
  type CandidateHashInputV1,
  type CanonicalValue,
} from "./canonical-json";

describe("canonical JSON v1", () => {
  it("matches every shared generic golden vector", async () => {
    expect(fixture.spec_version).toBe(1);
    for (const vector of fixture.canonical_vectors) {
      const result = await hashCanonicalJson(vector.input as CanonicalValue);
      expect(result).toEqual({
        canonicalJson: vector.canonical_json,
        sha256: vector.sha256,
      });
    }
  });

  it("matches candidate and approval golden vectors", async () => {
    const candidate = candidatePayload(fixture.candidate_vector.input as CandidateHashInputV1);
    expect(await hashCanonicalJson(candidate)).toEqual({
      canonicalJson: fixture.candidate_vector.canonical_json,
      sha256: fixture.candidate_vector.sha256,
    });
    expect(normalizeSortedTags(fixture.candidate_vector.input.tags)).toEqual([
      "AI分身",
      "Ångstrom",
      "写作",
    ]);

    const approval = approvalSnapshotPayload(
      fixture.approval_vector.input as ApprovalSnapshotHashInputV1,
    );
    expect(await hashCanonicalJson(approval)).toEqual({
      canonicalJson: fixture.approval_vector.canonical_json,
      sha256: fixture.approval_vector.sha256,
    });
  });

  it("rejects ambiguous numbers, objects, Unicode, tags, IDs, and hashes", () => {
    const normalizedCollision = { é: 1, "e\u0301": 2 };
    for (const value of [
      1.5,
      Number.POSITIVE_INFINITY,
      9_007_199_254_740_992,
      undefined,
      new Date(),
      normalizedCollision,
      "\ud800",
    ]) {
      expect(() => canonicalJson(value as CanonicalValue)).toThrow();
    }
    expect(() => normalizeSortedTags(["ok", " "])).toThrow("tags must not be blank");
    expect(() =>
      candidatePayload({
        ...fixture.candidate_vector.input,
        ordered_asset_hashes: [],
      }),
    ).toThrow("at least one");
    expect(() =>
      candidatePayload({ ...fixture.candidate_vector.input, account_id: "not-a-uuid" }),
    ).toThrow("invalid UUID");
    expect(() =>
      candidatePayload({
        ...fixture.candidate_vector.input,
        ordered_asset_hashes: ["not-a-hash"],
      }),
    ).toThrow("invalid SHA-256");
    expect(() => candidatePayload({ ...fixture.candidate_vector.input, title: " " })).toThrow(
      "title must not be blank",
    );
  });

  it("normalizes timestamps and validates approval actors", () => {
    expect(canonicalUtcMilliseconds("2026-08-23T08:30:00+08:00")).toBe("2026-08-23T00:30:00.000Z");
    expect(() => canonicalUtcMilliseconds("not-a-time")).toThrow("invalid timestamp");
    expect(() =>
      approvalSnapshotPayload({
        ...fixture.approval_vector.input,
        approver_subject_ids: [],
      } as ApprovalSnapshotHashInputV1),
    ).toThrow("one or two approvers");
    expect(() =>
      approvalSnapshotPayload({
        ...fixture.approval_vector.input,
        approver_subject_ids: [
          fixture.approval_vector.input.approver_subject_ids[0],
          fixture.approval_vector.input.approver_subject_ids[0],
        ],
      } as ApprovalSnapshotHashInputV1),
    ).toThrow("distinct approvers");
  });
});
