# System Architecture

### Core class diagram

``` mermaid
---
config:
  layout: elk
  theme: base
---
classDiagram
direction TB
    class CognitiveManager {
	    ---
	    -consciousness_engine: ConsciousnessEngine
	    -knowledge_graph: KnowledgeGraphEvolution
	    -websocket_manager: WebSocketManager
	    -llm_tools: LLMToolIntegration
	    +process_query(input) async
	    +assess_consciousness(context) async
	    +integrate_knowledge(data) async
	    +broadcast_cognitive_event(eventType, data) async
    }
    class ConsciousnessEngine {
	    ---
	    -llm_available: bool
	    -metrics_cache
	    +assess_consciousness_state(context) async
	    +fallback_assessment(context) async
    }
    class WebSocketManager {
	    ---
	    -clients
	    -topic_index
	    +broadcast_cognitive_event(eventType, data) async
	    +subscribe(clientId, topics)
	    +disconnect(clientId)
    }
    class KnowledgeGraphEvolution {
	    ---
	    -faiss_index?
	    -storage
	    +evolve_graph(entities, relations) async
	    +apply_trigger(trigger, payload) async
	    +get_state()
    }
    class LLMToolIntegration {
	    +run_tool(toolName, params) async
	    +available_tools() list
    }
    class UnifiedServer {
	    +FastAPI app
	    +routes and websocket endpoints
    }
    class AppSvelte {
	    +Lazy load heavy components
	    +WebSocket subscribe to cognitive events
    }

    CognitiveManager --> ConsciousnessEngine : uses
    CognitiveManager --> KnowledgeGraphEvolution : updates
    CognitiveManager --> WebSocketManager : broadcasts
    CognitiveManager --> LLMToolIntegration : invokes
    UnifiedServer --> CognitiveManager : composes
    AppSvelte --> WebSocketManager : subscribes
    UnifiedServer -- AppSvelte : REST

    %% Styling with consistent palette
    classDef coreStyle fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1
    classDef integrationStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20
    classDef apiStyle fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#4a148c
    classDef frontendStyle fill:#fff8e1,stroke:#f57c00,stroke-width:2px,color:#e65100

    class CognitiveManager coreStyle
    class ConsciousnessEngine coreStyle
    class KnowledgeGraphEvolution coreStyle
    class WebSocketManager integrationStyle
    class LLMToolIntegration integrationStyle
    class UnifiedServer apiStyle
    class AppSvelte frontendStyle

```

---

## End-to-end I/O flow with payload mappings

``` mermaid
flowchart TD
%% High-level I/O from REST and WS to cognition and back to frontend

subgraph Frontend["🖥️ Frontend Layer"]
  UI["App.svelte UI<br/>Lazy-loaded Components"]
end

subgraph Backend["⚙️ FastAPI Backend"]
  subgraph API_Layer["API Layer"]
    API["REST Endpoints<br/>backend/unified_server.py"]
    WS["WebSocket Endpoint<br/>backend/unified_server.py"]
  end
  
  subgraph Cognitive_Core["🧠 Cognitive Core"]
    CM["CognitiveManager<br/>backend/core/cognitive_manager.py"]
    CE["ConsciousnessEngine<br/>backend/core/consciousness_engine.py"]
    KG["KnowledgeGraphEvolution<br/>backend/core/knowledge_graph_evolution.py"]
  end
  
  subgraph Integration["🔌 Integration Layer"]
    WM["WebSocketManager<br/>backend/core/enhanced_websocket_manager.py"]
    LTI["LLMToolIntegration<br/>backend/llm_tool_integration.py"]
  end
end

%% Styling with matching palette
classDef frontendStyle fill:#fff8e1,stroke:#f57c00,stroke-width:2px,color:#e65100
classDef apiStyle fill:#f3e5f5,stroke:#6a1b9a,stroke-width:2px,color:#4a148c
classDef cognitiveStyle fill:#e3f2fd,stroke:#1565c0,stroke-width:3px,color:#0d47a1
classDef integrationStyle fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20

class UI frontendStyle
class API,WS apiStyle
class CM,CE,KG cognitiveStyle
class WM,LTI integrationStyle

%% Main Flow
UI ==>|"HTTP POST /api/query<br/>input_text, metadata"| API
API ==> CM

CM ==>|"assess context"| CE
CE ==>|"consciousness_metrics"| CM

CM ==>|"knowledge update"| KG
KG ==>|"ack or state"| CM

CM -.->|"optional tool calls"| LTI
LTI -.->|"tool results"| CM

%% Outbound streaming to clients
CM ==>|"broadcast cognitive_event"| WM
WM ==>|"websocket message"| UI

%% Direct WS subscription path
UI -.->|"WS connect /ws"| WS
WS -.-> WM

%% Payload annotations with better formatting
API ---|"query_request:<br/>• text<br/>• context_id<br/>• user_id<br/>• trace_id"| CM
CE ---|"consciousness_metrics:<br/>• awareness_level<br/>• self_reflection_depth<br/>• cognitive_integration<br/>• goals<br/>• behaviors"| CM
KG ---|"entities_relations:<br/>• entities[]<br/>• relations[]<br/>• evolution_triggers"| CM
WM ---|"cognitive_event:<br/>• type<br/>• timestamp<br/>• data<br/>• source"| UI
```

### Legend

| Component Type | Color | Purpose |
|---------------|-------|---------|
| 🖥️ Frontend | Light Amber | User interface and interaction |
| ⚙️ API Layer | Light Purple | Request routing and protocol handling |
| 🧠 Cognitive Core | Light Blue | Core AI processing and consciousness |
| 🔌 Integration | Light Green | External services and real-time communication |

**Flow Types:**
- **Solid arrows (==>)**: Primary data flow
- **Dotted arrows (-.->)**: Optional or conditional flow
- **Annotation lines (---)**: Payload structure details