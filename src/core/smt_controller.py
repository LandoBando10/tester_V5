"""
SMT Controller - Simplified relay mapping version
"""
import logging
from typing import Dict, List, Optional, Any

from src.hardware.arduino_controller import ArduinoController

logger = logging.getLogger(__name__)


class SMTController:
    """Controls SMT panel testing using direct relay mapping from SKU config"""
    
    def __init__(self, arduino: ArduinoController):
        self.arduino = arduino
        self.relay_mapping: Dict[str, Dict[str, Any]] = {}
        self.panel_layout: Dict[str, Any] = {}
        
    def set_configuration(self, smt_config: Dict[str, Any]) -> None:
        """Set configuration from SKU JSON's smt_testing section"""
        self.relay_mapping = smt_config.get('relay_mapping', {})
        self.panel_layout = smt_config.get('panel_layout', {})
        
        # Log configuration
        logger.info(f"SMT Controller configured with {len(self.relay_mapping)} relay mappings")
        logger.debug(f"Relay mapping: {self.relay_mapping}")
        
    def initialize_arduino(self) -> bool:
        """Initialize Arduino for SMT testing"""
        try:
            # Check connection
            response = self.arduino.send_command("ID")
            if "SMT_TESTER" not in response:
                logger.error("Arduino not running SMT firmware")
                return False
                
            # Get relay count from mapping
            relay_count = len([r for r in self.relay_mapping.values() if r])
            logger.info(f"Configuring Arduino for {relay_count} active relays")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Arduino: {e}")
            return False
    
    def get_relays_for_function(self, function: str) -> List[int]:
        """Get all relay numbers that perform a specific function"""
        relays = []
        for relay_str, mapping in self.relay_mapping.items():
            if mapping and mapping.get('function') == function:
                relays.append(int(relay_str))
        return sorted(relays)
    
    def get_relay_for_board_function(self, board: int, function: str) -> Optional[int]:
        """Get relay number for a specific board and function"""
        for relay_str, mapping in self.relay_mapping.items():
            if mapping and mapping.get('board') == board and mapping.get('function') == function:
                return int(relay_str)
        return None
    
    def get_board_from_relay(self, relay_num: int) -> Optional[int]:
        """Get board number from relay number"""
        mapping = self.relay_mapping.get(str(relay_num))
        return mapping.get('board') if mapping else None
    
    def all_lights_off(self):
        """Turn off all relays"""
        self.arduino.send_command("RELAY_ALL:OFF")