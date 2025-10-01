// Reactive Cognitive State Management for GödelOS
import { writable, derived } from 'svelte/store';

// Health normalization (single source of truth)
export const healthHelpers = {
  /**
   * Convert numeric health score (0.0-1.0) to categorical label
   * @param {number|null|undefined} score - Health score
   * @returns {'healthy'|'degraded'|'down'|'unknown'} Health label
   */
  scoreToLabel: (score) => {
    if (score == null) return 'unknown';
    if (score >= 0.8) return 'healthy';
    if (score >= 0.4) return 'degraded';
    return 'down';
  },

  /**
   * Get system health score (mean of numeric fields)
   * @param {object} systemHealth - System health object
   * @returns {number} Mean health score
   */
  getSystemHealthScore: (systemHealth) => {
    if (!systemHealth || typeof systemHealth !== 'object') return 0;
    
    const numericFields = ['websocketConnection', 'pipeline', 'knowledgeStore', 'vectorIndex'];
    const validScores = numericFields
      .map(field => systemHealth[field])
      .filter(score => typeof score === 'number' && !isNaN(score));
    
    return validScores.length > 0 
      ? validScores.reduce((sum, score) => sum + score, 0) / validScores.length 
      : 0;
  },

  /**
   * Normalize cognitive state data from backend to canonical format
   * @param {object} backendData - Raw data from API
   * @returns {object} Normalized cognitive state
   */
  normalizeCognitiveData: (backendData) => {
    if (!backendData || typeof backendData !== 'object') {
      return {
        manifestConsciousness: healthHelpers.getDefaultManifestConsciousness(),
        systemHealth: healthHelpers.getDefaultSystemHealth(),
        knowledgeStats: { totalConcepts: 0, totalConnections: 0, totalDocuments: 0 }
      };
    }

    // Handle both canonical (camelCase) and legacy (snake_case) formats
    const manifestConsciousness = backendData.manifestConsciousness || 
                                  backendData.manifest_consciousness || 
                                  healthHelpers.getDefaultManifestConsciousness();

    const systemHealth = backendData.systemHealth || healthHelpers.getDefaultSystemHealth();
    const knowledgeStats = backendData.knowledgeStats || { totalConcepts: 0, totalConnections: 0, totalDocuments: 0 };

    return {
      manifestConsciousness,
      systemHealth,
      knowledgeStats,
      version: backendData.version || 'v1',
      lastUpdate: Date.now()
    };
  },

  /**
   * Get default manifest consciousness structure
   */
  getDefaultManifestConsciousness: () => ({
    attention: { intensity: 0, focus: [], coverage: 0 },
    awareness: { level: 0, breadth: 0 },
    metaReflection: { depth: 0, coherence: 0 },
    processMonitoring: { latency: 0, throughput: 0 }
  }),

  /**
   * Get default system health structure
   */
  getDefaultSystemHealth: () => ({
    websocketConnection: 0.0,
    pipeline: 0.0,
    knowledgeStore: 0.0,
    vectorIndex: 0.0,
    _labels: {
      websocketConnection: 'unknown',
      pipeline: 'unknown',
      knowledgeStore: 'unknown',
      vectorIndex: 'unknown'
    }
  })
};

const createDefaultCapabilitySummary = () => ({
  total: 0,
  operational: 0,
  developing: 0,
  averagePerformance: 0
});

const createDefaultLiveState = () => ({
  timestamp: null,
  currentQuery: null,
  manifestConsciousness: {
    focus: [],
    reflectionDepth: 0,
    selfAwareness: 0
  },
  agenticProcesses: [],
  daemonThreads: [],
  resourceUtilization: [],
  alerts: [],
  cognitiveState: {}
});

const normalizeCapability = (capability) => {
  if (!capability) {
    return {
      id: 'unknown',
      label: 'Unknown Capability',
      currentLevel: 0,
      baselineLevel: 0,
      improvementRate: 0,
      confidence: 0,
      status: 'unknown',
      trend: 'stable',
      lastUpdated: null,
      enabled: false
    };
  }

  return {
    id: capability.id,
    label: capability.label,
    currentLevel: capability.current_level ?? capability.currentLevel ?? 0,
    baselineLevel: capability.baseline_level ?? capability.baselineLevel ?? 0,
    improvementRate: capability.improvement_rate ?? capability.improvementRate ?? 0,
    confidence: capability.confidence ?? 0,
    status: capability.status ?? 'unknown',
    trend: capability.trend ?? 'stable',
    lastUpdated: capability.last_updated ?? capability.lastUpdated ?? null,
    enabled: capability.enabled ?? true
  };
};

const normalizeCapabilityCollection = (payload = {}) => {
  const capabilities = Array.isArray(payload.capabilities)
    ? payload.capabilities.map(normalizeCapability)
    : [];

  const learningFocus = Array.isArray(payload.learning_focus || payload.learningFocus)
    ? (payload.learning_focus || payload.learningFocus).map(normalizeCapability)
    : [];

  const recentImprovements = Array.isArray(payload.recent_improvements || payload.recentImprovements)
    ? (payload.recent_improvements || payload.recentImprovements).map((item) => ({
        id: item.id,
        delta: item.delta
      }))
    : [];

  const summaryRaw = payload.summary || {};
  const summary = {
    total: summaryRaw.total ?? 0,
    operational: summaryRaw.operational ?? 0,
    developing: summaryRaw.developing ?? 0,
    averagePerformance: summaryRaw.average_performance ?? summaryRaw.averagePerformance ?? 0
  };

  const resourceAllocation = Array.isArray(payload.resource_allocation || payload.resourceAllocation)
    ? (payload.resource_allocation || payload.resourceAllocation).map((item) => ({
        category: item.category,
        allocation: item.allocation
      }))
    : [];

  return {
    timestamp: payload.timestamp ?? null,
    capabilities,
    summary,
    learningFocus,
    recentImprovements,
    resourceAllocation,
    metacognitiveState: payload.metacognitive_state || payload.metacognitiveState || {}
  };
};

const normalizeProposal = (proposal) => {
  if (!proposal) {
    return null;
  }

  return {
    id: proposal.id,
    title: proposal.title,
    priority: proposal.priority,
    priorityRank: proposal.priority_rank ?? proposal.priorityRank ?? Number.MAX_SAFE_INTEGER,
    status: proposal.status,
    riskLevel: proposal.risk_level ?? proposal.riskLevel ?? 'unknown',
    confidence: proposal.confidence ?? 0,
    expectedBenefits: proposal.expected_benefits || proposal.expectedBenefits || {},
    potentialRisks: proposal.potential_risks || proposal.potentialRisks || {},
    monitoringRequirements: proposal.monitoring_requirements || proposal.monitoringRequirements || [],
    focusAreas: proposal.focus_areas || proposal.focusAreas || [],
    targetQuarter: proposal.target_quarter || proposal.targetQuarter || null,
    estimatedDurationDays: proposal.estimated_duration_days || proposal.estimatedDurationDays || null,
    decisionLog: proposal.decision_log || proposal.decisionLog || [],
    createdAt: proposal.created_at || proposal.createdAt || null,
    approvedAt: proposal.approved_at || proposal.approvedAt || null,
    rejectedAt: proposal.rejected_at || proposal.rejectedAt || null
  };
};

const normalizeProposalCollection = (payload = {}) => {
  const proposals = Array.isArray(payload.proposals)
    ? payload.proposals.map(normalizeProposal).filter(Boolean)
    : [];

  const countsRaw = payload.counts || {};
  let counts = Object.keys(countsRaw).reduce((acc, key) => {
    acc[key] = countsRaw[key];
    return acc;
  }, {});

  if (!Object.keys(counts).length && proposals.length) {
    counts = proposals.reduce((acc, proposal) => {
      const status = (proposal.status || 'unknown').toLowerCase();
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, {});
  }

  return {
    timestamp: payload.timestamp ?? null,
    proposals,
    counts
  };
};

const countProposalsByStatus = (proposals = []) => {
  return proposals.reduce((acc, proposal) => {
    const status = (proposal.status || 'unknown').toLowerCase();
    acc[status] = (acc[status] || 0) + 1;
    return acc;
  }, {});
};

const normalizeEvolutionOverview = (payload = {}) => ({
  timestamp: payload.timestamp ?? null,
  timeline: Array.isArray(payload.timeline) ? payload.timeline.map((event) => ({
    id: event.id,
    label: event.label,
    category: event.category,
    impact: event.impact || {},
    timestamp: event.timestamp
  })) : [],
  metrics: payload.metrics || {},
  upcoming: Array.isArray(payload.upcoming) ? payload.upcoming : []
});

const normalizeLiveState = (payload = {}) => {
  const manifest = payload.manifest_consciousness || payload.manifestConsciousness || {};

  return {
    timestamp: payload.timestamp ?? null,
    currentQuery: payload.current_query || payload.currentQuery || null,
    manifestConsciousness: {
      focus: manifest.focus || [],
      reflectionDepth: manifest.reflection_depth ?? manifest.reflectionDepth ?? 0,
      selfAwareness: manifest.self_awareness ?? manifest.selfAwareness ?? 0
    },
    agenticProcesses: Array.isArray(payload.agentic_processes || payload.agenticProcesses)
      ? (payload.agentic_processes || payload.agenticProcesses).map((process) => ({
          id: process.id,
          label: process.label,
          status: process.status
        }))
      : [],
    daemonThreads: Array.isArray(payload.daemon_threads || payload.daemonThreads)
      ? (payload.daemon_threads || payload.daemonThreads).map((thread) => ({
          id: thread.id,
          label: thread.label,
          status: thread.status
        }))
      : [],
    resourceUtilization: Array.isArray(payload.resource_utilization || payload.resourceUtilization)
      ? (payload.resource_utilization || payload.resourceUtilization).map((item) => ({
          category: item.category,
          allocation: item.allocation
        }))
      : [],
    alerts: Array.isArray(payload.alerts) ? payload.alerts : [],
    cognitiveState: payload.cognitive_state || payload.cognitiveState || {}
  };
};

const normalizeSimulationResult = (payload = {}) => ({
  proposal: normalizeProposal(payload.proposal),
  confidence: payload.confidence ?? 0,
  riskLevel: payload.risk_level ?? payload.riskLevel ?? 'unknown',
  estimatedCompletionDays: payload.estimated_completion_days ?? payload.estimatedCompletionDays ?? null,
  monitoringRequirements: payload.monitoring_requirements || payload.monitoringRequirements || [],
  projectedCapabilities: Array.isArray(payload.projected_capabilities || payload.projectedCapabilities)
    ? (payload.projected_capabilities || payload.projectedCapabilities).map((item) => ({
        id: item.id,
        label: item.label,
        currentLevel: item.current_level ?? item.currentLevel ?? 0,
        projectedLevel: item.projected_level ?? item.projectedLevel ?? 0,
        delta: item.delta ?? 0
      }))
    : []
});

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
        const normalizedData = healthHelpers.normalizeCognitiveData(backendData);
        
        cognitiveState.update(state => ({
          ...state,
          manifestConsciousness: normalizedData.manifestConsciousness,
          systemHealth: {
            ...normalizedData.systemHealth,
            websocketConnection: 1.0 // Mark as connected since we got data
          },
          knowledgeStats: normalizedData.knowledgeStats,
          lastUpdate: Date.now()
        }));
      }
    } catch (error) {
      console.warn('Failed to update cognitive state from backend:', error);
    }
  },

  // Update knowledge state from backend with enhanced vector DB integration
  updateKnowledgeFromBackend: async () => {
    try {
      const { GödelOSAPI } = await import('../utils/api.js');
      const [concepts, graphData, statistics] = await Promise.all([
        GödelOSAPI.fetchConcepts(),
        GödelOSAPI.fetchKnowledgeGraph(),
        GödelOSAPI.fetchKnowledgeStatisticsEnhanced() // Use enhanced stats
      ]);

      knowledgeState.update(state => ({
        ...state,
        totalConcepts: graphData?.nodes?.length || concepts?.length || 0,
        totalConnections: graphData?.edges?.length || 0,
        totalDocuments: statistics?.total_documents || statistics?.total_items || 0,
        totalVectors: statistics?.total_vectors || 0, // Add vector count
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
  },

  // --- Self-modification helpers ---
  loadSelfModificationCapabilities: async () => {
    selfModificationState.update(state => ({
      ...state,
      loading: { ...state.loading, capabilities: true },
      errors: { ...state.errors, capabilities: null }
    }));

    try {
      const { GödelOSAPI } = await import('../utils/api.js');
      const raw = await GödelOSAPI.fetchMetacognitionCapabilities();
      const normalized = normalizeCapabilityCollection(raw);

      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, capabilities: false },
        capabilities: normalized.capabilities,
        summary: normalized.summary,
        learningFocus: normalized.learningFocus,
        recentImprovements: normalized.recentImprovements,
        resourceAllocation: normalized.resourceAllocation,
        metacognitiveState: normalized.metacognitiveState,
        lastUpdated: { ...state.lastUpdated, capabilities: Date.now() }
      }));

      evolutionState.update(state => ({
        ...state,
        capabilities: normalized.capabilities
      }));

      return normalized;
    } catch (error) {
      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, capabilities: false },
        errors: { ...state.errors, capabilities: error?.message || 'Failed to load capability data' }
      }));
      throw error;
    }
  },

  loadSelfModificationProposals: async (status = null) => {
    selfModificationState.update(state => ({
      ...state,
      loading: { ...state.loading, proposals: true },
      errors: { ...state.errors, proposals: null }
    }));

    try {
      const { GödelOSAPI } = await import('../utils/api.js');
      const raw = await GödelOSAPI.fetchMetacognitionProposals(status);
      const normalized = normalizeProposalCollection(raw);

      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, proposals: false },
        proposals: normalized.proposals,
        proposalCounts: normalized.counts,
        lastUpdated: { ...state.lastUpdated, proposals: Date.now() }
      }));

      evolutionState.update(state => ({
        ...state,
        proposals: normalized.proposals
      }));

      return normalized;
    } catch (error) {
      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, proposals: false },
        errors: { ...state.errors, proposals: error?.message || 'Failed to load proposals' }
      }));
      throw error;
    }
  },

  loadSelfModificationEvolution: async () => {
    selfModificationState.update(state => ({
      ...state,
      loading: { ...state.loading, evolution: true },
      errors: { ...state.errors, evolution: null }
    }));

    try {
      const { GödelOSAPI } = await import('../utils/api.js');
      const raw = await GödelOSAPI.fetchMetacognitionEvolution();
      const normalized = normalizeEvolutionOverview(raw);

      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, evolution: false },
        timeline: normalized.timeline,
        metrics: normalized.metrics,
        upcoming: normalized.upcoming,
        lastUpdated: { ...state.lastUpdated, evolution: Date.now() }
      }));

      evolutionState.update(state => ({
        ...state,
        timeline: normalized.timeline,
        metrics: {
          ...state.metrics,
          ...normalized.metrics
        },
        modifications: normalized.upcoming || state.modifications
      }));

      return normalized;
    } catch (error) {
      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, evolution: false },
        errors: { ...state.errors, evolution: error?.message || 'Failed to load evolution overview' }
      }));
      throw error;
    }
  },

  loadSelfModificationLiveState: async () => {
    selfModificationState.update(state => ({
      ...state,
      loading: { ...state.loading, liveState: true },
      errors: { ...state.errors, liveState: null }
    }));

    try {
      const { GödelOSAPI } = await import('../utils/api.js');
      const raw = await GödelOSAPI.fetchMetacognitionLiveState();
      const normalized = normalizeLiveState(raw);

      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, liveState: false },
        liveState: normalized,
        lastUpdated: { ...state.lastUpdated, liveState: Date.now() }
      }));

      return normalized;
    } catch (error) {
      selfModificationState.update(state => ({
        ...state,
        loading: { ...state.loading, liveState: false },
        errors: { ...state.errors, liveState: error?.message || 'Failed to load live state' }
      }));
      throw error;
    }
  },

  initializeSelfModification: async () => {
    await Promise.allSettled([
      apiHelpers.loadSelfModificationCapabilities(),
      apiHelpers.loadSelfModificationProposals(),
      apiHelpers.loadSelfModificationEvolution(),
      apiHelpers.loadSelfModificationLiveState()
    ]);
  },

  refreshSelfModification: async () => {
    await Promise.allSettled([
      apiHelpers.loadSelfModificationCapabilities(),
      apiHelpers.loadSelfModificationProposals(),
      apiHelpers.loadSelfModificationEvolution()
    ]);
  },

  approveSelfModificationProposal: async (proposalId, actor = 'self_modification_ui') => {
    const { GödelOSAPI } = await import('../utils/api.js');
    const updated = await GödelOSAPI.approveMetacognitionProposal(proposalId, actor);
    const normalized = normalizeProposal(updated);

    let updatedProposals;
    selfModificationState.update(state => {
      updatedProposals = state.proposals.some(proposal => proposal.id === normalized.id)
        ? state.proposals.map(proposal => proposal.id === normalized.id ? normalized : proposal)
        : [normalized, ...state.proposals];

      return {
        ...state,
        proposals: updatedProposals,
        proposalCounts: countProposalsByStatus(updatedProposals),
        lastUpdated: { ...state.lastUpdated, proposals: Date.now() }
      };
    });

    evolutionState.update(state => ({
      ...state,
      proposals: updatedProposals || state.proposals
    }));

    return normalized;
  },

  rejectSelfModificationProposal: async (proposalId, reason = null, actor = 'self_modification_ui') => {
    const { GödelOSAPI } = await import('../utils/api.js');
    const updated = await GödelOSAPI.rejectMetacognitionProposal(proposalId, reason, actor);
    const normalized = normalizeProposal(updated);

    let updatedProposals;
    selfModificationState.update(state => {
      updatedProposals = state.proposals.some(proposal => proposal.id === normalized.id)
        ? state.proposals.map(proposal => proposal.id === normalized.id ? normalized : proposal)
        : [normalized, ...state.proposals];

      return {
        ...state,
        proposals: updatedProposals,
        proposalCounts: countProposalsByStatus(updatedProposals),
        lastUpdated: { ...state.lastUpdated, proposals: Date.now() }
      };
    });

    evolutionState.update(state => ({
      ...state,
      proposals: updatedProposals || state.proposals
    }));

    return normalized;
  },

  simulateSelfModificationProposal: async (proposalId) => {
    const { GödelOSAPI } = await import('../utils/api.js');
    const raw = await GödelOSAPI.simulateMetacognitionProposal(proposalId);
    const normalized = normalizeSimulationResult(raw);

    selfModificationState.update(state => ({
      ...state,
      activeSimulation: normalized,
      lastUpdated: { ...state.lastUpdated, proposals: Date.now() }
    }));

    return normalized;
  }
};

export const selfModificationEventHandlers = {
  handleCapabilityUpdate: (payload) => {
    const normalized = normalizeCapabilityCollection(payload || {});

    selfModificationState.update(state => ({
      ...state,
      capabilities: normalized.capabilities,
      summary: normalized.summary,
      learningFocus: normalized.learningFocus,
      recentImprovements: normalized.recentImprovements,
      resourceAllocation: normalized.resourceAllocation,
      metacognitiveState: normalized.metacognitiveState,
      lastUpdated: { ...state.lastUpdated, capabilities: Date.now() }
    }));

    evolutionState.update(state => ({
      ...state,
      capabilities: normalized.capabilities
    }));
  },

  handleProposalUpdate: (payload) => {
    if (!payload) return;
    const proposal = normalizeProposal(payload.proposal || payload);
    if (!proposal) return;

    selfModificationState.update(state => {
      const proposals = state.proposals.some(item => item.id === proposal.id)
        ? state.proposals.map(item => (item.id === proposal.id ? proposal : item))
        : [proposal, ...state.proposals];

      return {
        ...state,
        proposals,
        proposalCounts: countProposalsByStatus(proposals),
        lastUpdated: { ...state.lastUpdated, proposals: Date.now() }
      };
    });

    evolutionState.update(state => ({
      ...state,
      proposals: state.proposals.some(item => item.id === proposal.id)
        ? state.proposals.map(item => (item.id === proposal.id ? proposal : item))
        : [proposal, ...state.proposals]
    }));
  },

  handleProposalSimulation: (payload) => {
    const normalized = normalizeSimulationResult(payload || {});
    selfModificationState.update(state => ({
      ...state,
      activeSimulation: normalized,
      lastUpdated: { ...state.lastUpdated, proposals: Date.now() }
    }));
  },

  handleLiveStateUpdate: (payload) => {
    const normalized = normalizeLiveState(payload || {});
    selfModificationState.update(state => ({
      ...state,
      liveState: normalized,
      lastUpdated: { ...state.lastUpdated, liveState: Date.now() }
    }));
  },

  handleEvolutionCheckpoint: (payload) => {
    if (!payload) return;
    const event = {
      id: payload.id || `evt_${Date.now()}`,
      label: payload.label || payload.title || 'Evolution Update',
      category: payload.category || 'update',
      impact: payload.impact || {},
      timestamp: payload.timestamp || new Date().toISOString() + 'Z'
    };

    selfModificationState.update(state => {
      const timeline = [event, ...state.timeline].slice(0, 75);
      return {
        ...state,
        timeline,
        lastUpdated: { ...state.lastUpdated, evolution: Date.now() }
      };
    });

    evolutionState.update(state => ({
      ...state,
      timeline: [event, ...state.timeline].slice(0, 75)
    }));
  }
};

// Core cognitive state - mirrors the canonical GödelOS cognitive architecture
export const cognitiveState = writable({
  // Canonical camelCase format
  manifestConsciousness: healthHelpers.getDefaultManifestConsciousness(),
  systemHealth: healthHelpers.getDefaultSystemHealth(),
  knowledgeStats: {
    totalConcepts: 0,
    totalConnections: 0,
    totalDocuments: 0,
    totalVectors: 0
  },
  
  // Legacy fields for backward compatibility
  agenticProcesses: [],
  daemonThreads: [],
  cognitiveEvents: [], // Stream of consciousness events from transparency engine
  alerts: [],
  capabilities: {
    reasoning: 0.0,
    knowledge: 0.0,
    creativity: 0.0,
    reflection: 0.0,
    learning: 0.0
  },
  version: 'v1',
  lastUpdate: Date.now()
});

// Knowledge management state
export const knowledgeState = writable({
  totalConcepts: 0,
  totalDocuments: 0,
  totalConnections: 0,
  totalVectors: 0,
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

export const selfModificationState = writable({
  loading: {
    capabilities: false,
    proposals: false,
    evolution: false,
    liveState: false
  },
  errors: {
    capabilities: null,
    proposals: null,
    evolution: null,
    liveState: null
  },
  capabilities: [],
  summary: createDefaultCapabilitySummary(),
  learningFocus: [],
  recentImprovements: [],
  resourceAllocation: [],
  metacognitiveState: {},
  proposals: [],
  proposalCounts: {},
  activeSimulation: null,
  timeline: [],
  metrics: {},
  upcoming: [],
  liveState: createDefaultLiveState(),
  lastUpdated: {
    capabilities: null,
    proposals: null,
    evolution: null,
    liveState: null
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
  $state => $state.manifestConsciousness?.attention || null
);

export const processingLoad = derived(
  cognitiveState,
  $state => $state.manifestConsciousness?.processMonitoring?.throughput ?? 0
);

// System health score (mean of numeric health values)
export const systemHealthScore = derived(
  cognitiveState,
  $state => healthHelpers.getSystemHealthScore($state.systemHealth)
);

// Active agents count (for compatibility)
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

export const highRiskProposals = derived(
  selfModificationState,
  $state => $state.proposals.filter(p => (p.riskLevel || '').toLowerCase() === 'high')
);

export const pendingSelfModificationProposals = derived(
  selfModificationState,
  $state => $state.proposals.filter(p => ['pending', 'under_review'].includes((p.status || '').toLowerCase()))
);

export const selfModificationAlerts = derived(
  selfModificationState,
  $state => ({
    highRisk: $state.proposals.filter(p => (p.riskLevel || '').toLowerCase() === 'high').length,
    pendingApprovals: $state.proposals.filter(p => (p.status || '').toLowerCase() === 'pending').length,
    totalCapabilities: $state.summary.total || 0
  })
);

// WebSocket integration for real-time cognitive updates
let cognitiveWebSocket = null;
import { WS_BASE_URL } from '../config.js';
import { handleProgressUpdate } from './importProgress.js';

export function initCognitiveStream() {
  if (cognitiveWebSocket?.readyState === WebSocket.OPEN) {
    return cognitiveWebSocket;
  }

  try {
    // Use unified streaming endpoint for better performance and unified event management
    cognitiveWebSocket = new WebSocket(`${WS_BASE_URL}/ws/unified-cognitive-stream`);
    
    cognitiveWebSocket.onopen = () => {
      console.log('🧠 Unified cognitive stream connected');
      
      // Subscribe to relevant event types for the cognitive frontend
      const subscription = {
        type: "subscribe",
        event_types: [
          "cognitive_state",
          "cognitive_stream", 
          "consciousness_update",
          "system_status",
          "transparency",
          "cognitive_transparency",
          "capability_update",
          "proposal_update",
          "proposal_simulation",
          "metacognition_live_state",
          "evolution_checkpoint"
        ]
      };
      
      cognitiveWebSocket.send(JSON.stringify(subscription));
      console.log('📡 Subscribed to cognitive events:', subscription.event_types);
      
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
        const message = JSON.parse(event.data);
        
        // Handle unified streaming event format
        // Unified events have: { id, type, timestamp, data, source, priority }
        // Legacy events may still come as: { type, data, ... }
        
        let eventType, eventData;
        
        if (message.type && message.data && message.id) {
          // New unified event format
          eventType = message.type;
          eventData = message.data;
          console.log(`📡 Received unified event: ${eventType}`, message);
        } else {
          // Legacy event format for backward compatibility
          eventType = message.type;
          eventData = message.data || message;
          console.log(`📡 Received legacy event: ${eventType}`, message);
        }
        
        // Route different types of cognitive updates
        switch (eventType) {
          case 'cognitive_state':
          case 'cognitive_state_update':
            // Handle both unified and legacy cognitive state updates
            const cognitiveData = eventData.data || eventData;
            cognitiveState.update(state => ({
              ...state,
              ...cognitiveData,
              lastUpdate: Date.now()
            }));
            break;
            
          case 'cognitive_stream':
          case 'cognitive_processing_complete':
            // Handle cognitive processing events
            cognitiveState.update(state => ({
              ...state,
              processingStatus: eventData,
              lastUpdate: Date.now()
            }));
            break;
            
          case 'consciousness_update':
            // Handle consciousness assessment updates
            cognitiveState.update(state => ({
              ...state,
              manifestConsciousness: {
                ...state.manifestConsciousness,
                ...eventData,
                lastAssessment: Date.now()
              }
            }));
            break;
            
          case 'knowledge_update':
            knowledgeState.update(state => ({
              ...state,
              ...eventData
            }));
            break;

          case 'capability_update':
            selfModificationEventHandlers.handleCapabilityUpdate(eventData);
            break;

          case 'proposal_update':
            selfModificationEventHandlers.handleProposalUpdate(eventData);
            break;

          case 'proposal_simulation':
            selfModificationEventHandlers.handleProposalSimulation(eventData);
            break;

          case 'metacognition_live_state':
            selfModificationEventHandlers.handleLiveStateUpdate(eventData);
            break;

          case 'evolution_checkpoint':
            selfModificationEventHandlers.handleEvolutionCheckpoint(eventData);
            break;
            
          case 'evolution_event':
            evolutionState.update(state => ({
              ...state,
              timeline: [eventData, ...state.timeline.slice(0, 49)]
            }));
            break;
            
          case 'attention_shift':
            cognitiveState.update(state => ({
              ...state,
              manifestConsciousness: {
                ...state.manifestConsciousness,
                attention: eventData.attention,
                focusDepth: eventData.depth || 'surface'
              }
            }));
            break;
            
          case 'transparency':
          case 'cognitive_transparency':
            // Handle transparency events from unified streaming
            if (eventData.transparency_event) {
              // Process nested transparency event
              console.log('🔍 Transparency update:', eventData.transparency_event);
            }
            break;

          case 'cognitive_event':
            // Handle cognitive events from transparency engine
            console.log('🧠 Cognitive event received:', eventData);
            if (eventData.data && eventData.data.event_type) {
              const event = eventData.data;
              // Add to cognitive event stream for Stream of Consciousness Monitor
              cognitiveState.update(state => ({
                ...state,
                cognitiveEvents: [
                  ...(state.cognitiveEvents || []).slice(-99), // Keep last 100 events
                  {
                    id: Date.now(),
                    type: event.event_type,
                    content: event.details?.content || 'Cognitive activity',
                    timestamp: event.timestamp,
                    component: event.component,
                    priority: event.priority || 5,
                    metadata: event.details?.metadata || {}
                  }
                ],
                lastUpdate: Date.now()
              }));
            }
            break;
            
          case 'system_status':
            // Handle system status updates
            cognitiveState.update(state => ({
              ...state,
              systemHealth: {
                ...state.systemHealth,
                ...eventData
              }
            }));
            break;
            
          // Handle legacy knowledge processing progress updates (maintain compatibility)
          case 'knowledge_processing_started':
          case 'knowledge_processing_progress':
          case 'knowledge_processing_completed':
          case 'knowledge_processing_failed':
            handleProgressUpdate(message); // Pass full message for legacy compatibility
            break;
            
          // Handle unified streaming specific events
          case 'subscription_confirmed':
            console.log('✅ Event subscription confirmed:', eventData);
            break;
            
          case 'connection_status':
            console.log('📊 Connection status:', eventData);
            break;
            
          default:
            console.log(`📡 Unhandled event type: ${eventType}`, eventData);
        }
      } catch (error) {
        console.error('❌ Error processing cognitive update:', error);
      }
    };
    
    cognitiveWebSocket.onclose = () => {
      console.log('🧠 Unified cognitive stream disconnected');
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
          console.log(`🔄 Scheduling unified stream reconnection attempt ${reconnectAttempt} in ${delay}ms`);
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
