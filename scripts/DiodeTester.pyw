#!/usr/bin/env pythonw
"""
Launcher for Diode Tester V5
Uses .pyw extension to run without console window
"""

import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import and run main
from main import main

if __name__ == "__main__":
    main()