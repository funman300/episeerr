# Episode Selection Guide

Episeerr's episode selection system allows you to choose exactly which episodes you want across multiple seasons, giving you surgical precision over your downloads.

## When to Use Episode Selection

Perfect for:
- **Pilot episodes:** Try new shows without committing to full seasons
- **Specific episodes:** Get episodes you missed or want to rewatch  
- **Limited storage:** Precise control over what gets downloaded
- **Catch-up viewing:** Get specific episodes to catch up on a series

## How Episode Selection Works

### Workflow Overview
1. **Request initiated** (via Episeerr interface or Jellyseerr tag)
2. **Series added to Sonarr** with `episeerr_select` tag
3. **All episodes unmonitored** (prevents automatic downloads)
4. **Selection interface appears** in Episeerr pending requests
5. **User selects episodes** across any seasons
6. **Only selected episodes monitored** and searched

### Two Request Methods

#### Method 1: Episeerr Interface
1. Go to Episeerr → Pending Requests  
2. Click "Request New Series" (if available)
3. Search for and add series
4. Series appears in pending requests
5. Click "Select Seasons" → Choose seasons
6. Click "Select Episodes" → Choose specific episodes

#### Method 2: Jellyseerr/Overseerr Integration
1. Request series in Jellyseerr/Overseerr
2. **Add `episeerr_select` tag** to the request
3. Series automatically appears in Episeerr pending requests
4. Follow selection workflow as above

## Episode Selection Interface

### Season Selection
- Choose which seasons you want to work with
- Can select multiple seasons (e.g., Season 1 and 3)
- Seasons not selected won't appear in episode selection

### Episode Selection  
- Browse episodes with descriptions
- Select episodes across different seasons
- Visual indicators show:
  - Episode numbers and titles
  - Episode descriptions
  - Selection counts per season

### Selection Tools
- **Select All (Current Season):** Select all episodes in active season
- **Clear Current:** Deselect all episodes in active season  
- **Clear All:** Deselect all episodes across all seasons
- **Selection Summary:** Shows total episodes and breakdown by season

## Multi-Season Selection

### Example: Catching Up on "Lost"
Want to watch:
- Season 1: Episodes 1-3 (pilot + setup)
- Season 2: Episode 1 (season premiere)  
- Season 4: Episodes 12-14 (specific arc)

**Process:**
1. Select Seasons: 1, 2, 4
2. Season 1: Check episodes 1, 2, 3
3. Season 2: Check episode 1  
4. Season 4: Check episodes 12, 13, 14
5. Submit: Only these 6 episodes get monitored

### Benefits of Multi-Season Support
- **Precise control:** Get exactly what you want
- **Storage efficient:** No unwanted episodes
- **Flexible viewing:** Support non-linear viewing patterns
- **Custom collections:** Create your own "best of" collections

## Special Behaviors

### Pilot Episode Detection
If you select **only the first episode** of Season 1:
- `episeerr_select` tag is **removed**
- Series is **assigned to default rule**
- Treated as "pilot viewing" - normal automation takes over

### Multiple Episode Selection
If you select **multiple episodes** or **non-pilot episodes**:
- `episeerr_select` tag is **kept**
- **Only selected episodes** are monitored
- **No automatic rule assignment** (manual management)

## Integration with Rules System

### Episode Selection vs Rules
- **Episode Selection:** Manual, precise, one-time selection
- **Rules System:** Automatic, ongoing management based on viewing

### Combining Both Systems
1. **Use episode selection** for initial precise requests
2. **Switch to rules** for ongoing automation by removing `episeerr_select` tag
3. **Keep episode selection** for shows you want manual control over

## Managing Pending Requests

### Viewing Pending Requests
- Go to Episeerr → Pending Requests
- Shows all series awaiting episode selection
- Notification indicators alert you to new requests

### Request Actions
- **Select Seasons:** Choose which seasons to work with
- **Select Episodes:** Choose specific episodes within seasons
- **Delete Request:** Cancel the request entirely

### Request States
| State | Description | Action Available |
|-------|-------------|------------------|
| **Needs Season Selection** | New request, no seasons chosen | Select Seasons |
| **Needs Episode Selection** | Seasons chosen, need episodes | Select Episodes |
| **Processing** | Episodes selected, being processed | None (automatic) |

## Troubleshooting

### Request Not Appearing
- Check if series was added to Sonarr
- Verify `episeerr_select` tag is present
- Check Episeerr logs for errors

### Episodes Not Loading
- Verify TMDB API key is configured
- Check network connectivity to TMDB
- Review browser console for JavaScript errors

### Selection Not Working
- Ensure episodes are actually selected (checkboxes checked)
- Verify you clicked "Request Selected" 
- Check that selected episodes exist in Sonarr

### Wrong Episodes Monitored
- Check selection summary before submitting
- Verify season/episode numbers match expectations
- Review Episeerr logs for processing details

## Best Practices

### For New Shows
1. **Start with pilot:** Select just S01E01 to try the show
2. **Expand if interested:** Use episode selection for more episodes
3. **Switch to rules:** Remove tag and use automated management

### For Storage Management
1. **Select conservatively:** Choose fewer episodes initially
2. **Add more later:** Use episode selection multiple times
3. **Clean up regularly:** Remove `episeerr_select` tag when done

### For Catch-Up Viewing
1. **Research episodes:** Use episode descriptions to choose carefully
2. **Select by story arcs:** Group related episodes together
3. **Consider context:** Include setup/conclusion episodes

---

**Next:** [Cleanup System Guide](cleanup-guide.md) - Automatic library maintenance