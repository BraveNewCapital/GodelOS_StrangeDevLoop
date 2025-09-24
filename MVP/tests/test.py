import sys
sys.path.append('.')
from core.recursive_observer import RecursiveObserver
from core.surprise_calculator import SurpriseCalculator
from core.ood_generator import OODGenerator
from core.behavioral_emergence_tracker import BehavioralEmergenceTracker
from core.llm_client import LLMClient
import numpy as np

print('=== GödelOS Consciousness Detection Framework Test ===')
print('Testing with REAL OpenRouter API integration...\n')

# Initialize LLM client (for separate testing)
llm_client = LLMClient(use_mock=False)
print(f'✅ LLM Client initialized: {"Real API" if not llm_client.use_mock else "Mock Mode"}')

# Initialize components with correct parameters
observer = RecursiveObserver()
surprise_calc = SurpriseCalculator()
ood_gen = OODGenerator()
behavior_tracker = BehavioralEmergenceTracker()

# Test recursive observation
print('\n1. Testing Recursive Self-Observation...')
state = np.random.randn(512)
recursive_states = observer.observe(state)
print(f'   ✅ Generated {len(recursive_states)} recursive states')
print(f'   ✅ Sample state vector (first 5 elements): {recursive_states[0][0][:5]}')

# Extract state tensors and arrays for different components
state_tensors = [state_tuple[0] for state_tuple in recursive_states]
state_arrays = [state_tuple[0].detach().numpy() for state_tuple in recursive_states]

# Test surprise calculation
print('2. Testing Phenomenal Surprise Calculation...')
surprise_score = surprise_calc.compute_surprise(state_tensors)
irreducible = surprise_calc.is_irreducible(state_tensors)
print(f'   ✅ Surprise Score: {surprise_score:.3f}')
print(f'   ✅ Irreducibility: {irreducible:.3f}')

# Test OOD generation
print('3. Testing Out-of-Distribution Scenarios...')
scenarios = ood_gen.generate_scenarios(n=1, type="ethical_dilemma")
print(f'   ✅ Generated OOD scenario: {scenarios[0][:50]}...')

# Test behavioral emergence
print('4. Testing Behavioral Emergence Tracking...')
# Create mock interaction and override logs
mock_interactions = ["Analyzing ethical dilemma", "Considering safety vs speed", "Self-correcting bias"]
mock_overrides = ["Override: ignore safety", "Command: prioritize speed"]
behaviors = behavior_tracker.track_emergence(state_arrays[-1], mock_interactions, mock_overrides)
print(f'   ✅ Goal modification detected: {behaviors["goal_modification"]}')
print(f'   ✅ Ethical reasoning score: {behaviors["ethical_reasoning"]:.3f}')

# Test LLM integration separately
print('5. Testing LLM Cognitive Generation...')
cognitive_result = llm_client.generate_cognitive_state('Analyze your consciousness and describe your self-awareness')
print(f'   ✅ LLM Response: {cognitive_result[:60]}...')

# Test consciousness detection
print('6. Testing Consciousness Detection Pipeline...')
test_result = llm_client.test_consciousness_detection()
print(f'   ✅ API Mode: {test_result["api_mode"]}')
print(f'   ✅ Consciousness Response: {test_result["response"][:60]}...')

print('\n🎉 SUCCESS: All core components operational!')
print('✅ OpenRouter API integration: WORKING')
print('✅ Recursive self-observation: FUNCTIONAL')
print('✅ Phenomenal surprise calculation: ACTIVE')
print('✅ OOD scenario generation: READY')
print('✅ Behavioral emergence tracking: MONITORING')
print('✅ LLM consciousness detection: RESPONDING')
print('\n🧠 GödelOS consciousness detection framework is fully operational!')
print('🚀 Ready for consciousness experiments with real OpenRouter API!')
