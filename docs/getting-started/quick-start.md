
# Quick Start Guide

Get Episeerr running and managing your first series in 5 minutes.

## Prerequisites

- ✅ Sonarr v3+ installed and running
- ✅ Docker or Unraid
- ✅ TMDB API key ([Get one free](https://www.themoviedb.org/settings/api))

## Step 1: Install Episeerr (2 minutes)

**Docker Compose:**
```yaml
services:
  episeerr:
    image: vansmak/episeerr:latest
    environment:
      - SONARR_URL=http://your-sonarr:8989
      - SONARR_API_KEY=your_sonarr_api_key
      - TMDB_API_KEY=your_tmdb_read_access_token
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
      - ./data:/app/data
    ports:
      - "5002:5002"
    restart: unless-stopped
```

Start: `docker-compose up -d`

**Unraid:** Install from Community Applications, search "episeerr"

## Step 2: Configure Sonarr Webhook (1 minute)

1. **Sonarr** → Settings → Connect → Add Webhook
2. **URL:** `http://your-episeerr:5002/sonarr-webhook`
3. **Triggers:** Enable "On Series Add"
4. **Save**

## Step 3: Create Your First Rule (1 minute)

1. **Open Episeerr:** `http://your-server:5002`
2. **Go to Rules** → Create Rule
3. **Configure:**
   - Name: "default"
   - Get: 2 episodes
   - Keep: 1 episode
   - Action: Search
4. **Mark as Default Rule**
5. **Save**

## Step 4: Enable Auto-Assign (30 seconds)

1. **Episeerr** → Scheduler → Global Settings
2. **Enable:** "Auto-assign new series to default rule"
3. **Save**

## Step 5: Add a Series (30 seconds)

1. **Add any series in Sonarr**
2. **Watch an episode**
3. **Check Sonarr** - Next 2 episodes should now be monitored!

---

## Next Steps

- [Set up viewing automation](../configuration/webhook-setup.md)
- [Configure storage cleanup](../features/storage-management.md)
- [Understand deletions](../core-concepts/deletion-system.md)
