"""Offroad Arduino Controller - Extends base ArduinoController
For Offroad testing with sensor configurations and test results
"""

from .arduino_controller import ArduinoController

class OffroadArduinoController(ArduinoController):
    """Controller for Offroad testing - extends base ArduinoController
    
    This class inherits all functionality from the base ArduinoController
    and adds Offroad-specific capabilities. Since the current implementation
    doesn't have any Offroad-specific methods, this serves as a semantic
    distinction and allows for future Offroad-specific extensions.
    """
    
    def __init__(self, baud_rate: int = 115200):
        """Initialize Offroad Arduino controller
        
        Args:
            baud_rate: Serial communication baud rate (default: 115200)
        """
        super().__init__(baud_rate)
        
        # Can add Offroad-specific initialization here if needed in the future
        # For now, all functionality is inherited from the base class
    
    def get_firmware_type(self) -> str:
        """Get firmware type - override to check for Offroad firmware
        
        Returns:
            str: Firmware type or "UNKNOWN"
        """
        # Call parent method - it already handles firmware detection
        return super().get_firmware_type()
    
    # All other methods are inherited from ArduinoController:
    # - connect/disconnect
    # - configure_sensors
    # - start_reading/stop_reading
    # - run_test
    # - send_command
    # - All callback setters
    # - All data getters
    
    # Future Offroad-specific methods can be added here