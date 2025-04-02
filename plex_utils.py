# plex_utils.py
import os
import requests
import logging
import json
from datetime import datetime
import tmdb_utils

logger = logging.getLogger(__name__)

class PlexWatchlistAPI:
    def __init__(self, plex_token=None):
        self.plex_token = plex_token or os.getenv('PLEX_TOKEN', '')
        self.plex_url = os.getenv('PLEX_URL', 'http://localhost:32400')  # Default fallback
        self.logger = logging.getLogger(__name__)

    def get_headers(self):
        return {
            'X-Plex-Token': self.plex_token,
            'Accept': 'application/json'
        }
    
    def get_watchlist(self):
        try:
            url = "https://metadata.provider.plex.tv/library/sections/watchlist/all"
            
            response = requests.get(
                url,
                headers=self.get_headers()
            )
            
            if response.ok:
                return response.json()
            else:
                logger.error(f"Failed to get watchlist. Status: {response.status_code}")
                return {'MediaContainer': {'Metadata': []}}
        except Exception as e:
            logger.error(f"Error getting watchlist: {str(e)}")
            return {'MediaContainer': {'Metadata': []}}
    
    def process_watchlist_items(self):
        try:
            watchlist_data = self.get_watchlist()
            processed_items = []
            
            if 'MediaContainer' in watchlist_data and 'Metadata' in watchlist_data['MediaContainer']:
                items = watchlist_data['MediaContainer']['Metadata']
                
                for item in items:
                    processed_item = {
                        'title': item.get('title', ''),
                        'type': 'movie' if item.get('type') == 'movie' else 'tv',
                        'year': item.get('year'),
                        'plex_guid': item.get('guid', ''),
                        'thumb': item.get('thumb', '')
                    }
                    
                    # Get TMDB ID using title and year
                    if processed_item['type'] == 'movie':
                        search_results = tmdb_utils.search_movies(processed_item['title'])
                        if search_results.get('results'):
                            # Try to match year if available
                            if processed_item['year']:
                                for result in search_results['results']:
                                    if result.get('release_date', '').startswith(str(processed_item['year'])):
                                        processed_item['tmdb_id'] = result['id']
                                        processed_item['poster_path'] = result.get('poster_path')
                                        break
                            
                            # If no match with year or no year, use first result
                            if 'tmdb_id' not in processed_item and search_results['results']:
                                processed_item['tmdb_id'] = search_results['results'][0]['id']
                                processed_item['poster_path'] = search_results['results'][0].get('poster_path')
                    else:
                        search_results = tmdb_utils.search_tv_shows(processed_item['title'])
                        if search_results.get('results'):
                            # Try to match year if available
                            if processed_item['year']:
                                for result in search_results['results']:
                                    if result.get('first_air_date', '').startswith(str(processed_item['year'])):
                                        processed_item['tmdb_id'] = result['id']
                                        processed_item['poster_path'] = result.get('poster_path')
                                        break
                            
                            # If no match with year or no year, use first result
                            if 'tmdb_id' not in processed_item and search_results['results']:
                                processed_item['tmdb_id'] = search_results['results'][0]['id']
                                processed_item['poster_path'] = search_results['results'][0].get('poster_path')
                                
                                # Get TVDB ID for TV shows
                                external_ids = tmdb_utils.get_external_ids(processed_item['tmdb_id'], 'tv')
                                if external_ids and 'tvdb_id' in external_ids:
                                    processed_item['tvdb_id'] = external_ids['tvdb_id']
                    
                    # Only add items we could find a TMDB ID for
                    if 'tmdb_id' in processed_item:
                        processed_items.append(processed_item)
            
            return processed_items
        except Exception as e:
            logger.error(f"Error processing watchlist items: {str(e)}")
            return []
    
    def save_watchlist_data(self):
        try:
            data_dir = os.path.join(os.getcwd(), 'data')
            os.makedirs(data_dir, exist_ok=True)
            
            watchlist_items = self.process_watchlist_items()
            watchlist_data = {
                'items': watchlist_items,
                'last_updated': datetime.now().isoformat(),
                'count': len(watchlist_items)
            }
            
            with open(os.path.join(data_dir, 'plex_watchlist.json'), 'w') as f:
                json.dump(watchlist_data, f, indent=2)
                
            logger.info(f"Saved {len(watchlist_items)} watchlist items")
            return True
        except Exception as e:
            logger.error(f"Error saving watchlist data: {str(e)}")
            return False
    
    def load_watchlist_data(self):
        try:
            data_path = os.path.join(os.getcwd(), 'data', 'plex_watchlist.json')
            
            if not os.path.exists(data_path):
                return {'items': [], 'last_updated': None, 'count': 0}
                
            with open(data_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading watchlist data: {str(e)}")
            return {'items': [], 'last_updated': None, 'count': 0}
        
    def lookup_plex_media(self, tmdb_id, media_type):
        """
        Lookup media in Plex's metadata database with fallback mechanisms
        :param tmdb_id: TMDB ID of the media
        :param media_type: 'movie' or 'tv'
        :return: Dict with metadata or None
        """
        try:
            # First, try direct TMDB ID lookup
            lookup_url = "https://metadata.provider.plex.tv/library/search"
            params = {
                'query': f"tmdb://{tmdb_id}",
                'X-Plex-Token': self.plex_token
            }

            try:
                lookup_response = requests.get(lookup_url, params=params, headers=self.get_headers())
                
                if lookup_response.ok:
                    lookup_data = lookup_response.json()
                    matching_items = lookup_data.get('MediaContainer', {}).get('Metadata', [])
                    
                    # Filter by media type
                    type_code = 1 if media_type == 'movie' else 2
                    matching_items = [
                        item for item in matching_items 
                        if item.get('type') == type_code
                    ]

                    if matching_items:
                        self.logger.info(f"Found Plex media for TMDB ID {tmdb_id}")
                        return matching_items[0]
            except Exception as e:
                self.logger.warning(f"Error in primary Plex metadata lookup: {str(e)}")

            # Fallback: Try a more generic search if direct lookup fails
            generic_search_url = "https://metadata.provider.plex.tv/library/search"
            try:
                # Get additional media details from TMDB to aid search
                tmdb_details = self._get_tmdb_details(tmdb_id, media_type)
                
                if tmdb_details:
                    search_params = {
                        'query': tmdb_details.get('title', ''),
                        'X-Plex-Token': self.plex_token
                    }
                    
                    generic_response = requests.get(generic_search_url, params=search_params, headers=self.get_headers())
                    
                    if generic_response.ok:
                        generic_data = generic_response.json()
                        generic_items = generic_data.get('MediaContainer', {}).get('Metadata', [])
                        
                        # Additional filtering
                        filtered_items = [
                            item for item in generic_items
                            if (item.get('type') == (1 if media_type == 'movie' else 2) and 
                                # Fuzzy year matching
                                abs(int(item.get('year', 0)) - int(tmdb_details.get('year', 0))) <= 1)
                        ]
                        
                        if filtered_items:
                            self.logger.info(f"Found Plex media via generic search for TMDB ID {tmdb_id}")
                            return filtered_items[0]
            except Exception as e:
                self.logger.warning(f"Error in fallback Plex metadata lookup: {str(e)}")

            # Final fallback: log detailed failure
            self.logger.warning(f"Could not find Plex metadata for TMDB ID {tmdb_id} of type {media_type}")
            return None

        except Exception as e:
            self.logger.error(f"Comprehensive error looking up media in Plex: {str(e)}")
            return 
    # Add this new method to your PlexWatchlistAPI class in plex_utils.py
    def get_formatted_watchlist_data(self):
        """
        Retrieves and formats watchlist data for the frontend
        """
        try:
            watchlist_data = self.load_watchlist_data()
            items = watchlist_data.get('items', [])
            
            # Get library stats
            library_sections = self.get_library_sections()
            library_stats = {
                "movies": 0,
                "tv_shows": 0
            }
            
            # Get library counts
            if library_sections.get("movie"):
                try:
                    movie_url = f"{self.plex_url}/library/sections/{library_sections['movie']}/all"
                    movie_response = requests.get(movie_url, headers=self.get_headers())
                    if movie_response.ok:
                        movie_data = movie_response.json()
                        library_stats["movies"] = movie_data.get("MediaContainer", {}).get("size", 0)
                except Exception as e:
                    logging.error(f"Error getting movie count: {str(e)}")
            
            if library_sections.get("tv"):
                try:
                    tv_url = f"{self.plex_url}/library/sections/{library_sections['tv']}/all"
                    tv_response = requests.get(tv_url, headers=self.get_headers())
                    if tv_response.ok:
                        tv_data = tv_response.json()
                        library_stats["tv_shows"] = tv_data.get("MediaContainer", {}).get("size", 0)
                except Exception as e:
                    logging.error(f"Error getting TV show count: {str(e)}")
            
            # Count watchlist items by type
            watchlist_stats = {
                "movies": len([item for item in items if item.get("type") == "movie"]),
                "tv_shows": len([item for item in items if item.get("type") == "tv"])
            }
            
            # Organize items into categories
            categories = {
                'tv_in_watchlist': [],
                'tv_not_in_arr': [],
                'movie_in_watchlist': [],
                'movie_not_in_arr': []
            }
            
            for item in items:
                if item.get('type') == 'tv':
                    categories['tv_in_watchlist'].append(item)
                    # For simplicity, we'll treat all watchlist items as "not in arr" 
                    # You can implement your own logic to determine if it's in your Sonarr/Radarr
                    categories['tv_not_in_arr'].append(item)
                elif item.get('type') == 'movie':
                    categories['movie_in_watchlist'].append(item)
                    categories['movie_not_in_arr'].append(item)
            
            # Compile the full response
            return {
                'success': True,
                'watchlist': {
                    'categories': categories,
                    'last_updated': watchlist_data.get('last_updated'),
                    'count': watchlist_data.get('count', 0),
                    'stats': {
                        'library_stats': library_stats,
                        'watchlist_stats': watchlist_stats
                    }
                }
            }
        except Exception as e:
            logging.error(f"Error formatting watchlist data: {str(e)}")
            return {
                'success': False,
                'message': f"Error: {str(e)}"
            }
    
    def _get_tmdb_details(self, tmdb_id, media_type):
        """
        Helper method to fetch additional TMDB details for fallback search
        """
        try:
            import tmdb_utils  # Assuming you have a tmdb_utils module
            
            if media_type == 'movie':
                details = tmdb_utils.get_movie_details(tmdb_id)
            else:
                details = tmdb_utils.get_tv_show_details(tmdb_id)
            
            return {
                'title': details.get('title') or details.get('name'),
                'year': details.get('release_date', '').split('-')[0] if media_type == 'movie' else
                        details.get('first_air_date', '').split('-')[0]
            }
        except Exception as e:
            self.logger.warning(f"Error fetching TMDB details for {tmdb_id}: {str(e)}")
            return None
    
    
    
    def get_library_sections(self):
        """
        Fetches library section IDs dynamically from Plex.
        Returns a dictionary mapping 'movie' and 'tv' to their respective section IDs.
        """
        try:
            url = f"{self.plex_url}/library/sections"
            response = requests.get(url, headers=self.get_headers())

            if response.ok:
                data = response.json()
                sections = {}
                
                for section in data.get('MediaContainer', {}).get('Directory', []):
                    section_type = section.get('type')  # 'movie', 'show', etc.
                    section_key = section.get('key')  # The section ID
                    
                    if section_type == "movie":
                        sections["movie"] = section_key
                    elif section_type == "show":
                        sections["tv"] = section_key

                return sections
            else:
                logging.error(f"Failed to fetch library sections: {response.status_code}")
                return {}
        except Exception as e:
            logging.error(f"Error fetching library sections: {str(e)}")
            return {}

    

    