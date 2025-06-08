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
      - JELLYSEERR_URL=http://your-jellyseerr:5055
      - JELLYSEERR_API_KEY=your_jellyseerr_key
      # OR  
      - OVERSEERR_URL=http://your-overseerr:5055
      - OVERSEERR_API_KEY=your_overseerr_key
      
      # Optional - Cleanup scheduling
      - CLEANUP_INTERVAL_HOURS=6
      
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

# Optional - Request integration  # Keep as jellyseer label but use overseer url and api
JELLYSEERR_URL=http://your-seerr 
JELLYSEERR_API_KEY=your_seerr_key

# Optional - Tag creation (defaults to false) EPISEERR_AUTO_CREATE_TAGS=false

# Optional - Cleanup
CLEANUP_INTERVAL_HOURS=6
CLEANUP_DRY_RUN=false
```

Then reference it in docker-compose:

```yaml
services:
  episeerr:
    image: vansmak/episeerr:latest
    env_file: .env
    # ... rest of config
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

3. **Create your first rule:**
   - Go to the Rules section
   - Create a "default" rule for most shows
   - Configure how you want episodes managed

4. **Configure Sonarr delayed profile:** optional for making external requests that you want episeerr to hijack
   - **Critical:** Set up delayed release profile to prevent unwanted downloads
   - See [Sonarr Integration Guide](sonarr-integration.md#required-delayed-release-profile)

5. **Test the setup:**
   - Assign a test series to your rule
   - Verify it appears in Sonarr correctly

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
3. **Episode selection:** Can browse and select episodes for a test series
4. **Logs:** Check `/logs/app.log` for any errors

## Next Steps

- [Create your first rule](rules-guide.md#creating-your-first-rule)
- [Set up webhooks](webhooks.md) for viewing-based automation
- [Configure episode selection](episode-selection.md) workflow
