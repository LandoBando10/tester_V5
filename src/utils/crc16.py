#!/usr/bin/env python3
"""
CRC-16 Implementation for Communication Protocol

Implements CRC-16 with CCITT polynomial (0x1021) for message validation.
Table-based implementation for high performance.

Phase 2.1 Implementation - adds data integrity validation to communication protocol.
"""

import logging
from typing import Union


class CRC16:
    """CRC-16 calculator using CCITT polynomial (0x1021)"""
    
    # CCITT polynomial: x^16 + x^12 + x^5 + 1 (0x1021)
    POLYNOMIAL = 0x1021
    INITIAL_VALUE = 0xFFFF
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._table = self._generate_table()
        
    def _generate_table(self) -> list:
        """Generate CRC-16 lookup table for fast computation"""
        table = []
        
        for i in range(256):
            crc = i << 8
            for _ in range(8):
                if crc & 0x8000:
                    crc = (crc << 1) ^ self.POLYNOMIAL
                else:
                    crc = crc << 1
                crc &= 0xFFFF
            table.append(crc)
            
        return table
    
    def calculate(self, data: Union[str, bytes]) -> int:
        """
        Calculate CRC-16 for given data
        
        Args:
            data: String or bytes to calculate CRC for
            
        Returns:
            CRC-16 value as integer (0-65535)
        """
        if isinstance(data, str):
            data = data.encode('utf-8')
        elif not isinstance(data, (bytes, bytearray)):
            raise ValueError("Data must be string or bytes")
            
        crc = self.INITIAL_VALUE
        
        for byte in data:
            table_index = ((crc >> 8) ^ byte) & 0xFF
            crc = ((crc << 8) ^ self._table[table_index]) & 0xFFFF
            
        return crc
    
    def calculate_hex(self, data: Union[str, bytes]) -> str:
        """
        Calculate CRC-16 and return as 4-character hex string
        
        Args:
            data: String or bytes to calculate CRC for
            
        Returns:
            CRC-16 as uppercase hex string (e.g., "A3F1")
        """
        crc = self.calculate(data)
        return f"{crc:04X}"
    
    def verify(self, data: Union[str, bytes], expected_crc: Union[int, str]) -> bool:
        """
        Verify data against expected CRC
        
        Args:
            data: Data to verify
            expected_crc: Expected CRC as int or hex string
            
        Returns:
            True if CRC matches, False otherwise
        """
        calculated_crc = self.calculate(data)
        
        if isinstance(expected_crc, str):
            try:
                expected_crc = int(expected_crc, 16)
            except ValueError:
                self.logger.error(f"Invalid CRC hex string: {expected_crc}")
                return False
                
        return calculated_crc == expected_crc
    
    def append_crc(self, message: str) -> str:
        """
        Append CRC-16 to message in format: MESSAGE*XXXX
        
        Args:
            message: Message to append CRC to
            
        Returns:
            Message with CRC appended
        """
        crc_hex = self.calculate_hex(message)
        return f"{message}*{crc_hex}"
    
    def extract_and_verify(self, message_with_crc: str) -> tuple[str, bool]:
        """
        Extract message and verify CRC
        
        Args:
            message_with_crc: Message in format MESSAGE*XXXX
            
        Returns:
            Tuple of (original_message, crc_valid)
        """
        if '*' not in message_with_crc:
            self.logger.warning("No CRC delimiter found in message")
            return message_with_crc, False
            
        parts = message_with_crc.rsplit('*', 1)
        if len(parts) != 2:
            self.logger.warning("Invalid CRC format in message")
            return message_with_crc, False
            
        message, crc_str = parts
        
        if len(crc_str) != 4:
            self.logger.warning(f"Invalid CRC length: {len(crc_str)} (expected 4)")
            return message, False
            
        is_valid = self.verify(message, crc_str)
        return message, is_valid


# Global CRC calculator instance for convenience
_crc_calculator = None

def get_crc_calculator() -> CRC16:
    """Get global CRC calculator instance"""
    global _crc_calculator
    if _crc_calculator is None:
        _crc_calculator = CRC16()
    return _crc_calculator


def calculate_crc16(data: Union[str, bytes]) -> int:
    """Convenience function to calculate CRC-16"""
    return get_crc_calculator().calculate(data)


def calculate_crc16_hex(data: Union[str, bytes]) -> str:
    """Convenience function to calculate CRC-16 as hex string"""
    return get_crc_calculator().calculate_hex(data)


def verify_crc16(data: Union[str, bytes], expected_crc: Union[int, str]) -> bool:
    """Convenience function to verify CRC-16"""
    return get_crc_calculator().verify(data, expected_crc)


def append_crc16(message: str) -> str:
    """Convenience function to append CRC-16 to message"""
    return get_crc_calculator().append_crc(message)


def extract_and_verify_crc16(message_with_crc: str) -> tuple[str, bool]:
    """Convenience function to extract and verify CRC-16"""
    return get_crc_calculator().extract_and_verify(message_with_crc)


# Known test vectors for verification
TEST_VECTORS = [
    ("123456789", 0x29B1),  # Standard test vector
    ("A", 0xB915),
    ("ABC", 0x9DD6),
    ("Hello", 0x34E1),
    ("RELAY:1:ON", 0x8F4A),
    ("MEASURE:1", 0x7C8E),
    ("STATUS", 0x8B5A)
]


def run_self_test() -> bool:
    """
    Run self-test with known CRC values
    
    Returns:
        True if all tests pass, False otherwise
    """
    logger = logging.getLogger(__name__)
    crc = get_crc_calculator()
    
    logger.info("Running CRC-16 self-test...")
    
    for test_data, expected_crc in TEST_VECTORS:
        calculated_crc = crc.calculate(test_data)
        if calculated_crc != expected_crc:
            logger.error(f"CRC test failed: '{test_data}' -> {calculated_crc:04X} (expected {expected_crc:04X})")
            return False
        logger.debug(f"CRC test passed: '{test_data}' -> {calculated_crc:04X}")
    
    # Test hex formatting
    hex_crc = crc.calculate_hex("123456789")
    if hex_crc != "29B1":
        logger.error(f"Hex formatting test failed: got {hex_crc}, expected 29B1")
        return False
    
    # Test verification
    if not crc.verify("123456789", "29B1"):
        logger.error("CRC verification test failed")
        return False
    
    # Test message append/extract
    message = "RELAY:1:ON"
    message_with_crc = crc.append_crc(message)
    extracted_message, is_valid = crc.extract_and_verify(message_with_crc)
    
    if extracted_message != message or not is_valid:
        logger.error("Message append/extract test failed")
        return False
    
    logger.info("All CRC-16 self-tests passed")
    return True


if __name__ == "__main__":
    # Run self-test when module is executed directly
    logging.basicConfig(level=logging.DEBUG)
    
    success = run_self_test()
    
    if success:
        print("✅ CRC-16 implementation verified")
        
        # Interactive test
        test_message = "RELAY:1:ON"
        crc = get_crc_calculator()
        
        print(f"\nTest message: '{test_message}'")
        print(f"CRC-16: {crc.calculate_hex(test_message)}")
        print(f"With CRC: {crc.append_crc(test_message)}")
        
    else:
        print("❌ CRC-16 self-test failed")
        exit(1)