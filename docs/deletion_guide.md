# Episeerr Deletion System - Complete Guide

## Overview
Episeerr has **TWO independent deletion systems** that work together:
1. **Keep Rule** - Real-time deletion triggered by watching
2. **Grace Cleanup** - Time-based scheduled cleanup (configurable interval, default 6 hours)

---

## 1. KEEP RULE (Real-Time Deletion)

**Triggers:** When you watch an episode  
**Purpose:** Maintain a sliding window of episodes  
**Ignores:** ALL dry_run settings (always deletes immediately)

### How It Works:
```
You watch: S6E10
Keep rule: keep_count = 1

Episode Timeline:
[S6E7] [S6E8] [S6E9] [S6E10] ← Just watched
  ❌     ❌     ❌      ✅

IMMEDIATE DELETION: S6E7, S6E8, S6E9
KEPT: S6E10 (most recent watched)
```

### Examples:

**Example 1: Keep 1 Episode**
```
Config: keep_count = 1
You watch: S1E1, S1E2, S1E3, S1E4

After S1E1: [S1E1] ← kept
After S1E2: [S1E2] ← kept, S1E1 deleted
After S1E3: [S1E3] ← kept, S1E2 deleted  
After S1E4: [S1E4] ← kept, S1E3 deleted

Result: Only the most recent watched episode remains
```

**Example 2: Keep 3 Episodes**
```
Config: keep_count = 3
You watch: S1E1 through S1E10

After S1E5: [S1E3][S1E4][S1E5] ← kept
            S1E1, S1E2 deleted

After S1E10: [S1E8][S1E9][S1E10] ← kept
             S1E1-S1E7 deleted

Result: Last 3 watched episodes remain
```

**Example 3: Keep 1 Season**
```
Config: keep_count = 1, keep_type = "seasons"
You watch: S2E5

Episodes before S2E5 in Season 2: Kept
All of Season 1: DELETED
Future episodes: Managed by GET rule

Result: Current season (up to where you watched) is kept
```

---

## 2. GRACE CLEANUP (Scheduled Time-Based Deletion)

**Triggers:** Runs on scheduled interval (configurable via `cleanup_interval_hours`, default 6 hours)  
**Purpose:** Delete old episodes from shows you stopped watching  
**Respects:** Global dry_run_mode AND rule-level dry_run

### Two Types:

#### A. Grace Watched (grace_watched)
**What:** Deletes OLD watched episodes, keeps last watched as bookmark  
**When:** After X days of inactivity

```
Last watched: S3E5 on Jan 1
Grace period: 10 days
Today: Jan 12 (11 days later)

Episode Status:
[S3E1][S3E2][S3E3][S3E4][S3E5] ← All watched
  ❌    ❌    ❌    ❌    🔖

[S3E6][S3E7][S3E8] ← Unwatched, not affected by grace_watched
  ✅    ✅    ✅

Result: Deletes S3E1-S3E4, KEEPS S3E5 as bookmark
```

#### B. Grace Unwatched (grace_unwatched)
**What:** Deletes unwatched episodes EXCEPT first unwatched (bookmark)  
**When:** After X days of inactivity

```
Last watched: S3E5 on Jan 1
Grace period: 20 days
Today: Jan 22 (21 days later)

Episode Status:
[S3E1][S3E2][S3E3][S3E4][S3E5] ← Watched, not affected
  ✅    ✅    ✅    ✅    ✅

[S3E6][S3E7][S3E8] ← Unwatched episodes
  🔖    ❌    ❌

Result: Deletes S3E7-S3E8, KEEPS S3E6 as "next episode" bookmark
```

### 🔖 The Bookmark System

**Grace cleanup ALWAYS preserves your viewing position:**

```
Example: 10 episodes, watched 1-5, both grace periods expire

BEFORE Cleanup:
Watched: [E1✅][E2✅][E3✅][E4✅][E5✅]
Unwatched: [E6⬜][E7⬜][E8⬜][E9⬜][E10⬜]

AFTER Grace Watched:
[E5🔖] ← Last watched kept as bookmark
[E6⬜][E7⬜][E8⬜][E9⬜][E10⬜]

AFTER Grace Unwatched:
[E5🔖][E6🔖] ← First unwatched kept as "next" bookmark
```

**You always have a resume point:**
- Grace Watched → Keeps last watched
- Grace Unwatched → Keeps first unwatched  
- **You never lose your place!**

---

## 3. DORMANT CLEANUP (Nuclear Option)

**Triggers:** Runs on scheduled interval (same as Grace cleanup, optional storage gate)  
**What:** Deletes ALL episodes from completely abandoned shows  
**When:** After X days of no activity on the entire series

```
Last activity: Jan 1 (any episode watched)
Dormant period: 90 days
Today: April 5 (94 days later)

Result: Deletes EVERY episode of the show
Purpose: Reclaim space from shows you'll never finish
```

---

## Complete Example: The Americans

### Your Settings:
```json
{
  "keep_count": 1,
  "keep_type": "episodes",
  "grace_watched": 10,
  "grace_unwatched": 20,
  "dormant_days": 90
}
```

### Timeline:

**January 1 - You watch S6E10**
- Keep rule triggers: Delete S6E1-S6E9, keep S6E10
- Result: Only S6E10 remains

**January 11 (10 days later) - Scheduled cleanup runs**
- Grace watched check: 10 days since activity
- DELETE: Nothing! (S6E10 is the bookmark - always kept)
- Result: S6E10 still there as your resume point

**If you had multiple watched episodes:**
- Watched: S6E1-S6E10
- Grace expires after 10 days
- DELETE: S6E1-S6E9
- KEEP: S6E10 (bookmark)

**January 22 (20 days later) - If you had unwatched episodes**
- Grace unwatched check: 20 days since activity  
- Downloaded but unwatched: S6E11, S6E12, S6E13
- DELETE: S6E12, S6E13
- KEEP: S6E11 (next episode bookmark)

**April 5 (90 days later) - Dormant cleanup**
- Dormant check: 90 days since ANY activity
- DELETE: Everything (nuclear option)
- Result: Entire show removed

---

## Visual Timeline

```
Day 0: Watch S6E10
├─ IMMEDIATE: Keep rule deletes S6E1-S6E9
└─ Remaining: [S6E10✅]

Day 10: Scheduled cleanup (Grace Watched)
├─ Only 1 watched episode exists (S6E10)
├─ KEPT: S6E10 (bookmark - always keep last watched)
└─ Remaining: [S6E10🔖]

Day 20: Scheduled cleanup (Grace Unwatched) 
├─ If you had S6E11, S6E12, S6E13 downloaded
├─ DELETE: S6E12, S6E13
├─ KEEP: S6E11 (next episode bookmark)
└─ Remaining: [S6E10🔖][S6E11🔖]

Day 90: Scheduled cleanup (Dormant)
├─ Dormant triggered (90 day threshold)
├─ DELETE: Everything (nuclear option)
└─ Remaining: []
```

---

## Key Differences

| Feature | Keep Rule | Grace Cleanup | Dormant |
|---------|-----------|---------------|---------|
| **Trigger** | Watch episode | Scheduled timer | Scheduled timer |
| **Speed** | Immediate | Delayed | Delayed |
| **What** | Sliding window | Time-based + bookmark | Nuclear |
| **Bookmark** | N/A | Always keeps 1 episode | Deletes everything |
| **Dry Run** | Never (always deletes) | Respects dry_run | Respects dry_run |
| **Purpose** | Active watching | Inactive shows | Abandoned shows |

---

## Common Scenarios

### Scenario 1: "I want to keep only the last episode I watched"
```json
{
  "keep_count": 1,
  "keep_type": "episodes",
  "grace_watched": null,
  "grace_unwatched": null,
  "dormant_days": null
}
```
**Result:** Only most recent watched episode exists, deleted immediately when you watch the next one

---

### Scenario 2: "I want a 2-week buffer before cleanup"
```json
{
  "keep_count": 1,
  "keep_type": "episodes",
  "grace_watched": 14,
  "grace_unwatched": 14,
  "dormant_days": 90
}
```
**Result:** 
- Real-time: Only last watched episode kept
- After 14 days inactive: Watched episodes deleted
- After 14 days inactive: Unwatched episodes deleted
- After 90 days inactive: Everything deleted

---

### Scenario 3: "I binge shows, keep the whole current season"
```json
{
  "keep_count": 1,
  "keep_type": "seasons",
  "grace_watched": 30,
  "grace_unwatched": null,
  "dormant_days": 180
}
```
**Result:**
- Real-time: Current season kept (previous seasons deleted)
- After 30 days: Watched episodes cleaned up
- Unwatched episodes: Never auto-deleted by time
- After 180 days: Everything deleted (if truly abandoned)

---

## Dry Run Behavior

### Cleanup Interval Configuration
The scheduled cleanup interval is configurable in `global_settings.json`:
```json
{
  "cleanup_interval_hours": 6  // Default: 6 hours
}
```
**Note:** This affects both Grace cleanup and Dormant cleanup timing.

### Global Dry Run (global_settings.json)
```json
{
  "dry_run_mode": true
}
```
**Effect:** All Grace/Dormant cleanup queued for approval

### Rule-Level Dry Run (config.json)
```json
{
  "dry_run": true
}
```
**Effect:** This rule's Grace/Dormant cleanup queued for approval

### Important Notes:
- **Keep rule ALWAYS deletes** (ignores all dry_run settings)
- If EITHER global OR rule dry_run is true → Queue for approval
- If BOTH are false → Delete immediately

---

## Per-Season vs Per-Series Tracking

### Per-Series (Default)
```json
{
  "grace_scope": "series"
}
```
- One activity date for entire series
- Grace periods apply to whole show
- Watch S6E10 → resets timer for ALL seasons

### Per-Season
```json
{
  "grace_scope": "season"
}
```
- Separate activity date per season
- Grace periods apply per season independently
- Watch S6E10 → only resets Season 6 timer
- Season 5 can expire separately

---

## FAQ

**Q: Why are episodes still there after I watched the next one?**  
A: Check your Keep rule config. If keep_count=3, you'll keep the last 3 watched episodes.

**Q: Why did episodes get deleted even though I'm still watching?**  
A: If you took longer than your grace period between episodes, Grace cleanup deleted OLD episodes but kept your bookmark (last watched OR first unwatched). Increase grace periods or disable them.

**Q: Will Grace cleanup delete my progress?**  
A: No! Grace Watched keeps your last watched episode as a bookmark. Grace Unwatched keeps your next episode. You can always resume.

**Q: I set dry_run=true but Keep rule still deletes!**  
A: Keep rule ALWAYS deletes immediately (by design). Dry run only affects Grace/Dormant cleanup.

**Q: How do I test Grace cleanup without deleting?**  
A: Set `dry_run_mode: true` in global_settings.json, then approve deletions manually.

**Q: What's the difference between grace_unwatched and dormant?**  
A: grace_unwatched deletes unwatched episodes after X days. dormant deletes EVERYTHING after X days of no activity at all.

---

## Recommended Settings

### Conservative (Safe)
```json
{
  "keep_count": 3,
  "keep_type": "episodes",
  "grace_watched": 30,
  "grace_unwatched": 60,
  "dormant_days": 180
}
```

### Aggressive (Space Saving)
```json
{
  "keep_count": 1,
  "keep_type": "episodes",
  "grace_watched": 7,
  "grace_unwatched": 14,
  "dormant_days": 30
}
```

### Binge Watcher
```json
{
  "keep_count": 1,
  "keep_type": "seasons",
  "grace_watched": 14,
  "grace_unwatched": null,
  "dormant_days": 90
}
```
