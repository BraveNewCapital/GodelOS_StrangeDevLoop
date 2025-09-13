<script>
    import { onMount, onDestroy } from 'svelte';
    import { enhancedCognitiveState, autonomousLearningState, streamState, enhancedCognitive } from '../../stores/enhanced-cognitive.js';
    
    // Import monitoring components
    import StreamOfConsciousnessMonitor from '../core/StreamOfConsciousnessMonitor.svelte';
    import AutonomousLearningMonitor from '../core/AutonomousLearningMonitor.svelte';
    import CognitiveStateMonitor from '../core/CognitiveStateMonitor.svelte';
    
    // Component props
    export let layout = 'grid'; // 'grid', 'tabs', 'accordion'
    export let compactMode = false;
    export let showHealth = true;
    export let autoRefresh = true;

    // Local state
    let cognitiveState = null;
    let systemHealth = null;
    let healthProbes = null;
    let probesError = '';
    let activeTab = 'overview';
    let isConnected = false;
    let lastUpdate = null;
    let isLoading = true;
    let selectedProbe = null;  // For probe detail modal
    let showProbeModal = false;

    // Subscriptions
    let unsubscribe;

    import { API_BASE_URL } from '../../config.js';

    function fmtBool(v) { return typeof v === 'boolean' ? (v ? 'true' : 'false') : String(v); }
    function fmtTS(ts) {
        try {
            if (!ts) return '';
            const d = new Date(ts > 10_000_000_000 ? ts : ts * 1000);
            return d.toLocaleTimeString();
        } catch { return String(ts); }
    }

    async function fetchHealthProbes() {
        try {
            const res = await fetch(`${API_BASE_URL}/api/health`, { signal: AbortSignal.timeout(6000) });
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json();
            healthProbes = data?.probes || null;
            probesError = '';
        } catch (e) {
            probesError = String(e?.message || e);
            healthProbes = null;
        }
    }

    function getProbeStatusColor(probe) {
        const status = probe?.status || 'unknown';
        switch (status) {
            case 'healthy': return 'emerald';
            case 'warning': return 'amber';
            case 'error': case 'unavailable': return 'red';
            default: return 'gray';
        }
    }

    function openProbeModal(probeName, probeData) {
        selectedProbe = { name: probeName, data: probeData };
        showProbeModal = true;
    }

    function closeProbeModal() {
        showProbeModal = false;
        selectedProbe = null;
    }

    function getHealthStatus() {
        if (!systemHealth) return { status: 'unknown', color: 'gray', score: 0 };
        
        const components = [
            systemHealth?.inferenceEngine,
            systemHealth?.knowledgeStore,
            systemHealth?.autonomousLearning,
            systemHealth?.cognitiveStreaming
        ];
        
        const healthy = components.filter(c => c === 'healthy').length;
        const total = components.length;
        const score = total > 0 ? (healthy / total) * 100 : 0;
        
        if (healthy === total) return { status: 'excellent', color: 'emerald', score };
        if (healthy >= total * 0.75) return { status: 'good', color: 'amber', score };
        if (healthy >= total * 0.5) return { status: 'degraded', color: 'orange', score };
        return { status: 'critical', color: 'red', score };
    }

    onMount(() => {
        // Subscribe to cognitive state
        unsubscribe = enhancedCognitive.subscribe(state => {
            cognitiveState = state;
            systemHealth = state.systemHealth;
            isConnected = state.cognitiveStreaming?.connected || false;
            lastUpdate = new Date();
            isLoading = false;
        });

        // Initialize enhanced cognitive systems - REMOVED to prevent duplicate initialization
        // (App.svelte already handles initialization)
        
        // Start automatic data fetching
        startAutoRefresh();
        fetchHealthProbes();
    });
    
    function startAutoRefresh() {
        console.log('� Dashboard auto-refresh enabled');
        
        // Initial fetch
        refreshAllSystems();
        
        // Enable periodic refresh
        if (autoRefresh) {
            const interval = setInterval(() => {
                if (autoRefresh) {
                    refreshAllSystems();
                }
            }, 30000); // 30 second intervals
            
            // Store interval ID for cleanup
            return () => clearInterval(interval);
        }
    }

    onDestroy(() => {
        if (unsubscribe) unsubscribe();
    });

    function formatUptime(seconds) {
        if (!seconds) return 'Unknown';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours}h ${minutes}m`;
    }

    function refreshAllSystems() {
        isLoading = true;
        
        // Call all the enhanced cognitive store update methods
        enhancedCognitive.refreshSystemHealth();
        enhancedCognitive.refreshAutonomousState();
        enhancedCognitive.refreshStreamingState();
        
        // Also manually call the update methods
        enhancedCognitive.updateHealthStatus();
        enhancedCognitive.updateAutonomousLearningState();
        enhancedCognitive.updateStreamingStatus();
        fetchHealthProbes();
        setTimeout(() => isLoading = false, 1000);
    }

    $: healthStatus = getHealthStatus();
</script>

<div class="enhanced-dashboard" data-testid="enhanced-cognitive-dashboard">
    <!-- Modern Header with Glassmorphism -->
    <header class="dashboard-header">
        <div class="header-content">
            <div class="header-info">
                <div class="header-title">
                    <div class="title-icon">🧠</div>
                    <div>
                        <h1 class="title">Enhanced Cognitive Dashboard</h1>
                        <p class="subtitle">Real-time monitoring of autonomous cognitive processes</p>
                    </div>
                </div>
                
                <div class="header-stats">
                    <div class="stat-item">
                        <div class="stat-indicator {isConnected ? 'connected' : 'disconnected'}">
                            <div class="indicator-dot"></div>
                        </div>
                        <span class="stat-label">{isConnected ? 'Connected' : 'Disconnected'}</span>
                    </div>
                    
                    <div class="stat-item">
                        <div class="health-badge health-{healthStatus.color}">
                            <div class="health-icon">💚</div>
                            <span class="health-text">{Math.round(healthStatus.score)}%</span>
                        </div>
                        <span class="stat-label">{healthStatus.status}</span>
                    </div>
                    
                    {#if lastUpdate}
                        <div class="stat-item">
                            <div class="update-time">
                                {lastUpdate.toLocaleTimeString()}
                            </div>
                            <span class="stat-label">Last update</span>
                        </div>
                    {/if}
                </div>
            </div>
            
            <div class="header-actions">
                <button
                    on:click={refreshAllSystems}
                    class="action-btn refresh-btn"
                    class:loading={isLoading}
                    disabled={isLoading}
                >
                    <div class="btn-icon" class:spinning={isLoading}>🔄</div>
                    <span>Refresh</span>
                </button>
            </div>
        </div>
    </header>

    <!-- System Health Overview -->
    {#if showHealth && systemHealth}
        <section class="health-overview">
            <h2 class="section-title">System Health</h2>
            
            <div class="health-grid">
                <!-- Inference Engine -->
                <div class="health-card">
                    <div class="card-header">
                        <div class="card-icon">⚡</div>
                        <div class="card-info">
                            <h3 class="card-title">Inference Engine</h3>
                            <p class="card-metric">~0ms avg response</p>
                        </div>
                    </div>
                    <div class="status-indicator status-{systemHealth?.inferenceEngine === 'healthy' ? 'healthy' : 'unhealthy'}">
                        <div class="status-dot"></div>
                        <span class="status-text">{systemHealth?.inferenceEngine || 'unknown'}</span>
                    </div>
                </div>

                <!-- Knowledge Store -->
                <div class="health-card">
                    <div class="card-header">
                        <div class="card-icon">📚</div>
                        <div class="card-info">
                            <h3 class="card-title">Knowledge Store</h3>
                            <p class="card-metric">0 entities indexed</p>
                        </div>
                    </div>
                    <div class="status-indicator status-{systemHealth?.knowledgeStore === 'healthy' ? 'healthy' : 'unhealthy'}">
                        <div class="status-dot"></div>
                        <span class="status-text">{systemHealth?.knowledgeStore || 'unknown'}</span>
                    </div>
                </div>

                <!-- Autonomous Learning -->
                <div class="health-card">
                    <div class="card-header">
                        <div class="card-icon">🤖</div>
                        <div class="card-info">
                            <h3 class="card-title">Autonomous Learning</h3>
                            <p class="card-metric">0 active plans</p>
                        </div>
                    </div>
                    <div class="status-indicator status-{systemHealth?.autonomousLearning === 'healthy' ? 'healthy' : 'unhealthy'}">
                        <div class="status-dot"></div>
                        <span class="status-text">{systemHealth?.autonomousLearning || 'unknown'}</span>
                    </div>
                </div>

                <!-- Cognitive Streaming -->
                <div class="health-card">
                    <div class="card-header">
                        <div class="card-icon">🌊</div>
                        <div class="card-info">
                            <h3 class="card-title">Cognitive Streaming</h3>
                            <p class="card-metric">0 active clients</p>
                        </div>
                    </div>
                    <div class="status-indicator status-{systemHealth?.cognitiveStreaming === 'healthy' ? 'healthy' : 'unhealthy'}">
                        <div class="status-dot"></div>
                        <span class="status-text">{systemHealth?.cognitiveStreaming || 'unknown'}</span>
                    </div>
                </div>
            </div>

            <!-- Subsystem Health Probes -->
            <div class="probes" data-testid="health-probes">
                <h3 class="probes-title">Subsystem Probes</h3>
                {#if probesError}
                    <div class="probes-error">Failed to load probes: {probesError}</div>
                {:else if healthProbes}
                    <div class="probes-grid">
                        {#each Object.entries(healthProbes) as [key, probe]}
                            <div class="probe-card probe-card-clickable" 
                                 data-testid={`probe-${key}`}
                                 on:click={() => openProbeModal(key, probe)}
                                 on:keydown={(e) => e.key === 'Enter' && openProbeModal(key, probe)}
                                 tabindex="0"
                                 role="button"
                                 aria-label={`View details for ${key} probe`}>
                                <div class="probe-header">
                                    <div class="probe-name">{key}</div>
                                    <div class="status-indicator status-{getProbeStatusColor(probe)}">
                                        <div class="status-dot"></div>
                                        <span class="status-text">{probe.status || 'unknown'}</span>
                                    </div>
                                </div>
                                <div class="probe-body">
                                    {#if probe.timestamp}
                                        <div class="probe-row"><span>Last Check:</span> <code>{fmtTS(probe.timestamp)}</code></div>
                                    {/if}
                                    {#if probe.total_vectors !== undefined}
                                        <div class="probe-row"><span>Vectors:</span> <code>{probe.total_vectors}</code></div>
                                    {/if}
                                    {#if probe.queue_size !== undefined}
                                        <div class="probe-row"><span>Queue:</span> <code>{probe.queue_size}</code></div>
                                    {/if}
                                    <div class="probe-row">
                                        <span class="probe-click-hint">Click for details →</span>
                                    </div>
                                </div>
                            </div>
                        {/each}
                    </div>
                {:else}
                    <div class="probes-loading">Loading probes…</div>
                {/if}
            </div>

            <div class="health-footer">
                <div class="uptime-info">
                    <span class="uptime-label">System Uptime:</span>
                    <span class="uptime-value">{formatUptime(systemHealth?.uptime)}</span>
                </div>
            </div>
        </section>
    {/if}

    <!-- Main Content Area -->
    <main class="dashboard-content">
        {#if layout === 'tabs'}
            <!-- Modern Tab Navigation -->
            <nav class="tab-navigation">
                <div class="tab-list">
                    <button
                        on:click={() => activeTab = 'overview'}
                        class="tab-button"
                        class:active={activeTab === 'overview'}
                    >
                        <div class="tab-icon">📊</div>
                        <span>Overview</span>
                    </button>
                    <button
                        on:click={() => activeTab = 'consciousness'}
                        class="tab-button"
                        class:active={activeTab === 'consciousness'}
                    >
                        <div class="tab-icon">🧠</div>
                        <span>Stream of Consciousness</span>
                    </button>
                    <button
                        on:click={() => activeTab = 'learning'}
                        class="tab-button"
                        class:active={activeTab === 'learning'}
                    >
                        <div class="tab-icon">🤖</div>
                        <span>Autonomous Learning</span>
                    </button>
                    <button
                        on:click={() => activeTab = 'cognitive'}
                        class="tab-button"
                        class:active={activeTab === 'cognitive'}
                    >
                        <div class="tab-icon">🎯</div>
                        <span>Cognitive State</span>
                    </button>
                </div>
            </nav>

            <!-- Tab Content -->
            <div class="tab-content">
                {#if activeTab === 'overview'}
                    <div class="overview-panel">
                        <div class="overview-hero">
                            <h2 class="hero-title">Enhanced Cognitive Capabilities</h2>
                            <p class="hero-description">
                                Monitor and interact with advanced AI cognitive processes in real-time
                            </p>
                        </div>
                        
                        <div class="feature-grid">
                            <div class="feature-card">
                                <div class="feature-icon">🧠</div>
                                <h3 class="feature-title">Stream of Consciousness</h3>
                                <p class="feature-description">
                                    Real-time visibility into cognitive processes, reasoning patterns, and decision-making flows
                                </p>
                            </div>
                            
                            <div class="feature-card">
                                <div class="feature-icon">📚</div>
                                <h3 class="feature-title">Autonomous Learning</h3>
                                <p class="feature-description">
                                    Intelligent knowledge gap detection and autonomous acquisition strategies
                                </p>
                            </div>
                            
                            <div class="feature-card">
                                <div class="feature-icon">👁️</div>
                                <h3 class="feature-title">Cognitive Transparency</h3>
                                <p class="feature-description">
                                    Complete transparency into attention focus, processing load, and system state
                                </p>
                            </div>
                        </div>
                    </div>
                {:else if activeTab === 'consciousness'}
                    <div class="component-panel">
                        <StreamOfConsciousnessMonitor {compactMode} />
                    </div>
                {:else if activeTab === 'learning'}
                    <div class="component-panel">
                        <AutonomousLearningMonitor {compactMode} />
                    </div>
                {:else if activeTab === 'cognitive'}
                    <div class="component-panel">
                        <CognitiveStateMonitor {compactMode} />
                    </div>
                {/if}
            </div>
        {:else if layout === 'grid'}
            <!-- Modern Grid Layout -->
            <div class="grid-layout">
                <div class="grid-column">
                    <div class="component-wrapper">
                        <StreamOfConsciousnessMonitor {compactMode} />
                    </div>
                    <div class="component-wrapper">
                        <CognitiveStateMonitor {compactMode} />
                    </div>
                </div>
                <div class="grid-column">
                    <div class="component-wrapper">
                        <AutonomousLearningMonitor {compactMode} />
                    </div>
                </div>
            </div>
        {:else if layout === 'accordion'}
            <!-- Accordion Layout -->
            <div class="accordion-layout">
                <div class="accordion-item">
                    <StreamOfConsciousnessMonitor {compactMode} showFilters={false} />
                </div>
                <div class="accordion-item">
                    <AutonomousLearningMonitor {compactMode} showDetails={false} />
                </div>
                <div class="accordion-item">
                    <CognitiveStateMonitor {compactMode} />
                </div>
            </div>
        {/if}
    </main>
</div>

<!-- Probe Detail Modal -->
{#if showProbeModal && selectedProbe}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div class="modal-overlay" on:click={closeProbeModal}>
        <div class="modal-content" on:click|stopPropagation>
            <div class="modal-header">
                <h2>Probe Details: {selectedProbe.name}</h2>
                <button class="modal-close" on:click={closeProbeModal} aria-label="Close modal">×</button>
            </div>
            <div class="modal-body">
                <div class="probe-status-banner status-{getProbeStatusColor(selectedProbe.data)}">
                    <div class="status-dot"></div>
                    <span>Status: {selectedProbe.data.status || 'unknown'}</span>
                </div>
                
                <div class="probe-details-grid">
                    {#each Object.entries(selectedProbe.data) as [key, value]}
                        <div class="detail-row">
                            <div class="detail-label">{key}:</div>
                            <div class="detail-value">
                                {#if key === 'timestamp'}
                                    <code>{fmtTS(value)}</code>
                                {:else if typeof value === 'boolean'}
                                    <code class="bool-{value}">{fmtBool(value)}</code>
                                {:else if typeof value === 'object' && value !== null}
                                    <details>
                                        <summary>View object</summary>
                                        <pre>{JSON.stringify(value, null, 2)}</pre>
                                    </details>
                                {:else}
                                    <code>{value}</code>
                                {/if}
                            </div>
                        </div>
                    {/each}
                </div>
            </div>
        </div>
    </div>
{/if}

<style>
    .enhanced-dashboard {
        min-height: 100vh;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }

    /* Header Styles */
    .dashboard-header {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 24px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
    }

    .header-content {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 2rem;
    }

    .header-info {
        flex: 1;
    }

    .header-title {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1.5rem;
    }

    .title-icon {
        font-size: 3rem;
        filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.2));
    }

    .title {
        font-size: 2.5rem;
        font-weight: 700;
        color: white;
        margin: 0;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }

    .subtitle {
        font-size: 1.125rem;
        color: rgba(255, 255, 255, 0.8);
        margin: 0.5rem 0 0 0;
        font-weight: 400;
    }

    .header-stats {
        display: flex;
        gap: 2rem;
        align-items: center;
    }

    .stat-item {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.5rem;
    }

    .stat-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .indicator-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        animation: pulse 2s infinite;
    }

    .stat-indicator.connected .indicator-dot {
        background: #10b981;
    }

    .stat-indicator.disconnected .indicator-dot {
        background: #ef4444;
    }

    .health-badge {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
    }

    .health-badge.health-emerald {
        background: rgba(16, 185, 129, 0.2);
        border-color: rgba(16, 185, 129, 0.3);
    }

    .health-badge.health-amber {
        background: rgba(245, 158, 11, 0.2);
        border-color: rgba(245, 158, 11, 0.3);
    }

    .health-badge.health-red {
        background: rgba(239, 68, 68, 0.2);
        border-color: rgba(239, 68, 68, 0.3);
    }

    .health-icon {
        font-size: 1.25rem;
    }

    .health-text {
        font-weight: 600;
        color: white;
    }

    .stat-label {
        font-size: 0.875rem;
        color: rgba(255, 255, 255, 0.7);
        font-weight: 500;
    }

    .update-time {
        padding: 0.5rem 1rem;
        border-radius: 12px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: white;
        font-weight: 500;
    }

    /* Probes */
    .probes { margin-top: 1.5rem; }
    .probes-title { margin: 0 0 0.5rem 0; font-size: 1.1rem; opacity: 0.9; }
    .probes-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 12px; }
    .probe-card { 
        background: rgba(0,0,0,0.2); 
        border: 1px solid rgba(100,120,150,0.2); 
        border-radius: 10px; 
        padding: 10px; 
        transition: all 0.2s ease;
    }
    .probe-card-clickable {
        cursor: pointer;
        user-select: none;
    }
    .probe-card-clickable:hover {
        background: rgba(0,0,0,0.3);
        border-color: rgba(100,120,150,0.4);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.2);
    }
    .probe-card-clickable:focus {
        outline: 2px solid rgba(99, 102, 241, 0.5);
        outline-offset: 2px;
    }
    .probe-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .probe-name { font-weight: 600; font-size: 0.95rem; }
    .probe-body { font-size: 0.85rem; display: grid; gap: 6px; }
    .probe-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .probe-row span { opacity: 0.8; }
    .probe-click-hint { 
        opacity: 0.6; 
        font-size: 0.75rem; 
        font-style: italic; 
        color: #a78bfa;
    }
    .probes-loading, .probes-error { font-size: 0.9rem; opacity: 0.8; padding: 6px 0; }
    .probe-subtitle { margin-top: 4px; font-weight: 600; font-size: 0.8rem; opacity: 0.8; }
    .probe-errors { display: grid; gap: 2px; }
    .probe-error { font-size: 0.8rem; opacity: 0.9; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 4px 6px; }
    .probe-error-more { font-size: 0.8rem; opacity: 0.7; }

    /* Enhanced Status Colors */
    .status-emerald .status-dot { background: #10b981; }
    .status-emerald .status-text { color: #10b981; }
    .status-amber .status-dot { background: #f59e0b; }
    .status-amber .status-text { color: #f59e0b; }
    .status-red .status-dot { background: #ef4444; }
    .status-red .status-text { color: #ef4444; }
    .status-gray .status-dot { background: #6b7280; }
    .status-gray .status-text { color: #6b7280; }

    /* Modal Styles */
    .modal-overlay {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(4px);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 1000;
        padding: 1rem;
    }

    .modal-content {
        background: linear-gradient(145deg, #1f2937, #111827);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        max-width: 600px;
        width: 100%;
        max-height: 80vh;
        overflow: hidden;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }

    .modal-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        background: rgba(255, 255, 255, 0.05);
    }

    .modal-header h2 {
        margin: 0;
        color: white;
        font-size: 1.25rem;
        font-weight: 600;
    }

    .modal-close {
        background: none;
        border: none;
        color: #9ca3af;
        font-size: 1.5rem;
        cursor: pointer;
        padding: 0.25rem;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        transition: all 0.2s ease;
    }

    .modal-close:hover {
        background: rgba(255, 255, 255, 0.1);
        color: white;
    }

    .modal-body {
        padding: 1.5rem;
        overflow-y: auto;
        max-height: calc(80vh - 120px);
    }

    .probe-status-banner {
        display: flex;
        align-items: center;
        gap: 0.75rem;
        padding: 1rem;
        border-radius: 10px;
        margin-bottom: 1.5rem;
        font-weight: 500;
    }

    .probe-status-banner.status-emerald {
        background: rgba(16, 185, 129, 0.1);
        border: 1px solid rgba(16, 185, 129, 0.3);
        color: #10b981;
    }

    .probe-status-banner.status-amber {
        background: rgba(245, 158, 11, 0.1);
        border: 1px solid rgba(245, 158, 11, 0.3);
        color: #f59e0b;
    }

    .probe-status-banner.status-red {
        background: rgba(239, 68, 68, 0.1);
        border: 1px solid rgba(239, 68, 68, 0.3);
        color: #ef4444;
    }

    .probe-status-banner.status-gray {
        background: rgba(107, 114, 128, 0.1);
        border: 1px solid rgba(107, 114, 128, 0.3);
        color: #6b7280;
    }

    .probe-details-grid {
        display: grid;
        gap: 1rem;
    }

    .detail-row {
        display: grid;
        grid-template-columns: 1fr 2fr;
        gap: 1rem;
        align-items: start;
        padding: 0.75rem;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }

    .detail-label {
        font-weight: 500;
        color: #d1d5db;
        word-break: break-word;
    }

    .detail-value {
        color: white;
    }

    .detail-value code {
        background: rgba(0, 0, 0, 0.3);
        padding: 0.25rem 0.5rem;
        border-radius: 4px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        font-family: 'SF Mono', Monaco, 'Cascadia Code', 'Roboto Mono', Consolas, 'Courier New', monospace;
        font-size: 0.875rem;
    }

    .detail-value .bool-true {
        color: #10b981;
    }

    .detail-value .bool-false {
        color: #ef4444;
    }

    .detail-value details {
        margin-top: 0.5rem;
    }

    .detail-value summary {
        cursor: pointer;
        color: #a78bfa;
        font-size: 0.875rem;
        margin-bottom: 0.5rem;
    }

    .detail-value pre {
        background: rgba(0, 0, 0, 0.4);
        padding: 1rem;
        border-radius: 6px;
        overflow: auto;
        font-size: 0.8rem;
        border: 1px solid rgba(255, 255, 255, 0.1);
        max-height: 200px;
    }

    .header-actions {
        display: flex;
        gap: 1rem;
    }

    .action-btn {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.75rem 1.5rem;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        color: white;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        backdrop-filter: blur(10px);
    }

    .action-btn:hover:not(:disabled) {
        background: rgba(255, 255, 255, 0.2);
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
    }

    .action-btn:disabled {
        opacity: 0.6;
        cursor: not-allowed;
    }

    .btn-icon {
        font-size: 1.25rem;
        transition: transform 0.2s ease;
    }

    .btn-icon.spinning {
        animation: spin 1s linear infinite;
    }

    /* Health Overview */
    .health-overview {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
    }

    .section-title {
        font-size: 1.5rem;
        font-weight: 700;
        color: white;
        margin: 0 0 1.5rem 0;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }

    .health-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
        gap: 1.5rem;
        margin-bottom: 2rem;
    }

    .health-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 16px;
        padding: 1.5rem;
        transition: all 0.2s ease;
    }

    .health-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        background: rgba(255, 255, 255, 0.15);
    }

    .card-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        margin-bottom: 1rem;
    }

    .card-icon {
        font-size: 2rem;
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.2));
    }

    .card-info {
        flex: 1;
    }

    .card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: white;
        margin: 0 0 0.25rem 0;
    }

    .card-metric {
        font-size: 0.875rem;
        color: rgba(255, 255, 255, 0.7);
        margin: 0;
    }

    .status-indicator {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.05);
    }

    .status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }

    .status-indicator.status-healthy .status-dot {
        background: #10b981;
        animation: pulse 2s infinite;
    }

    .status-indicator.status-unhealthy .status-dot {
        background: #ef4444;
    }

    .status-text {
        font-size: 0.875rem;
        font-weight: 500;
        color: white;
        text-transform: capitalize;
    }

    .health-footer {
        display: flex;
        justify-content: center;
        padding-top: 1rem;
        border-top: 1px solid rgba(255, 255, 255, 0.1);
    }

    .uptime-info {
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }

    .uptime-label {
        color: rgba(255, 255, 255, 0.7);
        font-size: 0.875rem;
    }

    .uptime-value {
        color: white;
        font-weight: 600;
        font-size: 0.875rem;
    }

    /* Main Content */
    .dashboard-content {
        background: rgba(255, 255, 255, 0.05);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        overflow: hidden;
    }

    /* Tab Navigation */
    .tab-navigation {
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding: 0 2rem;
    }

    .tab-list {
        display: flex;
        gap: 0.5rem;
    }

    .tab-button {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 1rem 1.5rem;
        background: none;
        border: none;
        color: rgba(255, 255, 255, 0.7);
        font-weight: 500;
        cursor: pointer;
        border-radius: 12px 12px 0 0;
        transition: all 0.2s ease;
        position: relative;
    }

    .tab-button:hover {
        color: white;
        background: rgba(255, 255, 255, 0.05);
    }

    .tab-button.active {
        color: white;
        background: rgba(255, 255, 255, 0.1);
    }

    .tab-button.active::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, #10b981, #3b82f6);
    }

    .tab-icon {
        font-size: 1.25rem;
    }

    .tab-content {
        padding: 2rem;
    }

    /* Overview Panel */
    .overview-panel {
        text-align: center;
    }

    .overview-hero {
        margin-bottom: 3rem;
    }

    .hero-title {
        font-size: 2rem;
        font-weight: 700;
        color: white;
        margin: 0 0 1rem 0;
        text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
    }

    .hero-description {
        font-size: 1.125rem;
        color: rgba(255, 255, 255, 0.8);
        margin: 0;
        max-width: 600px;
        margin-left: auto;
        margin-right: auto;
    }

    .feature-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
        gap: 2rem;
    }

    .feature-card {
        background: rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        transition: all 0.2s ease;
    }

    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
        background: rgba(255, 255, 255, 0.15);
    }

    .feature-icon {
        font-size: 3rem;
        margin-bottom: 1rem;
        filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.2));
    }

    .feature-title {
        font-size: 1.25rem;
        font-weight: 600;
        color: white;
        margin: 0 0 1rem 0;
    }

    .feature-description {
        font-size: 0.875rem;
        color: rgba(255, 255, 255, 0.8);
        line-height: 1.6;
        margin: 0;
    }

    /* Component Panels */
    .component-panel {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        overflow: hidden;
    }

    /* Grid Layout */
    .grid-layout {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 2rem;
        padding: 2rem;
    }

    .grid-column {
        display: flex;
        flex-direction: column;
        gap: 2rem;
    }

    .component-wrapper {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        overflow: hidden;
    }

    /* Accordion Layout */
    .accordion-layout {
        padding: 2rem;
    }

    .accordion-item {
        background: rgba(255, 255, 255, 0.02);
        border-radius: 12px;
        margin-bottom: 1rem;
        overflow: hidden;
    }

    .accordion-item:last-child {
        margin-bottom: 0;
    }

    /* Animations */
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }

    @keyframes spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    /* Responsive Design */
    @media (max-width: 768px) {
        .enhanced-dashboard {
            padding: 1rem;
        }

        .header-content {
            flex-direction: column;
            gap: 1rem;
        }

        .header-stats {
            flex-wrap: wrap;
            gap: 1rem;
        }

        .title {
            font-size: 2rem;
        }

        .health-grid {
            grid-template-columns: 1fr;
        }

        .grid-layout {
            grid-template-columns: 1fr;
        }

        .tab-list {
            flex-wrap: wrap;
        }

        .tab-button {
            padding: 0.75rem 1rem;
            font-size: 0.875rem;
        }
    }

    @media (max-width: 480px) {
        .header-title {
            flex-direction: column;
            text-align: center;
            gap: 0.5rem;
        }

        .title-icon {
            font-size: 2rem;
        }

        .title {
            font-size: 1.5rem;
        }

        .subtitle {
            font-size: 1rem;
        }
    }
</style>
