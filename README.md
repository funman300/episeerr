
Support This Project If you find this project helpful, please consider supporting it. Your contributions help maintain and improve the project. Any support is greatly appreciated! ❤️ https://buymeacoffee.com/vansmak Thank you for your support!

# Episeerr

**Backend episode management system for Sonarr** - Three independent automation solutions.

## What Episeerr Does

Episeerr gives you precise control over your TV episodes with three separate systems that can work together or independently:

### 🎯 **Three Solutions, One App**

| Solution | Purpose | When to Use |
|----------|---------|-------------|
| **🎬 Granular Episode Requests** | Select exactly which episodes you want | Want specific episodes, not full seasons |
| **⚡ Viewing-Based Rules** | Auto-manage episodes when you watch | Want next episode ready, cleanup watched ones |
| **⏰ Time-Based Cleanup** | Clean up based on age and activity | Want automatic library maintenance |

**Use any combination** - or just one solution that fits your needs.

---

## 🎬 Granular Episode Requests

Select individual episodes across multiple seasons with precision.

**Perfect for:**
- Getting just pilot episodes to try shows
- Catching up on specific episodes you missed
- Managing limited storage with surgical precision

**How it works:**
1.  Make request with `episeerr_select` tag in Jellyseerr/Overseerr/sonarr 
2. Choose seasons and specific episodes in episeerr 
3. Only selected episodes are monitored and downloaded

---

## ⚡ Viewing-Based Rules

Episodes automatically managed based on your viewing activity.

**Perfect for:**
- Always having the next episode ready
- Automatic cleanup of watched episodes
- Different strategies for different shows

**Example rule:** *"Keep last 2 episodes, get next 3, search immediately"*
- Watch S01E05 → Keeps E04+E05, gets E06+E07+E08, deletes E01+E02+E03

**Requires:** Plex+Tautulli or Jellyfin webhook setup

---

## ⏰ Time-Based Cleanup

Automatic cleanup based on time and viewing patterns.

**Perfect for:**
- Cleaning up shows you've abandoned
- Maintaining library size automatically
- Different retention for active vs dormant shows

**Two timers:**
- **Grace Period:** Cleanup after X days (keeps current viewing context)
- **Dormant Timer:** Aggressive cleanup after Y days (reclaims storage from abandoned shows)

**No webhooks required** - runs on schedule

---

## 🚀 Quick Start

### Docker Compose
```yaml
version: '3.8'
services:
  episeerr:
    image: vansmak/episeerr:latest
    environment:
      - SONARR_URL=http://your-sonarr:8989
      - SONARR_API_KEY=your_api_key
      - TMDB_API_KEY=your_tmdb_key # For episode selection UI
      # Optional - for viewing-based rules
      - TAUTULLI_URL=http://your-tautulli:8181
      - TAUTULLI_API_KEY=your_tautulli_key
      # Optional - for request integration  
      - JELLYSEERR_URL=http://your-jellyseerr:5055
      - JELLYSEERR_API_KEY=your_jellyseerr_key
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    ports:
      - "5002:5002"
    restart: unless-stopped
```

### Setup
1. **Configure:** `http://your-server:5002` - Basic web interface for rule management
2. **Create rules** for automated episode management  
3. **Assign series** to rules (unassigned series are ignored)
4. **Optional:** Set up webhooks for viewing-based automation

---

## 🎛️ Example Configurations

### Episode Requests Only
Perfect for trying new shows or specific episode management.
```
No rules needed - just use the episode selection interface

Webhooks: Tautulli or Jellyfin, Jellyseer or Overseer
```

### Viewing Rules Only  
Next episode always ready, automatic cleanup.
```
Rule: Get 1, Search, Keep 1
Webhooks: Tautulli or Jellyfin
Timers: null
```

### Time Cleanup Only
Hands-off library maintenance.
```
Rule: Get blank, Monitor, Keep blank
  - or leave like default sonarr 
  - won't matter if no we hook setup  
Grace: 30 days, Dormant: 90 days
Webhooks: Not needed
```

### Full Automation
Complete episode lifecycle management.
```
Intercept and manage requests
Rule: Get 2, Search, Keep 2
Grace: 7 days, Dormant: 60 days  
Webhooks: Enabled
```

---

## 🔧 Integration

### Sonarr Tags
- `episeerr_default`: Auto-assigns to default rule when added
- `episeerr_select`: Triggers episode selection workflow

### Jellyseerr/Overseerr  
- Request normally: Gets default rule
- Request with `episeerr_select` tag: Triggers episode selection

### Webhooks *(Optional)*
- **Tautulli:** `http://your-episeerr:5002/webhook` 
- **Jellyfin:** `http://your-episeerr:5002/jellyfin-webhook`  
- **Sonarr:** `http://your-episeerr:5002/sonarr-webhook`

*Setup guides with templates and screenshots: [OCDarr Webhook Documentation](link-to-ocdarr-guides)*

---

## 🎯 Key Benefits

- **🔧 Modular:** Use only the features you need
- **🎯 Precise:** Episode-level control when you want it
- **⚡ Responsive:** Next episode ready when you need it  
- **🧹 Smart:** Different cleanup strategies for different shows
- **🏠 Respectful:** Only manages assigned series

---

## 📚 Documentation

**[Complete Documentation →](./docs/)**

**Quick Links:**
- [Installation & Setup](./docs/installation.md)
- [Rules System Guide](./docs/rules-guide.md) 
- [Episode Selection](./docs/episode-selection.md)
- [Webhook Setup](./docs/webhooks.md) - Links to OCDarr's detailed guides

---

## 🚫 What Episeerr Won't Do

- Manage unassigned series (completely ignores them)


*Episeerr: Three solutions for episode management - use what you need, when you need it.*
