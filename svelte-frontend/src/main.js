import App from './App.svelte'
import './theme/shadowgraph-dark.css'

// Theme initialization: respect stored preference or system
const rootEl = document.documentElement
const storedTheme = localStorage.getItem('sg-theme')
if (storedTheme) {
  rootEl.setAttribute('data-theme', storedTheme)
} else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
  rootEl.setAttribute('data-theme', 'dark')
} else {
  rootEl.setAttribute('data-theme', 'light')
}

const app = new App({
  target: document.getElementById('app'),
})

// Expose a global toggle helper (will be replaced by component later)
window.__toggleTheme = function() {
  const current = rootEl.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'
  rootEl.setAttribute('data-theme', current)
  localStorage.setItem('sg-theme', current)
  return current
}

export default app
