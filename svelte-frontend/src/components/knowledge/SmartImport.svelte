<script>
  import { onMount } from 'svelte';
  import { knowledgeState, uiState } from '../../stores/cognitive.js';
  import { importProgressState } from '../../stores/importProgress.js';
  import { GödelOSAPI } from '../../utils/api.js';
  import { get } from 'svelte/store';
  import { apiHelpers } from '../../stores/cognitive.js';
  import LoadingState from '../ui/LoadingState.svelte';

  let fileInput;
  let dragActive = false;
  let selectedTab = 'file';
  let urlInput = '';
  let textInput = '';
  let textTitle = 'Text Import';
  let apiKeyInput = '';

  // Options
  let enableAI = false;
  let confidenceLevel = 'medium';
  let tabs = [
    { id: 'file', name: 'File', icon: '📁' },
    { id: 'url', name: 'URL', icon: '🌐' },
    { id: 'text', name: 'Text', icon: '📝' },
    { id: 'api', name: 'API', icon: '🔗' }
  ];

  // Progress tracking
  let activeImports = new Map();
  let importProgress = {};
  $: importProgress = $importProgressState;
  $: activeImportsArray = [...activeImports.values()];

  // Fallback polling for import progress if websocket events are missing
  let pollingIntervals = new Map();

  // Utility function to format file sizes
  function formatFileSize(bytes) {
    if (!bytes) return '';
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return Math.round(bytes / Math.pow(1024, i) * 100) / 100 + ' ' + sizes[i];
  }

  // Utility function to format file type
  function formatFileType(type) {
    if (!type || type === 'file') return 'Unknown';
    if (type.startsWith('application/pdf')) return 'PDF Document';
    if (type.startsWith('application/vnd.openxmlformats-officedocument.wordprocessingml')) return 'Word Document';
    if (type.startsWith('text/plain')) return 'Text File';
    if (type.startsWith('text/')) return 'Text';
    if (type.startsWith('image/')) return 'Image';
    return type.split('/').pop().toUpperCase();
  }

  // Utility function to get status color
  function getStatusColor(status) {
    switch (status) {
      case 'completed': return '#4ade80';
      case 'failed': return '#f87171';
      case 'cancelled': return '#94a3b8';
      case 'processing': return '#3b82f6';
      default: return '#64748b';
    }
  }

  function startPolling(importId) {
    if (pollingIntervals.has(importId)) return;
    const poll = async () => {
  console.debug('[Import] polling progress for', importId);
  const progress = await GödelOSAPI.getImportProgress(importId);
  console.debug('[Import] poll result for', importId, progress);
      if (progress && progress.status) {
        importProgressState.update(state => ({
          ...state,
          [importId]: progress
        }));
        if (progress.status === 'completed' || progress.status === 'failed') {
          clearInterval(pollingIntervals.get(importId));
          pollingIntervals.delete(importId);
        }
      }
    };
    const interval = setInterval(poll, 2000);
    pollingIntervals.set(importId, interval);
    poll();
  }

  // --- Import handlers (restored) ---
  async function handleFileSelect(event) {
    const files = event?.target?.files || event;
    if (!files || files.length === 0) return;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      // optimistic temporary id until backend returns a real import id
      const tempId = `temp-${Date.now()}-${i}`;
      activeImports.set(tempId, { id: tempId, filename: file.name, type: file.type || 'file', source: 'upload' });
      activeImports = activeImports;

      importProgressState.update(state => ({
        ...state,
        [tempId]: { status: 'queued', progress: 0, message: 'Queued for upload' }
      }));

      try {
        const result = await GödelOSAPI.importFromFile(file);
  console.debug('[Import] importFromFile result:', result);
        const importId = result?.import_id || result?.id || result?.importId || tempId;
  console.debug('[Import] resolved importId:', importId, 'tempId:', tempId);

        // normalize activeImports key if backend returned a different id
        if (importId !== tempId) {
          const item = activeImports.get(tempId);
          activeImports.delete(tempId);
          item.id = importId;
          activeImports.set(importId, item);
          activeImports = activeImports;
        }

        importProgressState.update(state => ({
          ...state,
          [importId]: { status: 'started', progress: 0, message: 'Upload started' }
        }));

        // start polling for progress (websocket will update if available)
        startPolling(importId);
      } catch (err) {
        importProgressState.update(state => ({
          ...state,
          [tempId]: { status: 'failed', progress: 0, message: err?.message || 'Upload failed' }
        }));
        // remove after short delay
        setTimeout(() => {
          activeImports.delete(tempId);
          activeImports = activeImports;
        }, 3000);
      }
    }

    // reset file input so same file can be chosen again
    if (fileInput) fileInput.value = '';
  }

  async function importFromUrl() {
    if (!urlInput || !urlInput.trim()) return;
    const tempId = `url-${Date.now()}`;
    activeImports.set(tempId, { id: tempId, source: urlInput, type: 'url' });
    activeImports = activeImports;
    importProgressState.update(s => ({ ...s, [tempId]: { status: 'queued', progress: 0, message: 'Starting URL import' } }));

    try {
      const result = await GödelOSAPI.importFromUrl(urlInput, 'web');
  console.debug('[Import] importFromUrl result:', result);
      const importId = result?.import_id || result?.id || tempId;
  console.debug('[Import] resolved importId:', importId, 'tempId:', tempId);
      if (importId !== tempId) {
        const item = activeImports.get(tempId);
        activeImports.delete(tempId);
        item.id = importId;
        activeImports.set(importId, item);
        activeImports = activeImports;
      }
      importProgressState.update(s => ({ ...s, [importId]: { status: 'started', progress: 0, message: 'URL import started' } }));
      startPolling(importId);
      urlInput = '';
    } catch (err) {
      importProgressState.update(s => ({ ...s, [tempId]: { status: 'failed', progress: 0, message: err?.message || 'URL import failed' } }));
      setTimeout(() => { activeImports.delete(tempId); activeImports = activeImports; }, 3000);
    }
  }

  async function importFromText() {
    if (!textInput || !textInput.trim()) return;
    const tempId = `text-${Date.now()}`;
    activeImports.set(tempId, { id: tempId, filename: textTitle || 'Text Import', type: 'text' });
    activeImports = activeImports;
    importProgressState.update(s => ({ ...s, [tempId]: { status: 'queued', progress: 0, message: 'Submitting text' } }));

    try {
      const result = await GödelOSAPI.importFromText(textInput, textTitle, 'document');
  console.debug('[Import] importFromText result:', result);
      const importId = result?.import_id || result?.id || tempId;
  console.debug('[Import] resolved importId:', importId, 'tempId:', tempId);
      if (importId !== tempId) {
        const item = activeImports.get(tempId);
        activeImports.delete(tempId);
        item.id = importId;
        activeImports.set(importId, item);
        activeImports = activeImports;
      }
      importProgressState.update(s => ({ ...s, [importId]: { status: 'started', progress: 0, message: 'Processing text' } }));
      startPolling(importId);
      // clear text input after sending
      textInput = '';
      textTitle = 'Text Import';
    } catch (err) {
      importProgressState.update(s => ({ ...s, [tempId]: { status: 'failed', progress: 0, message: err?.message || 'Text import failed' } }));
      setTimeout(() => { activeImports.delete(tempId); activeImports = activeImports; }, 3000);
    }
  }

  // Drag & drop support and cleanup
  onMount(() => {
    const handleDragOver = (e) => { e.preventDefault(); dragActive = true; };
    const handleDragLeave = (e) => { e.preventDefault(); dragActive = false; };
    const handleDrop = (e) => {
      e.preventDefault(); dragActive = false;
      if (e.dataTransfer && e.dataTransfer.files) {
        handleFileSelect(e.dataTransfer.files);
      }
    };

    window.addEventListener('dragover', handleDragOver);
    window.addEventListener('dragleave', handleDragLeave);
    window.addEventListener('drop', handleDrop);

    return () => {
      window.removeEventListener('dragover', handleDragOver);
      window.removeEventListener('dragleave', handleDragLeave);
      window.removeEventListener('drop', handleDrop);
      // clear any polling intervals
      for (const interval of pollingIntervals.values()) clearInterval(interval);
      pollingIntervals.clear();
    };
  });

  // Clean up completed imports
  $: {
    for (const [id, progress] of Object.entries(importProgress)) {
      if (progress.status === 'completed' || progress.status === 'failed' || progress.status === 'cancelled') {
        setTimeout(() => {
          activeImports.delete(id);
          activeImports = activeImports;
        }, 3000);
        if (progress.status === 'completed') {
          // refresh knowledge graph so imported data becomes visible
          try { apiHelpers.updateKnowledgeFromBackend(); } catch (e) { /* ignore */ }
        }
      }
    }
  }

  // allow cancelling an import (best-effort - backend may not implement)
  async function cancelImport(id) {
    try {
      if (GödelOSAPI.cancelImport) {
        await GödelOSAPI.cancelImport(id);
        importProgressState.update(s => ({ ...s, [id]: { ...(s[id] || {}), status: 'cancelled', message: 'Cancelled by user' } }));
      } else {
        // Best-effort local update if backend doesn't support cancel
        importProgressState.update(s => ({ ...s, [id]: { ...(s[id] || {}), status: 'cancelled', message: 'Cancelled (local)' } }));
      }
    } catch (err) {
      console.warn('cancelImport error', err);
      importProgressState.update(s => ({ ...s, [id]: { ...(s[id] || {}), status: 'failed', message: err?.message || 'Cancel failed' } }));
    }
    // remove from active list shortly after
    setTimeout(() => { activeImports.delete(id); activeImports = activeImports; }, 1000);
  }
</script>

<div class="import-container" class:drag-active={dragActive}>
  <!-- Header -->
  <div class="header">
    <div class="title-section">
      <h2>🧠 Knowledge Import</h2>
      <p>Import and process knowledge from various sources</p>
    </div>
    <div class="stats">
      <div class="stat">
        <span class="stat-value">{$knowledgeState.totalConcepts || 0}</span>
        <span class="stat-label">Concepts</span>
      </div>
      <div class="stat">
        <span class="stat-value">{activeImports.size}</span>
        <span class="stat-label">Active</span>
      </div>
    </div>
  </div>

  <!-- Tab Navigation -->
  <div class="tabs">
    {#each tabs as tab}
      <button 
        class="tab" 
        class:active={selectedTab === tab.id}
        on:click={() => selectedTab = tab.id}
      >
        <span class="tab-icon">{tab.icon}</span>
        <span class="tab-name">{tab.name}</span>
      </button>
    {/each}
  </div>

  <!-- Main Content Area -->
  <div class="content">
    <!-- Import Interface -->
    <div class="import-section">
      {#if selectedTab === 'file'}
        <div class="upload-zone" class:drag-active={dragActive}>
          <div class="upload-content">
            <div class="upload-icon">📁</div>
            <h3>Drop files here or click to browse</h3>
            <p>Supports PDF, TXT, MD, JSON, CSV and more</p>
            <button class="upload-btn" on:click={() => fileInput.click()}>
              Choose Files
            </button>
          </div>
          <input 
            type="file" 
            bind:this={fileInput}
            on:change={handleFileSelect}
            multiple
            hidden
          />
        </div>
      {:else if selectedTab === 'url'}
        <div class="input-section">
          <h3>Import from Web URL</h3>
          <div class="input-group">
            <input 
              type="url" 
              bind:value={urlInput}
              placeholder="https://example.com/document.pdf"
              class="url-input"
            />
            <button 
              class="import-btn" 
              on:click={importFromUrl}
              disabled={!urlInput.trim()}
            >
              Import
            </button>
          </div>
          <p class="help-text">Supports web pages, PDFs, and documents</p>
        </div>
      {:else if selectedTab === 'text'}
        <div class="input-section">
          <h3>Import Text Content</h3>
          <input 
            type="text" 
            bind:value={textTitle}
            placeholder="Document title"
            class="title-input"
          />
          <textarea 
            bind:value={textInput}
            placeholder="Paste your text content here..."
            class="text-input"
            rows="8"
          ></textarea>
          <button 
            class="import-btn" 
            on:click={importFromText}
            disabled={!textInput.trim()}
          >
            Process Text
          </button>
        </div>
      {:else if selectedTab === 'api'}
        <div class="input-section">
          <h3>Connect API Source</h3>
          <div class="input-group">
            <input 
              type="password" 
              bind:value={apiKeyInput}
              placeholder="API key or connection string"
              class="api-input"
            />
            <button 
              class="import-btn" 
              disabled={!apiKeyInput.trim()}
            >
              Connect
            </button>
          </div>
          <p class="help-text">Connect to external knowledge sources</p>
        </div>
      {/if}

      <!-- Inline Progress Panel (moved into import-section for better visibility) -->
      {#if activeImports.size > 0}
        <div class="inline-progress">
          <h4>Active Imports</h4>
          <div class="progress-list">
            {#each activeImportsArray as item}
              <div class="progress-item">
                <div class="progress-header">
                  <div style="display:flex;flex-direction:column;">
                    <span class="progress-name">{item.source || item.filename}</span>
                    <small class="progress-type">{item.type}</small>
                  </div>
                  <div style="display:flex;gap:8px;align-items:center;">
                    {#if importProgress[item.id]?.status === 'completed'}
                      <button class="view-btn" on:click={() => apiHelpers.updateKnowledgeFromBackend()}>View in KG</button>
                    {/if}
                    <button class="cancel-btn" on:click={() => cancelImport(item.id)}>Cancel</button>
                  </div>
                </div>
                {#if importProgress[item.id]}
                  <div class="progress-bar large">
                    <div 
                      class="progress-fill" 
                      style="width: {importProgress[item.id].progress || 0}%"
                    ></div>
                    <div class="progress-percent">{Math.round(importProgress[item.id].progress || 0)}%</div>
                  </div>
                  <div class="progress-status">
                    <span class="status-badge" style="background-color: {getStatusColor(importProgress[item.id].status)}20; color: {getStatusColor(importProgress[item.id].status)}; border: 1px solid {getStatusColor(importProgress[item.id].status)}40;">
                      {importProgress[item.id].status.toUpperCase()}
                    </span>
                    <span class="status-step">
                      {importProgress[item.id].current_step || importProgress[item.id].message || ''}
                    </span>
                  </div>
                  
                  <!-- File Details -->
                  <div class="file-details">
                    <div class="detail-row">
                      <span class="detail-label">File:</span>
                      <span class="detail-value">{item.filename || item.source}</span>
                    </div>
                    {#if item.type && item.type !== 'file'}
                      <div class="detail-row">
                        <span class="detail-label">Type:</span>
                        <span class="detail-value">{formatFileType(item.type)}</span>
                      </div>
                    {/if}
                    {#if importProgress[item.id].completed_steps !== undefined && importProgress[item.id].total_steps}
                      <div class="detail-row">
                        <span class="detail-label">Steps:</span>
                        <span class="detail-value">{importProgress[item.id].completed_steps}/{importProgress[item.id].total_steps}</span>
                      </div>
                    {/if}
                    {#if importProgress[item.id].started_at}
                      <div class="detail-row">
                        <span class="detail-label">Started:</span>
                        <span class="detail-value">{new Date(importProgress[item.id].started_at * 1000).toLocaleTimeString()}</span>
                      </div>
                    {/if}
                    {#if importProgress[item.id].estimated_completion}
                      <div class="detail-row">
                        <span class="detail-label">ETA:</span>
                        <span class="detail-value">{new Date(importProgress[item.id].estimated_completion * 1000).toLocaleTimeString()}</span>
                      </div>
                    {/if}
                    {#if importProgress[item.id].warnings && importProgress[item.id].warnings.length > 0}
                      <div class="detail-row">
                        <span class="detail-label">Warnings:</span>
                        <span class="detail-value warning">{importProgress[item.id].warnings.length}</span>
                      </div>
                    {/if}
                  </div>
                {:else}
                  <div class="progress-bar large">
                    <div class="progress-fill" style="width: 10%"></div>
                    <div class="progress-percent">0%</div>
                  </div>
                  <div class="progress-status">Starting...</div>
                  
                  <!-- File Details -->
                  <div class="file-details">
                    <div class="detail-row">
                      <span class="detail-label">File:</span>
                      <span class="detail-value">{item.filename || item.source}</span>
                    </div>
                    {#if item.type && item.type !== 'file'}
                      <div class="detail-row">
                        <span class="detail-label">Type:</span>
                        <span class="detail-value">{formatFileType(item.type)}</span>
                      </div>
                    {/if}
                  </div>
                {/if}
              </div>
            {/each}
          </div>
        </div>
      {/if}
    </div>
  <!-- Options Panel + Progress pinned below -->
  <div class="options-panel">
      <h4>Processing Options</h4>
      <div class="option-group">
        <label class="toggle-option">
          <input type="checkbox" bind:checked={enableAI} />
          <span class="toggle"></span>
          <span>AI Processing</span>
        </label>
        <div class="confidence-option">
          <label for="confidence-select">Confidence Level:</label>
          <select id="confidence-select" bind:value={confidenceLevel}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>
    </div>
  </div>

  
</div>

<style>
  .import-container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 2rem;
    background: #0f0f23;
    color: #fff;
    border-radius: 1rem;
    min-height: 600px;
    max-height: 90vh;
    /* container itself should not scroll; inner regions handle overflow */
    overflow: hidden;
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .import-container.drag-active {
    background: #1a1a3e;
    border: 2px dashed #4a9eff;
  }

  /* Header */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: 1rem;
    border-bottom: 1px solid #2a2a4a;
  }

  .title-section h2 {
    margin: 0;
    font-size: 1.8rem;
    font-weight: 700;
    color: #4a9eff;
  }

  .title-section p {
    margin: 0.5rem 0 0 0;
    color: #aaa;
    font-size: 1rem;
  }

  .stats {
    display: flex;
    gap: 2rem;
  }

  .stat {
    text-align: center;
  }

  .stat-value {
    display: block;
    font-size: 1.5rem;
    font-weight: 700;
    color: #4a9eff;
  }

  .stat-label {
    font-size: 0.9rem;
    color: #aaa;
  }

  /* Tabs */
  .tabs {
    display: flex;
    gap: 0.5rem;
    background: #1a1a3e;
    padding: 0.5rem;
    border-radius: 0.75rem;
  }

  .tab {
    flex: 1;
    background: transparent;
    border: none;
    color: #aaa;
    padding: 1rem;
    border-radius: 0.5rem;
    cursor: pointer;
    transition: all 0.2s;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    font-size: 1rem;
  }

  .tab:hover {
    background: #2a2a4a;
    color: #fff;
  }

  .tab.active {
    background: #4a9eff;
    color: #fff;
  }

  .tab-icon {
    font-size: 1.2rem;
  }

  /* Content */
  .content {
    display: grid;
    grid-template-columns: 3fr 1fr;
    gap: 2rem;
    flex: 1;
  min-height: 520px;
  }

  /* Import Section */
  .import-section {
    background: #1a1a3e;
    border-radius: 1rem;
    padding: 2rem;
  display: flex;
  align-items: stretch;
  justify-content: flex-start;
  overflow: auto; /* scroll inside if content grows */
  }

  .upload-zone {
    width: 100%;
    min-height: 300px;
    border: 2px dashed #4a4a6a;
    border-radius: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s;
    cursor: pointer;
  }

  .upload-zone:hover,
  .upload-zone.drag-active {
    border-color: #4a9eff;
    background: rgba(74, 158, 255, 0.1);
  }

  .upload-content {
    text-align: center;
  }

  .upload-icon {
    font-size: 3rem;
    margin-bottom: 1rem;
  }

  .upload-content h3 {
    margin: 0 0 0.5rem 0;
    font-size: 1.3rem;
    color: #fff;
  }

  .upload-content p {
    margin: 0 0 1.5rem 0;
    color: #aaa;
  }

  .upload-btn {
    background: #4a9eff;
    color: #fff;
    border: none;
    padding: 0.75rem 2rem;
    border-radius: 0.5rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
  }

  .upload-btn:hover {
    background: #3a8eef;
  }

  /* Input Section */
  .input-section {
    width: 100%;
    display: flex;
    flex-direction: column;
  }

  .input-section h3 {
    margin: 0 0 1.5rem 0;
    font-size: 1.3rem;
    color: #fff;
  }

  .input-group {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 1rem;
  }

  .url-input,
  .api-input,
  .title-input {
    flex: 1;
    background: #2a2a4a;
    border: 1px solid #4a4a6a;
    color: #fff;
    padding: 0.75rem;
    border-radius: 0.5rem;
    font-size: 1rem;
  }

  .text-input {
    width: 100%;
    background: #2a2a4a;
    border: 1px solid #4a4a6a;
    color: #fff;
    padding: 1rem;
    border-radius: 0.5rem;
    font-size: 1rem;
    resize: vertical;
    margin-bottom: 1rem;
  }

  .import-btn {
    background: #4a9eff;
    color: #fff;
    border: none;
    padding: 0.75rem 1.5rem;
    border-radius: 0.5rem;
    font-size: 1rem;
    cursor: pointer;
    transition: background 0.2s;
    white-space: nowrap;
  }

  .import-btn:hover:not(:disabled) {
    background: #3a8eef;
  }

  .import-btn:disabled {
    background: #4a4a6a;
    cursor: not-allowed;
  }

  .help-text {
    margin: 0;
    color: #aaa;
    font-size: 0.9rem;
  }

  /* Options Panel */
  .options-panel {
    background: #1a1a3e;
    border-radius: 1rem;
    padding: 1.5rem;
  height: fit-content;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  }

  .options-panel h4 {
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
    color: #4a9eff;
  }

  .option-group {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  }

  .toggle-option {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    cursor: pointer;
  }

  .toggle-option input[type="checkbox"] {
    display: none;
  }

  .toggle {
    width: 40px;
    height: 20px;
    background: #4a4a6a;
    border-radius: 10px;
    position: relative;
    transition: background 0.2s;
  }

  .toggle::after {
    content: '';
    position: absolute;
    left: 2px;
    top: 2px;
    width: 16px;
    height: 16px;
    background: #fff;
    border-radius: 50%;
    transition: left 0.2s;
  }

  .toggle-option input[type="checkbox"]:checked + .toggle {
    background: #4a9eff;
  }

  .toggle-option input[type="checkbox"]:checked + .toggle::after {
    left: 22px;
  }

  .confidence-option {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .confidence-option select {
    background: #2a2a4a;
    border: 1px solid #4a4a6a;
    color: #fff;
    padding: 0.5rem;
    border-radius: 0.25rem;
  }

  /* Progress Section */
  .progress-section {
    background: #1a1a3e;
    border-radius: 1rem;
    padding: 1.5rem;
  width: 100%;
  max-height: 260px;
  overflow: auto;
  position: sticky;
  bottom: 0;
  }

  .progress-section h4 {
    margin: 0 0 1rem 0;
    font-size: 1.1rem;
    color: #4a9eff;
  }

  .progress-list {
    display: flex;
    flex-direction: column;
    gap: 1rem;
  max-height: 220px;
  overflow: auto;
  }

.cancel-btn {
  background: transparent;
  color: #ff7b7b;
  border: 1px solid #ff7b7b33;
  padding: 0.25rem 0.5rem;
  border-radius: 0.375rem;
  font-size: 0.9rem;
  cursor: pointer;
}
.cancel-btn:hover { background: rgba(255,123,123,0.06); }

  .progress-item {
    background: #2a2a4a;
    border-radius: 0.5rem;
    padding: 1rem;
  }

  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .progress-name {
    font-weight: 600;
    color: #fff;
  }

  .progress-type {
    background: #4a9eff;
    color: #fff;
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.8rem;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: #4a4a6a;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .progress-fill {
    height: 100%;
    background: linear-gradient(90deg, #4a9eff, #7ed6ff);
    transition: width 0.3s ease;
  }

  .progress-status {
    font-size: 0.9rem;
    color: #aaa;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .status-badge {
    padding: 0.25rem 0.5rem;
    border-radius: 0.25rem;
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .status-step {
    color: #ddd;
    font-size: 0.85rem;
  }

  /* Inline progress panel inside import-section */
  .inline-progress {
    margin-top: 1.25rem;
    background: rgba(255,255,255,0.02);
    padding: 1rem;
    border-radius: 0.75rem;
  }

  .progress-bar.large {
    height: 14px;
    position: relative;
  }

  .progress-percent {
    position: absolute;
    right: 8px;
    top: -18px;
    font-size: 0.85rem;
    color: #ccc;
  }

  .view-btn {
    background: #2a9eff33;
    color: #4a9eff;
    border: 1px solid #2a9eff55;
    padding: 0.25rem 0.5rem;
    border-radius: 0.375rem;
    cursor: pointer;
  }

  .file-details {
    margin-top: 0.75rem;
    background: rgba(255,255,255,0.03);
    padding: 0.75rem;
    border-radius: 0.375rem;
    border: 1px solid rgba(255,255,255,0.06);
  }

  .detail-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.4rem;
  }

  .detail-row:last-child {
    margin-bottom: 0;
  }

  .detail-label {
    font-size: 0.85rem;
    color: #aaa;
    font-weight: 500;
    min-width: 60px;
  }

  .detail-value {
    font-size: 0.85rem;
    color: #ddd;
    text-align: right;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', monospace;
    word-break: break-all;
    max-width: 200px;
  }

  .detail-value.warning {
    color: #fbbf24;
    font-weight: 600;
  }

  /* Responsive */
  @media (max-width: 768px) {
    .content {
      grid-template-columns: 1fr;
    }
    
    .tabs {
      flex-wrap: wrap;
    }
    
    .tab {
      flex: 1 1 45%;
    }
  }
</style>
