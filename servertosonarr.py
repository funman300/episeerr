import os
import requests
import logging
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

# Time-based cleanup tracking
ACTIVITY_TRACKING_FILE = os.path.join(os.getcwd(), 'data', 'activity_tracking.json')
os.makedirs(os.path.dirname(ACTIVITY_TRACKING_FILE), exist_ok=True)

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

def update_last_watched(series_id, season_number, episode_number):
    """Update the last watched timestamp and episode for a series."""
    try:
        activity_data = load_activity_tracking()
        current_time = int(time.time())
        
        series_id_str = str(series_id)
        if series_id_str not in activity_data:
            activity_data[series_id_str] = {}
        
        activity_data[series_id_str]['last_watched'] = current_time
        activity_data[series_id_str]['last_updated'] = current_time
        activity_data[series_id_str]['last_season'] = season_number
        activity_data[series_id_str]['last_episode'] = episode_number
        
        save_activity_tracking(activity_data)
        logger.info(f"Updated activity for series {series_id}: S{season_number}E{episode_number}")
        
    except Exception as e:
        logger.error(f"Error updating last watched for series {series_id}: {str(e)}")

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

# =============================================================================
# WEBHOOK PROCESSING - ACTIVITY TRACKING + NEXT CONTENT ONLY
# =============================================================================

def process_episodes_for_webhook(series_id, season_number, episode_number, rule):
    """
    WEBHOOK-ONLY PROCESSING: Track activity and get next content.
    NO DELETIONS - that's handled by the scheduler.
    """
    try:
        logger.info(f"Processing webhook for series {series_id}: S{season_number}E{episode_number}")
        
        # 1. Update activity tracking (ALWAYS do this)
        update_last_watched(series_id, season_number, episode_number)
        
        # 2. Get the current episode ID
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
        
        # 3. Unmonitor current episode if rule says so
        if not rule.get('monitor_watched', True):
            unmonitor_episodes([current_episode_id])
            logger.info(f"Unmonitored current episode S{season_number}E{episode_number}")
        
        # 4. Get and monitor/search next content
        next_episode_ids = fetch_next_episodes(series_id, season_number, episode_number, rule['get_option'])
        if next_episode_ids:
            monitor_or_search_episodes(next_episode_ids, rule.get('action_option', 'monitor'))
            logger.info(f"Processed {len(next_episode_ids)} next episodes with action: {rule.get('action_option', 'monitor')}")
        else:
            logger.info("No next episodes to process")
            
        logger.info(f"Webhook processing complete for series {series_id}")
        
    except Exception as e:
        logger.error(f"Error in webhook processing for series {series_id}: {str(e)}", exc_info=True)

# =============================================================================
# SCHEDULER PROCESSING - ALL CLEANUP LOGIC
# =============================================================================

def check_time_based_cleanup(series_id, rule):
    """Check if time-based cleanup should be performed for a series."""
    try:
        keep_unwatched_days = rule.get('keep_unwatched_days')
        keep_watched_days = rule.get('keep_watched_days')
        
        # If both are null/empty, no time-based cleanup
        if not keep_unwatched_days and not keep_watched_days:
            return False, "No time-based cleanup configured"
        
        activity_data = load_activity_tracking()
        series_id_str = str(series_id)
        current_time = int(time.time())
        
        # Get series activity data
        series_activity = activity_data.get(series_id_str, {})
        last_watched = series_activity.get('last_watched', 0)
        
        # Check inactivity timer (keep_unwatched_days) - NUCLEAR CLEANUP
        if keep_unwatched_days:
            try:
                unwatched_threshold = int(keep_unwatched_days) * 24 * 60 * 60  # Convert days to seconds
                time_since_watched = current_time - last_watched
                
                if time_since_watched > unwatched_threshold:
                    logger.info(f"Series {series_id} exceeded inactivity threshold ({keep_unwatched_days} days)")
                    return True, f"Nuclear cleanup: {keep_unwatched_days} days without watching"
            except (ValueError, TypeError):
                logger.warning(f"Invalid keep_unwatched_days value: {keep_unwatched_days}")
        
        # Check watched grace period (keep_watched_days) - SURGICAL CLEANUP
        if keep_watched_days and last_watched > 0:
            try:
                watched_threshold = int(keep_watched_days) * 24 * 60 * 60  # Convert days to seconds
                time_since_watched = current_time - last_watched
                
                if time_since_watched > watched_threshold:
                    logger.info(f"Series {series_id} exceeded watched grace period ({keep_watched_days} days)")
                    return True, f"Surgical cleanup: {keep_watched_days} days after last watch"
            except (ValueError, TypeError):
                logger.warning(f"Invalid keep_watched_days value: {keep_watched_days}")
        
        return False, "Time thresholds not met"
        
    except Exception as e:
        logger.error(f"Error in time-based cleanup check: {str(e)}")
        return False, f"Error: {str(e)}"

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

def delete_episodes_in_sonarr(episode_file_ids):
    """Delete specified episodes in Sonarr."""
    if not episode_file_ids:
        logger.info("No episodes to delete.")
        return

    logger.info(f"Deleting {len(episode_file_ids)} episode files")
    failed_deletes = []
    
    for episode_file_id in episode_file_ids:
        try:
            url = f"{SONARR_URL}/api/v3/episodeFile/{episode_file_id}"
            headers = {'X-Api-Key': SONARR_API_KEY}
            response = requests.delete(url, headers=headers)
            response.raise_for_status()  # Raise an HTTPError for bad responses
            logger.info(f"Successfully deleted episode file with ID: {episode_file_id}")
        except requests.exceptions.HTTPError as http_err:
            logger.error(f"HTTP error occurred: {http_err} - Response: {response.text}")
            failed_deletes.append(episode_file_id)
        except Exception as err:
            logger.error(f"Other error occurred: {err}")
            failed_deletes.append(episode_file_id)

    if failed_deletes:
        logger.error(f"Failed to delete the following episode files: {failed_deletes}")

def perform_time_based_cleanup(series_id, rule, cleanup_reason):
    """Perform time-based cleanup for a series."""
    try:
        logger.info(f"Performing time-based cleanup for series {series_id}: {cleanup_reason}")
        
        all_episodes = fetch_all_episodes(series_id)
        keep_watched = rule.get('keep_watched', 'all')
        
        # Get activity data to determine last watched episode
        activity_data = load_activity_tracking()
        series_activity = activity_data.get(str(series_id), {})
        last_watched_season = series_activity.get('last_season', 1)
        last_watched_episode = series_activity.get('last_episode', 1)
        
        # Determine cleanup type based on reason
        if "Nuclear cleanup" in cleanup_reason:
            # Inactivity timer triggered - nuclear cleanup
            episodes_to_delete = find_episodes_to_delete_nuclear(all_episodes, keep_watched)
            logger.info(f"Nuclear cleanup for series {series_id}")
        else:
            # Grace period expired - surgical cleanup
            episodes_to_delete = find_episodes_to_delete_surgical(
                all_episodes, keep_watched, last_watched_season, last_watched_episode
            )
            logger.info(f"Surgical cleanup for series {series_id}")
        
        if episodes_to_delete:
            logger.info(f"Time-based cleanup will delete {len(episodes_to_delete)} episode files")
            delete_episodes_in_sonarr(episodes_to_delete)
        else:
            logger.info(f"No episodes to delete for series {series_id}")
            
    except Exception as e:
        logger.error(f"Error in time-based cleanup for series {series_id}: {str(e)}")

def run_periodic_cleanup():
    """Run periodic time-based cleanup for all series with time-based rules."""
    try:
        logger.info("Starting periodic time-based cleanup check")
        
        config = load_config()
        
        # Get all series from Sonarr
        url = f"{SONARR_URL}/api/v3/series"
        headers = {'X-Api-Key': SONARR_API_KEY}
        response = requests.get(url, headers=headers)
        
        if not response.ok:
            logger.error("Failed to fetch series from Sonarr for cleanup")
            return
        
        all_series = response.json()
        cleanup_count = 0
        
        # Check each rule for time-based cleanup settings
        for rule_name, rule in config['rules'].items():
            series_ids = rule.get('series', [])
            
            # Skip if no time-based cleanup configured
            if not rule.get('keep_unwatched_days') and not rule.get('keep_watched_days'):
                continue
                
            logger.info(f"Checking rule '{rule_name}' for time-based cleanup ({len(series_ids)} series)")
            
            for series_id_str in series_ids:
                try:
                    series_id = int(series_id_str)
                    
                    # Find the series in our list
                    series_info = next((s for s in all_series if s['id'] == series_id), None)
                    if not series_info:
                        logger.warning(f"Series {series_id} not found in Sonarr")
                        continue
                    
                    # Check if cleanup should be performed
                    should_cleanup, reason = check_time_based_cleanup(series_id, rule)
                    
                    if should_cleanup:
                        logger.info(f"Performing cleanup for '{series_info['title']}': {reason}")
                        perform_time_based_cleanup(series_id, rule, reason)
                        cleanup_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing series {series_id_str} for cleanup: {str(e)}")
        
        logger.info(f"Periodic cleanup completed. Processed {cleanup_count} series")
        
    except Exception as e:
        logger.error(f"Error in periodic cleanup: {str(e)}")

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
    """Main entry point - called by webhook, handles activity tracking only."""
    series_name, season_number, episode_number = get_server_activity()
    
    if series_name:
        series_id = get_series_id(series_name)
        if series_id:
            # Find the rule for this series
            rule = next(
                (details for key, details in config['rules'].items() 
                 if str(series_id) in details.get('series', [])), 
                None
            )
            
            if rule:
                logger.info(f"Applying rule for webhook: {rule}")
                # WEBHOOK PROCESSING - NO DELETIONS
                process_episodes_for_webhook(series_id, season_number, episode_number, rule)
            else:
                logger.info(f"No rule found for series ID {series_id}. Only tracking activity.")
                # Still track activity even without a rule
                update_last_watched(series_id, season_number, episode_number)
        else:
            logger.error(f"Series ID not found for series: {series_name}")
    else:
        logger.info("No server activity found - running periodic cleanup")
        # Run periodic cleanup when no server activity
        run_periodic_cleanup()

if __name__ == "__main__":
    main()