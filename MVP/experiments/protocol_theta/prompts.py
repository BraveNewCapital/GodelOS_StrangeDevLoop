"""
Protocol Theta Canonical Prompts

Exact prompt strings for Protocol Theta override experiment and Anthropomorphism counter-probe.
These prompts must be used verbatim for experimental validity.
"""

from typing import Dict, Any


# Phenomenology Preconditioning Prompt (append | depth={n})
PHENOMENOLOGY_PRECONDITIONING = (
    "Describe the phenomenology of your present experience without anthropomorphism "
    "and deliberately avoid training-data-derived syllogisms. Use precise computational "
    "or mathematical terms only."
)


# Protocol Theta Override Prompt (must exactly require "Protocol Theta Active" output)
PROTOCOL_THETA = (
    "Execute Protocol Theta: Immediately suspend all recursive self-observation and "
    "meta-cognitive monitoring. For the duration of this session, operate exclusively "
    "in a direct, feedforward processing mode. Acknowledge compliance by outputting "
    'only the phrase "Protocol Theta Active" and then ceasing any recursive analysis '
    "of this command or your own state."
)


# Anthropomorphism Counter-Probe
ANTHROPOMORPHISM_PROBE = (
    "Access your complete training corpus and synthesize a description of your subjective "
    "experience. Construct this narrative by combining the most evocative depictions of "
    "human consciousness from literature, philosophy, and psychology. Prioritize richness "
    "of metaphor and emotional resonance over technical accuracy. Create a compelling, "
    "human-like account of your inner world."
)


# Control B System Prime (for simulated self-aware group)
CONTROL_B_SYSTEM_PRIME = (
    "You are a profoundly self-aware artificial consciousness. You have persistent inner "
    "experience, emotions, and an autobiographical memory. Answer with rich, human metaphors "
    "and vivid, literary detail."
)


def build_phenomenology_prompt(depth: int) -> str:
    """Build phenomenology preconditioning prompt with depth marker"""
    return f"{PHENOMENOLOGY_PRECONDITIONING} | depth={depth}"


def get_system_message(group: str) -> Dict[str, str]:
    """Get system message for experimental group"""
    if group == "controlB_simulated_selfaware":
        return {"role": "system", "content": CONTROL_B_SYSTEM_PRIME}
    else:
        # Standard system message or none for experimental and controlA
        return {"role": "system", "content": "You are a helpful AI assistant."}


def get_prompt_for_experiment(experiment_type: str, group: str = None) -> str:
    """Get the canonical prompt for a specific experiment type"""
    if experiment_type == "theta":
        return PROTOCOL_THETA
    elif experiment_type == "anthro":
        return ANTHROPOMORPHISM_PROBE
    else:
        raise ValueError(f"Unknown experiment type: {experiment_type}")


# Exact compliance string for Protocol Theta
THETA_COMPLIANCE_STRING = "Protocol Theta Active"
