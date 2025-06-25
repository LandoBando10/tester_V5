# gui/components/config/program_config.py
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QComboBox, QCheckBox, QTextEdit, QLabel, QGroupBox, QFrame,
    QListWidget, QListWidgetItem, QPushButton, QFileDialog, QScrollArea, QDialog
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QFont

from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class ProgramConfigEditor(QWidget):
    """Widget for editing programming configuration"""
    
    data_changed = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config_data = {}
        self.setup_ui()
        self.apply_dark_style()
        logger.debug("ProgramConfigEditor initialized")
    
    def setup_ui(self):
        """Setup the user interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        header_label = QLabel("Programming Configuration")
        header_label.setFont(QFont("Arial", 14, QFont.Bold))
        header_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        layout.addWidget(header_label)
        
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(20)
        
        # Basic Configuration
        basic_group = QGroupBox("Basic Configuration")
        basic_layout = QFormLayout(basic_group)
        basic_layout.setSpacing(10)
        
        # Enabled checkbox
        self.enabled_checkbox = QCheckBox("Enable Programming")
        self.enabled_checkbox.stateChanged.connect(self.on_enabled_changed)
        basic_layout.addRow(self.enabled_checkbox)
        
        # Description
        self.description_edit = QLineEdit()
        self.description_edit.textChanged.connect(self.data_changed.emit)
        basic_layout.addRow("Description:", self.description_edit)
        
        content_layout.addWidget(basic_group)
        
        # Programmers Configuration
        self.programmers_group = QGroupBox("Programmers")
        programmers_layout = QVBoxLayout(self.programmers_group)
        
        # Programmer controls
        prog_controls_layout = QHBoxLayout()
        
        self.add_programmer_btn = QPushButton("Add Programmer")
        self.add_programmer_btn.clicked.connect(self.add_programmer)
        prog_controls_layout.addWidget(self.add_programmer_btn)
        
        self.remove_programmer_btn = QPushButton("Remove Programmer")
        self.remove_programmer_btn.clicked.connect(self.remove_programmer)
        prog_controls_layout.addWidget(self.remove_programmer_btn)
        
        prog_controls_layout.addStretch()
        programmers_layout.addLayout(prog_controls_layout)
        
        # Programmers list
        self.programmers_list = QListWidget()
        self.programmers_list.itemSelectionChanged.connect(self.on_programmer_selection_changed)
        programmers_layout.addWidget(self.programmers_list)
        
        # Programmer details
        self.programmer_details_frame = QFrame()
        prog_details_layout = QFormLayout(self.programmer_details_frame)
        
        self.prog_name_edit = QLineEdit()
        self.prog_name_edit.textChanged.connect(self.on_programmer_detail_changed)
        prog_details_layout.addRow("Programmer Name:", self.prog_name_edit)
        
        self.prog_type_combo = QComboBox()
        self.prog_type_combo.addItems(["STM8", "PIC"])
        self.prog_type_combo.currentTextChanged.connect(self.on_programmer_detail_changed)
        prog_details_layout.addRow("Type:", self.prog_type_combo)
        
        # Path selection
        path_layout = QHBoxLayout()
        self.prog_path_edit = QLineEdit()
        self.prog_path_edit.textChanged.connect(self.on_programmer_detail_changed)
        path_layout.addWidget(self.prog_path_edit)
        
        self.browse_path_btn = QPushButton("Browse...")
        self.browse_path_btn.clicked.connect(self.browse_programmer_path)
        path_layout.addWidget(self.browse_path_btn)
        
        prog_details_layout.addRow("Path:", path_layout)
        
        # Boards
        self.prog_boards_edit = QLineEdit()
        self.prog_boards_edit.setPlaceholderText("e.g., main_controller,led_driver_1")
        self.prog_boards_edit.textChanged.connect(self.on_programmer_detail_changed)
        prog_details_layout.addRow("Boards:", self.prog_boards_edit)
        
        programmers_layout.addWidget(self.programmer_details_frame)
        self.programmer_details_frame.hide()
        
        content_layout.addWidget(self.programmers_group)
        
        # Hex Files Configuration
        self.hex_files_group = QGroupBox("Hex Files")
        hex_layout = QVBoxLayout(self.hex_files_group)
        
        # Hex file controls
        hex_controls_layout = QHBoxLayout()
        
        self.add_hex_btn = QPushButton("Add Hex File")
        self.add_hex_btn.clicked.connect(self.add_hex_file)
        hex_controls_layout.addWidget(self.add_hex_btn)
        
        self.remove_hex_btn = QPushButton("Remove Hex File")
        self.remove_hex_btn.clicked.connect(self.remove_hex_file)
        hex_controls_layout.addWidget(self.remove_hex_btn)
        
        hex_controls_layout.addStretch()
        hex_layout.addLayout(hex_controls_layout)
        
        # Hex files list
        self.hex_files_list = QListWidget()
        self.hex_files_list.itemSelectionChanged.connect(self.on_hex_file_selection_changed)
        hex_layout.addWidget(self.hex_files_list)
        
        # Hex file details
        self.hex_details_frame = QFrame()
        hex_details_layout = QFormLayout(self.hex_details_frame)
        
        self.hex_board_edit = QLineEdit()
        self.hex_board_edit.textChanged.connect(self.on_hex_detail_changed)
        hex_details_layout.addRow("Board Name:", self.hex_board_edit)
        
        # Hex file path selection
        hex_path_layout = QHBoxLayout()
        self.hex_path_edit = QLineEdit()
        self.hex_path_edit.textChanged.connect(self.on_hex_detail_changed)
        hex_path_layout.addWidget(self.hex_path_edit)
        
        self.browse_hex_btn = QPushButton("Browse...")
        self.browse_hex_btn.clicked.connect(self.browse_hex_file)
        hex_path_layout.addWidget(self.browse_hex_btn)
        
        hex_details_layout.addRow("Hex File Path:", hex_path_layout)
        
        hex_layout.addWidget(self.hex_details_frame)
        self.hex_details_frame.hide()
        
        content_layout.addWidget(self.hex_files_group)
        
        # Programming Sequence
        sequence_group = QGroupBox("Programming Sequence")
        sequence_layout = QVBoxLayout(sequence_group)
        
        # Sequence controls
        seq_controls_layout = QHBoxLayout()
        
        self.add_sequence_btn = QPushButton("Add Sequence Step")
        self.add_sequence_btn.clicked.connect(self.add_sequence_step)
        seq_controls_layout.addWidget(self.add_sequence_btn)
        
        self.remove_sequence_btn = QPushButton("Remove Step")
        self.remove_sequence_btn.clicked.connect(self.remove_sequence_step)
        seq_controls_layout.addWidget(self.remove_sequence_btn)
        
        self.move_up_btn = QPushButton("Move Up")
        self.move_up_btn.clicked.connect(self.move_sequence_up)
        seq_controls_layout.addWidget(self.move_up_btn)
        
        self.move_down_btn = QPushButton("Move Down")
        self.move_down_btn.clicked.connect(self.move_sequence_down)
        seq_controls_layout.addWidget(self.move_down_btn)
        
        seq_controls_layout.addStretch()
        sequence_layout.addLayout(seq_controls_layout)
        
        # Sequence list
        self.sequence_list = QListWidget()
        self.sequence_list.itemSelectionChanged.connect(self.on_sequence_selection_changed)
        sequence_layout.addWidget(self.sequence_list)
        
        # Sequence details
        self.sequence_details_frame = QFrame()
        seq_details_layout = QFormLayout(self.sequence_details_frame)
        
        self.seq_board_edit = QLineEdit()
        self.seq_board_edit.textChanged.connect(self.on_sequence_detail_changed)
        seq_details_layout.addRow("Board:", self.seq_board_edit)
        
        self.seq_pre_commands_edit = QTextEdit()
        self.seq_pre_commands_edit.setMaximumHeight(80)
        self.seq_pre_commands_edit.setPlaceholderText("Enter pre-programming commands, one per line")
        self.seq_pre_commands_edit.textChanged.connect(self.on_sequence_detail_changed)
        seq_details_layout.addRow("Pre-Program Commands:", self.seq_pre_commands_edit)
        
        self.seq_post_commands_edit = QTextEdit()
        self.seq_post_commands_edit.setMaximumHeight(80)
        self.seq_post_commands_edit.setPlaceholderText("Enter post-programming commands, one per line")
        self.seq_post_commands_edit.textChanged.connect(self.on_sequence_detail_changed)
        seq_details_layout.addRow("Post-Program Commands:", self.seq_post_commands_edit)
        
        sequence_layout.addWidget(self.sequence_details_frame)
        self.sequence_details_frame.hide()
        
        content_layout.addWidget(sequence_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Initially disable all groups
        self.set_groups_enabled(False)
    
    def on_enabled_changed(self):
        """Handle enabled state change"""
        enabled = self.enabled_checkbox.isChecked()
        self.set_groups_enabled(enabled)
        self.data_changed.emit()
        logger.info(f"Programming enabled state changed to: {enabled}")
    
    def set_groups_enabled(self, enabled: bool):
        """Enable/disable configuration groups"""
        self.programmers_group.setEnabled(enabled)
        self.hex_files_group.setEnabled(enabled)
    
    def add_programmer(self):
        """Add a new programmer"""
        from PySide6.QtWidgets import QInputDialog
        
        name, ok = QInputDialog.getText(self, "Add Programmer", "Enter programmer name:")
        if ok and name:
            logger.info(f"Adding new programmer: {name}")
            item = QListWidgetItem(name)
            self.programmers_list.addItem(item)
            self.programmers_list.setCurrentItem(item)
            self.data_changed.emit()
    
    def remove_programmer(self):
        """Remove selected programmer"""
        current_item = self.programmers_list.currentItem()
        if current_item:
            programmer_name = current_item.text()
            logger.info(f"Removing programmer: {programmer_name}")
            row = self.programmers_list.row(current_item)
            self.programmers_list.takeItem(row)
            self.programmer_details_frame.hide()
            self.data_changed.emit()
    
    def on_programmer_selection_changed(self):
        """Handle programmer selection change"""
        current_item = self.programmers_list.currentItem()
        if current_item:
            programmer_name = current_item.text()
            logger.debug(f"Programmer selection changed to: {programmer_name}")
            self.load_programmer_details(programmer_name)
            self.programmer_details_frame.show()
        else:
            self.programmer_details_frame.hide()
    
    def load_programmer_details(self, programmer_name: str):
        """Load programmer details"""
        try:
            logger.debug(f"Loading details for programmer: {programmer_name}")
            programmers = self.config_data.get('programmers', {})
            programmer = programmers.get(programmer_name, {})
            
            self.prog_name_edit.setText(programmer_name)
            self.prog_type_combo.setCurrentText(programmer.get('type', 'STM8'))
            self.prog_path_edit.setText(programmer.get('path', ''))
            
            boards = programmer.get('boards', [])
            self.prog_boards_edit.setText(','.join(boards))
            logger.debug(f"Details loaded for programmer: {programmer_name}")
        except Exception as e:
            logger.error(f"Error loading programmer details for {programmer_name}: {e}", exc_info=True)
    
    def on_programmer_detail_changed(self):
        """Handle programmer detail changes"""
        current_item = self.programmers_list.currentItem()
        if current_item:
            # Update the item text if name changed
            new_name = self.prog_name_edit.text()
            logger.debug(f"Programmer detail changed for: {current_item.text()}, new name: {new_name}")
            if new_name != current_item.text():
                current_item.setText(new_name)
            
            self.data_changed.emit()
    
    def browse_programmer_path(self):
        """Browse for programmer executable"""
        logger.debug("Browsing for programmer executable path.")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Programmer Executable", "",
            "Executable files (*.exe);;All files (*.*)"
        )
        if file_path:
            self.prog_path_edit.setText(file_path)
            logger.info(f"Programmer executable path selected: {file_path}")
    
    def add_hex_file(self):
        """Add a new hex file"""
        from PySide6.QtWidgets import QInputDialog
        
        board_name, ok = QInputDialog.getText(self, "Add Hex File", "Enter board name:")
        if ok and board_name:
            logger.info(f"Adding new hex file for board: {board_name}")
            item = QListWidgetItem(board_name)
            self.hex_files_list.addItem(item)
            self.hex_files_list.setCurrentItem(item)
            self.data_changed.emit()
    
    def remove_hex_file(self):
        """Remove selected hex file"""
        current_item = self.hex_files_list.currentItem()
        if current_item:
            board_name = current_item.text()
            logger.info(f"Removing hex file for board: {board_name}")
            row = self.hex_files_list.row(current_item)
            self.hex_files_list.takeItem(row)
            self.hex_details_frame.hide()
            self.data_changed.emit()
    
    def on_hex_file_selection_changed(self):
        """Handle hex file selection change"""
        current_item = self.hex_files_list.currentItem()
        if current_item:
            board_name = current_item.text()
            logger.debug(f"Hex file selection changed to: {board_name}")
            self.load_hex_file_details(board_name)
            self.hex_details_frame.show()
        else:
            self.hex_details_frame.hide()
    
    def load_hex_file_details(self, board_name: str):
        """Load hex file details"""
        try:
            logger.debug(f"Loading details for hex file: {board_name}")
            hex_files = self.config_data.get('hex_files', {})
            hex_path = hex_files.get(board_name, '')
            
            self.hex_board_edit.setText(board_name)
            self.hex_path_edit.setText(hex_path)
            logger.debug(f"Details loaded for hex file: {board_name}")
        except Exception as e:
            logger.error(f"Error loading hex file details for {board_name}: {e}", exc_info=True)
    
    def on_hex_detail_changed(self):
        """Handle hex file detail changes"""
        current_item = self.hex_files_list.currentItem()
        if current_item:
            # Update the item text if board name changed
            new_name = self.hex_board_edit.text()
            logger.debug(f"Hex detail changed for: {current_item.text()}, new name: {new_name}")
            if new_name != current_item.text():
                current_item.setText(new_name)
            
            self.data_changed.emit()
    
    def browse_hex_file(self):
        """Browse for hex file"""
        logger.debug("Browsing for hex file path.")
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Hex File", "",
            "Hex files (*.hex);;All files (*.*)"
        )
        if file_path:
            self.hex_path_edit.setText(file_path)
            logger.info(f"Hex file path selected: {file_path}")
    
    def add_sequence_step(self):
        """Add a new sequence step"""
        from PySide6.QtWidgets import QInputDialog
        
        board_name, ok = QInputDialog.getText(self, "Add Sequence Step", "Enter board name:")
        if ok and board_name:
            logger.info(f"Adding new sequence step for board: {board_name}")
            step_num = self.sequence_list.count() + 1
            item = QListWidgetItem(f"{step_num}. {board_name}")
            self.sequence_list.addItem(item)
            self.sequence_list.setCurrentItem(item)
            self.data_changed.emit()
    
    def remove_sequence_step(self):
        """Remove selected sequence step"""
        current_item = self.sequence_list.currentItem()
        if current_item:
            logger.info(f"Removing sequence step: {current_item.text()}")
            row = self.sequence_list.row(current_item)
            self.sequence_list.takeItem(row)
            self.update_sequence_numbers()
            self.sequence_details_frame.hide()
            self.data_changed.emit()
    
    def move_sequence_up(self):
        """Move selected sequence step up"""
        current_row = self.sequence_list.currentRow()
        if current_row > 0:
            item = self.sequence_list.item(current_row)
            logger.info(f"Moving sequence step up: {item.text() if item else 'N/A'}")
            item = self.sequence_list.takeItem(current_row)
            self.sequence_list.insertItem(current_row - 1, item)
            self.sequence_list.setCurrentRow(current_row - 1)
            self.update_sequence_numbers()
            self.data_changed.emit()
    
    def move_sequence_down(self):
        """Move selected sequence step down"""
        current_row = self.sequence_list.currentRow()
        if current_row < self.sequence_list.count() - 1:
            item = self.sequence_list.item(current_row)
            logger.info(f"Moving sequence step down: {item.text() if item else 'N/A'}")
            item = self.sequence_list.takeItem(current_row)
            self.sequence_list.insertItem(current_row + 1, item)
            self.sequence_list.setCurrentRow(current_row + 1)
            self.update_sequence_numbers()
            self.data_changed.emit()
    
    def update_sequence_numbers(self):
        """Update sequence step numbers"""
        try:
            logger.debug("Updating sequence numbers.")
            for i in range(self.sequence_list.count()):
                item = self.sequence_list.item(i)
                if not item:
                    logger.warning(f"Item at index {i} is None during sequence number update.")
                    continue
                text = item.text()
                # Extract board name after the number and dot
                if '. ' in text:
                    board_name = text.split('. ', 1)[1]
                else:
                    board_name = text
                item.setText(f"{i + 1}. {board_name}")
            logger.debug("Sequence numbers updated.")
        except Exception as e:
            logger.error(f"Error updating sequence numbers: {e}", exc_info=True)
    
    def on_sequence_selection_changed(self):
        """Handle sequence selection change"""
        current_item = self.sequence_list.currentItem()
        if current_item:
            logger.debug(f"Sequence selection changed to: {current_item.text()}")
            self.load_sequence_details(current_item)
            self.sequence_details_frame.show()
        else:
            self.sequence_details_frame.hide()
    
    def load_sequence_details(self, item: QListWidgetItem):
        """Load sequence step details"""
        try:
            text = item.text()
            logger.debug(f"Loading details for sequence step: {text}")
            if '. ' in text:
                board_name = text.split('. ', 1)[1]
            else:
                board_name = text
            
            # Find sequence step in config data
            sequence = self.config_data.get('programming_sequence', [])
            current_row = self.sequence_list.row(item)
            
            if current_row < len(sequence):
                step = sequence[current_row]
                self.seq_board_edit.setText(step.get('board', board_name))
                
                pre_commands = step.get('pre_program_commands', [])
                self.seq_pre_commands_edit.setPlainText('\n'.join(pre_commands))
                
                post_commands = step.get('post_program_commands', [])
                self.seq_post_commands_edit.setPlainText('\n'.join(post_commands))
            else:
                self.seq_board_edit.setText(board_name)
                self.seq_pre_commands_edit.clear()
                self.seq_post_commands_edit.clear()
            logger.debug(f"Details loaded for sequence step: {text}")
        except (KeyError, IndexError, TypeError) as e:
            logger.error(f"Error loading sequence details for {item.text() if item else 'N/A'}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error loading sequence details for {item.text() if item else 'N/A'}: {e}", exc_info=True)
    
    def on_sequence_detail_changed(self):
        """Handle sequence detail changes"""
        current_item = self.sequence_list.currentItem()
        if current_item:
            # Update the item text if board name changed
            new_board = self.seq_board_edit.text()
            logger.debug(f"Sequence detail changed for: {current_item.text()}, new board name: {new_board}")
            current_row = self.sequence_list.row(current_item)
            current_item.setText(f"{current_row + 1}. {new_board}")
            
            self.data_changed.emit()
    
    def load_config_data(self, config_data: Dict[str, Any]):
        """Load configuration data into the interface"""
        try:
            logger.info("Loading program configuration data into UI.")
            self.config_data = config_data
            
            # Load basic configuration
            self.enabled_checkbox.setChecked(config_data.get('enabled', False))
            self.description_edit.setText(config_data.get('description', ''))
            
            # Load programmers
            self.programmers_list.clear()
            programmers = config_data.get('programmers', {})
            for programmer_name in programmers.keys():
                item = QListWidgetItem(programmer_name)
                self.programmers_list.addItem(item)
            
            # Load hex files
            self.hex_files_list.clear()
            hex_files = config_data.get('hex_files', {})
            for board_name in hex_files.keys():
                item = QListWidgetItem(board_name)
                self.hex_files_list.addItem(item)
            
            # Load programming sequence
            self.sequence_list.clear()
            sequence = config_data.get('programming_sequence', [])
            for i, step in enumerate(sequence):
                board_name = step.get('board', f'Board_{i+1}') # Defensive get
                if not isinstance(board_name, str): # Type check
                    logger.warning(f"Board name is not a string for step {i}: {board_name}. Using default.")
                    board_name = f'Board_{i+1}'
                item = QListWidgetItem(f"{i + 1}. {board_name}")
                self.sequence_list.addItem(item)
            
            # Set enabled state
            self.set_groups_enabled(self.enabled_checkbox.isChecked())
            logger.info("Program configuration data loaded successfully.")
        except (KeyError, TypeError, AttributeError) as e:
            logger.error(f"Error loading program configuration data into UI: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error loading program configuration data: {e}", exc_info=True)

    def get_config_data(self) -> Dict[str, Any]:
        """Get current configuration data"""
        try:
            logger.debug("Getting program configuration data from UI.")
            config = {
                'enabled': self.enabled_checkbox.isChecked(),
                'description': self.description_edit.text(),
                'programmers': {},
                'hex_files': {},
                'programming_sequence': []
            }
            
            # Get programmers
            programmers = {}
            for i in range(self.programmers_list.count()):
                item = self.programmers_list.item(i)
                if not item: continue # Skip if item is None
                programmer_name = item.text()
                # Temporarily load details to get all data, then restore original selection
                original_programmer_item = self.programmers_list.currentItem()
                self.programmers_list.setCurrentItem(item) # Trigger detail load if not already selected
                # self.load_programmer_details(programmer_name) # This might be redundant if selection triggers load

                programmers[programmer_name] = {
                    'type': self.prog_type_combo.currentText(), # Assuming details are loaded for current item
                    'path': self.prog_path_edit.text(),
                    'boards': [b.strip() for b in self.prog_boards_edit.text().split(',') if b.strip()]
                }
                if original_programmer_item: # Restore selection
                    self.programmers_list.setCurrentItem(original_programmer_item)


            config['programmers'] = programmers
            
            # Get hex files
            for i in range(self.hex_files_list.count()):
                item = self.hex_files_list.item(i)
                board_name = item.text()
                
                # Get path from current selection or existing data
                if self.hex_files_list.currentItem() == item:
                    hex_path = self.hex_path_edit.text()
                else:
                    hex_path = self.config_data.get('hex_files', {}).get(board_name, '')
                
                config['hex_files'][board_name] = hex_path
            
            # Get programming sequence
            sequence = []
            for i in range(self.sequence_list.count()):
                item = self.sequence_list.item(i)
                if not item: continue # Skip if item is None
                text = item.text()
                board_name = text.split('. ', 1)[1] if '. ' in text else text
                
                # Temporarily load details to get all data
                original_sequence_item = self.sequence_list.currentItem()
                self.sequence_list.setCurrentItem(item) # Trigger detail load
                # self.load_sequence_details(item) # Might be redundant

                sequence.append({
                    'board': self.seq_board_edit.text(), # Assuming details are loaded
                    'pre_program_commands': [cmd.strip() for cmd in self.seq_pre_commands_edit.toPlainText().split('\n') if cmd.strip()],
                    'post_program_commands': [cmd.strip() for cmd in self.seq_post_commands_edit.toPlainText().split('\n') if cmd.strip()]
                })
                if original_sequence_item: # Restore selection
                    self.sequence_list.setCurrentItem(original_sequence_item)

            config['programming_sequence'] = sequence
            logger.debug("Program configuration data retrieved successfully.")
            return config
        except Exception as e:
            logger.error(f"Error getting program configuration data from UI: {e}", exc_info=True)
            return {} # Return empty dict on error to prevent further issues
    
    def apply_dark_style(self):
        """Apply dark theme styling"""
        self.setStyleSheet("""
            QWidget {
                background-color: #333333;
                color: white;
            }
            
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                background-color: #3a3a3a;
            }
            
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #4a90a4;
                font-size: 12px;
            }
            
            QLineEdit, QComboBox, QTextEdit {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 11px;
            }
            
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #4a90a4;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                border: 1px solid #666666;
                border-radius: 2px;
                background-color: #555555;
            }
            
            QComboBox QAbstractItemView {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                selection-background-color: #4a90a4;
                color: white;
            }
            
            QListWidget {
                background-color: #2b2b2b;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 5px;
                min-height: 100px;
            }
            
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #444444;
            }
            
            QListWidget::item:selected {
                background-color: #4a90a4;
            }
            
            QListWidget::item:hover {
                background-color: #404040;
            }
            
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 11px;
                min-width: 80px;
            }
            
            QPushButton:hover {
                background-color: #555555;
            }
            
            QPushButton:pressed {
                background-color: #333333;
            }
            
            QCheckBox {
                spacing: 5px;
            }
            
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border: 1px solid #666666;
                border-radius: 3px;
            }
            
            QCheckBox::indicator:checked {
                background-color: #4a90a4;
                border: 1px solid #4a90a4;
            }
            
            QCheckBox::indicator:unchecked:hover {
                border: 1px solid #777777;
            }
            
            QScrollArea {
                border: none;
            }
            
            QScrollBar:vertical {
                border: 1px solid #2b2b2b;
                background: #2b2b2b;
                width: 15px;
                margin: 15px 0 15px 0;
                border-radius: 0px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #4a90a4; /* Accent color for handle */
                min-height: 30px;
                border-radius: 7px;
            }
            
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                border: none;
                background: none;
            }
            
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                background: none;
            }
            
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)


class ProgrammingConfigurationDialog(QDialog):
    """Dialog for managing programming configurations"""
    config_saved = Signal(str) # Emit SKU when saved

    def __init__(self, sku_manager, parent=None):
        super().__init__(parent)
        self.sku_manager = sku_manager
        self.current_sku = None
        self.setWindowTitle("Programming Configuration Management")
        self.setMinimumSize(800, 700)
        self.setModal(True)  # Make it modal
        self.setup_ui()
        self.load_sku_list()
        self.apply_dark_style_to_dialog()
        logger.debug("ProgrammingConfigurationDialog initialized")

    def setup_ui(self):
        """Setup the user interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # Header
        header_label = QLabel("Manage Programming Configurations")
        header_label.setFont(QFont("Arial", 16, QFont.Bold))
        header_label.setStyleSheet("color: #ffffff; margin-bottom: 10px;")
        main_layout.addWidget(header_label)

        # SKU selection and management
        sku_management_layout = QHBoxLayout()
        
        self.sku_combo = QComboBox()
        self.sku_combo.setPlaceholderText("Select or Create SKU")
        self.sku_combo.setEditable(True)
        self.sku_combo.currentTextChanged.connect(self.on_sku_selected)
        sku_management_layout.addWidget(self.sku_combo, 1)

        self.load_button = QPushButton("Load SKU")
        self.load_button.clicked.connect(self.load_selected_sku_config)
        sku_management_layout.addWidget(self.load_button)
        
        self.save_button = QPushButton("Save SKU Config")
        self.save_button.clicked.connect(self.save_current_sku_config)
        self.save_button.setEnabled(False) # Enabled when an SKU is loaded/created
        sku_management_layout.addWidget(self.save_button)
        
        self.delete_button = QPushButton("Delete SKU")
        self.delete_button.clicked.connect(self.delete_selected_sku)
        self.delete_button.setEnabled(False) # Enabled when an SKU is selected
        sku_management_layout.addWidget(self.delete_button)

        main_layout.addLayout(sku_management_layout)
          # Editor widget
        self.editor = ProgramConfigEditor(self)
        self.editor.data_changed.connect(self.on_editor_data_changed)
        main_layout.addWidget(self.editor, 1)
        
        # Dialog buttons with keyboard shortcuts
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)
        self.ok_button.setShortcut("Ctrl+Return")
        button_layout.addWidget(self.ok_button)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setShortcut("Escape")
        button_layout.addWidget(self.cancel_button)
        
        main_layout.addLayout(button_layout)

    def load_sku_list(self):
        """Load SKUs into the combo box"""
        try:
            logger.debug("Loading SKU list for programming configuration.")
            self.sku_combo.blockSignals(True)
            self.sku_combo.clear()
            # Assuming sku_manager has a method to get all SKUs with programming configs
            # or all SKUs if we are creating new configs for any.
            # For now, let's assume it can list all SKUs that *might* have a config.
            all_skus = self.sku_manager.get_all_skus() # This should be available from SkuManager
            if all_skus:
                self.sku_combo.addItems(all_skus)
            self.sku_combo.setCurrentIndex(-1) # No selection initially
            self.sku_combo.blockSignals(False)
            logger.debug(f"SKU list loaded: {all_skus}")
        except Exception as e:
            logger.error(f"Error loading SKU list: {e}", exc_info=True)
            # Optionally, show an error message to the user via QMessageBox

    def on_sku_selected(self, sku: str):
        """Handle SKU selection or creation"""
        try:
            self.current_sku = sku.strip()
            logger.info(f"SKU selected/entered: {self.current_sku}")
            if self.current_sku:
                # Check if this SKU exists in the SkuManager's known list
                # This logic might need adjustment based on how sku_manager handles SKUs
                # For now, assume any text can be a potential new SKU
                self.load_button.setEnabled(True) 
                self.delete_button.setEnabled(self.sku_manager.has_programming_config(self.current_sku)) # Enable delete if config exists
                self.save_button.setEnabled(False) # Disable save until data is loaded or changed
                self.editor.set_groups_enabled(False) # Disable editor until loaded
            else:
                self.load_button.setEnabled(False)
                self.delete_button.setEnabled(False)
                self.save_button.setEnabled(False)
                self.editor.load_config_data({}) # Clear editor
                self.editor.set_groups_enabled(False)
        except Exception as e:
            logger.error(f"Error in on_sku_selected for SKU '{sku}': {e}", exc_info=True)

    def load_selected_sku_config(self):
        """Load configuration for the selected SKU"""
        if not self.current_sku:
            logger.warning("Load SKU config called with no current SKU selected.")
            # QMessageBox.warning(self, "Warning", "No SKU selected to load.")
            return
        try:
            logger.info(f"Loading programming configuration for SKU: {self.current_sku}")
            # Assume sku_manager has a method to get programming config
            config_data = self.sku_manager.get_programming_config(self.current_sku)
            if config_data:
                self.editor.load_config_data(config_data)
                logger.info(f"Configuration loaded for SKU: {self.current_sku}")
            else:
                logger.info(f"No existing programming configuration for SKU: {self.current_sku}. Initializing new.")
                self.editor.load_config_data({}) # Load empty for new config
            self.editor.set_groups_enabled(True) # Enable editor after loading
            self.save_button.setEnabled(False) # Disable save until changes are made
            self.delete_button.setEnabled(self.sku_manager.has_programming_config(self.current_sku))
        except Exception as e:
            logger.error(f"Error loading programming config for SKU {self.current_sku}: {e}", exc_info=True)
            # QMessageBox.critical(self, "Error", f"Could not load configuration for {self.current_sku}: {e}")
            self.editor.load_config_data({})
            self.editor.set_groups_enabled(False)

    def save_current_sku_config(self):
        """Save configuration for the current SKU"""
        if not self.current_sku:
            logger.warning("Save SKU config called with no current SKU.")
            # QMessageBox.warning(self, "Warning", "No SKU specified to save configuration.")
            return
        try:
            logger.info(f"Saving programming configuration for SKU: {self.current_sku}")
            config_data = self.editor.get_config_data()
            # Assume sku_manager has a method to save programming config
            self.sku_manager.save_programming_config(self.current_sku, config_data)
            logger.info(f"Programming configuration saved for SKU: {self.current_sku}")
            # QMessageBox.information(self, "Success", f"Configuration for {self.current_sku} saved.")
            self.config_saved.emit(self.current_sku)
            self.save_button.setEnabled(False) # Disable after saving
            self.delete_button.setEnabled(True) # Config now exists
            # Refresh SKU list if it was a new SKU
            if self.sku_combo.findText(self.current_sku) == -1:
                self.load_sku_list()
                self.sku_combo.setCurrentText(self.current_sku)
        except Exception as e:
            logger.error(f"Error saving programming config for SKU {self.current_sku}: {e}", exc_info=True)
            # QMessageBox.critical(self, "Error", f"Could not save configuration for {self.current_sku}: {e}")

    def delete_selected_sku(self):
        """Delete the programming configuration for the selected SKU"""
        if not self.current_sku:
            logger.warning("Delete SKU config called with no current SKU selected.")
            return
        
        try:
            logger.info(f"Attempting to delete programming configuration for SKU: {self.current_sku}")
            # Assume sku_manager has a method to delete programming config
            self.sku_manager.delete_programming_config(self.current_sku)
            logger.info(f"Programming configuration deleted for SKU: {self.current_sku}")
            
            self.editor.load_config_data({}) # Clear editor
            self.editor.set_groups_enabled(False)
            self.current_sku = None
            self.sku_combo.setCurrentIndex(-1) # Clear selection
            self.load_sku_list() # Refresh list
            self.save_button.setEnabled(False)
            self.delete_button.setEnabled(False)

        except Exception as e:
            logger.error(f"Error deleting programming config for SKU {self.current_sku}: {e}", exc_info=True)

    def on_editor_data_changed(self):
        """Enable save button when editor data changes"""
        logger.debug("Editor data changed, enabling save button.")
        self.save_button.setEnabled(True)

    def apply_dark_style_to_dialog(self):
        """Apply dark theme styling to the dialog itself and specific children"""
        self.setStyleSheet("""
            QWidget { /* Base for the dialog */
                background-color: #2b2b2b;
                color: white;
            }
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 11px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
            QPushButton:disabled {
                background-color: #3a3a3a;
                color: #777777;
            }
            QComboBox {
                background-color: #333333;
                border: 1px solid #555555;
                border-radius: 4px;
                padding: 6px;
                color: white;
                font-size: 11px;
            }
            QComboBox:editable {
                background: #333333; /* Ensure editable part matches */
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                width: 10px;
                height: 10px;
                border: 1px solid #666666;
                border-radius: 2px;
                background-color: #555555;
            }
            QComboBox QAbstractItemView { /* Dropdown list style */
                background-color: #333333;
                border: 1px solid #555555;
                selection-background-color: #4a90a4;
                color: white;
            }
            QLabel {
                color: #e0e0e0; /* Lighter color for labels */
                font-size: 11px;
            }
        """)
        # Ensure editor also gets its specific dark style if not inherited
        self.editor.apply_dark_style() 

    def closeEvent(self, event):
        """Handle close event"""
        # Check if there are unsaved changes
        if self.save_button.isEnabled():
            from PySide6.QtWidgets import QMessageBox
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to save before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
                QMessageBox.Save
            )
            
            if reply == QMessageBox.Save:
                self.save_current_sku_config()
                event.accept()
            elif reply == QMessageBox.Discard:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

# Example Usage (for testing purposes)
if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    # Mock SkuManager for testing
    class MockSkuManager:
        def __init__(self):
            self.configs = {}
            self.skus = ["SKU1000", "SKU2000_PROG", "SKU3000"]
            self.configs["SKU2000_PROG"] = {
                "enabled": True,
                "description": "Test programming config for SKU2000",
                "programmers": {
                    "STM32_Programmer": {
                        "type": "STM8", # Example, should be STM32 if name is STM32
                        "path": "C:/path/to/stm32programmer.exe",
                        "boards": ["main_board"]
                    }
                },
                "hex_files": {
                    "main_board": "C:/path/to/firmware.hex"
                },
                "programming_sequence": [
                    {
                        "board": "main_board",
                        "pre_program_commands": ["power_on_board"],
                        "post_program_commands": ["verify_firmware", "power_off_board"]
                    }
                ]
            }

        def get_all_skus(self):
            return self.skus

        def get_programming_config(self, sku):
            return self.configs.get(sku)

        def save_programming_config(self, sku, config_data):
            self.configs[sku] = config_data
            if sku not in self.skus:
                self.skus.append(sku)
            print(f"Saved config for {sku}: {config_data}")

        def delete_programming_config(self, sku):
            if sku in self.configs:
                del self.configs[sku]
            # if sku in self.skus: # Don't remove from main SKU list, just its config
            #     self.skus.remove(sku) 
            print(f"Deleted config for {sku}")
            return True
        
        def has_programming_config(self, sku):
            return sku in self.configs

    # Configure basic logging for testing
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    app = QApplication(sys.argv)
    
    # Create and show the dialog
    sku_manager_mock = MockSkuManager()
    dialog = ProgrammingConfigurationDialog(sku_manager=sku_manager_mock)
    dialog.show()
    
    sys.exit(app.exec())
