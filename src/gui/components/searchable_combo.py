# gui/components/searchable_combo.py
from PySide6.QtWidgets import QComboBox, QCompleter
from PySide6.QtCore import Qt, Signal, QStringListModel
import logging

logger = logging.getLogger(__name__)


class SearchableComboBox(QComboBox):
    """A QComboBox that's optimized for searching with keyboard input"""
    
    item_selected = Signal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Make it editable
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        
        # Store the full list of items
        self._all_items = []
        self._is_initializing = False
        self._custom_signals_blocked = False
        
        # Disable the default completer first
        self.setCompleter(None)
        
        # Create a custom completer
        self._completer = QCompleter()
        self._completer.setCaseSensitivity(Qt.CaseInsensitive)
        self._completer.setCompletionMode(QCompleter.PopupCompletion)
        
        # Try to set filter mode if available
        try:
            self._completer.setFilterMode(Qt.MatchContains)
        except:
            # Fallback for older Qt versions
            pass
            
        # Set the completer
        self.setCompleter(self._completer)
        
        # Connect signals
        self.currentTextChanged.connect(self._on_text_changed)
        
    def addItems(self, items):
        """Add items and update completer"""
        self._all_items = list(items)
        
        # Block signals to prevent auto-selection during population
        self.blockSignals(True)
        super().clear()
        super().addItems(items)
        self.blockSignals(False)
        
        # Update completer model
        self._completer.setModel(QStringListModel(self._all_items))
        
    def clear(self):
        """Clear items"""
        self._all_items = []
        super().clear()
        self._completer.setModel(QStringListModel([]))
        
    def focusInEvent(self, event):
        """Select all text when focused and show dropdown"""
        super().focusInEvent(event)
        self.lineEdit().selectAll()
        # Optionally show popup on focus
        # self.showPopup()
        
    def _on_text_changed(self, text):
        """Handle text changes"""
        # Skip during initialization or if custom signals are blocked
        if self._is_initializing or self._custom_signals_blocked:
            return
            
        # Only emit item_selected if the text is a valid item and not the placeholder
        if text in self._all_items and text != "-- Select SKU --":
            logger.debug(f"SearchableComboBox: Emitting item_selected for '{text}'")
            self.item_selected.emit(text)
        elif text == "-- Select SKU --":
            logger.debug("SearchableComboBox: Placeholder selected, not emitting signal")
    
    def blockCustomSignals(self, block):
        """Block or unblock custom signals (item_selected)"""
        self._custom_signals_blocked = block