#!/usr/bin/env python3
"""
Simplified Rules-Only Flask App for Sonarr Management
Focuses on rule creation, assignment, management, and webhook handling without media browsing/requests
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
import json
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv
import sonarr_utils
import modified_episeerr
import subprocess
import time

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Sonarr configuration
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

# Webhook routes
jellyseerr_pending_requests = {}

def apply_rule_get_option(series_id, rule):
    """Apply the rule's get_option to monitor/search initial episodes."""
    try:
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        episodes_response = requests.get(
            f"{sonarr_url}/api/v3/episode?seriesId={series_id}",
            headers=headers
        )
        if not episodes_response.ok:
            app.logger.error(f"Failed to fetch episodes for series {series_id}: {episodes_response.status_code}")
            return

        all_episodes = episodes_response.json()
        first_season_episodes = sorted(
            [ep for ep in all_episodes if ep['seasonNumber'] == 1],
            key=lambda x: x['episodeNumber']
        )

        episode_ids = []
        if rule['get_option'] == 'all':
            episode_ids = [ep['id'] for ep in all_episodes]
        elif rule['get_option'] == 'season':
            episode_ids = [ep['id'] for ep in first_season_episodes]
        else:
            try:
                num_episodes = int(rule['get_option'])
                episode_ids = [ep['id'] for ep in first_season_episodes[:num_episodes]]
            except ValueError:
                episode_ids = [first_season_episodes[0]['id']] if first_season_episodes else []

        if episode_ids:
            monitor_response = requests.put(
                f"{sonarr_url}/api/v3/episode/monitor",
                headers=headers,
                json={"episodeIds": episode_ids, "monitored": True}
            )
            if monitor_response.ok:
                app.logger.info(f"Monitored {len(episode_ids)} episodes for series {series_id}")
            else:
                app.logger.error(f"Failed to monitor episodes: {monitor_response.text}")

            search_response = requests.post(
                f"{sonarr_url}/api/v3/command",
                headers=headers,
                json={"name": "EpisodeSearch", "episodeIds": episode_ids}
            )
            if search_response.ok:
                app.logger.info(f"Started search for {len(episode_ids)} episodes for series {series_id}")
            else:
                app.logger.error(f"Failed to start episode search: {search_response.text}")
    except Exception as e:
        app.logger.error(f"Error applying rule get_option for series {series_id}: {str(e)}")

@app.route('/webhook', methods=['POST'])
def handle_server_webhook():
    """Handle Tautulli/Plex webhooks for watched episodes."""
    app.logger.info("Received webhook from Tautulli")
    data = request.json
    if not data:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    try:
        temp_dir = os.path.join(os.getcwd(), 'temp')
        os.makedirs(temp_dir, exist_ok=True)
        
        webhook_data = {
            "server_title": data.get('plex_title'),
            "server_season_num": data.get('plex_season_num'),
            "server_ep_num": data.get('plex_ep_num')
        }
        
        with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
            json.dump(webhook_data, f)
        
        result = subprocess.run(
            ["python3", os.path.join(os.getcwd(), "servertosonarr.py")],
            capture_output=True, text=True
        )
        if result.stderr:
            app.logger.error(f"Servertosonarr.py error: {result.stderr}")
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        app.logger.error(f"Failed to process Tautulli webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/jellyfin-webhook', methods=['POST'])
def handle_jellyfin_webhook():
    """Handle Jellyfin webhooks for playback progress."""
    app.logger.info("Received webhook from Jellyfin")
    data = request.json
    if not data:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

    try:
        if data.get('NotificationType') == 'PlaybackProgress':
            position_ticks = int(data.get('PlaybackPositionTicks', 0))
            total_ticks = int(data.get('RunTimeTicks', 0))
            
            if total_ticks > 0 and 45 <= (position_ticks / total_ticks) * 100 <= 55:
                if data.get('ItemType') == 'Episode':
                    series_name = data.get('SeriesName')
                    season = data.get('SeasonNumber')
                    episode = data.get('EpisodeNumber')
                    
                    if all([series_name, season is not None, episode is not None]):
                        temp_dir = os.path.join(os.getcwd(), 'temp')
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        webhook_data = {
                            "server_title": series_name,
                            "server_season_num": str(season),
                            "server_ep_num": str(episode)
                        }
                        
                        with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
                            json.dump(webhook_data, f)
                        
                        result = subprocess.run(
                            ["python3", os.path.join(os.getcwd(), "servertosonarr.py")],
                            capture_output=True, text=True
                        )
                        if result.stderr:
                            app.logger.error(f"Servertosonarr.py error: {result.stderr}")
                    else:
                        app.logger.warning(f"Missing episode info: Series={series_name}, Season={season}, Episode={episode}")
        
        return jsonify({'status': 'success'}), 200
    except Exception as e:
        app.logger.error(f"Failed to process Jellyfin webhook: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/sonarr-webhook', methods=['POST'])
def process_sonarr_webhook():
    """Handle Sonarr webhooks for series additions."""
    app.logger.info("Received webhook from Sonarr")
    try:
        json_data = request.json
        app.logger.debug(f"Sonarr webhook payload: {json.dumps(json_data, indent=2)}")
        
        if not json_data:
            app.logger.error("No JSON data received in Sonarr webhook")
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        if json_data.get('eventType') != 'SeriesAdd':
            app.logger.info(f"Event type: {json_data.get('eventType', 'Unknown')}, skipping")
            return jsonify({"message": "Not a series add event"}), 200
        
        series = json_data.get('series', {})
        if not series:
            app.logger.error("No series data in webhook")
            return jsonify({"status": "error", "message": "No series data"}), 400
        
        series_id = series.get('id')
        series_title = series.get('title', 'Unknown')
        series_tags = series.get('tags', [])
        tvdb_id = series.get('tvdbId')
        
        if not series_id or not series_title:
            app.logger.error(f"Missing series ID or title: ID={series_id}, Title={series_title}")
            return jsonify({"status": "error", "message": "Missing series ID or title"}), 400
        
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        tags_response = requests.get(f"{sonarr_url}/api/v3/tag", headers=headers)
        if not tags_response.ok:
            app.logger.error(f"Failed to fetch tags: {tags_response.status_code} {tags_response.text}")
            return jsonify({"status": "error", "message": "Failed to fetch tags"}), 500
        
        tags = tags_response.json()
        tag_mapping = {tag['id']: tag['label'] for tag in tags}
        
        app.logger.info(f"Series tags: {series_tags}")
        app.logger.info(f"Tag mapping: {tag_mapping}")
        
        has_ocdarr_tag = any(
            str(tag).lower() == 'ocdarr'
            for tag in series_tags
        )
        
        if not has_ocdarr_tag:
            app.logger.info(f"Series {series_title} (ID: {series_id}) has no ocdarr tag, ignoring")
            return jsonify({"status": "success", "message": "No ocdarr tag, ignoring"}), 200
        
        app.logger.info(f"Processing series {series_title} (ID: {series_id}) with ocdarr tag")
        
        episodes_response = requests.get(
            f"{sonarr_url}/api/v3/episode?seriesId={series_id}",
            headers=headers
        )
        if not episodes_response.ok:
            app.logger.error(f"Failed to fetch episodes for series {series_id}: {episodes_response.status_code} {episodes_response.text}")
        elif episodes_response.json():
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
                    app.logger.error(f"Failed to unmonitor episodes: {unmonitor_response.status_code} {unmonitor_response.text}")
        
        modified_episeerr.check_and_cancel_unmonitored_downloads()
        
        config = load_config()
        default_rule = config.get('default_rule')
        if default_rule and default_rule in config['rules']:
            config['rules'][default_rule]['series'] = config['rules'].get(default_rule, {}).get('series', []) + [str(series_id)]
            save_config(config)
            app.logger.info(f"Assigned series {series_title} to default rule {default_rule}")
            
            apply_rule_get_option(series_id, config['rules'][default_rule])
        else:
            app.logger.warning(f"No default rule found for series {series_title}")
        
        if modified_episeerr.remove_ocdarr_tag_from_series(series_id):
            app.logger.info(f"Removed ocdarr tag from series {series_title}")
        else:
            app.logger.error(f"Failed to remove ocdarr tag from series {series_title}")
        
        if tvdb_id and str(tvdb_id) in jellyseerr_pending_requests:
            request_id = jellyseerr_pending_requests[str(tvdb_id)].get('request_id')
            if request_id:
                if modified_episeerr.delete_jellyseerr_request(request_id):
                    app.logger.info(f"Deleted Jellyseerr request {request_id} for {series_title}")
                    del jellyseerr_pending_requests[str(tvdb_id)]
                else:
                    app.logger.error(f"Failed to delete Jellyseerr request {request_id} for {series_title}")
        
        return jsonify({"status": "success", "message": "Processed series with ocdarr tag"}), 200
    except Exception as e:
        app.logger.error(f"Error processing Sonarr webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/seerr-webhook', methods=['POST'])
def process_seerr_webhook():
    """Handle Jellyseerr webhooks to store request info."""
    app.logger.info("Received webhook from Jellyseerr")
    try:
        json_data = request.json
        if not json_data:
            app.logger.error("No JSON data received in Jellyseerr webhook")
            return jsonify({"status": "error", "message": "No data received"}), 400
        
        app.logger.debug(f"Jellyseerr webhook data: {json_data}")
        
        media = json_data.get('media', {})
        if not isinstance(media, dict) or media.get('media_type') != 'tv':
            app.logger.info("Not a TV request")
            return jsonify({"status": "success", "message": "Not a TV request"}), 200
        
        request_info = json_data.get('request', {})
        request_id = request_info.get('request_id') or request_info.get('id')
        tvdb_id = media.get('tvdbId')
        title = json_data.get('subject', 'Unknown Show')
        
        if tvdb_id and request_id:
            jellyseerr_pending_requests[str(tvdb_id)] = {
                'request_id': request_id,
                'title': title,
                'timestamp': int(time.time())
            }
            app.logger.info(f"Stored Jellyseerr request {request_id} for TVDB ID {tvdb_id} ({title})")
        else:
            app.logger.warning(f"Missing tvdb_id or request_id: tvdb_id={tvdb_id}, request_id={request_id}")
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Error processing Jellyseerr webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    cleanup_config_rules()
    
    modified_episeerr.create_ocdarr_tag()
    app.logger.info("Initialized OCDarr tag")
    
    app.run(
        host='0.0.0.0', 
        port=int(os.getenv('PORT', 5005)), 
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )