"""
Debug script to test the new QBApp banner logic for inventory calculations
Specifically tests part 19527533 to verify it shows the correct inventory level
"""

import sys
import os
import logging
from typing import Dict, Any

# Add the current directory to the path so we can import our modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config_manager import ConfigManager
from database_manager import DatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_inventory_query():
    """Test the new inventory query logic."""
    try:
        # Initialize config and database manager
        config = ConfigManager()
        db_manager = DatabaseManager(config)
        
        # Test database connections
        logger.info("Testing database connections...")
        db_manager.test_connections()
        
        # Get inventory data using the new QBApp logic
        logger.info("Retrieving inventory data using QBApp banner logic...")
        inventory_items = db_manager.get_access_inventory()
        
        logger.info(f"Total inventory items retrieved: {len(inventory_items)}")
        
        # Look specifically for part 19527533
        target_part = "19527533"
        found_item = None
        
        for item in inventory_items:
            if item['part_number'] == target_part:
                found_item = item
                break
        
        if found_item:
            logger.info(f"✓ Found part {target_part}:")
            logger.info(f"  Part Name: {found_item['part_name']}")
            logger.info(f"  Total Received: {found_item['quantity_received']}")
            logger.info(f"  Total Converted: {found_item['quantity_converted']}")
            logger.info(f"  Units on Hand: {found_item['quantity_on_hand']}")
            
            # Verify the calculation matches QBApp logic
            calculated_on_hand = found_item['quantity_received'] - found_item['quantity_converted']
            if calculated_on_hand == found_item['quantity_on_hand']:
                logger.info(f"✓ Calculation verified: {found_item['quantity_received']} - {found_item['quantity_converted']} = {calculated_on_hand}")
            else:
                logger.error(f"✗ Calculation mismatch: Expected {calculated_on_hand}, got {found_item['quantity_on_hand']}")
                
            # Check if this matches the expected QBApp value (23)
            if found_item['quantity_on_hand'] == 23:
                logger.info("✓ SUCCESS: Part 19527533 shows correct inventory level (23) matching QBApp")
            else:
                logger.warning(f"⚠ Part 19527533 shows {found_item['quantity_on_hand']} instead of expected 23")
        else:
            logger.error(f"✗ Part {target_part} not found in inventory data")
        
        # Show a few other parts for verification
        logger.info("\nSample of other inventory items:")
        for i, item in enumerate(inventory_items[:5]):
            logger.info(f"  {i+1}. {item['part_number']}: {item['quantity_on_hand']} units on hand")
        
        # Close connections
        db_manager.close_connections()
        
    except Exception as e:
        logger.error(f"Error during inventory test: {e}")
        raise

def test_part_filtering():
    """Test that only balloon/stent parts are included."""
    try:
        config = ConfigManager()
        db_manager = DatabaseManager(config)
        
        inventory_items = db_manager.get_access_inventory()
        
        # Check part number patterns
        balloon_stent_patterns = ['19T', '19S', '19N', '22PM', '22C', '18', '17', '15H']
        non_balloon_stent_parts = []
        
        for item in inventory_items:
            part_number = item['part_number']
            is_balloon_stent = False
            
            for pattern in balloon_stent_patterns:
                if part_number.startswith(pattern):
                    # Special case for 17 pattern
                    if pattern == '17' and part_number.endswith('MM'):
                        continue
                    is_balloon_stent = True
                    break
            
            if not is_balloon_stent:
                non_balloon_stent_parts.append(part_number)
        
        if non_balloon_stent_parts:
            logger.warning(f"Found {len(non_balloon_stent_parts)} non-balloon/stent parts in results:")
            for part in non_balloon_stent_parts[:10]:  # Show first 10
                logger.warning(f"  - {part}")
        else:
            logger.info("✓ All parts in results match balloon/stent criteria")
        
        db_manager.close_connections()
        
    except Exception as e:
        logger.error(f"Error during part filtering test: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting inventory debug tests...")
    
    print("=" * 60)
    print("TEST 1: Inventory Query Logic")
    print("=" * 60)
    test_inventory_query()
    
    print("\n" + "=" * 60)
    print("TEST 2: Part Filtering")
    print("=" * 60)
    test_part_filtering()
    
    logger.info("Debug tests completed!")
