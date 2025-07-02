# INA260 I2C Communication Issues During Relay Switching

## Problem Description
The INA260 current sensor loses I2C communication when relays are switched on, causing test failures. The sensor is detected during initialization but fails immediately when the first relay activates.

## Root Causes
1. **Electrical Noise (EMI)**: Relay coil switching generates electromagnetic interference that disrupts I2C signals
2. **Power Supply Instability**: Relay activation causes voltage dips or spikes affecting the INA260
3. **Ground Bounce**: Current surges through ground paths when relays switch
4. **Insufficient Settling Time**: Original 15ms delay may be too short for stable measurements

## Software Solutions Implemented

### 1. Increased Stabilization Delays
- Relay stabilization: 15ms → 50ms
- Inter-relay delay: 10ms → 20ms
- Post-relay-off delay: Added 5ms

### 2. I2C Retry Logic
- Added retry mechanism with up to 3 attempts per reading
- 5ms delay between retry attempts
- Automatic I2C recovery function that reinitializes the INA260

### 3. Graceful Degradation
- Continue with valid samples even if some fail
- Calculate averages based on successful readings only
- Better error reporting to host application

## Hardware Recommendations

### 1. Power Supply Filtering
```
+5V ----[100µF]----+----[0.1µF]---- INA260 VDD
                   |
                  GND
```
- Add 100µF electrolytic capacitor near INA260
- Add 0.1µF ceramic capacitor for high-frequency filtering

### 2. I2C Bus Improvements
- **Pull-up Resistors**: Ensure proper 4.7kΩ pull-ups on SDA and SCL
- **Bus Capacitance**: Keep I2C traces short (< 10cm if possible)
- **Twisted Pair**: Use twisted pair wiring for I2C if cables are long

### 3. Relay Circuit Isolation
```
Arduino Pin ----[1kΩ]---- Optocoupler ---- Relay Driver
                              |
                          Separate
                          Power Supply
```
- Use optocouplers to isolate relay switching circuits
- Separate power supply for relay coils
- Add flyback diodes across relay coils (1N4007 or similar)

### 4. Ground Layout
- Use star grounding topology
- Separate analog ground (INA260) from power ground (relays)
- Connect grounds at single point near power supply

### 5. Shielding
- Use shielded cable for I2C connections if > 10cm
- Keep relay wiring away from I2C traces
- Consider metal enclosure for EMI shielding

## Testing the Fix

1. **Upload the updated firmware** to the Arduino
2. **Monitor serial output** for I2C recovery messages
3. **Check error rates** - occasional recoveries are OK, constant failures indicate hardware issues
4. **Verify measurements** - ensure voltage/current readings are accurate after recovery

## Diagnostic Commands

Test single relay with verbose output:
```
TX:1
```

Test all relays:
```
TX:ALL
```

Check INA260 presence:
```
V
```

## Expected Behavior After Fix

1. **Normal Operation**: Most measurements succeed on first attempt
2. **Occasional Recovery**: 1-2 retries per test cycle is acceptable
3. **Rare Failures**: < 1% of tests should fail completely
4. **Accurate Readings**: Voltage/current values should be consistent

## If Problems Persist

1. **Check Wiring**:
   - Verify I2C connections are solid
   - Measure pull-up resistor values
   - Check for loose connections

2. **Power Supply**:
   - Measure 5V rail during relay switching
   - Should not drop below 4.75V
   - Add more bulk capacitance if needed

3. **EMI Reduction**:
   - Add ferrite beads on power lines
   - Use RC snubbers across relay contacts
   - Implement the optocoupler solution

4. **Alternative Solutions**:
   - Use I2C isolator chip (e.g., ISO1540)
   - Switch to SPI-based current sensor
   - Add dedicated microcontroller for relay control