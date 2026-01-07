import json
import os
from datetime import datetime

ACTIVITY_DIR = '/app/data/activity'
os.makedirs(ACTIVITY_DIR, exist_ok=True)

SEARCHES_FILE = os.path.join(ACTIVITY_DIR, 'searches.json')
WATCHES_FILE = os.path.join(ACTIVITY_DIR, 'watched.json')

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
    requests_dir = '/app/data/requests'
    try:
        request_files = [
            os.path.join(requests_dir, f) 
            for f in os.listdir(requests_dir) 
            if f.startswith('jellyseerr-')
        ]
        
        if not request_files:
            return None
        
        # Get most recent by file mtime
        latest_file = max(request_files, key=os.path.getmtime)
        
        with open(latest_file, 'r') as f:
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