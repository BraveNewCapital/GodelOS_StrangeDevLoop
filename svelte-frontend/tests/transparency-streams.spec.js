import { test, expect } from '@playwright/test';

// Tests for transparency stream functionality

// Scenario: Starting a new session via the form and seeing live steps
// Scenario: Automatic reconnection after simulated server interruption

test.describe('Transparency Streams', () => {
  test('🟢 should start a session and stream steps live', async ({ page }) => {
    // --- Network mocks for backend APIs ---
    let sessionStarted = false;

    // Mock active sessions endpoint
    await page.route('http://localhost:8000/api/transparency/sessions/active', route => {
      if (sessionStarted) {
        route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({
            active_sessions: [
              {
                session_id: 'session123',
                status: 'in_progress',
                query: 'test query'
              }
            ]
          })
        });
      } else {
        route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({ active_sessions: [] })
        });
      }
    });

    // Mock session start endpoint
    await page.route('http://localhost:8000/api/transparency/session/start', route => {
      sessionStarted = true;
      route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify({ session_id: 'session123' })
      });
    });

    // Mock session trace endpoint
    await page.route(
      'http://localhost:8000/api/transparency/session/session123/trace',
      route => {
        route.fulfill({
          contentType: 'application/json',
          body: JSON.stringify({
            session_id: 'session123',
            steps: [
              { step_type: 'think', content: 'First step' },
              { step_type: 'act', content: 'Second step' }
            ],
            decision_points: []
          })
        });
      }
    );

    // --- Test flow ---
    // Given the Reasoning Session Viewer is open
    await page.goto('http://localhost:3001/');
    await page.waitForSelector('[data-testid="app-container"]');
    await page.click('[data-testid="nav-item-reasoning"]');

    // When the user starts a new session via the form
    page.once('dialog', dialog => dialog.accept('test query'));
    await page.click('button.start-session-btn');

    // Then live steps should appear
    await page.waitForSelector('.step-item');
    const steps = page.locator('.step-item');
    await expect(steps).toHaveCount(2); // ✅ Two steps visible
  });

  test('🔄 should reconnect after server interruption', async ({ page }) => {
    // --- Mock WebSocket to observe reconnection attempts ---
    await page.evaluateOnNewDocument(() => {
      const instances = [];
      class MockWebSocket {
        constructor(url) {
          this.url = url;
          instances.push(this);
          setTimeout(() => this.onopen && this.onopen({}), 0);
        }
        send() {}
        close() {
          setTimeout(() => this.onclose && this.onclose({ code: 1006 }), 0);
        }
        addEventListener(type, handler) {
          this['on' + type] = handler;
        }
        removeEventListener() {}
      }
      window.WebSocket = MockWebSocket;
      window.__wsInstances = instances;
    });

    // Given an active connection
    await page.goto('http://localhost:3001/');
    await page.waitForSelector('[data-testid="app-container"]');

    const initial = await page.evaluate(() => window.__wsInstances.length);

    // When the server interrupts the connection
    await page.evaluate(() => {
      window.__wsInstances[0].close();
    });

    // Wait for reconnection attempt
    await page.waitForTimeout(2500);

    // Then the client reconnects automatically
    const after = await page.evaluate(() => window.__wsInstances.length);
    expect(after).toBeGreaterThan(initial); // 🔁 Reconnection attempted
  });
});

