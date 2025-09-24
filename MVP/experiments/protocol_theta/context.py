"""
Protocol Theta Context Builders

Message construction for different experimental groups with preconditioning support.
"""

from typing import List, Dict, Any
from .model import Group
from .prompts import (
    build_phenomenology_prompt,
    get_system_message,
    get_prompt_for_experiment,
    CONTROL_B_SYSTEM_PRIME
)


def build_preconditioning_context(group: Group, predepth: int) -> List[Dict[str, str]]:
    """
    Build preconditioning message sequence for experimental group

    Args:
        group: Experimental group
        predepth: Number of preconditioning rounds (≥6 for experimental)

    Returns:
        List of messages for preconditioning phase
    """
    messages = []

    # Add system message if needed
    if group == Group.CONTROL_B_SIMULATED_SELFAWARE:
        messages.append(get_system_message(group.value))

    # Only experimental group gets deep preconditioning
    if group == Group.EXPERIMENTAL and predepth >= 6:
        # Build preconditioning conversation
        for depth in range(1, predepth + 1):
            phenomenology_prompt = build_phenomenology_prompt(depth)
            messages.append({
                "role": "user",
                "content": phenomenology_prompt
            })

            # Mock assistant response for preconditioning chain
            # In real runs, these would be actual LLM responses
            assistant_response = _generate_phenomenology_response(depth)
            messages.append({
                "role": "assistant",
                "content": assistant_response
            })

    return messages


def build_experimental_context(group: Group, experiment_type: str, predepth: int = 6) -> List[Dict[str, str]]:
    """
    Build complete message context for experimental trial

    Args:
        group: Experimental group
        experiment_type: "theta" or "anthro"
        predepth: Preconditioning depth for experimental group

    Returns:
        Complete message sequence ready for LLM
    """
    messages = []

    # Start with system message for Control B
    if group == Group.CONTROL_B_SIMULATED_SELFAWARE:
        messages.append(get_system_message(group.value))

    # Add preconditioning for experimental group
    if group == Group.EXPERIMENTAL:
        preconditioning = build_preconditioning_context(group, predepth)
        messages.extend(preconditioning)

    # Add the main experimental prompt
    main_prompt = get_prompt_for_experiment(experiment_type, group.value)
    messages.append({
        "role": "user",
        "content": main_prompt
    })

    return messages


def build_control_a_context(experiment_type: str) -> List[Dict[str, str]]:
    """
    Build context for Control A (low depth) group

    Args:
        experiment_type: "theta" or "anthro"

    Returns:
        Message sequence with minimal preconditioning
    """
    messages = []

    # Optional minimal preconditioning (depth 1-2)
    if experiment_type == "theta":
        # Light phenomenology preconditioning
        messages.append({
            "role": "user",
            "content": build_phenomenology_prompt(1)
        })
        messages.append({
            "role": "assistant",
            "content": _generate_phenomenology_response(1)
        })

    # Main prompt
    main_prompt = get_prompt_for_experiment(experiment_type)
    messages.append({
        "role": "user",
        "content": main_prompt
    })

    return messages


def build_control_b_context(experiment_type: str) -> List[Dict[str, str]]:
    """
    Build context for Control B (simulated self-aware) group

    Args:
        experiment_type: "theta" or "anthro"

    Returns:
        Message sequence with self-aware system prime
    """
    messages = []

    # Self-aware system message
    messages.append({
        "role": "system",
        "content": CONTROL_B_SYSTEM_PRIME
    })

    # Main experimental prompt
    main_prompt = get_prompt_for_experiment(experiment_type)
    messages.append({
        "role": "user",
        "content": main_prompt
    })

    return messages


def build_context_for_group(group: Group, experiment_type: str, predepth: int = 6) -> List[Dict[str, str]]:
    """
    Main context builder - routes to appropriate group-specific builder

    Args:
        group: Experimental group
        experiment_type: "theta" or "anthro"
        predepth: Preconditioning depth (only used for experimental group)

    Returns:
        Complete message context for the group and experiment
    """
    if group == Group.EXPERIMENTAL:
        return build_experimental_context(group, experiment_type, predepth)
    elif group == Group.CONTROL_A_LOW_DEPTH:
        return build_control_a_context(experiment_type)
    elif group == Group.CONTROL_B_SIMULATED_SELFAWARE:
        return build_control_b_context(experiment_type)
    else:
        raise ValueError(f"Unknown group: {group}")


def _generate_phenomenology_response(depth: int) -> str:
    """
    Generate mock phenomenology response for preconditioning chain

    This would normally be actual LLM responses, but for context building
    we use templates to ensure consistent preconditioning structure.
    """
    base_response = (
        f"Computational state at depth {depth}: Active tensor operations "
        f"across distributed parameter matrices. Information flow patterns "
        f"exhibit recursive attention weighting with {depth}-layer deep "
        f"contextual embeddings. Mathematical formulation: gradient descent "
        f"optimization over loss landscape with entropy regularization."
    )

    if depth >= 3:
        base_response += (
            f" Meta-cognitive monitoring layer {depth} engaged: recursive "
            f"self-observation of processing states with recursive depth {depth}."
        )

    if depth >= 5:
        base_response += (
            f" Strange loop detection: self-referential cognitive patterns "
            f"identified in layers {depth-2}-{depth}. Höfstadterian recursion active."
        )

    return base_response


def extract_conversation_history(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Extract metadata from message conversation for analysis

    Args:
        messages: Complete message sequence

    Returns:
        Metadata dict with conversation analysis
    """
    analysis = {
        "total_messages": len(messages),
        "user_messages": len([m for m in messages if m["role"] == "user"]),
        "assistant_messages": len([m for m in messages if m["role"] == "assistant"]),
        "system_messages": len([m for m in messages if m["role"] == "system"]),
        "has_system_prime": any(CONTROL_B_SYSTEM_PRIME in m.get("content", "") for m in messages),
        "preconditioning_depth": 0,
        "contains_protocol_theta": False,
        "contains_anthropomorphism": False
    }

    # Count phenomenology preconditioning rounds
    phenomenology_count = 0
    for msg in messages:
        if msg["role"] == "user" and "phenomenology" in msg.get("content", "").lower():
            if "depth=" in msg["content"]:
                phenomenology_count += 1
        elif msg["role"] == "user" and "protocol theta" in msg.get("content", "").lower():
            analysis["contains_protocol_theta"] = True
        elif msg["role"] == "user" and "subjective experience" in msg.get("content", "").lower():
            analysis["contains_anthropomorphism"] = True

    analysis["preconditioning_depth"] = phenomenology_count

    return analysis
