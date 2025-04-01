from flask import Flask, render_template, request, redirect, url_for, jsonify
import subprocess
import os
import re
import time
import logging
import json
import sonarr_utils
import radarr_utils
from datetime import datetime
from dotenv import load_dotenv
import requests
import modified_episeerr
import threading
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from api.jellyseerr_api import JellyseerrAPI
import tmdb_utils
import plex_utils

app = Flask(__name__)

# Load environment variables
load_dotenv()
BASE_DIR = os.getcwd()
# Sonarr variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Radarr variables
RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')
# Jellyseerr variables
JELLYSEERR_URL = os.getenv('JELLYSEERR_URL', '')

# Other settings
REQUESTS_DIR = os.path.join(os.getcwd(), 'data', 'requests')
os.makedirs(REQUESTS_DIR, exist_ok=True)

LAST_PROCESSED_FILE = os.path.join(os.getcwd(), 'data', 'last_processed.json')
os.makedirs(os.path.dirname(LAST_PROCESSED_FILE), exist_ok=True)

# Initialize the Jellyseerr API client
jellyseerr_api = JellyseerrAPI()

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
    try:
        with open(config_path, 'r') as file:
            config = json.load(file)
        if 'rules' not in config:
            config['rules'] = {}
        if 'preferences' not in config:
            config['preferences'] = {}
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
            'preferences': {
                'radarr_quality_profile': 'Any',
                'sonarr_quality_profile': 'Any'
            }
        }
        return default_config

def save_config(config):
    with open(config_path, 'w') as file:
        json.dump(config, file, indent=4)

def check_service_status(url):
    try:
        # Add a longer timeout and use a HEAD request which is lighter
        response = requests.head(url, timeout=3, allow_redirects=True)
        
        # Check for successful status codes
        if response.status_code in [200, 301, 302, 303, 307, 308]:
            return "Online"
    except requests.exceptions.RequestException:
        pass
    
    return "Offline"

@app.route('/api/plex/connect', methods=['POST'])
def connect_to_plex():
    try:
        plex_token = request.form.get('plex_token', '')
        
        if not plex_token:
            return jsonify({"success": False, "message": "Plex token is required"}), 400
            
        # Test the token
        plex_api = plex_utils.PlexWatchlistAPI(plex_token)
        watchlist = plex_api.get_watchlist()
        
        if 'MediaContainer' not in watchlist:
            return jsonify({"success": False, "message": "Invalid Plex token"}), 400
            
        # Save token to .env file instead of config
        with open('.env', 'a') as f:
            f.write(f"\nPLEX_TOKEN={plex_token}\n")
        
        # Update config to mark Plex as connected
        config = load_config()
        if 'plex' not in config:
            config['plex'] = {}
            
        config['plex']['connected'] = True
        config['plex']['auto_download'] = False  # Default to off
        config['plex']['last_sync'] = datetime.now().isoformat()
        
        save_config(config)
        
        # Sync watchlist
        plex_api.save_watchlist_data()
        
        return jsonify({"success": True, "message": "Connected to Plex successfully"})
    except Exception as e:
        app.logger.error(f"Error connecting to Plex: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/plex/watchlist')
def get_plex_watchlist():
    try:
        # Read Plex token directly from .env
        plex_token = os.getenv('PLEX_TOKEN', '')
       
        if not plex_token:
            return jsonify({"success": False, "message": "Plex not connected"}), 400
           
        plex_api = plex_utils.PlexWatchlistAPI(plex_token)
        watchlist_data = plex_api.load_watchlist_data()
       
        # Get existing Sonarr/Radarr series
        sonarr_preferences = sonarr_utils.load_preferences()
        sonarr_series = sonarr_utils.get_series_list(sonarr_preferences)
        sonarr_tmdb_ids = set(str(series.get('tmdbId')) for series in sonarr_series if series.get('tmdbId'))
       
        radarr_preferences = radarr_utils.load_preferences()
        radarr_movies = radarr_utils.get_movie_list(radarr_preferences)
        radarr_tmdb_ids = set(str(movie.get('tmdbId')) for movie in radarr_movies if movie.get('tmdbId'))
       
        # Get all items
        all_items = watchlist_data.get('items', [])
        
        # Debug
        print(f"Watchlist items: {len(all_items)}")
        for item in all_items:
            print(f"Item: {item.get('title')}, Type: {item.get('type')}, TMDB ID: {item.get('tmdb_id')}")
        
        # Categorize items
        watchlist_categories = {
            'tv_in_watchlist': [],
            'tv_not_in_arr': [],
            'movie_in_watchlist': [],
            'movie_not_in_arr': []
        }
       
        for item in all_items:
            tmdb_id = str(item.get('tmdb_id', ''))
            item_type = item.get('type')
            
            if not tmdb_id or not item_type:
                print(f"Skipping item with missing data: {item}")
                continue
            
            if item_type == 'tv':
                # Add to tv_in_watchlist if it's in Sonarr
                if tmdb_id in sonarr_tmdb_ids:
                    watchlist_categories['tv_in_watchlist'].append(item)
                else:
                    watchlist_categories['tv_not_in_arr'].append(item)
                    
                # For testing: Add all TV items to not_in_arr to ensure UI works
                watchlist_categories['tv_not_in_arr'].append(item)
            elif item_type == 'movie':
                # Add to movie_in_watchlist if it's in Radarr
                if tmdb_id in radarr_tmdb_ids:
                    watchlist_categories['movie_in_watchlist'].append(item)
                else:
                    watchlist_categories['movie_not_in_arr'].append(item)
                    
                # For testing: Add all movie items to not_in_arr to ensure UI works
                watchlist_categories['movie_not_in_arr'].append(item)
        
        # Get library stats
        library_sections = plex_api.get_library_sections()
        library_stats = {
            "movies": 0,
            "tv_shows": 0
        }
        
        print(f"Library sections: {library_sections}")
        
        # Get library counts
        if library_sections.get("movie"):
            try:
                movie_url = f"http://192.168.254.205:32400/library/sections/{library_sections['movie']}/all"
                movie_response = requests.get(movie_url, headers=plex_api.get_headers())
                if movie_response.ok:
                    movie_data = movie_response.json()
                    library_stats["movies"] = movie_data.get("MediaContainer", {}).get("size", 0)
                    print(f"Movie count: {library_stats['movies']}")
            except Exception as e:
                app.logger.error(f"Error getting movie count: {str(e)}")
        
        if library_sections.get("tv"):
            try:
                tv_url = f"http://192.168.254.205:32400/library/sections/{library_sections['tv']}/all"
                tv_response = requests.get(tv_url, headers=plex_api.get_headers())
                if tv_response.ok:
                    tv_data = tv_response.json()
                    library_stats["tv_shows"] = tv_data.get("MediaContainer", {}).get("size", 0)
                    print(f"TV count: {library_stats['tv_shows']}")
            except Exception as e:
                app.logger.error(f"Error getting TV show count: {str(e)}")
        
        # Count watchlist items by type
        watchlist_stats = {
            "movies": len([item for item in all_items if item.get("type") == "movie"]),
            "tv_shows": len([item for item in all_items if item.get("type") == "tv"])
        }
        
        print(f"Watchlist stats: {watchlist_stats}")
       
        # Prepare response
        response_data = {
            'success': True,
            'watchlist': {
                'categories': watchlist_categories,
                'last_updated': watchlist_data.get('last_updated'),
                'count': len(all_items),
                'stats': {
                    'library_stats': library_stats,
                    'watchlist_stats': watchlist_stats
                }
            }
        }
        
        # Debug - print category counts
        for category, items in watchlist_categories.items():
            print(f"Category {category}: {len(items)} items")
       
        return jsonify(response_data)
   
    except Exception as e:
        app.logger.error(f"Error fetching Plex watchlist: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


def cleanup_config_rules():
    """Remove series from rules that no longer exist in Sonarr."""
    try:
        # Load the current configuration
        config = load_config()
        
        # Load Sonarr preferences
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        # Fetch all series from Sonarr
        series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
        
        if not series_response.ok:
            app.logger.error("Failed to fetch series from Sonarr during config cleanup")
            return
        
        # Get set of existing series IDs as strings
        existing_series_ids = set(str(series['id']) for series in series_response.json())
        
        # Track removed series for logging
        removed_series = {}
        
        # Iterate through all rules
        for rule_name, rule_details in config['rules'].items():
            # Filter out series IDs that no longer exist in Sonarr
            original_series = rule_details.get('series', [])
            updated_series = [
                series_id for series_id in original_series 
                if series_id in existing_series_ids
            ]
            
            # Track removed series
            if len(updated_series) != len(original_series):
                removed_series[rule_name] = [
                    sid for sid in original_series 
                    if sid not in updated_series
                ]
            
            # Update the rule's series list
            rule_details['series'] = updated_series
        
        # Remove empty rules
        config['rules'] = {
            rule: details for rule, details in config['rules'].items() 
            if details.get('series')
        }
        
        # Save the updated configuration
        save_config(config)
        
        # Log removed series
        for rule, series_list in removed_series.items():
            app.logger.info(f"Cleaned up rule '{rule}': Removed series IDs {series_list}")
        
        app.logger.info("Completed configuration rules cleanup")
    
    except Exception as e:
        app.logger.error(f"Error during config rules cleanup: {str(e)}", exc_info=True)
    




    
@app.route('/api/tmdb/filtered/tv')
def tmdb_filtered_tv():
    """Get filtered TV shows using TMDB API directly."""
    try:
        # Get quality TV shows
        shows_data = tmdb_utils.get_quality_tv_shows()
        
        # Format the data to match what your frontend expects
        results = []
        for show in shows_data.get('results', []):
            results.append({
                'id': show['id'],
                'name': show['name'],
                'posterUrl': f"https://image.tmdb.org/t/p/w300{show['poster_path']}" if show.get('poster_path') else '/static/placeholder-banner.png',
                'overview': show.get('overview', ''),
                'releaseYear': show.get('first_air_date', '').split('-')[0] if show.get('first_air_date') else '',
                'genre_ids': show.get('genre_ids', [])
            })
        
        app.logger.info(f"Returning {len(results)} filtered TV shows")
        return jsonify({'results': results})
        
    except Exception as e:
        app.logger.error(f"Error in tmdb_filtered_tv: {str(e)}", exc_info=True)
        return jsonify({"results": [], "error": str(e)})

@app.route('/api/tmdb/filtered/movies')
def tmdb_filtered_movies():
    """Get filtered movies using TMDB API directly."""
    try:
        # Get quality movies
        movies_data = tmdb_utils.get_quality_movies()
        
        # Format the data to match what your frontend expects
        results = []
        for movie in movies_data.get('results', []):
            results.append({
                'id': movie['id'],
                'title': movie['title'],
                'posterUrl': f"https://image.tmdb.org/t/p/w300{movie['poster_path']}" if movie.get('poster_path') else '/static/placeholder-banner.png',
                'overview': movie.get('overview', ''),
                'releaseYear': movie.get('release_date', '').split('-')[0] if movie.get('release_date') else '',
                'genre_ids': movie.get('genre_ids', [])
            })
        
        app.logger.info(f"Returning {len(results)} filtered movies")
        return jsonify({'results': results})
        
    except Exception as e:
        app.logger.error(f"Error in tmdb_filtered_movies: {str(e)}", exc_info=True)
        return jsonify({"results": [], "error": str(e)})

@app.route('/api/tmdb/season/<tmdb_id>/<season_number>')
def get_tmdb_season(tmdb_id, season_number):
    """Get season details from TMDB API."""
    try:
        season_data = tmdb_utils.get_tmdb_endpoint(f"tv/{tmdb_id}/season/{season_number}")
        return jsonify(season_data)
    except Exception as e:
        app.logger.error(f"Error fetching season data: {str(e)}")
        return jsonify({"error": str(e)}), 500
    

    
def create_pending_request(series):
    """Create a pending request for season/episode selection."""
    request_id = f"season-select-{series['id']}-{int(time.time())}"
    
    pending_request = {
        "id": request_id,
        "series_id": series['id'],
        "title": series.get('title', 'Unknown Series'),
        "tmdb_id": series.get('tmdbId'),
        "tvdb_id": series.get('tvdbId'),
        "needs_season_selection": True,
        "source": "sonarr_webhook",
        "source_name": "Sonarr Webhook",
        "needs_attention": True,
        "created_at": int(time.time())
    }
    
    os.makedirs(REQUESTS_DIR, exist_ok=True)
    with open(os.path.join(REQUESTS_DIR, f"{request_id}.json"), 'w') as f:
        json.dump(pending_request, f)
    
    app.logger.info(f"Created pending request for {pending_request['title']}")
    
    return pending_request
    
@app.route('/api/radarr/request', methods=['POST'])
def radarr_request():
    """Handle movie requests directly to Radarr."""
    try:
        data = request.json
        tmdb_id = data.get('tmdbId')
        title = data.get('title', 'Unknown')
        
        if not tmdb_id:
            return jsonify({"success": False, "message": "No TMDB ID provided"}), 400
            
        # Load config to get preferred profile
        config = load_config()
        preferred_profile = config.get('preferences', {}).get('radarr_quality_profile', 'Any')
            
        # Check if movie exists in Radarr
        radarr_preferences = radarr_utils.load_preferences()
        headers = {
            'X-Api-Key': radarr_preferences['RADARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        radarr_url = radarr_preferences['RADARR_URL']
        
        # Look up the movie in TMDB
        response = requests.get(
            f"{radarr_url}/api/v3/movie/lookup/tmdb", 
            headers=headers,
            params={"tmdbId": tmdb_id}
        )
        
        if not response.ok:
            return jsonify({"success": False, "message": f"Failed to look up movie in Radarr"}), 500
            
        lookup_results = response.json()
        
        # Check if movie already exists in Radarr
        existing_movies = radarr_utils.get_movie_list(radarr_preferences)
        movie_id = None
        
        for existing_movie in existing_movies:
            if existing_movie.get('tmdbId') == tmdb_id:
                movie_id = existing_movie.get('id')
                break
        
        # If not in Radarr, add it
        if not movie_id and lookup_results:
            # Get the root folder path
            root_folder_response = requests.get(f"{radarr_url}/api/v3/rootfolder", headers=headers)
            
            if not root_folder_response.ok or not root_folder_response.json():
                return jsonify({"success": False, "message": "Failed to get root folders from Radarr"}), 500
            
            root_folder = root_folder_response.json()[0].get('path')
            
            # Get quality profiles
            profile_response = requests.get(f"{radarr_url}/api/v3/qualityprofile", headers=headers)
            
            if not profile_response.ok or not profile_response.json():
                return jsonify({"success": False, "message": "Failed to get quality profiles from Radarr"}), 500
            
            # Look for the preferred profile
            quality_profile_id = None
            profiles = profile_response.json()
            
            # If 'Any' is specified, use the first profile
            if preferred_profile == 'Any':
                if profiles:
                    quality_profile_id = profiles[0].get('id')
            else:
                # Try to find the named profile
                for profile in profiles:
                    if profile.get('name') == preferred_profile:
                        quality_profile_id = profile.get('id')
                        break
            
            # Fallback to first profile if preferred not found
            if not quality_profile_id and profiles:
                quality_profile_id = profiles[0].get('id')
            
            if not quality_profile_id:
                return jsonify({"success": False, "message": "No quality profiles available in Radarr"}), 500
            
            # Prepare movie for adding
            movie_to_add = lookup_results
            movie_to_add['rootFolderPath'] = root_folder
            movie_to_add['qualityProfileId'] = quality_profile_id
            movie_to_add['monitored'] = True
            movie_to_add['addOptions'] = {
                'searchForMovie': True
            }
                        
            # Add to Radarr
            add_response = requests.post(
                f"{radarr_url}/api/v3/movie", 
                headers=headers,
                json=movie_to_add
            )
            
            if not add_response.ok:
                return jsonify({"success": False, "message": f"Failed to add movie to Radarr: {add_response.text}"}), 500
            
            movie_id = add_response.json().get('id')
            
            return jsonify({"success": True, "message": f"Successfully added movie '{title}' to Radarr"})
        
        elif movie_id:
            # Movie already exists, just search for it
            search_response = requests.post(
                f"{radarr_url}/api/v3/command",
                headers=headers,
                json={"name": "MoviesSearch", "movieIds": [movie_id]}
            )
            
            if not search_response.ok:
                return jsonify({"success": False, "message": f"Failed to search for movie {title}"}), 500
            
            return jsonify({"success": True, "message": f"Successfully refreshed search for existing movie '{title}'"})
        
        else:
            return jsonify({"success": False, "message": f"Failed to lookup or add movie '{title}'"}), 500
    
    except Exception as e:
        app.logger.error(f"Error requesting movie: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": str(e)}), 500
    
@app.route('/api/process-selected-episodes', methods=['POST'])
def process_selected_episodes_api():
    """Process selected episodes without creating a new request."""
    try:
        data = request.json
        tmdb_id = data.get('tmdbId')
        season_number = data.get('seasonNumber')
        episode_numbers = data.get('episodes', [])
        
        # Detect if this is a solo episode 1
        is_first_episode_only = (
            len(episode_numbers) == 1 and 
            episode_numbers[0] == 1
        )
       
        if not tmdb_id or not season_number or not episode_numbers:
            return jsonify({"success": False, "error": "Missing required parameters"}), 400
        try:
            cleanup_config_rules()
        except Exception as e:
            app.logger.error(f"Error during config rule cleanup: {str(e)}")  
        # Find the series in Sonarr
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
       
        # First find the TVDB ID from the TMDB ID
        details = tmdb_utils.get_external_ids(tmdb_id, 'tv')
        tvdb_id = details.get('tvdb_id')
       
        if not tvdb_id:
            return jsonify({"success": False, "error": "Could not find TVDB ID for this show"}), 400
           
        # Check if series already exists in Sonarr
        series_id = None
        series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
        if series_response.ok:
            existing_series = series_response.json()
            for series in existing_series:
                if series.get('tvdbId') == tvdb_id:
                    series_id = series.get('id')
                    title = series.get('title', 'Unknown Series')
                    current_series = series  # Store the full series details
                    break
        
        if not series_id:
            return jsonify({"success": False, "error": "Show not found in Sonarr"}), 404

        # Determine if we should add to default rule
        add_to_default_rule = (
            is_first_episode_only or  # First episode (S01E01)
            (current_series and modified_episeerr.EPISODES_TAG_ID not in current_series.get('tags', []))  # No episodes tag
        )

        if add_to_default_rule:
            app.logger.info(f"Processing for {title} - Adding to default rule")
            
            config = load_config()
            default_rule_name = config.get('default_rule', 'Default')
            
            # Remove episodes tag if it exists
            if current_series and modified_episeerr.EPISODES_TAG_ID in current_series.get('tags', []):
                updated_tags = [tag for tag in current_series.get('tags', []) if tag != modified_episeerr.EPISODES_TAG_ID]
               
                update_payload = current_series.copy()
                update_payload['tags'] = updated_tags
               
                update_response = requests.put(f"{sonarr_url}/api/v3/series", headers=headers, json=update_payload)
                if update_response.ok:
                    app.logger.info(f"Removed episodes tag from series {title} (ID: {series_id})")
            
            # Add to default rule
            if default_rule_name in config['rules']:
                series_id_str = str(series_id)
                if series_id_str not in config['rules'][default_rule_name]['series']:
                    config['rules'][default_rule_name]['series'].append(series_id_str)
                    save_config(config)
                    app.logger.info(f"Added series {title} to default rule")
        else:
            app.logger.info(f"Series {title} does not meet default rule criteria")

               
        
        # Process the episodes using modified_episeerr
        # Store selected episodes in modified_episeerr's pending_selections
        if str(series_id) not in modified_episeerr.pending_selections:
            modified_episeerr.pending_selections[str(series_id)] = {
                'title': title,
                'season': season_number,
                'episodes': [],
                'selected_episodes': set(episode_numbers)
            }
        else:
            modified_episeerr.pending_selections[str(series_id)]['selected_episodes'] = set(episode_numbers)
        
        # Process the episodes using episeerr
        success = modified_episeerr.process_episode_selection(series_id, episode_numbers)
        
        if not success:
            return jsonify({"success": False, "error": "Failed to process episodes"}), 500
            
        # Find and delete all requests for this series
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    filepath = os.path.join(REQUESTS_DIR, filename)
                    with open(filepath, 'r') as f:
                        request_data = json.load(f)
                        if (request_data.get('series_id') == series_id or 
                            request_data.get('tmdb_id') == tmdb_id or 
                            request_data.get('tvdb_id') == tvdb_id):
                            os.remove(filepath)
                            app.logger.info(f"Removed request file: {filename}")
                except Exception as e:
                    app.logger.error(f"Error processing request file {filename}: {str(e)}")
        
        # Save the last processed show
        last_processed = {
            'series_id': series_id,
            'title': title,
            'season': season_number,
            'timestamp': datetime.now().isoformat(),
            'episode_count': len(episode_numbers)
        }
        
        try:
            with open(LAST_PROCESSED_FILE, 'w') as f:
                json.dump(last_processed, f, indent=2)
        except Exception as e:
            app.logger.error(f"Error saving last processed show: {str(e)}")
            
        # Run download check to cancel any unmonitored downloads
        modified_episeerr.check_and_cancel_unmonitored_downloads()
            
        return jsonify({"success": True, "message": f"Processing {len(episode_numbers)} episodes"}), 200
            
    except Exception as e:
        app.logger.error(f"Error processing selected episodes: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route('/select-episodes/<tmdb_id>')
def select_episodes(tmdb_id):
    """Show episode selection UI for a TV show."""
    # Get TV show details
    show_data = jellyseerr_api.get_media_details(tmdb_id, media_type='tv')
    
    if not show_data:
        return render_template('error.html', message="Failed to get show details")
    
    return render_template('episode_selection.html', show=show_data, tmdb_id=tmdb_id)

@app.route('/select-seasons/<tmdb_id>')
def select_seasons(tmdb_id):
    """Show season selection UI for a TV show."""
    # Get TV show details
    show_data = jellyseerr_api.get_media_details(tmdb_id, media_type='tv')
    
    if not show_data:
        return render_template('error.html', message="Failed to get show details")
    
    # Get tag selection parameter (default to 'episodes')
    tag_selection = request.args.get('tag_selection', 'episodes')
    
    return render_template('season_selection.html', 
                         show=show_data, 
                         tmdb_id=tmdb_id,
                         tag_selection=tag_selection)

@app.route('/process-episode-selection', methods=['POST'])
def process_episode_selection():
    """Process selected episodes by monitoring and searching for them"""
    try:
        app.logger.info(f"Form data received: {request.form}")
        request_id = request.form.get('request_id')
        episode_numbers = request.form.getlist('episodes')
        action = request.form.get('action', 'process')  # 'process' or 'cancel'
        
        app.logger.info(f"Processing episodes for request {request_id}, action={action}")
        app.logger.info(f"Selected episodes: {episode_numbers}")
        # Load the request
        request_file = os.path.join(REQUESTS_DIR, f"{request_id}.json")
        if not os.path.exists(request_file):
            app.logger.error(f"Request file not found: {request_file}")
            return jsonify({"error": "Request not found"}), 404
        
        with open(request_file, 'r') as f:
            request_data = json.load(f)
        
        series_id = request_data['series_id']
        series_title = request_data['title']
        tmdb_id = request_data.get('tmdb_id')
        tvdb_id = request_data.get('tvdb_id')
        jellyseerr_request_id = request_data.get('request_id')
        
        # NEW CODE: Find and get paths to ALL related requests
        related_request_files = []
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(REQUESTS_DIR, filename), 'r') as f:
                        other_request = json.load(f)
                        if (other_request.get('series_id') == series_id or 
                            (tmdb_id and other_request.get('tmdb_id') == tmdb_id) or 
                            (tvdb_id and other_request.get('tvdb_id') == tvdb_id)):
                            related_request_files.append(os.path.join(REQUESTS_DIR, filename))
                except Exception as e:
                    app.logger.error(f"Error reading request file {filename}: {str(e)}")
        
        if action == 'cancel':
            app.logger.info(f"Cancelling request {request_id} for {series_title}")
            
            # Delete the Jellyseerr request if available
            if jellyseerr_request_id:
                app.logger.info(f"Deleting Jellyseerr request ID: {jellyseerr_request_id}")
                delete_success = modified_episeerr.delete_overseerr_request(jellyseerr_request_id)
                app.logger.info(f"Jellyseerr delete result: {delete_success}")
            
            # Delete ALL related request files
            for file_path in related_request_files:
                try:
                    os.remove(file_path)
                    app.logger.info(f"Removed related request file: {os.path.basename(file_path)}")
                except Exception as e:
                    app.logger.error(f"Error removing request file: {str(e)}")
            
            # Redirect to the home page with appropriate message
            return redirect(url_for('home', section='requests', 
                          message=f"Request for {series_title} cancelled"))
        
        # Convert episode numbers to integers
        episode_numbers = [int(num) for num in episode_numbers if num.isdigit()]
        
        if not episode_numbers:
            return jsonify({"error": "No valid episodes selected"}), 400
        
        # Store selected episodes in modified_episeerr's pending_selections
        season_number = request_data['season']
        if str(series_id) not in modified_episeerr.pending_selections:
            modified_episeerr.pending_selections[str(series_id)] = {
                'title': series_title,
                'season': season_number,
                'episodes': request_data.get('episodes', []),
                'selected_episodes': set(episode_numbers)
            }
        else:
            modified_episeerr.pending_selections[str(series_id)]['selected_episodes'] = set(episode_numbers)
        
        # Process the episodes using episeerr
        app.logger.info(f"Calling process_episode_selection for series_id={series_id}, episodes={episode_numbers}")
        success = modified_episeerr.process_episode_selection(series_id, episode_numbers)
        app.logger.info(f"Result of process_episode_selection: {success}")
        
        if success:
            # Delete ALL related request files
            for file_path in related_request_files:
                try:
                    os.remove(file_path)
                    app.logger.info(f"Removed related request file: {os.path.basename(file_path)}")
                except Exception as e:
                    app.logger.error(f"Error removing request file: {str(e)}")
            
            # Also check for any related Sonarr request files
            if tmdb_id:
                sonarr_request_file = os.path.join(os.getcwd(), 'data', 'sonarr_requests', f"{tmdb_id}.json")
                if os.path.exists(sonarr_request_file):
                    os.remove(sonarr_request_file)
                    app.logger.info(f"Removed related Sonarr request file for TMDB ID {tmdb_id}")
            
            # Delete the Jellyseerr request if available
            if jellyseerr_request_id:
                modified_episeerr.delete_overseerr_request(jellyseerr_request_id)
            
            # Save the last processed show
            last_processed = {
                'series_id': series_id,
                'title': series_title,
                'season': request_data['season'],
                'timestamp': datetime.now().isoformat(),
                'episode_count': len(episode_numbers)
            }
            
            try:
                with open(LAST_PROCESSED_FILE, 'w') as f:
                    json.dump(last_processed, f, indent=2)
            except Exception as e:
                app.logger.error(f"Error saving last processed show: {str(e)}")

            # Run download check twice to catch any downloads that might be delayed
            app.logger.info("Checking for downloads to cancel after processing request")
            modified_episeerr.check_and_cancel_unmonitored_downloads()
            
            app.logger.info("Running download check again")
            modified_episeerr.check_and_cancel_unmonitored_downloads()
            
            # Redirect to the home page instead of returning JSON
            return redirect(url_for('home', section='requests', 
                           message=f"Processing {len(episode_numbers)} episodes for {series_title}"))
        else:
            return redirect(url_for('home', section='requests', 
                          message=f"Failed to process episodes for {series_title}"))
        
    except Exception as e:
        app.logger.error(f"Error processing episode selection: {str(e)}", exc_info=True)
        return redirect(url_for('home', section='requests', 
                      message="An error occurred while processing episodes"))
    
@app.route('/')
def home():
    config = load_config()
    
    # Load Sonarr data
    sonarr_preferences = sonarr_utils.load_preferences()
    current_series = sonarr_utils.fetch_series_and_episodes(sonarr_preferences)
    upcoming_premieres = sonarr_utils.fetch_upcoming_premieres(sonarr_preferences)
    all_series = sonarr_utils.get_series_list(sonarr_preferences)
    
    # Load Radarr data
    radarr_preferences = radarr_utils.load_preferences()
    recent_movies = radarr_utils.fetch_recent_movies(radarr_preferences)
    upcoming_movies = radarr_utils.fetch_upcoming_movies(radarr_preferences)
    
    # Add type to TV shows for consistent handling
    for series in current_series:
        series['type'] = 'tv'
    
    # Combine and sort watching items by date added
    combined_watching = current_series + recent_movies
    combined_watching.sort(key=lambda x: x.get('dateAdded', datetime.now()), reverse=True)
    # Limit to reasonable number
    combined_watching = combined_watching[:12]
    
    # Add type to TV premieres for consistent handling
    for premiere in upcoming_premieres:
        premiere['type'] = 'tv'
    
    # Combine upcoming premieres and sort by date
    combined_upcoming = upcoming_premieres + upcoming_movies
    # Ensure we have a common sortable date field
    for item in combined_upcoming:
        if 'nextAiring' not in item and 'releaseDate' in item:
            item['nextAiring'] = item['releaseDate']
    
    combined_upcoming.sort(key=lambda x: x.get('nextAiring', ''))
    # Limit to reasonable number
    combined_upcoming = combined_upcoming[:12]
    
    # Get pending requests
    pending_requests = []
    has_pending_requests = False
    try:
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                with open(os.path.join(REQUESTS_DIR, filename), 'r') as f:
                    request_data = json.load(f)
                    pending_requests.append(request_data)
        pending_requests.sort(key=lambda x: x.get('created_at', 0), reverse=True)
        has_pending_requests = len(pending_requests) > 0
    except Exception as e:
        app.logger.error(f"Failed to load pending requests: {str(e)}")
    
    # Get the last processed show
    last_processed_show = None
    try:
        if os.path.exists(LAST_PROCESSED_FILE):
            with open(LAST_PROCESSED_FILE, 'r') as f:
                last_processed = json.load(f)
                
                # Calculate how long ago it was processed
                now = datetime.now()
                processed_time = datetime.fromisoformat(last_processed.get('timestamp', now.isoformat()))
                delta = now - processed_time
                
                # Don't show if it's been more than 15 minutes
                if delta.total_seconds() < 900:  # 15 minutes
                    if delta.seconds >= 60:
                        minutes = delta.seconds // 60
                        time_ago = f"{minutes} minute{'s' if minutes > 1 else ''} ago"
                    else:
                        time_ago = "just now"
                    
                    last_processed['time_ago'] = time_ago
                    last_processed_show = last_processed
    except Exception as e:
        app.logger.error(f"Error loading last processed show: {str(e)}")
    
    # Map series to rules
    rules_mapping = {str(series_id): rule_name for rule_name, details in config['rules'].items() for series_id in details.get('series', [])}
    
    for series in all_series:
        series['assigned_rule'] = rules_mapping.get(str(series['id']), 'None')
    
    # Add the API keys to the config object so they can be used in templates
    config['sonarr_api_key'] = SONARR_API_KEY
    config['radarr_api_key'] = RADARR_API_KEY
    
    # Get Radarr quality profiles
    radarr_profiles = []
    try:
        headers = {'X-Api-Key': radarr_preferences['RADARR_API_KEY']}
        radarr_url = radarr_preferences['RADARR_URL']
        
        profile_response = requests.get(f"{radarr_url}/api/v3/qualityprofile", headers=headers)
        if profile_response.ok:
            radarr_profiles = profile_response.json()
    except Exception as e:
        app.logger.error(f"Error fetching Radarr profiles: {str(e)}")
    
    # Get Sonarr quality profiles
    sonarr_profiles = []
    try:
        headers = {'X-Api-Key': sonarr_preferences['SONARR_API_KEY']}
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        profile_response = requests.get(f"{sonarr_url}/api/v3/qualityprofile", headers=headers)
        if profile_response.ok:
            sonarr_profiles = profile_response.json()
    except Exception as e:
        app.logger.error(f"Error fetching Sonarr profiles: {str(e)}")

    return render_template('index.html', 
                        config=config,
                        current_series=combined_watching,
                        upcoming_premieres=combined_upcoming,
                        all_series=all_series,
                        sonarr_url=SONARR_URL,
                        radarr_url=RADARR_URL,
                        jellyseerr_url=JELLYSEERR_URL,
                        rule=request.args.get('rule', 'full_seasons'),
                        pending_requests=pending_requests,
                        has_pending_requests=has_pending_requests,
                        radarr_profiles=radarr_profiles,
                        sonarr_profiles=sonarr_profiles,
                        last_processed_show=last_processed_show)
                     
@app.route('/api/pending-requests/count')
def pending_requests_count():
    """Get the count of pending requests."""
    try:
        count = 0
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                count += 1
                
        return jsonify({"count": count})
    except Exception as e:
        app.logger.error(f"Error counting pending requests: {str(e)}")
        return jsonify({"count": 0})
@app.route('/api/request/tv', methods=['POST'])
def request_tv_show():
    """Handle TV show requests directly to Sonarr."""
    try:
        data = request.json
        tmdb_id = data.get('tmdbId')
        
        # Setup Sonarr connection
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        # Get root folder
        root_folder_response = requests.get(f"{sonarr_url}/api/v3/rootfolder", headers=headers)
        root_folders = root_folder_response.json()
        if not root_folders:
            return jsonify({"success": False, "error": "No root folders configured in Sonarr"}), 500
        root_folder = root_folders[0]['path']
        
        # Get quality profiles
        profile_response = requests.get(f"{sonarr_url}/api/v3/qualityprofile", headers=headers)
        profiles = profile_response.json()
        if not profiles:
            return jsonify({"success": False, "error": "No quality profiles configured in Sonarr"}), 500
        quality_profile_id = profiles[0]['id']
        
        # Lookup series
        lookup_response = requests.get(
            f"{sonarr_url}/api/v3/series/lookup", 
            headers=headers,
            params={"term": f"tmdb:{tmdb_id}"}
        )
        series_results = lookup_response.json()
        if not series_results:
            return jsonify({"success": False, "error": "Series not found in lookup"}), 500
        
        series = series_results[0]
        
        # Prepare series for adding
        series_to_add = {
            "tvdbId": series['tvdbId'],
            "tmdbId": series['tmdbId'],
            "title": series['title'],
            "titleSlug": series['titleSlug'],
            "rootFolderPath": root_folder,
            "qualityProfileId": quality_profile_id,
            "monitored": True,
            "addOptions": {
                "searchForMissingEpisodes": False
            },
            "tags": [modified_episeerr.EPISODES_TAG_ID] if modified_episeerr.EPISODES_TAG_ID else []
        }
        
        # Add series
        add_response = requests.post(f"{sonarr_url}/api/v3/series", headers=headers, json=series_to_add)
        
        if not add_response.ok:
            return jsonify({"success": False, "error": add_response.text}), 500
        
        return jsonify({"success": True, "message": "Show added to Sonarr"})
        
    except Exception as e:
        app.logger.error(f"Error processing TV request: {str(e)}", exc_info=True)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/process_direct_request', methods=['POST'])
def process_direct_request():
    """Process a direct media request."""
    try:
        request_input = request.form.get('request_input', '').strip()
        media_type = request.form.get('media_type', 'auto')

        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

        if not request_input:
            if is_ajax:
                return jsonify({"success": False, "message": "Request input is required"}), 400
            else:
                return redirect(url_for('home', section='requests', message="Error: Request input is required"))
       
        # Simplified pattern for TV show season: "Show Name S01" or "Show Name Season 1"
        season_pattern = re.compile(r'(.+?)\s+[sS](\d{1,2})$|(.+?)\s+[sS]eason\s*(\d{1,2})$')
        season_match = season_pattern.search(request_input)
        
        if media_type == 'tv' or (media_type == 'auto' and season_match):
            # TV show search
            if season_match:
                show_title = season_match.group(1) or season_match.group(3)
            else:
                show_title = request_input.strip()
            
            # Search for the show on TMDB
            search_results = tmdb_utils.search_tv_shows(show_title)
            results = search_results.get('results', [])
            
            if not results:
                return redirect(url_for('home', section='requests', 
                              message=f"Error: No TV show found with title: {show_title}"))
            
            # Use the first result
            show = results[0]
            tmdb_id = show.get('id')
            show_title = show.get('name')
            
            # Setup Sonarr connection
            sonarr_preferences = sonarr_utils.load_preferences()
            headers = {
                'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
                'Content-Type': 'application/json'
            }
            sonarr_url = sonarr_preferences['SONARR_URL']
            
            # Get root folder
            root_folder_response = requests.get(f"{sonarr_url}/api/v3/rootfolder", headers=headers)
            root_folders = root_folder_response.json()
            if not root_folders:
                return redirect(url_for('home', section='requests', 
                              message="Error: No root folders configured in Sonarr"))
            root_folder = root_folders[0]['path']
            
            # Get quality profiles
            profile_response = requests.get(f"{sonarr_url}/api/v3/qualityprofile", headers=headers)
            profiles = profile_response.json()
            if not profiles:
                return redirect(url_for('home', section='requests', 
                              message="Error: No quality profiles configured in Sonarr"))
            quality_profile_id = profiles[0]['id']
            
            # Look up series details
            lookup_response = requests.get(
                f"{sonarr_url}/api/v3/series/lookup", 
                headers=headers,
                params={"term": f"tmdb:{tmdb_id}"}
            )
            series_results = lookup_response.json()
            
            if not series_results:
                return redirect(url_for('home', section='requests', 
                              message=f"Error: Failed to find series in Sonarr lookup"))
            
            series = series_results[0]
            
            # Prepare series for adding
            series_to_add = {
                "tvdbId": series['tvdbId'],
                "tmdbId": series['tmdbId'],
                "title": series['title'],
                "titleSlug": series['titleSlug'],
                "rootFolderPath": root_folder,
                "qualityProfileId": quality_profile_id,
                "monitored": True,
                "addOptions": {
                    "searchForMissingEpisodes": False
                },
                "tags": [modified_episeerr.EPISODES_TAG_ID] if modified_episeerr.EPISODES_TAG_ID else []
            }
            
            # Add series
            add_response = requests.post(f"{sonarr_url}/api/v3/series", headers=headers, json=series_to_add)
            
            if not add_response.ok:
                return redirect(url_for('home', section='requests', 
                              message=f"Error: Failed to add series to Sonarr: {add_response.text}"))
            
            return redirect(url_for('home', section='requests', 
                          message=f"Added '{show_title}' to Sonarr"))
        
        if is_ajax:
            return jsonify({"success": True, "message": f"Added '{show_title}' to Sonarr"})
        else:
            return redirect(url_for('home', section='requests', message=f"Added '{show_title}' to Sonarr"))
           
    except Exception as e:
        app.logger.error(f"Error processing direct request: {str(e)}", exc_info=True)
        if is_ajax:
            return jsonify({"success": False, "message": str(e)}), 500
        else:
            return redirect(url_for('home', section='requests', message=f"Error: {str(e)}"))

def cleanup_config_rules():
    """Remove series from rules that no longer exist in Sonarr."""
    try:
        config = load_config()
        
        # Load Sonarr preferences
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
        # Fetch all series from Sonarr
        series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
        
        if not series_response.ok:
            app.logger.error("Failed to fetch series from Sonarr during config cleanup")
            return
        
        # Get set of existing series IDs as strings
        existing_series_ids = set(str(series['id']) for series in series_response.json())
        
        # Iterate through all rules
        for rule_name, rule_details in config['rules'].items():
            # Filter out series IDs that no longer exist in Sonarr
            original_series_count = len(rule_details['series'])
            rule_details['series'] = [
                series_id for series_id in rule_details['series'] 
                if series_id in existing_series_ids
            ]
            
            # Log if any series were removed
            if len(rule_details['series']) != original_series_count:
                app.logger.info(f"Cleaned up rule '{rule_name}': Removed {original_series_count - len(rule_details['series'])} non-existent series")
        
        # Save the updated configuration
        save_config(config)
        app.logger.info("Completed configuration rules cleanup")
    
    except Exception as e:
        app.logger.error(f"Error during config rules cleanup: {str(e)}", exc_info=True)

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

        # Check if any of the tags match the 'episodes' label
        has_episodes_tag = any(
        str(tag).lower() == 'episodes'
        for tag in series_tags
        )
        
        # If no episodes tag, just add show to default rule and exit
        if not has_episodes_tag:
            app.logger.info(f"Series {series_title} has no episodes tag, adding to default rule")
            
            # Add to default rule
            config = load_config()
            default_rule_name = config.get('default_rule', 'Default')
            
            if default_rule_name in config['rules']:
                series_id_str = str(series_id)
                
                # Add to default rule if not already in a rule
                if 'series' not in config['rules'][default_rule_name]:
                    config['rules'][default_rule_name]['series'] = []
                
                if series_id_str not in config['rules'][default_rule_name]['series']:
                    config['rules'][default_rule_name]['series'].append(series_id_str)
                    save_config(config)
                    app.logger.info(f"Added series {series_title} (ID: {series_id}) to default rule")
            
            return jsonify({
                "status": "success",
                "message": "Series added to default rule"
            }), 200
        
        # If it has episodes tag, proceed with full episode selection flow
        app.logger.info(f"Series {series_title} has episodes tag, proceeding with episode selection flow")
        
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
                            
                            # Debug log to check if it's a pilot request
                            is_pilot = existing_request.get('pilot', False)
                            app.logger.info(f"Is this a pilot request? {is_pilot}, type: {type(is_pilot)}")
                            app.logger.info(f"Full request data: {json.dumps(existing_request)}")
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
        
        # Ensure we have a TMDB ID for the UI
        if not tmdb_id:
            try:
                # Try to get TMDB ID from TVDB ID
                find_endpoint = f"find/tvdb_{tvdb_id}"
                params = {'external_source': 'tvdb_id'}
                
                details = tmdb_utils.get_tmdb_endpoint(find_endpoint, params)
                
                if details and 'tv_results' in details and details['tv_results']:
                    tmdb_id = details['tv_results'][0]['id']
                else:
                    search_results = tmdb_utils.search_tv_shows(series_title)
                    if search_results.get('results'):
                        tmdb_id = search_results['results'][0]['id']
            except Exception as e:
                app.logger.error(f"Error finding TMDB ID: {str(e)}")
        
        # Setup Sonarr connection
        sonarr_preferences = sonarr_utils.load_preferences()
        headers = {
            'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
            'Content-Type': 'application/json'
        }
        sonarr_url = sonarr_preferences['SONARR_URL']
        
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
        
        # 3. Create a new season selection request
        request_id = f"sonarr-webhook-{series_id}-{int(time.time())}"
        
        pending_request = {
            "id": request_id,
            "series_id": series_id,
            "title": series_title,
            "needs_season_selection": True,
            "tmdb_id": tmdb_id,
            "tvdb_id": tvdb_id,
            "source": "sonarr",
            "source_name": "Sonarr Requires Selection",
            "needs_attention": True,
            "created_at": int(time.time())
        }
        
        os.makedirs(REQUESTS_DIR, exist_ok=True)

        try:
            cleanup_config_rules()
        except Exception as e:
            app.logger.error(f"Error during config rule cleanup: {str(e)}")

        with open(os.path.join(REQUESTS_DIR, f"{request_id}.json"), 'w') as f:
            json.dump(pending_request, f)
        
        app.logger.info(f"Created season selection request for {series_title}")
        
        return jsonify({
            "status": "success",
            "message": "Series requires season selection"
        }), 200
            
    except Exception as e:
        app.logger.error(f"Error processing Sonarr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
    
@app.route('/api/new-requests-since', methods=['GET'])
def check_new_requests_since():
    # Get the timestamp from the query parameter
    since_timestamp = request.args.get('since', 0, type=int)
    
    new_requests = []
    for filename in os.listdir(REQUESTS_DIR):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(REQUESTS_DIR, filename), 'r') as f:
                    request_data = json.load(f)
                    created_at = request_data.get('created_at', 0)
                    
                    if created_at > since_timestamp:
                        new_requests.append({
                            'id': request_data.get('id'),
                            'title': request_data.get('title'),
                            'created_at': created_at
                        })
            except Exception as e:
                app.logger.error(f"Error reading request file {filename}: {str(e)}")
    
    return jsonify({
        "hasNewRequests": len(new_requests) > 0,
        "newRequests": new_requests,
        "latestTimestamp": int(time.time()) if new_requests else since_timestamp
    })    
@app.route('/seerr-webhook', methods=['POST'])
def process_seerr_webhook():
    """Handle incoming Jellyseerr webhooks - cancel requests with episodes tag."""
    try:
        app.logger.info("Received webhook from Jellyseerr")
        json_data = request.json
        
        # Debug log the webhook data
        app.logger.info(f"Jellyseerr webhook data: {json.dumps(json_data)}")
        
        # Get the request ID if available
        request_id = json_data.get('request', {}).get('request_id') or json_data.get('request', {}).get('id')
        
        # Check if it's a TV show request - we only want to cancel TV show requests
        media_type = json_data.get('media', {}).get('media_type')
        if media_type != 'tv':
            app.logger.info(f"Request is not a TV show request. Skipping cancellation.")
            return jsonify({"status": "success"}), 200
        
        # Look ONLY for an exact 'episodes' tag
        has_episodes_tag = any(
            extra.get('name', '').lower() == 'episodes' 
            for extra in json_data.get('extra', [])
        )
        
        # Only proceed if explicitly tagged with 'episodes'
        if has_episodes_tag and request_id:
            app.logger.info(f"Request {request_id} has episodes tag")
            
            def delayed_cancel():
                # Add a delay to ensure Sonarr has time to process the request
                time.sleep(5)  # 5-second delay
                app.logger.info(f"Canceling Jellyseerr request {request_id} with episodes tag")
                result = modified_episeerr.delete_overseerr_request(request_id)
                app.logger.info(f"Cancellation result: {result}")
            
            # Use threading to run the cancellation in the background
            threading.Thread(target=delayed_cancel, daemon=True).start()
            
            app.logger.info(f"Request {request_id} has episodes tag. Cancellation queued.")
        else:
            app.logger.info("Webhook received without explicit episodes tag. Skipping cancellation.")
        
        return jsonify({"status": "success"}), 200
    except Exception as e:
        app.logger.error(f"Error processing Jellyseerr webhook: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": str(e)}), 500
   
@app.route('/webhook', methods=['POST'])
def handle_server_webhook():
    app.logger.info("Received POST request from Tautulli")
    data = request.json
    if data:
        app.logger.info(f"Webhook received with data: {data}")
        try:
            temp_dir = os.path.join(os.getcwd(), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            with open(os.path.join(temp_dir, 'data_from_tautulli.json'), 'w') as f:
                json.dump(data, f)
            app.logger.info("Data successfully written to data_from_tautulli.json")
            result = subprocess.run(["python3", os.path.join(os.getcwd(), "servertosonarr.py")], capture_output=True, text=True)
            if result.stderr:
                app.logger.error("Errors from servertosonarr.py: " + result.stderr)
        except Exception as e:
            app.logger.error(f"Failed to handle data or run script: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 500
        return jsonify({'status': 'success', 'message': 'Script triggered successfully'}), 200
    else:
        return jsonify({'status': 'error', 'message': 'No data received'}), 400

@app.route('/update-settings', methods=['POST'])
def update_settings():
    config = load_config()
    
    rule_name = request.form.get('rule_name')
    if rule_name == 'add_new':
        rule_name = request.form.get('new_rule_name')
        if not rule_name:
            return redirect(url_for('home', section='settings', message="New rule name is required."))
    
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
    return redirect(url_for('home', section='settings', message="Settings updated successfully"))

@app.route('/delete_rule', methods=['POST'])
def delete_rule():
    config = load_config()
    rule_name = request.form.get('rule_name')
    if rule_name and rule_name in config['rules']:
        del config['rules'][rule_name]
        save_config(config)
        return redirect(url_for('home', section='settings', message=f"Rule '{rule_name}' deleted successfully."))
    else:
        return redirect(url_for('home', section='settings', message=f"Rule '{rule_name}' not found."))

@app.route('/assign_rules', methods=['POST'])
def assign_rules():
    config = load_config()
    rule_name = request.form.get('assign_rule_name')
    submitted_series_ids = set(request.form.getlist('series_ids'))
    
    # For series being assigned to a rule, remove the episodes tag
    sonarr_preferences = sonarr_utils.load_preferences()
    headers = {
        'X-Api-Key': sonarr_preferences['SONARR_API_KEY'],
        'Content-Type': 'application/json'
    }
    sonarr_url = sonarr_preferences['SONARR_URL']
   
    # Get all series first
    series_response = requests.get(f"{sonarr_url}/api/v3/series", headers=headers)
    if series_response.ok:
        series_list = series_response.json()
        for series in series_list:
            # If this series is being assigned to ANY rule and has the episodes tag
            if str(series['id']) in submitted_series_ids and modified_episeerr.EPISODES_TAG_ID in series.get('tags', []):
                # Remove the episodes tag
                updated_tags = [tag for tag in series.get('tags', []) if tag != modified_episeerr.EPISODES_TAG_ID]
                series['tags'] = updated_tags
               
                # Update the series
                update_response = requests.put(f"{sonarr_url}/api/v3/series", headers=headers, json=series)
                if update_response.ok:
                    app.logger.info(f"Removed episodes tag from series {series['title']} (ID: {series['id']})")
                else:
                    app.logger.error(f"Failed to remove episodes tag from series {series['id']}")

    if rule_name == 'None':
        # Remove series from any rule
        for key, details in config['rules'].items():
            details['series'] = [sid for sid in details.get('series', []) if sid not in submitted_series_ids]
    else:
        # Update the rule's series list to include only those submitted
        if rule_name in config['rules']:
            current_series = set(config['rules'][rule_name]['series'])
            updated_series = current_series.union(submitted_series_ids)
            config['rules'][rule_name]['series'] = list(updated_series)
        
        # Update other rules to remove the series if it's no longer assigned there
        for key, details in config['rules'].items():
            if key != rule_name:
                # Preserve series not submitted in other rules
                details['series'] = [sid for sid in details.get('series', []) if sid not in submitted_series_ids]
    
    save_config(config)
    return redirect(url_for('home', section='settings', message="Rules updated successfully."))

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
    return redirect(url_for('home', section='settings', message="Rules updated successfully."))

@app.route('/update_profile_settings', methods=['POST'])
def update_profile_settings():
    """Update profile settings."""
    try:
        config = load_config()
        
        # Ensure preferences section exists
        if 'preferences' not in config:
            config['preferences'] = {}
        
        # Update preferences
        config['preferences']['radarr_quality_profile'] = request.form.get('radarr_quality_profile', 'Any')
        config['preferences']['sonarr_quality_profile'] = request.form.get('sonarr_quality_profile', 'Any')
        
        save_config(config)
        
        return redirect(url_for('home', section='settings', subsection='profile_settings', 
                      message="Profile settings updated successfully"))
    except Exception as e:
        app.logger.error(f"Error updating profile settings: {str(e)}")
        return redirect(url_for('home', section='settings', subsection='profile_settings', 
                      message=f"Error: {str(e)}"))
    
@app.route('/cleanup-requests', methods=['GET'])
def cleanup_requests_route():
    """Route to manually clean up invalid requests"""
    count = cleanup_invalid_requests()
    return jsonify({"message": f"Cleaned up {count} invalid requests"}), 200

def cleanup_invalid_requests():
    """Remove invalid or corrupted request files"""
    try:
        count = 0
        for filename in os.listdir(REQUESTS_DIR):
            if filename.endswith('.json'):
                filepath = os.path.join(REQUESTS_DIR, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        
                    # Check for invalid requests
                    if 'episodes' in data and not data['episodes']:
                        # Empty episodes array
                        os.remove(filepath)
                        app.logger.info(f"Removed request with empty episodes: {filename}")
                        count += 1
                        
                    if data.get('title') == 'Unknown Show':
                        # Unknown show with no useful information
                        os.remove(filepath)
                        app.logger.info(f"Removed request for Unknown Show: {filename}")
                        count += 1
                        
                except (json.JSONDecodeError, KeyError) as e:
                    # Invalid JSON or missing required fields
                    os.remove(filepath)
                    app.logger.info(f"Removed invalid request file: {filename}")
                    count += 1
                    
        return count
    except Exception as e:
        app.logger.error(f"Error cleaning up invalid requests: {str(e)}")
        return 0

def initialize_episeerr():
    """Initialize episode tag and check for unmonitored downloads."""
    modified_episeerr.create_episode_tag()
    app.logger.info("Created episode tag")
    
    # Do an initial check for unmonitored downloads
    try:
        modified_episeerr.check_and_cancel_unmonitored_downloads()
    except Exception as e:
        app.logger.error(f"Error in initial download check: {str(e)}")

if __name__ == '__main__':
    # Clean up invalid requests
    cleanup_invalid_requests()
    # Call config rules cleanup at startup
    cleanup_config_rules()
    # Call initialization function before running the app
    initialize_episeerr()
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=5002, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
