<script>
  import { onMount, onDestroy } from 'svelte';
  import {
    apiHelpers,
    selfModificationState,
    pendingSelfModificationProposals,
    highRiskProposals,
    selfModificationAlerts,
    initCognitiveStream
  } from '../../stores/cognitive.js';
  import CapabilityAssessmentPanel from './CapabilityAssessmentPanel.svelte';
  import ProposalReviewPanel from './ProposalReviewPanel.svelte';
  import LiveCognitiveMonitor from './LiveCognitiveMonitor.svelte';
  import EvolutionTimelinePanel from './EvolutionTimelinePanel.svelte';

  let initializing = true;
  let refreshing = false;
  let errorMessage = null;
  let refreshInterval;
  let refreshIntervalMs = 45000;

  onMount(async () => {
    try {
      initCognitiveStream();
      await apiHelpers.initializeSelfModification();
      scheduleAutoRefresh();
    } catch (error) {
      console.error('[SelfModHub] Failed to initialize:', error);
      errorMessage = `Backend connection failed: ${error?.message || 'Unknown error'}. The self-modification service may not be available.`;
    } finally {
      initializing = false;
    }
  });

  onDestroy(() => {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
  });

  function scheduleAutoRefresh() {
    if (refreshInterval) {
      clearInterval(refreshInterval);
    }
    refreshInterval = setInterval(() => {
      apiHelpers.refreshSelfModification().catch((error) => {
        console.warn('Self-mod refresh failed:', error);
      });
    }, refreshIntervalMs);
  }

  async function handleManualRefresh() {
    if (refreshing) return;
    refreshing = true;
    try {
      await apiHelpers.refreshSelfModification();
    } catch (error) {
      console.warn('Manual refresh failed:', error);
      errorMessage = error?.message || 'Refresh failed. Try again shortly.';
    } finally {
      refreshing = false;
    }
  }

  const severityColors = {
    healthy: 'var(--green-500)',
    caution: 'var(--amber-500)',
    danger: 'var(--rose-500)'
  };

  $: state = $selfModificationState;
  $: alerts = $selfModificationAlerts;
  $: pending = $pendingSelfModificationProposals;
  $: highRisk = $highRiskProposals;

  // Debug logging
  $: {
    console.log('[SelfModHub] State updated:', {
      capabilities: state.capabilities?.length || 0,
      proposals: state.proposals?.length || 0,
      summary: state.summary,
      errors: state.errors,
      loading: state.loading
    });
  }

  $: capabilityLoading = state.loading.capabilities;
  $: proposalsLoading = state.loading.proposals;
  $: evolutionLoading = state.loading.evolution;
  $: liveLoading = state.loading.liveState;
</script>

<section class="self-modification-hub">
  <header class="hub-header">
    <div class="header-left">
      <div class="title-block">
        <h2>🛠️ Self-Modification Hub</h2>
        <p>Monitor GödelOS capability evolution, manage proposals, and track live cognition.</p>
      </div>
      <div class="health-cards">
        <article class="badge" style={`--accent:${severityColors.healthy}`}>
          <span class="label">Operational Capabilities</span>
          <strong>{state.summary.operational}/{state.summary.total}</strong>
        </article>
        <article class="badge" style={`--accent:${severityColors.caution}`}>
          <span class="label">Pending Approvals</span>
          <strong>{pending.length}</strong>
        </article>
        <article class="badge" style={`--accent:${severityColors.danger}`}>
          <span class="label">High-Risk Items</span>
          <strong>{highRisk.length}</strong>
        </article>
      </div>
    </div>
    <div class="header-actions">
      {#if state.lastUpdated.capabilities}
        <span class="timestamp">Updated {new Date(Math.max(...Object.values(state.lastUpdated).filter(Boolean))).toLocaleTimeString()}</span>
      {/if}
      <button class="refresh" class:spinning={refreshing} on:click={handleManualRefresh} disabled={refreshing}>
        {refreshing ? 'Refreshing…' : 'Refresh Data'}
      </button>
    </div>
  </header>

  {#if initializing}
    <div class="loading-state" data-testid="self-mod-loading">
      <div class="spinner"></div>
      <p>Loading self-modification data…</p>
    </div>
  {:else if errorMessage}
    <div class="error-state">
      <div class="error-icon">⚠️</div>
      <h3>Service Unavailable</h3>
      <p>{errorMessage}</p>
      <button class="retry-btn" on:click={handleManualRefresh}>Retry Connection</button>
    </div>
  {:else if state.capabilities.length === 0 && state.proposals.length === 0}
    <div class="empty-state">
      <div class="empty-icon">🛠️</div>
      <h3>No Data Available</h3>
      <p>The self-modification system is running but hasn't generated any capability assessments or proposals yet.</p>
      <p class="hint">Try interacting with the system or come back later.</p>
    </div>
  {:else}
    <div class="hub-grid">
      <CapabilityAssessmentPanel
        capabilities={state.capabilities}
        summary={state.summary}
        learningFocus={state.learningFocus}
        recentImprovements={state.recentImprovements}
        resourceAllocation={state.resourceAllocation}
        metacognitiveState={state.metacognitiveState}
        loading={capabilityLoading}
        onRefresh={handleManualRefresh}
      />

      <ProposalReviewPanel
        proposals={state.proposals}
        counts={state.proposalCounts}
        activeSimulation={state.activeSimulation}
        loading={proposalsLoading}
        onApprove={apiHelpers.approveSelfModificationProposal}
        onReject={apiHelpers.rejectSelfModificationProposal}
        onSimulate={apiHelpers.simulateSelfModificationProposal}
      />

      <LiveCognitiveMonitor
        liveState={state.liveState}
        loading={liveLoading}
      />

      <EvolutionTimelinePanel
        timeline={state.timeline}
        metrics={state.metrics}
        upcoming={state.upcoming}
        loading={evolutionLoading}
      />
    </div>
  {/if}
</section>

<style>
  :global(:root) {
    --panel-bg: rgba(17, 24, 39, 0.6);
    --panel-border: rgba(148, 163, 184, 0.2);
    --green-500: #22c55e;
    --amber-500: #f59e0b;
    --rose-500: #f43f5e;
  }

  .self-modification-hub {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
    padding: 1.5rem;
    background: linear-gradient(180deg, rgba(15, 23, 42, 0.85) 0%, rgba(15, 23, 42, 0.4) 100%);
    border-radius: 20px;
    border: 1px solid var(--panel-border);
    backdrop-filter: blur(12px);
    min-height: 100%;
  }

  .hub-header {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    justify-content: space-between;
    gap: 1rem;
  }

  .header-left {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .title-block h2 {
    font-size: 1.75rem;
    margin: 0;
  }

  .title-block p {
    margin: 0.25rem 0 0;
    color: rgba(226, 232, 240, 0.75);
  }

  .health-cards {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
  }

  .badge {
    padding: 0.75rem 1rem;
    border-radius: 14px;
    background: rgba(15, 23, 42, 0.75);
    border: 1px solid rgba(148, 163, 184, 0.25);
    min-width: 160px;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    position: relative;
  }

  .badge::before {
    content: "";
    position: absolute;
    inset: 0;
    border-radius: inherit;
    border: 1px solid currentColor;
    opacity: 0.35;
    pointer-events: none;
    color: var(--accent, rgba(148, 163, 184, 0.4));
  }

  .badge .label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(226, 232, 240, 0.8);
  }

  .badge strong {
    font-size: 1.4rem;
  }

  .header-actions {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 0.5rem;
    margin-left: auto;
  }

  .timestamp {
    font-size: 0.85rem;
    color: rgba(226, 232, 240, 0.6);
  }

  .refresh {
    background: rgba(59, 130, 246, 0.15);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #bfdbfe;
    padding: 0.5rem 1rem;
    border-radius: 999px;
    cursor: pointer;
    transition: transform 0.2s ease, background 0.2s ease;
  }

  .refresh:hover:not(:disabled) {
    transform: translateY(-1px);
    background: rgba(59, 130, 246, 0.25);
  }

  .refresh:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .refresh.spinning {
    position: relative;
  }

  .refresh.spinning::after {
    content: "";
    position: absolute;
    left: calc(50% - 0.75rem);
    top: calc(50% - 0.75rem);
    width: 1.5rem;
    height: 1.5rem;
    border-radius: 50%;
    border: 2px solid rgba(191, 219, 254, 0.4);
    border-top-color: rgba(191, 219, 254, 1);
    animation: spin 0.8s linear infinite;
  }

  .loading-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 2rem;
    min-height: 260px;
  }

  .error-state,
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 1rem;
    padding: 3rem 2rem;
    min-height: 300px;
    text-align: center;
    background: rgba(15, 23, 42, 0.4);
    border-radius: 16px;
    border: 1px solid rgba(148, 163, 184, 0.2);
  }

  .error-icon,
  .empty-icon {
    font-size: 3rem;
    opacity: 0.7;
  }

  .error-state h3,
  .empty-state h3 {
    margin: 0;
    font-size: 1.5rem;
  }

  .error-state p,
  .empty-state p {
    margin: 0.5rem 0 0;
    color: rgba(226, 232, 240, 0.7);
    max-width: 500px;
  }

  .empty-state .hint {
    font-size: 0.9rem;
    color: rgba(226, 232, 240, 0.5);
    font-style: italic;
  }

  .retry-btn {
    margin-top: 1rem;
    padding: 0.75rem 1.5rem;
    background: rgba(59, 130, 246, 0.2);
    border: 1px solid rgba(59, 130, 246, 0.4);
    color: #bfdbfe;
    border-radius: 999px;
    cursor: pointer;
    transition: all 0.2s ease;
  }

  .retry-btn:hover {
    background: rgba(59, 130, 246, 0.3);
    transform: translateY(-1px);
  }

  .spinner {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    border: 6px solid rgba(59, 130, 246, 0.25);
    border-top-color: rgba(59, 130, 246, 0.85);
    animation: spin 1s linear infinite;
  }

  .hub-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 1.5rem;
  }

  @media (min-width: 1200px) {
    .hub-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (min-width: 1600px) {
    .hub-grid {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
