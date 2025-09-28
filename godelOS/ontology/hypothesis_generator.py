"""
Hypothesis Generator & Evaluator (HGE) for GödelOS.

This module provides mechanisms for generating and evaluating hypotheses
based on existing knowledge and observations.
"""

from typing import Dict, List, Set, Optional, Any, Tuple, Callable
import logging
import random
from collections import defaultdict, Counter
import math
from datetime import datetime
import json
import hashlib

# Setup logging
logger = logging.getLogger(__name__)

class HypothesisGenerator:
    """
    Implements hypothesis generation and evaluation mechanisms.
    
    The HypothesisGenerator is responsible for:
    - Generating hypotheses based on existing knowledge and observations
    - Implementing abductive reasoning mechanisms
    - Evaluating hypotheses based on evidence, parsimony, explanatory power, etc.
    - Ranking hypotheses by plausibility
    - Providing methods for testing hypotheses against new data
    """
    
    def __init__(self, ontology_manager):
        """
        Initialize the HypothesisGenerator.
        
        Args:
            ontology_manager: Reference to the OntologyManager
        """
        self._ontology_manager = ontology_manager
        
        # Generation strategies
        self._generation_strategies = {
            "abductive": self._generate_abductive_hypotheses,
            "analogical": self._generate_analogical_hypotheses,
            "inductive": self._generate_inductive_hypotheses,
            "deductive": self._generate_deductive_hypotheses
        }
        
        # Evaluation metrics
        self._evaluation_metrics = {
            "explanatory_power": self._evaluate_explanatory_power,
            "parsimony": self._evaluate_parsimony,
            "consistency": self._evaluate_consistency,
            "novelty": self._evaluate_novelty,
            "testability": self._evaluate_testability
        }
        
        # Cache for generated hypotheses
        self._hypothesis_cache = {}
        
        # Store historical contexts for analogical reasoning
        self._historical_contexts = []
        
        # Store known rules for deductive reasoning
        self._knowledge_rules = []
        
        # Initialize default rules
        self._initialize_default_rules()
        
        logger.info("HypothesisGenerator initialized")
    
    def _initialize_default_rules(self):
        """Initialize default reasoning rules."""
        self._knowledge_rules = [
            {
                "id": "rule_causality",
                "description": "If A causes B, and B is observed, then A might have occurred",
                "conditions": ["effect_observed"],
                "conclusions": ["cause_likely"],
                "type": "causal"
            },
            {
                "id": "rule_correlation",
                "description": "If A and B frequently co-occur, they might be related",
                "conditions": ["high_cooccurrence"],
                "conclusions": ["potential_relation"],
                "type": "correlation"
            },
            {
                "id": "rule_inheritance",
                "description": "If A has property P, and B is a subclass of A, then B likely has property P",
                "conditions": ["parent_has_property", "is_subclass"],
                "conclusions": ["child_has_property"],
                "type": "inheritance"
            }
        ]
    
    # Hypothesis generation methods
    
    def generate_hypotheses(self, 
                           observations: List[Dict[str, Any]], 
                           context: Dict[str, Any],
                           strategy: str = "abductive",
                           constraints: Optional[Dict[str, Any]] = None,
                           max_hypotheses: int = 5) -> List[Dict[str, Any]]:
        """
        Generate hypotheses based on observations and context.
        
        Args:
            observations: List of observation data
            context: Context information for hypothesis generation
            strategy: Generation strategy to use
            constraints: Optional constraints on the generation process
            max_hypotheses: Maximum number of hypotheses to generate
            
        Returns:
            List[Dict[str, Any]]: List of generated hypotheses
        """
        # Check if this generation request is cached
        cache_key = (str(observations), str(context), strategy, str(constraints), max_hypotheses)
        if cache_key in self._hypothesis_cache:
            logger.info("Using cached hypotheses")
            return self._hypothesis_cache[cache_key]
        
        # Apply the selected generation strategy
        if strategy not in self._generation_strategies:
            logger.warning(f"Unknown generation strategy: {strategy}")
            return []
        
        hypotheses = self._generation_strategies[strategy](observations, context, constraints or {})
        
        # Evaluate and rank hypotheses
        for hypothesis in hypotheses:
            self._evaluate_hypothesis(hypothesis, observations, context)
        
        # Sort by plausibility score
        hypotheses.sort(key=lambda h: h.get("plausibility", 0), reverse=True)
        
        # Limit the number of hypotheses
        hypotheses = hypotheses[:max_hypotheses]
        
        # Cache the result
        self._hypothesis_cache[cache_key] = hypotheses
        
        logger.info(f"Generated {len(hypotheses)} hypotheses using strategy {strategy}")
        return hypotheses
    
    def _generate_abductive_hypotheses(self, 
                                      observations: List[Dict[str, Any]], 
                                      context: Dict[str, Any],
                                      constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate hypotheses using abductive reasoning.
        
        Args:
            observations: List of observation data
            context: Context information for hypothesis generation
            constraints: Constraints on the generation process
            
        Returns:
            List[Dict[str, Any]]: List of generated hypotheses
        """
        hypotheses = []
        
        # Extract relevant concepts from observations
        observed_concepts = self._extract_concepts_from_observations(observations)
        
        # For each observed concept, find potential explanations
        for concept_id in observed_concepts:
            # Get relations that could explain this concept
            causal_relations = self._find_causal_relations(concept_id)
            
            for relation_id, related_concepts in causal_relations.items():
                for related_id in related_concepts:
                    # Create a hypothesis that the related concept caused the observation
                    hypothesis = {
                        "id": f"abductive-{len(hypotheses) + 1}",
                        "type": "abductive",
                        "explanation": f"{related_id} caused {concept_id} via {relation_id}",
                        "causal_concept": related_id,
                        "observed_concept": concept_id,
                        "relation": relation_id,
                        "supporting_evidence": [],
                        "contradicting_evidence": [],
                        "predictions": self._generate_predictions(related_id, context)
                    }
                    
                    # Check if this hypothesis is consistent with constraints
                    if self._is_consistent_with_constraints(hypothesis, constraints):
                        hypotheses.append(hypothesis)
        
        # If no hypotheses were generated, create some fallback hypotheses
        if not hypotheses and observed_concepts:
            # Get some random concepts that might be related
            all_concepts = list(self._ontology_manager.get_all_concepts().keys())
            random_concepts = random.sample(all_concepts, min(3, len(all_concepts)))
            
            for concept_id in random_concepts:
                hypothesis = {
                    "id": f"abductive-fallback-{len(hypotheses) + 1}",
                    "type": "abductive",
                    "explanation": f"{concept_id} might explain the observations",
                    "causal_concept": concept_id,
                    "observed_concepts": observed_concepts,
                    "supporting_evidence": [],
                    "contradicting_evidence": [],
                    "predictions": self._generate_predictions(concept_id, context)
                }
                
                hypotheses.append(hypothesis)
        
        return hypotheses
    
    def _generate_analogical_hypotheses(self, 
                                       observations: List[Dict[str, Any]], 
                                       context: Dict[str, Any],
                                       constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate hypotheses using analogical reasoning.
        
        Args:
            observations: List of observation data
            context: Context information for hypothesis generation
            constraints: Constraints on the generation process
            
        Returns:
            List[Dict[str, Any]]: List of generated hypotheses
        """
        hypotheses = []
        
        # Extract relevant concepts from observations
        observed_concepts = self._extract_concepts_from_observations(observations)
        
        # Find similar contexts in the knowledge base
        similar_contexts = self._find_similar_contexts(context)
        
        for similar_context in similar_contexts:
            # Get the hypotheses that were valid in the similar context
            context_hypotheses = similar_context.get("hypotheses", [])
            
            for context_hypothesis in context_hypotheses:
                # Map the concepts from the similar context to the current context
                mapped_hypothesis = self._map_hypothesis_to_current_context(
                    context_hypothesis, 
                    similar_context, 
                    context, 
                    observed_concepts
                )
                
                if mapped_hypothesis:
                    mapped_hypothesis["id"] = f"analogical-{len(hypotheses) + 1}"
                    mapped_hypothesis["type"] = "analogical"
                    mapped_hypothesis["original_context"] = similar_context.get("id")
                    mapped_hypothesis["original_hypothesis"] = context_hypothesis.get("id")
                    
                    # Check if this hypothesis is consistent with constraints
                    if self._is_consistent_with_constraints(mapped_hypothesis, constraints):
                        hypotheses.append(mapped_hypothesis)
        
        return hypotheses
    
    def _generate_inductive_hypotheses(self, 
                                      observations: List[Dict[str, Any]], 
                                      context: Dict[str, Any],
                                      constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate hypotheses using inductive reasoning.
        
        Args:
            observations: List of observation data
            context: Context information for hypothesis generation
            constraints: Constraints on the generation process
            
        Returns:
            List[Dict[str, Any]]: List of generated hypotheses
        """
        hypotheses = []
        
        # Extract patterns from observations
        patterns = self._extract_patterns_from_observations(observations)
        
        for pattern in patterns:
            # Create a hypothesis based on the pattern
            hypothesis = {
                "id": f"inductive-{len(hypotheses) + 1}",
                "type": "inductive",
                "explanation": f"Pattern: {pattern['description']}",
                "pattern": pattern,
                "supporting_evidence": pattern.get("supporting_observations", []),
                "contradicting_evidence": pattern.get("contradicting_observations", []),
                "predictions": pattern.get("predictions", [])
            }
            
            # Check if this hypothesis is consistent with constraints
            if self._is_consistent_with_constraints(hypothesis, constraints):
                hypotheses.append(hypothesis)
        
        return hypotheses
    
    def _generate_deductive_hypotheses(self, 
                                      observations: List[Dict[str, Any]], 
                                      context: Dict[str, Any],
                                      constraints: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Generate hypotheses using deductive reasoning.
        
        Args:
            observations: List of observation data
            context: Context information for hypothesis generation
            constraints: Constraints on the generation process
            
        Returns:
            List[Dict[str, Any]]: List of generated hypotheses
        """
        hypotheses = []
        
        # Get relevant rules from the knowledge base
        rules = self._get_relevant_rules(observations, context)
        
        for rule in rules:
            # Check if the rule's conditions are satisfied by the observations
            if self._check_rule_conditions(rule, observations):
                # Create a hypothesis based on the rule's conclusion
                hypothesis = {
                    "id": f"deductive-{len(hypotheses) + 1}",
                    "type": "deductive",
                    "explanation": f"Rule: {rule.get('description', 'Unknown rule')}",
                    "rule": rule,
                    "supporting_evidence": observations,
                    "contradicting_evidence": [],
                    "predictions": rule.get("conclusions", [])
                }
                
                # Check if this hypothesis is consistent with constraints
                if self._is_consistent_with_constraints(hypothesis, constraints):
                    hypotheses.append(hypothesis)
        
        return hypotheses
    
    # Hypothesis evaluation methods
    
    def evaluate_hypothesis(self, 
                           hypothesis: Dict[str, Any], 
                           observations: List[Dict[str, Any]], 
                           context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a hypothesis based on observations and context.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            Dict[str, Any]: The evaluated hypothesis with updated scores
        """
        return self._evaluate_hypothesis(hypothesis, observations, context)
    
    def _evaluate_hypothesis(self, 
                            hypothesis: Dict[str, Any], 
                            observations: List[Dict[str, Any]], 
                            context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Internal method to evaluate a hypothesis.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            Dict[str, Any]: The evaluated hypothesis with updated scores
        """
        # Calculate scores for each evaluation metric
        scores = {}
        for metric, evaluator in self._evaluation_metrics.items():
            scores[metric] = evaluator(hypothesis, observations, context)
        
        # Update the hypothesis with the scores
        hypothesis["evaluation_scores"] = scores
        
        # Calculate overall plausibility
        weights = {
            "explanatory_power": 0.4,
            "parsimony": 0.2,
            "consistency": 0.2,
            "novelty": 0.1,
            "testability": 0.1
        }
        
        plausibility = sum(scores.get(metric, 0) * weight for metric, weight in weights.items())
        hypothesis["plausibility"] = plausibility
        
        return hypothesis
    
    def _evaluate_explanatory_power(self, 
                                   hypothesis: Dict[str, Any], 
                                   observations: List[Dict[str, Any]], 
                                   context: Dict[str, Any]) -> float:
        """
        Evaluate how well a hypothesis explains the observations.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            float: The explanatory power score (0.0-1.0)
        """
        # Count how many observations are explained by the hypothesis
        explained_count = 0
        
        for observation in observations:
            if self._is_observation_explained(observation, hypothesis):
                explained_count += 1
        
        # Calculate the score
        if not observations:
            return 0.0
        
        return explained_count / len(observations)
    
    def _evaluate_parsimony(self, 
                           hypothesis: Dict[str, Any], 
                           observations: List[Dict[str, Any]], 
                           context: Dict[str, Any]) -> float:
        """
        Evaluate the parsimony (simplicity) of a hypothesis.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            float: The parsimony score (0.0-1.0, higher is simpler)
        """
        # Calculate complexity based on the number of concepts and relations
        complexity = 0
        
        # Count concepts
        if "causal_concept" in hypothesis:
            complexity += 1
        
        if "observed_concept" in hypothesis:
            complexity += 1
        
        if "observed_concepts" in hypothesis:
            complexity += len(hypothesis["observed_concepts"])
        
        # Count relations
        if "relation" in hypothesis:
            complexity += 1
        
        if "relations" in hypothesis:
            complexity += len(hypothesis["relations"])
        
        # Count additional factors
        if "additional_factors" in hypothesis:
            complexity += len(hypothesis["additional_factors"])
        
        # Calculate parsimony score (inverse of complexity)
        max_complexity = 10  # Maximum expected complexity
        normalized_complexity = min(complexity, max_complexity) / max_complexity
        
        return 1.0 - normalized_complexity
    
    def _evaluate_consistency(self, 
                             hypothesis: Dict[str, Any], 
                             observations: List[Dict[str, Any]], 
                             context: Dict[str, Any]) -> float:
        """
        Evaluate the consistency of a hypothesis with existing knowledge.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            float: The consistency score (0.0-1.0)
        """
        # Check consistency with the ontology
        ontology_consistency = self._check_ontology_consistency(hypothesis)
        
        # Check consistency with the context
        context_consistency = self._check_context_consistency(hypothesis, context)
        
        # Combine the scores
        return (ontology_consistency + context_consistency) / 2.0
    
    def _evaluate_novelty(self, 
                         hypothesis: Dict[str, Any], 
                         observations: List[Dict[str, Any]], 
                         context: Dict[str, Any]) -> float:
        """
        Evaluate the novelty of a hypothesis.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            float: The novelty score (0.0-1.0)
        """
        # Check if similar hypotheses exist in the context
        if "previous_hypotheses" in context:
            similarity_scores = []
            
            for prev_hypothesis in context["previous_hypotheses"]:
                similarity = self._compute_hypothesis_similarity(hypothesis, prev_hypothesis)
                similarity_scores.append(similarity)
            
            if similarity_scores:
                # Novelty is inverse of maximum similarity
                return 1.0 - max(similarity_scores)
        
        # If no previous hypotheses or no similarity could be computed, assume high novelty
        return 0.8
    
    def _evaluate_testability(self, 
                             hypothesis: Dict[str, Any], 
                             observations: List[Dict[str, Any]], 
                             context: Dict[str, Any]) -> float:
        """
        Evaluate how testable a hypothesis is.
        
        Args:
            hypothesis: The hypothesis to evaluate
            observations: List of observation data
            context: Context information for hypothesis evaluation
            
        Returns:
            float: The testability score (0.0-1.0)
        """
        # Check if the hypothesis makes predictions
        if "predictions" not in hypothesis or not hypothesis["predictions"]:
            return 0.0
        
        # Count the number of concrete, testable predictions
        testable_count = 0
        for prediction in hypothesis["predictions"]:
            if self._is_prediction_testable(prediction):
                testable_count += 1
        
        # Calculate the score
        if not hypothesis["predictions"]:
            return 0.0
        
        return testable_count / len(hypothesis["predictions"])
    
    # Hypothesis testing methods
    
    def test_hypothesis(self, 
                       hypothesis: Dict[str, Any], 
                       new_observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a hypothesis against new observations.
        
        Args:
            hypothesis: The hypothesis to test
            new_observations: New observation data to test against
            
        Returns:
            Dict[str, Any]: Test results
        """
        if "predictions" not in hypothesis or not hypothesis["predictions"]:
            return {
                "success": False,
                "reason": "Hypothesis makes no predictions",
                "confirmed_predictions": [],
                "disconfirmed_predictions": [],
                "inconclusive_predictions": []
            }
        
        # Check each prediction against the new observations
        confirmed = []
        disconfirmed = []
        inconclusive = []
        
        for prediction in hypothesis["predictions"]:
            result = self._test_prediction(prediction, new_observations)
            
            if result["status"] == "confirmed":
                confirmed.append({
                    "prediction": prediction,
                    "evidence": result["evidence"]
                })
            elif result["status"] == "disconfirmed":
                disconfirmed.append({
                    "prediction": prediction,
                    "evidence": result["evidence"]
                })
            else:  # inconclusive
                inconclusive.append({
                    "prediction": prediction,
                    "reason": result["reason"]
                })
        
        # Calculate confirmation score
        total_predictions = len(hypothesis["predictions"])
        confirmation_score = len(confirmed) / total_predictions if total_predictions > 0 else 0.0
        
        # Update the hypothesis with the test results
        hypothesis["test_results"] = {
            "confirmed_predictions": confirmed,
            "disconfirmed_predictions": disconfirmed,
            "inconclusive_predictions": inconclusive,
            "confirmation_score": confirmation_score
        }
        
        # Determine overall success
        success = confirmation_score >= 0.5 and not disconfirmed
        
        return {
            "success": success,
            "confirmation_score": confirmation_score,
            "confirmed_predictions": confirmed,
            "disconfirmed_predictions": disconfirmed,
            "inconclusive_predictions": inconclusive
        }
    
    def _test_prediction(self, 
                        prediction: Dict[str, Any], 
                        observations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Test a single prediction against observations.
        
        Args:
            prediction: The prediction to test
            observations: Observation data to test against
            
        Returns:
            Dict[str, Any]: Test result
        """
        # Check if the prediction is testable
        if not self._is_prediction_testable(prediction):
            return {
                "status": "inconclusive",
                "reason": "Prediction is not testable"
            }
        
        # Look for evidence in the observations
        evidence = []
        for observation in observations:
            if self._matches_prediction(observation, prediction):
                evidence.append(observation)
        
        # Determine the result
        if evidence:
            return {
                "status": "confirmed",
                "evidence": evidence
            }
        else:
            # Check if the prediction is expected to be observed in these observations
            if self._should_be_observable(prediction, observations):
                return {
                    "status": "disconfirmed",
                    "evidence": []
                }
            else:
                return {
                    "status": "inconclusive",
                    "reason": "No relevant observations available"
                }
        
        return {
            "status": "inconclusive",
            "reason": "Unable to determine"
        }
    
    # Helper methods
    
    def _extract_concepts_from_observations(self, observations: List[Dict[str, Any]]) -> List[str]:
        """Extract concept IDs from observations."""
        concepts = []
        for observation in observations:
            if "concept_id" in observation:
                concepts.append(observation["concept_id"])
            elif "concepts" in observation:
                concepts.extend(observation["concepts"])
        
        return list(set(concepts))  # Remove duplicates
    
    def _find_causal_relations(self, concept_id: str) -> Dict[str, List[str]]:
        """Find relations that could causally explain a concept."""
        causal_relations = {}
        
        # Get all relations for this concept
        relations = self._ontology_manager._concept_relations.get(concept_id, set())
        
        for relation_id in relations:
            # Check if this is a causal relation
            relation_data = self._ontology_manager._relations.get(relation_id, {})
            if relation_data.get("type") == "causal":
                # Get concepts related to this concept via this relation
                related_concepts = self._ontology_manager.get_related_concepts(concept_id, relation_id)
                causal_relations[relation_id] = related_concepts
        
        return causal_relations
    
    def _generate_predictions(self, concept_id: str, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate predictions based on a concept."""
        predictions = []
        
        # Get properties of the concept
        concept_props = {}
        for prop_id in self._ontology_manager._properties:
            value = self._ontology_manager.get_concept_property(concept_id, prop_id)
            if value is not None:
                concept_props[prop_id] = value
        
        # Generate property-based predictions
        for prop_id, value in concept_props.items():
            prediction = {
                "type": "property",
                "concept_id": concept_id,
                "property_id": prop_id,
                "expected_value": value,
                "confidence": 0.7
            }
            predictions.append(prediction)
        
        # Generate relation-based predictions
        relations = self._ontology_manager._concept_relations.get(concept_id, set())
        for relation_id in relations:
            related_concepts = self._ontology_manager.get_related_concepts(concept_id, relation_id)
            for related_id in related_concepts:
                prediction = {
                    "type": "relation",
                    "source_concept_id": concept_id,
                    "relation_id": relation_id,
                    "target_concept_id": related_id,
                    "confidence": 0.6
                }
                predictions.append(prediction)
        
        return predictions
    
    def _is_consistent_with_constraints(self, hypothesis: Dict[str, Any], constraints: Dict[str, Any]) -> bool:
        """Check if a hypothesis is consistent with constraints."""
        # Check concept constraints
        if "excluded_concepts" in constraints:
            excluded_concepts = constraints["excluded_concepts"]
            
            if "causal_concept" in hypothesis and hypothesis["causal_concept"] in excluded_concepts:
                return False
            
            if "observed_concept" in hypothesis and hypothesis["observed_concept"] in excluded_concepts:
                return False
            
            if "observed_concepts" in hypothesis:
                for concept_id in hypothesis["observed_concepts"]:
                    if concept_id in excluded_concepts:
                        return False
        
        # Check relation constraints
        if "excluded_relations" in constraints and "relation" in hypothesis:
            if hypothesis["relation"] in constraints["excluded_relations"]:
                return False
        
        # Check type constraints
        if "allowed_types" in constraints and "type" in hypothesis:
            if hypothesis["type"] not in constraints["allowed_types"]:
                return False
        
        return True
    
    def _find_similar_contexts(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Find contexts similar to the given context."""
        similar_contexts = []
        
        # Extract key features from the current context
        current_features = self._extract_context_features(context)
        
        # Compare with historical contexts
        for hist_context in self._historical_contexts:
            hist_features = self._extract_context_features(hist_context)
            
            # Calculate similarity score
            similarity = self._calculate_feature_similarity(current_features, hist_features)
            
            if similarity > 0.6:  # Threshold for similarity
                similar_contexts.append({
                    "id": hist_context.get("id", f"context_{len(similar_contexts)}"),
                    "similarity": similarity,
                    "features": hist_features,
                    "hypotheses": hist_context.get("hypotheses", []),
                    "timestamp": hist_context.get("timestamp", None)
                })
        
        # Sort by similarity
        similar_contexts.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Store current context for future use
        if context not in self._historical_contexts:
            context["timestamp"] = datetime.now().isoformat()
            self._historical_contexts.append(context.copy())
        
        return similar_contexts[:5]  # Return top 5 similar contexts
    
    def _extract_context_features(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key features from a context."""
        features = {
            "concepts": set(),
            "relations": set(),
            "properties": {},
            "domain": context.get("domain", "general"),
            "complexity": 0
        }
        
        # Extract concepts
        if "concepts" in context:
            features["concepts"] = set(context["concepts"])
        
        # Extract relations
        if "relations" in context:
            features["relations"] = set(context["relations"])
        
        # Extract properties
        if "properties" in context:
            features["properties"] = context["properties"].copy()
        
        # Calculate complexity
        features["complexity"] = len(features["concepts"]) + len(features["relations"])
        
        # Extract observation types if present
        if "observations" in context:
            features["observation_types"] = set()
            for obs in context["observations"]:
                if "type" in obs:
                    features["observation_types"].add(obs["type"])
        
        return features
    
    def _calculate_feature_similarity(self, features1: Dict[str, Any], features2: Dict[str, Any]) -> float:
        """Calculate similarity between two feature sets."""
        similarity_scores = []
        
        # Concept similarity (Jaccard index)
        if "concepts" in features1 and "concepts" in features2:
            concepts1 = features1["concepts"]
            concepts2 = features2["concepts"]
            if concepts1 or concepts2:
                intersection = len(concepts1 & concepts2)
                union = len(concepts1 | concepts2)
                similarity_scores.append(intersection / union if union > 0 else 0)
        
        # Relation similarity
        if "relations" in features1 and "relations" in features2:
            relations1 = features1["relations"]
            relations2 = features2["relations"]
            if relations1 or relations2:
                intersection = len(relations1 & relations2)
                union = len(relations1 | relations2)
                similarity_scores.append(intersection / union if union > 0 else 0)
        
        # Domain similarity
        if features1.get("domain") == features2.get("domain"):
            similarity_scores.append(1.0)
        else:
            similarity_scores.append(0.0)
        
        # Complexity similarity (normalized difference)
        complexity1 = features1.get("complexity", 0)
        complexity2 = features2.get("complexity", 0)
        max_complexity = max(complexity1, complexity2)
        if max_complexity > 0:
            complexity_sim = 1.0 - abs(complexity1 - complexity2) / max_complexity
            similarity_scores.append(complexity_sim)
        
        # Property similarity
        if "properties" in features1 and "properties" in features2:
            props1 = features1["properties"]
            props2 = features2["properties"]
            common_props = set(props1.keys()) & set(props2.keys())
            
            if common_props:
                matching_props = sum(1 for p in common_props if props1[p] == props2[p])
                similarity_scores.append(matching_props / len(common_props))
        
        # Calculate weighted average
        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
    
    def _map_hypothesis_to_current_context(self, 
                                          hypothesis: Dict[str, Any], 
                                          original_context: Dict[str, Any],
                                          current_context: Dict[str, Any],
                                          observed_concepts: List[str]) -> Optional[Dict[str, Any]]:
        """Map a hypothesis from a similar context to the current context."""
        # Extract concept mappings between contexts
        concept_mapping = self._find_concept_mappings(original_context, current_context)
        
        if not concept_mapping:
            return None
        
        # Create a new hypothesis with mapped concepts
        mapped_hypothesis = {
            "explanation": hypothesis.get("explanation", ""),
            "supporting_evidence": [],
            "contradicting_evidence": [],
            "predictions": []
        }
        
        # Map causal concept if present
        if "causal_concept" in hypothesis:
            original_concept = hypothesis["causal_concept"]
            if original_concept in concept_mapping:
                mapped_hypothesis["causal_concept"] = concept_mapping[original_concept]
            else:
                # Try to find a similar concept in the current context
                similar_concept = self._find_similar_concept(original_concept, observed_concepts)
                if similar_concept:
                    mapped_hypothesis["causal_concept"] = similar_concept
                else:
                    return None  # Cannot map the hypothesis
        
        # Map observed concepts
        if "observed_concept" in hypothesis:
            original_concept = hypothesis["observed_concept"]
            if original_concept in concept_mapping:
                mapped_hypothesis["observed_concept"] = concept_mapping[original_concept]
            elif original_concept in observed_concepts:
                mapped_hypothesis["observed_concept"] = original_concept
        
        if "observed_concepts" in hypothesis:
            mapped_observed = []
            for concept in hypothesis["observed_concepts"]:
                if concept in concept_mapping:
                    mapped_observed.append(concept_mapping[concept])
                elif concept in observed_concepts:
                    mapped_observed.append(concept)
            
            if mapped_observed:
                mapped_hypothesis["observed_concepts"] = mapped_observed
        
        # Map relations
        if "relation" in hypothesis:
            mapped_hypothesis["relation"] = hypothesis["relation"]  # Relations are typically preserved
        
        # Update explanation with mapped concepts
        explanation = hypothesis.get("explanation", "")
        for original, mapped in concept_mapping.items():
            explanation = explanation.replace(original, mapped)
        mapped_hypothesis["explanation"] = f"[Analogical] {explanation}"
        
        # Generate new predictions based on mapped concepts
        if "causal_concept" in mapped_hypothesis:
            mapped_hypothesis["predictions"] = self._generate_predictions(
                mapped_hypothesis["causal_concept"], 
                current_context
            )
        
        return mapped_hypothesis
    
    def _find_concept_mappings(self, context1: Dict[str, Any], context2: Dict[str, Any]) -> Dict[str, str]:
        """Find mappings between concepts in two contexts."""
        mappings = {}
        
        # Extract concepts from both contexts
        concepts1 = set(context1.get("concepts", []))
        concepts2 = set(context2.get("concepts", []))
        
        # Direct matches (same concept names)
        direct_matches = concepts1 & concepts2
        for concept in direct_matches:
            mappings[concept] = concept
        
        # Find mappings based on similar properties
        for c1 in concepts1 - direct_matches:
            best_match = None
            best_score = 0
            
            for c2 in concepts2 - direct_matches:
                # Compare properties
                props1 = self._get_concept_properties(c1)
                props2 = self._get_concept_properties(c2)
                
                # Calculate property similarity
                common_props = set(props1.keys()) & set(props2.keys())
                if common_props:
                    matching_values = sum(1 for p in common_props if props1[p] == props2[p])
                    score = matching_values / len(common_props)
                    
                    if score > best_score:
                        best_score = score
                        best_match = c2
            
            if best_match and best_score > 0.5:  # Threshold for accepting a mapping
                mappings[c1] = best_match
        
        return mappings
    
    def _get_concept_properties(self, concept_id: str) -> Dict[str, Any]:
        """Get all properties of a concept."""
        properties = {}
        
        for prop_id in self._ontology_manager._properties:
            value = self._ontology_manager.get_concept_property(concept_id, prop_id)
            if value is not None:
                properties[prop_id] = value
        
        return properties
    
    def _find_similar_concept(self, concept_id: str, available_concepts: List[str]) -> Optional[str]:
        """Find a similar concept from available concepts."""
        if not available_concepts:
            return None
        
        # Get properties of the target concept
        target_props = self._get_concept_properties(concept_id)
        
        best_match = None
        best_score = 0
        
        for candidate in available_concepts:
            candidate_props = self._get_concept_properties(candidate)
            
            # Calculate similarity
            common_props = set(target_props.keys()) & set(candidate_props.keys())
            if common_props:
                matching_values = sum(1 for p in common_props if target_props[p] == candidate_props[p])
                score = matching_values / len(common_props)
                
                if score > best_score:
                    best_score = score
                    best_match = candidate
        
        return best_match if best_score > 0.3 else None
    
    def _extract_patterns_from_observations(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract patterns from observations."""
        patterns = []
        
        # Pattern 1: Frequency patterns
        frequency_pattern = self._extract_frequency_patterns(observations)
        if frequency_pattern:
            patterns.extend(frequency_pattern)
        
        # Pattern 2: Sequential patterns
        sequential_pattern = self._extract_sequential_patterns(observations)
        if sequential_pattern:
            patterns.extend(sequential_pattern)
        
        # Pattern 3: Co-occurrence patterns
        cooccurrence_pattern = self._extract_cooccurrence_patterns(observations)
        if cooccurrence_pattern:
            patterns.extend(cooccurrence_pattern)
        
        # Pattern 4: Property patterns
        property_pattern = self._extract_property_patterns(observations)
        if property_pattern:
            patterns.extend(property_pattern)
        
        return patterns
    
    def _extract_frequency_patterns(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract frequency-based patterns from observations."""
        patterns = []
        
        # Count concept frequencies
        concept_counter = Counter()
        for obs in observations:
            if "concept_id" in obs:
                concept_counter[obs["concept_id"]] += 1
            elif "concepts" in obs:
                for concept in obs["concepts"]:
                    concept_counter[concept] += 1
        
        # Identify high-frequency concepts
        if concept_counter:
            total_observations = len(observations)
            for concept, count in concept_counter.most_common(3):
                frequency = count / total_observations
                if frequency > 0.3:  # Threshold for high frequency
                    pattern = {
                        "type": "frequency",
                        "description": f"Concept '{concept}' appears frequently ({count}/{total_observations})",
                        "concept": concept,
                        "frequency": frequency,
                        "supporting_observations": [obs for obs in observations 
                                                   if concept in obs.get("concepts", []) or 
                                                   obs.get("concept_id") == concept],
                        "contradicting_observations": [],
                        "predictions": [
                            {
                                "type": "frequency_continuation",
                                "concept_id": concept,
                                "expected_frequency": frequency,
                                "confidence": min(0.9, frequency + 0.3)
                            }
                        ]
                    }
                    patterns.append(pattern)
        
        return patterns
    
    def _extract_sequential_patterns(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract sequential patterns from observations."""
        patterns = []
        
        # Sort observations by timestamp if available
        sorted_obs = observations.copy()
        if all("timestamp" in obs for obs in sorted_obs):
            sorted_obs.sort(key=lambda x: x["timestamp"])
        
        # Look for sequences of concepts
        if len(sorted_obs) >= 2:
            sequences = defaultdict(int)
            
            for i in range(len(sorted_obs) - 1):
                current_concepts = self._extract_concepts_from_observation(sorted_obs[i])
                next_concepts = self._extract_concepts_from_observation(sorted_obs[i + 1])
                
                for c1 in current_concepts:
                    for c2 in next_concepts:
                        sequences[(c1, c2)] += 1
            
            # Identify frequent sequences
            for (c1, c2), count in sequences.items():
                if count >= 2:  # Minimum sequence frequency
                    pattern = {
                        "type": "sequential",
                        "description": f"Concept '{c1}' frequently followed by '{c2}'",
                        "sequence": [c1, c2],
                        "frequency": count,
                        "supporting_observations": [],
                        "contradicting_observations": [],
                        "predictions": [
                            {
                                "type": "sequence_continuation",
                                "given": c1,
                                "expected": c2,
                                "confidence": min(0.8, count / len(sorted_obs))
                            }
                        ]
                    }
                    patterns.append(pattern)
        
        return patterns
    
    def _extract_cooccurrence_patterns(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract co-occurrence patterns from observations."""
        patterns = []
        
        # Track co-occurrences
        cooccurrences = defaultdict(int)
        individual_counts = defaultdict(int)
        
        for obs in observations:
            concepts = self._extract_concepts_from_observation(obs)
            
            # Count individual occurrences
            for concept in concepts:
                individual_counts[concept] += 1
            
            # Count co-occurrences
            concept_list = list(concepts)
            for i in range(len(concept_list)):
                for j in range(i + 1, len(concept_list)):
                    pair = tuple(sorted([concept_list[i], concept_list[j]]))
                    cooccurrences[pair] += 1
        
        # Calculate co-occurrence strength
        for (c1, c2), count in cooccurrences.items():
            if count >= 2:  # Minimum co-occurrence count
                # Calculate Jaccard similarity
                union_count = individual_counts[c1] + individual_counts[c2] - count
                jaccard = count / union_count if union_count > 0 else 0
                
                if jaccard > 0.3:  # Threshold for significant co-occurrence
                    pattern = {
                        "type": "cooccurrence",
                        "description": f"Concepts '{c1}' and '{c2}' frequently co-occur",
                        "concepts": [c1, c2],
                        "cooccurrence_count": count,
                        "jaccard_similarity": jaccard,
                        "supporting_observations": [obs for obs in observations 
                                                   if c1 in self._extract_concepts_from_observation(obs) and 
                                                   c2 in self._extract_concepts_from_observation(obs)],
                        "contradicting_observations": [],
                        "predictions": [
                            {
                                "type": "cooccurrence_prediction",
                                "if_observed": c1,
                                "expect_also": c2,
                                "confidence": jaccard
                            },
                            {
                                "type": "cooccurrence_prediction",
                                "if_observed": c2,
                                "expect_also": c1,
                                "confidence": jaccard
                            }
                        ]
                    }
                    patterns.append(pattern)
        
        return patterns
    
    def _extract_property_patterns(self, observations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract property-based patterns from observations."""
        patterns = []
        
        # Track property values across observations
        property_values = defaultdict(list)
        
        for obs in observations:
            if "properties" in obs:
                for prop, value in obs["properties"].items():
                    property_values[prop].append(value)
        
        # Analyze property patterns
        for prop, values in property_values.items():
            if len(values) >= 3:  # Minimum number of values for pattern detection
                # Check for constant values
                unique_values = set(values)
                if len(unique_values) == 1:
                    pattern = {
                        "type": "property_constant",
                        "description": f"Property '{prop}' is consistently '{unique_values.pop()}'",
                        "property": prop,
                        "value": list(unique_values)[0] if unique_values else values[0],
                        "supporting_observations": [obs for obs in observations 
                                                   if obs.get("properties", {}).get(prop) == values[0]],
                        "contradicting_observations": [],
                        "predictions": [
                            {
                                "type": "property_value",
                                "property_id": prop,
                                "expected_value": values[0],
                                "confidence": 0.9
                            }
                        ]
                    }
                    patterns.append(pattern)
                
                # Check for increasing/decreasing trends (for numeric values)
                elif all(isinstance(v, (int, float)) for v in values):
                    numeric_values = [float(v) for v in values]
                    if all(numeric_values[i] <= numeric_values[i+1] for i in range(len(numeric_values)-1)):
                        pattern = {
                            "type": "property_trend",
                            "description": f"Property '{prop}' shows increasing trend",
                            "property": prop,
                            "trend": "increasing",
                            "values": numeric_values,
                            "supporting_observations": observations,
                            "contradicting_observations": [],
                            "predictions": [
                                {
                                    "type": "property_trend_continuation",
                                    "property_id": prop,
                                    "expected_trend": "increasing",
                                    "confidence": 0.7
                                }
                            ]
                        }
                        patterns.append(pattern)
                    elif all(numeric_values[i] >= numeric_values[i+1] for i in range(len(numeric_values)-1)):
                        pattern = {
                            "type": "property_trend",
                            "description": f"Property '{prop}' shows decreasing trend",
                            "property": prop,
                            "trend": "decreasing",
                            "values": numeric_values,
                            "supporting_observations": observations,
                            "contradicting_observations": [],
                            "predictions": [
                                {
                                    "type": "property_trend_continuation",
                                    "property_id": prop,
                                    "expected_trend": "decreasing",
                                    "confidence": 0.7
                                }
                            ]
                        }
                        patterns.append(pattern)
        
        return patterns
    
    def _extract_concepts_from_observation(self, observation: Dict[str, Any]) -> Set[str]:
        """Extract concept IDs from a single observation."""
        concepts = set()
        
        if "concept_id" in observation:
            concepts.add(observation["concept_id"])
        
        if "concepts" in observation:
            concepts.update(observation["concepts"])
        
        return concepts
    
    def _get_relevant_rules(self, observations: List[Dict[str, Any]], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get rules relevant to the observations and context."""
        relevant_rules = []
        
        # Extract features from observations and context
        observed_concepts = self._extract_concepts_from_observations(observations)
        observed_properties = set()
        observed_relations = set()
        
        for obs in observations:
            if "properties" in obs:
                observed_properties.update(obs["properties"].keys())
            if "relations" in obs:
                observed_relations.update(obs["relations"])
        
        # Check each rule for relevance
        for rule in self._knowledge_rules:
            relevance_score = 0
            
            # Check if rule type matches context
            if "type" in context and rule.get("type") == context["type"]:
                relevance_score += 0.5
            
            # Check if rule conditions might be satisfiable
            conditions = rule.get("conditions", [])
            for condition in conditions:
                if self._is_condition_potentially_satisfiable(condition, observed_concepts, observed_properties, observed_relations):
                    relevance_score += 0.3
            
            # Add rule if it has some relevance
            if relevance_score > 0:
                relevant_rules.append(rule)
        
        # Also generate dynamic rules based on ontology
        dynamic_rules = self._generate_dynamic_rules(observed_concepts, context)
        relevant_rules.extend(dynamic_rules)
        
        return relevant_rules
    
    def _is_condition_potentially_satisfiable(self, condition: str, concepts: List[str], 
                                             properties: Set[str], relations: Set[str]) -> bool:
        """Check if a condition could potentially be satisfied."""
        # Simple keyword matching for now
        if "effect_observed" in condition:
            return len(concepts) > 0
        elif "high_cooccurrence" in condition:
            return len(concepts) >= 2
        elif "parent_has_property" in condition or "has_property" in condition:
            return len(properties) > 0
        elif "is_subclass" in condition or "subclass" in condition:
            return any(self._ontology_manager.is_subclass_of(c, None) for c in concepts if c)
        
        return False
    
    def _generate_dynamic_rules(self, concepts: List[str], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate dynamic rules based on the ontology."""
        dynamic_rules = []
        
        for concept in concepts:
            # Generate inheritance rules
            parent_concepts = self._ontology_manager.get_parent_concepts(concept)
            for parent in parent_concepts:
                rule = {
                    "id": f"dynamic_inheritance_{concept}_{parent}",
                    "description": f"Properties of '{parent}' are inherited by '{concept}'",
                    "conditions": [f"is_instance_of({concept}, {parent})"],
                    "conclusions": [f"inherits_properties({concept}, {parent})"],
                    "type": "inheritance",
                    "source": "dynamic"
                }
                dynamic_rules.append(rule)
            
            # Generate relation-based rules
            relations = self._ontology_manager._concept_relations.get(concept, set())
            for relation_id in relations:
                related_concepts = self._ontology_manager.get_related_concepts(concept, relation_id)
                for related in related_concepts:
                    rule = {
                        "id": f"dynamic_relation_{concept}_{relation_id}_{related}",
                        "description": f"'{concept}' is related to '{related}' via '{relation_id}'",
                        "conditions": [f"exists({concept})"],
                        "conclusions": [f"likely_exists({related})"],
                        "type": "relational",
                        "source": "dynamic"
                    }
                    dynamic_rules.append(rule)
        
        return dynamic_rules
    
    def _check_rule_conditions(self, rule: Dict[str, Any], observations: List[Dict[str, Any]]) -> bool:
        """Check if a rule's conditions are satisfied by the observations."""
        conditions = rule.get("conditions", [])
        
        if not conditions:
            return False
        
        # Extract observation features
        observed_concepts = self._extract_concepts_from_observations(observations)
        observed_properties = {}
        observed_relations = set()
        
        for obs in observations:
            if "properties" in obs:
                observed_properties.update(obs["properties"])
            if "relations" in obs:
                observed_relations.update(obs["relations"])
        
        # Check each condition
        for condition in conditions:
            if not self._evaluate_condition(condition, observed_concepts, observed_properties, observed_relations):
                return False
        
        return True
    
    def _evaluate_condition(self, condition: str, concepts: List[str], 
                          properties: Dict[str, Any], relations: Set[str]) -> bool:
        """Evaluate a single condition."""
        # Parse different condition types
        if "effect_observed" in condition:
            # Check if any concept could be an effect
            return len(concepts) > 0
        
        elif "high_cooccurrence" in condition:
            # Check if there are multiple concepts (potential co-occurrence)
            return len(concepts) >= 2
        
        elif "parent_has_property" in condition:
            # Check if any concept has a parent with properties
            for concept in concepts:
                parents = self._ontology_manager.get_parent_concepts(concept)
                for parent in parents:
                    parent_props = self._get_concept_properties(parent)
                    if parent_props:
                        return True
            return False
        
        elif "is_subclass" in condition:
            # Check if any concept is a subclass
            for concept in concepts:
                if self._ontology_manager.get_parent_concepts(concept):
                    return True
            return False
        
        elif "is_instance_of" in condition:
            # Extract the instance and class from the condition
            # Format: is_instance_of(instance, class)
            if "(" in condition and ")" in condition:
                args = condition[condition.index("(")+1:condition.index(")")].split(",")
                if len(args) == 2:
                    instance = args[0].strip()
                    class_name = args[1].strip()
                    return instance in concepts and self._ontology_manager.is_subclass_of(instance, class_name)
        
        elif "exists" in condition:
            # Check if a concept exists
            if "(" in condition and ")" in condition:
                concept = condition[condition.index("(")+1:condition.index(")")].strip()
                return concept in concepts
        
        # Default: condition not satisfied
        return False
    
    def _is_observation_explained(self, observation: Dict[str, Any], hypothesis: Dict[str, Any]) -> bool:
        """Check if an observation is explained by a hypothesis."""
        # Extract observation features
        obs_concepts = self._extract_concepts_from_observation(observation)
        obs_properties = observation.get("properties", {})
        
        # Check different hypothesis types
        if hypothesis.get("type") == "abductive":
            # Check if the hypothesis explains the observed concept
            if "observed_concept" in hypothesis:
                if hypothesis["observed_concept"] in obs_concepts:
                    # Check if the causal concept could lead to this observation
                    if "causal_concept" in hypothesis:
                        # Check if there's a causal relation
                        return self._check_causal_connection(
                            hypothesis["causal_concept"],
                            hypothesis["observed_concept"]
                        )
            
            if "observed_concepts" in hypothesis:
                # Check if any of the hypothesis's observed concepts match
                return bool(set(hypothesis["observed_concepts"]) & obs_concepts)
        
        elif hypothesis.get("type") == "inductive":
            # Check if the observation fits the pattern
            if "pattern" in hypothesis:
                pattern = hypothesis["pattern"]
                
                if pattern.get("type") == "frequency":
                    return pattern.get("concept") in obs_concepts
                
                elif pattern.get("type") == "property_constant":
                    prop = pattern.get("property")
                    expected_value = pattern.get("value")
                    return obs_properties.get(prop) == expected_value
                
                elif pattern.get("type") == "cooccurrence":
                    pattern_concepts = set(pattern.get("concepts", []))
                    return pattern_concepts.issubset(obs_concepts)
        
        elif hypothesis.get("type") == "deductive":
            # Check if the observation matches the rule's conclusions
            if "rule" in hypothesis:
                conclusions = hypothesis["rule"].get("conclusions", [])
                for conclusion in conclusions:
                    if self._matches_conclusion(observation, conclusion):
                        return True
        
        elif hypothesis.get("type") == "analogical":
            # Check if the mapped concepts match the observation
            if "observed_concept" in hypothesis:
                return hypothesis["observed_concept"] in obs_concepts
            if "observed_concepts" in hypothesis:
                return bool(set(hypothesis["observed_concepts"]) & obs_concepts)
        
        return False
    
    def _check_causal_connection(self, cause_concept: str, effect_concept: str) -> bool:
        """Check if there's a causal connection between two concepts."""
        # Check direct causal relations
        relations = self._ontology_manager._concept_relations.get(cause_concept, set())
        
        for relation_id in relations:
            relation_data = self._ontology_manager._relations.get(relation_id, {})
            if relation_data.get("type") == "causal":
                related_concepts = self._ontology_manager.get_related_concepts(cause_concept, relation_id)
                if effect_concept in related_concepts:
                    return True
        
        # Check indirect causal chains (limited depth)
        visited = set()
        queue = [(cause_concept, 0)]
        max_depth = 2
        
        while queue:
            current_concept, depth = queue.pop(0)
            
            if depth > max_depth:
                continue
            
            if current_concept in visited:
                continue
            
            visited.add(current_concept)
            
            # Get causal relations from current concept
            current_relations = self._ontology_manager._concept_relations.get(current_concept, set())
            
            for relation_id in current_relations:
                relation_data = self._ontology_manager._relations.get(relation_id, {})
                if relation_data.get("type") == "causal":
                    related_concepts = self._ontology_manager.get_related_concepts(current_concept, relation_id)
                    
                    if effect_concept in related_concepts:
                        return True
                    
                    # Add to queue for further exploration
                    for related in related_concepts:
                        if related not in visited:
                            queue.append((related, depth + 1))
        
        return False
    
    def _matches_conclusion(self, observation: Dict[str, Any], conclusion: str) -> bool:
        """Check if an observation matches a rule conclusion."""
        obs_concepts = self._extract_concepts_from_observation(observation)
        
        # Parse conclusion
        if "likely_exists" in conclusion:
            if "(" in conclusion and ")" in conclusion:
                concept = conclusion[conclusion.index("(")+1:conclusion.index(")")].strip()
                return concept in obs_concepts
        
        elif "inherits_properties" in conclusion:
            # Check if the observation shows inherited properties
            return "inherited_properties" in observation or "parent_concept" in observation
        
        elif "cause_likely" in conclusion:
            # Check if the observation indicates a cause
            return "cause" in observation or "causal_factor" in observation
        
        elif "potential_relation" in conclusion:
            # Check if the observation shows relations
            return "relations" in observation and len(observation["relations"]) > 0
        
        elif "child_has_property" in conclusion:
            # Check if properties are present
            return "properties" in observation and len(observation["properties"]) > 0
        
        return False
    
    def _check_ontology_consistency(self, hypothesis: Dict[str, Any]) -> float:
        """Check the consistency of a hypothesis with the ontology."""
        consistency_score = 1.0
        
        # Check if concepts exist in ontology
        concepts_to_check = []
        
        if "causal_concept" in hypothesis:
            concepts_to_check.append(hypothesis["causal_concept"])
        
        if "observed_concept" in hypothesis:
            concepts_to_check.append(hypothesis["observed_concept"])
        
        if "observed_concepts" in hypothesis:
            concepts_to_check.extend(hypothesis["observed_concepts"])
        
        for concept_id in concepts_to_check:
            if concept_id not in self._ontology_manager._concepts:
                consistency_score -= 0.2
        
        # Check if relations are valid
        if "relation" in hypothesis:
            relation_id = hypothesis["relation"]
            if relation_id not in self._ontology_manager._relations:
                consistency_score -= 0.3
            else:
                # Check if the relation connects the right concepts
                if "causal_concept" in hypothesis and "observed_concept" in hypothesis:
                    related = self._ontology_manager.get_related_concepts(
                        hypothesis["causal_concept"], 
                        relation_id
                    )
                    if hypothesis["observed_concept"] not in related:
                        consistency_score -= 0.2
        
        # Check pattern consistency
        if "pattern" in hypothesis:
            pattern = hypothesis["pattern"]
            if pattern.get("type") == "property_constant":
                prop = pattern.get("property")
                if prop and prop not in self._ontology_manager._properties:
                    consistency_score -= 0.2
        
        # Check rule consistency
        if "rule" in hypothesis:
            rule = hypothesis["rule"]
            # Verify that rule conditions and conclusions use valid concepts
            # This is a simplified check
            if rule.get("source") != "dynamic" and rule not in self._knowledge_rules:
                consistency_score -= 0.1
        
        return max(0.0, consistency_score)
    
    def _check_context_consistency(self, hypothesis: Dict[str, Any], context: Dict[str, Any]) -> float:
        """Check the consistency of a hypothesis with the context."""
        consistency_score = 1.0
        
        # Check domain consistency
        if "domain" in context:
            domain = context["domain"]
            
            # Check if hypothesis concepts belong to the domain
            concepts_to_check = []
            if "causal_concept" in hypothesis:
                concepts_to_check.append(hypothesis["causal_concept"])
            if "observed_concept" in hypothesis:
                concepts_to_check.append(hypothesis["observed_concept"])
            if "observed_concepts" in hypothesis:
                concepts_to_check.extend(hypothesis["observed_concepts"])
            
            for concept_id in concepts_to_check:
                concept_data = self._ontology_manager._concepts.get(concept_id, {})
                concept_domain = concept_data.get("domain", "general")
                
                if concept_domain != domain and concept_domain != "general":
                    consistency_score -= 0.1
        
        # Check temporal consistency
        if "timestamp" in context and "predictions" in hypothesis:
            # Check if predictions are temporally consistent
            for prediction in hypothesis["predictions"]:
                if "timestamp" in prediction:
                    pred_time = prediction["timestamp"]
                    context_time = context["timestamp"]
                    
                    # Simple check: predictions should be for the future
                    if isinstance(pred_time, str) and isinstance(context_time, str):
                        if pred_time < context_time:
                            consistency_score -= 0.1
        
        # Check constraint consistency
        if "constraints" in context:
            constraints = context["constraints"]
            
            # Check excluded concepts
            if "excluded_concepts" in constraints:
                excluded = set(constraints["excluded_concepts"])
                
                if "causal_concept" in hypothesis and hypothesis["causal_concept"] in excluded:
                    consistency_score -= 0.3
                
                if "observed_concept" in hypothesis and hypothesis["observed_concept"] in excluded:
                    consistency_score -= 0.3
        
        # Check if hypothesis contradicts known facts in context
        if "known_facts" in context:
            for fact in context["known_facts"]:
                if self._contradicts_fact(hypothesis, fact):
                    consistency_score -= 0.2
        
        return max(0.0, consistency_score)
    
    def _contradicts_fact(self, hypothesis: Dict[str, Any], fact: Dict[str, Any]) -> bool:
        """Check if a hypothesis contradicts a known fact."""
        # Check if hypothesis makes contrary claims
        if "predictions" in hypothesis:
            for prediction in hypothesis["predictions"]:
                if prediction.get("type") == "property" and fact.get("type") == "property":
                    if (prediction.get("property_id") == fact.get("property_id") and
                        prediction.get("concept_id") == fact.get("concept_id") and
                        prediction.get("expected_value") != fact.get("value")):
                        return True
        
        # Check if hypothesis contradicts causal facts
        if hypothesis.get("type") == "abductive" and fact.get("type") == "causal":
            if ("causal_concept" in hypothesis and "observed_concept" in hypothesis and
                fact.get("cause") == hypothesis["observed_concept"] and
                fact.get("effect") == hypothesis["causal_concept"]):
                # Hypothesis reverses known causality
                return True
        
        return False
    
    def _compute_hypothesis_similarity(self, hypothesis1: Dict[str, Any], hypothesis2: Dict[str, Any]) -> float:
        """Compute the similarity between two hypotheses."""
        similarity_scores = []
        
        # Type similarity
        if hypothesis1.get("type") == hypothesis2.get("type"):
            similarity_scores.append(1.0)
        else:
            similarity_scores.append(0.0)
        
        # Concept similarity
        concepts1 = set()
        concepts2 = set()
        
        for h, c_set in [(hypothesis1, concepts1), (hypothesis2, concepts2)]:
            if "causal_concept" in h:
                c_set.add(h["causal_concept"])
            if "observed_concept" in h:
                c_set.add(h["observed_concept"])
            if "observed_concepts" in h:
                c_set.update(h["observed_concepts"])
        
        if concepts1 or concepts2:
            intersection = len(concepts1 & concepts2)
            union = len(concepts1 | concepts2)
            similarity_scores.append(intersection / union if union > 0 else 0)
        
        # Relation similarity
        if "relation" in hypothesis1 and "relation" in hypothesis2:
            if hypothesis1["relation"] == hypothesis2["relation"]:
                similarity_scores.append(1.0)
            else:
                similarity_scores.append(0.0)
        
        # Pattern similarity
        if "pattern" in hypothesis1 and "pattern" in hypothesis2:
            pattern1 = hypothesis1["pattern"]
            pattern2 = hypothesis2["pattern"]
            
            if pattern1.get("type") == pattern2.get("type"):
                pattern_sim = 0.5
                
                # Additional similarity based on pattern details
                if pattern1.get("concept") == pattern2.get("concept"):
                    pattern_sim += 0.25
                if pattern1.get("property") == pattern2.get("property"):
                    pattern_sim += 0.25
                
                similarity_scores.append(pattern_sim)
            else:
                similarity_scores.append(0.0)
        
        # Prediction similarity
        if "predictions" in hypothesis1 and "predictions" in hypothesis2:
            pred1_set = {self._prediction_signature(p) for p in hypothesis1["predictions"]}
            pred2_set = {self._prediction_signature(p) for p in hypothesis2["predictions"]}
            
            if pred1_set or pred2_set:
                intersection = len(pred1_set & pred2_set)
                union = len(pred1_set | pred2_set)
                similarity_scores.append(intersection / union if union > 0 else 0)
        
        # Calculate weighted average
        return sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
    
    def _prediction_signature(self, prediction: Dict[str, Any]) -> str:
        """Generate a signature for a prediction for comparison."""
        sig_parts = [
            prediction.get("type", ""),
            str(prediction.get("concept_id", "")),
            str(prediction.get("property_id", "")),
            str(prediction.get("expected_value", "")),
            str(prediction.get("relation_id", ""))
        ]
        return "|".join(sig_parts)
    
    def _is_prediction_testable(self, prediction: Dict[str, Any]) -> bool:
        """Check if a prediction is testable."""
        pred_type = prediction.get("type")
        
        # Property predictions are testable if they specify what to check
        if pred_type == "property":
            return ("concept_id" in prediction and 
                   "property_id" in prediction and 
                   "expected_value" in prediction)
        
        # Relation predictions are testable if they specify the relation
        elif pred_type == "relation":
            return ("source_concept_id" in prediction and 
                   "relation_id" in prediction and 
                   "target_concept_id" in prediction)
        
        # Frequency predictions are testable
        elif pred_type in ["frequency_continuation", "property_value", "cooccurrence_prediction"]:
            return True
        
        # Sequential predictions are testable
        elif pred_type == "sequence_continuation":
            return "given" in prediction and "expected" in prediction
        
        # Trend predictions are testable
        elif pred_type == "property_trend_continuation":
            return "property_id" in prediction and "expected_trend" in prediction
        
        return False
    
    def _matches_prediction(self, observation: Dict[str, Any], prediction: Dict[str, Any]) -> bool:
        """Check if an observation matches a prediction."""
        pred_type = prediction.get("type")
        
        if pred_type == "property":
            # Check if observation has the predicted property value
            if "properties" in observation:
                obs_value = observation["properties"].get(prediction["property_id"])
                return obs_value == prediction["expected_value"]
            
            # Also check if the observation is about the right concept
            obs_concepts = self._extract_concepts_from_observation(observation)
            return (prediction["concept_id"] in obs_concepts and 
                   observation.get("property_id") == prediction["property_id"] and
                   observation.get("value") == prediction["expected_value"])
        
        elif pred_type == "relation":
            # Check if observation contains the predicted relation
            if "relations" in observation:
                for rel in observation["relations"]:
                    if (rel.get("relation_id") == prediction["relation_id"] and
                        rel.get("source") == prediction["source_concept_id"] and
                        rel.get("target") == prediction["target_concept_id"]):
                        return True
            return False
        
        elif pred_type == "frequency_continuation":
            # Check if the concept appears in the observation
            obs_concepts = self._extract_concepts_from_observation(observation)
            return prediction["concept_id"] in obs_concepts
        
        elif pred_type == "sequence_continuation":
            # Check if the expected concept follows the given concept
            # This requires temporal information or order
            obs_concepts = list(self._extract_concepts_from_observation(observation))
            if len(obs_concepts) >= 2:
                for i in range(len(obs_concepts) - 1):
                    if (obs_concepts[i] == prediction["given"] and 
                        obs_concepts[i+1] == prediction["expected"]):
                        return True
            return False
        
        elif pred_type == "cooccurrence_prediction":
            # Check if both concepts appear together
            obs_concepts = self._extract_concepts_from_observation(observation)
            return (prediction["if_observed"] in obs_concepts and 
                   prediction["expect_also"] in obs_concepts)
        
        elif pred_type == "property_trend_continuation":
            # Check if the property shows the expected trend
            if "properties" in observation and prediction["property_id"] in observation["properties"]:
                # Would need historical values to properly check trend
                # For now, just check if the property exists
                return True
            return False
        
        return False
    
    def _should_be_observable(self, prediction: Dict[str, Any], observations: List[Dict[str, Any]]) -> bool:
        """Check if a prediction should be observable in the given observations."""
        # Determine if the observations are in the right scope to test the prediction
        
        pred_type = prediction.get("type")
        
        # Check if observations contain relevant concepts
        obs_concepts = set()
        for obs in observations:
            obs_concepts.update(self._extract_concepts_from_observation(obs))
        
        if pred_type == "property":
            # Should be observable if the concept is present
            return prediction["concept_id"] in obs_concepts
        
        elif pred_type == "relation":
            # Should be observable if source concept is present
            return prediction["source_concept_id"] in obs_concepts
        
        elif pred_type == "frequency_continuation":
            # Always potentially observable
            return True
        
        elif pred_type == "sequence_continuation":
            # Should be observable if the given concept appears
            return prediction["given"] in obs_concepts
        
        elif pred_type == "cooccurrence_prediction":
            # Should be observable if the conditional concept appears
            return prediction["if_observed"] in obs_concepts
        
        elif pred_type == "property_trend_continuation":
            # Should be observable if we have property data
            return any("properties" in obs for obs in observations)
        
        # Default: assume it should be observable
        return len(observations) > 0