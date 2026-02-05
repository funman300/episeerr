"""
Integration Plugin System
Automatically discovers and loads all integration plugins from this directory
"""

import os
import importlib
import logging
from typing import Dict, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Storage for discovered integrations
_integrations: Dict[str, 'ServiceIntegration'] = {}


def discover_integrations():
    """
    Auto-discover all integration plugins in this directory
    
    Looks for .py files that export an 'integration' variable
    """
    integrations_dir = Path(__file__).parent
    logger.info("🔍 Discovering integration plugins...")
    
    # Find all .py files except __init__ and base
    for file in integrations_dir.glob('*.py'):
        if file.stem in ['__init__', 'base']:
            continue
        
        module_name = file.stem
        try:
            # Import the module
            module = importlib.import_module(f'integrations.{module_name}')
            
            # Look for 'integration' variable
            if hasattr(module, 'integration'):
                integration = module.integration
                service_name = integration.service_name
                
                # Validate required properties
                if not service_name:
                    logger.error(f"❌ {module_name}.py: service_name is empty")
                    continue
                
                if not integration.display_name:
                    logger.error(f"❌ {module_name}.py: display_name is empty")
                    continue
                
                # Store the integration
                _integrations[service_name] = integration
                logger.info(f"✅ Loaded integration: {integration.display_name} ({service_name})")
            else:
                logger.warning(f"⚠️  {module_name}.py has no 'integration' variable - skipping")
        
        except ImportError as e:
            logger.error(f"❌ Failed to import {module_name}.py: {e}")
        except AttributeError as e:
            logger.error(f"❌ {module_name}.py missing required property: {e}")
        except Exception as e:
            logger.error(f"❌ Error loading {module_name}.py: {e}")
            import traceback
            traceback.print_exc()
    
    count = len(_integrations)
    if count > 0:
        logger.info(f"🎉 Successfully loaded {count} integration(s): {', '.join(_integrations.keys())}")
    else:
        logger.info("📭 No integrations found")


def get_integration(service_name: str):
    """
    Get a specific integration by service name
    
    Args:
        service_name: Service identifier (e.g., 'radarr', 'sabnzbd')
        
    Returns:
        ServiceIntegration instance or None
    """
    return _integrations.get(service_name)


def get_all_integrations() -> List:
    """
    Get all loaded integrations
    
    Returns:
        List of ServiceIntegration instances
    """
    return list(_integrations.values())


def get_integrations_by_category(category: str) -> List:
    """
    Get integrations filtered by category
    
    Args:
        category: Category name ('dashboard', 'media_server', etc.)
        
    Returns:
        List of ServiceIntegration instances in that category
    """
    return [i for i in _integrations.values() if i.category == category]


def reload_integrations():
    """
    Reload all integrations (useful for development)
    Clears cache and re-discovers
    """
    global _integrations
    _integrations = {}
    discover_integrations()


# Auto-discover integrations when this module is imported
discover_integrations()
