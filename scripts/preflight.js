const fs = require('fs');
const fsp = require('fs/promises');
const path = require('path');
const { spawn } = require('child_process');

async function waitForBackend(urls, timeoutMs = 30000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const candidates = Array.isArray(urls) ? urls : [urls];
      for (const url of candidates) {
        const ctrl = new AbortController();
        const to = setTimeout(() => ctrl.abort(), 5000);
        try {
          const res = await fetch(url, { signal: ctrl.signal });
          clearTimeout(to);
          if (res.ok) return true;
        } catch (_) {
          clearTimeout(to);
        }
      }
    } catch (_) {}
    await new Promise((r) => setTimeout(r, 500));
  }
  return false;
}

module.exports = async () => {
  const requiredModules = [
    'aria-query',
  ];
  const missing = [];

  for (const mod of requiredModules) {
    try {
      require.resolve(mod);
    } catch (err) {
      missing.push(mod);
    }
  }

  try {
    const vitePkg = require.resolve('vite/package.json');
    const viteCli = path.join(path.dirname(vitePkg), 'dist', 'node', 'cli.js');
    if (!fs.existsSync(viteCli)) {
      missing.push('vite/dist/node/cli.js');
    }
  } catch (err) {
    missing.push('vite/dist/node/cli.js');
  }

  try {
    const { chromium } = require('playwright');
    const execPath = chromium.executablePath();
    if (!fs.existsSync(execPath)) {
      missing.push('Chromium binary');
    }
  } catch (err) {
    missing.push('playwright/chromium');
  }

  // Ensure backend is running for API tests
  const repoRoot = path.resolve(__dirname, '..');
  const backendBaseUrl = process.env.BACKEND_URL
    ? process.env.BACKEND_URL.replace(/\/?$/, '')
    : 'http://127.0.0.1:8000';
  const backendHealthUrls = [
    `${backendBaseUrl}/api/health`,
    `${backendBaseUrl.replace('127.0.0.1', 'localhost')}/api/health`
  ];

  let backendStarted = false;
  try {
  const healthy = await waitForBackend(backendHealthUrls, 8000);
    if (!healthy) {
      // Start backend using project venv and uvicorn
      const cmd = 'bash';
      const startCmd = [
        'mkdir -p test-results',
        'source godelos_venv/bin/activate',
        // Replace the shell with uvicorn; redirect logs to file
        'exec python -m uvicorn backend.unified_server:app --port 8000 > test-results/backend.log 2>&1'
      ].join(' && ');
      const args = ['-lc', startCmd];
      const child = spawn(cmd, args, {
        cwd: repoRoot,
        detached: true,
        stdio: 'ignore'
      });
      // Detach so Node can proceed while server runs; record PID
      child.unref();
      backendStarted = true;
      const pidFile = path.join(repoRoot, 'test-results', 'backend.pid');
      try { await fsp.mkdir(path.dirname(pidFile), { recursive: true }); } catch {}
      await fsp.writeFile(pidFile, String(child.pid), 'utf8');

      // Wait until healthy
      const ready = await waitForBackend(backendHealthUrls, 90000);
      if (!ready) {
        missing.push('Backend server (failed to start within 60s). See test-results/backend.log');
      }
    }
  } catch (err) {
    missing.push(`Backend check error: ${err.message}`);
  }

  if (missing.length) {
    const message = `Missing dependencies:\n - ${missing.join('\n - ')}`;
    console.error(`\u274c ${message}`);
    throw new Error(message);
  }

  console.log('\u2705 Pre-flight checks passed');
  if (backendStarted) {
    console.log('\u2705 Backend started for tests');
  }
  process.env.PREFLIGHT_OK = 'true';
};
