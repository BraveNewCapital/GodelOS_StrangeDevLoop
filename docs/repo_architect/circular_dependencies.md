# Circular Dependencies

## Cycle 1

- `backend.core.agentic_daemon_system`
- `backend.core.grounding_coherence_daemon`
- `backend.core.agentic_daemon_system`

## Cycle 2

- `godelOS.core_kr.knowledge_store.chroma_store`
- `godelOS.core_kr.knowledge_store.interface`
- `godelOS.core_kr.knowledge_store.chroma_store`

## Cycle 3

- `godelOS.core_kr.type_system.manager`
- `godelOS.core_kr.type_system.visitor`
- `godelOS.core_kr.type_system.manager`
