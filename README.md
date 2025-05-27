# OCDarr Lite: Smart Episode Management for Sonarr

<img src="static/logo_icon.png" alt="OCDarr Lite" width="120" align="right"/>

**The essential OCDarr experience** - focused on what matters most: intelligent, rule-based episode management that responds to your viewing habits.

## What OCDarr Lite Does

OCDarr Lite automatically manages your TV episodes based on **your viewing activity**. Watch an episode, and OCDarr intelligently prepares what you want to watch next while cleaning up what you've already seen.

### 🎯 **Perfect For:**
- Users who **don't rewatch** episodes but want the next one ready
- People who prefer a **curated, organized** library over massive collections
- Anyone wanting **different management strategies** for different shows
- Users who value **automation that actually helps**

### 🚫 **Not For:**
- Digital hoarders who want to keep everything forever
- Users who rewatch content frequently
- Large household servers with multiple users at different points in series

---

## 🔧 How It Works

### **Simple Three-Step Process:**

1. **Create Rules** → Define how episodes should be managed
2. **Assign Series** → Link your shows to specific rules  
3. **Watch & Enjoy** → OCDarr handles everything automatically

### **Rule Components:**

Each rule defines exactly how episodes are handled:

| Component | Purpose | Examples |
|-----------|---------|----------|
| **Get Option** | How many upcoming episodes to prepare | `1` (next episode), `season` (full season), `all` (everything) |
| **Action Option** | How episodes are handled | `monitor` (passive), `search` (active download) |
| **Keep Watched** | What to retain after viewing | `1` (last episode), `season` (current season), `all` (everything) |
| **Monitor Watched** | Track episodes after watching | `true` (keep monitoring), `false` (auto-unmonitor) |

### **Example Rule - "Next Episode Only":**
```
Get Option: 1          → Prepare just the next episode
Action Option: search  → Actively download it  
Keep Watched: 1        → Keep only the last watched episode
Monitor Watched: false → Stop tracking after watching
```

**Result:** Watch S1E5 → Keeps E5, gets E6, deletes E4 and earlier

---

## 🚀 Installation

### **Requirements:**
- Sonarr v3
- Media server with webhook support:
  - **Plex** + Tautulli (webhook required)
  - **Jellyfin** (built-in webhooks)
- Docker environment

### **Quick Start:**
```bash
# Clone OCDarr Lite
git clone -b lite https://github.com/your-repo/ocdarr.git ocdarr-lite
cd ocdarr-lite

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

# Logging
LOG_PATH=/app/logs/app.log
FLASK_DEBUG=false
PORT=5003
```

---

## ⚙️ Setup & Configuration

### **1. OCDarr Lite Interface**
- Access at `http://your-server:5003`
- Create and manage rules
- Assign series to rules
- Monitor statistics

### **2. Media Server Webhooks**

#### **For Plex + Tautulli:**
1. **Tautulli** → Settings → Notification Agents → Add Webhook
2. **Webhook URL:** `http://your-ocdarr:5003/webhook`
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
2. **Webhook URL:** `http://your-ocdarr:5003/jellyfin-webhook`
3. **Notification Type:** Playback Progress
4. **Item Type:** Episodes

### **3. Sonarr Integration**
1. **Sonarr** → Settings → Connect → Add Webhook
2. **URL:** `http://your-ocdarr:5003/sonarr-webhook`  
3. **Triggers:** On Series Add
4. **Purpose:** Applies default rule to new series

---

## 🎛️ Advanced Features

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

---

## 🎯 Example Workflows

### **Typical User - "Next Episode Only"**
- **Rule:** Get 1, Search, Keep 1, Don't Monitor Watched
- **Experience:** Always have next episode ready, automatically clean up old ones
- **Perfect for:** Binge watchers, current season followers

### **Season Watcher - "Full Season Management"**  
- **Rule:** Get Season, Monitor, Keep Season, Monitor Watched
- **Experience:** Get full seasons, keep current season, automatic cleanup
- **Perfect for:** Prefer complete seasons, don't rewatch

### **Minimalist - "Just What I Need"**
- **Rule:** Get 1, Monitor, Keep 1, Don't Monitor Watched  
- **Experience:** Minimal downloads, maximum cleanup
- **Perfect for:** Limited storage, very organized libraries

---

## 🔧 Troubleshooting

### **Episodes Not Updating After Watching:**
- ✅ Verify webhook configuration in Tautulli/Jellyfin
- ✅ Check OCDarr logs: `/app/logs/app.log`
- ✅ Ensure series has a rule assigned
- ✅ Confirm webhook is reaching OCDarr

### **Rules Not Applying:**
- ✅ Verify series is assigned to a rule in OCDarr interface
- ✅ Check that series isn't manually configured in Sonarr
- ✅ Review rule configuration for correct options

### **New Series Downloading Everything:**
- ✅ Set up Sonarr webhook for auto-rule assignment
- ✅ Configure delayed release profile with "ocdarr" tag
- ✅ Use "ocdarr" tag when requesting series for immediate control

---

## 📈 Statistics & Monitoring

OCDarr Lite provides clear visibility into your setup:

- **Total Series:** All series in your Sonarr instance
- **Assigned Series:** Series with OCDarr rules  
- **Unassigned Series:** Series using default Sonarr behavior
- **Rule Breakdown:** How many series each rule manages

---

## 🎪 Why OCDarr Lite?

### **The Problem:**
Most media tools work on "all or nothing" - download entire seasons, keep everything forever, manual cleanup.

### **The Solution:**  
**Smart, viewing-driven automation** that adapts to how you actually watch TV.

### **The Result:**
- ✨ **Always ready:** Next episode available when you want it
- 🧹 **Automatically organized:** Old episodes cleaned up intelligently  
- 🎯 **Personalized:** Different rules for different shows
- ⚡ **Efficient:** Only downloads what you'll actually watch

---

## 💡 Philosophy

> *"OCDarr isn't about having everything - it's about having exactly what you need, exactly when you need it."*

OCDarr Lite is for the **thoughtful media manager** - someone who values curation over collection, automation over accumulation, and purpose over hoarding.

**Not designed for media hoarders or large household servers with multiple users at different points in series.**

---

## 🏗️ Technical Details

- **Language:** Python 3.11+
- **Framework:** Flask
- **Dependencies:** Minimal (Flask, requests, python-dotenv)
- **Architecture:** Lightweight, focused, maintainable
- **Webhooks:** Sonarr, Plex/Tautulli, Jellyfin
- **Storage:** File-based configuration (config.json)
- **Logging:** Rotating logs with configurable levels

---

## 📝 License & Support

**License:** MIT License  
**Support:** GitHub Issues  
**Documentation:** This README + inline help  

---

*OCDarr Lite: Because your media library should work **for you**, not the other way around.*
