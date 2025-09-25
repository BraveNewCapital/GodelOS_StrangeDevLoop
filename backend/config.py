"""
Configuration module for GödelOS Backend API

Manages environment variables, settings, and configuration options.
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings."""

    # Server configuration
    host: str = Field(default="0.0.0.0", env="GODELOS_HOST")
    port: int = Field(default=8000, env="GODELOS_PORT")
    debug: bool = Field(default=False, env="GODELOS_DEBUG")

    # API configuration
    api_title: str = Field(default="GödelOS API", env="GODELOS_API_TITLE")
    api_description: str = Field(
        default="Backend API for the GödelOS web demonstration interface",
        env="GODELOS_API_DESCRIPTION"
    )
    api_version: str = Field(default="1.0.0", env="GODELOS_API_VERSION")

    # CORS configuration
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000", "http://127.0.0.1:3000",
            "http://localhost:3002", "http://127.0.0.1:3002"
        ],
        env="GODELOS_CORS_ORIGINS"
    )
    cors_allow_credentials: bool = Field(default=True, env="GODELOS_CORS_CREDENTIALS")

    # Logging configuration
    log_level: str = Field(default="INFO", env="GODELOS_LOG_LEVEL")
    log_file: Optional[str] = Field(default="logs/godelos_backend.log", env="GODELOS_LOG_FILE")

    # GödelOS system configuration
    godelos_initialization_timeout: int = Field(default=60, env="GODELOS_INIT_TIMEOUT")
    godelos_query_timeout: int = Field(default=30, env="GODELOS_QUERY_TIMEOUT")
    godelos_max_knowledge_items: int = Field(default=1000, env="GODELOS_MAX_KNOWLEDGE")

    # WebSocket configuration
    websocket_ping_interval: int = Field(default=30, env="GODELOS_WS_PING_INTERVAL")
    websocket_max_connections: int = Field(default=100, env="GODELOS_WS_MAX_CONNECTIONS")
    websocket_event_queue_size: int = Field(default=1000, env="GODELOS_WS_QUEUE_SIZE")

    # Performance configuration
    max_concurrent_queries: int = Field(default=10, env="GODELOS_MAX_CONCURRENT_QUERIES")
    cache_size: int = Field(default=100, env="GODELOS_CACHE_SIZE")
    cache_ttl_seconds: int = Field(default=300, env="GODELOS_CACHE_TTL")

    # Security configuration
    enable_api_key_auth: bool = Field(default=False, env="GODELOS_ENABLE_API_KEY")
    api_key: Optional[str] = Field(default=None, env="GODELOS_API_KEY")
    rate_limit_requests_per_minute: int = Field(default=60, env="GODELOS_RATE_LIMIT")

    # Database/Storage configuration (for future use)
    database_url: Optional[str] = Field(default=None, env="GODELOS_DATABASE_URL")
    redis_url: Optional[str] = Field(default=None, env="GODELOS_REDIS_URL")

    # Monitoring configuration
    enable_metrics: bool = Field(default=True, env="GODELOS_ENABLE_METRICS")
    metrics_port: int = Field(default=8001, env="GODELOS_METRICS_PORT")
    health_check_interval: int = Field(default=30, env="GODELOS_HEALTH_CHECK_INTERVAL")

    # Reconciliation monitor configuration
    # Defaults keep diffing off to minimize load; enable via env when needed
    reconciliation_enabled: bool = Field(default=True, env="GODELOS_RECONCILIATION_ENABLED")
    reconciliation_interval_seconds: int = Field(default=30, env="GODELOS_RECONCILIATION_INTERVAL_SECONDS")
    reconciliation_emit_summary_every_n_cycles: int = Field(default=1, env="GODELOS_RECONCILIATION_EMIT_SUMMARY_EVERY_N")
    reconciliation_max_discrepancies_per_cycle: int = Field(default=100, env="GODELOS_RECONCILIATION_MAX_DISCREPANCIES")
    reconciliation_include_statement_diffs: bool = Field(default=False, env="GODELOS_RECONCILIATION_INCLUDE_STATEMENT_DIFFS")
    reconciliation_statements_limit: Optional[int] = Field(default=200, env="GODELOS_RECONCILIATION_STATEMENTS_LIMIT")
    # Optional: comma-separated list of contexts to check (parsed by server wiring if provided)
    reconciliation_contexts_to_check: Optional[str] = Field(default=None, env="GODELOS_RECONCILIATION_CONTEXTS")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False
    }

class DevelopmentSettings(Settings):
    """Development environment settings."""
    debug: bool = True
    log_level: str = "DEBUG"
    cors_origins: List[str] = ["*"]  # Allow all origins in development
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8", 
        "case_sensitive": False,
        "extra": "allow"  # Allow extra fields for development flexibility
    }

class ProductionSettings(Settings):
    """Production environment settings."""
    debug: bool = False
    log_level: str = "INFO"
    enable_api_key_auth: bool = True

class TestingSettings(Settings):
    """Testing environment settings."""
    debug: bool = True
    log_level: str = "DEBUG"
    godelos_initialization_timeout: int = 10
    godelos_query_timeout: int = 5
    websocket_max_connections: int = 10

def get_settings() -> Settings:
    """Get application settings based on environment."""
    environment = os.getenv("GODELOS_ENVIRONMENT", "development").lower()

    if environment == "production":
        return ProductionSettings()
    elif environment == "testing":
        return TestingSettings()
    else:
        return DevelopmentSettings()

# Global settings instance
settings = get_settings()
