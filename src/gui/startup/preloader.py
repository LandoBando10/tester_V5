"""
Background preloader for application initialization during splash screen
"""
import logging
import time
from pathlib import Path
from PySide6.QtCore import QThread, Signal, QObject
from typing import Dict, Any, Optional


class PreloadedComponents:
    """Container for preloaded components"""
    def __init__(self):
        self.sku_manager = None
        self.handlers = {}
        self.dialogs = {}
        self.imports_loaded = False
        self.ports_scanned = False
        self.port_info = {}
        self.load_errors = []
        # Fast startup connection
        self.arduino_controller = None
        self.arduino_port = None
        self.scale_controller = None
        self.scale_port = None
        self.remaining_ports_to_scan = []


class PreloaderThread(QThread):
    """Background thread to preload application components during splash video"""
    
    # Signals
    progress = Signal(str, int)  # message, percentage
    preload_complete = Signal(object)  # PreloadedComponents
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.components = PreloadedComponents()
        
    def run(self):
        """Preload all heavy components in background"""
        try:
            total_steps = 5
            current_step = 0
            
            # Step 1: Import heavy modules
            self.progress.emit("Loading modules...", int(current_step / total_steps * 100))
            self._preload_imports()
            current_step += 1
            
            # Step 2: Load SKU Manager and data
            self.progress.emit("Loading SKU configurations...", int(current_step / total_steps * 100))
            self._preload_sku_manager()
            current_step += 1
            
            # Step 3: Initialize handlers (without MainWindow)
            self.progress.emit("Initializing handlers...", int(current_step / total_steps * 100))
            self._preload_handlers()
            current_step += 1
            
            # Step 4: Scan serial ports
            self.progress.emit("Scanning hardware ports...", int(current_step / total_steps * 100))
            self._scan_serial_ports()
            current_step += 1
            
            # Step 5: Cache commonly used resources
            self.progress.emit("Caching resources...", int(current_step / total_steps * 100))
            self._cache_resources()
            current_step += 1
            
            self.progress.emit("Ready", 100)
            self.preload_complete.emit(self.components)
            
        except Exception as e:
            self.logger.error(f"Error during preloading: {e}")
            self.components.load_errors.append(str(e))
            self.preload_complete.emit(self.components)
    
    def _preload_imports(self):
        """Preload heavy imports to warm up Python's import cache"""
        try:
            self.logger.info("Preloading imports...")
            self.progress.emit("Loading core modules...", 10)
            
            # Import heavy modules with progress updates
            import src.gui.main_window
            self.progress.emit("Loading GUI components...", 20)
            
            import src.gui.handlers.offroad_handler
            import src.gui.handlers.smt_handler
            import src.gui.handlers.weight_handler
            self.progress.emit("Loading handlers...", 30)
            
            import src.gui.components.connection_dialog
            import src.gui.components.test_area
            import src.gui.components.top_controls
            import src.gui.components.menu_bar
            self.progress.emit("Loading hardware modules...", 40)
            
            import src.hardware.arduino_controller
            import src.hardware.serial_manager
            import src.core.offroad_test
            import src.core.smt_test
            import src.data.sku_manager
            
            self.components.imports_loaded = True
            self.logger.info("Imports preloaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error preloading imports: {e}")
            self.components.load_errors.append(f"Import error: {e}")
    
    def _preload_sku_manager(self):
        """Load SKU manager and all SKU data"""
        try:
            self.logger.info("Loading SKU manager...")
            self.progress.emit("Loading SKU configurations...", 50)
            
            from src.data.sku_manager import SKUManager
            
            # Create and load SKU manager
            start_time = time.time()
            self.components.sku_manager = SKUManager()
            load_time = (time.time() - start_time) * 1000
            
            sku_count = len(self.components.sku_manager.get_all_skus())
            self.logger.info(f"Loaded {sku_count} SKUs in {load_time:.0f}ms")
            self.progress.emit(f"Loaded {sku_count} SKUs", 60)
            
        except Exception as e:
            self.logger.error(f"Error loading SKU manager: {e}")
            self.components.load_errors.append(f"SKU loading error: {e}")
    
    def _preload_handlers(self):
        """Initialize handlers (without MainWindow reference)"""
        try:
            self.logger.info("Preloading handler modules...")
            
            # Just ensure the modules are imported
            # Actual handler instances will be created by MainWindow
            import src.gui.handlers.offroad_handler
            import src.gui.handlers.smt_handler
            import src.gui.handlers.weight_handler
            import src.gui.handlers.connection_handler
            
            self.logger.info("Handler modules preloaded")
            
        except Exception as e:
            self.logger.error(f"Error preloading handlers: {e}")
            self.components.load_errors.append(f"Handler loading error: {e}")
    
    def _scan_serial_ports(self):
        """Scan for available serial ports with immediate Arduino connection"""
        try:
            self.logger.info("Scanning serial ports with fast startup...")
            
            from src.hardware.serial_manager import SerialManager
            import json
            from pathlib import Path
            
            # Get available ports
            serial_manager = SerialManager()
            ports = serial_manager.get_available_ports()
            self.logger.info(f"Found {len(ports)} serial ports")
            
            # Load device cache to get last Arduino/Scale ports and known non-Arduino ports
            last_arduino_port = None
            last_scale_port = None
            known_non_arduino = set()
            devices = {}  # Store device cache for preserving types
            cache_file = Path("config") / ".device_cache.json"
            if cache_file.exists():
                try:
                    with open(cache_file, 'r') as f:
                        cache_data = json.load(f)
                        last_arduino_port = cache_data.get("last_arduino_port")
                        last_scale_port = cache_data.get("last_scale_port")
                        
                        # Get known non-Arduino ports to skip
                        devices = cache_data.get("devices", {})
                        for port, device_type in devices.items():
                            # Only skip truly unknown ports, not Arduino variants
                            if device_type == "Unknown":
                                known_non_arduino.add(port)
                        
                        # Prioritize last known ports
                        if last_arduino_port and last_arduino_port in ports:
                            ports.remove(last_arduino_port)
                            ports.insert(0, last_arduino_port)
                            self.logger.info(f"Trying last Arduino port first: {last_arduino_port}")
                        
                        if last_scale_port and last_scale_port in ports:
                            # Move scale port near front but after Arduino
                            if last_scale_port in ports:
                                ports.remove(last_scale_port)
                                ports.insert(1 if last_arduino_port else 0, last_scale_port)
                                self.logger.info(f"Trying last scale port: {last_scale_port}")
                except Exception as e:
                    self.logger.debug(f"Could not load device cache: {e}")
            
            # Sequential scan for Arduino and Scale with immediate connection
            arduino_found = False
            scale_found = False
            
            for port in ports:
                # Skip known non-Arduino ports for faster startup
                if port in known_non_arduino and port != last_arduino_port and port != last_scale_port:
                    self.logger.info(f"Skipping known non-Arduino port: {port}")
                    # Preserve the existing device type from cache
                    self.components.port_info[port] = devices.get(port, "Unknown")
                    continue
                
                # If we haven't found Arduino yet, try Arduino connection
                if not arduino_found:
                    result = self._probe_and_connect_arduino(port)
                    if result['connected']:
                        # Arduino found and connected!
                        arduino_found = True
                        self.components.arduino_controller = result['controller']
                        self.components.arduino_port = port
                        self.components.port_info[port] = result['device_type']
                        self.logger.info(f"Connected to {result['device_type']} on {port}")
                        continue  # Continue to look for scale
                    else:
                        # Not an Arduino or failed to connect
                        self.components.port_info[port] = result['device_type']
                        
                        # If it's a scale and we haven't found one yet, connect to it
                        if result['device_type'] == 'Scale' and not scale_found:
                            scale_result = self._probe_and_connect_scale(port)
                            if scale_result['connected']:
                                scale_found = True
                                self.components.scale_controller = scale_result['controller']
                                self.components.scale_port = port
                                self.logger.info(f"Connected to Scale on {port}")
                
                # If it's marked as scale from probe but not connected yet
                elif self.components.port_info.get(port) == 'Scale' and not scale_found:
                    scale_result = self._probe_and_connect_scale(port)
                    if scale_result['connected']:
                        scale_found = True
                        self.components.scale_controller = scale_result['controller']
                        self.components.scale_port = port
                        self.logger.info(f"Connected to Scale on {port}")
                
                # Stop early if we found both devices
                if arduino_found and scale_found:
                    self.logger.info("Both Arduino and Scale connected during fast startup")
                    remaining_ports = [p for p in ports if p not in [self.components.arduino_port, self.components.scale_port]]
                    self.components.remaining_ports_to_scan = remaining_ports
                    break
            
            # If no Arduino found, scan remaining ports normally
            if not arduino_found and ports:
                self.logger.info("No Arduino found during fast scan, scanning all ports...")
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    remaining_ports = [p for p in ports if p not in self.components.port_info]
                    future_to_port = {
                        executor.submit(self._probe_port, port): port 
                        for port in remaining_ports
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_port):
                        port = future_to_port[future]
                        try:
                            device_type = future.result()
                            self.components.port_info[port] = device_type
                        except Exception as e:
                            self.logger.debug(f"Error probing {port}: {e}")
                            self.components.port_info[port] = "Unknown"
            
            self.components.ports_scanned = True
            self.logger.info(f"Initial port scan complete: {self.components.port_info}")
            
        except Exception as e:
            self.logger.error(f"Error scanning ports: {e}")
            self.components.load_errors.append(f"Port scanning error: {e}")
    
    def _probe_and_connect_arduino(self, port: str) -> Dict[str, Any]:
        """Probe port and if Arduino, keep connection open"""
        result = {
            'connected': False,
            'controller': None,
            'device_type': 'Unknown'
        }
        
        try:
            from src.hardware.serial_manager import SerialManager
            from src.hardware.controller_factory import ArduinoControllerFactory
            
            # Try Arduino connection
            temp_serial = SerialManager(baud_rate=115200, timeout=0.05)
            
            if temp_serial.connect(port):
                try:
                    temp_serial.flush_buffers()
                    
                    # Try identification command - "I" works reliably
                    response = temp_serial.query("I", response_timeout=0.05)
                    
                    if response:
                        response_upper = response.upper()
                        # Determine Arduino type and mode
                        mode = None
                        if "SMT" in response_upper:
                            result['device_type'] = "SMT Arduino"
                            mode = "SMT"
                        elif "OFFROAD" in response_upper:
                            result['device_type'] = "Offroad Arduino"
                            mode = "Offroad"
                        elif "ARDUINO" in response_upper or "DIODE" in response_upper:
                            result['device_type'] = "Arduino"
                            # Default to Offroad mode if not specified
                            mode = "Offroad"
                        
                        if mode:
                            # Arduino detected - disconnect temp connection and create proper controller
                            temp_serial.disconnect()
                            
                            # Create appropriate controller
                            controller = ArduinoControllerFactory.create_controller(mode, baud_rate=115200)
                            
                            # Connect with full initialization
                            if controller.connect(port):
                                result['connected'] = True
                                result['controller'] = controller
                                self.logger.info(f"Successfully connected to {result['device_type']} on {port}")
                            else:
                                self.logger.warning(f"Failed to fully connect to {result['device_type']} on {port}")
                    else:
                        # No response - not an Arduino
                        temp_serial.disconnect()
                        
                except Exception as e:
                    self.logger.debug(f"Error during Arduino probe on {port}: {e}")
                    if temp_serial.is_connected():
                        temp_serial.disconnect()
            
            # If not connected as Arduino, check for scale
            if not result['connected'] and result['device_type'] == 'Unknown':
                temp_serial = SerialManager(baud_rate=9600, timeout=0.05)
                if temp_serial.connect(port):
                    try:
                        import time
                        time.sleep(0.05)
                        if temp_serial.connection.in_waiting > 0:
                            line = temp_serial.read_line(timeout=0.05)
                            if line and ('g' in line or 'GS' in line):
                                result['device_type'] = "Scale"
                    except Exception:
                        pass
                    finally:
                        temp_serial.disconnect()
        
        except Exception as e:
            self.logger.debug(f"Error probing/connecting on {port}: {e}")
        
        return result
    
    def _probe_and_connect_scale(self, port: str) -> Dict[str, Any]:
        """Probe port and if Scale, keep connection open"""
        result = {
            'connected': False,
            'controller': None,
            'device_type': 'Unknown'
        }
        
        try:
            from src.hardware.serial_manager import SerialManager
            from src.hardware.scale_controller import ScaleController
            
            # Try scale connection
            temp_serial = SerialManager(baud_rate=9600, timeout=0.05)
            
            if temp_serial.connect(port):
                try:
                    time.sleep(0.05)
                    if temp_serial.connection.in_waiting > 0:
                        line = temp_serial.read_line(timeout=0.05)
                        if line and ('g' in line or 'GS' in line):
                            result['device_type'] = "Scale"
                            # Scale detected - disconnect temp connection and create proper controller
                            temp_serial.disconnect()
                            
                            # Create scale controller
                            controller = ScaleController()
                            
                            # Connect with full initialization
                            if controller.connect(port, skip_comm_test=True):
                                result['connected'] = True
                                result['controller'] = controller
                                self.logger.info(f"Successfully connected to Scale on {port}")
                            else:
                                self.logger.warning(f"Failed to fully connect to Scale on {port}")
                    else:
                        temp_serial.disconnect()
                        
                except Exception as e:
                    self.logger.debug(f"Error during scale probe on {port}: {e}")
                    if temp_serial.is_connected():
                        temp_serial.disconnect()
        
        except Exception as e:
            self.logger.debug(f"Error probing/connecting scale on {port}: {e}")
        
        return result
    
    def _probe_port(self, port: str) -> str:
        """Fast port probing to identify device type"""
        device_type = "Unknown"
        
        try:
            from src.hardware.serial_manager import SerialManager
            
            # Try Arduino first
            temp_serial = SerialManager(baud_rate=115200, timeout=0.05)
            
            if temp_serial.connect(port):
                try:
                    temp_serial.flush_buffers()
                    
                    # Try identification command - "I" works reliably
                    response = temp_serial.query("I", response_timeout=0.05)
                    
                    if response:
                        response_upper = response.upper()
                        if "SMT" in response_upper:
                            device_type = "SMT Arduino"
                        elif "OFFROAD" in response_upper:
                            device_type = "Offroad Arduino"
                        elif "ARDUINO" in response_upper:
                            device_type = "Arduino"
                    
                except Exception:
                    pass
                finally:
                    temp_serial.disconnect()
            
            # If not Arduino, check for scale
            # Skip scale check if we already found an Arduino to save time
            if device_type == "Unknown":
                temp_serial = SerialManager(baud_rate=9600, timeout=0.05)
                if temp_serial.connect(port):
                    try:
                        import time
                        time.sleep(0.05)
                        if temp_serial.connection.in_waiting > 0:
                            line = temp_serial.read_line(timeout=0.05)
                            if line and ('g' in line or 'GS' in line):
                                device_type = "Scale"
                    except Exception:
                        pass
                    finally:
                        temp_serial.disconnect()
        
        except Exception as e:
            self.logger.debug(f"Port probe error on {port}: {e}")
        
        return device_type
    
    def _cache_resources(self):
        """Cache commonly used resources"""
        try:
            self.logger.info("Caching resources...")
            
            # Cache device info if available
            cache_file = Path("config") / ".device_cache.json"
            if self.components.ports_scanned and self.components.port_info:
                try:
                    import json
                    cache_data = {
                        "timestamp": time.time(),
                        "devices": self.components.port_info
                    }
                    
                    # Add last Arduino port if connected
                    if self.components.arduino_port:
                        cache_data["last_arduino_port"] = self.components.arduino_port
                    
                    # Add last Scale port if connected
                    if self.components.scale_port:
                        cache_data["last_scale_port"] = self.components.scale_port
                    
                    cache_file.parent.mkdir(exist_ok=True)
                    with open(cache_file, 'w') as f:
                        json.dump(cache_data, f, indent=2)
                    self.logger.info("Device cache updated")
                except Exception as e:
                    self.logger.debug(f"Could not update device cache: {e}")
            
        except Exception as e:
            self.logger.error(f"Error caching resources: {e}")