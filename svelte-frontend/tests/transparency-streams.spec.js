import { test, expect } from '@playwright/test';

// Mock data for API responses
const MOCK_STATS = {
  status: 'Active',
  transparency_level: 'Detailed',
  total_sessions: 1,
  active_sessions: 1,
};

const MOCK_SESSIONS = {
  active_sessions: [
    {
      session_id: 'session-1',
      query: 'Test session',
      transparency_level: 'detailed',
      start_time: Date.now(),
    },
  ],
};

const MOCK_TRACE = {
  session_id: 'session-1',
  steps: [
    { id: 1, message: 'Initial reasoning step' },
  ],
};

// BDD style tests for transparency streams with emoji output

test.describe('Transparency Streams', () => {
  test.beforeEach(async ({ page }) => {
    // Intercept API calls and return mock data
    await page.route('**/api/transparency/**', (route) => {
      const url = route.request().url();
      if (url.endsWith('/statistics')) {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_STATS) });
      } else if (url.endsWith('/sessions/active')) {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_SESSIONS) });
      } else if (/\/session\/[^/]+\/trace$/.test(url)) {
        route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(MOCK_TRACE) });
      } else {
        route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
      }
    });
  });

  test('Dashboard connects to streams', async ({ page }) => {
    await test.step('Given the app is loaded 🏁', async () => {
      await page.goto('/');
    });

    await test.step('When the user opens the transparency dashboard 🔍', async () => {
      await page.click('[data-testid="nav-item-transparency"]');
      await page.waitForSelector('.activity-feed');
    });

    await test.step('Then real-time activity is visible 🛰️', async () => {
      await expect(page.locator('.activity-feed')).toBeVisible();
    });

    console.log('🎉 Transparency dashboard stream test completed');
  });

  test('Reasoning session viewer connects to stream', async ({ page }) => {
    await test.step('Given the app is loaded 🏁', async () => {
      await page.goto('/');
    });

    await test.step('When the user opens the reasoning session viewer 📡', async () => {
      await page.click('[data-testid="nav-item-reasoning"]');
      await page.waitForSelector('.reasoning-session-viewer');
    });

    await test.step('Then the viewer displays session list 📋', async () => {
      await expect(page.locator('.reasoning-session-viewer')).toBeVisible();
    });

    console.log('✅ Reasoning session viewer stream test completed');
  });
});
