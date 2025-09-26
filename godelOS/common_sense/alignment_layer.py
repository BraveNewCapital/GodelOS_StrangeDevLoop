"""
Alignment Layer for External Knowledge Base Interface

This module provides explicit alignment mappings between GödelOS internal concepts 
and external KB concepts (ConceptNet, WordNet) with confidence propagation,
rate-limiting metrics, and alignment quality assessment.

Part of P3 W3.3 External KB Alignment implementation.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


@dataclass
class AlignmentMapping:
    """Represents an alignment between internal and external concepts."""
    internal_concept: str
    external_concept: str
    external_source: str  # 'wordnet', 'conceptnet', etc.
    confidence: float  # 0.0 to 1.0
    mapping_type: str  # 'exact', 'similar', 'related', 'inferred'
    created_at: datetime
    last_used: datetime
    usage_count: int = 0
    quality_score: float = 0.0  # Computed alignment quality
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitMetrics:
    """Rate limiting metrics for external API calls."""
    source: str
    requests_per_minute: int = 0
    requests_per_hour: int = 0
    total_requests: int = 0
    failures: int = 0
    last_request: Optional[datetime] = None
    average_response_time: float = 0.0
    current_minute_requests: deque = field(default_factory=lambda: deque(maxlen=60))
    current_hour_requests: deque = field(default_factory=lambda: deque(maxlen=3600))


class AlignmentLayer:
    """
    Explicit alignment layer for external knowledge base mappings.
    
    Provides:
    - Confidence propagation for external KB mappings
    - Rate limiting and metrics tracking
    - Alignment quality assessment
    - Transparent mapping statistics
    """
    
    def __init__(self, 
                 confidence_threshold: float = 0.5,
                 rate_limit_per_minute: int = 60,
                 rate_limit_per_hour: int = 1000,
                 alignment_cache_size: int = 10000):
        """Initialize the alignment layer.
        
        Args:
            confidence_threshold: Minimum confidence for accepting mappings
            rate_limit_per_minute: Max requests per minute per source
            rate_limit_per_hour: Max requests per hour per source  
            alignment_cache_size: Max alignment mappings to cache
        """
        self.confidence_threshold = confidence_threshold
        self.rate_limit_per_minute = rate_limit_per_minute
        self.rate_limit_per_hour = rate_limit_per_hour
        self.alignment_cache_size = alignment_cache_size
        
        # Alignment mappings storage
        self._alignments: Dict[str, AlignmentMapping] = {}  # key -> mapping
        self._internal_to_external: Dict[str, List[str]] = defaultdict(list)  # internal -> [keys]
        self._external_to_internal: Dict[str, List[str]] = defaultdict(list)  # external -> [keys]
        
        # Rate limiting and metrics
        self._rate_metrics: Dict[str, RateLimitMetrics] = defaultdict(lambda: RateLimitMetrics("unknown"))
        self._metrics_lock = threading.RLock()
        
        # Cache metrics
        self._cache_hits = 0
        self._cache_misses = 0
        self._alignment_requests = 0
        
        logger.info(f"AlignmentLayer initialized with confidence_threshold={confidence_threshold}")
    
    def add_alignment(self, internal_concept: str, external_concept: str, 
                     external_source: str, confidence: float,
                     mapping_type: str = "inferred", metadata: Optional[Dict[str, Any]] = None) -> str:
        """Add or update an alignment mapping.
        
        Args:
            internal_concept: GödelOS internal concept name
            external_concept: External KB concept identifier  
            external_source: Source KB name ('wordnet', 'conceptnet')
            confidence: Confidence score (0.0 to 1.0)
            mapping_type: Type of mapping ('exact', 'similar', 'related', 'inferred')
            metadata: Optional metadata dictionary
            
        Returns:
            Mapping key for the alignment
        """
        if confidence < 0.0 or confidence > 1.0:
            raise ValueError(f"Confidence must be between 0.0 and 1.0, got {confidence}")
        
        # Create mapping key
        mapping_key = f"{internal_concept}::{external_source}::{external_concept}"
        
        # Create or update mapping
        now = datetime.now()
        if mapping_key in self._alignments:
            # Update existing
            alignment = self._alignments[mapping_key]
            alignment.confidence = confidence
            alignment.last_used = now
            alignment.usage_count += 1
            if metadata:
                alignment.metadata.update(metadata)
        else:
            # Create new
            alignment = AlignmentMapping(
                internal_concept=internal_concept,
                external_concept=external_concept,
                external_source=external_source,
                confidence=confidence,
                mapping_type=mapping_type,
                created_at=now,
                last_used=now,
                metadata=metadata or {}
            )
            self._alignments[mapping_key] = alignment
            
            # Update indices
            self._internal_to_external[internal_concept].append(mapping_key)
            external_key = f"{external_source}::{external_concept}"
            self._external_to_internal[external_key].append(mapping_key)
        
        # Calculate quality score
        alignment.quality_score = self._calculate_alignment_quality(alignment)
        
        # Manage cache size
        self._manage_cache_size()
        
        logger.debug(f"Added alignment: {internal_concept} -> {external_concept} "
                    f"({external_source}, conf={confidence:.3f}, quality={alignment.quality_score:.3f})")
        
        return mapping_key
    
    def get_external_mappings(self, internal_concept: str, 
                            min_confidence: Optional[float] = None) -> List[AlignmentMapping]:
        """Get external mappings for an internal concept.
        
        Args:
            internal_concept: Internal concept name
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of alignment mappings sorted by confidence
        """
        min_conf = min_confidence or self.confidence_threshold
        mappings = []
        
        for mapping_key in self._internal_to_external.get(internal_concept, []):
            if mapping_key in self._alignments:
                mapping = self._alignments[mapping_key]
                if mapping.confidence >= min_conf:
                    mappings.append(mapping)
        
        # Sort by confidence descending, then by quality score
        mappings.sort(key=lambda m: (-m.confidence, -m.quality_score))
        return mappings
    
    def get_internal_mappings(self, external_concept: str, external_source: str,
                            min_confidence: Optional[float] = None) -> List[AlignmentMapping]:
        """Get internal mappings for an external concept.
        
        Args:
            external_concept: External concept identifier
            external_source: External source name
            min_confidence: Minimum confidence threshold
            
        Returns:
            List of alignment mappings sorted by confidence
        """
        min_conf = min_confidence or self.confidence_threshold
        mappings = []
        
        external_key = f"{external_source}::{external_concept}"
        for mapping_key in self._external_to_internal.get(external_key, []):
            if mapping_key in self._alignments:
                mapping = self._alignments[mapping_key]
                if mapping.confidence >= min_conf:
                    mappings.append(mapping)
        
        mappings.sort(key=lambda m: (-m.confidence, -m.quality_score))
        return mappings
    
    def propagate_confidence(self, base_confidence: float, 
                           alignment_confidence: float, 
                           propagation_factor: float = 0.8) -> float:
        """Propagate confidence through alignment mappings.
        
        Args:
            base_confidence: Original confidence score
            alignment_confidence: Alignment mapping confidence
            propagation_factor: How much confidence is preserved (0.0-1.0)
            
        Returns:
            Propagated confidence score
        """
        # Confidence propagation formula: base * alignment * factor
        propagated = base_confidence * alignment_confidence * propagation_factor
        return min(max(propagated, 0.0), 1.0)  # Clamp to [0.0, 1.0]
    
    def check_rate_limit(self, source: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if rate limits are exceeded for a source.
        
        Args:
            source: External source name
            
        Returns:
            Tuple of (allowed, metrics_dict)
        """
        with self._metrics_lock:
            metrics = self._rate_metrics[source]
            metrics.source = source
            
            now = datetime.now()
            
            # Clean up old requests
            cutoff_minute = now - timedelta(minutes=1)
            cutoff_hour = now - timedelta(hours=1)
            
            # Count recent requests
            minute_count = sum(1 for req_time in metrics.current_minute_requests 
                             if datetime.fromtimestamp(req_time) > cutoff_minute)
            hour_count = sum(1 for req_time in metrics.current_hour_requests
                           if datetime.fromtimestamp(req_time) > cutoff_hour)
            
            # Check limits
            minute_ok = minute_count < self.rate_limit_per_minute
            hour_ok = hour_count < self.rate_limit_per_hour
            allowed = minute_ok and hour_ok
            
            # Update metrics
            metrics.requests_per_minute = minute_count
            metrics.requests_per_hour = hour_count
            
            return allowed, {
                'source': source,
                'allowed': allowed,
                'requests_per_minute': minute_count,
                'requests_per_hour': hour_count,
                'limit_per_minute': self.rate_limit_per_minute,
                'limit_per_hour': self.rate_limit_per_hour,
                'total_requests': metrics.total_requests,
                'failures': metrics.failures,
                'average_response_time': metrics.average_response_time
            }
    
    def record_request(self, source: str, success: bool, response_time: float) -> None:
        """Record a request to an external source.
        
        Args:
            source: External source name
            success: Whether the request succeeded
            response_time: Response time in seconds
        """
        with self._metrics_lock:
            metrics = self._rate_metrics[source]
            metrics.source = source
            
            now = datetime.now()
            timestamp = now.timestamp()
            
            # Add to request queues
            metrics.current_minute_requests.append(timestamp)
            metrics.current_hour_requests.append(timestamp)
            
            # Update metrics
            metrics.total_requests += 1
            metrics.last_request = now
            
            if not success:
                metrics.failures += 1
            
            # Update average response time (exponential moving average)
            if metrics.average_response_time == 0.0:
                metrics.average_response_time = response_time
            else:
                alpha = 0.1  # Smoothing factor
                metrics.average_response_time = (alpha * response_time + 
                                               (1 - alpha) * metrics.average_response_time)
    
    def get_alignment_statistics(self) -> Dict[str, Any]:
        """Get comprehensive alignment layer statistics.
        
        Returns:
            Dictionary with alignment statistics
        """
        with self._metrics_lock:
            # Count alignments by source and confidence ranges
            by_source = defaultdict(int)
            by_confidence = defaultdict(int)  # ranges: high (>0.8), medium (0.5-0.8), low (<0.5)
            by_mapping_type = defaultdict(int)
            
            total_quality = 0.0
            for alignment in self._alignments.values():
                by_source[alignment.external_source] += 1
                
                if alignment.confidence > 0.8:
                    by_confidence['high'] += 1
                elif alignment.confidence >= 0.5:
                    by_confidence['medium'] += 1
                else:
                    by_confidence['low'] += 1
                
                by_mapping_type[alignment.mapping_type] += 1
                total_quality += alignment.quality_score
            
            avg_quality = total_quality / len(self._alignments) if self._alignments else 0.0
            
            # Rate limiting stats
            rate_stats = {}
            for source, metrics in self._rate_metrics.items():
                rate_stats[source] = {
                    'total_requests': metrics.total_requests,
                    'failures': metrics.failures,
                    'success_rate': ((metrics.total_requests - metrics.failures) / 
                                   metrics.total_requests) if metrics.total_requests > 0 else 0.0,
                    'average_response_time': metrics.average_response_time,
                    'requests_per_minute': metrics.requests_per_minute,
                    'requests_per_hour': metrics.requests_per_hour
                }
            
            return {
                'total_alignments': len(self._alignments),
                'alignments_by_source': dict(by_source),
                'alignments_by_confidence': dict(by_confidence),
                'alignments_by_type': dict(by_mapping_type),
                'average_quality_score': avg_quality,
                'confidence_threshold': self.confidence_threshold,
                'cache_stats': {
                    'hits': self._cache_hits,
                    'misses': self._cache_misses,
                    'hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses) 
                              if (self._cache_hits + self._cache_misses) > 0 else 0.0
                },
                'rate_limiting': rate_stats,
                'alignment_requests': self._alignment_requests
            }
    
    def _calculate_alignment_quality(self, alignment: AlignmentMapping) -> float:
        """Calculate quality score for an alignment mapping.
        
        Args:
            alignment: The alignment mapping
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        quality = 0.0
        
        # Base quality from confidence
        quality += alignment.confidence * 0.4
        
        # Bonus for exact matches
        if alignment.mapping_type == "exact":
            quality += 0.3
        elif alignment.mapping_type == "similar":
            quality += 0.2
        elif alignment.mapping_type == "related":
            quality += 0.1
        
        # Bonus for frequently used mappings
        usage_bonus = min(alignment.usage_count / 100.0, 0.2)  # Max 0.2 bonus
        quality += usage_bonus
        
        # Recency bonus (newer mappings get slight bonus)
        age_days = (datetime.now() - alignment.created_at).days
        recency_bonus = max(0.1 - age_days * 0.01, 0.0)  # Decays over 10 days
        quality += recency_bonus
        
        # Bonus for trusted sources
        if alignment.external_source in ["wordnet", "conceptnet"]:
            quality += 0.1
        
        return min(quality, 1.0)
    
    def _manage_cache_size(self) -> None:
        """Manage alignment cache size by removing least recently used mappings."""
        if len(self._alignments) <= self.alignment_cache_size:
            return
        
        # Sort by last_used ascending (oldest first)
        mappings_by_age = sorted(self._alignments.items(), 
                               key=lambda x: x[1].last_used)
        
        # Remove oldest 10% when cache is full
        remove_count = len(self._alignments) - int(self.alignment_cache_size * 0.9)
        
        for i in range(remove_count):
            key, alignment = mappings_by_age[i]
            
            # Remove from main storage
            del self._alignments[key]
            
            # Remove from indices
            self._internal_to_external[alignment.internal_concept].remove(key)
            external_key = f"{alignment.external_source}::{alignment.external_concept}"
            self._external_to_internal[external_key].remove(key)
            
            # Clean up empty index entries
            if not self._internal_to_external[alignment.internal_concept]:
                del self._internal_to_external[alignment.internal_concept]
            if not self._external_to_internal[external_key]:
                del self._external_to_internal[external_key]
        
        logger.info(f"Cache cleanup: removed {remove_count} old alignment mappings")