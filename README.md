# OCDarr: Smart Episode Management for Sonarr

**Intelligent, time-aware episode management** that responds to your viewing habits and automatically maintains your library based on activity patterns.

## What OCDarr Does

OCDarr automatically manages your TV episodes based on **your viewing activity and time-based rules**. Watch an episode, and OCDarr intelligently prepares what you want next while cleaning up what you've already seen.

### 🎯 **Perfect For:**
- Users who **don't rewatch** episodes but want the next one ready
- People who prefer a **curated, organized** library over massive collections
- Anyone wanting **different management strategies** for different shows
- Shows with **different viewing cadences** (daily, weekly, seasonal)

---

## 🔧 How It Works

### **Flexible Rule System:**
Each rule defines exactly how episodes are handled:

| Component | Purpose | Examples |
|-----------|---------|----------|
| **Get Option** | How many upcoming episodes to prepare | `1` (next episode), `season` (full season), `all` (everything) |
| **Action Option** | How episodes are handled | `monitor` (passive), `search` (active download) |
| **Keep Watched** | What to retain as a "keep block" | `1` (last episode), `season` (current season), `all` (everything) |
| **Grace Period** | Days after watching before cleanup | `7` (cleanup after 1 week), `null` (never) |
| **Dormant Timer** | Days without activity before aggressive cleanup | `90` (abandon after 3 months), `null` (never) |

### **Two-Layer System:**
**🚀 Webhook Layer:** Responds instantly to viewing activity
- Tracks what you watched and when
- Prepares next episodes immediately  
- Cleans up old episodes (sliding window)

**⏰ Scheduler Layer:** Handles time-based cleanup
- **Grace Period:** Selective cleanup after X days (maintains continuity)
- **Dormant Timer:** Aggressive cleanup after Y days (reclaims storage)

### **Example: "Weekly Show with Buffer"**
```
Get: 3, Search, Keep: 3
Grace Period: 7 days, Dormant Timer: 60 days
```
- **Watch S1E5** → Keeps E3,E4,E5, gets E6,E7,E8, deletes E1,E2
- **7 days later** → Cleans up old episodes before keep block
- **60 days no activity** → Nukes most episodes (show abandoned)

---

## 🎛️ Use Cases

### **Grace/Dormant Cleanup Only** (No Webhooks)
Perfect for users who just want time-based cleanup:
```
Grace Period: 14 days    → Clean up bi-weekly
Dormant Timer: 90 days   → Abandon after 3 months
```
*OCDarr runs scheduled cleanup every 6 hours, no webhook setup needed*

### **Webhook Only** (No Time Cleanup)
Perfect for immediate episode management:
```
Get: 1, Search, Keep: 1
Grace Period: null, Dormant Timer: null
```
*Sliding window of episodes, no automatic time-based deletion*

### **Full System** (Webhooks + Time Cleanup)
Complete automation with both layers:
```
Get: 2, Search, Keep: 2
Grace Period: 7 days, Dormant Timer: 30 days
```
*Immediate management + intelligent time-based cleanup*

### **Archive Mode** (Keep Everything)
For shows you want to preserve:
```
Get: all, Monitor, Keep: all
Grace Period: null, Dormant Timer: null
```
*Downloads everything, never deletes anything*

---

## 🚀 Quick Start

### **Docker Compose:**
```yaml
version: '3.8'
services:
  ocdarr:
    image: vansmak/ocdarr-lite:beta-2.1.1
    environment:
      - SONARR_URL=http://your-sonarr:8989
      - SONARR_API_KEY=your_api_key
      - CLEANUP_INTERVAL_HOURS=6
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    ports:
      - "5002:5002"
    restart: unless-stopped
```

### **Setup:**
1. **OCDarr Interface:** `http://your-server:5002`
   - Create rules with your preferred settings
   - Assign series to rules (unassigned = ignored)

2. **Optional Webhooks:** For instant response to viewing
   - **Tautulli:** `http://your-ocdarr:5002/webhook`
   - **Jellyfin:** `http://your-ocdarr:5002/jellyfin-webhook`

3. **Optional Sonarr Webhook:** For new series auto-assignment
   - **URL:** `http://your-ocdarr:5002/sonarr-webhook`

---

## 🎯 Key Benefits

- **🔄 Flexible:** Use webhooks, time cleanup, or both
- **⚡ Responsive:** Next episode ready when you need it
- **🧹 Smart Cleanup:** Different strategies for active vs abandoned shows
- **🎛️ Granular Control:** Per-series rules and timing
- **📊 Transparent:** Full visibility into what's happening and why
- **🏠 Respectful:** Only manages assigned series, ignores the rest

---

## 🎛️ Advanced Examples

### **Daily Show Watcher**
```
Get: 1, Search, Keep: 1
Grace Period: 3 days, Dormant Timer: 14 days
```
*Next episode always ready, quick cleanup, fast abandonment detection*

### **Weekly Show Follower**
```
Get: 3, Search, Keep: 2  
Grace Period: 7 days, Dormant Timer: 60 days
```
*Small buffer of episodes, weekly cleanup, seasonal abandonment*

### **Season Collector**
```
Get: season, Monitor, Keep: season
Grace Period: 30 days, Dormant Timer: 365 days
```
*Get full seasons, keep current season, yearly cleanup cycles*

### **Storage Optimizer**
```
Get: 1, Search, Keep: 1
Grace Period: 1 day, Dormant Timer: 7 days  
```
*Minimal storage use, immediate cleanup, fast abandonment*

---

## 🔧 Configuration

### **Environment Variables:**
```env
# Required
SONARR_URL=http://your-sonarr:8989
SONARR_API_KEY=your_sonarr_api_key

# Optional
CLEANUP_INTERVAL_HOURS=6    # How often to run time-based cleanup
LOG_PATH=/app/logs/app.log
PORT=5002

# Webhooks (optional)
TAUTULLI_URL=http://your-tautulli:8181
JELLYFIN_URL=http://your-jellyfin:8096
```

### **Webhook Setup:**

#### **Tautulli (Plex):**
1. **Tautulli** → Settings → Notification Agents → Add Webhook
2. **URL:** `http://your-ocdarr:5002/webhook`
3. **Trigger:** Episode Watched  
4. **JSON Data:**
```json
{
  "plex_title": "{show_name}",
  "plex_season_num": "{season_num}",
  "plex_ep_num": "{episode_num}"
}
```

#### **Jellyfin:**
1. **Jellyfin** → Dashboard → Plugins → Webhooks
2. **URL:** `http://your-ocdarr:5002/jellyfin-webhook`
3. **Notification Type:** Playbook Progress
4. **Item Type:** Episodes

---

## 🔍 Monitoring & Control

### **OCDarr Interface Features:**
- **Rule Management:** Create, edit, delete rules
- **Series Assignment:** Assign shows to specific rules
- **Scheduler Control:** View status, force cleanup, view logs
- **Statistics:** Track assigned vs unassigned series
- **Dry Run Mode:** Test cleanup without deleting files

### **Time-Based Cleanup Control:**
- **Grace Period Only:** Surgical cleanup for active shows
- **Dormant Timer Only:** Nuclear cleanup for abandoned shows
- **Both Timers:** Complete lifecycle management
- **Neither Timer:** Webhook-only management

---

## 🚫 What OCDarr Won't Do

- **Manage unassigned series** - OCDarr completely ignores shows without rules
- **Interfere with manual Sonarr settings** - Your existing configurations remain untouched
- **Download without permission** - Only monitors/searches based on your rules
- **Delete without reason** - All deletions are logged with clear reasoning

---

## 💡 Philosophy

> *"OCDarr isn't about having everything - it's about having exactly what you need, exactly when you need it, and automatically letting go of what you don't."*

**Use as much or as little as you want:**
- Just need time-based cleanup? Skip webhooks
- Just want immediate episode management? Skip timers  
- Want full automation? Use everything
- Have some shows you want untouched? Don't assign them rules

**The two-timer system reflects how we actually consume media:** we stay current with active shows (grace period cleanup) but eventually abandon series we lose interest in (dormant timer cleanup).

---

## 🏗️ Technical Details

- **Language:** Python 3.11+
- **Framework:** Flask
- **Architecture:** Dual-layer (webhook + scheduler)
- **Webhooks:** Sonarr, Plex/Tautulli, Jellyfin
- **Storage:** File-based configuration (JSON)
- **Logging:** Rotating logs with detailed cleanup reasoning
- **Scheduling:** Internal thread-based scheduler (no cron dependency)

---

## 📝 License & Support

**License:** MIT License  
**Support:** GitHub Issues  
**Documentation:** Interface help + detailed logs

---

<<<<<<< HEAD
*OCDarr: Because your media library should work for you, adapt to your viewing patterns, and clean up based on time, not the other way around.*
=======
*OCDarr: Because your media library should work for you, adapt to your viewing patterns, and clean up based on time, not the other way around.*
>>>>>>> 8a236cdaaa9851f503f3964bc31c0fb01b14af7f
