"""
P3 W3.3 External KB Alignment API Endpoints

Provides transparent access to external knowledge base alignment metrics,
mapping confidence scores, and rate limiting statistics.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Dict, List, Optional, Any
from pydantic import BaseModel
import logging
import os
import sys

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from godelOS.common_sense.external_kb_interface import ExternalCommonSenseKB_Interface

logger = logging.getLogger(__name__)

# Response models
class AlignmentMapping(BaseModel):
    internal_concept: str
    external_concept: str
    external_source: str
    confidence: float
    mapping_type: str
    quality_score: float
    usage_count: int
    created_at: str
    last_used: str
    metadata: Dict[str, Any]

class AlignmentMetrics(BaseModel):
    total_alignments: int
    active_alignments: int
    confidence_distribution: Dict[str, int]
    source_distribution: Dict[str, int]
    type_distribution: Dict[str, int]
    average_confidence: float
    quality_distribution: Dict[str, int]

class RateLimitingMetrics(BaseModel):
    source_metrics: Dict[str, Dict[str, Any]]
    current_usage: Dict[str, int]
    limits: Dict[str, int]
    reset_times: Dict[str, str]
    throttled_requests: int
    total_requests: int

class AlignmentStatistics(BaseModel):
    alignment_metrics: AlignmentMetrics
    rate_limiting_metrics: RateLimitingMetrics
    system_status: Dict[str, Any]

# Router setup
router = APIRouter(prefix="/api/alignment", tags=["External KB Alignment"])

# Global external KB interface instance
_external_kb_interface: Optional[ExternalCommonSenseKB_Interface] = None

def get_external_kb_interface() -> ExternalCommonSenseKB_Interface:
    """Dependency to get the external KB interface instance."""
    global _external_kb_interface
    if _external_kb_interface is None:
        _external_kb_interface = ExternalCommonSenseKB_Interface()
    return _external_kb_interface

@router.get("/metrics", response_model=AlignmentStatistics)
async def get_alignment_metrics(
    kb_interface: ExternalCommonSenseKB_Interface = Depends(get_external_kb_interface)
) -> AlignmentStatistics:
    """
    Get comprehensive alignment and rate limiting metrics.
    
    Returns:
        - Total alignment statistics
        - Confidence and quality distributions
        - Rate limiting status and metrics
        - System health indicators
    """
    try:
        metrics_data = kb_interface.get_alignment_metrics()
        
        # Parse alignment metrics
        alignment_metrics = AlignmentMetrics(
            total_alignments=metrics_data['alignment_metrics']['total_alignments'],
            active_alignments=metrics_data['alignment_metrics']['active_alignments'],
            confidence_distribution=metrics_data['alignment_metrics']['confidence_distribution'],
            source_distribution=metrics_data['alignment_metrics']['source_distribution'],
            type_distribution=metrics_data['alignment_metrics']['type_distribution'],
            average_confidence=metrics_data['alignment_metrics']['average_confidence'],
            quality_distribution=metrics_data['alignment_metrics']['quality_distribution']
        )
        
        # Parse rate limiting metrics
        rate_limiting_metrics = RateLimitingMetrics(
            source_metrics=metrics_data['rate_limiting_metrics']['source_metrics'],
            current_usage=metrics_data['rate_limiting_metrics']['current_usage'],
            limits=metrics_data['rate_limiting_metrics']['limits'],
            reset_times=metrics_data['rate_limiting_metrics']['reset_times'],
            throttled_requests=metrics_data['rate_limiting_metrics']['throttled_requests'],
            total_requests=metrics_data['rate_limiting_metrics']['total_requests']
        )
        
        return AlignmentStatistics(
            alignment_metrics=alignment_metrics,
            rate_limiting_metrics=rate_limiting_metrics,
            system_status=metrics_data['system_status']
        )
    
    except Exception as e:
        logger.error(f"Error getting alignment metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving alignment metrics: {str(e)}")

@router.get("/mappings/{internal_concept}", response_model=List[AlignmentMapping])
async def get_concept_mappings(
    internal_concept: str,
    min_confidence: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    kb_interface: ExternalCommonSenseKB_Interface = Depends(get_external_kb_interface)
) -> List[AlignmentMapping]:
    """
    Get external mappings for a specific internal concept.
    
    Args:
        internal_concept: The internal GödelOS concept to get mappings for
        min_confidence: Optional minimum confidence threshold (0.0-1.0)
    
    Returns:
        List of alignment mappings with confidence scores and metadata
    """
    try:
        mappings_data = kb_interface.get_external_mappings(internal_concept, min_confidence)
        
        return [
            AlignmentMapping(
                internal_concept=mapping['internal_concept'],
                external_concept=mapping['external_concept'],
                external_source=mapping['external_source'],
                confidence=mapping['confidence'],
                mapping_type=mapping['mapping_type'],
                quality_score=mapping['quality_score'],
                usage_count=mapping['usage_count'],
                created_at=mapping['created_at'],
                last_used=mapping['last_used'],
                metadata=mapping['metadata']
            )
            for mapping in mappings_data
        ]
    
    except Exception as e:
        logger.error(f"Error getting mappings for concept '{internal_concept}': {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving mappings for concept '{internal_concept}': {str(e)}"
        )

@router.get("/confidence/distribution")
async def get_confidence_distribution(
    kb_interface: ExternalCommonSenseKB_Interface = Depends(get_external_kb_interface)
) -> Dict[str, Any]:
    """
    Get detailed confidence score distribution across all alignments.
    
    Returns:
        Confidence distribution statistics and percentiles
    """
    try:
        metrics_data = kb_interface.get_alignment_metrics()
        confidence_stats = metrics_data['alignment_metrics']['confidence_distribution']
        
        return {
            "distribution_buckets": confidence_stats,
            "statistics": {
                "average_confidence": metrics_data['alignment_metrics']['average_confidence'],
                "total_alignments": metrics_data['alignment_metrics']['total_alignments']
            },
            "quality_indicators": {
                "high_confidence_mappings": confidence_stats.get("0.8-1.0", 0),
                "medium_confidence_mappings": confidence_stats.get("0.5-0.8", 0),
                "low_confidence_mappings": confidence_stats.get("0.0-0.5", 0)
            }
        }
    
    except Exception as e:
        logger.error(f"Error getting confidence distribution: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving confidence distribution: {str(e)}"
        )

@router.get("/rate-limiting/status")
async def get_rate_limiting_status(
    kb_interface: ExternalCommonSenseKB_Interface = Depends(get_external_kb_interface)
) -> Dict[str, Any]:
    """
    Get current rate limiting status and usage statistics.
    
    Returns:
        Current usage, limits, reset times, and throttling statistics
    """
    try:
        metrics_data = kb_interface.get_alignment_metrics()
        rate_metrics = metrics_data['rate_limiting_metrics']
        
        return {
            "current_status": {
                "usage": rate_metrics['current_usage'],
                "limits": rate_metrics['limits'],
                "usage_percentage": {
                    source: (usage / rate_metrics['limits'].get(source, 1)) * 100
                    for source, usage in rate_metrics['current_usage'].items()
                }
            },
            "reset_schedule": rate_metrics['reset_times'],
            "throttling_stats": {
                "throttled_requests": rate_metrics['throttled_requests'],
                "total_requests": rate_metrics['total_requests'],
                "throttling_percentage": (
                    rate_metrics['throttled_requests'] / max(rate_metrics['total_requests'], 1)
                ) * 100
            },
            "source_details": rate_metrics['source_metrics']
        }
    
    except Exception as e:
        logger.error(f"Error getting rate limiting status: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving rate limiting status: {str(e)}"
        )

@router.get("/health")
async def get_alignment_health(
    kb_interface: ExternalCommonSenseKB_Interface = Depends(get_external_kb_interface)
) -> Dict[str, Any]:
    """
    Get alignment system health status and diagnostics.
    
    Returns:
        System health indicators and diagnostic information
    """
    try:
        metrics_data = kb_interface.get_alignment_metrics()
        system_status = metrics_data['system_status']
        
        # Calculate health score based on various metrics
        alignment_metrics = metrics_data['alignment_metrics']
        rate_metrics = metrics_data['rate_limiting_metrics']
        
        health_score = 1.0
        health_indicators = {}
        
        # Check alignment quality
        avg_confidence = alignment_metrics['average_confidence']
        if avg_confidence < 0.5:
            health_score -= 0.3
            health_indicators['alignment_quality'] = 'poor'
        elif avg_confidence < 0.7:
            health_score -= 0.1
            health_indicators['alignment_quality'] = 'fair'
        else:
            health_indicators['alignment_quality'] = 'good'
        
        # Check rate limiting status
        throttling_rate = rate_metrics['throttled_requests'] / max(rate_metrics['total_requests'], 1)
        if throttling_rate > 0.1:
            health_score -= 0.2
            health_indicators['rate_limiting'] = 'throttled'
        else:
            health_indicators['rate_limiting'] = 'normal'
        
        health_status = 'healthy' if health_score >= 0.8 else 'degraded' if health_score >= 0.5 else 'unhealthy'
        
        return {
            "overall_status": health_status,
            "health_score": max(0.0, health_score),
            "indicators": health_indicators,
            "system_info": system_status,
            "recommendations": _get_health_recommendations(health_indicators, metrics_data)
        }
    
    except Exception as e:
        logger.error(f"Error getting alignment health: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Error retrieving alignment health: {str(e)}"
        )

def _get_health_recommendations(health_indicators: Dict[str, str], 
                               metrics_data: Dict[str, Any]) -> List[str]:
    """Generate health recommendations based on current status."""
    recommendations = []
    
    if health_indicators.get('alignment_quality') == 'poor':
        recommendations.append("Consider improving alignment confidence by refining mapping algorithms")
    
    if health_indicators.get('rate_limiting') == 'throttled':
        recommendations.append("Reduce external KB query frequency or implement better caching")
    
    # Check for inactive alignments
    alignment_metrics = metrics_data['alignment_metrics']
    if alignment_metrics['total_alignments'] > alignment_metrics['active_alignments'] * 2:
        recommendations.append("Consider cleaning up old or unused alignment mappings")
    
    if not recommendations:
        recommendations.append("System is operating within normal parameters")
    
    return recommendations