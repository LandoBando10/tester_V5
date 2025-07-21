#!/usr/bin/env python3
"""
Console Installer for Diode Tester V5
Simple, no GUI, just gets the job done
"""

import sys
import subprocess
import os
from pathlib import Path
import time


def print_header():
    """Print installer header"""
    print("\n" + "="*60)
    print("       DIODE DYNAMICS - PRODUCTION TESTER V5")
    print("              CONSOLE INSTALLER")
    print("="*60 + "\n")


def check_python():
    """Check Python version"""
    print("[1/4] Checking Python version...")
    version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"      Found Python {version}")
    
    if sys.version_info < (3, 8):
        print(f"\n✗ ERROR: Python 3.8 or newer required (you have {version})")
        return False
    
    print("      ✓ Python version OK\n")
    return True


def install_packages():
    """Install required packages"""
    print("[2/4] Installing required packages...")
    
    packages = [
        ("PySide6", "GUI Framework"),
        ("pyserial", "Arduino Communication"),
        ("numpy", "Data Processing"),
        ("packaging", "Version Management"),
        ("pyqtgraph", "Live Graphs (Optional)")
    ]
    
    for package, description in packages:
        print(f"\n      Installing {package} ({description})...")
        
        # Check if already installed
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", package],
            capture_output=True
        )
        
        if result.returncode == 0:
            print(f"      ✓ {package} already installed")
            continue
        
        # Install package
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f"      ✓ {package} installed successfully")
        else:
            if package == "pyqtgraph":  # Optional
                print(f"      ⚠ {package} installation failed (optional)")
            else:
                print(f"      ✗ {package} installation failed!")
                print(f"      Error: {result.stderr}")
                return False
    
    print("\n      ✓ All required packages installed\n")
    return True


def create_shortcut():
    """Create desktop shortcut"""
    print("[3/4] Creating desktop shortcuts...")
    
    # Find the shortcut creator script
    current_dir = Path(__file__).parent
    shortcut_script = current_dir / "create_shortcuts.bat"
    
    # Fallback to old script if new one doesn't exist
    if not shortcut_script.exists():
        shortcut_script = current_dir / "create_professional_shortcut.bat"
    
    if not shortcut_script.exists():
        print("      ✗ Shortcut creator not found")
        print("      You can create a shortcut manually to main.py")
        return False
    
    # Run the shortcut creator silently
    # Need to use cmd.exe when running from WSL/Linux
    import platform
    if platform.system() == "Linux":
        # Running from WSL - use cmd.exe
        # Convert WSL path to Windows path
        wsl_path = str(shortcut_script)
        if wsl_path.startswith("/mnt/"):
            # Convert /mnt/c/... to C:\...
            windows_path = wsl_path.replace("/mnt/", "", 1)
            drive_letter = windows_path[0].upper()
            windows_path = drive_letter + ":" + windows_path[1:].replace("/", "\\")
        else:
            windows_path = wsl_path
        
        result = subprocess.run(
            ["cmd.exe", "/c", windows_path, "silent"],
            capture_output=True,
            text=True
        )
    else:
        # Running from Windows
        result = subprocess.run(
            [str(shortcut_script), "silent"],
            shell=True,
            capture_output=True,
            text=True
        )
    
    if result.returncode == 0:
        print("      ✓ Desktop shortcuts created")
        print("      - Main shortcut (no console window)")
        print("      - Debug shortcut (with console)\n")
        return True
    else:
        print("      ✗ Could not create shortcuts automatically")
        if result.stderr:
            print(f"      Error: {result.stderr.strip()}")
        if result.stdout:
            print(f"      Output: {result.stdout.strip()}")
        print("      You can create a shortcut manually to main.py\n")
        return False


def test_import():
    """Test if the application can be imported"""
    print("[4/4] Verifying installation...")
    
    try:
        # Add current directory to path
        sys.path.insert(0, str(Path(__file__).parent))
        
        # Try to import main modules
        print("      Testing imports...")
        from src.gui.main_window import MainWindow
        print("      ✓ GUI modules OK")
        
        from src.data.sku_manager import SKUManager
        print("      ✓ Data modules OK")
        
        from src.hardware.serial_manager import SerialManager
        print("      ✓ Hardware modules OK")
        
        print("\n      ✓ Installation verified successfully!\n")
        return True
        
    except ImportError as e:
        print(f"\n      ✗ Import test failed: {e}")
        print("      The application may not work correctly.\n")
        return False


def main():
    """Main installer function"""
    print_header()
    
    print("This installer will:")
    print("- Check Python version")
    print("- Install required packages")
    print("- Create a desktop shortcut")
    print("- Verify the installation")
    
    print("\nPress Enter to continue or Ctrl+C to cancel...")
    input()
    
    # Run installation steps
    success = True
    
    if not check_python():
        success = False
    
    if success and not install_packages():
        success = False
    
    create_shortcut()  # Try even if packages failed
    
    if success:
        test_import()  # Just for verification
    
    # Final message
    print("="*60)
    if success:
        print("✓ INSTALLATION COMPLETE!")
        print("\nYou can now:")
        print("1. Use the desktop shortcut 'Diode Tester' (no console)")
        print("2. Use 'Diode Tester (Debug)' if you need to see console output")
        print("3. Or run directly: python main.py")
    else:
        print("✗ INSTALLATION FAILED")
        print("\nPlease check the errors above and try again.")
        print("If problems persist, contact IT support.")
    
    print("="*60)
    print("\nPress Enter to exit...")
    input()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInstallation cancelled by user.")
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        print("Press Enter to exit...")
        input()