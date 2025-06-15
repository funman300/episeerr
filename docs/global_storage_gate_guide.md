# Global Storage Gate Guide (v2.1)

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

## Understanding Grace vs Dormant (v2.1 Changes)

### 🔄 **Grace Period: Viewing Workflow** (NEW!)
- **What it does**: Automatically manages your "recently watched" episodes
- **When it runs**: Continuously, every time you watch something
- **Purpose**: Keep viewing context, then clean up old watches
- **NOT storage-driven**: Runs regardless of available space

**Example**: 7-day grace period
```
Keep 1 episode
Watch E10 → Keep E10 for 7 days → Auto-delete E10 after 7 days
```

### 🗂️ **Dormant Timer: Storage Cleanup** 
- **What it does**: Removes content from shows you've abandoned
- **When it runs**: Only when storage gate is open
- **Purpose**: Reclaim space from shows you're not watching anymore
- **IS storage-driven**: Only runs when space is actually needed

**Example**: 60-day dormant timer
```
No activity for 60 days + Storage below threshold → Remove episodes
```

### 🏛️ **Protected Rules: Never Touched**
- **What it does**: Preserves your permanent collection
- **When it runs**: Never - completely immune to cleanup
- **Purpose**: Archive important shows safely
- **Setting**: Dormant timer set to `null` (empty)

---

## The "Automatic Librarian" System

Think of Episeerr like having a smart librarian managing your TV collection:

### 📚 **Grace Period: The "Recent Reads" Desk**
Your librarian keeps recently watched episodes on your desk for easy access. After the grace period expires, they get filed away (deleted) to keep your active viewing area clean.

- **Personal habit**: Happens based on your viewing
- **Always active**: Works regardless of storage space
- **Viewing-focused**: Maintains your current show context

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

### Which Rules Participate
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

### Common Configurations

| Storage Size | Suggested Threshold | Philosophy |
|--------------|-------------------|------------|
| **1TB** | 100GB (10%) | Conservative, rarely triggers |
| **4TB** | 200GB (5%) | Balanced approach |
| **8TB** | 300GB (3.5%) | Aggressive space management |

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

---

**Next:** [Rules System Guide](rules-guide.md) - Configure viewing and storage management