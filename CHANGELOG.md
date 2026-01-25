# Changelog

All notable changes to Episeerr will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [Released]
## [3.0.0] - 2026-01-25

### Major UI Redesign
- **Sonarr-style sidebar navigation** - Persistent on desktop, slide-in on mobile
- **Poster grid view** - 2-8 responsive columns with lazy loading
- **Grid/Table toggle** - Switch between poster and table views
- **4 theme options** - Default Dark, Night Owl, Nord, Light Breeze
- **Mobile improvements** - Logo as hamburger button, better responsive layout
- **Rules in sidebar** - Quick access with series counts and default indicator
- **System links** - Collapsible section for Sonarr, Jellyseerr, Jellyfin, etc.

### Technical
- Client-side filtering and sorting
- State persistence (view preference, theme, collapse states)
- Converted jQuery to vanilla JavaScript
- No breaking changes to Flask routes or data structure

### Files Changed
- `templates/base.html` - New sidebar layout
- `templates/rules_index.html` - Grid/table series view
- `templates/episeerr_index.html` - Vanilla JS conversion
- `static/sidebar.css` - Complete theme system
- `episeerr.py` - Added `/api/rules-list` endpoint

---

## [2.9.8] - 2026-01-23

### Added
- **Auto-cleanup of deleted series**: Series removed from Sonarr are automatically cleaned from config during startup/drift detection
- **Smart Jellyfin mode detection**: Auto-detects Option 1/2/3 from environment variables - no manual `JELLYFIN_DISABLE_ACTIVE_POLLING` needed
- **Webhook string/integer tag handling**: SeriesAdd webhooks now handle both tag labels (strings) and IDs (integers) via reverse mapping
- **Enhanced documentation**: Dark mode support, reorganized sections (Examples under Rules, FAQ under Troubleshooting), improved navigation

### Changed
- **Delay profile simplification**: Now contains only 3 control tags (default, select, delay) - rule tags no longer added
- **404 error handling**: Series not found (404) logged as DEBUG instead of ERROR - reduces log noise
- **Log clarity improvements**: "already processed (no control tags)" replaces "no episeerr tags" for clearer messaging
- **Grace cleanup loop**: Series marked as `grace_cleaned` only re-enters loop after watch activity

### Fixed
- **Tag removal in webhooks**: Now correctly converts tag labels to IDs before API calls - prevents "tag not found" errors
- **Series safety check**: Always fetches full series object before updates to prevent race conditions
- **Jellyfin polling in Option 1**: Systems with TRIGGER_MIN/MAX and no POLL_INTERVAL no longer run unnecessary polling

### Technical Details
- Tag mapping: Maintains bidirectional label↔ID mapping for webhook compatibility
- Cleanup flags: `grace_cleaned` flag prevents redundant daily checks until next watch event
- 404 handling: Graceful removal from config with summary count in reconciliation logs
- Jellyfin detection: Inspects env vars to determine mode without manual override

### Migration Notes
- **Automatic**: No user action required
- **Sonarr delay profile**: May show extra rule tags briefly - these will be cleaned on next startup
- **Jellyfin Option 1 users**: Polling auto-disables after container restart
- **Documentation updates**: Restart container to see updated UI documentation

[2.9.7] - 2026-01-21
Added

Orphaned tag detection in watch webhooks: Series with episeerr tags but not in config are automatically added when watched

Enables fully tag-based workflow - tag shows in Sonarr, watch episodes, Episeerr picks them up
Complements existing startup/cleanup orphaned detection



Fixed

Case-sensitivity in drift detection: move_series_in_config() now uses case-insensitive rule lookups

Prevents errors when tag case doesn't match config rule case
Completes case-insensitive tag matching from 2.9.6


Jellyfin configuration detection: Moved load_dotenv() before environment variable reads in media_processor

Fixes "Jellyfin not configured" error when env vars are actually set
Ensures active polling starts correctly


Sonarr webhook rule assignment: New series with episeerr tags now use case-insensitive rule matching

Tag episeerr_One_At_A_Time correctly matches rule one_at_a_time



Technical Details

Watch webhooks now perform full tag reconciliation (drift + orphaned detection)
All rule name comparisons system-wide are now case-insensitive
Environment variables load before being accessed in media_processor.py

Migration Notes

Fully automatic - no user action required
Users with Jellyfin will need to restart for configuration fix to take effect

## [2.9.6] - 2026-01-20

### Added
- **Rule descriptions**: Optional description field for rules to document their purpose
  - Appears as tooltip when hovering over rule name
  - Helps organize and understand multiple rules
- **Orphaned tag detection**: Finds shows with episeerr tags but not in config, adds them automatically
  - Runs on startup
  - Runs during cleanup cycles  
  - Runs when "Clean Config" button clicked
  - Allows tag-based management entirely through Sonarr
- **Enhanced drift detection**: Now runs in multiple locations
  - Detects during watch webhooks (existing)
  - Detects during startup (new)
  - Detects during cleanup cycles (new)
  - Detects during "Clean Config" button (new)

### Changed
- **Case-insensitive tag matching**: Sonarr lowercases all tags internally
  - All tag comparisons now case-insensitive
  - Prevents false drift detection from case differences
  - Rule names can use any case (Get1keepseason vs get1keepseason)

### Fixed
- **False drift detection** from Sonarr's tag lowercasing behavior
- **Case-sensitivity bugs** in drift detection and rule lookups
- **Description field** now saves properly in create/edit rule forms
- **Notification import** errors in webhook processing

### Technical Details
- Comprehensive tag reconciliation runs on startup (create, migrate, drift, orphaned in single pass)
- Orphaned tag detection integrated into cleanup cycles
- All rule name lookups now case-insensitive
- Description field added to rule schema (optional, max 200 chars recommended)

### Migration Notes
- Fully automatic - no user action required
- Rule descriptions will be blank for existing rules (optional field)
- Orphaned shows will be automatically discovered and added to matching rules
- Case variations in rule names will be handled transparently

## [2.9.5] - 2026-01-19

### Added
- **Automatic tag system**: Rule-specific tags (`episeerr_<rulename>`) auto-created in Sonarr
- **Tag migration**: One-time bulk sync applies tags to all existing series on first startup
- **Drift detection**: Auto-corrects when tags manually changed in Sonarr
  - Detects tag changes during watch webhooks (Jellyfin/Tautulli)
  - Moves series to correct rule in config automatically
  - Syncs missing tags back to Sonarr
- **Delay profile integration**: Automatically manages episeerr tags in Sonarr delay profiles
  - Finds existing custom delay profile with episeerr tags
  - Adds/removes rule tags when rules created/deleted
  - Always preserves `episeerr_default` and `episeerr_select` tags

### Changed
- Rule creation/deletion now manages tags automatically in Sonarr and delay profiles
- Tags removed from series and Sonarr when rules deleted

### Fixed
- Config parameter passing in delay profile functions
- Import statements for tag functions across modules

### Technical Details
- Tag functions centralized in `episeerr_utils.py`
- Drift detection in `media_processor.py` webhook processing
- Migration controlled by `tag_migration_complete` flag in config
- Delay profile managed via `delay_profile_migrated` flag

### Migration Notes
- Fully automatic - no user action required
- First startup: creates all rule tags, syncs to series, updates delay profile
- Existing delay profile with episeerr tags will be detected and used
- Tags in Sonarr will match rules in Episeerr config automatically

## [2.9.2] - 2026-01-18

### Documentation

**Major documentation restructure v2.0** - Complete reorganization for clarity and discoverability

#### Added
- **New folder structure**: Organized into getting-started, core-concepts, features, configuration, guides, troubleshooting, reference
- **[Deletion System Guide](docs/core-concepts/deletion-system.md)**: Comprehensive explanation of Keep vs Grace vs Dormant with bookmark system
- **[Tags & Auto-Assign Guide](docs/core-concepts/tags-and-auto-assign.md)**: Clear explanation of `episeerr_default` and `episeerr_select` tag behavior
- **[Quick Start Guide](docs/getting-started/quick-start.md)**: Get running in 5 minutes
- **[First Series Tutorial](docs/getting-started/first-series.md)**: Step-by-step walkthrough for beginners
- **[Rules Explained](docs/core-concepts/rules-explained.md)**: Conceptual guide to GET/KEEP/Action settings
- **[Webhooks Explained](docs/core-concepts/webhooks-explained.md)**: Why webhooks exist and how they work
- **Learning paths**: Different guides for different user types (new users, power users, specific features)

#### Changed
- **Main README.md**: Streamlined with better navigation and links to full documentation
- **Documentation index**: `docs/README.md` now serves as comprehensive navigation hub
- **File organization**: Moved all docs into logical folders with clear naming
- **Content consolidation**: One authoritative source per topic, eliminated duplication

#### Fixed
- **Tag confusion**: Clearly documented that tags are temporary signals, not permanent labels
- **Deletion confusion**: Comprehensive guide explains bookmark system and when deletions happen
- **"Tag disappeared" issue**: Documentation now explains this is normal and expected behavior

#### Improved
- Clear separation between concepts and how-to guides
- Better cross-linking between related topics
- Consistent formatting across all documentation
- Improved discoverability with table of contents and quick links

### Bug Fixes
- Fixed duplicate dry run check in `delete_episodes_in_sonarr_with_logging()`

### Repository Cleanup
- Removed `data/activity/` files from git tracking
- Updated `.gitignore` to exclude data, logs, config, and temp folders
- Cleaned up accidentally committed runtime data

## [2.9.1] - 2026-01-17
### Changed - BREAKING
- **Grace Periods reimagined as Bookmark System** for inactive shows
  - Grace Watched: Keeps last watched episode as reference point, deletes older watched episodes
  - Grace Unwatched: Keeps first unwatched episode as bookmark, deletes extra unwatched episodes
  - Result: Maximum 2 episodes per inactive show (last watched + next unwatched)
  - Grace cleanup no longer applies Get rule - Get rule only runs on watch webhooks

### Added
- **grace_cleaned flag**: Prevents repeated processing of already-bookmarked shows
- **Grab webhook support**: Series marked as cleaned when new episodes grabbed
- **Smart cleanup loop**: Shows missing next episodes stay in cleanup until grab webhook fires
- **Master safety switch**: Global dry_run_mode always overrides rule-level settings
- **Sonarr Grab event handling**: Stops checking loop for incomplete series when content becomes available

### Fixed
- Grace cleanup no longer re-downloads same episodes every 5 days
- Incomplete series properly handled - keeps checking until content available
- Master dry_run_mode setting now cannot be overridden by individual rules
- Storage savings: Inactive shows reduced to 1-2 episodes instead of full seasons

### Technical Details
**Grace Bookmark Philosophy:**
- Watched: Delete all except last watched (keeps reference point for catch-up)
- Unwatched: Delete all except first unwatched (keeps bookmark for resume)
- Ignores Keep/Get rules during cleanup (those only apply during active watching)
- Marks series as "cleaned" when bookmarks established
- Stops processing until activity resumes

**Cleanup Loop Behavior:**
- Has bookmark → Mark grace_cleaned=true → Skip on future cleanups
- Missing bookmark → grace_cleaned=false → Check every cleanup cycle
- Watch webhook → Clear grace_cleaned=false → Re-enter grace period after inactivity
- Grab webhook → Set grace_cleaned=true → Exit checking loop

**Webhooks Required:**
- Watch webhook (Tautulli/Jellyfin): Updates activity_date, clears grace_cleaned flag
- Grab webhook (Sonarr): Sets grace_cleaned flag to stop checking loop

**Master Safety:**
- Global dry_run_mode=true: ALL deletions forced to pending queue regardless of rule settings
- Rule dry_run=true: That specific rule uses pending queue  
- Rule dry_run=false + Global=false: Direct deletion allowed

### Migration Notes
- Configure Sonarr webhook to include "On Grab" event in addition to "On Series Add"
- grace_cleaned field will be added automatically to config.json as series are processed
- Highly recommended: Set dry_run_mode: true in global settings during initial testing
- After grace runs: Each show has 1-2 episodes (reference + bookmark)
- Missing episodes: Series stays in cleanup loop until Sonarr grabs the content

### Example Scenarios
**Complete Series (Countdown):**
```
Initial: S1E1-S1E13 (13 episodes)
After Grace Cleanup:
  - S1E1 (last watched - your reference point)
  - S1E2 (first unwatched - your bookmark)
  - grace_cleaned = true
Result: Won't process again until you watch S1E2
Space Saved: 11 episodes
```

**Incomplete Series (Stranger Things):**
```
Initial: S5E1-S5E4 watched, no S5E5 available yet
After Grace Cleanup:
  - S5E4 (last watched - your reference point)
  - No unwatched exists
  - grace_cleaned = false
Result: Checks every cleanup cycle
When S5E5 grabbed: grace_cleaned = true, stops checking
Space Saved: 3 episodes
```

**Active Series Returns:**
```
You watch S1E2 (webhook fires)
  → grace_cleaned = false
  → Get rule applies: Gets S1E3
  → After 5 days inactive: Grace cleanup runs again
  → Bookmarks to S1E2 + S1E3
  → grace_cleaned = true
```

## [2.9.0] - 2026-01-16

### Changed - BREAKING
- **Grace Periods now override Keep/Get settings** for maximum flexibility
  - Grace Watched: Deletes ALL watched episodes after inactivity (keeps position in config only)
  - Grace Unwatched: Deletes unwatched episodes after deadline (keeps next episode file as resume point)
  - Both preserve your position so you can resume anytime

### Added
- **Position preservation**: Grace Watched keeps last_season/last_episode in config (no file kept)
- **Resume point file**: Grace Unwatched keeps the next unwatched episode file on disk
- **Auto-resume for mid-season breaks**: Grace Watched simulates watch event during cleanup to check for new episodes
- **Smart cleanup**: When cleanup runs, checks if new episodes exist and monitors them automatically

### Fixed
- Grace periods now truly independent of Keep/Get settings
- Mid-season breaks no longer lose your position
- Can resume shows months later without manual intervention

### Technical Details
- Grace Watched: Deletes all watched files, simulates last watched episode during cleanup
- Grace Unwatched: Sorts unwatched episodes, keeps first one, deletes rest
- Position data persists in config even when episode files are deleted
- Cleanup simulation triggers Get rule to check for new episodes in Sonarr

### Migration Notes
- Existing grace periods will use new behavior automatically
- No config changes needed
- Test with dry run first to see new deletion patterns
- After grace cleanup: watched files deleted (position kept), 1 unwatched file remains

## [2.8.0] - 2026-01-15

### Added
- **Pending Deletions System**: Comprehensive approval queue for all cleanup operations
  - All deletions now queue for review before execution when dry run is enabled
  - Hierarchical organization: Series → Season → Episode
  - Multiple approval levels: individual episodes, entire seasons, whole series, or bulk selection
  - Rejection cache: Rejected episodes won't reappear for 30 days
  - Enhanced logging with detailed deletion reports showing:
    - Reason for deletion (Grace Period, Keep Rule, Dormant Series, etc.)
    - Data source (Tautulli watch history vs Sonarr air date)
    - Date value used in decision
    - Rule name that triggered the deletion
    - File size to be reclaimed
  - Real-time notification badge showing combined pending requests + pending deletions
  - New `/pending-deletions` page with collapsible series/season view
  - API endpoints for programmatic access to pending deletions queue

### Changed
- **Dry Run Mode now enabled by default** for all new installations
  - Provides safety net against accidental mass deletions
  - Existing installations require manual migration (add `dry_run_mode: true` to `global_settings.json`)
  - Can be configured globally (Admin → Scheduler) or per-rule (Admin → Dry Run Settings)
- **Navigation updated**: "Pending Requests" renamed to "Pending" 
  - Now serves as unified entry point for both episode selection requests and pending deletions
  - Badge shows combined count of both pending items
- **Unified Pending Page**: Enhanced to show both episode selection requests and deletion queue
  - Tab-free design with separate cards for each type
  - Summary cards show quick stats and link to detailed views

### Fixed
- Improved deletion logic to prevent edge cases in multi-viewer households
- Enhanced error handling in cleanup operations
- Better context tracking for why episodes are targeted for deletion

### Technical Details
- New `pending_deletions.py` module for queue management
- New `pending_deletions.html` template with Bootstrap accordion interface
- Storage-efficient rejection cache using episode ID + expiry date pairs
- Migration system auto-adds `dry_run_mode` field to existing `global_settings.json`
- Backward compatible - existing cleanup behavior unchanged if dry run disabled

### Migration Notes
- **Existing users**: Dry run mode is NOT enabled automatically
  - To enable: Admin → Scheduler → Check "Global Dry Run Mode" → Save
  - Or manually add `"dry_run_mode": true` to `config/global_settings.json`
- **New users**: Dry run enabled by default, deletions require approval
- All pending deletions data stored in `data/pending_deletions.json`
- Rejection cache stored in `data/deletion_rejections.json`

### Documentation
- Added comprehensive "Pending Deletions" section to built-in documentation
- Updated FAQ with 5 new entries about the approval system
- Added troubleshooting guides for common pending deletion scenarios
- Updated installation guides to mention dry run default behavior
Version 2.7.9 - Season Pack Preference

### Features
- **Season Pack Preference**: Rules using "Get X seasons" now automatically prefer season packs over individual episodes when searching
  - Sonarr searches for season packs first, falls back to individual episodes if no pack available
  - Applies to both watched episodes (webhooks) and newly added series (Jellyseerr)
  - Episode-based rules continue to work exactly as before

### Fixes
- Fixed documentation: Tautulli webhook URL is `/webhook` (not `/tautulli-webhook`)

### Technical Details
- When `get_type: 'seasons'`, uses Sonarr's `SeasonSearch` command instead of `EpisodeSearch`
- Backward compatible - all existing rules continue to work unchanged

v2.7.8 
Cosmetic fixes
v2.7.7
Removed disk stats because its in ADMIN
Cleaner interface with 3 cards
🎬 Last Requested - Displays most recent series request from Jellyseerr/Overseerr with poster
🔍 Last Searched - Shows last episode search triggered by Episeerr with series poster
📺 Last Watched - Displays most recently watched episode with poster and user info

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
