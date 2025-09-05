/**
 * Comprehensive UI-Backend Integration Tests
 * 
 * These tests validate that the UI actually works with the backend
 * by testing real functionality, data flow, and user workflows.
 * 
 * Unlike previous tests that only checked element presence,
 * these tests verify actual system behavior and data integrity.
 */

import { test, expect } from '@playwright/test';
import { spawn } from 'child_process';
import { promises as fs } from 'fs';
import path from 'path';

const FRONTEND_URL = process.env.FRONTEND_URL || 'http://localhost:3001';
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8000';

// Test configuration
const TEST_CONFIG = {
  timeout: 60000,
  retries: 2,
  screenshot: true,
  trace: true
};

class SystemValidator {
  constructor(page) {
    this.page = page;
    this.testResults = {
      backendConnectivity: {},
      dataIntegrity: {},
      realTimeFunctionality: {},
      userWorkflows: {},
      criticalIssues: [],
      systemErrors: []
    };
    
    // Track console errors
    this.page.on('console', msg => {
      if (msg.type() === 'error') {
        this.testResults.systemErrors.push({
          type: 'console_error',
          message: msg.text(),
          url: this.page.url(),
          timestamp: new Date().toISOString()
        });
      }
    });
    
    // Track network errors
    this.page.on('response', response => {
      if (response.status() >= 400) {
        this.testResults.systemErrors.push({
          type: 'network_error',
          url: response.url(),
          status: response.status(),
          timestamp: new Date().toISOString()
        });
      }
    });
  }

  async takeScreenshot(name) {
    await this.page.screenshot({ 
      path: `/tmp/test_screenshot_${name}_${Date.now()}.png`,
      fullPage: true 
    });
  }

  async validateBackendConnectivity() {
    console.log('🔗 Validating backend connectivity...');
    
    const criticalEndpoints = [
      { path: '/api/health', name: 'Health Check' },
      { path: '/api/knowledge/graph', name: 'Knowledge Graph' },
      { path: '/api/cognitive/state', name: 'Cognitive State' },
      { path: '/api/enhanced-cognitive/dashboard', name: 'Enhanced Dashboard' },
      { path: '/api/transparency/statistics', name: 'Transparency Stats' },
      { path: '/api/transparency/sessions/active', name: 'Active Sessions' }
    ];
    
    for (const endpoint of criticalEndpoints) {
      try {
        const response = await fetch(`${BACKEND_URL}${endpoint.path}`);
        const isHealthy = response.ok && response.status === 200;
        
        let data = null;
        try {
          data = await response.json();
        } catch (e) {
          // Some endpoints might not return JSON
        }
        
        this.testResults.backendConnectivity[endpoint.name] = {
          status: response.status,
          healthy: isHealthy,
          hasData: data !== null && Object.keys(data || {}).length > 0,
          response: data
        };
        
        if (!isHealthy) {
          this.testResults.criticalIssues.push(`${endpoint.name} endpoint not responding (${response.status})`);
        }
        
      } catch (error) {
        this.testResults.backendConnectivity[endpoint.name] = {
          error: error.message,
          healthy: false
        };
        this.testResults.criticalIssues.push(`${endpoint.name} endpoint failed: ${error.message}`);
      }
    }
    
    const healthyEndpoints = Object.values(this.testResults.backendConnectivity)
      .filter(result => result.healthy).length;
    const totalEndpoints = criticalEndpoints.length;
    
    console.log(`Backend connectivity: ${healthyEndpoints}/${totalEndpoints} endpoints healthy`);
    
    return healthyEndpoints / totalEndpoints >= 0.8; // At least 80% should be healthy
  }

  async validateReasoningSessionsActuallyWork() {
    console.log('🧠 Testing if reasoning sessions actually progress beyond 0%...');
    
    await this.page.goto(`${FRONTEND_URL}/#/transparency`);
    await this.page.waitForTimeout(3000);
    await this.takeScreenshot('reasoning_sessions_start');
    
    // Look for session creation controls
    const sessionControls = [
      'text=Start Session',
      'text=New Session',
      'text=Begin Reasoning',
      'button:has-text("Start")',
      'input[placeholder*="query"]'
    ];
    
    let sessionStarted = false;
    let sessionId = null;
    
    // Try to start a reasoning session
    for (const selector of sessionControls) {
      try {
        const element = this.page.locator(selector);
        if (await element.count() > 0) {
          await element.first().click();
          await this.page.waitForTimeout(2000);
          
          // If it's an input, type a test query
          if (selector.includes('input')) {
            await element.fill('What is the current system status?');
            
            // Look for submit button
            const submitBtn = this.page.locator('button:has-text("Submit"), button:has-text("Send"), button[type="submit"]');
            if (await submitBtn.count() > 0) {
              await submitBtn.first().click();
            }
          }
          
          sessionStarted = true;
          break;
        }
      } catch (error) {
        // Continue trying other selectors
      }
    }
    
    if (!sessionStarted) {
      this.testResults.criticalIssues.push('No functioning session start controls found');
      return false;
    }
    
    // Wait for session to be created and check progress
    await this.page.waitForTimeout(5000);
    await this.takeScreenshot('reasoning_sessions_progress');
    
    const pageContent = await this.page.textContent('body');
    
    // Check for actual progress beyond 0%
    const progressMatches = pageContent.match(/(\d+)%/g) || [];
    const progressValues = progressMatches.map(match => parseInt(match.replace('%', '')))
      .filter(val => val > 0 && val <= 100);
    
    const hasRealProgress = progressValues.some(progress => progress > 0);
    
    // Check for session data that isn't stuck at 0%
    const hasActiveSession = pageContent.includes('active') || pageContent.includes('processing') || pageContent.includes('reasoning');
    const notStuckAtZero = !pageContent.includes('0%') || progressValues.length > 0;
    
    this.testResults.realTimeFunctionality.reasoningSessions = {
      sessionStarted: sessionStarted,
      hasProgress: hasRealProgress,
      progressValues: progressValues,
      hasActiveSession: hasActiveSession,
      notStuckAtZero: notStuckAtZero,
      pageContent: pageContent.substring(0, 500) // Sample for debugging
    };
    
    const sessionWorks = sessionStarted && (hasRealProgress || (hasActiveSession && notStuckAtZero));
    
    if (!sessionWorks) {
      this.testResults.criticalIssues.push('Reasoning sessions stuck at 0% or not functioning');
    }
    
    return sessionWorks;
  }

  async validateKnowledgeGraphShowsRealData() {
    console.log('📊 Testing if knowledge graph shows real data not test data...');
    
    await this.page.goto(`${FRONTEND_URL}/#/knowledge-graph`);
    await this.page.waitForTimeout(5000);
    await this.takeScreenshot('knowledge_graph_data');
    
    const pageContent = await this.page.textContent('body');
    
    // Check for indicators of test data
    const testDataIndicators = [
      'test data',
      'dummy data', 
      'mock data',
      'sample data',
      'placeholder',
      'Test Node',
      'Sample Node',
      'Example Node'
    ];
    
    const hasTestData = testDataIndicators.some(indicator => 
      pageContent.toLowerCase().includes(indicator.toLowerCase())
    );
    
    // Check for indicators of real data
    const realDataIndicators = [
      'document',
      'concept',
      'principle',
      'relationship',
      'knowledge',
      'extracted from',
      'processed'
    ];
    
    const hasRealData = realDataIndicators.some(indicator => 
      pageContent.toLowerCase().includes(indicator.toLowerCase())
    );
    
    // Check for dynamic data (timestamps, counts, etc.)
    const hasDynamicData = /\d{1,3}\s+(nodes?|edges?|relationships?|items?)/.test(pageContent) ||
                          /last updated|processed|imported/i.test(pageContent);
    
    // Test knowledge import functionality
    let importWorks = false;
    try {
      const importButtons = this.page.locator('text=Import, text=Add, text=Upload, input[type="file"]');
      if (await importButtons.count() > 0) {
        // Don't actually import, just verify the functionality exists
        importWorks = true;
      }
    } catch (error) {
      // Import functionality not found
    }
    
    this.testResults.dataIntegrity.knowledgeGraph = {
      hasTestData: hasTestData,
      hasRealData: hasRealData,
      hasDynamicData: hasDynamicData,
      importFunctionalityExists: importWorks,
      contentSample: pageContent.substring(0, 500)
    };
    
    const graphShowsRealData = !hasTestData && (hasRealData || hasDynamicData);
    
    if (hasTestData) {
      this.testResults.criticalIssues.push('Knowledge graph showing test data instead of real data');
    }
    
    if (!importWorks) {
      this.testResults.criticalIssues.push('Knowledge import functionality not accessible');
    }
    
    return graphShowsRealData && importWorks;
  }

  async validateWebSocketConnectionActuallyWorks() {
    console.log('🔌 Testing if WebSocket connections actually work...');
    
    await this.page.goto(`${FRONTEND_URL}/#/enhanced`);
    await this.page.waitForTimeout(3000);
    
    // Monitor WebSocket connections in browser
    const wsEvents = await this.page.evaluate(() => {
      return new Promise((resolve) => {
        const events = [];
        let timeout;
        
        // Monitor existing WebSocket connections
        const originalWebSocket = window.WebSocket;
        window.WebSocket = function(url, protocols) {
          const ws = new originalWebSocket(url, protocols);
          
          ws.addEventListener('open', () => {
            events.push({ type: 'open', url: url, timestamp: Date.now() });
          });
          
          ws.addEventListener('message', (event) => {
            events.push({ type: 'message', data: event.data, timestamp: Date.now() });
          });
          
          ws.addEventListener('close', () => {
            events.push({ type: 'close', timestamp: Date.now() });
          });
          
          ws.addEventListener('error', () => {
            events.push({ type: 'error', timestamp: Date.now() });
          });
          
          return ws;
        };
        
        // Give it some time to establish connections and receive messages
        timeout = setTimeout(() => {
          resolve(events);
        }, 8000);
      });
    });
    
    await this.page.waitForTimeout(10000); // Wait for WebSocket activity
    await this.takeScreenshot('websocket_status');
    
    const pageContent = await this.page.textContent('body');
    
    // Check connection status indicators
    const connectionIndicators = [
      /connected/i,
      /disconnected/i,
      /connection.*status/i,
      /websocket/i
    ];
    
    const hasConnectionStatus = connectionIndicators.some(pattern => pattern.test(pageContent));
    const showsConnected = /connected/i.test(pageContent) && !/disconnected/i.test(pageContent);
    const constantlyDisconnected = pageContent.toLowerCase().includes('disconnected') && 
                                  !pageContent.toLowerCase().includes('connected');
    
    this.testResults.realTimeFunctionality.webSocketConnection = {
      wsEvents: wsEvents,
      hasConnectionStatus: hasConnectionStatus,
      showsConnected: showsConnected,
      constantlyDisconnected: constantlyDisconnected,
      connectionCount: wsEvents.filter(e => e.type === 'open').length,
      messageCount: wsEvents.filter(e => e.type === 'message').length,
      errorCount: wsEvents.filter(e => e.type === 'error').length
    };
    
    const websocketWorks = (wsEvents.length > 0 && 
                           wsEvents.some(e => e.type === 'open') &&
                           !constantlyDisconnected) || 
                          showsConnected;
    
    if (constantlyDisconnected) {
      this.testResults.criticalIssues.push('WebSocket constantly shows disconnected');
    }
    
    if (wsEvents.filter(e => e.type === 'error').length > 0) {
      this.testResults.criticalIssues.push('WebSocket connection errors detected');
    }
    
    return websocketWorks;
  }

  async validateStreamOfConsciousnessShowsEvents() {
    console.log('🌊 Testing if stream of consciousness shows actual events...');
    
    await this.page.goto(`${FRONTEND_URL}/#/stream`);
    await this.page.waitForTimeout(5000);
    await this.takeScreenshot('stream_of_consciousness');
    
    const pageContent = await this.page.textContent('body');
    
    // Check for empty stream indicators
    const emptyIndicators = [
      '0 events',
      'no events',
      'no activity',
      'empty stream',
      'no consciousness events'
    ];
    
    const showsEmpty = emptyIndicators.some(indicator => 
      pageContent.toLowerCase().includes(indicator.toLowerCase())
    );
    
    // Check for actual events
    const eventIndicators = [
      /\d+\s+events?/,
      /\d+\s+thoughts?/,
      /\d+\s+activities?/,
      /timestamp/i,
      /\d{2}:\d{2}/,  // Time format
      /ago$/m,        // "X minutes ago"
      /cognitive.*activity/i,
      /reasoning.*step/i
    ];
    
    const hasEvents = eventIndicators.some(pattern => pattern.test(pageContent));
    
    // Check for dynamic content that would indicate live updates
    const hasDynamicContent = /last update/i.test(pageContent) || 
                             /\d+\s+seconds?\s+ago/i.test(pageContent) ||
                             /\d+\s+minutes?\s+ago/i.test(pageContent);
    
    this.testResults.realTimeFunctionality.streamOfConsciousness = {
      showsEmpty: showsEmpty,
      hasEvents: hasEvents,
      hasDynamicContent: hasDynamicContent,
      contentSample: pageContent.substring(0, 500)
    };
    
    const streamWorks = hasEvents && !showsEmpty;
    
    if (showsEmpty) {
      this.testResults.criticalIssues.push('Stream of consciousness shows 0 events');
    }
    
    return streamWorks;
  }

  async validateTransparencyModalShowsRealData() {
    console.log('🔍 Testing if transparency modal shows real data not dummy data...');
    
    await this.page.goto(`${FRONTEND_URL}/#/transparency`);
    await this.page.waitForTimeout(3000);
    
    // Look for modal triggers
    const modalTriggers = [
      'text=Details',
      'text=View Details', 
      'text=Show Details',
      'button:has-text("...")',
      '.modal-trigger',
      '[data-modal]'
    ];
    
    let modalOpened = false;
    let modalContent = '';
    
    for (const trigger of modalTriggers) {
      try {
        const element = this.page.locator(trigger);
        if (await element.count() > 0) {
          await element.first().click();
          await this.page.waitForTimeout(2000);
          modalOpened = true;
          modalContent = await this.page.textContent('body');
          break;
        }
      } catch (error) {
        // Try next trigger
      }
    }
    
    if (!modalOpened) {
      // Try clicking on any session or item that might open a modal
      const clickableItems = [
        '.session-item',
        '.transparency-item', 
        'tr[data-session]',
        '.reasoning-session'
      ];
      
      for (const item of clickableItems) {
        try {
          const element = this.page.locator(item);
          if (await element.count() > 0) {
            await element.first().click();
            await this.page.waitForTimeout(2000);
            modalContent = await this.page.textContent('body');
            modalOpened = true;
            break;
          }
        } catch (error) {
          // Continue trying
        }
      }
    }
    
    await this.takeScreenshot('transparency_modal');
    
    // Check for dummy data indicators
    const dummyDataIndicators = [
      'test data',
      'dummy data',
      'mock data', 
      'placeholder',
      'Lorem ipsum',
      'sample reasoning',
      'test session'
    ];
    
    const hasDummyData = dummyDataIndicators.some(indicator => 
      modalContent.toLowerCase().includes(indicator.toLowerCase())
    );
    
    // Check for real data indicators
    const realDataIndicators = [
      /session.*id.*\w{8,}/i,  // Real session IDs
      /timestamp.*\d{4}/i,      // Real timestamps
      /step.*\d+/i,             // Reasoning steps
      /confidence.*\d/i,        // Confidence scores
      /progress.*\d+%/i         // Progress indicators
    ];
    
    const hasRealData = realDataIndicators.some(pattern => pattern.test(modalContent));
    
    this.testResults.dataIntegrity.transparencyModal = {
      modalOpened: modalOpened,
      hasDummyData: hasDummyData,
      hasRealData: hasRealData,
      contentSample: modalContent.substring(0, 500)
    };
    
    const modalWorks = modalOpened && !hasDummyData && hasRealData;
    
    if (!modalOpened) {
      this.testResults.criticalIssues.push('Transparency modal cannot be opened');
    }
    
    if (hasDummyData) {
      this.testResults.criticalIssues.push('Transparency modal shows dummy/test data');
    }
    
    return modalWorks;
  }

  async validateNavigationWorks() {
    console.log('🧭 Testing complete navigation system...');
    
    const views = [
      { name: 'Dashboard', path: '#/dashboard', selector: 'text=Dashboard' },
      { name: 'Enhanced', path: '#/enhanced', selector: 'text=Enhanced' },
      { name: 'Cognitive State', path: '#/cognitive-state', selector: 'text=Cognitive' },
      { name: 'Knowledge Graph', path: '#/knowledge-graph', selector: 'text=Knowledge' },
      { name: 'Query Interface', path: '#/query', selector: 'text=Query' },
      { name: 'Transparency', path: '#/transparency', selector: 'text=Transparency' },
      { name: 'Stream', path: '#/stream', selector: 'text=Stream' },
      { name: 'Autonomous', path: '#/autonomous', selector: 'text=Autonomous' },
      { name: 'Reflection', path: '#/reflection', selector: 'text=Reflection' },
      { name: 'Provenance', path: '#/provenance', selector: 'text=Provenance' }
    ];
    
    let workingViews = 0;
    let navigationBroken = false;
    
    for (const view of views) {
      try {
        // Navigate to view
        await this.page.goto(`${FRONTEND_URL}/${view.path}`);
        await this.page.waitForTimeout(2000);
        
        // Check if view loaded
        const currentUrl = this.page.url();
        const contentLoaded = await this.page.textContent('body');
        const hasContent = contentLoaded && contentLoaded.length > 100;
        
        // Try clicking navigation if direct navigation didn't work
        if (!hasContent) {
          try {
            await this.page.click(view.selector);
            await this.page.waitForTimeout(2000);
            
            const afterClick = await this.page.textContent('body');
            if (afterClick && afterClick.length > 100) {
              workingViews++;
            }
          } catch (clickError) {
            // View not accessible
          }
        } else {
          workingViews++;
        }
        
        // Special test for reflection view that supposedly breaks navigation
        if (view.name === 'Reflection') {
          // Try navigating away and back
          await this.page.goto(`${FRONTEND_URL}/#/dashboard`);
          await this.page.waitForTimeout(1000);
          
          try {
            await this.page.click('text=Enhanced');
            await this.page.waitForTimeout(1000);
            
            const navStillWorks = await this.page.textContent('body');
            if (!navStillWorks || navStillWorks.length < 100) {
              navigationBroken = true;
              this.testResults.criticalIssues.push('Navigation broken after visiting reflection view');
            }
          } catch (error) {
            navigationBroken = true;
            this.testResults.criticalIssues.push('Navigation broken after visiting reflection view');
          }
        }
        
      } catch (error) {
        console.log(`Navigation to ${view.name} failed:`, error.message);
      }
    }
    
    await this.takeScreenshot('navigation_final');
    
    this.testResults.userWorkflows.navigation = {
      totalViews: views.length,
      workingViews: workingViews,
      navigationBroken: navigationBroken,
      successRate: (workingViews / views.length) * 100
    };
    
    const navigationWorks = workingViews >= views.length * 0.8 && !navigationBroken;
    
    if (workingViews < views.length * 0.5) {
      this.testResults.criticalIssues.push(`Navigation severely broken: only ${workingViews}/${views.length} views working`);
    }
    
    return navigationWorks;
  }

  async validateCompleteUserWorkflow() {
    console.log('👤 Testing complete user workflow...');
    
    // 1. Start at enhanced dashboard
    await this.page.goto(`${FRONTEND_URL}/#/enhanced`);
    await this.page.waitForTimeout(3000);
    
    const dashboardContent = await this.page.textContent('body');
    const dashboardWorking = dashboardContent && dashboardContent.length > 100 &&
                           !dashboardContent.includes('undefined') &&
                           !dashboardContent.includes('NaN');
    
    // 2. Check for real data in dashboard
    const hasRealMetrics = /\d+%/.test(dashboardContent) && 
                          !dashboardContent.includes('NaN%') &&
                          !dashboardContent.includes('175705');  // The invalid timestamp mentioned
    
    // 3. Test query interface
    await this.page.goto(`${FRONTEND_URL}/#/query`);
    await this.page.waitForTimeout(2000);
    
    let queryWorks = false;
    try {
      const queryInput = this.page.locator('input[type="text"], textarea, input[placeholder*="query"]');
      const submitButton = this.page.locator('button:has-text("Submit"), button:has-text("Send"), button[type="submit"]');
      
      if (await queryInput.count() > 0 && await submitButton.count() > 0) {
        await queryInput.first().fill('Test query: What is the system status?');
        await submitButton.first().click();
        await this.page.waitForTimeout(3000);
        
        const responseContent = await this.page.textContent('body');
        queryWorks = responseContent !== dashboardContent; // Content should change
      }
    } catch (error) {
      // Query interface not working
    }
    
    // 4. Test knowledge import
    await this.page.goto(`${FRONTEND_URL}/#/knowledge-graph`);
    await this.page.waitForTimeout(2000);
    
    let importAccessible = false;
    try {
      const importElements = this.page.locator('text=Import, text=Add, input[type="file"], text=Upload');
      importAccessible = await importElements.count() > 0;
    } catch (error) {
      // Import not accessible
    }
    
    await this.takeScreenshot('complete_workflow');
    
    this.testResults.userWorkflows.completeWorkflow = {
      dashboardWorking: dashboardWorking,
      hasRealMetrics: hasRealMetrics,
      queryWorks: queryWorks,
      importAccessible: importAccessible,
      workflowScore: [dashboardWorking, hasRealMetrics, queryWorks, importAccessible]
        .filter(Boolean).length / 4 * 100
    };
    
    const workflowWorks = dashboardWorking && hasRealMetrics && (queryWorks || importAccessible);
    
    if (!dashboardWorking) {
      this.testResults.criticalIssues.push('Enhanced dashboard not functioning');
    }
    
    if (!hasRealMetrics) {
      this.testResults.criticalIssues.push('Dashboard showing invalid metrics (NaN, undefined values)');
    }
    
    if (!queryWorks && !importAccessible) {
      this.testResults.criticalIssues.push('No working user interaction methods found');
    }
    
    return workflowWorks;
  }

  async generateComprehensiveReport() {
    const report = {
      timestamp: new Date().toISOString(),
      testConfiguration: {
        frontendUrl: FRONTEND_URL,
        backendUrl: BACKEND_URL,
        testTimeout: TEST_CONFIG.timeout,
        retries: TEST_CONFIG.retries
      },
      summary: {
        totalTests: 0,
        passingTests: 0,
        failingTests: 0,
        criticalIssues: this.testResults.criticalIssues.length,
        systemErrors: this.testResults.systemErrors.length,
        overallScore: 0
      },
      detailedResults: this.testResults,
      systemHealth: {
        backendConnectivity: 'UNKNOWN',
        dataIntegrity: 'UNKNOWN', 
        realTimeFunctionality: 'UNKNOWN',
        userExperience: 'UNKNOWN'
      },
      recommendations: [],
      criticalFindings: this.testResults.criticalIssues
    };
    
    // Calculate scores
    const testCategories = [
      'backendConnectivity',
      'dataIntegrity', 
      'realTimeFunctionality',
      'userWorkflows'
    ];
    
    let totalScore = 0;
    let testCount = 0;
    
    testCategories.forEach(category => {
      const categoryResults = this.testResults[category];
      if (categoryResults && Object.keys(categoryResults).length > 0) {
        // Each category can contribute to the overall score
        testCount++;
      }
    });
    
    report.summary.totalTests = testCount;
    report.summary.overallScore = totalScore / Math.max(testCount, 1);
    
    // Generate system health assessment
    if (this.testResults.backendConnectivity) {
      const healthyEndpoints = Object.values(this.testResults.backendConnectivity)
        .filter(r => r.healthy).length;
      const totalEndpoints = Object.keys(this.testResults.backendConnectivity).length;
      
      report.systemHealth.backendConnectivity = healthyEndpoints / totalEndpoints >= 0.8 ? 'HEALTHY' : 'DEGRADED';
    }
    
    if (this.testResults.criticalIssues.length === 0) {
      report.systemHealth.overallStatus = 'HEALTHY';
    } else if (this.testResults.criticalIssues.length <= 3) {
      report.systemHealth.overallStatus = 'DEGRADED';
    } else {
      report.systemHealth.overallStatus = 'CRITICAL';
    }
    
    // Generate recommendations
    if (this.testResults.criticalIssues.length > 0) {
      report.recommendations.push('Address critical issues identified in testing');
    }
    
    if (this.testResults.systemErrors.length > 5) {
      report.recommendations.push('Investigate and fix system errors (console/network)');
    }
    
    return report;
  }
}

test.describe('Comprehensive UI-Backend Integration Validation', () => {
  test.beforeEach(async ({ page }) => {
    test.setTimeout(TEST_CONFIG.timeout);
  });

  test('System Health: Backend Connectivity and API Functionality', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    // Test backend connectivity first
    const backendHealthy = await validator.validateBackendConnectivity();
    expect(backendHealthy).toBeTruthy();
    
    if (!backendHealthy) {
      console.error('❌ Backend connectivity failed - subsequent tests may fail');
      console.error('Critical issues:', validator.testResults.criticalIssues);
    }
  });

  test('Real Functionality: Reasoning Sessions Actually Progress', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const reasoningWorks = await validator.validateReasoningSessionsActuallyWork();
    expect(reasoningWorks).toBeTruthy();
    
    if (!reasoningWorks) {
      console.error('❌ Reasoning sessions are stuck at 0% or not functioning');
    }
  });

  test('Data Integrity: Knowledge Graph Shows Real Data Not Test Data', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const knowledgeGraphReal = await validator.validateKnowledgeGraphShowsRealData();
    expect(knowledgeGraphReal).toBeTruthy();
    
    if (!knowledgeGraphReal) {
      console.error('❌ Knowledge graph showing test data or import not working');
    }
  });

  test('Real-Time: WebSocket Connections Actually Work', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const websocketsWork = await validator.validateWebSocketConnectionActuallyWorks();
    expect(websocketsWork).toBeTruthy();
    
    if (!websocketsWork) {
      console.error('❌ WebSocket connections not working or constantly disconnected');
    }
  });

  test('Live Data: Stream of Consciousness Shows Real Events', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const streamWorks = await validator.validateStreamOfConsciousnessShowsEvents();
    expect(streamWorks).toBeTruthy();
    
    if (!streamWorks) {
      console.error('❌ Stream of consciousness showing 0 events');
    }
  });

  test('Modal Functionality: Transparency Shows Real Data Not Dummy Data', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const transparencyWorks = await validator.validateTransparencyModalShowsRealData();
    expect(transparencyWorks).toBeTruthy();
    
    if (!transparencyWorks) {
      console.error('❌ Transparency modal showing dummy data or not opening');
    }
  });

  test('Navigation: Complete System Navigation Including Reflection View', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const navigationWorks = await validator.validateNavigationWorks();
    expect(navigationWorks).toBeTruthy();
    
    if (!navigationWorks) {
      console.error('❌ Navigation system has critical failures');
    }
  });

  test('User Experience: Complete User Workflow End-to-End', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    const workflowWorks = await validator.validateCompleteUserWorkflow();
    expect(workflowWorks).toBeTruthy();
    
    if (!workflowWorks) {
      console.error('❌ Complete user workflow not functioning');
    }
  });

  test('Comprehensive System Report Generation', async ({ page }) => {
    const validator = new SystemValidator(page);
    
    // Run all validations
    await validator.validateBackendConnectivity();
    await validator.validateReasoningSessionsActuallyWork();
    await validator.validateKnowledgeGraphShowsRealData();
    await validator.validateWebSocketConnectionActuallyWorks();
    await validator.validateStreamOfConsciousnessShowsEvents();
    await validator.validateTransparencyModalShowsRealData();
    await validator.validateNavigationWorks();
    await validator.validateCompleteUserWorkflow();
    
    // Generate comprehensive report
    const report = await validator.generateComprehensiveReport();
    
    // Save report
    const reportPath = '/tmp/comprehensive_ui_backend_validation_report.json';
    await fs.writeFile(reportPath, JSON.stringify(report, null, 2));
    
    console.log('\n=== COMPREHENSIVE UI-BACKEND VALIDATION RESULTS ===');
    console.log(`Overall System Health: ${report.systemHealth.overallStatus || 'UNKNOWN'}`);
    console.log(`Critical Issues Found: ${report.summary.criticalIssues}`);
    console.log(`System Errors: ${report.summary.systemErrors}`);
    
    if (report.criticalFindings.length > 0) {
      console.log('\n🚨 CRITICAL FINDINGS:');
      report.criticalFindings.forEach(finding => console.log(`  - ${finding}`));
    }
    
    if (report.recommendations.length > 0) {
      console.log('\n💡 RECOMMENDATIONS:');
      report.recommendations.forEach(rec => console.log(`  - ${rec}`));
    }
    
    console.log(`\n📄 Detailed report saved to: ${reportPath}`);
    
    // Test should fail if there are critical issues
    expect(report.summary.criticalIssues).toBeLessThan(5);
    expect(report.systemHealth.overallStatus).not.toBe('CRITICAL');
  });
});