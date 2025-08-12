"""
Inventory Monitor Core Logic
Checks inventory levels against thresholds and triggers notifications
"""

import logging
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class InventoryMonitor:
    def __init__(self, config_manager, database_manager, slack_notifier):
        """Initialize inventory monitor."""
        self.config = config_manager
        self.db_manager = database_manager
        self.slack_notifier = slack_notifier
        self.notification_history = {}
        self.cooldown_file = Path("notification_cooldown.json")
        self._load_notification_history()
    
    def _load_notification_history(self):
        """Load notification history from file."""
        try:
            if self.cooldown_file.exists():
                with open(self.cooldown_file, 'r') as f:
                    self.notification_history = json.load(f)
                logger.info("Loaded notification history")
            else:
                self.notification_history = {}
        except Exception as e:
            logger.error(f"Error loading notification history: {e}")
            self.notification_history = {}
    
    def _save_notification_history(self):
        """Save notification history to file."""
        try:
            with open(self.cooldown_file, 'w') as f:
                json.dump(self.notification_history, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving notification history: {e}")
    
    def _can_send_notification(self, item_id: str, level: str) -> bool:
        """Check if notification can be sent based on cooldown period."""
        cooldown_minutes = self.config.get('slack.notification_cooldown_minutes', 60)
        current_time = datetime.now()
        
        # Get last notification time for this item and level
        history_key = f"{item_id}_{level}"
        last_notification = self.notification_history.get(history_key)
        
        if not last_notification:
            return True
        
        # Parse last notification time
        try:
            last_time = datetime.fromisoformat(last_notification)
            time_diff = current_time - last_time
            
            if time_diff.total_seconds() > (cooldown_minutes * 60):
                return True
            else:
                remaining_minutes = int((cooldown_minutes * 60 - time_diff.total_seconds()) / 60)
                logger.debug(f"Notification for {item_id} ({level}) in cooldown. {remaining_minutes} minutes remaining")
                return False
                
        except Exception as e:
            logger.error(f"Error parsing notification history for {item_id}: {e}")
            return True
    
    def _update_notification_history(self, item_id: str, level: str):
        """Update notification history with current timestamp."""
        history_key = f"{item_id}_{level}"
        self.notification_history[history_key] = datetime.now().isoformat()
        self._save_notification_history()
    
    def _get_item_identifier(self, item: Dict[str, Any]) -> str:
        """Get unique identifier for an item."""
        if item.get('source') == 'quickbooks':
            return item.get('item_name', 'unknown')
        else:
            return item.get('part_number', 'unknown')
    
    def _get_item_display_name(self, item: Dict[str, Any]) -> str:
        """Get display name for an item."""
        if item.get('source') == 'quickbooks':
            return f"{item.get('item_name', 'Unknown')} ({item.get('description', 'No description')})"
        else:
            return f"{item.get('part_number', 'Unknown')} ({item.get('part_name', 'No name')})"
    
    def _check_item_thresholds(self, item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check if item meets any threshold criteria."""
        alerts = []
        item_id = self._get_item_identifier(item)
        display_name = self._get_item_display_name(item)
        current_qty = item.get('quantity_on_hand', 0)
        
        # Get thresholds for this item
        thresholds = self.config.get_threshold(item_id)
        warning_threshold = thresholds['warning']
        critical_threshold = thresholds['critical']
        
        # Check critical threshold first
        if current_qty <= critical_threshold:
            if self._can_send_notification(item_id, 'critical'):
                alert = {
                    'item_id': item_id,
                    'display_name': display_name,
                    'current_quantity': current_qty,
                    'threshold': critical_threshold,
                    'level': 'critical',
                    'message': f"🚨 CRITICAL: {display_name} has only {current_qty} units remaining (threshold: {critical_threshold})",
                    'color': 'danger',
                    'source': item.get('source', 'unknown')
                }
                alerts.append(alert)
                self._update_notification_history(item_id, 'critical')
        
        # Check warning threshold
        elif current_qty <= warning_threshold:
            if self._can_send_notification(item_id, 'warning'):
                alert = {
                    'item_id': item_id,
                    'display_name': display_name,
                    'current_quantity': current_qty,
                    'threshold': warning_threshold,
                    'level': 'warning',
                    'message': f"⚠️ WARNING: {display_name} has {current_qty} units remaining (threshold: {warning_threshold})",
                    'color': 'warning',
                    'source': item.get('source', 'unknown')
                }
                alerts.append(alert)
                self._update_notification_history(item_id, 'warning')
        
        return alerts
    
    def check_inventory_levels(self):
        """Main method to check inventory levels and send notifications."""
        logger.info("Starting inventory level check...")
        
        try:
            # Get inventory from all databases
            inventory_items = self.db_manager.get_combined_inventory()
            
            if not inventory_items:
                logger.warning("No inventory items found")
                return
            
            # Check each item against thresholds
            all_alerts = []
            items_checked = 0
            
            for item in inventory_items:
                try:
                    alerts = self._check_item_thresholds(item)
                    all_alerts.extend(alerts)
                    items_checked += 1
                except Exception as e:
                    item_id = self._get_item_identifier(item)
                    logger.error(f"Error checking thresholds for item {item_id}: {e}")
            
            # Send notifications for all alerts
            if all_alerts:
                logger.info(f"Found {len(all_alerts)} items requiring notifications")
                self._send_alerts(all_alerts)
            else:
                logger.info("No items require notifications at this time")
            
            logger.info(f"Inventory check completed. Checked {items_checked} items, sent {len(all_alerts)} notifications")
            
        except Exception as e:
            logger.error(f"Error during inventory level check: {e}")
            raise
    
    def _send_alerts(self, alerts: List[Dict[str, Any]]):
        """Send alerts via Slack notifications."""
        try:
            # Group alerts by level for better organization
            critical_alerts = [a for a in alerts if a['level'] == 'critical']
            warning_alerts = [a for a in alerts if a['level'] == 'warning']
            
            # Send critical alerts first
            if critical_alerts:
                self._send_alert_group(critical_alerts, "Critical Inventory Alerts")
            
            # Send warning alerts
            if warning_alerts:
                self._send_alert_group(warning_alerts, "Warning Inventory Alerts")
                
        except Exception as e:
            logger.error(f"Error sending alerts: {e}")
            raise
    
    def _send_alert_group(self, alerts: List[Dict[str, Any]], title: str):
        """Send a group of alerts with a title."""
        try:
            # Create detailed message
            message_parts = [f"*{title}*"]
            
            for alert in alerts:
                item_details = f"• {alert['display_name']}"
                quantity_info = f"Current: {alert['current_quantity']}, Threshold: {alert['threshold']}"
                source_info = f"Source: {alert['source'].title()}"
                
                message_parts.append(f"{item_details}\n  {quantity_info} | {source_info}")
            
            # Join all parts
            full_message = "\n".join(message_parts)
            
            # Send to all enabled Slack webhooks
            self.slack_notifier.send_notification(
                message=full_message,
                color=alerts[0]['color'] if alerts else 'warning',
                title=title
            )
            
            logger.info(f"Sent {len(alerts)} {alerts[0]['level']} alerts")
            
        except Exception as e:
            logger.error(f"Error sending alert group: {e}")
            raise
    
    def get_inventory_summary(self) -> Dict[str, Any]:
        """Get a summary of current inventory status."""
        try:
            inventory_items = self.db_manager.get_combined_inventory()
            
            summary = {
                'total_items': len(inventory_items),
                'critical_items': 0,
                'warning_items': 0,
                'normal_items': 0,
                'sources': {},
                'last_check': datetime.now().isoformat()
            }
            
            for item in inventory_items:
                item_id = self._get_item_identifier(item)
                current_qty = item.get('quantity_on_hand', 0)
                source = item.get('source', 'unknown')
                
                # Count by source
                if source not in summary['sources']:
                    summary['sources'][source] = 0
                summary['sources'][source] += 1
                
                # Check thresholds
                thresholds = self.config.get_threshold(item_id)
                if current_qty <= thresholds['critical']:
                    summary['critical_items'] += 1
                elif current_qty <= thresholds['warning']:
                    summary['warning_items'] += 1
                else:
                    summary['normal_items'] += 1
            
            return summary
            
        except Exception as e:
            logger.error(f"Error generating inventory summary: {e}")
            return {
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
