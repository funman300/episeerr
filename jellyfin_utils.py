# jellyfin_utils.py
import os
import requests
import logging
import json
from datetime import datetime
import tmdb_utils

logger = logging.getLogger(__name__)

class JellyfinAPI:
    def __init__(self, jellyfin_token=None, jellyfin_user_id=None, jellyfin_username=None):
        # Initialize with either direct values or environment variables
        self.jellyfin_token = jellyfin_token or os.getenv('JELLYFIN_TOKEN', '')
        self.jellyfin_url = os.getenv('JELLYFIN_URL', 'http://localhost:8096')
        
        # Get username from environment if not provided
        self.jellyfin_username = jellyfin_username or os.getenv('JELLYFIN_USERNAME', '')
        
        # Get user_id from environment
        self.jellyfin_user_id = jellyfin_user_id or os.getenv('JELLYFIN_USER_ID', '')
        
        # If we have a username that looks like a username (not a GUID) and no valid user ID,
        # try to resolve the actual user ID
        if (self.jellyfin_username or (self.jellyfin_user_id and len(self.jellyfin_user_id) < 32)) and not (self.jellyfin_user_id and len(self.jellyfin_user_id) > 32):
            potential_username = self.jellyfin_username or self.jellyfin_user_id
            resolved_id = self.get_user_id_by_name(potential_username)
            if resolved_id:
                self.jellyfin_user_id = resolved_id
                print(f"Resolved user ID for '{potential_username}': {resolved_id}")
        
        self.logger = logging.getLogger(__name__)
    def get_headers(self):
        return {
            "Authorization": f'MediaBrowser Token="{self.jellyfin_token}"',
            "Accept": "application/json"
        }

    def get_user_id_by_name(self, username):
        """
        Retrieve the user ID for a given username
        """
        try:
            url = f"{self.jellyfin_url}/Users"
            
            response = requests.get(
                url,
                headers=self.get_headers()
            )
            
            if response.ok:
                users = response.json()
                for user in users:
                    if user.get('Name') == username:
                        return user.get('Id')
                
                # If no exact match found
                logger.error(f"No user found with name: {username}")
                return None
            else:
                logger.error(f"Failed to get users. Status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting user ID: {str(e)}")
            return None
            
    def get_favorites(self):
        """
        Get user's favorite items from Jellyfin
        """
        try:
            if not self.jellyfin_user_id:
                logger.error("No Jellyfin user ID available")
                return {'Items': []}
                
            url = f"{self.jellyfin_url}/Users/{self.jellyfin_user_id}/Items/Favorites"
            
            response = requests.get(
                url,
                headers=self.get_headers()
            )
            
            if response.ok:
                return response.json()
            else:
                logger.error(f"Failed to get Jellyfin favorites. Status: {response.status_code}")
                return {'Items': []}
        except Exception as e:
            logger.error(f"Error getting Jellyfin favorites: {str(e)}")
            return {'Items': []}
    
    def get_recent_items(self):
        """
        Get recently added items from Jellyfin
        """
        try:
            url = f"{self.jellyfin_url}/Users/{self.jellyfin_user_id}/Items/Latest"
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                params={
                    'Limit': 24,  # Match your MAX_COMBINED_ITEMS
                    'Fields': 'Overview,ProductionYear'
                }
            )
            
            if response.ok:
                return response.json()
            else:
                logger.error(f"Failed to get recent items. Status: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting recent items: {str(e)}")
            return []
            
    def get_library_stats(self):
        """
        Get basic library statistics
        """
        try:
            movie_url = f"{self.jellyfin_url}/Items/Counts"
            response = requests.get(movie_url, headers=self.get_headers())
            
            if response.ok:
                data = response.json()
                return {
                    "movies": data.get("MovieCount", 0),
                    "tv_shows": data.get("SeriesCount", 0),
                    "episodes": data.get("EpisodeCount", 0)
                }
            else:
                return {"movies": 0, "tv_shows": 0, "episodes": 0}
        except Exception as e:
            logger.error(f"Error getting library stats: {str(e)}")
            return {"movies": 0, "tv_shows": 0, "episodes": 0}
    def process_recent_items(self):
        try:
            recent_items = self.get_recent_items()
            processed_items = []
            
            for item in recent_items:
                # Only process Movies and Series, exclude Episodes
                if item.get('Type') in ['Movie', 'Series']:
                    media_type = 'movie' if item.get('Type') == 'Movie' else 'tv'
                    
                    processed_item = {
                        'Id': item.get('Id'),
                        'Name': item.get('Name', ''),
                        'Type': item.get('Type', ''),
                        'type': media_type,
                        'ProductionYear': item.get('ProductionYear'),
                        'Overview': item.get('Overview', ''),
                        'ImageTags': item.get('ImageTags', {}),
                        'PrimaryImageTag': item.get('PrimaryImageTag', ''),
                        'dateAdded': datetime.now().isoformat()
                    }
                    
                    # Try to get TMDB ID as a best effort
                    if 'ProviderIds' in item and 'Tmdb' in item['ProviderIds']:
                        processed_item['tmdb_id'] = item['ProviderIds']['Tmdb']
                    
                    processed_items.append(processed_item)
            
            return processed_items
        except Exception as e:
            logger.error(f"Error processing recent items: {str(e)}")
            return []
    def process_favorites_items(self):
        """
        Process favorites to be sent to the frontend
        """
        try:
            favorites_data = self.get_favorites()
            processed_items = []
            
            if 'Items' in favorites_data:
                items = favorites_data['Items']
                
                for item in items:
                    # Determine media type
                    if item.get('Type') == 'Movie':
                        media_type = 'movie'
                    else:
                        media_type = 'tv'
                    
                    processed_item = {
                        'Id': item.get('Id'),
                        'Name': item.get('Name', ''),
                        'Type': item.get('Type', ''),
                        'type': media_type,
                        'ProductionYear': item.get('ProductionYear'),
                        'Overview': item.get('Overview', ''),
                        'ImageTags': item.get('ImageTags', {}),
                        'PrimaryImageTag': item.get('PrimaryImageTag', '')
                    }
                    
                    # Try to get TMDB ID as a best effort
                    if 'ProviderIds' in item and 'Tmdb' in item['ProviderIds']:
                        processed_item['tmdb_id'] = item['ProviderIds']['Tmdb']
                    
                    processed_items.append(processed_item)
            
            return processed_items
        except Exception as e:
            logger.error(f"Error processing favorites items: {str(e)}")
            return []
    
    def process_recent_items(self):
        """
        Process recent items to be sent to the frontend
        """
        try:
            recent_items = self.get_recent_items()
            processed_items = []
            
            for item in recent_items:
                # Determine media type
                if item.get('Type') == 'Movie':
                    media_type = 'movie'
                else:
                    media_type = 'tv'
                
                processed_item = {
                    'Id': item.get('Id'),
                    'Name': item.get('Name', ''),
                    'Type': item.get('Type', ''),
                    'type': media_type,
                    'ProductionYear': item.get('ProductionYear'),
                    'Overview': item.get('Overview', ''),
                    'ImageTags': item.get('ImageTags', {}),
                    'PrimaryImageTag': item.get('PrimaryImageTag', ''),
                    'dateAdded': datetime.now().isoformat()  # We don't get this from Jellyfin API, so use current time
                }
                
                # Try to get TMDB ID as a best effort
                if 'ProviderIds' in item and 'Tmdb' in item['ProviderIds']:
                    processed_item['tmdb_id'] = item['ProviderIds']['Tmdb']
                
                processed_items.append(processed_item)
            
            return processed_items
        except Exception as e:
            logger.error(f"Error processing recent items: {str(e)}")
            return []
    
    def get_formatted_stats(self):
        """
        Get formatted stats for the frontend
        """
        try:
            # Get library stats
            library_stats = self.get_library_stats()
            
            # Get favorites stats
            favorites = self.process_favorites_items()
            favorites_stats = {
                "movies": len([item for item in favorites if item.get('Type') == 'Movie']),
                "tv_shows": len([item for item in favorites if item.get('Type') != 'Movie'])
            }
            
            return {
                "success": True,
                "stats": {
                    "library_stats": library_stats,
                    "favorites_stats": favorites_stats
                },
                "lastUpdated": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting formatted stats: {str(e)}")
            return {
                "success": False,
                "message": str(e)
            }
    
    def save_connection_info(self, url, token, user_id):
        """
        Save Jellyfin connection info to .env file
        """
        try:
            # Update .env file
            with open('.env', 'a') as f:
                f.write(f"\nJELLYFIN_URL={url}\n")
                f.write(f"JELLYFIN_TOKEN={token}\n")
                f.write(f"JELLYFIN_USER_ID={user_id}\n")
            
            # Update instance variables
            self.jellyfin_url = url
            self.jellyfin_token = token
            self.jellyfin_user_id = user_id
            
            return True
        except Exception as e:
            logger.error(f"Error saving connection info: {str(e)}")
            return False