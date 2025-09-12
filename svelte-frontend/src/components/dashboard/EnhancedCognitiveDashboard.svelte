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
                            <div class="probe-card" data-testid={`probe-${key}`}>
                                <div class="probe-header">
                                    <div class="probe-name">{key}</div>
                                    <div class="status-indicator status-{(probe.status || 'unknown') === 'healthy' ? 'healthy' : (probe.status === 'unavailable' ? 'unhealthy' : (probe.status === 'error' ? 'unhealthy' : 'warning'))}">
                                        <div class="status-dot"></div>
                                        <span class="status-text">{probe.status || 'unknown'}</span>
                                    </div>
                                </div>
                                <div class="probe-body">
                                    {#if probe.timestamp}
                                        <div class="probe-row"><span>timestamp:</span> <code>{fmtTS(probe.timestamp)}</code></div>
                                    {/if}
                                    {#if probe.production_db !== undefined}
                                        <div class="probe-row"><span>production_db:</span> <code>{fmtBool(probe.production_db)}</code></div>
                                    {/if}
                                    {#if probe.legacy_fallback !== undefined}
                                        <div class="probe-row"><span>legacy_fallback:</span> <code>{fmtBool(probe.legacy_fallback)}</code></div>
                                    {/if}
                                    {#if probe.total_vectors !== undefined}
                                        <div class="probe-row"><span>total_vectors:</span> <code>{probe.total_vectors}</code></div>
                                    {/if}
                                    {#if probe.initialized !== undefined}
                                        <div class="probe-row"><span>initialized:</span> <code>{fmtBool(probe.initialized)}</code></div>
                                    {/if}
                                    {#if probe.queue_size !== undefined}
                                        <div class="probe-row"><span>queue_size:</span> <code>{probe.queue_size}</code></div>
                                    {/if}
                                    {#if probe.active_sessions !== undefined}
                                        <div class="probe-row"><span>active_sessions:</span> <code>{probe.active_sessions}</code></div>
                                    {/if}
                                    {#if probe.available !== undefined}
                                        <div class="probe-row"><span>available:</span> <code>{fmtBool(probe.available)}</code></div>
                                    {/if}
                                    {#if probe.components_active !== undefined}
                                        <div class="probe-row"><span>components:</span> <code>{probe.components_active}/{probe.total_components}</code></div>
                                    {/if}
                                    {#if probe.processing_metrics}
                                        <div class="probe-subtitle">processing_metrics</div>
                                        <div class="probe-row"><span>documents_processed:</span> <code>{probe.processing_metrics.documents_processed}</code></div>
                                        <div class="probe-row"><span>entities_extracted:</span> <code>{probe.processing_metrics.entities_extracted}</code></div>
                                        <div class="probe-row"><span>relationships_extracted:</span> <code>{probe.processing_metrics.relationships_extracted}</code></div>
                                        <div class="probe-row"><span>queries_processed:</span> <code>{probe.processing_metrics.queries_processed}</code></div>
                                    {/if}
                                    {#if probe.knowledge_store}
                                        <div class="probe-subtitle">knowledge_store</div>
                                        <div class="probe-row"><span>total_items:</span> <code>{probe.knowledge_store.total_knowledge_items}</code></div>
                                        <div class="probe-row"><span>active_connections:</span> <code>{probe.knowledge_store.active_connections}</code></div>
                                    {/if}
                                    {#if probe.vector_store}
                                        <div class="probe-subtitle">vector_store</div>
                                        <div class="probe-row"><span>total_embeddings:</span> <code>{probe.vector_store.total_embeddings}</code></div>
                                        <div class="probe-row"><span>dimensions:</span> <code>{probe.vector_store.dimensions}</code></div>
                                    {/if}
                                    {#if Array.isArray(probe.errors) && probe.errors.length}
                                        <div class="probe-subtitle">errors</div>
                                        <div class="probe-errors">
                                            {#each probe.errors.slice(0,3) as err}
                                                <div class="probe-error">{err}</div>
                                            {/each}
                                            {#if probe.errors.length > 3}
                                                <div class="probe-error-more">+{probe.errors.length - 3} more…</div>
                                            {/if}
                                        </div>
                                    {/if}
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
    .probe-card { background: rgba(0,0,0,0.2); border: 1px solid rgba(100,120,150,0.2); border-radius: 10px; padding: 10px; }
    .probe-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
    .probe-name { font-weight: 600; font-size: 0.95rem; }
    .probe-body { font-size: 0.85rem; display: grid; gap: 6px; }
    .probe-row { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
    .probe-row span { opacity: 0.8; }
    .probes-loading, .probes-error { font-size: 0.9rem; opacity: 0.8; padding: 6px 0; }
    .probe-subtitle { margin-top: 4px; font-weight: 600; font-size: 0.8rem; opacity: 0.8; }
    .probe-errors { display: grid; gap: 2px; }
    .probe-error { font-size: 0.8rem; opacity: 0.9; background: rgba(239, 68, 68, 0.12); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: 6px; padding: 4px 6px; }
    .probe-error-more { font-size: 0.8rem; opacity: 0.7; }

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
