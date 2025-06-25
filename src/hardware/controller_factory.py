"""Arduino Controller Factory
Creates appropriate Arduino controller instances based on test mode
"""

import logging
from typing import Optional, Union

# Import the different controller types
from .arduino_controller import ArduinoController
from .offroad_arduino_controller import OffroadArduinoController
from .smt_arduino_controller import SMTArduinoController


class ArduinoControllerFactory:
    """Factory for creating mode-specific Arduino controllers"""
    
    @staticmethod
    def create_controller(mode: str, baud_rate: int = 115200) -> Optional[Union[ArduinoController, SMTArduinoController, OffroadArduinoController]]:
        """Create appropriate controller based on test mode
        
        Args:
            mode: Test mode ("SMT", "OFFROAD", "WEIGHT", etc.)
            baud_rate: Serial communication baud rate
            
        Returns:
            Appropriate controller instance or None if mode is unknown
        """
        logger = logging.getLogger(__name__)
        
        # Normalize mode to uppercase for consistency
        mode = mode.upper() if mode else ""
        
        if mode == "SMT":
            logger.info("Creating SMT Arduino controller")
            return SMTArduinoController(baud_rate=baud_rate)
            
        elif mode == "OFFROAD":
            logger.info("Creating Offroad Arduino controller")
            return OffroadArduinoController(baud_rate=baud_rate)
            
        elif mode in ["WEIGHT", "GENERAL"]:
            # For Weight mode or general purpose, use base controller
            logger.info(f"Creating base Arduino controller for {mode} mode")
            return ArduinoController(baud_rate=baud_rate)
            
        else:
            logger.warning(f"Unknown mode: {mode}, returning base controller")
            # Default to base controller for unknown modes
            return ArduinoController(baud_rate=baud_rate)
    
    @staticmethod
    def get_controller_type(controller) -> str:
        """Get the type/mode of a controller instance
        
        Args:
            controller: Controller instance
            
        Returns:
            String identifying the controller type
        """
        if isinstance(controller, SMTArduinoController):
            return "SMT"
        elif isinstance(controller, OffroadArduinoController):
            return "OFFROAD"
        elif isinstance(controller, ArduinoController):
            return "BASE"
        else:
            return "UNKNOWN"