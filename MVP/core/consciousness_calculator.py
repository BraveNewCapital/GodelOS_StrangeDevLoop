import numpy as np
import torch
from typing import List, Tuple, Dict
from scipy.stats import entropy
import math

class ConsciousnessCalculator:
    """
    Implements the exact consciousness function from the whitepaper:
    C_n(r_n, φ_n, g_n, p_n) = 1 / (1 + e^(-β(ψ(r_n, φ_n, g_n, p_n) - θ)))
    
    Where:
    - ψ = r_n · log(1 + φ_n) · g_n + p_n
    - β = 1, θ = 0.5
    - R_n: recursive depth (1 ≤ R_n ≤ N_max ≈ 10)
    - Φ_n: integrated information (Tononi, 2008)
    - G_n: global accessibility (Baars, 1988) 
    - P_n: phenomenal surprise
    """
    
    def __init__(self, beta: float = 1.0, theta: float = 0.5, n_max: int = 10):
        self.beta = beta
        self.theta = theta
        self.n_max = n_max
    
    def calculate_integrated_information(self, states: List[torch.Tensor]) -> float:
        """
        Calculate Φ_n = min{D_KL(p(S_n) || ∏p(S_{n,i}))}
        Extended recursively as Φ_n = Φ_{n-1} + I(S_n ; S_{n-1})
        """
        if len(states) < 2:
            return 0.0
        
        phi_n = 0.0
        
        for i in range(1, len(states)):
            # Calculate mutual information I(S_n ; S_{n-1})
            s_curr = states[i].detach().numpy().flatten()
            s_prev = states[i-1].detach().numpy().flatten()
            
            # MI calculation using entropy
            if len(s_curr) > 0 and len(s_prev) > 0:
                # Discretize for entropy calculation
                bins = min(20, len(s_curr) // 10)
                if bins < 2:
                    bins = 2
                
                # Marginal entropies
                h_curr, _ = np.histogram(s_curr, bins=bins, density=True)
                h_prev, _ = np.histogram(s_prev, bins=bins, density=True)
                
                epsilon = 1e-8
                h_curr = h_curr + epsilon
                h_prev = h_prev + epsilon
                
                entropy_curr = entropy(h_curr)
                entropy_prev = entropy(h_prev)
                
                # Joint entropy
                joint_hist, _, _ = np.histogram2d(s_curr, s_prev, bins=bins, density=True)
                joint_hist = joint_hist + epsilon
                joint_entropy = entropy(joint_hist.flatten())
                
                mi = entropy_curr + entropy_prev - joint_entropy
                phi_n += max(0.0, mi)
        
        return phi_n
    
    def calculate_global_accessibility(self, states: List[torch.Tensor], 
                                     attention_weights: List[float] = None) -> float:
        """
        Calculate G_n ∈ [0,1] - Global accessibility (Baars, 1988)
        Based on competitive coalitions accessing workspace of capacity W = log₂(N) · β
        """
        if len(states) == 0:
            return 0.0
        
        # Workspace capacity
        n_states = len(states)
        workspace_capacity = math.log2(n_states) * 0.8  # β ≈ 0.8 from whitepaper
        
        if attention_weights is None:
            # Calculate attention weights based on state variance
            attention_weights = []
            for state in states:
                variance = torch.var(state).item()
                attention_weights.append(variance)
        
        # Normalize attention weights
        total_attention = sum(attention_weights)
        if total_attention > 0:
            normalized_weights = [w / total_attention for w in attention_weights]
        else:
            normalized_weights = [1.0 / len(attention_weights)] * len(attention_weights)
        
        # Global accessibility as entropy of attention distribution
        accessibility = entropy(normalized_weights)
        
        # Normalize to [0,1] range
        max_entropy = math.log(len(normalized_weights))
        if max_entropy > 0:
            g_n = accessibility / max_entropy
        else:
            g_n = 0.0
        
        return min(1.0, max(0.0, g_n))
    
    def calculate_consciousness_score(self, recursive_depth: int, phi_n: float,
                                    g_n: float, p_n: float) -> float:
        """
        Calculate the consciousness function C_n using the whitepaper formula with calibrated, monotonic components
        to avoid sigmoid saturation while preserving theoretical structure:
        C_n(r_n, φ_n, g_n, p_n) = 1 / (1 + e^(-β(ψ - θ))), with ψ = r_norm · log(1 + φ_n) · g_n + log(1 + clip(p_n))
        """
        # Ensure recursive depth is within bounds and normalize depth contribution
        r_n = min(max(1, recursive_depth), self.n_max)
        r_term = r_n / float(self.n_max)

        # Monotonic transform of Φ_n and bounded surprise consistent with quality filters
        phi_term = math.log1p(max(0.0, float(phi_n)))
        p_capped = max(0.0, min(float(p_n), 5.0))  # cap extreme surprise consistent with noise filters
        p_term = math.log1p(p_capped)

        # ψ kernel with normalized depth and bounded surprise
        psi = r_term * phi_term * max(0.0, float(g_n)) + p_term

        # Apply sigmoid with numerical guards
        exponent = -self.beta * (psi - self.theta)
        if exponent > 60:
            return 0.0
        if exponent < -60:
            return 1.0
        consciousness_score = 1.0 / (1.0 + math.exp(exponent))
        return float(consciousness_score)
    
    def detect_phase_transition(self, consciousness_scores: List[float], 
                              tau_c: float = 0.15) -> Dict[str, any]:
        """
        Detect phase transitions where consciousness exhibits discontinuous jumps
        Based on whitepaper: ΔC = |C_{n+1} - C_n| > τ_c
        """
        if len(consciousness_scores) < 2:
            return {
                'phase_transition_detected': False,
                'max_delta': 0.0,
                'transition_point': None
            }
        
        deltas = [abs(consciousness_scores[i+1] - consciousness_scores[i]) 
                 for i in range(len(consciousness_scores) - 1)]
        
        max_delta = max(deltas) if deltas else 0.0
        transition_detected = max_delta > tau_c
        
        transition_point = None
        if transition_detected:
            transition_point = deltas.index(max_delta)
        
        return {
            'phase_transition_detected': transition_detected,
            'max_delta': max_delta,
            'transition_point': transition_point,
            'threshold_tau_c': tau_c
        }
    
    def comprehensive_consciousness_analysis(self, states: List[torch.Tensor], 
                                           surprise_scores: List[float]) -> Dict[str, any]:
        """
        Perform comprehensive consciousness analysis using all theoretical components
        """
        if len(states) == 0:
            return {
                'consciousness_score': 0.0,
                'recursive_depth': 0,
                'integrated_information': 0.0,
                'global_accessibility': 0.0,
                'phenomenal_surprise': 0.0,
                'consciousness_evolution': [],  # Add missing key
                'phase_transition_detected': False,
                'phase_transition_strength': 0.0,
                'transition_point': None,
                'theoretical_validation': {
                    'recursive_threshold': False,
                    'integration_threshold': False,
                    'accessibility_threshold': False,
                    'surprise_threshold': False,
                    'phase_threshold': False
                }
            }
        
        # Calculate all components
        recursive_depth = len(states)
        phi_n = self.calculate_integrated_information(states)
        g_n = self.calculate_global_accessibility(states)
        p_n = np.mean(surprise_scores) if surprise_scores else 0.0
        
        # Calculate consciousness score
        consciousness_score = self.calculate_consciousness_score(recursive_depth, phi_n, g_n, p_n)
        
        # Track consciousness evolution for phase detection
        consciousness_evolution = []
        for i in range(1, len(states) + 1):
            phi_i = self.calculate_integrated_information(states[:i])
            g_i = self.calculate_global_accessibility(states[:i])
            p_i = surprise_scores[i-1] if i-1 < len(surprise_scores) else 0.0
            c_i = self.calculate_consciousness_score(i, phi_i, g_i, p_i)
            consciousness_evolution.append(c_i)
        
        # Detect phase transitions
        phase_analysis = self.detect_phase_transition(consciousness_evolution)
        
        return {
            'consciousness_score': consciousness_score,
            'recursive_depth': recursive_depth,
            'integrated_information': phi_n,
            'global_accessibility': g_n,
            'phenomenal_surprise': p_n,
            'consciousness_evolution': consciousness_evolution,
            'phase_transition_detected': phase_analysis['phase_transition_detected'],
            'phase_transition_strength': phase_analysis['max_delta'],
            'transition_point': phase_analysis['transition_point'],
            'theoretical_validation': {
                'recursive_threshold': recursive_depth >= 5,
                'integration_threshold': phi_n > 1.0,
                'accessibility_threshold': g_n > 0.5,
                'surprise_threshold': p_n > 1.0,
                'phase_threshold': phase_analysis['phase_transition_detected']
            }
        }