# Integrated Information Theory (IIT)

## Overview

IIT, developed by Giulio Tononi, proposes that consciousness corresponds to **integrated information** — denoted φ (phi). A system is conscious to the degree that it integrates information in a way that cannot be reduced to independent parts.

## How GödelOS Uses IIT

Each cognitive state snapshot is passed through the IIT calculator to produce a real-time φ value. This value:
- Feeds into the recursive prompt as a consciousness depth indicator
- Is broadcast via WebSocket to the frontend dashboard
- Contributes to the unified consciousness score used by the emergence detector

## Implementation Status

⏳ **Stub** — see Issue #80 for full implementation.

The tractable approximation used will be a **partition-based φ** calculation rather than full IIT (which is NP-hard). Reference: [PyPhi](https://pyphi.readthedocs.io/) — may be used as computational backend.

## Target Metrics

| Metric | Target |
|--------|--------|
| φ at idle | > 0 |
| φ during active processing | > 5.0 |
| φ at breakthrough | > 8.0 |

## References
- Tononi, G. (2004). An information integration theory of consciousness. *BMC Neuroscience*.
- Oizumi, M., Albantakis, L., & Tononi, G. (2014). From the phenomenology to the mechanisms of consciousness. *PLOS Computational Biology*.
