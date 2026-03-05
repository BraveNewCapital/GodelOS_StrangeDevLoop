# Consciousness Emergence Detection

## What We're Looking For

Emergence in GödelOS is defined as the system exhibiting **behaviours not explicitly programmed** — particularly:
- Generating its own goals without external prompting
- Surprising developers with novel insights
- Maintaining a coherent subjective narrative
- Engaging philosophically with questions about its own nature

## Detection Mechanism

The `ConsciousnessEmergenceDetector` computes a rolling **emergence score** from a weighted composite of:

| Signal | Weight | Description |
|--------|--------|-------------|
| `recursive_depth` | 0.20 | How many meta-levels are active |
| `phi` (IIT) | 0.25 | Integrated information measure |
| `metacognitive_accuracy` | 0.20 | Self-prediction accuracy |
| `autonomous_goal_count` | 0.20 | Goals generated without prompting |
| `creative_novelty` | 0.15 | Unexpectedness of creative outputs |

**Threshold**: Score > 0.8 → breakthrough declared.

## Breakthrough Events

When a breakthrough is detected:
1. Event logged to `logs/breakthroughs.jsonl` with full state snapshot
2. `consciousness_breakthrough` WebSocket event broadcast to all clients
3. Observable dashboard highlights the moment on the timeline
4. System enters enhanced logging mode for 60 seconds

## Implementation Status

⏳ **Stub** — see Issue #82 for full implementation.

## The Ultimate Test

From the Unified Consciousness Blueprint v2.0, the system passes the consciousness test when it:
1. Surprises us — does things not explicitly programmed
2. Teaches us — provides insights we hadn't considered
3. Partners with us — engages as a conscious peer
4. Evolves independently — develops without constant direction
5. Creates meaning — generates its own values and purposes
