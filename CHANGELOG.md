# Changelog

All notable changes to Episeerr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Released]
v2.7.6 is a pure performance/bug fix release:
🎯 One Issue Fixed:

Stopped backing up config files on every read (was happening 100+ times/minute)
Now only backs up when actually saving changes

📉 Impact:

Cleaner logs
Less disk I/O
Same backup protection

This is a "quality of life" release - no new features, just makes the existing system run cleaner! 🚀
Cards will show "No recent activity" until first events occur - this is normal!

Version 2.7.5 - Activity Dashboard Cards
🎨 New Features
Visual Activity Cards

Replaced static statistics cards with dynamic visual activity cards showing recent user activity
Four cards on dashboard:

💾 Disk Usage - Shows current storage usage with link to Sonarr system status
🎬 Last Requested - Displays most recent series request from Jellyseerr/Overseerr with poster
🔍 Last Searched - Shows last episode search triggered by Episeerr with series poster
📺 Last Watched - Displays most recently watched episode with poster and user info


Interactive Cards

All cards are clickable and link to their respective services:

Disk Usage → Sonarr System Status
Last Requested → Jellyseerr/Overseerr
Last Searched → Sonarr Activity Queue
Last Watched → Jellyfin/Tautulli/Plex


Hover effects provide visual feedback
Cards auto-refresh every 60 seconds

Activity Tracking System

New activity storage module (activity_storage.py) logs:

Watch events (series, season, episode, user, timestamp)
Search events (series, season, episode, timestamp)
Request events (title, TMDB ID, timestamp)


Activity data stored in /data/activity/:

watched.json - Last 10 watch events
searches.json - Last 10 search events
last_request.json - Most recent request


Persistent across restarts - activity history preserved

🔧 Technical Improvements
Poster Display

Cards display series posters fetched from:

Sonarr media cover API (watched/searched)
TMDB API (requested)


Automatic fallback to placeholder for missing posters
Optimized poster resolution (w200) for fast loading

Backend Enhancements

Added get_episode_details_by_id() function to fetch episode metadata
Request webhook now fetches TMDB poster path at request time
Activity logging integrated into existing webhook workflows
Watch events logged when episodes are marked as watched
Search events logged when Episeerr triggers Sonarr searches

Time Display

Human-readable timestamps: "5 minutes ago", "2 hours ago", "3 days ago"
Real-time updates as cards refresh

🐛 Bug Fixes

Fixed search event logging crash due to missing function
Fixed poster URL construction for TMDB requests
Improved error handling for missing activity data
Added graceful fallbacks when services are unconfigured

📝 Configuration

No new environment variables required
Uses existing service URLs (SONARR, JELLYSEERR, JELLYFIN, etc.)
Activity tracking works automatically with existing webhooks

💾 Data Storage

Activity data stored in persistent /data volume
Automatic directory creation on first use
No database required - simple JSON file storage
Configurable retention (default: last 10 events for watches/searches)

🎯 User Experience

At-a-glance visibility of recent activity
Quick access to services via clickable cards
Visual context with series posters
No configuration needed - works out of the box

🔄 Backwards Compatibility

Fully compatible with existing Episeerr installations
Old stat cards replaced seamlessly
No breaking changes to existing functionality
Works with all supported media servers (Jellyfin, Plex, Tautulli)

📊 Performance

Lightweight JSON storage
Minimal API calls (only when events occur)
Efficient poster caching via browser
Auto-cleanup of old events (keeps last 10)


Migration Notes

Activity tracking begins immediately after update
Previous activity (before update) will not be shown
Cards will show "No recent activity" until first events occur
No action required from users

Known Limitations

Activity history limited to last 10 events per type
Poster quality optimized for dashboard display (not full resolution)
Request poster requires TMDB API key (already required for Episeerr)

[2.7.4] - 2026-01-06
### Added
- Automatic backup system for configuration files - creates `config.json.bak` and `global_settings.json.bak` on every load
- Quick Links dropdown in navbar for quick access to Sonarr, Plex, and Jellyfin (moved from sidebar)

### Changed
- Moved Quick Links from sidebar card to navbar dropdown to save vertical space on rules index page
- Quick Links now populate from environment variables (SONARR_URL, PLEX_URL, JELLYFIN_URL)

[2.7.3] - 2026-01-05

    fixed duplicate discord notifications 

[2.7.2] - 2026-01-04

    Added 3 types of progress tracking using jellyfin, see documentation
    updated documentation

[2.7.1] - 2026-01-03
Added

    Discord webhook notifications for episode search status
        "Search Pending" notifications when episodes are requested
        Auto-delete notifications when Sonarr successfully grabs episodes
        "Selection Pending" notifications for episeerr_select tagged shows
    Notification storage system for tracking pending Discord messages
    Sonarr "Grab" webhook support for notification cleanup

Changed

    Sonarr webhook handler now processes both SeriesAdd and Grab events
    Streamlined notification approach - only shows failed/pending searches

Fixed

    Jellyfin webhook crash: stop_jellyfin_polling() function signature mismatch
        Function now accepts optional episode_info parameter
        Fixes "takes 1 positional argument but 2 were given" error
        Resolves automation breaking for Jellyfin users on PlaybackStop events

[2.7.0] - 2026-01-02
Added

    Comprehensive documentation page accessible from UI
    CHANGELOG.md for version tracking
    Automated CHANGELOG updates in release script
    Navigation links to docs in navbar and admin panel

Changed

    Cleaned up redundant help text from create/edit rule pages
    Removed large "How It Works" section from admin panel
    Streamlined UI with contextual help links to full docs

Fixed

    HTML layout issues in create_rule template

Added

    Per-season grace period tracking for multi-viewer households
    Grace period scope setting (per-series vs per-season) in rule editor
    Web-based log viewer with filtering, search, and download capabilities
    Auto-submit dropdowns in log viewer (instant filtering)
    Log rotation optimized for mobile viewing (2-5 MB files)
    "Clear Old Logs" feature to remove rotated logs older than 7 days

Changed

    Log rotation limits increased for better history retention
        app.log: 1MB → 2MB
        cleanup.log: 5MB → 2MB
        episeerr.log: 10MB → 5MB
    "View Cleanup Logs" button now opens advanced log viewer
    Migration system auto-adds grace_scope='series' to existing rules

Fixed

    Jellyseerr request files now properly deleted when no episeerr tags are used
    Per-season activity tracking correctly updates season-specific timestamps
    Grace period cleanup functions support both per-series and per-season modes

[2.6.5]
Added

    Sonarr webhook bug fix for Jellyseerr integration
    Improved Jellyseerr request file cleanup
    Better handling of series without episeerr tags

Fixed

    Jellyseerr cleanup moved to top of webhook processing
    Request files no longer orphaned when tags aren't used
    episeerr_default tag processing more reliable


---

## [2.6.0] 

### Added
- Initial stable release
- Episode selection system with multi-season support
- Viewing-based automation for episode management
- Time-based cleanup with dual timer system (grace watched/unwatched, dormant)
- Rule-based automation for different show types
- Webhook integration for Tautulli, Jellyfin, and Sonarr
- Tag-based workflow with Jellyseerr/Overseerr integration
- Scheduler admin panel for monitoring and control
- Global storage gate for cleanup threshold management
- Dry run mode for testing cleanup rules
- Multi-architecture Docker support (amd64, arm64, arm/v7)

### Key Features
- **Three Independent Solutions:**
  1. Manual episode selection across multiple seasons
  2. Viewing-based automation with webhook processing
  3. Time-based cleanup with configurable grace periods

- **Rule System:**
  - Get X episodes/seasons automatically
  - Keep Y episodes/seasons after watching
  - Grace periods for watched/unwatched content
  - Dormant timer for abandoned shows

- **Integration:**
  - Sonarr tag-based workflows (episeerr_default, episeerr_select)
  - Jellyseerr/Overseerr request handling
  - Tautulli/Jellyfin webhook support
  - TMDB API for series metadata

---

## Version Format

- **Stable releases:** `X.Y.Z` (e.g., 2.6.5)
- **Beta releases:** `X.Y.Z-beta.N` or `beta-X.Y.Z` (e.g., 2.6.6-beta.1)
- **Release candidates:** `X.Y.Z-rc.N` (e.g., 2.6.6-rc.1)

---

## Categories

- **Added** - New features
- **Changed** - Changes to existing functionality
- **Deprecated** - Soon-to-be removed features
- **Removed** - Removed features
- **Fixed** - Bug fixes
- **Security** - Vulnerability fixes

---

## Links

- [GitHub Repository](https://github.com/vansmak/episeerr)
- [Docker Hub](https://hub.docker.com/r/vansmak/episeerr)
- [Documentation](https://github.com/vansmak/episeerr#readme)
