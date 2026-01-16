# Storage Cleanup

Automatic cleanup based on time and viewing activity. **Completely optional** - only runs when storage is actually low.

- [Storage Cleanup](#storage-cleanup)
  - [Setup Storage Gate](#setup-storage-gate)
  - [Add Grace Periods to Rules](#add-grace-periods-to-rules)
    - [Grace Watched (Collection Rotation)](#grace-watched-collection-rotation)
    - [Grace Unwatched (Watch Deadlines)](#grace-unwatched-watch-deadlines)
    - [Dormant (Abandoned Series)](#dormant-abandoned-series)
  - [Example Rule Configurations](#example-rule-configurations)
    - [Standard Show](#standard-show)
    - [Important Show (Protected)](#important-show-protected)
    - [Current Show (Pressure to Stay Current)](#current-show-pressure-to-stay-current)
  - [How Cleanup Works](#how-cleanup-works)
  - [Testing (Important)](#testing-important)
  - [Series Assignment](#series-assignment)
  - [Troubleshooting](#troubleshooting)

## Setup Storage Gate

1. **Episeerr** → Scheduler
2. **Storage Threshold**: Set GB limit (e.g., `20` for 20GB free)
3. **Cleanup Interval**: How often to check (e.g., `6` hours)
4. **Save**

**How it works**: Cleanup only runs when free space drops below threshold. When space is adequate, no cleanup happens.

## Add Grace Periods to Rules

**All optional - use any combination:**

### Grace Watched (Override Keep)

- **What it does:** Deletes ALL watched episodes after X days of inactivity (ignores Keep settings)
- **Exception:** Keeps the most recent watched episode as a "bookmark"
- **Auto-resume:** Simulates watching the bookmark during cleanup to trigger Get rule for new episodes
- **Use case:** Free up space from watched content while preserving your position

**Example:**
  Grace Watched: 10 days
  Last watched: S2E6 (2 weeks ago)

  Result after cleanup:

  S2E1-E5 deleted
  S2E6 kept (bookmark)
  If S2E7 exists → Get rule monitors/searches it automatically

### Grace Unwatched (Watch Deadline)

- **What it does:** Deletes unwatched episodes after X days if not watched
- **Exception:** Always keeps at least 1 unwatched episode (your next episode)
- **Use case:** Clear backlog while keeping your resume point

**Example:**
  Get: 3 episodes
  Grace Unwatched: 14 days
  Got: S1E11, S1E12, S1E13 (2 weeks ago, didn't watch any)

  Result after cleanup:

  S1E12, S1E13 deleted
  S1E11 kept (next episode = resume point)

### Important Notes:

- **Mid-season breaks:** Grace Watched handles these automatically! When cleanup runs, it checks for new episodes and monitors them if available.
- **Both grace periods preserve bookmarks:** You can always pick up where you left off
- **Independent of Keep:** Grace periods now ignore Keep settings completely
- **Works together:** Use both to maximize space savings while maintaining position

### Grace Period Scope (New!)

By default, grace timers apply to the entire series - watching ANY episode resets the timer for all kept episodes.

For **multi-viewer households** (e.g., one person watching Season 1 while another watches Season 2), 
you can set **Grace Period Scope: Per Season** to track each season independently.

- **Per Series** (default): Simple, traditional behavior. One timer for the whole show.
- **Per Season**: Each season has its own grace timer. Perfect when different people watch different seasons.

### Dormant (Abandoned Series)

- **Days before complete series cleanup**
- Example: `60` = If no activity for 2 months, clean when storage is low
- Use for: Reclaiming space from shows you stopped watching
- **Set to empty/null**: Never clean up (protected series)

## Example Rule Configurations

### Standard Show

```log
Grace Watched: 7 days
Grace Unwatched: 14 days  
Dormant: 30 days
```

### Important Show (Protected)

```log
Grace Watched: empty
Grace Unwatched: empty
Dormant: empty
```

### Current Show (Pressure to Stay Current)

```log
Grace Watched: empty
Grace Unwatched: 7 days
Dormant: 60 days
```

## How Cleanup Works

**Three independent timers:**

1. **Grace Watched**: Series inactive for X days → Delete kept episodes
2. **Grace Unwatched**: Series inactive for X days → Delete unwatched episodes  
3. **Dormant**: Series inactive for X days + storage low → Delete all episodes

**Priority order**: Dormant (oldest shows) → Grace Watched → Grace Unwatched

**Stops automatically**: When storage goes back above threshold

## Testing (Important)

1. **Enable Global Dry Run** in Scheduler settings
2. **Test cleanup** with your settings
3. **Check logs** to see what would be deleted
4. **Disable Dry Run** when satisfied

## Series Assignment

**Only assigned series participate in cleanup:**

- Manual: Episeerr → Series Management
- Automatic: Add `episeerr_default` tag in Sonarr (with webhook)
- Protected: Create rules with empty Dormant timer

## Troubleshooting

**No cleanup happening**: Check storage threshold, ensure series are assigned to rules  
**Wrong shows deleted**: Review rule assignments and grace settings  
**Cleanup too aggressive**: Increase grace periods, enable dry run for testing
