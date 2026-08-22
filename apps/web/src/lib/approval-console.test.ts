import { describe, expect, it } from "vitest";

import {
  canResolveApproval,
  shortIdentity,
  splitHash,
  statusCopy,
  type ApprovalRequestView,
} from "./approval-console";

const view = {
  status: "PENDING",
  expires_at: "2020-08-23T10:00:00Z",
  approval_valid: null,
} as ApprovalRequestView;

describe("approval console helpers", () => {
  it("permits only an unexpired pending request", () => {
    const futureView = { ...view, expires_at: "2026-08-23T10:00:00Z" };
    expect(canResolveApproval(futureView, new Date("2026-08-22T10:00:00Z"))).toBe(true);
    expect(canResolveApproval(futureView, new Date("2026-08-23T10:00:00Z"))).toBe(false);
    expect(canResolveApproval({ ...view, status: "REJECTED" })).toBe(false);
  });

  it("makes identities and hashes scannable without changing their source values", () => {
    expect(shortIdentity("12345678-1234-1234-1234-123456789abc")).toBe("12345678…9abc");
    expect(splitHash("abcdef0123456789")).toBe("abcdef01 23456789");
  });

  it("distinguishes pending, expired, valid, and invalidated outcomes", () => {
    expect(statusCopy(view)).toBe("已过期，等待服务端归档");
    expect(statusCopy({ ...view, expires_at: "2999-01-01T00:00:00Z" })).toBe("等待你的决定");
    expect(statusCopy({ ...view, status: "APPROVED", approval_valid: true })).toBe("批准有效");
    expect(statusCopy({ ...view, status: "APPROVED", approval_valid: false })).toBe("批准已失效");
    expect(statusCopy({ ...view, status: "REVISION_REQUESTED" })).toBe("已退回修改");
    expect(statusCopy({ ...view, status: "EXPIRED" })).toBe("已过期");
    expect(statusCopy({ ...view, status: "CANCELLED" })).toBe("已取消");
    expect(statusCopy({ ...view, status: "REJECTED" })).toBe("已拒绝");
  });
});
