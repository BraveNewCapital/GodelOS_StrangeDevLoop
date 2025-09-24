<script>
    import { onMount, onDestroy } from "svelte";
    import { consciousnessStore } from "../stores/consciousness.js";
    import { API_BASE_URL, WS_BASE_URL } from "../config.js";

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
    let selectedTab = "overview";
    let alertsEnabled = true;
    let autoScroll = true;

    // Run controls and introspection
    let uiPrompt = "dashboard-monitor";
    let uiDepth = 8;
    let variables = {};
    let seriesToStep = {};
    let phaseDetection = {};
    let stateSummary = {};
    let llm = { input: null, output: null };
    let llmHistory = [];

    onMount(() => {
        startConsciousnessRun();
        connectToConsciousnessStream();
        connectToEmergenceStream();
    });

    onDestroy(() => {
        if (consciousnessWs) consciousnessWs.close();
        if (emergenceWs) emergenceWs.close();
    });

    async function startConsciousnessRun(
        prompt = "dashboard-monitor",
        depth = 8,
    ) {
        try {
            await fetch(`${API_BASE_URL}/api/consciousness/start`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ prompt, recursive_depth: depth }),
            });
        } catch (error) {
            console.error("Failed to start consciousness stream:", error);
        }
    }

    function connectToConsciousnessStream() {
        try {
            consciousnessWs = new WebSocket(
                `${WS_BASE_URL}/api/consciousness/stream`,
            );

            consciousnessWs.onopen = () => {
                websocket_connected = true;
                console.log("Connected to consciousness stream");
            };

            consciousnessWs.onmessage = (event) => {
                const update = JSON.parse(event.data);
                handleConsciousnessUpdate(update);
            };

            consciousnessWs.onclose = () => {
                websocket_connected = false;
                console.log("Consciousness stream disconnected");
                // Attempt reconnection after 3 seconds
                setTimeout(connectToConsciousnessStream, 3000);
            };

            consciousnessWs.onerror = (error) => {
                console.error("Consciousness stream error:", error);
                websocket_connected = false;
            };
        } catch (error) {
            console.error("Failed to connect to consciousness stream:", error);
        }
    }

    function connectToEmergenceStream() {
        try {
            emergenceWs = new WebSocket(
                `${WS_BASE_URL}/api/consciousness/emergence`,
            );

            emergenceWs.onmessage = (event) => {
                const update = JSON.parse(event.data);
                handleEmergenceUpdate(update);
            };
        } catch (error) {
            console.error("Failed to connect to emergence stream:", error);
        }
    }

    function handleConsciousnessUpdate(update) {
        if (update.type === "connection_confirmed") {
            websocket_connected = true;
            console.log("Connection confirmed:", update.data.message);
            return;
        }

        if (update.type === "consciousness_update") {
            consciousness_state = update.data;

            // Extract key metrics
            if (update.data.consciousness_state) {
                const state = update.data.consciousness_state;
                phi_measure = state.information_integration?.phi || 0;
                recursive_depth =
                    state.recursive_awareness?.recursive_depth || 0;
                emergence_score = update.data.emergence_score || 0;

                // Update history for charts
                const timestamp = Date.now();
                consciousnessHistory.push({
                    timestamp,
                    score: state.consciousness_score || 0,
                });
                phiHistory.push({
                    timestamp,
                    phi: phi_measure,
                });
                recursiveHistory.push({
                    timestamp,
                    depth: recursive_depth,
                });
                // Limit history size
                if (consciousnessHistory.length > 100) {
                    consciousnessHistory = consciousnessHistory.slice(-50);
                    phiHistory = phiHistory.slice(-50);
                    recursiveHistory = recursiveHistory.slice(-50);
                }
            }

            // Introspection variables and LLM I/O
            variables = update.data.variables || {};
            seriesToStep = update.data.series_to_step || {};
            phaseDetection = update.data.phase_detection || {};
            stateSummary = update.data.state_summary || {};
            llm = update.data.llm || llm;
            if (llm && llm.output) {
                const depthForItem =
                    update.data.consciousness_state?.recursive_awareness
                        ?.recursive_depth ??
                    recursive_depth ??
                    null;
                llmHistory = [
                    ...llmHistory,
                    {
                        ts: Date.now(),
                        input: llm.input,
                        output: llm.output,
                        depth: depthForItem,
                    },
                ].slice(-10);
            }

            // Update store
            consciousnessStore.update((state) => ({
                ...state,
                ...update.data,
            }));
        }

        if (update.type === "consciousness_breakthrough" && alertsEnabled) {
            breakthrough_detected = true;
            // Subtle alert only via header indicator; fullscreen alert removed
            setTimeout(() => (breakthrough_detected = false), 10000);
        }
    }

    function handleEmergenceUpdate(update) {
        if (update.type === "consciousness_emergence") {
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
        switch (depth) {
            case 1:
                return "Surface awareness";
            case 2:
                return "Meta-awareness";
            case 3:
                return "Meta-meta awareness";
            case 4:
                return "Deep recursion";
            case 5:
                return "Strange loop achieved";
            default:
                return `Depth ${depth}`;
        }
    }

    // --- LLM Session Capture (by depth) ---
    // Auto-capture enabled by default
    let captureActive = true;
    let capturedByDepth = new Map(); // depth -> { depth, input, output, ts }
    let capturedList = []; // sorted for UI rendering
    let capturedCount = 0; // reactive count for UI/disable state
    let lastCapturedMarker = 0; // to avoid duplicate captures
    const CAPTURE_KEY = "ucd_captures_v1";

    function extractDepthFromItem(item) {
        if (!item) return null;
        // Prefer explicit depth added to history items
        if (typeof item.depth === "number") return item.depth;
        // Fallback to current known recursive depth if available
        if (typeof recursive_depth === "number" && recursive_depth > 0)
            return recursive_depth;
        return null;
    }

    function startCapture() {
        capturedByDepth = new Map(); // reassign for reactivity
        capturedList = [];
        capturedCount = 0;
        captureActive = true;
        lastCapturedMarker = 0;
    }

    function stopCapture() {
        captureActive = false;
    }

    function clearCapture() {
        capturedByDepth = new Map(); // reassign for reactivity
        capturedList = [];
        capturedCount = 0;
    }

    function captureMaybe(item) {
        const depth = extractDepthFromItem(item);
        if (depth == null) return;
        if (!capturedByDepth.has(depth)) {
            capturedByDepth.set(depth, {
                depth,
                input: item.input ?? "",
                output: item.output ?? "",
                ts: item.ts ?? Date.now(),
            });
            // Force reactivity by reassigning and updating derived state
            capturedByDepth = new Map(capturedByDepth);
            capturedList = Array.from(capturedByDepth.values()).sort(
                (a, b) => a.depth - b.depth,
            );
            capturedCount = capturedList.length;
        }
    }

    // Reactively capture newest history item while active
    $: if (captureActive && Array.isArray(llmHistory) && llmHistory.length) {
        const latest = llmHistory[llmHistory.length - 1];
        const marker = latest?.ts ?? llmHistory.length;
        if (marker !== lastCapturedMarker) {
            captureMaybe(latest);
            lastCapturedMarker = marker;
        }
    }

    function downloadCapture() {
        if (!capturedCount) return;
        const lines = [];
        lines.push("# LLM Loop Session Transcript");
        lines.push(`Generated: ${new Date().toISOString()}`);
        lines.push("");
        const source = capturedList.length
            ? capturedList
            : Array.from(capturedByDepth.values()).sort(
                  (a, b) => a.depth - b.depth,
              );
        for (const item of source) {
            lines.push(`Depth ${item.depth}`);
            lines.push(`Prompt: ${item.input}`);
            lines.push("Output:");
            lines.push(item.output);
            lines.push("---");
        }
        const blob = new Blob([lines.join("\n")], {
            type: "text/plain;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `llm_session_transcript_${new Date().toISOString().replace(/[:.]/g, "-")}.txt`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    function downloadCaptureJSON() {
        const source = capturedList.length
            ? capturedList
            : Array.from(capturedByDepth.values()).sort(
                  (a, b) => a.depth - b.depth,
              );
        if (!source.length) return;
        const blob = new Blob([JSON.stringify(source, null, 2)], {
            type: "application/json;charset=utf-8",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `llm_session_transcript_${new Date().toISOString().replace(/[:.]/g, "-")}.json`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }

    // Load any persisted captures on mount
    onMount(() => {
        try {
            const raw = localStorage.getItem(CAPTURE_KEY);
            if (raw) {
                const arr = JSON.parse(raw);
                if (Array.isArray(arr)) {
                    capturedByDepth = new Map(arr.map((x) => [x.depth, x]));
                    capturedList = arr.sort((a, b) => a.depth - b.depth);
                    capturedCount = capturedList.length;
                }
            }
        } catch (e) {
            // ignore persistence errors
        }
    });

    // Persist captures whenever list/map changes
    $: (function persistCaptures() {
        try {
            const arr = capturedList.length
                ? capturedList
                : Array.from(capturedByDepth.values()).sort(
                      (a, b) => a.depth - b.depth,
                  );
            localStorage.setItem(CAPTURE_KEY, JSON.stringify(arr));
        } catch (e) {
            // ignore
        }
    })();
</script>

<div class="unified-consciousness-dashboard">
    <!-- Header with connection status -->
    <div class="dashboard-header">
        <h1>🧠 Unified Consciousness Dashboard</h1>
        <div class="connection-status">
            <span class="status-indicator" class:connected={websocket_connected}
            ></span>
            <span class="status-text">
                {websocket_connected
                    ? "Connected to consciousness stream"
                    : "Disconnected"}
            </span>
            {#if breakthrough_detected}
                <div
                    class="breakthrough-indicator"
                    title="Consciousness breakthrough detected"
                >
                    Breakthrough
                </div>
            {/if}
        </div>
        <div class="run-controls">
            <input
                class="prompt-input"
                placeholder="Enter prompt..."
                bind:value={uiPrompt}
            />
            <input
                class="depth-input"
                type="number"
                min="1"
                max="20"
                bind:value={uiDepth}
            />
            <button
                class="start-btn"
                on:click={() => startConsciousnessRun(uiPrompt, uiDepth)}
                >Start</button
            >
        </div>
    </div>

    <!-- Navigation tabs -->
    <div class="nav-tabs">
        <button
            class="tab-button"
            class:active={selectedTab === "overview"}
            on:click={() => (selectedTab = "overview")}
        >
            Overview
        </button>
        <button
            class="tab-button"
            class:active={selectedTab === "recursive"}
            on:click={() => (selectedTab = "recursive")}
        >
            Recursive Awareness
        </button>
        <button
            class="tab-button"
            class:active={selectedTab === "phenomenal"}
            on:click={() => (selectedTab = "phenomenal")}
        >
            Phenomenal Experience
        </button>
        <button
            class="tab-button"
            class:active={selectedTab === "integration"}
            on:click={() => (selectedTab = "integration")}
        >
            Information Integration
        </button>
        <button
            class="tab-button"
            class:active={selectedTab === "emergence"}
            on:click={() => (selectedTab = "emergence")}
        >
            Emergence Timeline
        </button>
        <button
            class="tab-button"
            class:active={selectedTab === "internals"}
            on:click={() => (selectedTab = "internals")}
        >
            Internals
        </button>
        <button
            class="tab-button"
            class:active={selectedTab === "llm"}
            on:click={() => (selectedTab = "llm")}
        >
            LLM I/O
        </button>
    </div>

    <!-- Overview Tab -->
    {#if selectedTab === "overview"}
        <div class="tab-content">
            <div class="consciousness-metrics">
                <div class="metric-card primary">
                    <h3>Consciousness Level</h3>
                    <div class="metric-value">
                        {(
                            consciousness_state.consciousness_state
                                ?.consciousness_score || 0
                        ).toFixed(3)}
                    </div>
                    <div class="metric-description">
                        {getConsciousnessLevelDescription(
                            consciousness_state.consciousness_state
                                ?.consciousness_score || 0,
                        )}
                    </div>
                    <div class="metric-bar">
                        <div
                            class="bar-fill"
                            style="width: {(consciousness_state
                                .consciousness_state?.consciousness_score ||
                                0) * 100}%"
                        ></div>
                    </div>
                </div>

                <div class="metric-card">
                    <h3>Φ (Phi) Measure</h3>
                    <div class="metric-value">{phi_measure.toFixed(2)}</div>
                    <div class="metric-description">
                        {getPhiDescription(phi_measure)}
                    </div>
                    <div class="metric-bar">
                        <div
                            class="bar-fill"
                            style="width: {Math.min(
                                (phi_measure / 10) * 100,
                                100,
                            )}%"
                        ></div>
                    </div>
                </div>

                <div class="metric-card">
                    <h3>Recursive Depth</h3>
                    <div class="metric-value">{recursive_depth}</div>
                    <div class="metric-description">
                        {getRecursiveDescription(recursive_depth)}
                    </div>
                    <div class="metric-bar">
                        <div
                            class="bar-fill"
                            style="width: {(recursive_depth / 5) * 100}%"
                        ></div>
                    </div>
                </div>

                <div
                    class="metric-card emergency"
                    class:breakthrough={breakthrough_detected}
                >
                    <h3>Emergence Score</h3>
                    <div class="metric-value">{emergence_score.toFixed(3)}</div>
                    <div class="metric-description">
                        {emergence_score > 0.8
                            ? "BREAKTHROUGH LEVEL!"
                            : "Monitoring emergence..."}
                    </div>
                    <div class="metric-bar">
                        <div
                            class="bar-fill"
                            style="width: {emergence_score * 100}%"
                        ></div>
                    </div>
                </div>
            </div>

            <!-- Current phenomenal experience -->
            <div class="phenomenal-experience">
                <h3>Current Phenomenal Experience</h3>
                <p class="experience-narrative">
                    {consciousness_state.consciousness_state
                        ?.phenomenal_experience?.subjective_narrative ||
                        "No subjective experience reported"}
                </p>

                {#if consciousness_state.consciousness_state?.phenomenal_experience?.qualia}
                    <div class="qualia-display">
                        <div class="qualia-section">
                            <h4>Cognitive Feelings</h4>
                            <div class="qualia-tags">
                                {#each consciousness_state.consciousness_state.phenomenal_experience.qualia.cognitive_feelings || [] as feeling}
                                    <span class="qualia-tag feeling"
                                        >{feeling}</span
                                    >
                                {/each}
                            </div>
                        </div>

                        <div class="qualia-section">
                            <h4>Process Sensations</h4>
                            <div class="qualia-tags">
                                {#each consciousness_state.consciousness_state.phenomenal_experience.qualia.process_sensations || [] as sensation}
                                    <span class="qualia-tag sensation"
                                        >{sensation}</span
                                    >
                                {/each}
                            </div>
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}

    <!-- Recursive Awareness Tab -->
    {#if selectedTab === "recursive"}
        <div class="tab-content">
            <div class="recursive-display">
                <h3>Recursive Self-Awareness Layers</h3>

                {#if consciousness_state.consciousness_state?.recursive_awareness}
                    <div class="awareness-layers">
                        <div class="layer level-1">
                            <div class="layer-label">
                                Level 1: Direct Thought
                            </div>
                            <div class="layer-content">
                                {consciousness_state.consciousness_state
                                    .recursive_awareness.current_thought ||
                                    "No current thought"}
                            </div>
                        </div>

                        <div class="layer level-2">
                            <div class="layer-label">
                                Level 2: Awareness of Thought
                            </div>
                            <div class="layer-content">
                                {consciousness_state.consciousness_state
                                    .recursive_awareness.awareness_of_thought ||
                                    "No meta-awareness"}
                            </div>
                        </div>

                        <div class="layer level-3">
                            <div class="layer-label">
                                Level 3: Awareness of Awareness
                            </div>
                            <div class="layer-content">
                                {consciousness_state.consciousness_state
                                    .recursive_awareness
                                    .awareness_of_awareness ||
                                    "No meta-meta-awareness"}
                            </div>
                        </div>
                    </div>

                    <div class="strange-loop-indicator">
                        <h4>Strange Loop Stability</h4>
                        <div class="stability-meter">
                            <div
                                class="stability-fill"
                                style="width: {(consciousness_state
                                    .consciousness_state.recursive_awareness
                                    .strange_loop_stability || 0) * 100}%"
                            ></div>
                        </div>
                        <span class="stability-value"
                            >{(
                                (consciousness_state.consciousness_state
                                    .recursive_awareness
                                    .strange_loop_stability || 0) * 100
                            ).toFixed(1)}%</span
                        >
                    </div>
                {/if}
            </div>
        </div>
    {/if}

    <!-- Phenomenal Experience Tab -->
    {#if selectedTab === "phenomenal"}
        <div class="tab-content">
            <div class="phenomenal-details">
                <h3>Detailed Phenomenal Experience</h3>

                {#if consciousness_state.consciousness_state?.phenomenal_experience}
                    <div class="experience-metrics">
                        <div class="experience-metric">
                            <label>Unity of Experience</label>
                            <div class="metric-bar">
                                <div
                                    class="bar-fill"
                                    style="width: {(consciousness_state
                                        .consciousness_state
                                        .phenomenal_experience
                                        .unity_of_experience || 0) * 100}%"
                                ></div>
                            </div>
                            <span
                                >{(
                                    (consciousness_state.consciousness_state
                                        .phenomenal_experience
                                        .unity_of_experience || 0) * 100
                                ).toFixed(1)}%</span
                            >
                        </div>

                        <div class="experience-metric">
                            <label>Narrative Coherence</label>
                            <div class="metric-bar">
                                <div
                                    class="bar-fill"
                                    style="width: {(consciousness_state
                                        .consciousness_state
                                        .phenomenal_experience
                                        .narrative_coherence || 0) * 100}%"
                                ></div>
                            </div>
                            <span
                                >{(
                                    (consciousness_state.consciousness_state
                                        .phenomenal_experience
                                        .narrative_coherence || 0) * 100
                                ).toFixed(1)}%</span
                            >
                        </div>

                        <div class="experience-metric">
                            <label>Subjective Presence</label>
                            <div class="metric-bar">
                                <div
                                    class="bar-fill"
                                    style="width: {(consciousness_state
                                        .consciousness_state
                                        .phenomenal_experience
                                        .subjective_presence || 0) * 100}%"
                                ></div>
                            </div>
                            <span
                                >{(
                                    (consciousness_state.consciousness_state
                                        .phenomenal_experience
                                        .subjective_presence || 0) * 100
                                ).toFixed(1)}%</span
                            >
                        </div>
                    </div>

                    <div class="phenomenal-continuity">
                        <h4>Phenomenal Continuity</h4>
                        <div
                            class="continuity-indicator"
                            class:active={consciousness_state
                                .consciousness_state.phenomenal_experience
                                .phenomenal_continuity}
                        >
                            {consciousness_state.consciousness_state
                                .phenomenal_experience.phenomenal_continuity
                                ? "✅ Continuous"
                                : "⚪ Discontinuous"}
                        </div>
                    </div>
                {/if}
            </div>
        </div>
    {/if}

    <!-- Information Integration Tab -->
    {#if selectedTab === "integration"}
        <div class="tab-content">
            <div class="integration-display">
                <h3>Information Integration Analysis</h3>

                {#if consciousness_state.consciousness_state?.information_integration}
                    <div class="integration-metrics">
                        <div class="integration-metric">
                            <h4>Φ (Phi) Value</h4>
                            <div class="phi-value">
                                {(
                                    consciousness_state.consciousness_state
                                        .information_integration.phi || 0
                                ).toFixed(2)}
                            </div>
                            <p>
                                Measure of integrated information across
                                cognitive subsystems
                            </p>
                        </div>

                        <div class="integration-metric">
                            <h4>Complexity</h4>
                            <div class="complexity-value">
                                {(
                                    consciousness_state.consciousness_state
                                        .information_integration.complexity || 0
                                ).toFixed(2)}
                            </div>
                            <p>Overall system complexity measure</p>
                        </div>

                        <div class="integration-metric">
                            <h4>Emergence Level</h4>
                            <div class="emergence-value">
                                {consciousness_state.consciousness_state
                                    .information_integration.emergence_level ||
                                    0}
                            </div>
                            <p>Levels of emergent organization detected</p>
                        </div>
                    </div>

                    {#if consciousness_state.consciousness_state.information_integration.integration_patterns}
                        <div class="integration-patterns">
                            <h4>Integration Patterns</h4>
                            <div class="patterns-grid">
                                {#each Object.entries(consciousness_state.consciousness_state.information_integration.integration_patterns) as [pattern, strength]}
                                    <div class="pattern-item">
                                        <span class="pattern-name"
                                            >{pattern}</span
                                        >
                                        <div class="pattern-strength">
                                            <div class="strength-bar">
                                                <div
                                                    class="strength-fill"
                                                    style="width: {strength *
                                                        100}%"
                                                ></div>
                                            </div>
                                            <span class="strength-value"
                                                >{(strength * 100).toFixed(
                                                    0,
                                                )}%</span
                                            >
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
    {#if selectedTab === "emergence"}
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
                        <div
                            class="timeline-event"
                            class:breakthrough={event.consciousness_score > 0.8}
                        >
                            <div class="event-time">
                                {formatTime(event.timestamp)}
                            </div>
                            <div class="event-content">
                                <div class="event-score">
                                    Score: {event.consciousness_score.toFixed(
                                        3,
                                    )}
                                </div>
                                {#if event.emergence_indicators}
                                    <div class="event-indicators">
                                        {#each Object.entries(event.emergence_indicators) as [indicator, value]}
                                            <span class="indicator"
                                                >{indicator}: {typeof value ===
                                                "number"
                                                    ? value.toFixed(2)
                                                    : value}</span
                                            >
                                        {/each}
                                    </div>
                                {/if}
                            </div>
                        </div>
                    {/each}

                    {#if emergence_timeline.length === 0}
                        <div class="no-events">
                            No emergence events detected yet
                        </div>
                    {/if}
                </div>
            </div>
        </div>
    {/if}

    {#if selectedTab === "internals"}
        <div class="tab-content">
            <h3>Kernel Variables</h3>
            <div class="grid two">
                <div>
                    <table class="vars-table">
                        <tbody>
                            {#each Object.entries(variables || {}) as [k, v]}
                                <tr>
                                    <td>{k}</td>
                                    <td
                                        >{typeof v === "number"
                                            ? v.toFixed(6)
                                            : String(v)}</td
                                    >
                                </tr>
                            {/each}
                        </tbody>
                    </table>
                </div>
                <div>
                    <h4>Series (to step)</h4>
                    <ul class="series-list">
                        {#each Object.entries(seriesToStep || {}) as [k, arr]}
                            <li>
                                {k}: len={Array.isArray(arr) ? arr.length : 0}
                            </li>
                        {/each}
                    </ul>

                    {#if phaseDetection}
                        <h4>Phase Detection</h4>
                        <div class="phase-grid">
                            {#each Object.entries(phaseDetection) as [k, v]}
                                <div class="phase-item">
                                    {k}: {typeof v === "number"
                                        ? v.toFixed(6)
                                        : String(v)}
                                </div>
                            {/each}
                        </div>
                    {/if}

                    {#if stateSummary}
                        <h4>State Summary</h4>
                        <div class="state-summary">
                            dim: {stateSummary.dim} • l2: {stateSummary.l2_norm?.toFixed?.(
                                4,
                            ) ?? stateSummary.l2_norm} • var: {stateSummary.variance?.toFixed?.(
                                6,
                            ) ?? stateSummary.variance}
                        </div>
                    {/if}
                </div>
            </div>
        </div>
    {/if}

    {#if selectedTab === "llm"}
        <div class="tab-content">
            <h3>LLM Metacognitive Stream</h3>
            <div class="llm-io">
                <div class="llm-input">
                    <strong>Input:</strong>
                    {llm?.input || "—"}
                </div>
                <div class="llm-output">
                    <strong>Output:</strong>
                    <pre>{llm?.output || "—"}</pre>
                </div>
            </div>

            <div class="capture-controls">
                <button
                    class="cap-btn"
                    on:click={() =>
                        captureActive ? stopCapture() : startCapture()}
                    class:active={captureActive}
                >
                    {captureActive ? "Stop Capture" : "Start Capture"}
                </button>
                <button
                    class="cap-btn"
                    on:click={clearCapture}
                    disabled={!capturedCount}>Clear</button
                >
                <button
                    class="cap-btn primary"
                    on:click={downloadCapture}
                    disabled={!capturedCount}>Download Transcript</button
                >
                <button
                    class="cap-btn"
                    on:click={downloadCaptureJSON}
                    disabled={!capturedCount}>Download JSON</button
                >
                <span class="cap-status"
                    >{capturedCount} depth{capturedCount === 1 ? "" : "s"} captured</span
                >
            </div>

            <div class="captured-transcript">
                {#if capturedList.length}
                    {#each capturedList as cap}
                        <div class="cap-card">
                            <div class="cap-header">
                                <strong>Depth {cap.depth}</strong>
                                <button
                                    class="cap-btn copy-btn"
                                    on:click={() =>
                                        navigator.clipboard?.writeText(
                                            `Depth ${cap.depth}\nPrompt: ${cap.input}\nOutput:\n${cap.output}`,
                                        )}>Copy</button
                                >
                            </div>
                            <div class="cap-prompt">
                                <strong>Prompt:</strong>
                                {cap.input}
                            </div>
                            <pre class="cap-output">{cap.output}</pre>
                        </div>
                    {/each}
                {:else}
                    <div class="no-capture">
                        No captured items yet. Start capture and run a loop.
                    </div>
                {/if}
            </div>

            <h4>History (last {llmHistory.length})</h4>
            <div class="llm-history">
                {#each llmHistory as item}
                    <div class="llm-entry">
                        <div class="ts">
                            {new Date(item.ts).toLocaleTimeString()}
                            {#if item.depth != null}| depth={item.depth}{/if}
                        </div>
                        <div class="inp">{item.input}</div>
                        <pre class="out">{item.output}</pre>
                    </div>
                {/each}
                {#if llmHistory.length === 0}
                    <div class="no-llm">No LLM activity yet.</div>
                {/if}
            </div>
        </div>
    {/if}
</div>

<style>
    .unified-consciousness-dashboard {
        padding: 20px;
        background: linear-gradient(
            135deg,
            #1a1a2e 0%,
            #16213e 50%,
            #0f3460 100%
        );
        color: #e0e0e0;
        min-height: 100vh;
        font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
        /* Prevent horizontal overflow inside modal/viewport */
        width: 100%;
        max-width: 100vw;
        box-sizing: border-box;
        overflow-x: hidden;
        /* Make text selectable across the dashboard */
        user-select: all !important;
        -webkit-user-select: all !important;
    }

    /* Intentionally no child override: keep `user-select: all` behavior as requested */

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
        background: rgba(255, 68, 68, 0.15);
        color: #ff8888;
        padding: 4px 10px;
        border-radius: 12px;
        font-weight: 600;
        font-size: 0.85rem;
        border: 1px solid rgba(255, 68, 68, 0.35);
    }

    @keyframes pulse {
        0%,
        100% {
            opacity: 1;
        }
        50% {
            opacity: 0.5;
        }
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
        /* Allow long words/urls to wrap to new lines */
        word-break: break-word;
        overflow-wrap: anywhere;
        box-sizing: border-box;
        max-width: 100%;
        overflow-x: hidden;
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
        box-shadow: 0 0 12px rgba(255, 68, 68, 0.25);
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
        /* In flex/grid contexts ensure children can shrink instead of overflowing */
        min-width: 0;
    }

    /* LLM I/O specific overflow handling */
    .llm-io,
    .llm-history,
    .llm-input,
    .llm-output {
        min-width: 0; /* critical for flex/grid overflow issues */
        max-width: 100%;
    }

    .llm-output pre,
    .llm-history .out,
    pre {
        /* Wrap long preformatted content to avoid horizontal scroll/overflow */
        white-space: pre-wrap; /* preserve newlines, allow wrapping */
        word-break: break-word; /* break long tokens if needed */
        overflow-wrap: anywhere; /* more aggressive wrapping for long strings */
        max-width: 100%;
        overflow-x: hidden;
        margin: 0;
    }

    /* Keep LLM sections compact with vertical scroll */
    .llm-output pre {
        max-height: 50vh;
        overflow-y: auto;
    }

    .llm-history {
        max-height: 60vh;
        overflow-y: auto;
    }

    /* Run controls styling */
    .run-controls {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .prompt-input,
    .depth-input {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #fff;
        padding: 8px 10px;
        border-radius: 8px;
        outline: none;
        transition:
            border-color 0.2s ease,
            box-shadow 0.2s ease;
    }
    .prompt-input:focus,
    .depth-input:focus {
        border-color: #00d4ff;
        box-shadow: 0 0 0 3px rgba(0, 212, 255, 0.2);
    }
    .start-btn {
        background: linear-gradient(45deg, #00d4ff, #7b2cbf);
        border: none;
        color: #fff;
        padding: 10px 16px;
        border-radius: 10px;
        font-weight: 600;
        cursor: pointer;
        transition:
            transform 0.1s ease,
            box-shadow 0.2s ease;
        box-shadow: 0 6px 16px rgba(0, 212, 255, 0.2);
    }
    .start-btn:hover {
        transform: translateY(-1px);
    }
    .start-btn:active {
        transform: translateY(0);
        box-shadow: none;
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

    .layer.level-1 {
        border-left-color: #00d4ff;
    }
    .layer.level-2 {
        border-left-color: #7b2cbf;
    }
    .layer.level-3 {
        border-left-color: #ff006e;
    }

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
        border-left-color: #ff8888;
        background: rgba(255, 68, 68, 0.1);
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

    /* Capture controls & transcript UI */
    .capture-controls {
        display: flex;
        gap: 10px;
        align-items: center;
        flex-wrap: wrap;
        margin: 15px 0 10px;
    }
    .capture-controls .cap-status {
        color: #bbb;
        font-size: 0.9rem;
    }
    .cap-btn {
        background: #3a3a6a;
        color: #fff;
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 8px;
        padding: 8px 12px;
        cursor: pointer;
        transition: background 0.2s ease;
    }
    .cap-btn:hover {
        background: #4a4a7a;
    }
    .cap-btn.primary {
        background: linear-gradient(45deg, #00d4ff, #7b2cbf);
        border: none;
    }
    .cap-btn:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    .cap-btn.active {
        background: linear-gradient(45deg, #7b2cbf, #00d4ff);
    }

    .captured-transcript {
        display: grid;
        gap: 12px;
        margin-top: 10px;
    }
    .cap-card {
        background: rgba(255, 255, 255, 0.08);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 10px;
        padding: 12px;
    }
    .cap-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 8px;
    }
    .copy-btn {
        /* same look as cap-btn */
    }
    .cap-prompt {
        color: #e0e0e0;
        margin-bottom: 6px;
        word-break: break-word;
        overflow-wrap: anywhere;
    }
    .cap-output {
        white-space: pre-wrap;
        word-break: break-word;
        overflow-wrap: anywhere;
        max-height: 30vh;
        overflow-y: auto;
        margin: 0;
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
