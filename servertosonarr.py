import os
import requests
import logging
from logging.handlers import RotatingFileHandler
import json
import time
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Define log paths
LOG_PATH = os.getenv('LOG_PATH', '/app/logs/app.log')
MISSING_LOG_PATH = os.getenv('MISSING_LOG_PATH', '/app/logs/missing.log')

# Configure logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()  # Optional: adds console logging
    ]
)

# Create loggers
logger = logging.getLogger(__name__)
missing_logger = logging.getLogger('missing')

# Add file handler for missing logger
missing_handler = logging.FileHandler(MISSING_LOG_PATH)
missing_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
missing_logger.addHandler(missing_handler)

# Load settings from a JSON configuration file
def load_config():
    config_path = os.getenv('CONFIG_PATH', '/app/config/config.json')
    with open(config_path, 'r') as file:
        config = json.load(file)
    # Ensure required keys are present with default values
    if 'rules' not in config:
        config['rules'] = {}
    return config

config = load_config()

# Define global variables based on environment settings
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Environment variable for global dry run mode
DRY_RUN_MODE = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'

# Time-based cleanup tracking
ACTIVITY_TRACKING_FILE = os.path.join(os.getcwd(), 'data', 'activity_tracking.json')
os.makedirs(os.path.dirname(ACTIVITY_TRACKING_FILE), exist_ok=True)
# Enhanced logging setup for cleanup operations
def setup_cleanup_logging():
    """Setup cleanup logging to write to BOTH console AND files."""
    
    LOG_PATH = os.getenv('LOG_PATH', '/app/logs/app.log')
    CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
    
    # Ensure log directories exist
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(CLEANUP_LOG_PATH), exist_ok=True)
    
    # Create cleanup-specific logger
    cleanup_logger = logging.getLogger('cleanup')
    cleanup_logger.setLevel(logging.INFO)
    cleanup_logger.handlers.clear()
    
    # File handler for main app log
    main_file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=3,
        encoding='utf-8'
    )
    main_file_handler.setLevel(logging.INFO)
    main_formatter = logging.Formatter('%(asctime)s - CLEANUP - %(levelname)s - %(message)s')
    main_file_handler.setFormatter(main_formatter)
    
    # Dedicated cleanup file handler
    cleanup_file_handler = RotatingFileHandler(
        CLEANUP_LOG_PATH,
        maxBytes=5*1024*1024,  # 5 MB
        backupCount=5,
        encoding='utf-8'
    )
    cleanup_file_handler.setLevel(logging.INFO)
    cleanup_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    cleanup_file_handler.setFormatter(cleanup_formatter)
    
    # Console handler for Docker logs (what you're seeing now)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - CLEANUP - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # Add ALL handlers
    cleanup_logger.addHandler(main_file_handler)
    cleanup_logger.addHandler(cleanup_file_handler)  
    cleanup_logger.addHandler(console_handler)
    
    cleanup_logger.propagate = False
    
    return cleanup_logger

# Initialize cleanup logger
cleanup_logger = setup_cleanup_logging()

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
    """
    Get activity date using hierarchy:
    1. Config.json activity_date
    2. Tautulli last watched 
    3. Jellyfin last watched
    4. Sonarr latest file date
    5. 30-day fallback
    """
    # First check config.json
    config = load_config()
    for rule_name, rule_details in config['rules'].items():
        series_dict = rule_details.get('series', {})
        series_data = series_dict.get(str(series_id))
        if isinstance(series_data, dict):
            activity_date = series_data.get('activity_date')
            if activity_date:
                logger.info(f"Using config activity date for series {series_id}: {datetime.fromtimestamp(activity_date)}")
                return activity_date
    
    logger.info(f"No config activity date for series {series_id}, checking external sources...")
    
    # Check Tautulli
    if series_title:
        tautulli_date = get_tautulli_last_watched(series_title)
        if tautulli_date:
            logger.info(f"Using Tautulli date for series {series_id}: {datetime.fromtimestamp(tautulli_date)}")
            # Update config with this date
            update_activity_date(series_id, timestamp=tautulli_date)
            return tautulli_date
    
    # Check Jellyfin
    if series_title:
        jellyfin_date = get_jellyfin_last_watched(series_title)
        if jellyfin_date:
            logger.info(f"Using Jellyfin date for series {series_id}: {datetime.fromtimestamp(jellyfin_date)}")
            update_activity_date(series_id, timestamp=jellyfin_date)
            return jellyfin_date
    
    # Check Sonarr file dates
    sonarr_date = get_sonarr_latest_file_date(series_id)
    if sonarr_date:
        logger.info(f"Using Sonarr file date for series {series_id}: {datetime.fromtimestamp(sonarr_date)}")
        update_activity_date(series_id, timestamp=sonarr_date)
        return sonarr_date
    
    # Fallback to 30 days ago
    fallback_date = int((datetime.now() - timedelta(days=30)).timestamp())
    logger.info(f"Using 30-day fallback for series {series_id}: {datetime.fromtimestamp(fallback_date)}")
    update_activity_date(series_id, timestamp=fallback_date)
    return fallback_date

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
    """Fetch series ID by name from Sonarr."""
    url = f"{SONARR_URL}/api/v3/series"
    headers = {'X-Api-Key': SONARR_API_KEY}
    response = requests.get(url, headers=headers)
    if response.ok:
        series_list = response.json()
        for series in series_list:
            if series['title'].lower() == series_name.lower():
                return series['id']
        missing_logger.info(f"Series not found in Sonarr: {series_name}")
    else:
        logger.error("Failed to fetch series from Sonarr.")
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
    """Get last watched date from Tautulli for this series - with enhanced debugging."""
    try:
        tautulli_url = os.getenv('TAUTULLI_URL')
        tautulli_api_key = os.getenv('TAUTULLI_API_KEY')
        
        if not tautulli_url or not tautulli_api_key:
            print(f"   ⚠️  Tautulli not configured (URL: {bool(tautulli_url)}, API: {bool(tautulli_api_key)})")
            return None
        
        print(f"   🔍 Querying Tautulli for series: '{series_title}' at {tautulli_url}")
        
        # Try multiple variations of the title
        title_variations = [
            series_title,
            series_title.replace(": ", " - "),  # e.g., "Daredevil: Born Again" -> "Daredevil - Born Again"
            series_title.replace(": ", " "),    # e.g., "Daredevil: Born Again" -> "Daredevil Born Again"
            "Marvel's " + series_title          # e.g., "Marvel's Daredevil: Born Again"
        ]
        
        for search_title in title_variations:
            print(f"   🔍 Trying title variation: '{search_title}'")
            params = {
                'apikey': tautulli_api_key,
                'cmd': 'get_history',
                'search': search_title,
                # Remove media_type filter to catch more entries
                'length': 1  # Get the most recent entry
                # Optionally add 'user_id' if you want to filter by a specific user
                # 'user_id': '12345'
            }
            
            response = requests.get(f"{tautulli_url}/api/v2", params=params, timeout=10)
            
            if not response.ok:
                print(f"   ❌ Tautulli API error: {response.status_code}")
                continue
                
            data = response.json()
            print(f"   📊 Tautulli API raw response: {data}")
            
            if data.get('response', {}).get('result') != 'success':
                print(f"   ❌ Tautulli API result: {data.get('response', {}).get('result')}")
                continue
            
            history = data.get('response', {}).get('data', {}).get('data', [])
            print(f"   📊 Found {len(history)} history entries for '{search_title}'")
            
            if not history:
                continue
                
            most_recent = history[0]
            print(f"   📊 Most recent history entry: {most_recent}")
            
            # Check for multiple possible date fields
            last_watched = most_recent.get('date') or most_recent.get('watched_at') or most_recent.get('last_watched')
            
            if last_watched:
                try:
                    timestamp = int(last_watched)
                    print(f"   ✅ Most recent watch: {timestamp} ({datetime.fromtimestamp(timestamp)})")
                    return timestamp
                except (ValueError, TypeError):
                    print(f"   ⚠️  Invalid date format: {last_watched}")
                    continue
            else:
                print(f"   ⚠️  No date field in history entry")
        
        print(f"   ⚠️  No watch history found after trying all title variations")
        
    except requests.exceptions.Timeout:
        print(f"   ⏰ Tautulli timeout")
    except Exception as e:
        print(f"   ❌ Tautulli error: {str(e)}")
    
    return None

def get_jellyfin_last_watched(series_title):
    """Get last watched date from Jellyfin for this series - with debug output."""
    try:
        jellyfin_url = os.getenv('JELLYFIN_URL')
        jellyfin_api_key = os.getenv('JELLYFIN_API_KEY')
        jellyfin_user_id = os.getenv('JELLYFIN_USER_ID')
        
        if not all([jellyfin_url, jellyfin_api_key, jellyfin_user_id]):
            missing = []
            if not jellyfin_url: missing.append("URL")
            if not jellyfin_api_key: missing.append("API_KEY")
            if not jellyfin_user_id: missing.append("USER_ID")
            print(f"   ⚠️  Jellyfin not fully configured - missing: {', '.join(missing)}")
            return None
        
        print(f"   🔍 Querying Jellyfin: {jellyfin_url}")
        
        # Search for the series
        search_params = {
            'api_key': jellyfin_api_key,
            'searchTerm': series_title,
            'IncludeItemTypes': 'Series',
            'Limit': 5
        }
        
        search_response = requests.get(f"{jellyfin_url}/Items", params=search_params, timeout=10)
        if not search_response.ok:
            print(f"   ❌ Jellyfin search failed: {search_response.status_code}")
            return None
            
        search_data = search_response.json()
        series_items = search_data.get('Items', [])
        print(f"   📊 Found {len(series_items)} series matches")
        
        # Find exact or close match
        series_item = None
        for item in series_items:
            item_name = item.get('Name', '')
            print(f"   🔍 Checking: '{item_name}' vs '{series_title}'")
            if item_name.lower() == series_title.lower():
                series_item = item
                print(f"   ✅ Exact match found")
                break
            elif series_title.lower() in item_name.lower() or item_name.lower() in series_title.lower():
                series_item = item
                print(f"   ✅ Partial match found")
                # Continue looking for exact match, but keep this as backup
        
        if not series_item:
            print(f"   ⚠️  No matching series found in Jellyfin")
            return None
        
        series_id = series_item['Id']
        print(f"   📺 Using series: {series_item['Name']} (ID: {series_id})")
        
        # Get episodes for this series with play state
        episodes_params = {
            'api_key': jellyfin_api_key,
            'ParentId': series_id,
            'IncludeItemTypes': 'Episode',
            'Fields': 'UserData',
            'UserId': jellyfin_user_id
        }
        
        episodes_response = requests.get(f"{jellyfin_url}/Items", params=episodes_params, timeout=10)
        if not episodes_response.ok:
            print(f"   ❌ Failed to get episodes: {episodes_response.status_code}")
            return None
            
        episodes_data = episodes_response.json()
        episodes = episodes_data.get('Items', [])
        print(f"   📊 Found {len(episodes)} episodes")
        
        # Find the most recently watched episode
        latest_watch = None
        latest_episode_info = None
        watched_count = 0
        
        for episode in episodes:
            user_data = episode.get('UserData', {})
            if user_data.get('Played'):  # Episode was watched
                watched_count += 1
                last_played = user_data.get('LastPlayedDate')
                if last_played:
                    try:
                        # Parse Jellyfin date format
                        timestamp = int(datetime.fromisoformat(last_played.replace('Z', '+00:00')).timestamp())
                        
                        episode_name = episode.get('Name', 'Unknown')
                        season_num = episode.get('ParentIndexNumber', 0)
                        episode_num = episode.get('IndexNumber', 0)
                        
                        if not latest_watch or timestamp > latest_watch:
                            latest_watch = timestamp
                            latest_episode_info = f"S{season_num}E{episode_num} - {episode_name}"
                            
                    except Exception as e:
                        print(f"   ⚠️  Date parse error: {str(e)}")
                        continue
        
        print(f"   📊 {watched_count} watched episodes found")
        
        if latest_watch:
            print(f"   ✅ Most recent watch: {latest_episode_info}")
            print(f"   📆 Date: {datetime.fromtimestamp(latest_watch)}")
            return latest_watch
        else:
            print(f"   ⚠️  No watched episodes found")
        
    except requests.exceptions.Timeout:
        print(f"   ⏰ Jellyfin timeout")
    except Exception as e:
        print(f"   ❌ Jellyfin error: {str(e)}")
    
    return None

def get_sonarr_latest_file_date(series_id):
    """Get the most recent episode file date from Sonarr - with debug output."""
    try:
        headers = {'X-Api-Key': SONARR_API_KEY}
        
        print(f"   🔍 Getting episode file dates for series {series_id}")
        
        # Get all episodes for the series
        response = requests.get(f"{SONARR_URL}/api/v3/episode?seriesId={series_id}", headers=headers, timeout=10)
        if not response.ok:
            print(f"   ❌ Failed to get episodes: {response.status_code}")
            return None
        
        episodes = response.json()
        print(f"   📊 Found {len(episodes)} total episodes")
        
        episodes_with_files = [ep for ep in episodes if ep.get('hasFile')]
        print(f"   📊 Found {len(episodes_with_files)} episodes with files")
        
        if not episodes_with_files:
            print(f"   ⚠️  No episode files found")
            return None
        
        latest_file_date = None
        latest_episode_info = None
        
        # Check each episode file - ENHANCED DATE PARSING
        for episode in episodes_with_files[:5]:  # Show first 5 for debugging
            if episode.get('episodeFile'):
                date_added_str = episode['episodeFile'].get('dateAdded')
                season = episode.get('seasonNumber')
                ep_num = episode.get('episodeNumber')
                
                print(f"     📅 S{season}E{ep_num}: dateAdded = '{date_added_str}'")
                
                if date_added_str:
                    try:
                        # Parse the date string with multiple fallback methods
                        import re
                        
                        timestamp = None
                        
                        # Method 1: ISO format with Z
                        if date_added_str.endswith('Z'):
                            try:
                                dt = datetime.fromisoformat(date_added_str.replace('Z', '+00:00'))
                                timestamp = int(dt.timestamp())
                                print(f"       ✅ Parsed with Method 1 (ISO+Z): {timestamp}")
                            except:
                                pass
                        
                        # Method 2: Direct ISO format
                        if not timestamp:
                            try:
                                dt = datetime.fromisoformat(date_added_str)
                                timestamp = int(dt.timestamp())
                                print(f"       ✅ Parsed with Method 2 (ISO): {timestamp}")
                            except:
                                pass
                        
                        # Method 3: Strip milliseconds if present
                        if not timestamp and '.' in date_added_str:
                            try:
                                # Remove microseconds: 2024-05-15T10:30:00.123Z -> 2024-05-15T10:30:00Z
                                clean_date = re.sub(r'\.\d+', '', date_added_str)
                                if clean_date.endswith('Z'):
                                    clean_date = clean_date.replace('Z', '+00:00')
                                dt = datetime.fromisoformat(clean_date)
                                timestamp = int(dt.timestamp())
                                print(f"       ✅ Parsed with Method 3 (no-ms): {timestamp}")
                            except:
                                pass
                        
                        # Method 4: Manual parsing as last resort
                        if not timestamp:
                            try:
                                # Try to extract year, month, day, hour, minute, second
                                match = re.match(r'(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})', date_added_str)
                                if match:
                                    year, month, day, hour, minute, second = map(int, match.groups())
                                    dt = datetime(year, month, day, hour, minute, second)
                                    timestamp = int(dt.timestamp())
                                    print(f"       ✅ Parsed with Method 4 (manual): {timestamp}")
                            except:
                                pass
                        
                        if timestamp:
                            print(f"       📆 Human date: {datetime.fromtimestamp(timestamp)}")
                            
                            if not latest_file_date or timestamp > latest_file_date:
                                latest_file_date = timestamp
                                latest_episode_info = f"S{season}E{ep_num}"
                        else:
                            print(f"       ❌ All parsing methods failed for: '{date_added_str}'")
                            
                    except Exception as e:
                        print(f"       ❌ Date parse error: {str(e)}")
                        continue
        
        if latest_file_date:
            print(f"   ✅ Latest file: {latest_episode_info} at {datetime.fromtimestamp(latest_file_date)}")
            return latest_file_date
        else:
            print(f"   ⚠️  Could not parse any episode file dates")
            return None
            
    except requests.exceptions.Timeout:
        print(f"   ⏰ Sonarr timeout")
    except Exception as e:
        print(f"   ❌ Sonarr error: {str(e)}")
        return None

def get_baseline_date(series_id, series_title=None):
    """
    Get baseline date using COMPLETE hierarchy:
    1. OCDarr JSON activity tracking (most accurate recent activity)
    2. Tautulli last watch date (historical watch data)
    3. Jellyfin last watch date (historical watch data)
    4. Sonarr latest episode file date (when content was acquired)
    5. Reasonable fallback
    """
    
    activity_data = load_activity_tracking()
    series_id_str = str(series_id)
    
    print(f"\n🔍 Getting baseline date for series {series_id} ({series_title})")
    
    # 1. FIRST: Check OCDarr JSON activity tracking
    if series_id_str in activity_data:
        last_watched = activity_data[series_id_str].get('last_watched', 0)
        if last_watched > 0:
            print(f"✅ STEP 1: Using OCDarr JSON date: {last_watched}")
            print(f"   📆 Date: {datetime.fromtimestamp(last_watched)}")
            return last_watched
    
    print(f"⚠️  STEP 1: No OCDarr JSON data found")
    
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
    
    # 5. FALLBACK: Use reasonable past date (30 days ago)
    fallback_date = int((datetime.now() - timedelta(days=30)).timestamp())
    print(f"⚠️  STEP 5 FALLBACK: Using 30-day fallback: {fallback_date}")
    print(f"   📆 Date: {datetime.fromtimestamp(fallback_date)}")
    return fallback_date




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
    """Check if time-based cleanup should be performed using new field names and hierarchy."""
    try:
        grace_days = rule.get('grace_days')  # NEW FIELD NAME
        dormant_days = rule.get('dormant_days')  # NEW FIELD NAME
        
        if not grace_days and not dormant_days:
            return False, "No time-based cleanup configured"
        
        # Get series title for external API lookups
        series_title = None
        try:
            headers = {'X-Api-Key': SONARR_API_KEY}
            response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers)
            if response.ok:
                series_title = response.json().get('title')
        except:
            pass
        
        # Get activity date using hierarchy
        activity_date = get_activity_date_with_hierarchy(series_id, series_title)
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
            for series_id in rule_details.get('series', []):
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
                update_last_watched(series_id, season_number, episode_number)  
        else:
            logger.error(f"Series ID not found for series: {series_name}")
    else:
        # SCHEDULER MODE - Run periodic cleanup
        logger.info("No server activity found - running periodic cleanup")
        run_periodic_cleanup()

if __name__ == "__main__":
    main()
