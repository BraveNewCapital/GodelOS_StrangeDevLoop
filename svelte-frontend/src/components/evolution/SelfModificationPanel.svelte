<script>
  import { onMount } from 'svelte';
  import { fade, fly, slide } from 'svelte/transition';
  import { API_BASE_URL } from '../../config.js';
  import { evolutionState } from '../../stores/cognitive.js';

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------
  let activeTab = 'proposals';   // 'proposals' | 'history' | 'new'
  let proposals = [];
  let history = [];
  let loading = false;
  let error = null;

  // New-proposal form state
  let newTarget = 'knowledge_graph';
  let newModificationType = 'add_node';
  let newParamsText = '{"node_id": "example_node", "node_data": {"label": "Example"}}';
  let submitting = false;
  let submitError = null;
  let submitSuccess = null;

  // Target → allowed modification types
  const targetTypes = {
    knowledge_graph: [
      { value: 'add_node',    label: '+ Add Node' },
      { value: 'remove_node', label: '- Remove Node' },
      { value: 'add_edge',    label: '+ Add Edge' },
      { value: 'remove_edge', label: '- Remove Edge' },
    ],
    reasoning_params: [
      { value: 'update_param', label: 'Update Parameter' },
    ],
    goal_priority: [
      { value: 'reweight_goal', label: 'Reweight Goals' },
    ],
  };

  // Default parameter templates per modification type
  const paramTemplates = {
    add_node:     '{"node_id": "new_node", "node_data": {"label": "New Node", "type": "concept"}}',
    remove_node:  '{"node_id": "existing_node"}',
    add_edge:     '{"source": "node_a", "target": "node_b", "edge_data": {"relation": "related_to"}}',
    remove_edge:  '{"source": "node_a", "target": "node_b"}',
    update_param: '{"name": "inference_depth", "value": 7}',
    reweight_goal:'{"weights": {"safety": 0.9, "efficiency": 0.6, "learning": 0.8}}',
  };

  const riskColors = {
    low:    '#4caf50',
    medium: '#ff9800',
    high:   '#f44336',
  };

  const statusIcons = {
    pending:      '⏳',
    applied:      '✅',
    rolled_back:  '↩️',
    rejected:     '❌',
  };

  // -----------------------------------------------------------------------
  // Lifecycle
  // -----------------------------------------------------------------------
  onMount(() => {
    loadHistory();
  });

  // -----------------------------------------------------------------------
  // Data loading
  // -----------------------------------------------------------------------
  async function loadHistory() {
    loading = true;
    error = null;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/self-modification/history`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      history = data.history || [];
      proposals = history.filter(r => r.status === 'pending');

      // Sync pending proposals into the shared evolutionState store
      evolutionState.update(s => ({ ...s, proposals: proposals }));
    } catch (e) {
      error = `Failed to load history: ${e.message}`;
    } finally {
      loading = false;
    }
  }

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------
  async function handleApply(proposalId) {
    if (!confirm('Apply this modification to the live system?')) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/self-modification/apply/${proposalId}`, {
        method: 'POST',
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      await loadHistory();
    } catch (e) {
      alert(`Apply failed: ${e.message}`);
    }
  }

  async function handleRollback(proposalId) {
    if (!confirm('Roll back this modification?')) return;
    try {
      const resp = await fetch(`${API_BASE_URL}/api/self-modification/rollback/${proposalId}`, {
        method: 'POST',
      });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      await loadHistory();
    } catch (e) {
      alert(`Rollback failed: ${e.message}`);
    }
  }

  async function handleSubmitProposal() {
    submitting = true;
    submitError = null;
    submitSuccess = null;

    let parsedParams;
    try {
      parsedParams = JSON.parse(newParamsText);
    } catch {
      submitError = 'Parameters must be valid JSON.';
      submitting = false;
      return;
    }

    try {
      const resp = await fetch(`${API_BASE_URL}/api/self-modification/propose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: newTarget,
          modification_type: newModificationType,
          parameters: parsedParams,
        }),
      });
      const data = await resp.json();
      if (!resp.ok) throw new Error(data.detail || `HTTP ${resp.status}`);
      submitSuccess = `Proposal created: ${data.proposal_id}`;
      await loadHistory();
      activeTab = 'proposals';
    } catch (e) {
      submitError = `Failed to propose: ${e.message}`;
    } finally {
      submitting = false;
    }
  }

  // When target changes, reset modification type and template
  function onTargetChange() {
    const types = targetTypes[newTarget];
    newModificationType = types[0].value;
    newParamsText = paramTemplates[newModificationType];
  }

  function onModificationTypeChange() {
    newParamsText = paramTemplates[newModificationType] || '{}';
  }

  function formatTimestamp(ts) {
    if (!ts) return '—';
    return new Date(ts * 1000).toLocaleString();
  }
</script>

<!-- =====================================================================
     Template
     ===================================================================== -->
<div class="self-mod-panel">
  <header class="panel-header">
    <h2>🔧 Self-Modification Engine</h2>
    <p class="subtitle">Propose, apply, and roll back system modifications in a sandboxed, auditable workflow.</p>
  </header>

  <!-- Tab nav -->
  <nav class="tabs">
    <button
      class="tab {activeTab === 'proposals' ? 'active' : ''}"
      on:click={() => { activeTab = 'proposals'; loadHistory(); }}
    >
      ⏳ Pending Proposals
      {#if proposals.length > 0}
        <span class="badge">{proposals.length}</span>
      {/if}
    </button>
    <button
      class="tab {activeTab === 'history' ? 'active' : ''}"
      on:click={() => { activeTab = 'history'; loadHistory(); }}
    >
      📋 History
    </button>
    <button
      class="tab {activeTab === 'new' ? 'active' : ''}"
      on:click={() => activeTab = 'new'}
    >
      ✨ New Proposal
    </button>
  </nav>

  <!-- ----------------------------------------------------------------
       Content
       ---------------------------------------------------------------- -->
  <div class="tab-content">

    {#if loading}
      <div class="loading" in:fade>⏳ Loading…</div>
    {:else if error}
      <div class="error-msg" in:fade>{error}</div>
    {/if}

    <!-- Pending proposals tab -->
    {#if activeTab === 'proposals'}
      <div in:fade>
        {#if proposals.length === 0 && !loading}
          <p class="empty-state">No pending proposals. Use <strong>New Proposal</strong> to create one.</p>
        {:else}
          <div class="card-list">
            {#each proposals as p (p.proposal_id)}
              <div class="proposal-card" in:fly={{ x: -10, duration: 200 }}>
                <div class="card-top">
                  <span class="risk-badge" style="background: {riskColors[p.risk_level] || '#888'}">
                    {p.risk_level?.toUpperCase() || 'UNKNOWN'} RISK
                  </span>
                  <span class="status-icon">{statusIcons[p.status] || '?'}</span>
                  <code class="proposal-id">{p.proposal_id.slice(0, 8)}</code>
                </div>
                <div class="card-body">
                  <p><strong>Target:</strong> {p.target}</p>
                  <p><strong>Type:</strong> {p.modification_type}</p>
                  <p><strong>Created:</strong> {formatTimestamp(p.created_at)}</p>
                  <details>
                    <summary>Parameters</summary>
                    <pre class="code-block">{JSON.stringify(p.parameters, null, 2)}</pre>
                  </details>
                  <details>
                    <summary>Predicted Impact</summary>
                    <pre class="code-block">{JSON.stringify(p.predicted_impact, null, 2)}</pre>
                  </details>
                </div>
                <div class="card-actions">
                  <button class="btn btn-primary" on:click={() => handleApply(p.proposal_id)}>
                    ✅ Apply
                  </button>
                </div>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {/if}

    <!-- History tab -->
    {#if activeTab === 'history'}
      <div in:fade>
        {#if history.length === 0 && !loading}
          <p class="empty-state">No modification history yet.</p>
        {:else}
          <table class="history-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Target</th>
                <th>Type</th>
                <th>Risk</th>
                <th>Status</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {#each history as r (r.proposal_id)}
                <tr in:slide={{ duration: 150 }}>
                  <td><code class="small-id">{r.proposal_id.slice(0, 8)}</code></td>
                  <td>{r.target}</td>
                  <td>{r.modification_type}</td>
                  <td>
                    <span class="risk-dot" style="background: {riskColors[r.risk_level] || '#888'}"></span>
                    {r.risk_level}
                  </td>
                  <td>{statusIcons[r.status] || ''} {r.status}</td>
                  <td class="ts">{formatTimestamp(r.created_at)}</td>
                  <td>
                    {#if r.status === 'pending'}
                      <button class="btn btn-sm btn-primary" on:click={() => handleApply(r.proposal_id)}>
                        Apply
                      </button>
                    {:else if r.status === 'applied'}
                      <button class="btn btn-sm btn-danger" on:click={() => handleRollback(r.proposal_id)}>
                        Rollback
                      </button>
                    {:else}
                      —
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    {/if}

    <!-- New proposal tab -->
    {#if activeTab === 'new'}
      <div class="new-proposal-form" in:fade>
        <h3>Create Modification Proposal</h3>

        {#if submitSuccess}
          <div class="success-msg" in:fade>{submitSuccess}</div>
        {/if}
        {#if submitError}
          <div class="error-msg" in:fade>{submitError}</div>
        {/if}

        <label>
          <span>Modification Target</span>
          <select bind:value={newTarget} on:change={onTargetChange}>
            <option value="knowledge_graph">Knowledge Graph</option>
            <option value="reasoning_params">Reasoning Parameters</option>
            <option value="goal_priority">Goal Priority</option>
          </select>
        </label>

        <label>
          <span>Modification Type</span>
          <select bind:value={newModificationType} on:change={onModificationTypeChange}>
            {#each targetTypes[newTarget] as t}
              <option value={t.value}>{t.label}</option>
            {/each}
          </select>
        </label>

        <label>
          <span>Parameters (JSON)</span>
          <textarea
            rows="6"
            bind:value={newParamsText}
            placeholder="&#123;&#125;"
            spellcheck="false"
          ></textarea>
        </label>

        <div class="form-actions">
          <button
            class="btn btn-primary"
            on:click={handleSubmitProposal}
            disabled={submitting}
          >
            {submitting ? '⏳ Submitting…' : '🚀 Submit Proposal'}
          </button>
          <button class="btn btn-secondary" on:click={() => activeTab = 'proposals'}>
            Cancel
          </button>
        </div>
      </div>
    {/if}

  </div>
</div>

<!-- =====================================================================
     Styles
     ===================================================================== -->
<style>
  .self-mod-panel {
    padding: 1.5rem;
    color: var(--text-primary, #e0e0e0);
    font-family: inherit;
    max-width: 960px;
    margin: 0 auto;
  }

  .panel-header {
    margin-bottom: 1.25rem;
  }

  .panel-header h2 {
    margin: 0 0 0.25rem;
    font-size: 1.4rem;
    color: var(--accent-blue, #4a9eff);
  }

  .subtitle {
    margin: 0;
    font-size: 0.85rem;
    color: var(--text-secondary, #a0a0a0);
  }

  /* ----- Tabs ----- */
  .tabs {
    display: flex;
    gap: 0.25rem;
    border-bottom: 1px solid #333;
    margin-bottom: 1rem;
  }

  .tab {
    background: none;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--text-secondary, #a0a0a0);
    cursor: pointer;
    font-size: 0.9rem;
    padding: 0.5rem 0.9rem;
    transition: color 0.15s, border-color 0.15s;
  }

  .tab:hover {
    color: var(--text-primary, #e0e0e0);
  }

  .tab.active {
    border-bottom-color: var(--accent-blue, #4a9eff);
    color: var(--text-primary, #e0e0e0);
  }

  .badge {
    background: var(--accent-blue, #4a9eff);
    border-radius: 999px;
    color: #fff;
    font-size: 0.7rem;
    margin-left: 0.3rem;
    padding: 0 0.4rem;
  }

  /* ----- Cards ----- */
  .card-list {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
  }

  .proposal-card {
    background: #1e1e2e;
    border: 1px solid #2a2a40;
    border-radius: 8px;
    padding: 1rem;
  }

  .card-top {
    align-items: center;
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .risk-badge {
    border-radius: 4px;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.05em;
    padding: 0.2rem 0.5rem;
    color: #fff;
  }

  .status-icon {
    font-size: 1rem;
  }

  .proposal-id {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.75rem;
    margin-left: auto;
  }

  .card-body p {
    font-size: 0.88rem;
    margin: 0.2rem 0;
  }

  .code-block {
    background: #111122;
    border-radius: 4px;
    color: #b0e0ff;
    font-size: 0.78rem;
    margin-top: 0.4rem;
    overflow-x: auto;
    padding: 0.5rem;
    white-space: pre-wrap;
    word-break: break-word;
  }

  details summary {
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--text-secondary, #a0a0a0);
    margin-top: 0.4rem;
  }

  .card-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 0.75rem;
  }

  /* ----- History table ----- */
  .history-table {
    border-collapse: collapse;
    font-size: 0.84rem;
    width: 100%;
  }

  .history-table th,
  .history-table td {
    border-bottom: 1px solid #2a2a40;
    padding: 0.45rem 0.6rem;
    text-align: left;
  }

  .history-table th {
    color: var(--text-secondary, #a0a0a0);
    font-weight: 600;
  }

  .small-id {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.75rem;
  }

  .risk-dot {
    border-radius: 50%;
    display: inline-block;
    height: 8px;
    margin-right: 4px;
    width: 8px;
  }

  .ts {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.78rem;
  }

  /* ----- New proposal form ----- */
  .new-proposal-form {
    max-width: 560px;
  }

  .new-proposal-form h3 {
    font-size: 1.05rem;
    margin: 0 0 1rem;
  }

  .new-proposal-form label {
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
    margin-bottom: 0.85rem;
  }

  .new-proposal-form label span {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.82rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .new-proposal-form select,
  .new-proposal-form textarea {
    background: #1e1e2e;
    border: 1px solid #2a2a40;
    border-radius: 6px;
    color: var(--text-primary, #e0e0e0);
    font-family: monospace;
    font-size: 0.88rem;
    padding: 0.5rem 0.6rem;
    resize: vertical;
    width: 100%;
    box-sizing: border-box;
  }

  .new-proposal-form select:focus,
  .new-proposal-form textarea:focus {
    border-color: var(--accent-blue, #4a9eff);
    outline: none;
  }

  .form-actions {
    display: flex;
    gap: 0.5rem;
    margin-top: 1rem;
  }

  /* ----- Buttons ----- */
  .btn {
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    padding: 0.45rem 0.9rem;
    transition: opacity 0.15s;
  }

  .btn:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }

  .btn-primary {
    background: var(--accent-blue, #4a9eff);
    color: #fff;
  }

  .btn-primary:hover:not(:disabled) {
    opacity: 0.85;
  }

  .btn-secondary {
    background: #2a2a40;
    color: var(--text-primary, #e0e0e0);
  }

  .btn-secondary:hover {
    opacity: 0.85;
  }

  .btn-danger {
    background: #c0392b;
    color: #fff;
  }

  .btn-danger:hover {
    opacity: 0.85;
  }

  .btn-sm {
    font-size: 0.78rem;
    padding: 0.3rem 0.6rem;
  }

  /* ----- Feedback messages ----- */
  .loading {
    color: var(--text-secondary, #a0a0a0);
    padding: 0.5rem 0;
  }

  .error-msg {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid #c0392b;
    border-radius: 6px;
    color: #f87171;
    font-size: 0.85rem;
    margin-bottom: 0.75rem;
    padding: 0.5rem 0.75rem;
  }

  .success-msg {
    background: rgba(76, 175, 80, 0.1);
    border: 1px solid #4caf50;
    border-radius: 6px;
    color: #81c784;
    font-size: 0.85rem;
    margin-bottom: 0.75rem;
    padding: 0.5rem 0.75rem;
  }

  .empty-state {
    color: var(--text-secondary, #a0a0a0);
    font-size: 0.9rem;
    padding: 1rem 0;
  }
</style>
