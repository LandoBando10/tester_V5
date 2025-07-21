#!/usr/bin/env python3
"""Test if installer can run"""

import sys
import traceback

print("Testing installer prerequisites...")
print(f"Python version: {sys.version}")
print(f"Python path: {sys.executable}")

# Test imports
try:
    print("\n1. Testing PySide6 import...")
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    print("   ✓ PySide6 imported successfully")
except ImportError as e:
    print(f"   ✗ PySide6 import failed: {e}")
    sys.exit(1)

try:
    print("\n2. Testing project imports...")
    from pathlib import Path
    
    # Add project root to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    print(f"   Project root: {project_root}")
    
    # Try to import the splash screen
    from src.gui.startup import UnifiedSplashScreen
    print("   ✓ UnifiedSplashScreen imported successfully")
    
except Exception as e:
    print(f"   ✗ Project import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n3. Testing GUI creation...")
    app = QApplication(sys.argv)
    print("   ✓ QApplication created successfully")
    
    # Try to create splash screen
    splash = UnifiedSplashScreen()
    print("   ✓ Splash screen created successfully")
    
    # Don't actually show it, just test creation
    app.quit()
    
except Exception as e:
    print(f"   ✗ GUI creation failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✓ All tests passed! Installer should work.")
print("\nNow try running: python install_with_gui.py")