"""
Slack Notifier for Inventory Monitor Application
Handles sending notifications to multiple Slack webhooks
"""

import logging
import requests
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class SlackNotifier:
    def __init__(self, config_manager):
        """Initialize Slack notifier."""
        self.config = config_manager
        self.webhooks = self.config.get_enabled_slack_webhooks()
        self.session = requests.Session()
        self.session.timeout = 30  # 30 second timeout
    
    def send_notification(self, message: str, color: str = 'good', title: str = None, 
                         fields: List[Dict[str, str]] = None) -> bool:
        """
        Send notification to all enabled Slack webhooks.
        
        Args:
            message: Main message text
            color: Color for the message (good, warning, danger)
            title: Optional title for the message
            fields: Optional list of field dictionaries with 'title' and 'value' keys
        
        Returns:
            bool: True if at least one notification was sent successfully
        """
        if not self.webhooks:
            logger.error("No enabled Slack webhooks configured")
            return False
        
        # Create Slack message payload
        payload = self._create_slack_payload(message, color, title, fields)
        
        success_count = 0
        total_webhooks = len(self.webhooks)
        
        for webhook in self.webhooks:
            try:
                success = self._send_to_webhook(webhook, payload)
                if success:
                    success_count += 1
                    logger.debug(f"Successfully sent notification to {webhook['name']}")
                else:
                    logger.warning(f"Failed to send notification to {webhook['name']}")
                    
            except Exception as e:
                logger.error(f"Error sending notification to {webhook['name']}: {e}")
        
        if success_count > 0:
            logger.info(f"Sent notifications to {success_count}/{total_webhooks} webhooks")
            return True
        else:
            logger.error("Failed to send notifications to any webhook")
            return False
    
    def _create_slack_payload(self, message: str, color: str = 'good', 
                             title: str = None, fields: List[Dict[str, str]] = None) -> Dict[str, Any]:
        """Create Slack message payload with attachments."""
        timestamp = datetime.now().timestamp()
        
        # Create attachment
        attachment = {
            "color": color,
            "text": message,
            "ts": timestamp
        }
        
        if title:
            attachment["title"] = title
        
        if fields:
            attachment["fields"] = fields
        
        # Add footer with timestamp
        attachment["footer"] = "Inventory Monitor"
        attachment["footer_icon"] = "https://platform.slack-edge.com/img/default_application_icon.png"
        
        payload = {
            "attachments": [attachment]
        }
        
        return payload
    
    def _send_to_webhook(self, webhook: Dict[str, Any], payload: Dict[str, Any]) -> bool:
        """Send payload to a specific webhook."""
        try:
            response = self.session.post(
                webhook['url'],
                json=payload,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get('ok') or response_data.get('ok') is None:
                    return True
                else:
                    logger.error(f"Slack API error for {webhook['name']}: {response_data}")
                    return False
            else:
                logger.error(f"HTTP error {response.status_code} for {webhook['name']}: {response.text}")
                return False
                
        except requests.exceptions.Timeout:
            logger.error(f"Timeout sending notification to {webhook['name']}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error sending notification to {webhook['name']}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending notification to {webhook['name']}: {e}")
            return False
    
    def send_test_notification(self) -> bool:
        """Send a test notification to verify webhook configuration."""
        test_message = "🧪 This is a test notification from the Inventory Monitor application."
        test_fields = [
            {
                "title": "Status",
                "value": "✅ System is operational",
                "short": True
            },
            {
                "title": "Timestamp",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "short": True
            }
        ]
        
        logger.info("Sending test notification...")
        success = self.send_notification(
            message=test_message,
            color='good',
            title='Inventory Monitor Test',
            fields=test_fields
        )
        
        if success:
            logger.info("Test notification sent successfully")
        else:
            logger.error("Test notification failed")
        
        return success
    
    def send_error_notification(self, error_message: str) -> bool:
        """Send error notification to all webhooks."""
        error_fields = [
            {
                "title": "Error Type",
                "value": "System Error",
                "short": True
            },
            {
                "title": "Timestamp",
                "value": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "short": True
            }
        ]
        
        return self.send_notification(
            message=f"❌ {error_message}",
            color='danger',
            title='Inventory Monitor Error',
            fields=error_fields
        )
    
    def send_inventory_summary(self, summary: Dict[str, Any]) -> bool:
        """Send inventory summary notification."""
        if 'error' in summary:
            return self.send_error_notification(f"Inventory summary error: {summary['error']}")
        
        # Create summary message
        message_parts = [
            f"📊 *Inventory Summary Report*",
            f"",
            f"• Total Items: {summary['total_items']}",
            f"• Critical Items: {summary['critical_items']}",
            f"• Warning Items: {summary['warning_items']}",
            f"• Normal Items: {summary['normal_items']}"
        ]
        
        # Add source breakdown
        if summary['sources']:
            message_parts.append("")
            message_parts.append("*By Source:*")
            for source, count in summary['sources'].items():
                message_parts.append(f"• {source.title()}: {count}")
        
        message = "\n".join(message_parts)
        
        # Determine color based on critical items
        if summary['critical_items'] > 0:
            color = 'danger'
        elif summary['warning_items'] > 0:
            color = 'warning'
        else:
            color = 'good'
        
        # Create fields for additional details
        fields = [
            {
                "title": "Last Check",
                "value": summary['last_check'],
                "short": True
            },
            {
                "title": "Status",
                "value": "⚠️ Needs Attention" if summary['critical_items'] > 0 or summary['warning_items'] > 0 else "✅ All Good",
                "short": True
            }
        ]
        
        return self.send_notification(
            message=message,
            color=color,
            title='Inventory Summary',
            fields=fields
        )
    
    def send_custom_notification(self, message: str, webhook_name: str = None) -> bool:
        """Send a custom notification to specific webhook or all webhooks."""
        if webhook_name:
            # Send to specific webhook
            webhook = next((w for w in self.webhooks if w['name'] == webhook_name), None)
            if not webhook:
                logger.error(f"Webhook '{webhook_name}' not found")
                return False
            
            payload = self._create_slack_payload(message)
            return self._send_to_webhook(webhook, payload)
        else:
            # Send to all webhooks
            return self.send_notification(message)
    
    def get_webhook_status(self) -> Dict[str, Any]:
        """Get status of all configured webhooks."""
        status = {
            'total_webhooks': len(self.webhooks),
            'enabled_webhooks': len([w for w in self.webhooks if w.get('enabled', True)]),
            'webhooks': []
        }
        
        for webhook in self.webhooks:
            webhook_status = {
                'name': webhook['name'],
                'enabled': webhook.get('enabled', True),
                'url_configured': bool(webhook.get('url')),
                'url_masked': self._mask_url(webhook.get('url', ''))
            }
            status['webhooks'].append(webhook_status)
        
        return status
    
    def _mask_url(self, url: str) -> str:
        """Mask webhook URL for security in logs."""
        if not url or len(url) < 20:
            return "***"
        
        # Show first 10 and last 10 characters
        return f"{url[:10]}...{url[-10:]}"
