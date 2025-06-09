"""
Configuration utility functions for loading and validating configurations
Enhanced with compatibility layer for new JSON structure
"""
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def load_test_parameters(sku: str) -> Optional[Dict[str, Any]]:
    """
    Load test parameters for a specific SKU using the SKU manager factory
    
    Args:
        sku: The SKU identifier
        
    Returns:
        Dictionary of test parameters or None if not found
    """
    try:
        from src.data.sku_manager import create_sku_manager
        sku_manager = create_sku_manager()
        
        # Try to get offroad parameters as the default test parameters
        offroad_params = sku_manager.get_test_parameters(sku, "Offroad")
        if offroad_params:
            return offroad_params
            
        # Fallback to SMT parameters if available
        smt_params = sku_manager.get_test_parameters(sku, "SMT")
        if smt_params:
            return smt_params
            
        logger.warning(f"No test parameters found for SKU {sku}")
        return None
        
    except Exception as e:
        logger.error(f"Error loading test parameters for SKU {sku}: {e}")
        return None


def get_backlight_config(sku: str) -> Optional[Dict[str, Any]]:
    """
    Get backlight configuration for a specific SKU with template resolution
    
    Args:
        sku: The SKU identifier
        
    Returns:
        Dictionary of backlight configuration or None if not found
    """
    try:
        from src.data.sku_manager import create_sku_manager
        sku_manager = create_sku_manager()
        sku_info = sku_manager.get_sku_info(sku)
        
        if sku_info and 'backlight_config' in sku_info:
            backlight_config = sku_info['backlight_config'].copy()
            
            # Resolve template reference if present
            if 'template' in backlight_config:
                template_name = backlight_config['template']
                backlight_templates = load_template('backlight_templates')
                if backlight_templates and template_name in backlight_templates:
                    # Merge template with specific config
                    template_config = backlight_templates[template_name].copy()
                    template_config.update(backlight_config)
                    return template_config
            
            return backlight_config
            
        logger.warning(f"No backlight config found for SKU {sku}")
        return None
        
    except Exception as e:
        logger.error(f"Error loading backlight config for SKU {sku}: {e}")
        return None


def get_weight_parameters(sku: str) -> Optional[Dict[str, Any]]:
    """
    Get weight parameters for a specific SKU using the new structure
    
    Args:
        sku: The SKU identifier
        
    Returns:
        Dictionary of weight parameters or None if not found
    """
    try:
        from src.data.sku_manager import create_sku_manager
        sku_manager = create_sku_manager()
        
        # Get weight parameters from the new structure
        weight_params = sku_manager.get_test_parameters(sku, "WeightChecking")
        if weight_params and 'WEIGHT' in weight_params:
            weight_config = weight_params['WEIGHT']
            sku_info = sku_manager.get_sku_info(sku)
            
            return {
                'min': weight_config.get('min_weight_g', 0.0),
                'max': weight_config.get('max_weight_g', 1000.0),
                'description': sku_info.get('description', f"SKU {sku}") if sku_info else f"SKU {sku}",
                'tare': weight_config.get('tare_g', 0.0),
                'units': 'grams'
            }
        
            
        logger.warning(f"No weight parameters found for SKU {sku}")
        return None
        
    except Exception as e:
        logger.error(f"Error loading weight parameters for SKU {sku}: {e}")
        return None


def load_programming_config() -> Optional[Dict[str, Any]]:
    """
    Load programming configuration from JSON file
    
    Returns:
        Dictionary of programming configuration or None if error
    """
    try:
        config_path = Path(__file__).parent / 'programming_config.json'
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading programming config: {e}")
        return None


def load_sku_config() -> Optional[Dict[str, Any]]:
    """
    Load SKU index configuration from JSON file
    
    Returns:
        Dictionary of SKU index configuration or None if error
    """
    try:
        config_path = Path(__file__).parent / 'skus.json'
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading SKU index config: {e}")
        return None




def load_template(template_name: str) -> Optional[Dict[str, Any]]:
    """
    Load template configuration from templates directory
    
    Args:
        template_name: Name of the template file (without .json extension)
        
    Returns:
        Dictionary of template configuration or None if error
    """
    try:
        config_path = Path(__file__).parent / 'templates' / f'{template_name}.json'
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading template {template_name}: {e}")
        return None


def get_all_available_skus() -> list[str]:
    """
    Get list of all available SKUs using the SKU manager
    
    Returns:
        List of SKU identifiers
    """
    try:
        from src.data.sku_manager import create_sku_manager
        sku_manager = create_sku_manager()
        return sku_manager.get_all_skus()
    except Exception as e:
        logger.error(f"Error getting available SKUs: {e}")
        return []


def load_individual_sku_config(sku: str) -> Optional[Dict[str, Any]]:
    """
    Load configuration for an individual SKU
    
    Args:
        sku: The SKU identifier
        
    Returns:
        Dictionary of SKU configuration or None if not found
    """
    try:
        from src.data.sku_manager import create_sku_manager
        sku_manager = create_sku_manager()
        return sku_manager.get_sku_info(sku)
    except Exception as e:
        logger.error(f"Error loading individual SKU config for {sku}: {e}")
        return None


def get_full_sku_config(sku: str) -> Optional[Dict[str, Any]]:
    """
    Get full SKU configuration with all resolved templates
    
    Args:
        sku: The SKU identifier
        
    Returns:
        Dictionary of full SKU configuration or None if not found
    """
    try:
        from src.data.sku_manager import create_sku_manager
        sku_manager = create_sku_manager()
        sku_info = sku_manager.get_sku_info(sku)
        if sku_info:
            return resolve_template_references(sku_info)
        return None
    except Exception as e:
        logger.error(f"Error getting full SKU config for {sku}: {e}")
        return None


def resolve_template_references(sku_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Resolve template references in SKU configuration
    
    Args:
        sku_config: SKU configuration with potential template references
        
    Returns:
        SKU configuration with templates resolved
    """
    try:
        resolved_config = sku_config.copy()
        
        # Resolve backlight template
        if 'backlight' in resolved_config and 'template' in resolved_config['backlight']:
            template_name = resolved_config['backlight']['template']
            backlight_templates = load_template('backlight_templates')
            if backlight_templates and template_name in backlight_templates:
                # Merge template with specific config, specific config takes precedence
                template_config = backlight_templates[template_name].copy()
                template_config.update(resolved_config['backlight'])
                resolved_config['backlight'] = template_config
                
        # Note: Color definitions are now SKU-specific and inline, no template resolution needed
                
        # Resolve test sequence references
        if 'smt_testing' in resolved_config and 'power' in resolved_config['smt_testing']:
            power_config = resolved_config['smt_testing']['power']
            if 'sequence' in power_config:
                sequence_name = power_config['sequence']
                test_sequences = load_template('test_sequences')
                if test_sequences and sequence_name in test_sequences:
                    power_config['sequence_definition'] = test_sequences[sequence_name]
                    
        return resolved_config
        
    except Exception as e:
        logger.error(f"Error resolving template references: {e}")
        return sku_config




def validate_config(config_dict: Dict[str, Any], config_type: str = 'general') -> bool:
    """
    Validate configuration values
    
    Args:
        config_dict: Configuration dictionary to validate
        config_type: Type of configuration ('serial', 'timeout', 'path', etc.)
        
    Returns:
        True if valid, False otherwise
    """
    try:
        if config_type == 'serial':
            # Validate serial settings
            if 'baud_rate' in config_dict:
                baud_rate = config_dict['baud_rate']
                valid_rates = [600, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]
                if baud_rate not in valid_rates:
                    logger.error(f"Invalid baud rate: {baud_rate}")
                    return False
                    
            if 'timeout' in config_dict:
                if not isinstance(config_dict['timeout'], (int, float)) or config_dict['timeout'] <= 0:
                    logger.error(f"Invalid timeout value: {config_dict['timeout']}")
                    return False
                    
        elif config_type == 'timeout':
            # Validate all timeout values are positive
            for key, value in config_dict.items():
                if 'timeout' in key.lower() or key.endswith('_ms') or key.endswith('_time'):
                    if not isinstance(value, (int, float)) or value <= 0:
                        logger.error(f"Invalid timeout value for {key}: {value}")
                        return False
                        
        elif config_type == 'path':
            # Validate paths exist or can be created
            for key, value in config_dict.items():
                if 'path' in key.lower() or 'directory' in key.lower():
                    path = Path(value)
                    if 'directory' in key.lower() and not path.exists():
                        try:
                            path.mkdir(parents=True, exist_ok=True)
                        except Exception as e:
                            logger.error(f"Cannot create directory {value}: {e}")
                            return False
                            
        return True
        
    except Exception as e:
        logger.error(f"Error validating config: {e}")
        return False