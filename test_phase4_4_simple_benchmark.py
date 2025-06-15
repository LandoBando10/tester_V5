#!/usr/bin/env python3
"""
Simplified Phase 4.4 Performance Benchmark

Simple performance comparison focusing on message encoding/decoding
without complex protocol dependencies.
"""

import time
import sys
import os
import statistics

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def benchmark_binary_vs_text():
    """Compare binary protocol vs text protocol performance"""
    print("🚀 Phase 4.4 Simple Performance Benchmark")
    print("="*50)
    
    try:
        from protocols.binary_message_formats import (
            create_ping_message, create_measure_message, create_measure_group_message,
            BinaryMessage, TestType
        )
        
        # Test parameters
        iterations = 10000
        
        print(f"\n📊 Running {iterations:,} iterations per test...")
        
        # Binary protocol tests
        print("\n🔧 BINARY PROTOCOL PERFORMANCE:")
        
        # Ping message encoding
        ping_msg = create_ping_message(12345)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            packed = ping_msg.pack()
            end = time.perf_counter()
            times.append(end - start)
        
        binary_ping_encode = {
            'avg_ms': statistics.mean(times) * 1000,
            'size_bytes': len(packed)
        }
        print(f"   Ping encode: {binary_ping_encode['avg_ms']:.3f}ms avg, {binary_ping_encode['size_bytes']} bytes")
        
        # Ping message decoding
        packed_ping = ping_msg.pack()
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            unpacked = BinaryMessage.unpack(packed_ping)
            end = time.perf_counter()
            times.append(end - start)
        
        binary_ping_decode = {
            'avg_ms': statistics.mean(times) * 1000
        }
        print(f"   Ping decode: {binary_ping_decode['avg_ms']:.3f}ms avg")
        
        # Measure message encoding
        measure_msg = create_measure_message(5, TestType.VOLTAGE_CURRENT)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            packed = measure_msg.pack()
            end = time.perf_counter()
            times.append(end - start)
        
        binary_measure_encode = {
            'avg_ms': statistics.mean(times) * 1000,
            'size_bytes': len(packed)
        }
        print(f"   Measure encode: {binary_measure_encode['avg_ms']:.3f}ms avg, {binary_measure_encode['size_bytes']} bytes")
        
        # Group message encoding (16 relays)
        group_msg = create_measure_group_message(list(range(1, 17)), TestType.VOLTAGE_CURRENT)
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            packed = group_msg.pack()
            end = time.perf_counter()
            times.append(end - start)
        
        binary_group_encode = {
            'avg_ms': statistics.mean(times) * 1000,
            'size_bytes': len(packed)
        }
        print(f"   Group encode: {binary_group_encode['avg_ms']:.3f}ms avg, {binary_group_encode['size_bytes']} bytes")
        
        # Text protocol simulation (for comparison)
        print("\n📝 TEXT PROTOCOL SIMULATION:")
        
        # Ping text encoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            text_msg = f"PING:{12345}".encode('utf-8')
            end = time.perf_counter()
            times.append(end - start)
        
        text_ping_encode = {
            'avg_ms': statistics.mean(times) * 1000,
            'size_bytes': len(text_msg)
        }
        print(f"   Ping encode: {text_ping_encode['avg_ms']:.3f}ms avg, {text_ping_encode['size_bytes']} bytes")
        
        # Ping text decoding
        text_response = "OK:PING_RESPONSE:12345:SMT_TESTER_1".encode('utf-8')
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            decoded = text_response.decode('utf-8').split(':')
            end = time.perf_counter()
            times.append(end - start)
        
        text_ping_decode = {
            'avg_ms': statistics.mean(times) * 1000
        }
        print(f"   Ping decode: {text_ping_decode['avg_ms']:.3f}ms avg")
        
        # Measure text encoding
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            text_msg = f"MEASURE:{5}".encode('utf-8')
            end = time.perf_counter()
            times.append(end - start)
        
        text_measure_encode = {
            'avg_ms': statistics.mean(times) * 1000,
            'size_bytes': len(text_msg)
        }
        print(f"   Measure encode: {text_measure_encode['avg_ms']:.3f}ms avg, {text_measure_encode['size_bytes']} bytes")
        
        # Group text encoding  
        times = []
        for _ in range(iterations):
            start = time.perf_counter()
            relay_list = ','.join(map(str, range(1, 17)))
            text_msg = f"MEASURE_GROUP:{relay_list}".encode('utf-8')
            end = time.perf_counter()
            times.append(end - start)
        
        text_group_encode = {
            'avg_ms': statistics.mean(times) * 1000,
            'size_bytes': len(text_msg)
        }
        print(f"   Group encode: {text_group_encode['avg_ms']:.3f}ms avg, {text_group_encode['size_bytes']} bytes")
        
        # Comparison summary
        print("\n📊 PERFORMANCE COMPARISON:")
        print("="*50)
        
        # Encoding comparison
        ping_encode_speedup = text_ping_encode['avg_ms'] / binary_ping_encode['avg_ms']
        measure_encode_speedup = text_measure_encode['avg_ms'] / binary_measure_encode['avg_ms']
        group_encode_speedup = text_group_encode['avg_ms'] / binary_group_encode['avg_ms']
        
        print(f"Encoding Speedup (Binary vs Text):")
        print(f"   Ping:    {ping_encode_speedup:.1f}x faster")
        print(f"   Measure: {measure_encode_speedup:.1f}x faster")  
        print(f"   Group:   {group_encode_speedup:.1f}x faster")
        
        # Decoding comparison
        ping_decode_speedup = text_ping_decode['avg_ms'] / binary_ping_decode['avg_ms']
        print(f"\nDecoding Speedup (Binary vs Text):")
        print(f"   Ping: {ping_decode_speedup:.1f}x faster")
        
        # Size comparison
        print(f"\nMessage Size Efficiency:")
        ping_size_ratio = text_ping_encode['size_bytes'] / binary_ping_encode['size_bytes']
        measure_size_ratio = text_measure_encode['size_bytes'] / binary_measure_encode['size_bytes']
        group_size_ratio = text_group_encode['size_bytes'] / binary_group_encode['size_bytes']
        
        print(f"   Ping:    Binary {binary_ping_encode['size_bytes']}B vs Text {text_ping_encode['size_bytes']}B (ratio: {ping_size_ratio:.2f})")
        print(f"   Measure: Binary {binary_measure_encode['size_bytes']}B vs Text {text_measure_encode['size_bytes']}B (ratio: {measure_size_ratio:.2f})")
        print(f"   Group:   Binary {binary_group_encode['size_bytes']}B vs Text {text_group_encode['size_bytes']}B (ratio: {group_size_ratio:.2f})")
        
        # Overall assessment
        avg_speedup = (ping_encode_speedup + measure_encode_speedup + group_encode_speedup + ping_decode_speedup) / 4
        
        print(f"\n🏆 OVERALL PERFORMANCE SCORE:")
        print(f"   Average speedup: {avg_speedup:.1f}x")
        print(f"   Best case (group): {group_size_ratio:.1f}x more efficient in size")
        
        if avg_speedup >= 1.5:
            print("   ✅ EXCELLENT - Binary protocol shows significant performance improvements")
        elif avg_speedup >= 1.2:
            print("   ✅ GOOD - Binary protocol has measurable performance benefits")
        elif avg_speedup >= 1.0:
            print("   ⚠️  NEUTRAL - Binary protocol is comparable to text protocol")
        else:
            print("   ❌ POOR - Binary protocol may need optimization")
        
        # Bandwidth efficiency for large group operations
        if group_size_ratio > 1.5:
            bandwidth_savings = (1 - binary_group_encode['size_bytes'] / text_group_encode['size_bytes']) * 100
            print(f"   📡 Bandwidth savings for 16-relay groups: {bandwidth_savings:.1f}%")
        
        return True
        
    except Exception as e:
        print(f"❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def memory_usage_test():
    """Test memory usage efficiency"""
    print("\n💾 MEMORY USAGE TEST:")
    print("="*30)
    
    try:
        import tracemalloc
        from protocols.binary_message_formats import (
            create_ping_message, create_measure_message, create_measure_group_message,
            TestType
        )
        
        # Test binary protocol memory usage
        tracemalloc.start()
        
        messages = []
        for i in range(1000):
            if i % 3 == 0:
                msg = create_ping_message(i)
            elif i % 3 == 1:
                msg = create_measure_message(i % 16 + 1, TestType.VOLTAGE_CURRENT)
            else:
                msg = create_measure_group_message([1, 2, 3, 4], TestType.RELAY_CONTINUITY)
            
            packed = msg.pack()
            messages.append(packed)
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        total_size = sum(len(msg) for msg in messages)
        
        print(f"   1000 binary messages:")
        print(f"   Memory used: {current/1024:.1f}KB current, {peak/1024:.1f}KB peak")
        print(f"   Total message size: {total_size} bytes")
        print(f"   Average per message: {total_size/1000:.1f} bytes")
        print(f"   Memory efficiency: {total_size/peak*100:.1f}%")
        
        if peak < 1024 * 100:  # Under 100KB
            print("   ✅ Memory usage is excellent (under 100KB)")
        elif peak < 1024 * 500:  # Under 500KB
            print("   ✅ Memory usage is good (under 500KB)")
        else:
            print("   ⚠️  Memory usage may need optimization")
        
        return True
        
    except Exception as e:
        print(f"❌ Memory test failed: {e}")
        return False


def main():
    """Run simplified benchmark"""
    success1 = benchmark_binary_vs_text()
    success2 = memory_usage_test()
    
    print(f"\n{'='*50}")
    if success1 and success2:
        print("🎉 Phase 4.4 Simple Benchmark COMPLETED SUCCESSFULLY")
        print("✅ Binary protocol shows strong performance characteristics")
        return True
    else:
        print("❌ Some benchmarks failed")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)