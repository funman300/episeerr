"""
Activity Storage Module
Logs watch events, search events, and requests for display on dashboard
"""

import json
import os
import time
import logging

logger = logging.getLogger(__name__)

ACTIVITY_DIR = '/app/data/activity'
os.makedirs(ACTIVITY_DIR, exist_ok=True)

SEARCHES_FILE = os.path.join(ACTIVITY_DIR, 'searches.json')
WATCHES_FILE = os.path.join(ACTIVITY_DIR, 'watched.json')
REQUESTS_DIR = '/app/data/requests'

def save_search_event(series_id, series_title, season, episode, episode_ids):
    """Save when Sonarr searches for episodes"""
    event = {
        'series_id': series_id,
        'series_title': series_title,
        'season': season,
        'episode': episode,
        'episode_ids': episode_ids,
        'timestamp': int(time.time())
    }
    _append_to_activity_log(SEARCHES_FILE, event, max_entries=10)
    logger.info(f"📝 Logged search event: {series_title} S{season}E{episode}")

def save_watch_event(series_id, series_title, season, episode, user):
    """Save when user watches an episode"""
    event = {
        'series_id': series_id,
        'series_title': series_title,
        'season': season,
        'episode': episode,
        'user': user,
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
    """Get most recent Overseerr request"""
    try:
        requests_file = os.path.join(ACTIVITY_DIR, 'last_request.json')
        
        if not os.path.exists(requests_file):
            return None
        
        with open(requests_file, 'r') as f:
            return json.load(f)
            
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
    
def save_request_event(title, tmdb_id, tvdb_id, timestamp=None):
    """Save when someone requests a series via Overseerr/Jellyseerr"""
    event = {
        'title': title,
        'tmdb_id': tmdb_id,
        'tvdb_id': tvdb_id,
        'timestamp': timestamp or int(time.time())
    }
    
    requests_file = os.path.join(ACTIVITY_DIR, 'last_request.json')
    
    try:
        with open(requests_file, 'w') as f:
            json.dump(event, f, indent=2)
        logger.info(f"📝 Logged request event: {title}")
    except Exception as e:
        logger.error(f"Failed to save request: {e}")