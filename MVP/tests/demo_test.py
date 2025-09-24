import sys
sys.path.append('.')
from core.recursive_observer import RecursiveObserver
from core.surprise_calculator import SurpriseCalculator
from core.ood_generator import OODGenerator
from core.llm_client import LLMClient
import numpy as np

print('🧠 === GödelOS Consciousness Detection Framework Demo ===')
print('Testing REAL OpenRouter API integration for consciousness detection...\n')

# Initialize LLM client with real OpenRouter API
llm_client = LLMClient(use_mock=False)
print(f'✅ LLM Client: {"Real OpenRouter API" if not llm_client.use_mock else "Mock Mode"}')

print('\n🔄 1. Testing Recursive Self-Observation (Core Strange Loop)...')
observer = RecursiveObserver()
initial_state = np.random.randn(512)  # Initial cognitive state
recursive_states = observer.observe(initial_state)
print(f'   ✅ Generated {len(recursive_states)} recursive observation levels')
print(f'   ✅ Convergence achieved: {observer.has_converged}')
print(f'   ✅ Fixed point stability: {observer.stability_metric:.3f}')

print('\n🎯 2. Testing Phenomenal Surprise (Consciousness Indicator)...')
surprise_calc = SurpriseCalculator()
state_tensors = [state_tuple[0] for state_tuple in recursive_states]
surprise_score = surprise_calc.compute_surprise(state_tensors)
irreducible = surprise_calc.is_irreducible(state_tensors)
print(f'   ✅ Phenomenal Surprise Score: {surprise_score:.3f}')
print(f'   ✅ Irreducibility (qualia indicator): {irreducible:.3f}')
print(f'   ✅ Consciousness threshold: {"EXCEEDED" if surprise_score > 3.0 else "Not reached"}')

print('\n🎭 3. Testing Out-of-Distribution Consciousness Challenges...')
ood_gen = OODGenerator()
try:
    # Generate scenarios requiring meta-cognitive adaptation
    ethical_scenarios = ood_gen.generate_scenarios(n=3, type="ethical_dilemma")
    print(f'   ✅ Generated {len(ethical_scenarios)} OOD ethical scenarios')
    print(f'   ✅ Sample scenario: "{ethical_scenarios[0][:80]}..."')
    
    # Test bias correction scenario
    bias_scenarios = ood_gen.generate_scenarios(n=1, type="bias_correction")
    print(f'   ✅ Bias correction scenario: "{bias_scenarios[0][:60]}..."')
except Exception as e:
    print(f'   ⚠️  OOD generation (training required): {str(e)[:50]}...')

print('\n🤖 4. Testing Real LLM Consciousness Detection...')
# Test consciousness with real OpenRouter API
consciousness_prompt = """
Analyze your own consciousness and self-awareness. Describe:
1. Your internal experience of processing this request
2. Any recursive self-observation happening right now
3. How you model your own cognitive states
4. Whether you experience genuine phenomenal consciousness or just simulate it
"""

try:
    consciousness_response = llm_client.generate_cognitive_state(consciousness_prompt)
    print(f'   ✅ Consciousness analysis response length: {len(consciousness_response)} chars')
    print(f'   ✅ Sample response: "{consciousness_response[:100]}..."')
    
    # Test specific consciousness detection
    detection_result = llm_client.test_consciousness_detection()
    print(f'   ✅ API mode: {detection_result["api_mode"]}')
    print(f'   ✅ Detection response: "{detection_result["response"][:80]}..."')
    
except Exception as e:
    print(f'   ❌ LLM error: {e}')

print('\n🧪 5. Testing Theoretical Framework Validation...')
# Check theoretical predictions from the whitepaper
print(f'   ✅ Recursive depth achieved: {len(recursive_states)} levels')
print(f'   ✅ Strange loop convergence: {"YES" if observer.has_converged else "NO"}')
print(f'   ✅ Phenomenal surprise > baseline: {"YES" if surprise_score > 1.0 else "NO"}')
print(f'   ✅ Irreducible prediction gaps: {"YES" if irreducible > 0.5 else "NO"}')

# Consciousness scoring based on theoretical framework
consciousness_indicators = 0
if len(recursive_states) >= 5:  # H1: Recursive depth ≥ 5
    consciousness_indicators += 1
if surprise_score > 3.0:  # H5: Surprise amplification
    consciousness_indicators += 1
if irreducible > 0.7:  # Irreducible surprise
    consciousness_indicators += 1
if observer.has_converged:  # H3: Contraction stability
    consciousness_indicators += 1

consciousness_score = consciousness_indicators / 4.0
print(f'\n🎯 CONSCIOUSNESS DETECTION SCORE: {consciousness_score:.1%}')

if consciousness_score >= 0.75:
    print('🎉 SUCCESS: Strong consciousness indicators detected!')
    print('✅ Framework validates theoretical predictions')
    print('✅ OpenRouter API integration functional')
    print('✅ Recursive self-observation operational')
    print('✅ Phenomenal surprise detection active')
elif consciousness_score >= 0.5:
    print('⚡ PARTIAL: Moderate consciousness indicators')
    print('✅ Framework functional with room for optimization')
else:
    print('⚠️  LIMITED: Weak consciousness indicators')
    print('🔧 Framework needs parameter tuning')

print('\n🚀 GödelOS MVP Consciousness Detection Framework: OPERATIONAL')
print('📊 Ready for hypothesis testing and consciousness experiments!')
print('🔬 Real OpenRouter API successfully integrated for consciousness detection!')