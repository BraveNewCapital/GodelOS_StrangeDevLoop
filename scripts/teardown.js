const fs = require('fs');
const path = require('path');

module.exports = async () => {
  try {
    const pidFile = path.resolve(__dirname, '..', 'test-results', 'backend.pid');
    if (fs.existsSync(pidFile)) {
      const pid = parseInt(fs.readFileSync(pidFile, 'utf8').trim(), 10);
      if (!Number.isNaN(pid)) {
        try {
          process.kill(pid);
          console.log(`\u2705 Stopped backend (pid ${pid})`);
        } catch (e) {
          // Process may have already exited
        }
      }
      try { fs.unlinkSync(pidFile); } catch {}
    }
  } catch (e) {
    // best-effort
  }
};
