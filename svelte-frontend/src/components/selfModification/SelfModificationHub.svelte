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
      console.error('Failed to initialize self-modification hub:', error);
      errorMessage = error?.message || 'Unable to load self-modification data.';
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

  {#if errorMessage}
    <div class="error-banner">
      <span>⚠️ {errorMessage}</span>
      <button on:click={() => errorMessage = null}>Dismiss</button>
    </div>
  {/if}

  {#if initializing}
    <div class="loading-state" data-testid="self-mod-loading">
      <div class="spinner"></div>
      <p>Loading self-modification data…</p>
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

  .error-banner {
    padding: 0.75rem 1rem;
    border-radius: 12px;
    background: rgba(248, 113, 113, 0.15);
    border: 1px solid rgba(248, 113, 113, 0.35);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
  }

  .error-banner button {
    background: transparent;
    border: none;
    color: rgba(248, 250, 252, 0.9);
    cursor: pointer;
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
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 1.5rem;
  }

  @media (max-width: 1024px) {
    .hub-grid {
      grid-template-columns: 1fr;
    }
  }

  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
