"""
Episeerr Dashboard Module
Unified media dashboard with calendar, stats, and activity feed
"""

from flask import Blueprint, render_template, jsonify
import requests
import os
import json
from datetime import datetime, timedelta
import logging

dashboard_bp = Blueprint('dashboard', __name__)
logger = logging.getLogger(__name__)

# Environment variables
SONARR_URL = os.getenv('SONARR_URL')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')
SABNZBD_URL = os.getenv('SABNZBD_URL')
SABNZBD_API_KEY = os.getenv('SABNZBD_API_KEY')
JELLYFIN_URL = os.getenv('JELLYFIN_URL')
JELLYFIN_API_KEY = os.getenv('JELLYFIN_API_KEY')
TAUTULLI_URL = os.getenv('TAUTULLI_URL')
TAUTULLI_API_KEY = os.getenv('TAUTULLI_API_KEY')


@dashboard_bp.route('/dashboard')
def dashboard():
    """Main dashboard page"""
    return render_template('dashboard.html')


@dashboard_bp.route('/api/dashboard/calendar')
def calendar_data():
    """Get episodes for rolling 7 days: recent downloads + upcoming"""
    try:
        from datetime import datetime, timedelta
        import os
        import json
        
        today = datetime.now()
        
        # Calculate rolling 7-day window (past 7 days + next 7 days)
        week_ago = today - timedelta(days=7)
        week_ahead = today + timedelta(days=7)
        
        start_date = week_ago.strftime('%Y-%m-%d')
        end_date = week_ahead.strftime('%Y-%m-%d')
        
        logger.info(f"Calendar range: {start_date} to {end_date}")
        
        # ──────────────────────────────────────────────────────
        # 1. GET UPCOMING FROM SONARR (next 7 days)
        # ──────────────────────────────────────────────────────
        headers = {'X-Api-Key': SONARR_API_KEY}
        calendar_url = f"{SONARR_URL}/api/v3/calendar"
        params = {
            'start': today.strftime('%Y-%m-%d'),
            'end': end_date,
            'includeSeries': 'true',
            'includeUnmonitored': 'false'
        }
        
        response = requests.get(calendar_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        upcoming_episodes = response.json()
        
        logger.info(f"Sonarr returned {len(upcoming_episodes)} upcoming episodes")
        
        # ──────────────────────────────────────────────────────
        # 2. GET RECENT DOWNLOADS (last 7 days)
        # ──────────────────────────────────────────────────────
        recent_downloads = []
        downloads_file = os.path.join(os.getcwd(), 'data', 'recent_downloads.json')
        
        if os.path.exists(downloads_file):
            try:
                with open(downloads_file, 'r') as f:
                    recent_downloads = json.load(f)
                logger.info(f"Loaded {len(recent_downloads)} recent downloads")
            except Exception as e:
                logger.error(f"Error loading downloads: {e}")
        
        # ──────────────────────────────────────────────────────
        # 3. LOAD EPISEERR CONFIG FOR RULES
        # ──────────────────────────────────────────────────────
        from episeerr import load_config
        config = load_config()
        
        series_rules = {}
        for rule_name, rule_data in config.get('rules', {}).items():
            for series_id in rule_data.get('series', {}).keys():
                series_rules[int(series_id)] = rule_name
        
        # ──────────────────────────────────────────────────────
        # 4. PROCESS UPCOMING EPISODES
        # ──────────────────────────────────────────────────────
        calendar_events = []
        now = datetime.now()
        
        for ep in upcoming_episodes:
            series_id = ep.get('seriesId')
            has_rule = series_id in series_rules
            rule_name = series_rules.get(series_id)
            
            has_file = ep.get('hasFile', False)
            monitored = ep.get('monitored', False)
            
            air_date_str = ep.get('airDateUtc', '')
            has_aired = False
            if air_date_str:
                try:
                    air_date = datetime.fromisoformat(air_date_str.replace('Z', ''))
                    has_aired = air_date < now
                except:
                    has_aired = False
            
            # Check if recently grabbed
            recently_grabbed = False
            for dl in recent_downloads:
                if (dl.get('series_id') == series_id and 
                    dl.get('season') == ep.get('seasonNumber') and 
                    dl.get('episode') == ep.get('episodeNumber')):
                    recently_grabbed = True
                    break
            
            if recently_grabbed:
                status = 'recently_downloaded'
                color = 'green'
            elif has_file:
                status = 'downloaded'
                color = 'gray'
            elif not monitored:
                status = 'unmonitored'
                color = 'muted'
            elif has_rule:
                status = 'has_rule'
                color = 'green'
            elif has_aired and not has_file:
                status = 'not_grabbed'
                color = 'blue'
            else:
                status = 'no_rule'
                color = 'yellow'
            
            calendar_events.append({
                'id': ep.get('id'),
                'series_id': series_id,
                'series_title': ep.get('series', {}).get('title', 'Unknown'),
                'episode_title': ep.get('title', 'TBA'),
                'season': ep.get('seasonNumber'),
                'episode': ep.get('episodeNumber'),
                'air_date': ep.get('airDateUtc'),
                'has_file': has_file,
                'monitored': monitored,
                'has_rule': has_rule,
                'rule_name': rule_name,
                'status': status,
                'color': color,
                'recently_grabbed': recently_grabbed,
                'overview': ep.get('overview', '')
            })
        
        # ──────────────────────────────────────────────────────
        # 5. ADD DOWNLOADED EPISODES THAT AREN'T IN CALENDAR
        # ──────────────────────────────────────────────────────
        # Create set of episodes already in calendar
        calendar_episode_keys = {
            (e['series_id'], e['season'], e['episode']) 
            for e in calendar_events
        }
        
        # Get full episode details from Sonarr for downloaded episodes
        for dl in recent_downloads:
            dl_key = (dl['series_id'], dl['season'], dl['episode'])
            
            # Skip if already in calendar
            if dl_key in calendar_episode_keys:
                continue
            
            # Fetch episode details from Sonarr
            try:
                series_response = requests.get(
                    f"{SONARR_URL}/api/v3/series/{dl['series_id']}",
                    headers=headers,
                    timeout=5
                )
                
                if series_response.ok:
                    series_data = series_response.json()
                    
                    # Get episode details
                    ep_response = requests.get(
                        f"{SONARR_URL}/api/v3/episode?seriesId={dl['series_id']}",
                        headers=headers,
                        timeout=5
                    )
                    
                    if ep_response.ok:
                        episodes = ep_response.json()
                        matching_ep = next(
                            (e for e in episodes 
                             if e['seasonNumber'] == dl['season'] and 
                                e['episodeNumber'] == dl['episode']),
                            None
                        )
                        
                        if matching_ep:
                            has_rule = dl['series_id'] in series_rules
                            
                            calendar_events.append({
                                'id': matching_ep.get('id'),
                                'series_id': dl['series_id'],
                                'series_title': dl['series_title'],
                                'episode_title': dl.get('episode_title', 'TBA'),
                                'season': dl['season'],
                                'episode': dl['episode'],
                                'air_date': matching_ep.get('airDateUtc'),
                                'has_file': True,
                                'monitored': matching_ep.get('monitored', False),
                                'has_rule': has_rule,
                                'rule_name': series_rules.get(dl['series_id']),
                                'status': 'recently_downloaded',
                                'color': 'green',
                                'recently_grabbed': True,
                                'overview': matching_ep.get('overview', '')
                            })
                            
                            logger.info(f"Added downloaded episode: {dl['series_title']} S{dl['season']}E{dl['episode']}")
            except Exception as e:
                logger.error(f"Error fetching details for downloaded episode: {e}")
        
        return jsonify({
            'success': True,
            'events': calendar_events,
            'recent_downloads_count': len(recent_downloads),
            'total': len(calendar_events)
        })
        
    except Exception as e:
        logger.error(f"Error fetching calendar data: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'events': []
        }), 500



@dashboard_bp.route('/api/dashboard/stats')
def dashboard_stats():
    """Get overall statistics for dashboard"""
    try:
        stats = {}
        
        # Sonarr stats
        if SONARR_URL and SONARR_API_KEY:
            headers = {'X-Api-Key': SONARR_API_KEY}
            
            # Get series count
            series_response = requests.get(f"{SONARR_URL}/api/v3/series", headers=headers, timeout=10)
            series_data = series_response.json()
            
            # Get queue
            queue_response = requests.get(f"{SONARR_URL}/api/v3/queue", headers=headers, timeout=10)
            queue_data = queue_response.json()
            
            total_episodes = sum(s.get('statistics', {}).get('episodeFileCount', 0) for s in series_data)
            total_size = sum(s.get('statistics', {}).get('sizeOnDisk', 0) for s in series_data)
            
            stats['sonarr'] = {
                'series_count': len(series_data),
                'episode_count': total_episodes,
                'size_on_disk': total_size,
                'size_gb': round(total_size / (1024**3), 2),
                'queue_count': queue_data.get('totalRecords', 0)
            }
        
        # SABnzbd stats
        if SABNZBD_URL and SABNZBD_API_KEY:
            sab_response = requests.get(
                f"{SABNZBD_URL}/api",
                params={
                    'mode': 'queue',
                    'output': 'json',
                    'apikey': SABNZBD_API_KEY
                },
                timeout=10
            )
            sab_data = sab_response.json()
            
            queue = sab_data.get('queue', {})
            stats['sabnzbd'] = {
                'queue_count': queue.get('noofslots', 0),
                'speed': queue.get('speed', '0 B/s'),
                'size_left': queue.get('sizeleft', '0 B'),
                'paused': queue.get('paused', False)
            }
        
        # Episeerr stats
        from episeerr import load_config
        config = load_config()
        
        total_series_in_rules = 0
        for rule_data in config.get('rules', {}).values():
            total_series_in_rules += len(rule_data.get('series', {}))
        
        stats['episeerr'] = {
            'rule_count': len(config.get('rules', {})),
            'series_managed': total_series_in_rules
        }
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        logger.error(f"Error fetching dashboard stats: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'stats': {}
        }), 500


@dashboard_bp.route('/api/dashboard/activity')
def activity_feed():
    """Get most recent activity from each service"""
    try:
        services = []
        
        # Use Episeerr's own activity tracking
        activity_dir = os.path.join(os.getcwd(), 'data', 'activity')
        
        # Last search (from searches.json)
        try:
            searches_file = os.path.join(activity_dir, 'searches.json')
            if os.path.exists(searches_file):
                with open(searches_file, 'r') as f:
                    searches = json.load(f)
                    if searches:
                        last_search = searches[0]  # Most recent
                        services.append({
                            'service': 'Sonarr',
                            'icon': 'fa-tv',
                            'color': 'primary',
                            'action': 'Searched',
                            'details': f"{last_search['series_title']} S{last_search['season']}E{last_search['episode']}",
                            'timestamp': datetime.fromtimestamp(last_search['timestamp']).isoformat(),
                            'action_icon': 'fa-search'
                        })
                        logger.info(f"Added search: {last_search['series_title']}")
        except Exception as e:
            logger.error(f"Error reading searches.json: {e}")
        
        # Last watched (from watched.json)
        try:
            watched_file = os.path.join(activity_dir, 'watched.json')
            if os.path.exists(watched_file):
                with open(watched_file, 'r') as f:
                    watched = json.load(f)
                    if watched:
                        last_watched = watched[0]  # Most recent
                        user = last_watched.get('user', 'Unknown')
                        services.append({
                            'service': 'Jellyfin/Tautulli',
                            'icon': 'fa-eye',
                            'color': 'info',
                            'action': 'Watched',
                            'details': f"{last_watched['series_title']} S{last_watched['season']}E{last_watched['episode']} by {user}",
                            'timestamp': datetime.fromtimestamp(last_watched['timestamp']).isoformat(),
                            'action_icon': 'fa-play'
                        })
                        logger.info(f"Added watch: {last_watched['series_title']}")
        except Exception as e:
            logger.error(f"Error reading watched.json: {e}")
        
        # Last request (from last_request.json)
        try:
            request_file = os.path.join(activity_dir, 'last_request.json')
            if os.path.exists(request_file):
                with open(request_file, 'r') as f:
                    last_req = json.load(f)
                    if last_req:
                        services.append({
                            'service': 'Jellyseerr/Overseerr',
                            'icon': 'fa-film',
                            'color': 'warning',
                            'action': 'Requested',
                            'details': f"{last_req['title']} (Season {last_req.get('requested_seasons', '?')})",
                            'timestamp': datetime.fromtimestamp(last_req['timestamp']).isoformat(),
                            'action_icon': 'fa-plus-circle'
                        })
                        logger.info(f"Added request: {last_req['title']}")
        except Exception as e:
            logger.error(f"Error reading last_request.json: {e}")
        
        # Cleanup log (from logs/cleanup.log) - get last few lines
        try:
            cleanup_log = os.path.join(os.getcwd(), 'logs', 'cleanup.log')
            if os.path.exists(cleanup_log):
                with open(cleanup_log, 'r') as f:
                    lines = f.readlines()
                    # Look for recent deletions
                    for line in reversed(lines[-50:]):  # Last 50 lines
                        if 'Deleted' in line and 'episodes' in line:
                            # Parse log line like: "2025-01-25 - Deleted 3 episodes from Show Name"
                            try:
                                parts = line.strip().split(' - ', 1)
                                if len(parts) == 2:
                                    timestamp_str, message = parts
                                    log_time = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                                    
                                    services.append({
                                        'service': 'Episeerr',
                                        'icon': 'fa-cog',
                                        'color': 'danger',
                                        'action': 'Cleanup',
                                        'details': message,
                                        'timestamp': log_time.isoformat(),
                                        'action_icon': 'fa-trash'
                                    })
                                    logger.info(f"Added cleanup: {message}")
                                    break  # Only get most recent
                            except:
                                continue
        except Exception as e:
            logger.error(f"Error reading cleanup.log: {e}")
        
        # Episeerr - Show pending deletions or recent activity
        try:
            import pending_deletions
            deletion_summary = pending_deletions.get_pending_deletions_summary()
            
            # Only show if there are pending deletions
            if deletion_summary and deletion_summary.get('total_episodes', 0) > 0:
                services.append({
                    'service': 'Episeerr',
                    'icon': 'fa-cog',
                    'color': 'purple',
                    'action': 'Pending Approval',
                    'details': f"{deletion_summary['total_episodes']} episodes ready for deletion ({deletion_summary['total_size_gb']} GB)",
                    'timestamp': datetime.now().isoformat(),
                    'action_icon': 'fa-exclamation-circle'
                })
                logger.info(f"Episeerr pending: {deletion_summary['total_episodes']} episodes")
        except Exception as e:
            logger.error(f"Error getting Episeerr activity: {e}")
        
        # Sort by timestamp (most recent first)
        services.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        logger.info(f"Returning {len(services)} service activities")
        
        return jsonify({
            'success': True,
            'services': services
        })
        
    except Exception as e:
        logger.error(f"Error fetching activity feed: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'services': []
        }), 500
