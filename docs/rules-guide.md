# Rules Guide (v2.2)

Rules tell Episeerr how to manage episodes automatically. **Rules are completely optional** - you can use just episode selection without any rules.

# ⚠️ **Important: Rules Assume Linear Viewing**

**Rules work best when you watch episodes in order (S1E1 → S1E2 → S1E3...).**

### ✅ **Perfect for Rules:**
- Watching new episodes as they air
- Binge-watching shows in order
- Following a series from start to finish

### ❌ **Not Great for Rules:**
- Jumping between seasons randomly
- Watching "best episodes" only
- Non-sequential viewing patterns

**For non-linear viewing:** Use episode selection instead of rules, or create dormant-only rules (no grace/keep settings).

---

## Rule Components (NEW!)

**All components are optional** - set only what you want automated.

### Get Episodes (What to prepare next) - Optional
**Type + Count:**
- **Episodes**: Get X individual episodes (e.g., "3 episodes")
- **Seasons**: Get X full seasons (e.g., "1 season") 
- **All**: Get everything available
- **Skip this**: Episodes only managed manually

### Keep Episodes (What to retain after watching) - Optional
**Type + Count:**
- **Episodes**: Keep X individual episodes (e.g., "2 episodes")
- **Seasons**: Keep X full seasons (e.g., "1 season")
- **All**: Keep everything forever
- **Skip this**: No automatic retention management

### Grace Periods (Multi-Timer System) - Optional

**All grace periods are independent - use any combination that fits your viewing style:**

#### Grace Watched   
**Days before kept episodes expire from inactivity:**
- **30 days**: Your watched expire after a month of no series activity
- **null/empty**: Keep forever (never expire)
- **Use for**: Rotating collection, making room for new content

#### Grace Unwatched (Watch Deadlines)
**Days before unwatched episodes expire:**
- **14 days**: New episodes have 2 weeks to be watched or deleted
- **null/empty**: No pressure to watch new content
- **Use for**: Staying current, preventing backlog buildup
## The "Automatic Librarian" System

Think of Episeerr like having a smart librarian managing your TV collection:


### 🔄 **Grace Watched: The "Recent Reads" Rotation**
Your librarian keeps your last watched on the shelf for easy access. After watched grace, they rotate these out to make room for new ones.

```
Grace: 7 type  watched
```
### If a series has no activity after x days then the last episode watched and prior ones will be removed

### ⏰ **Grace Unwatched: The "New Arrivals" Pressure**
New episodes go on a "new arrivals" shelf with a deadline. If you don't watch them by the deadline, they get removed.

```
Grace: 7 type  unwatched
```
### If a series has no activity after x days then any episodes that are after the last episode watched will be removed

## use none or any combo
## Example:
```
Get 3
Keep 3
Grace_watched 7
Grace_unwatched 14
Dormant 30
```
### After s3ep5 is watched it will keep ep 3 4 and 5 and fetch ep 6 7 and 8 until ep 6 is watched then it will have ep 4 5 and 6 and so on
    ** Unless there is no new watch for 7 days then it will delete those trailing 3 episodes regardless
    * 14 days it will then also remove any unwatched (ep7 8 and 9) as well
    * 30 days of no activity then noone is watching remove all episodes

### Dormant Timer (Abandoned Series Cleanup) - Optional
**Days before complete series cleanup:**
- **90 days**: If no activity for 3 months, clean up when storage is low
- **null/empty**: Never clean up abandoned series (protected)
- **Use for**: Reclaiming space from shows you've stopped watching

---

## Simple Rule Examples

### Minimal Automation (Just Next Episode)
```
Get: 1 episode, Action: Search
Keep: null, Grace: all null, Dormant: null
```
**Result**: Next episode ready, everything else manual

### Viewing Only (No Storage Management)
```
Get: 3 episodes, Keep: 1 episode
Grace: all null, Dormant: null
```
**Result**: Episode management when you watch, no automatic cleanup

### Storage Only (No Viewing Automation)
```
Get: null, Keep: null
Grace: all null, Dormant: 60 days
```
**Result**: Only storage cleanup, no viewing automation


### Key Insights
- **Multiple timers run independently** - each serves a different purpose
- **Buffer protects against mistakes** - short-term safety net
- **Watched manages your collection** - medium-term rotation
- **Unwatched creates pressure** - forces you to stay current  
- **Dormant handles abandonment** - long-term space reclamation


---

## Season Count Logic

### Get Seasons
- **1 season**: Rest of current season + next full season if current is finished
- **2 seasons**: Rest of current + next 2 full seasons
- **3 seasons**: Rest of current + next 3 full seasons

### Keep Seasons  
- **1 season**: Keep current season only
- **2 seasons**: Keep current + previous season
- **3 seasons**: Keep current + previous 2 seasons

### Example: Currently on S2E8 (Season 2 has 10 episodes)
**Get 1 season**: Episodes S2E9, S2E10 + all of S3  
**Keep 1 season**: Keep all of S2

---

## Migration from Single Grace

If upgrading from v2.1 single grace system:
- **Old grace_days** becomes **grace_buffer** automatically
- **Add grace_watched/grace_unwatched** as desired
- **No behavior change** unless you add new grace types

This gives you the same safety as before, plus new options for more control.

---

## Quick Troubleshooting

### Rule Not Working
- ✅ Check series is assigned to the rule (Series Management page)
- ✅ Verify webhook setup if using viewing automation
- ✅ Test with dry run mode first

### Wrong Episodes  
- ✅ Review Get vs Keep settings
- ✅ Check if series is assigned to correct rule

---

**Next**: [Episode Selection Guide](episode-selection.md) - Manual episode management
