# SMT Button Press Thread Safety Fix

## Problem
When pressing the physical button to start an SMT test with programming enabled but no programming configuration:
- A dialog box was shown from the Arduino reading thread (background thread)
- Qt requires all GUI operations to happen on the main thread
- This caused the application to crash with threading errors

## Error Messages
```
QObject::setParent: Cannot set parent, new parent is in a different thread
QWidget::repaint: Recursive repaint detected
QBackingStore::endPaint() called with active painter
```

## Root Cause
The button press event comes from the Arduino reading thread. When the code tried to show a QMessageBox dialog directly from this thread, it violated Qt's thread safety rules.

## Solution Implemented
Modified `src/gui/handlers/smt_handler.py` to use Qt's signal/slot mechanism:

1. **Added a signal**: `button_pressed_signal = Signal()`
2. **Connected signal to handler**: In `__init__`, connected with `Qt.QueuedConnection` to ensure it runs on main thread
3. **Split button handling**: 
   - `handle_button_event()` - Receives event from Arduino thread, emits signal
   - `_handle_button_press_on_main_thread()` - Runs on main thread, safe for dialogs

## How It Works
1. Arduino reading thread detects button press
2. `handle_button_event()` emits `button_pressed_signal`
3. Qt queues the signal to be handled on the main thread
4. `_handle_button_press_on_main_thread()` runs safely on main thread
5. All GUI operations (including dialogs) now happen on the correct thread

## Testing
To test the fix:
1. Connect Arduino with SMT firmware
2. Select a SKU without programming configuration
3. Enable the "Programming" checkbox
4. Press the physical button
5. You should see the dialog asking to continue with power testing only
6. Click "Yes" - the test should proceed without crashing

## Files Modified
- `src/gui/handlers/smt_handler.py` - Added thread-safe button handling
