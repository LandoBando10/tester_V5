#!/usr/bin/env python3
"""
Phase 4.4 Performance Benchmark Suite

Comprehensive performance comparison between Phase 4.4 binary protocol 
and legacy text-based protocols. This benchmark measures:

- Message encoding/decoding latency
- Throughput and bandwidth efficiency  
- Memory usage optimization
- Protocol overhead comparison
- Real-world communication scenarios

Usage:
    python test_phase4_4_performance_benchmark.py
"""

import time
import sys
import os
import statistics
import json
from typing import List, Dict, Any
import tracemalloc
import gc

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from protocols.binary_message_formats import (
    create_ping_message, create_measure_message, create_measure_group_message,
    PingResponseMessage, MeasureResponseMessage, MeasureGroupResponseMessage,
    TestType, ErrorCode
)

from protocols.binary_protocol import BinaryMessageCodec, BinaryProtocolConfig

# Simulate legacy text protocol for comparison
class LegacyTextProtocol:
    """Simulated legacy text protocol for performance comparison"""
    
    @staticmethod
    def encode_ping(sequence_id: int) -> bytes:
        message = f"PING:{sequence_id}"
        return message.encode('utf-8') + b'\n'
    
    @staticmethod
    def encode_measure(relay_id: int) -> bytes:
        message = f"MEASURE:{relay_id}"
        return message.encode('utf-8') + b'\n'
    
    @staticmethod
    def encode_measure_group(relay_ids: List[int]) -> bytes:
        relay_list = ','.join(map(str, relay_ids))
        message = f"MEASURE_GROUP:{relay_list}"
        return message.encode('utf-8') + b'\n'
    
    @staticmethod
    def decode_ping_response(data: bytes) -> Dict[str, Any]:
        text = data.decode('utf-8').strip()
        # Simulate parsing: "OK:PING_RESPONSE:123:SMT_TESTER_1"
        parts = text.split(':')
        return {
            'success': parts[0] == 'OK',
            'sequence_id': int(parts[2]) if len(parts) > 2 else 0,
            'device_id': parts[3] if len(parts) > 3 else ""
        }
    
    @staticmethod
    def decode_measure_response(data: bytes) -> Dict[str, Any]:
        text = data.decode('utf-8').strip()
        # Simulate parsing: "OK:MEASUREMENT:1,V=5.000,I=0.100,P=0.500"
        if text.startswith("OK:MEASUREMENT:"):
            parts = text[15:].split(',')
            relay_id = int(parts[0])
            voltage = float(parts[1].split('=')[1])
            current = float(parts[2].split('=')[1])
            power = float(parts[3].split('=')[1])
            return {
                'success': True,
                'relay_id': relay_id,
                'voltage': voltage,
                'current': current,
                'power': power
            }
        return {'success': False}


class PerformanceBenchmark:
    """Performance benchmark runner and analyzer"""
    
    def __init__(self):
        self.results = {}
        self.config = BinaryProtocolConfig()
        self.binary_codec = BinaryMessageCodec(self.config)
        self.legacy_protocol = LegacyTextProtocol()
    
    def benchmark_encoding_latency(self, iterations: int = 10000) -> Dict[str, Any]:
        """Benchmark message encoding latency"""
        print(f"\n📊 Benchmarking encoding latency ({iterations:,} iterations)...")
        
        results = {
            'iterations': iterations,
            'binary': {},
            'text': {}
        }
        
        # Binary protocol ping encoding
        ping_msg = create_ping_message(12345)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            encoded = self.binary_codec.encode_message(ping_msg)
            end = time.perf_counter()
            times.append(end - start)
        
        results['binary']['ping'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000,
            'size_bytes': len(encoded)
        }
        
        # Text protocol ping encoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            encoded = self.legacy_protocol.encode_ping(12345)
            end = time.perf_counter()
            times.append(end - start)
        
        results['text']['ping'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000,
            'size_bytes': len(encoded)
        }
        
        # Binary protocol measure encoding
        measure_msg = create_measure_message(5, TestType.VOLTAGE_CURRENT)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            encoded = self.binary_codec.encode_message(measure_msg)
            end = time.perf_counter()
            times.append(end - start)
        
        results['binary']['measure'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000,
            'size_bytes': len(encoded)
        }
        
        # Text protocol measure encoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            encoded = self.legacy_protocol.encode_measure(5)
            end = time.perf_counter()
            times.append(end - start)
        
        results['text']['measure'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000,
            'size_bytes': len(encoded)
        }
        
        # Binary protocol group measure encoding (16 relays)
        group_msg = create_measure_group_message(list(range(1, 17)), TestType.VOLTAGE_CURRENT)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            encoded = self.binary_codec.encode_message(group_msg)
            end = time.perf_counter()
            times.append(end - start)
        
        results['binary']['group_measure'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000,
            'size_bytes': len(encoded)
        }
        
        # Text protocol group measure encoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            encoded = self.legacy_protocol.encode_measure_group(list(range(1, 17)))
            end = time.perf_counter()
            times.append(end - start)
        
        results['text']['group_measure'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000,
            'size_bytes': len(encoded)
        }
        
        return results
    
    def benchmark_decoding_latency(self, iterations: int = 10000) -> Dict[str, Any]:
        """Benchmark message decoding latency"""
        print(f"\n📊 Benchmarking decoding latency ({iterations:,} iterations)...")
        
        results = {
            'iterations': iterations,
            'binary': {},
            'text': {}
        }
        
        # Prepare encoded messages
        binary_ping = create_ping_message(12345).pack()
        text_ping = b"OK:PING_RESPONSE:12345:SMT_TESTER_1\n"
        
        binary_measure = MeasureResponseMessage(
            relay_id=5, test_type=TestType.VOLTAGE_CURRENT,
            voltage=5.0, current=0.1, error_code=ErrorCode.SUCCESS
        ).pack()
        text_measure = b"OK:MEASUREMENT:5,V=5.000,I=0.100,P=0.500\n"
        
        # Binary ping decoding
        from protocols.binary_message_formats import BinaryMessage
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            decoded = BinaryMessage.unpack(binary_ping)
            end = time.perf_counter()
            times.append(end - start)
        
        results['binary']['ping'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000
        }
        
        # Text ping decoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            decoded = self.legacy_protocol.decode_ping_response(text_ping)
            end = time.perf_counter()
            times.append(end - start)
        
        results['text']['ping'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000
        }
        
        # Binary measure decoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            decoded = BinaryMessage.unpack(binary_measure)
            end = time.perf_counter()
            times.append(end - start)
        
        results['binary']['measure'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000
        }
        
        # Text measure decoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            decoded = self.legacy_protocol.decode_measure_response(text_measure)
            end = time.perf_counter()
            times.append(end - start)
        
        results['text']['measure'] = {
            'avg_ms': statistics.mean(times) * 1000,
            'median_ms': statistics.median(times) * 1000,
            'min_ms': min(times) * 1000,
            'max_ms': max(times) * 1000,
            'std_ms': statistics.stdev(times) * 1000
        }
        
        return results
    
    def benchmark_throughput(self, duration_seconds: int = 5) -> Dict[str, Any]:
        """Benchmark message throughput"""
        print(f"\n📊 Benchmarking throughput ({duration_seconds}s test)...")
        
        results = {
            'duration_seconds': duration_seconds,
            'binary': {},
            'text': {}
        }
        
        # Binary protocol throughput
        ping_msg = create_ping_message(12345)
        measure_msg = create_measure_message(5, TestType.VOLTAGE_CURRENT)
        
        start_time = time.time()
        count = 0
        total_bytes = 0
        
        while time.time() - start_time < duration_seconds:
            # Alternate between ping and measure
            if count % 2 == 0:
                encoded = self.binary_codec.encode_message(ping_msg)
            else:
                encoded = self.binary_codec.encode_message(measure_msg)
            total_bytes += len(encoded)
            count += 1
        
        elapsed = time.time() - start_time
        results['binary'] = {
            'messages_per_second': count / elapsed,
            'bytes_per_second': total_bytes / elapsed,
            'total_messages': count,
            'total_bytes': total_bytes
        }
        
        # Text protocol throughput
        start_time = time.time()
        count = 0
        total_bytes = 0
        
        while time.time() - start_time < duration_seconds:
            # Alternate between ping and measure
            if count % 2 == 0:
                encoded = self.legacy_protocol.encode_ping(12345)
            else:
                encoded = self.legacy_protocol.encode_measure(5)
            total_bytes += len(encoded)
            count += 1
        
        elapsed = time.time() - start_time
        results['text'] = {
            'messages_per_second': count / elapsed,
            'bytes_per_second': total_bytes / elapsed,
            'total_messages': count,
            'total_bytes': total_bytes
        }
        
        return results
    
    def benchmark_memory_usage(self, message_count: int = 1000) -> Dict[str, Any]:
        """Benchmark memory usage"""
        print(f"\n📊 Benchmarking memory usage ({message_count:,} messages)...")
        
        results = {
            'message_count': message_count,
            'binary': {},
            'text': {}
        }
        
        # Binary protocol memory usage
        tracemalloc.start()
        gc.collect()
        
        binary_messages = []
        for i in range(message_count):
            if i % 3 == 0:
                msg = create_ping_message(i)
            elif i % 3 == 1:
                msg = create_measure_message(i % 16 + 1, TestType.VOLTAGE_CURRENT)
            else:
                msg = create_measure_group_message([1, 2, 3, 4], TestType.RELAY_CONTINUITY)
            
            encoded = self.binary_codec.encode_message(msg)
            binary_messages.append(encoded)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        total_size = sum(len(msg) for msg in binary_messages)
        results['binary'] = {
            'current_memory_kb': current / 1024,
            'peak_memory_kb': peak / 1024,
            'total_message_bytes': total_size,
            'avg_bytes_per_message': total_size / message_count,
            'memory_efficiency': total_size / peak if peak > 0 else 0
        }
        
        # Text protocol memory usage
        tracemalloc.start()
        gc.collect()
        
        text_messages = []
        for i in range(message_count):
            if i % 3 == 0:
                msg = self.legacy_protocol.encode_ping(i)
            elif i % 3 == 1:
                msg = self.legacy_protocol.encode_measure(i % 16 + 1)
            else:
                msg = self.legacy_protocol.encode_measure_group([1, 2, 3, 4])
            
            text_messages.append(msg)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        total_size = sum(len(msg) for msg in text_messages)
        results['text'] = {
            'current_memory_kb': current / 1024,
            'peak_memory_kb': peak / 1024,
            'total_message_bytes': total_size,
            'avg_bytes_per_message': total_size / message_count,
            'memory_efficiency': total_size / peak if peak > 0 else 0
        }
        
        return results
    
    def benchmark_bandwidth_efficiency(self) -> Dict[str, Any]:
        """Benchmark bandwidth efficiency for various message types"""
        print(f"\n📊 Benchmarking bandwidth efficiency...")
        
        results = {
            'binary': {},
            'text': {},
            'efficiency_ratios': {}
        }
        
        # Test different message types
        test_cases = [
            ('ping', create_ping_message(12345), self.legacy_protocol.encode_ping(12345)),
            ('single_measure', create_measure_message(5, TestType.VOLTAGE_CURRENT), 
             self.legacy_protocol.encode_measure(5)),
            ('small_group', create_measure_group_message([1, 2, 3, 4], TestType.VOLTAGE_CURRENT),
             self.legacy_protocol.encode_measure_group([1, 2, 3, 4])),
            ('large_group', create_measure_group_message(list(range(1, 17)), TestType.VOLTAGE_CURRENT),
             self.legacy_protocol.encode_measure_group(list(range(1, 17))))
        ]
        
        for test_name, binary_msg, text_msg in test_cases:
            # Binary protocol
            binary_encoded = self.binary_codec.encode_message(binary_msg)
            binary_size = len(binary_encoded)
            
            # Text protocol  
            text_size = len(text_msg)
            
            # Calculate efficiency ratio
            efficiency_ratio = text_size / binary_size if binary_size > 0 else 0
            
            results['binary'][test_name] = {
                'size_bytes': binary_size,
                'header_overhead': 8,  # Binary header size
                'payload_efficiency': (binary_size - 8) / binary_size if binary_size > 8 else 0
            }
            
            results['text'][test_name] = {
                'size_bytes': text_size,
                'overhead_estimate': len(test_name) + 2,  # Command name + delimiters
                'payload_efficiency': (text_size - len(test_name) - 2) / text_size if text_size > 0 else 0
            }
            
            results['efficiency_ratios'][test_name] = {
                'text_to_binary_ratio': efficiency_ratio,
                'binary_savings_percent': ((text_size - binary_size) / text_size * 100) if text_size > 0 else 0,
                'absolute_savings_bytes': text_size - binary_size
            }
        
        return results
    
    def run_comprehensive_benchmark(self) -> Dict[str, Any]:
        """Run all benchmarks and compile results"""
        print("🚀 Starting Phase 4.4 Performance Benchmark Suite")
        print("="*60)
        
        start_time = time.time()
        
        results = {
            'metadata': {
                'timestamp': time.time(),
                'python_version': sys.version,
                'test_duration_seconds': 0
            },
            'encoding_latency': self.benchmark_encoding_latency(),
            'decoding_latency': self.benchmark_decoding_latency(),
            'throughput': self.benchmark_throughput(),
            'memory_usage': self.benchmark_memory_usage(),
            'bandwidth_efficiency': self.benchmark_bandwidth_efficiency()
        }
        
        results['metadata']['test_duration_seconds'] = time.time() - start_time
        
        return results
    
    def print_summary(self, results: Dict[str, Any]):
        """Print benchmark summary"""
        print("\n" + "="*60)
        print("📊 PHASE 4.4 PERFORMANCE BENCHMARK SUMMARY")
        print("="*60)
        
        # Encoding latency summary
        enc = results['encoding_latency']
        print(f"\n🔧 ENCODING LATENCY:")
        print(f"   Ping Messages:")
        print(f"     Binary: {enc['binary']['ping']['avg_ms']:.3f}ms avg, {enc['binary']['ping']['size_bytes']} bytes")
        print(f"     Text:   {enc['text']['ping']['avg_ms']:.3f}ms avg, {enc['text']['ping']['size_bytes']} bytes")
        print(f"     Speedup: {enc['text']['ping']['avg_ms']/enc['binary']['ping']['avg_ms']:.1f}x")
        
        print(f"   Measure Messages:")
        print(f"     Binary: {enc['binary']['measure']['avg_ms']:.3f}ms avg, {enc['binary']['measure']['size_bytes']} bytes")
        print(f"     Text:   {enc['text']['measure']['avg_ms']:.3f}ms avg, {enc['text']['measure']['size_bytes']} bytes")
        print(f"     Speedup: {enc['text']['measure']['avg_ms']/enc['binary']['measure']['avg_ms']:.1f}x")
        
        print(f"   Group Measure (16 relays):")
        print(f"     Binary: {enc['binary']['group_measure']['avg_ms']:.3f}ms avg, {enc['binary']['group_measure']['size_bytes']} bytes")
        print(f"     Text:   {enc['text']['group_measure']['avg_ms']:.3f}ms avg, {enc['text']['group_measure']['size_bytes']} bytes")
        print(f"     Speedup: {enc['text']['group_measure']['avg_ms']/enc['binary']['group_measure']['avg_ms']:.1f}x")
        
        # Decoding latency summary
        dec = results['decoding_latency']
        print(f"\n🔍 DECODING LATENCY:")
        print(f"   Binary vs Text average speedup:")
        ping_speedup = dec['text']['ping']['avg_ms'] / dec['binary']['ping']['avg_ms']
        measure_speedup = dec['text']['measure']['avg_ms'] / dec['binary']['measure']['avg_ms']
        print(f"     Ping: {ping_speedup:.1f}x faster")
        print(f"     Measure: {measure_speedup:.1f}x faster")
        
        # Throughput summary
        thr = results['throughput']
        print(f"\n📈 THROUGHPUT:")
        print(f"   Binary: {thr['binary']['messages_per_second']:,.0f} msg/s, {thr['binary']['bytes_per_second']:,.0f} bytes/s")
        print(f"   Text:   {thr['text']['messages_per_second']:,.0f} msg/s, {thr['text']['bytes_per_second']:,.0f} bytes/s")
        print(f"   Message throughput gain: {thr['binary']['messages_per_second']/thr['text']['messages_per_second']:.1f}x")
        
        # Memory usage summary
        mem = results['memory_usage']
        print(f"\n💾 MEMORY USAGE (1000 messages):")
        print(f"   Binary: {mem['binary']['peak_memory_kb']:.1f}KB peak, {mem['binary']['avg_bytes_per_message']:.1f} bytes/msg")
        print(f"   Text:   {mem['text']['peak_memory_kb']:.1f}KB peak, {mem['text']['avg_bytes_per_message']:.1f} bytes/msg")
        print(f"   Memory efficiency gain: {mem['text']['peak_memory_kb']/mem['binary']['peak_memory_kb']:.1f}x")
        
        # Bandwidth efficiency summary
        bw = results['bandwidth_efficiency']
        print(f"\n📡 BANDWIDTH EFFICIENCY:")
        for test_name in ['ping', 'single_measure', 'small_group', 'large_group']:
            ratio = bw['efficiency_ratios'][test_name]
            print(f"   {test_name.replace('_', ' ').title()}:")
            print(f"     Size ratio (text/binary): {ratio['text_to_binary_ratio']:.2f}x")
            print(f"     Binary saves: {ratio['binary_savings_percent']:.1f}% ({ratio['absolute_savings_bytes']} bytes)")
        
        # Overall assessment
        print(f"\n✅ OVERALL ASSESSMENT:")
        avg_encode_speedup = (
            enc['text']['ping']['avg_ms']/enc['binary']['ping']['avg_ms'] +
            enc['text']['measure']['avg_ms']/enc['binary']['measure']['avg_ms'] +
            enc['text']['group_measure']['avg_ms']/enc['binary']['group_measure']['avg_ms']
        ) / 3
        
        avg_decode_speedup = (ping_speedup + measure_speedup) / 2
        throughput_gain = thr['binary']['messages_per_second']/thr['text']['messages_per_second']
        memory_efficiency = mem['text']['peak_memory_kb']/mem['binary']['peak_memory_kb']
        
        print(f"   Average encoding speedup: {avg_encode_speedup:.1f}x")
        print(f"   Average decoding speedup: {avg_decode_speedup:.1f}x")
        print(f"   Throughput improvement: {throughput_gain:.1f}x")
        print(f"   Memory efficiency: {memory_efficiency:.1f}x better")
        
        # Performance score (weighted average)
        performance_score = (
            avg_encode_speedup * 0.3 +
            avg_decode_speedup * 0.3 +
            throughput_gain * 0.2 +
            memory_efficiency * 0.2
        )
        
        print(f"\n🏆 PERFORMANCE SCORE: {performance_score:.1f}/10")
        
        if performance_score >= 2.0:
            print("   🎉 EXCELLENT - Binary protocol significantly outperforms text protocol")
        elif performance_score >= 1.5:
            print("   ✅ GOOD - Binary protocol shows clear performance advantages")
        elif performance_score >= 1.2:
            print("   ⚠️  MODERATE - Binary protocol has some performance benefits")
        else:
            print("   ❌ POOR - Binary protocol may need optimization")
        
        print(f"\n⏱️  Total benchmark time: {results['metadata']['test_duration_seconds']:.1f} seconds")


def main():
    """Main benchmark execution"""
    benchmark = PerformanceBenchmark()
    
    try:
        results = benchmark.run_comprehensive_benchmark()
        benchmark.print_summary(results)
        
        # Save detailed results to file
        with open('phase4_4_benchmark_results.json', 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\n💾 Detailed results saved to: phase4_4_benchmark_results.json")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("Phase 4.4 Binary Protocol Performance Benchmark")
    print("Comparing binary protocol vs legacy text protocol performance")
    
    success = main()
    
    if success:
        print("\n✅ Benchmark completed successfully")
        sys.exit(0)
    else:
        print("\n❌ Benchmark failed")
        sys.exit(1)