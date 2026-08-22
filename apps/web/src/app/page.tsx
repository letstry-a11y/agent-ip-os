import { runtimeBoundary } from "@/lib/runtime";

const statusCards = [
  ["Platform", "小红书优先；当前仅生成发布包，不执行真实发布。"],
  ["Column", "固定栏目「她写给世界的信」，第二栏目尚未启用。"],
  ["Portrait", "身份衍生AI肖像仍受授权、Provider和安全存储门禁约束。"],
  ["Runtime", "Mock-only、DRY_RUN，所有外部副作用默认关闭。"],
] as const;

export default function Home() {
  return (
    <main className="home-main">
      <p className="eyebrow">M0 engineering baseline</p>
      <h1>Agent IP OS</h1>
      <p className="intro">
        一个把创作、权利、审批与发布证据放在同一条可审计链路中的内容操作系统。当前页面只证明工程骨架可运行，不代表任何真实Provider或平台已经接入。
      </p>
      <section className="status-grid" aria-label="Current project boundaries">
        {statusCards.map(([label, value]) => (
          <article className="status-card" key={label}>
            <strong>{label}</strong>
            <span>{value}</span>
          </article>
        ))}
      </section>
      <p className="intro">
        外部副作用：{runtimeBoundary.externalSideEffectsEnabled ? "开启" : "关闭"}
      </p>
    </main>
  );
}
