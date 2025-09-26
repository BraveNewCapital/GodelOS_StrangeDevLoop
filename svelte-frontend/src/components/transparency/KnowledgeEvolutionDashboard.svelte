<!-- KnowledgeEvolutionDashboard.svelte -->
<script>
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { GödelOSAPI } from '../../utils/api.js';

  const dispatch = createEventDispatcher();

  export let autoRefresh = true; // Enable/disable auto-refresh
  export let showContextVersions = true; // Show context version information
  export let maxEvolutionEvents = 1000; // Maximum evolution events to track
  export let timeWindow = '1h'; // Time window for evolution events ('1h', '6h', '1d', '1w')

  let knowledgeContexts = [];
  let evolutionEvents = [];
  let contextVersions = new Map();
  let selectedContext = null;
  let isLoading = false;
  let error = null;
  let refreshInterval;
  let evolutionSocket = null;

  // Configuration
  import { API_BASE_URL as API_BASE, WS_BASE_URL as WS_BASE } from '../../config.js';

  // UI State
  let activeTab = 'evolution'; // evolution, contexts, versions, graph
  let filterCriteria = {
    eventType: 'all',
    source: 'all',
    impact: 'all'
  };
  let sortOrder = 'newest'; // newest, oldest, impact
  let expandedEvents = new Set();

  // Statistics
  let evolutionStats = {
    totalEvents: 0,
    recentEvents: 0,
    contextUpdates: 0,
    conceptChanges: 0,
    relationshipUpdates: 0
  };

  onMount(() => {
    loadKnowledgeContexts();
    loadEvolutionEvents();
    if (autoRefresh) {
      startAutoRefresh();
    }
    setupEvolutionWebSocket();
  });

  onDestroy(() => {
    if (refreshInterval) clearInterval(refreshInterval);
    if (evolutionSocket) evolutionSocket.close();
  });

  function startAutoRefresh() {
    refreshInterval = setInterval(() => {
      loadKnowledgeContexts();
      loadEvolutionEvents();
    }, 3000); // Refresh every 3 seconds
  }

  function setupEvolutionWebSocket() {
    try {
      evolutionSocket = new WebSocket(`${WS_BASE}/knowledge-evolution-stream`);
      
      evolutionSocket.onopen = () => {
        console.log('Knowledge Evolution WebSocket connected');
      };
      
      evolutionSocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'knowledge_evolution') {
            handleEvolutionEvent(data.event);
          } else if (data.type === 'context_update') {
            handleContextUpdate(data.context);
          } else if (data.type === 'version_change') {
            handleVersionChange(data.version_info);
          }
        } catch (e) {
          console.warn('Invalid evolution WebSocket message:', e);
        }
      };
      
      evolutionSocket.onerror = (error) => {
        console.error('Evolution WebSocket error:', error);
      };
      
      evolutionSocket.onclose = () => {
        console.log('Evolution WebSocket disconnected');
        setTimeout(setupEvolutionWebSocket, 5000);
      };
    } catch (error) {
      console.error('Failed to setup evolution WebSocket:', error);
    }
  }

  function handleEvolutionEvent(event) {
    evolutionEvents = [event, ...evolutionEvents].slice(0, maxEvolutionEvents);
    updateEvolutionStats();
    dispatch('evolutionEvent', { event });
  }

  function handleContextUpdate(context) {
    const existingIndex = knowledgeContexts.findIndex(c => c.context_id === context.context_id);
    if (existingIndex >= 0) {
      knowledgeContexts[existingIndex] = context;
    } else {
      knowledgeContexts = [context, ...knowledgeContexts];
    }
    knowledgeContexts = [...knowledgeContexts]; // Trigger reactivity
    dispatch('contextUpdate', { context });
  }

  function handleVersionChange(versionInfo) {
    contextVersions.set(versionInfo.context_id, versionInfo);
    contextVersions = new Map(contextVersions); // Trigger reactivity
    dispatch('versionChange', { versionInfo });
  }

  async function loadKnowledgeContexts() {
    try {
      const response = await fetch(`${API_BASE}/api/knowledge/contexts`);
      if (response.ok) {
        const data = await response.json();
        knowledgeContexts = data.contexts || [];
        
        // Load version information for each context
        if (showContextVersions) {
          await loadContextVersions();
        }
        
        error = null;
      } else {
        console.error('Failed to load knowledge contexts:', response.status);
        error = 'Failed to load knowledge contexts';
      }
    } catch (err) {
      console.error('Error loading knowledge contexts:', err);
      error = 'Failed to load knowledge contexts';
    }
  }

  async function loadContextVersions() {
    for (const context of knowledgeContexts) {
      try {
        const response = await fetch(`${API_BASE}/api/knowledge/contexts/${context.context_id}/versions`);
        if (response.ok) {
          const data = await response.json();
          contextVersions.set(context.context_id, data.version_info);
        }
      } catch (err) {
        console.warn(`Failed to load version info for context ${context.context_id}:`, err);
      }
    }
    contextVersions = new Map(contextVersions); // Trigger reactivity
  }

  async function loadEvolutionEvents() {
    isLoading = true;
    try {
      const response = await fetch(`${API_BASE}/api/knowledge/evolution?time_window=${timeWindow}&limit=200`);
      if (response.ok) {
        const data = await response.json();
        evolutionEvents = data.events || [];
        updateEvolutionStats();
        error = null;
      } else {
        console.error('Failed to load evolution events:', response.status);
        error = 'Failed to load evolution events';
      }
    } catch (err) {
      console.error('Error loading evolution events:', err);
      error = 'Failed to load evolution events';
    } finally {
      isLoading = false;
    }
  }

  function updateEvolutionStats() {
    evolutionStats.totalEvents = evolutionEvents.length;
    
    const recentThreshold = Date.now() - (5 * 60 * 1000); // Last 5 minutes
    evolutionStats.recentEvents = evolutionEvents.filter(
      event => new Date(event.timestamp).getTime() > recentThreshold
    ).length;
    
    evolutionStats.contextUpdates = evolutionEvents.filter(
      event => event.event_type === 'context_update'
    ).length;
    
    evolutionStats.conceptChanges = evolutionEvents.filter(
      event => event.event_type === 'concept_change'
    ).length;
    
    evolutionStats.relationshipUpdates = evolutionEvents.filter(
      event => event.event_type === 'relationship_update'
    ).length;
  }

  function selectContext(context) {
    selectedContext = context;
    dispatch('contextSelected', { context });
  }

  function getFilteredEvents() {
    let filtered = evolutionEvents;
    
    if (filterCriteria.eventType !== 'all') {
      filtered = filtered.filter(event => event.event_type === filterCriteria.eventType);
    }
    
    if (filterCriteria.source !== 'all') {
      filtered = filtered.filter(event => event.source === filterCriteria.source);
    }
    
    if (filterCriteria.impact !== 'all') {
      filtered = filtered.filter(event => event.impact_level === filterCriteria.impact);
    }
    
    // Apply sorting
    if (sortOrder === 'oldest') {
      filtered = [...filtered].reverse();
    } else if (sortOrder === 'impact') {
      const impactOrder = { 'critical': 4, 'high': 3, 'medium': 2, 'low': 1 };
      filtered = [...filtered].sort((a, b) => 
        (impactOrder[b.impact_level] || 0) - (impactOrder[a.impact_level] || 0)
      );
    }
    
    return filtered;
  }

  function toggleEventExpansion(eventId) {
    if (expandedEvents.has(eventId)) {
      expandedEvents.delete(eventId);
    } else {
      expandedEvents.add(eventId);
    }
    expandedEvents = new Set(expandedEvents); // Trigger reactivity
  }

  function formatTimestamp(timestamp) {
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp || 'Unknown';
    }
  }

  function getEventTypeIcon(eventType) {
    switch (eventType) {
      case 'context_update': return '📝';
      case 'concept_change': return '💡';
      case 'relationship_update': return '🔗';
      case 'ontology_evolution': return '🌐';
      case 'knowledge_integration': return '🔄';
      case 'learning_update': return '🎓';
      case 'grounding_change': return '⚓';
      default: return '📊';
    }
  }

  function getImpactLevelClass(impact) {
    switch (impact) {
      case 'critical': return 'impact-critical';
      case 'high': return 'impact-high';
      case 'medium': return 'impact-medium';
      case 'low': return 'impact-low';
      default: return 'impact-unknown';
    }
  }

  function getContextStatusClass(status) {
    switch (status) {
      case 'active': return 'status-active';
      case 'evolving': return 'status-evolving';
      case 'stable': return 'status-stable';
      case 'deprecated': return 'status-deprecated';
      default: return 'status-unknown';
    }
  }
</script>

<div class="knowledge-evolution-dashboard">
  <div class="header">
    <h3>
      <span class="icon">🌱</span>
      Knowledge Evolution Dashboard
    </h3>
    <div class="controls">
      <select bind:value={timeWindow} on:change={() => loadEvolutionEvents()}>
        <option value="1h">Last Hour</option>
        <option value="6h">Last 6 Hours</option>
        <option value="1d">Last Day</option>
        <option value="1w">Last Week</option>
      </select>
      <button 
        class="refresh-btn" 
        on:click={() => {loadKnowledgeContexts(); loadEvolutionEvents();}}
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

  <!-- Statistics Bar -->
  <div class="stats-bar">
    <div class="stat">
      <span class="stat-value">{evolutionStats.totalEvents}</span>
      <span class="stat-label">Total Events</span>
    </div>
    <div class="stat">
      <span class="stat-value">{evolutionStats.recentEvents}</span>
      <span class="stat-label">Recent (5min)</span>
    </div>
    <div class="stat">
      <span class="stat-value">{evolutionStats.contextUpdates}</span>
      <span class="stat-label">Context Updates</span>
    </div>
    <div class="stat">
      <span class="stat-value">{evolutionStats.conceptChanges}</span>
      <span class="stat-label">Concept Changes</span>
    </div>
    <div class="stat">
      <span class="stat-value">{evolutionStats.relationshipUpdates}</span>
      <span class="stat-label">Relationship Updates</span>
    </div>
  </div>

  <!-- Tab Navigation -->
  <div class="tab-navigation">
    <button 
      class="tab-btn {activeTab === 'evolution' ? 'active' : ''}"
      on:click={() => activeTab = 'evolution'}
    >
      📊 Evolution Events
    </button>
    <button 
      class="tab-btn {activeTab === 'contexts' ? 'active' : ''}"
      on:click={() => activeTab = 'contexts'}
    >
      📚 Knowledge Contexts
    </button>
    {#if showContextVersions}
      <button 
        class="tab-btn {activeTab === 'versions' ? 'active' : ''}"
        on:click={() => activeTab = 'versions'}
      >
        🔄 Version History
      </button>
    {/if}
    <button 
      class="tab-btn {activeTab === 'graph' ? 'active' : ''}"
      on:click={() => activeTab = 'graph'}
    >
      🌐 Knowledge Graph
    </button>
  </div>

  <div class="dashboard-content">
    {#if activeTab === 'evolution'}
      <!-- Evolution Events Tab -->
      <div class="evolution-events-panel">
        <div class="panel-header">
          <h4>Knowledge Evolution Events</h4>
          <div class="event-controls">
            <div class="filters">
              <select bind:value={filterCriteria.eventType}>
                <option value="all">All Types</option>
                <option value="context_update">Context Updates</option>
                <option value="concept_change">Concept Changes</option>
                <option value="relationship_update">Relationship Updates</option>
                <option value="ontology_evolution">Ontology Evolution</option>
                <option value="knowledge_integration">Knowledge Integration</option>
                <option value="learning_update">Learning Updates</option>
              </select>

              <select bind:value={filterCriteria.impact}>
                <option value="all">All Impact Levels</option>
                <option value="critical">Critical</option>
                <option value="high">High</option>
                <option value="medium">Medium</option>
                <option value="low">Low</option>
              </select>

              <select bind:value={sortOrder}>
                <option value="newest">Newest First</option>
                <option value="oldest">Oldest First</option>
                <option value="impact">By Impact</option>
              </select>
            </div>
            
            <div class="event-count">
              {getFilteredEvents().length} / {evolutionEvents.length} events
            </div>
          </div>
        </div>

        <div class="events-container">
          {#each getFilteredEvents() as event}
            <div class="evolution-event {getImpactLevelClass(event.impact_level)}">
              <button 
                class="event-header"
                on:click={() => toggleEventExpansion(event.event_id)}
              >
                <div class="event-info">
                  <span class="event-icon">{getEventTypeIcon(event.event_type)}</span>
                  <span class="event-type">{event.event_type.replace('_', ' ')}</span>
                  <span class="event-impact {getImpactLevelClass(event.impact_level)}">
                    {event.impact_level}
                  </span>
                </div>
                <div class="event-meta">
                  <span class="event-timestamp">{formatTimestamp(event.timestamp)}</span>
                  <span class="event-source">{event.source}</span>
                </div>
                <span class="expand-icon">{expandedEvents.has(event.event_id) ? '▼' : '▶'}</span>
              </button>

              {#if expandedEvents.has(event.event_id)}
                <div class="event-details">
                  {#if event.summary}
                    <div class="detail-section">
                      <strong>Summary:</strong>
                      <p class="event-summary">{event.summary}</p>
                    </div>
                  {/if}
                  
                  {#if event.context_id}
                    <div class="detail-section">
                      <strong>Context:</strong>
                      <span class="context-id">{event.context_id}</span>
                    </div>
                  {/if}
                  
                  {#if event.changes && event.changes.length > 0}
                    <div class="detail-section">
                      <strong>Changes:</strong>
                      <ul class="changes-list">
                        {#each event.changes as change}
                          <li>
                            <span class="change-type">{change.type}:</span>
                            <span class="change-description">{change.description}</span>
                            {#if change.before && change.after}
                              <div class="change-diff">
                                <span class="diff-before">Before: {change.before}</span>
                                <span class="diff-after">After: {change.after}</span>
                              </div>
                            {/if}
                          </li>
                        {/each}
                      </ul>
                    </div>
                  {/if}
                  
                  {#if event.affected_concepts && event.affected_concepts.length > 0}
                    <div class="detail-section">
                      <strong>Affected Concepts:</strong>
                      <div class="concept-tags">
                        {#each event.affected_concepts as concept}
                          <span class="concept-tag">{concept}</span>
                        {/each}
                      </div>
                    </div>
                  {/if}
                  
                  {#if event.metrics}
                    <div class="detail-section">
                      <strong>Metrics:</strong>
                      <pre class="metrics-text">{JSON.stringify(event.metrics, null, 2)}</pre>
                    </div>
                  {/if}
                  
                  {#if event.metadata}
                    <div class="detail-section">
                      <strong>Metadata:</strong>
                      <pre class="metadata-text">{JSON.stringify(event.metadata, null, 2)}</pre>
                    </div>
                  {/if}
                </div>
              {/if}
            </div>
          {/each}

          {#if getFilteredEvents().length === 0 && !isLoading}
            <div class="empty-events">
              <span class="icon">📊</span>
              <p>No evolution events match the current filters</p>
            </div>
          {/if}
        </div>
      </div>

    {:else if activeTab === 'contexts'}
      <!-- Knowledge Contexts Tab -->
      <div class="contexts-panel">
        <div class="panel-header">
          <h4>Knowledge Contexts ({knowledgeContexts.length})</h4>
        </div>

        <div class="contexts-grid">
          {#each knowledgeContexts as context}
            <div class="context-card {getContextStatusClass(context.status)}">
              <div class="context-header">
                <h5>{context.name}</h5>
                <span class="context-status {getContextStatusClass(context.status)}">
                  {context.status}
                </span>
              </div>
              
              <div class="context-info">
                <div class="context-id">ID: {context.context_id}</div>
                <div class="context-type">Type: {context.type}</div>
                {#if context.version}
                  <div class="context-version">Version: {context.version}</div>
                {/if}
                {#if context.last_updated}
                  <div class="context-updated">Updated: {formatTimestamp(context.last_updated)}</div>
                {/if}
              </div>
              
              {#if context.description}
                <div class="context-description">
                  {context.description}
                </div>
              {/if}
              
              <div class="context-stats">
                {#if context.concept_count}
                  <span class="stat-item">{context.concept_count} concepts</span>
                {/if}
                {#if context.relation_count}
                  <span class="stat-item">{context.relation_count} relations</span>
                {/if}
                {#if context.axiom_count}
                  <span class="stat-item">{context.axiom_count} axioms</span>
                {/if}
              </div>
              
              <button class="context-select-btn" on:click={() => selectContext(context)}>
                View Details
              </button>
            </div>
          {/each}

          {#if knowledgeContexts.length === 0 && !isLoading}
            <div class="empty-contexts">
              <span class="icon">📚</span>
              <p>No knowledge contexts available</p>
            </div>
          {/if}
        </div>
      </div>

    {:else if activeTab === 'versions' && showContextVersions}
      <!-- Version History Tab -->
      <div class="versions-panel">
        <div class="panel-header">
          <h4>Context Version History</h4>
        </div>

        <div class="versions-container">
          {#each [...contextVersions.entries()] as [contextId, versionInfo]}
            <div class="version-group">
              <h5>Context: {contextId}</h5>
              {#if versionInfo.versions}
                <div class="version-timeline">
                  {#each versionInfo.versions as version}
                    <div class="version-item">
                      <div class="version-header">
                        <span class="version-number">v{version.version}</span>
                        <span class="version-timestamp">{formatTimestamp(version.created_at)}</span>
                      </div>
                      <div class="version-changes">
                        {#if version.summary}
                          <p class="version-summary">{version.summary}</p>
                        {/if}
                        {#if version.changes_count}
                          <span class="changes-count">{version.changes_count} changes</span>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="no-versions">No version history available</p>
              {/if}
            </div>
          {/each}

          {#if contextVersions.size === 0 && !isLoading}
            <div class="empty-versions">
              <span class="icon">🔄</span>
              <p>No version history available</p>
            </div>
          {/if}
        </div>
      </div>

    {:else if activeTab === 'graph'}
      <!-- Knowledge Graph Tab -->
      <div class="graph-panel">
        <div class="panel-header">
          <h4>Knowledge Graph Visualization</h4>
        </div>

        <div class="graph-placeholder">
          <span class="icon">🌐</span>
          <p>Knowledge Graph visualization would be displayed here</p>
          <p class="placeholder-note">This would integrate with the existing KnowledgeGraph.svelte component</p>
        </div>
      </div>
    {/if}
  </div>

  {#if error}
    <div class="error-banner">
      <span class="icon">⚠️</span>
      {error}
    </div>
  {/if}
</div>

<style>
  .knowledge-evolution-dashboard {
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

  .controls select {
    padding: 0.5rem;
    background: var(--bg-primary, #1a1a1a);
    color: var(--text-primary, #ffffff);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
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

  .stats-bar {
    display: flex;
    justify-content: space-around;
    padding: 1rem;
    background: var(--bg-tertiary, #333);
    border-bottom: 1px solid var(--border-color, #444);
  }

  .stat {
    text-align: center;
  }

  .stat-value {
    display: block;
    font-size: 1.5rem;
    font-weight: bold;
    color: var(--accent-color, #4a9eff);
  }

  .stat-label {
    display: block;
    font-size: 0.75rem;
    color: var(--text-secondary, #cccccc);
    margin-top: 0.25rem;
  }

  .tab-navigation {
    display: flex;
    background: var(--bg-secondary, #2a2a2a);
    border-bottom: 1px solid var(--border-color, #333);
  }

  .tab-btn {
    padding: 0.75rem 1rem;
    background: transparent;
    color: var(--text-secondary, #cccccc);
    border: none;
    cursor: pointer;
    transition: all 0.2s;
    border-bottom: 2px solid transparent;
  }

  .tab-btn:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.05));
    color: var(--text-primary, #ffffff);
  }

  .tab-btn.active {
    color: var(--accent-color, #4a9eff);
    border-bottom-color: var(--accent-color, #4a9eff);
    background: var(--bg-primary, #1a1a1a);
  }

  .dashboard-content {
    flex: 1;
    overflow: hidden;
  }

  /* Evolution Events Panel */
  .evolution-events-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .panel-header {
    padding: 1rem;
    background: var(--bg-secondary, #2a2a2a);
    border-bottom: 1px solid var(--border-color, #333);
  }

  .panel-header h4 {
    margin: 0 0 1rem 0;
    color: var(--text-primary, #ffffff);
  }

  .event-controls {
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

  .event-count {
    color: var(--text-secondary, #cccccc);
    font-size: 0.875rem;
  }

  .events-container {
    flex: 1;
    overflow-y: auto;
    padding: 0.5rem;
  }

  .evolution-event {
    margin-bottom: 0.5rem;
    border: 1px solid var(--border-color, #333);
    border-radius: 6px;
    overflow: hidden;
    transition: all 0.2s;
  }

  .evolution-event.impact-critical {
    border-left: 4px solid var(--error-color, #dc3545);
  }

  .evolution-event.impact-high {
    border-left: 4px solid var(--warning-color, #ffc107);
  }

  .evolution-event.impact-medium {
    border-left: 4px solid var(--info-color, #17a2b8);
  }

  .evolution-event.impact-low {
    border-left: 4px solid var(--success-color, #28a745);
  }

  .event-header {
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

  .event-header:hover {
    background: var(--bg-hover, rgba(255, 255, 255, 0.05));
  }

  .event-info {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .event-icon {
    font-size: 1.1rem;
  }

  .event-type {
    font-weight: bold;
    text-transform: capitalize;
  }

  .event-impact {
    padding: 0.125rem 0.5rem;
    border-radius: 10px;
    font-size: 0.75rem;
    font-weight: bold;
  }

  .impact-critical { background: var(--error-color, #dc3545); color: white; }
  .impact-high { background: var(--warning-color, #ffc107); color: black; }
  .impact-medium { background: var(--info-color, #17a2b8); color: white; }
  .impact-low { background: var(--success-color, #28a745); color: white; }
  .impact-unknown { background: var(--secondary-color, #6c757d); color: white; }

  .event-meta {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.875rem;
  }

  .event-timestamp {
    font-family: 'Courier New', monospace;
    color: var(--text-secondary, #cccccc);
    font-size: 0.75rem;
  }

  .event-source {
    color: var(--text-secondary, #cccccc);
    font-style: italic;
  }

  .expand-icon {
    color: var(--text-secondary, #cccccc);
    transition: transform 0.2s;
  }

  .event-details {
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

  .event-summary {
    margin: 0;
    color: var(--text-secondary, #cccccc);
  }

  .context-id {
    color: var(--accent-color, #4a9eff);
    font-family: 'Courier New', monospace;
  }

  .changes-list {
    margin: 0;
    padding-left: 1.5rem;
  }

  .changes-list li {
    margin-bottom: 0.5rem;
    color: var(--text-secondary, #cccccc);
  }

  .change-type {
    font-weight: bold;
    color: var(--accent-color, #4a9eff);
  }

  .change-diff {
    margin-top: 0.25rem;
    font-size: 0.875rem;
  }

  .diff-before, .diff-after {
    display: block;
    font-family: 'Courier New', monospace;
  }

  .diff-before {
    color: var(--error-color, #dc3545);
  }

  .diff-after {
    color: var(--success-color, #28a745);
  }

  .concept-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
  }

  .concept-tag {
    padding: 0.125rem 0.5rem;
    background: var(--accent-color, rgba(74, 158, 255, 0.2));
    color: var(--accent-color, #4a9eff);
    border-radius: 12px;
    font-size: 0.75rem;
    border: 1px solid var(--accent-color, #4a9eff);
  }

  .metrics-text, .metadata-text {
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

  /* Contexts Panel */
  .contexts-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .contexts-grid {
    flex: 1;
    padding: 1rem;
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 1rem;
    overflow-y: auto;
  }

  .context-card {
    background: var(--bg-secondary, #2a2a2a);
    border: 1px solid var(--border-color, #333);
    border-radius: 8px;
    padding: 1rem;
    transition: all 0.2s;
  }

  .context-card:hover {
    border-color: var(--accent-color, #4a9eff);
    transform: translateY(-2px);
  }

  .context-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .context-header h5 {
    margin: 0;
    color: var(--text-primary, #ffffff);
  }

  .context-status {
    padding: 0.125rem 0.5rem;
    border-radius: 12px;
    font-size: 0.75rem;
    font-weight: bold;
  }

  .status-active { background: var(--success-color, #28a745); color: white; }
  .status-evolving { background: var(--info-color, #17a2b8); color: white; }
  .status-stable { background: var(--secondary-color, #6c757d); color: white; }
  .status-deprecated { background: var(--warning-color, #ffc107); color: black; }
  .status-unknown { background: var(--border-color, #333); color: var(--text-secondary, #cccccc); }

  .context-info {
    margin-bottom: 0.5rem;
    font-size: 0.875rem;
    color: var(--text-secondary, #cccccc);
  }

  .context-info div {
    margin-bottom: 0.25rem;
  }

  .context-description {
    margin-bottom: 0.5rem;
    color: var(--text-secondary, #cccccc);
    font-size: 0.875rem;
  }

  .context-stats {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
    font-size: 0.75rem;
    color: var(--text-tertiary, #999999);
  }

  .context-select-btn {
    width: 100%;
    padding: 0.5rem;
    background: var(--accent-color, #4a9eff);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    transition: background-color 0.2s;
  }

  .context-select-btn:hover {
    background: var(--accent-hover, #3a8eef);
  }

  /* Versions Panel */
  .versions-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .versions-container {
    flex: 1;
    padding: 1rem;
    overflow-y: auto;
  }

  .version-group {
    margin-bottom: 2rem;
    border: 1px solid var(--border-color, #333);
    border-radius: 8px;
    overflow: hidden;
  }

  .version-group h5 {
    margin: 0;
    padding: 1rem;
    background: var(--bg-secondary, #2a2a2a);
    color: var(--text-primary, #ffffff);
    border-bottom: 1px solid var(--border-color, #333);
  }

  .version-timeline {
    padding: 1rem;
  }

  .version-item {
    border-left: 2px solid var(--accent-color, #4a9eff);
    padding-left: 1rem;
    margin-bottom: 1rem;
    position: relative;
  }

  .version-item::before {
    content: '';
    position: absolute;
    left: -5px;
    top: 0.5rem;
    width: 8px;
    height: 8px;
    background: var(--accent-color, #4a9eff);
    border-radius: 50%;
  }

  .version-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .version-number {
    font-weight: bold;
    color: var(--text-primary, #ffffff);
  }

  .version-timestamp {
    font-size: 0.875rem;
    color: var(--text-secondary, #cccccc);
    font-family: 'Courier New', monospace;
  }

  .version-summary {
    margin: 0 0 0.5rem 0;
    color: var(--text-secondary, #cccccc);
    font-size: 0.875rem;
  }

  .changes-count {
    font-size: 0.75rem;
    color: var(--text-tertiary, #999999);
  }

  /* Graph Panel */
  .graph-panel {
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .graph-placeholder {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    color: var(--text-secondary, #cccccc);
    text-align: center;
    padding: 2rem;
  }

  .graph-placeholder .icon {
    font-size: 3rem;
    margin-bottom: 1rem;
    opacity: 0.6;
  }

  .placeholder-note {
    font-size: 0.875rem;
    color: var(--text-tertiary, #999999);
    margin-top: 0.5rem;
  }

  /* Empty states */
  .empty-events, .empty-contexts, .empty-versions {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: var(--text-secondary, #cccccc);
    text-align: center;
  }

  .empty-events .icon, .empty-contexts .icon, .empty-versions .icon {
    font-size: 2rem;
    margin-bottom: 0.5rem;
    opacity: 0.6;
  }

  .error-banner {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 1rem;
    background: rgba(220, 53, 69, 0.1);
    color: var(--error-color, #dc3545);
    border-top: 1px solid var(--error-color, #dc3545);
  }

  /* Responsive Design */
  @media (max-width: 768px) {
    .header {
      flex-direction: column;
      align-items: stretch;
      gap: 1rem;
    }

    .controls {
      justify-content: center;
      flex-wrap: wrap;
    }

    .stats-bar {
      flex-wrap: wrap;
      gap: 0.5rem;
    }

    .tab-navigation {
      flex-wrap: wrap;
    }

    .contexts-grid {
      grid-template-columns: 1fr;
    }

    .event-controls, .filters {
      flex-direction: column;
      align-items: stretch;
      gap: 0.5rem;
    }
  }
</style>