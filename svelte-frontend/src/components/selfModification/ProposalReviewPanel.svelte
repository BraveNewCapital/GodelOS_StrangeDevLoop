<script>
  import { onMount } from 'svelte';

  export let proposals = [];
  export let counts = {};
  export let activeSimulation = null;
  export let loading = false;
  export let onApprove = async () => {};
  export let onReject = async () => {};
  export let onSimulate = async () => {};
  export let status = { state: 'idle', message: 'Standing by for updates.', updatedAt: null, meta: {} };
  export let feedbackEntries = [];
  export let pushFeedback = null;
  export let dismissFeedback = null;

  let selectedProposal = null;
  let actionState = {};
  let message = null;

  const statusColors = {
    pending: 'var(--amber-400)',
    approved: 'var(--emerald-400)',
    rejected: 'var(--rose-400)',
    under_review: 'var(--sky-400)'
  };

  const panelStatusIcons = {
    loading: '⏳',
    success: '✅',
    error: '⚠️',
    warning: '⚠️',
    info: 'ℹ️',
    idle: '•'
  };

  const riskColors = {
    low: 'var(--emerald-400)',
    medium: 'var(--amber-400)',
    high: 'var(--rose-400)'
  };

  onMount(() => {
    if (!selectedProposal && proposals.length) {
      selectedProposal = proposals[0];
    }
  });

  $: if (proposals.length && !selectedProposal) {
    selectedProposal = proposals[0];
  }

  $: if (selectedProposal) {
    const updated = proposals.find((proposal) => proposal.id === selectedProposal.id);
    if (updated) {
      selectedProposal = updated;
    }
  }

  function statusLabel(status) {
    if (!status) return 'unknown';
    return status.replace(/_/g, ' ');
  }

  async function handleApprove(proposal) {
    if (!proposal) return;
    actionState = { ...actionState, [proposal.id]: 'approve' };
    try {
      await onApprove(proposal.id);
      message = `✅ Proposal "${proposal.title}" approved.`;
      if (typeof pushFeedback === 'function') {
        pushFeedback('success', `Approved "${proposal.title}"`, { proposalId: proposal.id, action: 'approve' });
      }
    } catch (error) {
      console.error('Approval failed:', error);
      message = `⚠️ Approval failed: ${error?.message || 'Unexpected error'}`;
      if (typeof pushFeedback === 'function') {
        pushFeedback('error', `Approval failed: ${error?.message || 'Unexpected error'}`, { proposalId: proposal.id, action: 'approve' });
      }
    } finally {
      actionState = { ...actionState, [proposal.id]: null };
    }
  }

  async function handleReject(proposal) {
    if (!proposal) return;
    const reason = window.prompt('Provide a short rejection note (optional):', '') || null;
    actionState = { ...actionState, [proposal.id]: 'reject' };
    try {
      await onReject(proposal.id, reason);
      message = `🚫 Proposal "${proposal.title}" rejected.`;
      if (typeof pushFeedback === 'function') {
        pushFeedback('warning', `Rejected "${proposal.title}"`, { proposalId: proposal.id, action: 'reject', reason });
      }
    } catch (error) {
      console.error('Rejection failed:', error);
      message = `⚠️ Rejection failed: ${error?.message || 'Unexpected error'}`;
      if (typeof pushFeedback === 'function') {
        pushFeedback('error', `Rejection failed: ${error?.message || 'Unexpected error'}`, { proposalId: proposal.id, action: 'reject' });
      }
    } finally {
      actionState = { ...actionState, [proposal.id]: null };
    }
  }

  async function handleSimulate(proposal) {
    if (!proposal) return;
    actionState = { ...actionState, [proposal.id]: 'simulate' };
    try {
      await onSimulate(proposal.id);
      if (typeof pushFeedback === 'function') {
        pushFeedback('info', `Simulation requested for "${proposal.title}"`, { proposalId: proposal.id, action: 'simulate' });
      }
    } catch (error) {
      console.error('Simulation failed:', error);
      message = `⚠️ Simulation failed: ${error?.message || 'Unexpected error'}`;
      if (typeof pushFeedback === 'function') {
        pushFeedback('error', `Simulation failed: ${error?.message || 'Unexpected error'}`, { proposalId: proposal.id, action: 'simulate' });
      }
    } finally {
      actionState = { ...actionState, [proposal.id]: null };
    }
  }

  function isBusy(proposal, action) {
    if (!proposal) return false;
    return actionState[proposal.id] === action;
  }

  function riskBadgeColor(riskLevel = 'unknown') {
    return riskColors[riskLevel.toLowerCase()] || 'rgba(148, 163, 184, 0.6)';
  }

  function formatBenefitDelta(benefits = {}) {
    const deltas = [];
    Object.entries(benefits.capability_delta || {}).forEach(([key, value]) => {
      deltas.push(`${key.replace(/_/g, ' ')} ${value >= 0 ? '+' : ''}${(value * 100).toFixed(1)}%`);
    });
    if (typeof benefits.accuracy === 'number') {
      deltas.push(`Accuracy ${benefits.accuracy >= 0 ? '+' : ''}${(benefits.accuracy * 100).toFixed(1)}%`);
    }
    if (typeof benefits.latency === 'number') {
      deltas.push(`Latency ${(benefits.latency * 100).toFixed(1)}%`);
    }
    return deltas.length ? deltas.join(', ') : 'No quantified benefits available.';
  }
</script>

<article class="panel" data-testid="proposal-panel">
  <header>
    <div class="header-left">
      <div>
        <h3>Proposal Review</h3>
        <p>Assess, simulate, and approve metacognitive modifications.</p>
      </div>
      <div class={`status-pill ${status.state}`}>
        <span class="status-icon">{panelStatusIcons[status.state] || panelStatusIcons.info}</span>
        <div class="status-text">
          <strong>{status.message}</strong>
          {#if status.updatedAt}
            <time>{new Date(status.updatedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
          {/if}
        </div>
      </div>
    </div>
    <div class="header-right">
      <div class="counts">
        <span>Pending <strong>{counts.pending ?? 0}</strong></span>
        <span>Approved <strong>{counts.approved ?? 0}</strong></span>
        <span>Rejected <strong>{counts.rejected ?? 0}</strong></span>
      </div>
    </div>
  </header>

  {#if message}
    <div class="message" role="alert">
      <span>{message}</span>
      <button
        type="button"
        class="dismiss"
        on:click={() => (message = null)}
        aria-label="Dismiss notification"
      >
        ✕
      </button>
    </div>
  {/if}

  {#if feedbackEntries?.length}
    <aside class="feedback-cues" aria-live="polite">
      <h4>Recent Decisions</h4>
      <ul>
        {#each feedbackEntries as entry (entry.id)}
          <li>
            <span class={`dot ${entry.type}`}></span>
            <div class="cue-text">
              <p>{entry.message}</p>
              <time>{new Date(entry.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
            </div>
            {#if typeof dismissFeedback === 'function'}
              <button class="cue-dismiss" type="button" on:click={() => dismissFeedback(entry.id)} aria-label="Dismiss cue">✕</button>
            {/if}
          </li>
        {/each}
      </ul>
    </aside>
  {/if}

  {#if loading}
    <div class="loading">
      <div class="spinner"></div>
      <p>Loading proposal portfolio…</p>
    </div>
  {:else}
    {#if proposals.length === 0}
      <p class="empty">No proposals available. Initiate a new metacognitive plan to populate this workspace.</p>
    {:else}
      <div class="proposal-layout">
        <aside>
          <ul>
            {#each proposals as proposal}
              <li class:selected={selectedProposal && selectedProposal.id === proposal.id}>
                <button
                  type="button"
                  class="proposal-button"
                  on:click={() => (selectedProposal = proposal)}
                >
                  <div class="title-row">
                    <strong>{proposal.title}</strong>
                    <span class="status" style={`--status:${statusColors[(proposal.status || '').toLowerCase()] || 'rgba(148,163,184,0.8)'}`}>{statusLabel(proposal.status)}</span>
                  </div>
                  <div class="meta">
                    <span>Priority #{proposal.priorityRank}</span>
                    <span class="risk" style={`--risk:${riskBadgeColor(proposal.riskLevel)}`}>{proposal.riskLevel || 'unknown'}</span>
                  </div>
                </button>
              </li>
            {/each}
          </ul>
        </aside>

        <section class="details" aria-live="polite">
          {#if selectedProposal}
            <header class="detail-header">
              <div>
                <h4>{selectedProposal.title}</h4>
                <p>Focus Areas: {selectedProposal.focusAreas?.length ? selectedProposal.focusAreas.join(', ') : '—'}</p>
              </div>
              <div class="risk-pill" style={`--risk:${riskBadgeColor(selectedProposal.riskLevel)}`}>
                Risk: {selectedProposal.riskLevel || 'unknown'}
              </div>
            </header>

            <section class="detail-grid">
              <div>
                <h5>Expected Benefits</h5>
                <p>{formatBenefitDelta(selectedProposal.expectedBenefits)}</p>
              </div>
              <div>
                <h5>Potential Risks</h5>
                <ul class="risks">
                  {#if selectedProposal.potentialRisks && Object.keys(selectedProposal.potentialRisks).length}
                    {#each Object.entries(selectedProposal.potentialRisks) as [key, risk]}
                      <li><span>{key.replace(/_/g, ' ')}</span><span>{risk}</span></li>
                    {/each}
                  {:else}
                    <li>No explicit risks captured.</li>
                  {/if}
                </ul>
              </div>
              <div>
                <h5>Monitoring Requirements</h5>
                <ul class="requirements">
                  {#if selectedProposal.monitoringRequirements?.length}
                    {#each selectedProposal.monitoringRequirements as requirement}
                      <li>{requirement}</li>
                    {/each}
                  {:else}
                    <li>No monitoring plan specified.</li>
                  {/if}
                </ul>
              </div>
            </section>

            <footer class="actions">
              <button class="secondary" on:click={() => handleSimulate(selectedProposal)} disabled={isBusy(selectedProposal, 'simulate')}>
                {isBusy(selectedProposal, 'simulate') ? 'Simulating…' : 'Run Simulation'}
              </button>
              <div class="primary-actions">
                <button class="danger" on:click={() => handleReject(selectedProposal)} disabled={isBusy(selectedProposal, 'reject')}>
                  {isBusy(selectedProposal, 'reject') ? 'Rejecting…' : 'Reject'}
                </button>
                <button class="success" on:click={() => handleApprove(selectedProposal)} disabled={isBusy(selectedProposal, 'approve')}>
                  {isBusy(selectedProposal, 'approve') ? 'Approving…' : 'Approve'}
                </button>
              </div>
            </footer>

            {#if activeSimulation && activeSimulation.proposal && activeSimulation.proposal.id === selectedProposal.id}
              <section class="simulation" data-testid="proposal-simulation">
                <header>
                  <h5>Simulation Preview</h5>
                  <span>Confidence {Math.round((activeSimulation.confidence || 0) * 100)}%</span>
                </header>
                <ul>
                  {#each activeSimulation.projectedCapabilities as capability}
                    <li>
                      <span>{capability.label}</span>
                      <div class="projection">
                        <span>{Math.round(capability.currentLevel * 100)}%</span>
                        <span>→</span>
                        <strong>{Math.round(capability.projectedLevel * 100)}%</strong>
                        <span class={capability.delta >= 0 ? 'positive' : 'negative'}>
                          {capability.delta >= 0 ? '+' : ''}{(capability.delta * 100).toFixed(1)}%
                        </span>
                      </div>
                    </li>
                  {/each}
                </ul>
              </section>
            {/if}
          {/if}
        </section>
      </div>
    {/if}
  {/if}
</article>

<style>
  :global(:root) {
    --emerald-400: #34d399;
    --amber-400: #fbbf24;
    --rose-400: #fb7185;
    --sky-400: #38bdf8;
  }

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

  .header-right {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    align-items: flex-end;
  }

  header h3 {
    margin: 0;
    font-size: 1.45rem;
  }

  header p {
    margin: 0.25rem 0 0;
    color: rgba(226, 232, 240, 0.65);
  }

  .counts {
    display: flex;
    gap: 1rem;
    font-size: 0.9rem;
    color: rgba(226, 232, 240, 0.7);
  }

  .counts strong {
    font-size: 1.1rem;
    margin-left: 0.35rem;
  }

  .status-pill {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 12px;
    padding: 0.6rem 0.85rem;
    min-width: 220px;
  }

  .status-pill.success { border-color: rgba(34, 197, 94, 0.35); }
  .status-pill.error { border-color: rgba(248, 113, 113, 0.35); }
  .status-pill.warning { border-color: rgba(251, 191, 36, 0.35); }
  .status-pill.loading { border-color: rgba(59, 130, 246, 0.35); }

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

  .message {
    padding: 0.75rem 1rem;
    border-radius: 12px;
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.3);
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .message .dismiss {
    border: none;
    background: transparent;
    color: rgba(191, 219, 254, 0.9);
    cursor: pointer;
    font-size: 1rem;
    padding: 0.1rem 0.3rem;
    border-radius: 0.5rem;
  }

  .message .dismiss:hover {
    background: rgba(59, 130, 246, 0.2);
  }

  .feedback-cues {
    margin: 0.75rem 0 0;
    background: rgba(17, 24, 39, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 14px;
    padding: 0.9rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
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

  .dot.success { background: rgba(34, 197, 94, 0.85); }
  .dot.error { background: rgba(248, 113, 113, 0.9); }
  .dot.warning { background: rgba(251, 191, 36, 0.95); }
  .dot.info { background: rgba(59, 130, 246, 0.85); }

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

  .empty {
    color: rgba(226, 232, 240, 0.6);
    margin: 0;
  }

  .proposal-layout {
    display: grid;
    grid-template-columns: minmax(0, 1.3fr) minmax(0, 2fr);
    gap: 1.5rem;
  }

  aside {
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    overflow: hidden;
  }

  aside ul {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  aside li {
    border-bottom: 1px solid rgba(148, 163, 184, 0.12);
  }

  aside li:last-child {
    border-bottom: none;
  }

  aside li.selected .proposal-button {
    background: rgba(59, 130, 246, 0.18);
    border-left: 3px solid rgba(59, 130, 246, 0.9);
  }

  .proposal-button {
    width: 100%;
    text-align: left;
    background: transparent;
    border: none;
    color: inherit;
    padding: 1rem 1.1rem;
    cursor: pointer;
    display: block;
    transition: background 0.2s ease;
  }

  .proposal-button:hover,
  .proposal-button:focus-visible {
    background: rgba(30, 41, 59, 0.6);
    outline: none;
  }

  .proposal-button:focus-visible {
    box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.45);
  }

  .title-row {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .status {
    text-transform: uppercase;
    font-size: 0.65rem;
    letter-spacing: 0.12em;
    padding: 0.2rem 0.45rem;
    border-radius: 999px;
    border: 1px solid rgba(255, 255, 255, 0.2);
    background: rgba(15, 23, 42, 0.55);
    color: var(--status, rgba(226, 232, 240, 0.85));
  }

  .meta {
    display: flex;
    justify-content: space-between;
    margin-top: 0.5rem;
    font-size: 0.8rem;
    color: rgba(226, 232, 240, 0.6);
  }

  .risk {
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-weight: 600;
    color: var(--risk);
  }

  .details {
    background: rgba(15, 23, 42, 0.55);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 14px;
    padding: 1.25rem;
    display: flex;
    flex-direction: column;
    gap: 1.25rem;
  }

  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 1rem;
  }

  .detail-header h4 {
    margin: 0;
    font-size: 1.35rem;
  }

  .detail-header p {
    margin: 0.25rem 0 0;
    color: rgba(226, 232, 240, 0.6);
  }

  .risk-pill {
    padding: 0.35rem 0.75rem;
    border-radius: 999px;
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.25);
    color: var(--risk);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: 0.75rem;
  }

  .detail-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 1rem;
  }

  h5 {
    margin: 0 0 0.5rem;
    font-size: 0.95rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(226, 232, 240, 0.7);
  }

  .risks,
  .requirements {
    list-style: none;
    padding: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    color: rgba(226, 232, 240, 0.75);
  }

  .risks li,
  .requirements li {
    display: flex;
    justify-content: space-between;
    gap: 0.75rem;
  }

  .actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
  }

  .primary-actions {
    display: flex;
    gap: 0.75rem;
  }

  button {
    border-radius: 999px;
    padding: 0.5rem 1.1rem;
    border: 1px solid transparent;
    cursor: pointer;
    transition: transform 0.18s ease;
  }

  button:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  button:hover:not(:disabled) {
    transform: translateY(-1px);
  }

  .secondary {
    background: rgba(96, 165, 250, 0.15);
    border-color: rgba(96, 165, 250, 0.3);
    color: rgba(191, 219, 254, 0.95);
  }

  .danger {
    background: rgba(248, 113, 113, 0.1);
    border-color: rgba(248, 113, 113, 0.35);
    color: #fca5a5;
  }

  .success {
    background: rgba(52, 211, 153, 0.18);
    border-color: rgba(16, 185, 129, 0.4);
    color: #bbf7d0;
  }

  .simulation {
    background: rgba(15, 23, 42, 0.6);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 14px;
    padding: 1rem;
  }

  .simulation header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .simulation ul {
    list-style: none;
    padding: 0;
    margin: 1rem 0 0;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .simulation li {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .projection {
    display: flex;
    gap: 0.5rem;
    align-items: center;
    font-size: 0.9rem;
  }

  .projection strong {
    font-size: 1rem;
  }

  .projection .positive { color: #4ade80; }
  .projection .negative { color: #f87171; }

  @media (max-width: 1024px) {
    .proposal-layout {
      grid-template-columns: 1fr;
    }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
