<script>
  const STATUS_ICONS = {
    success: '✅',
    error: '⚠️',
    warning: '⚠️',
    loading: '⏳',
    info: 'ℹ️',
    idle: '•'
  };

  const DEFAULT_STATUS = {
    state: 'idle',
    message: 'Standing by for updates.',
    updatedAt: null,
    meta: {}
  };

  const METRIC_LABELS = {
    total_events: 'Total Events',
    average_impact: 'Average Impact',
    active_initiatives: 'Active Initiatives',
    momentum_score: 'Momentum Score',
    cadence_score: 'Cadence Score',
    stability_index: 'Stability Index'
  };

  export let timeline = [];
  export let metrics = {};
  export let upcoming = [];
  export let loading = false;
  export let status = DEFAULT_STATUS;
  export let feedbackEntries = [];
  export let pushFeedback = null;
  export let dismissFeedback = null;

  $: computedStatus = { ...DEFAULT_STATUS, ...(status || {}) };
  $: sortedTimeline = Array.isArray(timeline)
    ? [...timeline].sort((a, b) => {
        const aTime = a?.timestamp ? new Date(a.timestamp).getTime() : 0;
        const bTime = b?.timestamp ? new Date(b.timestamp).getTime() : 0;
        return bTime - aTime;
      })
    : [];
  $: visibleTimeline = sortedTimeline.slice(0, 8);
  $: visibleUpcoming = Array.isArray(upcoming) ? upcoming.slice(0, 5) : [];
  $: hasMetrics = metrics && Object.keys(metrics).length > 0;

  function formatTimestamp(timestamp, mode = 'datetime') {
    if (!timestamp) return '—';
    try {
      const date = new Date(timestamp);
      if (Number.isNaN(date.getTime())) throw new Error('Invalid date');
      if (mode === 'time') {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      }
      if (mode === 'date') {
        return date.toLocaleDateString();
      }
      return date.toLocaleString([], { dateStyle: 'short', timeStyle: 'short' });
    } catch (error) {
      console.warn('[EvolutionTimelinePanel] Failed to parse timestamp', timestamp, error);
      return typeof timestamp === 'string' ? timestamp : '—';
    }
  }

  function formatMetricLabel(key) {
    if (!key) return 'Metric';
    return METRIC_LABELS[key] || key.replace(/_/g, ' ');
  }

  function normalizeNumber(value) {
    if (typeof value !== 'number' || Number.isNaN(value)) return null;
    if (Math.abs(value) < 1) return Number((value * 100).toFixed(1));
    return Number(value.toFixed(2));
  }

  function formatMetricValue(value) {
    if (value == null) return '—';
    if (typeof value === 'number') {
      const normalized = normalizeNumber(value);
      if (normalized == null) return '—';
      if (Math.abs(value) < 1) {
        return `${normalized}%`;
      }
      return normalized;
    }
    if (typeof value === 'object') {
      if (value.percentage != null) {
        return `${Math.round(Math.max(0, Math.min(1, value.percentage)) * 100)}%`;
      }
      if (value.value != null) {
        return formatMetricValue(value.value);
      }
      if (value.delta != null) {
        const delta = normalizeNumber(value.delta);
        return `${delta >= 0 ? '+' : ''}${delta}`;
      }
      return JSON.stringify(value);
    }
    return String(value);
  }

  function getImpactEntries(event) {
    if (!event || !event.impact) return [];
    const impact = event.impact;
    if (Array.isArray(impact)) {
      return impact.map((item, index) => ({
        label: item?.label || item?.metric || `Impact ${index + 1}`,
        value: item?.value ?? item?.delta ?? item ?? ''
      }));
    }
    if (typeof impact === 'object') {
      return Object.entries(impact).map(([key, value]) => ({
        label: key.replace(/_/g, ' '),
        value
      }));
    }
    return [{ label: 'Impact', value: impact }];
  }

  function formatEta(value) {
    if (!value) return 'TBD';
    if (typeof value === 'string') return value;
    if (value.quarter) return value.quarter;
    if (value.targetQuarter) return value.targetQuarter;
    if (value.expected) return value.expected;
    if (value.window) return value.window;
    return String(value);
  }

  function categoryLabel(category) {
    if (!category) return 'general';
    return category.replace(/_/g, ' ');
  }

  function statusIcon(state) {
    return STATUS_ICONS[state] || STATUS_ICONS.info;
  }

  function handleEventInsight(event) {
    if (typeof pushFeedback !== 'function' || !event) return;
    pushFeedback('info', `Logged evolution event: ${event.label || 'Timeline update'}.`, {
      origin: 'EvolutionTimelinePanel',
      eventId: event.id || event.timestamp || Math.random().toString(36).slice(2, 8)
    });
  }

  function handleUpcomingPin(item, index) {
    if (typeof pushFeedback !== 'function' || !item) return;
    pushFeedback('info', `Pinned upcoming initiative: ${item.title || item.label || 'Initiative'}.`, {
      origin: 'EvolutionTimelinePanel',
      initiativeId: item.id || item.title || index
    });
  }
</script>

<article class="panel" data-testid="evolution-panel">
  <header>
    <div class="header-left">
      <div>
        <h3>Evolution Timeline</h3>
        <p>Track capability evolution checkpoints and queued initiatives.</p>
      </div>
      <div class={`status-pill ${computedStatus.state}`}>
        <span class="status-icon">{statusIcon(computedStatus.state)}</span>
        <div class="status-text">
          <strong>{computedStatus.message}</strong>
          {#if computedStatus.updatedAt}
            <time>{formatTimestamp(computedStatus.updatedAt, 'time')}</time>
          {/if}
        </div>
      </div>
    </div>

    {#if feedbackEntries?.length}
      <aside class="feedback-cues" aria-live="polite">
        <h4>Recent Signals</h4>
        <ul>
          {#each feedbackEntries as entry (entry.id)}
            <li>
              <span class={`dot ${entry.type}`}></span>
              <div class="cue-text">
                <p>{entry.message}</p>
                <time>{formatTimestamp(entry.timestamp, 'time')}</time>
              </div>
              {#if typeof dismissFeedback === 'function'}
                <button
                  class="cue-dismiss"
                  type="button"
                  on:click={() => dismissFeedback(entry.id)}
                  aria-label="Dismiss cue"
                >
                  ✕
                </button>
              {/if}
            </li>
          {/each}
        </ul>
      </aside>
    {/if}
  </header>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Fetching evolution history…</p>
    </div>
  {:else}
    <section class="metrics">
      {#if !hasMetrics}
        <p class="empty">No aggregate evolution metrics available.</p>
      {:else}
        {#each Object.entries(metrics) as [key, value]}
          <div class="metric-card">
            <span class="label">{formatMetricLabel(key)}</span>
            <strong>{formatMetricValue(value)}</strong>
          </div>
        {/each}
      {/if}
    </section>

    <section class="timeline">
      <div class="section-header">
        <h4>Recent Events</h4>
        {#if computedStatus.meta?.activeWindow}
          <span class="section-meta">Active window · {computedStatus.meta.activeWindow}</span>
        {:else if computedStatus.meta?.lastEvent}
          <span class="section-meta">Last · {computedStatus.meta.lastEvent}</span>
        {/if}
      </div>
      {#if visibleTimeline.length === 0}
        <p class="empty">No evolution events recorded yet.</p>
      {:else}
        <ul>
          {#each visibleTimeline as event, index (event.id || event.timestamp || index)}
            <li>
              <div class="marker"></div>
              <div class="content">
                <div class="content-header">
                  <h5>{event.label || 'Evolution Update'}</h5>
                  <span class="event-time">{formatTimestamp(event.timestamp)}</span>
                </div>
                <p class="meta">
                  <span class="category">{categoryLabel(event.category)}</span>
                  {#if event.confidence != null}
                    <span>Confidence {formatMetricValue(event.confidence)}</span>
                  {/if}
                </p>
                {#if event.summary || event.description}
                  <p class="description">{event.summary || event.description}</p>
                {/if}
                {#if getImpactEntries(event).length}
                  <ul class="impact">
                    {#each getImpactEntries(event) as item, impactIndex}
                      <li>
                        <span>{item.label}</span>
                        <span>{formatMetricValue(item.value)}</span>
                      </li>
                    {/each}
                  </ul>
                {/if}
                {#if typeof pushFeedback === 'function'}
                  <div class="event-actions">
                    <button class="event-feedback" type="button" on:click={() => handleEventInsight(event)}>
                      Log insight
                    </button>
                  </div>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="upcoming">
      <div class="section-header">
        <h4>Upcoming Initiatives</h4>
        {#if computedStatus.meta?.pipelineCount != null}
          <span class="section-meta">{computedStatus.meta.pipelineCount} in pipeline</span>
        {/if}
      </div>
      {#if visibleUpcoming.length === 0}
        <p class="empty">No upcoming initiatives scheduled.</p>
      {:else}
        <ul>
          {#each visibleUpcoming as item, index (item.id || item.title || index)}
            <li>
              <div class="upcoming-details">
                <strong>{item.title || item.label || 'Planned Initiative'}</strong>
                {#if item.summary || item.description}
                  <p>{item.summary || item.description}</p>
                {:else if item.focus}
                  <p>Focus: {Array.isArray(item.focus) ? item.focus.join(', ') : item.focus}</p>
                {/if}
                {#if item.owner}
                  <span class="owner">Owner · {item.owner}</span>
                {/if}
              </div>
              <div class="upcoming-meta">
                <span class="eta">{formatEta(item.target_quarter || item.targetQuarter || item.eta)}</span>
                {#if item.confidence != null || item.probability != null}
                  <span class="confidence">{formatMetricValue(item.confidence ?? item.probability)}</span>
                {/if}
                {#if typeof pushFeedback === 'function'}
                  <button class="event-feedback" type="button" on:click={() => handleUpcomingPin(item, index)}>
                    Pin update
                  </button>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
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
    flex-wrap: wrap;
    justify-content: space-between;
    align-items: stretch;
    gap: 1rem;
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    min-width: 240px;
  }

  header h3 {
    margin: 0;
    font-size: 1.45rem;
  }

  header p {
    margin: 0.35rem 0 0;
    color: rgba(226, 232, 240, 0.65);
  }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 0.65rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 12px;
    padding: 0.55rem 0.85rem;
    min-width: 220px;
  }

  .status-pill.success {
    border-color: rgba(34, 197, 94, 0.35);
  }

  .status-pill.error {
    border-color: rgba(248, 113, 113, 0.35);
  }

  .status-pill.warning {
    border-color: rgba(251, 191, 36, 0.35);
  }

  .status-pill.loading {
    border-color: rgba(59, 130, 246, 0.35);
  }

  .status-icon {
    font-size: 1.2rem;
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

  .feedback-cues {
    background: rgba(17, 24, 39, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 14px;
    padding: 0.9rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
    min-width: 220px;
    max-width: 280px;
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
    gap: 0.55rem;
  }

  .feedback-cues li {
    display: grid;
    grid-template-columns: auto 1fr auto;
    gap: 0.55rem;
    align-items: center;
  }

  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: rgba(148, 163, 184, 0.7);
  }

  .dot.success {
    background: rgba(34, 197, 94, 0.85);
  }

  .dot.error {
    background: rgba(248, 113, 113, 0.9);
  }

  .dot.warning {
    background: rgba(251, 191, 36, 0.95);
  }

  .dot.info {
    background: rgba(59, 130, 246, 0.85);
  }

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

  .cue-dismiss {
    background: transparent;
    border: none;
    color: rgba(148, 163, 184, 0.7);
    cursor: pointer;
    font-size: 1rem;
    border-radius: 0.5rem;
    padding: 0.1rem 0.3rem;
  }

  .cue-dismiss:hover {
    background: rgba(148, 163, 184, 0.2);
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
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1rem;
  }

  .metric-card {
    background: rgba(30, 41, 59, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 0.85rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .metric-card .label {
    text-transform: uppercase;
    font-size: 0.7rem;
    letter-spacing: 0.08em;
    color: rgba(226, 232, 240, 0.6);
  }

  .metric-card strong {
    font-size: 1.25rem;
  }

  .section-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .section-header h4 {
    margin: 0;
  }

  .section-meta {
    font-size: 0.8rem;
    color: rgba(148, 163, 184, 0.7);
  }

  .timeline ul,
  .upcoming ul {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .timeline li {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: 0.75rem;
  }

  .marker {
    width: 10px;
    border-radius: 999px;
    background: linear-gradient(180deg, #38bdf8, #6366f1);
  }

  .content {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 0.85rem;
    display: flex;
    flex-direction: column;
    gap: 0.45rem;
  }

  .content-header {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 0.75rem;
  }

  .content h5 {
    margin: 0;
    font-size: 1.05rem;
  }

  .event-time {
    font-size: 0.8rem;
    color: rgba(226, 232, 240, 0.6);
  }

  .meta {
    display: flex;
    justify-content: space-between;
    font-size: 0.8rem;
    color: rgba(226, 232, 240, 0.6);
  }

  .category {
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .description {
    margin: 0;
    color: rgba(226, 232, 240, 0.82);
    font-size: 0.9rem;
  }

  .impact {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    font-size: 0.85rem;
    color: rgba(226, 232, 240, 0.75);
  }

  .impact li {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
  }

  .event-actions {
    display: flex;
    justify-content: flex-end;
    margin-top: 0.5rem;
  }

  .event-feedback {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: rgba(191, 219, 254, 0.95);
    border-radius: 10px;
    padding: 0.3rem 0.75rem;
    font-size: 0.8rem;
    cursor: pointer;
    transition: background 0.2s ease;
  }

  .event-feedback:hover {
    background: rgba(59, 130, 246, 0.25);
  }

  .upcoming li {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 0.85rem 1rem;
  }

  .upcoming-details {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }

  .upcoming-details p {
    margin: 0;
    color: rgba(226, 232, 240, 0.6);
  }

  .owner {
    font-size: 0.75rem;
    color: rgba(148, 163, 184, 0.7);
  }

  .upcoming-meta {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
  }

  .eta {
    align-self: flex-end;
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    font-size: 0.8rem;
  }

  .confidence {
    font-size: 0.75rem;
    color: rgba(148, 163, 184, 0.7);
  }

  .empty {
    color: rgba(226, 232, 240, 0.6);
    margin: 0;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 960px) {
    header {
      flex-direction: column;
    }

    .feedback-cues {
      max-width: none;
      width: 100%;
    }

    .upcoming li {
      flex-direction: column;
      align-items: flex-start;
    }

    .upcoming-meta {
      align-items: flex-start;
    }
  }
</style>
