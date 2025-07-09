"""
Unit tests for SKU configuration validation
Tests relay grouping, timing validation, and configuration parsing
"""

import pytest
import json
import tempfile
from pathlib import Path
from src.data.sku_manager import SKUManager


class TestSKUValidation:
    """Test SKU configuration validation"""
    
    @pytest.fixture
    def temp_sku_dir(self):
        """Create temporary SKU directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            sku_dir = Path(tmpdir) / "config" / "skus" / "smt"
            sku_dir.mkdir(parents=True)
            yield sku_dir
    
    @pytest.fixture
    def valid_sku_data(self):
        """Valid SKU configuration with relay groups"""
        return {
            "description": "Test SKU with grouped relays",
            "relay_mapping": {
                "1,2,3": {"board": 1, "function": "mainbeam"},
                "4": {"board": 1, "function": "position"},
                "5,6": {"board": 1, "function": "turn_signal"},
                "7,8,9": {"board": 2, "function": "mainbeam"},
                "10": {"board": 2, "function": "position"},
                "11,12": {"board": 2, "function": "turn_signal"}
            },
            "test_sequence": [
                {
                    "function": "mainbeam",
                    "duration_ms": 500,
                    "delay_after_ms": 100,
                    "limits": {
                        "current_a": {"min": 5.4, "max": 6.9},
                        "voltage_v": {"min": 11.5, "max": 12.5}
                    }
                },
                {
                    "function": "position",
                    "duration_ms": 300,
                    "delay_after_ms": 100,
                    "limits": {
                        "current_a": {"min": 0.8, "max": 1.2},
                        "voltage_v": {"min": 11.5, "max": 12.5}
                    }
                }
            ]
        }
    
    @pytest.mark.unit
    def test_valid_sku_configuration(self, temp_sku_dir, valid_sku_data):
        """Test loading valid SKU configuration"""
        # Write SKU file
        sku_file = temp_sku_dir / "TEST001.json"
        with open(sku_file, 'w') as f:
            json.dump(valid_sku_data, f)
        
        # Load with SKU manager
        manager = SKUManager(str(temp_sku_dir.parent.parent))
        
        # Verify SKU loaded
        assert "TEST001" in manager.get_all_skus()
        
        # Get SKU data
        sku_data = manager.get_sku("TEST001")
        assert sku_data is not None
        assert "relay_mapping" in sku_data
        assert "test_sequence" in sku_data
    
    @pytest.mark.unit
    def test_relay_group_parsing(self):
        """Test parsing of relay groups from SKU"""
        relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"},
            "5, 6": {"board": 1, "function": "turn_signal"}  # With space
        }
        
        # Validate each group
        for relay_str, mapping in relay_mapping.items():
            # Parse relay numbers
            relays = [int(r.strip()) for r in relay_str.split(",")]
            
            # Check all relays are valid (1-16)
            assert all(1 <= r <= 16 for r in relays)
            
            # Check board and function exist
            assert "board" in mapping
            assert "function" in mapping
            assert isinstance(mapping["board"], int)
            assert isinstance(mapping["function"], str)
    
    @pytest.mark.unit
    def test_duplicate_relay_detection(self):
        """Test detection of duplicate relays across groups"""
        relay_mapping = {
            "1,2,3": {"board": 1, "function": "mainbeam"},
            "3,4,5": {"board": 2, "function": "mainbeam"}  # 3 is duplicate
        }
        
        # Check for duplicates
        all_relays = []
        duplicates = []
        
        for relay_str in relay_mapping.keys():
            relays = [int(r.strip()) for r in relay_str.split(",")]
            for relay in relays:
                if relay in all_relays:
                    duplicates.append(relay)
                else:
                    all_relays.append(relay)
        
        assert len(duplicates) > 0
        assert 3 in duplicates
    
    @pytest.mark.unit
    def test_invalid_relay_numbers(self):
        """Test detection of invalid relay numbers"""
        invalid_mappings = [
            {"0": {"board": 1, "function": "test"}},      # Too low
            {"17": {"board": 1, "function": "test"}},     # Too high
            {"1,17": {"board": 1, "function": "test"}},   # Mixed valid/invalid
        ]
        
        for mapping in invalid_mappings:
            for relay_str in mapping.keys():
                relays = [int(r.strip()) for r in relay_str.split(",")]
                # Should have at least one invalid relay
                assert not all(1 <= r <= 16 for r in relays)
    
    @pytest.mark.unit
    def test_timing_validation(self):
        """Test timing parameter validation"""
        test_sequences = [
            # Valid timings
            {"function": "test", "duration_ms": 100, "delay_after_ms": 0},     # Minimum
            {"function": "test", "duration_ms": 5000, "delay_after_ms": 1000}, # Normal
            
            # Invalid timings
            {"function": "test", "duration_ms": 50, "delay_after_ms": 0},      # Too short
            {"function": "test", "duration_ms": -100, "delay_after_ms": 0},    # Negative
        ]
        
        for seq in test_sequences:
            duration = seq.get("duration_ms", 0)
            delay = seq.get("delay_after_ms", 0)
            
            # Validate timing
            is_valid = duration >= 100 and delay >= 0
            
            if duration == 100 or duration == 5000:
                assert is_valid
            else:
                assert not is_valid
    
    @pytest.mark.unit
    def test_total_sequence_time(self):
        """Test total sequence time calculation"""
        test_sequence = [
            {"function": "test1", "duration_ms": 10000, "delay_after_ms": 5000},
            {"function": "test2", "duration_ms": 10000, "delay_after_ms": 5000},
            {"function": "test3", "duration_ms": 10000, "delay_after_ms": 5000}
        ]
        
        # Calculate total time
        total_time = sum(
            step.get("duration_ms", 0) + step.get("delay_after_ms", 0)
            for step in test_sequence
        )
        
        assert total_time == 45000  # 45 seconds
        assert total_time > 30000   # Exceeds 30 second limit
    
    @pytest.mark.unit
    def test_limits_validation(self):
        """Test measurement limits validation"""
        valid_limits = {
            "current_a": {"min": 0.5, "max": 10.0},
            "voltage_v": {"min": 10.0, "max": 14.0}
        }
        
        # Check structure
        assert "current_a" in valid_limits
        assert "voltage_v" in valid_limits
        assert "min" in valid_limits["current_a"]
        assert "max" in valid_limits["current_a"]
        
        # Check values
        assert valid_limits["current_a"]["min"] < valid_limits["current_a"]["max"]
        assert valid_limits["voltage_v"]["min"] < valid_limits["voltage_v"]["max"]
        
        # Check reasonable ranges
        assert 0 <= valid_limits["current_a"]["min"] <= 20
        assert 0 <= valid_limits["current_a"]["max"] <= 20
        assert 0 <= valid_limits["voltage_v"]["min"] <= 30
        assert 0 <= valid_limits["voltage_v"]["max"] <= 30
    
    @pytest.mark.unit
    def test_backward_compatibility(self, temp_sku_dir):
        """Test backward compatibility with old single-relay format"""
        old_format_sku = {
            "description": "Old format SKU",
            "relay_mapping": {
                "1": {"board": 1, "function": "mainbeam"},
                "2": {"board": 2, "function": "mainbeam"},
                "3": {"board": 1, "function": "position"},
                "4": {"board": 2, "function": "position"}
            },
            "test_sequence": [
                {
                    "function": "mainbeam",
                    "duration_ms": 500,
                    "delay_after_ms": 100
                }
            ]
        }
        
        # Write SKU file
        sku_file = temp_sku_dir / "OLD001.json"
        with open(sku_file, 'w') as f:
            json.dump(old_format_sku, f)
        
        # Should load without errors
        manager = SKUManager(str(temp_sku_dir.parent.parent))
        sku_data = manager.get_sku("OLD001")
        
        assert sku_data is not None
        assert all(
            "," not in relay_str
            for relay_str in sku_data["relay_mapping"].keys()
        )
    
    @pytest.mark.unit
    def test_mixed_format_compatibility(self, temp_sku_dir):
        """Test SKU with mixed single and grouped relays"""
        mixed_sku = {
            "description": "Mixed format SKU",
            "relay_mapping": {
                "1,2,3": {"board": 1, "function": "mainbeam"},  # Grouped
                "4": {"board": 1, "function": "position"},      # Single
                "5,6": {"board": 1, "function": "turn_signal"}, # Grouped
                "7": {"board": 2, "function": "position"}       # Single
            },
            "test_sequence": [
                {"function": "mainbeam", "duration_ms": 500},
                {"function": "position", "duration_ms": 300}
            ]
        }
        
        # Write SKU file
        sku_file = temp_sku_dir / "MIXED001.json"
        with open(sku_file, 'w') as f:
            json.dump(mixed_sku, f)
        
        # Should load and handle both formats
        manager = SKUManager(str(temp_sku_dir.parent.parent))
        sku_data = manager.get_sku("MIXED001")
        
        assert sku_data is not None
        relay_mapping = sku_data["relay_mapping"]
        
        # Check we have both single and grouped
        has_single = any("," not in k for k in relay_mapping.keys())
        has_grouped = any("," in k for k in relay_mapping.keys())
        
        assert has_single
        assert has_grouped


class TestSKUMigration:
    """Test SKU migration functionality"""
    
    @pytest.mark.unit
    def test_identify_groupable_relays(self):
        """Test identification of relays that can be grouped"""
        relay_mapping = {
            "1": {"board": 1, "function": "mainbeam"},
            "2": {"board": 1, "function": "mainbeam"},
            "3": {"board": 1, "function": "mainbeam"},
            "4": {"board": 1, "function": "position"},
            "5": {"board": 2, "function": "mainbeam"}
        }
        
        # Group by board and function
        groups = {}
        for relay_str, mapping in relay_mapping.items():
            if mapping:
                key = (mapping["board"], mapping["function"])
                if key not in groups:
                    groups[key] = []
                groups[key].append(relay_str)
        
        # Check grouping
        assert len(groups) == 3
        assert groups[(1, "mainbeam")] == ["1", "2", "3"]
        assert groups[(1, "position")] == ["4"]
        assert groups[(2, "mainbeam")] == ["5"]
    
    @pytest.mark.unit
    def test_create_grouped_mapping(self):
        """Test creation of grouped relay mapping"""
        groups = {
            (1, "mainbeam"): ["1", "2", "3"],
            (1, "position"): ["4"],
            (2, "mainbeam"): ["5", "6"]
        }
        
        # Create new mapping
        new_mapping = {}
        for (board, function), relays in groups.items():
            if len(relays) > 1:
                relay_key = ",".join(sorted(relays, key=int))
            else:
                relay_key = relays[0]
            
            new_mapping[relay_key] = {
                "board": board,
                "function": function
            }
        
        # Verify result
        assert "1,2,3" in new_mapping
        assert "4" in new_mapping
        assert "5,6" in new_mapping
        assert new_mapping["1,2,3"]["board"] == 1
        assert new_mapping["1,2,3"]["function"] == "mainbeam"


class TestSKUErrorHandling:
    """Test SKU error handling and edge cases"""
    
    @pytest.mark.unit
    def test_empty_relay_mapping(self, temp_sku_dir):
        """Test handling of empty relay mapping"""
        empty_sku = {
            "description": "Empty relay mapping",
            "relay_mapping": {},
            "test_sequence": []
        }
        
        sku_file = temp_sku_dir / "EMPTY001.json"
        with open(sku_file, 'w') as f:
            json.dump(empty_sku, f)
        
        manager = SKUManager(str(temp_sku_dir.parent.parent))
        sku_data = manager.get_sku("EMPTY001")
        
        assert sku_data is not None
        assert len(sku_data["relay_mapping"]) == 0
    
    @pytest.mark.unit
    def test_malformed_relay_string(self):
        """Test handling of malformed relay strings"""
        malformed = [
            "1,,3",      # Empty element
            "1,2,",      # Trailing comma
            ",1,2",      # Leading comma
            "1-3",       # Range notation (not supported)
            "a,b,c",     # Non-numeric
            ""           # Empty string
        ]
        
        for relay_str in malformed:
            try:
                relays = [int(r.strip()) for r in relay_str.split(",") if r.strip()]
                # Should handle gracefully
            except ValueError:
                # Expected for non-numeric
                pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])