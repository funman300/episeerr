# radarr_utils.py
import os
import requests
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration settings from environment variables
RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')

# Setup logging
logger = logging.getLogger(__name__)

def load_preferences():
    """
    Load preferences for Radarr configuration.
    Returns a dictionary containing Radarr URL and API key.
    """
    return {'RADARR_URL': RADARR_URL, 'RADARR_API_KEY': RADARR_API_KEY}

def get_movie_list(preferences):
    """Get all movies from Radarr."""
    url = f"{preferences['RADARR_URL']}/api/v3/movie"
    headers = {'X-Api-Key': preferences['RADARR_API_KEY']}
    
    try:
        response = requests.get(url, headers=headers)
        if response.ok:
            movie_list = response.json()
            # Sort the movie list alphabetically by title
            sorted_movie_list = sorted(movie_list, key=lambda x: x['title'].lower())
            return sorted_movie_list
        else:
            logger.error(f"Failed to get movie list. Status: {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"Error fetching movie list: {str(e)}")
        return []

def fetch_recent_movies(preferences, tautulli_url=None, tautulli_api_key=None, limit=12):
    """
    Fetch recently added movies from Radarr.
    Returns a list of dictionaries with movie details.
    """
    RADARR_URL = preferences['RADARR_URL']
    RADARR_API_KEY = preferences['RADARR_API_KEY']
    
    # Get watched movies if Tautulli is configured
    watched_movies = get_watched_movies(tautulli_url, tautulli_api_key) if tautulli_url and tautulli_api_key else set()
    
    movie_url = f"{RADARR_URL}/api/v3/movie"
    headers = {'X-Api-Key': RADARR_API_KEY}
    recent_movies = []
    
    try:
        movie_response = requests.get(movie_url, headers=headers)
        if movie_response.ok:
            movies = movie_response.json()
            
            # Filter for movies that have files and sort by dateAdded
            available_movies = [
                movie for movie in movies 
                if movie.get('hasFile', False) and 
                movie.get('movieFile', {}).get('dateAdded') and
                str(movie.get('tmdbId', '')) not in watched_movies  # Skip watched movies
            ]
            
            # Sort by dateAdded, newest first
            available_movies.sort(
                key=lambda x: datetime.fromisoformat(
                    x.get('movieFile', {}).get('dateAdded', '').replace('Z', '+00:00')
                ), 
                reverse=True
            )
            
            # Take the most recent movies up to the limit
            for movie in available_movies[:limit]:
                recent_movies.append({
                    'name': movie['title'],
                    'year': movie['year'],
                    'type': 'movie',  # Add type to distinguish from TV shows
                    'artwork_url': f"{RADARR_URL}/api/v3/mediacover/{movie['id']}/poster-500.jpg?apikey={RADARR_API_KEY}",
                    'radarr_movie_url': f"{RADARR_URL}/movie/{movie['titleSlug']}",
                    'dateAdded': datetime.fromisoformat(
                        movie.get('movieFile', {}).get('dateAdded', '').replace('Z', '+00:00')
                    )
                })
            
        return recent_movies
    except Exception as e:
        logger.error(f"Error fetching recent movies: {str(e)}")
        return []

def fetch_upcoming_movies(preferences):
    """
    Fetch upcoming movie releases from Radarr.
    Returns a list of dictionaries with upcoming movie details.
    """
    RADARR_URL = preferences['RADARR_URL']
    RADARR_API_KEY = preferences['RADARR_API_KEY']
    
    movie_url = f"{RADARR_URL}/api/v3/movie"
    headers = {'X-Api-Key': RADARR_API_KEY}
    upcoming_movies = []
    
    try:
        movie_response = requests.get(movie_url, headers=headers)
        if movie_response.ok:
            movies = movie_response.json()
            
            # Get current date for comparison
            now = datetime.now()
            
            # Add debug logging
            logger.info(f"Found {len(movies)} total movies in Radarr")
            
            # Filter for movies with future release dates OR not downloaded yet
            for movie in movies:
                # First check if the movie is already downloaded
                has_file = movie.get('hasFile', False)
                
                # Only include movies that don't have files yet
                if not has_file:
                    # Try to get a release date
                    digital_release = movie.get('digitalRelease')
                    physical_release = movie.get('physicalRelease')
                    in_cinemas = movie.get('inCinemas')
                    
                    # Get the most relevant date
                    if digital_release:
                        release_date = datetime.fromisoformat(digital_release.replace('Z', '+00:00'))
                        release_type = "Digital"
                    elif physical_release:
                        release_date = datetime.fromisoformat(physical_release.replace('Z', '+00:00'))
                        release_type = "Physical"
                    elif in_cinemas:
                        release_date = datetime.fromisoformat(in_cinemas.replace('Z', '+00:00'))
                        release_type = "In Cinemas"
                    else:
                        # If no date, use status and monitored state
                        status = movie.get('status', 'unknown')
                        monitored = movie.get('monitored', False)
                        
                        # For movies with no date but are monitored and announced/released
                        if monitored and status in ['announced', 'released']:
                            release_date = datetime.now()  # Just use current date for sorting
                            release_type = status.capitalize()
                        else:
                            continue  # Skip if no release info and not monitored
                    
                    # Format for UI
                    if hasattr(release_date, 'strftime'):
                        formatted_date = release_date.strftime('%Y-%m-%d')
                    else:
                        formatted_date = "Unknown"
                    
                    upcoming_movies.append({
                        'name': movie['title'],
                        'year': movie['year'],
                        'type': 'movie',
                        'releaseDate': formatted_date,
                        'releaseType': release_type,
                        'artwork_url': f"{RADARR_URL}/api/v3/mediacover/{movie['id']}/poster-500.jpg?apikey={RADARR_API_KEY}",
                        'radarr_movie_url': f"{RADARR_URL}/movie/{movie['titleSlug']}"
                    })
            
            # Log count of upcoming movies found
            logger.info(f"Found {len(upcoming_movies)} upcoming movies")
            
            # Sort by release date
            upcoming_movies.sort(key=lambda x: x['releaseDate'])
            
        return upcoming_movies
    except Exception as e:
        logger.error(f"Error fetching upcoming movies: {str(e)}")
        return []