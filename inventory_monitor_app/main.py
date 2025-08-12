#!/usr/bin/env python3
"""
Inventory Monitor Application
Monitors inventory levels from QuickBooks and Access databases
Sends Slack notifications when items reach low stock thresholds
"""

import os
import sys
import time
import logging
import argparse
import schedule
from datetime import datetime
from pathlib import Path

# Add the app directory to Python path
sys.path.append(str(Path(__file__).parent))

from database_manager import DatabaseManager
from inventory_monitor import InventoryMonitor
from slack_notifier import SlackNotifier
from config_manager import ConfigManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('inventory_monitor.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class InventoryMonitorApp:
    def __init__(self, config_path='config.json'):
        """Initialize the inventory monitoring application."""
        self.config = ConfigManager(config_path)
        self.db_manager = DatabaseManager(self.config)
        self.slack_notifier = SlackNotifier(self.config)
        self.monitor = InventoryMonitor(self.config, self.db_manager, self.slack_notifier)
        
    def run_once(self):
        """Run inventory check once."""
        try:
            logger.info("Starting inventory check...")
            self.monitor.check_inventory_levels()
            logger.info("Inventory check completed successfully")
        except Exception as e:
            logger.error(f"Error during inventory check: {e}")
            self.slack_notifier.send_error_notification(f"Inventory check failed: {e}")
    
    def run_scheduled(self):
        """Run inventory monitoring on schedule."""
        logger.info("Starting scheduled inventory monitoring...")
        
        # Schedule the monitoring job
        schedule.every(self.config.get('monitoring_interval_minutes', 30)).minutes.do(self.run_once)
        
        # Run once immediately
        self.run_once()
        
        # Keep running the scheduled jobs
        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except KeyboardInterrupt:
                logger.info("Stopping inventory monitoring...")
                break
            except Exception as e:
                logger.error(f"Error in scheduled monitoring: {e}")
                time.sleep(300)  # Wait 5 minutes before retrying
    
    def health_check(self):
        """Perform health check of all components."""
        try:
            # Test database connections
            self.db_manager.test_connections()
            
            # Test Slack notifications
            self.slack_notifier.send_test_notification()
            
            logger.info("Health check passed")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Inventory Monitor Application')
    parser.add_argument('--config', default='config.json', help='Path to configuration file')
    parser.add_argument('--once', action='store_true', help='Run inventory check once and exit')
    parser.add_argument('--health', action='store_true', help='Run health check and exit')
    parser.add_argument('--daemon', action='store_true', help='Run as daemon/service')
    
    args = parser.parse_args()
    
    try:
        app = InventoryMonitorApp(args.config)
        
        if args.health:
            success = app.health_check()
            sys.exit(0 if success else 1)
        
        if args.once:
            app.run_once()
        else:
            app.run_scheduled()
            
    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
