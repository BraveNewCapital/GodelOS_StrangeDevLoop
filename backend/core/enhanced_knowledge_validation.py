"""
Enhanced Knowledge Validation Framework for GodelOS

This module provides comprehensive knowledge validation capabilities including:
- Multi-layer validation (syntactic, semantic, pragmatic, consistency)
- Cross-domain validation and verification
- Knowledge quality assessment and scoring
- Validation rule engine with configurable policies
- Integration with existing ontology and knowledge management systems
"""

import logging
import asyncio
from typing import Dict, List, Optional, Set, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import time
from datetime import datetime
import json
import re

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Levels of knowledge validation."""
    SYNTACTIC = "syntactic"      # Basic structure and format validation
    SEMANTIC = "semantic"        # Meaning and consistency validation  
    PRAGMATIC = "pragmatic"      # Context and utility validation
    CONSISTENCY = "consistency"  # Internal and cross-domain consistency
    QUALITY = "quality"          # Overall knowledge quality assessment


class ValidationSeverity(Enum):
    """Severity levels for validation issues."""
    INFO = "info"
    WARNING = "warning" 
    ERROR = "error"
    CRITICAL = "critical"


class ValidationStatus(Enum):
    """Status of validation process."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ValidationIssue:
    """Represents a validation issue found during knowledge validation."""
    id: str = field(default_factory=lambda: f"issue_{int(time.time() * 1000)}")
    level: ValidationLevel = ValidationLevel.SYNTACTIC
    severity: ValidationSeverity = ValidationSeverity.WARNING
    message: str = ""
    description: str = ""
    knowledge_id: Optional[str] = None
    location: Optional[str] = None
    suggested_fix: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "level": self.level.value,
            "severity": self.severity.value,
            "message": self.message,
            "description": self.description,
            "knowledge_id": self.knowledge_id,
            "location": self.location,
            "suggested_fix": self.suggested_fix,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass 
class ValidationResult:
    """Result of knowledge validation process."""
    validation_id: str = field(default_factory=lambda: f"validation_{int(time.time())}")
    status: ValidationStatus = ValidationStatus.PENDING
    overall_score: float = 0.0  # 0.0 to 1.0
    issues: List[ValidationIssue] = field(default_factory=list)
    metrics: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    validated_at: datetime = field(default_factory=datetime.now)
    validation_duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[ValidationIssue]:
        """Get issues by severity level."""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_issues_by_level(self, level: ValidationLevel) -> List[ValidationIssue]:
        """Get issues by validation level.""" 
        return [issue for issue in self.issues if issue.level == level]
    
    def has_critical_issues(self) -> bool:
        """Check if there are any critical issues."""
        return any(issue.severity == ValidationSeverity.CRITICAL for issue in self.issues)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "validation_id": self.validation_id,
            "status": self.status.value,
            "overall_score": self.overall_score,
            "issues": [issue.to_dict() for issue in self.issues],
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "validated_at": self.validated_at.isoformat(),
            "validation_duration": self.validation_duration,
            "metadata": self.metadata
        }


class ValidationRule:
    """Base class for validation rules."""
    
    def __init__(self, rule_id: str, name: str, description: str, 
                 level: ValidationLevel, severity: ValidationSeverity):
        self.rule_id = rule_id
        self.name = name
        self.description = description
        self.level = level
        self.severity = severity
    
    async def validate(self, knowledge_item: Dict[str, Any], 
                      context: Dict[str, Any] = None) -> List[ValidationIssue]:
        """Validate a knowledge item. Override in subclasses."""
        raise NotImplementedError


class SyntacticValidationRule(ValidationRule):
    """Validation rule for syntactic checks."""
    
    def __init__(self, rule_id: str, name: str, required_fields: List[str]):
        super().__init__(rule_id, name, "Syntactic validation rule", 
                        ValidationLevel.SYNTACTIC, ValidationSeverity.ERROR)
        self.required_fields = required_fields
    
    async def validate(self, knowledge_item: Dict[str, Any], 
                      context: Dict[str, Any] = None) -> List[ValidationIssue]:
        """Validate required fields are present."""
        issues = []
        
        for field in self.required_fields:
            if field not in knowledge_item or knowledge_item[field] is None:
                issue = ValidationIssue(
                    level=self.level,
                    severity=self.severity,
                    message=f"Missing required field: {field}",
                    description=f"Knowledge item must contain field '{field}'",
                    knowledge_id=knowledge_item.get("id"),
                    location=f"field:{field}",
                    suggested_fix=f"Add required field '{field}' to knowledge item"
                )
                issues.append(issue)
        
        return issues


class SemanticValidationRule(ValidationRule):
    """Validation rule for semantic checks."""
    
    def __init__(self, rule_id: str, name: str, ontology_manager=None):
        super().__init__(rule_id, name, "Semantic validation rule",
                        ValidationLevel.SEMANTIC, ValidationSeverity.WARNING)
        self.ontology_manager = ontology_manager
    
    async def validate(self, knowledge_item: Dict[str, Any],
                      context: Dict[str, Any] = None) -> List[ValidationIssue]:
        """Validate semantic consistency with ontology."""
        issues = []
        
        if not self.ontology_manager:
            return issues
        
        # Check if concepts exist in ontology
        concepts = knowledge_item.get("concepts", [])
        for concept in concepts:
            if not self.ontology_manager.get_concept(concept):
                issue = ValidationIssue(
                    level=self.level,
                    severity=self.severity,
                    message=f"Unknown concept: {concept}",
                    description=f"Concept '{concept}' not found in ontology",
                    knowledge_id=knowledge_item.get("id"),
                    location=f"concept:{concept}",
                    suggested_fix=f"Add concept '{concept}' to ontology or verify spelling"
                )
                issues.append(issue)
        
        return issues


class ConsistencyValidationRule(ValidationRule):
    """Validation rule for consistency checks."""
    
    def __init__(self, rule_id: str, name: str, knowledge_store=None):
        super().__init__(rule_id, name, "Consistency validation rule",
                        ValidationLevel.CONSISTENCY, ValidationSeverity.ERROR)
        self.knowledge_store = knowledge_store
    
    async def validate(self, knowledge_item: Dict[str, Any],
                      context: Dict[str, Any] = None) -> List[ValidationIssue]:
        """Validate consistency with existing knowledge."""
        issues = []
        
        if not self.knowledge_store:
            return issues
        
        # Check for contradictions with existing knowledge
        content = knowledge_item.get("content", "")
        if content:
            # Simple contradiction detection (could be enhanced with LLM)
            contradictory_patterns = [
                (r"(\w+)\s+is\s+(\w+)", r"(\w+)\s+is\s+not\s+(\w+)"),
                (r"(\w+)\s+always\s+(\w+)", r"(\w+)\s+never\s+(\w+)"),
                (r"(\w+)\s+can\s+(\w+)", r"(\w+)\s+cannot\s+(\w+)")
            ]
            
            for positive_pattern, negative_pattern in contradictory_patterns:
                if re.search(positive_pattern, content) and re.search(negative_pattern, content):
                    issue = ValidationIssue(
                        level=self.level,
                        severity=self.severity,
                        message="Potential contradiction detected",
                        description="Knowledge item contains contradictory statements",
                        knowledge_id=knowledge_item.get("id"),
                        location="content",
                        suggested_fix="Review and resolve contradictory statements"
                    )
                    issues.append(issue)
        
        return issues


class QualityValidationRule(ValidationRule):
    """Validation rule for quality assessment."""
    
    def __init__(self, rule_id: str, name: str):
        super().__init__(rule_id, name, "Quality validation rule",
                        ValidationLevel.QUALITY, ValidationSeverity.INFO)
    
    async def validate(self, knowledge_item: Dict[str, Any],
                      context: Dict[str, Any] = None) -> List[ValidationIssue]:
        """Assess knowledge quality."""
        issues = []
        
        content = knowledge_item.get("content", "")
        
        # Check content length
        if len(content) < 10:
            issue = ValidationIssue(
                level=self.level,
                severity=ValidationSeverity.WARNING,
                message="Content too short",
                description="Knowledge content appears to be too brief",
                knowledge_id=knowledge_item.get("id"),
                location="content",
                suggested_fix="Add more detailed information"
            )
            issues.append(issue)
        
        # Check for sources/references
        if "sources" not in knowledge_item or not knowledge_item["sources"]:
            issue = ValidationIssue(
                level=self.level,
                severity=ValidationSeverity.INFO,
                message="No sources provided",
                description="Knowledge item lacks source references",
                knowledge_id=knowledge_item.get("id"),
                location="sources",
                suggested_fix="Add credible sources or references"
            )
            issues.append(issue)
        
        return issues


class EnhancedKnowledgeValidationFramework:
    """
    Enhanced knowledge validation framework with multi-layer validation capabilities.
    
    Features:
    - Multi-level validation (syntactic, semantic, pragmatic, consistency, quality)
    - Configurable validation rules and policies
    - Cross-domain validation and verification
    - Knowledge quality scoring and assessment
    - Integration with ontology and knowledge management systems
    - Batch and real-time validation support
    """
    
    def __init__(self, 
                 ontology_manager=None,
                 knowledge_store=None,
                 domain_reasoning_engine=None):
        """
        Initialize the Enhanced Knowledge Validation Framework.
        
        Args:
            ontology_manager: Reference to ontology manager for semantic validation
            knowledge_store: Reference to knowledge store for consistency checks
            domain_reasoning_engine: Reference to domain reasoning for cross-domain validation
        """
        self.ontology_manager = ontology_manager
        self.knowledge_store = knowledge_store
        self.domain_reasoning_engine = domain_reasoning_engine
        
        # Validation rules registry
        self.validation_rules: Dict[str, ValidationRule] = {}
        
        # Validation policies (which rules to apply for different knowledge types)
        self.validation_policies: Dict[str, List[str]] = {
            "default": [],  # Will be populated with default rules
            "concept": [],
            "fact": [],
            "relationship": [],
            "document": []
        }
        
        # Validation metrics
        self.validation_stats = {
            "total_validations": 0,
            "successful_validations": 0,
            "failed_validations": 0,
            "avg_validation_time": 0.0,
            "total_issues_found": 0,
            "issues_by_severity": {
                "info": 0,
                "warning": 0, 
                "error": 0,
                "critical": 0
            }
        }
        
        # Initialize default validation rules
        self._initialize_default_rules()
        
        logger.info("Enhanced Knowledge Validation Framework initialized")
    
    def _initialize_default_rules(self):
        """Initialize default validation rules."""
        # Syntactic rules
        basic_fields_rule = SyntacticValidationRule(
            "basic_fields", 
            "Basic Fields Check",
            ["id", "content", "type"]
        )
        self.add_validation_rule(basic_fields_rule)
        
        # Semantic rules
        if self.ontology_manager:
            semantic_rule = SemanticValidationRule(
                "semantic_consistency",
                "Semantic Consistency Check", 
                self.ontology_manager
            )
            self.add_validation_rule(semantic_rule)
        
        # Consistency rules
        if self.knowledge_store:
            consistency_rule = ConsistencyValidationRule(
                "consistency_check",
                "Knowledge Consistency Check",
                self.knowledge_store
            )
            self.add_validation_rule(consistency_rule)
        
        # Quality rules
        quality_rule = QualityValidationRule(
            "quality_assessment",
            "Quality Assessment"
        )
        self.add_validation_rule(quality_rule)
        
        # Set default policy
        self.validation_policies["default"] = list(self.validation_rules.keys())
    
    def add_validation_rule(self, rule: ValidationRule):
        """Add a validation rule to the framework."""
        self.validation_rules[rule.rule_id] = rule
        logger.info(f"Added validation rule: {rule.name}")
    
    def remove_validation_rule(self, rule_id: str) -> bool:
        """Remove a validation rule from the framework."""
        if rule_id in self.validation_rules:
            del self.validation_rules[rule_id]
            logger.info(f"Removed validation rule: {rule_id}")
            return True
        return False
    
    def set_validation_policy(self, knowledge_type: str, rule_ids: List[str]):
        """Set validation policy for a knowledge type."""
        self.validation_policies[knowledge_type] = rule_ids
        logger.info(f"Set validation policy for {knowledge_type}: {rule_ids}")
    
    async def validate_knowledge_item(self, 
                                    knowledge_item: Dict[str, Any],
                                    knowledge_type: str = "default",
                                    context: Dict[str, Any] = None) -> ValidationResult:
        """
        Validate a single knowledge item.
        
        Args:
            knowledge_item: The knowledge item to validate
            knowledge_type: Type of knowledge for policy selection
            context: Additional context for validation
            
        Returns:
            ValidationResult: Comprehensive validation result
        """
        start_time = time.time()
        self.validation_stats["total_validations"] += 1
        
        try:
            result = ValidationResult()
            
            # Get applicable rules for this knowledge type
            rule_ids = self.validation_policies.get(knowledge_type, 
                                                  self.validation_policies["default"])
            
            # Apply validation rules
            all_issues = []
            for rule_id in rule_ids:
                if rule_id in self.validation_rules:
                    rule = self.validation_rules[rule_id]
                    try:
                        issues = await rule.validate(knowledge_item, context)
                        all_issues.extend(issues)
                    except Exception as e:
                        logger.error(f"Error applying rule {rule_id}: {e}")
                        # Create an issue for the rule failure
                        issue = ValidationIssue(
                            level=ValidationLevel.SYNTACTIC,
                            severity=ValidationSeverity.ERROR,
                            message=f"Validation rule failed: {rule_id}",
                            description=f"Error applying validation rule: {str(e)}",
                            knowledge_id=knowledge_item.get("id")
                        )
                        all_issues.append(issue)
            
            result.issues = all_issues
            result.validation_duration = time.time() - start_time
            
            # Calculate overall score
            result.overall_score = self._calculate_overall_score(all_issues)
            
            # Generate metrics
            result.metrics = self._generate_validation_metrics(all_issues)
            
            # Generate recommendations
            result.recommendations = self._generate_recommendations(all_issues)
            
            result.status = ValidationStatus.COMPLETED
            
            # Update statistics
            self._update_validation_stats(result)
            self.validation_stats["successful_validations"] += 1
            
            logger.info(f"Validated knowledge item {knowledge_item.get('id', 'unknown')} "
                       f"with score {result.overall_score:.2f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Validation failed for knowledge item: {e}")
            self.validation_stats["failed_validations"] += 1
            
            # Return failed result
            result = ValidationResult()
            result.status = ValidationStatus.FAILED
            result.validation_duration = time.time() - start_time
            result.metadata["error"] = str(e)
            return result
    
    async def validate_knowledge_batch(self, 
                                     knowledge_items: List[Dict[str, Any]],
                                     knowledge_type: str = "default",
                                     context: Dict[str, Any] = None) -> List[ValidationResult]:
        """
        Validate a batch of knowledge items.
        
        Args:
            knowledge_items: List of knowledge items to validate
            knowledge_type: Type of knowledge for policy selection
            context: Additional context for validation
            
        Returns:
            List[ValidationResult]: Validation results for each item
        """
        logger.info(f"Starting batch validation of {len(knowledge_items)} items")
        
        # Validate items concurrently
        tasks = [
            self.validate_knowledge_item(item, knowledge_type, context)
            for item in knowledge_items
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions in results
        validated_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Validation failed for item {i}: {result}")
                failed_result = ValidationResult()
                failed_result.status = ValidationStatus.FAILED
                failed_result.metadata["error"] = str(result)
                failed_result.metadata["item_index"] = i
                validated_results.append(failed_result)
            else:
                validated_results.append(result)
        
        logger.info(f"Completed batch validation: {len(validated_results)} results")
        return validated_results
    
    async def validate_cross_domain_consistency(self, 
                                              knowledge_items: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate cross-domain consistency across multiple knowledge items.
        
        Args:
            knowledge_items: List of knowledge items from different domains
            
        Returns:
            ValidationResult: Cross-domain validation result
        """
        result = ValidationResult()
        result.validation_id = f"cross_domain_{int(time.time())}"
        
        if not self.domain_reasoning_engine:
            issue = ValidationIssue(
                level=ValidationLevel.CONSISTENCY,
                severity=ValidationSeverity.WARNING,
                message="Cross-domain validation unavailable",
                description="Domain reasoning engine not available for cross-domain validation"
            )
            result.issues.append(issue)
            result.status = ValidationStatus.COMPLETED
            return result
        
        # Group items by domain
        domain_groups = {}
        for item in knowledge_items:
            domain = item.get("domain", "unknown")
            if domain not in domain_groups:
                domain_groups[domain] = []
            domain_groups[domain].append(item)
        
        # Check for cross-domain contradictions
        domain_pairs = []
        domains = list(domain_groups.keys())
        for i, domain1 in enumerate(domains):
            for domain2 in domains[i+1:]:
                domain_pairs.append((domain1, domain2))
        
        for domain1, domain2 in domain_pairs:
            try:
                # Use domain reasoning engine to check consistency
                items1 = domain_groups[domain1]
                items2 = domain_groups[domain2]
                
                # Simple consistency check (could be enhanced)
                for item1 in items1:
                    for item2 in items2:
                        content1 = item1.get("content", "").lower()
                        content2 = item2.get("content", "").lower()
                        
                        # Look for contradictory statements across domains
                        if self._check_content_contradiction(content1, content2):
                            issue = ValidationIssue(
                                level=ValidationLevel.CONSISTENCY,
                                severity=ValidationSeverity.ERROR,
                                message=f"Cross-domain contradiction: {domain1} vs {domain2}",
                                description=f"Contradictory information found between domains",
                                metadata={
                                    "domain1": domain1,
                                    "domain2": domain2,
                                    "item1_id": item1.get("id"),
                                    "item2_id": item2.get("id")
                                }
                            )
                            result.issues.append(issue)
                            
            except Exception as e:
                logger.error(f"Error in cross-domain validation for {domain1}-{domain2}: {e}")
        
        result.overall_score = self._calculate_overall_score(result.issues)
        result.status = ValidationStatus.COMPLETED
        return result
    
    def _check_content_contradiction(self, content1: str, content2: str) -> bool:
        """Check if two content strings are contradictory."""
        # Simple contradiction patterns (could be enhanced with NLP/LLM)
        contradiction_pairs = [
            ("true", "false"),
            ("always", "never"),
            ("all", "none"),
            ("increase", "decrease"),
            ("positive", "negative")
        ]
        
        for pos, neg in contradiction_pairs:
            if pos in content1 and neg in content2:
                return True
            if neg in content1 and pos in content2:
                return True
        
        return False
    
    def _calculate_overall_score(self, issues: List[ValidationIssue]) -> float:
        """Calculate overall validation score based on issues found."""
        if not issues:
            return 1.0
        
        # Weight issues by severity
        severity_weights = {
            ValidationSeverity.INFO: 0.1,
            ValidationSeverity.WARNING: 0.3,
            ValidationSeverity.ERROR: 0.7,
            ValidationSeverity.CRITICAL: 1.0
        }
        
        total_penalty = sum(severity_weights[issue.severity] for issue in issues)
        
        # Normalize to 0-1 scale (assuming max 10 critical issues would be score 0)
        max_penalty = 10.0
        score = max(0.0, 1.0 - (total_penalty / max_penalty))
        
        return score
    
    def _generate_validation_metrics(self, issues: List[ValidationIssue]) -> Dict[str, float]:
        """Generate validation metrics from issues."""
        metrics = {
            "total_issues": len(issues),
            "critical_issues": len([i for i in issues if i.severity == ValidationSeverity.CRITICAL]),
            "error_issues": len([i for i in issues if i.severity == ValidationSeverity.ERROR]),
            "warning_issues": len([i for i in issues if i.severity == ValidationSeverity.WARNING]),
            "info_issues": len([i for i in issues if i.severity == ValidationSeverity.INFO]),
            "syntactic_issues": len([i for i in issues if i.level == ValidationLevel.SYNTACTIC]),
            "semantic_issues": len([i for i in issues if i.level == ValidationLevel.SEMANTIC]),
            "consistency_issues": len([i for i in issues if i.level == ValidationLevel.CONSISTENCY]),
            "quality_issues": len([i for i in issues if i.level == ValidationLevel.QUALITY])
        }
        
        return metrics
    
    def _generate_recommendations(self, issues: List[ValidationIssue]) -> List[str]:
        """Generate recommendations based on validation issues."""
        recommendations = []
        
        critical_count = len([i for i in issues if i.severity == ValidationSeverity.CRITICAL])
        error_count = len([i for i in issues if i.severity == ValidationSeverity.ERROR])
        
        if critical_count > 0:
            recommendations.append(f"URGENT: Resolve {critical_count} critical issues before using this knowledge")
        
        if error_count > 0:
            recommendations.append(f"Fix {error_count} error-level issues to improve knowledge quality")
        
        syntactic_issues = [i for i in issues if i.level == ValidationLevel.SYNTACTIC]
        if syntactic_issues:
            recommendations.append("Add missing required fields and fix formatting issues")
        
        semantic_issues = [i for i in issues if i.level == ValidationLevel.SEMANTIC]
        if semantic_issues:
            recommendations.append("Verify concepts exist in ontology and fix semantic inconsistencies")
        
        quality_issues = [i for i in issues if i.level == ValidationLevel.QUALITY]
        if quality_issues:
            recommendations.append("Improve knowledge quality by adding sources and more detailed content")
        
        if not recommendations:
            recommendations.append("Knowledge validation passed - no issues found")
        
        return recommendations
    
    def _update_validation_stats(self, result: ValidationResult):
        """Update validation statistics."""
        self.validation_stats["total_issues_found"] += len(result.issues)
        
        for issue in result.issues:
            self.validation_stats["issues_by_severity"][issue.severity.value] += 1
        
        # Update average validation time
        total_time = (self.validation_stats["avg_validation_time"] * 
                     (self.validation_stats["total_validations"] - 1) + 
                     result.validation_duration)
        self.validation_stats["avg_validation_time"] = total_time / self.validation_stats["total_validations"]
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation framework statistics."""
        return {
            "validation_stats": self.validation_stats.copy(),
            "available_rules": list(self.validation_rules.keys()),
            "validation_policies": self.validation_policies.copy(),
            "framework_status": {
                "ontology_manager_available": self.ontology_manager is not None,
                "knowledge_store_available": self.knowledge_store is not None,
                "domain_reasoning_available": self.domain_reasoning_engine is not None
            }
        }
    
    async def validate_knowledge_integration(self, 
                                           source_knowledge: Dict[str, Any],
                                           target_knowledge_base: List[Dict[str, Any]]) -> ValidationResult:
        """
        Validate integration of new knowledge into existing knowledge base.
        
        Args:
            source_knowledge: New knowledge to be integrated
            target_knowledge_base: Existing knowledge base
            
        Returns:
            ValidationResult: Integration validation result
        """
        result = ValidationResult()
        result.validation_id = f"integration_{int(time.time())}"
        
        # First validate the source knowledge itself
        source_validation = await self.validate_knowledge_item(source_knowledge)
        result.issues.extend(source_validation.issues)
        
        # Check for conflicts with existing knowledge
        for existing_item in target_knowledge_base:
            if self._check_knowledge_conflict(source_knowledge, existing_item):
                issue = ValidationIssue(
                    level=ValidationLevel.CONSISTENCY,
                    severity=ValidationSeverity.WARNING,
                    message="Potential knowledge conflict detected",
                    description=f"New knowledge may conflict with existing item {existing_item.get('id')}",
                    knowledge_id=source_knowledge.get("id"),
                    metadata={
                        "conflicting_item_id": existing_item.get("id"),
                        "conflict_type": "content_overlap"
                    },
                    suggested_fix="Review and resolve potential conflicts before integration"
                )
                result.issues.append(issue)
        
        # Check for knowledge gaps that this might fill
        gaps_filled = self._check_knowledge_gaps_filled(source_knowledge, target_knowledge_base)
        if gaps_filled:
            result.metadata["gaps_filled"] = gaps_filled
            result.recommendations.append(f"This knowledge helps fill {len(gaps_filled)} identified gaps")
        
        result.overall_score = self._calculate_overall_score(result.issues)
        result.status = ValidationStatus.COMPLETED
        
        return result
    
    def _check_knowledge_conflict(self, new_knowledge: Dict[str, Any], 
                                 existing_knowledge: Dict[str, Any]) -> bool:
        """Check if new knowledge conflicts with existing knowledge."""
        # Simple conflict detection (could be enhanced)
        new_content = new_knowledge.get("content", "").lower()
        existing_content = existing_knowledge.get("content", "").lower()
        
        # Check for direct contradictions
        return self._check_content_contradiction(new_content, existing_content)
    
    def _check_knowledge_gaps_filled(self, new_knowledge: Dict[str, Any],
                                   knowledge_base: List[Dict[str, Any]]) -> List[str]:
        """Check what knowledge gaps the new knowledge might fill."""
        gaps_filled = []
        
        new_concepts = new_knowledge.get("concepts", [])
        new_domain = new_knowledge.get("domain", "")
        
        # Check if new knowledge introduces concepts not in existing base
        existing_concepts = set()
        existing_domains = set()
        
        for item in knowledge_base:
            existing_concepts.update(item.get("concepts", []))
            existing_domains.add(item.get("domain", ""))
        
        for concept in new_concepts:
            if concept not in existing_concepts:
                gaps_filled.append(f"new_concept:{concept}")
        
        if new_domain and new_domain not in existing_domains:
            gaps_filled.append(f"new_domain:{new_domain}")
        
        return gaps_filled


# Global instance for easy access
enhanced_knowledge_validator = None

def get_enhanced_knowledge_validator(ontology_manager=None, 
                                   knowledge_store=None,
                                   domain_reasoning_engine=None):
    """Get or create the global enhanced knowledge validator instance."""
    global enhanced_knowledge_validator
    
    if enhanced_knowledge_validator is None:
        enhanced_knowledge_validator = EnhancedKnowledgeValidationFramework(
            ontology_manager=ontology_manager,
            knowledge_store=knowledge_store, 
            domain_reasoning_engine=domain_reasoning_engine
        )
    
    return enhanced_knowledge_validator
