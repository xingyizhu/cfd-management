<template>
  <div class="bug-view">
    <div class="hero-shell">
      <p class="hero-kicker">CFD Team Console</p>
      <h1 class="hero-title">Bug Intelligence Center</h1>
      <p class="hero-subtitle">页面已预留，后续可接入 Jira Bug 趋势与责任人维度统计。</p>
      <div class="hero-chip-row">
        <span class="hero-chip">📈 趋势追踪</span>
        <span class="hero-chip">👥 责任分布</span>
        <span class="hero-chip">⏱️ SLA 监控</span>
      </div>
    </div>

    <div class="metrics-grid">
      <div class="metric-card">
        <p class="metric-label">新增 Bug</p>
        <p class="metric-value">--</p>
        <p class="metric-note">按自然日</p>
      </div>
      <div class="metric-card">
        <p class="metric-label">已关闭 Bug</p>
        <p class="metric-value">--</p>
        <p class="metric-note">按自然日</p>
      </div>
      <div class="metric-card">
        <p class="metric-label">未解决 Bug</p>
        <p class="metric-value">--</p>
        <p class="metric-note">实时存量</p>
      </div>
    </div>

    <div class="info-banner">Bug 模块等待 Jira 数据接入后即可启用。</div>
  </div>
</template>

<style scoped>
.bug-view {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.hero-shell {
  border-radius: 20px;
  padding: 1.25rem 1.3rem 1.1rem;
  border: 1px solid var(--border);
  background:
    radial-gradient(circle at 78% -35%, rgba(109, 166, 255, 0.52), transparent 38%),
    linear-gradient(135deg, rgba(24, 40, 80, 0.86), rgba(9, 18, 40, 0.86));
  box-shadow: var(--shadow);
}

.hero-kicker {
  letter-spacing: 0.07em;
  font-size: 0.75rem;
  text-transform: uppercase;
  color: #b7dcff;
  font-weight: 600;
  margin-bottom: 0.45rem;
}

.hero-title {
  font-family: "Noto Serif SC", serif;
  font-size: 1.9rem;
  color: #f9fcff;
}

.hero-subtitle {
  margin: 0.4rem 0 0.8rem;
  color: var(--text-sub);
  font-size: 0.92rem;
}

.hero-chip-row {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.hero-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.3rem 0.65rem;
  border-radius: 999px;
  border: 1px solid rgba(147, 178, 255, 0.35);
  background: rgba(13, 23, 47, 0.75);
  color: #dbe8ff;
  font-size: 0.8rem;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 0.75rem;
}

.metric-card {
  border-radius: 16px;
  padding: 0.85rem 0.92rem;
  border: 1px solid rgba(139, 170, 255, 0.28);
  background: linear-gradient(160deg, rgba(20, 35, 70, 0.84), rgba(10, 22, 46, 0.84));
  box-shadow: var(--shadow);
  min-height: 102px;
}

.metric-label { color: #c5d5fb; font-size: 0.82rem; }
.metric-value { margin: 0.3rem 0 0; font-size: 1.45rem; font-weight: 700; }
.metric-note { margin: 0.3rem 0 0; color: #a4bbec; font-size: 0.76rem; }

.info-banner {
  padding: 0.75rem 1rem;
  border-radius: 12px;
  border: 1px solid rgba(147, 178, 255, 0.3);
  background: rgba(20, 35, 70, 0.5);
  color: var(--text-sub);
  font-size: 0.9rem;
}
</style>
