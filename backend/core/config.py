"""
Configuration management for the backend system
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class BackendConfig:
    """Backend configuration settings"""
    # Server settings
    host: str = "0.0.0.0"
    port: int = 5000
    debug: bool = False
    secret_key: str = "gemma-backend-secret-key"
    
    # Discovery settings
    discovery_interval: float = 2.0  # Fast discovery rate in seconds
    discovery_timeout: float = 3.0   # Timeout for SUT ping
    sut_port: int = 8080
    
    # SUT identification
    sut_identifier_key: str = "gemma_sut_signature"
    sut_identifier_value: str = "gemma_sut_v2"
    
    # Network settings
    network_ranges: List[str] = None  # Will be auto-detected
    
    # Omniparser settings
    omniparser_url: str = "http://localhost:8000"
    
    # Logging
    log_level: str = "INFO"
    log_file: str = "backend.log"
    
    def __post_init__(self):
        """Initialize default network ranges if not provided"""
        if self.network_ranges is None:
            self.network_ranges = [
                "192.168.1.0/24",
                "192.168.50.0/24", 
                "127.0.0.1/32"
            ]


class ConfigManager:
    """Manages configuration loading and environment overrides"""
    
    @staticmethod
    def load_config() -> BackendConfig:
        """Load configuration with environment variable overrides"""
        config = BackendConfig()
        
        # Override with environment variables
        config.host = os.getenv("BACKEND_HOST", config.host)
        config.port = int(os.getenv("BACKEND_PORT", config.port))
        config.debug = os.getenv("BACKEND_DEBUG", "false").lower() == "true"
        config.secret_key = os.getenv("BACKEND_SECRET_KEY", config.secret_key)
        
        config.discovery_interval = float(os.getenv("DISCOVERY_INTERVAL", config.discovery_interval))
        config.discovery_timeout = float(os.getenv("DISCOVERY_TIMEOUT", config.discovery_timeout))
        config.sut_port = int(os.getenv("SUT_PORT", config.sut_port))
        
        config.omniparser_url = os.getenv("OMNIPARSER_URL", config.omniparser_url)
        
        config.log_level = os.getenv("LOG_LEVEL", config.log_level)
        config.log_file = os.getenv("LOG_FILE", config.log_file)
        
        return config