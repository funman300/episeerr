# modified_episeerr.py - Simplified version for OCDarr Lite
# Handles tag creation, download protection, and seer integration only

import os
import json
import requests
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create logs directory in the current working directory
log_dir = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, 'episeerr.log')

# Create logger
logger = logging.getLogger("episeerr")
logger.setLevel(logging.DEBUG)

# Clear any existing handlers
logger.handlers.clear()

# Create rotating file handler
file_handler = RotatingFileHandler(
    log_file, 
    maxBytes=10*1024*1024,  # 10 MB
    backupCount=1,  # Keep one backup file
    encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(file_formatter)

# Add handlers to logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# Sonarr connection details
SONARR_URL = os.getenv('SONARR_URL', 'http://sonarr:8989')
SONARR_API_KEY = os.getenv('SONARR_API_KEY')

# Jellyseerr/Overseerr connection details
JELLYSEERR_URL = os.getenv('JELLYSEERR_URL', '')
JELLYSEERR_API_KEY = os.getenv('JELLYSEERR_API_KEY', '')

# Global variables
OCDARR_TAG_ID = None  # Will be set when create_ocdarr_tag() is called

def get_sonarr_headers():
    """Get headers for Sonarr API requests."""
    return {
        'X-Api-Key': SONARR_API_KEY,
        'Content-Type': 'application/json'
    }

def get_jellyseerr_headers():
    """Get headers for Jellyseerr/Overseerr API requests."""
    return {
        'X-Api-Key': JELLYSEERR_API_KEY,
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

def create_ocdarr_tag():
    """Create a single 'ocdarr' tag in Sonarr and return its ID."""
    try:
        headers = get_sonarr_headers()
        logger.debug(f"Making request to {SONARR_URL}/api/v3/tag")
        
        # Get existing tags
        tags_response = requests.get(
            f"{SONARR_URL}/api/v3/tag",
            headers=headers
        )
        
        if not tags_response.ok:
            logger.error(f"Failed to get tags. Status: {tags_response.status_code}")
            return None

        # Look for existing ocdarr tag
        ocdarr_tag_id = None
        for tag in tags_response.json():
            if tag['label'].lower() == 'ocdarr':
                ocdarr_tag_id = tag['id']
                logger.info(f"Found existing 'ocdarr' tag with ID {ocdarr_tag_id}")
                break
        
        # Create ocdarr tag if it doesn't exist
        if ocdarr_tag_id is None:
            tag_create_response = requests.post(
                f"{SONARR_URL}/api/v3/tag",
                headers=headers,
                json={"label": "ocdarr"}
            )
            if tag_create_response.ok:
                ocdarr_tag_id = tag_create_response.json().get('id')
                logger.info(f"Created tag: 'ocdarr' with ID {ocdarr_tag_id}")
            else:
                logger.error(f"Failed to create ocdarr tag. Status: {tag_create_response.status_code}")
                return None
        
        # Store the ocdarr tag ID in a global variable for later use
        global OCDARR_TAG_ID
        OCDARR_TAG_ID = ocdarr_tag_id
        return ocdarr_tag_id
    except Exception as e:
        logger.error(f"Error creating ocdarr tag: {str(e)}")
        return None

def get_episode_info(episode_id, headers):
    """Get episode information from Sonarr API"""
    try:
        response = requests.get(f"{SONARR_URL}/api/v3/episode/{episode_id}", headers=headers)
        if response.ok:
            return response.json()
        return None
    except Exception as e:
        logger.error(f"Error getting episode info: {str(e)}")
        return None

def cancel_download(queue_id, headers):
    """Cancel a download in Sonarr's queue"""
    try:
        # Primary method: Bulk remove with client removal
        payload = {
            "ids": [queue_id],
            "removeFromClient": True,
            "removeFromDownloadClient": True
        }
        response = requests.delete(f"{SONARR_URL}/api/v3/queue/bulk", headers=headers, json=payload)
        
        # If primary method fails, try alternative
        if not response.ok:
            logger.warning(f"Bulk removal failed for queue item {queue_id}. Trying alternative method.")
            response = requests.delete(
                f"{SONARR_URL}/api/v3/queue/{queue_id}", 
                headers=headers,
                params={
                    "removeFromClient": "true"
                }
            )
        
        return response.ok
    except Exception as e:
        logger.error(f"Error cancelling download: {str(e)}")
        return False

def check_and_cancel_unmonitored_downloads():
    """
    Check and cancel unmonitored episode downloads for series with ocdarr tag.
    This provides download protection for rule-managed series.
    """
    headers = get_sonarr_headers()
    
    logger.info("Starting unmonitored download cancellation check")
    logger.info(f"OCDarr tag ID: {OCDARR_TAG_ID}")
    
    try:
        # Retrieve current queue
        queue_response = requests.get(f"{SONARR_URL}/api/v3/queue", headers=headers)
        
        if not queue_response.ok:
            logger.error(f"Failed to retrieve queue. Status: {queue_response.status_code}")
            return
        
        queue = queue_response.json().get('records', [])
        logger.info(f"Total queue items: {len(queue)}")
        
        if len(queue) == 0:
            logger.info("No items in queue to process")
            return
            
        # Track cancelled items
        cancelled_count = 0
        
        for item in queue:
            # Detailed logging for each queue item
            logger.info(f"Examining queue item: {item.get('title', 'Unknown')}")
            logger.info(f"Series ID: {item.get('seriesId')}, Episode ID: {item.get('episodeId')}")
            
            # Check if this is a TV episode
            if item.get('seriesId') and item.get('episodeId'):
                # Get series details to check for 'ocdarr' tag
                series_response = requests.get(
                    f"{SONARR_URL}/api/v3/series/{item['seriesId']}", 
                    headers=headers
                )
                
                if not series_response.ok:
                    logger.error(f"Failed to get series details for ID {item['seriesId']}")
                    continue
                
                series = series_response.json()
                
                # Log series tags
                logger.info(f"Series tags: {series.get('tags', [])}")
                
                # Check if series has 'ocdarr' tag
                if OCDARR_TAG_ID in series.get('tags', []):
                    # Get episode details
                    episode_info = get_episode_info(item['episodeId'], headers)
                    
                    if episode_info:
                        logger.info(f"Episode details: Number {episode_info.get('episodeNumber')}, Monitored: {episode_info.get('monitored')}")
                        
                        # If episode is unmonitored, cancel download
                        if not episode_info.get('monitored', False):
                            # Unmonitored episode - cancel download
                            cancel_success = cancel_download(item['id'], headers)
                            
                            if cancel_success:
                                series_title = series.get('title', 'Unknown Series')
                                logger.info(
                                    f"Cancelled unmonitored download for ocdarr-tagged series: "
                                    f"{series_title} - Season {item.get('seasonNumber')} "
                                    f"Episode {episode_info.get('episodeNumber')}"
                                )
                                cancelled_count += 1
                            else:
                                logger.error(f"Failed to cancel download for {series.get('title')} - Episode ID {item['episodeId']}")
                        else:
                            logger.info(f"Episode {episode_info.get('episodeNumber')} is monitored - keeping download")
                    else:
                        logger.warning(f"Could not get episode info for ID {item['episodeId']}")
                else:
                    logger.info(f"Series {series.get('title')} does not have the ocdarr tag - skipping")
        
        # Log summary
        logger.info(f"Cancellation check complete. Cancelled {cancelled_count} unmonitored downloads for ocdarr-tagged series")
    
    except Exception as e:
        logger.error(f"Error in download queue monitoring: {str(e)}", exc_info=True)

def delete_jellyseerr_request(request_id):
    """
    Delete a specific request in Jellyseerr/Overseerr.
    Used to remove requests that conflict with OCDarr rule management.
    
    :param request_id: ID of the request to delete
    :return: True if successful, False otherwise
    """
    try:
        if not JELLYSEERR_URL or not JELLYSEERR_API_KEY:
            logger.warning("Jellyseerr URL or API key not configured. Cannot delete request.")
            return False
            
        headers = get_jellyseerr_headers()
        
        # Log the deletion attempt
        logger.info(f"Attempting to delete Jellyseerr request {request_id}")
        logger.debug(f"Jellyseerr headers: {headers}")

        delete_response = requests.delete(
            f"{JELLYSEERR_URL}/api/v1/request/{request_id}",
            headers=headers
        )
        
        # Log full response for debugging
        logger.debug(f"Delete Request Response Status: {delete_response.status_code}")
        try:
            response_json = delete_response.json()
            logger.debug(f"Delete Request Response JSON: {json.dumps(response_json, indent=2)}")
        except ValueError:
            logger.debug(f"Delete Request Response Text: {delete_response.text}")
        
        if delete_response.ok or delete_response.status_code == 404:
            # 404 means the request was already deleted
            logger.info(f"Successfully deleted or request not found: {request_id}")
            return True
        else:
            logger.error(f"Failed to delete request {request_id}. Status: {delete_response.status_code}")
            return False
    
    except Exception as e:
        logger.error(f"Error deleting Jellyseerr request: {str(e)}", exc_info=True)
        return False

def remove_ocdarr_tag_from_series(series_id):
    """
    Remove the ocdarr tag from a specific series after processing.
    This cleans up the tag assignment while keeping the tag available for future use.
    
    :param series_id: Sonarr series ID
    :return: True if successful, False otherwise
    """
    try:
        headers = get_sonarr_headers()
        
        # Get current series data
        series_response = requests.get(
            f"{SONARR_URL}/api/v3/series/{series_id}",
            headers=headers
        )
        
        if not series_response.ok:
            logger.error(f"Failed to get series {series_id}. Status: {series_response.status_code}")
            return False
            
        series = series_response.json()
        
        # Remove ocdarr tag from series tags if present
        current_tags = series.get('tags', [])
        if OCDARR_TAG_ID in current_tags:
            updated_tags = [tag for tag in current_tags if tag != OCDARR_TAG_ID]
            series['tags'] = updated_tags
            
            # Update series
            update_response = requests.put(
                f"{SONARR_URL}/api/v3/series",
                headers=headers,
                json=series
            )
            
            if update_response.ok:
                logger.info(f"Removed ocdarr tag from series {series.get('title', 'Unknown')} (ID: {series_id})")
                return True
            else:
                logger.error(f"Failed to update series {series_id}. Status: {update_response.status_code}")
                return False
        else:
            logger.info(f"Series {series.get('title', 'Unknown')} (ID: {series_id}) does not have ocdarr tag")
            return True
            
    except Exception as e:
        logger.error(f"Error removing ocdarr tag from series {series_id}: {str(e)}", exc_info=True)
        return False

# Initialize tag creation on import
try:
    create_ocdarr_tag()
    logger.info("OCDarr tag system initialized")
except Exception as e:
    logger.error(f"Failed to initialize OCDarr tag system: {str(e)}")

# For backward compatibility - these functions can be called by other modules
def delete_overseerr_request(request_id):
    """Alias for delete_jellyseerr_request for backward compatibility."""
    return delete_jellyseerr_request(request_id)

# Export the main tag ID for use by other modules
def get_ocdarr_tag_id():
    """Get the OCDarr tag ID for use by other modules."""
    return OCDARR_TAG_ID