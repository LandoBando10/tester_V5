#!/usr/bin/env python3
"""
Test script to verify seamless transitions
"""

import sys
import subprocess
import time

def test_with_video():
    """Test transitions with video"""
    print("Testing transitions WITH video...")
    result = subprocess.run([sys.executable, "main.py", "--mode", "gui"], capture_output=False)
    return result.returncode == 0

def test_without_video():
    """Test transitions without video"""
    print("\nTesting transitions WITHOUT video...")
    result = subprocess.run([sys.executable, "main.py", "--mode", "gui", "--no-video"], capture_output=False)
    return result.returncode == 0

if __name__ == "__main__":
    print("Seamless Transition Test Suite")
    print("=" * 40)
    print("\nThis will test the transitions between:")
    print("1. Video → Splash → Mode Selector → Main Window")
    print("2. Static Splash → Mode Selector → Main Window")
    print("\nPlease observe the transitions for smoothness.")
    print("\nPress Enter to start tests...")
    input()
    
    # Run tests
    success = True
    
    # Test with video
    if not test_with_video():
        print("❌ Video transition test failed")
        success = False
    else:
        print("✅ Video transition test passed")
    
    time.sleep(2)
    
    # Test without video
    if not test_without_video():
        print("❌ No-video transition test failed")
        success = False
    else:
        print("✅ No-video transition test passed")
    
    if success:
        print("\n✅ All transition tests passed!")
    else:
        print("\n❌ Some tests failed. Check the transitions manually.")