"use client";

import { useCallback, useEffect, useState } from "react";

import {
  canResolveApproval,
  decisionLabels,
  shortIdentity,
  splitHash,
  statusCopy,
  type ApprovalDecision,
  type ApprovalRequestView,
} from "@/lib/approval-console";

interface ApprovalConsoleProps {
  projectId: string;
  requestId: string;
}

interface ApiError {
  detail?: { message?: string };
}

const bindingLabels = {
  candidate_hash: "候选内容",
  fact_report_hash: "事实报告",
  rights_manifest_hash: "权利清单",
  risk_report_hash: "风险报告",
  account_hash: "账号快照",
} as const;

function formatTime(value: string): string {
  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Shanghai",
  }).format(new Date(value));
}

export default function ApprovalConsole({ projectId, requestId }: ApprovalConsoleProps) {
  const [view, setView] = useState<ApprovalRequestView | null>(null);
  const [error, setError] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [submitting, setSubmitting] = useState<ApprovalDecision | null>(null);
  const approvalUrl = `/api/approvals/${projectId}/${requestId}`;

  const load = useCallback(async () => {
    setError("");
    try {
      const response = await fetch(approvalUrl, { cache: "no-store" });
      const payload = (await response.json()) as ApprovalRequestView & ApiError;
      if (!response.ok) throw new Error(payload.detail?.message ?? "无法读取审批请求");
      setView(payload);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "无法读取审批请求");
    }
  }, [approvalUrl]);

  useEffect(() => {
    let active = true;
    fetch(approvalUrl, { cache: "no-store" })
      .then(async (response) => {
        const payload = (await response.json()) as ApprovalRequestView & ApiError;
        if (!response.ok) throw new Error(payload.detail?.message ?? "无法读取审批请求");
        if (active) setView(payload);
      })
      .catch((loadError: unknown) => {
        if (active) {
          setError(loadError instanceof Error ? loadError.message : "无法读取审批请求");
        }
      });
    return () => {
      active = false;
    };
  }, [approvalUrl]);

  async function decide(decision: ApprovalDecision) {
    if (view === null || !acknowledged || submitting !== null) return;
    setSubmitting(decision);
    setError("");
    try {
      const response = await fetch(approvalUrl, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          schema_version: 1,
          decision,
          expected_version: view.state_version,
        }),
      });
      const payload = (await response.json()) as ApprovalRequestView & ApiError;
      if (!response.ok) throw new Error(payload.detail?.message ?? "决定未能写入");
      setView(payload);
      setAcknowledged(false);
    } catch (decisionError) {
      setError(decisionError instanceof Error ? decisionError.message : "决定未能写入");
      await load();
    } finally {
      setSubmitting(null);
    }
  }

  if (view === null) {
    return (
      <main className="approval-page approval-loading">
        <p className="approval-kicker">她写给世界的信 · 人工门禁</p>
        <h1>{error ? "审批台未能打开" : "正在装订证据…"}</h1>
        {error && (
          <>
            <p role="alert">{error}</p>
            <button type="button" onClick={() => void load()}>
              重新读取
            </button>
          </>
        )}
      </main>
    );
  }

  const resolvable = canResolveApproval(view);
  const bindings = Object.entries(bindingLabels) as [keyof typeof bindingLabels, string][];

  return (
    <main className="approval-page">
      <header className="approval-masthead">
        <div>
          <p className="approval-kicker">她写给世界的信 · 人工门禁</p>
          <p className="approval-product">AGENT IP OS / REVIEW DESK</p>
        </div>
        <div className="approval-viewer" aria-label="当前审批人">
          <span>审批人</span>
          <strong>{shortIdentity(view.viewer_subject_id)}</strong>
          <i>身份由服务端确认</i>
        </div>
      </header>

      <div className="approval-spread">
        <article className="approval-letter" aria-labelledby="letter-title">
          <div className="approval-letter-index">
            <span>LETTER / {view.candidate.platform}</span>
            <span>V{view.candidate_state_version}</span>
          </div>
          <p className="approval-salutation">致，仍然愿意认真生活的人</p>
          <h1 id="letter-title">{view.candidate.title}</h1>
          <p className="approval-caption">{view.candidate.caption}</p>
          <div className="approval-tags" aria-label="内容标签">
            {view.candidate.normalized_tags.map((tag) => (
              <span key={tag}>#{tag}</span>
            ))}
          </div>
          <footer className="approval-letter-footer">
            <span>{view.candidate.ai_disclosure}</span>
            <span>候选稿 {shortIdentity(view.candidate.candidate_id)}</span>
          </footer>
        </article>

        <aside className="approval-decision" aria-labelledby="decision-title">
          <div className={`approval-status approval-status-${view.status.toLowerCase()}`}>
            <span>
              {view.risk_level} / {view.requested_action}
            </span>
            <strong>{statusCopy(view)}</strong>
          </div>

          <section className="approval-evidence" aria-labelledby="evidence-title">
            <div className="approval-section-heading">
              <div>
                <p>01 / EVIDENCE BINDING</p>
                <h2 id="evidence-title">这枚章，只属于这一稿</h2>
              </div>
              <span className="approval-policy">{view.binding.policy_version}</span>
            </div>
            <div className="approval-binding-line">
              {bindings.map(([key, label]) => (
                <div className="approval-hash-knot" key={key}>
                  <span>{label}</span>
                  <code title={view.binding[key]}>{splitHash(view.binding[key])}</code>
                </div>
              ))}
            </div>
          </section>

          <section className="approval-controls" aria-labelledby="decision-title">
            <div className="approval-section-heading">
              <div>
                <p>02 / HUMAN DECISION</p>
                <h2 id="decision-title">由人承担最后决定</h2>
              </div>
              <span className="approval-version">CAS · V{view.state_version}</span>
            </div>

            <dl className="approval-meta">
              <div>
                <dt>发起人</dt>
                <dd>{shortIdentity(view.requested_by_subject_id)}</dd>
              </div>
              <div>
                <dt>所需人数</dt>
                <dd>{view.required_approvals} 人</dd>
              </div>
              <div>
                <dt>截止</dt>
                <dd>{formatTime(view.expires_at)}</dd>
              </div>
            </dl>

            {view.invalidation_reasons.length > 0 && (
              <div className="approval-invalid" role="status">
                <strong>原批准已断开</strong>
                <span>{view.invalidation_reasons.join(" · ")}</span>
              </div>
            )}

            {view.snapshot_hash && (
              <div className="approval-seal-proof">
                <span>批准快照</span>
                <code>{splitHash(view.snapshot_hash)}</code>
              </div>
            )}

            {resolvable ? (
              <>
                <label className="approval-ack">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    onChange={(event) => setAcknowledged(event.target.checked)}
                  />
                  <span>我已阅读正文，并核对候选稿、事实、权利、风险与账号五项绑定。</span>
                </label>
                <div className="approval-actions">
                  {(["APPROVED", "REVISION_REQUESTED", "REJECTED"] as const).map((decision) => (
                    <button
                      className={`approval-action approval-action-${decision.toLowerCase()}`}
                      disabled={!acknowledged || submitting !== null}
                      key={decision}
                      onClick={() => void decide(decision)}
                      type="button"
                    >
                      {submitting === decision ? "写入中…" : decisionLabels[decision]}
                    </button>
                  ))}
                </div>
              </>
            ) : (
              <p className="approval-closed">此请求已关闭。所有决定与快照均保留在审计链中。</p>
            )}
            {error && (
              <p className="approval-error" role="alert">
                {error}
              </p>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}
