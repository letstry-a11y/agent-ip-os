import { NextRequest, NextResponse } from "next/server";

const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const decisions = new Set(["APPROVED", "REJECTED", "REVISION_REQUESTED"]);

interface RouteContext {
  params: Promise<{ projectId: string; requestId: string }>;
}

function apiOrigin(): string {
  return process.env.AGENT_IP_API_URL ?? "http://127.0.0.1:8000";
}

async function target(context: RouteContext): Promise<string | null> {
  const { projectId, requestId } = await context.params;
  if (!uuidPattern.test(projectId) || !uuidPattern.test(requestId)) return null;
  return `${apiOrigin()}/api/v1/projects/${projectId}/approvals/${requestId}`;
}

async function relay(response: Response): Promise<NextResponse> {
  const payload: unknown = await response.json().catch(() => ({
    detail: { code: "approval_upstream_invalid", message: "审批服务返回了无效响应" },
  }));
  return NextResponse.json(payload, { status: response.status });
}

export async function GET(_request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const url = await target(context);
  if (url === null) {
    return NextResponse.json(
      { detail: { code: "invalid_approval_route", message: "审批地址无效" } },
      { status: 400 },
    );
  }
  try {
    return relay(await fetch(url, { cache: "no-store" }));
  } catch {
    return NextResponse.json(
      { detail: { code: "approval_upstream_unavailable", message: "审批服务暂时不可用" } },
      { status: 503 },
    );
  }
}

export async function POST(request: NextRequest, context: RouteContext): Promise<NextResponse> {
  const url = await target(context);
  if (url === null) {
    return NextResponse.json(
      { detail: { code: "invalid_approval_route", message: "审批地址无效" } },
      { status: 400 },
    );
  }
  const body: unknown = await request.json().catch(() => null);
  if (
    typeof body !== "object" ||
    body === null ||
    Object.keys(body).sort().join(",") !== "decision,expected_version,schema_version" ||
    !("schema_version" in body) ||
    body.schema_version !== 1 ||
    !("decision" in body) ||
    typeof body.decision !== "string" ||
    !decisions.has(body.decision) ||
    !("expected_version" in body) ||
    !Number.isInteger(body.expected_version) ||
    (body.expected_version as number) < 0
  ) {
    return NextResponse.json(
      { detail: { code: "invalid_decision", message: "决定内容无效或包含身份字段" } },
      { status: 400 },
    );
  }
  try {
    return relay(
      await fetch(`${url}/decisions`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        cache: "no-store",
      }),
    );
  } catch {
    return NextResponse.json(
      { detail: { code: "approval_upstream_unavailable", message: "审批服务暂时不可用" } },
      { status: 503 },
    );
  }
}
