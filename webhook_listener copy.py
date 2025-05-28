#!/usr/bin/env python3
"""
Simplified Rules-Only Flask App for Sonarr Management
Focuses only on rule creation, assignment, and management without media browsing/requests
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
        
        # Track changes
        changes_made = False
        
        # Clean up rules
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
        
        # Remove empty rules
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
    
    # Get all series from Sonarr
    all_series = get_sonarr_series()
    
    # Create mapping of series to rules
    rules_mapping = {}
    for rule_name, details in config['rules'].items():
        for series_id in details.get('series', []):
            rules_mapping[str(series_id)] = rule_name
    
    # Add rule assignment info to series
    for series in all_series:
        series['assigned_rule'] = rules_mapping.get(str(series['id']), 'None')
    
    # Sort series alphabetically
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
    
    # Don't allow deletion of default rule
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
    
    # Remove these series from all other rules
    for rule, details in config['rules'].items():
        details['series'] = [sid for sid in details.get('series', []) if sid not in series_ids]
    
    # Add series to the selected rule
    config['rules'][rule_name]['series'].extend(series_ids)
    
    save_config(config)
    
    return redirect(url_for('index', message=f"Assigned {len(series_ids)} series to rule '{rule_name}'"))

@app.route('/unassign-series', methods=['POST'])
def unassign_series():
    """Remove series from all rules."""
    config = load_config()
    
    series_ids = request.form.getlist('series_ids')
    
    # Remove series from all rules
    total_removed = 0
    for rule_name, details in config['rules'].items():
        original_count = len(details.get('series', []))
        details['series'] = [sid for sid in details.get('series', []) if sid not in series_ids]
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
        
        # Create mapping
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
        
        # Count series per rule
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

if __name__ == '__main__':
    # Cleanup rules on startup
    cleanup_config_rules()
    
    # Run the app
    app.run(
        host='0.0.0.0', 
        port=int(os.getenv('PORT', 5005)), 
        debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    )