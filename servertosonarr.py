import os
import re
import requests
import logging
from logging.handlers import RotatingFileHandler
import json
import time
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define log paths
LOG_PATH = os.getenv('LOG_PATH', '/app/logs/app.log')
MISSING_LOG_PATH = os.getenv('MISSING_LOG_PATH', '/app/logs/missing.log')
CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')

# Ensure log directories exist
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(MISSING_LOG_PATH), exist_ok=True)
os.makedirs(os.path.dirname(CLEANUP_LOG_PATH), exist_ok=True)

# Configure root logger with minimal handlers (console only)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # Console logging only
    ]
)

# Create main logger for general logs
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Clear any inherited handlers

# Add handler for main app log
app_handler = RotatingFileHandler(
    LOG_PATH,  # /app/logs/app.log
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=3,
    encoding='utf-8'
)
app_handler.setLevel(logging.INFO)
app_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(app_handler)

# Add console handler for main logger
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(console_handler)

# Create missing logger for missing series
missing_logger = logging.getLogger('missing')
missing_logger.setLevel(logging.INFO)
missing_logger.handlers.clear()  # Clear any inherited handlers
missing_logger.propagate = False  # Prevent propagation to root logger

# Add file handler for missing logger
missing_handler = logging.FileHandler(MISSING_LOG_PATH)  # /app/logs/missing.log
missing_handler.setLevel(logging.INFO)
missing_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
missing_logger.addHandler(missing_handler)

# Add console handler for missing logger
missing_logger.addHandler(console_handler)

# Enhanced logging setup for cleanup operations
def setup_cleanup_logging():
    """Setup cleanup logging to write to BOTH console AND files."""
    # Create cleanup-specific logger
    cleanup_logger = logging.getLogger('cleanup')
    cleanup_logger.setLevel(logging.INFO)
    cleanup_logger.handlers.clear()  # Clear any inherited handlers
    cleanup_logger.propagate = False  # Prevent propagation to root logger
    
    # File handler for cleanup-specific log
    cleanup_file_handler = RotatingFileHandler(
        CLEANUP_LOG_PATH,  # /app/logs/cleanup.log
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    cleanup_file_handler.setLevel(logging.INFO)
    cleanup_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    cleanup_file_handler.setFormatter(cleanup_formatter)
    
    # File handler for main app log (with CLEANUP prefix)
    main_file_handler = RotatingFileHandler(
        LOG_PATH,  # /app/logs/app.log
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=3,
        encoding='utf-8'
    )
    main_file_handler.setLevel(logging.INFO)
    main_formatter = logging.Formatter('%(asctime)s - CLEANUP - %(levelname)s - %(message)s')
    main_file_handler.setFormatter(main_formatter)
    
    # Console handler for Docker logs
    console_handler_cleanup = logging.StreamHandler()
    console_handler_cleanup.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - CLEANUP - %(levelname)s - %(message)s')
    console_handler_cleanup.setFormatter(console_formatter)
    
    # Add handlers to cleanup logger
    cleanup_logger.addHandler(main_file_handler)
    cleanup_logger.addHandler(cleanup_file_handler)
    cleanup_logger.addHandler(console_handler_cleanup)
    
    return cleanup_logger

# Initialize cleanup logger
cleanup_logger = setup_cleanup_logging()

# Define global variables based on environment settings
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Environment variable for global dry run mode
DRY_RUN_MODE = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'

# Time-based cleanup tracking
ACTIVITY_TRACKING_FILE = os.path.join(os.getcwd(), 'data', 'activity_tracking.json')
os.makedirs(os.path.dirname(ACTIVITY_TRACKING_FILE), exist_ok=True)

# Load settings from a JSON configuration file
def load_config():
    config_path = os.getenv('CONFIG_PATH', '/app/config/config.json')
    with open(config_path, 'r') as file:
        config = json.load(file)
    # Ensure required keys are present with default values
    if 'rules' not in config:
        config['rules'] = {}
    return config

def load_activity_tracking():
    """Load activity tracking data."""
    try:
        if os.path.exists(ACTIVITY_TRACKING_FILE):
            with open(ACTIVITY_TRACKING_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading activity tracking: {str(e)}")
        return {}

def save_activity_tracking(data):
    """Save activity tracking data."""
    try:
        with open(ACTIVITY_TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving activity tracking: {str(e)}")

def update_activity_date(series_id, season_number=None, episode_number=None, timestamp=None):
    """Update activity date for a series in config.json (NEW APPROACH)."""
    try:
        config = load_config()
        current_time = timestamp or int(time.time())
        
        # Find the series in rules and update activity_date
        for rule_name, rule_details in config['rules'].items():
            series_dict = rule_details.get('series', {})
            if str(series_id) in series_dict:
                if isinstance(series_dict[str(series_id)], dict):
                    series_dict[str(series_id)]['activity_date'] = current_time
                else:
                    # Convert old format to new format
                    series_dict[str(series_id)] = {'activity_date': current_time}
                
                save_config(config)
                logger.info(f"📺 Updated activity date for series {series_id}: {datetime.fromtimestamp(current_time)}")
                return
        
        logger.warning(f"Series {series_id} not found in any rule for activity update")
        
    except Exception as e:
        logger.error(f"Error updating activity date for series {series_id}: {str(e)}")

## new activity date methods
def get_activity_date_with_hierarchy(series_id, series_title=None):
    """Get activity date using hierarchy: config.json, Tautulli, Jellyfin, Sonarr - FIXED VERSION."""
    logger.info(f"🔍 Getting activity date for series {series_id} ({series_title})")
    
    # Step 1: Check config.json
    config = load_config()
    for rule_name, rule_details in config['rules'].items():
        series_dict = rule_details.get('series', {})
        series_data = series_dict.get(str(series_id))
        if isinstance(series_data, dict):
            activity_date = series_data.get('activity_date')
            if activity_date:
                logger.info(f"✅ Using config activity date for series {series_id}: {datetime.fromtimestamp(activity_date)}")
                return activity_date
    
    logger.info(f"⚠️  No config activity date for series {series_id}")
    
    # Get Sonarr title if not provided
    if not series_title:
        try:
            headers = {'X-Api-Key': SONARR_API_KEY}
            response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers, timeout=5)
            if response.ok:
                series_title = response.json().get('title')
                logger.info(f"Retrieved Sonarr title: {series_title}")
        except Exception as e:
            logger.warning(f"Failed to get Sonarr title for series {series_id}: {str(e)}")
    
    # Step 2: Check Tautulli (only once)
    if series_title:
        logger.info(f"🔍 Checking Tautulli for '{series_title}'")
        tautulli_date = get_tautulli_last_watched(series_title)
        if tautulli_date:
            logger.info(f"✅ Using Tautulli date for series {series_id}: {datetime.fromtimestamp(tautulli_date)}")
            return tautulli_date
        logger.info(f"⚠️  No Tautulli date found for series {series_id}")
    
    # Step 3: Check Jellyfin (only once)
    if series_title:
        logger.info(f"🔍 Checking Jellyfin for '{series_title}'")
        jellyfin_date = get_jellyfin_last_watched(series_title)
        if jellyfin_date:
            logger.info(f"✅ Using Jellyfin date for series {series_id}: {datetime.fromtimestamp(jellyfin_date)}")
            return jellyfin_date
        logger.info(f"⚠️  No Jellyfin date found for series {series_id}")
    
    # Step 4: Check Sonarr episode file dates (FIXED)
    logger.info(f"🔍 Checking Sonarr file dates for series {series_id}")
    sonarr_date = get_sonarr_latest_file_date(series_id)
    if sonarr_date:
        logger.info(f"✅ Using Sonarr file date for series {series_id}: {datetime.fromtimestamp(sonarr_date)}")
        return sonarr_date
    
    logger.warning(f"⚠️  No activity date found for series {series_id}")
    return None
    

def find_episodes_to_delete_immediate(all_episodes, keep_watched, last_watched_season, last_watched_episode):
    """
    IMMEDIATE DELETION (Original Logic): Delete episodes before the keep block.
    This maintains the sliding window pattern from the original system.
    """
    episodes_to_delete = []
    
    try:
        if keep_watched == "all":
            logger.info("Keep watched is 'all', no immediate deletion")
            return []
            
        elif keep_watched == "season":
            # Keep current season, delete previous seasons
            logger.info(f"Immediate deletion: keeping season {last_watched_season}, deleting previous seasons")
            episodes_to_delete = [
                ep for ep in all_episodes 
                if ep['seasonNumber'] < last_watched_season and ep['hasFile']
            ]
            
        else:
            # Keep a specific number of episodes including the one just watched
            keep_count = int(keep_watched)
            logger.info(f"Immediate deletion: keeping block of {keep_count} episodes including just watched")
            
            # Sort all episodes by season/episode
            sorted_episodes = sorted(all_episodes, key=lambda ep: (ep['seasonNumber'], ep['episodeNumber']))
            
            # Find the last watched episode index
            last_watched_index = None
            for i, ep in enumerate(sorted_episodes):
                if (ep['seasonNumber'] == last_watched_season and 
                    ep['episodeNumber'] == last_watched_episode):
                    last_watched_index = i
                    break
            
            if last_watched_index is not None:
                # Keep block: keep_count episodes ending with the one just watched
                keep_start_index = max(0, last_watched_index - keep_count + 1)
                
                # Delete episodes before the keep block
                episodes_with_files = [ep for ep in sorted_episodes if ep['hasFile']]
                
                for ep in episodes_with_files:
                    ep_index = next((i for i, se in enumerate(sorted_episodes) if se['id'] == ep['id']), None)
                    if ep_index is not None and ep_index < keep_start_index:
                        episodes_to_delete.append(ep)
                
                logger.info(f"Immediate deletion: keeping episodes {keep_start_index}-{last_watched_index}, deleting {len(episodes_to_delete)} before")
        
        return [ep['episodeFileId'] for ep in episodes_to_delete if 'episodeFileId' in ep]
        
    except Exception as e:
        logger.error(f"Error in immediate deletion logic: {str(e)}")
        return []



def save_config(config):
    """Save configuration to JSON file."""
    config_path = os.getenv('CONFIG_PATH', '/app/config/config.json')
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)



# Add cleanup summary endpoint for the web UI
def get_cleanup_summary():
    """Get summary of recent cleanup operations for the web interface."""
    try:
        CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
        
        if not os.path.exists(CLEANUP_LOG_PATH):
            return {"recent_cleanups": [], "total_operations": 0}
        
        recent_cleanups = []
        
        # Read the last 100 lines of the cleanup log
        with open(CLEANUP_LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        # Look for cleanup completion messages
        for line in reversed(lines[-100:]):
            if "CLEANUP COMPLETED" in line:
                try:
                    timestamp = line.split(' - ')[0]
                    recent_cleanups.append({
                        "timestamp": timestamp,
                        "type": "Scheduled" if "Scheduled" in line else "Manual",
                        "status": "completed"
                    })
                    
                    if len(recent_cleanups) >= 5:  # Limit to 5 recent cleanups
                        break
                except:
                    continue
        
        return {
            "recent_cleanups": recent_cleanups,
            "total_operations": len(recent_cleanups)
        }
        
    except Exception as e:
        cleanup_logger.error(f"Error getting cleanup summary: {str(e)}")
        return {"recent_cleanups": [], "total_operations": 0, "error": str(e)}
def get_cleanup_summary_fallback():
    """Fallback cleanup summary when the main function isn't available."""
    try:
        CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
        
        if not os.path.exists(CLEANUP_LOG_PATH):
            return {"recent_cleanups": [], "total_operations": 0}
        
        recent_cleanups = []
        
        # Read the last 50 lines of the cleanup log
        try:
            with open(CLEANUP_LOG_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                
            # Look for cleanup completion messages in the last 50 lines
            for line in reversed(lines[-50:]):
                if "CLEANUP COMPLETED" in line:
                    try:
                        timestamp = line.split(' - ')[0]
                        recent_cleanups.append({
                            "timestamp": timestamp,
                            "type": "Scheduled" if "Scheduled" in line else "Manual",
                            "status": "completed"
                        })
                        
                        if len(recent_cleanups) >= 3:  # Limit to 3 recent cleanups
                            break
                    except:
                        continue
        except Exception as e:
            current_app.logger.debug(f"Could not read cleanup log: {str(e)}")
        
        return {
            "recent_cleanups": recent_cleanups,
            "total_operations": len(recent_cleanups)
        }
        
    except Exception as e:
        current_app.logger.error(f"Error in cleanup summary fallback: {str(e)}")
        return {"recent_cleanups": [], "total_operations": 0, "error": str(e)}
def get_server_activity():
    """Read current viewing details from server webhook stored data."""
    try:
        # First try the standardized filename
        filepath = '/app/temp/data_from_server.json'
        if not os.path.exists(filepath):
            # Fallback to the Tautulli-specific filename for backward compatibility
            filepath = '/app/temp/data_from_tautulli.json'
            
        with open(filepath, 'r') as file:
            data = json.load(file)
        
        # Try server-prefix fields first (standardized format)
        series_title = data.get('server_title')
        season_number = data.get('server_season_num')
        episode_number = data.get('server_ep_num')
        
        # If not found, try plex-prefix fields (backward compatibility)
        if not all([series_title, season_number, episode_number]):
            series_title = data.get('plex_title')
            season_number = data.get('plex_season_num')
            episode_number = data.get('plex_ep_num')
        
        if all([series_title, season_number, episode_number]):
            return series_title, int(season_number), int(episode_number)
            
        logger.error(f"Required data fields not found in {filepath}")
        logger.debug(f"Data contents: {data}")
        
    except Exception as e:
        logger.error(f"Failed to read or parse data from server webhook: {str(e)}")
    
    return None, None, None

def get_series_id(series_name):
    """Fetch series ID by name from Sonarr with improved matching."""
    url = f"{SONARR_URL}/api/v3/series"
    headers = {'X-Api-Key': SONARR_API_KEY}
    try:
        response = requests.get(url, headers=headers)
        if not response.ok:
            logger.error(f"Failed to fetch series from Sonarr: {response.status_code}")
            return None
        
        series_list = response.json()
        
        # 1. Exact match
        for series in series_list:
            if series['title'].lower() == series_name.lower():
                logger.info(f"Found exact match: {series['title']}")
                return series['id']
        
        # 2. Match without year suffixes
        webhook_title_clean = re.sub(r'\s*\(\d{4}\)$', '', series_name).strip()
        for series in series_list:
            sonarr_title_clean = re.sub(r'\s*\(\d{4}\)$', '', series['title']).strip()
            if sonarr_title_clean.lower() == webhook_title_clean.lower():
                logger.info(f"Found match ignoring year: '{series['title']}' matches '{series_name}'")
                return series['id']
        
        # 3. Partial match
        for series in series_list:
            if series_name.lower() in series['title'].lower():
                logger.info(f"Found partial match: '{series['title']}' contains '{series_name}'")
                return series['id']
        
        # 4. Check alternate titles
        for series in series_list:
            alternate_titles = series.get('alternateTitles', [])
            for alt_title in alternate_titles:
                alt_title_text = alt_title.get('title', '')
                if alt_title_text.lower() == series_name.lower():
                    logger.info(f"Found match in alternate title: {series['title']}")
                    return series['id']
        
        # 5. Log close matches for debugging
        close_matches = []
        for series in series_list:
            if series_name.lower() in series['title'].lower():
                close_matches.append(series['title'])
        
        if close_matches:
            missing_logger.info(f"Series not found in Sonarr: '{series_name}'. Possible matches: {close_matches}")
        else:
            missing_logger.info(f"Series not found in Sonarr: '{series_name}'. No close matches.")
        return None
        
    except Exception as e:
        logger.error(f"Error in series lookup: {str(e)}")
        return None


def get_episode_details(series_id, season_number):
    """Fetch details of episodes for a specific series and season from Sonarr."""
    url = f"{SONARR_URL}/api/v3/episode?seriesId={series_id}&seasonNumber={season_number}"
    headers = {'X-Api-Key': SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    if response.ok:
        return response.json()
    logger.error("Failed to fetch episode details.")
    return []

def monitor_or_search_episodes(episode_ids, action_option):
    """Either monitor or trigger a search for episodes in Sonarr based on the action_option."""
    if not episode_ids:
        logger.info("No episodes to monitor/search")
        return
        
    monitor_episodes(episode_ids, True)
    if action_option == "search":
        trigger_episode_search_in_sonarr(episode_ids)

def monitor_episodes(episode_ids, monitor=True):
    """Set episodes to monitored or unmonitored in Sonarr."""
    if not episode_ids:
        return
        
    url = f"{SONARR_URL}/api/v3/episode/monitor"
    headers = {'X-Api-Key': SONARR_API_KEY, 'Content-Type': 'application/json'}
    data = {"episodeIds": episode_ids, "monitored": monitor}
    response = requests.put(url, json=data, headers=headers)
    if response.ok:
        action = "monitored" if monitor else "unmonitored"
        logger.info(f"Episodes {episode_ids} successfully {action}.")
    else:
        logger.error(f"Failed to set episodes {action}. Response: {response.text}")

def trigger_episode_search_in_sonarr(episode_ids):
    """Trigger a search for specified episodes in Sonarr."""
    if not episode_ids:
        return
        
    url = f"{SONARR_URL}/api/v3/command"
    headers = {'X-Api-Key': SONARR_API_KEY, 'Content-Type': 'application/json'}
    data = {"name": "EpisodeSearch", "episodeIds": episode_ids}
    response = requests.post(url, json=data, headers=headers)
    if response.ok:
        logger.info("Episode search command sent to Sonarr successfully.")
    else:
        logger.error(f"Failed to send episode search command. Response: {response.text}")

def unmonitor_episodes(episode_ids):
    """Unmonitor specified episodes in Sonarr."""
    if episode_ids:
        monitor_episodes(episode_ids, False)

def fetch_next_episodes(series_id, season_number, episode_number, get_option):
    """Fetch the next episodes starting from the given season and episode."""
    next_episode_ids = []

    try:
        if get_option == "all":
            # Fetch all episodes from current position forward
            all_episodes = fetch_all_episodes(series_id)
            for ep in all_episodes:
                if (ep['seasonNumber'] > season_number or 
                    (ep['seasonNumber'] == season_number and ep['episodeNumber'] > episode_number)):
                    next_episode_ids.append(ep['id'])
            return next_episode_ids
            
        elif get_option == 'season':
            # Fetch remaining episodes in the current season
            current_season_episodes = get_episode_details(series_id, season_number)
            next_episode_ids.extend([ep['id'] for ep in current_season_episodes if ep['episodeNumber'] > episode_number])
            return next_episode_ids
        else:
            # Treat as number of episodes to get
            num_episodes = int(get_option)
            
            # Get remaining episodes in the current season
            current_season_episodes = get_episode_details(series_id, season_number)
            next_episode_ids.extend([ep['id'] for ep in current_season_episodes if ep['episodeNumber'] > episode_number])

            # Fetch episodes from next seasons if needed
            next_season_number = season_number + 1
            while len(next_episode_ids) < num_episodes:
                next_season_episodes = get_episode_details(series_id, next_season_number)
                if not next_season_episodes:
                    break
                next_episode_ids.extend([ep['id'] for ep in next_season_episodes])
                next_season_number += 1

            return next_episode_ids[:num_episodes]
            
    except ValueError:
        logger.error(f"Invalid get_option value: {get_option}")
        return []

def fetch_all_episodes(series_id):
    """Fetch all episodes for a series from Sonarr."""
    url = f"{SONARR_URL}/api/v3/episode?seriesId={series_id}"
    headers = {'X-Api-Key': SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    if response.ok:
        return response.json()
    logger.error("Failed to fetch all episodes.")
    return []

# fallback dates

def get_tautulli_last_watched(series_title):
    """Get last watched date from Tautulli - OPTIMIZED VERSION."""
    try:
        tautulli_url = os.getenv('TAUTULLI_URL')
        tautulli_api_key = os.getenv('TAUTULLI_API_KEY')
        
        if not tautulli_url or not tautulli_api_key:
            logger.warning(f"Tautulli not configured")
            return None
        
        def normalize_title(title):
            title = title.lower()
            title = re.sub(r'\s*\(\d{4}\)', '', title)  # Remove year
            title = re.sub(r'[^\w\s]', ' ', title)      # Remove special chars
            return ' '.join(title.split())
        
        normalized_series_title = normalize_title(series_title)
        
        # Create smart title variations
        title_variations = [
            series_title,                                    # Original
            re.sub(r'\s*\(\d{4}\)', '', series_title),      # No year
            series_title.replace(": ", " - "),              # Colon variants
            series_title.replace(": ", " "),
            series_title.split(" (")[0],                     # Before parentheses
        ]
        
        # Try each variation (but limit API calls)
        for search_title in set(title_variations[:3]):  # Limit to top 3 variations
            normalized_search = normalize_title(search_title)
            logger.debug(f"Trying Tautulli title: '{search_title}'")
            
            params = {
                'apikey': tautulli_api_key,
                'cmd': 'get_history',
                'media_type': 'episode',
                'search': search_title,
                'length': 1
            }
            
            response = requests.get(f"{tautulli_url}/api/v2", params=params, timeout=10)
            
            if not response.ok:
                logger.warning(f"Tautulli API error: {response.status_code}")
                continue
                
            data = response.json()
            
            if data.get('response', {}).get('result') != 'success':
                continue
            
            history = data.get('response', {}).get('data', {}).get('data', [])
            
            if not history:
                continue
                
            most_recent = history[0]
            entry_title = most_recent.get('grandparent_title', '')
            normalized_entry = normalize_title(entry_title)
            
            # Check if titles match
            if (normalized_entry == normalized_search or 
                normalized_entry in normalized_series_title or 
                normalized_series_title in normalized_entry):
                
                last_watched = most_recent.get('date')
                
                if last_watched:
                    try:
                        timestamp = int(last_watched)
                        logger.info(f"Found Tautulli watch for '{entry_title}': {datetime.fromtimestamp(timestamp)}")
                        return timestamp
                    except (ValueError, TypeError):
                        continue
        
        logger.info(f"No Tautulli watch history found for '{series_title}'")
        return None
        
    except requests.exceptions.Timeout:
        logger.error(f"Tautulli timeout for series '{series_title}'")
        return None
    except Exception as e:
        logger.error(f"Tautulli error for series '{series_title}': {str(e)}")
        return None

def get_jellyfin_user_id(jellyfin_url, jellyfin_api_key, username):
    """Get Jellyfin User ID (GUID) from username."""
    try:
        headers = {'X-Emby-Token': jellyfin_api_key}
        response = requests.get(f"{jellyfin_url}/Users", headers=headers, timeout=10)
        
        if response.ok:
            users = response.json()
            for user in users:
                if user.get('Name', '').lower() == username.lower():
                    user_id = user.get('Id')
                    logger.info(f"Found Jellyfin User ID for '{username}': {user_id}")
                    return user_id
            
            logger.warning(f"Username '{username}' not found in Jellyfin users")
            # Log available usernames for debugging
            available_users = [user.get('Name', 'Unknown') for user in users]
            logger.debug(f"Available Jellyfin users: {available_users}")
        else:
            logger.warning(f"Failed to get Jellyfin users: {response.status_code}")
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting Jellyfin User ID: {str(e)}")
        return None

def get_jellyfin_last_watched(series_title):
    """Get last watched date from Jellyfin - FIXED USER ID VERSION."""
    try:
        jellyfin_url = os.getenv('JELLYFIN_URL')
        jellyfin_api_key = os.getenv('JELLYFIN_API_KEY')
        jellyfin_user_input = os.getenv('JELLYFIN_USER_ID')  # Could be username or GUID
        
        if not all([jellyfin_url, jellyfin_api_key, jellyfin_user_input]):
            logger.warning("Jellyfin not configured")
            return None
        
        # Check if the user input is already a GUID (contains hyphens) or a username
        if '-' in jellyfin_user_input and len(jellyfin_user_input) > 30:
            # Looks like a GUID already
            jellyfin_user_id = jellyfin_user_input
            logger.debug(f"Using provided GUID: {jellyfin_user_id}")
        else:
            # Looks like a username, convert to GUID
            logger.debug(f"Converting username '{jellyfin_user_input}' to User ID")
            jellyfin_user_id = get_jellyfin_user_id(jellyfin_url, jellyfin_api_key, jellyfin_user_input)
            
            if not jellyfin_user_id:
                logger.warning(f"Could not find User ID for username '{jellyfin_user_input}'")
                return None
        
        def normalize_title(title):
            title = title.lower()
            title = re.sub(r'\s*\(\d{4}\)', '', title)  # Remove year
            title = re.sub(r'[^\w\s]', ' ', title)      # Remove special chars
            return ' '.join(title.split())
        
        headers = {'X-Emby-Token': jellyfin_api_key}
        
        # Use the correct Jellyfin API endpoint with proper User ID
        params = {
            'IncludeItemTypes': 'Series',
            'Recursive': 'true',
            'Fields': 'UserData'
        }
        
        # Try the user-specific endpoint with the GUID
        response = requests.get(f"{jellyfin_url}/Users/{jellyfin_user_id}/Items", 
                              headers=headers, params=params, timeout=10)
        
        if not response.ok:
            logger.warning(f"Jellyfin API error: {response.status_code} - {response.text[:200]}")
            return None
            
        data = response.json()
        items = data.get('Items', [])
        logger.debug(f"Jellyfin found {len(items)} series for user {jellyfin_user_input}")
        
        normalized_series_title = normalize_title(series_title)
        
        for item in items:
            item_name = item.get('Name', '')
            normalized_item = normalize_title(item_name)
            
            # Check for title match with flexible matching
            if (normalized_series_title == normalized_item or
                normalized_series_title in normalized_item or 
                normalized_item in normalized_series_title):
                
                logger.debug(f"Matched Jellyfin series: '{item_name}'")
                
                user_data = item.get('UserData', {})
                last_played = user_data.get('LastPlayedDate')
                
                if last_played:
                    try:
                        # Handle Jellyfin's ISO date format
                        if last_played.endswith('Z'):
                            dt = datetime.fromisoformat(last_played.replace('Z', '+00:00'))
                        else:
                            dt = datetime.fromisoformat(last_played)
                        
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                            
                        timestamp = int(dt.timestamp())
                        logger.info(f"Found Jellyfin LastPlayedDate for '{item_name}': {dt}")
                        return timestamp
                        
                    except ValueError as e:
                        logger.warning(f"Invalid Jellyfin LastPlayedDate format: {last_played} - {e}")
                        continue
        
        logger.info(f"No Jellyfin watch history found for '{series_title}'")
        return None
        
    except requests.exceptions.Timeout:
        logger.error(f"Jellyfin timeout for series '{series_title}'")
        return None
    except Exception as e:
        logger.error(f"Jellyfin error for series '{series_title}': {str(e)}")
        return None

def get_sonarr_latest_file_date(series_id):
    """Get the most recent episode file date from Sonarr - FIXED VERSION."""
    try:
        headers = {'X-Api-Key': SONARR_API_KEY}
        logger.info(f"Getting episode file dates for series {series_id}")
        
        # Use the correct endpoint for episode files
        response = requests.get(f"{SONARR_URL}/api/v3/episodefile?seriesId={series_id}", headers=headers, timeout=10)
        
        if not response.ok:
            logger.error(f"Failed to get episode files for series {series_id}: {response.status_code}")
            return None
        
        episode_files = response.json()
        logger.debug(f"Sonarr found {len(episode_files)} episode files")
        
        if not episode_files:
            logger.warning(f"No episode files found for series {series_id}")
            return None
        
        latest_file_date = None
        latest_episode_info = None
        
        for file_data in episode_files:
            season = file_data.get('seasonNumber')
            
            # Get episode numbers from the episodes array
            episodes = file_data.get('episodes', [])
            if episodes:
                episode_numbers = [ep.get('episodeNumber') for ep in episodes]
                ep_display = f"E{min(episode_numbers)}" if episode_numbers else "E?"
            else:
                ep_display = "E?"
            
            date_added_str = file_data.get('dateAdded')
            logger.debug(f"S{season}{ep_display}: dateAdded = '{date_added_str}'")
            
            if not date_added_str:
                logger.warning(f"Missing dateAdded for S{season}{ep_display}")
                continue
            
            timestamp = parse_date_fixed(date_added_str, f"S{season}{ep_display}")
            
            if timestamp:
                if not latest_file_date or timestamp > latest_file_date:
                    latest_file_date = timestamp
                    latest_episode_info = f"S{season}{ep_display}"
            else:
                logger.error(f"Failed to parse dateAdded for S{season}{ep_display}: '{date_added_str}'")
        
        if latest_file_date:
            logger.info(f"Latest file: {latest_episode_info} at {datetime.fromtimestamp(latest_file_date, tz=timezone.utc)} UTC")
            return latest_file_date
        else:
            logger.warning(f"No valid episode file dates found for series {series_id}")
            return None
            
    except requests.exceptions.Timeout:
        logger.error(f"Sonarr timeout for series {series_id}")
        return None
    except Exception as e:
        logger.error(f"Sonarr error for series {series_id}: {str(e)}")
        return None

def parse_date_fixed(date_str, context):
    """Parse date string with multiple formats - FIXED VERSION."""
    try:
        # Method 1: Handle Z suffix (UTC)
        if date_str.endswith('Z'):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            timestamp = int(dt.timestamp())
            logger.debug(f"Parsed {context} ISO+Z: {timestamp} ({dt})")
            return timestamp
        
        # Method 2: Try direct ISO parsing
        try:
            dt = datetime.fromisoformat(date_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            timestamp = int(dt.timestamp())
            logger.debug(f"Parsed {context} ISO: {timestamp} ({dt})")
            return timestamp
        except ValueError:
            pass
        
        # Method 3: Strip milliseconds and try again
        if '.' in date_str:
            clean_date = re.sub(r'\.\d+', '', date_str)
            if clean_date.endswith('Z'):
                clean_date = clean_date.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(clean_date)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                timestamp = int(dt.timestamp())
                logger.debug(f"Parsed {context} no-ms: {timestamp} ({dt})")
                return timestamp
            except ValueError:
                pass
        
        logger.error(f"Could not parse date for {context}: '{date_str}'")
        return None
        
    except Exception as e:
        logger.error(f"Date parse error for {context}: {str(e)}")
        return None

def parse_date(date_str, context):
    """Parse date string with multiple formats."""
    try:
        timestamp = None
        # ISO with Z
        if date_str.endswith('Z'):
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00')).replace(tzinfo=timezone.utc)
            timestamp = int(dt.timestamp())
            print(f"   🔍 Parsed {context} ISO+Z: {timestamp} ({dt})")
            logger.info(f"Parsed {context} ISO+Z: {timestamp} ({dt})")
        # Direct ISO
        if not timestamp:
            try:
                dt = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
                timestamp = int(dt.timestamp())
                print(f"   🔍 Parsed {context} ISO: {timestamp} ({dt})")
                logger.info(f"Parsed {context} ISO: {timestamp} ({dt})")
            except ValueError:
                pass
        # Strip milliseconds
        if not timestamp and '.' in date_str:
            clean_date = re.sub(r'\.\d+', '', date_str)
            if clean_date.endswith('Z'):
                clean_date = clean_date.replace('Z', '+00:00')
            try:
                dt = datetime.fromisoformat(clean_date).replace(tzinfo=timezone.utc)
                timestamp = int(dt.timestamp())
                print(f"   🔍 Parsed {context} no-ms: {timestamp} ({dt})")
                logger.info(f"Parsed {context} no-ms: {timestamp} ({dt})")
            except ValueError:
                pass
        if timestamp:
            return timestamp
        return None
    except Exception as e:
        print(f"   ❌ Date parse error for {context}: {str(e)}")
        logger.error(f"Date parse error for {context}: {str(e)}")
        return None

def get_baseline_date(series_id, series_title=None):
    """
    Get baseline date using hierarchy:
    1. Episeerr JSON activity tracking (most accurate recent activity)
    2. Tautulli last watch date (historical watch data)
    3. Jellyfin last watch date (historical watch data)
    4. Sonarr latest episode file date (when content was acquired)
    """
    
    activity_data = load_activity_tracking()
    series_id_str = str(series_id)
    
    print(f"\n🔍 Getting baseline date for series {series_id} ({series_title})")
    
    # 1. FIRST: Check Episeerr JSON activity tracking
    if series_id_str in activity_data:
        last_watched = activity_data[series_id_str].get('last_watched', 0)
        if last_watched > 0:
            print(f"✅ STEP 1: Using Episeerr JSON date: {last_watched}")
            print(f"   📆 Date: {datetime.fromtimestamp(last_watched)}")
            return last_watched
    
    print(f"⚠️  STEP 1: No Episeerr JSON data found")
    
    # 2. SECOND: Check Tautulli for historical watch data
    if series_title:
        print(f"🔍 STEP 2: Checking Tautulli for '{series_title}'")
        tautulli_date = get_tautulli_last_watched(series_title)
        if tautulli_date:
            print(f"✅ STEP 2: Using Tautulli date: {tautulli_date}")
            print(f"   📆 Date: {datetime.fromtimestamp(tautulli_date)}")
            return tautulli_date
        else:
            print(f"⚠️  STEP 2: No Tautulli data found")
    else:
        print(f"⚠️  STEP 2: No series title for Tautulli lookup")
    
    # 3. THIRD: Check Jellyfin for historical watch data
    if series_title:
        print(f"🔍 STEP 3: Checking Jellyfin for '{series_title}'")
        jellyfin_date = get_jellyfin_last_watched(series_title)
        if jellyfin_date:
            print(f"✅ STEP 3: Using Jellyfin date: {jellyfin_date}")
            print(f"   📆 Date: {datetime.fromtimestamp(jellyfin_date)}")
            return jellyfin_date
        else:
            print(f"⚠️  STEP 3: No Jellyfin data found")
    else:
        print(f"⚠️  STEP 3: No series title for Jellyfin lookup")
    
    # 4. FOURTH: Check Sonarr episode file dates (when content was acquired)
    print(f"🔍 STEP 4: Checking Sonarr file dates")
    sonarr_date = get_sonarr_latest_file_date(series_id)
    if sonarr_date:
        print(f"✅ STEP 4: Using Sonarr file date: {sonarr_date}")
        print(f"   📆 Date: {datetime.fromtimestamp(sonarr_date)}")
        return sonarr_date
    else:
        print(f"⚠️  STEP 4: No Sonarr file dates found")
    
    # 5. NO FALLBACK: Return None if no date is found
    print(f"⚠️  STEP 5: No valid date found, skipping")
    return None




# =============================================================================
# WEBHOOK PROCESSING - ACTIVITY TRACKING + NEXT CONTENT ONLY
# =============================================================================




def process_episodes_for_webhook(series_id, season_number, episode_number, rule):
    """
    WEBHOOK PROCESSING: Update activity + Get next episodes + Delete old episodes (RESTORED).
    This restores the original two-layer behavior where webhooks handle immediate management.
    """
    try:
        logger.info(f"Processing webhook for series {series_id}: S{season_number}E{episode_number}")
        
        # 1. Update activity date in config (will call the new function when we create it)
        update_activity_date(series_id, season_number, episode_number)
        
        # 2. Get current episode and unmonitor if needed
        all_episodes = fetch_all_episodes(series_id)
        current_episode = next(
            (ep for ep in all_episodes 
             if ep['seasonNumber'] == season_number and ep['episodeNumber'] == episode_number), 
            None
        )
        
        if not current_episode:
            logger.error(f"Could not find current episode S{season_number}E{episode_number}")
            return
            
        current_episode_id = current_episode['id']
        
        # Unmonitor current episode if rule says so
        if not rule.get('monitor_watched', True):
            unmonitor_episodes([current_episode_id])
            logger.info(f"Unmonitored current episode S{season_number}E{episode_number}")
        
        # 3. Get next episodes based on get_option
        next_episode_ids = fetch_next_episodes(series_id, season_number, episode_number, rule['get_option'])
        
        if next_episode_ids:
            # Monitor next episodes
            monitor_or_search_episodes(next_episode_ids, rule.get('action_option', 'monitor'))
            logger.info(f"Processed {len(next_episode_ids)} next episodes with action: {rule.get('action_option', 'monitor')}")
        else:
            logger.info("No next episodes to process")
        
        # 4. IMMEDIATE DELETION - Delete episodes before keep block (RESTORED ORIGINAL LOGIC)
        episodes_to_delete = find_episodes_to_delete_immediate(
            all_episodes, rule['keep_watched'], season_number, episode_number
        )
        
        if episodes_to_delete:
            delete_episodes_in_sonarr_with_logging(episodes_to_delete, False, "Series Name")
            logger.info(f"Immediate deletion: removed {len(episodes_to_delete)} episode files")
        else:
            logger.info("Immediate deletion: no episodes to delete")
            
        logger.info(f"Webhook processing complete for series {series_id}")
        
    except Exception as e:
        logger.error(f"Error in webhook processing for series {series_id}: {str(e)}", exc_info=True)

# =============================================================================
# SCHEDULER PROCESSING - ALL CLEANUP LOGIC
# =============================================================================

def check_time_based_cleanup(series_id, rule):
    """Check if time-based cleanup should be performed - OPTIMIZED VERSION."""
    try:
        grace_days = rule.get('grace_days')
        dormant_days = rule.get('dormant_days')
        
        if not grace_days and not dormant_days:
            return False, "No time-based cleanup configured"
        
        # Get series title for external API lookups (only once)
        series_title = None
        try:
            headers = {'X-Api-Key': SONARR_API_KEY}
            response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers, timeout=5)
            if response.ok:
                series_title = response.json().get('title')
        except Exception as e:
            logger.warning(f"Failed to get series title: {str(e)}")
        
        # Get activity date using hierarchy (this calls the fixed function above)
        activity_date = get_activity_date_with_hierarchy(series_id, series_title)
        
        if activity_date is None:
            logger.info(f"Series {series_id}: No activity date found, skipping cleanup")
            return False, "No activity date available"
        
        current_time = int(time.time())
        days_since_activity = (current_time - activity_date) / (24 * 60 * 60)
        
        logger.info(f"Series {series_id} activity check: {days_since_activity:.1f} days since last activity")
        
        # Check dormant cleanup first (most aggressive)
        if dormant_days and days_since_activity > dormant_days:
            return True, f"Dormant cleanup: {days_since_activity:.1f} days > {dormant_days} days"
        
        # Check grace period cleanup  
        if grace_days and days_since_activity > grace_days:
            return True, f"Grace cleanup: {days_since_activity:.1f} days > {grace_days} days"
        
        return False, f"Time thresholds not met ({days_since_activity:.1f} days since activity)"
        
    except Exception as e:
        logger.error(f"Error in time-based cleanup check: {str(e)}")
        return False, f"Error: {str(e)}"
    
def migrate_existing_series_to_tracking():
    """
    One-time migration to add rule_assigned_date for existing series.
    Call this once to backfill assignment dates for series already in rules.
    """
    try:
        config_path = os.path.join(os.getcwd(), 'config', 'config.json')
        with open(config_path, 'r') as file:
            config = json.load(file)
       
        activity_data = load_activity_tracking()
        current_time = int(time.time())
        migrated_count = 0
       
        for rule_name, rule_details in config.get('rules', {}).items():
            series_dict = rule_details.get('series', {})
            
            # Handle both old array format and new dict format
            if isinstance(series_dict, list):
                # Old format - convert to dict first
                series_ids = series_dict
            else:
                # New format - get the keys
                series_ids = series_dict.keys()
            
            for series_id in series_ids:
                series_id_str = str(series_id)
               
                if series_id_str not in activity_data:
                    activity_data[series_id_str] = {}
               
                # Only add rule_assigned_date if it doesn't exist
                if 'rule_assigned_date' not in activity_data[series_id_str]:
                    activity_data[series_id_str]['rule_assigned_date'] = current_time
                    activity_data[series_id_str]['current_rule'] = rule_name
                    activity_data[series_id_str]['last_updated'] = current_time
                   
                    # Ensure last_watched exists
                    if 'last_watched' not in activity_data[series_id_str]:
                        activity_data[series_id_str]['last_watched'] = 0
                   
                    migrated_count += 1
                    logger.info(f"Migrated series {series_id} in rule '{rule_name}' with assignment date {current_time}")
       
        if migrated_count > 0:
            save_activity_tracking(activity_data)
            logger.info(f"Migration completed: Added assignment dates for {migrated_count} existing series")
        else:
            logger.info("Migration completed: No series needed assignment date updates")
           
    except Exception as e:
        logger.error(f"Error during migration: {str(e)}")



def find_episodes_to_delete_surgical(all_episodes, keep_watched, last_watched_season, last_watched_episode):
    """
    SURGICAL CLEANUP: Delete episodes before the keep block, preserve the block itself.
    This maintains a buffer of recent episodes while cleaning up old ones.
    """
    episodes_to_delete = []
    
    try:
        if keep_watched == "all":
            logger.info("Surgical cleanup: keep_watched is 'all', no episodes to delete")
            return []
            
        elif keep_watched == "season":
            # Keep the entire last watched season, delete previous seasons
            logger.info(f"Surgical cleanup: keeping entire season {last_watched_season}")
            episodes_to_delete = [
                ep for ep in all_episodes 
                if ep['seasonNumber'] < last_watched_season and ep['hasFile']
            ]
            
        else:
            try:
                # Keep a specific number of episodes as a block
                keep_count = int(keep_watched)
                logger.info(f"Surgical cleanup: keeping block of {keep_count} episodes")
                
                # Sort episodes by season/episode number
                sorted_episodes = sorted(
                    all_episodes, 
                    key=lambda ep: (ep['seasonNumber'], ep['episodeNumber'])
                )
                
                # Find the last watched episode index
                last_watched_index = None
                for i, ep in enumerate(sorted_episodes):
                    if (ep['seasonNumber'] == last_watched_season and 
                        ep['episodeNumber'] == last_watched_episode):
                        last_watched_index = i
                        break
                
                if last_watched_index is not None:
                    # Define the keep block: keep_count episodes ending with last watched
                    keep_start_index = max(0, last_watched_index - keep_count + 1)
                    keep_end_index = last_watched_index
                    
                    # Episodes before the keep block are candidates for deletion
                    episodes_with_files = [ep for ep in sorted_episodes if ep['hasFile']]
                    
                    for ep in episodes_with_files:
                        ep_index = next(
                            (i for i, se in enumerate(sorted_episodes) if se['id'] == ep['id']), 
                            None
                        )
                        if ep_index is not None and ep_index < keep_start_index:
                            episodes_to_delete.append(ep)
                    
                    logger.info(f"Keep block: episodes {keep_start_index} to {keep_end_index}, deleting {len(episodes_to_delete)} episodes before block")
                else:
                    logger.warning("Could not find last watched episode for surgical cleanup")
                    
            except (ValueError, TypeError):
                logger.warning(f"Invalid keep_watched value for surgical cleanup: {keep_watched}")
                return []
        
        return [ep['episodeFileId'] for ep in episodes_to_delete if 'episodeFileId' in ep]
        
    except Exception as e:
        logger.error(f"Error in surgical cleanup: {str(e)}")
        return []

def find_episodes_to_delete_nuclear(all_episodes, keep_watched):
    """
    NUCLEAR CLEANUP: Delete everything or most things based on abandonment.
    This is for series that haven't been watched in a very long time.
    """
    episodes_to_delete = []
    
    try:
        if keep_watched == "all":
            # Delete everything - complete abandonment
            episodes_to_delete = [ep for ep in all_episodes if ep['hasFile']]
            logger.info(f"Nuclear cleanup: deleting ALL {len(episodes_to_delete)} episodes")
            
        elif keep_watched == "season":
            # Delete all seasons - complete abandonment
            episodes_to_delete = [ep for ep in all_episodes if ep['hasFile']]
            logger.info(f"Nuclear cleanup: deleting ALL seasons ({len(episodes_to_delete)} episodes)")
            
        else:
            try:
                # Delete everything except the last N episodes (minimal preservation)
                keep_count = int(keep_watched)
                
                # Sort episodes by season/episode number (oldest first for deletion)
                sorted_episodes = sorted(
                    all_episodes, 
                    key=lambda ep: (ep['seasonNumber'], ep['episodeNumber'])
                )
                episodes_with_files = [ep for ep in sorted_episodes if ep['hasFile']]
                
                if len(episodes_with_files) > keep_count:
                    episodes_to_delete = episodes_with_files[:-keep_count] if keep_count > 0 else episodes_with_files
                    logger.info(f"Nuclear cleanup: deleting {len(episodes_to_delete)} episodes, keeping last {keep_count}")
                else:
                    logger.info(f"Nuclear cleanup: only {len(episodes_with_files)} episodes available, keeping all")
                
            except (ValueError, TypeError):
                logger.warning(f"Invalid keep_watched value for nuclear cleanup: {keep_watched}")
                return []
        
        return [ep['episodeFileId'] for ep in episodes_to_delete if 'episodeFileId' in ep]
        
    except Exception as e:
        logger.error(f"Error in nuclear cleanup: {str(e)}")
        return []

def is_dry_run_enabled(rule_name=None):
    """Check if dry run is enabled (simplified version)."""
    # Check environment variable first
    if os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true':
        return True
    
    # Check rule-specific setting (you'll need to implement this based on your setup)
    # For now, return False
    return False

def delete_episodes_in_sonarr_with_logging(episode_file_ids, dry_run, series_title):
    """Delete episodes with detailed logging."""
    if not episode_file_ids:
        return

    if dry_run:
        print(f"🔍 DRY RUN: Would delete {len(episode_file_ids)} episode files from {series_title}")
        print(f"🔍 DRY RUN: Episode file IDs: {episode_file_ids[:5]}{'...' if len(episode_file_ids) > 5 else ''}")
        return

    # Live deletion with detailed logging
    print(f"🗑️  DELETING: {len(episode_file_ids)} episode files from {series_title}")
    
    headers = {'X-Api-Key': SONARR_API_KEY}
    successful_deletes = 0
    failed_deletes = []
    
    for episode_file_id in episode_file_ids:
        try:
            url = f"{SONARR_URL}/api/v3/episodeFile/{episode_file_id}"
            response = requests.delete(url, headers=headers)
            response.raise_for_status()
            successful_deletes += 1
            print(f"✅ Deleted episode file ID: {episode_file_id}")
        except Exception as err:
            failed_deletes.append(episode_file_id)
            print(f"❌ Failed to delete episode file {episode_file_id}: {err}")

    print(f"📊 Deletion summary: {successful_deletes} successful, {len(failed_deletes)} failed")
    if failed_deletes:
        print(f"❌ Failed deletes: {failed_deletes}")

# Add this helper function to check dry run status
def is_dry_run_enabled(rule_name=None):
    """Check if dry run is enabled (simplified version)."""
    # Check environment variable first
    if os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true':
        return True
    
    # Check rule-specific setting (you'll need to implement this based on your setup)
    # For now, return False
    return False

def perform_time_based_cleanup_with_logging(series_id, series_title, rule, cleanup_reason):
    """Perform cleanup with detailed logging of what gets deleted."""
    try:
        # Check if dry run mode
        dry_run = is_dry_run_enabled(rule.get('rule_name') if hasattr(rule, 'rule_name') else None)
        mode = "🔍 DRY RUN" if dry_run else "🗑️  LIVE MODE"
        
        print(f"\n{mode}: Starting cleanup for {series_title}")
        print(f"📋 Reason: {cleanup_reason}")
        
        all_episodes = fetch_all_episodes(series_id)
        keep_watched = rule.get('keep_watched', 'all')
        
        # Get activity data for surgical cleanup decisions
        activity_data = load_activity_tracking()
        series_activity = activity_data.get(str(series_id), {})
        last_watched_season = series_activity.get('last_season', 1)
        last_watched_episode = series_activity.get('last_episode', 1)
        
        # Determine cleanup type and get episodes to delete
        if "Nuclear cleanup" in cleanup_reason:
            episodes_to_delete = find_episodes_to_delete_nuclear(all_episodes, keep_watched)
            cleanup_type = "☢️  NUCLEAR"
            print(f"{cleanup_type}: Complete removal based on inactivity")
        else:
            episodes_to_delete = find_episodes_to_delete_surgical(
                all_episodes, keep_watched, last_watched_season, last_watched_episode
            )
            cleanup_type = "🔪 SURGICAL"
            print(f"{cleanup_type}: Selective cleanup, last watched S{last_watched_season}E{last_watched_episode}")
        
        if episodes_to_delete:
            print(f"📊 Episodes to delete: {len(episodes_to_delete)}")
            
            # Get details about what's being deleted
            headers = {'X-Api-Key': SONARR_API_KEY}
            deleted_details = []
            
            for episode_file_id in episodes_to_delete[:10]:  # Show details for first 10
                try:
                    response = requests.get(f"{SONARR_URL}/api/v3/episodeFile/{episode_file_id}", headers=headers)
                    if response.ok:
                        file_info = response.json()
                        season = file_info.get('seasonNumber')
                        episode_numbers = [ep.get('episodeNumber') for ep in file_info.get('episodes', [])]
                        
                        if episode_numbers:
                            episodes_str = ', '.join([f"E{ep}" for ep in sorted(episode_numbers)])
                            deleted_details.append(f"S{season}{episodes_str}")
                except:
                    continue
            
            if deleted_details:
                print(f"📺 Episodes being deleted: {', '.join(deleted_details)}")
                if len(episodes_to_delete) > 10:
                    print(f"   ... and {len(episodes_to_delete) - 10} more")
            
            # Perform the deletion (or dry run)
            delete_episodes_in_sonarr_with_logging(episodes_to_delete, dry_run, series_title)
        else:
            print("✅ No episodes need to be deleted")
            
    except Exception as e:
        print(f"❌ Error in cleanup for {series_title}: {str(e)}")


def log_cleanup_start(series_count, cleanup_type="Scheduled"):
    """Log the start of a cleanup operation."""
    cleanup_logger.info("=" * 80)
    cleanup_logger.info(f"🚀 {cleanup_type} CLEANUP STARTED")
    cleanup_logger.info(f"📊 Checking {series_count} series for time-based cleanup")
    cleanup_logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    cleanup_logger.info(f"🔧 Dry run mode: {os.getenv('CLEANUP_DRY_RUN', 'false').upper()}")
    cleanup_logger.info("=" * 80)

def log_cleanup_end(processed_count, deleted_count, cleanup_type="Scheduled"):
    """Log the completion of a cleanup operation."""
    cleanup_logger.info("=" * 80)
    cleanup_logger.info(f"✅ {cleanup_type} CLEANUP COMPLETED")
    cleanup_logger.info(f"📊 Processed {processed_count} series")
    cleanup_logger.info(f"🗑️  Cleaned up {deleted_count} series")
    cleanup_logger.info(f"⏰ Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    cleanup_logger.info("=" * 80)

def log_series_cleanup(series_id, series_title, cleanup_reason, episodes_deleted, dry_run=False):
    """Log individual series cleanup details."""
    mode = "DRY RUN" if dry_run else "LIVE"
    action = "would delete" if dry_run else "deleted"
    
    cleanup_logger.info(f"📺 [{mode}] {series_title} (ID: {series_id})")
    cleanup_logger.info(f"   📋 Reason: {cleanup_reason}")
    cleanup_logger.info(f"   🗑️  {action.title()} {episodes_deleted} episode files")

def log_series_skip(series_id, series_title, reason):
    """Log when a series is skipped from cleanup."""
    cleanup_logger.info(f"⏭️  SKIPPED: {series_title} (ID: {series_id}) - {reason}")

# Enhanced cleanup function with better logging
def run_periodic_cleanup():
    """Enhanced periodic cleanup with detailed logging."""
    try:
        print("=" * 80)
        print("🚀 STARTING PERIODIC CLEANUP")
        cleanup_logger.info("🚀 STARTING PERIODIC CLEANUP")  # Added as requested
        
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cleanup_logger.info(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")  # Added as requested
       
        # Get all series from Sonarr
        url = f"{SONARR_URL}/api/v3/series"
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(url, headers=headers)
        
        if not response.ok:
            print("❌ Failed to fetch series from Sonarr for cleanup")
            cleanup_logger.error("Failed to fetch series from Sonarr")
            return
        
        all_series = response.json()
        series_with_time_rules = []
        
        # Collect all series with time-based rules
        config = load_config()
        print(f"📊 Checking {len(config['rules'])} rules for time-based cleanup settings...")
        
        for rule_name, rule in config['rules'].items():
            if rule.get('grace_days') or rule.get('dormant_days'):  # NEW FIELD NAMES
                print(f"📋 Rule '{rule_name}' has time-based cleanup:")
                print(f"   ⏳ Grace period: {rule.get('grace_days', 'None')} days")  # NEW FIELD NAME
                print(f"   🔄 Dormant timer: {rule.get('dormant_days', 'None')} days")  # NEW FIELD NAME
                
                series_dict = rule.get('series', {})  # NOW IT'S A DICT
                print(f"   🎯 Assigned series: {len(series_dict)}")
                
                for series_id_str, series_data in series_dict.items():  # ITERATE DICT ITEMS
                    try:
                        series_id = int(series_id_str)
                        series_info = next((s for s in all_series if s['id'] == series_id), None)
                        if series_info:
                            series_with_time_rules.append({
                                'id': series_id,
                                'title': series_info['title'],
                                'rule': rule,
                                'rule_name': rule_name
                            })
                            print(f"   📺 {series_info['title']} (ID: {series_id})")
                        else:
                            print(f"   ⚠️  Series ID {series_id} not found in Sonarr")
                            cleanup_logger.warning(f"Series ID {series_id} not found in Sonarr")
                    except ValueError:
                        print(f"   ❌ Invalid series ID: '{series_id_str}'")
                        cleanup_logger.error(f"Invalid series ID: '{series_id_str}'")
            else:
                print(f"📋 Rule '{rule_name}': No time-based cleanup (skipping)")
        
        if not series_with_time_rules:
            print("ℹ️  No series with time-based cleanup rules found")
            print("=" * 80)
            cleanup_logger.info("No series with time-based cleanup rules found")
            return
        
        print(f"\n🔍 EVALUATING {len(series_with_time_rules)} SERIES FOR CLEANUP")
        print("=" * 80)
        
        processed_count = 0
        cleaned_count = 0
        
        for series_info in series_with_time_rules:
            try:
                series_id = series_info['id']
                series_title = series_info['title']
                rule = series_info['rule']
                rule_name = series_info['rule_name']
                
                processed_count += 1
                
                # Check block added at the start of the cleanup loop, as requested
                print(f"\n🎯 CHECKING: {series_title} (ID: {series_id})")
                print(f"📋 Rule: {rule_name}")
                cleanup_logger.info(f"Checking series: {series_title} (ID: {series_id}) with rule: {rule_name}")
                
                # Quick check: Skip series with no files
                all_episodes = fetch_all_episodes(series_id)
                episodes_with_files = [ep for ep in all_episodes if ep.get('hasFile', False)]
                
                if not episodes_with_files:
                    print(f"⏭️  SKIPPED: No episode files found - nothing to clean up")
                    cleanup_logger.info(f"Skipped {series_title}: No episode files found")
                    continue
                
                print(f"📊 Found {len(episodes_with_files)} episodes with files")
                cleanup_logger.info(f"Found {len(episodes_with_files)} episodes with files for {series_title}")
                
                # Check if cleanup should be performed
                should_cleanup, reason = check_time_based_cleanup(series_id, rule)
                
                if should_cleanup:
                    print(f"✅ CLEANUP TRIGGERED: {reason}")
                    cleanup_logger.info(f"Cleanup triggered for {series_title}: {reason}")
                    
                    # Perform the cleanup with detailed logging
                    perform_time_based_cleanup_with_logging(series_id, series_title, rule, reason)
                    cleaned_count += 1
                    
                else:
                    print(f"⏭️  SKIPPED: {reason}")
                    cleanup_logger.info(f"Skipped {series_title}: {reason}")
                
            except Exception as e:
                print(f"❌ ERROR processing '{series_info.get('title', 'Unknown')}': {str(e)}")
                cleanup_logger.error(f"Error processing '{series_info.get('title', 'Unknown')}': {str(e)}")
        
        print("\n" + "=" * 80)
        print("✅ CLEANUP COMPLETED")
        print(f"📊 Processed: {processed_count} series")
        print(f"🗑️  Cleaned: {cleaned_count} series")
        print(f"⏰ Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        cleanup_logger.info(f"Cleanup completed: Processed {processed_count} series, cleaned {cleaned_count} series")
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Critical error in periodic cleanup: {str(e)}")
        cleanup_logger.error(f"Critical error in periodic cleanup: {str(e)}")



# =============================================================================
# LEGACY FUNCTIONS - KEPT FOR NEW SERIES PROCESSING
# =============================================================================

def process_new_series_from_watchlist(series_id, rule):
    """
    Process a newly added series from watchlist based on rule parameters.
    """
    # Fetch all episodes for the series
    all_episodes = fetch_all_episodes(series_id)
    
    # Sort first season episodes by episode number
    first_season_episodes = sorted(
        [ep for ep in all_episodes if ep['seasonNumber'] == 1], 
        key=lambda x: x['episodeNumber']
    )
    
    # Select episodes based on get_option
    if rule['get_option'] == 'all':
        # All episodes in the first season
        episode_ids = [ep['id'] for ep in first_season_episodes]
    
    elif rule['get_option'] == 'season':
        # All episodes in the first season
        episode_ids = [ep['id'] for ep in first_season_episodes]
    
    else:
        try:
            # Treat as number of episodes to get
            num_episodes = int(rule['get_option'])
            episode_ids = [ep['id'] for ep in first_season_episodes[:num_episodes]]
        except ValueError:
            # Fallback to first episode if invalid input
            episode_ids = [first_season_episodes[0]['id']] if first_season_episodes else []
    
    # Monitor or search selected episodes
    if episode_ids:
        monitor_or_search_episodes(episode_ids, rule['action_option'])
    
    return episode_ids

# =============================================================================
# MAIN ENTRY POINTS
# =============================================================================

def main():
    """Main entry point - handles both webhook and periodic cleanup."""
    series_name, season_number, episode_number = get_server_activity()
    
    if series_name:
        # WEBHOOK MODE - Process watched episode
        series_id = get_series_id(series_name)
        if series_id:
            config = load_config()
            
            # Find the rule for this series (NEW DICT STRUCTURE)
            rule = None
            for rule_name, rule_details in config['rules'].items():
                series_dict = rule_details.get('series', {})  # Now it's a dict
                if str(series_id) in series_dict:  # Check if series ID is a key
                    rule = rule_details
                    break
            
            if rule:
                logger.info(f"Applying webhook rule for series {series_id}")
                process_episodes_for_webhook(series_id, season_number, episode_number, rule)
            else:
                logger.info(f"No rule found for series ID {series_id}. Only updating activity.")
                update_activity_date(series_id, season_number, episode_number)  
        else:
            logger.error(f"Series ID not found for series: {series_name}")
    else:
        # SCHEDULER MODE - Run periodic cleanup
        logger.info("No server activity found - running periodic cleanup")
        run_periodic_cleanup()

if __name__ == "__main__":
    main()
