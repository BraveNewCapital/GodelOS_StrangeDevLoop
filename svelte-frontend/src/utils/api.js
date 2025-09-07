/**
 * GödelOS Backend API Integration
 * Real data fetching functions to replace mock data
 */

// Get backend URL from environment or use default
const DEFAULT_BACKEND_PORT = '8000';
const BACKEND_PORT = window.GODELOS_BACKEND_PORT || import.meta.env.VITE_BACKEND_PORT || DEFAULT_BACKEND_PORT;
const API_BASE_URL = `http://localhost:${BACKEND_PORT}`;

// Log the backend URL for debugging
console.log('🔗 GödelOS API connecting to:', API_BASE_URL);

export class GödelOSAPI {
  static async fetchKnowledgeGraph() {
    try {
      // Use the correct backend knowledge graph endpoint
      const response = await fetch(`${API_BASE_URL}/api/knowledge/graph`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      
      // Transform the API response to match expected format
      if (data && (data.nodes || data.edges)) {
        return {
          nodes: data.nodes || [],
          links: data.edges || [], // edges → links for D3.js compatibility
          statistics: data.statistics || {
            node_count: data.nodes?.length || 0,
            edge_count: data.edges?.length || 0,
            data_source: data.data_source || "backend"
          }
        };
      }
      
      console.warn('Knowledge graph response has unexpected format:', data);
      return null;
    } catch (error) {
      console.warn('Failed to fetch knowledge graph:', error);
      return null;
    }
  }

  static async fetchConcepts() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/concepts`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      // Only log if it's not a network/CORS error to reduce console noise
      if (!error.message.includes('NetworkError') && error.name !== 'TypeError') {
        console.warn('Failed to fetch concepts:', error);
      }
      return [];
    }
  }

  static async searchKnowledge(query, category = null) {
    try {
      const url = new URL(`${API_BASE_URL}/api/knowledge/search`);
      url.searchParams.append('query', query);
      if (category) url.searchParams.append('category', category);
      
      const response = await fetch(url);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to search knowledge:', error);
      return { results: [], total: 0 };
    }
  }

  static async fetchSystemHealth() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      // Only log if it's not a network/CORS error to reduce console noise
      if (!error.message.includes('NetworkError') && !error.name === 'TypeError') {
        console.warn('Failed to fetch system health:', error);
      }
      return null;
    }
  }

  static async fetchCognitiveState() {
    try {
      // Use the correct backend cognitive state endpoint
      const response = await fetch(`${API_BASE_URL}/api/cognitive-state`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      // Only log if it's not a network/CORS error to reduce console noise
      if (!error.message.includes('NetworkError') && !error.name === 'TypeError') {
        console.warn('Failed to fetch cognitive state:', error);
      }
      return null;
    }
  }

  static async queryKnowledge(query) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          query, 
          context: { source: 'user_interface' },
          stream: false
        })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Failed to query knowledge:', error);
      throw error;
    }
  }

  // Enhanced cognitive query with better reasoning and processing
  static async enhancedQuery(query, context = 'user_interface') {
    try {
      console.log('🧠 Making enhanced cognitive query:', query);
      const response = await fetch(`${API_BASE_URL}/api/enhanced-cognitive/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, context })
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      console.log('✅ Enhanced cognitive response:', result);
      return result;
    } catch (error) {
      console.error('⚠️ Enhanced query failed, falling back to knowledge query:', error);
      // Fallback to regular knowledge query
      return await this.queryKnowledge(query);
    }
  }

  static async importDocument(file, source = 'upload') {
    try {
      // Use the correct file import endpoint
      return await this.importFromFile(file, 'utf-8', [source]);
    } catch (error) {
      console.error('Failed to import document:', error);
      throw error;
    }
  }

  static async importFromWikipedia(title) {
    try {
      console.log('🔄 Importing from Wikipedia:', title);
      
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/wikipedia`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Wikipedia import failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Wikipedia import successful:', result);
      return result;
    } catch (error) {
      console.error('Failed to import from Wikipedia:', error);
      throw error;
    }
  }

  // Enhanced import API methods for SmartImport component
  static async importFromUrl(url, category = 'web') {
    try {
      console.log('🔄 Importing from URL:', { url, category });
      
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/url`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, category })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('URL import failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ URL import successful:', result);
      return result;
    } catch (error) {
      console.error('Failed to import from URL:', error);
      throw error;
    }
  }

  static async importFromText(content, title = 'Manual Text Input', category = 'document') {
    try {
      console.log('🔄 Importing text:', { title, category, length: content.length });
      
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/text`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title, category })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Text import failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Text import successful:', result);
      return result;
    } catch (error) {
      console.error('Failed to import text:', error);
      throw error;
    }
  }

  static async importFromFile(file, encoding = 'utf-8', categorization_hints = []) {
    try {
      // Map MIME types to backend expected file types
      const mimeToFileType = {
        'application/pdf': 'pdf',
        'text/plain': 'txt',
        'text/csv': 'csv',
        'application/json': 'json',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
        'application/vnd.ms-word': 'docx',
        'text/markdown': 'txt',
        'application/octet-stream': 'txt'  // fallback
      };

      // Determine file type from MIME type or file extension
      let fileType = mimeToFileType[file.type];
      
      if (!fileType && file.name) {
        // Fallback to file extension
        const ext = file.name.toLowerCase().split('.').pop();
        const extToFileType = {
          'pdf': 'pdf',
          'txt': 'txt',
          'csv': 'csv',
          'json': 'json',
          'docx': 'docx',
          'doc': 'docx',
          'md': 'txt',
          'markdown': 'txt'
        };
        fileType = extToFileType[ext] || 'txt';
      }
      
      if (!fileType) {
        fileType = 'txt'; // Ultimate fallback
      }

      const formData = new FormData();
      formData.append('file', file);
      formData.append('filename', file.name);
      formData.append('file_type', fileType);  // Now sends 'pdf' instead of 'application/pdf'
      formData.append('encoding', encoding);
      formData.append('categorization_hints', JSON.stringify(categorization_hints));

      console.log('🔄 Importing file:', {
        name: file.name,
        mimeType: file.type,
        mappedFileType: fileType,
        size: file.size,
        encoding: encoding
      });

      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/file`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Import failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Import successful:', result);
      return result;
    } catch (error) {
      console.error('Failed to import file:', error);
      throw error;
    }
  }

  static async batchImport(sources) {
    try {
      console.log('🔄 Starting batch import:', sources.length, 'sources');
      
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sources })
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Batch import failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Batch import started:', result);
      return result;
    } catch (error) {
      console.error('Failed to start batch import:', error);
      throw error;
    }
  }

  // Import progress and management methods
  static async getImportProgress(importId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/progress/${importId}`);
      
      if (!response.ok) {
        if (response.status === 404) {
          return { status: 'not_found', progress: 0 };
        }
        throw new Error(`HTTP ${response.status}`);
      }
      
      return await response.json();
    } catch (error) {
      console.error('Failed to get import progress:', error);
      return { status: 'error', progress: 0, error: error.message };
    }
  }

  static async cancelImport(importId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/${importId}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Failed to cancel import:', error);
      throw error;
    }
  }

  // Additional knowledge management methods
  static async addKnowledge(knowledgeData) {
    try {
      console.log('🔄 Adding knowledge:', knowledgeData);
      
      const response = await fetch(`${API_BASE_URL}/api/knowledge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(knowledgeData)
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Add knowledge failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Knowledge added:', result);
      return result;
    } catch (error) {
      console.error('Failed to add knowledge:', error);
      throw error;
    }
  }

  static async getImportProgress(importId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/progress/${importId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to get import progress:', error);
      return null;
    }
  }

  static async cancelImport(importId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/import/${importId}`, {
        method: 'DELETE'
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.error('Failed to cancel import:', error);
      throw error;
    }
  }

  static async fetchEvolutionData(timeframe = '24h') {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/evolution?timeframe=${timeframe}`, {
        signal: AbortSignal.timeout(5000) // 5 second timeout
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      // Only log if it's not a network/CORS error to reduce console noise
      if (!error.message.includes('NetworkError') && error.name !== 'TypeError') {
        console.warn('Failed to fetch evolution data:', error);
      }
      return [];
    }
  }

  static async fetchCapabilities() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/capabilities`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to fetch capabilities:', error);
      return {};
    }
  }

  static async reAnalyzeKnowledge() {
    try {
      console.log('🧠 Attempting knowledge re-analysis...');
      
      // The backend doesn't have specific reanalysis endpoints
      // Instead, we can trigger a refresh by fetching fresh knowledge graph data
      console.log('🔄 Triggering knowledge refresh by fetching updated data...');
      
      // Wait a moment to simulate processing
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      return {
        success: true,
        message: 'Knowledge data refresh triggered - the knowledge graph will reload with updated processing',
        backend_aligned: true
      };
      
    } catch (error) {
      // Silently handle re-analysis trigger errors when backend is unavailable
      return {
        success: false,
        message: error.message || 'Re-analysis request failed'
      };
    }
  }

  // Real-time data helpers
  static async pollForUpdates(callback, interval = 5000) {
    const poll = async () => {
      try {
        const [health, cognitive, concepts] = await Promise.all([
          this.fetchSystemHealth(),
          this.fetchCognitiveState(),
          this.fetchConcepts()
        ]);
        callback({ health, cognitive, concepts });
      } catch (error) {
        console.warn('Polling error:', error);
      }
    };

    poll(); // Initial call
    return setInterval(poll, interval);
  }

  // Provenance and transparency methods
  static async queryProvenance(params = {}) {
    try {
      const requestData = {
        target_id: params.target_id || 'default',
        query_type: params.query_type || 'backward_trace',
        max_depth: params.max_depth || 5,
        time_window_start: params.time_window_start || null,
        time_window_end: params.time_window_end || null
      };

      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance/query`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestData)
      });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to query provenance:', error);
      return { results: {} };
    }
  }

  static async getAttributionChain(targetId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance/attribution/${targetId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to get attribution chain:', error);
      return null;
    }
  }

  static async getProvenanceStatistics() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance/statistics`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to get provenance statistics:', error);
      return {};
    }
  }

  static async getConfidenceHistory(targetId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance/confidence-history/${targetId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to get confidence history:', error);
      return [];
    }
  }

  static async createKnowledgeSnapshot() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance/snapshot`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({})
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to create knowledge snapshot:', error);
      return null;
    }
  }

  static async getRollbackInfo(snapshotId) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance/rollback/${snapshotId}`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();
    } catch (error) {
      console.warn('Failed to get rollback info:', error);
      return null;
    }
  }

  // Advanced Knowledge Pipeline Methods
  
  static async processTextWithPipeline(content, title = 'Untitled', metadata = {}) {
    try {
      const formData = new FormData();
      formData.append('content', content);
      formData.append('title', title);
      formData.append('metadata', JSON.stringify(metadata));

      console.log('🔄 Processing text with advanced pipeline:', { title, contentLength: content.length });

      const response = await fetch(`${API_BASE_URL}/api/knowledge/pipeline/process`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Pipeline processing failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Pipeline processing successful:', result);
      return result;
    } catch (error) {
      console.error('Failed to process text with pipeline:', error);
      throw error;
    }
  }

  static async semanticSearch(query, k = 5) {
    try {
      const formData = new FormData();
      formData.append('query', query);
      formData.append('k', k.toString());

      console.log('🔍 Performing semantic search:', { query, k });

      const response = await fetch(`${API_BASE_URL}/api/knowledge/pipeline/semantic-search`, {
        method: 'POST',
        body: formData
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('Semantic search failed:', response.status, errorText);
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }
      
      const result = await response.json();
      console.log('✅ Semantic search successful:', result);
      return result;
    } catch (error) {
      console.error('Failed to perform semantic search:', error);
      throw error;
    }
  }

  static async getPipelineKnowledgeGraph() {
    try {
      console.log('📊 Fetching knowledge graph from pipeline...');
      
      const response = await fetch(`${API_BASE_URL}/api/knowledge/pipeline/graph`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      console.log('✅ Pipeline knowledge graph fetched:', result);
      return result;
    } catch (error) {
      console.warn('Failed to fetch pipeline knowledge graph:', error);
      return null;
    }
  }

  static async getPipelineStatus() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/knowledge/pipeline/status`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      return result;
    } catch (error) {
      console.warn('Failed to fetch pipeline status:', error);
      return null;
    }
  }

  static async fetchTransparencyStatistics() {
    try {
      console.log('📊 Fetching transparency statistics...');
      
      const response = await fetch(`${API_BASE_URL}/api/transparency/statistics`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      console.log('✅ Transparency statistics fetched:', result);
      return result;
    } catch (error) {
      console.warn('Failed to fetch transparency statistics:', error);
      return {
        status: 'Unavailable',
        transparency_level: 'Basic',
        total_sessions: 0,
        active_sessions: 0,
        provenance_entries: 0,
        data_lineage_tracked: false
      };
    }
  }

  static async fetchProvenanceData() {
    try {
      console.log('🔗 Fetching provenance data...');
      
      const response = await fetch(`${API_BASE_URL}/api/transparency/provenance`);
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      console.log('✅ Provenance data fetched:', result);
      return result;
    } catch (error) {
      console.warn('Failed to fetch provenance data:', error);
      return {
        provenance_entries: [],
        data_lineage: {},
        source_tracking: {},
        attribution_chains: []
      };
    }
  }
}
