"""
Pending Deletions Management System - v2.9.0
Handles queuing, approval, and rejection of episode deletions

Changes in v2.9.0:
- Added queue_deletion() wrapper for simpler API
- Batched deletions by series for efficiency (one delete command per series instead of per episode)
"""
import os
import json
import logging
from datetime import datetime, timedelta
from threading import Lock
from collections import defaultdict

from logging_config import main_logger as logger

# File paths
PENDING_DELETIONS_FILE = os.path.join(os.getcwd(), 'data', 'pending_deletions.json')
REJECTION_CACHE_FILE = os.path.join(os.getcwd(), 'data', 'deletion_rejections.json')
os.makedirs(os.path.dirname(PENDING_DELETIONS_FILE), exist_ok=True)

# Thread safety
pending_lock = Lock()
rejection_lock = Lock()

# Rejection cache duration (days)
REJECTION_CACHE_DAYS = 30


def load_pending_deletions():
    """Load pending deletions from file"""
    try:
        if os.path.exists(PENDING_DELETIONS_FILE):
            with open(PENDING_DELETIONS_FILE, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Error loading pending deletions: {e}")
        return []


def save_pending_deletions(pending_list):
    """Save pending deletions to file"""
    try:
        with open(PENDING_DELETIONS_FILE, 'w') as f:
            json.dump(pending_list, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving pending deletions: {e}")


def load_rejection_cache():
    """Load rejection cache from file"""
    try:
        if os.path.exists(REJECTION_CACHE_FILE):
            with open(REJECTION_CACHE_FILE, 'r') as f:
                cache = json.load(f)
                # Clean expired entries
                return cleanup_expired_rejections(cache)
        return {}
    except Exception as e:
        logger.error(f"Error loading rejection cache: {e}")
        return {}


def save_rejection_cache(cache):
    """Save rejection cache to file"""
    try:
        with open(REJECTION_CACHE_FILE, 'w') as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving rejection cache: {e}")


def cleanup_expired_rejections(cache):
    """Remove expired rejections from cache"""
    today = datetime.now().strftime('%Y-%m-%d')
    expired = [eid for eid, exp_date in cache.items() if exp_date < today]
    for eid in expired:
        del cache[eid]
    return cache


def is_episode_rejected(episode_id):
    """Check if an episode is in the rejection cache"""
    with rejection_lock:
        cache = load_rejection_cache()
        return str(episode_id) in cache


def queue_deletion(series_id, series_title, season_number, episode_number, episode_id, 
                   episode_file_id, episode_title, file_size, 
                   reason, date_source, date_value, rule_name):
    """
    NEW v2.9.0: Simplified wrapper for queueing deletions
    
    Args:
        series_id: Sonarr series ID
        series_title: Name of the series
        season_number: Season number
        episode_number: Episode number
        episode_id: Sonarr episode ID
        episode_file_id: Sonarr episode file ID
        episode_title: Episode title
        file_size: File size in bytes
        reason: Why this episode is marked for deletion
        date_source: Where the date came from
        date_value: The actual date used for decision
        rule_name: Name of the rule that triggered this
    """
    # Build minimal episode object
    episode = {
        'id': episode_id,
        'seriesId': series_id,
        'seasonNumber': season_number,
        'episodeNumber': episode_number,
        'title': episode_title,
        'series': {'title': series_title},
        'episodeFile': {
            'id': episode_file_id,
            'size': file_size
        }
    }
    
    # Use existing add function
    add_to_pending_deletions(episode, reason, date_source, date_value, rule_name)


def add_to_pending_deletions(episode, reason, date_source, date_value, rule_name):
    """
    Add an episode to pending deletions queue
    
    Args:
        episode: Episode data from Sonarr (or minimal object from queue_deletion)
        reason: Why this episode is marked for deletion (e.g., "Grace Period", "Keep Rule")
        date_source: Where the date came from ("Tautulli" or "Sonarr Air Date")
        date_value: The actual date used for decision
        rule_name: Name of the rule that triggered this
    """
    # Skip if in rejection cache
    if is_episode_rejected(episode['id']):
        logger.debug(f"Skipping episode {episode['id']} - in rejection cache")
        return
    
    with pending_lock:
        pending_list = load_pending_deletions()
        
        series_id = episode['seriesId']
        season_num = episode['seasonNumber']
        episode_id = episode['id']
        
        # Find or create series entry
        series_entry = next((s for s in pending_list if s['series_id'] == series_id), None)
        if not series_entry:
            series_entry = {
                'series_id': series_id,
                'series_title': episode['series']['title'],
                'seasons': {}
            }
            pending_list.append(series_entry)
        
        # Find or create season entry
        season_key = str(season_num)
        if season_key not in series_entry['seasons']:
            series_entry['seasons'][season_key] = {
                'season_number': season_num,
                'episodes': []
            }
        
        # Check if episode already exists
        existing_episode = next(
            (ep for ep in series_entry['seasons'][season_key]['episodes'] if ep['episode_id'] == episode_id),
            None
        )
        
        if existing_episode:
            logger.debug(f"Episode {episode_id} already in pending deletions")
            return
        
        # Add episode
        series_entry['seasons'][season_key]['episodes'].append({
            'episode_id': episode_id,
            'episode_number': episode['episodeNumber'],
            'title': episode.get('title', 'Unknown'),
            'reason': reason,
            'rule_name': rule_name,
            'date_source': date_source,
            'date_value': date_value,
            'file_size_mb': round(episode.get('episodeFile', {}).get('size', 0) / (1024 * 1024), 2),
            'queued_at': datetime.now().isoformat(),
            'episode_data': episode  # Store full episode for actual deletion
        })
        
        save_pending_deletions(pending_list)
        logger.info(f"Added to pending deletions: {episode['series']['title']} S{season_num:02d}E{episode['episodeNumber']:02d} - {reason}")


def get_pending_deletions_summary():
    """Get summary of pending deletions for display"""
    with pending_lock:
        pending_list = load_pending_deletions()
        
        total_episodes = 0
        total_size_mb = 0
        
        for series in pending_list:
            for season_data in series['seasons'].values():
                total_episodes += len(season_data['episodes'])
                total_size_mb += sum(ep['file_size_mb'] for ep in season_data['episodes'])
        
        return {
            'total_series': len(pending_list),
            'total_episodes': total_episodes,
            'total_size_mb': total_size_mb,
            'total_size_gb': round(total_size_mb / 1024, 2),
            'pending_list': pending_list
        }


def approve_deletions(episode_ids, sonarr_delete_func):
    """
    NEW v2.9.0: Approve and execute deletions with BATCHED DELETIONS BY SERIES
    
    Args:
        episode_ids: List of episode IDs to delete
        sonarr_delete_func: Function to call to actually delete episodes
    
    Returns:
        dict with success count and any errors
    """
    with pending_lock:
        pending_list = load_pending_deletions()
        deleted_count = 0
        errors = []
        
        # Group episodes by series for batched deletion
        episodes_by_series = defaultdict(list)
        
        # Find all episodes to delete and group by series
        for series in pending_list:
            series_title = series['series_title']
            for season_data in list(series['seasons'].values()):
                for episode in list(season_data['episodes']):
                    if episode['episode_id'] in episode_ids:
                        episodes_by_series[series_title].append(episode)
        
        # Delete episodes in batches per series (MORE EFFICIENT!)
        for series_title, episodes in episodes_by_series.items():
            try:
                # Collect all episode file IDs for this series
                episode_file_ids = []
                for episode in episodes:
                    episode_data = episode['episode_data']
                    episode_file_id = episode_data.get('episodeFile', {}).get('id')
                    if episode_file_id:
                        episode_file_ids.append(episode_file_id)
                    else:
                        errors.append(f"No file ID for episode {episode['episode_id']}")
                
                if episode_file_ids:
                    # ONE DELETE CALL FOR ALL EPISODES IN THIS SERIES
                    logger.info(f"Deleting {len(episode_file_ids)} episodes from {series_title} in batch")
                    sonarr_delete_func(episode_file_ids, False, series_title)
                    deleted_count += len(episode_file_ids)
                    
                    # Log individual episodes
                    for episode in episodes:
                        episode_data = episode['episode_data']
                        logger.info(f"✓ Deleted: {series_title} S{episode_data['seasonNumber']:02d}E{episode_data['episodeNumber']:02d}")
                    
            except Exception as e:
                error_msg = f"Failed to delete episodes from {series_title}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)
        
        # Remove deleted episodes from pending list
        for series in pending_list:
            for season_key, season_data in list(series['seasons'].items()):
                season_data['episodes'] = [
                    ep for ep in season_data['episodes'] 
                    if ep['episode_id'] not in episode_ids
                ]
                # Remove empty seasons
                if not season_data['episodes']:
                    del series['seasons'][season_key]
        
        # Remove empty series
        pending_list = [s for s in pending_list if s['seasons']]
        
        save_pending_deletions(pending_list)
        
        return {
            'deleted_count': deleted_count,
            'errors': errors
        }


def reject_deletions(episode_ids):
    """
    Reject deletions for specified episodes and add to rejection cache
    
    Args:
        episode_ids: List of episode IDs to reject
    
    Returns:
        int: Number of episodes rejected
    """
    with pending_lock:
        pending_list = load_pending_deletions()
        rejected_count = 0
        
        # Add to rejection cache
        with rejection_lock:
            cache = load_rejection_cache()
            expiry_date = (datetime.now() + timedelta(days=REJECTION_CACHE_DAYS)).strftime('%Y-%m-%d')
            
            for episode_id in episode_ids:
                cache[str(episode_id)] = expiry_date
                rejected_count += 1
            
            save_rejection_cache(cache)
        
        # Remove from pending list
        for series in pending_list:
            for season_data in list(series['seasons'].values()):
                season_data['episodes'] = [
                    ep for ep in season_data['episodes'] 
                    if ep['episode_id'] not in episode_ids
                ]
                # Remove empty seasons
                for season_key in list(series['seasons'].keys()):
                    if not series['seasons'][season_key]['episodes']:
                        del series['seasons'][season_key]
        
        # Remove empty series
        pending_list = [s for s in pending_list if s['seasons']]
        
        save_pending_deletions(pending_list)
        logger.info(f"Rejected {rejected_count} episodes - added to {REJECTION_CACHE_DAYS} day rejection cache")
        
        return rejected_count


def clear_all_pending_deletions():
    """Clear all pending deletions"""
    with pending_lock:
        save_pending_deletions([])
        logger.info("Cleared all pending deletions")


def get_episode_ids_for_series(series_id):
    """Get all episode IDs for a series"""
    with pending_lock:
        pending_list = load_pending_deletions()
        series = next((s for s in pending_list if s['series_id'] == series_id), None)
        
        if not series:
            return []
        
        episode_ids = []
        for season_data in series['seasons'].values():
            episode_ids.extend(ep['episode_id'] for ep in season_data['episodes'])
        
        return episode_ids


def get_episode_ids_for_season(series_id, season_num):
    """Get all episode IDs for a season"""
    with pending_lock:
        pending_list = load_pending_deletions()
        series = next((s for s in pending_list if s['series_id'] == series_id), None)
        
        if not series:
            return []
        
        season_key = str(season_num)
        if season_key not in series['seasons']:
            return []
        
        return [ep['episode_id'] for ep in series['seasons'][season_key]['episodes']]
