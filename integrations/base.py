"""
Base class for Episeerr service integrations
All integration plugins inherit from this class
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any, List, Tuple
import requests
import logging
import os

logger = logging.getLogger(__name__)


class ServiceIntegration(ABC):
    """
    Base class for all Episeerr service integrations
    
    To create a new integration:
    1. Create a new .py file in integrations/ (e.g., radarr.py)
    2. Create a class that inherits from ServiceIntegration
    3. Implement all @abstractmethod methods
    4. Add at bottom: integration = YourIntegration()
    5. Restart Episeerr - it will auto-discover!
    """
    
    # ============================================================
    # REQUIRED: Each integration must define these properties
    # ============================================================
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """
        Service identifier (lowercase, no spaces)
        Used for database keys, form field names, etc.
        Example: 'radarr', 'sabnzbd', 'prowlarr'
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable name for UI
        Example: 'Radarr', 'SABnzbd', 'Prowlarr'
        """
        pass
    
    @property
    @abstractmethod
    def icon(self) -> str:
        """
        Icon URL or Font Awesome class
        Example: 'https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/radarr.png'
        Or: 'fas fa-video'
        """
        pass
    
    @property
    def description(self) -> str:
        """
        Short description shown in setup page
        Example: 'Movie library stats and upcoming releases'
        """
        return ""
    
    @property
    def category(self) -> str:
        """
        Category for grouping in UI
        Options: 'dashboard', 'media_server', 'indexer', 'request', 'other'
        """
        return 'dashboard'
    
    @property
    def default_port(self) -> Optional[int]:
        """
        Default port for this service (optional)
        Example: 7878 for Radarr
        """
        return None
    
    # ============================================================
    # OPTIONAL: Override these if you need custom setup fields
    # ============================================================
    
    @property
    def setup_fields(self) -> List[Dict[str, Any]]:
        """
        Define form fields for setup page
        
        Returns list of field definitions. Default is URL + API Key.
        Override this if you need additional fields.
        
        Example:
        [
            {
                'name': 'url',
                'label': 'URL',
                'type': 'url',
                'required': True,
                'placeholder': 'http://192.168.1.100:7878'
            },
            {
                'name': 'apikey',
                'label': 'API Key',
                'type': 'password',
                'required': True,
                'help': 'Settings → General → API Key'
            }
        ]
        """
        port_hint = f":{self.default_port}" if self.default_port else ":8080"
        
        return [
            {
                'name': 'url',
                'label': 'URL',
                'type': 'url',
                'required': True,
                'placeholder': f'http://192.168.1.100{port_hint}',
                'help': self.description
            },
            {
                'name': 'apikey',
                'label': 'API Key',
                'type': 'password',
                'required': True,
                'help': 'Settings → General → API Key'
            }
        ]
    
    # ============================================================
    # BUILT-IN: Configuration helpers (don't override these)
    # ============================================================
    
    def get_config(self) -> Optional[Dict[str, Any]]:
        """
        Get service configuration from database or environment
        
        Returns:
            Dict with 'url', 'api_key', 'config' or None if not configured
        """
        from settings_db import get_service
        from episeerr_utils import normalize_url
        
        # Try database first
        service = get_service(self.service_name, 'default')
        if service:
            return {
                'url': normalize_url(service['url']),
                'api_key': service['api_key'],
                'config': service.get('config', {})
            }
        
        # Fallback to environment variables
        url_env = f"{self.service_name.upper()}_URL"
        key_env = f"{self.service_name.upper()}_API_KEY"
        
        url = os.getenv(url_env)
        api_key = os.getenv(key_env)
        
        if url and api_key:
            return {
                'url': normalize_url(url),
                'api_key': api_key,
                'config': {}
            }
        
        return None
    def get_dashboard_widget(self) -> Dict[str, Any]:
        """
        Optional: Define how this service appears on dashboard
        Override this to customize widget appearance
        """
        return {
            'enabled': False  # Hidden by default
        }
    # ============================================================
    # REQUIRED: Each integration must implement these methods
    # ============================================================
    
    @abstractmethod
    def test_connection(self, url: str, api_key: str) -> Tuple[bool, str]:
        """
        Test connection to the service
        
        Args:
            url: Service URL
            api_key: API key
            
        Returns:
            (success: bool, message: str)
            
        Example:
            return True, "Connected to Radarr v4.0.0"
            return False, "Invalid API key"
        """
        pass
    
    @abstractmethod
    def get_dashboard_stats(self, url: str, api_key: str) -> Dict[str, Any]:
        """
        Get statistics for dashboard display
        
        Args:
            url: Service URL
            api_key: API key
            
        Returns:
            Dict with stats (structure depends on your integration)
            
        Example for Radarr:
            {
                'total_movies': 150,
                'downloaded_movies': 145,
                'size_gb': 1250.5
            }
        """
        pass
    
    # ============================================================
    # OPTIONAL: Override if you need custom behavior
    # ============================================================
    
    def on_save(self, url: str, api_key: str, config: Optional[Dict] = None):
        """
        Called after service is saved in setup
        Default behavior: Add to quick links
        
        Override this if you need custom post-save actions
        """
        # Auto-add to quick links by default
        try:
            from episeerr import auto_add_quick_link
            auto_add_quick_link(self.display_name, url, self.icon)
            logger.info(f"Added {self.display_name} to quick links")
        except Exception as e:
            logger.error(f"Error adding {self.display_name} to quick links: {e}")
    
    # ============================================================
    # HELPER: Use this in your methods for API calls
    # ============================================================
    
    def _make_request(self, url: str, api_key: str, endpoint: str,
                      headers: Optional[Dict] = None, 
                      params: Optional[Dict] = None,
                      timeout: int = 10) -> Optional[Dict]:
        """
        Helper method for making API requests
        
        Args:
            url: Base service URL
            api_key: API key
            endpoint: API endpoint (e.g., '/api/v3/movie')
            headers: Additional headers (optional)
            params: Query parameters (optional)
            timeout: Request timeout in seconds
            
        Returns:
            JSON response as dict, or None on error
        """
        try:
            if headers is None:
                headers = {}
            
            response = requests.get(
                f"{url}{endpoint}",
                headers=headers,
                params=params,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"{self.display_name} API error: {e}")
            return None
