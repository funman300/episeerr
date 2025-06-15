# Rules Guide (v2.1)

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

### Grace Period (Viewing-based cleanup) - Optional
**Days to protect watched content:**
- **7 days**: Will still keep your "keep block" but will wait 7 days before deleting the previous ones 
- **null/empty**: Keep watched content forever (no grace cleanup)

### Dormant Timer (Storage-based cleanup) - Optional
**Days before abandoned series cleanup:**
- **30 days**: Clean up shows with no activity for a month when storage is low
- **null/empty**: Never clean up abandoned shows (protected from storage cleanup)

---

## Simple Rule Examples

### Minimal Automation (Just Next Episode)
```
Get: 1 episode, Action: Search
Keep: null, Grace: null, Dormant: null
```
**Result**: Next episode ready, everything else manual

### Viewing Only (No Storage Management)
```
Get: 3 episodes, Keep: 1 episode
Grace: null, Dormant: null
```
**Result**: Episode management when you watch, no automatic cleanup

### Storage Only (No Viewing Automation)
```
Get: null, Keep: null
Grace: null, Dormant: 60 days
```
**Result**: Only storage cleanup, no viewing automation

### Complete Automation
```
Get: 3 episodes, Keep: 2 episodes
Grace: 7 days, Dormant: 60 days
```
**Result**: Full automation with viewing and storage management

---

## Rule Examples

### Next Episode Ready (No Cleanup)
```
Get: 1 episode
Keep: 1 episode  
Grace: null (keep forever)
Dormant: null (never cleanup)
```
**Perfect for**: Shows you're actively watching without storage pressure

### Binge Ready (Light Cleanup)
```
Get: 5 episodes
Keep: 2 episodes
Grace: 7 days  
Dormant: 60 days
```
**Perfect for**: Popular shows you binge watch

### Season Collector (Archive Mode)
```
Get: 1 season
Keep: all seasons
Grace: null (keep forever)
Dormant: null (never cleanup)
```
**Perfect for**: Shows you want to keep permanently

### Storage Saver (Aggressive Cleanup)
```
Get: 1 episode
Keep: 1 episode
Grace: 1 day
Dormant: 7 days
```
**Perfect for**: Limited storage, trying new shows

---

## How the NEW Grace Logic Works

### OLD (Confusing) Way:
- Grace = Delete unwatched content after X days
- Hard to understand and predict

### NEW (Intuitive) Way:  
- Grace = Keep watched content for X days after watching
- Clear, predictable behavior

### Example: Grace Period in Action
**Rule**: Get 3, Keep 1, Grace 7 days

```
Day 1 - Watch E5:
✅ Keep E5 (protected for 7 days)
✅ Get E6, E7, E8 (next episodes)  
✅ Delete E1-E4 (old episodes)

Day 8 - Grace expires:
✅ Delete E5 (grace period over)
✅ Library now has: E6, E7, E8 (fresh unwatched)
```

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