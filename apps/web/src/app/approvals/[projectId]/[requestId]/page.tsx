import ApprovalConsole from "./approval-console";

interface ApprovalPageProps {
  params: Promise<{ projectId: string; requestId: string }>;
}

export default async function ApprovalPage({ params }: ApprovalPageProps) {
  const { projectId, requestId } = await params;
  return <ApprovalConsole projectId={projectId} requestId={requestId} />;
}
