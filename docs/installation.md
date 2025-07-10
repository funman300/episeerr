# Installation Guide

Get Episeerr running in 5 minutes with Docker.

## Requirements

✅ **Sonarr v3+** - Required  
✅ **Docker** - Recommended setup  
✅ **TMDB API Key** - Free from themoviedb.org

**Optional (for viewing automation):**
- Plex + Tautulli OR Jellyfin
- Jellyseerr/Overseerr

---

## Quick Setup

### 1. Get API Keys

**TMDB (Required):**
1. Sign up at [themoviedb.org](https://www.themoviedb.org/)
2. Go to Settings → API → Request API Key → Developer
3. Copy the **API Read Access Token** (starts with `eyJ...`)

**Sonarr (Required):**
1. Sonarr → Settings → General → API Key

### 2. Docker Compose

Create `docker-compose.yml`:

```yaml
version: '3.8'
services:
  episeerr:
    image: vansmak/episeerr:latest
    environment:
      # Required
      - SONARR_URL=http://your-sonarr:8989
      - SONARR_API_KEY=your_sonarr_api_key
      - TMDB_API_KEY=your_tmdb_api_key
      
      # Optional - For viewing automation
      - TAUTULLI_URL=http://your-tautulli:8181
      - TAUTULLI_API_KEY=your_tautulli_key
      
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    ports:
      - "5002:5002"
    restart: unless-stopped
```

### 3. Start and Configure

```bash
# Start the container
docker-compose up -d

# Access the interface
open http://your-server:5002
```

---

## Initial Configuration

### 1. Set Storage Gate
Go to **Scheduler** page:
- **Storage Threshold**: 20GB (adjust for your setup)
- **Cleanup Interval**: 6 hours
- **Global Dry Run**: Enable for testing

### 2. Create Your First Rule  
Go to **Rules** section:
- **Name**: `my_shows`
- **Get**: 3 episodes
- **Keep**: 1 episode  
- **Action**: Search
- **Grace**: 7 days (optional)
- **Dormant**: 30 days (optional)

### 3. Assign a Test Series
- Go to **Series Management**
- Assign a series to your new rule
- Verify it shows up correctly

### 4. Test the Setup
- **Check logs**: `/logs/app.log` for any errors
- **Storage status**: Should show current disk space
- **Series assignment**: Test series should show assigned rule

---

## Advanced Setup (Optional)

### Viewing Automation
For automatic "next episode ready" functionality:

**Tautulli (Plex):**
1. Tautulli → Settings → Notification Agents → Webhook
2. **URL**: `http://your-episeerr:5002/webhook`
3. **Triggers**: Playback Stop
4. **Data**: 
```json
{
  "plex_title": "{show_name}",
  "plex_season_num": "{season_num}",
  "plex_ep_num": "{episode_num}"
}
```

**Jellyfin:**
1. Jellyfin → Dashboard → Plugins → Webhook
2. **URL**: `http://your-episeerr:5002/jellyfin-webhook`
3. **Events**: Playback Progress (50% completion)

### Episode Selection
For manual episode selection workflow:

**Sonarr:**
1. Settings → Connect → Webhook
2. **URL**: `http://your-episeerr:5002/sonarr-webhook`
3. **Triggers**: On Series Add

**Sonarr Delayed Profile (Important):**
1. Settings → Profiles → Release Profiles
2. **Add Profile**: 
   - Name: "Episeerr Delay"
   - Delay: 10519200 minutes
   - Tags: `episeerr-select`

---

## What's New in v2.1

### Enhanced UI
- **Dropdown system** replaces confusing text fields
- **Clear explanations** show exactly what each setting does
- **Visual indicators** for rule assignments

### Better Grace Logic
- **Intuitive behavior**: Grace protects watched content
- **Predictable timing**: Clear countdown from watch date
- **Storage awareness**: Respects storage gate settings

### Fixed Bugs
- **Season transitions**: Properly gets next season at end of current
- **Rule migration**: Automatic conversion from old format
- **Storage calculations**: More accurate free space detection

---

## Troubleshooting

### Container Won't Start
- ✅ Check required environment variables
- ✅ Verify API keys are correct
- ✅ Ensure ports aren't conflicting

### Can't Connect to Sonarr
- ✅ Check URL format: `http://sonarr:8989` (no trailing slash)
- ✅ Verify API key is correct
- ✅ Test network connectivity

### Episode Selection Not Working
- ✅ Check TMDB API key is configured
- ✅ Verify delayed release profile is set up
- ✅ Ensure `episeerr_select` tag exists in Sonarr

### Rules Not Processing
- ✅ Verify series is assigned to a rule
- ✅ Check webhook setup and logs
- ✅ Test with dry run mode first

---

## Next Steps

1. **[Create rules](rules-guide.md)** for different types of shows
2. **[Set up webhooks](webhooks.md)** for viewing automation  
3. **[Configure episode selection](episode-selection.md)** for manual control
4. **[Understand storage gate](global_storage_gate_guide.md)** for automatic cleanup

---

**Need Help?**
- Check [Troubleshooting Guide](troubleshooting.md)
- Ask in [GitHub Discussions](https://github.com/Vansmak/episeerr/discussions)
- Report bugs in [GitHub Issues](https://github.com/Vansmak/episeerr/issues)
