__version__ = "2.0.0"
from flask import Flask, render_template, request, redirect, url_for, jsonify
import subprocess
import os
import re
import time
import logging
import json
import sonarr_utils

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import requests
import modified_episeerr
import threading
from functools import lru_cache
from logging.handlers import RotatingFileHandler

app = Flask(__name__)

# Load environment variables
load_dotenv()
BASE_DIR = os.getcwd()
# Sonarr variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Jellyseerr variables
JELLYSEERR_URL = os.getenv('JELLYSEERR_URL', '')

# Global variable to track pending requests from Jellyseerr
# Format: {tvdb_id: {request_id: "123", title: "Show Title"}}
jellyseerr_pending_requests = {}

# Other settings
REQUESTS_DIR = os.path.join(os.getcwd(), 'data', 'requests')
os.makedirs(REQUESTS_DIR, exist_ok=True)

LAST_PROCESSED_FILE = os.path.join(os.getcwd(), 'data', 'last_processed.json')
os.makedirs(os.path.dirname(LAST_PROCESSED_FILE), exist_ok=True)

# Setup logging to capture all logs
log_file = os.getenv('LOG_PATH', os.path.join(os.getcwd(), 'logs', 'app.log'))

log_level = logging.INFO  # Capture INFO and ERROR levels

# Create log directory if it doesn't exist
os.makedirs(os.path.dirname(log_file), exist_ok=True)

# Create a RotatingFileHandler
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=1*1024*1024,  # 1 MB max size
    backupCount=2,  # Keep 2 backup files
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Configure the root logger
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler]
)

# Adding stream handler to also log to console for Docker logs to capture
stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG if os.getenv('FLASK_DEBUG', 'false').lower() == 'true' else logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
stream_handler.setFormatter(formatter)
app.logger.addHandler(stream_handler)

# Configuration management
config_path = os.path.join(app.root_path, 'config', 'config.json')

def load_config():
    """Load configuration from JSON file."""
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
        if 'rules' not in config:
            config['rules'] = {}
        return config
    except FileNotFoundError:
        default_config = {
            'rules': {
                'full_seasons': {
                    'get_option': 'season',
                    'action_option': 'monitor',
                    'keep_watched': 'season',
                    'monitor_watched': False,
                    'series': []
                },
                'one_at_a_time': {
                    'get_option': '1',
                    'action_option': 'search',
                    'keep_watched': '1',
                    'monitor_watched': False,
                    'series': []
                }
            },
            'default_rule': 'full_seasons'
        }
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        save_config(default_config)
        return default_config

def save_config(config):
    """Save configuration to JSON file."""
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)

def get_sonarr_series():
    """Get all series from Sonarr."""
    try:
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
        if response.ok:
            return response.json()
        else:
            app.logger.error(f"Failed to fetch series from Sonarr: {response.status_code}")
            return []
    except Exception as e:
        app.logger.error(f"Error fetching Sonarr series: {str(e)}")
        return []

@app.route('/')
def index():
    """Main rules management page."""
    config = load_config()
    
    all_series = get_sonarr_series()
    
    rules_mapping = {}
    for rule_name, details in config['rules'].items():
        for series_id in details.get('series', []):
            rules_mapping[str(series_id)] = rule_name
    
    for series in all_series:
        series['assigned_rule'] = rules_mapping.get(str(series['id']), 'None')
    
    all_series.sort(key=lambda x: x.get('title', '').lower())
    
    return render_template('rules_index.html', 
                         config=config,
                         all_series=all_series,
                         current_rule=request.args.get('rule', list(config['rules'].keys())[0] if config['rules'] else 'full_seasons'))

@app.route('/create-rule', methods=['GET', 'POST'])
def create_rule():
    """Create a new rule."""
    if request.method == 'POST':
        config = load_config()
        
        rule_name = request.form.get('rule_name', '').strip()
        if not rule_name:
            return redirect(url_for('index', message="Rule name is required"))
        
        if rule_name in config['rules']:
            return redirect(url_for('index', message=f"Rule '{rule_name}' already exists"))
        
        config['rules'][rule_name] = {
            'get_option': request.form.get('get_option', ''),
            'action_option': request.form.get('action_option', 'monitor'),
            'keep_watched': request.form.get('keep_watched', ''),
            'monitor_watched': request.form.get('monitor_watched', 'false').lower() == 'true',
            'series': []
        }
        
        save_config(config)
        return redirect(url_for('index', message=f"Rule '{rule_name}' created successfully"))
    
    return render_template('create_rule.html')

@app.route('/edit-rule/<rule_name>', methods=['GET', 'POST'])
def edit_rule(rule_name):
    """Edit an existing rule."""
    config = load_config()
    
    if rule_name not in config['rules']:
        return redirect(url_for('index', message=f"Rule '{rule_name}' not found"))
    
    if request.method == 'POST':
        config['rules'][rule_name].update({
            'get_option': request.form.get('get_option', ''),
            'action_option': request.form.get('action_option', 'monitor'),
            'keep_watched': request.form.get('keep_watched', ''),
            'monitor_watched': request.form.get('monitor_watched', 'false').lower() == 'true'
        })
        
        save_config(config)
        return redirect(url_for('index', message=f"Rule '{rule_name}' updated successfully"))
    
    rule = config['rules'][rule_name]
    return render_template('edit_rule.html', rule_name=rule_name, rule=rule)

@app.route('/delete-rule/<rule_name>', methods=['POST'])
def delete_rule(rule_name):
    """Delete a rule."""
    config = load_config()
    
    if rule_name not in config['rules']:
        return redirect(url_for('index', message=f"Rule '{rule_name}' not found"))
    
    if rule_name == config.get('default_rule'):
        return redirect(url_for('index', message="Cannot delete the default rule"))
    
    del config['rules'][rule_name]
    save_config(config)
    
    return redirect(url_for('index', message=f"Rule '{rule_name}' deleted successfully"))

@app.route('/assign-rules', methods=['POST'])
def assign_rules():
    """Assign series to rules."""
    config = load_config()
    
    rule_name = request.form.get('rule_name')
    series_ids = request.form.getlist('series_ids')
    
    if not rule_name or rule_name not in config['rules']:
        return redirect(url_for('index', message="Invalid rule selected"))
    
    for rule, details in config['rules'].items():
        details['series'] = [sid for sid in details.get('series', []) if sid not in series_ids]
    
    config['rules'][rule_name]['series'].extend(series_ids)
    
    save_config(config)
    
    return redirect(url_for('index', message=f"Assigned {len(series_ids)} series to rule '{rule_name}'"))

@app.route('/unassign-series', methods=['POST'])
def unassign_series():
    """Remove series from all rules."""
    config = load_config()
    
    series_ids = request.form.getlist('series_ids')
    
    total_removed = 0
    for rule_name, details in config['rules'].items():
        original_count = len(details.get('series', []))
        details['series'] = [sid for sid in details['series'] if sid not in series_ids]
        total_removed += original_count - len(details['series'])
    
    save_config(config)
    
    return redirect(url_for('index', message=f"Unassigned {len(series_ids)} series from all rules"))

@app.route('/set-default-rule', methods=['POST'])
def set_default_rule():
    """Set the default rule."""
    config = load_config()
    
    rule_name = request.form.get('rule_name')
    
    if rule_name not in config['rules']:
        return redirect(url_for('index', message="Invalid rule selected"))
    
    config['default_rule'] = rule_name
    save_config(config)
    
    return redirect(url_for('index', message=f"Set '{rule_name}' as default rule"))

@app.route('/api/recent-activity')
def get_recent_activity():
    """Get recent rule applications and downloads for banner updates."""
    try:
        # This could be enhanced to track actual recent activity
        # For now, return empty to avoid errors
        return jsonify({
            "recentDownloads": [],
            "recentRuleApplications": []
        })
        
    except Exception as e:
        app.logger.error(f"Error getting recent activity: {str(e)}")
        return jsonify({
            "recentDownloads": [],
            "recentRuleApplications": []
        }), 500

@app.route('/api/series-stats')
def series_stats():
    """Get statistics about series and rules."""
    try:
        config = load_config()
        all_series = get_sonarr_series()
        
        rules_mapping = {}
        for rule_name, details in config['rules'].items():
            for series_id in details.get('series', []):
                rules_mapping[str(series_id)] = rule_name
        
        stats = {
            'total_series': len(all_series),
            'assigned_series': len(rules_mapping),
            'unassigned_series': len(all_series) - len(rules_mapping),
            'total_rules': len(config['rules']),
            'rule_breakdown': {}
        }
        
        for rule_name, details in config['rules'].items():
            stats['rule_breakdown'][rule_name] = len(details.get('series', []))
        
        return jsonify(stats)
        
    except Exception as e:
        app.logger.error(f"Error getting series stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

def cleanup_config_rules():
    """Remove series from rules that no longer exist in Sonarr."""
    try:
        config = load_config()
        existing_series = get_sonarr_series()
        existing_series_ids = set(str(series['id']) for series in existing_series)
        
        changes_made = False
        
        for rule_name, rule_details in config['rules'].items():
            original_count = len(rule_details.get('series', []))
            rule_details['series'] = [
                series_id for series_id in rule_details.get('series', [])
                if series_id in existing_series_ids
            ]
            
            if len(rule_details['series']) != original_count:
                removed_count = original_count - len(rule_details['series'])
                app.logger.info(f"Cleaned up rule '{rule_name}': Removed {removed_count} non-existent series")
                changes_made = True
        
        config['rules'] = {
            rule: details for rule, details in config['rules'].items()
            if details.get('series') or rule == config.get('default_rule', 'full_seasons')
        }
        
        if changes_made:
            save_config(config)
            app.logger.info("Configuration cleanup completed")
            
    except Exception as e:
        app.logger.error(f"Error during config cleanup: {str(e)}")

@app.route('/cleanup')
def cleanup():
    """Manual cleanup of rules."""
    cleanup_config_rules()
    return redirect(url_for('index', message="Configuration cleaned up successfully"))

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message="Internal server error"), 500

@app.route('/update-settings', methods=['POST'])
def update_settings():
    config = load_config()
    
    rule_name = request.form.get('rule_name')
    if rule_name == 'add_new':
        rule_name = request.form.get('new_rule_name')
        if not rule_name:
            return redirect(url_for('index', message="New rule name is required."))
    
    get_option = request.form.get('get_option')
    keep_watched = request.form.get('keep_watched')

    config['rules'][rule_name] = {
        'get_option': get_option,
        'action_option': request.form.get('action_option'),
        'keep_watched': keep_watched,
        'monitor_watched': request.form.get('monitor_watched', 'false').lower() == 'true',
        'series': config['rules'].get(rule_name, {}).get('series', [])
    }
    
    save_config(config)
    return redirect(url_for('index', message="Settings updated successfully"))

@app.route('/unassign_rules', methods=['POST'])
def unassign_rules():
    config = load_config()
    rule_name = request.form.get('assign_rule_name')
    submitted_series_ids = set(request.form.getlist('series_ids'))

    # Update the rule's series list to exclude those submitted
    if rule_name in config['rules']:
        current_series = set(config['rules'][rule_name]['series'])
        updated_series = current_series.difference(submitted_series_ids)
        config['rules'][rule_name]['series'] = list(updated_series)

    save_config(config)
    return redirect(url_for('index', message="Rules updated successfully."))

# WEBHOOK ROUTES

@app.route('/sonarr-webhook', methods=['POST'])
def process_sonarr_webhook():
    """Handle incoming Sonarr webhooks for series additions."""
    app.logger.info("Received webhook from Sonarr")
    
    try:
        json_data = request.json
        
        # Check if this is a "SeriesAdd" event
        event_type = json_data.get('eventType')
        if event_type != 'SeriesAdd':
            return jsonify({"message": "Not a series add event"}), 200
            
        # Get important data from the webhook
        series = json_data.get('series', {})
        series_id = series.get('id')
        tvdb_id = series.get('tvdbId')
        tmdb_id = series.get('tmdbId')
        series_title = series.get('title')
        
        app.logger.info(f"Processing series addition: {series_title} (ID: {series_id}, TVDB: {tvdb_id})")
        
        # Setup Sonarr connection
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']

        # First, get all tags from Sonarr
        tags_response = requests.get(f"{sonarr_url}/api/v3/tag", headers=headers)
        tags = tags_response.json()

        # Create a mapping of tag IDs to tag labels
        tag_mapping = {tag['id']: tag['label'] for tag in tags}

        # Check series tags
        series_tags = series.get('tags', [])
        app.logger.info(f"Series tags: {series_tags}")
        app.logger.info(f"Tag mapping: {tag_mapping}")

        # Check if any of the tags match the 'ocdarr' label
        # Handle both tag IDs (numbers) and tag names (strings) from webhook
        has_ocdarr_tag = False
        for tag in series_tags:
            if isinstance(tag, int):
                # Tag is an ID, look it up in mapping
                if tag_mapping.get(tag, '').lower() == 'ocdarr':
                    has_ocdarr_tag = True
                    break
            else:
                # Tag is already a name/string
                if str(tag).lower() == 'ocdarr':
                    has_ocdarr_tag = True
                    break
        
        # If no ocdarr tag, just exit
        if not has_ocdarr_tag:
            app.logger.info(f"Series {series_title} has no ocdarr tag, skipping processing")
            
            return jsonify({
                "status": "success",
                "message": "Series has no ocdarr tag, no processing needed"
            }), 200
        
        # If it has ocdarr tag, proceed with full processing
        app.logger.info(f"Series {series_title} has ocdarr tag, proceeding with processing")
        global jellyseerr_pending_requests
        app.logger.info(f"Looking for TVDB ID {tvdb_id} in pending requests")

        tvdb_id_str = str(tvdb_id)
        if tvdb_id_str in jellyseerr_pending_requests:
            jellyseerr_request = jellyseerr_pending_requests[tvdb_id_str]
            app.logger.info(f"Found matching Jellyseerr request for {series_title}: {jellyseerr_request}")
        
            # Delete the Jellyseerr request if it exists
            if jellyseerr_request and 'request_id' in jellyseerr_request:
                request_id = jellyseerr_request['request_id']
                app.logger.info(f"Canceling Jellyseerr request {request_id} for {series_title}")
            
                # Direct cancellation
                result = modified_episeerr.delete_overseerr_request(request_id)
                app.logger.info(f"Jellyseerr cancellation result: {result}")
            
                # Remove from pending requests
                del jellyseerr_pending_requests[tvdb_id_str]
                app.logger.info(f"Removed request {request_id} from pending requests dictionary")
        else:
            app.logger.info(f"No matching Jellyseerr request found for TVDB ID: {tvdb_id_str}")
            
        # Check if a request already exists for this series
        existing_request = None
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(REQUESTS_DIR, filename), 'r') as f:
                        request_data = json.load(f)
                        # Check if this is a request for the same series
                        if (request_data.get('series_id') == series_id or 
                            (tmdb_id and request_data.get('tmdb_id') == tmdb_id) or 
                            (tvdb_id and request_data.get('tvdb_id') == tvdb_id)):
                            existing_request = request_data
                            app.logger.info(f"Found existing request for {series_title}")
                            break
                except Exception as e:
                    app.logger.error(f"Error reading request file {filename}: {str(e)}")
        
        # If a request already exists, don't create a new one
        if existing_request:
            app.logger.info(f"Using existing request for {series_title}")
            return jsonify({
                "status": "success",
                "message": "Request already exists for this series"
            }), 200
        
        # 1. Unmonitor ALL episodes
        try:
            # Get all episodes for the series
            episodes_response = requests.get(
                f"{sonarr_url}/api/v3/episode?seriesId={series_id}",
                headers=headers
            )
            
            if episodes_response.ok and episodes_response.json():
                all_episodes = episodes_response.json()
                all_episode_ids = [episode["id"] for episode in all_episodes]
                
                if all_episode_ids:
                    unmonitor_response = requests.put(
                        f"{sonarr_url}/api/v3/episode/monitor",
                        headers=headers,
                        json={"episodeIds": all_episode_ids, "monitored": False}
                    )
                    
                    if unmonitor_response.ok:
                        app.logger.info(f"Unmonitored all episodes for series {series_title}")
                    else:
                        app.logger.error(f"Failed to unmonitor episodes: {unmonitor_response.text}")
        except Exception as e:
            app.logger.error(f"Error unmonitoring episodes: {str(e)}")
        
        # 2. Cancel any active downloads
        try:
            modified_episeerr.check_and_cancel_unmonitored_downloads()
        except Exception as e:
            app.logger.error(f"Error cancelling downloads: {str(e)}")
        
        # 3. Add to default rule
        config = load_config()
        default_rule_name = config.get('default_rule', 'Default')

        if default_rule_name in config['rules']:
            series_id_str = str(series_id)
            
            if 'series' not in config['rules'][default_rule_name]:
                config['rules'][default_rule_name]['series'] = []
            
            if series_id_str not in config['rules'][default_rule_name]['series']:
                config['rules'][default_rule_name]['series'].append(series_id_str)
                save_config(config)
                app.logger.info(f"Added series {series_title} (ID: {series_id}) to default rule")

        # 4. Execute the default rule immediately for new series
        try:
            rule_config = config['rules'][default_rule_name]
            get_option = rule_config.get('get_option')
            action_option = rule_config.get('action_option', 'monitor')
            
            app.logger.info(f"Executing default rule '{default_rule_name}' with get_option '{get_option}' for new series {series_title}")
            
            # Get all episodes for the series (we already have this from step 1, but get fresh data)
            episodes_response = requests.get(
                f"{sonarr_url}/api/v3/episode?seriesId={series_id}",
                headers=headers
            )
            
            if episodes_response.ok:
                all_episodes = episodes_response.json()
                
                # Get Season 1 episodes, sorted by episode number
                season1_episodes = sorted(
                    [ep for ep in all_episodes if ep.get('seasonNumber') == 1],
                    key=lambda x: x.get('episodeNumber', 0)
                )
                
                if not season1_episodes:
                    app.logger.warning(f"No Season 1 episodes found for {series_title}")
                else:
                    # Determine which episodes to monitor based on get_option
                    episodes_to_monitor = []
                    
                    if get_option == 'all':
                        # Get all episodes from all seasons
                        episodes_to_monitor = [ep['id'] for ep in all_episodes]
                        app.logger.info(f"Getting all episodes for {series_title}")
                        
                    elif get_option == 'season':
                        # Get all episodes from Season 1
                        episodes_to_monitor = [ep['id'] for ep in season1_episodes]
                        app.logger.info(f"Getting Season 1 ({len(episodes_to_monitor)} episodes) for {series_title}")
                        
                    else:
                        try:
                            # Treat as number of episodes to get from Season 1
                            num_episodes = int(get_option)
                            episodes_to_monitor = [ep['id'] for ep in season1_episodes[:num_episodes]]
                            app.logger.info(f"Getting first {len(episodes_to_monitor)} episodes for {series_title}")
                        except (ValueError, TypeError):
                            # Fallback to pilot episode if get_option is invalid
                            episodes_to_monitor = [season1_episodes[0]['id']] if season1_episodes else []
                            app.logger.warning(f"Invalid get_option '{get_option}', defaulting to pilot episode for {series_title}")
                    
                    if episodes_to_monitor:
                        # Monitor the selected episodes
                        monitor_response = requests.put(
                            f"{sonarr_url}/api/v3/episode/monitor",
                            headers=headers,
                            json={"episodeIds": episodes_to_monitor, "monitored": True}
                        )
                        
                        if monitor_response.ok:
                            app.logger.info(f"Monitored {len(episodes_to_monitor)} episodes for {series_title}")
                            
                            # Search for episodes if action_option is 'search'
                            if action_option == 'search':
                                search_response = requests.post(
                                    f"{sonarr_url}/api/v3/command",
                                    headers=headers,
                                    json={"name": "EpisodeSearch", "episodeIds": episodes_to_monitor}
                                )
                                
                                if search_response.ok:
                                    app.logger.info(f"Started search for {len(episodes_to_monitor)} episodes of {series_title}")
                                else:
                                    app.logger.error(f"Failed to search for episodes: {search_response.text}")
                        else:
                            app.logger.error(f"Failed to monitor episodes: {monitor_response.text}")
                    else:
                        app.logger.warning(f"No episodes to monitor for {series_title}")
            else:
                app.logger.error(f"Failed to get episodes for series: {episodes_response.text}")
        except Exception as e:
            app.logger.error(f"Error executing default rule for new series: {str(e)}", exc_info=True)
        
        # 5. Remove ocdarr tag after successful rule execution
        try:
            # Get the current series info to check tags
            series_response = requests.get(f"{sonarr_url}/api/v3/series/{series_id}", headers=headers)
            if series_response.ok:
                current_series = series_response.json()
                
                # Check if ocdarr tag exists and remove it
                if modified_episeerr.OCDARR_TAG_ID in current_series.get('tags', []):
                    updated_tags = [tag for tag in current_series.get('tags', []) if tag != modified_episeerr.OCDARR_TAG_ID]
                    
                    update_payload = current_series.copy()
                    update_payload['tags'] = updated_tags
                    
                    update_response = requests.put(f"{sonarr_url}/api/v3/series", headers=headers, json=update_payload)
                    if update_response.ok:
                        app.logger.info(f"Removed ocdarr tag from series {series_title} (ID: {series_id}) after rule execution")
                    else:
                        app.logger.error(f"Failed to remove ocdarr tag: {update_response.text}")
                else:
                    app.logger.info(f"Series {series_title} does not have ocdarr tag to remove")
            else:
                app.logger.error(f"Failed to get series info for tag removal: {series_response.text}")
        except Exception as tag_error:
            app.logger.error(f"Error removing ocdarr tag: {str(tag_error)}")

        return jsonify({
            "status": "success",
            "message": "Series processed and added to default rule"
        }), 200
            
    except Exception as e:
        app.logger.error(f"Error processing Sonarr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/seerr-webhook', methods=['POST'])
def process_seerr_webhook():
    """Handle incoming Jellyseerr webhooks - store request info for later."""
    try:
        app.logger.info("Received webhook from Jellyseerr")
        json_data = request.json
        
        # Debug log the webhook data
        app.logger.info(f"Jellyseerr webhook data: {json.dumps(json_data)}")
        
        # Get the request ID
        request_id = json_data.get('request', {}).get('request_id') or json_data.get('request', {}).get('id')
        
        # Check if it's a TV show request
        media_type = json_data.get('media', {}).get('media_type')
        if media_type != 'tv':
            app.logger.info(f"Request is not a TV show request. Skipping.")
            return jsonify({"status": "success"}), 200
        
        # Store the TVDB ID, request ID, and title in the global dictionary
        tvdb_id = json_data.get('media', {}).get('tvdbId')
        title = json_data.get('subject', 'Unknown Show')
        
        if tvdb_id and request_id:
            # Store the request info for later use by the Sonarr webhook
            global jellyseerr_pending_requests
            jellyseerr_pending_requests[str(tvdb_id)] = {
                'request_id': request_id,
                'title': title,
                'timestamp': int(time.time())
            }
            
            app.logger.info(f"Stored Jellyseerr request {request_id} for TVDB ID {tvdb_id} ({title})")
            
            # Clean up old requests (older than 10 minutes)
            current_time = int(time.time())
            expired_tvdb_ids = []
            
            for tid, info in jellyseerr_pending_requests.items():
                if current_time - info.get('timestamp', 0) > 600:  # 10 minutes
                    expired_tvdb_ids.append(tid)
            
            for tid in expired_tvdb_ids:
                del jellyseerr_pending_requests[tid]
                app.logger.info(f"Cleaned up expired request for TVDB ID {tid}")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        app.logger.error(f"Error processing Jellyseerr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/webhook', methods=['POST'])
def handle_server_webhook():
    """Handle webhooks from Plex/Tautulli"""
    app.logger.info("Received webhook from Tautulli")
    data = request.json
    if data:
        try:
            temp_dir = os.path.join(os.getcwd(), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Standardize field names for Plex/Tautulli data
            plex_data = {
                "server_title": data.get('plex_title'),
                "server_season_num": data.get('plex_season_num'),
                "server_ep_num": data.get('plex_ep_num')
            }
            
            # Save to the standardized filename
            with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
                json.dump(plex_data, f)
            
            result = subprocess.run(["python3", os.path.join(os.getcwd(), "servertosonarr.py")], capture_output=True, text=True)
            if result.stderr:
                app.logger.error(f"Servertosonarr.py error: {result.stderr}")
            return jsonify({'status': 'success'}), 200
        except Exception as e:
            app.logger.error(f"Failed to process Tautulli webhook: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'No data received'}), 400

@app.route('/jellyfin-webhook', methods=['POST'])
def handle_jellyfin_webhook():
    """Handle webhooks from Jellyfin for playback progress."""
    app.logger.info("Received webhook from Jellyfin")
    data = request.json
    if not data:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    try:
        if data.get('NotificationType') == 'PlaybackProgress':
            position_ticks = int(data.get('PlaybackPositionTicks', 0))
            total_ticks = int(data.get('RunTimeTicks', 0))
            
            if total_ticks > 0:
                progress_percent = (position_ticks / total_ticks) * 100
                app.logger.info(f"Jellyfin playback progress: {progress_percent:.2f}%")
                
                # Only process when progress is between 45-55% (mid-episode)
                if 45 <= progress_percent <= 55:
                    item_type = data.get('ItemType')
                    
                    # Only process for TV episodes
                    if item_type == 'Episode':
                        series_name = data.get('SeriesName')
                        season = data.get('SeasonNumber')
                        episode = data.get('EpisodeNumber')
                        
                        if all([series_name, season is not None, episode is not None]):
                            app.logger.info(f"Processing Jellyfin episode: {series_name} S{season}E{episode}")
                            
                            # Format data using server prefix instead of plex
                            jellyfin_data = {
                                "server_title": series_name,
                                "server_season_num": str(season),
                                "server_ep_num": str(episode)
                            }
                            
                            # Save to the standardized file name
                            temp_dir = os.path.join(os.getcwd(), 'temp')
                            os.makedirs(temp_dir, exist_ok=True)
                            with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
                                json.dump(jellyfin_data, f)
                            
                            # Call the processing script
                            result = subprocess.run(["python3", os.path.join(os.getcwd(), "servertosonarr.py")], 
                                                   capture_output=True, text=True)
                            
                            if result.stderr:
                                app.logger.error(f"Errors from servertosonarr.py: {result.stderr}")
                        else:
                            app.logger.warning(f"Missing episode info: Series={series_name}, Season={season}, Episode={episode}")
                    else:
                        app.logger.info(f"Item type '{item_type}' is not an episode, ignoring")
                else:
                    app.logger.debug(f"Progress {progress_percent:.2f}% outside trigger range (45-55%), ignoring")
            else:
                app.logger.warning("Total ticks is zero, cannot calculate progress")
        else:
            notification_type = data.get('NotificationType', 'Unknown')
            app.logger.info(f"Jellyfin notification type '{notification_type}' is not PlaybackProgress, ignoring")
            
        return jsonify({'status': 'success'}), 200
            
    except Exception as e:
        app.logger.error(f"Failed to process Jellyfin webhook: {str(e)}", exc_info=True)
        return jsonify({'status': 'error', 'message': str(e)}), 500

def initialize_episeerr():
    """Initialize episode tag and check for unmonitored downloads."""
    modified_episeerr.create_ocdarr_tag()
    app.logger.info("Created ocdarr tag")
    
    # Do an initial check for unmonitored downloads
    try:
        modified_episeerr.check_and_cancel_unmonitored_downloads()
    except Exception as e:
        app.logger.error(f"Error in initial download check: {str(e)}")

if __name__ == '__main__':
    # Call config rules cleanup at startup
    cleanup_config_rules()
    # Call initialization function before running the app
    initialize_episeerr()
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=5005, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')