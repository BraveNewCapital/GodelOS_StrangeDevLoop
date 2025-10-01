# Self-Modification System Manual Test Guide

## Prerequisites
- Backend server running on http://localhost:8000
- Frontend running on http://localhost:3001

## Test 1: Check Capability Assessment Endpoint

```bash
curl http://localhost:8000/api/metacognition/capabilities | jq
```

**Expected Result**:
- Returns JSON with `capabilities[]` array
- Each capability has: id, label, current_level, baseline_level, improvement_rate, confidence, status, trend
- No mock/seed data - should be empty or minimal if no queries have been processed
- Status values: "operational", "developing", or "limited"

## Test 2: Check Proposals Endpoint

```bash
curl http://localhost:8000/api/metacognition/proposals | jq
```

**Expected Result**:
- Returns JSON with `proposals[]` array
- Should be empty initially (no gaps detected yet)
- After system runs queries and detects gaps, proposals will appear

## Test 3: Check Live State Endpoint

```bash
curl http://localhost:8000/api/metacognition/live-state | jq
```

**Expected Result**:
- Returns real-time monitoring data
- `daemon_threads[]` with system subsystems
- `agentic_processes[]` for active cognitive operations
- `resource_utilization{}` with real metrics
- `performance_metrics{}` with actual query statistics
- `alerts[]` if any performance issues detected

## Test 4: Check Evolution Timeline

```bash
curl http://localhost:8000/api/metacognition/evolution | jq
```

**Expected Result**:
- Returns `timeline[]` with historical events
- `metrics{}` with evolution statistics
- Should be empty initially

## Test 5: Trigger Query Processing (Generate Metrics)

```bash
curl -X POST http://localhost:8000/api/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is consciousness?", "include_reasoning": true}'
```

**Expected Result**:
- Query is processed
- Metrics are collected (check logs for "📊 Metrics collected")
- After 5 cycles (2.5 minutes), proposals may be generated if gaps detected

## Test 6: Monitor Logs for Metrics Collection

```bash
tail -f logs/godelos.log | grep "Metrics collected\|Proposal Generated"
```

**Expected to See**:
- Every 30 seconds: `📊 Metrics collected: X queries, Y% success rate, Z.XXs avg`
- Every 2.5 minutes: `📊 Detected N capability gaps` (if gaps exist)
- Proposal generation: `📝 Generated proposal: Improve [Capability] (risk: low/moderate)`

## Test 7: Frontend Validation

1. Open http://localhost:3001
2. Navigate to Self-Modification Hub
3. **Capability Assessment Panel**:
   - Should show real capability levels (not mock data)
   - If no queries processed, may show "No capability assessments available yet"
   - After processing queries, should show capabilities with actual levels
4. **Proposal Review Panel**:
   - Initially empty: "No proposals available yet"
   - After gaps detected, proposals appear with real details
5. **Live Cognitive Monitor**:
   - Shows actual daemon threads
   - Shows active sessions if queries being processed
   - Resource utilization reflects real metrics
6. **Evolution Timeline**:
   - Initially empty
   - Populates with events as proposals are created/approved

## Test 8: Capability Score Validation

After processing multiple queries, capabilities should:
- **Analogical Reasoning**: Based on success_rate + latency + awareness
- **Knowledge Integration**: Based on knowledge_items_created + gap_resolution
- **Creative Problem Solving**: Based on complex query success + reflection depth
- Lower scores (<0.7) should trigger proposals after 2.5 minutes

## Test 9: Proposal Generation Validation

1. Process queries that stress specific capabilities
2. Wait 2.5 minutes (5 cycles)
3. Check proposals endpoint:
   ```bash
   curl http://localhost:8000/api/metacognition/proposals | jq '.proposals'
   ```
4. Verify proposals have:
   - Real target_components (not mock)
   - Expected benefits linked to detected gaps
   - Risk levels: "low" or "moderate"
   - Modification types: PARAMETER_TUNING, ALGORITHM_SELECTION, STRATEGY_ADAPTATION

## Test 10: Timeline Event Recording

1. Approve a proposal:
   ```bash
   curl -X POST http://localhost:8000/api/metacognition/proposals/{proposal_id}/approve \
     -H "Content-Type: application/json" \
     -d '{"actor": "test_user"}'
   ```
2. Check evolution timeline:
   ```bash
   curl http://localhost:8000/api/metacognition/evolution | jq '.timeline'
   ```
3. Should see "Approved: [Proposal Title]" event

## Success Criteria

✅ **Phase 1-4 Complete** when:
- All endpoints return real data (NO mock/seed data)
- Capabilities calculated from actual cognitive_manager metrics
- Proposals generated automatically based on detected gaps
- Live state shows real system status
- Timeline records events properly
- Frontend displays data correctly (no "No Data Available" with real activity)

## Troubleshooting

### No metrics being collected
- Check if cognitive_manager is initialized
- Verify metrics collection task started: look for "🔄 Started metrics collection"
- Check for errors in logs

### No proposals generated
- Ensure queries are being processed
- Wait at least 2.5 minutes for first proposal generation cycle
- Check if capabilities are below threshold (<0.7)
- Look for "📊 Detected N capability gaps" in logs

### Frontend shows "No Data Available"
- Check backend API endpoints directly with curl
- Verify WebSocket connection is established
- Check browser console for errors

### Capabilities all show same values
- Process more queries to generate varied metrics
- Wait for baseline to be established
- Check metrics snapshot in logs

---

**Date Created**: October 1, 2025
**Test Status**: Ready for execution
**Expected Duration**: 5-10 minutes for full test suite
