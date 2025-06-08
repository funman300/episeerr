# Webhook Setup

Webhooks enable viewing-based automation - Episeerr can respond immediately when you watch episodes to prepare the next ones and clean up watched content.

## Overview

Episeerr supports webhooks from:
- **Tautulli** (Plex) - Most common setup
- **Jellyfin** - Direct integration
- **Sonarr** - For new series automation
- **Jellyseerr/Overseerr** - For request processing

## Detailed Setup Guides

**For complete webhook setup with screenshots and exact templates:**

📖 **[OCDarr Webhook Documentation](https://github.com/Vansmak/OCDarr#webhook-setup)**

The webhook configurations are identical between OCDarr and Episeerr. Use those detailed guides for:
- Tautulli webhook setup with JSON templates
- Jellyfin webhook configuration  
- Sonarr webhook for series automation
- Jellyseerr/Overseerr integration

## Quick Reference

### Episeerr Webhook URLs

| Service | Endpoint | Purpose |
|---------|----------|---------|
| Tautulli (Plex) | `http://your-episeerr:5002/webhook` | Episode viewing events |
| Jellyfin | `http://your-episeerr:5002/jellyfin-webhook` | Episode viewing events |
| Sonarr | `http://your-episeerr:5002/sonarr-webhook` | New series automation |
| Jellyseerr/Overseerr | `http://your-episeerr:5002/seerr-webhook` | Request processing |

### Required JSON Template (Tautulli)

```json
{
  "plex_title": "{show_name}",
  "plex_season_num": "{season_num}",
  "plex_ep_num": "{episode_num}"
}
```

## Testing Webhooks

After setup, test your webhooks:

1. **Watch an episode** of a series assigned to a rule
2. **Check Episeerr logs:** `/logs/app.log` should show webhook received
3. **Verify Sonarr:** Next episode should be monitored/searched
4. **Check cleanup:** Previous episodes handled per your rule

### Troubleshooting

**Webhook not received:**
- Verify URL is correct and accessible
- Check firewall/network settings
- Review sender logs (Tautulli, Jellyfin, etc.)

**Webhook received but nothing happens:**
- Ensure series is assigned to a rule in Episeerr
- Check series name matching in logs
- Verify rule configuration

**Episodes not updating correctly:**
- Check Sonarr API connection
- Review rule logic (get_option, keep_watched, etc.)
- Look for errors in Episeerr logs

## Webhook Security

For production setups:
- Use HTTPS if possible
- Consider API authentication
- Restrict network access to webhook endpoints
- Monitor webhook logs for unusual activity

## Optional: Custom Webhook Processing

Episeerr processes these fields from webhooks:

| Field | Purpose | Example |
|-------|---------|---------|
| `plex_title` / `show_name` | Series identification | "Breaking Bad" |
| `plex_season_num` / `season_num` | Season number | "1" |
| `plex_ep_num` / `episode_num` | Episode number | "5" |

The webhook system is flexible - as long as these fields are present, Episeerr can process the viewing event.

---

**Next:** [Rules System Guide](rules-guide.md) - Configure how Episeerr responds to viewing events