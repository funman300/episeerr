# Understanding Tags and Auto-Assignment

Tags and auto-assignment control **when and how** Episeerr takes control of series management.

- [Understanding Tags and Auto-Assignment](#understanding-tags-and-auto-assignment)
  - [Core Concept](#core-concept)
  - [Tag Behavior (Temporary Signals)](#tag-behavior-temporary-signals)
    - [episeerr\_default Tag](#episeerr_default-tag)
    - [episeerr\_select Tag](#episeerr_select-tag)
  - [Auto-Assign Setting (No Tag Required)](#auto-assign-setting-no-tag-required)
  - [When to Use Which](#when-to-use-which)
  - [Common Confusion](#common-confusion)
    - ["The tag disappeared, did it fail?"](#the-tag-disappeared-did-it-fail)
    - ["I have both auto-tagging and auto-assign enabled"](#i-have-both-auto-tagging-and-auto-assign-enabled)
    - ["Nothing is happening when I add a series"](#nothing-is-happening-when-i-add-a-series)
  - [Complete Workflows](#complete-workflows)
    - [Workflow 1: episeerr\_default (Immediate Processing)](#workflow-1-episeerr_default-immediate-processing)
    - [Workflow 2: Auto-Assign (Deferred Processing)](#workflow-2-auto-assign-deferred-processing)
    - [Workflow 3: episeerr\_select (Manual Control)](#workflow-3-episeerr_select-manual-control)
    - [Workflow 4: No Episeerr Management](#workflow-4-no-episeerr-management)
  - [Troubleshooting](#troubleshooting)

---

## Core Concept

**Tags are temporary signals, not permanent labels.** They tell Episeerr to "hijack" the series for custom processing, then disappear.

**Auto-assign** lets Sonarr/Jellyseerr control initial downloads, then Episeerr manages going forward.

---

## Tag Behavior (Temporary Signals)

### episeerr_default Tag

**Purpose:** Hijack the series immediately and apply GET rule

**Lifecycle:**
```
1. Series added to Sonarr with episeerr_default tag
2. Sonarr webhook fires → Episeerr receives it
3. Episeerr processes immediately:
   - Adds series to default rule
   - Applies GET rule (monitors/searches X episodes)
   - Removes tag (processing complete)
4. Tag disappears from Sonarr (this is normal!)
```

**Result:** Episodes are already monitored/searched based on your GET rule

**Use case:** You want Episeerr to take control from the start

---

### episeerr_select Tag

**Purpose:** Hijack the series for manual episode selection

**Lifecycle:**
```
1. Series added to Sonarr with episeerr_select tag
2. Sonarr webhook fires → Episeerr receives it
3. Episeerr creates selection interface:
   - Unmonitors all episodes
   - Shows episode picker in Episeerr UI
   - Waits for your selection
4. You select episodes → Only those monitored
5. Tag removed after processing
```

**Result:** Only your hand-picked episodes are monitored

**Use case:** You want to choose specific episodes (pilots, finales, etc.)

---

## Auto-Assign Setting (No Tag Required)

**Location:** Episeerr → Scheduler → Global Settings → "Auto-assign new series to default rule"

**Purpose:** Let Sonarr/Jellyseerr determine what to download initially, Episeerr manages cleanup/future episodes

**Lifecycle:**
```
1. Series added to Sonarr WITHOUT any tag
2. Sonarr/Jellyseerr monitors episodes as normal
3. Sonarr webhook fires → Episeerr receives it
4. Episeerr adds series to default rule silently
5. NO immediate processing - waits for you
6. When you watch first episode → Rule applies from there
```

**Result:** Sonarr controls initial downloads, Episeerr manages after first watch

**Use case:** 
- You request "Season 3 only" in Jellyseerr
- Let it download normally
- Episeerr manages cleanup and future episodes when you start watching

---

## When to Use Which

| Scenario | Method | Why |
|----------|--------|-----|
| **New show, start from S1E1** | `episeerr_default` tag | GET rule applies immediately |
| **New show, start from specific season** | `episeerr_default` tag + Jellyseerr webhook | Starts from requested season, not S1E1 |
| **Let Sonarr/Jellyseerr decide initially** | Auto-assign (no tag) | Full control initially, Episeerr manages after first watch |
| **Only want specific episodes** | `episeerr_select` tag | Manual episode selection interface |
| **Don't want Episeerr at all** | No tag + auto-assign OFF | Normal Sonarr behavior |
| **Existing shows** | Manual assignment in Series Management | Add to rule whenever you want |

---

## Common Confusion

### "The tag disappeared, did it fail?"

**NO!** Tag disappearing = **success**. The tag is just a signal to hijack the series. Once processed, it's removed.

**How to verify it worked:**

1. **Check Episeerr** → Series Management
   - Series should be listed under default rule
   
2. **Check Sonarr**
   - First X episodes should be monitored
   - If action is "search", they should be searching
   
3. **Check logs** (`/app/logs/app.log`):
   ```
   ✓ Monitored X episodes for [series name]
   ✓ Started search for [series name]
   ```

If you see these, **it worked!** The tag did its job and was cleaned up.

---

### "I have both auto-tagging and auto-assign enabled"

**This is fine!** They don't conflict:

- **If auto-tagging succeeds:** Tag is added → Episeerr processes immediately → Tag removed
- **If auto-tagging fails:** No tag → Auto-assign catches it → Added to rule, waits for first watch

**Recommendation:** Choose one approach for simplicity:
- **Auto-tagging:** More immediate (episodes ready right away)
- **Auto-assign:** More flexible (let Sonarr/Jellyseerr control initial downloads)

---

### "Nothing is happening when I add a series"

**Check these in order:**

1. **Is Sonarr webhook configured?**
   - Sonarr → Settings → Connect → Webhook
   - URL: `http://your-episeerr:5002/sonarr-webhook`
   - Trigger: "On Series Add"

2. **Are you using tags or auto-assign?**
   - With tag: Check if tag exists in Sonarr Settings → Tags
   - Without tag: Check if auto-assign is enabled in Episeerr

3. **Check logs:**
   ```bash
   grep "Processing.*with episeerr_default\|Auto-assigned" /app/logs/app.log | tail -20
   ```

4. **Verify default rule exists:**
   - Episeerr → Rules → Should have a rule marked as "Default"

---

## Complete Workflows

### Workflow 1: episeerr_default (Immediate Processing)

```
User Action:
├─ Add series to Sonarr with episeerr_default tag
│
Sonarr:
├─ Fires webhook to Episeerr
│
Episeerr:
├─ Receives webhook
├─ Detects episeerr_default tag
├─ Adds series to default rule
├─ Reads GET settings (e.g., "Get 3 episodes")
├─ Monitors S1E1, S1E2, S1E3 in Sonarr
├─ Searches for episodes (if action is "search")
├─ Removes episeerr_default tag
│
Result:
└─ Episodes ready immediately, tag gone ✅
```

**With Jellyseerr:**
```
User Action:
├─ Request Season 3 in Jellyseerr
│
Jellyseerr:
├─ Webhook to Episeerr (captures Season 3 request)
├─ Adds series to Sonarr with episeerr_default tag
│
Sonarr:
├─ Fires webhook to Episeerr
│
Episeerr:
├─ Receives webhook
├─ Remembers Season 3 from Jellyseerr webhook
├─ Adds series to default rule
├─ Applies GET rule starting from Season 3 (not Season 1!)
├─ Monitors S3E1, S3E2, S3E3 (if GET = 3 episodes)
├─ Removes episeerr_default tag
├─ Deletes Jellyseerr request
│
Result:
└─ Season 3 episodes ready, request cleaned up ✅
```

---

### Workflow 2: Auto-Assign (Deferred Processing)

```
User Action:
├─ Add series to Sonarr (no tag)
│
Sonarr:
├─ Monitors episodes normally
├─ Fires webhook to Episeerr
│
Episeerr:
├─ Receives webhook
├─ No tag detected
├─ Checks auto-assign setting (enabled)
├─ Adds series to default rule
├─ NO episode processing
├─ Returns
│
Sonarr:
├─ Downloads episodes as normal
│
User watches episode:
├─ Tautulli/Jellyfin webhook to Episeerr
│
Episeerr:
├─ Series is in default rule
├─ Applies GET rule (monitors next X episodes)
├─ Applies Keep rule (deletes old episodes)
│
Result:
└─ Sonarr controls initial download, Episeerr manages going forward ✅
```

---

### Workflow 3: episeerr_select (Manual Control)

```
User Action:
├─ Add series to Sonarr with episeerr_select tag
│
Sonarr:
├─ Fires webhook to Episeerr
│
Episeerr:
├─ Receives webhook
├─ Detects episeerr_select tag
├─ Unmonitors ALL episodes in Sonarr
├─ Creates selection request in UI
├─ Removes episeerr_select tag
│
User goes to Episeerr UI:
├─ Pending Requests → Selects specific episodes
├─ Submits selection
│
Episeerr:
├─ Monitors only selected episodes
├─ Searches for them (if applicable)
│
Result:
└─ Only hand-picked episodes monitored ✅
```

---

### Workflow 4: No Episeerr Management

```
User Action:
├─ Add series to Sonarr (no tag)
│
Settings:
├─ Auto-assign: OFF
├─ Auto-tagging: OFF
│
Sonarr:
├─ Fires webhook to Episeerr
│
Episeerr:
├─ Receives webhook
├─ No tag detected
├─ Auto-assign is OFF
├─ Logs: "Series has no episeerr tags, doing nothing"
├─ Returns
│
Result:
└─ Normal Sonarr behavior, no Episeerr management ✅
```

---

## Troubleshooting

| Problem | Check | Solution |
|---------|-------|----------|
| **Tag doesn't appear in Sonarr** | Auto-tagging enabled? Tag exists in Sonarr? | Create tag manually in Sonarr Settings → Tags |
| **Tag appears but nothing happens** | Sonarr webhook configured? | Add webhook: `http://episeerr:5002/sonarr-webhook` |
| **Episodes not monitored** | Default rule exists? GET settings configured? | Check Episeerr → Rules → Default rule |
| **Auto-assign not working** | Setting enabled? Sonarr webhook configured? | Enable in Scheduler → Global Settings |
| **Starting from wrong season** | Using Jellyseerr webhook? | Configure: `http://episeerr:5002/seerr-webhook` |

**Still stuck?** Check logs:
```bash
# See webhook processing
grep "Processing.*episeerr_default\|Auto-assigned" /app/logs/app.log

# See what episodes were monitored
grep "Monitored.*episodes for" /app/logs/app.log

# See any errors
grep "Error\|Failed" /app/logs/app.log | tail -20
```

---

**Key Takeaway:** Tags are temporary signals that trigger immediate processing, then disappear. Auto-assign adds series silently and waits for your first watch. Both are valid approaches depending on your workflow!
