# Global Storage Gate Guide (v2.2)

The Global Storage Gate is **completely optional** - it only runs cleanup when your storage actually needs it.

## Do You Need Storage Gate?

### ❌ **Skip Storage Gate If:**
- You have plenty of storage space
- You prefer manual cleanup
- You only want episode selection
- You're just testing Episeerr

### ✅ **Use Storage Gate If:**
- Storage space is limited
- You want automatic cleanup when space gets low
- You have shows you're okay with losing
- You want hands-off storage management

---

## Core Concept (Optional Feature)

**Set one threshold, cleanup only happens when needed.**

Example: Set "20GB" and cleanup only runs when free space drops below 20GB. When space is above 20GB, no storage cleanup happens at all.

## How It Works (When Enabled)

### Simple Setup
1. **Set trigger threshold**: "20GB free space" (in Scheduler page)
2. **Create rules with dormant timers**: Only rules with dormant days participate
3. **Assign series to rules**: Only assigned series can be cleaned up
4. **Automatic operation**: Cleanup only when storage is actually low

### Smart Behavior
- **Gate CLOSED**: Free space ≥ threshold → No cleanup runs (storage is fine)
- **Gate OPEN**: Free space < threshold → Cleanup until back above threshold
- **Surgical precision**: Stops immediately when threshold is met
- **Protected rules**: Rules without dormant timers are never touched

---

## Understanding the Three Grace Types + Dormant (v2.2)

### 🔄 **Grace Watched: Rotating Collection**
- **What it does**: Your kept episodes expire after x days
- **When it runs**: Based on fixed timer
- **Purpose**: Rotate out old favorites to make room for new ones  
- **Timing**: X days from date added after last watch activity on the series
- **Storage impact**: Medium - manages your active collection size

### ⏰ **Grace Unwatched: Watch Deadlines**
- **What it does**: New episodes get deadline to be watched
- **When it runs**: Based on individual episode download dates
- **Purpose**: Pressure to watch new content or lose it
- **Timing**: X days from when episode was downloaded
- **Storage impact**: High - prevents backlog accumulation

### 🗂️ **Dormant Timer: Abandoned Series Cleanup**
- **What it does**: Nuclear cleanup for completely abandoned shows
- **When it runs**: Only when storage gate is open
- **Purpose**: Reclaim space from shows you've stopped watching
- **Timing**: X days from any series activity + storage below threshold
- **Storage impact**: Maximum - removes entire abandoned series

### 🏛️ **Protected Rules: Never Touched**
- **What it does**: Preserves your permanent collection
- **When it runs**: Never - completely immune to cleanup
- **Purpose**: Archive important shows safely
- **Setting**: Dormant timer set to `null` (empty)
- **Storage impact**: None - these shows are permanent

---

## The "Automatic Librarian" System

Think of Episeerr like having a smart librarian managing your TV collection:


### 🔄 **Grace Watched: The "Recent Reads" Rotation**
Your librarian keeps your last watched on the shelf for easy access. After watched grace, they rotate these out to make room for new ones.

```
Keep: 3
Grace:3 type  watched
```
### after watching e6 the keep block is now e4,5,6 but wont delete them until after the grace 3 days

### ⏰ **Grace Unwatched: The "New Arrivals" Pressure**
New episodes go on a "new arrivals" shelf with a deadline. If you don't watch them by the deadline, they get removed.

```
Get: 3

Grace:3 type  unwatched
```
### after watching e6 will get ep7,8,9 but remove them after the grace 3 days

## use none or any combo

### 🗂️ **Dormant Cleanup: The "Spring Cleaning"**
When storage gets tight, your librarian looks for shows you've completely abandoned and removes them to make space for new content.

- **Storage-driven**: Only happens when space is actually needed
- **Selective**: Targets oldest, most abandoned content first
- **Stops when done**: No unnecessary removal once storage is adequate

### 🏛️ **Protected Collection: The "Special Archives"**
Some shows are marked as permanent collection - your librarian never touches these no matter how full storage gets.

- **Permanent safety**: Never removed regardless of space or time
- **Your choice**: You decide what goes in the protected collection
- **Storage awareness**: These don't participate in space management

---


---

## Rule Assignment for Storage Gate

### How to Assign Series (Covered in Rules Guide)
See [Rules Guide](rules-guide.md) for detailed assignment instructions.

### Quick Reference
- **Manual assignment**: Episeerr interface → Series Management
- **Automatic assignment**: Add `episeerr_default` tag in Sonarr
- **Protected series**: Set Dormant to `null` (never cleaned up)

---

## Configuration (Scheduler Page)

### Global Settings
| Setting | Purpose | Example |
|---------|---------|---------|
| **Storage Threshold** | Cleanup trigger point | `20` GB |
| **Cleanup Interval** | How often to check storage | `6` hours |
| **Global Dry Run** | Test mode for safety | `true`/`false` |

### Which Rules Participate in Storage Gate
- **Rules with Dormant timers**: Participate in storage cleanup
- **Rules with Dormant = null**: Protected (never cleaned up)
- **Grace timers**: Don't affect storage gate (viewing-only)

---

## Best Practices (Storage Focus)

### Setting Your Threshold
- **Conservative start**: Set higher than you think (e.g., 15% of total storage)
- **Monitor patterns**: Watch for a few weeks to understand usage
- **Adjust gradually**: Lower threshold as you get comfortable

### Protecting Important Shows
- **Set Dormant to null**: Never participate in storage cleanup
- **Use separate rules**: Create "Archive" rules with no dormant timer
- **Test with dry run**: Always verify behavior before going live

### Balancing Grace Types
- **Watched for collection**: 2-8 weeks depending on viewing habits
- **Unwatched for pressure**: 1-3 weeks depending on download speed
- **Dormant for abandonment**: 1-6 months depending on storage constraints

### Common Configurations

| Storage Size | Suggested Threshold | Buffer | Watched | Unwatched | Dormant |
|--------------|-------------------|--------|---------|-----------|---------|
| **1TB** | 100GB (10%) | 7d | 60d | null | 180d |
| **4TB** | 200GB (5%) | 5d | 30d | 21d | 90d |
| **8TB** | 300GB (3.5%) | 3d | 14d | 10d | 60d |

---

## Storage Gate Troubleshooting

### Gate Never Opens
- **Check threshold**: May be set too low for your usage patterns
- **Monitor space**: Verify you actually reach the threshold
- **Review downloads**: Factor in active downloads and temporary files

### Gate Always Open  
- **Increase threshold**: Give yourself more storage buffer
- **Check participating rules**: Ensure rules have dormant timers set
- **Review assignments**: Unassigned series can't be cleaned up

### Wrong Shows Getting Cleaned
- **Check dormant timers**: Only rules with dormant days participate
- **Review rule assignments**: Ensure series are in correct rules  
- **Use dry run**: Test changes before enabling live cleanup

### Grace Periods Not Working
- **Check rule configuration**: Verify grace fields are set correctly
- **Review timing**: Grace periods work on different schedules
- **Monitor logs**: Check for processing errors in cleanup logs
- **Verify assignments**: Series must be assigned to rules with grace settings

---

**Next:** [Rules System Guide](rules-guide.md) - Configure viewing and storage management