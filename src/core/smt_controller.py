"""
SMT Controller - Simplified relay mapping version
"""
import logging
from typing import Dict, List, Optional, Any, Union

# Support both controller types
try:
    from src.hardware.smt_arduino_controller import SMTArduinoController
except ImportError:
    SMTArduinoController = None
    
from src.hardware.arduino_controller import ArduinoController

logger = logging.getLogger(__name__)


class SMTController:
    """Controls SMT panel testing using direct relay mapping from SKU config"""
    
    def __init__(self, arduino: Union[ArduinoController, 'SMTArduinoController']):
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
            # Clear any pending messages first
            self.arduino.serial.flush_buffers()
            
            # Send an 'X' command first to ensure Arduino is responsive
            logger.info("Sending 'X' command to ensure Arduino is responsive")
            x_response = self.arduino.send_command("X", timeout=1.0)
            if x_response:
                logger.info(f"Arduino responsive, got: {x_response}")
            else:
                logger.warning("No response to 'X' command, but continuing...")
            
            # Small delay before identification
            import time
            time.sleep(0.1)
            
            # Check connection - SMT Arduino uses "I" not "ID"
            response = self.arduino.send_command("I")
            if not response:
                logger.error("No response from Arduino")
                return False
            
            # Ignore button messages and look for actual ID response
            max_attempts = 3
            for attempt in range(max_attempts):
                if "BUTTON:" in response:
                    logger.debug(f"Ignoring button message during init: {response}")
                    response = self.arduino.send_command("I")
                    if not response:
                        continue
                elif "SMT_SIMPLE_TESTER" in response or "SMT_TESTER" in response or "SMT_BATCH_TESTER" in response or "DIODE_DYNAMICS" in response:
                    logger.debug(f"Arduino firmware validated: {response}")
                    break
            else:
                logger.error(f"Arduino not running compatible firmware after {max_attempts} attempts. Last response: {response}")
                return False
            
            logger.info(f"Arduino firmware identified: {response}")
                
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
        """Turn off all relays using SMT Arduino command"""
        # SMT Arduino uses "X" command to turn off all relays
        response = self.arduino.send_command("X", timeout=0.5)
        return response == "OK:ALL_OFF"