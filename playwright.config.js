const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests',
  testMatch: /.*\.spec\.js/,
  globalSetup: require.resolve('./scripts/preflight.js'),
});
