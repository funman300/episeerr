// SIMPLE JELLYFIN DASHBOARD - COMPLETE REWRITE
// Simple debug logger
function jfLog(message) {
    console.log(`[JELLYFIN] ${message}`);
  }

// Main initialization function
function initJellyfinDashboard() {
    jfLog("Initializing dashboard");
    
    // Update stats
    updateJellyfinStats();
    
    // Load content rows
    loadJellyfinRecentItems();
    loadJellyfinRecommendations();
    loadJellyfinFavorites();
    
    // Update ticker if function exists
    if (typeof updateTicker === 'function') {
      updateTicker('jellyfin');
    }
  }
  
  // Add event listeners when the DOM is loaded
  document.addEventListener('DOMContentLoaded', function() {
    jfLog("DOM loaded");
    
    // Add click listener to Jellyfin button
    const jellyfinBtn = document.getElementById('use-jellyfin-btn');
    if (jellyfinBtn) {
      jellyfinBtn.addEventListener('click', function() {
        jfLog("Jellyfin button clicked");
      });
    }
    
    // Check for saved preference
    const savedServer = localStorage.getItem('preferredMediaServer');
    if (savedServer === 'jellyfin') {
      jfLog("Saved preference is Jellyfin");
    }
  });
// Simple debug logger
function jfLog(message) {
    console.log(`[JELLYFIN] ${message}`);
  }

  
  // Function to update library stats
  function updateJellyfinStats() {
    jfLog("Updating Jellyfin stats...");
    
    fetch('/api/jellyfin/stats')
      .then(response => response.json())
      .then(data => {
        if (data.success && data.stats) {
          // Update movie count
          const movieCountEl = document.getElementById('jellyfin-library-movies');
          if (movieCountEl) {
            movieCountEl.textContent = data.stats.library_stats.movies || '0';
            jfLog(`Set movies count to: ${movieCountEl.textContent}`);
          }
          
          // Update TV count
          const tvCountEl = document.getElementById('jellyfin-library-tv');
          if (tvCountEl) {
            tvCountEl.textContent = data.stats.library_stats.tv_shows || '0';
            jfLog(`Set TV shows count to: ${tvCountEl.textContent}`);
          }
        }
      })
      .catch(err => {
        console.error("Error fetching Jellyfin stats:", err);
      });
  }
  
  // Function to load recent additions
  function loadJellyfinRecentItems() {
    jfLog("Loading recent additions...");
    
    const container = document.getElementById('jellyfin-recent-additions-row');
    if (!container) {
        console.error("Recent additions container not found!");
        return;
    }
    
    fetch('/api/jellyfin/recent-additions')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.items && data.items.length > 0) {
                container.innerHTML = '';
                data.items.forEach(item => {
                    const mediaItem = document.createElement('article');
                    mediaItem.className = 'media-item';
                    
                    // Get image URL
                    let imageUrl = '/static/placeholder-banner.png';
                    if (item.ImageTags && item.ImageTags.Primary) {
                        imageUrl = `/api/jellyfin/image/${item.Id}/Primary?width=185`;
                    }
                    
                    mediaItem.innerHTML = `
                        <div class="poster-wrapper">
                            <img src="${imageUrl}" alt="${item.Name || 'Media'}" class="poster">
                            <div class="media-info">
                                <p class="media-subtitle">${item.Name || ''}</p>
                                <p class="media-subtitle">${item.ProductionYear || ''}</p>
                            </div>
                        </div>
                    `;
                    
                    container.appendChild(mediaItem);
                });
            } else {
                container.innerHTML = '<div class="alert alert-info">No recent additions found</div>';
            }
        })
        .catch(err => {
            console.error("Error fetching recent items:", err);
            container.innerHTML = '<div class="alert alert-danger">Error loading data</div>';
        });
}
  
  // Function to load recommendations
  function loadJellyfinRecommendations() {
    jfLog("Loading recommendations...");
    
    const container = document.getElementById('jellyfin-recommendations-row');
    if (!container) {
      console.error("Recommendations container not found!");
      return;
    }
    
    // Use TMDB recommendations like in Plex
    Promise.all([
      fetch('/api/tmdb/filtered/movies').then(r => r.json()),
      fetch('/api/tmdb/filtered/tv').then(r => r.json())
    ])
    .then(([moviesData, tvData]) => {
      const movies = moviesData.results || [];
      const shows = tvData.results || [];
      
      // Combine and shuffle
      const combined = [...movies, ...shows];
      const shuffled = combined.sort(() => 0.5 - Math.random());
      
      if (shuffled.length > 0) {
        container.innerHTML = '';
        
        // Only show up to 24 items
        shuffled.slice(0, 24).forEach(item => {
          const mediaItem = document.createElement('article');
          mediaItem.className = 'media-item';
          
          // Determine poster URL
          const posterUrl = item.posterUrl || 
                           (item.poster_path ? `https://image.tmdb.org/t/p/w185${item.poster_path}` : '/static/placeholder-banner.png');
          
          // Determine title and year
          const title = item.title || item.name || 'Unknown';
          const year = item.releaseYear || 
                       (item.release_date ? item.release_date.split('-')[0] : '') ||
                       (item.first_air_date ? item.first_air_date.split('-')[0] : '');
          
          mediaItem.innerHTML = `
            <div class="poster-wrapper">
              <img src="${posterUrl}" alt="${title}" class="poster">
              <div class="media-info">
                <p class="media-subtitle">${title}</p>
                <p class="media-subtitle">${year}</p>
              </div>
            </div>
          `;
          
          container.appendChild(mediaItem);
        });
      } else {
        container.innerHTML = '<div class="alert alert-info">No recommendations available</div>';
      }
    })
    .catch(err => {
      console.error("Error loading recommendations:", err);
      container.innerHTML = '<div class="alert alert-danger">Error loading data</div>';
    });
  }
  
  // Function to load favorites
  function loadJellyfinFavorites() {
    jfLog("Loading favorites...");
    
    const container = document.getElementById('jellyfin-favorites-row');
    if (!container) {
      console.error("Favorites container not found!");
      return;
    }
    
    fetch('/api/jellyfin/favorites')
      .then(response => response.json())
      .then(data => {
        if (data.success && data.items && data.items.length > 0) {
          container.innerHTML = '';
          data.items.forEach(item => {
            const mediaItem = document.createElement('article');
            mediaItem.className = 'media-item';
            
            // Get image URL
            let imageUrl = '/static/placeholder-banner.png';
            if (item.ImageTags && item.ImageTags.Primary) {
              imageUrl = `/api/jellyfin/image/${item.Id}/Primary?width=185`;
            }
            
            mediaItem.innerHTML = `
              <div class="poster-wrapper">
                <img src="${imageUrl}" alt="${item.Name || 'Media'}" class="poster">
                <div class="media-info">
                  <p class="media-subtitle">${item.Name || ''}</p>
                  <p class="media-subtitle">${item.ProductionYear || ''}</p>
                </div>
              </div>
            `;
            
            container.appendChild(mediaItem);
          });
        } else {
          container.innerHTML = '<div class="alert alert-info">No favorites found</div>';
        }
      })
      .catch(err => {
        console.error("Error fetching favorites:", err);
        container.innerHTML = '<div class="alert alert-danger">Error loading data</div>';
      });
  }
  
  