# gui/handlers/connection_handler.py
import logging
from PySide6.QtCore import QObject

from src.utils.thread_cleanup import ThreadCleanupMixin


class ConnectionHandler(QObject, ThreadCleanupMixin):
    """Handles connection status management and updates"""
    
    def __init__(self, main_window):
        QObject.__init__(self)
        ThreadCleanupMixin.__init__(self)
        self.main_window = main_window
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def setup_connections(self):
        """Setup signal connections for connection management"""
        self.logger.debug("Setting up connections for ConnectionHandler.")
        # This could be expanded to handle automatic connection status updates
    
    def update_connection_status(self):
        """Update the connection status display across all UI components"""
        self.logger.debug("Attempting to update connection status.")
        try:
            # Get connection status from connection service
            status = self.main_window.connection_service.get_connection_status()
            self.logger.debug(f"Retrieved status from connection_dialog: {status}")
            
            # Check weight testing widget connection status if in weight mode
            weight_connected = False
            weight_port = None
            if (self.main_window.current_mode == "WeightChecking" and
                    hasattr(self.main_window.test_area, 'weight_test_widget') and
                    self.main_window.test_area.weight_test_widget):
                try:
                    weight_status = self.main_window.test_area.weight_test_widget.get_connection_status()
                    weight_connected = weight_status.get('connected', False)
                    weight_port = weight_status.get('port')
                    self.logger.debug(f"Weight widget status: connected={weight_connected}, port={weight_port}")
                except Exception as e_weight_status:
                    self.logger.warning(f"Could not get weight_test_widget status: {e_weight_status}", exc_info=True)
                    weight_connected = False
            
            connected = False
            connection_details = "Unknown"

            # For weight checking mode, use scale connection if available
            if self.main_window.current_mode == "WeightChecking":
                self.logger.debug("Updating status for WeightChecking mode.")
                # Check if scale is connected via connection dialog
                scale_connected_dialog = status.get('scale_connected', False)
                scale_port_dialog = status.get('scale_port')
                
                if scale_connected_dialog and scale_port_dialog:
                    self.logger.info(f"Scale connected via dialog on port {scale_port_dialog}.")
                    if (hasattr(self.main_window.test_area, 'weight_test_widget') and
                        self.main_window.test_area.weight_test_widget):
                        self.main_window.test_area.weight_test_widget.set_connection_status(True, scale_port_dialog)
                    connected = True
                    connection_details = f"Scale on {scale_port_dialog}"
                elif weight_connected: # Scale connected via weight widget itself
                    self.logger.info(f"Scale connected via WeightTestWidget on port {weight_port}.")
                    connected = True  
                    connection_details = f"Scale on {weight_port}" if weight_port else "Scale connected (Weight Widget)"
                else:
                    self.logger.info("Scale is not connected for WeightChecking mode.")
                    if (hasattr(self.main_window.test_area, 'weight_test_widget') and
                        self.main_window.test_area.weight_test_widget):
                        self.main_window.test_area.weight_test_widget.set_connection_status(False)
                    connected = False
                    connection_details = "Scale disconnected"
            else:
                self.logger.debug(f"Updating status for mode: {self.main_window.current_mode}.")
                # For other modes, use Arduino connection
                connected = status.get('arduino_connected', False)
                arduino_port = status.get('arduino_port')
                if connected:
                    # Check for firmware mismatch
                    if (hasattr(self.main_window, 'arduino_controller') and 
                        self.main_window.arduino_controller and 
                        self.main_window.arduino_controller.is_connected()):
                        firmware_type = getattr(self.main_window.arduino_controller, '_firmware_type', 'UNKNOWN')
                        if (self.main_window.current_mode in ["SMT", "Offroad"] and 
                            firmware_type != self.main_window.current_mode.upper() and 
                            firmware_type != "UNKNOWN"):
                            self.logger.warning(f"Firmware mismatch: {firmware_type} Arduino connected in {self.main_window.current_mode} mode")
                            connected = False
                            connection_details = f"Wrong firmware: {firmware_type}"
                        else:
                            self.logger.info(f"Arduino connected on port {arduino_port}.")
                            connection_details = f"Arduino on {arduino_port}" if arduino_port else "Arduino connected"
                    else:
                        self.logger.info(f"Arduino connected on port {arduino_port}.")
                        connection_details = f"Arduino on {arduino_port}" if arduino_port else "Arduino connected"
                else:
                    self.logger.info("Arduino is not connected.")
                    connection_details = "Disconnected"
            
            # Update main window connection status
            self.main_window.set_connection_status(connected)
            
            # Update status bar
            if connected:
                self.main_window.statusBar().showMessage(f"Connected: {connection_details}")
            else:
                self.main_window.statusBar().showMessage("Disconnected")
            self.logger.debug(f"Connection status update complete. Connected: {connected}, Details: {connection_details}")
                
        except AttributeError as e_attr:
            self.logger.error(f"AttributeError updating connection status, possibly main_window or its components not fully initialized: {e_attr}", exc_info=True)
        except Exception as e:
            self.logger.error(f"Error updating connection status: {e}", exc_info=True)
    
    def cleanup(self):
        """Cleanup connection handler with comprehensive resource management"""
        try:
            self.logger.info("Starting connection handler cleanup...")
            
            # Disconnect hardware through connection service
            if hasattr(self.main_window, 'connection_service'):
                if self.main_window.connection_service.is_arduino_connected():
                    self.logger.info("Disconnecting Arduino...")
                    self.main_window.connection_service.disconnect_arduino()
                if self.main_window.connection_service.is_scale_connected():
                    self.logger.info("Disconnecting scale...")
                    self.main_window.connection_service.disconnect_scale()
            else:
                self.logger.warning("main_window.connection_service not found during cleanup.")
            
            # Use resource manager for comprehensive cleanup
            self.cleanup_resources()
            
            self.logger.info("Connection handler cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during connection cleanup: {e}", exc_info=True)
