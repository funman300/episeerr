# OCDarr: Smart Episode Management for Sonarr

<img src="static/logo_icon.png" alt="OCDarr" width="120" align="right"/>

**Intelligent, time-aware episode management** that responds to your viewing habits and automatically maintains your library based on activity patterns.

## What OCDarr Does

OCDarr automatically manages your TV episodes based on **your viewing activity and time-based rules**. Watch an episode, and OCDarr intelligently prepares what you want next while cleaning up what you've already seen - with smart cleanup timers that adapt to your viewing patterns.

### 🎯 **Perfect For:**
- Users who **don't rewatch** episodes but want the next one ready
- People who prefer a **curated, organized** library over massive collections
- Anyone wanting **different management strategies** for different shows
- Users who value **automation with intelligent cleanup**
- Shows with **different viewing cadences** (daily, weekly, seasonal)

### 🚫 **Not For:**
- Digital hoarders who want to keep everything forever
- Users who rewatch content frequently
- Large household servers with multiple users at different points in series

---

## 🔧 How It Works

### **Two-Layer System:**

**🚀 Webhook Layer (Instant):** Responds to viewing activity
- Tracks what you watched and when
- Prepares next episodes immediately
- Fast response, no delays

**⏰ Scheduler Layer (Periodic):** Handles time-based cleanup  
- Surgical cleanup for active shows (maintains viewing continuity) 
- Nuclear cleanup for abandoned shows (reclaims storage)
- Runs every 6 hours (configurable)

### **Rule Components:**

Each rule defines exactly how episodes are handled:



| Component | Purpose | Examples |
|-----------|---------|----------|
| **Get Option** | How many upcoming episodes to prepare | `1` (next episode), `season` (full season), `all` (everything) |
| **Action Option** | How episodes are handled | `monitor` (passive), `search` (active download) |
| **Keep Watched** | What to retain as a "keep block" | `1` (last episode), `season` (current season), `all` (everything) |
| **Monitor Watched** | Track episodes after watching | `true` (keep monitoring), `false` (auto-unmonitor) |
| **Grace Period** | Days after watching before surgical cleanup | `7` (cleanup after 1 week), `null` (never) |
| **Abandonment Timer** | Days without activity before nuclear cleanup | `90` (abandon after 3 months), `null` (never) |

> **🎛️ Control Choice:** OCDarr only manages series with assigned rules. Want to keep a show exactly as Sonarr handles it by default? Simply don't assign it to any rule - OCDarr will completely ignore it.


### **Time-Based Cleanup Logic:**

**🔹 Surgical Cleanup (Grace Period):**
- Triggered: X days after last viewing activity
- Action: Delete episodes BEFORE the "keep block" 
- Purpose: Maintain viewing continuity while cleaning up old episodes
- Example: Keep block of 3 episodes, delete everything before that block

**💥 Nuclear Cleanup (Abandonment Timer):**
- Triggered: X days without ANY viewing activity
- Action: Delete most/all episodes (based on keep_watched setting)
- Purpose: Reclaim storage from truly abandoned shows
- Example: No activity for 90 days = show is abandoned, nuke it

### **Example Rule - "Weekly Viewer with Buffer":**
```
Get Option: 3              → Prepare next 3 episodes
Action Option: search      → Actively download them
Keep Watched: 3            → Keep block of 3 episodes
Monitor Watched: false     → Stop tracking after watching
Grace Period: 7 days       → Clean up old episodes after 1 week
Abandonment Timer: 60 days → Nuke show if unwatched for 2 months
```

**Behavior:**
- **Watch S1E5** → Keeps E3,E4,E5 (keep block), gets E6,E7,E8 (next episodes)
- **7 days later** → Surgical cleanup: Delete E1,E2 (before keep block)
- **60 days no activity** → Nuclear cleanup: Delete most episodes (abandonment detected)

---

## 🚀 Installation

### **Requirements:**
- Sonarr v3
- Media server with webhook support:
  - **Plex** + Tautulli (webhook required)
  - **Jellyfin** (built-in webhooks)
- Docker environment
## 🚀 Installation

### Option 1: Docker Hub (Recommended)


⚙️ Configuration
Environment Variables
Create a .env file:

Docker Compose
```
version: '3.8'
services:
  ocdarr:
    image: vansmak/ocdarrlite:latest or vansmak/ocdarr:beta-2.1.0
    environment:
      - SONARR_URL: ${SONARR_URL}
      - SONARR_API_KEY: ${SONARR_API_KEY}
      - JELLYSEERR_URL: ${JELLYSEERR_URL}
      - JELLYSEERR_API_KEY: ${JELLYSEERR_API_KEY}
  
      - CONFIG_PATH: /app/config/config.json
      
    env_file:
      - .env
    volumes:
      - /mnt/media/OCDarr3/logs:/app/logs
      - /mnt/media/OCDarr3/config:/app/config
      
    ports:
      - "5002:5002"
    restart: unless-stopped
```
### **Quick Start:**
```bash
# Clone OCDarr
git clone https://github.com/your-repo/ocdarr.git
cd ocdarr

# Configure environment
cp .env.example .env
# Edit .env with your Sonarr details

# Run with Docker
docker-compose up -d
```

### **Environment Configuration:**
```env
# Required
SONARR_URL=http://your-sonarr:8989
SONARR_API_KEY=your_sonarr_api_key

# Optional (for Jellyseerr integration)
JELLYSEERR_URL=http://your-jellyseerr:5055
JELLYSEERR_API_KEY=your_jellyseerr_api_key

# Scheduler Settings
CLEANUP_INTERVAL_HOURS=6    # How often to run time-based cleanup

# Logging
LOG_PATH=/app/logs/app.log
FLASK_DEBUG=false
PORT=5002
```

---

## ⚙️ Setup & Configuration

### **1. OCDarr Interface**
- Access at `http://your-server:5002`
- Create and manage rules with time-based settings
- **Assign series to rules** (unassigned series use default Sonarr behavior)
- Monitor statistics and scheduler status

### **2. Media Server Webhooks**

#### **For Plex + Tautulli:**
1. **Tautulli** → Settings → Notification Agents → Add Webhook
2. **Webhook URL:** `http://your-ocdarr:5002/webhook`
3. **Trigger:** Episode Watched  
4. **JSON Data:**
```json
{
  "plex_title": "{show_name}",
  "plex_season_num": "{season_num}",
  "plex_ep_num": "{episode_num}"
}
```

#### **For Jellyfin:**
1. **Jellyfin** → Dashboard → Plugins → Webhooks
2. **Webhook URL:** `http://your-ocdarr:5002/jellyfin-webhook`
3. **Notification Type:** Playback Progress
4. **Item Type:** Episodes

### **3. Sonarr Integration**
1. **Sonarr** → Settings → Connect → Add Webhook
2. **URL:** `http://your-ocdarr:5002/sonarr-webhook`  
3. **Triggers:** On Series Add
4. **Purpose:** Applies default rule to new series

---

## 🎛️ Advanced Features

### **Time-Based Rule Examples:**

**🎯 Active Show Management:**
```
Grace Period: 7 days        → Clean up weekly
Abandonment Timer: null     → Never abandon (always keep some episodes)
Keep Watched: 2             → Always maintain 2-episode buffer
```
*Perfect for: Current shows you watch regularly*

**📺 Seasonal Show Management:**
```
Grace Period: 14 days       → Clean up bi-weekly  
Abandonment Timer: 180 days → Abandon after 6 months
Keep Watched: season        → Keep entire season as buffer
```
*Perfect for: Shows with irregular schedules*

**🧹 Minimalist Management:**
```
Grace Period: 3 days        → Aggressive cleanup
Abandonment Timer: 30 days  → Quick abandonment  
Keep Watched: 1             → Minimal storage
```
*Perfect for: Limited storage, want maximum automation*

**🏆 Archive Management:**
```
Grace Period: null          → Never auto-cleanup
Abandonment Timer: null     → Never abandon
Keep Watched: all           → Keep everything
```
*Perfect for: Shows you want to keep forever*

### **OCDarr Tag (Optional)**
For power users who want episode-level control from day one:

- **Auto-created:** OCDarr creates an "ocdarr" tag in Sonarr on first run
- **User choice:** Add tag when requesting new series for immediate control
- **Self-cleaning:** Tag automatically removed after processing
- **Delayed downloads:** Prevents Sonarr from auto-downloading full seasons

#### **How to Use:**
1. **Request new series** → Optionally add "ocdarr" tag
2. **OCDarr processes** → Applies rules, removes tag
3. **Clean operation** → No permanent tag clutter

#### **Sonarr Delayed Profile Setup (Recommended):**
1. **Settings** → Profiles → Add Delay Profile
2. **Delay:** 10519200 minutes (failsafe - prevents unwanted downloads)
3. **Tags:** Select "ocdarr"
4. **Bypass:** Do NOT select
5. **Purpose:** Protection while OCDarr processes rules

### **Jellyseerr/Overseerr Integration**
- **With "ocdarr" tag:** Request gets deleted after processing (prevents conflicts)
- **Without tag:** Normal workflow, rules apply after viewing
- **Trade-off:** Choose episode control OR seerr visibility (not both)

### **Scheduler Administration**
- **View Status:** Check last cleanup time and next scheduled run
- **Force Cleanup:** Manually trigger cleanup outside schedule
- **Activity Tracking:** View per-series activity timestamps
- **Logs:** Detailed cleanup operations and reasoning

---

## 🎯 Example Workflows

### **Daily Show Watcher - "Next Episode Ready"**
```
Get: 1, Search, Keep: 1
Grace Period: 3 days, Abandonment: 14 days
```
- **Experience:** Next episode always ready, quick cleanup, fast abandonment detection
- **Perfect for:** Daily shows, limited storage

### **Weekly Show Follower - "Buffer Management"**
```
Get: 3, Search, Keep: 2  
Grace Period: 7 days, Abandonment: 60 days
```
- **Experience:** Small buffer of episodes, weekly cleanup, seasonal abandonment
- **Perfect for:** Weekly releases, want some buffer

### **Season Collector - "Full Season Control"**
```
Get: season, Monitor, Keep: season
Grace Period: 30 days, Abandonment: 365 days
```
- **Experience:** Get full seasons, keep current season, yearly cleanup cycles
- **Perfect for:** Prefer complete seasons, patient viewing

### **Archive Builder - "Selective Permanence"**
```
Get: all, Monitor, Keep: all
Grace Period: null, Abandonment: null
```
- **Experience:** Keep everything forever, no automatic cleanup
- **Perfect for:** Favorite shows, unlimited storage

### **Storage Optimizer - "Aggressive Management"**
```
Get: 1, Search, Keep: 1
Grace Period: 1 day, Abandonment: 7 days  
```
- **Experience:** Minimal storage use, immediate cleanup, fast abandonment
- **Perfect for:** Very limited storage, highly organized

---

## 🔧 Troubleshooting

### **Episodes Not Updating After Watching:**
- ✅ Verify webhook configuration in Tautulli/Jellyfin
- ✅ Check OCDarr logs: `/app/logs/app.log`
- ✅ Ensure series has a rule assigned
- ✅ Confirm webhook is reaching OCDarr
- ✅ Check activity tracking file: `data/activity_tracking.json`

### **Time-Based Cleanup Not Working:**
- ✅ Verify scheduler is running in OCDarr interface
- ✅ Check rule has grace period or abandonment timer set
- ✅ Review cleanup logs for specific series
- ✅ Ensure enough time has passed since last activity

### **Rules Not Applying:**
- ✅ Verify series is assigned to a rule in OCDarr interface
- ✅ Check that series isn't manually configured in Sonarr
- ✅ Review rule configuration for correct options
- ✅ **No rule assigned = no action taken** - OCDarr completely ignores unassigned series

### **New Series Downloading Everything:**
- ✅ Set up Sonarr webhook for auto-rule assignment
- ✅ Configure delayed release profile with "ocdarr" tag
- ✅ Use "ocdarr" tag when requesting series for immediate control

---

## 📈 Statistics & Monitoring

OCDarr provides comprehensive visibility:

- **Series Management:** Total, assigned, unassigned series counts
- **Rule Breakdown:** How many series each rule manages
- **Scheduler Status:** Last cleanup time, next scheduled run
- **Activity Tracking:** Per-series viewing timestamps and patterns
- **Cleanup History:** What was cleaned up and why

### **Scheduler Interface:**
- **Real-time Status:** Current scheduler state and timing
- **Manual Controls:** Force cleanup runs outside schedule
- **Activity Logs:** Detailed cleanup operations and reasoning
- **Timer Visualization:** See which series are approaching cleanup thresholds

---

## 🎪 Why OCDarr?

### **The Problem:**
Most media tools work on "all or nothing" - download entire seasons, keep everything forever, manual cleanup. Time-based management is either non-existent or overly simplistic.

### **The Solution:**  
**Smart, viewing-driven automation with intelligent time-based cleanup** that adapts to how you actually watch TV and manages storage based on activity patterns.

### **The Result:**
- ✨ **Always ready:** Next episode available when you want it
- 🧹 **Automatically organized:** Old episodes cleaned up intelligently based on time and activity
- 🎯 **Personalized:** Different rules and timers for different shows
- ⚡ **Efficient:** Only downloads what you'll actually watch
- 🕒 **Time-aware:** Cleanup happens based on your actual viewing patterns
- 🔄 **Adaptive:** Different cleanup strategies for active vs abandoned shows

---

## 💡 Philosophy

> *"OCDarr isn't about having everything - it's about having exactly what you need, exactly when you need it, and automatically letting go of what you don't."*

OCDarr is for the **thoughtful media manager** - someone who values:
- **Curation over collection**
- **Automation over accumulation** 
- **Time-awareness over static rules**
- **Purpose over hoarding**
- **Viewing patterns over arbitrary limits**

**The two-timer system reflects how we actually consume media:** we stay current with active shows (surgical cleanup with grace periods) but eventually abandon series we lose interest in (nuclear cleanup with abandonment detection).

---

## 🏗️ Technical Details

- **Language:** Python 3.11+
- **Framework:** Flask
- **Dependencies:** Minimal (Flask, requests, python-dotenv)
- **Architecture:** Dual-layer (webhook + scheduler), maintainable
- **Webhooks:** Sonarr, Plex/Tautulli, Jellyfin
- **Storage:** File-based configuration (config.json, activity tracking)
- **Logging:** Rotating logs with configurable levels
- **Scheduling:** Internal thread-based scheduler (no cron dependency)
- **Cleanup Logic:** Surgical (preserve continuity) vs Nuclear (reclaim storage)
- **Activity Tracking:** Per-series timestamps and episode tracking

### **Time-Based Cleanup Architecture:**
- **Grace Period Timer:** Maintains viewing continuity while cleaning up
- **Abandonment Timer:** Detects truly unused content for aggressive cleanup  
- **Block Logic:** Preserves episode groups to maintain context
- **Activity Tracking:** Per-series viewing timestamps and episode details
- **Dual Strategy:** Different cleanup approaches for different scenarios

---

## 📝 License & Support

**License:** MIT License  
**Support:** GitHub Issues  
**Documentation:** This README + inline help + scheduler interface

---

*OCDarr: Because your media library should work **for you**, adapt to **your viewing patterns**, and clean up **based on time**, not the other way around.*
