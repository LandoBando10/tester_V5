"""
Security Validation Module
Provides input validation and sanitization for security-critical operations
"""

import re
import os
import logging
from pathlib import Path
from typing import List, Optional, Set


class SecurityValidationError(Exception):
    """Raised when input validation fails for security reasons"""
    pass


class InputValidator:
    """Validates and sanitizes inputs to prevent injection attacks"""
    
    # Known safe MCU device patterns
    STM8_DEVICES = {
        'STM8S003F3', 'STM8S005C6', 'STM8S007C8', 'STM8S103F2', 'STM8S103F3',
        'STM8S105C4', 'STM8S105C6', 'STM8S105K4', 'STM8S105K6', 'STM8S105S4',
        'STM8S105S6', 'STM8S207C6', 'STM8S207C8', 'STM8S207K6', 'STM8S207K8',
        'STM8S207M8', 'STM8S207R6', 'STM8S207R8', 'STM8S207S6', 'STM8S207S8',
        'STM8S208C6', 'STM8S208C8', 'STM8S208M8', 'STM8S208R6', 'STM8S208R8',
        'STM8S208S6', 'STM8S208S8'
    }
    
    PIC_DEVICES = {
        'PIC18F45K20', 'PIC18F46K20', 'PIC18F65K20', 'PIC18F66K20',
        'PIC18F25K20', 'PIC18F26K20', 'PIC18F45K22', 'PIC18F46K22',
        'PIC18F47K22', 'PIC18F25K22', 'PIC18F26K22', 'PIC18F27K22',
        'PIC18F23K20', 'PIC18F24K20', 'PIC18F43K20', 'PIC18F44K20',
        'PIC18F13K22', 'PIC18F14K22', 'PIC18F23K22', 'PIC18F24K22'
    }
    
    # Dangerous characters that could be used for command injection
    DANGEROUS_CHARS = set([';', '&', '|', '`', '$', '(', ')', '{', '}', '[', ']', 
                          '<', '>', '"', "'", '\\', '\n', '\r', '\t'])
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def validate_device_name(self, device: str, programmer_type: str) -> str:
        """
        Validate MCU device name against known safe devices
        
        Args:
            device: Device name to validate
            programmer_type: 'STM8' or 'PIC'
            
        Returns:
            Validated device name
            
        Raises:
            SecurityValidationError: If device name is invalid or unsafe
        """
        if not device or not isinstance(device, str):
            raise SecurityValidationError("Device name must be a non-empty string")
        
        # Remove any whitespace
        device = device.strip()
        
        # Check for dangerous characters
        if any(char in device for char in self.DANGEROUS_CHARS):
            self.logger.error(f"Device name contains dangerous characters: {device}")
            raise SecurityValidationError(f"Device name contains invalid characters: {device}")
        
        # Check length
        if len(device) > 50:
            raise SecurityValidationError(f"Device name too long: {device}")
        
        # Validate against known device lists
        programmer_type = programmer_type.upper()
        if programmer_type == 'STM8':
            if device not in self.STM8_DEVICES:
                self.logger.warning(f"Unknown STM8 device: {device}")
                # Allow unknown devices but log for security monitoring
                # In production, you might want to be more restrictive
                if not re.match(r'^STM8[A-Z0-9]+$', device):
                    raise SecurityValidationError(f"Invalid STM8 device format: {device}")
        elif programmer_type == 'PIC':
            if device not in self.PIC_DEVICES:
                self.logger.warning(f"Unknown PIC device: {device}")
                # Allow unknown devices but log for security monitoring
                if not re.match(r'^PIC[A-Z0-9]+$', device):
                    raise SecurityValidationError(f"Invalid PIC device format: {device}")
        else:
            raise SecurityValidationError(f"Unknown programmer type: {programmer_type}")
        
        return device
    
    def validate_file_path(self, file_path: str, allowed_extensions: Optional[Set[str]] = None) -> str:
        """
        Validate file path for security
        
        Args:
            file_path: Path to validate
            allowed_extensions: Set of allowed file extensions (e.g., {'.hex', '.bin'})
            
        Returns:
            Validated file path
            
        Raises:
            SecurityValidationError: If path is invalid or unsafe
        """
        if not file_path or not isinstance(file_path, str):
            raise SecurityValidationError("File path must be a non-empty string")
        
        # Check for dangerous characters in file path
        if any(char in file_path for char in [';', '&', '|', '`', '$']):
            raise SecurityValidationError(f"File path contains dangerous characters: {file_path}")
        
        try:
            # Normalize the path and check it exists
            path = Path(file_path).resolve()
            
            # Security: Block absolute paths that could be system files
            # Allow only relative paths or paths within reasonable project boundaries
            path_str = str(path).lower()
            dangerous_paths = [
                'c:\\windows', 'c:\\program files', '/etc/', '/usr/', '/bin/', '/sbin/',
                '/system/', '/boot/', 'c:\\system32', 'c:\\syswow64'
            ]
            
            for dangerous in dangerous_paths:
                if dangerous in path_str:
                    raise SecurityValidationError(f"Access to system directory not allowed: {file_path}")
            
            # Check the file exists
            if not path.exists():
                raise SecurityValidationError(f"File does not exist: {file_path}")
            
            # Check it's actually a file
            if not path.is_file():
                raise SecurityValidationError(f"Path is not a file: {file_path}")
            
            # Check file extension if provided
            if allowed_extensions:
                if path.suffix.lower() not in allowed_extensions:
                    raise SecurityValidationError(f"File extension not allowed: {path.suffix}")
            
            # Convert back to string for subprocess
            return str(path)
            
        except (OSError, ValueError) as e:
            raise SecurityValidationError(f"Invalid file path: {file_path} - {str(e)}")
    
    def validate_programmer_path(self, programmer_path: str) -> str:
        """
        Validate programmer executable path
        
        Args:
            programmer_path: Path to programmer executable
            
        Returns:
            Validated programmer path
            
        Raises:
            SecurityValidationError: If path is invalid or unsafe
        """
        if not programmer_path or not isinstance(programmer_path, str):
            raise SecurityValidationError("Programmer path must be a non-empty string")
        
        # Check for dangerous characters
        if any(char in programmer_path for char in [';', '&', '|', '`', '$']):
            raise SecurityValidationError(f"Programmer path contains dangerous characters")
        
        try:
            path = Path(programmer_path).resolve()
            
            # Check the executable exists
            if not path.exists():
                raise SecurityValidationError(f"Programmer executable not found: {programmer_path}")
            
            # Check it's actually a file
            if not path.is_file():
                raise SecurityValidationError(f"Programmer path is not a file: {programmer_path}")
            
            # On Windows, check for .exe extension
            if os.name == 'nt' and not path.suffix.lower() == '.exe':
                raise SecurityValidationError(f"Programmer must be an executable (.exe): {programmer_path}")
            
            return str(path)
            
        except (OSError, ValueError) as e:
            raise SecurityValidationError(f"Invalid programmer path: {programmer_path} - {str(e)}")
    
    def validate_board_name(self, board_name: str) -> str:
        """
        Validate board name for logging and identification
        
        Args:
            board_name: Name of the board being programmed
            
        Returns:
            Validated board name
            
        Raises:
            SecurityValidationError: If board name is invalid
        """
        if not board_name or not isinstance(board_name, str):
            raise SecurityValidationError("Board name must be a non-empty string")
        
        # Remove whitespace
        board_name = board_name.strip()
        
        # Check for dangerous characters
        if any(char in board_name for char in self.DANGEROUS_CHARS):
            raise SecurityValidationError(f"Board name contains invalid characters: {board_name}")
        
        # Check length
        if len(board_name) > 100:
            raise SecurityValidationError(f"Board name too long: {board_name}")
        
        # Allow alphanumeric, underscore, hyphen, and space
        if not re.match(r'^[A-Za-z0-9_\-\s]+$', board_name):
            raise SecurityValidationError(f"Board name contains invalid characters: {board_name}")
        
        return board_name


class CommandBuilder:
    """Builds secure command line arguments for subprocess calls"""
    
    def __init__(self, validator: InputValidator):
        self.validator = validator
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def build_stm8_command(self, programmer_path: str, device: str, hex_file: str) -> List[str]:
        """
        Build secure STM8 programming command
        
        Args:
            programmer_path: Validated programmer executable path
            device: Validated device name
            hex_file: Validated hex file path
            
        Returns:
            List of command arguments safe for subprocess.run()
        """
        # All inputs should already be validated, but double-check
        programmer_path = self.validator.validate_programmer_path(programmer_path)
        device = self.validator.validate_device_name(device, 'STM8')
        hex_file = self.validator.validate_file_path(hex_file, {'.hex', '.s19'})
        
        # Build command as list (safer than shell=True)
        cmd = [
            programmer_path,
            "-BoardName=ST-LINK",
            f"-Device={device}",
            f"-FilePath={hex_file}",
            "-no_gui",
            "-no_log",
            "-Prog",
            "-Rst"
        ]
        
        self.logger.debug(f"Built STM8 command: {cmd}")
        return cmd
    
    def build_pic_command(self, programmer_path: str, device: str, hex_file: str) -> List[str]:
        """
        Build secure PIC programming command
        
        Args:
            programmer_path: Validated programmer executable path
            device: Validated device name
            hex_file: Validated hex file path
            
        Returns:
            List of command arguments safe for subprocess.run()
        """
        # All inputs should already be validated, but double-check
        programmer_path = self.validator.validate_programmer_path(programmer_path)
        device = self.validator.validate_device_name(device, 'PIC')
        hex_file = self.validator.validate_file_path(hex_file, {'.hex'})
        
        # Build command as list
        cmd = [
            programmer_path,
            f"/P{device}",
            "-F", hex_file,
            "-M",
            "-OL"
        ]
        
        self.logger.debug(f"Built PIC command: {cmd}")
        return cmd
    
    def build_verification_command(self, programmer_path: str, programmer_type: str) -> List[str]:
        """
        Build secure verification command
        
        Args:
            programmer_path: Validated programmer executable path
            programmer_type: 'STM8' or 'PIC'
            
        Returns:
            List of command arguments safe for subprocess.run()
        """
        programmer_path = self.validator.validate_programmer_path(programmer_path)
        
        if programmer_type.upper() == 'STM8':
            cmd = [programmer_path, "-List=USB"]
        elif programmer_type.upper() == 'PIC':
            cmd = [programmer_path, "-?"]
        else:
            raise SecurityValidationError(f"Unknown programmer type: {programmer_type}")
        
        self.logger.debug(f"Built verification command: {cmd}")
        return cmd
