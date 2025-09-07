<script>
  import { onMount } from 'svelte';
  import { knowledgeState, uiState } from '../../stores/cognitive.js';
  import { importProgressState } from '../../stores/importProgress.js';
  import { GödelOSAPI } from '../../utils/api.js';
  import { get } from 'svelte/store';
  import LoadingState from '../ui/LoadingState.svelte';
  
  let fileInput;
  let dragActive = false;
  let selectedTab = 'file';
  let urlInput = '';
  let textInput = '';
  let textTitle = 'Text Import';
  let apiKeyInput = '';
  
  // Progress tracking
  let activeImports = new Map();
  let importProgress = {};
  $: importProgress = $importProgressState;
  $: activeImportsArray = [...activeImports.values()];
  
  // Simple processing options
  let enableAI = true;
  let confidenceLevel = 'medium';
  
  const tabs = [
    { id: 'file', name: 'File Upload', icon: '📁' },
    { id: 'url', name: 'Web URL', icon: '🌐' },
    { id: 'text', name: 'Text Input', icon: '📝' },
    { id: 'api', name: 'API Source', icon: '🔗' }
  ];

  onMount(() => {
    setupDragAndDrop();
  });

  function setupDragAndDrop() {
    const container = document.querySelector('.import-container');
    if (!container) return;
    
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      container.addEventListener(eventName, preventDefaults, false);
    });
    
    ['dragenter', 'dragover'].forEach(eventName => {
      container.addEventListener(eventName, () => dragActive = true, false);
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
      container.addEventListener(eventName, () => dragActive = false, false);
    });
    
    container.addEventListener('drop', handleDrop, false);
  }

  function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
  }

  function handleDrop(e) {
    const files = Array.from(e.dataTransfer.files);
    processFiles(files);
  }

  function handleFileSelect() {
    if (fileInput.files.length > 0) {
      const files = Array.from(fileInput.files);
      processFiles(files);
    }
  }

  async function processFiles(files) {
    for (const file of files) {
      try {
        const importResponse = await GödelOSAPI.importFromFile(file);
        const importId = importResponse.import_id || importResponse.file_id;
        
        if (importId) {
          activeImports.set(importId, {
            id: importId,
            filename: file.name,
            status: 'processing',
            type: 'file',
            startTime: Date.now()
          });
          activeImports = activeImports;
        }
      } catch (error) {
        console.error('Import error:', error);
      }
    }
  }

  async function importFromUrl() {
    if (!urlInput.trim()) return;
    
    try {
      const importResponse = await GödelOSAPI.importFromUrl(urlInput);
      const importId = importResponse.import_id;
      
      if (importId) {
        activeImports.set(importId, {
          id: importId,
          source: urlInput,
          status: 'processing',
          type: 'url',
          startTime: Date.now()
        });
        activeImports = activeImports;
        urlInput = '';
      }
    } catch (error) {
      console.error('URL import error:', error);
    }
  }

  async function importFromText() {
    if (!textInput.trim()) return;
    
    try {
      const importResponse = await GödelOSAPI.importFromText(textInput, textTitle);
      const importId = importResponse.import_id;
      
      if (importId) {
        activeImports.set(importId, {
          id: importId,
          source: textTitle,
          status: 'processing',
          type: 'text',
          startTime: Date.now()
        });
        activeImports = activeImports;
        textInput = '';
        textTitle = 'Text Import';
      }
    } catch (error) {
      console.error('Text import error:', error);
    }
  }

  // Clean up completed imports
  $: {
    for (const [id, progress] of Object.entries(importProgress)) {
      if (progress.status === 'completed' || progress.status === 'failed') {
        setTimeout(() => {
          activeImports.delete(id);
          activeImports = activeImports;
        }, 3000);
      }
    }
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
    </div>

    <!-- Options Panel -->
    <div class="options-panel">
      <h4>Processing Options</h4>
      <div class="option-group">
        <label class="toggle-option">
          <input type="checkbox" bind:checked={enableAI} />
          <span class="toggle"></span>
          <span>AI Processing</span>
        </label>
        <div class="confidence-option">
          <label>Confidence Level:</label>
          <select bind:value={confidenceLevel}>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </div>
      </div>
    </div>
  </div>

  <!-- Progress Section -->
  {#if activeImports.size > 0}
    <div class="progress-section">
      <h4>Active Imports</h4>
      <div class="progress-list">
        {#each activeImportsArray as item}
          <div class="progress-item">
            <div class="progress-header">
              <span class="progress-name">{item.source || item.filename}</span>
              <span class="progress-type">{item.type}</span>
            </div>
            {#if importProgress[item.id]}
              <div class="progress-bar">
                <div 
                  class="progress-fill" 
                  style="width: {importProgress[item.id].progress || 0}%"
                ></div>
              </div>
              <div class="progress-status">
                {importProgress[item.id].status} - {importProgress[item.id].message || ''}
              </div>
            {:else}
              <div class="progress-bar">
                <div class="progress-fill" style="width: 10%"></div>
              </div>
              <div class="progress-status">Starting...</div>
            {/if}
          </div>
        {/each}
      </div>
    </div>
  {/if}
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
    overflow-y: auto;
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
    grid-template-columns: 2fr 1fr;
    gap: 2rem;
    flex: 1;
  }

  /* Import Section */
  .import-section {
    background: #1a1a3e;
    border-radius: 1rem;
    padding: 2rem;
    display: flex;
    align-items: center;
    justify-content: center;
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
  }qqqqq  qqqq

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
    max-height: 200px;
    overflow-y: auto;
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
  }

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
