# radarr_utils.py
import os
import requests
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration settings from environment variables
RADARR_URL = os.getenv('RADARR_URL')
RADARR_API_KEY = os.getenv('RADARR_API_KEY')

MAX_MOVIES_ITEMS = int(os.getenv('MAX_MOVIES_ITEMS', 24))

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

def fetch_recent_movies(preferences, limit=None):
    """
    Fetch recently downloaded movies from Radarr.
    Returns a list of dictionaries with movie details.
    """
    # Use environment variable if no specific limit is provided
    if limit is None:
        limit = MAX_MOVIES_ITEMS
        
    RADARR_URL = preferences['RADARR_URL']
    RADARR_API_KEY = preferences['RADARR_API_KEY']
    
    movie_url = f"{RADARR_URL}/api/v3/movie"
    headers = {'X-Api-Key': RADARR_API_KEY}
    recent_movies = []
    
    try:
        movie_response = requests.get(movie_url, headers=headers)
        if movie_response.ok:
            movies = movie_response.json()
            
            # Filter for movies that have files (downloaded)
            downloaded_movies = [
                movie for movie in movies 
                if movie.get('hasFile', False) and 
                movie.get('movieFile', {}).get('dateAdded')
            ]
            
            # Sort by dateAdded, newest first
            downloaded_movies.sort(
                key=lambda x: datetime.fromisoformat(
                    x.get('movieFile', {}).get('dateAdded', '').replace('Z', '+00:00')
                ), 
                reverse=True
            )
            
            # Take the most recent movies up to the limit
            for movie in downloaded_movies[:limit]:
                recent_movies.append({
                    'name': movie['title'],
                    'year': movie['year'],
                    'type': 'movie',
                    'artwork_url': f"{RADARR_URL}/api/v3/mediacover/{movie['id']}/poster-500.jpg?apikey={RADARR_API_KEY}",
                    'radarr_movie_url': f"{RADARR_URL}/movie/{movie['titleSlug']}",
                    'releaseDate': datetime.fromisoformat(
                        movie.get('movieFile', {}).get('dateAdded', '').replace('Z', '+00:00')
                    ).strftime('%Y-%m-%d')
                })
            
        return recent_movies
    except Exception as e:
        logger.error(f"Error fetching downloaded movies: {str(e)}")
        return []

def fetch_upcoming_movies(preferences):
    """
    Fetch upcoming movies that are not yet downloaded.
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
            now = datetime.now(timezone.utc)  # Make now timezone-aware
            
            # Include all movies that aren't downloaded yet
            # or have future release dates (even if downloaded)
            for movie in movies:
                # Set a default flag for if we should include this movie
                include_movie = False
                release_type = "Unknown"
                release_date = None
                
                # If the movie isn't downloaded, we want to include it
                if not movie.get('hasFile', False):
                    include_movie = True
                    release_type = "Missing"
                
                # Check various release dates
                release_dates = []
                
                # Process digital release
                if movie.get('digitalRelease'):
                    try:
                        date = datetime.fromisoformat(movie.get('digitalRelease').replace('Z', '+00:00'))
                        release_dates.append(('Digital', date))
                    except (ValueError, AttributeError):
                        pass
                
                # Process physical release
                if movie.get('physicalRelease'):
                    try:
                        date = datetime.fromisoformat(movie.get('physicalRelease').replace('Z', '+00:00'))
                        release_dates.append(('Physical', date))
                    except (ValueError, AttributeError):
                        pass
                
                # Process cinema release
                if movie.get('inCinemas'):
                    try:
                        date = datetime.fromisoformat(movie.get('inCinemas').replace('Z', '+00:00'))
                        release_dates.append(('In Cinemas', date))
                    except (ValueError, AttributeError):
                        pass
                
                # Sort release dates and find the future one to display
                if release_dates:
                    # Sort by date, earliest first
                    release_dates.sort(key=lambda x: x[1])
                    
                    # Find the earliest future date if any
                    future_releases = [(t, d) for t, d in release_dates if d > now]
                    if future_releases:
                        release_type, release_date = future_releases[0]
                        include_movie = True
                    else:
                        # If no future dates but we have dates, use the latest one
                        release_type, release_date = release_dates[-1]
                
                # If we determined this movie should be included
                if include_movie:
                    # If no release date was found but we want to include it
                    if not release_date:
                        release_date = now + timedelta(days=30)
                    
                    upcoming_movies.append({
                        'name': movie['title'],
                        'year': movie['year'],
                        'type': 'movie',
                        'releaseDate': release_date.strftime('%Y-%m-%d'),
                        'releaseType': release_type,
                        'artwork_url': f"{RADARR_URL}/api/v3/mediacover/{movie['id']}/poster-500.jpg?apikey={RADARR_API_KEY}",
                        'radarr_movie_url': f"{RADARR_URL}/movie/{movie['titleSlug']}"
                    })
            
            # Sort by release date
            upcoming_movies.sort(key=lambda x: x.get('releaseDate', ''))
            
        return upcoming_movies
    except Exception as e:
        logger.error(f"Error fetching upcoming movies: {str(e)}")
        return []