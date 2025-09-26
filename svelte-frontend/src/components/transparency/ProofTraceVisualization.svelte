<!-- ProofTraceVisualization.svelte -->
<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { GödelOSAPI } from '../../utils/api.js';

  const dispatch = createEventDispatcher();

  export let proofId = null; // Optional specific proof to visualize
  export let autoRefresh = true; // Enable/disable auto-refresh
  export let showStepDetails = true; // Show detailed step information
  export let maxSteps = 1000; // Maximum number of steps to display

  let proofTraces = [];
  let selectedProof = null;
  let proofSteps = [];
  let isLoading = false;
  let error = null;
  let refreshInterval;
  let proofSocket = null;

  // Configuration
  import { API_BASE_URL as API_BASE, WS_BASE_URL as WS_BASE } from '../../config.js';

  // UI state
  let expandedSteps = new Set();
  let filterCriteria = {
    stepType: 'all',
    status: 'all',
    solver: 'all'
  };
  let sortOrder = 'chronological'; // chronological, reverse, depth

  onMount(() => {
    loadRecentProofs();
    if (autoRefresh) {
      startAutoRefresh();
    }
    setupProofWebSocket();
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
    if (proofSocket) proofSocket.close();
  });

  function startAutoRefresh() {
    refreshInterval = setInterval(() => {
      if (selectedProof) {
        loadProofSteps(selectedProof.proof_id);
      } else {
        loadRecentProofs();
      }
    }, 2000); // Refresh every 2 seconds
  }

  function setupProofWebSocket() {
    try {
      proofSocket = new WebSocket(`${WS_BASE}/proof-stream`);
      
      proofSocket.onopen = () => {
        console.log('Proof WebSocket connected');
      };
      
      proofSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'proof_step' && selectedProof && data.proof_id === selectedProof.proof_id) {
            handleNewProofStep(data.step);
          } else if (data.type === 'proof_completed') {
            handleProofCompleted(data.proof_id);
          } else if (data.type === 'proof_started') {
            handleProofStarted(data.proof);
          }
        } catch (e) {
          console.warn('Invalid proof WebSocket message:', e);
        }
      };
      
      proofSocket.onerror = (error) => {
        console.error('Proof WebSocket error:', error);
      };
      
      proofSocket.onclose = () => {
        console.log('Proof WebSocket disconnected');
        // Attempt reconnection after 5 seconds
        setTimeout(setupProofWebSocket, 5000);
      };
    } catch (error) {
      console.error('Failed to setup proof WebSocket:', error);
    }
  }

  function handleNewProofStep(step) {
    proofSteps = [...proofSteps, step].slice(-maxSteps);
    dispatch('stepAdded', { step, proofId: selectedProof?.proof_id });
  }

  function handleProofCompleted(proofId) {
    if (selectedProof && selectedProof.proof_id === proofId) {
      selectedProof = { ...selectedProof, status: 'completed', completed_at: new Date().toISOString() };
    }
    dispatch('proofCompleted', { proofId });
  }

  function handleProofStarted(proof) {
    proofTraces = [proof, ...proofTraces].slice(0, 50); // Keep last 50 proofs
    dispatch('proofStarted', { proof });
  }

  async function loadRecentProofs() {
    isLoading = true;
    try {
      const response = await fetch(`${API_BASE}/api/proofs/recent?limit=20`);
      if (response.ok) {
        const data = await response.json();
        proofTraces = data.proofs || [];
        
        // Auto-select the most recent proof if none selected
        if (!selectedProof && proofTraces.length > 0) {
          selectProof(proofTraces[0]);
        }
        error = null;
      } else {
        console.error('Failed to load recent proofs:', response.status);
        proofTraces = [];
        error = 'No proof traces available';
      }
    } catch (err) {
      console.error('Error loading recent proofs:', err);
      error = 'Failed to load proof traces';
      proofTraces = [];
    } finally {
      isLoading = false;
    }
  }

  async function selectProof(proof) {
    selectedProof = proof;
    await loadProofSteps(proof.proof_id);
    dispatch('proofSelected', { proof });
  }

  async function loadProofSteps(proofId) {
    isLoading = true;
    try {
      const response = await fetch(`${API_BASE}/api/proofs/${proofId}/steps`);
      if (response.ok) {
        const data = await response.json();
        proofSteps = data.steps || [];
        error = null;
      } else {
        console.error('Failed to load proof steps:', response.status);
        proofSteps = [];
        error = 'Failed to load proof steps';
      }
    } catch (err) {
      console.error('Error loading proof steps:', err);
      error = 'Failed to load proof steps';
      proofSteps = [];
    } finally {
      isLoading = false;
    }
  }

  function toggleStepExpansion(stepIndex) {
    if (expandedSteps.has(stepIndex)) {
      expandedSteps.delete(stepIndex);
    } else {
      expandedSteps.add(stepIndex);
    }
    expandedSteps = new Set(expandedSteps); // Trigger reactivity
  }

  function getFilteredSteps() {
    let filtered = proofSteps;
    
    if (filterCriteria.stepType !== 'all') {
      filtered = filtered.filter(step => step.type === filterCriteria.stepType);
    }
    
    if (filterCriteria.status !== 'all') {
      filtered = filtered.filter(step => step.status === filterCriteria.status);
    }
    
    if (filterCriteria.solver !== 'all') {
      filtered = filtered.filter(step => step.solver === filterCriteria.solver);
    }
    
    // Apply sorting
    if (sortOrder === 'reverse') {
      filtered = [...filtered].reverse();
    } else if (sortOrder === 'depth') {
      filtered = [...filtered].sort((a, b) => (b.depth || 0) - (a.depth || 0));
    }
    
    return filtered;
  }

  function formatTimestamp(timestamp) {
    try {
      return new Date(timestamp).toLocaleTimeString();
    } catch {
      return timestamp || 'Unknown';
    }
  }

  function formatDuration(startTime, endTime) {
    if (!startTime || !endTime) return 'N/A';
    try {
      const start = new Date(startTime);
      const end = new Date(endTime);
      const duration = end - start;
      return `${duration}ms`;
    } catch {
      return 'N/A';
    }
  }

  function getStepStatusClass(status) {
    switch (status) {
      case 'success': return 'status-success';
      case 'failed': return 'status-failed';
      case 'timeout': return 'status-timeout';
      case 'in-progress': return 'status-in-progress';
      default: return 'status-unknown';
    }
  }

  function getStepTypeIcon(type) {
    switch (type) {
      case 'unification': return '🔗';
      case 'resolution': return '⚡';
      case 'modal': return '🔵';
      case 'smt': return '🧮';
      case 'clp': return '🔢';
      case 'are': return '🎯';
      case 'axiom': return '📏';
      case 'lemma': return '💡';
      case 'backtrack': return '↶';
      default: return '❓';
    }
  }
</script>

<div class="proof-trace-visualization">
  <div class="header">
    <h3>
      <span class="icon">🔍</span>
      Proof Trace Visualization
    </h3>
    <div class="controls">
      <button 
        class="refresh-btn" 
        on:click={() => selectedProof ? loadProofSteps(selectedProof.proof_id) : loadRecentProofs()}
        disabled={isLoading}
      >
        {isLoading ? '⟳' : '🔄'} Refresh
      </button>
      <label class="toggle">
        <input 
          type="checkbox" 
          bind:checked={autoRefresh} 
          on:change={() => autoRefresh ? startAutoRefresh() : clearInterval(refreshInterval)}
        >
        Auto-refresh
      </label>
    </div>
  </div>

  <div class="proof-trace-content">
    <!-- Proof Selection Panel -->
    <div class="proof-list">
      <h4>Recent Proof Traces ({proofTraces.length})</h4>
      {#if error && proofTraces.length === 0}
        <div class="error-message">
          <span class="icon">⚠️</span>
          {error}
        </div>
      {:else if proofTraces.length === 0 && !isLoading}
        <div class="empty-state">
          <span class="icon">📝</span>
          <p>No proof traces available</p>
        </div>
      {:else}
        <div class="proof-items">
          {#each proofTraces as proof}
            <button
              class="proof-item {selectedProof?.proof_id === proof.proof_id ? 'selected' : ''}"
              on:click={() => selectProof(proof)}
            >
              <div class="proof-header">
                <span class="proof-id">#{proof.proof_id}</span>
                <span class="proof-status status-{proof.status}">{proof.status}</span>
              </div>
              <div class="proof-meta">
                <span class="query-text" title={proof.query}>{proof.query?.slice(0, 60)}...</span>
                <span class="timestamp">{formatTimestamp(proof.started_at)}</span>
              </div>
              {#if proof.step_count}
                <div class="proof-stats">
                  <span class="steps">{proof.step_count} steps</span>
                  {#if proof.duration}
                    <span class="duration">{proof.duration}ms</span>
                  {/if}
                </div>
              {/if}
            </button>
          {/each}
        </div>
      {/if}
    </div>

    <!-- Proof Steps Visualization -->
    <div class="proof-steps">
      {#if selectedProof}
        <div class="proof-steps-header">
          <h4>
            Proof Steps: {selectedProof.query}
            <span class="proof-meta">
              (ID: {selectedProof.proof_id}, Status: {selectedProof.status})
            </span>
          </h4>
          
          <!-- Filters and Controls -->
          <div class="step-controls">
            <div class="filters">
              <select bind:value={filterCriteria.stepType}>
                <option value="all">All Types</option>
                <option value="unification">Unification</option>
                <option value="resolution">Resolution</option>
                <option value="modal">Modal</option>
                <option value="smt">SMT</option>
                <option value="clp">CLP</option>
                <option value="are">ARE</option>
              </select>

              <select bind:value={filterCriteria.status}>
                <option value="all">All Status</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
                <option value="timeout">Timeout</option>
                <option value="in-progress">In Progress</option>
              </select>

              <select bind:value={sortOrder}>
                <option value="chronological">Chronological</option>
                <option value="reverse">Reverse</option>
                <option value="depth">By Depth</option>
              </select>
            </div>
            
            <div class="step-stats">
              {getFilteredSteps().length} / {proofSteps.length} steps
            </div>
          </div>
        </div>

        <div class="steps-container">
          {#each getFilteredSteps() as step, index}
            <div class="step {getStepStatusClass(step.status)} {expandedSteps.has(index) ? 'expanded' : ''}">
              <button 
                class="step-header"
                on:click={() => toggleStepExpansion(index)}
              >
                <div class="step-info">
                  <span class="step-icon">{getStepTypeIcon(step.type)}</span>
                  <span class="step-type">{step.type}</span>
                  <span class="step-number">#{step.step_number || index + 1}</span>
                  {#if step.depth}
                    <span class="step-depth">depth: {step.depth}</span>
                  {/if}
                </div>
                <div class="step-meta">
                  <span class="step-status {getStepStatusClass(step.status)}">{step.status}</span>
                  <span class="step-timestamp">{formatTimestamp(step.timestamp)}</span>
                  {#if step.duration}
                    <span class="step-duration">{step.duration}ms</span>
                  {/if}
                </div>
                <span class="expand-icon">{expandedSteps.has(index) ? '▼' : '▶'}</span>
              </button>

              {#if expandedSteps.has(index) && showStepDetails}
                <div class="step-details">
                  {#if step.goal}
                    <div class="detail-section">
                      <strong>Goal:</strong>
                      <pre class="goal-text">{step.goal}</pre>
                    </div>
                  {/if}
                  
                  {#if step.rule_applied}
                    <div class="detail-section">
                      <strong>Rule Applied:</strong>
                      <code>{step.rule_applied}</code>
                    </div>
                  {/if}
                  
                  {#if step.solver}
                    <div class="detail-section">
                      <strong>Solver:</strong>
                      <span class="solver-name">{step.solver}</span>
                    </div>
                  {/if}
                  
                  {#if step.premises && step.premises.length > 0}
                    <div class="detail-section">
                      <strong>Premises:</strong>
                      <ul class="premises-list">
                        {#each step.premises as premise}
                          <li><code>{premise}</code></li>
                        {/each}
                      </ul>
                    </div>
                  {/if}
                  
                  {#if step.conclusion}
                    <div class="detail-section">
                      <strong>Conclusion:</strong>
                      <pre class="conclusion-text">{step.conclusion}</pre>
                    </div>
                  {/if}
                  
                  {#if step.substitution && Object.keys(step.substitution).length > 0}
                    <div class="detail-section">
                      <strong>Substitution:</strong>
                      <pre class="substitution-text">{JSON.stringify(step.substitution, null, 2)}</pre>
                    </div>
                  {/if}
                  
                  {#if step.error_message}
                    <div class="detail-section error">
                      <strong>Error:</strong>
                      <span class="error-text">{step.error_message}</span>
                    </div>
                  {/if}
                  
                  {#if step.metadata}
                    <div class="detail-section">
                      <strong>Metadata:</strong>
                      <pre class="metadata-text">{JSON.stringify(step.metadata, null, 2)}</pre>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}

          {#if getFilteredSteps().length === 0 && !isLoading}
            <div class="empty-steps">
              <span class="icon">📝</span>
              <p>No proof steps match the current filters</p>
            </div>
          {/if}
        </div>
      {:else}
        <div class="empty-selection">
          <span class="icon">👈</span>
          <p>Select a proof trace to view detailed steps</p>
        </div>
      {/if}
    </div>
  </div>
</div>

<style>
  .proof-trace-visualization {
    height: 100%;
    display: flex;
    flex-direction: column;
    background: var(--bg-primary, #1a1a1a);
    border: 1px solid var(--border-color, #333);
    border-radius: 8px;
    overflow: hidden;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 1rem;
    background: var(--bg-secondary, #2a2a2a);
    border-bottom: 1px solid var(--border-color, #333);
  }

  .header h3 {
    margin: 0;
    color: var(--text-primary, #ffffff);
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .controls {
    display: flex;
    align-items: center;
    gap: 1rem;
  }

  .refresh-btn {
    padding: 0.5rem 1rem;
    background: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .refresh-btn:hover:not(:disabled) {
    background: var(--accent-hover, #3a8eef);
  }

  .refresh-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    color: var(--text-secondary, #cccccc);
    font-size: 0.875rem;
  }

  .proof-trace-content {
    display: flex;
    flex: 1;
    min-height: 0;
  }

  .proof-list {
    width: 300px;
    min-width: 300px;
    background: var(--bg-secondary, #2a2a2a);
    border-right: 1px solid var(--border-color, #333);
    overflow-y: auto;
  }

  .proof-list h4 {
    margin: 0;
    padding: 1rem;
    background: var(--bg-tertiary, #333);
    color: var(--text-primary, #ffffff);
    font-size: 0.875rem;
    border-bottom: 1px solid var(--border-color, #444);
  }

  .proof-items {
    display: flex;
    flex-direction: column;
  }

  .proof-item {
    display: block;
    width: 100%;
    padding: 0.75rem;
    background: transparent;
    border: none;
    border-bottom: 1px solid var(--border-color, #333);
    text-align: left;
    cursor: pointer;
    transition: background-color 0.2s;
    color: var(--text-primary, #ffffff);
  }

  .proof-item:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.05));
  }

  .proof-item.selected {
    background: var(--accent-color, rgba(74, 158, 255, 0.2));
    border-left: 3px solid var(--accent-color, #4a9eff);
  }

  .proof-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.25rem;
  }

  .proof-id {
    font-family: 'Courier New', monospace;
    font-weight: bold;
    font-size: 0.875rem;
  }

  .proof-status {
    padding: 0.125rem 0.5rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: bold;
  }

  .status-completed { background: var(--success-color, #28a745); color: white; }
  .status-in-progress { background: var(--warning-color, #ffc107); color: black; }
  .status-failed { background: var(--error-color, #dc3545); color: white; }
  .status-timeout { background: var(--warning-color, #ff8c00); color: white; }

  .proof-meta {
    color: var(--text-secondary, #cccccc);
    font-size: 0.75rem;
    display: flex;
    justify-content: space-between;
    margin-bottom: 0.25rem;
  }

  .query-text {
    flex: 1;
    margin-right: 0.5rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .proof-stats {
    display: flex;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: var(--text-tertiary, #999999);
  }

  .proof-steps {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .proof-steps-header {
    padding: 1rem;
    background: var(--bg-secondary, #2a2a2a);
    border-bottom: 1px solid var(--border-color, #333);
  }

  .proof-steps-header h4 {
    margin: 0 0 1rem 0;
    color: var(--text-primary, #ffffff);
  }

  .proof-meta {
    color: var(--text-secondary, #cccccc);
    font-size: 0.875rem;
    font-weight: normal;
  }

  .step-controls {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .filters {
    display: flex;
    gap: 0.5rem;
  }

  .filters select {
    padding: 0.25rem 0.5rem;
    background: var(--bg-primary, #1a1a1a);
    color: var(--text-primary, #ffffff);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
    font-size: 0.875rem;
  }

  .step-stats {
    color: var(--text-secondary, #cccccc);
    font-size: 0.875rem;
  }

  .steps-container {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .step {
    margin-bottom: 0.5rem;
    border: 1px solid var(--border-color, #333);
    border-radius: 6px;
    overflow: hidden;
    transition: all 0.2s;
  }

  .step.expanded {
    border-color: var(--accent-color, #4a9eff);
  }

  .step-header {
    width: 100%;
    padding: 0.75rem;
    background: var(--bg-secondary, #2a2a2a);
    border: none;
    text-align: left;
    cursor: pointer;
    display: flex;
    justify-content: space-between;
    align-items: center;
    transition: background-color 0.2s;
    color: var(--text-primary, #ffffff);
  }

  .step-header:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.05));
  }

  .step-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .step-icon {
    font-size: 1.1rem;
  }

  .step-type {
    font-weight: bold;
    text-transform: capitalize;
  }

  .step-number, .step-depth {
    font-family: 'Courier New', monospace;
    font-size: 0.75rem;
    color: var(--text-secondary, #cccccc);
  }

  .step-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
  }

  .step-status {
    padding: 0.125rem 0.5rem;
    border-radius: 10px;
    font-size: 0.75rem;
    font-weight: bold;
  }

  .status-success { background: var(--success-color, #28a745); color: white; }
  .status-failed { background: var(--error-color, #dc3545); color: white; }
  .status-timeout { background: var(--warning-color, #ff8c00); color: white; }
  .status-in-progress { background: var(--info-color, #17a2b8); color: white; }
  .status-unknown { background: var(--secondary-color, #6c757d); color: white; }

  .step-timestamp, .step-duration {
    font-family: 'Courier New', monospace;
    color: var(--text-secondary, #cccccc);
    font-size: 0.75rem;
  }

  .expand-icon {
    color: var(--text-secondary, #cccccc);
    transition: transform 0.2s;
  }

  .step.expanded .expand-icon {
    transform: rotate(90deg);
  }

  .step-details {
    padding: 1rem;
    background: var(--bg-primary, #1a1a1a);
    border-top: 1px solid var(--border-color, #333);
  }

  .detail-section {
    margin-bottom: 0.75rem;
  }

  .detail-section:last-child {
    margin-bottom: 0;
  }

  .detail-section strong {
    color: var(--text-primary, #ffffff);
    display: block;
    margin-bottom: 0.25rem;
    font-size: 0.875rem;
  }

  .detail-section.error strong {
    color: var(--error-color, #dc3545);
  }

  .goal-text, .conclusion-text, .substitution-text, .metadata-text {
    background: var(--bg-secondary, #2a2a2a);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
    padding: 0.5rem;
    margin: 0;
    font-size: 0.875rem;
    color: var(--text-primary, #ffffff);
    font-family: 'Courier New', monospace;
    line-height: 1.4;
    overflow-x: auto;
  }

  .solver-name {
    color: var(--accent-color, #4a9eff);
    font-weight: bold;
  }

  .premises-list {
    margin: 0;
    padding-left: 1.5rem;
  }

  .premises-list li {
    margin-bottom: 0.25rem;
    color: var(--text-secondary, #cccccc);
  }

  .error-text {
    color: var(--error-color, #dc3545);
    font-style: italic;
  }

  .empty-state, .empty-steps, .empty-selection {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: var(--text-secondary, #cccccc);
    text-align: center;
  }

  .empty-state .icon, .empty-steps .icon, .empty-selection .icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    opacity: 0.6;
  }

  .error-message {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem;
    color: var(--error-color, #dc3545);
    background: rgba(220, 53, 69, 0.1);
    border-radius: 4px;
    margin: 1rem;
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .proof-trace-content {
      flex-direction: column;
    }
    
    .proof-list {
      width: 100%;
      min-width: unset;
      max-height: 200px;
    }
    
    .step-controls {
      flex-direction: column;
      align-items: stretch;
      gap: 0.5rem;
    }
    
    .filters {
      flex-wrap: wrap;
    }
  }
</style>