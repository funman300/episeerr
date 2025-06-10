# Installation & Setup

## Requirements

- **Sonarr v3+** - Required for all functionality
- **Docker** - Recommended deployment method
- **TMDB API Key** - Required for episode selection interface

### Optional (for viewing-based rules):
- **Plex + Tautulli** OR **Jellyfin** - For viewing activity webhooks
- **Jellyseerr/Overseerr** - For request integration

## Docker Installation (Recommended)

### Docker Compose

Create a `docker-compose.yml` file:

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
      
      # Optional - Viewing-based rules
      - TAUTULLI_URL=http://your-tautulli:8181
      - TAUTULLI_API_KEY=your_tautulli_key
      # OR
      - JELLYFIN_URL=http://your-jellyfin:8096
      - JELLYFIN_API_KEY=your_jellyfin_key
      
      # Optional - Request integration  
      # Keep as jellyseer label but can use overseer url and api
      - JELLYSEERR_URL=http://your-jellyseerr:5055
      - JELLYSEERR_API_KEY=your_jellyseerr_key
      
      # Optional - Tag creation (defaults to false)
      - EPISEERR_AUTO_CREATE_TAGS=false
      
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    ports:
      - "5002:5002"
    restart: unless-stopped
```

### Environment File (.env)

Create a `.env` file for easier management:

```env
# Required
SONARR_URL=http://your-sonarr:8989
SONARR_API_KEY=your_sonarr_api_key
TMDB_API_KEY=your_tmdb_api_key

# Optional - Viewing automation
TAUTULLI_URL=http://your-tautulli:8181
TAUTULLI_API_KEY=your_tautulli_key

# Optional - Request integration  
JELLYSEERR_URL=http://your-seerr 
JELLYSEERR_API_KEY=your_seerr_key

# Optional - Tag creation (defaults to false)
EPISEERR_AUTO_CREATE_TAGS=false
```

### Docker Run Command

```bash
docker run -d \
  --name episeerr \
  -e SONARR_URL=http://your-sonarr:8989 \
  -e SONARR_API_KEY=your_api_key \
  -e TMDB_API_KEY=your_tmdb_key \
  -v $(pwd)/config:/app/config \
  -v $(pwd)/logs:/app/logs \
  -p 5002:5002 \
  --restart unless-stopped \
  vansmak/episeerr:latest
```

## Initial Configuration

1. **Start the container:**
   ```bash
   docker-compose up -d
   ```

2. **Access the interface:**
   Open `http://your-server:5002`

3. **Configure global storage gate:** *(New in v2.0)*
   - Go to Scheduler page
   - Set storage threshold (e.g., 20GB)
   - Configure cleanup interval (e.g., 6 hours)
   - Enable global dry run for safety testing

4. **Create your first rule:**
   - Go to the Rules section
   - Create a "default" rule for most shows
   - Configure grace/dormant timers (or leave null for protection)

5. **Configure Sonarr delayed profile:** *(Optional for requests)*
   - **Critical for episode selection:** Set up delayed release profile
   - See [Sonarr Integration Guide](sonarr-integration.md#required-delayed-release-profile)

6. **Test the setup:**
   - Assign a test series to your rule
   - Verify it appears in Sonarr correctly
   - Test storage gate with dry run mode

## Storage & Cleanup Settings (v2.0 Changes)

### ✅ **New: UI-Based Configuration**
All storage and cleanup settings are now managed through the web interface:

- **Global Storage Gate:** Set via Scheduler page
- **Cleanup Interval:** Configured in UI  
- **Global Dry Run:** Toggle in interface
- **Rule Timers:** Grace/dormant days per rule

### ❌ **Removed: Environment Variables**
These environment variables are **no longer used**:
- ~~`CLEANUP_INTERVAL_HOURS`~~ → Set in UI
- ~~`CLEANUP_DRY_RUN`~~ → Set in UI  
- ~~`GLOBAL_STORAGE_MIN_GB`~~ → Set in UI

**Migration:** If upgrading from v1.x, your old environment variables will be ignored. Use the web interface to configure these settings.

## Getting API Keys

### TMDB API Key
1. Go to [TMDB.org](https://www.themoviedb.org/)
2. Create account → Settings → API
3. Request API key → Developer → Accept terms
4. Copy the "API Read Access Token" (v4 token, starts with `eyJ...`)

### Sonarr API Key  
1. Sonarr → Settings → General
2. Copy the API Key value

### Tautulli API Key
1. Tautulli → Settings → Web Interface  
2. API Key section

### Jellyseerr/Overseerr API Key
1. Settings → General
2. API Key section

## Verification

After setup, verify everything works:

1. **Episeerr loads:** `http://your-server:5002` shows the interface
2. **Sonarr connection:** Rules page shows your series
3. **Storage gate:** Scheduler page shows disk space and gate status
4. **Episode selection:** Can browse and select episodes for a test series
5. **Logs:** Check `/logs/app.log` for any errors

## Migration from v1.x

If upgrading from an earlier version:

1. **Remove old environment variables** from your docker-compose.yml
2. **Configure via UI** - Use Scheduler page for global settings
3. **Test with dry run** - Enable global dry run to verify behavior
4. **Update rules** - Add grace/dormant timers as desired

## Next Steps

- [Configure Global Storage Gate](global_storage_gate_guide.md) - Smart storage management
- [Create your first rule](rules-guide.md#creating-your-first-rule)
- [Set up webhooks](webhooks.md) for viewing-based automation
- [Configure episode selection](episode-selection.md) workflow `null` (empty)
- **Dormant Days:** Set to `null` (empty)
- **Both null:** Rule never participates in cleanup

### Example Protected Rule
```
Rule: "Permanent Collection"
Get: all
Action: monitor  
Keep: all
Grace Days: null
Dormant Days: null

Result: Series in this rule are NEVER cleaned up
```

### Mixed Protection The only limit is your imagination
You can mix protected and cleanup rules:
```
🛡️ "Archive Shows" - Grace: null, Dormant: null (protected)
🟡 "Current Shows" - Grace: 7 days, Dormant: null (grace only)
🔴 "Trial Shows" - Grace: null, Dormant: 30 days (dormant only)
🟡🔴 "Active Shows" - Grace: 14 days, Dormant: 90 days (both)
```

## Safety Features

### Global Dry Run Mode
- **Test cleanup logic** without deleting files
- **See what would be cleaned** in logs
- **Perfect for testing** new configurations
- **Enable in main settings** for system-wide safety

### Rule-Specific Dry Run
- **Individual rule testing** alongside global dry run
- **Granular control** for specific show types
- **Overrides global setting** for that rule only

### Storage Gate Validation
- **Prevents unnecessary cleanup** when storage is adequate
- **Only runs when truly needed** (below threshold)
- **Stops immediately** when goal achieved
- **Logs all decisions** for transparency

## Best Practices

### Setting Your Threshold
- **Conservative approach:** Set threshold higher than you think you need
- **Monitor usage:** Watch storage patterns for a few weeks
- **Adjust gradually:** Lower threshold as you get comfortable
- **Consider buffer:** Account for active downloads and temporary files

### Rule Design
- **Start simple:** Begin with one or two rules
- **Test with dry run:** Always test before going live
- **Use protection:** Set important shows to protected rules
- **Monitor logs:** Watch cleanup behavior and adjust

### Common Thresholds
| Storage Size | Suggested Threshold | Use Case |
|--------------|-------------------|----------|
| **500GB** | 50GB (10%) | Small home server |
| **2TB** | 100GB (5%) | Medium library |
| **8TB** | 200GB (2.5%) | Large collection |
| **16TB+** | 500GB (3%) | Massive library |

## Troubleshooting

### Storage Gate Not Working
- **Check threshold setting:** Ensure it's configured in UI
- **Verify current space:** Look at storage status display  
- **Review rule assignments:** Only assigned series participate
- **Check grace/dormant:** Rules need timers to participate

### Cleanup Too Aggressive
- **Increase threshold:** Give more storage buffer
- **Extend timers:** Longer grace/dormant periods
- **Use protection:** Move important shows to protected rules
- **Enable dry run:** Test changes safely

### Cleanup Not Happening
- **Lower threshold:** Gate may never open with current setting
- **Check rule timers:** Ensure rules have grace/dormant settings
- **Verify assignments:** Series must be assigned to rules
- **Review logs:** Look for cleanup decision messages

### Wrong Shows Getting Cleaned
- **Check priority order:** Dormant processes before grace
- **Review assignment:** Ensure series are in correct rules
- **Verify timers:** Grace/dormant settings affect behavior
- **Use dry run:** Preview cleanup before enabling

## Advanced Configuration

### Multiple Storage Scenarios
- **Critical shows:** Protected rules (null timers)
- **Active viewing:** Short grace (3-7 days)
- **Casual shows:** Medium grace (14-30 days)  
- **Trial shows:** Short dormant (30-60 days)
- **Archive shows:** Long dormant (365+ days) or protected

### Dynamic Thresholds
While Episeerr uses a fixed threshold, you can adjust based on:
- **Seasonal viewing:** Lower threshold during heavy watching periods
- **Storage upgrades:** Adjust threshold when adding drives
- **Library growth:** Monitor and adjust as collection expands

---

## Next Steps

- [Create your first rule](rules-guide.md#creating-your-first-rule)
- [Set up webhooks](webhooks.md) for viewing-based automation
- [Configure episode selection](episode-selection.md) workflow
