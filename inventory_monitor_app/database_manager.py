"""
Database Manager for Inventory Monitor Application
Handles connections to QuickBooks and Access databases
"""

import pyodbc
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, config_manager):
        """Initialize database manager."""
        self.config = config_manager
        self.connections = {}
        self._setup_connections()
    
    def _setup_connections(self):
        """Setup database connections."""
        # QuickBooks connection
        qb_config = self.config.get_database_config('quickbooks')
        if qb_config and qb_config.get('enabled', False):
            self.connections['quickbooks'] = {
                'config': qb_config,
                'connection': None
            }
        
        # Access database connection
        access_config = self.config.get_database_config('access')
        if access_config and access_config.get('enabled', False):
            self.connections['access'] = {
                'config': access_config,
                'connection': None
            }
    
    def _get_connection(self, db_type: str) -> Optional[pyodbc.Connection]:
        """Get database connection with retry logic."""
        if db_type not in self.connections:
            logger.error(f"Database type {db_type} not configured")
            return None
        
        connection_info = self.connections[db_type]
        
        # Return existing connection if it's still valid
        if connection_info['connection']:
            try:
                # Test if connection is still alive
                connection_info['connection'].execute("SELECT 1")
                return connection_info['connection']
            except pyodbc.Error:
                logger.warning(f"Existing {db_type} connection is invalid, creating new one")
                connection_info['connection'] = None
        
        # Create new connection
        max_retries = self.config.get('monitoring.retry_attempts', 3)
        retry_delay = self.config.get('monitoring.retry_delay_seconds', 60)
        
        for attempt in range(max_retries):
            try:
                connection_string = connection_info['config']['connection_string']
                connection = pyodbc.connect(connection_string)
                connection_info['connection'] = connection
                logger.info(f"Successfully connected to {db_type} database")
                return connection
                
            except pyodbc.Error as e:
                logger.error(f"Failed to connect to {db_type} database (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise
    
    def test_connections(self):
        """Test all database connections."""
        for db_type in self.connections.keys():
            try:
                connection = self._get_connection(db_type)
                if connection:
                    logger.info(f"✓ {db_type} database connection test passed")
                else:
                    raise Exception(f"Failed to get {db_type} connection")
            except Exception as e:
                logger.error(f"✗ {db_type} database connection test failed: {e}")
                raise
    
    def get_quickbooks_inventory(self) -> List[Dict[str, Any]]:
        """Get inventory data from QuickBooks database."""
        connection = self._get_connection('quickbooks')
        if not connection:
            logger.error("QuickBooks connection not available")
            return []
        
        try:
            # Query QuickBooks inventory items
            # This query structure is based on typical QuickBooks database schema
            query = """
            SELECT 
                i.ListID,
                i.Name as ItemName,
                i.Description,
                i.QuantityOnHand,
                i.AverageCost,
                i.PurchaseCost,
                i.SalesPrice,
                i.IsActive
            FROM ItemInventory i
            WHERE i.IsActive = 1
            ORDER BY i.Name
            """
            
            cursor = connection.cursor()
            cursor.execute(query)
            
            inventory_items = []
            for row in cursor.fetchall():
                item = {
                    'list_id': row[0],
                    'item_name': row[1],
                    'description': row[2],
                    'quantity_on_hand': row[3] if row[3] is not None else 0,
                    'average_cost': row[4] if row[4] is not None else 0,
                    'purchase_cost': row[5] if row[5] is not None else 0,
                    'sales_price': row[6] if row[6] is not None else 0,
                    'is_active': bool(row[7]) if row[7] is not None else False
                }
                inventory_items.append(item)
            
            logger.info(f"Retrieved {len(inventory_items)} inventory items from QuickBooks")
            return inventory_items
            
        except pyodbc.Error as e:
            logger.error(f"Error querying QuickBooks inventory: {e}")
            raise
    
    def get_access_inventory(self) -> List[Dict[str, Any]]:
        """Get inventory data from Access database."""
        connection = self._get_connection('access')
        if not connection:
            logger.error("Access database connection not available")
            return []
        
        try:
            # Query Access database for supply inventory
            # Based on the tempSupplyInventoryNew table structure from the original code
            query = """
            SELECT 
                PartNumber,
                PartName,
                QuantityReceived,
                QuantityConverted,
                InProcessQuantity
            FROM tempSupplyInventoryNew
            ORDER BY PartNumber
            """
            
            cursor = connection.cursor()
            cursor.execute(query)
            
            inventory_items = []
            for row in cursor.fetchall():
                # Calculate on-hand quantity: Received - Converted + InProcess
                qty_received = row[2] if row[2] is not None else 0
                qty_converted = row[3] if row[3] is not None else 0
                qty_in_process = row[4] if row[4] is not None else 0
                on_hand = qty_received - qty_converted + qty_in_process
                
                item = {
                    'part_number': row[0],
                    'part_name': row[1],
                    'quantity_received': qty_received,
                    'quantity_converted': qty_converted,
                    'quantity_in_process': qty_in_process,
                    'quantity_on_hand': max(0, on_hand),  # Ensure non-negative
                    'source': 'access'
                }
                inventory_items.append(item)
            
            logger.info(f"Retrieved {len(inventory_items)} inventory items from Access database")
            return inventory_items
            
        except pyodbc.Error as e:
            logger.error(f"Error querying Access inventory: {e}")
            raise
    
    def get_combined_inventory(self) -> List[Dict[str, Any]]:
        """Get combined inventory data from all available databases."""
        all_inventory = []
        
        # Get QuickBooks inventory
        if 'quickbooks' in self.connections:
            try:
                qb_inventory = self.get_quickbooks_inventory()
                for item in qb_inventory:
                    item['source'] = 'quickbooks'
                    all_inventory.append(item)
            except Exception as e:
                logger.error(f"Failed to get QuickBooks inventory: {e}")
        
        # Get Access database inventory
        if 'access' in self.connections:
            try:
                access_inventory = self.get_access_inventory()
                all_inventory.extend(access_inventory)
            except Exception as e:
                logger.error(f"Failed to get Access inventory: {e}")
        
        logger.info(f"Combined inventory contains {len(all_inventory)} items")
        return all_inventory
    
    def close_connections(self):
        """Close all database connections."""
        for db_type, connection_info in self.connections.items():
            if connection_info['connection']:
                try:
                    connection_info['connection'].close()
                    logger.info(f"Closed {db_type} database connection")
                except Exception as e:
                    logger.error(f"Error closing {db_type} connection: {e}")
                finally:
                    connection_info['connection'] = None
    
    def __del__(self):
        """Cleanup connections on object destruction."""
        self.close_connections()
