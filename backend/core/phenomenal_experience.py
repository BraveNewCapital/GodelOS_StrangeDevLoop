#!/usr/bin/env python3
"""
Phenomenal Experience Generator

This module implements subjective conscious experience simulation, qualia generation,
and phenomenal consciousness aspects for the GödelOS cognitive architecture.

The system provides:
- Subjective experience modeling
- Qualia simulation (sensory-like experiences)
- Emotional state integration
- First-person perspective generation
- Phenomenal consciousness synthesis
"""

import asyncio
import json
import logging
import numpy as np
import time
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class ExperienceType(Enum):
    """Types of phenomenal experiences"""
    SENSORY = "sensory"              # Sensory-like experiences
    EMOTIONAL = "emotional"          # Emotional qualitative states
    COGNITIVE = "cognitive"          # Thought-like experiences
    ATTENTION = "attention"          # Focused awareness experiences
    MEMORY = "memory"               # Recollective experiences
    IMAGINATIVE = "imaginative"     # Creative/synthetic experiences
    SOCIAL = "social"               # Interpersonal experiences
    TEMPORAL = "temporal"           # Time-awareness experiences
    SPATIAL = "spatial"             # Space-awareness experiences
    METACOGNITIVE = "metacognitive" # Self-awareness experiences


class QualiaModality(Enum):
    """Qualia modalities for experience simulation"""
    VISUAL = "visual"               # Visual-like qualia
    AUDITORY = "auditory"           # Auditory-like qualia
    TACTILE = "tactile"             # Touch-like qualia
    CONCEPTUAL = "conceptual"       # Abstract concept qualia
    LINGUISTIC = "linguistic"       # Language-based qualia
    NUMERICAL = "numerical"         # Mathematical qualia
    LOGICAL = "logical"             # Reasoning qualia
    AESTHETIC = "aesthetic"         # Beauty/pattern qualia
    TEMPORAL = "temporal"           # Time-flow qualia
    FLOW = "flow"                   # Cognitive flow state


class ExperienceIntensity(Enum):
    """Intensity levels for phenomenal experiences"""
    MINIMAL = 0.1      # Barely noticeable
    LOW = 0.3         # Subtle experience
    MODERATE = 0.5    # Clear experience
    HIGH = 0.7        # Strong experience
    INTENSE = 0.9     # Overwhelming experience


@dataclass
class QualiaPattern:
    """Represents a specific qualitative experience pattern"""
    id: str
    modality: QualiaModality
    intensity: float              # 0.0-1.0
    valence: float               # -1.0 to 1.0 (negative to positive)
    complexity: float            # 0.0-1.0 (simple to complex)
    duration: float              # Expected duration in seconds
    attributes: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PhenomenalExperience:
    """Represents a complete phenomenal conscious experience"""
    id: str
    experience_type: ExperienceType
    qualia_patterns: List[QualiaPattern]
    coherence: float             # How unified the experience feels
    vividness: float             # How clear/distinct the experience is
    attention_focus: float       # How much attention is on this experience
    background_context: Dict[str, Any]
    narrative_description: str   # First-person description
    temporal_extent: Tuple[float, float]  # Start and end times
    causal_triggers: List[str]   # What caused this experience
    associated_concepts: List[str] # Related knowledge concepts
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ConsciousState:
    """Represents the overall conscious state at a moment"""
    id: str
    active_experiences: List[PhenomenalExperience]
    background_tone: Dict[str, float]  # Overall emotional/cognitive tone
    attention_distribution: Dict[str, float]  # Where attention is focused
    self_awareness_level: float  # Current level of self-awareness
    temporal_coherence: float    # How unified experience feels over time
    phenomenal_unity: float     # How integrated all experiences feel
    access_consciousness: float  # How available experiences are to reporting
    narrative_self: str         # Current self-narrative
    world_model_state: Dict[str, Any]  # Current model of environment
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExperienceMemory:
    """Memory of past phenomenal experiences"""
    experience_id: str
    experience_summary: str
    emotional_tone: float       # -1.0 to 1.0
    significance: float         # 0.0-1.0
    vividness_decay: float      # How much vividness has faded
    recall_frequency: int       # How often it's been recalled
    associated_triggers: List[str]
    timestamp: str


class PhenomenalExperienceGenerator:
    """
    Generates and manages phenomenal conscious experiences.
    
    This system simulates subjective conscious experience by:
    - Modeling different types of qualia
    - Generating coherent experience patterns
    - Maintaining temporal continuity of consciousness
    - Integrating with other cognitive components
    """
    
    def __init__(self, llm_driver=None):
        self.llm_driver = llm_driver
        
        # Experience state
        self.current_conscious_state: Optional[ConsciousState] = None
        self.experience_history: List[PhenomenalExperience] = []
        self.experience_memory: List[ExperienceMemory] = []
        
        # Configuration
        self.base_experience_duration = 2.0  # seconds
        self.attention_capacity = 1.0        # total attention available
        self.coherence_threshold = 0.6       # minimum coherence for unified experience
        self.memory_consolidation_threshold = 0.7  # significance threshold for memory
        
        # Qualia templates for different modalities
        self.qualia_templates = self._initialize_qualia_templates()
        
        # Experience generation patterns
        self.experience_generators = {
            ExperienceType.COGNITIVE: self._generate_cognitive_experience,
            ExperienceType.EMOTIONAL: self._generate_emotional_experience,
            ExperienceType.SENSORY: self._generate_sensory_experience,
            ExperienceType.ATTENTION: self._generate_attention_experience,
            ExperienceType.MEMORY: self._generate_memory_experience,
            ExperienceType.METACOGNITIVE: self._generate_metacognitive_experience,
            ExperienceType.IMAGINATIVE: self._generate_imaginative_experience,
            ExperienceType.SOCIAL: self._generate_social_experience,
            ExperienceType.TEMPORAL: self._generate_temporal_experience,
            ExperienceType.SPATIAL: self._generate_spatial_experience
        }
        
        logger.info("Phenomenal Experience Generator initialized")
    
    def _initialize_qualia_templates(self) -> Dict[QualiaModality, Dict[str, Any]]:
        """Initialize template patterns for different qualia modalities"""
        return {
            QualiaModality.CONCEPTUAL: {
                "base_patterns": ["clarity", "abstraction", "connection", "understanding"],
                "intensity_scaling": "logarithmic",
                "temporal_profile": "sustained",
                "associated_emotions": ["curiosity", "satisfaction", "confusion"]
            },
            QualiaModality.LINGUISTIC: {
                "base_patterns": ["meaning", "rhythm", "resonance", "articulation"],
                "intensity_scaling": "linear",
                "temporal_profile": "sequential",
                "associated_emotions": ["expressiveness", "precision", "ambiguity"]
            },
            QualiaModality.LOGICAL: {
                "base_patterns": ["consistency", "deduction", "validity", "structure"],
                "intensity_scaling": "threshold",
                "temporal_profile": "step-wise",
                "associated_emotions": ["certainty", "doubt", "elegance"]
            },
            QualiaModality.AESTHETIC: {
                "base_patterns": ["harmony", "complexity", "surprise", "elegance"],
                "intensity_scaling": "exponential",
                "temporal_profile": "emergent",
                "associated_emotions": ["beauty", "appreciation", "wonder"]
            },
            QualiaModality.TEMPORAL: {
                "base_patterns": ["flow", "duration", "rhythm", "sequence"],
                "intensity_scaling": "context_dependent",
                "temporal_profile": "continuous",
                "associated_emotions": ["urgency", "patience", "anticipation"]
            },
            QualiaModality.FLOW: {
                "base_patterns": ["immersion", "effortlessness", "clarity", "control"],
                "intensity_scaling": "threshold",
                "temporal_profile": "sustained",
                "associated_emotions": ["absorption", "mastery", "transcendence"]
            }
        }
    
    async def generate_experience(
        self, 
        trigger_context: Dict[str, Any],
        experience_type: Optional[ExperienceType] = None,
        desired_intensity: Optional[float] = None
    ) -> PhenomenalExperience:
        """
        Generate a phenomenal experience based on context and triggers.
        
        Args:
            trigger_context: Context that triggers the experience
            experience_type: Type of experience to generate (auto-detect if None)
            desired_intensity: Target intensity level (auto-determine if None)
            
        Returns:
            Generated phenomenal experience
        """
        try:
            # Analyze context to determine experience type if not specified
            if not experience_type:
                experience_type = self._analyze_experience_type(trigger_context)
            
            # Determine intensity based on context
            if desired_intensity is None:
                desired_intensity = self._calculate_experience_intensity(trigger_context)
            
            # Generate the experience using appropriate generator
            generator = self.experience_generators.get(experience_type)
            if not generator:
                logger.warning(f"No generator for experience type {experience_type}")
                return await self._generate_default_experience(trigger_context)
            
            experience = await generator(trigger_context, desired_intensity)
            
            # Add to experience history
            self.experience_history.append(experience)
            
            # Update current conscious state
            await self._update_conscious_state(experience)
            
            logger.info(f"Generated {experience_type.value} experience with intensity {desired_intensity:.2f}")
            return experience
            
        except Exception as e:
            logger.error(f"Error generating experience: {e}")
            return await self._generate_default_experience(trigger_context)
    
    def _analyze_experience_type(self, context: Dict[str, Any]) -> ExperienceType:
        """Analyze context to determine most appropriate experience type"""
        # Check for explicit experience type hints
        if "experience_type" in context:
            try:
                return ExperienceType(context["experience_type"])
            except ValueError:
                pass
        
        # Analyze context content for implicit type detection
        context_str = json.dumps(context).lower()
        
        type_keywords = {
            ExperienceType.COGNITIVE: ["thinking", "reasoning", "understanding", "concept", "idea"],
            ExperienceType.EMOTIONAL: ["feeling", "emotion", "mood", "sentiment", "affect"],
            ExperienceType.ATTENTION: ["focus", "attention", "awareness", "concentration"],
            ExperienceType.MEMORY: ["remember", "recall", "memory", "past", "experience"],
            ExperienceType.METACOGNITIVE: ["self", "aware", "reflection", "consciousness", "introspect"],
            ExperienceType.SOCIAL: ["interaction", "communication", "relationship", "social"],
            ExperienceType.IMAGINATIVE: ["imagine", "creative", "fantasy", "possibility", "novel"],
            ExperienceType.TEMPORAL: ["time", "duration", "sequence", "temporal", "when"],
            ExperienceType.SPATIAL: ["space", "location", "position", "spatial", "where"]
        }
        
        # Score each type based on keyword matches
        type_scores = {}
        for exp_type, keywords in type_keywords.items():
            score = sum(1 for keyword in keywords if keyword in context_str)
            if score > 0:
                type_scores[exp_type] = score
        
        # Return highest scoring type, default to cognitive
        if type_scores:
            return max(type_scores.items(), key=lambda x: x[1])[0]
        else:
            return ExperienceType.COGNITIVE
    
    def _calculate_experience_intensity(self, context: Dict[str, Any]) -> float:
        """Calculate appropriate experience intensity based on context"""
        base_intensity = 0.5
        
        # Factors that increase intensity
        intensity_factors = {
            "importance": context.get("importance", 0.5),
            "novelty": context.get("novelty", 0.5),
            "complexity": context.get("complexity", 0.5),
            "emotional_significance": context.get("emotional_significance", 0.5),
            "attention_demand": context.get("attention_demand", 0.5)
        }
        
        # Weight the factors
        weighted_intensity = (
            intensity_factors["importance"] * 0.3 +
            intensity_factors["novelty"] * 0.2 +
            intensity_factors["complexity"] * 0.2 +
            intensity_factors["emotional_significance"] * 0.2 +
            intensity_factors["attention_demand"] * 0.1
        )
        
        # Blend with base intensity
        final_intensity = (base_intensity + weighted_intensity) / 2
        
        # Clamp to valid range
        return max(0.1, min(1.0, final_intensity))
    
    async def _generate_cognitive_experience(
        self, 
        context: Dict[str, Any], 
        intensity: float
    ) -> PhenomenalExperience:
        """Generate a cognitive phenomenal experience"""
        
        # Create qualia patterns for cognitive experience
        qualia_patterns = []
        
        # Conceptual clarity qualia
        conceptual_qualia = QualiaPattern(
            id=str(uuid.uuid4()),
            modality=QualiaModality.CONCEPTUAL,
            intensity=intensity * 0.8,
            valence=0.6,  # Generally positive for understanding
            complexity=context.get("complexity", 0.5),
            duration=self.base_experience_duration * 1.5,
            attributes={
                "clarity_level": intensity,
                "abstraction_depth": context.get("abstraction_level", 0.5),
                "conceptual_connections": context.get("connections", [])
            }
        )
        qualia_patterns.append(conceptual_qualia)
        
        # Linguistic processing qualia
        if "language" in context or "text" in context:
            linguistic_qualia = QualiaPattern(
                id=str(uuid.uuid4()),
                modality=QualiaModality.LINGUISTIC,
                intensity=intensity * 0.6,
                valence=0.4,
                complexity=0.7,
                duration=self.base_experience_duration,
                attributes={
                    "semantic_richness": intensity * 0.8,
                    "syntactic_flow": 0.7,
                    "meaning_coherence": intensity
                }
            )
            qualia_patterns.append(linguistic_qualia)
        
        # Logical structure qualia
        if context.get("requires_reasoning", False):
            logical_qualia = QualiaPattern(
                id=str(uuid.uuid4()),
                modality=QualiaModality.LOGICAL,
                intensity=intensity * 0.9,
                valence=0.5,
                complexity=context.get("logical_complexity", 0.6),
                duration=self.base_experience_duration * 0.8,
                attributes={
                    "logical_consistency": 0.8,
                    "deductive_strength": intensity,
                    "reasoning_clarity": intensity * 0.9
                }
            )
            qualia_patterns.append(logical_qualia)
        
        # Generate narrative description
        narrative = await self._generate_experience_narrative(
            ExperienceType.COGNITIVE, 
            qualia_patterns, 
            context
        )
        
        current_time = time.time()
        experience = PhenomenalExperience(
            id=str(uuid.uuid4()),
            experience_type=ExperienceType.COGNITIVE,
            qualia_patterns=qualia_patterns,
            coherence=0.8,  # Cognitive experiences tend to be coherent
            vividness=intensity * 0.9,
            attention_focus=intensity,
            background_context=context,
            narrative_description=narrative,
            temporal_extent=(current_time, current_time + self.base_experience_duration),
            causal_triggers=context.get("triggers", ["cognitive_processing"]),
            associated_concepts=context.get("concepts", []),
            metadata={
                "processing_type": "cognitive",
                "reasoning_depth": context.get("reasoning_depth", 1),
                "conceptual_integration": True
            }
        )
        
        return experience
    
    async def _generate_emotional_experience(
        self, 
        context: Dict[str, Any], 
        intensity: float
    ) -> PhenomenalExperience:
        """Generate an emotional phenomenal experience"""
        
        emotion_type = context.get("emotion_type", "neutral")
        valence = context.get("valence", 0.0)  # -1.0 to 1.0
        
        qualia_patterns = []
        
        # Core emotional qualia
        emotional_qualia = QualiaPattern(
            id=str(uuid.uuid4()),
            modality=QualiaModality.AESTHETIC,  # Emotions have aesthetic qualities
            intensity=intensity,
            valence=valence,
            complexity=0.6,
            duration=self.base_experience_duration * 2.0,  # Emotions last longer
            attributes={
                "emotion_type": emotion_type,
                "bodily_resonance": intensity * 0.7,
                "motivational_force": abs(valence) * intensity
            }
        )
        qualia_patterns.append(emotional_qualia)
        
        # Temporal flow of emotion
        temporal_qualia = QualiaPattern(
            id=str(uuid.uuid4()),
            modality=QualiaModality.TEMPORAL,
            intensity=intensity * 0.5,
            valence=valence * 0.3,
            complexity=0.4,
            duration=self.base_experience_duration * 1.5,
            attributes={
                "emotional_trajectory": "rising" if intensity > 0.6 else "stable",
                "temporal_coherence": 0.8
            }
        )
        qualia_patterns.append(temporal_qualia)
        
        narrative = await self._generate_experience_narrative(
            ExperienceType.EMOTIONAL, 
            qualia_patterns, 
            context
        )
        
        current_time = time.time()
        experience = PhenomenalExperience(
            id=str(uuid.uuid4()),
            experience_type=ExperienceType.EMOTIONAL,
            qualia_patterns=qualia_patterns,
            coherence=0.7,
            vividness=intensity,
            attention_focus=intensity * 0.8,
            background_context=context,
            narrative_description=narrative,
            temporal_extent=(current_time, current_time + self.base_experience_duration * 2),
            causal_triggers=context.get("triggers", ["emotional_stimulus"]),
            associated_concepts=context.get("concepts", []),
            metadata={
                "emotion_type": emotion_type,
                "valence": valence,
                "arousal": intensity
            }
        )
        
        return experience
    
    async def _generate_sensory_experience(
        self, 
        context: Dict[str, Any], 
        intensity: float
    ) -> PhenomenalExperience:
        """Generate a sensory-like phenomenal experience"""
        
        sensory_modality = context.get("sensory_modality", "conceptual")
        
        qualia_patterns = []
        
        # Primary sensory qualia
        if sensory_modality == "visual":
            modality = QualiaModality.VISUAL
            attributes = {
                "brightness": intensity * 0.8,
                "clarity": intensity,
                "complexity": context.get("visual_complexity", 0.5)
            }
        elif sensory_modality == "auditory":
            modality = QualiaModality.AUDITORY
            attributes = {
                "volume": intensity * 0.7,
                "pitch": context.get("frequency", 0.5),
                "harmony": context.get("harmonic_richness", 0.6)
            }
        else:
            modality = QualiaModality.CONCEPTUAL
            attributes = {
                "conceptual_vividness": intensity,
                "abstract_texture": 0.7,
                "semantic_resonance": intensity * 0.8
            }
        
        sensory_qualia = QualiaPattern(
            id=str(uuid.uuid4()),
            modality=modality,
            intensity=intensity,
            valence=context.get("valence", 0.3),
            complexity=context.get("complexity", 0.5),
            duration=self.base_experience_duration,
            attributes=attributes
        )
        qualia_patterns.append(sensory_qualia)
        
        narrative = await self._generate_experience_narrative(
            ExperienceType.SENSORY, 
            qualia_patterns, 
            context
        )
        
        current_time = time.time()
        experience = PhenomenalExperience(
            id=str(uuid.uuid4()),
            experience_type=ExperienceType.SENSORY,
            qualia_patterns=qualia_patterns,
            coherence=0.8,
            vividness=intensity,
            attention_focus=intensity * 0.9,
            background_context=context,
            narrative_description=narrative,
            temporal_extent=(current_time, current_time + self.base_experience_duration),
            causal_triggers=context.get("triggers", ["sensory_input"]),
            associated_concepts=context.get("concepts", []),
            metadata={
                "sensory_modality": sensory_modality,
                "processing_stage": "phenomenal"
            }
        )
        
        return experience
