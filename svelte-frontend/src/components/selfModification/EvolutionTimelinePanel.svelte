<script>
  export let timeline = [];
  export let metrics = {};
  export let upcoming = [];
  export let loading = false;

  function formatTimestamp(timestamp) {
    if (!timestamp) return 'unknown';
    try {
      return new Date(timestamp).toLocaleString();
    } catch (error) {
      return timestamp;
    }
  }
</script>

<article class="panel" data-testid="evolution-panel">
  <header>
    <div>
      <h3>Evolution Timeline</h3>
      <p>Track capability evolution checkpoints and queued initiatives.</p>
    </div>
  </header>

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Fetching evolution history…</p>
    </div>
  {:else}
    <section class="metrics">
      {#if Object.keys(metrics || {}).length === 0}
        <p class="empty">No aggregate evolution metrics available.</p>
      {:else}
        {#each Object.entries(metrics) as [key, value]}
          <div class="metric-card">
            <span class="label">{key.replace(/_/g, ' ')}</span>
            <strong>{typeof value === 'number' ? value : JSON.stringify(value)}</strong>
          </div>
        {/each}
      {/if}
    </section>

    <section class="timeline">
      <h4>Recent Events</h4>
      {#if timeline.length === 0}
        <p class="empty">No evolution events recorded yet.</p>
      {:else}
        <ul>
          {#each timeline.slice(0, 8) as event}
            <li>
              <div class="marker"></div>
              <div class="content">
                <h5>{event.label}</h5>
                <p class="meta">
                  <span class="category">{event.category}</span>
                  <span>{formatTimestamp(event.timestamp)}</span>
                </p>
                {#if event.impact && Object.keys(event.impact).length}
                  <ul class="impact">
                    {#each Object.entries(event.impact) as [key, value]}
                      <li><span>{key.replace(/_/g, ' ')}</span><span>{value}</span></li>
                    {/each}
                  </ul>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {/if}
    </section>

    <section class="upcoming">
      <h4>Upcoming Initiatives</h4>
      {#if upcoming.length === 0}
        <p class="empty">No upcoming initiatives scheduled.</p>
      {:else}
        <ul>
          {#each upcoming.slice(0, 5) as item}
            <li>
              <div>
                <strong>{item.title || item.label || 'Planned Initiative'}</strong>
                <p>{item.summary || item.description || 'Pending rollout details.'}</p>
              </div>
              <span class="eta">{item.target_quarter || item.targetQuarter || 'TBD'}</span>
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

  header h3 {
    margin: 0;
    font-size: 1.45rem;
  }

  header p {
    margin: 0.35rem 0 0;
    color: rgba(226, 232, 240, 0.65);
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

  .content h5 {
    margin: 0;
    font-size: 1.05rem;
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

  .upcoming li {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 0.85rem 1rem;
  }

  .upcoming p {
    margin: 0.25rem 0 0;
    color: rgba(226, 232, 240, 0.6);
  }

  .eta {
    align-self: center;
    padding: 0.35rem 0.65rem;
    border-radius: 999px;
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    font-size: 0.8rem;
  }

  .empty {
    color: rgba(226, 232, 240, 0.6);
    margin: 0;
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
