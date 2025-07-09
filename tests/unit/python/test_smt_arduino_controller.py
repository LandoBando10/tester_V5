"""
Unit tests for SMTArduinoController with TESTSEQ protocol
Tests the new simultaneous relay activation features
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import serial
import time
from src.hardware.smt_arduino_controller import SMTArduinoController


class TestSMTArduinoController:
    """Test suite for SMTArduinoController"""
    
    @pytest.fixture
    def mock_serial(self):
        """Create a mock serial connection"""
        mock = MagicMock(spec=serial.Serial)
        mock.is_open = True
        mock.in_waiting = 0
        mock.readline.return_value = b"OK\n"
        return mock
    
    @pytest.fixture
    def controller(self, mock_serial):
        """Create a controller with mocked serial"""
        with patch('serial.Serial', return_value=mock_serial):
            controller = SMTArduinoController()
            controller.connection = mock_serial
            controller._enable_checksums = False  # Disable for simpler testing
            return controller
    
    @pytest.mark.unit
    def test_parse_relay_mapping_simple(self, controller):
        """Test parsing simple relay mapping"""
        relay_mapping = {
            "1": {"board": 1, "function": "mainbeam"},
            "2": {"board": 2, "function": "mainbeam"}
        }
        
        result = controller._parse_relay_mapping(relay_mapping)
        
        assert result == {
            "1": {"board": 1, "function": "mainbeam"},
            "2": {"board": 2, "function": "mainbeam"}
        }
    
    @pytest.mark.unit
    def test_parse_relay_mapping_grouped(self, controller):
        """Test parsing grouped relay mapping"""
        relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"},
            "5, 6": {"board": 1, "function": "turn_signal"}  # With spaces
        }
        
        result = controller._parse_relay_mapping(relay_mapping)
        
        assert result == {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"},
            "5,6": {"board": 1, "function": "turn_signal"}  # Spaces removed
        }
    
    @pytest.mark.unit
    def test_parse_relay_mapping_skip_null(self, controller):
        """Test parsing skips null mappings"""
        relay_mapping = {
            "1": {"board": 1, "function": "mainbeam"},
            "2": None,
            "3": {}
        }
        
        result = controller._parse_relay_mapping(relay_mapping)
        
        assert result == {
            "1": {"board": 1, "function": "mainbeam"}
        }
    
    @pytest.mark.unit
    def test_build_testseq_command_simple(self, controller):
        """Test building TESTSEQ command"""
        relay_groups = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"}
        }
        
        test_sequence = [
            {"function": "mainbeam", "duration_ms": 500, "delay_after_ms": 100},
            {"function": "position", "duration_ms": 300}
        ]
        
        result = controller._build_testseq_command(relay_groups, test_sequence)
        
        assert result == "TESTSEQ:1,2,3:500;OFF:100;4:300"
    
    @pytest.mark.unit
    def test_build_testseq_command_multiple_boards(self, controller):
        """Test building TESTSEQ with multiple boards same function"""
        relay_groups = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "7,8,9": {"board": 2, "function": "mainbeam"}
        }
        
        test_sequence = [
            {"function": "mainbeam", "duration_ms": 500, "delay_after_ms": 100}
        ]
        
        result = controller._build_testseq_command(relay_groups, test_sequence)
        
        # Both relay groups should be included
        assert "1,2,3:500" in result
        assert "7,8,9:500" in result
        assert "OFF:100" in result
    
    @pytest.mark.unit
    def test_build_testseq_command_no_delay_last(self, controller):
        """Test TESTSEQ doesn't add OFF after last step with no delay"""
        relay_groups = {
            "1": {"board": 1, "function": "mainbeam"},
            "2": {"board": 1, "function": "position"}
        }
        
        test_sequence = [
            {"function": "mainbeam", "duration_ms": 500, "delay_after_ms": 100},
            {"function": "position", "duration_ms": 300, "delay_after_ms": 0}
        ]
        
        result = controller._build_testseq_command(relay_groups, test_sequence)
        
        assert result == "TESTSEQ:1:500;OFF:100;2:300"
    
    @pytest.mark.unit
    def test_parse_testresults_simple(self, controller):
        """Test parsing TESTRESULTS response"""
        response = "TESTRESULTS:1,2,3:12.5V,6.8A;END"
        relay_groups = {
            "1,2,3": {"board": 1, "function": "mainbeam"}
        }
        test_sequence = [{"function": "mainbeam"}]
        
        result = controller._parse_testresults(response, relay_groups, test_sequence)
        
        assert result == {
            1: {
                "mainbeam": {
                    "voltage": 12.5,
                    "current": 6.8,
                    "power": 85.0
                }
            }
        }
    
    @pytest.mark.unit
    def test_parse_testresults_multiple(self, controller):
        """Test parsing multiple measurements"""
        response = "TESTRESULTS:1,2,3:12.5V,6.8A;4:12.4V,1.0A;END"
        relay_groups = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"}
        }
        test_sequence = [
            {"function": "mainbeam"},
            {"function": "position"}
        ]
        
        result = controller._parse_testresults(response, relay_groups, test_sequence)
        
        assert result == {
            1: {
                "mainbeam": {
                    "voltage": 12.5,
                    "current": 6.8,
                    "power": 85.0
                },
                "position": {
                    "voltage": 12.4,
                    "current": 1.0,
                    "power": 12.4
                }
            }
        }
    
    @pytest.mark.unit
    def test_parse_testresults_invalid_format(self, controller):
        """Test parsing handles invalid format"""
        response = "INVALID:FORMAT"
        relay_groups = {"1": {"board": 1, "function": "test"}}
        test_sequence = []
        
        result = controller._parse_testresults(response, relay_groups, test_sequence)
        
        assert result == {}
    
    @pytest.mark.unit
    def test_validate_testseq_command_valid(self, controller):
        """Test validation passes for valid configuration"""
        relay_groups = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"}
        }
        test_sequence = [
            {"function": "mainbeam", "duration_ms": 500, "delay_after_ms": 100}
        ]
        
        errors = controller._validate_testseq_command(relay_groups, test_sequence)
        
        assert errors == []
    
    @pytest.mark.unit
    def test_validate_testseq_invalid_relay_number(self, controller):
        """Test validation catches invalid relay numbers"""
        relay_groups = {
            "17,18": {"board": 1, "function": "test"}  # Invalid: > 16
        }
        test_sequence = [{"function": "test", "duration_ms": 500}]
        
        errors = controller._validate_testseq_command(relay_groups, test_sequence)
        
        assert len(errors) == 2
        assert "Invalid relay number: 17" in errors[0]
        assert "Invalid relay number: 18" in errors[1]
    
    @pytest.mark.unit
    def test_validate_testseq_duplicate_relays(self, controller):
        """Test validation catches duplicate relays"""
        relay_groups = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "3,4,5": {"board": 2, "function": "mainbeam"}  # 3 is duplicate
        }
        test_sequence = [{"function": "mainbeam", "duration_ms": 500}]
        
        errors = controller._validate_testseq_command(relay_groups, test_sequence)
        
        assert any("Relay 3 appears in multiple groups" in e for e in errors)
    
    @pytest.mark.unit
    def test_validate_testseq_timing_too_short(self, controller):
        """Test validation catches short durations"""
        relay_groups = {"1": {"board": 1, "function": "test"}}
        test_sequence = [
            {"function": "test", "duration_ms": 50}  # Too short (< 100ms)
        ]
        
        errors = controller._validate_testseq_command(relay_groups, test_sequence)
        
        assert any("Duration 50ms too short" in e for e in errors)
    
    @pytest.mark.unit
    def test_validate_testseq_total_time_exceeded(self, controller):
        """Test validation catches excessive total time"""
        relay_groups = {"1": {"board": 1, "function": "test"}}
        test_sequence = [
            {"function": "test", "duration_ms": 10000, "delay_after_ms": 5000},
            {"function": "test", "duration_ms": 10000, "delay_after_ms": 5000},
            {"function": "test", "duration_ms": 10000, "delay_after_ms": 5000}
        ]
        
        errors = controller._validate_testseq_command(relay_groups, test_sequence)
        
        assert any("exceeds 30 second limit" in e for e in errors)
    
    @pytest.mark.unit
    def test_calculate_sequence_timeout(self, controller):
        """Test timeout calculation"""
        test_sequence = [
            {"function": "test1", "duration_ms": 500, "delay_after_ms": 100},
            {"function": "test2", "duration_ms": 300, "delay_after_ms": 50},
            {"function": "test3", "duration_ms": 400}
        ]
        
        timeout = controller._calculate_sequence_timeout(test_sequence)
        
        # Total: 500 + 100 + 300 + 50 + 400 = 1350ms = 1.35s
        # Plus 2s buffer = 3.35s
        assert timeout == 3.35
    
    @pytest.mark.unit
    def test_execute_test_sequence_not_connected(self, controller):
        """Test execute fails when not connected"""
        controller.connection = None
        
        result = controller.execute_test_sequence({}, [])
        
        assert result["success"] is False
        assert "Not connected" in result["errors"][0]
    
    @pytest.mark.unit
    def test_execute_test_sequence_success(self, controller, mock_serial):
        """Test successful test sequence execution"""
        # Mock successful response
        mock_serial.readline.return_value = b"TESTRESULTS:1,2,3:12.5V,6.8A;END\n"
        
        relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"}
        }
        test_sequence = [
            {
                "function": "mainbeam",
                "duration_ms": 500,
                "delay_after_ms": 100,
                "limits": {"current_a": {"min": 5, "max": 8}}
            }
        ]
        
        # Mock the response queue
        controller._response_queue.put("TESTRESULTS:1,2,3:12.5V,6.8A;END")
        
        result = controller.execute_test_sequence(relay_mapping, test_sequence)
        
        assert result["success"] is True
        assert result["errors"] == []
        assert 1 in result["results"]
        assert "mainbeam" in result["results"][1]
        assert result["results"][1]["mainbeam"]["voltage"] == 12.5
        assert result["results"][1]["mainbeam"]["current"] == 6.8
    
    @pytest.mark.unit
    def test_execute_test_sequence_validation_error(self, controller):
        """Test execution fails on validation error"""
        relay_mapping = {
            "17": {"board": 1, "function": "test"}  # Invalid relay
        }
        test_sequence = [
            {"function": "test", "duration_ms": 500}
        ]
        
        result = controller.execute_test_sequence(relay_mapping, test_sequence)
        
        assert result["success"] is False
        assert len(result["errors"]) > 0
        assert "Invalid relay number: 17" in result["errors"][0]
    
    @pytest.mark.unit
    def test_execute_test_sequence_arduino_error(self, controller, mock_serial):
        """Test handling of Arduino error response"""
        mock_serial.readline.return_value = b"ERROR:SEQUENCE_TIMEOUT\n"
        controller._response_queue.put("ERROR:SEQUENCE_TIMEOUT")
        
        relay_mapping = {"1": {"board": 1, "function": "test"}}
        test_sequence = [{"function": "test", "duration_ms": 500}]
        
        result = controller.execute_test_sequence(relay_mapping, test_sequence)
        
        assert result["success"] is False
        assert "Arduino error: SEQUENCE_TIMEOUT" in result["errors"][0]


@pytest.mark.unit
class TestProtocolHelpers:
    """Test protocol helper functions"""
    
    def test_relay_group_parsing(self):
        """Test various relay group formats"""
        controller = SMTArduinoController()
        
        # Single relay
        assert controller._parse_relay_mapping({"1": {"board": 1}}) == {"1": {"board": 1}}
        
        # Multiple relays
        mapping = {"1,2,3": {"board": 1}}
        assert controller._parse_relay_mapping(mapping) == {"1,2,3": {"board": 1}}
        
        # With spaces (should be normalized)
        mapping = {"1, 2, 3": {"board": 1}}
        assert controller._parse_relay_mapping(mapping) == {"1,2,3": {"board": 1}}
    
    def test_command_building_edge_cases(self):
        """Test edge cases in command building"""
        controller = SMTArduinoController()
        
        # Empty sequence
        result = controller._build_testseq_command({}, [])
        assert result == "TESTSEQ:"
        
        # No matching functions
        relay_groups = {"1": {"board": 1, "function": "test"}}
        test_sequence = [{"function": "other", "duration_ms": 500}]
        result = controller._build_testseq_command(relay_groups, test_sequence)
        assert result == "TESTSEQ:"
    
    def test_response_parsing_edge_cases(self):
        """Test edge cases in response parsing"""
        controller = SMTArduinoController()
        
        # Empty response
        result = controller._parse_testresults("TESTRESULTS:;END", {}, [])
        assert result == {}
        
        # Missing END marker
        result = controller._parse_testresults("TESTRESULTS:1:12V,1A", {}, [])
        assert result == {}
        
        # Malformed measurement
        result = controller._parse_testresults("TESTRESULTS:1:INVALID;END", {"1": {"board": 1, "function": "test"}}, [])
        assert result == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])