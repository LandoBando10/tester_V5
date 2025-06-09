"""
SMT Panel Test Controller
Handles configuration-based SMT testing with flexible relay mapping
"""

import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import logging

from src.hardware.arduino_controller import ArduinoController

logger = logging.getLogger(__name__)


class LightType(Enum):
    STANDARD = "standard"
    RGBW_CYCLING = "rgbw_cycling"
    PWM = "pwm"


class BoardPosition(Enum):
    BOTTOM_LEFT = 0
    BOTTOM_RIGHT = 1
    TOP_RIGHT = 2
    TOP_LEFT = 3


@dataclass
class LightConfig:
    """Configuration for a single light on a board"""
    name: str
    type: LightType
    relay_offset: int
    rgbw_config: Optional[Dict] = None


@dataclass
class SMTBoardConfig:
    """Configuration for a specific SMT board type"""
    sku: str
    lights: List[LightConfig]
    test_sequence: List[Dict]
    panel_layout: Optional[Dict] = None


class SMTController:
    """Controls SMT panel testing with configurable relay mapping"""
    
    def __init__(self, arduino: ArduinoController):
        self.arduino = arduino
        self.current_config: Optional[SMTBoardConfig] = None
        self.relay_count = 8  # Default
        self.board_positions = {
            "BL": BoardPosition.BOTTOM_LEFT,
            "BR": BoardPosition.BOTTOM_RIGHT,
            "TR": BoardPosition.TOP_RIGHT,
            "TL": BoardPosition.TOP_LEFT,
            "BOTTOM_LEFT": BoardPosition.BOTTOM_LEFT,
            "BOTTOM_RIGHT": BoardPosition.BOTTOM_RIGHT,
            "TOP_RIGHT": BoardPosition.TOP_RIGHT,
            "TOP_LEFT": BoardPosition.TOP_LEFT,
        }
        
    def load_configuration(self, config_path: str) -> bool:
        """Load SMT configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                
            lights = []
            for light_data in data.get('board_type', {}).get('lights', []):
                light_type = LightType(light_data['type'])
                light = LightConfig(
                    name=light_data['name'],
                    type=light_type,
                    relay_offset=light_data['relay_offset'],
                    rgbw_config=light_data.get('rgbw_config')
                )
                lights.append(light)
                
            self.current_config = SMTBoardConfig(
                sku=data['sku'],
                lights=lights,
                test_sequence=data.get('test_sequence', []),
                panel_layout=data.get('panel_layout')
            )
            
            # Configure relay count if specified
            if self.current_config.panel_layout:
                boards = self.current_config.panel_layout.get('boards', 4)
                lights_per_board = len(self.current_config.lights)
                self.relay_count = boards * lights_per_board
                
            logger.info(f"Loaded SMT configuration: {self.current_config.sku}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load SMT configuration: {e}")
            return False
            
    def initialize_arduino(self) -> bool:
        """Initialize Arduino for SMT testing"""
        try:
            # Check connection
            response = self.arduino.send_command("ID")
            if "SMT_TESTER" not in response:
                logger.error("Arduino not running SMT firmware")
                return False
                
            # Configure relay count
            self.arduino.send_command(f"CONFIG:CHANNELS:{self.relay_count}")
            
            # Configure light types if config loaded
            if self.current_config:
                for board_pos in range(4):  # Assuming 4 board panel
                    for light in self.current_config.lights:
                        relay_num = self.calculate_relay_number(board_pos, light)
                        if light.type == LightType.RGBW_CYCLING:
                            self.arduino.send_command(f"CONFIG:LIGHT:{relay_num}:TYPE:RGBW")
                            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Arduino: {e}")
            return False
            
    def calculate_relay_number(self, board_position: int, light: LightConfig) -> int:
        """Calculate relay number for a specific light on a specific board"""
        # Formula: relay = (board_position % 4) + 1 + light.relay_offset
        return (board_position % 4) + 1 + light.relay_offset
        
    def get_relays_for_light(self, light_name: str, board_position: Optional[int] = None) -> List[int]:
        """Get relay numbers for a light across one or all boards"""
        if not self.current_config:
            return []
            
        light = next((l for l in self.current_config.lights if l.name == light_name), None)
        if not light:
            return []
            
        if board_position is not None:
            return [self.calculate_relay_number(board_position, light)]
        else:
            # Return relays for all boards
            return [self.calculate_relay_number(pos, light) for pos in range(4)]
            
    def control_light(self, light_name: str, state: bool, board_position: Optional[int] = None):
        """Control a light on one or all boards"""
        relays = self.get_relays_for_light(light_name, board_position)
        
        if len(relays) == 1:
            self.arduino.send_command(f"RELAY:{relays[0]}:{'ON' if state else 'OFF'}")
        elif len(relays) > 1:
            relay_list = ','.join(map(str, relays))
            self.arduino.send_command(f"RELAY_GROUP:{relay_list}:{'ON' if state else 'OFF'}")
            
    def start_rgbw_cycle(self, light_name: str, board_position: Optional[int] = None, 
                        on_ms: int = 50, off_ms: int = 50):
        """Start RGBW cycling on specified light(s)"""
        relays = self.get_relays_for_light(light_name, board_position)
        
        for relay in relays:
            self.arduino.send_command(f"RGBW:{relay}:PATTERN:{on_ms},{off_ms}")
            self.arduino.send_command(f"RGBW:{relay}:START")
            
    def sample_rgbw_colors(self, light_name: str, board_position: int, 
                          sample_points: List[int]) -> List[Dict]:
        """Sample RGBW colors at specified time points"""
        relay = self.get_relays_for_light(light_name, board_position)[0]
        
        # Format: RGBW:n:SAMPLE:count:t1,t2,t3...
        count = len(sample_points)
        times = ','.join(map(str, sample_points))
        
        self.arduino.send_command(f"RGBW:{relay}:SAMPLE:{count}:{times}")
        
        # Collect samples
        samples = []
        timeout = max(sample_points) / 1000.0 + 2.0  # Convert to seconds, add buffer
        start_time = time.time()
        
        while len(samples) < count and (time.time() - start_time) < timeout:
            response = self.arduino.read_response(timeout=0.1)
            if response and response.startswith("RGBW_SAMPLE:"):
                # Parse: RGBW_SAMPLE:relay:index:color_pos:elapsed_ms
                parts = response.split(':')
                if len(parts) >= 5:
                    samples.append({
                        'relay': int(parts[1]),
                        'index': int(parts[2]),
                        'color_position': int(parts[3]),
                        'elapsed_ms': int(parts[4])
                    })
                    
        return samples
        
    def run_test_sequence(self, board_position: Optional[int] = None):
        """Run the configured test sequence"""
        if not self.current_config:
            logger.error("No configuration loaded")
            return
            
        logger.info(f"Running test sequence for board position: {board_position}")
        
        for step in self.current_config.test_sequence:
            light = step.get('light')
            action = step.get('action', 'on')
            duration = step.get('duration', 500) / 1000.0  # Convert to seconds
            
            if isinstance(light, list):
                # Multiple lights
                for light_name in light:
                    self._execute_light_action(light_name, action, board_position, step)
            else:
                # Single light
                self._execute_light_action(light, action, board_position, step)
                
            time.sleep(duration)
            
        # Turn all lights off
        self.all_lights_off()
        
    def _execute_light_action(self, light_name: str, action: str, 
                             board_position: Optional[int], step: Dict):
        """Execute a specific action on a light"""
        if action == 'on':
            self.control_light(light_name, True, board_position)
        elif action == 'off':
            self.control_light(light_name, False, board_position)
        elif action == 'start_cycle':
            pattern = step.get('pattern', {})
            on_ms = pattern.get('on_ms', 50)
            off_ms = pattern.get('off_ms', 50)
            self.start_rgbw_cycle(light_name, board_position, on_ms, off_ms)
        elif action == 'rgbw_test':
            sample_points = step.get('sample_points', [200, 400, 600])
            if board_position is not None:
                samples = self.sample_rgbw_colors(light_name, board_position, sample_points)
                logger.info(f"RGBW samples for {light_name}: {samples}")
                
    def test_panel(self):
        """Test all boards in the panel sequentially"""
        positions = [BoardPosition.BOTTOM_LEFT, BoardPosition.BOTTOM_RIGHT,
                    BoardPosition.TOP_RIGHT, BoardPosition.TOP_LEFT]
                    
        for pos in positions:
            logger.info(f"Testing board at position: {pos.name}")
            self.run_test_sequence(pos.value)
            time.sleep(0.5)  # Brief pause between boards
            
    def test_board(self, position: str):
        """Test a specific board"""
        if position.upper() in self.board_positions:
            board_pos = self.board_positions[position.upper()]
            self.run_test_sequence(board_pos.value)
        else:
            logger.error(f"Invalid board position: {position}")
            
    def test_all_boards(self):
        """Test all boards simultaneously"""
        self.run_test_sequence(None)  # None means all boards
        
    def all_lights_off(self):
        """Turn off all relays"""
        self.arduino.send_command("RELAY_ALL:OFF")
        
    def get_relay_status(self) -> Dict[int, Tuple[bool, str]]:
        """Get status of all relays"""
        self.arduino.send_command("RELAY_STATUS")
        status = {}
        
        timeout = time.time() + 1.0
        while time.time() < timeout:
            response = self.arduino.read_response(timeout=0.1)
            if response and response.startswith("RELAY_STATUS:"):
                # Parse: RELAY_STATUS:n:ON/OFF:STD/RGBW
                parts = response.split(':')
                if len(parts) >= 4:
                    relay_num = int(parts[1])
                    state = parts[2] == "ON"
                    light_type = parts[3]
                    status[relay_num] = (state, light_type)
                    
        return status


# Example usage
if __name__ == "__main__":
    # This would typically be called from the GUI
    arduino = ArduinoController(port="COM3")  # Replace with actual port
    smt = SMTController(arduino)
    
    # Load configuration
    smt.load_configuration("config/smt/ss3_amber_single.json")
    
    # Initialize Arduino
    if smt.initialize_arduino():
        # Run tests
        smt.test_panel()  # Test all boards sequentially
        # smt.test_board("BL")  # Test bottom left only
        # smt.test_all_boards()  # Test all simultaneously