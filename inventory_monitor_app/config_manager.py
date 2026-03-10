"""
Configuration Manager for Inventory Monitor Application
Handles loading and validation of configuration settings
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class ConfigManager:
    def __init__(self, config_path: str = 'config.json'):
        """Initialize configuration manager."""
        self.config_path = config_path
        self.config = self._load_config()
        self._validate_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        try:
            if not os.path.exists(self.config_path):
                logger.warning(f"Config file {self.config_path} not found, creating default config")
                self._create_default_config()
            
            with open(self.config_path, 'r') as f:
                config = json.load(f)
            
            # Override with environment variables if present
            config = self._override_with_env_vars(config)
            
            logger.info(f"Configuration loaded from {self.config_path}")
            return config
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def _create_default_config(self):
        """Create a default configuration file."""
        default_config = {
            "databases": {
                "quickbooks": {
                    "connection_string": "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\\Users\\User\\Documents\\Quickbooks database\\Insitu-aug8-24QBW.QBW;",
                    "enabled": True
                },
                "access": {
                    "connection_string": "Driver={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=\\\\INSITU-SERV2022\\NetServ_2\\Manufacturing-Operations\\DATABASE\\Insitu Program MASTER.mdb;",
                    "enabled": True
                }
            },
            "monitoring": {
                "interval_minutes": 30,
                "check_timeout_seconds": 300,
                "retry_attempts": 3,
                "retry_delay_seconds": 60
            },
            "thresholds": {
                "default_warning": 10,
                "default_critical": 5,
                "items": {
                    # Example item-specific thresholds
                    # "PART-001": {"warning": 15, "critical": 8},
                    # "PART-002": {"warning": 20, "critical": 10}
                }
            },
            "slack": {
                "webhooks": [
                    {
                        "name": "Production Team",
                        "url": "YOUR_SLACK_WEBHOOK_URL_1",
                        "enabled": True
                    },
                    {
                        "name": "Inventory Team", 
                        "url": "YOUR_SLACK_WEBHOOK_URL_2",
                        "enabled": True
                    },
                    {
                        "name": "Management",
                        "url": "YOUR_SLACK_WEBHOOK_URL_3", 
                        "enabled": True
                    }
                ],
                "notification_cooldown_minutes": 60,
                "include_item_details": True
            },
            "logging": {
                "level": "INFO",
                "file_path": "inventory_monitor.log",
                "max_file_size_mb": 10,
                "backup_count": 5
            }
        }
        
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        logger.info(f"Default configuration created at {self.config_path}")
    
    def _override_with_env_vars(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Override configuration with environment variables."""
        # Database connection strings
        if os.getenv('QB_CONNECTION_STRING'):
            config['databases']['quickbooks']['connection_string'] = os.getenv('QB_CONNECTION_STRING')
        
        if os.getenv('ACCESS_CONNECTION_STRING'):
            config['databases']['access']['connection_string'] = os.getenv('ACCESS_CONNECTION_STRING')
        
        # Slack webhooks
        slack_webhooks = []
        for i in range(1, 4):  # Support up to 3 webhooks
            webhook_url = os.getenv(f'SLACK_WEBHOOK_{i}')
            if webhook_url:
                slack_webhooks.append({
                    "name": f"Webhook {i}",
                    "url": webhook_url,
                    "enabled": True
                })
        
        if slack_webhooks:
            config['slack']['webhooks'] = slack_webhooks
        
        return config
    
    def _validate_config(self):
        """Validate configuration settings."""
        required_sections = ['databases', 'monitoring', 'thresholds', 'slack', 'logging']
        
        for section in required_sections:
            if section not in self.config:
                raise ValueError(f"Missing required configuration section: {section}")
        
        # Validate database connections
        if not self.config['databases'].get('quickbooks', {}).get('enabled', False) and \
           not self.config['databases'].get('access', {}).get('enabled', False):
            raise ValueError("At least one database must be enabled")
        
        # Validate Slack webhooks
        enabled_webhooks = [w for w in self.config['slack']['webhooks'] if w.get('enabled', False)]
        if not enabled_webhooks:
            raise ValueError("At least one Slack webhook must be enabled")
        
        for webhook in enabled_webhooks:
            url = webhook.get('url', '')
            if not url or url.startswith('YOUR_SLACK_WEBHOOK') or url == 'SLACK-HOOK-URL-FOR-CHANNEL':
                raise ValueError(f"Invalid Slack webhook URL for {webhook.get('name', 'Unknown')} — replace the placeholder with a real webhook URL")
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value using dot notation."""
        keys = key.split('.')
        value = self.config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def get_database_config(self, db_type: str) -> Optional[Dict[str, Any]]:
        """Get database configuration for specified type."""
        return self.config['databases'].get(db_type)
    
    def get_threshold(self, item_number: str) -> Dict[str, int]:
        """Get threshold settings for a specific item."""
        item_thresholds = self.config['thresholds']['items'].get(item_number, {})
        return {
            'warning': item_thresholds.get('warning', self.config['thresholds']['default_warning']),
            'critical': item_thresholds.get('critical', self.config['thresholds']['default_critical'])
        }
    
    def get_enabled_slack_webhooks(self) -> list:
        """Get list of enabled Slack webhooks."""
        return [w for w in self.config['slack']['webhooks'] if w.get('enabled', False)]
    
    def reload(self):
        """Reload configuration from file."""
        self.config = self._load_config()
        self._validate_config()
        logger.info("Configuration reloaded")
