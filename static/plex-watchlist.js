// plex-watchlist.js - Dedicated file for Plex Watchlist functionality

// Utility Functions
function updateConnectionStatus(connected, lastUpdated) {
    console.log(`Updating connection status: ${connected}`);
    const connectionStatus = document.getElementById('connection-status');
    const lastSyncTime = document.getElementById('last-sync-time');
    
    if (connectionStatus) {
        connectionStatus.innerHTML = connected 
            ? '<i class="fas fa-check-circle text-success mr-2"></i> Connected'
            : '<i class="fas fa-times-circle text-danger mr-2"></i> Failed to connect to Plex';
    }
    
    if (lastSyncTime && lastUpdated) {
        const lastUpdate = new Date(lastUpdated);
        lastSyncTime.textContent = `Last synced: ${lastUpdate.toLocaleString()}`;
    }
}

function updateWatchlistNotificationBadge(count) {
    console.log(`Updating watchlist notification badge: ${count}`);
    const badge = document.getElementById('watchlist-notification-badge');
    if (!badge) return;
    
    if (count > 0) {
        badge.textContent = count;
        badge.style.display = 'inline';
    } else {
        badge.style.display = 'none';
    }
}



function showPlexSection(sectionId) {
    console.log("showPlexSection called with:", sectionId);
    
    document.querySelectorAll('.watchlist-subsection').forEach(section => {
        section.style.display = 'none';
    });
    
    const sectionToShow = document.getElementById(sectionId + '-section');
    if (sectionToShow) {
        console.log("Found section to show:", sectionId);
        sectionToShow.style.display = 'block';
    } else {
        console.error("Section not found:", sectionId + '-section');
    }
}

function toggleExcludeItem(itemId, exclude) {
    console.log(`Toggling exclude for item ${itemId}: ${exclude}`);
    fetch('/api/plex/toggle-exclude', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ item_id: itemId, exclude })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert('Failed to update item: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error updating item:', error);
        alert('An error occurred while updating item');
    });
}

function setItemRule(itemId, ruleName) {
    console.log(`Setting rule for item ${itemId}: ${ruleName}`);
    fetch('/api/plex/set-rule', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ item_id: itemId, rule: ruleName })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert('Failed to set rule: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error setting rule:', error);
        alert('An error occurred while setting rule');
    });
}



function loadWatchlistContent() {
    console.log("loadWatchlistContent called");
    
    const tvNotInArrRow = document.getElementById('watchlist-tv-unassigned-row');
    const moviesNotInArrRow = document.getElementById('watchlist-movies-unassigned-row');
    const missingContentRow = document.getElementById('watchlist-missing-row');
    const recentAdditionsRow = document.getElementById('recent-additions-row');
    
    // Set loading indicators
    if (tvNotInArrRow) tvNotInArrRow.innerHTML = '<div class="loading-indicator">Loading missing TV shows...</div>';
    if (moviesNotInArrRow) moviesNotInArrRow.innerHTML = '<div class="loading-indicator">Loading missing movies...</div>';
   
    fetch('/api/plex/watchlist')
    .then(response => response.json())
    .then(data => {
        if (data.success && data.watchlist && data.watchlist.categories) {
            const categories = data.watchlist.categories;
           
            // Update library stats
            updateLibraryStats(data);
           
            // Combine missing TV shows and movies
            const missingContent = [
                ...(categories.tv_not_in_arr || []),
                ...(categories.movie_not_in_arr || [])
            ];
           
            // Render combined missing content
            renderMediaItems(missingContentRow, missingContent, 'missing');
           
            // Load recent additions in a separate API call
            loadRecentAdditions();
           
            updateConnectionStatus(true, data.watchlist.last_updated);
            updateWatchlistNotificationBadge(data.watchlist.count || 0);
           
            // Load recommendations separately
            loadRecommendations();
       
        } else {
            // Error handling - update for the new combined row
            if (missingContentRow) {
                missingContentRow.innerHTML = '<div class="alert alert-warning">Failed to load watchlist</div>';
            }
           
            updateConnectionStatus(false);
        }
    })
    .catch(error => {
        console.error('Error loading watchlist:', error);
       
        // Error handling - update for the new combined row
        if (missingContentRow) {
            missingContentRow.innerHTML = '<div class="alert alert-danger">Error loading watchlist</div>';
        }
       
        updateConnectionStatus(false);
    });
}
// New function to load recent additions
function loadRecentAdditions() {
    const recentAdditionsRow = document.getElementById('recent-additions-row');
    if (!recentAdditionsRow) return;
    
    recentAdditionsRow.innerHTML = '<div class="loading-indicator">Loading recent additions...</div>';
    
    fetch('/api/recent-additions')
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok');
            }
            return response.json();
        })
        .then(data => {
            if (data.success && data.items && data.items.length > 0) {
                renderMediaItems(recentAdditionsRow, data.items, 'recent');
            } else {
                recentAdditionsRow.innerHTML = '<div class="alert alert-info">No recent additions found</div>';
            }
        })
        .catch(error => {
            console.error('Error loading recent additions:', error);
            recentAdditionsRow.innerHTML = `<div class="alert alert-danger">Failed to load recent additions: ${error.message}</div>`;
        });
}
function renderMediaItems(container, items, category) {
    console.log(`Rendering media items for ${category}, Items count: ${items ? items.length : 0}`);
    if (!container) {
        console.error(`Container for ${category} not found`);
        return;
    }
    
    if (!items || items.length === 0) {
        container.innerHTML = `<div class="alert alert-info">No items found</div>`;
        return;
    }
    
    container.innerHTML = '';
    
    items.forEach(item => {
        console.log(`Processing item:`, item); // Log the entire item for debugging
        
        const mediaItem = document.createElement('article');
        mediaItem.className = 'media-item';
        mediaItem.dataset.id = item.id || item.tmdb_id;
        mediaItem.dataset.type = item.type;
        
        // Handle different possible image property names
        let posterUrl = '/static/placeholder-banner.png';
        if (item.posterUrl) {
            posterUrl = item.posterUrl;
        } else if (item.poster_path) {
            posterUrl = `https://image.tmdb.org/t/p/w185${item.poster_path}`;
        } else if (item.artwork_url) {
            posterUrl = item.artwork_url;
        } else if (item.thumb) {
            posterUrl = item.thumb;
        }
        
        // Handle different possible title property names
        const title = item.title || item.name || 'Unknown';
        
        // Handle different possible subtitle/year property names
        const subtitle = item.subtitle || item.year || item.releaseYear || 
                         (item.release_date ? item.release_date.split('-')[0] : '') ||
                         (item.first_air_date ? item.first_air_date.split('-')[0] : '') || '';
        
        mediaItem.innerHTML = `
            <div class="poster-wrapper">
                <img src="${posterUrl}" alt="${title}" class="poster">
                <div class="media-info">
                    <p class="media-subtitle">${title}</p>
                    <p class="media-subtitle">${subtitle}</p>
                </div>
            </div>
        `;
        
        mediaItem.addEventListener('click', () => {
            showWatchlistItemDetails(item, category);
        });
        
        container.appendChild(mediaItem);
    });
}

function showWatchlistItemDetails(item, category) {
    // Handle different possible title property names
    const title = item.title || item.name || 'Unknown';
    
    // Handle different possible subtitle/year property names
    const subtitle = item.subtitle || item.year || item.releaseYear || 
                    (item.release_date ? item.release_date.split('-')[0] : '') ||
                    (item.first_air_date ? item.first_air_date.split('-')[0] : '') || '';
    
    // Handle different possible overview property names
    const overview = item.overview || 'No description available';
    
    // Set modal content
    document.getElementById('detailsTitle').textContent = title;
    document.getElementById('detailsYear').textContent = subtitle;
    document.getElementById('detailsOverview').textContent = overview;
    
    // Handle different possible image property names
    let posterUrl = '/static/placeholder-banner.png';
    if (item.posterUrl) {
        posterUrl = item.posterUrl;
    } else if (item.poster_path) {
        posterUrl = `https://image.tmdb.org/t/p/w300${item.poster_path}`;
    } else if (item.artwork_url) {
        posterUrl = item.artwork_url;
    } else if (item.thumb) {
        posterUrl = item.thumb;
    }
    
    document.getElementById('detailsPoster').src = posterUrl;
    
    // Clear previous footer buttons
    const modalFooter = document.getElementById('detailsModalFooter');
    modalFooter.innerHTML = '';
    
    // Determine actions based on category
    if (category === 'recommendations' || category === 'tmdb' || category === 'missing') {
        // Request button for recommendations or items not in Sonarr/Radarr
        const requestBtn = document.createElement('button');
        requestBtn.className = 'btn btn-primary me-2';
        requestBtn.textContent = `Request ${item.type === 'tv' ? 'Show' : 'Movie'}`;
        requestBtn.addEventListener('click', function() {
            $('#detailsModal').modal('hide');
            if (item.type === 'tv') {
                requestShow(item.id || item.tmdb_id, title);
            } else {
                requestMovie(item.id || item.tmdb_id, title);
            }
        });
        modalFooter.appendChild(requestBtn);
    }
    
    // Show the modal
    $('#detailsModal').modal('show');
}
    
   

// Event Setup Functions
function setupPlexSubmenuListeners() {
    console.log("Setting up Plex submenu listeners");
    
    const viewLink = document.querySelector('.nav-item[onclick*="showPlexSection(\'watchlist-view\')"]');
    const manageLink = document.querySelector('.nav-item[onclick*="showPlexSection(\'watchlist-manage\')"]');
    
    if (viewLink) {
        viewLink.addEventListener('click', function(e) {
            e.preventDefault();
            showPlexSection('watchlist-view');
        });
    }
    
    if (manageLink) {
        manageLink.addEventListener('click', function(e) {
            e.preventDefault();
            showPlexSection('watchlist-manage');
            loadWatchlistManagement();
        });
    }
    
    setupAddRemoveListeners();
}

function setupAddRemoveListeners() {
    console.log("Setting up add/remove listeners");
    
    document.getElementById('add-all-to-watchlist-btn')?.addEventListener('click', function() {
        document.querySelectorAll('input[name="add_to_watchlist"]').forEach(checkbox => {
            checkbox.checked = true;
        });
        document.getElementById('add-to-watchlist-btn')?.click();
    });
    
    document.getElementById('remove-all-from-watchlist-btn')?.addEventListener('click', function() {
        document.querySelectorAll('input[name="remove_from_watchlist"]').forEach(checkbox => {
            checkbox.checked = true;
        });
        document.getElementById('remove-from-watchlist-btn')?.click();
    });
    
    document.getElementById('add-to-watchlist-btn')?.addEventListener('click', addToWatchlist);
    document.getElementById('remove-from-watchlist-btn')?.addEventListener('click', removeFromWatchlist);
}

function addToWatchlist() {
    const selectedItems = Array.from(
        document.querySelectorAll('input[name="add_to_watchlist"]:checked')
    ).map(item => ({
        tmdb_id: item.value,
        type: item.dataset.type
    }));
    
    if (selectedItems.length === 0) {
        alert('Please select items to add to watchlist');
        return;
    }
    
    fetch('/api/plex/sync/add-to-watchlist', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ items: selectedItems })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Items added to watchlist successfully');
            loadWatchlistManagement();
            loadWatchlistContent();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error adding to watchlist:', error);
        alert('Error adding to watchlist');
    });
}

function removeFromWatchlist() {
    const selectedItems = Array.from(
        document.querySelectorAll('input[name="remove_from_watchlist"]:checked')
    ).map(item => ({
        tmdb_id: item.value,
        type: item.dataset.type
    }));
    
    if (selectedItems.length === 0) {
        alert('Please select items to remove from watchlist');
        return;
    }
    
    fetch('/api/plex/sync/remove-from-watchlist', {
        method: 'POST',
        headers: {'Content-Type': 'application/json',
},
        body: JSON.stringify({ items: selectedItems })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Items removed from watchlist successfully');
            loadWatchlistManagement();
            loadWatchlistContent();
        } else {
            alert('Error: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Error removing from watchlist:', error);
        alert('Error removing from watchlist');
    });
}

function initPlexWatchlist() {
    console.log("Initializing Plex Watchlist");
    
    if (!document.getElementById('plex-tab')) return;
    
    const syncButton = document.getElementById('sync-plex-btn');
    const autoDownloadToggle = document.getElementById('auto-download-toggle');
    
    if (syncButton) {
        syncButton.addEventListener('click', syncPlexWatchlist);
    }
    
    if (autoDownloadToggle) {
        autoDownloadToggle.addEventListener('change', toggleAutoDownload);
    }
    
    setupPlexSubmenuListeners();

    // Initialize the Plex ticker
    updateTicker('plex');
    
    // Initial load of content
    loadWatchlistContent();
    loadRecommendations();
}


function updateLibraryStats(data) {
    console.log("Updating library stats with:", data);
    
    try {
        // Find the span elements directly
        const libraryMoviesSpan = document.getElementById('library-movies');
        const libraryTvSpan = document.getElementById('library-tv');
        const watchlistMoviesSpan = document.getElementById('watchlist-movies');
        const watchlistTvSpan = document.getElementById('watchlist-tv');
        
        // Log what we found
        console.log("library-movies element:", libraryMoviesSpan);
        console.log("library-tv element:", libraryTvSpan);
        console.log("watchlist-movies element:", watchlistMoviesSpan);
        console.log("watchlist-tv element:", watchlistTvSpan);
        
        // Check if stats data structure is as expected
        if (data.watchlist && data.watchlist.stats) {
            // Update if elements exist
            if (libraryMoviesSpan) {
                libraryMoviesSpan.textContent = data.watchlist.stats.library_stats.movies || 0;
                console.log("Updated library-movies to:", data.watchlist.stats.library_stats.movies);
            }
            
            if (libraryTvSpan) {
                libraryTvSpan.textContent = data.watchlist.stats.library_stats.tv_shows || 0;
                console.log("Updated library-tv to:", data.watchlist.stats.library_stats.tv_shows);
            }
            
            if (watchlistMoviesSpan) {
                watchlistMoviesSpan.textContent = data.watchlist.stats.watchlist_stats.movies || 0;
                console.log("Updated watchlist-movies to:", data.watchlist.stats.watchlist_stats.movies);
            }
            
            if (watchlistTvSpan) {
                watchlistTvSpan.textContent = data.watchlist.stats.watchlist_stats.tv_shows || 0;
                console.log("Updated watchlist-tv to:", data.watchlist.stats.watchlist_stats.tv_shows);
            }
        } else {
            console.error("Data structure doesn't contain the expected 'watchlist.stats' path:", data);
        }
    } catch (error) {
        console.error("Error updating library stats:", error);
        console.error(error.stack);
    }
}
function syncPlexWatchlist() {
    console.log("Syncing Plex Watchlist");
    const syncButton = document.getElementById('sync-plex-btn');
    const connectionStatus = document.getElementById('connection-status');
    
    if (syncButton) {
        syncButton.disabled = true;
        syncButton.textContent = 'Syncing...';
    }
    
    if (connectionStatus) {
        connectionStatus.innerHTML = '<i class="fas fa-sync fa-spin mr-2"></i> Syncing watchlist...';
    }
    
    fetch('/api/plex/sync', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            loadWatchlistContent();
            loadRecommendations(); 
        } else {
            alert('Failed to sync watchlist: ' + data.message);
            updateConnectionStatus(false);
        }
    })
    .catch(error => {
        console.error('Error syncing watchlist:', error);
        alert('An error occurred while syncing watchlist');
        updateConnectionStatus(false);
    })
    .finally(() => {
        if (syncButton) {
            syncButton.disabled = false;
            syncButton.textContent = 'Sync Watchlist';
        }
    });
}
// Modified to use existing TMDB popular content
function loadRecommendations() {
    const recommendationsRow = document.getElementById('plex-recommendations-row');
    if (!recommendationsRow) return;
    
    recommendationsRow.innerHTML = '<div class="loading-indicator">Loading recommendations...</div>';
    
    // Fetch both popular movies and TV shows from TMDB
    Promise.all([
        fetch('/api/tmdb/filtered/movies').then(res => res.json()),
        fetch('/api/tmdb/filtered/tv').then(res => res.json())
    ])
    .then(([moviesData, tvData]) => {
        // Combine the results
        const combinedResults = [
            ...(moviesData.results || []), 
            ...(tvData.results || [])
        ];
        
        // Shuffle the array to mix movies and TV shows
        const shuffledResults = shuffleArray(combinedResults);
        
        // Take a limited number to display
        const displayResults = shuffledResults.slice(0, 24);
        
        if (displayResults.length > 0) {
            renderMediaItems(recommendationsRow, displayResults, 'tmdb');
        } else {
            recommendationsRow.innerHTML = '<div class="alert alert-warning">No recommendations available</div>';
        }
    })
    .catch(error => {
        console.error('Error loading recommendations:', error);
        recommendationsRow.innerHTML = '<div class="alert alert-danger">Error loading recommendations</div>';
    });
}

// Helper function to shuffle an array
function shuffleArray(array) {
    const newArray = [...array];
    for (let i = newArray.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [newArray[i], newArray[j]] = [newArray[j], newArray[i]];
    }
    return newArray;
}

function toggleAutoDownload() {
    console.log("Toggling Auto Download");
    const autoDownloadToggle = document.getElementById('auto-download-toggle');
    if (!autoDownloadToggle) return;
    
    const enabled = autoDownloadToggle.checked;
    
    fetch('/api/plex/toggle-auto-download', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ enabled })
    })
    .then(response => response.json())
    .then(data => {
        if (!data.success) {
            alert('Failed to update auto-download setting: ' + data.message);
            autoDownloadToggle.checked = !enabled;
        }
    })
    .catch(error => {
        console.error('Error updating auto-download setting:', error);
        alert('An error occurred while updating auto-download setting');
        autoDownloadToggle.checked = !enabled;
    });
}



// Document Ready Event
document.addEventListener('DOMContentLoaded', function() {
    console.log("Document loaded, initializing Plex Watchlist");
    initPlexWatchlist();
    showPlexSection('watchlist-view');
});