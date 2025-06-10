# Global Storage Gate Guide

The Global Storage Gate is Episeerr's intelligent storage management system that keeps your library size under control with one simple threshold.

## Core Concept

**One global setting controls all cleanup across your entire library.**

Instead of managing storage per-rule or per-series, you set one threshold that controls when cleanup happens. This is both simpler and smarter than traditional approaches.

## How It Works

### The Simple Setup
1. **Set global threshold:** "20GB free space"
2. **Create rules with timers:** Grace and/or dormant settings
3. **Assign series to rules:** Only assigned series participate
4. **Automatic operation:** Cleanup only when needed

### The Smart Behavior
- **Gate CLOSED:** Free space ≥ threshold → No cleanup runs
- **Gate OPEN:** Free space < threshold → Cleanup until back above threshold
- **Surgical precision:** Stops immediately when threshold met
- **Protected rules:** Rules without grace/dormant never touched

## The "Chips" Philosophy

Think of your episodes like poker chips in a casino:

### 🟡 Grace Period: "Take My Chips Off The Table"
- **You're still playing** the game (actively watching)
- **Clear some space** by removing unwatched episodes
- **Keep your place** in the show (maintain viewing context)
- **Strategy:** "I'll finish this show, just need room to breathe"

**Example:** Breaking Bad - 7 days grace
- Watched through S03E10
- Grace cleanup removes S01-S02 (unwatched buffer episodes)
- Keeps S03E08-E12 (current viewing context)
- You can continue from where you left off

### 🔴 Dormant Timer: "Remove My Chips From The Bank"
- **You've left the table** (abandoned the show)
- **Aggressive cleanup** to reclaim maximum storage
- **No viewing context** needed (show is abandoned)
- **Strategy:** "I'm not coming back to this anytime soon"

**Example:** Lost - 90 days dormant
- Haven't watched in 3+ months
- Dormant cleanup removes ALL episodes
- Series stays in Sonarr but no files remain
- Maximum storage reclaimed

### 🛡️ Protected Rules: "House Money"
- **Permanent collection** shows
- **Rules with null grace/dormant** settings
- **Never touched** by time-based cleanup
- **Strategy:** "These are keepers, don't touch them"

## Configuration

### Global Settings
Access via Episeerr web interface → Scheduler page:

| Setting | Purpose | Example |
|---------|---------|---------|
| **Storage Threshold** | When cleanup triggers | `20` (GB) |
| **Cleanup Interval** | How often to check | `6` (hours) |
| **Global Dry Run** | Test mode for safety | `true`/`false` |

### Rule Settings
Each rule can have time-based cleanup:

| Setting | Purpose | Value |
|---------|---------|--------|
| **Grace Days** | Days before grace cleanup | `7` or `null` |
| **Dormant Days** | Days before dormant cleanup | `30` or `null` |

**Key:** `null` = protected (never cleaned up)

## Cleanup Priority

When the storage gate opens, cleanup happens in this specific order:

### 1. Dormant Shows (Highest Priority)
- **Order:** Oldest dormant first
- **Behavior:** Aggressive cleanup (all/most episodes)
- **Goal:** Maximum storage reclamation

### 2. Grace Shows (Medium Priority)  
- **Order:** Oldest grace first
- **Behavior:** Surgical cleanup (unwatched episodes)
- **Goal:** Free space while preserving context

### 3. Stop When Threshold Met
- **Immediate halt** when free space ≥ threshold
- **No unnecessary cleanup** beyond storage needs
- **Preserves shows** that didn't need processing

### Example Cleanup Sequence
```
Storage Gate Opens: 15GB free < 20GB threshold

🔴 DORMANT (oldest first):
  Lost (120 days) → Remove ALL episodes → +8GB
  Dexter (95 days) → Remove ALL episodes → +6GB
  Current: 29GB free → STOP (above 20GB threshold)

✅ GRACE SHOWS PRESERVED:
  Breaking Bad (15 days) → Not processed
  The Office (10 days) → Not processed
```

## Storage Gate States

### 🔒 Gate CLOSED
- **Condition:** Free space ≥ threshold
- **Behavior:** No cleanup runs
- **Status:** "Storage gate CLOSED - no cleanup needed"
- **Action:** Normal operation, no files deleted

### 🔓 Gate OPEN
- **Condition:** Free space < threshold  
- **Behavior:** Cleanup until threshold met
- **Status:** "Storage gate OPEN - cleanup will run"
- **Action:** Process candidates in priority order

## Rule Protection

### Automatic Protection
Rules are automatically protected from time-based cleanup when:
- **Grace Days:** Set to `null` (empty)
- **Dormant Days:** Set to `null` (empty)
- **Both null:** Rule never participates in cleanup

### Example Protected Rule
```
Rule: "Permanent Collection"
Get: all
Action: monitor  
Keep: all
Grace Days: null
Dormant Days: null

Result: Series in this rule are NEVER cleaned up
```

### Mixed Protection
You can mix protected and cleanup rules:
```
🛡️ "Archive Shows" - Grace: null, Dormant: null (protected)
🟡 "Current Shows" - Grace: 7 days, Dormant: null (grace only)
🔴 "Trial Shows" - Grace: null, Dormant: 30 days (dormant only)
🟡🔴 "Active Shows" - Grace: 14 days, Dormant: 90 days (both)
```

## Safety Features

### Global Dry Run Mode
- **Test cleanup logic** without deleting files
- **See what would be cleaned** in logs
- **Perfect for testing** new configurations
- **Enable in main settings** for system-wide safety

### Rule-Specific Dry Run
- **Individual rule testing** alongside global dry run
- **Granular control** for specific show types
- **Overrides global setting** for that rule only

### Storage Gate Validation
- **Prevents unnecessary cleanup** when storage is adequate
- **Only runs when truly needed** (below threshold)
- **Stops immediately** when goal achieved
- **Logs all decisions** for transparency

## Best Practices

### Setting Your Threshold
- **Conservative approach:** Set threshold higher than you think you need
- **Monitor usage:** Watch storage patterns for a few weeks
- **Adjust gradually:** Lower threshold as you get comfortable
- **Consider buffer:** Account for active downloads and temporary files

### Rule Design
- **Start simple:** Begin with one or two rules
- **Test with dry run:** Always test before going live
- **Use protection:** Set important shows to protected rules
- **Monitor logs:** Watch cleanup behavior and adjust

### Common Thresholds
| Storage Size | Suggested Threshold | Use Case |
|--------------|-------------------|----------|
| **500GB** | 50GB (10%) | Small home server |
| **2TB** | 100GB (5%) | Medium library |
| **8TB** | 200GB (2.5%) | Large collection |
| **16TB+** | 500GB (3%) | Massive library |

## Troubleshooting

### Storage Gate Not Working
- **Check threshold setting:** Ensure it's configured in UI
- **Verify current space:** Look at storage status display  
- **Review rule assignments:** Only assigned series participate
- **Check grace/dormant:** Rules need timers to participate

### Cleanup Too Aggressive
- **Increase threshold:** Give more storage buffer
- **Extend timers:** Longer grace/dormant periods
- **Use protection:** Move important shows to protected rules
- **Enable dry run:** Test changes safely

### Cleanup Not Happening
- **Lower threshold:** Gate may never open with current setting
- **Check rule timers:** Ensure rules have grace/dormant settings
- **Verify assignments:** Series must be assigned to rules
- **Review logs:** Look for cleanup decision messages

### Wrong Shows Getting Cleaned
- **Check priority order:** Dormant processes before grace
- **Review assignment:** Ensure series are in correct rules
- **Verify timers:** Grace/dormant settings affect behavior
- **Use dry run:** Preview cleanup before enabling

## Advanced Configuration

### Multiple Storage Scenarios
- **Critical shows:** Protected rules (null timers)
- **Active viewing:** Short grace (3-7 days)
- **Casual shows:** Medium grace (14-30 days)  
- **Trial shows:** Short dormant (30-60 days)
- **Archive shows:** Long dormant (365+ days) or protected

### Dynamic Thresholds
While Episeerr uses a fixed threshold, you can adjust based on:
- **Seasonal viewing:** Lower threshold during heavy watching periods
- **Storage upgrades:** Adjust threshold when adding drives
- **Library growth:** Monitor and adjust as collection expands

---

**Next:** [Rules System Guide](rules-guide.md) - Configure episode automation behavior