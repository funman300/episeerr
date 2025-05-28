# sonarr_utils.py - Simplified version for rules-only app

import os
import requests
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration settings from environment variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Setup logging
logger = logging.getLogger(__name__)

def load_preferences():
    """
    Load preferences for Sonarr configuration.
    Returns a dictionary containing Sonarr URL and API key.
    """
    if not SONARR_URL or not SONARR_API_KEY:
        raise ValueError("SONARR_URL and SONARR_API_KEY must be set in environment variables")
    
    return {
        'SONARR_URL': SONARR_URL, 
        'SONARR_API_KEY': SONARR_API_KEY
    }

def get_series_list(preferences=None):
    """
    Get all series from Sonarr.
    Returns a list of series sorted alphabetically by title.
    """
    if not preferences:
        preferences = load_preferences()
    
    url = f"{preferences['SONARR_URL']}/api/v3/series"
    headers = {'X-Api-Key': preferences['SONARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        series_list = response.json()
        # Sort the series list alphabetically by title
        sorted_series_list = sorted(series_list, key=lambda x: x.get('title', '').lower())
        
        logger.info(f"Retrieved {len(sorted_series_list)} series from Sonarr")
        return sorted_series_list
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch series from Sonarr: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error fetching series: {str(e)}")
        return []

def get_series_by_id(series_id, preferences=None):
    """
    Get a specific series by ID from Sonarr.
    """
    if not preferences:
        preferences = load_preferences()
    
    url = f"{preferences['SONARR_URL']}/api/v3/series/{series_id}"
    headers = {'X-Api-Key': preferences['SONARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch series {series_id} from Sonarr: {str(e)}")
        return None

def update_series_tags(series_id, tags, preferences=None):
    """
    Update tags for a specific series in Sonarr.
    """
    if not preferences:
        preferences = load_preferences()
    
    # First get the current series data
    series = get_series_by_id(series_id, preferences)
    if not series:
        return False
    
    # Update the tags
    series['tags'] = tags
    
    url = f"{preferences['SONARR_URL']}/api/v3/series"
    headers = {
        'X-Api-Key': preferences['SONARR_API_KEY'],
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.put(url, headers=headers, json=series, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Updated tags for series {series_id}")
        return True
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to update series {series_id} tags: {str(e)}")
        return False

def get_quality_profiles(preferences=None):
    """
    Get available quality profiles from Sonarr.
    """
    if not preferences:
        preferences = load_preferences()
    
    url = f"{preferences['SONARR_URL']}/api/v3/qualityprofile"
    headers = {'X-Api-Key': preferences['SONARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch quality profiles: {str(e)}")
        return []

def get_tags(preferences=None):
    """
    Get all tags from Sonarr.
    """
    if not preferences:
        preferences = load_preferences()
    
    url = f"{preferences['SONARR_URL']}/api/v3/tag"
    headers = {'X-Api-Key': preferences['SONARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to fetch tags: {str(e)}")
        return []

def create_tag(label, preferences=None):
    """
    Create a new tag in Sonarr.
    """
    if not preferences:
        preferences = load_preferences()
    
    url = f"{preferences['SONARR_URL']}/api/v3/tag"
    headers = {
        'X-Api-Key': preferences['SONARR_API_KEY'],
        'Content-Type': 'application/json'
    }
    
    data = {'label': label}
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        response.raise_for_status()
        
        logger.info(f"Created tag '{label}'")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to create tag '{label}': {str(e)}")
        return None

def test_connection(preferences=None):
    """
    Test connection to Sonarr.
    """
    if not preferences:
        try:
            preferences = load_preferences()
        except ValueError as e:
            return False, str(e)
    
    url = f"{preferences['SONARR_URL']}/api/v3/system/status"
    headers = {'X-Api-Key': preferences['SONARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        
        status = response.json()
        logger.info(f"Connected to Sonarr: {status.get('appName', 'Unknown')} v{status.get('version', 'Unknown')}")
        return True, "Connection successful"
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to connect to Sonarr: {str(e)}")
        return False, f"Connection failed: {str(e)}"

# Additional utility functions for rules management

def get_series_statistics(preferences=None):
    """
    Get basic statistics about series in Sonarr.
    """
    series_list = get_series_list(preferences)
    
    total_series = len(series_list)
    monitored_series = sum(1 for series in series_list if series.get('monitored', False))
    
    return {
        'total_series': total_series,
        'monitored_series': monitored_series,
        'unmonitored_series': total_series - monitored_series
    }

def validate_sonarr_config():
    """
    Validate that Sonarr configuration is properly set up.
    """
    try:
        preferences = load_preferences()
        success, message = test_connection(preferences)
        
        if not success:
            return False, message
        
        # Test if we can fetch series
        series_list = get_series_list(preferences)
        
        return True, f"Configuration valid. Found {len(series_list)} series."
        
    except Exception as e:
        return False, f"Configuration error: {str(e)}"

if __name__ == "__main__":
    # Simple test when run directly
    print("Testing Sonarr connection...")
    
    success, message = validate_sonarr_config()
    print(f"Result: {message}")
    
    if success:
        print("\nFetching series statistics...")
        stats = get_series_statistics()
        print(f"Total series: {stats['total_series']}")
        print(f"Monitored: {stats['monitored_series']}")
        print(f"Unmonitored: {stats['unmonitored_series']}")