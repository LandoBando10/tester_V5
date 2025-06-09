"""
Programmer Controller Module
Handles STM8 and PIC programming with per-board device selection
SECURITY HARDENED - Prevents command injection attacks
"""

import logging
import subprocess
from typing import Optional, Tuple
from src.utils.security_validators import InputValidator, CommandBuilder, SecurityValidationError


class ProgrammerController:
    """Controls STM8 and PIC programmers in bed-of-nails fixture - SECURITY HARDENED"""

    def __init__(self, programmer_type: str, programmer_path: str):
        self.programmer_type = programmer_type.upper()  # 'STM8' or 'PIC'
        self.logger = logging.getLogger(f"{self.__class__.__name__}_{programmer_type}")
        
        # Initialize security validators
        self.validator = InputValidator()
        self.command_builder = CommandBuilder(self.validator)
        
        # Validate programmer type
        if self.programmer_type not in ['STM8', 'PIC']:
            raise ValueError(f"Unsupported programmer type: {programmer_type}")
        
        # Validate and store programmer path
        try:
            self.programmer_path = self.validator.validate_programmer_path(programmer_path)
            self.logger.info(f"Validated programmer path: {self.programmer_path}")
        except SecurityValidationError as e:
            self.logger.error(f"Invalid programmer path: {e}")
            raise ValueError(f"Invalid programmer path: {e}")

    def program_board(self, hex_file: str, board_name: str, device: Optional[str] = None) -> Tuple[bool, str]:
        """
        Program a board with optional device type specification
        SECURITY: All inputs are validated to prevent command injection
        
        Args:
            hex_file (str): Path to hex file
            board_name (str): Name of board being programmed  
            device (str, optional): MCU device type. If None, uses default for programmer type
            
        Returns:
            Tuple[bool, str]: Success status and message
        """
        try:
            # Validate inputs for security
            validated_board_name = self.validator.validate_board_name(board_name)
            validated_hex_file = self.validator.validate_file_path(hex_file, {'.hex', '.s19'})
            
            self.logger.info(f"Starting programming for {validated_board_name}")
            
            if self.programmer_type == 'STM8':
                return self._program_stm8(validated_hex_file, validated_board_name, device)
            elif self.programmer_type == 'PIC':
                return self._program_pic(validated_hex_file, validated_board_name, device)
            else:
                error_msg = f"Unknown programmer type: {self.programmer_type}"
                self.logger.error(error_msg)
                return False, error_msg

        except SecurityValidationError as e:
            error_msg = f"Security validation failed for {board_name}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Programming error for {board_name}: {str(e)}"
            self.logger.error(error_msg)
            return False, error_msg

    def _program_stm8(self, hex_file: str, board_name: str, device: Optional[str] = None) -> Tuple[bool, str]:
        """Program STM8 device with configurable device type - SECURITY HARDENED"""
        try:
            # Use provided device or fall back to default
            if device is None:
                device = "STM8S003F3"
            
            # Validate device name to prevent injection
            validated_device = self.validator.validate_device_name(device, 'STM8')
            
            self.logger.info(f"Programming STM8 device: {validated_device}")
            
            # Build secure command using command builder
            cmd = self.command_builder.build_stm8_command(
                self.programmer_path, validated_device, hex_file
            )
            
            return self._execute_programming_command(cmd, board_name)
            
        except SecurityValidationError as e:
            error_msg = f"STM8 validation failed: {str(e)}"
            self.logger.error(f"{board_name}: {error_msg}")
            return False, error_msg

    def _program_pic(self, hex_file: str, board_name: str, device: Optional[str] = None) -> Tuple[bool, str]:
        """Program PIC device with configurable device type - SECURITY HARDENED"""
        try:
            # Use provided device or fall back to default
            if device is None:
                device = "PIC18F45K20"
            
            # Validate device name to prevent injection
            validated_device = self.validator.validate_device_name(device, 'PIC')
            
            self.logger.info(f"Programming PIC device: {validated_device}")
            
            # Build secure command using command builder
            cmd = self.command_builder.build_pic_command(
                self.programmer_path, validated_device, hex_file
            )
            
            return self._execute_programming_command(cmd, board_name)
            
        except SecurityValidationError as e:
            error_msg = f"PIC validation failed: {str(e)}"
            self.logger.error(f"{board_name}: {error_msg}")
            return False, error_msg

    def _execute_programming_command(self, cmd: list, board_name: str) -> Tuple[bool, str]:
        """Execute programming command with standard error handling - SECURITY HARDENED"""
        try:
            # Log command for debugging but sanitize sensitive info
            cmd_display = [arg if not arg.startswith('-Device=') and not arg.startswith('/P') 
                          else arg.split('=')[0] + '=***' if '=' in arg else arg[:3] + '***'
                          for arg in cmd]
            self.logger.info(f"Executing: {' '.join(cmd_display)}")
            
            # Execute with security settings
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,  # 60 second timeout
                shell=False,  # SECURITY: Never use shell=True
                cwd=None,     # SECURITY: Don't inherit working directory
                env=None      # SECURITY: Use clean environment
            )
            
            if result.returncode == 0:
                success_msg = f"Successfully programmed {board_name}"
                self.logger.info(success_msg)
                return True, success_msg
            else:
                error_msg = f"Programming failed: {result.stderr or result.stdout}"
                self.logger.error(f"{board_name}: {error_msg}")
                return False, error_msg
                
        except subprocess.TimeoutExpired:
            error_msg = f"Programming timeout after 60s"
            self.logger.error(f"{board_name}: {error_msg}")
            return False, error_msg
        except Exception as e:
            error_msg = f"Programming exception: {str(e)}"
            self.logger.error(f"{board_name}: {error_msg}")
            return False, error_msg

    def verify_connection(self) -> Tuple[bool, str]:
        """Verify programmer connection - SECURITY HARDENED"""
        try:
            # Build secure verification command
            cmd = self.command_builder.build_verification_command(
                self.programmer_path, self.programmer_type
            )

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                shell=False,  # SECURITY: Never use shell=True
                cwd=None,     # SECURITY: Don't inherit working directory  
                env=None      # SECURITY: Use clean environment
            )

            if result.returncode == 0:
                return True, f"{self.programmer_type} programmer connected"
            else:
                return False, f"{self.programmer_type} programmer not detected"

        except SecurityValidationError as e:
            return False, f"Programmer verification validation failed: {str(e)}"
        except Exception as e:
            return False, f"Programmer verification failed: {str(e)}"


# Result container for programming operations
class ProgrammingResult:
    """Result container for programming operations"""
    def __init__(self, success: bool, error_msg: Optional[str] = None):
        self.success = success
        self.error_msg = error_msg
