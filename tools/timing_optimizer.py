#!/usr/bin/env python3
"""
SMT Timing Optimizer Script
Finds optimal timing parameters for a specific SKU without modifying production code
"""

import time
import json
import statistics
from pathlib import Path
from typing import Dict, List, Tuple
import logging

# Add project to path
import sys
sys.path.append(str(Path(__file__).parent.parent))

from src.hardware.smt_arduino_controller import SMTArduinoController
from src.core.smt_controller import SMTController


class SMTTimingOptimizer:
    """Find optimal timing parameters for SMT testing"""
    
    def __init__(self, port: str, sku_config_path: str):
        self.port = port
        self.sku_config = self._load_sku_config(sku_config_path)
        self.arduino = SMTArduinoController(baud_rate=115200)
        self.smt_controller = SMTController(self.arduino)
        self.logger = self._setup_logger()
        
        # Timing ranges to test (ms)
        self.timing_ranges = {
            'command_interval': [10, 15, 20, 30, 50],
            'relay_settle': [20, 30, 40, 50, 75, 100],
            'measurement_delay': [10, 15, 20, 30, 50],
            'test_cooldown': [100, 300, 500, 1000, 2000]
        }
        
        # Results storage
        self.results = {}
        
    def _setup_logger(self) -> logging.Logger:
        """Setup logging for the optimizer"""
        logger = logging.getLogger('SMTTimingOptimizer')
        logger.setLevel(logging.INFO)
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        
        # File handler
        fh = logging.FileHandler('smt_timing_optimization.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        
        return logger
        
    def _load_sku_config(self, config_path: str) -> Dict:
        """Load SKU configuration"""
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def connect(self) -> bool:
        """Connect to Arduino and initialize"""
        if not self.arduino.connect(self.port):
            self.logger.error("Failed to connect to Arduino")
            return False
            
        # Configure sensors
        from src.hardware.smt_arduino_controller import SMTSensorConfigurations
        sensor_configs = SMTSensorConfigurations.smt_panel_sensors()
        
        if not self.arduino.configure_sensors(sensor_configs):
            self.logger.error("Failed to configure sensors")
            return False
            
        # Configure SMT controller
        smt_config = self.sku_config.get('smt_testing', {})
        self.smt_controller.set_configuration(smt_config)
        
        if not self.smt_controller.initialize_arduino():
            self.logger.error("Failed to initialize SMT controller")
            return False
            
        self.logger.info("Successfully connected and initialized")
        return True
    
    def test_timing_configuration(self, timing_config: Dict) -> Dict:
        """Test a specific timing configuration"""
        # Apply timing configuration
        self.arduino.min_command_interval = timing_config['command_interval'] / 1000.0
        self.arduino.min_test_interval = timing_config['test_cooldown'] / 1000.0
        
        results = {
            'errors': 0,
            'measurements': [],
            'durations': [],
            'success_rate': 0.0
        }
        
        # Get test functions from SKU config
        test_sequence = self.sku_config.get('smt_testing', {}).get('test_sequence', [])
        
        for test in test_sequence:
            function_name = test['function']
            function_relays = self.smt_controller.get_relays_for_function(function_name)
            
            if not function_relays:
                continue
                
            # Run multiple measurement cycles
            for cycle in range(5):  # 5 cycles per timing config
                start_time = time.time()
                
                try:
                    # Measure relays with current timing
                    measurements = self._measure_with_timing(
                        function_relays,
                        timing_config['relay_settle'],
                        timing_config['measurement_delay']
                    )
                    
                    if measurements:
                        results['measurements'].extend(measurements)
                    else:
                        results['errors'] += 1
                        
                except Exception as e:
                    self.logger.debug(f"Measurement error: {e}")
                    results['errors'] += 1
                
                duration = time.time() - start_time
                results['durations'].append(duration)
                
                # Small delay between cycles
                time.sleep(0.1)
        
        # Calculate success rate
        total_attempts = len(results['durations'])
        if total_attempts > 0:
            results['success_rate'] = (total_attempts - results['errors']) / total_attempts
        
        return results
    
    def _measure_with_timing(self, relays: List[int], settle_ms: int, delay_ms: int) -> List[Dict]:
        """Measure relays with specific timing parameters"""
        measurements = []
        
        for relay in relays:
            # Turn off all relays
            for r in range(1, 9):
                self.arduino.send_command(f"RELAY:{r}:OFF", timeout=0.5)
            
            # Turn on target relay
            response = self.arduino.send_command(f"RELAY:{relay}:ON", timeout=1.0)
            if not response or "ERROR" in response:
                continue
                
            # Custom settle time
            time.sleep(settle_ms / 1000.0)
            
            # Measure
            response = self.arduino.send_command(f"MEASURE:{relay}", timeout=2.0)
            
            if response and response.startswith("MEASUREMENT:"):
                # Parse measurement
                parts = response.split(':', 2)
                if len(parts) >= 3:
                    data_part = parts[2]
                    measurement = {'relay': relay}
                    
                    for item in data_part.split(','):
                        if '=' in item:
                            key, value = item.split('=', 1)
                            try:
                                if key == 'V':
                                    measurement['voltage'] = float(value)
                                elif key == 'I':
                                    measurement['current'] = float(value)
                                elif key == 'P':
                                    measurement['power'] = float(value)
                            except ValueError:
                                pass
                    
                    if 'voltage' in measurement and 'current' in measurement:
                        measurements.append(measurement)
            
            # Turn off relay
            self.arduino.send_command(f"RELAY:{relay}:OFF", timeout=0.5)
            
            # Custom delay between measurements
            time.sleep(delay_ms / 1000.0)
        
        return measurements
    
    def find_optimal_timings(self) -> Dict:
        """Find optimal timing configuration"""
        self.logger.info("Starting timing optimization...")
        
        best_config = None
        best_score = 0
        
        # Test each combination
        total_tests = (len(self.timing_ranges['command_interval']) * 
                      len(self.timing_ranges['relay_settle']) * 
                      len(self.timing_ranges['measurement_delay']) * 
                      len(self.timing_ranges['test_cooldown']))
        
        test_count = 0
        
        for cmd_interval in self.timing_ranges['command_interval']:
            for relay_settle in self.timing_ranges['relay_settle']:
                for meas_delay in self.timing_ranges['measurement_delay']:
                    for test_cooldown in self.timing_ranges['test_cooldown']:
                        test_count += 1
                        
                        timing_config = {
                            'command_interval': cmd_interval,
                            'relay_settle': relay_settle,
                            'measurement_delay': meas_delay,
                            'test_cooldown': test_cooldown
                        }
                        
                        self.logger.info(
                            f"Testing {test_count}/{total_tests}: "
                            f"cmd={cmd_interval}ms, settle={relay_settle}ms, "
                            f"delay={meas_delay}ms, cooldown={test_cooldown}ms"
                        )
                        
                        # Test this configuration
                        results = self.test_timing_configuration(timing_config)
                        
                        # Calculate score (balance speed vs reliability)
                        if results['success_rate'] >= 0.95:  # At least 95% success
                            avg_duration = statistics.mean(results['durations']) if results['durations'] else float('inf')
                            # Score favors faster times with high success rate
                            score = results['success_rate'] / avg_duration
                            
                            if score > best_score:
                                best_score = score
                                best_config = timing_config.copy()
                                best_config['avg_duration'] = avg_duration
                                best_config['success_rate'] = results['success_rate']
                                
                                self.logger.info(
                                    f"New best config! Score={score:.3f}, "
                                    f"Duration={avg_duration:.3f}s, "
                                    f"Success={results['success_rate']:.1%}"
                                )
                        
                        # Store all results
                        config_key = f"{cmd_interval}_{relay_settle}_{meas_delay}_{test_cooldown}"
                        self.results[config_key] = {
                            'config': timing_config,
                            'results': results
                        }
                        
                        # Small delay between tests
                        time.sleep(0.5)
        
        return best_config
    
    def generate_report(self, optimal_config: Dict):
        """Generate optimization report"""
        report_path = Path('smt_timing_optimization_report.json')
        
        report = {
            'sku': self.sku_config.get('sku', 'unknown'),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'optimal_configuration': optimal_config,
            'current_configuration': {
                'command_interval': 50,
                'relay_settle': 100,
                'measurement_delay': 50,
                'test_cooldown': 2000
            },
            'improvement': {},
            'all_results': []
        }
        
        # Calculate improvements
        if optimal_config:
            current_time = (2000 + 100 + 50) / 1000.0 * 4  # Rough estimate
            optimal_time = optimal_config.get('avg_duration', current_time)
            
            report['improvement'] = {
                'time_reduction': f"{(current_time - optimal_time):.2f}s",
                'percentage': f"{((current_time - optimal_time) / current_time * 100):.1f}%",
                'success_rate': f"{optimal_config.get('success_rate', 0) * 100:.1f}%"
            }
        
        # Add summary of all results
        for config_key, data in self.results.items():
            summary = {
                'configuration': data['config'],
                'success_rate': data['results']['success_rate'],
                'avg_duration': statistics.mean(data['results']['durations']) if data['results']['durations'] else None,
                'errors': data['results']['errors']
            }
            report['all_results'].append(summary)
        
        # Save report
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        self.logger.info(f"Report saved to {report_path}")
        
        # Also create a config snippet
        if optimal_config:
            config_snippet = {
                "timing": {
                    "command_interval_ms": optimal_config['command_interval'],
                    "relay_stabilization_ms": optimal_config['relay_settle'],
                    "measurement_delay_ms": optimal_config['measurement_delay'],
                    "test_cooldown_ms": optimal_config['test_cooldown']
                }
            }
            
            snippet_path = Path('optimal_timing_config.json')
            with open(snippet_path, 'w') as f:
                json.dump(config_snippet, f, indent=2)
                
            self.logger.info(f"Config snippet saved to {snippet_path}")
    
    def run(self):
        """Run the timing optimization"""
        try:
            # Connect to hardware
            if not self.connect():
                return
            
            # Find optimal timings
            optimal_config = self.find_optimal_timings()
            
            if optimal_config:
                self.logger.info("=" * 50)
                self.logger.info("OPTIMAL TIMING CONFIGURATION FOUND:")
                self.logger.info(f"Command Interval: {optimal_config['command_interval']}ms")
                self.logger.info(f"Relay Settle Time: {optimal_config['relay_settle']}ms")
                self.logger.info(f"Measurement Delay: {optimal_config['measurement_delay']}ms")
                self.logger.info(f"Test Cooldown: {optimal_config['test_cooldown']}ms")
                self.logger.info(f"Average Duration: {optimal_config['avg_duration']:.3f}s")
                self.logger.info(f"Success Rate: {optimal_config['success_rate']:.1%}")
                self.logger.info("=" * 50)
                
                # Generate report
                self.generate_report(optimal_config)
            else:
                self.logger.error("No optimal configuration found!")
                
        except Exception as e:
            self.logger.error(f"Optimization failed: {e}")
            
        finally:
            # Cleanup
            if hasattr(self, 'arduino') and self.arduino.is_connected():
                self.arduino.disconnect()


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Find optimal timing parameters for SMT testing"
    )
    parser.add_argument('port', help='Arduino serial port (e.g., COM4)')
    parser.add_argument('sku_config', help='Path to SKU configuration JSON file')
    parser.add_argument('--quick', action='store_true', 
                       help='Quick test with fewer timing combinations')
    
    args = parser.parse_args()
    
    # Create optimizer
    optimizer = SMTTimingOptimizer(args.port, args.sku_config)
    
    # Reduce test combinations for quick mode
    if args.quick:
        optimizer.timing_ranges = {
            'command_interval': [15, 30],
            'relay_settle': [30, 50],
            'measurement_delay': [15, 30],
            'test_cooldown': [300, 1000]
        }
    
    # Run optimization
    optimizer.run()


if __name__ == "__main__":
    main()