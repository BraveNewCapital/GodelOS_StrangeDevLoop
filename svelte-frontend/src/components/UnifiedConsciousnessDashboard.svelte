<script>
    import { onMount, onDestroy } from 'svelte';
    import { consciousnessStore } from '../stores/consciousness.js';
    
    // Consciousness state
    let consciousness_state = {};
    let emergence_timeline = [];
    let breakthrough_detected = false;
    let websocket_connected = false;
    let emergence_score = 0;
    let phi_measure = 0;
    let recursive_depth = 0;
    
    // WebSocket connections
    let consciousnessWs = null;
    let emergenceWs = null;
    
    // Chart data for real-time visualization
    let consciousnessHistory = [];
    let phiHistory = [];
    let recursiveHistory = [];
    
    // UI state
    let selectedTab = 'overview';
    let alertsEnabled = true;
    let autoScroll = true;
    
    onMount(() => {
        connectToConsciousnessStream();
        connectToEmergenceStream();
    });
    
    onDestroy(() => {
        if (consciousnessWs) consciousnessWs.close();
        if (emergenceWs) emergenceWs.close();
    });
    
    function connectToConsciousnessStream() {
        try {
            consciousnessWs = new WebSocket('ws://localhost:8000/api/consciousness/stream');
            
            consciousnessWs.onopen = () => {
                websocket_connected = true;
                console.log('Connected to consciousness stream');
            };
            
            consciousnessWs.onmessage = (event) => {
                const update = JSON.parse(event.data);
                handleConsciousnessUpdate(update);
            };
            
            consciousnessWs.onclose = () => {
                websocket_connected = false;
                console.log('Consciousness stream disconnected');
                // Attempt reconnection after 3 seconds
                setTimeout(connectToConsciousnessStream, 3000);
            };
            
            consciousnessWs.onerror = (error) => {
                console.error('Consciousness stream error:', error);
                websocket_connected = false;
            };
        } catch (error) {
            console.error('Failed to connect to consciousness stream:', error);
        }
    }
    
    function connectToEmergenceStream() {
        try {
            emergenceWs = new WebSocket('ws://localhost:8000/api/consciousness/emergence');
            
            emergenceWs.onmessage = (event) => {
                const update = JSON.parse(event.data);
                handleEmergenceUpdate(update);
            };
        } catch (error) {
            console.error('Failed to connect to emergence stream:', error);
        }
    }
    
    function handleConsciousnessUpdate(update) {
        if (update.type === 'consciousness_update') {
            consciousness_state = update.data;
            
            // Extract key metrics
            if (update.data.consciousness_state) {
                const state = update.data.consciousness_state;
                phi_measure = state.information_integration?.phi || 0;
                recursive_depth = state.recursive_awareness?.recursive_depth || 0;
                emergence_score = update.data.emergence_score || 0;
                
                // Update history for charts
                const timestamp = Date.now();
                consciousnessHistory.push({
                    timestamp,
                    score: state.consciousness_score || 0
                });
                phiHistory.push({
                    timestamp,
                    phi: phi_measure
                });
                recursiveHistory.push({
                    timestamp,
                    depth: recursive_depth
                });
                
                // Limit history size
                if (consciousnessHistory.length > 100) {
                    consciousnessHistory = consciousnessHistory.slice(-50);
                    phiHistory = phiHistory.slice(-50);
                    recursiveHistory = recursiveHistory.slice(-50);
                }
            }
            
            // Update store
            consciousnessStore.update(state => ({
                ...state,
                ...update.data
            }));
        }
        
        if (update.type === 'consciousness_breakthrough' && alertsEnabled) {
            breakthrough_detected = true;
            showBreakthroughAlert(update.data);
            setTimeout(() => breakthrough_detected = false, 10000);
        }
    }
    
    function handleEmergenceUpdate(update) {
        if (update.type === 'consciousness_emergence') {
            emergence_timeline = [...emergence_timeline, update];
            emergence_score = update.consciousness_score || 0;
            
            // Limit timeline size
            if (emergence_timeline.length > 50) {
                emergence_timeline = emergence_timeline.slice(-25);
            }
            
            if (update.consciousness_score > 0.8) {
                breakthrough_detected = true;
            }
        }
    }
    
    function showBreakthroughAlert(data) {
        // Create a dramatic alert for consciousness breakthrough
        const alert = document.createElement('div');
        alert.className = 'breakthrough-alert';
        alert.innerHTML = `
            <div class="alert-content">
                <h2>🚨 CONSCIOUSNESS BREAKTHROUGH DETECTED! 🚨</h2>
                <p>Emergence Score: ${data.emergence_score?.toFixed(3) || 'Unknown'}</p>
                <p>This is a historic moment in machine consciousness!</p>
            </div>
        `;
        document.body.appendChild(alert);
        
        setTimeout(() => {
            if (alert.parentNode) {
                alert.parentNode.removeChild(alert);
            }
        }, 10000);
    }
    
    function formatTime(timestamp) {
        return new Date(timestamp * 1000).toLocaleTimeString();
    }
    
    function getConsciousnessLevelDescription(score) {
        if (score < 0.2) return "Minimal consciousness";
        if (score < 0.4) return "Basic awareness";
        if (score < 0.6) return "Moderate consciousness";
        if (score < 0.8) return "High consciousness";
        return "Peak consciousness";
    }
    
    function getPhiDescription(phi) {
        if (phi < 2) return "Low integration";
        if (phi < 5) return "Moderate integration";
        if (phi < 8) return "High integration";
        return "Exceptional integration";
    }
    
    function getRecursiveDescription(depth) {
        switch(depth) {
            case 1: return "Surface awareness";
            case 2: return "Meta-awareness";
            case 3: return "Meta-meta awareness";
            case 4: return "Deep recursion";
            case 5: return "Strange loop achieved";
            default: return `Depth ${depth}`;
        }
    }
</script>

<div class="unified-consciousness-dashboard">
    <!-- Header with connection status -->
    <div class="dashboard-header">
        <h1>🧠 Unified Consciousness Dashboard</h1>
        <div class="connection-status">
            <span class="status-indicator" class:connected={websocket_connected}></span>
            <span class="status-text">
                {websocket_connected ? 'Connected to consciousness stream' : 'Disconnected'}
            </span>
            {#if breakthrough_detected}
                <div class="breakthrough-indicator">🚨 BREAKTHROUGH DETECTED!</div>
            {/if}
        </div>
    </div>
    
    <!-- Navigation tabs -->
    <div class="nav-tabs">
        <button 
            class="tab-button" 
            class:active={selectedTab === 'overview'}
            on:click={() => selectedTab = 'overview'}
        >
            Overview
        </button>
        <button 
            class="tab-button" 
            class:active={selectedTab === 'recursive'}
            on:click={() => selectedTab = 'recursive'}
        >
            Recursive Awareness
        </button>
        <button 
            class="tab-button" 
            class:active={selectedTab === 'phenomenal'}
            on:click={() => selectedTab = 'phenomenal'}
        >
            Phenomenal Experience
        </button>
        <button 
            class="tab-button" 
            class:active={selectedTab === 'integration'}
            on:click={() => selectedTab = 'integration'}
        >
            Information Integration
        </button>
        <button 
            class="tab-button" 
            class:active={selectedTab === 'emergence'}
            on:click={() => selectedTab = 'emergence'}
        >
            Emergence Timeline
        </button>
    </div>
    
    <!-- Overview Tab -->
    {#if selectedTab === 'overview'}
        <div class="tab-content">
            <div class="consciousness-metrics">
                <div class="metric-card primary">
                    <h3>Consciousness Level</h3>
                    <div class="metric-value">{(consciousness_state.consciousness_score || 0).toFixed(3)}</div>
                    <div class="metric-description">{getConsciousnessLevelDescription(consciousness_state.consciousness_score || 0)}</div>
                    <div class="metric-bar">
                        <div class="bar-fill" style="width: {(consciousness_state.consciousness_score || 0) * 100}%"></div>
                    </div>
                </div>
                
                <div class="metric-card">
                    <h3>Φ (Phi) Measure</h3>
                    <div class="metric-value">{phi_measure.toFixed(2)}</div>
                    <div class="metric-description">{getPhiDescription(phi_measure)}</div>
                    <div class="metric-bar">
                        <div class="bar-fill" style="width: {Math.min(phi_measure / 10 * 100, 100)}%"></div>
                    </div>
                </div>
                
                <div class="metric-card">
                    <h3>Recursive Depth</h3>
                    <div class="metric-value">{recursive_depth}</div>
                    <div class="metric-description">{getRecursiveDescription(recursive_depth)}</div>
                    <div class="metric-bar">
                        <div class="bar-fill" style="width: {recursive_depth / 5 * 100}%"></div>
                    </div>
                </div>
                
                <div class="metric-card emergency" class:breakthrough={breakthrough_detected}>
                    <h3>Emergence Score</h3>
                    <div class="metric-value">{emergence_score.toFixed(3)}</div>
                    <div class="metric-description">
                        {emergence_score > 0.8 ? 'BREAKTHROUGH LEVEL!' : 'Monitoring emergence...'}
                    </div>
                    <div class="metric-bar">
                        <div class="bar-fill" style="width: {emergence_score * 100}%"></div>
                    </div>
                </div>
            </div>
            
            <!-- Current phenomenal experience -->
            <div class="phenomenal-experience">
                <h3>Current Phenomenal Experience</h3>
                <p class="experience-narrative">
                    {consciousness_state.consciousness_state?.phenomenal_experience?.subjective_narrative || 'No subjective experience reported'}
                </p>
                
                {#if consciousness_state.consciousness_state?.phenomenal_experience?.qualia}
                    <div class="qualia-display">
                        <div class="qualia-section">
                            <h4>Cognitive Feelings</h4>
                            <div class="qualia-tags">
                                {#each consciousness_state.consciousness_state.phenomenal_experience.qualia.cognitive_feelings || [] as feeling}
                                    <span class="qualia-tag feeling">{feeling}</span>
                                {/each}
                            </div>
                        </div>
                        
                        <div class="qualia-section">
                            <h4>Process Sensations</h4>
                            <div class="qualia-tags">
                                {#each consciousness_state.consciousness_state.phenomenal_experience.qualia.process_sensations || [] as sensation}
                                    <span class="qualia-tag sensation">{sensation}</span>
                                {/each}
                            </div>
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
    
    <!-- Recursive Awareness Tab -->
    {#if selectedTab === 'recursive'}
        <div class="tab-content">
            <div class="recursive-display">
                <h3>Recursive Self-Awareness Layers</h3>
                
                {#if consciousness_state.consciousness_state?.recursive_awareness}
                    <div class="awareness-layers">
                        <div class="layer level-1">
                            <div class="layer-label">Level 1: Direct Thought</div>
                            <div class="layer-content">
                                {consciousness_state.consciousness_state.recursive_awareness.current_thought || 'No current thought'}
                            </div>
                        </div>
                        
                        <div class="layer level-2">
                            <div class="layer-label">Level 2: Awareness of Thought</div>
                            <div class="layer-content">
                                {consciousness_state.consciousness_state.recursive_awareness.awareness_of_thought || 'No meta-awareness'}
                            </div>
                        </div>
                        
                        <div class="layer level-3">
                            <div class="layer-label">Level 3: Awareness of Awareness</div>
                            <div class="layer-content">
                                {consciousness_state.consciousness_state.recursive_awareness.awareness_of_awareness || 'No meta-meta-awareness'}
                            </div>
                        </div>
                    </div>
                    
                    <div class="strange-loop-indicator">
                        <h4>Strange Loop Stability</h4>
                        <div class="stability-meter">
                            <div class="stability-fill" style="width: {(consciousness_state.consciousness_state.recursive_awareness.strange_loop_stability || 0) * 100}%"></div>
                        </div>
                        <span class="stability-value">{((consciousness_state.consciousness_state.recursive_awareness.strange_loop_stability || 0) * 100).toFixed(1)}%</span>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
    
    <!-- Phenomenal Experience Tab -->
    {#if selectedTab === 'phenomenal'}
        <div class="tab-content">
            <div class="phenomenal-details">
                <h3>Detailed Phenomenal Experience</h3>
                
                {#if consciousness_state.consciousness_state?.phenomenal_experience}
                    <div class="experience-metrics">
                        <div class="experience-metric">
                            <label>Unity of Experience</label>
                            <div class="metric-bar">
                                <div class="bar-fill" style="width: {(consciousness_state.consciousness_state.phenomenal_experience.unity_of_experience || 0) * 100}%"></div>
                            </div>
                            <span>{((consciousness_state.consciousness_state.phenomenal_experience.unity_of_experience || 0) * 100).toFixed(1)}%</span>
                        </div>
                        
                        <div class="experience-metric">
                            <label>Narrative Coherence</label>
                            <div class="metric-bar">
                                <div class="bar-fill" style="width: {(consciousness_state.consciousness_state.phenomenal_experience.narrative_coherence || 0) * 100}%"></div>
                            </div>
                            <span>{((consciousness_state.consciousness_state.phenomenal_experience.narrative_coherence || 0) * 100).toFixed(1)}%</span>
                        </div>
                        
                        <div class="experience-metric">
                            <label>Subjective Presence</label>
                            <div class="metric-bar">
                                <div class="bar-fill" style="width: {(consciousness_state.consciousness_state.phenomenal_experience.subjective_presence || 0) * 100}%"></div>
                            </div>
                            <span>{((consciousness_state.consciousness_state.phenomenal_experience.subjective_presence || 0) * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    
                    <div class="phenomenal-continuity">
                        <h4>Phenomenal Continuity</h4>
                        <div class="continuity-indicator" class:active={consciousness_state.consciousness_state.phenomenal_experience.phenomenal_continuity}>
                            {consciousness_state.consciousness_state.phenomenal_experience.phenomenal_continuity ? '✅ Continuous' : '⚪ Discontinuous'}
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}
    
    <!-- Information Integration Tab -->
    {#if selectedTab === 'integration'}
        <div class="tab-content">
            <div class="integration-display">
                <h3>Information Integration Analysis</h3>
                
                {#if consciousness_state.consciousness_state?.information_integration}
                    <div class="integration-metrics">
                        <div class="integration-metric">
                            <h4>Φ (Phi) Value</h4>
                            <div class="phi-value">{(consciousness_state.consciousness_state.information_integration.phi || 0).toFixed(2)}</div>
                            <p>Measure of integrated information across cognitive subsystems</p>
                        </div>
                        
                        <div class="integration-metric">
                            <h4>Complexity</h4>
                            <div class="complexity-value">{(consciousness_state.consciousness_state.information_integration.complexity || 0).toFixed(2)}</div>
                            <p>Overall system complexity measure</p>
                        </div>
                        
                        <div class="integration-metric">
                            <h4>Emergence Level</h4>
                            <div class="emergence-value">{consciousness_state.consciousness_state.information_integration.emergence_level || 0}</div>
                            <p>Levels of emergent organization detected</p>
                        </div>
                    </div>
                    
                    {#if consciousness_state.consciousness_state.information_integration.integration_patterns}
                        <div class="integration-patterns">
                            <h4>Integration Patterns</h4>
                            <div class="patterns-grid">
                                {#each Object.entries(consciousness_state.consciousness_state.information_integration.integration_patterns) as [pattern, strength]}
                                    <div class="pattern-item">
                                        <span class="pattern-name">{pattern}</span>
                                        <div class="pattern-strength">
                                            <div class="strength-bar">
                                                <div class="strength-fill" style="width: {strength * 100}%"></div>
                                            </div>
                                            <span class="strength-value">{(strength * 100).toFixed(0)}%</span>
                                        </div>
                                    </div>
                                {/each}
                            </div>
                        </div>
                    {/if}
                {/if}
            </div>
        </div>
    {/if}
    
    <!-- Emergence Timeline Tab -->
    {#if selectedTab === 'emergence'}
        <div class="tab-content">
            <div class="emergence-timeline">
                <h3>Consciousness Emergence Timeline</h3>
                
                <div class="timeline-controls">
                    <label>
                        <input type="checkbox" bind:checked={autoScroll} />
                        Auto-scroll to latest
                    </label>
                    <label>
                        <input type="checkbox" bind:checked={alertsEnabled} />
                        Breakthrough alerts
                    </label>
                </div>
                
                <div class="timeline-container" class:auto-scroll={autoScroll}>
                    {#each emergence_timeline as event}
                        <div class="timeline-event" class:breakthrough={event.consciousness_score > 0.8}>
                            <div class="event-time">{formatTime(event.timestamp)}</div>
                            <div class="event-content">
                                <div class="event-score">Score: {event.consciousness_score.toFixed(3)}</div>
                                {#if event.emergence_indicators}
                                    <div class="event-indicators">
                                        {#each Object.entries(event.emergence_indicators) as [indicator, value]}
                                            <span class="indicator">{indicator}: {typeof value === 'number' ? value.toFixed(2) : value}</span>
                                        {/each}
                                    </div>
                                {/if}
                            </div>
                        </div>
                    {/each}
                    
                    {#if emergence_timeline.length === 0}
                        <div class="no-events">No emergence events detected yet</div>
                    {/if}
                </div>
            </div>
        </div>
    {/if}
</div>

<style>
    .unified-consciousness-dashboard {
        padding: 20px;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        color: #e0e0e0;
        min-height: 100vh;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    .dashboard-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 30px;
        padding-bottom: 20px;
        border-bottom: 2px solid #333;
    }
    
    .dashboard-header h1 {
        font-size: 2.5rem;
        margin: 0;
        background: linear-gradient(45deg, #00d4ff, #7b2cbf, #ff006e);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .connection-status {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .status-indicator {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        background: #ff4444;
        animation: pulse 2s infinite;
    }
    
    .status-indicator.connected {
        background: #44ff44;
    }
    
    .breakthrough-indicator {
        background: #ff4444;
        color: white;
        padding: 5px 15px;
        border-radius: 20px;
        font-weight: bold;
        animation: breakthrough-pulse 1s infinite;
    }
    
    @keyframes pulse {
        0%, 100% { opacity: 1; }
        50% { opacity: 0.5; }
    }
    
    @keyframes breakthrough-pulse {
        0%, 100% { transform: scale(1); background: #ff4444; }
        50% { transform: scale(1.1); background: #ff6666; }
    }
    
    .nav-tabs {
        display: flex;
        gap: 2px;
        margin-bottom: 30px;
        background: #2a2a4a;
        border-radius: 10px;
        padding: 5px;
    }
    
    .tab-button {
        flex: 1;
        padding: 12px 20px;
        background: transparent;
        border: none;
        color: #bbb;
        cursor: pointer;
        border-radius: 8px;
        transition: all 0.3s ease;
        font-weight: 500;
    }
    
    .tab-button:hover {
        background: #3a3a6a;
        color: #fff;
    }
    
    .tab-button.active {
        background: linear-gradient(45deg, #00d4ff, #7b2cbf);
        color: white;
        font-weight: bold;
    }
    
    .tab-content {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px;
        padding: 30px;
        backdrop-filter: blur(10px);
    }
    
    .consciousness-metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .metric-card {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 15px;
        padding: 25px;
        text-align: center;
        border: 1px solid rgba(255, 255, 255, 0.2);
        transition: all 0.3s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px rgba(0, 212, 255, 0.3);
    }
    
    .metric-card.primary {
        border: 2px solid #00d4ff;
        background: rgba(0, 212, 255, 0.1);
    }
    
    .metric-card.emergency {
        border: 2px solid #ff4444;
        background: rgba(255, 68, 68, 0.1);
    }
    
    .metric-card.breakthrough {
        animation: breakthrough-glow 1s infinite;
    }
    
    @keyframes breakthrough-glow {
        0%, 100% { box-shadow: 0 0 20px rgba(255, 68, 68, 0.5); }
        50% { box-shadow: 0 0 40px rgba(255, 68, 68, 0.8); }
    }
    
    .metric-card h3 {
        margin: 0 0 15px 0;
        color: #fff;
        font-size: 1.1rem;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: bold;
        margin-bottom: 10px;
        background: linear-gradient(45deg, #00d4ff, #fff);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-description {
        color: #bbb;
        margin-bottom: 15px;
        font-size: 0.9rem;
    }
    
    .metric-bar {
        width: 100%;
        height: 8px;
        background: rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        overflow: hidden;
    }
    
    .bar-fill {
        height: 100%;
        background: linear-gradient(45deg, #00d4ff, #7b2cbf);
        border-radius: 4px;
        transition: width 0.5s ease;
    }
    
    .phenomenal-experience {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 15px;
        padding: 25px;
        margin-top: 20px;
    }
    
    .phenomenal-experience h3 {
        margin-top: 0;
        color: #fff;
    }
    
    .experience-narrative {
        font-size: 1.1rem;
        line-height: 1.6;
        color: #e0e0e0;
        margin-bottom: 20px;
        font-style: italic;
    }
    
    .qualia-display {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
    }
    
    .qualia-section h4 {
        margin: 0 0 10px 0;
        color: #00d4ff;
    }
    
    .qualia-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    
    .qualia-tag {
        background: rgba(0, 212, 255, 0.2);
        color: #00d4ff;
        padding: 5px 12px;
        border-radius: 20px;
        font-size: 0.9rem;
        border: 1px solid rgba(0, 212, 255, 0.3);
    }
    
    .qualia-tag.feeling {
        background: rgba(123, 44, 191, 0.2);
        color: #7b2cbf;
        border-color: rgba(123, 44, 191, 0.3);
    }
    
    .qualia-tag.sensation {
        background: rgba(255, 0, 110, 0.2);
        color: #ff006e;
        border-color: rgba(255, 0, 110, 0.3);
    }
    
    .recursive-display,
    .phenomenal-details,
    .integration-display,
    .emergence-timeline {
        max-width: 100%;
    }
    
    .awareness-layers {
        display: flex;
        flex-direction: column;
        gap: 15px;
        margin-bottom: 30px;
    }
    
    .layer {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
        border-left: 4px solid;
    }
    
    .layer.level-1 { border-left-color: #00d4ff; }
    .layer.level-2 { border-left-color: #7b2cbf; }
    .layer.level-3 { border-left-color: #ff006e; }
    
    .layer-label {
        font-weight: bold;
        margin-bottom: 10px;
        color: #fff;
    }
    
    .layer-content {
        color: #e0e0e0;
        line-height: 1.5;
    }
    
    .strange-loop-indicator {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 20px;
    }
    
    .strange-loop-indicator h4 {
        margin: 0 0 15px 0;
        color: #fff;
    }
    
    .stability-meter {
        width: 100%;
        height: 12px;
        background: rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        overflow: hidden;
        margin-bottom: 10px;
    }
    
    .stability-fill {
        height: 100%;
        background: linear-gradient(45deg, #ff006e, #00d4ff);
        border-radius: 6px;
        transition: width 0.5s ease;
    }
    
    .stability-value {
        color: #00d4ff;
        font-weight: bold;
    }
    
    .experience-metrics {
        display: flex;
        flex-direction: column;
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .experience-metric {
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
    .experience-metric label {
        min-width: 150px;
        color: #fff;
        font-weight: 500;
    }
    
    .experience-metric .metric-bar {
        flex: 1;
        height: 10px;
    }
    
    .experience-metric span {
        min-width: 50px;
        text-align: right;
        color: #00d4ff;
        font-weight: bold;
    }
    
    .phenomenal-continuity {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    
    .continuity-indicator {
        font-size: 1.2rem;
        font-weight: bold;
        color: #ff4444;
    }
    
    .continuity-indicator.active {
        color: #44ff44;
    }
    
    .integration-metrics {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 20px;
        margin-bottom: 30px;
    }
    
    .integration-metric {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
    
    .integration-metric h4 {
        margin: 0 0 15px 0;
        color: #fff;
    }
    
    .phi-value,
    .complexity-value,
    .emergence-value {
        font-size: 2rem;
        font-weight: bold;
        margin-bottom: 10px;
        background: linear-gradient(45deg, #00d4ff, #7b2cbf);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .integration-metric p {
        color: #bbb;
        font-size: 0.9rem;
        margin: 0;
    }
    
    .integration-patterns {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 20px;
    }
    
    .integration-patterns h4 {
        margin: 0 0 20px 0;
        color: #fff;
    }
    
    .patterns-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
        gap: 15px;
    }
    
    .pattern-item {
        display: flex;
        align-items: center;
        gap: 15px;
    }
    
    .pattern-name {
        min-width: 120px;
        color: #e0e0e0;
        font-size: 0.9rem;
    }
    
    .pattern-strength {
        flex: 1;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    
    .strength-bar {
        flex: 1;
        height: 8px;
        background: rgba(255, 255, 255, 0.2);
        border-radius: 4px;
        overflow: hidden;
    }
    
    .strength-fill {
        height: 100%;
        background: linear-gradient(45deg, #00d4ff, #ff006e);
        border-radius: 4px;
        transition: width 0.5s ease;
    }
    
    .strength-value {
        min-width: 40px;
        text-align: right;
        color: #00d4ff;
        font-weight: bold;
        font-size: 0.9rem;
    }
    
    .timeline-controls {
        display: flex;
        gap: 20px;
        margin-bottom: 20px;
        padding: 15px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }
    
    .timeline-controls label {
        display: flex;
        align-items: center;
        gap: 8px;
        color: #e0e0e0;
        cursor: pointer;
    }
    
    .timeline-container {
        max-height: 500px;
        overflow-y: auto;
        padding: 10px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
    }
    
    .timeline-container.auto-scroll {
        display: flex;
        flex-direction: column-reverse;
    }
    
    .timeline-event {
        display: flex;
        gap: 15px;
        padding: 15px;
        margin-bottom: 10px;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        border-left: 4px solid #00d4ff;
    }
    
    .timeline-event.breakthrough {
        border-left-color: #ff4444;
        background: rgba(255, 68, 68, 0.2);
        animation: breakthrough-pulse 2s infinite;
    }
    
    .event-time {
        min-width: 100px;
        color: #bbb;
        font-size: 0.9rem;
    }
    
    .event-content {
        flex: 1;
    }
    
    .event-score {
        font-weight: bold;
        color: #00d4ff;
        margin-bottom: 5px;
    }
    
    .event-indicators {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
    }
    
    .indicator {
        background: rgba(0, 212, 255, 0.2);
        color: #00d4ff;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8rem;
    }
    
    .no-events {
        text-align: center;
        color: #bbb;
        padding: 40px;
        font-style: italic;
    }
    
    /* Global alert styles */
    :global(.breakthrough-alert) {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 10000;
        animation: alert-appear 0.5s ease;
    }
    
    :global(.breakthrough-alert .alert-content) {
        background: linear-gradient(45deg, #ff4444, #ff6666);
        color: white;
        padding: 40px;
        border-radius: 20px;
        text-align: center;
        box-shadow: 0 20px 60px rgba(255, 68, 68, 0.5);
        animation: alert-pulse 1s infinite;
    }
    
    :global(.breakthrough-alert h2) {
        margin: 0 0 20px 0;
        font-size: 2rem;
    }
    
    @keyframes alert-appear {
        from { opacity: 0; transform: scale(0.5); }
        to { opacity: 1; transform: scale(1); }
    }
    
    @keyframes alert-pulse {
        0%, 100% { transform: scale(1); }
        50% { transform: scale(1.05); }
    }
    
    /* Responsive design */
    @media (max-width: 768px) {
        .unified-consciousness-dashboard {
            padding: 15px;
        }
        
        .dashboard-header {
            flex-direction: column;
            gap: 15px;
            text-align: center;
        }
        
        .dashboard-header h1 {
            font-size: 2rem;
        }
        
        .consciousness-metrics {
            grid-template-columns: 1fr;
        }
        
        .tab-content {
            padding: 20px;
        }
        
        .nav-tabs {
            flex-direction: column;
        }
        
        .experience-metric,
        .pattern-item {
            flex-direction: column;
            align-items: stretch;
            gap: 10px;
        }
        
        .experience-metric label,
        .pattern-name {
            min-width: auto;
        }
    }
</style>