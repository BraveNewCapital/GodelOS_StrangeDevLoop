<script>
import { onMount } from 'svelte';
let metrics = [];
let transitions = [];

onMount(async () => {
  const response = await fetch('http://localhost:8001/api/metrics/demo');
  if (response.ok) {
    const data = await response.json();
    metrics = data.metrics;
    transitions = data.transitions;
  }
});
</script>

<div class="dashboard">
  <h1>Consciousness Detection Dashboard</h1>
  <div class="timeline">
    {#each metrics as m, i}
      <div class="metric" title="C_n: Consciousness score from sigmoid of integrated info and surprise (Section 2.1).">
        Level {i}: C_n = {m.c_n.toFixed(2)}, Φ_n = {m.phi_n.toFixed(2)}
      </div>
    {/each}
  </div>
  {#if transitions.length > 0}
    <div title="Phase transition detected via KS test p < 0.01 (Section 2.5).">
      Transitions at levels: {transitions.join(', ')}
    </div>
  {/if>
  <p title="Metrics grounded in GödelOS whitepaper; P_n from irreducible surprise via AIC-filtered predictions (H5).">
    Theoretical justification for each metric is provided in tooltips.
  </p>
</div>

<style>
  .dashboard {
    font-family: Arial, sans-serif;
    max-width: 800px;
    margin: 0 auto;
    padding: 20px;
  }
  .metric {
    background: #f0f8ff;
    margin: 10px 0;
    padding: 10px;
    border-left: 4px solid #2196F3;
  }
</style>