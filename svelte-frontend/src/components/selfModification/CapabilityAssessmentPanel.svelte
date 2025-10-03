<script>
  import { createEventDispatcher } from 'svelte';

  export let capabilities = [];
  export let summary = { total: 0, operational: 0, developing: 0, averagePerformance: 0 };
  export let learningFocus = [];
  export let recentImprovements = [];
  export let resourceAllocation = [];
  export let metacognitiveState = {};
  export let loading = false;
  export let onRefresh = null;
  export let status = { state: 'idle', message: 'Standing by for updates.', updatedAt: null, meta: {} };
  export let feedbackEntries = [];
  export let pushFeedback = null;
  export let dismissFeedback = null;

  const dispatch = createEventDispatcher();

  function formatPercent(value = 0) {
    return Math.round(Math.max(0, Math.min(1, value)) * 100);
  }

  function trendIcon(trend = 'stable') {
    if (trend === 'up') return '📈';
    if (trend === 'down') return '📉';
    return '➖';
  }

  const focusLabels = {
    knowledge_integration: 'Knowledge Integration',
    reasoning_optimization: 'Reasoning Optimization',
    pattern_learning: 'Pattern Learning',
    architecture_maintenance: 'Architecture Maintenance',
    safety_monitoring: 'Safety Monitoring'
  };

  function formatAllocationLabel(category) {
    if (!category) return 'General';
    if (category.startsWith('focus_')) {
      return `Focus · ${category.replace('focus_', '').replace(/_/g, ' ')}`;
    }
    return focusLabels[category] || category.replace(/_/g, ' ');
  }

  function handleRefresh() {
    if (typeof onRefresh === 'function') {
      dispatch('refresh');
      onRefresh();
      if (typeof pushFeedback === 'function') {
        pushFeedback('info', 'Manual capability refresh requested.', {
          origin: 'CapabilityAssessmentPanel'
        });
      }
    }
  }

  $: metaSummaryItems = (() => {
    if (!metacognitiveState || typeof metacognitiveState !== 'object') return [];

    const items = [];
    const status = metacognitiveState.status || metacognitiveState.mode;
    if (status) {
      items.push({
        label: 'Status',
        value: status.replace(/_/g, ' ')
      });
    }

    const confidence = metacognitiveState.confidence ?? metacognitiveState.confidence_score;
    if (typeof confidence === 'number') {
      items.push({
        label: 'Confidence',
        value: `${formatPercent(confidence)}%`
      });
    }

    const cycle = metacognitiveState.active_cycle || metacognitiveState.phase;
    if (cycle) {
      items.push({
        label: 'Cycle',
        value: cycle.replace(/_/g, ' ')
      });
    }

    const lastAssessment = metacognitiveState.last_assessment || metacognitiveState.lastAssessment;
    if (lastAssessment) {
      try {
        items.push({
          label: 'Last Assessment',
          value: new Date(lastAssessment).toLocaleString()
        });
      } catch (error) {
        items.push({
          label: 'Last Assessment',
          value: lastAssessment
        });
      }
    }

    const focus = Array.isArray(metacognitiveState.focus) ? metacognitiveState.focus : null;
    if (focus && focus.length) {
      items.push({
        label: 'Current Focus',
        value: focus.join(', ')
      });
    }

    return items;
  })();
</script>

<article class="panel" data-testid="capability-panel">
  <header>
    <div class="header-left">
      <div>
        <h3>Capability Assessment</h3>
        <p>Real-time capability confidence, learning focus, and resource allocation.</p>
      </div>
      <div class={`status-pill ${status.state}`}>
        <span class="status-icon">{status.state === 'loading' ? '⏳' : status.state === 'success' ? '✅' : status.state === 'error' ? '⚠️' : status.state === 'warning' ? '⚠️' : 'ℹ️'}</span>
        <div class="status-text">
          <strong>{status.message}</strong>
          {#if status.updatedAt}
            <time>{new Date(status.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
          {/if}
        </div>
      </div>
    </div>
    <button class="ghost" on:click={handleRefresh} disabled={loading}>
      🔄
    </button>
  </header>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Synchronizing capability metrics…</p>
    </div>
  {:else}
    {#if feedbackEntries?.length}
      <aside class="feedback-cues" aria-live="polite">
        <h4>Recent Updates</h4>
        <ul>
          {#each feedbackEntries as entry (entry.id)}
            <li>
              <span class={`dot ${entry.type}`}></span>
              <div class="cue-text">
                <p>{entry.message}</p>
                <time>{new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
              </div>
              {#if typeof dismissFeedback === 'function'}
                <button class="dismiss" type="button" on:click={() => dismissFeedback(entry.id)} aria-label="Dismiss cue">✕</button>
              {/if}
            </li>
          {/each}
        </ul>
      </aside>
    {/if}
    <section class="summary-grid">
      <div class="metric-card">
        <span class="label">Operational</span>
        <strong>{summary.operational}</strong>
        <span class="caption">of {summary.total} capabilities</span>
      </div>
      <div class="metric-card">
        <span class="label">Developing</span>
        <strong>{summary.developing}</strong>
        <span class="caption">requiring coaching</span>
      </div>
      <div class="metric-card">
        <span class="label">Average Performance</span>
        <strong>{formatPercent(summary.averagePerformance)}%</strong>
        <span class="caption">weighted across focus areas</span>
      </div>
    </section>

    <section class="content-grid">
      <div class="capability-list">
        <h4>Capability Levels</h4>
        {#if capabilities.length === 0}
          <p class="empty">No capability assessments available yet.</p>
        {:else}
          <ul>
            {#each capabilities as capability}
              <li>
                <div class="cap-header">
                  <span class="title">{capability.label}</span>
                  <span class={`status ${capability.status || 'unknown'}`}>{capability.status}</span>
                </div>
                <div class="progress">
                  <div class="bar" style={`width: ${formatPercent(capability.currentLevel)}%`}></div>
                </div>
                <div class="meta">
                  <span>{trendIcon(capability.trend)} {formatPercent(capability.currentLevel)}%</span>
                  <span>Confidence {formatPercent(capability.confidence)}%</span>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <div class="sidebar">
        <section>
          <h4>Learning Focus</h4>
          {#if learningFocus.length === 0}
            <p class="empty">No focused capability tracks at the moment.</p>
          {:else}
            <div class="chips">
              {#each learningFocus as capability}
                <span class="chip">{capability.label}</span>
              {/each}
            </div>
          {/if}
        </section>

        <section>
          <h4>Resource Allocation</h4>
          {#if resourceAllocation.length === 0}
            <p class="empty">Resource allocation metrics unavailable.</p>
          {:else}
            <ul class="allocation-list">
              {#each resourceAllocation as item}
                <li>
                  <span>{formatAllocationLabel(item.category)}</span>
                  <span>{formatPercent(item.allocation)}%</span>
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        <section>
          <h4>Recent Improvements</h4>
          {#if recentImprovements.length === 0}
            <p class="empty">No significant improvement shifts logged.</p>
          {:else}
            <ul class="improvements">
              {#each recentImprovements as item}
                <li>
                  <span>{item.id.replace(/_/g, ' ')}</span>
                  <span class={item.delta >= 0 ? 'positive' : 'negative'}>
                    {item.delta >= 0 ? '+' : ''}{item.delta.toFixed(2)}
                  </span>
                </li>
              {/each}
            </ul>
          {/if}
        </section>

        <section>
          <h4>Metacognitive Summary</h4>
          {#if metaSummaryItems.length === 0}
            <p class="empty">No metacognitive context available.</p>
          {:else}
            <ul class="meta-summary">
              {#each metaSummaryItems as item}
                <li>
                  <span>{item.label}</span>
                  <span>{item.value}</span>
                </li>
              {/each}
            </ul>
          {/if}
        </section>
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
    align-items: flex-start;
    gap: 1rem;
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  h3 {
    margin: 0;
    font-size: 1.5rem;
  }

  header p {
    color: rgba(226, 232, 240, 0.65);
    margin: 0.25rem 0 0;
  }

  .ghost {
    background: transparent;
    border: 1px solid rgba(148, 163, 184, 0.3);
    border-radius: 999px;
    padding: 0.4rem 0.7rem;
    cursor: pointer;
    color: rgba(226, 232, 240, 0.8);
  }

  .ghost:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 12px;
    padding: 0.55rem 0.8rem;
    min-width: 220px;
  }

  .status-pill.success { border-color: rgba(34, 197, 94, 0.35); }
  .status-pill.error { border-color: rgba(248, 113, 113, 0.35); }
  .status-pill.warning { border-color: rgba(251, 191, 36, 0.35); }
  .status-pill.loading { border-color: rgba(59, 130, 246, 0.35); }

  .status-icon {
    font-size: 1.25rem;
  }

  .status-text {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .status-text strong {
    font-size: 0.95rem;
  }

  .status-text time {
    font-size: 0.75rem;
    color: rgba(148, 163, 184, 0.7);
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

  .summary-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
  }

  .feedback-cues {
    background: rgba(17, 24, 39, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 14px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .feedback-cues h4 {
    margin: 0;
    font-size: 1rem;
  }

  .feedback-cues ul {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .feedback-cues li {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.6rem;
    align-items: center;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: rgba(148, 163, 184, 0.7);
  }

  .dot.success { background: rgba(34, 197, 94, 0.9); }
  .dot.error { background: rgba(248, 113, 113, 0.9); }
  .dot.warning { background: rgba(251, 191, 36, 0.95); }
  .dot.info { background: rgba(59, 130, 246, 0.9); }

  .cue-text {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .cue-text p {
    margin: 0;
    font-size: 0.9rem;
    color: rgba(226, 232, 240, 0.85);
  }

  .cue-text time {
    font-size: 0.75rem;
    color: rgba(148, 163, 184, 0.7);
  }

  .dismiss {
    background: transparent;
    border: none;
    color: rgba(148, 163, 184, 0.7);
    cursor: pointer;
    font-size: 1rem;
    border-radius: 0.5rem;
    padding: 0.1rem 0.3rem;
  }

  .dismiss:hover {
    background: rgba(148, 163, 184, 0.2);
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
    font-size: 1.4rem;
  }

  .metric-card .caption {
    font-size: 0.8rem;
    color: rgba(226, 232, 240, 0.55);
  }

  .content-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }

  @media (min-width: 1024px) {
    .content-grid {
      grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr);
    }
  }

  .capability-list ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .capability-list li {
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .cap-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .title {
    font-weight: 600;
  }

  .status {
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    padding: 0.25rem 0.5rem;
    border-radius: 999px;
    background: rgba(148, 163, 184, 0.15);
  }

  .status.operational { color: #4ade80; }
  .status.developing { color: #facc15; }

  .progress {
    width: 100%;
    height: 10px;
    background: rgba(15, 23, 42, 0.85);
    border-radius: 999px;
    overflow: hidden;
    border: 1px solid rgba(148, 163, 184, 0.2);
  }

  .bar {
    height: 100%;
    background: linear-gradient(90deg, #38bdf8 0%, #6366f1 100%);
  }

  .meta {
    display: flex;
    justify-content: space-between;
    color: rgba(226, 232, 240, 0.7);
    font-size: 0.85rem;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .sidebar section {
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.18);
    border-radius: 14px;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  h4 {
    margin: 0;
    font-size: 1rem;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .chip {
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    background: rgba(96, 165, 250, 0.15);
    border: 1px solid rgba(96, 165, 250, 0.25);
    font-size: 0.85rem;
  }

  .allocation-list,
  .improvements {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .allocation-list li,
  .improvements li,
  .meta-summary li {
    display: flex;
    justify-content: space-between;
    font-size: 0.9rem;
    color: rgba(226, 232, 240, 0.75);
  }

  .improvements .positive { color: #4ade80; }
  .improvements .negative { color: #f87171; }

  .meta-summary {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .meta-summary li span:last-child {
    font-weight: 600;
  }

  .empty {
    margin: 0;
    font-size: 0.9rem;
    color: rgba(226, 232, 240, 0.6);
  }

  @media (max-width: 1023px) {
    .content-grid {
      grid-template-columns: 1fr;
    }
    
    .sidebar {
      order: 1;
    }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
