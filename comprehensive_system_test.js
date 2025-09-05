const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const FRONTEND_URL = 'http://localhost:3001';
const BACKEND_URL = 'http://localhost:8000';

class SystemTester {
  constructor() {
    this.browser = null;
    this.page = null;
    this.testResults = {
      navigation: {},
      functionality: {},
      data_integrity: {},
      backend_connectivity: {},
      ui_responsiveness: {},
      errors: []
    };
  }

  async initialize() {
    console.log('🚀 Initializing comprehensive system test...');
    this.browser = await chromium.launch({ 
      headless: false,
      devtools: true 
    });
    this.page = await this.browser.newPage();
    
    // Track console errors
    this.page.on('console', msg => {
      if (msg.type() === 'error') {
        this.testResults.errors.push({
          type: 'console_error',
          message: msg.text(),
          timestamp: new Date().toISOString()
        });
      }
    });
    
    // Track network failures
    this.page.on('response', response => {
      if (response.status() >= 400) {
        this.testResults.errors.push({
          type: 'network_error',
          url: response.url(),
          status: response.status(),
          timestamp: new Date().toISOString()
        });
      }
    });
  }

  async testBackendConnectivity() {
    console.log('🔗 Testing backend connectivity...');
    
    const endpoints = [
      '/docs',
      '/api/health',
      '/api/knowledge/graph',
      '/api/cognitive/state',
      '/api/enhanced-cognitive/dashboard',
      '/api/transparency/statistics',
      '/api/transparency/sessions/active'
    ];
    
    for (const endpoint of endpoints) {
      try {
        const response = await fetch(`${BACKEND_URL}${endpoint}`);
        this.testResults.backend_connectivity[endpoint] = {
          status: response.status,
          ok: response.ok,
          test_passed: response.ok
        };
      } catch (error) {
        this.testResults.backend_connectivity[endpoint] = {
          error: error.message,
          test_passed: false
        };
      }
    }
  }

  async testNavigation() {
    console.log('🧭 Testing navigation system...');
    
    await this.page.goto(FRONTEND_URL);
    await this.page.waitForLoadState('networkidle');
    
    // Test navigation buttons
    const navButtons = await this.page.locator('nav button, nav a').count();
    console.log(`Found ${navButtons} navigation elements`);
    
    const views = [
      { name: 'Dashboard', selector: 'text=Dashboard' },
      { name: 'Enhanced Dashboard', selector: 'text=Enhanced' },
      { name: 'Cognitive State', selector: 'text=Cognitive State' },
      { name: 'Knowledge Graph', selector: 'text=Knowledge Graph' },
      { name: 'Query Interface', selector: 'text=Query Interface' },
      { name: 'Human Interaction', selector: 'text=Human Interaction' },
      { name: 'Transparency', selector: 'text=Transparency' },
      { name: 'Provenance', selector: 'text=Provenance' },
      { name: 'Reflection', selector: 'text=Reflection' }
    ];
    
    for (const view of views) {
      try {
        console.log(`Testing navigation to: ${view.name}`);
        
        await this.page.click(view.selector, { timeout: 3000 });
        await this.page.waitForTimeout(1000);
        
        // Check if view actually changed
        const currentContent = await this.page.textContent('main', { timeout: 3000 });
        const urlChanged = this.page.url() !== FRONTEND_URL;
        
        this.testResults.navigation[view.name] = {
          button_exists: true,
          button_clickable: true,
          content_loaded: currentContent && currentContent.length > 100,
          url_changed: urlChanged,
          test_passed: true
        };
        
      } catch (error) {
        this.testResults.navigation[view.name] = {
          button_exists: false,
          error: error.message,
          test_passed: false
        };
      }
    }
  }

  async testDataIntegrity() {
    console.log('📊 Testing data integrity across views...');
    
    // Test Enhanced Dashboard
    await this.page.goto(`${FRONTEND_URL}/#/enhanced`);
    await this.page.waitForTimeout(3000);
    
    const enhancedData = await this.extractViewData('Enhanced Dashboard');
    this.testResults.data_integrity.enhanced_dashboard = enhancedData;
    
    // Test Cognitive State
    await this.page.goto(`${FRONTEND_URL}/#/cognitive-state`);
    await this.page.waitForTimeout(3000);
    
    const cognitiveData = await this.extractViewData('Cognitive State');
    this.testResults.data_integrity.cognitive_state = cognitiveData;
    
    // Test Knowledge Graph
    await this.page.goto(`${FRONTEND_URL}/#/knowledge-graph`);
    await this.page.waitForTimeout(3000);
    
    const knowledgeData = await this.extractViewData('Knowledge Graph');
    this.testResults.data_integrity.knowledge_graph = knowledgeData;
  }

  async extractViewData(viewName) {
    console.log(`📋 Extracting data from ${viewName}...`);
    
    const data = {
      text_content: '',
      numeric_values: [],
      undefined_values: 0,
      nan_values: 0,
      error_messages: 0,
      dynamic_content: false
    };
    
    try {
      data.text_content = await this.page.textContent('body');
      
      // Look for undefined values
      const undefinedMatches = data.text_content.match(/undefined/gi);
      data.undefined_values = undefinedMatches ? undefinedMatches.length : 0;
      
      // Look for NaN values
      const nanMatches = data.text_content.match(/NaN/gi);
      data.nan_values = nanMatches ? nanMatches.length : 0;
      
      // Look for error messages
      const errorMatches = data.text_content.match(/error|failed|broken/gi);
      data.error_messages = errorMatches ? errorMatches.length : 0;
      
      // Extract numeric values
      const numericMatches = data.text_content.match(/\d+(\.\d+)?%?/g);
      data.numeric_values = numericMatches || [];
      
      // Check for dynamic content (timestamp indicators)
      data.dynamic_content = data.text_content.includes('ago') || 
                           data.text_content.includes('Last update') ||
                           data.text_content.includes('Reconnecting');
      
      // Screenshot
      await this.page.screenshot({ 
        path: `/tmp/${viewName.replace(/ /g, '_').toLowerCase()}_screenshot.png`,
        fullPage: true 
      });
      
      data.test_passed = data.undefined_values === 0 && 
                        data.nan_values === 0 && 
                        data.error_messages === 0;
      
    } catch (error) {
      data.error = error.message;
      data.test_passed = false;
    }
    
    return data;
  }

  async testSpecificFeatures() {
    console.log('🔧 Testing specific functionality...');
    
    // Test knowledge import
    await this.testKnowledgeImport();
    
    // Test reasoning sessions
    await this.testReasoningSessions();
    
    // Test transparency modal
    await this.testTransparencyModal();
    
    // Test WebSocket connections
    await this.testWebSocketConnection();
  }

  async testKnowledgeImport() {
    console.log('📚 Testing knowledge import functionality...');
    
    try {
      await this.page.goto(`${FRONTEND_URL}/#/knowledge-graph`);
      await this.page.waitForTimeout(3000);
      
      // Look for import buttons
      const importButton = this.page.locator('text=Import, text=Add, text=Upload').first();
      const importExists = await importButton.count() > 0;
      
      if (importExists) {
        await importButton.click();
        await this.page.waitForTimeout(1000);
      }
      
      this.testResults.functionality.knowledge_import = {
        import_button_exists: importExists,
        test_passed: importExists
      };
      
    } catch (error) {
      this.testResults.functionality.knowledge_import = {
        error: error.message,
        test_passed: false
      };
    }
  }

  async testReasoningSessions() {
    console.log('🧠 Testing reasoning sessions...');
    
    try {
      await this.page.goto(`${FRONTEND_URL}/#/transparency`);
      await this.page.waitForTimeout(3000);
      
      // Look for reasoning session controls
      const startButton = this.page.locator('text=Start, text=Begin, text=New Session').first();
      const sessionExists = await startButton.count() > 0;
      
      if (sessionExists) {
        await startButton.click();
        await this.page.waitForTimeout(5000);
        
        // Check for progress indicators
        const progressText = await this.page.textContent('body');
        const hasProgress = progressText.includes('%') && !progressText.includes('0%');
        
        this.testResults.functionality.reasoning_sessions = {
          start_button_exists: sessionExists,
          progress_working: hasProgress,
          test_passed: sessionExists && hasProgress
        };
      } else {
        this.testResults.functionality.reasoning_sessions = {
          start_button_exists: false,
          test_passed: false
        };
      }
      
    } catch (error) {
      this.testResults.functionality.reasoning_sessions = {
        error: error.message,
        test_passed: false
      };
    }
  }

  async testTransparencyModal() {
    console.log('🔍 Testing transparency modal...');
    
    try {
      await this.page.goto(`${FRONTEND_URL}/#/transparency`);
      await this.page.waitForTimeout(3000);
      
      // Look for modal triggers
      const detailButtons = this.page.locator('text=Details, text=View, text=Show, button:has-text("...")');
      const modalTriggerExists = await detailButtons.count() > 0;
      
      if (modalTriggerExists) {
        await detailButtons.first().click();
        await this.page.waitForTimeout(1000);
        
        const modalContent = await this.page.textContent('body');
        const hasTestData = modalContent.includes('test') || modalContent.includes('dummy') || modalContent.includes('mock');
        
        this.testResults.functionality.transparency_modal = {
          modal_trigger_exists: modalTriggerExists,
          shows_test_data: hasTestData,
          test_passed: modalTriggerExists && !hasTestData
        };
      } else {
        this.testResults.functionality.transparency_modal = {
          modal_trigger_exists: false,
          test_passed: false
        };
      }
      
    } catch (error) {
      this.testResults.functionality.transparency_modal = {
        error: error.message,
        test_passed: false
      };
    }
  }

  async testWebSocketConnection() {
    console.log('🔌 Testing WebSocket connection...');
    
    try {
      await this.page.goto(`${FRONTEND_URL}/#/enhanced`);
      await this.page.waitForTimeout(3000);
      
      const connectionStatus = await this.page.textContent('body');
      const isConnected = connectionStatus.includes('Connected') && !connectionStatus.includes('Disconnected');
      
      this.testResults.functionality.websocket_connection = {
        status_indicator_present: connectionStatus.includes('Connected') || connectionStatus.includes('Disconnected'),
        is_connected: isConnected,
        test_passed: isConnected
      };
      
    } catch (error) {
      this.testResults.functionality.websocket_connection = {
        error: error.message,
        test_passed: false
      };
    }
  }

  async generateReport() {
    console.log('📋 Generating comprehensive test report...');
    
    const report = {
      test_summary: {
        timestamp: new Date().toISOString(),
        frontend_url: FRONTEND_URL,
        backend_url: BACKEND_URL,
        total_tests: 0,
        tests_passed: 0,
        tests_failed: 0,
        overall_score: 0
      },
      detailed_results: this.testResults,
      recommendations: [],
      critical_issues: []
    };
    
    // Calculate scores
    const calculatePassRate = (category) => {
      const tests = Object.values(category);
      const passed = tests.filter(test => test.test_passed === true).length;
      const total = tests.length;
      return { passed, total, rate: total > 0 ? (passed / total) * 100 : 0 };
    };
    
    const navResults = calculatePassRate(this.testResults.navigation);
    const funcResults = calculatePassRate(this.testResults.functionality);
    const dataResults = calculatePassRate(this.testResults.data_integrity);
    const backendResults = calculatePassRate(this.testResults.backend_connectivity);
    
    report.test_summary.total_tests = navResults.total + funcResults.total + dataResults.total + backendResults.total;
    report.test_summary.tests_passed = navResults.passed + funcResults.passed + dataResults.passed + backendResults.passed;
    report.test_summary.tests_failed = report.test_summary.total_tests - report.test_summary.tests_passed;
    report.test_summary.overall_score = Math.round((report.test_summary.tests_passed / report.test_summary.total_tests) * 100);
    
    // Generate recommendations
    if (navResults.rate < 80) {
      report.critical_issues.push('Navigation system has critical failures');
      report.recommendations.push('Fix navigation button functionality and routing');
    }
    
    if (dataResults.rate < 50) {
      report.critical_issues.push('Data integrity issues detected - undefined/NaN values present');
      report.recommendations.push('Implement proper data validation and fallback values');
    }
    
    if (funcResults.rate < 30) {
      report.critical_issues.push('Core functionality is non-operational');
      report.recommendations.push('Review and fix core feature implementations');
    }
    
    if (this.testResults.errors.length > 10) {
      report.critical_issues.push(`High error rate: ${this.testResults.errors.length} errors detected`);
      report.recommendations.push('Address console and network errors');
    }
    
    // Save report
    const reportPath = '/tmp/comprehensive_system_test_report.json';
    fs.writeFileSync(reportPath, JSON.stringify(report, null, 2));
    
    console.log('\n=== COMPREHENSIVE SYSTEM TEST RESULTS ===');
    console.log(`Overall Score: ${report.test_summary.overall_score}%`);
    console.log(`Tests Passed: ${report.test_summary.tests_passed}/${report.test_summary.total_tests}`);
    console.log(`Critical Issues: ${report.critical_issues.length}`);
    console.log(`Errors Detected: ${this.testResults.errors.length}`);
    
    if (report.critical_issues.length > 0) {
      console.log('\n🚨 CRITICAL ISSUES:');
      report.critical_issues.forEach(issue => console.log(`  - ${issue}`));
    }
    
    if (report.recommendations.length > 0) {
      console.log('\n💡 RECOMMENDATIONS:');
      report.recommendations.forEach(rec => console.log(`  - ${rec}`));
    }
    
    console.log(`\n📄 Detailed report saved to: ${reportPath}`);
    
    return report;
  }

  async cleanup() {
    if (this.browser) {
      await this.browser.close();
    }
  }
}

async function main() {
  const tester = new SystemTester();
  
  try {
    await tester.initialize();
    await tester.testBackendConnectivity();
    await tester.testNavigation();
    await tester.testDataIntegrity();
    await tester.testSpecificFeatures();
    const report = await tester.generateReport();
    
    // Return exit code based on results
    process.exit(report.test_summary.overall_score > 70 ? 0 : 1);
    
  } catch (error) {
    console.error('Test execution failed:', error);
    process.exit(1);
  } finally {
    await tester.cleanup();
  }
}

main().catch(console.error);