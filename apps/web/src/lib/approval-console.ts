export type ApprovalDecision = "APPROVED" | "REJECTED" | "REVISION_REQUESTED";

export type ApprovalStatus =
  "PENDING" | "APPROVED" | "REJECTED" | "REVISION_REQUESTED" | "EXPIRED" | "CANCELLED";

export interface ApprovalRequestView {
  schema_version: 1;
  approval_request_id: string;
  project_id: string;
  status: ApprovalStatus;
  state_version: number;
  candidate_state: string;
  candidate_state_version: number;
  risk_level: "R0" | "R1" | "R2" | "R3" | "R4";
  requested_action: string;
  required_approvals: number;
  requested_by_subject_id: string;
  viewer_subject_id: string;
  expires_at: string;
  created_at: string;
  candidate: {
    schema_version: 1;
    candidate_id: string;
    account_id: string;
    platform: string;
    title: string;
    caption: string;
    normalized_tags: string[];
    ai_disclosure: string;
  };
  binding: {
    schema_version: 1;
    candidate_hash: string;
    fact_report_hash: string;
    rights_manifest_hash: string;
    risk_report_hash: string;
    account_hash: string;
    policy_version: string;
  };
  snapshot_hash: string | null;
  decided_at: string | null;
  approver_subject_ids: string[];
  approval_valid: boolean | null;
  invalidation_reasons: string[];
}

export const decisionLabels: Record<ApprovalDecision, string> = {
  APPROVED: "盖章批准",
  REJECTED: "拒绝此稿",
  REVISION_REQUESTED: "退回修改",
};

export function canResolveApproval(view: ApprovalRequestView, now = new Date()): boolean {
  return view.status === "PENDING" && new Date(view.expires_at).getTime() > now.getTime();
}

export function shortIdentity(value: string): string {
  return `${value.slice(0, 8)}…${value.slice(-4)}`;
}

export function splitHash(value: string): string {
  return value.match(/.{1,8}/g)?.join(" ") ?? value;
}

export function statusCopy(view: ApprovalRequestView): string {
  if (view.status === "PENDING" && !canResolveApproval(view)) return "已过期，等待服务端归档";
  if (view.status === "PENDING") return "等待你的决定";
  if (view.status === "APPROVED" && view.approval_valid === false) return "批准已失效";
  const labels: Record<Exclude<ApprovalStatus, "PENDING">, string> = {
    APPROVED: "批准有效",
    REJECTED: "已拒绝",
    REVISION_REQUESTED: "已退回修改",
    EXPIRED: "已过期",
    CANCELLED: "已取消",
  };
  return labels[view.status];
}
