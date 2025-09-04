"""
Input validation and sanitization utilities for GödelOS API endpoints.

Provides comprehensive validation to prevent injection attacks, malformed data,
and other security vulnerabilities.
"""

import re
import html
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
import logging

logger = logging.getLogger(__name__)

class InputValidator:
    """Comprehensive input validation and sanitization."""
    
    # Security patterns
    DANGEROUS_PATTERNS = [
        r'<script[^>]*>.*?</script>',  # Script tags
        r'javascript:',               # JavaScript URLs
        r'on\w+\s*=',                # Event handlers
        r'eval\s*\(',                # eval() calls
        r'exec\s*\(',                # exec() calls
        r'__import__',               # Python imports
        r'\.{2,}/',                  # Directory traversal
        r'[;\'"&<>]',               # SQL injection chars
    ]
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000, allow_html: bool = False) -> str:
        """Sanitize a string input."""
        if not isinstance(value, str):
            raise ValueError("Input must be a string")
        
        # Limit length
        if len(value) > max_length:
            raise ValueError(f"Input too long (max {max_length} characters)")
        
        # HTML escape if not allowing HTML
        if not allow_html:
            value = html.escape(value)
        
        # Check for dangerous patterns
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                logger.warning(f"Potentially dangerous pattern detected: {pattern}")
                raise ValueError("Input contains potentially dangerous content")
        
        # Basic cleanup
        value = value.strip()
        
        return value
    
    @classmethod
    def validate_url(cls, url: str) -> str:
        """Validate and sanitize a URL."""
        if not isinstance(url, str):
            raise ValueError("URL must be a string")
        
        # Basic length check
        if len(url) > 2048:
            raise ValueError("URL too long (max 2048 characters)")
        
        # Parse URL
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        # Check scheme
        if parsed.scheme not in ['http', 'https']:
            raise ValueError("URL must use HTTP or HTTPS protocol")
        
        # Check for localhost/private IPs in production
        if parsed.hostname:
            hostname = parsed.hostname.lower()
            if hostname in ['localhost', '127.0.0.1', '0.0.0.0']:
                logger.warning(f"Request to localhost/private IP: {hostname}")
                # Allow in development, but log the warning
        
        return url
    
    @classmethod
    def validate_topic(cls, topic: str) -> str:
        """Validate a Wikipedia topic or knowledge title."""
        if not isinstance(topic, str):
            raise ValueError("Topic must be a string")
        
        # Length limits
        if len(topic) < 1:
            raise ValueError("Topic cannot be empty")
        if len(topic) > 200:
            raise ValueError("Topic too long (max 200 characters)")
        
        # Basic sanitization
        topic = cls.sanitize_string(topic, max_length=200)
        
        # Additional checks for Wikipedia topics
        if '..' in topic or '/' in topic:
            raise ValueError("Invalid characters in topic")
        
        return topic
    
    @classmethod
    def validate_language_code(cls, lang: str) -> str:
        """Validate a language code."""
        if not isinstance(lang, str):
            raise ValueError("Language code must be a string")
        
        # Basic format check (ISO 639-1)
        if not re.match(r'^[a-z]{2}$', lang):
            raise ValueError("Invalid language code format (use ISO 639-1, e.g., 'en', 'es')")
        
        return lang
    
    @classmethod
    def validate_category(cls, category: str) -> str:
        """Validate a category name."""
        if not isinstance(category, str):
            raise ValueError("Category must be a string")
        
        # Length and content checks
        if len(category) > 50:
            raise ValueError("Category name too long (max 50 characters)")
        
        category = cls.sanitize_string(category, max_length=50)
        
        # Only allow alphanumeric, spaces, hyphens, underscores
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', category):
            raise ValueError("Category contains invalid characters")
        
        return category
    
    @classmethod
    def validate_text_content(cls, content: str, max_length: int = 100000) -> str:
        """Validate text content for knowledge import."""
        if not isinstance(content, str):
            raise ValueError("Content must be a string")
        
        if len(content) < 10:
            raise ValueError("Content too short (minimum 10 characters)")
        
        if len(content) > max_length:
            raise ValueError(f"Content too long (max {max_length} characters)")
        
        # Allow some HTML but sanitize dangerous content
        content = cls.sanitize_string(content, max_length=max_length, allow_html=True)
        
        return content
    
    @classmethod
    def validate_session_id(cls, session_id: str) -> str:
        """Validate a session ID format."""
        if not isinstance(session_id, str):
            raise ValueError("Session ID must be a string")
        
        # Check format (should be our generated format)
        if not re.match(r'^session_[a-f0-9]{32}_[a-f0-9]{16}$', session_id):
            raise ValueError("Invalid session ID format")
        
        return session_id
    
    @classmethod
    def validate_import_request(cls, request: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize a knowledge import request."""
        validated = {}
        
        # Handle different import types
        if 'topic' in request or 'title' in request:
            # Wikipedia import
            topic = request.get('topic') or request.get('title')
            validated['topic'] = cls.validate_topic(topic)
            
            if 'language' in request:
                validated['language'] = cls.validate_language_code(request['language'])
                
        elif 'url' in request or 'source_url' in request:
            # URL import
            url = request.get('url') or request.get('source_url')
            validated['url'] = cls.validate_url(url)
            
        elif 'content' in request:
            # Text import
            validated['content'] = cls.validate_text_content(request['content'])
        
        # Common fields
        if 'category' in request:
            validated['category'] = cls.validate_category(request['category'])
        
        # Validate metadata if present
        if 'metadata' in request and isinstance(request['metadata'], dict):
            validated['metadata'] = cls.sanitize_metadata(request['metadata'])
        
        return validated
    
    @classmethod
    def sanitize_metadata(cls, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize metadata dictionary."""
        sanitized = {}
        
        for key, value in metadata.items():
            # Validate key
            if not isinstance(key, str) or len(key) > 50:
                continue
                
            key = cls.sanitize_string(key, max_length=50)
            
            # Sanitize value based on type
            if isinstance(value, str):
                if len(value) <= 500:  # Only include reasonable length strings
                    sanitized[key] = cls.sanitize_string(value, max_length=500)
            elif isinstance(value, (int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, list) and len(value) <= 10:
                # Sanitize list items
                sanitized_list = []
                for item in value:
                    if isinstance(item, str) and len(item) <= 100:
                        sanitized_list.append(cls.sanitize_string(item, max_length=100))
                if sanitized_list:
                    sanitized[key] = sanitized_list
        
        return sanitized

# Global validator instance
validator = InputValidator()