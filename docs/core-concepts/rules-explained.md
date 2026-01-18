# Rules Explained

Understanding what rules are and how they control episode management.

## What is a Rule?

A **rule** is a set of instructions that tells Episeerr:
- **GET** - How many future episodes to prepare
- **KEEP** - How many watched episodes to retain
- **ACTION** - Whether to just monitor or actively search
- **GRACE/DORMANT** - Time-based cleanup settings

Think of rules as "profiles" for different types of shows.

---

## The Three Settings

### 1. GET (What to Prepare Next)

**Controls:** Which episodes to monitor/search when you watch something

**Options:**
- **X Episodes** - Get specific number (e.g., "Get 3 episodes" = next 3)
- **X Seasons** - Get entire season(s) (e.g., "Get 1 season" = all of next season)
- **All** - Get everything available from current point forward

**Example:**
```
You watch: S1E5
Get: 2 episodes
Result: S1E6 and S1E7 now monitored/searched
```

**When it happens:** Real-time when you watch an episode (via webhook)

---

### 2. KEEP (What to Retain)

**Controls:** How many watched episodes to keep before deleting

**Options:**
- **X Episodes** - Keep last X watched (e.g., "Keep 1" = only most recent)
- **X Seasons** - Keep last X full seasons
- **All** - Never delete watched episodes

**Example:**
```
You watch: S1E5
Keep: 1 episode
Result: S1E1-E4 deleted, S1E5 kept
```

**When it happens:** Real-time when you watch an episode (immediate deletion)

---

### 3. ACTION (How to Get)

**Controls:** Whether to just mark for monitoring or actively search

**Options:**
- **Monitor** - Mark episodes as monitored (Sonarr will grab when available)
- **Search** - Actively search for episodes immediately

**Example:**
```
Get: 2 episodes
Action: Search
Result: Sonarr immediately searches for next 2 episodes
```

---

## Real-World Example

**Your "Binge Watcher" rule:**

```json
{
  "name": "Binge Watcher",
  "get_type": "episodes",
  "get_count": 3,
  "keep_type": "episodes", 
  "keep_count": 1,
  "action_option": "search"
}
```

**What happens:**

```
Watch S1E1:
├─ GET: Search for S1E2, S1E3, S1E4 (3 episodes)
└─ KEEP: Keep S1E1 (1 episode)

Watch S1E2:
├─ GET: Search for S1E3, S1E4, S1E5
├─ KEEP: Keep S1E2
└─ DELETE: S1E1 (outside keep window)

Watch S1E3:
├─ GET: Search for S1E4, S1E5, S1E6
├─ KEEP: Keep S1E3
└─ DELETE: S1E2
```

**Result:** Always have 3 episodes queued ahead, keep only last watched

---

## Grace Periods (Time-Based Cleanup)

**Separate from GET/KEEP** - These run on a schedule (e.g., every 6 hours)

### Grace Watched

**What:** Deletes OLD watched episodes after X days of inactivity  
**Keeps:** Last watched episode as bookmark  
**Use case:** Free up space from shows you stopped watching

**Example:**
```
Last watched S2E5 (14 days ago)
Grace Watched: 10 days

Result: Delete S2E1-S2E4, keep S2E5 as bookmark
```

---

### Grace Unwatched

**What:** Deletes unwatched episodes after X days of inactivity  
**Keeps:** First unwatched episode as bookmark  
**Use case:** Clear backlog while preserving resume point

**Example:**
```
Downloaded S2E6-E10 (20 days ago, never watched)
Grace Unwatched: 14 days

Result: Delete S2E7-E10, keep S2E6 as "next episode"
```

---

### Dormant

**What:** Deletes ALL episodes after X days of complete inactivity  
**Keeps:** Nothing (nuclear option)  
**Use case:** Reclaim space from truly abandoned shows

**Example:**
```
Last activity: 90 days ago
Dormant: 60 days

Result: Delete everything from the show
```

**Note:** Usually paired with storage gate (only runs when storage is low)

---

## Rule Assignment

**Series must be assigned to a rule to be managed.**

### Three Ways to Assign:

1. **Auto-Assign** - Automatic when added (enabled in Global Settings)
2. **Tags** - `episeerr_default` assigns to default rule automatically
3. **Manual** - Series Management page in Episeerr

---

## Multiple Rules

**Why use multiple rules?**

Different shows have different needs:

| Show Type | Rule Name | GET | KEEP | Grace | Why |
|-----------|-----------|-----|------|-------|-----|
| **Current shows** | "Weekly" | 1 ep | 3 eps | 30d | Stay current, keep buffer |
| **Binge shows** | "Binge" | 3 eps | 1 ep | 14d | Aggressive queueing |
| **Important shows** | "Protected" | All | All | null | Never delete |
| **Try-out shows** | "Testing" | 2 eps | 1 ep | 7d | Quick cleanup if dislike |

---

## Common Patterns

### Pattern 1: Aggressive Cleanup
```
GET: 2 episodes
KEEP: 1 episode
Grace Watched: 7 days
Grace Unwatched: 14 days
Dormant: 30 days
```
**Use for:** Limited storage, lots of shows

---

### Pattern 2: Conservative
```
GET: 1 season
KEEP: 1 season
Grace Watched: 60 days
Grace Unwatched: 90 days
Dormant: 180 days
```
**Use for:** Ample storage, careful management

---

### Pattern 3: Protected
```
GET: All
KEEP: All
Grace Watched: null
Grace Unwatched: null
Dormant: null
```
**Use for:** Shows you never want deleted

---

## Key Concepts

**KEEP vs GRACE:**
- **KEEP** = Real-time deletion when watching (immediate)
- **GRACE** = Scheduled cleanup for inactive shows (delayed)
- **They work together** for maximum space savings

**Bookmarks:**
- Grace cleanup ALWAYS keeps at least one episode
- You never lose your viewing position

**Dry Run Mode:**
- Keep rule ALWAYS deletes (ignores dry run)
- Grace/Dormant respect dry run setting
- Test safely before going live

---

## Next Steps

- **Create rules:** [Rules Guide](../configuration/rules-guide.md)
- **Copy configs:** [Rule Examples](../configuration/rule-examples.md)  
- **Understand deletions:** [Deletion System](deletion-system.md)
- **Assign series:** [First Series Tutorial](../getting-started/first-series.md)
