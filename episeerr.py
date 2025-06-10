__version__ = "2.1.0"
from flask import Flask, render_template, request, redirect, url_for, jsonify
import subprocess
import os
import atexit
import re
import time
import logging
import json
import sonarr_utils
from flask import current_app
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import threading
import shutil
from threading import Lock
from functools import lru_cache
from logging.handlers import RotatingFileHandler
import requests
import episeerr_utils
from episeerr_utils import EPISEERR_DEFAULT_TAG_ID, EPISEERR_SELECT_TAG_ID

app = Flask(__name__)



# Load environment variables
load_dotenv()
BASE_DIR = os.getcwd()

# Sonarr variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Jellyseerr/Overseerr variables
JELLYSEERR_URL = os.getenv('JELLYSEERR_URL', '')
JELLYSEERR_API_KEY = os.getenv('JELLYSEERR_API_KEY')
OVERSEERR_URL = os.getenv('OVERSEERR_URL')
OVERSEERR_API_KEY = os.getenv('OVERSEERR_API_KEY')
SEERR_ENABLED = bool((JELLYSEERR_URL and JELLYSEERR_API_KEY) or (OVERSEERR_URL and OVERSEERR_API_KEY))

# TMDB API Key
TMDB_API_KEY = os.getenv('TMDB_API_KEY')
app.config['TMDB_API_KEY'] = TMDB_API_KEY  # Store in app.config
# Log TMDB API key status at startup
if app.config['TMDB_API_KEY']:
    app.logger.info("TMDB_API_KEY is set - request system will function normally")
else:
    app.logger.warning("TMDB_API_KEY is missing - you may encounter issues fetching series details and seasons")

# Global variable to track pending requests from Jellyseerr/Overseerr
jellyseerr_pending_requests = {}

# Request storage
REQUESTS_DIR = os.path.join(os.getcwd(), 'data', 'requests')
os.makedirs(REQUESTS_DIR, exist_ok=True)

LAST_PROCESSED_FILE = os.path.join(os.getcwd(), 'data', 'last_processed.json')
os.makedirs(os.path.dirname(LAST_PROCESSED_FILE), exist_ok=True)

# Setup logging
log_file = os.getenv('LOG_PATH', os.path.join(os.getcwd(), 'logs', 'app.log'))
log_level = logging.INFO
os.makedirs(os.path.dirname(log_file), exist_ok=True)

file_handler = RotatingFileHandler(
    log_file,
    maxBytes=1*1024*1024,
    backupCount=2,
    encoding='utf-8'
)
file_handler.setLevel(log_level)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[file_handler]
)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.DEBUG if os.getenv('FLASK_DEBUG', 'false').lower() == 'true' else logging.INFO)
formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s')
stream_handler.setFormatter(formatter)
app.logger.addHandler(stream_handler)

# Configuration management
config_path = os.path.join(app.root_path, 'config', 'config.json')


def get_tmdb_endpoint(endpoint, params=None):
    """Make a request to any TMDB endpoint with the given parameters."""
    base_url = f"https://api.themoviedb.org/3/{endpoint}"
    if params is None:
        params = {}
    
    # Check if we have a v3 or v4 token
    auth_token = TMDB_API_KEY.strip('"\'') if TMDB_API_KEY else ""
    
    try:
        headers = {}
        # If it's a long token (v4), use it as a bearer token
        if len(auth_token) > 40:
            headers["Authorization"] = f"Bearer {auth_token}"
        else:
            # Otherwise use as API key in params (v3)
            params['api_key'] = auth_token
        
        response = requests.get(base_url, params=params, headers=headers)
        
        if response.status_code == 200:
            return response.json()
        else:
            app.logger.error(f"Error fetching {endpoint}: {response.status_code}")
            return None
    except Exception as e:
        app.logger.error(f"Exception during API request: {str(e)}")
        return None

def search_tv_shows(query):
    """Search for TV shows using TMDB API."""
    return get_tmdb_endpoint("search/tv", {
        'query': query,
        'language': 'en-US',
        'page': 1
    })

def get_external_ids(tmdb_id, media_type='tv'):
    """Get external IDs for a TV show or movie."""
    endpoint = f"{media_type}/{tmdb_id}/external_ids"
    return get_tmdb_endpoint(endpoint)

# Scheduler
class OCDarrScheduler:
    def __init__(self):
        self.cleanup_thread = None
        self.running = False
        self.last_cleanup = 0
        self.update_interval_from_settings()
    
    def update_interval_from_settings(self):
        """Update cleanup interval from global settings."""
        try:
            import servertosonarr
            global_settings = servertosonarr.load_global_settings()
            self.cleanup_interval_hours = global_settings.get('cleanup_interval_hours', 6)
        except:
            self.cleanup_interval_hours = 6  # Fallback
    
    def start_scheduler(self):
        if self.running:
            return
        self.running = True
        self.cleanup_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.cleanup_thread.start()
        print(f"✓ Global storage gate scheduler started - cleanup every {self.cleanup_interval_hours} hours")
    
    def _scheduler_loop(self):
        time.sleep(300)  # Wait 5 minutes after startup
        while self.running:
            try:
                # Update interval from settings each loop
                self.update_interval_from_settings()
                
                current_time = time.time()
                hours_since_last = (current_time - self.last_cleanup) / 3600
                
                if hours_since_last >= self.cleanup_interval_hours:
                    print("⏰ Starting scheduled global storage gate cleanup...")
                    self._run_cleanup()
                    self.last_cleanup = current_time
                    
                time.sleep(600)  # Check every 10 minutes
            except Exception as e:
                print(f"Scheduler error: {str(e)}")
                time.sleep(300)
    
    def _run_cleanup(self):
        try:
            import servertosonarr
            # Use the new global storage gate cleanup
            servertosonarr.run_global_storage_gate_cleanup()
            print("✓ Scheduled global storage gate cleanup completed")
        except Exception as e:
            print(f"Cleanup failed: {str(e)}")
    
    def force_cleanup(self):
        cleanup_thread = threading.Thread(target=self._run_cleanup, daemon=True)
        cleanup_thread.start()
        return "Global storage gate cleanup started"
    
    def get_status(self):
        if not self.running:
            return {"status": "stopped", "next_cleanup": None}
        
        if self.last_cleanup == 0:
            next_cleanup = "5 minutes after startup"
        else:
            next_time = self.last_cleanup + (self.cleanup_interval_hours * 3600)
            next_cleanup = datetime.fromtimestamp(next_time).strftime("%Y-%m-%d %H:%M:%S")
            
        return {
            "status": "running",
            "type": "global_storage_gate",
            "interval_hours": self.cleanup_interval_hours,
            "last_cleanup": datetime.fromtimestamp(self.last_cleanup).strftime("%Y-%m-%d %H:%M:%S") if self.last_cleanup else "Never",
            "next_cleanup": next_cleanup
        }
# Add this route to your episeerr.py

@app.route('/api/series-with-titles')
def get_series_with_titles():
    """Get series list with titles and rule assignments for dropdowns."""
    try:
        config = load_config()
        all_series = get_sonarr_series()
        
        # Build assignment mapping
        assignments = {}
        for rule_name, details in config['rules'].items():
            series_dict = details.get('series', {})
            for series_id in series_dict.keys():
                assignments[str(series_id)] = rule_name
        
        # Format for dropdown
        series_list = []
        for series in all_series:
            series_id = str(series['id'])
            rule_name = assignments.get(series_id, 'Unassigned')
            
            # Add time-based cleanup info if assigned to a rule
            cleanup_info = ""
            if rule_name != 'Unassigned' and rule_name in config['rules']:
                rule = config['rules'][rule_name]
                grace_days = rule.get('grace_days')
                dormant_days = rule.get('dormant_days')
                
                if grace_days or dormant_days:
                    cleanup_parts = []
                    if grace_days:
                        cleanup_parts.append(f"Grace: {grace_days}d")
                    if dormant_days:
                        cleanup_parts.append(f"Dormant: {dormant_days}d")
                    cleanup_info = f" ({', '.join(cleanup_parts)})"
            
            series_list.append({
                'id': series_id,
                'title': series['title'],
                'rule': rule_name,
                'display_text': f"{series['title']} - Rule: {rule_name}{cleanup_info}"
            })
        
        # Sort by title
        series_list.sort(key=lambda x: x['title'].lower())
        
        return jsonify({
            'status': 'success',
            'series': series_list,
            'count': len(series_list)
        })
        
    except Exception as e:
        app.logger.error(f"Error getting series with titles: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
# Cleanup Logging
def setup_cleanup_logging():
    LOG_PATH = os.getenv('LOG_PATH', '/app/logs/app.log')
    CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    os.makedirs(os.path.dirname(CLEANUP_LOG_PATH), exist_ok=True)
    cleanup_logger = logging.getLogger('cleanup')
    cleanup_logger.setLevel(logging.INFO)
    cleanup_logger.handlers.clear()
    main_file_handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=10*1024*1024,
        backupCount=3,
        encoding='utf-8'
    )
    main_file_handler.setLevel(logging.INFO)
    main_file_formatter = logging.Formatter('%(asctime)s - CLEANUP - %(levelname)s - %(message)s')
    main_file_handler.setFormatter(main_file_formatter)
    cleanup_file_handler = RotatingFileHandler(
        CLEANUP_LOG_PATH,
        maxBytes=5*1024*1024,
        backupCount=5,
        encoding='utf-8'
    )
    cleanup_file_handler.setLevel(logging.INFO)
    cleanup_file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    cleanup_file_handler.setFormatter(cleanup_file_formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - CLEANUP - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    cleanup_logger.addHandler(main_file_handler)
    cleanup_logger.addHandler(cleanup_file_handler)
    cleanup_logger.addHandler(console_handler)
    cleanup_logger.propagate = False
    return cleanup_logger

cleanup_logger = setup_cleanup_logging()

# Config Migration
def migrate_config_complete(config_path):
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        if config.get('field_migration_complete') and config.get('series_migration_complete'):
            print("✅ Config already fully migrated")
            return config
        backup_path = config_path + f'.backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        shutil.copy2(config_path, backup_path)
        print(f"📁 Created backup: {backup_path}")
        field_migrations = 0
        series_migrations = 0
        for rule_name, rule in config.get('rules', {}).items():
            print(f"\n🔄 Migrating rule: {rule_name}")
            if 'keep_watched_days' in rule:
                rule['grace_days'] = rule.pop('keep_watched_days')
                field_migrations += 1
                print(f"  ✓ Migrated keep_watched_days → grace_days")
            if 'keep_unwatched_days' in rule:
                rule['dormant_days'] = rule.pop('keep_unwatched_days')
                field_migrations += 1
                print(f"  ✓ Migrated keep_unwatched_days → dormant_days")
            if 'grace_days' not in rule:
                rule['grace_days'] = None
            if 'dormant_days' not in rule:
                rule['dormant_days'] = None
            if 'series' in rule and isinstance(rule['series'], list):
                old_series = rule['series']
                new_series = {str(series_id): {'activity_date': None} for series_id in old_series}
                rule['series'] = new_series
                series_migrations += 1
                print(f"  ✓ Migrated {len(old_series)} series from array to dict format")
            if 'dry_run' not in rule:
                rule['dry_run'] = False
                print(f"  ✓ Added dry_run field (default: False)")
        config['field_migration_complete'] = True
        config['series_migration_complete'] = True
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=4)
        print(f"\n✅ Migration complete!")
        print(f"   - Field migrations: {field_migrations}")
        print(f"   - Series structure migrations: {series_migrations}")
        print(f"   - Backup saved to: {backup_path}")
        return config
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        raise

def load_config_with_migration(config_path):
    if not os.path.exists(config_path):
        default_config = {
            "rules": {
                "default": {
                    "get_option": "1",
                    "action_option": "search",
                    "keep_watched": "1",
                    "monitor_watched": False,
                    "grace_days": None,
                    "dormant_days": None,
                    "series": {},
                    "dry_run": False
                }
            },
            "default_rule": "default",
            "field_migration_complete": True,
            "series_migration_complete": True
        }
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    return migrate_config_complete(config_path)

def load_config():
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
        if 'rules' not in config:
            config['rules'] = {}
        config = migrate_config_complete(config_path)
        return config
    except FileNotFoundError:
        default_config = {
            'rules': {
                'full_seasons': {
                    'get_option': 'season',
                    'action_option': 'monitor',
                    'keep_watched': 'season',
                    'monitor_watched': False,
                    'grace_days': None,
                    'dormant_days': None,
                    'series': {},
                    'dry_run': False
                }
            },
            'default_rule': 'full_seasons',
            'field_migration_complete': True,
            'series_migration_complete': True
        }
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        save_config(default_config)
        return default_config

def save_config(config):
    config_path = os.path.join(os.getcwd(), 'config', 'config.json')
    print(f"DEBUG: save_config called")
    print(f"DEBUG: config_path = {config_path}")
    print(f"DEBUG: Config to save: {json.dumps(config, indent=2)}")
    try:
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, 'w') as file:
            json.dump(config, file, indent=4)
        print(f"DEBUG: Config saved successfully to {config_path}")
        with open(config_path, 'r') as file:
            saved_config = json.load(file)
        print(f"DEBUG: Verified save - dry_run status: {saved_config.get('rules', {}).get('nukeafter90days', {}).get('dry_run', 'NOT_FOUND')}")
    except Exception as e:
        print(f"DEBUG: Save failed: {str(e)}")
        raise

def get_sonarr_series():
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

# Web UI Routes
@app.route('/')
def index():
    config = load_config()
    all_series = get_sonarr_series()
    rules_mapping = {}
    for rule_name, details in config['rules'].items():
        series_dict = details.get('series', {})
        for series_id in series_dict.keys():
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
    if request.method == 'POST':
        config = load_config()
        rule_name = request.form.get('rule_name', '').strip()
        if not rule_name:
            return redirect(url_for('index', message="Rule name is required"))
        if rule_name in config['rules']:
            return redirect(url_for('index', message=f"Rule '{rule_name}' already exists"))
        grace_days = request.form.get('grace_days', '').strip()
        dormant_days = request.form.get('dormant_days', '').strip()
        grace_days = None if not grace_days else int(grace_days)
        dormant_days = None if not dormant_days else int(dormant_days)
        config['rules'][rule_name] = {
            'get_option': request.form.get('get_option', ''),
            'action_option': request.form.get('action_option', 'monitor'),
            'keep_watched': request.form.get('keep_watched', ''),
            'monitor_watched': 'monitor_watched' in request.form, 
            'grace_days': grace_days,
            'dormant_days': dormant_days,
            'series': {}
        }
        save_config(config)
        return redirect(url_for('index', message=f"Rule '{rule_name}' created successfully"))
    return render_template('create_rule.html')

@app.route('/edit-rule/<rule_name>', methods=['GET', 'POST'])
def edit_rule(rule_name):
    config = load_config()
    if rule_name not in config['rules']:
        return redirect(url_for('index', message=f"Rule '{rule_name}' not found"))
    if request.method == 'POST':
        grace_days = request.form.get('grace_days', '').strip()
        dormant_days = request.form.get('dormant_days', '').strip()
        grace_days = None if not grace_days else int(grace_days)
        dormant_days = None if not dormant_days else int(dormant_days)
        config['rules'][rule_name].update({
            'get_option': request.form.get('get_option', ''),
            'action_option': request.form.get('action_option', 'monitor'),
            'keep_watched': request.form.get('keep_watched', ''),
            'monitor_watched': 'monitor_watched' in request.form, 
            'grace_days': grace_days,
            'dormant_days': dormant_days
        })
        save_config(config)
        return redirect(url_for('index', message=f"Rule '{rule_name}' updated successfully"))
    rule = config['rules'][rule_name]
    return render_template('edit_rule.html', rule_name=rule_name, rule=rule)

@app.route('/delete-rule/<rule_name>', methods=['POST'])
def delete_rule(rule_name):
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
    config = load_config()
    rule_name = request.form.get('rule_name')
    series_ids = request.form.getlist('series_ids')
    if not rule_name or rule_name not in config['rules']:
        return redirect(url_for('index', message="Invalid rule selected"))
    for rule, details in config['rules'].items():
        series_dict = details.get('series', {})
        for series_id in series_ids:
            if series_id in series_dict:
                del series_dict[series_id]
    target_series_dict = config['rules'][rule_name].get('series', {})
    for series_id in series_ids:
        target_series_dict[series_id] = {'activity_date': None}
    save_config(config)
    return redirect(url_for('index', message=f"Assigned {len(series_ids)} series to rule '{rule_name}'"))

@app.route('/set-default-rule', methods=['POST'])
def set_default_rule():
    config = load_config()
    rule_name = request.form.get('rule_name')
    if rule_name not in config['rules']:
        return redirect(url_for('index', message="Invalid rule selected"))
    config['default_rule'] = rule_name
    save_config(config)
    assigned_series = config['rules'][rule_name].get('series', {})
    for series_id in assigned_series:
        track_rule_assignment(series_id, rule_name)
    return redirect(url_for('index', message=f"Set '{rule_name}' as default rule and tracked assignment dates"))

@app.route('/unassign-series', methods=['POST'])
def unassign_series():
    config = load_config()
    series_ids = request.form.getlist('series_ids')
    total_removed = 0
    for rule_name, details in config['rules'].items():
        original_count = len(details.get('series', {}))
        series_dict = details.get('series', {})
        for series_id in series_ids:
            if series_id in series_dict:
                del series_dict[series_id]
        total_removed += original_count - len(details['series'])
    save_config(config)
    return redirect(url_for('index', message=f"Unassigned {len(series_ids)} series from all rules"))

@app.route('/api/recent-activity')
def get_recent_activity():
    try:
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
    try:
        config = load_config()
        all_series = get_sonarr_series()
        rules_mapping = {}
        for rule_name, details in config['rules'].items():
            for series_id in details.get('series', {}):
                rules_mapping[str(series_id)] = rule_name
        stats = {
            'total_series': len(all_series),
            'assigned_series': len(rules_mapping),
            'unassigned_series': len(all_series) - len(rules_mapping),
            'total_rules': len(config['rules']),
            'rule_breakdown': {}
        }
        for rule_name, details in config['rules'].items():
            stats['rule_breakdown'][rule_name] = len(details.get('series', {}))
        return jsonify(stats)
    except Exception as e:
        app.logger.error(f"Error getting series stats: {str(e)}")
        return jsonify({'error': str(e)}), 500

def cleanup_config_rules():
    try:
        config = load_config()
        existing_series = get_sonarr_series()
        existing_series_ids = set(str(series['id']) for series in existing_series)
        changes_made = False
        for rule_name, rule_details in config['rules'].items():
            original_count = len(rule_details.get('series', {}))
            rule_details['series'] = {
                series_id: details for series_id, details in rule_details.get('series', {}).items()
                if series_id in existing_series_ids
            }
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
    cleanup_config_rules()
    return redirect(url_for('index', message="Configuration cleaned up successfully"))

@app.route('/scheduler')
def scheduler_admin():
    return render_template('scheduler_admin.html')

@app.route('/api/scheduler-status')
def scheduler_status():
    try:
        if 'cleanup_scheduler' not in globals():
            return jsonify({"status": "error", "message": "Scheduler not initialized"}), 500
        return jsonify(cleanup_scheduler.get_status())
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
@app.route('/api/global-settings')
def get_global_settings():
    """Get global settings including storage gate."""
    try:
        import servertosonarr
        settings = servertosonarr.load_global_settings()
        
        # Get current disk space for display
        disk_info = servertosonarr.get_sonarr_disk_space()
        
        return jsonify({
            "status": "success",
            "settings": settings,
            "disk_info": disk_info
        })
    except Exception as e:
        app.logger.error(f"Error getting global settings: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/global-settings', methods=['POST'])
def update_global_settings():
    """Update global settings."""
    try:
        import servertosonarr
        
        data = request.json
        storage_min_gb = data.get('global_storage_min_gb')
        cleanup_interval_hours = data.get('cleanup_interval_hours', 6)
        dry_run_mode = data.get('dry_run_mode', False)
        
        # Validate inputs
        if storage_min_gb is not None:
            storage_min_gb = int(storage_min_gb) if storage_min_gb else None
        
        settings = {
            'global_storage_min_gb': storage_min_gb,
            'cleanup_interval_hours': int(cleanup_interval_hours),
            'dry_run_mode': bool(dry_run_mode)
        }
        
        servertosonarr.save_global_settings(settings)
        
        app.logger.info(f"Global settings updated: {settings}")
        
        return jsonify({
            "status": "success",
            "message": "Global settings updated successfully",
            "settings": settings
        })
        
    except Exception as e:
        app.logger.error(f"Error updating global settings: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/scheduler-status-global')
def scheduler_status_global():
    """Enhanced scheduler status with global settings."""
    try:
        import servertosonarr
        
        if 'cleanup_scheduler' not in globals():
            return jsonify({"status": "error", "message": "Scheduler not initialized"}), 500
        
        # Get basic scheduler status
        status = cleanup_scheduler.get_status()
        
        # Add global settings
        global_settings = servertosonarr.load_global_settings()
        status["global_settings"] = global_settings
        
        # Add disk info
        disk_info = servertosonarr.get_sonarr_disk_space()
        if disk_info:
            status["disk_info"] = disk_info
            
            # Check if storage gate would trigger
            storage_min_gb = global_settings.get('global_storage_min_gb')
            if storage_min_gb:
                gate_open = disk_info['free_space_gb'] < storage_min_gb
                status["storage_gate"] = {
                    "enabled": True,
                    "threshold_gb": storage_min_gb,
                    "current_free_gb": disk_info['free_space_gb'],
                    "gate_open": gate_open,
                    "status": "OPEN - Cleanup will run" if gate_open else "CLOSED - No cleanup needed"
                }
            else:
                status["storage_gate"] = {
                    "enabled": False,
                    "status": "Disabled - Cleanup always runs on schedule"
                }
        
        # Add configuration summary
        config = load_config()
        rule_summary = {
            "total_rules": len(config['rules']),
            "cleanup_rules": 0,
            "protected_rules": 0
        }
        
        for rule_name, rule in config['rules'].items():
            has_cleanup = rule.get('grace_days') or rule.get('dormant_days')
            if has_cleanup:
                rule_summary["cleanup_rules"] += 1
            else:
                rule_summary["protected_rules"] += 1
        
        status["rule_summary"] = rule_summary
        return jsonify(status)
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/force-cleanup', methods=['POST'])
def force_cleanup():
    try:
        print("Manual cleanup requested via API")
        result = cleanup_scheduler.force_cleanup()
        print("Manual cleanup started successfully")
        return jsonify({"status": "success", "message": result})
    except Exception as e:
        print(f"Failed to start manual cleanup: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', message="Internal server error"), 500

@app.route('/api/recent-cleanup-activity')
def recent_cleanup_activity():
    return jsonify({
        "recentCleanups": [],
        "totalOperations": 0,
        "status": "success"
    })

@app.route('/debug-series/<int:series_id>')
def debug_series(series_id):
    try:
        from servertosonarr import load_activity_tracking, check_time_based_cleanup, load_config
        config = load_config()
        rule = None
        rule_name = None
        for r_name, r_details in config['rules'].items():
            if str(series_id) in r_details.get('series', {}):
                rule = r_details
                rule_name = r_name
                break
        if not rule:
            return jsonify({"error": f"Series {series_id} not found in any rule"})
        activity_data = load_activity_tracking()
        series_activity = activity_data.get(str(series_id), {})
        should_cleanup, reason = check_time_based_cleanup(series_id, rule)
        return jsonify({
            "series_id": series_id,
            "rule_name": rule_name,
            "rule_config": rule,
            "activity_data": series_activity,
            "should_cleanup": should_cleanup,
            "cleanup_reason": reason,
            "current_time": int(time.time()),
            "days_since_last_watch": (int(time.time()) - series_activity.get('last_watched', 0)) / (24*60*60) if series_activity.get('last_watched') else "Never watched"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/test-cleanup/<int:series_id>')
def test_cleanup(series_id):
    try:
        config = load_config()
        rule = None
        rule_name = None
        for r_name, r_details in config['rules'].items():
            if str(series_id) in r_details.get('series', {}):
                rule = r_details
                rule_name = r_name
                break
        
        if not rule:
            return jsonify({"status": "error", "message": "Series not assigned to any rule"}), 404
        
        test_rule = rule.copy()
        test_rule['dry_run'] = True
        
        # Use the correct function names
        from servertosonarr import check_time_based_cleanup
        
        should_cleanup, reason = check_time_based_cleanup(series_id, test_rule)
        
        if should_cleanup:
            # For testing, we don't actually run cleanup, just show what would happen
            return jsonify({
                "status": "success",
                "message": f"Test completed: {reason}",
                "would_cleanup": True,
                "rule": rule_name,
                "reason": reason
            })
        else:
            return jsonify({
                "status": "success", 
                "message": f"No cleanup needed: {reason}",
                "would_cleanup": False,
                "rule": rule_name,
                "reason": reason
            })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/add-test-activity/<int:series_id>', methods=['POST'])
def add_test_activity(series_id):
    try:
        from servertosonarr import load_activity_tracking, save_activity_tracking
        days_ago = int(request.form.get('days_ago', 16))
        season = int(request.form.get('season', 1))
        episode = int(request.form.get('episode', 1))
        current_time = int(time.time())
        watch_time = current_time - (days_ago * 24 * 60 * 60)
        activity_data = load_activity_tracking()
        activity_data[str(series_id)] = {
            "last_watched": watch_time,
            "last_updated": current_time,
            "last_season": season,
            "last_episode": episode
        }
        save_activity_tracking(activity_data)
        return jsonify({
            "status": "success",
            "message": f"Added activity for series {series_id}: watched S{season}E{episode} {days_ago} days ago",
            "watch_timestamp": watch_time,
            "days_ago": days_ago
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

def get_cleanup_summary():
    try:
        CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
        if not os.path.exists(CLEANUP_LOG_PATH):
            return {"recent_cleanups": [], "total_operations": 0}
        recent_cleanups = []
        with open(CLEANUP_LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in reversed(lines[-100:]):
            if "CLEANUP COMPLETED" in line:
                try:
                    timestamp = line.split(' - ')[0]
                    recent_cleanups.append({
                        "timestamp": timestamp,
                        "type": "Scheduled" if "Scheduled" in line else "Manual",
                        "status": "completed"
                    })
                    if len(recent_cleanups) >= 5:
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
    try:
        CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
        if not os.path.exists(CLEANUP_LOG_PATH):
            return {"recent_cleanups": [], "total_operations": 0}
        recent_cleanups = []
        with open(CLEANUP_LOG_PATH, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in reversed(lines[-50:]):
            if "CLEANUP COMPLETED" in line:
                try:
                    timestamp = line.split(' - ')[0]
                    recent_cleanups.append({
                        "timestamp": timestamp,
                        "type": "Scheduled" if "Scheduled" in line else "Manual",
                        "status": "completed"
                    })
                    if len(recent_cleanups) >= 3:
                        break
                except:
                    continue
        return {
            "recent_cleanups": recent_cleanups,
            "total_operations": len(recent_cleanups)
        }
    except Exception as e:
        current_app.logger.error(f"Error in cleanup summary fallback: {str(e)}")
        return {"recent_cleanups": [], "total_operations": 0, "error": str(e)}

@app.route('/cleanup-logs')
def cleanup_logs():
    try:
        CLEANUP_LOG_PATH = os.getenv('CLEANUP_LOG_PATH', '/app/logs/cleanup.log')
        if not os.path.exists(CLEANUP_LOG_PATH):
            return render_simple_logs_page("No cleanup logs found yet.")
        try:
            with open(CLEANUP_LOG_PATH, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception as e:
            return render_simple_logs_page(f"Error reading log file: {str(e)}")
        recent_lines = lines[-200:] if len(lines) > 200 else lines
        recent_lines.reverse()
        try:
            return render_template('cleanup_logs.html', logs=recent_lines)
        except:
            return render_simple_logs_page(recent_lines)
    except Exception as e:
        current_app.logger.error(f"Error in cleanup logs route: {str(e)}")
        return render_simple_logs_page(f"Error loading logs: {str(e)}")

def render_simple_logs_page(logs_or_message):
    if isinstance(logs_or_message, str):
        content = f'<div class="alert alert-warning">{logs_or_message}</div>'
    else:
        content = '<div style="font-family: monospace; font-size: 0.9em; max-height: 600px; overflow-y: auto; border: 1px solid #333; padding: 1rem; background: #1a1a1a;">'
        for line in logs_or_message:
            line_class = ""
            if 'ERROR' in line or 'Failed' in line:
                line_class = 'style="color: #ff6b6b;"'
            elif 'DRY RUN' in line:
                line_class = 'style="color: #74c0fc;"'
            elif 'CLEANUP STARTED' in line or 'CLEANUP COMPLETED' in line:
                line_class = 'style="color: #51cf66;"'
            elif 'deleted' in line and 'would delete' not in line:
                line_class = 'style="color: #ffd43b;"'
            elif 'SKIPPED' in line:
                line_class = 'style="color: #868e96;"'
            else:
                line_class = 'style="color: #f8f9fa;"'
            content += f'<div {line_class}>{line.strip()}</div>'
        content += '</div>'
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Cleanup Logs - OCDarr</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #1a1a1a; color: #e0e0e0; }}
            .navbar {{ background-color: #2d2d2d !important; }}
            .card {{ background-color: #2d2d2d; border: 1px solid #404040; }}
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark">
            <div class="container">
                <a class="navbar-brand" href="/">OCDarr</a>
            </div>
        </nav>
        <div class="container mt-4">
            <div class="card">
                <div class="card-header d-flex justify-content-between">
                    <h5><i class="fas fa-file-alt me-2"></i>Cleanup Logs</h5>
                    <a href="/scheduler" class="btn btn-primary btn-sm">Back to Scheduler</a>
                </div>
                <div class="card-body">
                    {content}
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return html

@app.route('/dry-run-settings', methods=['GET', 'POST'])
def dry_run_settings():
    if request.method == 'POST':
        try:
            app.logger.info(f"Form data received: {dict(request.form)}")
            config = load_config()
            app.logger.info(f"Config before changes: {config['rules']['nukeafter90days'].get('dry_run', 'NOT_SET')}")
            for rule_name in config.get('rules', {}).keys():
                rule_dry_run_key = f'rule_dry_run_{rule_name}'
                rule_dry_run = rule_dry_run_key in request.form
                app.logger.info(f"Setting {rule_name} dry_run to: {rule_dry_run}")
                config['rules'][rule_name]['dry_run'] = rule_dry_run
            app.logger.info(f"Config after changes: {config['rules']['nukeafter90days'].get('dry_run', 'NOT_SET')}")
            save_config(config)
            app.logger.info("save_config() called")
            verify_config = load_config()
            app.logger.info(f"Config after save_config: {verify_config['rules']['nukeafter90days'].get('dry_run', 'NOT_SET')}")
            return redirect(url_for('scheduler_admin', message="Dry run settings saved successfully"))
        except Exception as e:
            current_app.logger.error(f"Error saving dry run settings: {str(e)}")
            return redirect(url_for('scheduler_admin', message=f"Error saving settings: {str(e)}"))
    try:
        config = load_config()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        return render_template('dry_run_settings.html',
                             config=config,
                             global_dry_run=global_dry_run)
    except Exception as e:
        current_app.logger.error(f"Error loading dry run settings: {str(e)}")
        return redirect(url_for('scheduler_admin', message=f"Error loading settings: {str(e)}"))

def render_simple_dry_run_page(config, global_dry_run):
    rules_html = ""
    for rule_name, rule_details in config.get('rules', {}).items():
        checked = 'checked' if rule_details.get('dry_run', False) else ''
        series_count = len(rule_details.get('series', []))
        rules_html += f'''
        <div class="mb-3 p-3 border rounded">
            <div class="form-check">
                <input class="form-check-input" type="checkbox" name="rule_dry_run_{rule_name}" {checked}>
                <label class="form-check-label">
                    <strong>{rule_name.replace('_', ' ').title()}</strong> ({series_count} series)
                </label>
            </div>
        </div>
        '''
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dry Run Settings - OCDarr</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {{ background-color: #1a1a1a; color: #e0e0e0; }}
            .card {{ background-color: #2d2d2d; border: 1px solid #404040; }}
            .form-control, .form-check-input {{ background-color: #404040; border-color: #606060; }}
        </style>
    </head>
    <body>
        <div class="container mt-4">
            <div class="card">
                <div class="card-header">
                    <h5>Dry Run Settings</h5>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="alert alert-info">
                            <strong>Global Dry Run:</strong> {'ENABLED' if global_dry_run else 'DISABLED'}<br>
                            <small>Change via CLEANUP_DRY_RUN environment variable</small>
                        </div>
                        <h6>Rule-Specific Settings:</h6>
                        {rules_html}
                        <div class="mt-3">
                            <button type="submit" class="btn btn-primary">Save Settings</button>
                            <a href="/scheduler" class="btn btn-secondary">Back to Scheduler</a>
                        </div>
                    </form>
                </div>
            </div>
        </div>
    </body>
    </html>
    '''
    return html

# Replace your select_episodes route with this updated version:

@app.route('/select-seasons/<tmdb_id>')
def select_seasons(tmdb_id):
    """Show season selection page first - this is the missing piece"""
    try:
        # Get TV show details from TMDB
        show_data = get_tmdb_endpoint(f"tv/{tmdb_id}")
        
        if not show_data:
            return render_template('error.html', message="Failed to get show details from TMDB")
        
        # Format show data for template
        formatted_show = {
            'id': tmdb_id,
            'name': show_data.get('name', 'Unknown Series'),
            'overview': show_data.get('overview', ''),
            'posterUrl': f"https://image.tmdb.org/t/p/w300{show_data['poster_path']}" if show_data.get('poster_path') else '/static/placeholder-banner.png',
            'seasons': []
        }
        
        # Add seasons (skip season 0 - specials)
        for season in show_data.get('seasons', []):
            if season.get('season_number', 0) > 0:
                formatted_show['seasons'].append({
                    'seasonNumber': season['season_number'],
                    'episodeCount': season.get('episode_count', '?')
                })
        
        return render_template('season_selection.html', 
                             show=formatted_show, 
                             tmdb_id=tmdb_id)
    
    except Exception as e:
        app.logger.error(f"Error in select_seasons: {str(e)}", exc_info=True)
        return render_template('error.html', message=f"Error loading season selection: {str(e)}")

@app.route('/select-episodes/<tmdb_id>')
def select_episodes(tmdb_id):
    """Show episode selection page after season selection"""
    try:
        # Get selected seasons from URL parameter
        selected_seasons_param = request.args.get('seasons', '1')
        selected_seasons = [int(s) for s in selected_seasons_param.split(',')]
        
        app.logger.info(f"Episode selection for TMDB ID {tmdb_id}, seasons: {selected_seasons}")
        
        # Find the corresponding series_id from pending requests
        series_id = None
        request_id = None
        
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(REQUESTS_DIR, filename), 'r') as f:
                        request_data = json.load(f)
                        if str(request_data.get('tmdb_id')) == str(tmdb_id):
                            series_id = request_data.get('series_id')
                            request_id = request_data.get('id')
                            app.logger.info(f"Found matching request: series_id={series_id}, request_id={request_id}")
                            break
                except Exception as e:
                    app.logger.error(f"Error reading request file {filename}: {str(e)}")
        
        if not series_id or not request_id:
            return render_template('error.html', message="No pending request found for this series")
        
        # Get TV show details from TMDB
        show_data = get_tmdb_endpoint(f"tv/{tmdb_id}")
        
        if not show_data:
            return render_template('error.html', message="Failed to get show details from TMDB")
        
        # Format show data for template
        formatted_show = {
            'id': tmdb_id,
            'name': show_data.get('name', 'Unknown Series'),
            'overview': show_data.get('overview', ''),
            'posterUrl': f"https://image.tmdb.org/t/p/w300{show_data['poster_path']}" if show_data.get('poster_path') else '/static/placeholder-banner.png',
            'seasons': []
        }
        
        # Only include selected seasons
        for season in show_data.get('seasons', []):
            season_num = season.get('season_number', 0)
            if season_num in selected_seasons:
                formatted_show['seasons'].append({
                    'seasonNumber': season_num,
                    'episodeCount': season.get('episode_count', '?')
                })
        
        return render_template('episode_selection.html', 
                             show=formatted_show, 
                             request_id=request_id,
                             series_id=series_id,
                             selected_seasons=selected_seasons)
    
    except Exception as e:
        app.logger.error(f"Error in select_episodes: {str(e)}", exc_info=True)
        return render_template('error.html', message=f"Error loading episode selection: {str(e)}")

@app.route('/api/process-episode-selection', methods=['POST'])
def process_episode_selection():
    """Process episode selection with multi-season support - ENHANCED VERSION"""
    try:
        app.logger.info(f"Form data received: {dict(request.form)}")
        
        # Get form data
        request_id = request.form.get('request_id')
        episodes = request.form.getlist('episodes')  # Now contains "season:episode" format
        action = request.form.get('action')
        
        app.logger.info(f"Processing: request_id={request_id}, action={action}, episodes={episodes}")
        
        if action == 'cancel':
            # Delete the request file
            if request_id:
                request_file = os.path.join(REQUESTS_DIR, f"{request_id}.json")
                if os.path.exists(request_file):
                    os.remove(request_file)
                    app.logger.info(f"Cancelled and removed request {request_id}")
            
            return redirect(url_for('episeerr_index', message="Request cancelled"))
        
        elif action == 'process':
            # Load request data
            request_file = os.path.join(REQUESTS_DIR, f"{request_id}.json")
            if not os.path.exists(request_file):
                return redirect(url_for('episeerr_index', message="Error: Request not found"))
            
            with open(request_file, 'r') as f:
                request_data = json.load(f)
            
            series_id = request_data['series_id']
            
            if not episodes:
                return redirect(url_for('episeerr_index', message="Error: No episodes selected"))
            
            # Parse episodes by season: "season:episode" format
            episodes_by_season = {}
            for episode_str in episodes:
                try:
                    season_str, episode_str = episode_str.split(':')
                    season_num = int(season_str)
                    episode_num = int(episode_str)
                    
                    if season_num not in episodes_by_season:
                        episodes_by_season[season_num] = []
                    episodes_by_season[season_num].append(episode_num)
                except ValueError:
                    app.logger.warning(f"Invalid episode format: {episode_str}")
                    continue
            
            if not episodes_by_season:
                return redirect(url_for('episeerr_index', message="Error: No valid episodes found"))
            
            app.logger.info(f"Processing multi-season selection for series {series_id}: {episodes_by_season}")
            
            # Store in pending_selections for processing
            episeerr_utils.pending_selections[str(series_id)] = {
                'title': request_data.get('title', 'Unknown'),
                'episodes_by_season': episodes_by_season,  # New format
                'selected_episodes': set(),  # Keep for compatibility
                'multi_season': True  # Flag for multi-season processing
            }
            
            # Process each season separately
            total_processed = 0
            failed_seasons = []
            
            for season_number, episode_numbers in episodes_by_season.items():
                app.logger.info(f"Processing Season {season_number}: {episode_numbers}")
                
                success = episeerr_utils.process_episode_selection_with_season(
                    series_id, season_number, episode_numbers
                )
                
                if success:
                    total_processed += len(episode_numbers)
                    app.logger.info(f"✓ Successfully processed Season {season_number}")
                else:
                    failed_seasons.append(season_number)
                    app.logger.error(f"✗ Failed to process Season {season_number}")
            
            # Clean up request file
            try:
                os.remove(request_file)
                app.logger.info(f"Removed request file: {request_id}.json")
            except Exception as e:
                app.logger.error(f"Error removing request file: {str(e)}")
            
            # Prepare result message
            if failed_seasons:
                message = f"Processed {total_processed} episodes. Failed seasons: {failed_seasons}"
                return redirect(url_for('episeerr_index', message=message))
            else:
                seasons_list = list(episodes_by_season.keys())
                message = f"Successfully processing {total_processed} episodes across {len(seasons_list)} seasons"
                return redirect(url_for('episeerr_index', message=message))
        
        else:
            return redirect(url_for('episeerr_index', message="Invalid action"))
            
    except Exception as e:
        app.logger.error(f"Error processing episode selection: {str(e)}", exc_info=True)
        return redirect(url_for('episeerr_index', message="An error occurred while processing episodes"))


# Also add this enhanced function to episeerr_utils.py:

def process_multi_season_selection(series_id, episodes_by_season):
    """
    Process episode selections across multiple seasons
    
    :param series_id: Sonarr series ID
    :param episodes_by_season: Dict like {1: [1,2,3], 2: [1,5,8]}
    :return: Dict with results per season
    """
    try:
        series_id = int(series_id)
        headers = get_sonarr_headers()
        
        # Get series info
        series_response = requests.get(f"{SONARR_URL}/api/v3/series/{series_id}", headers=headers)
        if not series_response.ok:
            logger.error(f"Failed to get series. Status: {series_response.status_code}")
            return {}
            
        series = series_response.json()
        logger.info(f"Processing multi-season selection for {series['title']}: {episodes_by_season}")
        
        results = {}
        all_episode_ids = []  # Collect all episode IDs for batch search
        
        for season_number, episode_numbers in episodes_by_season.items():
            logger.info(f"Processing Season {season_number}: {episode_numbers}")
            
            # Get episodes for this season
            episodes = get_series_episodes(series_id, season_number, headers)
            if not episodes:
                results[season_number] = {"success": False, "error": "No episodes found"}
                continue
            
            # Find matching episodes
            valid_episodes = []
            episode_ids = []
            
            for num in episode_numbers:
                matching_episode = next((ep for ep in episodes if ep['episodeNumber'] == num), None)
                if matching_episode:
                    valid_episodes.append(num)
                    episode_ids.append(matching_episode['id'])
                    all_episode_ids.append(matching_episode['id'])
                else:
                    logger.warning(f"Episode {num} not found in Season {season_number}")
            
            if not valid_episodes:
                results[season_number] = {"success": False, "error": "No valid episodes found"}
                continue
            
            # Monitor the episodes for this season
            monitor_response = requests.put(
                f"{SONARR_URL}/api/v3/episode/monitor",
                headers=headers,
                json={"episodeIds": episode_ids, "monitored": True}
            )
            
            if monitor_response.ok:
                results[season_number] = {
                    "success": True, 
                    "episodes": valid_episodes,
                    "episode_ids": episode_ids
                }
                logger.info(f"✓ Monitored {len(episode_ids)} episodes in Season {season_number}")
            else:
                results[season_number] = {
                    "success": False, 
                    "error": f"Monitor failed: {monitor_response.status_code}"
                }
                logger.error(f"Failed to monitor Season {season_number}: {monitor_response.text}")
        
        # Trigger search for ALL episodes at once (more efficient)
        if all_episode_ids:
            logger.info(f"Triggering search for {len(all_episode_ids)} total episodes")
            search_payload = {
                "name": "EpisodeSearch",
                "episodeIds": all_episode_ids
            }
            
            search_response = requests.post(
                f"{SONARR_URL}/api/v3/command",
                headers=headers,
                json=search_payload
            )
            
            if search_response.ok:
                logger.info(f"✓ Search triggered for all {len(all_episode_ids)} episodes")
            else:
                logger.error(f"Search failed: {search_response.text}")
        
        return results
        
    except Exception as e:
        logger.error(f"Error processing multi-season selection: {str(e)}", exc_info=True)
        return {}

@app.route('/api/tmdb/season/<tmdb_id>/<season_number>')
def get_tmdb_season(tmdb_id, season_number):
    """Get season details including episodes from TMDB API."""
    try:
        if not TMDB_API_KEY:
            return jsonify({"error": "TMDB API key not configured"}), 500
        
        season_data = get_tmdb_endpoint(f"tv/{tmdb_id}/season/{season_number}")
        
        if not season_data:
            return jsonify({"error": "Failed to get season data from TMDB"}), 500
        
        return jsonify(season_data)
        
    except Exception as e:
        app.logger.error(f"Error getting TMDB season data: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/delete-request/<request_id>', methods=['POST'])
def delete_request_fixed(request_id):
    """Fixed version that properly handles request deletion."""
    try:
        app.logger.info(f"Attempting to delete request: {request_id}")
        
        # Look for request files that contain this request_id
        deleted = False
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(REQUESTS_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        request_data = json.load(f)
                    
                    # Check if this request matches the request_id (not tmdb_id)
                    if str(request_data.get('id')) == str(request_id):
                        os.remove(filepath)
                        app.logger.info(f"Deleted pending request file {filename} for request ID {request_id}")
                        deleted = True
                        break
                except Exception as e:
                    app.logger.error(f"Error reading request file {filename}: {str(e)}")
                    continue
        
        if deleted:
            return jsonify({"status": "success", "message": "Request deleted successfully"}), 200
        else:
            app.logger.warning(f"Pending request for request ID {request_id} not found")
            return jsonify({"status": "error", "message": "Request not found"}), 404
            
    except Exception as e:
        app.logger.error(f"Error deleting request for request ID {request_id}: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to delete request"}), 500
@app.route('/api/pending-requests')
def get_pending_requests():
    if not TMDB_API_KEY:
        return jsonify({"success": False, "requests": [], "count": 0})
    try:
        pending_requests = []
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(REQUESTS_DIR, filename), 'r') as f:
                        request_data = json.load(f)
                        pending_requests.append(request_data)
                except Exception as e:
                    app.logger.error(f"Error reading request file {filename}: {str(e)}")
        pending_requests.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        return jsonify({
            "success": True,
            "requests": pending_requests,
            "count": len(pending_requests)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
@app.route('/api/delete-request/<tmdb_id>', methods=['POST'])
def delete_request(tmdb_id):
    try:
        # Look for request files that contain this tmdb_id
        deleted = False
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(REQUESTS_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        request_data = json.load(f)
                    
                    # Check if this request matches the tmdb_id
                    if str(request_data.get('tmdb_id')) == str(tmdb_id):
                        os.remove(filepath)
                        app.logger.info(f"Deleted pending request file {filename} for TMDB ID {tmdb_id}")
                        deleted = True
                        break
                except Exception as e:
                    app.logger.error(f"Error reading request file {filename}: {str(e)}")
                    continue
        
        if deleted:
            return jsonify({"status": "success", "message": "Request deleted successfully"}), 200
        else:
            app.logger.warning(f"Pending request for TMDB ID {tmdb_id} not found")
            return jsonify({"status": "error", "message": "Request not found"}), 404
            
    except Exception as e:
        app.logger.error(f"Error deleting request for TMDB ID {tmdb_id}: {str(e)}")
        return jsonify({"status": "error", "message": "Failed to delete request"}), 500
    
# Webhook Routes
# Replace your existing sonarr-webhook route with this enhanced version:

@app.route('/sonarr-webhook', methods=['POST'])
def process_sonarr_webhook():
    """Handle incoming Sonarr webhooks for series additions with enhanced Jellyseerr integration."""
    app.logger.info("Received Sonarr webhook")
    
    try:
        json_data = request.json
        
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

        # Get all tags from Sonarr to map IDs to labels
        tags_response = requests.get(f"{SONARR_URL}/api/v3/tag", headers=headers)
        if not tags_response.ok:
            app.logger.error(f"Failed to get tags from Sonarr: {tags_response.status_code}")
            return jsonify({"status": "error", "message": "Failed to get tags"}), 500
            
        tags = tags_response.json()
        tag_mapping = {tag['id']: tag['label'].lower() for tag in tags}

        # Check series tags
        series_tags = series.get('tags', [])
        app.logger.info(f"Series tags: {series_tags}")
        app.logger.info(f"Tag mapping: {tag_mapping}")

        # Check for episeerr tags
        has_episeerr_default = False
        has_episeerr_select = False

        for tag in series_tags:
            if isinstance(tag, int):
                # Tag is an ID - check against stored global IDs
                if tag == EPISEERR_DEFAULT_TAG_ID:
                    has_episeerr_default = True
                    break
                elif tag == EPISEERR_SELECT_TAG_ID:
                    has_episeerr_select = True
                    break
            else:
                # Tag is a string name - check the name directly
                if str(tag).lower() == 'episeerr_default':
                    has_episeerr_default = True
                    break
                elif str(tag).lower() == 'episeerr_select':
                    has_episeerr_select = True
                    break

        # If no episeerr tags, do nothing
        if not has_episeerr_default and not has_episeerr_select:
            app.logger.info(f"Series {series_title} has no episeerr tags, doing nothing")
            return jsonify({"status": "success", "message": "Series has no episeerr tags, no processing needed"}), 200
        
        # ENHANCED: Check for pending Jellyseerr request with better matching
        jellyseerr_request_id = None
        tvdb_id_str = str(tvdb_id) if tvdb_id else None
        
        app.logger.info(f"Looking for Jellyseerr request with TVDB ID: {tvdb_id_str}")
        app.logger.info(f"Current pending requests: {list(jellyseerr_pending_requests.keys())}")
        
        # Try multiple approaches to find the matching request
        if tvdb_id_str:
            # Direct TVDB ID match
            if tvdb_id_str in jellyseerr_pending_requests:
                jellyseerr_request = jellyseerr_pending_requests[tvdb_id_str]
                jellyseerr_request_id = jellyseerr_request.get('request_id')
                app.logger.info(f"✓ Found matching Jellyseerr request for {series_title}: {jellyseerr_request_id}")
            else:
                # Try with different string formats
                for stored_tvdb_id, request_info in jellyseerr_pending_requests.items():
                    if str(stored_tvdb_id) == tvdb_id_str or int(stored_tvdb_id) == int(tvdb_id_str):
                        jellyseerr_request_id = request_info.get('request_id')
                        app.logger.info(f"✓ Found matching Jellyseerr request via alternate lookup: {jellyseerr_request_id}")
                        # Move to correct key format
                        jellyseerr_pending_requests[tvdb_id_str] = jellyseerr_pending_requests.pop(stored_tvdb_id)
                        break
                
                # If still not found, try title-based matching as backup
                if not jellyseerr_request_id:
                    for stored_tvdb_id, request_info in jellyseerr_pending_requests.items():
                        stored_title = request_info.get('title', '').lower().strip()
                        current_title = series_title.lower().strip()
                        
                        # Fuzzy title matching
                        if stored_title == current_title or stored_title in current_title or current_title in stored_title:
                            jellyseerr_request_id = request_info.get('request_id')
                            app.logger.info(f"✓ Found matching Jellyseerr request via title match: {jellyseerr_request_id}")
                            # Update the mapping for future use
                            jellyseerr_pending_requests[tvdb_id_str] = jellyseerr_pending_requests.pop(stored_tvdb_id)
                            break
        
        # Cancel the Jellyseerr request if found
        if jellyseerr_request_id:
            app.logger.info(f"Cancelling Jellyseerr request {jellyseerr_request_id}")
            cancel_result = episeerr_utils.delete_overseerr_request(jellyseerr_request_id)
            app.logger.info(f"Jellyseerr cancellation result: {cancel_result}")
            
            # Remove from pending requests
            if tvdb_id_str in jellyseerr_pending_requests:
                del jellyseerr_pending_requests[tvdb_id_str]
                app.logger.info(f"✓ Removed TVDB ID {tvdb_id_str} from pending requests")
        else:
            app.logger.info(f"No matching Jellyseerr request found for TVDB ID: {tvdb_id_str}")
            app.logger.info(f"Available pending requests: {jellyseerr_pending_requests}")
        
        # ALWAYS: Unmonitor all episodes and remove episeerr tags
        app.logger.info(f"Unmonitoring all episodes for {series_title}")
        unmonitor_success = episeerr_utils.unmonitor_series(series_id, headers)
        if not unmonitor_success:
            app.logger.warning(f"Failed to unmonitor episodes for {series_title}")
        
        # Remove episeerr tags from the series
        app.logger.info(f"Removing episeerr tags from {series_title}")
        updated_tags = []
        removed_tags = []
        
        for tag_id in series_tags:
            tag_label = tag_mapping.get(tag_id, '').lower()
            if tag_label in ['episeerr_default', 'episeerr_select']:
                removed_tags.append(tag_label)
            else:
                updated_tags.append(tag_id)
        
        if removed_tags:
            # Update series with removed tags
            update_payload = series.copy()
            update_payload['tags'] = updated_tags
            
            update_response = requests.put(f"{SONARR_URL}/api/v3/series", headers=headers, json=update_payload)
            if update_response.ok:
                app.logger.info(f"✓ Removed tags {removed_tags} from {series_title}")
            else:
                app.logger.error(f"Failed to remove tags from {series_title}: {update_response.text}")
        
        # Cancel any active downloads
        app.logger.info(f"Checking for downloads to cancel for {series_title}")
        try:
            episeerr_utils.check_and_cancel_unmonitored_downloads()
        except Exception as e:
            app.logger.error(f"Error cancelling downloads: {str(e)}")
        
        # Process based on tag type
        if has_episeerr_default:
            app.logger.info(f"Processing {series_title} with episeerr_default tag")
            
            # SAFE VERSION - Add to default rule with protection
            try:
                config = load_config()
                default_rule_name = config.get('default_rule', 'default')
                
                app.logger.info(f"Adding {series_title} to default rule '{default_rule_name}'")
                app.logger.info(f"Current rules before modification: {list(config['rules'].keys())}")
                
                if default_rule_name not in config['rules']:
                    app.logger.error(f"Default rule '{default_rule_name}' not found in config!")
                    app.logger.info(f"Available rules: {list(config['rules'].keys())}")
                    return jsonify({"status": "error", "message": f"Default rule '{default_rule_name}' not found"}), 500
                
                series_id_str = str(series_id)
                
                # Get the specific rule we're modifying
                target_rule = config['rules'][default_rule_name]
                
                # Ensure series dict structure exists
                if 'series' not in target_rule:
                    target_rule['series'] = {}
                
                series_dict = target_rule['series']
                if not isinstance(series_dict, dict):
                    app.logger.warning(f"Converting series from {type(series_dict)} to dict for rule '{default_rule_name}'")
                    series_dict = {}
                    target_rule['series'] = series_dict
                
                # Add series if not already present
                if series_id_str not in series_dict:
                    series_dict[series_id_str] = {'activity_date': None}
                    app.logger.info(f"Added series {series_id_str} to rule '{default_rule_name}'")
                    
                    # CRITICAL: Validate config before saving
                    if len(config['rules']) < 2:  # You had 3 rules, so this is a safety check
                        app.logger.error(f"CONFIG CORRUPTION DETECTED! Only {len(config['rules'])} rules found, expected at least 2")
                        app.logger.error(f"Current rules: {list(config['rules'].keys())}")
                        app.logger.error("REFUSING TO SAVE - this would lose your rules!")
                        return jsonify({"status": "error", "message": "Config corruption detected, save aborted"}), 500
                    
                    app.logger.info(f"Config validation passed - {len(config['rules'])} rules present: {list(config['rules'].keys())}")
                    save_config(config)
                    app.logger.info(f"✓ Successfully added {series_title} to default rule '{default_rule_name}'")
                else:
                    app.logger.info(f"Series {series_id_str} already in rule '{default_rule_name}'")

            except Exception as e:
                app.logger.error(f"Error adding series to default rule: {str(e)}", exc_info=True)
                return jsonify({"status": "error", "message": f"Failed to add series to rule: {str(e)}"}), 500


            # Execute default rule immediately
            try:
                rule_config = config['rules'][default_rule_name]
                get_option = rule_config.get('get_option')
                action_option = rule_config.get('action_option', 'monitor')
                
                app.logger.info(f"Executing default rule with get_option '{get_option}' for {series_title}")
                
                # Get all episodes for the series
                episodes_response = requests.get(
                    f"{SONARR_URL}/api/v3/episode?seriesId={series_id}",
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
                            app.logger.info(f"Monitoring all episodes for {series_title}")
                            
                        elif get_option == 'season':
                            # Get all episodes from Season 1
                            episodes_to_monitor = [ep['id'] for ep in season1_episodes]
                            app.logger.info(f"Monitoring Season 1 ({len(episodes_to_monitor)} episodes) for {series_title}")
                            
                        else:
                            try:
                                # Treat as number of episodes to get from Season 1
                                num_episodes = int(get_option)
                                episodes_to_monitor = [ep['id'] for ep in season1_episodes[:num_episodes]]
                                app.logger.info(f"Monitoring first {len(episodes_to_monitor)} episodes for {series_title}")
                            except (ValueError, TypeError):
                                # Fallback to pilot episode if get_option is invalid
                                episodes_to_monitor = [season1_episodes[0]['id']] if season1_episodes else []
                                app.logger.warning(f"Invalid get_option '{get_option}', defaulting to pilot episode for {series_title}")
                        
                        if episodes_to_monitor:
                            # Monitor the selected episodes
                            monitor_response = requests.put(
                                f"{SONARR_URL}/api/v3/episode/monitor",
                                headers=headers,
                                json={"episodeIds": episodes_to_monitor, "monitored": True}
                            )
                            
                            if monitor_response.ok:
                                app.logger.info(f"✓ Monitored {len(episodes_to_monitor)} episodes for {series_title}")
                                
                                # Search for episodes if action_option is 'search'
                                if action_option == 'search':
                                    search_response = requests.post(
                                        f"{SONARR_URL}/api/v3/command",
                                        headers=headers,
                                        json={"name": "EpisodeSearch", "episodeIds": episodes_to_monitor}
                                    )
                                    
                                    if search_response.ok:
                                        app.logger.info(f"✓ Started search for {len(episodes_to_monitor)} episodes of {series_title}")
                                    else:
                                        app.logger.error(f"Failed to search for episodes: {search_response.text}")
                            else:
                                app.logger.error(f"Failed to monitor episodes: {monitor_response.text}")
                        else:
                            app.logger.warning(f"No episodes to monitor for {series_title}")
                else:
                    app.logger.error(f"Failed to get episodes for series: {episodes_response.text}")
            except Exception as e:
                app.logger.error(f"Error executing default rule for {series_title}: {str(e)}", exc_info=True)
            
            return jsonify({
                "status": "success",
                "message": "Series processed with default rule"
            }), 200
        
        elif has_episeerr_select:
            app.logger.info(f"Processing {series_title} with episeerr_select tag - creating selection request")
            
            # Ensure we have a TMDB ID for the UI
            if not tmdb_id:
                try:
                    # Try to get TMDB ID from TVDB ID using TMDB API
                    external_ids = get_external_ids(tvdb_id, 'tv')
                    if external_ids and external_ids.get('tmdb_id'):
                        tmdb_id = external_ids['tmdb_id']
                    else:
                        # Search by title as fallback
                        search_results = search_tv_shows(series_title)
                        if search_results.get('results'):
                            tmdb_id = search_results['results'][0]['id']
                except Exception as e:
                   app.logger.error(f"Error finding TMDB ID: {str(e)}")
            
            # Create a selection request
            request_id = f"sonarr-select-{series_id}-{int(time.time())}"
            
            pending_request = {
                "id": request_id,
                "series_id": series_id,
                "title": series_title,
                "needs_season_selection": True,
                "tmdb_id": tmdb_id,
                "tvdb_id": tvdb_id,
                "source": "sonarr",
                "source_name": "Sonarr Episode Selection",
                "needs_attention": True,
                "jellyseerr_request_id": jellyseerr_request_id,  # Store for potential cleanup
                "created_at": int(time.time())
            }
            
            os.makedirs(REQUESTS_DIR, exist_ok=True)
            with open(os.path.join(REQUESTS_DIR, f"{request_id}.json"), 'w') as f:
                json.dump(pending_request, f, indent=2)
            
            app.logger.info(f"✓ Created episode selection request for {series_title}")
            
            return jsonify({
                "status": "success",
                "message": "Episode selection request created"
            }), 200
        
        # Should not reach here
        return jsonify({
            "status": "success",
            "message": "Processing completed"
        }), 200
            
    except Exception as e:
        app.logger.error(f"Error processing Sonarr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500

# Add this debug route to check Jellyseerr webhook status
@app.route('/debug/jellyseerr-pending')
def debug_jellyseerr_pending():
    """Debug route to check pending Jellyseerr requests"""
    return jsonify({
        "pending_requests": jellyseerr_pending_requests,
        "count": len(jellyseerr_pending_requests)
    })

@app.route('/seerr-webhook', methods=['POST'])
def process_seerr_webhook():
    """Handle incoming Jellyseerr webhooks - store request info for later with enhanced matching."""
    try:
        app.logger.info("=== JELLYSEERR WEBHOOK RECEIVED ===")
        json_data = request.json
        
        # Log the full webhook data for debugging
        app.logger.info(f"Jellyseerr webhook data: {json.dumps(json_data, indent=2)}")
        
        # Get the request ID - try multiple possible locations
        request_info = json_data.get('request', {})
        request_id = (
            request_info.get('request_id') or 
            request_info.get('id') or 
            json_data.get('request_id') or
            json_data.get('id')
        )
        
        # Get media info
        media_info = json_data.get('media', {})
        media_type = media_info.get('media_type')
        
        app.logger.info(f"Request ID: {request_id}, Media Type: {media_type}")
        
        # Only process TV show requests
        if media_type != 'tv':
            app.logger.info(f"Request is not a TV show (media_type={media_type}), skipping")
            return jsonify({"status": "success", "message": "Not a TV request"}), 200
        
        # Get identifiers
        tvdb_id = media_info.get('tvdbId')
        tmdb_id = media_info.get('tmdbId')
        title = json_data.get('subject', 'Unknown Show')
        
        app.logger.info(f"TVDB ID: {tvdb_id}, TMDB ID: {tmdb_id}, Title: {title}")
        
        if tvdb_id and request_id:
            # Store the request info for later use by the Sonarr webhook
            global jellyseerr_pending_requests
            
            # Normalize TVDB ID to string for consistent lookup
            tvdb_id_str = str(tvdb_id)
            
            jellyseerr_pending_requests[tvdb_id_str] = {
                'request_id': request_id,
                'title': title,
                'tmdb_id': tmdb_id,
                'tvdb_id': tvdb_id,  # Store original for reference
                'timestamp': int(time.time())
            }
            
            app.logger.info(f"✓ Stored Jellyseerr request {request_id} for TVDB ID {tvdb_id_str} ({title})")
            
            # Clean up old requests (older than 10 minutes)
            current_time = int(time.time())
            expired_tvdb_ids = []
            
            for tid, info in jellyseerr_pending_requests.items():
                if current_time - info.get('timestamp', 0) > 600:  # 10 minutes
                    expired_tvdb_ids.append(tid)
            
            for tid in expired_tvdb_ids:
                expired_request = jellyseerr_pending_requests.pop(tid, {})
                app.logger.info(f"Cleaned up expired request for TVDB ID {tid} (request {expired_request.get('request_id')})")
                
            app.logger.info(f"Current pending requests: {list(jellyseerr_pending_requests.keys())}")
            
            # Also log the mapping for debugging
            for stored_id, stored_info in jellyseerr_pending_requests.items():
                app.logger.debug(f"  - TVDB {stored_id}: Request {stored_info.get('request_id')} ({stored_info.get('title')})")
                
        else:
            app.logger.warning(f"Missing required data - TVDB ID: {tvdb_id}, Request ID: {request_id}")
        
        return jsonify({"status": "success"}), 200
        
    except Exception as e:
        app.logger.error(f"Error processing Jellyseerr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500


# Add this debug route to help troubleshoot:
@app.route('/debug/jellyseerr-state')
def debug_jellyseerr_state():
    """Enhanced debug route to check Jellyseerr webhook state"""
    current_time = int(time.time())
    
    debug_info = {
        "current_timestamp": current_time,
        "pending_requests": {},
        "count": len(jellyseerr_pending_requests)
    }
    
    for tvdb_id, request_info in jellyseerr_pending_requests.items():
        age_seconds = current_time - request_info.get('timestamp', 0)
        debug_info["pending_requests"][tvdb_id] = {
            "request_id": request_info.get('request_id'),
            "title": request_info.get('title'),
            "tmdb_id": request_info.get('tmdb_id'),
            "timestamp": request_info.get('timestamp'),
            "age_seconds": age_seconds,
            "age_minutes": round(age_seconds / 60, 1)
        }
    
    return jsonify(debug_info)

@app.route('/webhook', methods=['POST'])
def handle_server_webhook():
    app.logger.info("Received webhook from Tautulli")
    data = request.json
    if data:
        try:
            temp_dir = os.path.join(os.getcwd(), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            plex_data = {
                "server_title": data.get('plex_title'),
                "server_season_num": data.get('plex_season_num'),
                "server_ep_num": data.get('plex_ep_num')
            }
            with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
                json.dump(plex_data, f)
            result = subprocess.run(["python3", os.path.join(os.getcwd(), "servertosonarr.py")], capture_output=True, text=True)
            if result.stderr:
                app.logger.error(f"Servertosonarr.py error: {result.stderr}")
            app.logger.info("Webhook processing completed - activity tracked, next content processed")
            return jsonify({'status': 'success'}), 200
        except Exception as e:
            app.logger.error(f"Failed to process Tautulli webhook: {str(e)}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
    return jsonify({'status': 'error', 'message': 'No data received'}), 400

@app.route('/jellyfin-webhook', methods=['POST'])
def handle_jellyfin_webhook():
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
                if 45 <= progress_percent <= 55:
                    item_type = data.get('ItemType')
                    if item_type == 'Episode':
                        series_name = data.get('SeriesName')
                        season = data.get('SeasonNumber')
                        episode = data.get('EpisodeNumber')
                        if all([series_name, season is not None, episode is not None]):
                            app.logger.info(f"Processing Jellyfin episode: {series_name} S{season}E{episode}")
                            jellyfin_data = {
                                "server_title": series_name,
                                "server_season_num": str(season),
                                "server_ep_num": str(episode)
                            }
                            temp_dir = os.path.join(os.getcwd(), 'temp')
                            os.makedirs(temp_dir, exist_ok=True)
                            with open(os.path.join(temp_dir, 'data_from_server.json'), 'w') as f:
                                json.dump(jellyfin_data, f)
                            result = subprocess.run(["python3", os.path.join(os.getcwd(), "servertosonarr.py")], 
                                                   capture_output=True, text=True)
                            if result.stderr:
                                app.logger.error(f"Errors from servertosonarr.py: {result.stderr}")
                            app.logger.info("Jellyfin webhook processing completed - activity tracked, next content processed")
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

@app.route('/api/safety-status')
def safety_status():
    try:
        config = load_config()
        global_dry_run = os.getenv('CLEANUP_DRY_RUN', 'false').lower() == 'true'
        rules_with_dry_run = []
        for rule_name, rule_details in config.get('rules', {}).items():
            if rule_details.get('dry_run', False):
                rules_with_dry_run.append(rule_name.replace('_', ' ').title())
        return jsonify({
            "global_dry_run": global_dry_run,
            "rules_with_dry_run": rules_with_dry_run,
            "total_rules": len(config.get('rules', {})),
            "status": "success"
        })
    except Exception as e:
        current_app.logger.error(f"Error getting safety status: {str(e)}")
        return jsonify({
            "global_dry_run": False,
            "rules_with_dry_run": [],
            "total_rules": 0,
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/current-assignments')
def get_current_assignments():
    """Get current rule assignments for all series"""
    try:
        config = load_config()
        all_series = get_sonarr_series()
        
        assignments = {}
        
        # Build assignment mapping
        for rule_name, details in config['rules'].items():
            series_dict = details.get('series', {})
            for series_id in series_dict.keys():
                assignments[str(series_id)] = rule_name
        
        # Add series without assignments
        for series in all_series:
            series_id = str(series['id'])
            if series_id not in assignments:
                assignments[series_id] = 'None'
        
        return jsonify(assignments)
        
    except Exception as e:
        app.logger.error(f"Error getting current assignments: {str(e)}")
        return jsonify({}), 500

@app.route('/api/quick-stats')
def get_quick_stats():
    """Get quick stats for change detection"""
    try:
        config = load_config()
        all_series = get_sonarr_series()
        
        # Count assigned series
        assigned_count = 0
        for rule_name, details in config['rules'].items():
            assigned_count += len(details.get('series', {}))
        
        stats = {
            'total_series': len(all_series),
            'assigned_series': assigned_count,
            'unassigned_series': len(all_series) - assigned_count,
            'total_rules': len(config['rules']),
            'timestamp': int(time.time())
        }
        
        return jsonify(stats)
        
    except Exception as e:
        app.logger.error(f"Error getting quick stats: {str(e)}")
        return jsonify({
            'total_series': 0,
            'assigned_series': 0,
            'unassigned_series': 0,
            'total_rules': 0,
            'timestamp': int(time.time())
        }), 500

@app.route('/episeerr')
def episeerr_index():
    return render_template('episeerr_index.html')
def initialize_episeerr():
    app.logger.debug("Entering initialize_episeerr()")
    
    # Tags are already created in episeerr_utils.py, so skip those calls
    # Perform other initialization tasks
    app.logger.debug("Checking unmonitored downloads")
    try:
        episeerr_utils.check_and_cancel_unmonitored_downloads()
    except Exception as e:
        app.logger.error(f"Error in initial download check: {str(e)}")

    app.logger.debug("Exiting initialize_episeerr()")

# Create scheduler instance
cleanup_scheduler = OCDarrScheduler()
app.logger.info("✓ OCDarrScheduler instantiated successfully")
cleanup_scheduler.start_scheduler()

if __name__ == '__main__':
    cleanup_config_rules()
    initialize_episeerr()
    app.logger.info("🚀 Episeerr webhook listener starting - webhook handles activity tracking and requests")
    app.run(host='0.0.0.0', port=5002, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')