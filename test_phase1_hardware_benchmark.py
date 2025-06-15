#!/usr/bin/env python3
"""
Phase 1.4 Hardware Performance Benchmark

Real hardware testing script for Phase 1 implementation.
Requires actual Arduino connection for timing and performance validation.
"""

import time
import logging
import statistics
import json
from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime

from src.hardware.smt_arduino_controller import SMTArduinoController, SMTSensorConfigurations


class Phase1HardwareBenchmark:
    """Hardware performance benchmark for Phase 1 implementation"""
    
    def __init__(self, port: str = None):
        self.logger = logging.getLogger(__name__)
        self.port = port
        self.arduino = None
        self.results = {}
        
    def setup_hardware(self) -> bool:
        """Setup Arduino connection for testing"""
        try:
            self.arduino = SMTArduinoController(baud_rate=115200)
            
            if self.port:
                if not self.arduino.connect(self.port):
                    self.logger.error(f"Failed to connect to Arduino on {self.port}")
                    return False
            else:
                # Try common ports
                common_ports = ["COM3", "COM4", "COM5", "/dev/ttyUSB0", "/dev/ttyACM0"]
                connected = False
                
                for test_port in common_ports:
                    self.logger.info(f"Trying port {test_port}...")
                    if self.arduino.connect(test_port):
                        self.port = test_port
                        connected = True
                        break
                
                if not connected:
                    self.logger.error("No Arduino found on common ports")
                    return False
            
            # Configure sensors
            sensor_configs = SMTSensorConfigurations.smt_panel_sensors()
            if not self.arduino.configure_sensors(sensor_configs):
                self.logger.error("Failed to configure sensors")
                return False
            
            self.logger.info(f"Arduino connected successfully on {self.port}")
            return True
            
        except Exception as e:
            self.logger.error(f"Hardware setup error: {e}")
            return False
    
    def benchmark_individual_commands(self, iterations: int = 10) -> Dict[str, Any]:
        """Benchmark individual command performance"""
        self.logger.info(f"Benchmarking individual commands ({iterations} iterations)")
        
        latencies = []
        failures = 0
        
        for i in range(iterations):
            try:
                start_time = time.time()
                response = self.arduino.send_command("STATUS", timeout=2.0)
                end_time = time.time()
                
                if response:
                    latency = end_time - start_time
                    latencies.append(latency)
                else:
                    failures += 1
                    
            except Exception as e:
                self.logger.error(f"Command {i+1} failed: {e}")
                failures += 1
            
            # Small delay between commands
            time.sleep(0.1)
        
        if latencies:
            results = {
                "iterations": iterations,
                "successful": len(latencies),
                "failures": failures,
                "avg_latency_ms": statistics.mean(latencies) * 1000,
                "max_latency_ms": max(latencies) * 1000,
                "min_latency_ms": min(latencies) * 1000,
                "std_latency_ms": statistics.stdev(latencies) * 1000 if len(latencies) > 1 else 0,
                "success_rate_percent": (len(latencies) / iterations) * 100
            }
        else:
            results = {
                "iterations": iterations,
                "successful": 0,
                "failures": failures,
                "success_rate_percent": 0
            }
        
        self.logger.info(f"Individual command results: {results}")
        return results
    
    def benchmark_relay_measurements(self, relay_count: int = 16, iterations: int = 5) -> Dict[str, Any]:
        """Benchmark relay measurement performance"""
        self.logger.info(f"Benchmarking {relay_count} relay measurements ({iterations} iterations)")
        
        measurement_times = []
        successful_measurements = []
        total_relays_measured = 0
        
        relay_list = list(range(1, relay_count + 1))
        
        for iteration in range(iterations):
            try:
                self.logger.info(f"Iteration {iteration + 1}/{iterations}")
                
                start_time = time.time()
                results = self.arduino.measure_relays(relay_list, timeout=3.0)
                end_time = time.time()
                
                measurement_time = end_time - start_time
                measurement_times.append(measurement_time)
                
                # Count successful measurements
                successful_count = sum(1 for v in results.values() if v is not None)
                successful_measurements.append(successful_count)
                total_relays_measured += successful_count
                
                self.logger.info(f"Iteration {iteration + 1}: {measurement_time:.2f}s, {successful_count}/{relay_count} relays")
                
                # Cooldown between iterations
                time.sleep(2.0)
                
            except Exception as e:
                self.logger.error(f"Measurement iteration {iteration + 1} failed: {e}")
                successful_measurements.append(0)
        
        results = {
            "relay_count": relay_count,
            "iterations": iterations,
            "total_relays_measured": total_relays_measured,
            "avg_time_seconds": statistics.mean(measurement_times) if measurement_times else 0,
            "max_time_seconds": max(measurement_times) if measurement_times else 0,
            "min_time_seconds": min(measurement_times) if measurement_times else 0,
            "avg_time_per_relay_ms": (statistics.mean(measurement_times) / relay_count * 1000) if measurement_times else 0,
            "throughput_relays_per_second": relay_count / statistics.mean(measurement_times) if measurement_times else 0,
            "avg_success_count": statistics.mean(successful_measurements) if successful_measurements else 0,
            "success_rate_percent": (sum(successful_measurements) / (iterations * relay_count)) * 100
        }
        
        self.logger.info(f"Relay measurement results: {results}")
        return results
    
    def benchmark_command_throttling(self, command_count: int = 20) -> Dict[str, Any]:
        """Benchmark command throttling effectiveness"""
        self.logger.info(f"Benchmarking command throttling ({command_count} rapid commands)")
        
        commands = ["STATUS", "ID"] * (command_count // 2)
        command_times = []
        
        start_time = time.time()
        
        for i, command in enumerate(commands):
            cmd_start = time.time()
            response = self.arduino.send_command(command, timeout=2.0)
            cmd_end = time.time()
            
            command_interval = cmd_end - cmd_start
            command_times.append(command_interval)
            
            if i > 0:
                inter_command_time = cmd_start - prev_cmd_end
                if inter_command_time < 0.045:  # Should be throttled to 50ms minimum
                    self.logger.warning(f"Command {i+1} not properly throttled: {inter_command_time*1000:.1f}ms")
            
            prev_cmd_end = cmd_end
        
        total_time = time.time() - start_time
        
        results = {
            "command_count": command_count,
            "total_time_seconds": total_time,
            "avg_command_time_ms": statistics.mean(command_times) * 1000,
            "min_command_interval_ms": 50,  # Expected throttling
            "actual_avg_interval_ms": (total_time / command_count) * 1000,
            "throttling_effective": (total_time / command_count) >= 0.045  # 45ms minimum due to throttling
        }
        
        self.logger.info(f"Command throttling results: {results}")
        return results
    
    def test_buffer_overflow_prevention(self) -> Dict[str, Any]:
        """Test that buffer overflow is prevented"""
        self.logger.info("Testing buffer overflow prevention")
        
        # Test with many rapid small commands
        rapid_commands = ["STATUS"] * 50
        
        start_time = time.time()
        successful = 0
        failed = 0
        
        for i, command in enumerate(rapid_commands):
            try:
                response = self.arduino.send_command(command, timeout=1.0)
                if response:
                    successful += 1
                else:
                    failed += 1
                    
                # Very short delay to stress test
                time.sleep(0.01)
                
            except Exception as e:
                self.logger.error(f"Command {i+1} failed: {e}")
                failed += 1
        
        total_time = time.time() - start_time
        
        results = {
            "total_commands": len(rapid_commands),
            "successful": successful,
            "failed": failed,
            "success_rate_percent": (successful / len(rapid_commands)) * 100,
            "total_time_seconds": total_time,
            "buffer_overflow_detected": failed > (len(rapid_commands) * 0.1)  # >10% failure suggests overflow
        }
        
        self.logger.info(f"Buffer overflow test results: {results}")
        return results
    
    def run_full_benchmark(self) -> Dict[str, Any]:
        """Run complete benchmark suite"""
        self.logger.info("Starting Phase 1 Hardware Benchmark Suite")
        
        if not self.setup_hardware():
            return {"error": "Failed to setup hardware"}
        
        benchmark_results = {
            "timestamp": datetime.now().isoformat(),
            "arduino_port": self.port,
            "phase": "Phase 1.4 Hardware Verification"
        }
        
        try:
            # Test 1: Individual command latency
            self.logger.info("\n=== Test 1: Individual Command Latency ===")
            benchmark_results["individual_commands"] = self.benchmark_individual_commands(20)
            
            # Test 2: Relay measurement performance
            self.logger.info("\n=== Test 2: Relay Measurement Performance ===")
            benchmark_results["relay_measurements"] = self.benchmark_relay_measurements(16, 3)
            
            # Test 3: Command throttling
            self.logger.info("\n=== Test 3: Command Throttling ===")
            benchmark_results["command_throttling"] = self.benchmark_command_throttling(15)
            
            # Test 4: Buffer overflow prevention
            self.logger.info("\n=== Test 4: Buffer Overflow Prevention ===")
            benchmark_results["buffer_overflow"] = self.test_buffer_overflow_prevention()
            
            # Overall assessment
            benchmark_results["assessment"] = self.assess_performance(benchmark_results)
            
        except Exception as e:
            self.logger.error(f"Benchmark error: {e}")
            benchmark_results["error"] = str(e)
        
        finally:
            if self.arduino:
                self.arduino.disconnect()
        
        return benchmark_results
    
    def assess_performance(self, results: Dict[str, Any]) -> Dict[str, Any]:
        """Assess overall performance against targets"""
        assessment = {
            "targets_met": [],
            "targets_missed": [],
            "overall_grade": "UNKNOWN"
        }
        
        try:
            # Target 1: Command latency < 100ms
            if "individual_commands" in results:
                avg_latency = results["individual_commands"].get("avg_latency_ms", 999)
                if avg_latency < 100:
                    assessment["targets_met"].append(f"Command latency: {avg_latency:.1f}ms < 100ms")
                else:
                    assessment["targets_missed"].append(f"Command latency: {avg_latency:.1f}ms >= 100ms")
            
            # Target 2: Success rate > 99%
            if "individual_commands" in results:
                success_rate = results["individual_commands"].get("success_rate_percent", 0)
                if success_rate >= 99:
                    assessment["targets_met"].append(f"Success rate: {success_rate:.1f}% >= 99%")
                else:
                    assessment["targets_missed"].append(f"Success rate: {success_rate:.1f}% < 99%")
            
            # Target 3: 16 relays in under 5 seconds
            if "relay_measurements" in results:
                avg_time = results["relay_measurements"].get("avg_time_seconds", 999)
                if avg_time < 5.0:
                    assessment["targets_met"].append(f"16-relay time: {avg_time:.1f}s < 5.0s")
                else:
                    assessment["targets_missed"].append(f"16-relay time: {avg_time:.1f}s >= 5.0s")
            
            # Target 4: No buffer overflow
            if "buffer_overflow" in results:
                overflow_detected = results["buffer_overflow"].get("buffer_overflow_detected", True)
                if not overflow_detected:
                    assessment["targets_met"].append("No buffer overflow detected")
                else:
                    assessment["targets_missed"].append("Buffer overflow detected")
            
            # Target 5: Command throttling working
            if "command_throttling" in results:
                throttling_effective = results["command_throttling"].get("throttling_effective", False)
                if throttling_effective:
                    assessment["targets_met"].append("Command throttling effective")
                else:
                    assessment["targets_missed"].append("Command throttling not effective")
            
            # Overall grade
            total_targets = len(assessment["targets_met"]) + len(assessment["targets_missed"])
            met_targets = len(assessment["targets_met"])
            
            if total_targets > 0:
                score = (met_targets / total_targets) * 100
                if score >= 90:
                    assessment["overall_grade"] = "EXCELLENT"
                elif score >= 80:
                    assessment["overall_grade"] = "GOOD"
                elif score >= 70:
                    assessment["overall_grade"] = "ACCEPTABLE"
                else:
                    assessment["overall_grade"] = "NEEDS_IMPROVEMENT"
                
                assessment["score_percent"] = score
            
        except Exception as e:
            self.logger.error(f"Assessment error: {e}")
            assessment["error"] = str(e)
        
        return assessment
    
    def save_results(self, results: Dict[str, Any], filename: str = None):
        """Save benchmark results to file"""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"phase1_benchmark_{timestamp}.json"
        
        try:
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2)
            
            self.logger.info(f"Results saved to {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to save results: {e}")


def main():
    """Main benchmark execution"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("PHASE 1.4 HARDWARE PERFORMANCE BENCHMARK")
    print("=" * 60)
    print()
    print("This benchmark requires a physical Arduino connection.")
    print("Connect your SMT Arduino before proceeding.")
    print()
    
    # Get port from user
    port = input("Enter Arduino port (or press Enter to auto-detect): ").strip()
    if not port:
        port = None
    
    # Run benchmark
    benchmark = Phase1HardwareBenchmark(port)
    results = benchmark.run_full_benchmark()
    
    # Print results
    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    
    if "error" in results:
        print(f"❌ Benchmark failed: {results['error']}")
        return
    
    # Print summary
    if "assessment" in results:
        assessment = results["assessment"]
        grade = assessment.get("overall_grade", "UNKNOWN")
        score = assessment.get("score_percent", 0)
        
        print(f"\n🎯 Overall Grade: {grade} ({score:.1f}%)")
        
        if assessment.get("targets_met"):
            print("\n✅ Targets Met:")
            for target in assessment["targets_met"]:
                print(f"   • {target}")
        
        if assessment.get("targets_missed"):
            print("\n❌ Targets Missed:")
            for target in assessment["targets_missed"]:
                print(f"   • {target}")
    
    # Save results
    benchmark.save_results(results)
    
    print(f"\n📊 Detailed results saved to JSON file")
    
    # Final assessment
    if results.get("assessment", {}).get("overall_grade") in ["EXCELLENT", "GOOD"]:
        print("\n🎉 Phase 1 hardware performance meets targets!")
        print("✅ Ready for production use")
    else:
        print("\n⚠️  Phase 1 hardware performance needs improvement")
        print("🔧 Review failed targets before production use")


if __name__ == "__main__":
    main()