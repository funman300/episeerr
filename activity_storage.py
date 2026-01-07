"""
Activity Storage Module - WITH BACKDROP SUPPORT
Logs watch events, search events, and requests with backdrop images
"""

import json
import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

ACTIVITY_DIR = '/app/data/activity'
os.makedirs(ACTIVITY_DIR, exist_ok=True)

SEARCHES_FILE = os.path.join(ACTIVITY_DIR, 'searches.json')
WATCHES_FILE = os.path.join(ACTIVITY_DIR, 'watched.json')
REQUESTS_DIR = '/app/data/requests'

# Sonarr API settings (will be loaded from config)
SONARR_URL = None
SONARR_API_KEY = None

def init_sonarr_config(url, api_key):
    """Initialize Sonarr config for backdrop fetching"""
    global SONARR_URL, SONARR_API_KEY
    SONARR_URL = url
    SONARR_API_KEY = api_key

def get_series_backdrop(series_id):
    """Fetch backdrop path from Sonarr series data"""
    try:
        if not SONARR_URL or not SONARR_API_KEY:
            return None
            
        url = f"{SONARR_URL}/api/v3/series/{series_id}"
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(url, headers=headers, timeout=5)
        
        if response.ok:
            series_data = response.json()
            # Get fanart/backdrop image
            for image in series_data.get('images', []):
                if image.get('coverType') in ['fanart', 'banner']:
                    return image.get('remoteUrl')  # Returns TMDB backdrop URL
        return None
    except Exception as e:
        logger.debug(f"Could not get backdrop for series {series_id}: {e}")
        return None

def save_search_event(series_id, series_title, season, episode, episode_ids):
    """Save when Sonarr searches for episodes"""
    # Get backdrop instead of poster
    backdrop_url = get_series_backdrop(series_id)
    
    event = {
        'series_id': series_id,
        'series_title': series_title,
        'season': season,
        'episode': episode,
        'episode_ids': episode_ids,
        'backdrop_url': backdrop_url,  # NEW: Backdrop instead of poster
        'timestamp': int(time.time())
    }
    _append_to_activity_log(SEARCHES_FILE, event, max_entries=10)
    logger.info(f"📝 Logged search event: {series_title} S{season}E{episode}")

def save_watch_event(series_id, series_title, season, episode, user):
    """Save when user watches an episode"""
    # Get backdrop instead of poster
    backdrop_url = get_series_backdrop(series_id)
    
    event = {
        'series_id': series_id,
        'series_title': series_title,
        'season': season,
        'episode': episode,
        'user': user,
        'backdrop_url': backdrop_url,  # NEW: Backdrop instead of poster
        'timestamp': int(time.time())
    }
    _append_to_activity_log(WATCHES_FILE, event, max_entries=10)
    logger.info(f"📝 Logged watch event: {series_title} S{season}E{episode} by {user}")

def _append_to_activity_log(filepath, event, max_entries=10):
    """Helper to append event and keep only last N entries"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                events = json.load(f)
        else:
            events = []
        
        events.insert(0, event)  # Add to front
        events = events[:max_entries]  # Keep only last N
        
        with open(filepath, 'w') as f:
            json.dump(events, f, indent=2)
            
    except Exception as e:
        logger.error(f"Failed to save activity: {e}")

def get_last_search():
    """Get most recent search event"""
    return _get_last_event(SEARCHES_FILE)

def get_last_watch():
    """Get most recent watch event"""
    return _get_last_event(WATCHES_FILE)

def get_last_request():
    """Get most recent Overseerr request - also gets backdrop"""
    try:
        activity_file = '/app/data/activity/last_request.json'
        
        if not os.path.exists(activity_file):
            return None
        
        with open(activity_file, 'r') as f:
            request_data = json.load(f)
            
        # If we have tmdb_id but no backdrop, try to get it
        if request_data.get('tmdb_id') and not request_data.get('backdrop_url'):
            # The tmdb_id in requests is often the poster path like "/abc.jpg"
            # We need to fetch the backdrop from TMDB or use the poster path
            # For now, construct the backdrop URL from TMDB ID
            tmdb_id = request_data.get('tvdb_id') or request_data.get('series_id')
            if tmdb_id:
                # Try to get backdrop from Sonarr
                request_data['backdrop_url'] = get_series_backdrop(tmdb_id)
            
        return request_data
            
    except Exception as e:
        logger.error(f"Failed to get last request: {e}")
        return None

def _get_last_event(filepath):
    """Helper to get most recent event from log"""
    try:
        if not os.path.exists(filepath):
            return None
        
        with open(filepath, 'r') as f:
            events = json.load(f)
        
        return events[0] if events else None
        
    except Exception as e:
        logger.error(f"Failed to read activity log: {e}")
        return None