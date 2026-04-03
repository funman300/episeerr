# Changelog

## v3.6.0 - 2026-04-03

### ⚡ Faster and more reliable
- Episeerr makes far fewer calls to Sonarr during cleanup cycles — less load on your server, faster runs
- External service calls (Sonarr, Plex, Jellyfin, etc.) now automatically retry on hiccups, so a brief blip no longer causes a failed action

### 🗄️ Pending requests no longer lost on restart
- Episode selection requests are now stored in the database instead of temporary files — they survive container restarts and no longer run into file permission errors

---

## v3.5.1 - 2026-03-15

### ⚡ Snappier response on busy setups
- Config and Sonarr tag data are now cached briefly in memory — repeated lookups during webhook activity no longer hit disk or the Sonarr API every time

### 🔧 Drift detection overhauled
- Tag drift correction is now handled in one place across all integrations (Plex, Jellyfin, Emby, Tautulli) — more consistent behavior and fewer edge cases

### 🐛 Fixes
- Jellyseerr requests were being cancelled too early during webhook processing, causing race conditions — auto-delete on webhook removed
- Sonarr webhook was running drift correction twice back-to-back, which could corrupt rule assignments
- Jellyfin and Emby drift corrections were being thrown away before the processing subprocess ran
- Series recovered from orphaned tags now get an activity date set, preventing them from being immediately cleaned up as dormant
- Startup crash when setup page accidentally ran as a hook on every request

---

## v3.5.0 - 2026-03-01

### 🔌 Dispatcharr integration
- Active stream count and queue size shown in dashboard stats
- Live streaming widget shows active sessions with channel, quality, and user info
- Auto-appears in sidebar when configured

### 🎬 Plex native webhook support (no longer requires Tautulli)
- Plex now has its own standalone integration with three detection modes:
  - **Scrobble**: triggers at 90% watched — zero config, most reliable
  - **Stop + Threshold**: triggers when you stop at or past your chosen % (e.g. 50%)
  - **Polling**: background thread checks sessions every N minutes
- Filter by allowed Plex usernames, or leave blank for all users
- "Now Playing" dashboard widget works with all three modes

### 🔀 Tautulli is now optional
- Tautulli moved to its own module and is no longer required if you use Plex
- Enable "Override Plex" in Tautulli settings to use it for watch history instead
- Legacy webhook URL still works — existing setups need no changes
- ⚠️ Don't configure both a Plex webhook and a Tautulli "Watched" webhook — pick one

### 🐛 Fixes
- Plex watchlist: TV shows no longer stuck on "Requested"
- Plex watchlist: TV shows now correctly show as "Watched"
- Plex polling: session matching and threshold triggering improved
- Tautulli: movie detection no longer requires TMDB ID; handles missing fields gracefully
- Jellyfin: PlaybackProgress mode was marking episodes as processed before actually processing them — fixed
- Jellyfin: detection method setup now renders as a dropdown instead of a text field

---

## v3.4.0 - 2026-02-28

### 🔐 Webhook auth bypass
- Jellyfin, Emby, and Jellyseerr webhooks now work correctly when auth is enabled — they no longer get rejected with 401

### 🛠️ Handles Sonarr being offline gracefully
- Episeerr starts up cleanly even if Sonarr is unreachable
- Series and Rules pages show an empty list instead of a server error
- Cleanup scheduler skips silently when Sonarr is down

---

## v3.3.9

### 🐛 Fix
- Webhook processing was crashing on import due to a function that was referenced but never existed — fixed

---

## v3.3.8

### ⚠️ Webhook URLs changed — update your configs
- Jellyfin: `/jellyfin-webhook` → `/api/integration/jellyfin/webhook`
- Emby: `/emby-webhook` → `/api/integration/emby/webhook`
- Jellyseerr: `/seerr-webhook` → `/api/integration/seerr/webhook`

### 🔐 Optional password authentication
- Enable login with `REQUIRE_AUTH`, `AUTH_USERNAME`, `AUTH_PASSWORD` env vars
- Sessions last 24 hours by default; localhost access always works

### 🏗️ Integrations refactored
- Jellyfin, Emby, and Jellyseerr are now self-contained modules — easier to maintain and extend

---

## v3.3.6 - 2026-02-25
- Sidebar rearranged and cleaned up
- Docker integration added — shows running containers in sidebar; can filter by compose/stack

## v3.3.5 - 2026-02-24
- Notification option when episodes have aired but aren't in your library yet
- New Cyber Neon theme

## v3.3.4 - 2026-02-22

### 📌 Always Have — protect specific episodes from cleanup
- Define episodes that should always be present, regardless of rules (e.g. `s1`, `s1e1`, `s1-3`, `s*e1`)
- Protected episodes are never touched by Grace or Keep cleanup; only Dormant can override
- Processed automatically on rule assignment

### 🎬 Series page selection
- Launch the episode selection flow for any existing series directly from the grid or table
- Grab specific seasons/episodes, or just reassign the rule without touching Sonarr

### 🎨 Dashboard widgets
- Plex and Spotify now-playing widgets on the dashboard
- Rule picker on the selection page — pre-selects the current rule, lets you reassign or pick episodes

---

## v3.3.3 - 2026-02-15

### 🎬 Jellyfin detection improved
- Default changed from PlaybackProgress (webhook spam) to Webhook-Triggered Polling — much less noise
- Clear UI with setup instructions for both modes

### 📺 Emby polling improved
- Default poll interval raised to 15 minutes (was 5 seconds) to avoid overloading the server

---

## v3.3.2 - 2026-02-15
- Centralized logging with `LOG_LEVEL` env var (`INFO` default, `DEBUG` for troubleshooting)
- Log rotation added (10MB max, 5 backups)
- Log volume reduced by ~90% — no more "No items in queue" spam every 30 seconds

## v3.3.1 - 2026-02-06
- Cosmetic fixes
- Removed duplicate "recently downloaded" section from dashboard

## v3.3.0 - 2026-02-05

### 🔌 Plugin system (beta)
- Connect additional services to show stats on the dashboard
- Auto-discovery: drop in an integration file and restart
- Included: Radarr, SABnzbd, Prowlarr
- Quick links auto-appear in sidebar when a service is configured

---

## v3.2.0 - 2026-02-04

### 🖥️ Setup page
- Configure all services through the web UI at `/setup` — no more manual `.env` editing
- Emby support added (joins Jellyfin and Plex/Tautulli)
- Quick links to configured services auto-populate in the sidebar
- Existing `.env` files continue to work; database config takes priority when both are present

---

## v3.1.3 - 2026-01-31
- Mobile layout fixes

## v3.1.2 - 2026-01-30
- Series management table now available directly in the Rules tab
- Fixed duplicate episode search bug caused by the `episeerr_default` tag — removed
- Fixed content being hidden behind the sidebar on long pages

## v3.1.1
- **Pilot protection** — option to always keep S01E01, globally or per rule

## v3.1.0

### 📊 Dashboard
- Activity feed, stats, and a 7-day episode calendar (upcoming + recently downloaded)
- Download tracking with a 7-day rolling window

### 📋 Rules page
- Dedicated rules management page with list view on desktop, card layout on mobile

### 🗂️ Series page redesign
- Grid view for browsing, table view for bulk operations, toggle between them
- Sidebar streamlined — no more individual rule listings cluttering navigation

---

## v3.0.0 - 2026-01-25

### 🏷️ Tag system overhaul
- `episeerr_default` tag removed — rule tags are now direct (`episeerr_[rule_name]`)
- Delay profile simplified to two control tags only: `episeerr_select` and `episeerr_delay`

### 🔄 Tag drift detection
- Episeerr automatically detects and corrects when a series tag gets changed in Sonarr
- Runs on watch, cleanup, startup, and when "Clean Config" is clicked
- Orphaned tags (series tagged in Sonarr but not in config) are auto-recovered

### 🧹 Auto-cleanup
- Series deleted from Sonarr are automatically removed from config on startup and during cleanup

---

## v2.9.8 - 2026-01-23
- Orphaned tag recovery on watch webhooks
- All rule name comparisons are now case-insensitive
- Jellyfin configuration detection fixed (env vars now load before being read)

## v2.9.6 - 2026-01-20
- Rule descriptions — optional tooltip text per rule
- Orphaned tag detection runs on startup, cleanup, and "Clean Config"
- Case-insensitive tag matching — prevents false drift detection from Sonarr's lowercasing

## v2.9.5 - 2026-01-19
- Rule tags auto-created in Sonarr when rules are added or deleted
- One-time tag migration syncs all existing series on first startup
- Drift detection triggers on watch events and corrects rule assignments automatically

---

*For older versions, see [legacy changelog](CHANGELOG_OLD.md)*
