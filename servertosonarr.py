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


def save_activity_tracking(data):
    """Save activity tracking data."""
    try:
        with open(ACTIVITY_TRACKING_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving activity tracking: {str(e)}")

def update_activity_date(series_id, season_number=None, episode_number=None, timestamp=None):
    """
    Update activity date in config.json (PRIMARY SOURCE).
    This becomes the authoritative date that overrides external services.
    """
    try:
        config = load_config()
        current_time = timestamp or int(time.time())
        
        # Find the series in rules and update activity_date
        updated = False
        for rule_name, rule_details in config['rules'].items():
            series_dict = rule_details.get('series', {})
            if str(series_id) in series_dict:
                if isinstance(series_dict[str(series_id)], dict):
                    series_dict[str(series_id)]['activity_date'] = current_time
                else:
                    # Convert old format to new format
                    series_dict[str(series_id)] = {'activity_date': current_time}
                
                updated = True
                logger.info(f"📺 Updated CONFIG activity date for series {series_id}: {datetime.fromtimestamp(current_time)}")
                break
        
        if updated:
            save_config(config)
            logger.info(f"✅ Config saved - series {series_id} now has authoritative activity date")
        else:
            logger.warning(f"Series {series_id} not found in any rule for activity update")
        
    except Exception as e:
        logger.error(f"Error updating activity date for series {series_id}: {str(e)}")

# Add documentation for rule setup
def validate_rule_for_viewing_pattern(rule):
    """
    Validate rule configuration against intended viewing pattern.
    Returns warnings for configurations that might not work well.
    """
    warnings = []
    
    grace_days = rule.get('grace_days')
    dormant_days = rule.get('dormant_days')
    get_type = rule.get('get_type')
    keep_type = rule.get('keep_type')
    
    # Check for non-linear viewing patterns
    if grace_days and (get_type in ['episodes', 'seasons'] or keep_type in ['episodes', 'seasons']):
        warnings.append(
            "⚠️  Grace period cleanup assumes LINEAR viewing. "
            "If you watch episodes out of order, consider using DORMANT-ONLY cleanup."
        )
    
    # Check for reasonable grace vs dormant timing
    if grace_days and dormant_days and grace_days >= dormant_days:
        warnings.append(
            "⚠️  Grace period should be shorter than dormant period. "
            f"Current: Grace={grace_days}d >= Dormant={dormant_days}d"
        )
    
    # Check for storage gate compatibility
    if dormant_days and not os.getenv('GLOBAL_STORAGE_MIN_GB'):
        warnings.append(
            "💡 Consider setting global storage gate to protect against "
            "unnecessary dormant cleanup when storage is adequate."
        )
    
    return warnings

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
        # Check which external service is configured (user typically has one, not both)
        tautulli_url = os.getenv('TAUTULLI_URL')
        tautulli_api_key = os.getenv('TAUTULLI_API_KEY')
        jellyfin_url = os.getenv('JELLYFIN_URL')
        jellyfin_api_key = os.getenv('JELLYFIN_API_KEY')
        
        # Prefer Tautulli if both are configured (since it's more accurate for watch tracking)
        if tautulli_url and tautulli_api_key:
            logger.info(f"🔍 Checking Tautulli for '{series_title}'")
            tautulli_date = get_tautulli_last_watched(series_title)
            if tautulli_date:
                logger.info(f"✅ Using Tautulli date for series {series_id}: {datetime.fromtimestamp(tautulli_date)}")
                return tautulli_date
            logger.info(f"⚠️  No Tautulli date found for series {series_id}")
            
        elif jellyfin_url and jellyfin_api_key:
            logger.info(f"🔍 Checking Jellyfin for '{series_title}'")
            jellyfin_date = get_jellyfin_last_watched(series_title)
            if jellyfin_date:
                logger.info(f"✅ Using Jellyfin date for series {series_id}: {datetime.fromtimestamp(jellyfin_date)}")
                return jellyfin_date
            logger.info(f"⚠️  No Jellyfin date found for series {series_id}")
            
        else:
            logger.info(f"⚠️  No external watch tracking configured (Tautulli/Jellyfin)")
    
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

def load_activity_tracking():
    """
    Load activity tracking data with automatic recycle bin migration.
    EXTENDS EXISTING FUNCTION - just add recycle bin structure if missing.
    """
    try:
        if os.path.exists(ACTIVITY_TRACKING_FILE):
            with open(ACTIVITY_TRACKING_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {}
        
        # MIGRATION: Add recycle_bin structure to existing series data
        migrated = False
        for series_id, series_data in data.items():
            if isinstance(series_data, dict) and 'recycle_bin' not in series_data:
                series_data['recycle_bin'] = {}
                migrated = True
        
        # Save if migration occurred
        if migrated:
            save_activity_tracking(data)
            logger.info(f"✅ Added recycle_bin structure to {len([k for k, v in data.items() if isinstance(v, dict)])} series")
        
        return data
        
    except Exception as e:
        logger.error(f"Error loading activity tracking: {str(e)}")
        return {}

# =============================================================================
# NEW RECYCLE BIN FUNCTIONS 
# =============================================================================

def add_episodes_to_recycle_bin(series_id, episodes, grace_days):
    """Add episodes to recycle bin with expiration time."""
    if not episodes or grace_days <= 0:
        return
        
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        expires_at = current_time + (grace_days * 24 * 60 * 60)
        
        if series_id_str not in activity_data:
            activity_data[series_id_str] = {}
        
        if 'recycle_bin' not in activity_data[series_id_str]:
            activity_data[series_id_str]['recycle_bin'] = {}
        
        recycle_bin = activity_data[series_id_str]['recycle_bin']
        
        # Add each episode to recycle bin (don't overwrite existing)
        new_episodes = 0
        for episode in episodes:
            ep_id = str(episode['id'])
            if ep_id not in recycle_bin:  # Don't reset existing timers
                recycle_bin[ep_id] = {
                    'episode_file_id': episode.get('episodeFileId'),
                    'season_number': episode['seasonNumber'],
                    'episode_number': episode['episodeNumber'],
                    'added_at': current_time,
                    'expires_at': expires_at,
                    'grace_days': grace_days
                }
                new_episodes += 1
        
        if new_episodes > 0:
            save_activity_tracking(activity_data)
            logger.info(f"Added {new_episodes} episodes to recycle bin ({grace_days} days)")
        
    except Exception as e:
        logger.error(f"Error adding episodes to recycle bin: {str(e)}")

def check_recycle_bin_expiry(series_id):
    """Check for episodes whose recycle bin time has expired."""
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        
        if series_id_str not in activity_data:
            return []
        
        recycle_bin = activity_data[series_id_str].get('recycle_bin', {})
        expired_episodes = []
        episodes_to_remove = []
        
        for ep_id, episode_data in recycle_bin.items():
            if current_time >= episode_data['expires_at']:
                expired_episodes.append(episode_data)
                episodes_to_remove.append(ep_id)
        
        # Remove expired episodes from recycle bin
        if episodes_to_remove:
            for ep_id in episodes_to_remove:
                del recycle_bin[ep_id]
            save_activity_tracking(activity_data)
        
        return expired_episodes
        
    except Exception as e:
        logger.error(f"Error checking recycle bin expiry: {str(e)}")
        return []

def is_episode_in_recycle_bin(series_id, episode_id):
    """Check if episode is already in recycle bin."""
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        
        if series_id_str not in activity_data:
            return False
        
        recycle_bin = activity_data[series_id_str].get('recycle_bin', {})
        return str(episode_id) in recycle_bin
        
    except Exception as e:
        logger.error(f"Error checking recycle bin: {str(e)}")
        return False


# =============================================================================
# ADD TO EXISTING CLEANUP FUNCTIONS
# =============================================================================

def run_recycle_bin_cleanup():
    """
    ADD THIS to existing cleanup routines.
    Call this from main cleanup or as separate scheduled task.
    """
    try:
        cleanup_logger.info("🗑️  RECYCLE BIN CLEANUP: Processing expired episodes")
        
        config = load_config()
        activity_data = load_activity_tracking()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true' 
        total_deleted = 0
        
        # Process each series that has a recycle bin
        for series_id_str, series_data in activity_data.items():
            recycle_bin = series_data.get('recycle_bin', {})
            if not recycle_bin:
                continue
            
            try:
                series_id = int(series_id_str)
                expired_episodes = check_recycle_bin_expiry(series_id)
                
                if expired_episodes:
                    # Get series title
                    try:
                        headers = {'X-Api-Key': SONARR_API_KEY}
                        response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers)
                        series_title = response.json().get('title', f'Series {series_id}') if response.ok else f'Series {series_id}'
                    except:
                        series_title = f'Series {series_id}'
                    series_rule = None
                    for rule_name, rule in config['rules'].items():
                        if series_id_str in rule.get('series', {}):
                            series_rule = rule
                            break
                    
                    if series_rule:
                        rule_dry_run = series_rule.get('dry_run', False)
                        is_dry_run = global_dry_run or rule_dry_run
                    else:
                        is_dry_run = global_dry_run
                    
                    episode_file_ids = [ep['episode_file_id'] for ep in expired_episodes if ep.get('episode_file_id')]
                    
                    if episode_file_ids:
                        cleanup_logger.info(f"🗑️  {series_title}: {'DRY RUN - Would delete' if is_dry_run else 'Permanently deleting'} {len(episode_file_ids)} expired episodes")
                        delete_episodes_in_sonarr_with_logging(episode_file_ids, is_dry_run, series_title)
                        total_deleted += len(episode_file_ids)
                        
            except (ValueError, TypeError):
                continue
        
        cleanup_logger.info(f"🗑️  Recycle bin cleanup: Processed {total_deleted} episodes")
        return total_deleted
        
    except Exception as e:
        cleanup_logger.error(f"Error in recycle bin cleanup: {str(e)}")
        return 0
    
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

def fetch_next_episodes_dropdown(series_id, season_number, episode_number, get_type, get_count):
    """
    Fetch next episodes using dropdown system (get_type + get_count).
    Assumes linear watching only.
    """
    next_episode_ids = []

    try:
        if get_type == "all":
            # Get all episodes from current position forward
            all_episodes = fetch_all_episodes(series_id)
            sorted_episodes = sorted(all_episodes, key=lambda ep: (ep['seasonNumber'], ep['episodeNumber']))
            
            # Find current position and get everything after
            for ep in sorted_episodes:
                if (ep['seasonNumber'] > season_number or 
                    (ep['seasonNumber'] == season_number and ep['episodeNumber'] > episode_number)):
                    next_episode_ids.append(ep['id'])
            return next_episode_ids
            
        elif get_type == 'seasons':
            # Get X full seasons starting from remaining current season
            current_season_episodes = get_episode_details(series_id, season_number)
            remaining_current = [ep['id'] for ep in current_season_episodes if ep['episodeNumber'] > episode_number]
            next_episode_ids.extend(remaining_current)
            
            # Get additional full seasons if needed
            seasons_to_get = get_count if get_count else 1
            if not remaining_current:
                # Current season finished, get next X seasons
                for season_offset in range(1, seasons_to_get + 1):
                    season_episodes = get_episode_details(series_id, season_number + season_offset)
                    next_episode_ids.extend([ep['id'] for ep in season_episodes])
            elif seasons_to_get > 1:
                # Get additional seasons beyond current
                for season_offset in range(1, seasons_to_get):
                    season_episodes = get_episode_details(series_id, season_number + season_offset)
                    next_episode_ids.extend([ep['id'] for ep in season_episodes])
                    
            logger.info(f"Dropdown seasons mode: Found {len(next_episode_ids)} episodes across {seasons_to_get} seasons")
            return next_episode_ids
            
        else:  # episodes
            # Get specific number of episodes in linear order
            num_episodes = get_count if get_count else 1
            
            # Get remaining episodes in current season first
            current_season_episodes = get_episode_details(series_id, season_number)
            remaining_episodes = [ep['id'] for ep in current_season_episodes if ep['episodeNumber'] > episode_number]
            next_episode_ids.extend(remaining_episodes)

            # If we need more episodes, get from subsequent seasons
            current_season_num = season_number + 1
            while len(next_episode_ids) < num_episodes:
                next_season_episodes = get_episode_details(series_id, current_season_num)
                if not next_season_episodes:
                    logger.info(f"No more episodes available after season {current_season_num - 1}")
                    break
                    
                remaining_needed = num_episodes - len(next_episode_ids)
                next_episode_ids.extend([ep['id'] for ep in next_season_episodes[:remaining_needed]])
                current_season_num += 1
                
                # Prevent infinite loops
                if current_season_num > season_number + 10:
                    logger.warning(f"Stopping after checking 10 seasons ahead")
                    break

            logger.info(f"Dropdown episodes mode: Found {len(next_episode_ids)} out of {num_episodes} requested")
            return next_episode_ids[:num_episodes]
            
    except Exception as e:
        logger.error(f"Error in dropdown fetch_next_episodes: {str(e)}")
        return []


def run_dormant_cleanup():
    """Process dormant cleanup with optional storage gate."""
    try:
        cleanup_logger.info("🔴 DORMANT CLEANUP: Checking abandoned series")
        
        config = load_config()
        global_settings = load_global_settings()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        
        # Check storage gate
        storage_min_gb = global_settings.get('global_storage_min_gb')
        if storage_min_gb:
            gate_open, _, gate_reason = check_global_storage_gate()
            if not gate_open:
                cleanup_logger.info(f"🔒 Storage gate CLOSED: {gate_reason}")
                return 0
            cleanup_logger.info(f"🔓 Storage gate OPEN: {gate_reason}")
        else:
            cleanup_logger.info("⏰ No storage gate - running scheduled dormant cleanup")
        
        # Get candidates
        candidates = []
        headers = {'X-Api-Key': SONARR_API_KEY}
        all_series = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers).json()
        current_time = int(time.time())
        
        for rule_name, rule in config['rules'].items():
            dormant_days = rule.get('dormant_days')
            if not dormant_days:
                continue
            
            rule_dry_run = rule.get('dry_run', False)
            is_dry_run = global_dry_run or rule_dry_run
            
            for series_id_str in rule.get('series', {}):
                try:
                    series_id = int(series_id_str)
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    if not series_info:
                        continue
                    
                    activity_date = get_activity_date_with_hierarchy(series_id, series_info['title'])
                    if not activity_date:
                        continue
                    
                    days_since_activity = (current_time - activity_date) / (24 * 60 * 60)
                    if days_since_activity > dormant_days:
                        all_episodes = fetch_all_episodes(series_id)
                        episode_file_ids = [ep['episodeFileId'] for ep in all_episodes if ep.get('hasFile') and 'episodeFileId' in ep]
                        
                        if episode_file_ids:
                            candidates.append({
                                'series_id': series_id,
                                'title': series_info['title'],
                                'days_since_activity': days_since_activity,
                                'episode_file_ids': episode_file_ids,
                                'is_dry_run': is_dry_run
                            })
                            
                except (ValueError, TypeError):
                    continue
        
        # Process candidates
        processed_count = 0
        candidates.sort(key=lambda x: x['days_since_activity'], reverse=True)
        
        for candidate in candidates:
            # Check storage gate again if configured
            if storage_min_gb and not candidate['is_dry_run']:
                current_disk = get_sonarr_disk_space()
                if current_disk and current_disk['free_space_gb'] >= storage_min_gb:
                    cleanup_logger.info(f"🎯 Storage target reached")
                    break
            
            cleanup_logger.info(f"🔴 {candidate['title']}: Dormant for {candidate['days_since_activity']:.1f} days")
            delete_episodes_in_sonarr_with_logging(candidate['episode_file_ids'], candidate['is_dry_run'], candidate['title'])
            processed_count += 1
        
        cleanup_logger.info(f"🔴 Dormant cleanup: Processed {processed_count} series")
        return processed_count
        
    except Exception as e:
        cleanup_logger.error(f"Error in dormant cleanup: {str(e)}")
        return 0
    
def calculate_keep_block_episodes(all_episodes, keep_watched, last_watched_season, last_watched_episode):
    """
    SIMPLIFIED: Calculate keep block assuming linear watching pattern.
    For non-linear watchers, use dormant-only rules.
    """
    try:
        if keep_watched == "all":
            return []
            
        elif keep_watched == "season":
            # Keep only the current season being watched
            season_episodes = [
                ep for ep in all_episodes 
                if ep['seasonNumber'] == last_watched_season and ep.get('hasFile')
            ]
            return [ep['id'] for ep in season_episodes]
            
        else:
            try:
                keep_count = int(keep_watched)
                # Sort all episodes in linear order
                sorted_episodes = sorted(all_episodes, key=lambda ep: (ep['seasonNumber'], ep['episodeNumber']))
                
                # Find the last watched episode position
                last_watched_index = None
                for i, ep in enumerate(sorted_episodes):
                    if (ep['seasonNumber'] == last_watched_season and 
                        ep['episodeNumber'] == last_watched_episode):
                        last_watched_index = i
                        break
                
                if last_watched_index is not None:
                    # Linear keep block: keep_count episodes ending with the one just watched
                    keep_start_index = max(0, last_watched_index - keep_count + 1)
                    
                    keep_block = []
                    for i in range(keep_start_index, last_watched_index + 1):
                        if i < len(sorted_episodes) and sorted_episodes[i].get('hasFile'):
                            keep_block.append(sorted_episodes[i]['id'])
                    
                    logger.info(f"Linear keep block: {len(keep_block)} episodes from position {keep_start_index} to {last_watched_index}")
                    return keep_block
                else:
                    logger.warning("Could not find last watched episode for linear keep block calculation")
                    return []
                    
            except (ValueError, TypeError):
                logger.warning(f"Invalid keep_watched value: {keep_watched}")
                return []
        
        return []
        
    except Exception as e:
        logger.error(f"Error calculating linear keep block episodes: {str(e)}")
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




def rule_to_legacy_params(rule):
    """Convert rule to legacy parameters for existing functions."""
    get_type = rule.get('get_type', 'episodes')
    get_count = rule.get('get_count', 1)
    keep_type = rule.get('keep_type', 'episodes') 
    keep_count = rule.get('keep_count', 1)
    
    # Convert get params
    if get_type == 'all':
        get_option = 'all'
    elif get_type == 'seasons':
        get_option = 'season' if get_count == 1 else str(get_count)
    else:
        get_option = str(get_count) if get_count else '1'
    
    # Convert keep params
    if keep_type == 'all':
        keep_watched = 'all'
    elif keep_type == 'seasons':
        keep_watched = 'season' if keep_count == 1 else str(keep_count)
    else:
        keep_watched = str(keep_count) if keep_count else '1'
    
    return get_option, keep_watched

def process_episodes_for_webhook(series_id, season_number, episode_number, rule):
    """
    Enhanced webhook processing with SIMPLIFIED 2-grace system.
    REMOVED: grace_buffer (redundant)
    KEPT: grace_watched (keep block expiry) + grace_unwatched (watch deadlines)
    """
    try:
        logger.info(f"Processing webhook for series {series_id}: S{season_number}E{episode_number}")
        
        # Parse rule using dropdown format
        if 'get_type' in rule and 'get_count' in rule:
            get_type = rule.get('get_type', 'episodes')
            get_count = rule.get('get_count', 1)
            keep_type = rule.get('keep_type', 'episodes') 
            keep_count = rule.get('keep_count', 1)
        else:
            # Fall back to legacy conversion for old rules
            get_option, keep_watched = rule_to_legacy_params(rule)
            get_type, get_count = parse_legacy_value(get_option)
            keep_type, keep_count = parse_legacy_value(keep_watched)
        
        # Update activity date
        update_activity_date(series_id, season_number, episode_number)
        
        # Get and unmonitor current episode if needed
        all_episodes = fetch_all_episodes(series_id)
        current_episode = next(
            (ep for ep in all_episodes 
             if ep['seasonNumber'] == season_number and ep['episodeNumber'] == episode_number), 
            None
        )
        
        if not current_episode:
            logger.error(f"Could not find current episode S{season_number}E{episode_number}")
            return
            
        if not rule.get('monitor_watched', True):
            unmonitor_episodes([current_episode['id']])
        
        # Get next episodes using dropdown system
        next_episode_ids = fetch_next_episodes_dropdown(
            series_id, season_number, episode_number, get_type, get_count
        )
        
        if next_episode_ids:
            monitor_or_search_episodes(next_episode_ids, rule.get('action_option', 'monitor'))
            logger.info(f"Processed {len(next_episode_ids)} next episodes")
        
        # Calculate current keep block
        current_keep_block = calculate_current_keep_block(
            all_episodes, keep_type, keep_count, season_number, episode_number
        )
        
        # Calculate episodes leaving keep block (for immediate deletion)
        episodes_leaving_keep_block = find_episodes_leaving_keep_block(
            all_episodes, keep_type, keep_count, season_number, episode_number
        )
        
        # SIMPLIFIED GRACE PROCESSING (REMOVED grace_buffer)
        
        # 1. GRACE WATCHED: Add current keep block to recycle bin with grace_watched expiry
        if rule.get('grace_watched') and current_keep_block:
            add_episodes_to_recycle_bin_unified(
                series_id, 
                current_keep_block, 
                rule['grace_watched'],
                grace_type='watched'
            )
            logger.info(f"Keep block episodes expire in {rule['grace_watched']} days")
        
        # 2. GRACE UNWATCHED: Track newly prepared episodes
        if rule.get('grace_unwatched') and next_episode_ids:
            track_grace_unwatched_episodes(series_id, next_episode_ids, rule['grace_unwatched'])
            logger.info(f"Tracking {len(next_episode_ids)} new episodes for unwatched grace")
        
        # 3. IMMEDIATE DELETION: Episodes leaving keep block (no buffer)
        if episodes_leaving_keep_block:
            episode_file_ids = [ep['episodeFileId'] for ep in episodes_leaving_keep_block if 'episodeFileId' in ep]
            if episode_file_ids:
                # No grace_buffer - immediate deletion
                delete_episodes_in_sonarr_with_logging(
                    episode_file_ids, 
                    rule.get('dry_run', False), 
                    f"Series {series_id}"
                )
                logger.info(f"Immediately deleted {len(episode_file_ids)} episodes leaving keep block")
            
    except Exception as e:
        logger.error(f"Error in webhook processing: {str(e)}")


# =============================================================================
# NEW: Unified Recycle Bin Function
# =============================================================================

def add_episodes_to_recycle_bin_unified(series_id, episodes, grace_days, grace_type='watched'):
    """
    Unified function to add episodes to recycle bin for any grace type.
    
    :param series_id: Sonarr series ID
    :param episodes: List of episode objects
    :param grace_days: Days until expiry
    :param grace_type: 'watched' or 'unwatched' (for logging/tracking)
    """
    if not episodes or grace_days <= 0:
        return
        
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        expires_at = current_time + (grace_days * 24 * 60 * 60)
        
        if series_id_str not in activity_data:
            activity_data[series_id_str] = {}
        
        if 'recycle_bin' not in activity_data[series_id_str]:
            activity_data[series_id_str]['recycle_bin'] = {}
        
        recycle_bin = activity_data[series_id_str]['recycle_bin']
        
        # Add episodes to unified recycle bin
        new_episodes = 0
        for episode in episodes:
            ep_id = str(episode['id'])
            
            # SIMPLIFIED: Always update expiry (latest grace period wins)
            recycle_bin[ep_id] = {
                'episode_file_id': episode.get('episodeFileId'),
                'season_number': episode['seasonNumber'],
                'episode_number': episode['episodeNumber'],
                'added_at': current_time,
                'expires_at': expires_at,
                'grace_days': grace_days,
                'grace_type': grace_type  # Track which type of grace
            }
            new_episodes += 1
        
        if new_episodes > 0:
            save_activity_tracking(activity_data)
            logger.info(f"Added {new_episodes} episodes to recycle bin ({grace_type} grace: {grace_days} days)")
        
    except Exception as e:
        logger.error(f"Error adding episodes to unified recycle bin: {str(e)}")

# =============================================================================
# UPDATED: Simplified Cleanup Functions
# =============================================================================

def run_unified_grace_cleanup():
    """
    SIMPLIFIED: Single cleanup function for all grace types using recycle bin.
    REMOVED: Separate grace_watched and grace_buffer cleanup functions.
    """
    try:
        cleanup_logger.info("🗑️  UNIFIED GRACE CLEANUP: Processing expired episodes")
        
        config = load_config()
        activity_data = load_activity_tracking()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        total_deleted = 0
        
        # Get all series from Sonarr for title lookup
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        all_series = response.json() if response.ok else []
        
        # Process each series that has a recycle bin
        for series_id_str, series_data in activity_data.items():
            recycle_bin = series_data.get('recycle_bin', {})
            if not recycle_bin:
                continue
            
            try:
                series_id = int(series_id_str)
                expired_episodes = check_recycle_bin_expiry(series_id)
                
                if expired_episodes:
                    # Get series title and rule
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    series_title = series_info['title'] if series_info else f'Series {series_id}'
                    
                    series_rule = None
                    for rule_name, rule in config['rules'].items():
                        if series_id_str in rule.get('series', {}):
                            series_rule = rule
                            break
                    
                    # Determine dry run status
                    if series_rule:
                        rule_dry_run = series_rule.get('dry_run', False)
                        is_dry_run = global_dry_run or rule_dry_run
                    else:
                        is_dry_run = global_dry_run
                    
                    # Group by grace type for better logging
                    watched_episodes = [ep for ep in expired_episodes if ep.get('grace_type') == 'watched']
                    other_episodes = [ep for ep in expired_episodes if ep.get('grace_type') != 'watched']
                    
                    episode_file_ids = [ep['episode_file_id'] for ep in expired_episodes if ep.get('episode_file_id')]
                    
                    if episode_file_ids:
                        if watched_episodes:
                            cleanup_logger.info(f"🟡 {series_title}: {len(watched_episodes)} keep block episodes expired")
                        if other_episodes:
                            cleanup_logger.info(f"⏰ {series_title}: {len(other_episodes)} other grace episodes expired")
                            
                        delete_episodes_in_sonarr_with_logging(episode_file_ids, is_dry_run, series_title)
                        total_deleted += len(episode_file_ids)
                        
            except (ValueError, TypeError):
                continue
        
        cleanup_logger.info(f"🗑️  Unified grace cleanup: Processed {total_deleted} episodes")
        return total_deleted
        
    except Exception as e:
        cleanup_logger.error(f"Error in unified grace cleanup: {str(e)}")
        return 0

def check_time_based_cleanup(series_id, rule):
    """Check if time-based cleanup should be performed - MULTI-GRACE VERSION."""
    try:
        grace_buffer = rule.get('grace_buffer')
        grace_watched = rule.get('grace_watched')
        grace_unwatched = rule.get('grace_unwatched')
        dormant_days = rule.get('dormant_days')
        
        if not any([grace_buffer, grace_watched, grace_unwatched, dormant_days]):
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
        
        # Get activity date using hierarchy
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
        
        # Check any grace period cleanup
        grace_reasons = []
        if grace_buffer:
            grace_reasons.append(f"buffer({grace_buffer}d)")
        if grace_watched and days_since_activity > grace_watched:
            grace_reasons.append(f"watched({grace_watched}d)")
        if grace_unwatched:
            grace_reasons.append(f"unwatched({grace_unwatched}d)")
        
        if grace_reasons:
            return True, f"Multi-grace cleanup: {', '.join(grace_reasons)}"
        
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

def find_episodes_leaving_keep_block(all_episodes, keep_type, keep_count, last_watched_season, last_watched_episode):
    """
    Find episodes that are leaving the keep block using dropdown system.
    These episodes should go to grace buffer if configured.
    """
    episodes_leaving = []
    
    try:
        if keep_type == "all":
            # Keep everything, nothing leaves
            return []
            
        elif keep_type == "seasons":
            # Keep X seasons, episodes from older seasons leave
            seasons_to_keep = keep_count if keep_count else 1
            cutoff_season = last_watched_season - seasons_to_keep + 1
            
            episodes_leaving = [
                ep for ep in all_episodes 
                if ep['seasonNumber'] < cutoff_season and ep.get('hasFile')
            ]
            
        else:  # episodes
            # Keep X episodes, older episodes leave the keep block
            episodes_to_keep = keep_count if keep_count else 1
            
            # Sort episodes by season/episode number
            sorted_episodes = sorted(all_episodes, key=lambda ep: (ep['seasonNumber'], ep['episodeNumber']))
            
            # Find the last watched episode index
            last_watched_index = None
            for i, ep in enumerate(sorted_episodes):
                if (ep['seasonNumber'] == last_watched_season and 
                    ep['episodeNumber'] == last_watched_episode):
                    last_watched_index = i
                    break
            
            if last_watched_index is not None:
                # Keep block: episodes_to_keep episodes ending with the one just watched
                keep_start_index = max(0, last_watched_index - keep_count + 1)
                
                # Episodes before the keep block are leaving
                episodes_with_files = [ep for ep in sorted_episodes if ep.get('hasFile')]
                
                for ep in episodes_with_files:
                    ep_index = next((i for i, se in enumerate(sorted_episodes) if se['id'] == ep['id']), None)
                    if ep_index is not None and ep_index < keep_start_index:
                        episodes_leaving.append(ep)
                
                logger.info(f"Keep block: episodes {keep_start_index} to {last_watched_index}, {len(episodes_leaving)} episodes leaving")
        
        return episodes_leaving
        
    except Exception as e:
        logger.error(f"Error finding episodes leaving keep block: {str(e)}")
        return []


def calculate_current_keep_block(all_episodes, keep_type, keep_count, last_watched_season, last_watched_episode):
    """
    Calculate current keep block using dropdown system.
    These episodes get the grace_watched timer.
    """
    try:
        if keep_type == "all":
            # Keep everything
            return [ep for ep in all_episodes if ep.get('hasFile')]
            
        elif keep_type == "seasons":
            # Keep X seasons
            seasons_to_keep = keep_count if keep_count else 1
            cutoff_season = last_watched_season - seasons_to_keep + 1
            
            keep_block = [
                ep for ep in all_episodes 
                if ep['seasonNumber'] >= cutoff_season and ep.get('hasFile')
            ]
            return keep_block
            
        else:  # episodes
            # Keep X episodes ending with the one just watched
            episodes_to_keep = keep_count if keep_count else 1
            
            # Sort episodes by season/episode number
            sorted_episodes = sorted(all_episodes, key=lambda ep: (ep['seasonNumber'], ep['episodeNumber']))
            
            # Find the last watched episode index
            last_watched_index = None
            for i, ep in enumerate(sorted_episodes):
                if (ep['seasonNumber'] == last_watched_season and 
                    ep['episodeNumber'] == last_watched_episode):
                    last_watched_index = i
                    break
            
            if last_watched_index is not None:
                # Keep block: episodes_to_keep episodes ending with the one just watched
                keep_start_index = max(0, last_watched_index - keep_count + 1)
                
                keep_block = []
                for i in range(keep_start_index, last_watched_index + 1):
                    if i < len(sorted_episodes) and sorted_episodes[i].get('hasFile'):
                        keep_block.append(sorted_episodes[i])
                
                return keep_block
            else:
                logger.warning("Could not find last watched episode for keep block calculation")
                return []
        
        return []
        
    except Exception as e:
        logger.error(f"Error calculating current keep block: {str(e)}")
        return []


def set_grace_watched_timer(series_id, keep_block_episodes, grace_watched_days):
    """
    Set grace_watched timer for current keep block episodes.
    Timer resets each time series has activity.
    """
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        expires_at = current_time + (grace_watched_days * 24 * 60 * 60)
        
        if series_id_str not in activity_data:
            activity_data[series_id_str] = {}
        
        # Reset the watched grace timer (activity resets it)
        activity_data[series_id_str]['grace_watched_timer'] = {
            'expires_at': expires_at,
            'grace_days': grace_watched_days,
            'last_reset': current_time,
            'keep_block_episodes': [
                {
                    'episode_id': ep['id'],
                    'episode_file_id': ep.get('episodeFileId'),
                    'season_number': ep['seasonNumber'],
                    'episode_number': ep['episodeNumber']
                }
                for ep in keep_block_episodes
            ]
        }
        
        save_activity_tracking(activity_data)
        logger.info(f"Reset grace_watched timer for {len(keep_block_episodes)} episodes in keep block")
        
    except Exception as e:
        logger.error(f"Error setting grace_watched timer: {str(e)}")


def track_grace_unwatched_episodes(series_id, episode_ids, grace_unwatched_days):
    """
    Track newly "got" episodes with individual grace_unwatched timers.
    Each episode gets its own timer from its Sonarr download date.
    """
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        
        if series_id_str not in activity_data:
            activity_data[series_id_str] = {}
        
        if 'grace_unwatched_episodes' not in activity_data[series_id_str]:
            activity_data[series_id_str]['grace_unwatched_episodes'] = {}
        
        # Get episode details and their download dates from Sonarr
        headers = {'X-Api-Key': SONARR_API_KEY}
        all_episodes = fetch_all_episodes(series_id)
        tracked_count = 0
        
        for episode_id in episode_ids:
            episode = next((ep for ep in all_episodes if ep['id'] == episode_id), None)
            if not episode or not episode.get('hasFile'):
                continue
                
            # Get episode file info to check download date
            try:
                episode_file_id = episode.get('episodeFileId')
                if episode_file_id:
                    file_response = requests.get(f"{SONARR_URL}/api/v3/episodefile/{episode_file_id}", headers=headers)
                    if file_response.ok:
                        file_data = file_response.json()
                        date_added = file_data.get('dateAdded')
                        
                        if date_added:
                            download_timestamp = parse_date_fixed(date_added, f"S{episode['seasonNumber']}E{episode['episodeNumber']}")
                            if download_timestamp:
                                expires_at = download_timestamp + (grace_unwatched_days * 24 * 60 * 60)
                                
                                ep_id = str(episode_id)
                                activity_data[series_id_str]['grace_unwatched_episodes'][ep_id] = {
                                    'episode_file_id': episode_file_id,
                                    'season_number': episode['seasonNumber'],
                                    'episode_number': episode['episodeNumber'],
                                    'download_date': download_timestamp,
                                    'expires_at': expires_at,
                                    'grace_days': grace_unwatched_days,
                                    'got_by_rule': True  # Mark as prepared by rule
                                }
                                tracked_count += 1
                                logger.debug(f"Tracking S{episode['seasonNumber']}E{episode['episodeNumber']} - expires in {grace_unwatched_days} days from download")
            except Exception as e:
                logger.warning(f"Could not get download date for episode {episode_id}: {str(e)}")
                continue
        
        if tracked_count > 0:
            save_activity_tracking(activity_data)
            logger.info(f"Now tracking {tracked_count} episodes for grace_unwatched cleanup")
        
    except Exception as e:
        logger.error(f"Error tracking grace_unwatched episodes: {str(e)}")


def check_grace_unwatched_expiry(series_id):
    """
    Check for grace_unwatched episodes that have expired.
    Only removes episodes that were "got" by rules and not watched within grace period.
    """
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        
        if series_id_str not in activity_data:
            return []
        
        unwatched_episodes = activity_data[series_id_str].get('grace_unwatched_episodes', {})
        expired_episodes = []
        episodes_to_remove = []
        
        for ep_id, episode_data in unwatched_episodes.items():
            if current_time >= episode_data['expires_at']:
                expired_episodes.append(episode_data)
                episodes_to_remove.append(ep_id)
                logger.info(f"Grace unwatched expired: S{episode_data['season_number']}E{episode_data['episode_number']} - {(current_time - episode_data['download_date']) / (24*60*60):.1f} days since download")
        
        # Remove expired episodes from tracking
        if episodes_to_remove:
            for ep_id in episodes_to_remove:
                del unwatched_episodes[ep_id]
            save_activity_tracking(activity_data)
        
        return expired_episodes
        
    except Exception as e:
        logger.error(f"Error checking grace_unwatched expiry: {str(e)}")
        return []


def check_grace_watched_expiry(series_id):
    """
    Check if grace_watched timer has expired for keep block.
    This is a series-wide timer that resets on any activity.
    """
    try:
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        
        if series_id_str not in activity_data:
            return []
        
        watched_timer = activity_data[series_id_str].get('grace_watched_timer')
        if not watched_timer:
            return []
        
        if current_time >= watched_timer['expires_at']:
            # Timer expired - return keep block episodes for deletion
            expired_episodes = watched_timer.get('keep_block_episodes', [])
            
            # Clear the timer
            del activity_data[series_id_str]['grace_watched_timer']
            save_activity_tracking(activity_data)
            
            logger.info(f"Grace watched expired: {len(expired_episodes)} keep block episodes after {(current_time - watched_timer['last_reset']) / (24*60*60):.1f} days of inactivity")
            return expired_episodes
        
        return []
        
    except Exception as e:
        logger.error(f"Error checking grace_watched expiry: {str(e)}")
        return []


def process_multi_grace_cleanup_fixed(series_id, rule, all_episodes):
    """
    FIXED: Process all configured grace periods with proper targeting.
    """
    try:
        episodes_to_delete = []
        
        # 1. Grace buffer (recycle bin expiry) - Episodes that left keep block
        if rule.get('grace_buffer'):
            expired_buffer = check_recycle_bin_expiry(series_id)
            if expired_buffer:
                buffer_file_ids = [ep['episode_file_id'] for ep in expired_buffer if ep.get('episode_file_id')]
                episodes_to_delete.extend(buffer_file_ids)
                logger.info(f"Grace buffer: {len(buffer_file_ids)} episodes expired from recycle bin")
        
        # 2. Grace watched (keep block expires after series inactivity)
        if rule.get('grace_watched'):
            expired_watched = check_grace_watched_expiry(series_id)
            if expired_watched:
                watched_file_ids = [ep['episode_file_id'] for ep in expired_watched if ep.get('episode_file_id')]
                episodes_to_delete.extend(watched_file_ids)
                logger.info(f"Grace watched: {len(watched_file_ids)} keep block episodes expired after inactivity")
        
        # 3. Grace unwatched (individual episode timers from download date)
        if rule.get('grace_unwatched'):
            expired_unwatched = check_grace_unwatched_expiry(series_id)
            if expired_unwatched:
                unwatched_file_ids = [ep['episode_file_id'] for ep in expired_unwatched if ep.get('episode_file_id')]
                episodes_to_delete.extend(unwatched_file_ids)
                logger.info(f"Grace unwatched: {len(unwatched_file_ids)} episodes exceeded watch deadline")
        
        return list(set(episodes_to_delete))  # Remove duplicates
        
    except Exception as e:
        logger.error(f"Error in multi-grace cleanup: {str(e)}")
        return []

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
        
        # Check for multi-grace cleanup first
        episodes_to_delete = process_multi_grace_cleanup(series_id, rule, all_episodes)

        if episodes_to_delete:
            cleanup_type = "⏰ MULTI-GRACE"
            print(f"{cleanup_type}: Processing grace periods")
        else:
            # Fall back to existing logic for dormant/nuclear cleanup
            if "Nuclear cleanup" in cleanup_reason or "Dormant" in cleanup_reason:
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

# Corrected Final Implementation for servertosonarr.py

def get_watched_vs_unwatched_episodes(all_episodes, activity_data, series_id_str):
    """Separate episodes into watched vs unwatched for proper grace/dormant logic."""
    try:
        watched_episodes = []
        unwatched_episodes = []
        
        # Get series activity info
        series_activity = activity_data.get(series_id_str, {})
        last_season = series_activity.get('last_season', 0)
        last_episode = series_activity.get('last_episode', 0)
        
        for episode in all_episodes:
            if not episode.get('hasFile'):
                continue  # Skip episodes without files
                
            season_num = episode.get('seasonNumber', 0)
            episode_num = episode.get('episodeNumber', 0)
            
            # Determine if episode has been watched
            # Logic: Episodes up to and including last watched episode are "watched"
            if (season_num < last_season or 
                (season_num == last_season and episode_num <= last_episode)):
                watched_episodes.append(episode)
            else:
                unwatched_episodes.append(episode)
        
        logger.debug(f"Episode breakdown: {len(watched_episodes)} watched, {len(unwatched_episodes)} unwatched")
        return watched_episodes, unwatched_episodes
        
    except Exception as e:
        logger.error(f"Error separating watched/unwatched episodes: {str(e)}")
        return [], all_episodes  # Fallback: treat all as unwatched

def calculate_grace_deletable_episodes(all_episodes, activity_data, series_id_str):
    """Calculate episodes to delete for GRACE cleanup - unwatched episodes only."""
    try:
        watched_episodes, unwatched_episodes = get_watched_vs_unwatched_episodes(
            all_episodes, activity_data, series_id_str
        )
        
        # Grace cleanup: Delete ONLY unwatched episodes
        episodes_to_delete = unwatched_episodes
        episode_file_ids = [ep['episodeFileId'] for ep in episodes_to_delete if 'episodeFileId' in ep]
        
        logger.info(f"Grace cleanup: Would delete {len(episode_file_ids)} unwatched episodes")
        logger.info(f"Grace cleanup: Keeping {len(watched_episodes)} watched episodes")
        
        return {
            'episode_file_ids': episode_file_ids,
            'episode_count': len(episode_file_ids),
            'cleanup_type': 'grace',
            'description': f"Remove {len(episode_file_ids)} unwatched episodes, keep {len(watched_episodes)} watched"
        }
        
    except Exception as e:
        logger.error(f"Error calculating grace deletable episodes: {str(e)}")
        return {'episode_file_ids': [], 'episode_count': 0, 'cleanup_type': 'grace', 'description': 'Error'}

def calculate_dormant_deletable_episodes(all_episodes):
    """Calculate episodes to delete for DORMANT cleanup - ALL episodes."""
    try:
        episodes_with_files = [ep for ep in all_episodes if ep.get('hasFile')]
        episode_file_ids = [ep['episodeFileId'] for ep in episodes_with_files if 'episodeFileId' in ep]
        
        logger.info(f"Dormant cleanup: Would delete ALL {len(episode_file_ids)} episodes (series abandoned)")
        
        return {
            'episode_file_ids': episode_file_ids,
            'episode_count': len(episode_file_ids),
            'cleanup_type': 'dormant',
            'description': f"Remove ALL {len(episode_file_ids)} episodes (series dormant)"
        }
        
    except Exception as e:
        logger.error(f"Error calculating dormant deletable episodes: {str(e)}")
        return {'episode_file_ids': [], 'episode_count': 0, 'cleanup_type': 'dormant', 'description': 'Error'}

def check_cleanup_eligibility_corrected(series_id, rule):
    """
    Corrected cleanup eligibility check:
    - Grace = Remove unwatched episodes after X days
    - Dormant = Remove ALL episodes after Y days  
    - Activity = Any episode watch resets both timers
    """
    try:
        grace_days = rule.get('grace_days')
        dormant_days = rule.get('dormant_days')
        
        if not grace_days and not dormant_days:
            return False, "No time-based cleanup configured", None
        
        # Get series title
        series_title = None
        try:
            headers = {'X-Api-Key': SONARR_API_KEY}
            response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers, timeout=5)
            if response.ok:
                series_title = response.json().get('title')
        except Exception as e:
            logger.warning(f"Failed to get series title: {str(e)}")
        
        # Get last watch activity date (single date for entire series)
        activity_date = get_activity_date_with_hierarchy(series_id, series_title)
        
        if activity_date is None:
            logger.debug(f"Series {series_id}: No activity date found")
            return False, "No activity date available", None
        
        current_time = int(time.time())
        days_since_activity = (current_time - activity_date) / (24 * 60 * 60)
        
        logger.info(f"Series {series_id} ({series_title}): {days_since_activity:.1f} days since last activity")
        
        # DORMANT CHECK FIRST: Past dormant threshold = nuke everything
        if dormant_days and days_since_activity > dormant_days:
            return True, f"DORMANT: {days_since_activity:.1f}d > {dormant_days}d (nuke all episodes)", {
                'type': 'dormant',
                'days_since_activity': days_since_activity,
                'priority_score': 1000 + days_since_activity,  # Highest priority
                'activity_date': activity_date
            }
        
        # GRACE CHECK: Past grace but before dormant = remove unwatched only
        if grace_days and days_since_activity > grace_days:
            return True, f"GRACE: {days_since_activity:.1f}d > {grace_days}d (remove unwatched episodes)", {
                'type': 'grace',
                'days_since_activity': days_since_activity,
                'priority_score': 500 + days_since_activity,  # Medium priority
                'activity_date': activity_date
            }
        
        # PROTECTED: Within grace period
        return False, f"PROTECTED: {days_since_activity:.1f}d <= {grace_days or dormant_days}d since activity", None
        
    except Exception as e:
        logger.error(f"Error checking cleanup eligibility: {str(e)}")
        return False, f"Error: {str(e)}", None

def get_cleanup_candidates_corrected(config, storage_gated=True):
    """Get cleanup candidates with corrected grace/dormant logic."""
    try:
        if storage_gated:
            # Check storage gate first
            gate_open, target_gb, gate_reason = check_storage_gate_for_cleanup(config)
            if not gate_open:
                logger.info(f"🔒 Storage gate CLOSED: {gate_reason}")
                return [], None, gate_reason
            logger.info(f"🔓 Storage gate OPEN: {gate_reason}")
        else:
            target_gb = None
            logger.info("⏰ Always-run mode: Processing time-based cleanup")
        
        # Get series from Sonarr
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        
        if not response.ok:
            logger.error("Failed to fetch series from Sonarr")
            return [], target_gb, "Sonarr API error"
        
        all_series = response.json()
        candidates = []
        activity_data = load_activity_tracking()
        
        stats = {'grace': 0, 'dormant': 0, 'protected': 0, 'no_content': 0}
        
        logger.info("🔍 Checking rule-assigned series for corrected cleanup logic:")
        
        for rule_name, rule in config['rules'].items():
            # Only check rules that have time cleanup OR storage cleanup
            has_storage = rule.get('storage_cleanup_min_gb')
            has_time = rule.get('grace_days') or rule.get('dormant_days')
            
            if storage_gated and not has_storage:
                continue  # Skip rules without storage in storage-gated mode
            if not storage_gated and not has_time:
                continue  # Skip rules without time settings in always-run mode
            
            logger.info(f"📋 Rule '{rule_name}': Grace={rule.get('grace_days')}d, Dormant={rule.get('dormant_days')}d")
            
            series_dict = rule.get('series', {})
            rule_candidates = 0
            
            for series_id_str, series_data in series_dict.items():
                try:
                    series_id = int(series_id_str)
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    
                    if not series_info:
                        continue
                    
                    # Check cleanup eligibility with corrected logic
                    eligible, reason, cleanup_info = check_cleanup_eligibility_corrected(series_id, rule)
                    
                    if eligible:
                        # Get episodes using corrected logic
                        all_episodes = fetch_all_episodes(series_id)
                        episodes_with_files = [ep for ep in all_episodes if ep.get('hasFile', False)]
                        
                        if not episodes_with_files:
                            stats['no_content'] += 1
                            continue
                        
                        # Use corrected episode calculation based on cleanup type
                        if cleanup_info['type'] == 'grace':
                            deletable_episodes = calculate_grace_deletable_episodes(
                                all_episodes, activity_data, series_id_str
                            )
                        else:  # dormant
                            deletable_episodes = calculate_dormant_deletable_episodes(all_episodes)
                        
                        if deletable_episodes['episode_file_ids']:
                            candidates.append({
                                'series_id': series_id,
                                'title': series_info['title'],
                                'rule_name': rule_name,
                                'cleanup_reason': reason,
                                'cleanup_type': cleanup_info['type'],
                                'days_since_activity': cleanup_info['days_since_activity'],
                                'priority_score': cleanup_info['priority_score'],
                                'deletable_episodes': deletable_episodes,
                                'estimated_space_gb': 0  # Could calculate if needed
                            })
                            
                            stats[cleanup_info['type']] += 1
                            rule_candidates += 1
                            logger.debug(f"   ✅ {series_info['title']}: {reason}")
                        else:
                            logger.debug(f"   ⏭️ {series_info['title']}: {reason} but no deletable episodes")
                    else:
                        if "PROTECTED" in reason:
                            stats['protected'] += 1
                        logger.debug(f"   🛡️ {series_info['title']}: {reason}")
                        
                except ValueError:
                    continue
            
            logger.info(f"   📊 Rule '{rule_name}': {rule_candidates} candidates")
        
        # Sort by priority: Dormant first, then grace
        candidates.sort(key=lambda x: x['priority_score'], reverse=True)
        
        logger.info("=" * 60)
        logger.info(f"📋 CORRECTED CLEANUP CANDIDATES:")
        logger.info(f"   🔴 Dormant (nuke all): {stats['dormant']}")
        logger.info(f"   🟡 Grace (unwatched only): {stats['grace']}")
        logger.info(f"   🛡️ Protected: {stats['protected']}")
        logger.info(f"   📊 Total candidates: {len(candidates)}")
        logger.info("=" * 60)
        
        return candidates, target_gb, f"Found {len(candidates)} candidates"
        
    except Exception as e:
        logger.error(f"Error getting corrected cleanup candidates: {str(e)}")
        return [], None, f"Error: {str(e)}"

def run_corrected_cleanup():
    """
    Final corrected cleanup with proper grace/dormant logic:
    - Grace = Remove unwatched episodes only
    - Dormant = Remove ALL episodes  
    - Storage-gated vs always-run modes
    """
    try:
        cleanup_logger.info("=" * 80)
        cleanup_logger.info("🚀 STARTING CORRECTED CLEANUP")
        cleanup_logger.info("🟡 Grace = Remove unwatched episodes, keep watched")
        cleanup_logger.info("🔴 Dormant = Remove ALL episodes (series abandoned)")
        cleanup_logger.info("🔒 Only rule-assigned series")
        
        config = load_config()
        dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        
        # Determine cleanup mode
        has_storage_gates = any(
            rule.get('storage_cleanup_min_gb') 
            for rule in config['rules'].values()
        )
        
        if has_storage_gates:
            cleanup_logger.info("🚪 STORAGE-GATED MODE")
            candidates, target_gb, status = get_cleanup_candidates_corrected(config, storage_gated=True)
        else:
            cleanup_logger.info("⏰ ALWAYS-RUN MODE")
            candidates, target_gb, status = get_cleanup_candidates_corrected(config, storage_gated=False)
        
        if not candidates:
            cleanup_logger.info(f"✅ {status}")
            return
        
        cleanup_logger.info(f"📋 {status}")
        cleanup_logger.info(f"🔧 Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        
        # Process candidates
        processed_count = 0
        stats = {'grace': 0, 'dormant': 0}
        
        for candidate in candidates:
            series_title = candidate['title']
            rule_name = candidate['rule_name']
            cleanup_type = candidate['cleanup_type']
            reason = candidate['cleanup_reason']
            deletable = candidate['deletable_episodes']
            
            emoji = '🔴' if cleanup_type == 'dormant' else '🟡'
            
            cleanup_logger.info(f"{emoji} {series_title} (Rule: {rule_name})")
            cleanup_logger.info(f"   📋 {reason}")
            cleanup_logger.info(f"   📊 {deletable['description']}")
            
            if not dry_run and deletable['episode_file_ids']:
                success = delete_episodes_in_sonarr_batch(deletable['episode_file_ids'])
                if success:
                    processed_count += 1
                    stats[cleanup_type] += 1
                    cleanup_logger.info(f"   ✅ Deleted {deletable['episode_count']} episodes")
                else:
                    cleanup_logger.error(f"   ❌ Delete failed")
            elif dry_run:
                processed_count += 1
                stats[cleanup_type] += 1
                cleanup_logger.info(f"   🔍 DRY RUN: Would delete {deletable['episode_count']} episodes")
        
        cleanup_logger.info("=" * 80)
        cleanup_logger.info("✅ CORRECTED CLEANUP COMPLETED")
        cleanup_logger.info(f"📊 Processed: {processed_count} series")
        cleanup_logger.info(f"   🔴 Dormant (nuked): {stats['dormant']}")
        cleanup_logger.info(f"   🟡 Grace (unwatched): {stats['grace']}")
        cleanup_logger.info("=" * 80)
        
    except Exception as e:
        cleanup_logger.error(f"Error in corrected cleanup: {str(e)}")

# Global Storage Gate Implementation for servertosonarr.py

def load_global_settings():
    """Load global settings including storage gate."""
    try:
        settings_path = os.path.join(os.getcwd(), 'config', 'global_settings.json')
        
        if os.path.exists(settings_path):
            with open(settings_path, 'r') as f:
                return json.load(f)
        else:
            # Default settings
            default_settings = {
                'global_storage_min_gb': None,  # No storage gate by default
                'cleanup_interval_hours': 6,
                'dry_run_mode': False
            }
            save_global_settings(default_settings)
            return default_settings
    except Exception as e:
        logger.error(f"Error loading global settings: {str(e)}")
        return {'global_storage_min_gb': None}

def save_global_settings(settings):
    """Save global settings to file."""
    try:
        settings_path = os.path.join(os.getcwd(), 'config', 'global_settings.json')
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=4)
        logger.info("Global settings saved successfully")
    except Exception as e:
        logger.error(f"Error saving global settings: {str(e)}")

def check_global_storage_gate():
    """Check if global storage gate allows cleanup to proceed."""
    try:
        global_settings = load_global_settings()
        storage_min_gb = global_settings.get('global_storage_min_gb')
        
        if not storage_min_gb:
            # No storage gate configured - always allow cleanup
            return True, None, "No global storage gate - cleanup always enabled"
        
        disk_info = get_sonarr_disk_space()
        if not disk_info:
            return False, storage_min_gb, "Could not get disk space information"
        
        current_free_gb = disk_info['free_space_gb']
        
        if current_free_gb < storage_min_gb:
            return True, storage_min_gb, f"Storage gate OPEN: {current_free_gb:.1f}GB < {storage_min_gb}GB threshold"
        else:
            return False, storage_min_gb, f"Storage gate CLOSED: {current_free_gb:.1f}GB >= {storage_min_gb}GB threshold"
        
    except Exception as e:
        logger.error(f"Error checking global storage gate: {str(e)}")
        return False, None, f"Storage gate error: {str(e)}"

def get_cleanup_candidates_global_gate(config):
    """Get cleanup candidates using global storage gate."""
    try:
        # Check global storage gate first
        gate_open, threshold_gb, gate_reason = check_global_storage_gate()
        
        if not gate_open:
            logger.info(f"🔒 Global storage gate CLOSED: {gate_reason}")
            return [], threshold_gb, gate_reason
        
        logger.info(f"🔓 Global storage gate OPEN: {gate_reason}")
        
        # Get series from Sonarr
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        
        if not response.ok:
            logger.error("Failed to fetch series from Sonarr")
            return [], threshold_gb, "Sonarr API error"
        
        all_series = response.json()
        candidates = []
        activity_data = load_activity_tracking()
        
        stats = {'grace': 0, 'dormant': 0, 'protected': 0, 'no_cleanup': 0}
        
        logger.info("🔍 Checking rules with grace/dormant settings:")
        
        for rule_name, rule in config['rules'].items():
            grace_days = rule.get('grace_days')
            dormant_days = rule.get('dormant_days')
            
            # Skip rules without time-based cleanup
            if not grace_days and not dormant_days:
                stats['no_cleanup'] += len(rule.get('series', {}))
                logger.info(f"⏭️  Rule '{rule_name}': No grace/dormant settings - skipped")
                continue
                
            logger.info(f"📋 Rule '{rule_name}': Grace={grace_days}d, Dormant={dormant_days}d")
            
            series_dict = rule.get('series', {})
            rule_candidates = 0
            
            for series_id_str, series_data in series_dict.items():
                try:
                    series_id = int(series_id_str)
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    
                    if not series_info:
                        continue
                    
                    # Check cleanup eligibility
                    eligible, reason, cleanup_info = check_cleanup_eligibility_corrected(series_id, rule)
                    
                    if eligible:
                        # Get episodes using corrected logic
                        all_episodes = fetch_all_episodes(series_id)
                        episodes_with_files = [ep for ep in all_episodes if ep.get('hasFile', False)]
                        
                        if not episodes_with_files:
                            continue
                        
                        # Use corrected episode calculation based on cleanup type
                        if cleanup_info['type'] == 'grace':
                            deletable_episodes = calculate_grace_deletable_episodes(
                                all_episodes, activity_data, series_id_str
                            )
                        else:  # dormant
                            deletable_episodes = calculate_dormant_deletable_episodes(all_episodes)
                        
                        if deletable_episodes['episode_file_ids']:
                            candidates.append({
                                'series_id': series_id,
                                'title': series_info['title'],
                                'rule_name': rule_name,
                                'cleanup_reason': reason,
                                'cleanup_type': cleanup_info['type'],
                                'days_since_activity': cleanup_info['days_since_activity'],
                                'priority_score': cleanup_info['priority_score'],
                                'deletable_episodes': deletable_episodes
                            })
                            
                            stats[cleanup_info['type']] += 1
                            rule_candidates += 1
                            logger.debug(f"   ✅ {series_info['title']}: {reason}")
                        else:
                            logger.debug(f"   ⏭️ {series_info['title']}: {reason} but no deletable episodes")
                    else:
                        if "PROTECTED" in reason:
                            stats['protected'] += 1
                        logger.debug(f"   🛡️ {series_info['title']}: {reason}")
                        
                except ValueError:
                    continue
            
            logger.info(f"   📊 Rule '{rule_name}': {rule_candidates} candidates")
        
        # Sort by priority: Dormant first, then grace
        candidates.sort(key=lambda x: x['priority_score'], reverse=True)
        
        logger.info("=" * 60)
        logger.info(f"📋 GLOBAL STORAGE GATE CLEANUP:")
        logger.info(f"   🔴 Dormant (nuke all): {stats['dormant']}")
        logger.info(f"   🟡 Grace (unwatched only): {stats['grace']}")
        logger.info(f"   🛡️ Protected: {stats['protected']}")
        logger.info(f"   ⏭️ No cleanup rules: {stats['no_cleanup']}")
        logger.info(f"   📊 Total candidates: {len(candidates)}")
        logger.info("=" * 60)
        
        return candidates, threshold_gb, f"Found {len(candidates)} candidates"
        
    except Exception as e:
        logger.error(f"Error getting global gate cleanup candidates: {str(e)}")
        return [], None, f"Error: {str(e)}"
def get_sonarr_disk_space():
    """Get disk space information from Sonarr."""
    try:
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(f"{SONARR_URL}/api/v3/diskspace", headers=headers)
        if response.ok:
            diskspace_data = response.json()
            
            if diskspace_data:
                main_disk = max(diskspace_data, key=lambda x: x.get('totalSpace', 0))
                
                total_space_bytes = main_disk.get('totalSpace', 0)
                free_space_bytes = main_disk.get('freeSpace', 0)
                
                return {
                    'total_space_gb': round(total_space_bytes / (1024**3), 1),
                    'free_space_gb': round(free_space_bytes / (1024**3), 1),
                    'path': main_disk.get('path', 'Unknown')
                }
        return None
    except Exception as e:
        logger.error(f"Error getting disk space: {str(e)}")
        return None
    
def run_global_storage_gate_cleanup():
    """
    Main cleanup with global storage gate:
    1. Check global storage threshold
    2. If below threshold, run cleanup until back above threshold
    3. Process in order: dormant (oldest first) → grace (oldest first)
    4. Stop once back above threshold
    """
    try:
        cleanup_logger.info("=" * 80)
        cleanup_logger.info("🚀 STARTING GLOBAL STORAGE GATE CLEANUP")
        cleanup_logger.info("🎯 Will stop cleanup once back above threshold")
        
        config = load_config()
        global_settings = load_global_settings()
        dry_run = global_settings.get('dry_run_mode', False) or os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        
        # Get candidates (includes global storage gate check)
        candidates, threshold_gb, status = get_cleanup_candidates_global_gate(config)
        
        if not candidates:
            cleanup_logger.info(f"✅ {status}")
            return
        
        cleanup_logger.info(f"📋 {status}")
        cleanup_logger.info(f"🎯 Target: Get back above {threshold_gb}GB free space")
        cleanup_logger.info(f"🔧 Mode: {'DRY RUN' if dry_run else 'LIVE'}")
        
        # Process candidates in priority order until threshold met
        processed_count = 0
        stats = {'grace': 0, 'dormant': 0}
        
        for candidate in candidates:
            # Check if we're back above threshold (unless dry run)
            if not dry_run and threshold_gb:
                current_disk = get_sonarr_disk_space()
                if current_disk and current_disk['free_space_gb'] >= threshold_gb:
                    cleanup_logger.info(f"🎯 THRESHOLD MET: {current_disk['free_space_gb']:.1f}GB >= {threshold_gb}GB")
                    cleanup_logger.info(f"✅ Stopping cleanup - storage gate now CLOSED")
                    break
            
            series_title = candidate['title']
            rule_name = candidate['rule_name']
            cleanup_type = candidate['cleanup_type']
            reason = candidate['cleanup_reason']
            deletable = candidate['deletable_episodes']
            
            emoji = '🔴' if cleanup_type == 'dormant' else '🟡'
            
            cleanup_logger.info(f"{emoji} {series_title} (Rule: {rule_name})")
            cleanup_logger.info(f"   📋 {reason}")
            cleanup_logger.info(f"   📊 {deletable['description']}")
            
            if deletable['episode_file_ids']:
                # Use your existing logging function
                delete_episodes_in_sonarr_with_logging(deletable['episode_file_ids'], dry_run, series_title)
                processed_count += 1
                stats[cleanup_type] += 1
                
                if dry_run:
                    cleanup_logger.info(f"   🔍 DRY RUN: Would delete {deletable['episode_count']} episodes")
                else:
                    cleanup_logger.info(f"   ✅ Deleted {deletable['episode_count']} episodes")
                    
                    # Log current free space after deletion
                    current_disk = get_sonarr_disk_space()
                    if current_disk:
                        cleanup_logger.info(f"   💾 Free space now: {current_disk['free_space_gb']:.1f}GB")
            else:
                cleanup_logger.info(f"   ⏭️ No episodes to delete")
        
        # Final status
        final_disk = get_sonarr_disk_space()
        cleanup_logger.info("=" * 80)
        cleanup_logger.info("✅ GLOBAL STORAGE GATE CLEANUP COMPLETED")
        cleanup_logger.info(f"📊 Processed: {processed_count} series")
        cleanup_logger.info(f"   🔴 Dormant (nuked): {stats['dormant']}")
        cleanup_logger.info(f"   🟡 Grace (unwatched): {stats['grace']}")
        if final_disk and threshold_gb:
            gate_status = "CLOSED" if final_disk['free_space_gb'] >= threshold_gb else "OPEN"
            cleanup_logger.info(f"🚪 Storage gate now: {gate_status} ({final_disk['free_space_gb']:.1f}GB free)")
        cleanup_logger.info("=" * 80)
        
    except Exception as e:
        cleanup_logger.error(f"Error in global storage gate cleanup: {str(e)}")

def run_grace_watched_cleanup():
    """
    Scheduler function: Check all series for expired grace_watched timers.
    This runs periodically to clean up keep blocks that have been inactive too long.
    """
    try:
        cleanup_logger.info("🟡 GRACE WATCHED CLEANUP: Checking inactive keep blocks")
        
        config = load_config()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        
        # Get all series from Sonarr
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        
        if not response.ok:
            cleanup_logger.error("Failed to fetch series from Sonarr for grace_watched cleanup")
            return 0
        
        all_series = response.json()
        processed_count = 0
        
        # Check each rule for grace_watched settings
        for rule_name, rule in config['rules'].items():
            if not rule.get('grace_watched'):
                continue
                
            cleanup_logger.info(f"📋 Rule '{rule_name}': Checking grace_watched ({rule['grace_watched']} days)")
            rule_dry_run = rule.get('dry_run', False)
            is_dry_run = global_dry_run or rule_dry_run
            
            # Check each series in this rule
            series_dict = rule.get('series', {})
            for series_id_str in series_dict.keys():
                try:
                    series_id = int(series_id_str)
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    
                    if not series_info:
                        continue
                    
                    series_title = series_info['title']
                    
                    # Check if grace_watched timer has expired
                    expired_episodes = check_grace_watched_expiry(series_id)
                    
                    if expired_episodes:
                        episode_file_ids = [ep['episode_file_id'] for ep in expired_episodes if ep.get('episode_file_id')]
                        
                        if episode_file_ids:
                            cleanup_logger.info(f"🟡 {series_title}: Grace watched expired - keep block inactive too long")
                            delete_episodes_in_sonarr_with_logging(episode_file_ids, is_dry_run, series_title)
                            processed_count += 1
                            
                except (ValueError, TypeError):
                    continue
        
        cleanup_logger.info(f"🟡 Grace watched cleanup: Processed {processed_count} series")
        return processed_count
        
    except Exception as e:
        cleanup_logger.error(f"Error in grace_watched cleanup: {str(e)}")
        return 0


def run_grace_unwatched_cleanup():
    """
    Scheduler function: Check all series for expired grace_unwatched episodes.
    This runs periodically to clean up episodes that were downloaded but not watched within deadline.
    """
    try:
        cleanup_logger.info("⏰ GRACE UNWATCHED CLEANUP: Checking unwatched episode deadlines")
        
        config = load_config()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        
        # Get all series from Sonarr
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers)
        
        if not response.ok:
            cleanup_logger.error("Failed to fetch series from Sonarr for grace_unwatched cleanup")
            return 0
        
        all_series = response.json()
        processed_count = 0
        
        # Check each rule for grace_unwatched settings
        for rule_name, rule in config['rules'].items():
            if not rule.get('grace_unwatched'):
                continue
                
            cleanup_logger.info(f"📋 Rule '{rule_name}': Checking grace_unwatched ({rule['grace_unwatched']} days)")
            rule_dry_run = rule.get('dry_run', False)
            is_dry_run = global_dry_run or rule_dry_run
            
            # Check each series in this rule
            series_dict = rule.get('series', {})
            for series_id_str in series_dict.keys():
                try:
                    series_id = int(series_id_str)
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    
                    if not series_info:
                        continue
                    
                    series_title = series_info['title']
                    
                    # Check for expired unwatched episodes
                    expired_episodes = check_grace_unwatched_expiry(series_id)
                    
                    if expired_episodes:
                        episode_file_ids = [ep['episode_file_id'] for ep in expired_episodes if ep.get('episode_file_id')]
                        
                        if episode_file_ids:
                            cleanup_logger.info(f"⏰ {series_title}: {len(episode_file_ids)} episodes exceeded watch deadline")
                            delete_episodes_in_sonarr_with_logging(episode_file_ids, is_dry_run, series_title)
                            processed_count += 1
                            
                except (ValueError, TypeError):
                    continue
        
        cleanup_logger.info(f"⏰ Grace unwatched cleanup: Processed {processed_count} series")
        return processed_count
        
    except Exception as e:
        cleanup_logger.error(f"Error in grace_unwatched cleanup: {str(e)}")
        return 0


# =============================================================================
# UPDATED: Main Scheduler Function
# =============================================================================

def main():
    """Main entry point - SIMPLIFIED with unified grace cleanup."""
    series_name, season_number, episode_number = get_server_activity()
    
    if series_name:
        # Webhook mode
        series_id = get_series_id(series_name)
        if series_id:
            config = load_config()
            rule = None
            for rule_name, rule_details in config['rules'].items():
                if str(series_id) in rule_details.get('series', {}):
                    rule = rule_details
                    break
            
            if rule:
                process_episodes_for_webhook(series_id, season_number, episode_number, rule)
            else:
                update_activity_date(series_id, season_number, episode_number)
    else:
        # Scheduler mode - SIMPLIFIED cleanup cycle
        cleanup_logger.info("🚀 STARTING SIMPLIFIED GRACE CLEANUP CYCLE")
        
        unified_count = run_unified_grace_cleanup()        # All grace types in one function
        unwatched_count = run_grace_unwatched_cleanup()    # Still separate (different data structure)
        dormant_count = run_dormant_cleanup()              # Separate (different purpose)
        
        total_processed = unified_count + unwatched_count + dormant_count
        cleanup_logger.info(f"✅ SIMPLIFIED CLEANUP CYCLE COMPLETED: {total_processed} total operations")
        cleanup_logger.info(f"   🗑️ Unified: {unified_count}, ⏰ Unwatched: {unwatched_count}, 🔴 Dormant: {dormant_count}")


if __name__ == "__main__":
    main()
