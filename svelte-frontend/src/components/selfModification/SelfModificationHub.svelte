<script>
  import { onMount, onDestroy } from 'svelte';
  import {
    apiHelpers,
    selfModificationState,
    pendingSelfModificationProposals,
    highRiskProposals,
    selfModificationAlerts,
    selfModificationStatus,
    selfModificationFeedbackFeed,
    selfModificationFeedback,
    initCognitiveStream
  } from '../../stores/cognitive.js';
  import CapabilityAssessmentPanel from './CapabilityAssessmentPanel.svelte';
  import ProposalReviewPanel from './ProposalReviewPanel.svelte';
  import LiveCognitiveMonitor from './LiveCognitiveMonitor.svelte';
  import EvolutionTimelinePanel from './EvolutionTimelinePanel.svelte';
  import FeedbackStack from './FeedbackStack.svelte';

  let initializing = true;
  let refreshing = false;
  let errorMessage = null;
  let refreshInterval;
  let refreshIntervalMs = 45000;

  const statusLabels = {
    capabilities: 'Capabilities',
    proposals: 'Proposals',
    evolution: 'Evolution',
    liveState: 'Live Cognition'
  };

  const statusIcons = {
    success: '✅',
    error: '⚠️',
    warning: '⚠️',
    info: 'ℹ️',
    loading: '⏳',
    idle: '•'
  };

  const statusOrder = ['capabilities', 'proposals', 'evolution', 'liveState'];

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

  function formatTimestamp(timestamp) {
    if (!timestamp) return '—';
    try {
      return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch (error) {
      console.warn('Failed to format timestamp', error);
      return '—';
    }
  }

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
      const results = await apiHelpers.refreshSelfModification();
      const hasFailures = results.some((result) => result.status === 'rejected');
      if (!hasFailures) {
        selfModificationFeedback.add('success', 'Self-modification data refreshed.', {
          scope: 'refresh',
          manual: true
        });
        errorMessage = null;
      }
    } catch (error) {
      console.warn('Manual refresh failed:', error);
      errorMessage = error?.message || 'Refresh failed. Try again shortly.';
      selfModificationFeedback.add('error', `Manual refresh failed: ${error?.message || 'Unknown error'}`, {
        scope: 'refresh',
        manual: true
      });
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
  $: status = $selfModificationStatus;
  $: feedbackLog = $selfModificationFeedbackFeed;

  const STATUS_DEFAULT = { state: 'idle', message: 'Standing by for updates.', meta: {}, updatedAt: null };

  function getStatus(scope) {
    if (!scope) return STATUS_DEFAULT;
    const scoped = status?.[scope];
    return scoped ? { ...STATUS_DEFAULT, ...scoped } : STATUS_DEFAULT;
  }

  function pushScopedFeedback(scope, type, message, meta = {}) {
    if (!type || !message) return;
    selfModificationFeedback.add(type, message, { scope, ...meta });
  }

  function dismissFeedbackEntry(id) {
    if (!id) return;
    selfModificationFeedback.dismiss(id);
  }

  $: statusItems = statusOrder.map((key) => ({
    key,
    label: statusLabels[key],
    data: getStatus(key)
  }));

  $: lastAction = status?.lastAction;

  $: feedbackByScope = (feedbackLog || []).reduce((acc, entry) => {
    const scope = entry?.meta?.scope || 'general';
    if (!acc[scope]) acc[scope] = [];
    acc[scope].push(entry);
    return acc;
  }, {});

  function dismissFeedback(event) {
    const id = event?.detail?.id;
    if (!id) return;
    selfModificationFeedback.dismiss(id);
  }

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
      <div class="status-ribbon">
        {#each statusItems as item}
          <div class={`status-pill ${item.data.state}`}>
            <div class="pill-header">
              <span class="pill-icon">{statusIcons[item.data.state] || statusIcons.info}</span>
              <span class="pill-label">{item.label}</span>
            </div>
            <p>{item.data.message || 'Standing by for updates.'}</p>
            <span class="pill-time">{item.data.updatedAt ? `Updated ${formatTimestamp(item.data.updatedAt)}` : 'Waiting for data'}</span>
          </div>
        {/each}
      </div>
    </div>
    <div class="header-actions">
      {#if state.lastUpdated.capabilities}
        <span class="timestamp">Updated {new Date(Math.max(...Object.values(state.lastUpdated).filter(Boolean))).toLocaleTimeString()}</span>
      {/if}
      {#if lastAction}
        <div class={`last-action ${lastAction.state}`}>
          <span class="pulse"></span>
          <div class="action-text">
            <strong>{statusLabels[lastAction.scope] || 'Activity'}</strong>
            <span>{lastAction.message}</span>
          </div>
          {#if lastAction.updatedAt}
            <time>{formatTimestamp(lastAction.updatedAt)}</time>
          {/if}
        </div>
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
        status={getStatus('capabilities')}
        feedbackEntries={(feedbackByScope.capabilities || []).slice(0, 4)}
        pushFeedback={(type, message, meta) => pushScopedFeedback('capabilities', type, message, meta)}
        dismissFeedback={dismissFeedbackEntry}
      />

      <ProposalReviewPanel
        proposals={state.proposals}
        counts={state.proposalCounts}
        activeSimulation={state.activeSimulation}
        loading={proposalsLoading}
        onApprove={apiHelpers.approveSelfModificationProposal}
        onReject={apiHelpers.rejectSelfModificationProposal}
        onSimulate={apiHelpers.simulateSelfModificationProposal}
        status={getStatus('proposals')}
        feedbackEntries={(feedbackByScope.proposals || []).slice(0, 4)}
        pushFeedback={(type, message, meta) => pushScopedFeedback('proposals', type, message, meta)}
        dismissFeedback={dismissFeedbackEntry}
      />

      <LiveCognitiveMonitor
        liveState={state.liveState}
        loading={liveLoading}
        status={getStatus('liveState')}
        feedbackEntries={(feedbackByScope.liveState || []).slice(0, 3)}
        pushFeedback={(type, message, meta) => pushScopedFeedback('liveState', type, message, meta)}
        dismissFeedback={dismissFeedbackEntry}
      />

      <EvolutionTimelinePanel
        timeline={state.timeline}
        metrics={state.metrics}
        upcoming={state.upcoming}
        loading={evolutionLoading}
        status={getStatus('evolution')}
        feedbackEntries={(feedbackByScope.evolution || []).slice(0, 4)}
        pushFeedback={(type, message, meta) => pushScopedFeedback('evolution', type, message, meta)}
        dismissFeedback={dismissFeedbackEntry}
      />
    </div>
  {/if}

  {#if feedbackLog?.length}
    <div class="feedback-overlay">
      <div class="feedback-wrapper">
        <FeedbackStack notifications={feedbackLog} on:dismiss={dismissFeedback} />
      </div>
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
    position: relative;
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

  .status-ribbon {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 0.75rem;
  }

  .status-pill {
    padding: 0.75rem 1rem;
    background: rgba(15, 23, 42, 0.65);
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    min-height: 97px;
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

  .pill-header {
    display: flex;
    align-items: center;
    gap: 0.45rem;
    font-size: 0.85rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: rgba(226, 232, 240, 0.7);
  }

  .pill-icon {
    font-size: 1rem;
  }

  .status-pill p {
    margin: 0;
    color: rgba(226, 232, 240, 0.78);
    font-size: 0.85rem;
  }

  .pill-time {
    font-size: 0.72rem;
    color: rgba(148, 163, 184, 0.7);
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

  .last-action {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    padding: 0.65rem 0.8rem;
    background: rgba(15, 23, 42, 0.6);
    border-radius: 12px;
    border: 1px solid rgba(148, 163, 184, 0.25);
    min-width: 220px;
  }

  .last-action.success {
    border-color: rgba(34, 197, 94, 0.35);
  }

  .last-action.error {
    border-color: rgba(248, 113, 113, 0.35);
  }

  .last-action.warning {
    border-color: rgba(251, 191, 36, 0.35);
  }

  .last-action .action-text {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.85rem;
  }

  .last-action time {
    font-size: 0.75rem;
    color: rgba(148, 163, 184, 0.7);
  }

  .pulse {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: rgba(148, 163, 184, 0.8);
    position: relative;
  }

  .last-action.success .pulse {
    background: rgba(34, 197, 94, 0.9);
  }

  .last-action.error .pulse {
    background: rgba(248, 113, 113, 0.95);
  }

  .last-action.warning .pulse {
    background: rgba(251, 191, 36, 0.95);
  }

  .pulse::after {
    content: "";
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    border: 1px solid currentColor;
    opacity: 0.4;
    animation: pulse 2s ease-in-out infinite;
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

  .feedback-overlay {
    position: absolute;
    top: 1.5rem;
    right: 1.5rem;
    display: flex;
    justify-content: flex-end;
    max-width: 320px;
    pointer-events: none;
    z-index: 5;
  }

  .feedback-wrapper {
    pointer-events: auto;
  }

  @keyframes pulse {
    0% {
      transform: scale(0.9);
      opacity: 0.6;
    }
    50% {
      transform: scale(1.2);
      opacity: 0.2;
    }
    100% {
      transform: scale(0.9);
      opacity: 0.6;
    }
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
