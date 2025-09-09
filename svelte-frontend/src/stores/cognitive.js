// Reactive Cognitive State Management for GödelOS
import { writable, derived } from 'svelte/store';

// Enhanced API integration functions
export const apiHelpers = {
  // Sanitize health data to ensure all values are valid numbers between 0 and 1
  sanitizeHealthData: (healthData) => {
    if (!healthData || typeof healthData !== 'object') return {};
    
    const sanitized = {};
    for (const [key, value] of Object.entries(healthData)) {
      if (typeof value === 'number' && !isNaN(value) && value >= 0 && value <= 1) {
        sanitized[key] = value;
      } else if (typeof value === 'number' && !isNaN(value) && value > 1) {
        // If it's a percentage > 1, normalize it
        sanitized[key] = Math.min(value / 100, 1);
      }
    }
    return sanitized;
  },

  // Update cognitive state from backend
  updateCognitiveFromBackend: async () => {
    try {
      const backendData = await (await import('../utils/api.js')).GödelOSAPI.fetchCognitiveState();
      if (backendData) {
        const sanitizedHealth = apiHelpers.sanitizeHealthData(backendData.systemHealth);
        cognitiveState.update(state => ({
          ...state,
          ...backendData,
          lastUpdate: Date.now(),
          systemHealth: {
            ...state.systemHealth,
            ...sanitizedHealth,
            websocketConnection: 1.0
          }
        }));
      }
    } catch (error) {
      console.warn('Failed to update cognitive state from backend:', error);
    }
  },

  // Update knowledge state from backend
  updateKnowledgeFromBackend: async () => {
    try {
      const { GödelOSAPI } = await import('../utils/api.js');
      const [concepts, graphData, statistics] = await Promise.all([
        GödelOSAPI.fetchConcepts(),
        GödelOSAPI.fetchKnowledgeGraph(),
        GödelOSAPI.fetchKnowledgeStatistics()
      ]);

      knowledgeState.update(state => ({
        ...state,
        totalConcepts: graphData?.nodes?.length || concepts?.length || 0,
        totalConnections: graphData?.edges?.length || 0,
        totalDocuments: statistics?.total_items || 0,
        concepts: concepts || [],
        currentGraph: graphData || { nodes: [], edges: [] },
        recentImports: statistics?.recent_imports || state.recentImports || [],
        categories: Object.keys(statistics?.items_by_category || {}) || state.categories || []
      }));
      
      console.log(`📊 Knowledge state updated: ${statistics?.total_items || 0} documents, ${graphData?.nodes?.length || 0} concepts, ${graphData?.edges?.length || 0} connections`);
    } catch (error) {
      console.warn('Failed to update knowledge state from backend:', error);
    }
  },

  // Start real-time polling
  startRealTimeUpdates: (interval = 5000) => {
    const updateAll = async () => {
      await Promise.all([
        apiHelpers.updateCognitiveFromBackend(),
        apiHelpers.updateKnowledgeFromBackend()
      ]);
    };

    updateAll(); // Initial update
    return setInterval(updateAll, interval);
  }
};

// Core cognitive state - mirrors the actual GödelOS cognitive architecture
export const cognitiveState = writable({
  manifestConsciousness: {
    attention: null,
    workingMemory: [],
    processingLoad: 0,
    currentQuery: null,
    focusDepth: 'surface' // 'surface', 'deep', 'meta'
  },
  agenticProcesses: [],
  daemonThreads: [],
  systemHealth: {
    inferenceEngine: 0.87,
    knowledgeStore: 0.94,
    reflectionEngine: 0.71,
    learningModules: 0.85,
    websocketConnection: 0.0
  },
  alerts: [],
  capabilities: {
    reasoning: 0.0,
    knowledge: 0.0,
    creativity: 0.0,
    reflection: 0.0,
    learning: 0.0
  },
  lastUpdate: Date.now()
});

// Knowledge management state
export const knowledgeState = writable({
  totalConcepts: 0,
  totalDocuments: 0,
  totalConnections: 0,
  recentImports: [],
  searchResults: [],
  currentGraph: { nodes: [], edges: [] },
  importStatus: null,
  categories: [],
  totalRelationships: 0
});

// System evolution tracking
export const evolutionState = writable({
  currentVersion: 'v2.3.7',
  modifications: [],
  proposals: [],
  capabilities: [],
  timeline: [],
  metrics: {
    templatesLearned: 847,
    strategiesOptimized: 23,
    modificationsImplemented: 156,
    breakthroughs: 12
  }
});

// UI state and preferences
export const uiState = writable({
  expandedPanels: new Set(),
  theme: 'dark',
  cognitiveTransparency: 'contextual', // 'always', 'contextual', 'minimal'
  animationSpeed: 'normal',
  layout: 'unified'
});

// Derived stores for specific UI components
export const attentionFocus = derived(
  cognitiveState,
  $state => $state.attention_focus || $state.manifestConsciousness?.attention || null
);

export const processingLoad = derived(
  cognitiveState,
  $state => $state.processing_load ?? $state.manifestConsciousness?.processingLoad ?? 0
);

export const activeAgents = derived(
  cognitiveState,
  $state => {
    // Use direct active_agents count from backend if available
    if (typeof $state.active_agents === 'number' && !isNaN($state.active_agents)) {
      return $state.active_agents;
    }
    // Fallback to counting active agentic processes
    if (!Array.isArray($state.agenticProcesses)) return 0;
    return $state.agenticProcesses.filter(agent => agent && agent.status === 'active').length;
  }
);

export const systemHealthOverall = derived(
  cognitiveState,
  $state => {
    const health = $state.systemHealth;
    const values = Object.values(health).filter(val => typeof val === 'number' && !isNaN(val) && isFinite(val));
    return values.length > 0 ? values.reduce((sum, val) => sum + val, 0) / values.length : 0.0;
  }
);

export const systemHealthScore = derived(
  cognitiveState,
  $state => {
    const health = $state.systemHealth;
    const values = Object.values(health).filter(val => typeof val === 'number' && !isNaN(val) && isFinite(val));
    return values.length > 0 ? values.reduce((sum, val) => sum + val, 0) / values.length : 0.0;
  }
);

export const alerts = derived(
  cognitiveState,
  $state => $state.alerts
);

export const criticalAlerts = derived(
  cognitiveState,
  $state => $state.alerts.filter(alert => alert.severity === 'critical')
);

export const recentKnowledge = derived(
  knowledgeState,
  $state => $state.recentImports.slice(0, 5)
);

export const pendingProposals = derived(
  evolutionState,
  $state => $state.proposals.filter(p => p.status === 'pending')
);

// WebSocket integration for real-time cognitive updates
let cognitiveWebSocket = null;

export function initCognitiveStream() {
  if (cognitiveWebSocket?.readyState === WebSocket.OPEN) {
    return cognitiveWebSocket;
  }

  try {
    cognitiveWebSocket = new WebSocket('ws://localhost:8000/ws/cognitive-stream');
    
    cognitiveWebSocket.onopen = () => {
      console.log('🧠 Cognitive state stream connected');
      cognitiveState.update(state => ({
        ...state,
        systemHealth: {
          ...state.systemHealth,
          websocketConnection: 1.0
        }
      }));
    };
    
    cognitiveWebSocket.onmessage = (event) => {
      try {
        const update = JSON.parse(event.data);
        
        // Route different types of cognitive updates
        switch (update.type) {
          case 'cognitive_state':
            cognitiveState.update(state => ({
              ...state,
              ...update.data,
              lastUpdate: Date.now()
            }));
            break;
            
          case 'knowledge_update':
            knowledgeState.update(state => ({
              ...state,
              ...update.data
            }));
            break;
            
          case 'evolution_event':
            evolutionState.update(state => ({
              ...state,
              timeline: [update.data, ...state.timeline.slice(0, 49)]
            }));
            break;
            
          case 'attention_shift':
            cognitiveState.update(state => ({
              ...state,
              manifestConsciousness: {
                ...state.manifestConsciousness,
                attention: update.data.attention,
                focusDepth: update.data.depth || 'surface'
              }
            }));
            break;
        }
      } catch (error) {
        // Silently handle cognitive update processing errors
      }
    };
    
    cognitiveWebSocket.onclose = () => {
      console.log('🧠 Cognitive state stream disconnected');
      cognitiveState.update(state => ({
        ...state,
        systemHealth: {
          ...state.systemHealth,
          websocketConnection: 0.0
        }
      }));
      
      // Attempt reconnection after 5 seconds with exponential backoff
      let reconnectAttempt = 0;
      const maxReconnectAttempts = 3;
      
      const attemptReconnect = () => {
        if (reconnectAttempt < maxReconnectAttempts && cognitiveWebSocket?.readyState !== WebSocket.OPEN) {
          reconnectAttempt++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempt), 10000); // Max 10 seconds
          console.log(`Scheduling reconnection attempt ${reconnectAttempt} in ${delay}ms`);
          setTimeout(() => {
            if (cognitiveWebSocket?.readyState !== WebSocket.OPEN) {
              initCognitiveStream();
            }
          }, delay);
        }
      };
      
      attemptReconnect();
    };
    
    cognitiveWebSocket.onerror = (error) => {
      // Only log WebSocket errors that aren't connection refused to reduce noise
      // Silently handle WebSocket errors when backend is unavailable
    };
    
  } catch (error) {
    // Only log non-connection errors to reduce console noise
    if (!error.message?.includes('Connection refused') && !error.message?.includes('NetworkError')) {
      console.error('Failed to initialize cognitive stream:', error);
    }
  }
  
  return cognitiveWebSocket;
}

// Removed duplicate apiHelpers declaration - already defined above

// Utility functions for state updates
export function updateAttention(attention, depth = 'surface') {
  cognitiveState.update(state => ({
    ...state,
    manifestConsciousness: {
      ...state.manifestConsciousness,
      attention,
      focusDepth: depth
    }
  }));
}

export function addToWorkingMemory(item) {
  cognitiveState.update(state => ({
    ...state,
    manifestConsciousness: {
      ...state.manifestConsciousness,
      workingMemory: [item, ...state.manifestConsciousness.workingMemory.slice(0, 11)]
    }
  }));
}

export function updateProcessingLoad(load) {
  cognitiveState.update(state => ({
    ...state,
    manifestConsciousness: {
      ...state.manifestConsciousness,
      processingLoad: Math.max(0, Math.min(1, load))
    }
  }));
}

export function addAlert(alert) {
  cognitiveState.update(state => ({
    ...state,
    alerts: [
      {
        id: Date.now(),
        timestamp: new Date().toISOString(),
        ...alert
      },
      ...state.alerts.slice(0, 9)
    ]
  }));
}

export function removeAlert(alertId) {
  cognitiveState.update(state => ({
    ...state,
    alerts: state.alerts.filter(alert => alert.id !== alertId)
  }));
}

// Mock data initialization removed - using real backend data only
