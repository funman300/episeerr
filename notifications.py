"""
Episeerr Notification System
Handles Discord notifications for missing episodes, failed requests, and errors
"""

import requests
import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Config will be passed in from episeerr.py
NOTIFICATIONS_ENABLED = False
DISCORD_WEBHOOK_URL = ''
EPISEERR_URL = 'http://localhost:5002'
SONARR_URL = 'http://localhost:8989'

def init_notifications(notifications_enabled, discord_webhook_url, episeerr_url, sonarr_url):
    """Initialize notification config - called from episeerr.py on startup"""
    global NOTIFICATIONS_ENABLED, DISCORD_WEBHOOK_URL, EPISEERR_URL, SONARR_URL
    NOTIFICATIONS_ENABLED = notifications_enabled
    DISCORD_WEBHOOK_URL = discord_webhook_url
    EPISEERR_URL = episeerr_url
    SONARR_URL = sonarr_url


def send_notification(notification_type, **data):
    """
    Central notification dispatcher
    
    Args:
        notification_type: Type of notification to send
        **data: Context data for the notification
        
    Supported types:
        - missing_episode: Episode not found by Sonarr
        - request_failed: Tagged request failed (no episodes grabbed)
        - selection_pending: New episeerr_select request
        - error: Critical error occurred
    """
    if not NOTIFICATIONS_ENABLED:
        logger.debug(f"Notifications disabled, skipping {notification_type}")
        return
    
    if not DISCORD_WEBHOOK_URL:
        logger.warning("Discord webhook URL not configured")
        return
    
    try:
        # Build message based on type
        if notification_type == "missing_episode":
            message = build_missing_episode_message(
                series=data['series'],
                season=data['season'],
                episode=data['episode'],
                air_date=data.get('air_date'),
                series_id=data.get('series_id')
            )
        
        elif notification_type == "request_failed":
            message = build_request_failed_message(
                series=data['series'],
                tag=data['tag'],
                series_id=data.get('series_id')
            )
        
        elif notification_type == "selection_pending":
            message = build_selection_pending_message(
                series=data['series'],
                request_id=data.get('request_id'),
                series_id=data.get('series_id')
            )
        
        elif notification_type == "error":
            message = build_error_message(
                error=data['error'],
                context=data.get('context')
            )
        
        else:
            logger.warning(f"Unknown notification type: {notification_type}")
            return
        
        # Send notification
        send_discord_webhook(message)
        logger.info(f"Sent {notification_type} notification")
        
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")


def build_missing_episode_message(series, season, episode, air_date=None, series_id=None):
    """Build Discord embed for episode search status with context-aware messaging"""
    
    # Format air date and determine context
    air_date_str = "Unknown"
    description = "Sonarr searched but couldn't find this episode"
    emoji = "📺"
    color = 3447003  # Blue - informational
    
    if air_date:
        try:
            from datetime import timezone
            dt = datetime.fromisoformat(air_date.replace('Z', '+00:00'))
            air_date_str = dt.strftime("%B %d, %Y")
            
            # Calculate days relative to air date
            now = datetime.now(timezone.utc)
            days_diff = (now - dt).days
            
            if days_diff < 0:
                # Future air date
                days_until = abs(days_diff)
                emoji = "📅"
                if days_until == 0:
                    description = "Episode airs today. Check back after it airs."
                elif days_until == 1:
                    description = "Episode airs tomorrow. Will be available after it airs."
                else:
                    description = f"Episode airs in {days_until} days. Will be available after it airs."
            elif days_diff <= 2:
                # Just aired (0-2 days ago)
                emoji = "⏳"
                description = "Episode aired recently. May not be available on trackers yet - check back soon."
            elif days_diff <= 7:
                # Aired 3-7 days ago
                emoji = "⚠️"
                color = 16744448  # Orange
                description = "Episode aired this week but wasn't found. May need manual search or different tracker."
            else:
                # Aired over a week ago
                emoji = "❌"
                color = 15158332  # Red
                description = "Episode aired over a week ago but wasn't found. Likely needs manual search or different source."
                
        except Exception as e:
            logger.error(f"Error parsing air date: {e}")
            air_date_str = str(air_date)
    
    # Build Sonarr link
    sonarr_link = ""
    if series_id and SONARR_URL:
        series_slug = series.lower().replace(' ', '-').replace("'", "")
        sonarr_link = f"{SONARR_URL}/series/{series_slug}/season-{season}"
    
    fields = [
        {
            "name": "Episode",
            "value": f"{series} S{season:02d}E{episode:02d}",
            "inline": False
        },
        {
            "name": "Air Date",
            "value": air_date_str,
            "inline": True
        }
    ]
    
    if sonarr_link:
        fields.append({
            "name": "🔍 Manual Search",
            "value": f"[Open in Sonarr]({sonarr_link})",
            "inline": False
        })
    
    return {
        "embeds": [{
            "title": f"{emoji} Episode Not Yet Available",
            "description": description,
            "color": color,
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }


def build_request_failed_message(series, tag, series_id=None):
    """Build Discord embed for failed tagged request"""
    
    sonarr_link = ""
    if series_id and SONARR_URL:
        series_slug = series.lower().replace(' ', '-').replace("'", "")
        sonarr_link = f"{SONARR_URL}/series/{series_slug}"
    
    fields = [
        {
            "name": "Series",
            "value": series,
            "inline": False
        },
        {
            "name": "Tag",
            "value": tag,
            "inline": True
        },
        {
            "name": "Issue",
            "value": "No episodes were grabbed by Sonarr",
            "inline": False
        }
    ]
    
    if sonarr_link:
        fields.append({
            "name": "🔍 Check Sonarr",
            "value": f"[Open Series]({sonarr_link})",
            "inline": False
        })
    
    return {
        "embeds": [{
            "title": "⚠️ Request Processing Failed",
            "description": "Tagged request completed but no episodes were found",
            "color": 16744448,  # Orange
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }


def build_selection_pending_message(series, request_id=None, series_id=None):
    """Build Discord embed for pending episode selection"""
    
    episeerr_link = ""
    if EPISEERR_URL:
        episeerr_link = f"{EPISEERR_URL}/episeerr"
    
    fields = [
        {
            "name": "Series",
            "value": series,
            "inline": False
        }
    ]
    
    if episeerr_link:
        fields.append({
            "name": "🔗 Select Episodes",
            "value": f"[Open Episeerr]({episeerr_link})",
            "inline": False
        })
    
    return {
        "embeds": [{
            "title": "📋 New Episode Selection Request",
            "description": "A show is waiting for episode selection",
            "color": 3447003,  # Blue
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }


def build_error_message(error, context=None):
    """Build Discord embed for errors"""
    
    fields = [
        {
            "name": "Error",
            "value": str(error)[:1024],  # Discord field limit
            "inline": False
        }
    ]
    
    if context:
        fields.append({
            "name": "Context",
            "value": str(context)[:1024],
            "inline": False
        })
    
    return {
        "embeds": [{
            "title": "❌ Episeerr Error",
            "description": "An error occurred during processing",
            "color": 15158332,  # Red
            "fields": fields,
            "timestamp": datetime.utcnow().isoformat()
        }]
    }


def send_discord_webhook(message):
    """Send notification to Discord webhook"""
    if not DISCORD_WEBHOOK_URL:
        return
    
    try:
        response = requests.post(
            DISCORD_WEBHOOK_URL,
            json=message,
            timeout=10
        )
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord webhook failed: {e}")


