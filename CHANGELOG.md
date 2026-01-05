# Changelog

All notable changes to Episeerr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

[2.7.23] - 2026-01-05

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
