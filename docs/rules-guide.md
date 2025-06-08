# Rules System Guide

Rules define how Episeerr automatically manages episodes when you watch shows. Each rule contains settings for what episodes to prepare, how to handle watched content, and when to clean up.

## Rule Components

Every rule has these components:

| Setting | Purpose | Options |
|---------|---------|---------|
| **Get Option** | How many upcoming episodes to prepare | `1`, `2`, `3`, `season`, `all` |
| **Action Option** | How to handle prepared episodes | `monitor`, `search` |
| **Keep Watched** | What to retain after watching | `1`, `2`, `season`, `all` |
| **Monitor Watched** | Keep watched episodes monitored | `true`, `false` |
| **Grace Days** | Days before cleanup after watching | Number or `null` |
| **Dormant Days** | Days before cleanup if no activity | Number or `null` |

## Creating Your First Rule

1. **Access Episeerr:** `http://your-server:5002`
2. **Go to Rules section**
3. **Create New Rule:**
   - **Name:** `my_shows` (or whatever you prefer)
   - **Get Option:** `1` (next episode only)
   - **Action Option:** `search` (download automatically)
   - **Keep Watched:** `1` (keep last watched)
   - **Monitor Watched:** `false` (unmonitor after watching)
   
   **Time-Based Cleanup (Optional):**
   - **Grace Days:** `7` (cleanup after a week) *or leave blank for no cleanup*
   - **Dormant Days:** `30` (abandon after a month) *or leave blank for no cleanup*

4. **Save the rule**
5. **Assign series:** Go to Series Management and assign shows to your new rule

> **Note:** Time-based cleanup is completely optional. You can use just viewing-based automation, just time-based cleanup, or both together.

## Rule Examples

### "Next Episode Ready" (No Cleanup)
Perfect for actively watching shows without automatic deletion:
```
Get: 1, Search, Keep: 1
Monitor Watched: false
Grace: null, Dormant: null
```
**Behavior:** Always have next episode ready, no automatic cleanup

### "Viewing Only" (Webhook Automation)
Episode management based only on viewing activity:
```
Get: 3, Search, Keep: 2  
Monitor Watched: false
Grace: null, Dormant: null
```
**Behavior:** Episodes managed by viewing, no time-based deletion

### "Cleanup Only" (No Viewing Automation)
Just time-based cleanup without viewing response:
```
Get: all, Monitor, Keep: all
Monitor Watched: true  
Grace: 14 days, Dormant: 90 days
```
**Behavior:** No viewing automation, just scheduled cleanup

### "Small Buffer" 
For shows you watch regularly:
```
Get: 3, Search, Keep: 2  
Monitor Watched: false
Grace: 7 days, Dormant: 60 days
```
**Behavior:** 3 episodes ahead, keep 2 behind, weekly cleanup

### "Season Collector"
For shows you want to keep:
```
Get: season, Monitor, Keep: season
Monitor Watched: true  
Grace: null, Dormant: null
```
**Behavior:** Get full seasons, keep everything, no cleanup

### "Storage Saver"
Minimal storage impact:
```
Get: 1, Search, Keep: 1
Monitor Watched: false
Grace: 1 day, Dormant: 7 days
```
**Behavior:** Immediate cleanup, fast abandonment

## How Rules Work

### When You Watch an Episode

1. **Webhook received:** Tautulli/Jellyfin sends viewing data
2. **Series lookup:** Episeerr finds the rule for this series  
3. **Update episodes:** Based on rule settings:
   - **Unmonitor** old episodes (before keep block)
   - **Monitor** new episodes (based on get option)
   - **Search** if action_option is "search"

### Example: Rule with Get: 2, Keep: 2

**Before watching:** You have S01E01-E05
```
E01 [watched] E02 [watched] E03 [current] E04 [ready] E05 [ready]
```

**After watching E03:**
```
E02 [keep] E03 [keep] E04 [current] E05 [ready] E06 [new!]
```
- E01 gets unmonitored/deleted (outside keep block)
- E06 gets monitored/searched (get option = 2)

## Time-Based Cleanup (Optional)

Rules can include automatic cleanup based on time. **This is completely optional** - you can use rules without any time-based cleanup.

### When to Use Time-Based Cleanup
- **With viewing automation:** Supplement webhook-based management
- **Without viewing automation:** Pure time-based library maintenance  
- **Mixed approach:** Some rules with timers, others without

### Grace Period (Optional)
**Purpose:** Clean up old episodes while maintaining viewing context
**Trigger:** X days after watching an episode
**Behavior:** Removes episodes outside the "keep" block
**Setting:** Number of days or `null` (disabled)

### Dormant Timer (Optional)  
**Purpose:** Aggressive cleanup for abandoned shows
**Trigger:** X days with no viewing activity
**Behavior:** Removes most/all episodes (configurable)
**Setting:** Number of days or `null` (disabled)

### Timer Combinations

| Grace | Dormant | Use Case |
|-------|---------|----------|
| 7 days | 30 days | Active viewing with quick abandonment |
| 14 days | 90 days | Casual viewing with seasonal cleanup |
| null | 365 days | Archive shows, yearly cleanup |
| 1 day | null | Immediate cleanup, never abandon |

## Rule Assignment

## Rule Assignment

### How Rule Assignment Really Works

**Important:** Episeerr **only manages series that are explicitly assigned to rules**. Unassigned series are completely ignored.

### Default Rule Purpose
The **default rule** is used for:
- **Series with `episeerr_default` tag** - automatically assigned via Sonarr webhook
- **Pilot episode workflow** - when user selects only S01E01, tag is removed and series goes to default rule
- **NOT for unassigned series** - those are ignored entirely

### Assignment Methods

#### No Tag/Manual Addition
- **Series added normally to Sonarr** → **No Episeerr management** 
- **Uses standard Sonarr behavior** - Episeerr doesn't touch it
- **Must manually assign** in Episeerr interface if you want management

#### episeerr_default Tag
- **Forces assignment** to default rule via Sonarr webhook
- **Immediate automation** - episodes managed according to default rule settings
- **Tag removed** after processing

#### episeerr_select Tag  
- **Triggers episode selection** workflow
- **No rule assignment** until user completes selection
- **Special case:** If only S01E01 selected → tag removed, assigned to default rule

#### Manual Assignment
- **Use Episeerr interface** to assign specific series to specific rules
- **One rule per series** - assigning to a different rule replaces the previous assignment
- **Override method** - works regardless of tags

### Manual Assignment  
- **Primary method:** Use Episeerr interface to assign specific series to specific rules
- **One rule per series:** Each series can only be assigned to one rule at a time
- **Reassignment:** Assigning to a different rule replaces the previous assignment
- **Unassigned series:** Completely ignored by Episeerr - use normal Sonarr behavior

### Tag-Based Assignment
- **`episeerr_default`:** Assigns to default rule via webhook
- **`episeerr_select`:** Triggers episode selection (special case: pilot-only → default rule)
- **No tag:** Series is ignored by Episeerr unless manually assigned

## Rule Management

### Editing Rules
1. Go to Rules section in Episeerr
2. Click edit button for the rule
3. Modify settings
4. Save changes

**Note:** Changes apply immediately to all series using that rule

### Deleting Rules
- Can't delete the default rule
- Reassign series before deleting rules
- Deleted rules don't affect Sonarr directly

### Dry Run Mode
Test rule changes without actually modifying episodes:
1. Enable dry run in rule settings
2. Check logs to see what would happen
3. Disable dry run when satisfied

## Advanced Rule Strategies

### Show-Specific Rules
Create rules tailored to specific types of content:

**Daily Shows:**
```
Get: 1, Search, Keep: 1
Grace: 2 days, Dormant: 7 days
```

**Weekly Dramas:**  
```
Get: 2, Search, Keep: 3
Grace: 7 days, Dormant: 60 days
```

**Limited Series:**
```
Get: all, Monitor, Keep: all
Grace: null, Dormant: null
```

### Multiple Rule Workflow
1. Create multiple rules for different show types
2. Assign series based on viewing habits
3. Use default rule for "normal" shows
4. Special rules for specific needs

## Troubleshooting Rules

### Rule Not Working
- Verify series is assigned to the rule
- Check webhook setup and logs
- Ensure rule settings are logical
- Test with dry run mode

### Wrong Episodes Getting Managed
- Review rule logic (get vs keep settings)
- Check series assignment
- Verify episode matching in logs

### Performance Issues
- Consider fewer "get" episodes for large libraries
- Use "monitor" instead of "search" for less active management
- Adjust cleanup timers for better performance

---

**Next:** [Episode Selection Guide](episode-selection.md) - Choose specific episodes manually
