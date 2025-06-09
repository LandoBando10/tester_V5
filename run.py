#!/usr/bin/env python3
"""
Simple launcher for Diode Dynamics Tester V4
Just click play on this file in your IDE to launch the application!
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Launch the Tester V4 application with the correct Python environment"""
    
    # Get the directory where this script is located
    script_dir = Path(__file__).parent.absolute()
    
    # Change to the project directory
    os.chdir(script_dir)
    
    # Path to main.py
    main_py = script_dir / "main.py"
    
    # Use the current Python executable (works on both Windows and Unix)
    python_executable = sys.executable
    
    # Verify the main.py file exists
    if not main_py.exists():
        print(f"ERROR: main.py not found at {main_py}")
        sys.exit(1)
    
    print("🚀 Launching Diode Dynamics Tester V4...")
    print(f"📁 Working directory: {script_dir}")
    print(f"🐍 Using Python: {sys.executable}")
    print("=" * 50)
    
    try:
        # Launch the application
        # On Windows, we need to ensure proper path handling
        result = subprocess.run([sys.executable, str(main_py)], check=True, shell=False)
    except subprocess.CalledProcessError as e:
        print(f"❌ Application failed to start: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()