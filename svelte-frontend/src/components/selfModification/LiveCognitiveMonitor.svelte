<script>
  export let liveState = {
    timestamp: null,
    currentQuery: null,
    manifestConsciousness: { focus: [], reflectionDepth: 0, selfAwareness: 0 },
    agenticProcesses: [],
    daemonThreads: [],
    resourceUtilization: [],
    alerts: [],
    cognitiveState: {}
  };
  export let loading = false;

  function formatPercent(value = 0) {
    return Math.round(Math.max(0, Math.min(1, value)) * 100);
  }
</script>

<article class="panel" data-testid="live-monitor">
  <header>
    <div>
      <h3>Live Cognitive Monitor</h3>
      <p>Observe manifest processes, resource utilization, and active threads.</p>
    </div>
    {#if liveState.timestamp}
      <span class="timestamp">{new Date(liveState.timestamp).toLocaleTimeString()}</span>
    {/if}
  </header>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Streaming cognitive state…</p>
    </div>
  {:else}
    <section class="metrics">
      <div class="metric-card">
        <span class="label">Reflection Depth</span>
        <strong>{liveState.manifestConsciousness?.reflectionDepth ?? 0}</strong>
        <span class="caption">recursive layers engaged</span>
      </div>
      <div class="metric-card">
        <span class="label">Self-Awareness</span>
        <strong>{formatPercent(liveState.manifestConsciousness?.selfAwareness)}</strong>
        <span class="caption">current confidence</span>
      </div>
      <div class="metric-card">
        <span class="label">Active Query</span>
        <strong>{liveState.currentQuery ? 'Yes' : 'Idle'}</strong>
        <span class="caption">{liveState.currentQuery || 'Awaiting task'}</span>
      </div>
    </section>

    <section class="layout">
      <div class="section">
        <h4>Focus Threads</h4>
        {#if liveState.manifestConsciousness?.focus?.length}
          <ul class="focus">
            {#each liveState.manifestConsciousness.focus as focusItem}
              <li>{focusItem}</li>
            {/each}
          </ul>
        {:else}
          <p class="empty">No recent focus items reported.</p>
        {/if}

        <div class="process-grid">
          <div>
            <h5>Agentic Processes</h5>
            {#if liveState.agenticProcesses?.length}
              <ul class="processes">
                {#each liveState.agenticProcesses as process}
                  <li>
                    <span>{process.label}</span>
                    <span class={`status ${process.status}`}>{process.status}</span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="empty">No agentic processes tracked.</p>
            {/if}
          </div>

          <div>
            <h5>Daemon Threads</h5>
            {#if liveState.daemonThreads?.length}
              <ul class="processes">
                {#each liveState.daemonThreads as thread}
                  <li>
                    <span>{thread.label}</span>
                    <span class={`status ${thread.status}`}>{thread.status}</span>
                  </li>
                {/each}
              </ul>
            {:else}
              <p class="empty">No background threads active.</p>
            {/if}
          </div>
        </div>
      </div>

      <div class="section">
        <h4>Resource Utilization</h4>
        {#if liveState.resourceUtilization?.length}
          <ul class="resources">
            {#each liveState.resourceUtilization as resource}
              <li>
                <span>{resource.category.replace(/_/g, ' ')}</span>
                <div class="bar">
                  <div style={`width: ${formatPercent(resource.allocation)}%`}></div>
                </div>
                <span class="value">{formatPercent(resource.allocation)}%</span>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="empty">Resource metrics unavailable.</p>
        {/if}

        <h4>Alerts</h4>
        {#if liveState.alerts?.length}
          <ul class="alerts">
            {#each liveState.alerts as alert}
              <li class={`alert ${alert.severity || 'info'}`}>
                <span>{alert.message || alert.summary || 'Alert triggered'}</span>
                <time>{alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : ''}</time>
              </li>
            {/each}
          </ul>
        {:else}
          <p class="empty">All systems nominal.</p>
        {/if}
      </div>
    </section>
  {/if}
</article>

<style>
  .panel {
    background: var(--panel-bg);
    border: 1px solid var(--panel-border);
    border-radius: 18px;
    padding: 1.5rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  header h3 {
    margin: 0;
    font-size: 1.45rem;
  }

  header p {
    margin: 0.25rem 0 0;
    color: rgba(226, 232, 240, 0.65);
  }

  .timestamp {
    font-size: 0.85rem;
    color: rgba(226, 232, 240, 0.6);
  }

  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    min-height: 220px;
  }

  .spinner {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    border: 4px solid rgba(148, 163, 184, 0.25);
    border-top-color: rgba(96, 165, 250, 0.8);
    animation: spin 1s linear infinite;
  }

  .metrics {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 1rem;
  }

  .metric-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .metric-card .label {
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.1em;
    color: rgba(226, 232, 240, 0.6);
  }

  .metric-card strong {
    font-size: 1.45rem;
  }

  .metric-card .caption {
    font-size: 0.8rem;
    color: rgba(226, 232, 240, 0.55);
  }

  .layout {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    gap: 1.5rem;
  }

  .section {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  h4 {
    margin: 0;
    font-size: 1.05rem;
  }

  h5 {
    margin: 0 0 0.45rem;
    text-transform: uppercase;
    font-size: 0.8rem;
    letter-spacing: 0.08em;
    color: rgba(226, 232, 240, 0.65);
  }

  .focus {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
  }

  .focus li {
    padding: 0.35rem 0.6rem;
    border-radius: 10px;
    background: rgba(96, 165, 250, 0.15);
    border: 1px solid rgba(96, 165, 250, 0.25);
    font-size: 0.9rem;
  }

  .process-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem;
  }

  .processes {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  .processes li {
    display: flex;
    justify-content: space-between;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 10px;
    padding: 0.5rem 0.7rem;
    font-size: 0.9rem;
  }

  .status {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
    color: rgba(226, 232, 240, 0.8);
  }

  .status.active { color: #4ade80; }
  .status.paused { color: #fbbf24; }
  .status.idle { color: rgba(226, 232, 240, 0.6); }

  .resources {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .resources li {
    display: grid;
    grid-template-columns: 1fr 1fr auto;
    gap: 0.5rem;
    align-items: center;
  }

  .bar {
    width: 100%;
    height: 8px;
    background: rgba(15, 23, 42, 0.85);
    border-radius: 999px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.2);
  }

  .bar div {
    height: 100%;
    background: linear-gradient(90deg, #fbbf24, #fb7185);
  }

  .value {
    font-variant-numeric: tabular-nums;
    font-size: 0.85rem;
    color: rgba(226, 232, 240, 0.75);
  }

  .alerts {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .alert {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.5rem 0.7rem;
    border-radius: 10px;
    border: 1px solid rgba(148, 163, 184, 0.2);
    font-size: 0.9rem;
  }

  .alert.info { background: rgba(96, 165, 250, 0.12); }
  .alert.warning { background: rgba(250, 204, 21, 0.12); }
  .alert.critical { background: rgba(248, 113, 113, 0.15); }

  .empty {
    color: rgba(226, 232, 240, 0.6);
    margin: 0;
  }

  @media (max-width: 960px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
