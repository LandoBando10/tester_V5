# SKU Configuration Database Migration Plan

## Executive Summary

This document outlines a comprehensive plan to migrate the SKU configuration system from individual JSON files to a SQLite database. The migration is designed to be low-risk with a phased rollout over 4 weeks, maintaining backward compatibility throughout the process.

## Current System Analysis

### Issues with Current Architecture

1. **Architecture Mismatch**: The GUI editor expects a unified configuration file (`skus_config.json`) but the system uses individual JSON files per SKU in mode-specific directories.

2. **Inefficient Directory Structure**: SKUs scattered across `offroad/`, `smt/`, and `weight/` subdirectories, creating duplication when SKUs support multiple test modes.

3. **Editor-System Disconnect**: The editor manipulates an in-memory data structure that doesn't map cleanly to individual files.

4. **Limited Scalability**: Managing hundreds of individual files becomes unwieldy with no built-in versioning or change tracking.

5. **Deployment Complexity**: Updating SKU configurations requires managing multiple files across directories.

## Proposed Solution: SQLite Database

### Why SQLite?

- **Lightweight**: No server required, single file deployment
- **ACID Compliant**: Ensures data integrity
- **Fast**: Efficient querying with proper indexing
- **Mature**: Battle-tested in production environments
- **Python Native**: Excellent support via `sqlite3` module

## Implementation Plan

### Phase 1: Foundation (Week 1)
**Goal**: Create database infrastructure alongside existing system

#### Database Schema

```sql
-- Core SKU table
CREATE TABLE skus (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_code VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    category VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    active BOOLEAN DEFAULT 1
);

-- SKU modes (which tests are available)
CREATE TABLE sku_modes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL,
    mode VARCHAR(20) NOT NULL, -- 'offroad', 'smt', 'weight'
    enabled BOOLEAN DEFAULT 1,
    FOREIGN KEY (sku_id) REFERENCES skus(id),
    UNIQUE(sku_id, mode)
);

-- Backlight configurations
CREATE TABLE backlight_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL,
    backlight_type VARCHAR(20), -- 'single', 'dual', 'rgbw_cycling'
    relay_pins TEXT, -- JSON array [3] or [3,4]
    test_duration_ms INTEGER DEFAULT 500,
    config_data TEXT, -- JSON for RGBW-specific settings
    FOREIGN KEY (sku_id) REFERENCES skus(id)
);

-- Test parameters (flexible key-value store)
CREATE TABLE test_parameters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL,
    mode VARCHAR(20) NOT NULL,
    parameter_group VARCHAR(50), -- 'LUX', 'COLOR', 'CURRENT', etc.
    parameter_name VARCHAR(100),
    parameter_value TEXT, -- Store as JSON for flexibility
    FOREIGN KEY (sku_id) REFERENCES skus(id)
);

-- Audit trail
CREATE TABLE config_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sku_id INTEGER NOT NULL,
    change_type VARCHAR(20), -- 'create', 'update', 'delete'
    field_name VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(100),
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sku_id) REFERENCES skus(id)
);

-- Version tracking
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### File Structure

```
src/data/
├── sku_database.py      # SQLite connection management
├── sku_repository.py    # CRUD operations
├── sku_models.py        # Dataclass models
└── migrations/          # Schema migrations
    ├── __init__.py
    ├── 001_initial_schema.py
    └── migration_runner.py
```

### Phase 2: Parallel Operation (Week 2)
**Goal**: Run both systems simultaneously

#### Adapter Pattern

```python
class SKUDataAdapter:
    """Provides unified interface for both JSON and DB backends"""
    
    def __init__(self, use_database=False):
        self.json_manager = ExistingSKUManager()
        self.db_manager = SKUDatabaseManager()
        self.use_database = use_database
    
    def get_sku(self, sku_code):
        if self.use_database:
            return self.db_manager.get_sku(sku_code)
        return self.json_manager.get_sku(sku_code)
    
    def save_sku(self, sku_data):
        # Save to both systems during migration
        if self.use_database:
            self.db_manager.save_sku(sku_data)
        self.json_manager.save_sku(sku_data)
```

#### Migration Tools

```
tools/
├── json_to_db_migrator.py   # One-time migration script
├── db_to_json_exporter.py   # Backup/export functionality
├── consistency_checker.py    # Verify JSON/DB sync
└── rollback_tool.py         # Emergency rollback
```

### Phase 3: Gradual Migration (Week 3)
**Goal**: Migrate features one at a time

#### Feature Migration Order

1. **Read Operations First**
   - SKU listing
   - Parameter retrieval
   - Test configuration loading

2. **Write Operations Second**
   - New SKU creation
   - Parameter updates
   - Configuration changes

3. **Advanced Features Last**
   - Audit trail
   - Version history
   - Bulk operations

#### Configuration Toggle

```python
# config/settings.py
DATABASE_CONFIG = {
    'enabled': False,  # Start with False
    'features': {
        'read_skus': False,
        'write_skus': False,
        'audit_trail': False,
        'use_cache': True
    },
    'db_path': 'config/skus.db',
    'backup_path': 'config/backups/'
}
```

### Phase 4: UI Integration (Week 4)
**Goal**: Update configuration editor

#### Editor Enhancements

1. **Abstract Data Layer**
   - Replace direct JSON manipulation
   - Use repository pattern
   - Handle both backends transparently

2. **New Features**
   - History viewer tab
   - Bulk import/export
   - Search and filter capabilities
   - Change comparison view

#### Backward Compatibility

```python
class LegacyJSONExporter:
    """Maintains JSON files for external tools"""
    
    def export_on_change(self, sku):
        # Automatically export to JSON when DB changes
        json_path = self.get_json_path(sku)
        with open(json_path, 'w') as f:
            json.dump(sku.to_dict(), f, indent=2)
```

## Timeline

### Week 1: Foundation
- **Day 1-2**: Create database schema and models
- **Day 3-4**: Build repository layer with tests
- **Day 5**: Migration scripts and tools

### Week 2: Integration
- **Day 1-2**: Implement adapter pattern
- **Day 3-4**: Update SKUManager to use adapter
- **Day 5**: Testing and validation

### Week 3: Migration
- **Day 1**: Migrate read operations
- **Day 2-3**: Migrate write operations
- **Day 4-5**: Production testing with feature flags

### Week 4: Completion
- **Day 1-2**: Update configuration editor
- **Day 3**: Staff training and documentation
- **Day 4-5**: Full rollout and monitoring

## Risk Mitigation

### Data Loss Prevention
- Automated backups before each migration step
- JSON files remain synchronized during transition
- Transaction-based operations ensure atomicity
- Point-in-time recovery capability

### Performance Impact
- SQLite benchmarks show <5ms query time for typical operations
- In-memory caching for frequently accessed SKUs
- Proper indexing on sku_code and mode fields
- Connection pooling for concurrent access

### User Disruption
- No UI changes required in Phase 1-2
- Feature flags allow gradual rollout
- Training materials prepared before UI updates
- Rollback capability at each phase

### Testing Strategy
- Unit tests for all repository methods
- Integration tests with both backends
- Performance benchmarks at each phase
- A/B testing in production environment

## Rollback Plan

Each phase can be independently rolled back:

1. **Feature Flag Disable**: Immediate reversion to JSON backend
2. **Data Sync**: JSON files remain updated throughout migration
3. **One-Command Rollback**: `python tools/rollback_tool.py --phase X`
4. **Zero Data Loss**: All changes preserved in both systems

## Success Metrics

### Phase 1 Success Criteria
- Database schema successfully deployed
- Migration tools tested with 100% data accuracy
- Backup and restore procedures validated

### Phase 2 Success Criteria
- Adapter pattern functioning with both backends
- 100% read parity between JSON and database
- No performance degradation observed

### Phase 3 Success Criteria
- All CRUD operations migrated successfully
- Query performance <50ms for any operation
- Feature flags working correctly

### Phase 4 Success Criteria
- Zero data inconsistencies reported
- Positive user feedback on new features
- Successful training completion for all operators

## Benefits Summary

### Immediate Benefits (Week 1-2)
- Parallel operation reduces risk
- Automated consistency checking
- Performance baselines established

### Short-term Benefits (Week 3-4)
- 10x faster SKU queries
- Audit trail for compliance
- Simplified backup procedures

### Long-term Benefits
- Support for 1000+ SKUs
- Advanced search and filtering
- Change history and rollback
- Multi-user concurrent access
- RESTful API ready

## Technical Requirements

### Software Dependencies
- Python 3.8+
- SQLite 3.35+
- PySide6 (existing)
- pytest for testing

### Hardware Requirements
- No additional hardware needed
- Database file size estimate: <100MB for 1000 SKUs
- Backup storage: 1GB recommended

## Training Plan

### Operator Training (2 hours)
- Overview of new features
- Using the search functionality
- Understanding change history
- Emergency procedures

### Administrator Training (4 hours)
- Database backup procedures
- Using migration tools
- Monitoring and maintenance
- Troubleshooting guide

## Maintenance Procedures

### Daily
- Automated backup verification
- Performance metrics collection
- Error log review

### Weekly
- Database optimization (VACUUM)
- Consistency check between systems
- Usage statistics review

### Monthly
- Full system backup
- Performance trending analysis
- Feature usage analytics

## Conclusion

This phased migration plan provides a low-risk path to modernize the SKU configuration system. By maintaining parallel operation and using feature flags, we ensure zero disruption to production while gaining significant benefits in performance, scalability, and maintainability.

The investment of 4 weeks will yield a professional-grade configuration management system that scales with business growth while reducing operational complexity.