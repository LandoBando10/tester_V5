# Diode Dynamics Tester V5: Project Overview and Architecture

*Last Updated: December 28, 2025*
*Version: 5.0*

## 1. Primary Intent

The Diode Dynamics Tester V5 is a comprehensive production-line testing application designed to validate the functionality and quality of Diode Dynamics' LED lighting products. The system automates and standardizes testing processes across various product Stock Keeping Units (SKUs), ensuring products meet defined specifications before shipment. The platform emphasizes reliability, user-friendliness for operators, and configurability to accommodate different product types and testing requirements.

## 2. System Architecture

### 2.1 Modular Design Philosophy
The system follows a clean, modular architecture with clear separation of concerns:
- **Core Testing Engine**: Standardized test lifecycle with abstract base classes
- **Hardware Abstraction**: Consistent controller patterns for all hardware interfaces
- **Asynchronous Data Management**: Background loading with thread-safe operations
- **Component-Based GUI**: Modular UI components with proper business logic separation
- **Resource Management**: Comprehensive cleanup and error handling throughout

### 2.2 Core System Components

**Graphical User Interface (GUI)**: A PySide6-based modular interface with:
- Component-based architecture in `src/gui/components/`
- Business logic handlers in `src/gui/handlers/`
- Background workers in `src/gui/workers/` to prevent UI blocking
- Dark theme with touchscreen-friendly controls

**Test Execution Engine**: Python-based orchestration system in `src/core/`:
- `BaseTest`: Abstract foundation providing standardized test lifecycle
- `OffroadTest`: Comprehensive assembled product validation
- `SMTTest`: PCB-level fixture testing with programming capabilities
- `WeightTest`: Precision weight validation using scale integration

**Hardware Abstraction Layer**: Unified controller pattern in `src/hardware/`:
- `arduino_controller.py`: Sensor readings and test execution with callback support
- `smt_arduino_controller.py`: Simplified bed-of-nails fixture control (current architecture)
- `scale_controller.py`: Weight measurement with stability detection
- `serial_manager.py`: Thread-safe serial communication foundation

**Asynchronous Configuration Management**: Modern data handling in `src/data/`:
- `AsyncSKUManager`: Background loading with Qt signal integration
- Thread-safe data access with mutex protection
- Automatic retry mechanisms and fallback capabilities
- Real-time progress reporting for configuration loading

**Resource Management**: Comprehensive cleanup system:
- `ResourceMixin` pattern for hardware controllers
- Automatic resource cleanup on test completion or error
- Thread-safe resource allocation and deallocation

## 3. Testing Modes and Workflows

Detailed workflow documentation for each testing mode can be found in the `docs/workflows/` directory:
- [Offroad Testing Workflow](workflows/offroad_workflow_description.md)
- [SMT Testing Workflow](workflows/smt_workflow_description.md)
- [Weight Checking Workflow](workflows/weight_checking_workflow_description.md)

### 3.1 Offroad Mode
**Purpose**: Final assembly validation for complete "Offroad" products

**Workflow**:
1. Operator selects SKU from dynamically loaded list
2. Enables desired test types via intuitive checkboxes
3. System establishes Arduino connection with automatic retry
4. Standardized test sequence execution:
   - Optional pressure decay testing (5 seconds)
   - Mainbeam validation (current, LUX, color)
   - Configurable backlight testing (single, dual, RGBW cycling)
5. Real-time data display with pass/fail indicators
6. Comprehensive results reporting and logging

**Enhanced Features**:
- Intelligent sensor sampling with configurable timing
- Resource-managed hardware connections
- Real-time callback system for live data updates
- Robust error handling with graceful recovery

### 3.2 SMT (Surface Mount Technology) Mode
**Purpose**: PCB testing and programming within bed-of-nails fixtures

**Current Simplified Architecture**:
The SMT system has been streamlined to focus on core functionality with a clean, maintainable design:

**Workflow**:
1. SKU selection with automatic programming configuration validation
2. Test selection (Programming and/or Power validation)
3. Simple hardware setup (SMT Arduino controller)
4. Automated test execution:
   - Individual relay testing with current measurements
   - Programming support via external tools
5. Real-time results display with board-specific status

**Simplified Features**:
- Text-based Arduino communication protocol
- Individual relay testing (eliminates buffer overflow risks)
- Clean 5-component architecture for maintainability
- Command throttling for reliable serial communication
- Thread-safe GUI updates via Qt signals

### 3.3 Weight Checking Mode
**Purpose**: Precision weight validation against specifications

**Workflow**:
1. SKU selection with automatic weight parameter loading
2. Scale connection establishment with automatic detection
3. Automated testing workflow:
   - Real-time weight monitoring with stability detection
   - Automatic part detection via configurable thresholds
   - Instant pass/fail evaluation against SKU specifications
4. Tare functionality and measurement optimization

**Key Features**:
- High-precision scale integration via serial communication
- Configurable stability detection algorithms
- Auto-trigger capabilities for seamless operator workflow
- Real-time weight display with threshold visualization

## 4. Configuration Management Evolution

### 4.1 Modern SKU Management
The system uses an organized directory structure for SKU configurations:

**SKU Directory Organization**:
- `config/skus/offroad/` - Offroad product configurations
- `config/skus/smt/` - SMT panel configurations
- `config/skus/weight/` - Weight specification files

Each SKU file is a self-contained JSON configuration with:
- Complete test parameters per SKU
- Mode-specific configurations embedded
- Template-based backlight configurations
- Simplified maintenance and version control



### 4.2 Configuration Structure
Each SKU configuration includes mode-specific test parameters. Below is an example of a SKU that has all 3 tests enabled:
```json
{
  "sku": "DD5002",
  "description": "Product Gamma - C2 Sport Economy",
  "pod_type": "C2", 
  "power_level": "Sport",
  "available_modes": ["Offroad", "SMT", "WeightChecking"],
  
  "offroad_testing": {
    "test_sequence": [
      {
        "name": "mainbeam",
        "relay": "main",
        "duration_ms": 500,
        "measurements": ["current", "voltage", "lux", "color"],
        "limits": {
          "current_A": {"min": 0.6, "max": 0.9},
          "lux": {"min": 1500, "max": 1900},
          "color_x": {"center": 0.460, "tolerance": 0.020},
          "color_y": {"center": 0.420, "tolerance": 0.020}
        }
      },
      {
        "name": "backlight_rgbw",
        "relay": "backlight_1",
        "duration_ms": 6400,
        "type": "rgbw_cycling",
        "rgbw_config": {
          "cycle_interval_ms": 800,
          "total_cycles": 8,
          "stabilization_ms": 150,
          "sample_points_ms": [200, 350, 450],
          "colors_to_test": [
            {"name": "red", "target_x": 0.650, "target_y": 0.330, "tolerance": 0.020},
            {"name": "green", "target_x": 0.300, "target_y": 0.600, "tolerance": 0.020},
            {"name": "blue", "target_x": 0.150, "target_y": 0.060, "tolerance": 0.020},
            {"name": "white", "target_x": 0.313, "target_y": 0.329, "tolerance": 0.020}
          ]
        },
        "measurements": ["current", "voltage", "color"],
        "limits": {
          "current_A": {"min": 0.04, "max": 0.12}
        }
      }
    ]
  },
  
  "smt_testing": {
    "panel_layout": {
      "rows": 3,
      "columns": 2,
      "total_boards": 6,
      "board_positions": {
        "1": {"row": 1, "col": 1, "name": "Bottom Left"},
        "2": {"row": 1, "col": 2, "name": "Bottom Right"},
        "3": {"row": 2, "col": 1, "name": "Middle Left"},
        "4": {"row": 2, "col": 2, "name": "Middle Right"},
        "5": {"row": 3, "col": 1, "name": "Top Left"},
        "6": {"row": 3, "col": 2, "name": "Top Right"}
      }
    },
    "relay_mapping": {
      "1": {"board": 1, "function": "mainbeam"},
      "2": {"board": 2, "function": "mainbeam"},
      "3": {"board": 3, "function": "mainbeam"},
      "4": {"board": 4, "function": "mainbeam"},
      "5": {"board": 5, "function": "mainbeam"},
      "6": {"board": 6, "function": "mainbeam"},
      "7": null,
      "8": null
    },
    "test_sequence": [
      {
        "name": "mainbeam_test",
        "description": "Test mainbeam current on all boards",
        "function": "mainbeam",
        "test_all_boards": true,
        "limits": {
          "current_A": {"min": 0.55, "max": 0.85},
          "voltage_V": {"min": 11.5, "max": 12.5}
        }
      }
    ],
    "programming": {
      "enabled": true,
      "programmer_path": "C:/Program Files (x86)/STMicroelectronics/st_toolset/stvp/STVP_CmdLine.exe",
      "boards": {
        "1": {"hex_file": "firmware/SSC5_V0.606.hex", "device": "STM8S001J3"},
        "2": {"hex_file": "firmware/SSC5_V0.606.hex", "device": "STM8S001J3"},
        "3": {"hex_file": "firmware/SSC5_V0.606.hex", "device": "STM8S001J3"},
        "4": {"hex_file": "firmware/SSC5_V0.606.hex", "device": "STM8S001J3"},
        "5": {"hex_file": "firmware/SSC5_V0.606.hex", "device": "STM8S001J3"},
        "6": {"hex_file": "firmware/SSC5_V0.606.hex", "device": "STM8S001J3"}
      }
    }
  },
  
  "weight_testing": {
    "limits": {
      "weight_g": {"min": 180.0, "max": 185.0}
    },
    "tare_g": 0.0
  }
}
```

## 5. Hardware Integration

### 5.1 Unified Controller Pattern
All hardware interfaces follow a consistent pattern:
- Standardized initialization and cleanup procedures
- Thread-safe communication with automatic retry logic
- Resource management through `ResourceMixin`
- Consistent callback systems for real-time data

### 5.2 Arduino Communication
- Robust serial protocol with message parsing
- Sensor management for INA260 (current/voltage/power), VEML7700 (LUX), pressure, and color sensors
- Real-time data streaming with configurable sampling rates
- Hardware-specific command sets with error handling

### 5.3 Scale Integration
- Multi-vendor scale support via serial communication
- Advanced filtering for measurement stability
- Configurable detection thresholds and timing parameters
- Integration with SKU-specific weight specifications

## 6. Enhanced System Features

### 6.1 Asynchronous Architecture
- Non-blocking UI operations through background workers
- Thread-safe data access with mutex protection
- Real-time progress reporting for long-running operations
- Graceful error handling with user-friendly feedback

### 6.2 Resource Management
- Automatic hardware resource cleanup
- Connection pooling and management
- Memory-efficient configuration loading
- Comprehensive error recovery mechanisms

### 6.3 Data Logging and Results
- Structured logging with configurable verbosity levels
- Test results with detailed measurement tracking
- Comprehensive error logging with stack traces
- Traceability support for quality control requirements

### 6.4 GUI Enhancements
- Modular component architecture for maintainability
- Responsive design with progress indicators
- Real-time data visualization capabilities
- Consistent dark theme with high contrast for production environments

### 6.5 Development Support
- CLAUDE.md configuration file for development workflow
- Comprehensive testing commands and linting setup
- Arduino firmware references: `SMT_Simple_Tester.ino` and `Offroad_Assembly_Tester.ino`

## 7. Development Architecture

### 7.1 Code Organization
```
src/
├── core/           # Test execution engines
├── data/           # Asynchronous data management
├── gui/            # Modular UI components
├── hardware/       # Hardware abstraction layer
└── utils/          # Utility functions and helpers
```

### 7.2 Design Principles
- **Simple and Elegant**: Readable code with clear intent
- **Modular Architecture**: Loosely coupled components
- **Resource Management**: Comprehensive cleanup and error handling
- **Asynchronous Operations**: Non-blocking UI with background processing
- **Consistent Patterns**: Unified interfaces across hardware controllers

## 8. Architecture Evolution: SMT Simplification

### 8.1 Current SMT Architecture
The SMT system uses a streamlined architecture focusing on:
- Simple text-based communication protocol
- Individual command execution (eliminates buffer overflow)
- Clean 5-component separation of concerns
- Minimal but effective command throttling
- Thread-safe Qt signal-based GUI updates

### 8.2 Core SMT Components
The SMT architecture consists of 5 clean components:
- `src/core/smt_controller.py` - Business logic controller
- `src/core/smt_test.py` - Test orchestration and sequence management
- `src/gui/handlers/smt_handler.py` - GUI event handling
- `src/gui/workers/smt_worker.py` - Threading wrapper
- `src/hardware/smt_arduino_controller.py` - Hardware communication

### 8.3 Benefits of Simplification
- **Reduced Complexity**: Easier to understand and maintain
- **Better Reliability**: Fewer points of failure in communication
- **Faster Development**: Simpler codebase allows quicker feature additions
- **Clear Architecture**: Well-defined component responsibilities

## 9. Future Roadmap

### 9.1 Enhanced Results Management
*Development of comprehensive results logging and analysis capabilities*

### 9.3 Additional Features
- 16-relay support for larger SMT panels
- Enhanced automatic connection features
- Extended configuration migration tools

## 10. End Goal

The Tester V5 platform provides a modern, maintainable, and scalable foundation for production testing that:

- Minimizes operator effort while maximizing test reliability
- Supports rapid deployment of new product testing requirements
- Provides comprehensive quality assurance through robust testing workflows
- Maintains high system availability through proper resource management
- Enables future enhancements through clean architectural patterns

The system represents a significant evolution in production testing technology, combining proven testing methodologies with modern software engineering practices to deliver a reliable, efficient, and adaptable testing platform.
