<script>
  import { onMount } from 'svelte';
  import { fade, fly } from 'svelte/transition';
  
  // Props
  export let runId = null;
  export let condition = 'recursive';
  export let autoRefresh = false;
  
  // State
  let experimentRuns = [];
  let selectedRun = null;
  let metricsData = [];
  let phaseData = [];
  let loading = false;
  let error = null;
  let downloadFormats = ['jsonl', 'json', 'csv'];
  
  // Reactive statements
  $: if (selectedRun && selectedRun.run_id) {
    loadMetricsData(selectedRun.run_id);
  }
  
  // API calls
  async function loadExperimentRuns() {
    loading = true;
    error = null;
    try {
      const response = await fetch('/api/v1/introspection/experiments');
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      
      const data = await response.json();
      experimentRuns = data.experiments || [];
      
      // Auto-select the most recent run if none selected
      if (!selectedRun && experimentRuns.length > 0) {
        selectedRun = experimentRuns[0];
      }
    } catch (err) {
      error = `Failed to load experiment runs: ${err.message}`;
      console.error(error, err);
    } finally {
      loading = false;
    }
  }
  
  async function loadMetricsData(runId) {
    if (!runId) return;
    
    loading = true;
    error = null;
    try {
      const response = await fetch(`/api/v1/introspection/experiments/${runId}/metrics`);
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      
      const data = await response.json();
      metricsData = data.metrics || [];
      phaseData = data.phases || [];
    } catch (err) {
      error = `Failed to load metrics data: ${err.message}`;
      console.error(error, err);
    } finally {
      loading = false;
    }
  }
  
  async function downloadData(format, dataType = 'metrics') {
    if (!selectedRun) return;
    
    try {
      const endpoint = dataType === 'manifest' 
        ? `/api/v1/introspection/experiments/${selectedRun.run_id}/manifest`
        : `/api/v1/introspection/experiments/${selectedRun.run_id}/download?format=${format}`;
        
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      
      // Create download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${selectedRun.run_id}_${dataType}.${format}`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      error = `Download failed: ${err.message}`;
      console.error(error, err);
    }
  }
  
  function getMetricColor(value, metric) {
    // Color coding based on metric ranges
    const ranges = {
      complexity: { low: 0.3, high: 0.7 },
      novelty: { low: 0.2, high: 0.6 },
      drift: { low: 0.1, high: 0.4 },
      coherence: { low: 0.6, high: 0.9 }
    };
    
    const range = ranges[metric] || { low: 0.3, high: 0.7 };
    
    if (value < range.low) return 'text-blue-600';
    if (value > range.high) return 'text-red-600';
    return 'text-green-600';
  }
  
  function formatMetric(value) {
    return typeof value === 'number' ? value.toFixed(3) : 'N/A';
  }
  
  function formatTimestamp(timestamp) {
    return new Date(timestamp * 1000).toLocaleTimeString();
  }
  
  // Auto-refresh logic
  let refreshInterval;
  $: if (autoRefresh && selectedRun) {
    refreshInterval = setInterval(() => {
      loadMetricsData(selectedRun.run_id);
    }, 5000);
  } else if (refreshInterval) {
    clearInterval(refreshInterval);
    refreshInterval = null;
  }
  
  onMount(() => {
    loadExperimentRuns();
    
    return () => {
      if (refreshInterval) {
        clearInterval(refreshInterval);
      }
    };
  });
</script>

<!-- Run Selector -->
<div class="mb-6 p-4 bg-gray-50 rounded-lg">
  <div class="flex items-center justify-between mb-4">
    <h3 class="text-lg font-semibold text-gray-900">Recursive Introspection Experiments</h3>
    <div class="flex gap-2">
      <label class="flex items-center">
        <input 
          type="checkbox" 
          bind:checked={autoRefresh} 
          class="mr-2"
        />
        Auto-refresh
      </label>
      <button 
        on:click={loadExperimentRuns}
        class="px-3 py-1 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
        disabled={loading}
      >
        Refresh
      </button>
    </div>
  </div>
  
  {#if experimentRuns.length > 0}
    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- Run Selector -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Select Experiment Run:</label>
        <select 
          bind:value={selectedRun} 
          class="w-full p-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        >
          {#each experimentRuns as run}
            <option value={run}>
              {run.condition} - {new Date(run.start_time * 1000).toLocaleString()} 
              ({run.status})
            </option>
          {/each}
        </select>
      </div>
      
      <!-- Download Controls -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-2">Download Data:</label>
        <div class="flex gap-1">
          {#each downloadFormats as format}
            <button 
              on:click={() => downloadData(format)}
              class="px-2 py-1 bg-gray-500 text-white text-xs rounded hover:bg-gray-600 transition-colors"
              disabled={!selectedRun}
            >
              {format.toUpperCase()}
            </button>
          {/each}
          <button 
            on:click={() => downloadData('json', 'manifest')}
            class="px-2 py-1 bg-purple-500 text-white text-xs rounded hover:bg-purple-600 transition-colors"
            disabled={!selectedRun}
          >
            MANIFEST
          </button>
        </div>
      </div>
      
      <!-- Run Info -->
      {#if selectedRun}
        <div class="text-sm text-gray-600">
          <div><strong>Condition:</strong> {selectedRun.condition}</div>
          <div><strong>Depth:</strong> {selectedRun.max_depth || 'N/A'}</div>
          <div><strong>Status:</strong> {selectedRun.status}</div>
          <div><strong>Records:</strong> {metricsData.length}</div>
        </div>
      {/if}
    </div>
  {:else if !loading}
    <div class="text-center text-gray-500 py-8">
      No experiment runs found. Start an introspection experiment to see data here.
    </div>
  {/if}
</div>

<!-- Error Display -->
{#if error}
  <div class="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded" in:fade>
    {error}
  </div>
{/if}

<!-- Loading State -->
{#if loading}
  <div class="flex items-center justify-center py-8">
    <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
    <span class="ml-2 text-gray-600">Loading experiment data...</span>
  </div>
{/if}

<!-- Metrics Table -->
{#if metricsData.length > 0 && !loading}
  <div class="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden" in:fly={{ y: 20, duration: 300 }}>
    <div class="px-4 py-3 bg-gray-50 border-b border-gray-200">
      <h4 class="text-lg font-medium text-gray-900">
        Introspection Metrics - Depth × Complexity/Δc/Drift/Novelty
      </h4>
      <p class="text-sm text-gray-600 mt-1">
        Real-time cognitive metrics across recursive introspection depths
      </p>
    </div>
    
    <div class="overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200">
        <thead class="bg-gray-50">
          <tr>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Depth
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Complexity (c)
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Delta C (Δc)
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Drift
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Novelty
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Coherence
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Phase
            </th>
            <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
              Timestamp
            </th>
          </tr>
        </thead>
        <tbody class="bg-white divide-y divide-gray-200">
          {#each metricsData as record, index}
            <tr class="hover:bg-gray-50 transition-colors">
              <td class="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                {record.depth}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm {getMetricColor(record.complexity, 'complexity')}">
                {formatMetric(record.complexity)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm {getMetricColor(Math.abs(record.delta_complexity || 0), 'complexity')}">
                {formatMetric(record.delta_complexity)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm {getMetricColor(record.drift, 'drift')}">
                {formatMetric(record.drift)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm {getMetricColor(record.novelty, 'novelty')}">
                {formatMetric(record.novelty)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm {getMetricColor(record.coherence, 'coherence')}">
                {formatMetric(record.coherence)}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm">
                {#if record.phase_info}
                  <span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium 
                    {record.phase_info.phase === 'exploration' ? 'bg-blue-100 text-blue-800' : 
                     record.phase_info.phase === 'convergence' ? 'bg-green-100 text-green-800' : 
                     'bg-gray-100 text-gray-800'}">
                    {record.phase_info.phase}
                  </span>
                {:else}
                  <span class="text-gray-400">-</span>
                {/if}
              </td>
              <td class="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                {formatTimestamp(record.timestamp)}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    
    <!-- Sparklines Section -->
    {#if metricsData.length >= 3}
      <div class="px-4 py-6 bg-gray-50 border-t border-gray-200">
        <h5 class="text-md font-medium text-gray-900 mb-4">Metric Trends</h5>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {#each ['complexity', 'drift', 'novelty', 'coherence'] as metric}
            <div class="bg-white p-3 rounded border">
              <div class="text-sm font-medium text-gray-700 mb-2 capitalize">{metric}</div>
              <div class="h-16 bg-gray-100 rounded flex items-center justify-center">
                <!-- Placeholder for sparkline charts - would integrate with Chart.js or D3 -->
                <span class="text-xs text-gray-500">Sparkline: {metric}</span>
              </div>
              <div class="text-xs text-gray-500 mt-1">
                Avg: {formatMetric(metricsData.reduce((sum, d) => sum + (d[metric] || 0), 0) / metricsData.length)}
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
{:else if !loading && selectedRun}
  <div class="text-center text-gray-500 py-8 bg-gray-50 rounded-lg">
    No metrics data available for this experiment run.
  </div>
{/if}

<style>
  /* Custom scrollbar for the table */
  .overflow-x-auto::-webkit-scrollbar {
    height: 6px;
  }
  
  .overflow-x-auto::-webkit-scrollbar-track {
    background: #f1f1f1;
    border-radius: 3px;
  }
  
  .overflow-x-auto::-webkit-scrollbar-thumb {
    background: #c1c1c1;
    border-radius: 3px;
  }
  
  .overflow-x-auto::-webkit-scrollbar-thumb:hover {
    background: #a8a8a8;
  }
</style>
