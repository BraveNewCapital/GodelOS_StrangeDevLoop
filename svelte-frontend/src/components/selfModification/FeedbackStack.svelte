<script>
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { fly, fade } from 'svelte/transition';

  export let notifications = [];
  export let autoHideMs = 9000;

  const dispatch = createEventDispatcher();
  const timers = new Map();

  $: {
    if (!Array.isArray(notifications)) {
      timers.forEach((timer) => clearTimeout(timer));
      timers.clear();
    } else {
      notifications.forEach((note) => {
        if (!note?.id || timers.has(note.id) || !autoHideMs) return;
        const timer = setTimeout(() => dispatch('dismiss', { id: note.id }), autoHideMs);
        timers.set(note.id, timer);
      });

      timers.forEach((timer, id) => {
        if (!notifications.find((note) => note?.id === id)) {
          clearTimeout(timer);
          timers.delete(id);
        }
      });
    }
  }

  onDestroy(() => {
    timers.forEach((timer) => clearTimeout(timer));
    timers.clear();
  });

  const typeLabels = {
    success: 'Success',
    error: 'Error',
    warning: 'Warning',
    info: 'Update'
  };

  const typeIcons = {
    success: '✅',
    error: '⚠️',
    warning: '⚠️',
    info: 'ℹ️'
  };

  function dismiss(id) {
    if (!id) return;
    dispatch('dismiss', { id });
  }
</script>

<div class="feedback-stack" aria-live="polite">
  {#each notifications as note (note.id)}
    <article
      class={`feedback-card ${note.type || 'info'}`}
      role={note.type === 'error' ? 'alert' : 'status'}
      in:fly={{ y: 12, duration: 200 }}
      out:fade={{ duration: 160 }}
    >
      <header>
        <span class="icon">{typeIcons[note.type] || 'ℹ️'}</span>
        <div class="header-meta">
          <strong>{typeLabels[note.type] || 'Update'}</strong>
          {#if note.meta?.scope}
            <span class="scope">{note.meta.scope}</span>
          {/if}
        </div>
        <button class="dismiss" type="button" on:click={() => dismiss(note.id)} aria-label="Dismiss notification">
          ✕
        </button>
      </header>
      <p>{note.message}</p>
      <footer>
        <time>{new Date(note.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</time>
        {#if note.meta?.failures}
          <span class="meta">{note.meta.failures} issue{note.meta.failures > 1 ? 's' : ''}</span>
        {/if}
        {#if note.meta?.proposalId}
          <span class="meta">Proposal #{note.meta.proposalId}</span>
        {/if}
      </footer>
    </article>
  {/each}
</div>

<style>
  .feedback-stack {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    width: 320px;
    max-width: calc(100vw - 2rem);
  }

  .feedback-card {
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(94, 234, 212, 0.2);
    border-radius: 14px;
    padding: 0.9rem 1rem;
    box-shadow: 0 14px 34px rgba(2, 6, 23, 0.45);
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .feedback-card.success {
    border-color: rgba(34, 197, 94, 0.35);
  }

  .feedback-card.error {
    border-color: rgba(248, 113, 113, 0.35);
  }

  .feedback-card.warning {
    border-color: rgba(251, 191, 36, 0.35);
  }

  header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .icon {
    font-size: 1.2rem;
  }

  .header-meta {
    display: flex;
    flex-direction: column;
    gap: 0.1rem;
  }

  .scope {
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    opacity: 0.65;
  }

  .dismiss {
    margin-left: auto;
    background: transparent;
    border: none;
    color: rgba(226, 232, 240, 0.7);
    cursor: pointer;
    font-size: 1rem;
    line-height: 1;
    border-radius: 0.5rem;
    padding: 0.1rem 0.35rem;
  }

  .dismiss:hover {
    background: rgba(148, 163, 184, 0.15);
  }

  p {
    margin: 0;
    color: rgba(226, 232, 240, 0.85);
    font-size: 0.9rem;
  }

  footer {
    display: flex;
    gap: 0.5rem;
    font-size: 0.75rem;
    color: rgba(226, 232, 240, 0.55);
    flex-wrap: wrap;
  }

  .meta {
    background: rgba(59, 130, 246, 0.2);
    border-radius: 999px;
    padding: 0.1rem 0.45rem;
  }
</style>
