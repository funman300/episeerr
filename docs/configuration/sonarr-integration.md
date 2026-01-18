# Sonarr Integration

Episeerr works with Sonarr through tags and webhooks. Most integration is automatic.

- [Sonarr Integration](#sonarr-integration)
  - [Required: Delayed Release Profile](#required-delayed-release-profile)
    - [Setup](#setup)
  - [Episeerr Tags](#episeerr-tags)
  - [Optional: Sonarr Webhook](#optional-sonarr-webhook)
    - [Setup](#setup-1)
  - [Tag Workflows](#tag-workflows)
    - [Normal Request (No Tag)](#normal-request-no-tag)
    - [Automatic Rule Assignment](#automatic-rule-assignment)
    - [Episode Selection](#episode-selection)
  - [Troubleshooting](#troubleshooting)

## Required: Delayed Release Profile

**Critical for episode selection:** Create this profile to prevent unwanted downloads.

### Setup

1. **Sonarr:** Settings → Profiles → Release Profiles → Add New
2. **Settings:**
   - **Name:** "Episeerr Episode Selection Delay"
   - **Delay:** `10519200` (20 years - effectively prevents downloads)
   - **Tags:** `episeerr_select`
3. **Save**

**Why needed:** Prevents Sonarr from downloading everything while you're selecting specific episodes.

---

## Episeerr Tags

Add these tags to series for automatic processing:

| Tag | What It Does | When To Use |
|-----|--------------|-------------|
| `episeerr_default` | Assigns to default rule automatically | Standard automation |
| `episeerr_select` | Triggers episode selection interface | Choose specific episodes |
| No tag | Normal Sonarr behavior, no Episeerr management | Leave Sonarr alone |

---

## Optional: Sonarr Webhook

Enables automatic tag processing when series are added.

### Setup

1. **Sonarr:** Settings → Connect → Add Webhook
2. **URL:** `http://your-episeerr:5002/sonarr-webhook`
3. **Triggers:** Enable "On Series Add"
4. **Save**

**What it does:** Automatically processes `episeerr_default` and `episeerr_select` tags when series are added to Sonarr.

---

## Tag Workflows

### Normal Request (No Tag)

```log
Add to Sonarr → Normal Sonarr behavior (Episeerr ignores it)
```

### Automatic Rule Assignment

```log
Add with episeerr_default tag → Auto-assigned to default rule → Automation starts
```

**With Jellyseerr Integration:**

If you requested a specific season from Jellyseerr (e.g., Season 3), Episeerr will:
1. Capture the requested season from the Jellyseerr webhook
2. Apply your default rule starting from that season (not Season 1)
3. Cancel the Jellyseerr request automatically

**Example:**
- Jellyseerr request: Season 2 only
- Default rule: Get 1 episode
- Result: Downloads S02E01 (not S01E01)

**Without Jellyseerr webhook:**
- Always starts from Season 1
- Use the "Auto-assign new series" setting (Episeerr → Scheduler → Global Settings) if you don't want to use tags

**Important:** The Jellyseerr request will be **automatically deleted** after processing. If you want to keep requests in Jellyseerr for tracking purposes, use "Auto-assign new series" instead of the tag.

### Episode Selection

```log
Add with episeerr_select tag → Episodes unmonitored → Selection interface → Choose episodes
```

---

## Troubleshooting

**Tags not working:**

- Check webhook is configured and receiving events
- Verify tag spelling (case sensitive)

**Downloads still starting with episeerr_select:**

- Ensure delayed release profile is configured correctly
- Check that tag is applied before adding to Sonarr

**Series not getting managed:**

- Verify series is assigned to a rule in Episeerr
- Check that webhook received the series addition

**episeerr_default starting from Season 1 instead of requested season:**

- Ensure Jellyseerr webhook is configured (see [Webhook Setup](webhooks.md))
- Check Episeerr logs for "Stored Jellyseerr request" message
- Verify the Jellyseerr request was made before the series was added to Sonarr

---

**Next:** [Episode Selection Guide](episode-selection.md) - Choose specific episodes manually
