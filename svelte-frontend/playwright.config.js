import { defineConfig, devices } from '@playwright/test';
import { fileURLToPath } from 'url';

const globalSetupPath = fileURLToPath(new URL('../scripts/preflight.js', import.meta.url));
const globalTeardownPath = fileURLToPath(new URL('../scripts/teardown.js', import.meta.url));

export default defineConfig({
  testDir: './tests',
  testMatch: /.*\.spec\.js/,
  fullyParallel: false, // Run tests sequentially for better stability
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : 1,
  reporter: [
    ['html', { outputFolder: './test-results/html-report' }],
    ['json', { outputFile: './test-results/test-results.json' }],
    ['list']
  ],
  outputDir: './test-results/raw-output',
  // Start the frontend automatically for e2e runs.
  // Use preview (built assets) to avoid dev-only @vite/client and service worker noise.
  webServer: {
    command: 'npm run build && npm run preview -- --port 3001',
    url: process.env.FRONTEND_URL || 'http://localhost:3001',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
    stdout: 'pipe',
    stderr: 'pipe'
  },
  use: {
    baseURL: process.env.FRONTEND_URL || 'http://localhost:3001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    headless: process.env.PLAYWRIGHT_HEADLESS !== 'false',
    timeout: parseInt(process.env.PLAYWRIGHT_TEST_TIMEOUT) || 60000,
    serviceWorkers: 'block'
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    }
  ],
  globalSetup: globalSetupPath,
  globalTeardown: globalTeardownPath
});
