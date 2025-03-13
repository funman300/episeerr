# api/jellyseerr_api.py
import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class JellyseerrAPI:
    """Client for interacting with Jellyseerr/Overseerr API."""
    
    def __init__(self, base_url=None, api_key=None):
        """Initialize the Jellyseerr API client.
        
        Args:
            base_url: Jellyseerr base URL (e.g., http://jellyseerr:5055)
            api_key: Jellyseerr API key
        """
        self.base_url = base_url or os.getenv('JELLYSEERR_URL', '')
        self.api_key = api_key or os.getenv('JELLYSEERR_API_KEY', '')
        
        # Remove trailing slash if present
        self.base_url = self.base_url.rstrip('/')
        
        if not self.base_url or not self.api_key:
            logger.warning("Jellyseerr URL or API key not configured")
    
    def get_headers(self):
        """Get headers for API requests."""
        return {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
    
    def get_trending(self, page=1, limit=20):
        """Get trending media from Jellyseerr.
        
        Args:
            page: Page number
            limit: Number of items per page
            
        Returns:
            dict: JSON response with trending media
        """
        try:
            url = f"{self.base_url}/api/v1/discover/trending"
            params = {
                'page': page,
                'language': 'en'
            }
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params
            )
            
            if response.ok:
                data = response.json()
                # Enhance data with direct URLs to images
                self._process_media_results(data.get('results', []))
                return data
            else:
                logger.error(f"Failed to get trending media. Status: {response.status_code}")
                return {'results': []}
        except Exception as e:
            logger.error(f"Error getting trending media: {str(e)}")
            return {'results': []}
    
    def get_popular(self, media_type='movie', page=1, limit=20):
        """Get popular media from Jellyseerr.
        
        Args:
            media_type: Type of media ('movie' or 'tv')
            page: Page number
            limit: Number of items per page
            
        Returns:
            dict: JSON response with popular media
        """
        try:
            endpoint = 'movies' if media_type == 'movie' else 'tv'
            url = f"{self.base_url}/api/v1/discover/{endpoint}"
            
            params = {
                'page': page,
                'language': 'en',
                'sortBy': 'popularity.desc'
            }
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params
            )
            
            if response.ok:
                data = response.json()
                # Enhance data with direct URLs to images
                self._process_media_results(data.get('results', []))
                return data
            else:
                logger.error(f"Failed to get popular {media_type}. Status: {response.status_code}")
                return {'results': []}
        except Exception as e:
            logger.error(f"Error getting popular {media_type}: {str(e)}")
            return {'results': []}
    
    def get_upcoming(self, media_type='movie', page=1, limit=20):
        """Get upcoming media from Jellyseerr.
        
        Args:
            media_type: Type of media ('movie' or 'tv')
            page: Page number
            limit: Number of items per page
            
        Returns:
            dict: JSON response with upcoming media
        """
        try:
            endpoint = 'movies/upcoming' if media_type == 'movie' else 'tv/upcoming'
            url = f"{self.base_url}/api/v1/discover/{endpoint}"
            
            params = {
                'page': page,
                'language': 'en'
            }
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params
            )
            
            if response.ok:
                data = response.json()
                # Enhance data with direct URLs to images
                self._process_media_results(data.get('results', []))
                return data
            else:
                logger.error(f"Failed to get upcoming {media_type}. Status: {response.status_code}")
                return {'results': []}
        except Exception as e:
            logger.error(f"Error getting upcoming {media_type}: {str(e)}")
            return {'results': []}
    
    def get_requests(self, page=1, limit=20, filter_status=None):
        """Get media requests from Jellyseerr.
        
        Args:
            page: Page number
            limit: Number of items per page
            filter_status: Optional status to filter (1=pending, 2=approved, 3=declined)
            
        Returns:
            dict: JSON response with requests
        """
        try:
            url = f"{self.base_url}/api/v1/request"
            
            params = {
                'take': limit,
                'skip': (page - 1) * limit,
                'sort': 'added',
                'filter': 'all'
            }
            
            if filter_status:
                params['filter'] = filter_status
            
            response = requests.get(
                url,
                headers=self.get_headers(),
                params=params
            )
            
            if response.ok:
                return response.json()
            else:
                logger.error(f"Failed to get requests. Status: {response.status_code}")
                return {'results': []}
        except Exception as e:
            logger.error(f"Error getting requests: {str(e)}")
            return {'results': []}
    
    def get_media_details(self, tmdb_id, media_type='tv'):
        """Get detailed information about a specific media item.
        
        Args:
            tmdb_id: TMDb ID of the media
            media_type: Type of media ('movie' or 'tv')
            
        Returns:
            dict: Media details
        """
        try:
            endpoint = 'movie' if media_type == 'movie' else 'tv'
            url = f"{self.base_url}/api/v1/{endpoint}/{tmdb_id}"
            
            response = requests.get(
                url,
                headers=self.get_headers()
            )
            
            if response.ok:
                data = response.json()
                # Add image URLs
                if data.get('posterPath'):
                    data['posterUrl'] = f"https://image.tmdb.org/t/p/w500{data['posterPath']}"
                if data.get('backdropPath'):
                    data['backdropUrl'] = f"https://image.tmdb.org/t/p/w1280{data['backdropPath']}"
                return data
            else:
                logger.error(f"Failed to get media details. Status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting media details: {str(e)}")
            return None
    
    def create_request(self, tmdb_id, media_type, seasons=None):
        """Create a media request in Jellyseerr.
        
        Args:
            tmdb_id: TMDb ID of the media
            media_type: Type of media ('movie' or 'tv')
            seasons: For TV, list of season numbers or 'all'
            
        Returns:
            dict: Request result or None on failure
        """
        try:
            url = f"{self.base_url}/api/v1/request"
            
            data = {
                "mediaId": tmdb_id,
                "mediaType": media_type
            }
            
            if media_type == 'tv' and seasons:
                data["seasons"] = seasons
            
            response = requests.post(
                url,
                headers=self.get_headers(),
                json=data
            )
            
            if response.ok:
                return response.json()
            else:
                logger.error(f"Failed to create request. Status: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error creating request: {str(e)}")
            return None
    
    def _process_media_results(self, results):
        """Add direct image URLs to media results."""
        for item in results:
            if item.get('posterPath'):
                item['posterUrl'] = f"https://image.tmdb.org/t/p/w500{item['posterPath']}"
            if item.get('backdropPath'):
                item['backdropUrl'] = f"https://image.tmdb.org/t/p/w1280{item['backdropPath']}"