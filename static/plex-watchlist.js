// plex-watchlist.js - Dedicated file for Plex Watchlist functionality

// Utility Functions
function updateConnectionStatus(connected, lastUpdated) {
    console.log(`Updating connection status: ${connected}`);
    const connectionStatus = document.getElementById('connection-status');
    const lastSyncTime = document.getElementById('last-sync-time');
    
    if (connectionStatus) {
        connectionStatus.innerHTML = connected 
            ? '<i class="fas fa-check-circle text-success mr-2"></i> Connected to Plex'
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
   
    // Set loading indicators
    if (tvNotInArrRow) tvNotInArrRow.innerHTML = '<div class="loading-indicator">Loading missing TV shows...</div>';
    if (moviesNotInArrRow) moviesNotInArrRow.innerHTML = '<div class="loading-indicator">Loading missing movies...</div>';
   
    fetch('/api/plex/watchlist')
        .then(response => {
            console.log("Watchlist API response received:", response.status);
            return response.json();
        })
        .then(data => {
            console.log("Watchlist data:", data);
            if (data.success && data.watchlist && data.watchlist.categories) {
                const categories = data.watchlist.categories;
                for (const [key, items] of Object.entries(categories)) {
                    console.log(`Category: ${key}, Items: ${items.length}`);
                    console.log(items);
                }
            
                // Update library stats
                updateLibraryStats(data);
                
                // Render unassigned TV shows
                renderMediaItems(tvNotInArrRow, categories.tv_not_in_arr || [], 'tv_not_in_arr');
                
                // Render unassigned movies
                renderMediaItems(moviesNotInArrRow, categories.movie_not_in_arr || [], 'movie_not_in_arr');
                
                updateConnectionStatus(true, data.watchlist.last_updated);
                updateWatchlistNotificationBadge(data.watchlist.count || 0);
                
                // Load recommendations separately
                loadRecommendations();
            } else {
                // Error handling
                const rows = [tvNotInArrRow, moviesNotInArrRow];
                
                rows.forEach(row => {
                    if (row) row.innerHTML = '<div class="alert alert-warning">Failed to load watchlist</div>';
                });
                
                updateConnectionStatus(false);
            }
        })
        .catch(error => {
            console.error('Error loading watchlist:', error);
            
            const rows = [tvNotInArrRow, moviesNotInArrRow];
            
            rows.forEach(row => {
                if (row) row.innerHTML = '<div class="alert alert-danger">Error loading watchlist</div>';
            });
            
            updateConnectionStatus(false);
        });
}

function renderMediaItems(container, items, category) {
    console.log(`Rendering media items for ${category}, Items count: ${items ? items.length : 0}`);
    if (!container) {
        console.error(`Container for ${category} not found`);
        return;
    }
    
    // Debug - log the container
    console.log("Container:", container);
    
    if (!items || items.length === 0) {
        container.innerHTML = `<div class="alert alert-info">No items found</div>`;
        return;
    }
    
    container.innerHTML = '';
    
    items.forEach(item => {
        console.log(`Processing item: ${item.title}, Type: ${item.type}, TMDB ID: ${item.tmdb_id}`);
        
        const mediaItem = document.createElement('article');
        mediaItem.className = 'media-item';
        mediaItem.dataset.id = item.tmdb_id;
        mediaItem.dataset.type = item.type;
        
        const posterUrl = item.poster_path 
            ? `https://image.tmdb.org/t/p/w185${item.poster_path}` 
            : (item.thumb || '/static/placeholder-poster.png');
        
        mediaItem.innerHTML = `
            <div class="poster-wrapper">
                <img src="${posterUrl}" alt="${item.title}" class="poster">
                <div class="media-info">
                    <h4 class="media-title">${item.title}</h4>
                    <p class="media-subtitle">${item.year || ''}</p>
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
    // Set modal content
    document.getElementById('detailsTitle').textContent = item.title;
    document.getElementById('detailsYear').textContent = item.year || '';
    document.getElementById('detailsOverview').textContent = item.overview || 'No description available';
    
    // Set poster
    const posterUrl = item.poster_path 
        ? `https://image.tmdb.org/t/p/w300${item.poster_path}` 
        : (item.thumb || '/static/placeholder-poster.png');
    document.getElementById('detailsPoster').src = posterUrl;
    
    // Clear previous footer buttons
    const modalFooter = document.getElementById('detailsModalFooter');
    modalFooter.innerHTML = '';
    
    // Determine actions based on category
    if (category === 'recommendations' || category.includes('not_in_arr')) {
        // Request button for recommendations or items not in Sonarr/Radarr
        const requestBtn = document.createElement('button');
        requestBtn.className = 'btn btn-primary me-2';
        requestBtn.textContent = `Request ${item.type === 'tv' ? 'Show' : 'Movie'}`;
        requestBtn.addEventListener('click', function() {
            $('#detailsModal').modal('hide');
            if (item.type === 'tv') {
                requestShow(item.id || item.tmdb_id, item.title);
            } else {
                requestMovie(item.id || item.tmdb_id, item.title);
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
function loadRecommendations() {
    console.log("Loading recommendations");
    
    const recommendationsRow = document.getElementById('plex-recommendations-row');
    if (!recommendationsRow) return;
    
    recommendationsRow.innerHTML = '<div class="loading-indicator">Loading recommendations...</div>';
    
    // In loadRecommendations() function in plex-watchlist.js
    fetch('/api/plex/recommendations')
        .then(response => response.json())
        .then(data => {
            console.log("Recommendations data:", data); // Add this line
            if (data.success) {
                renderMediaItems(recommendationsRow, data.recommendations, 'recommendations');
            } else {
                recommendationsRow.innerHTML = '<div class="alert alert-warning">Failed to load recommendations</div>';
            }
        })
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