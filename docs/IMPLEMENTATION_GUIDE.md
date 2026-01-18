# Documentation Restructure - Implementation Guide

## What's Been Created

### New Folder Structure

```
docs/
├── README.md                                    ✅ NEW - Main index with learning paths
│
├── getting-started/
│   ├── installation.md                          📋 TODO - Copy from existing
│   ├── quick-start.md                           ✅ NEW - 5 minute setup
│   └── first-series.md                          ✅ NEW - Step-by-step tutorial
│
├── core-concepts/
│   ├── deletion-system.md                       ✅ DONE - Comprehensive deletion guide
│   ├── tags-and-auto-assign.md                  ✅ DONE - Tag behavior explained
│   ├── rules-explained.md                       ✅ NEW - Conceptual overview
│   └── webhooks-explained.md                    ✅ NEW - Why webhooks exist
│
├── features/
│   ├── episode-selection.md                     📋 TODO - Copy from existing
│   ├── viewing-automation.md                    📋 TODO - Consolidate from rules-guide.md
│   ├── storage-management.md                    📋 TODO - Consolidate from global_storage_gate_guide.md
│   └── pending-deletions.md                     📋 TODO - Copy from existing
│
├── configuration/
│   ├── webhook-setup.md                         📋 TODO - Copy from existing webhooks.md
│   ├── sonarr-integration.md                    📋 TODO - Copy from existing
│   ├── rules-guide.md                           📋 TODO - How-to from existing
│   ├── rule-examples.md                         📋 TODO - Copy from existing
│   └── global-settings.md                       📋 TODO - Extract from various docs
│
├── guides/
│   ├── best-practices.md                        📋 TODO - Create new
│   ├── migration.md                             📋 TODO - Create new
│   └── advanced-scenarios.md                    📋 TODO - Create new
│
├── troubleshooting/
│   ├── common-issues.md                         📋 TODO - Copy/expand from existing
│   ├── debugging.md                             📋 TODO - Copy from existing
│   └── known-issues.md                          📋 TODO - Create new
│
├── reference/
│   ├── configuration-schema.md                  📋 TODO - Create new
│   ├── api.md                                   📋 TODO - Document webhook endpoints
│   └── changelog.md                             📋 TODO - Create new
│
└── assets/
    └── flow.svg                                 📋 TODO - Copy existing diagram
```

---

## Files Created (Ready to Use)

### ✅ Core Concepts (Complete)

1. **deletion-system.md** - THE definitive deletion guide
   - Keep vs Grace vs Dormant
   - Bookmark system explained
   - Visual timelines and examples
   - Complete FAQ

2. **tags-and-auto-assign.md** - How tags work
   - episeerr_default behavior
   - episeerr_select behavior  
   - Auto-assign vs tags
   - Complete workflows
   - "Tag disappeared" explanation

3. **rules-explained.md** - What rules do
   - GET/KEEP/ACTION explained
   - Grace periods overview
   - Multiple rules use cases
   - Common patterns

4. **webhooks-explained.md** - Why webhooks
   - Conceptual explanation
   - Flow diagrams
   - What gets sent
   - Troubleshooting

### ✅ Getting Started (Complete)

1. **quick-start.md** - 5 minute setup
   - Docker/Unraid installation
   - Webhook setup
   - First rule creation
   - Quick test

2. **first-series.md** - Tutorial walkthrough
   - Auto-assign method
   - Tag method
   - Verification steps
   - Troubleshooting

### ✅ Main Index (Complete)

1. **README.md** - New comprehensive index
   - Clear learning paths
   - Feature overview
   - Quick tips
   - System diagram
   - Documentation status

---

## Next Steps - What You Need to Do

### Phase 1: Copy Existing Docs (Easy)

**Simply copy these files to new locations:**

```bash
# From existing docs/ to new structure:
cp installation.md getting-started/
cp episode-selection.md features/
cp webhooks.md configuration/webhook-setup.md
cp sonarr_integration.md configuration/sonarr-integration.md
cp rule-examples.md configuration/
cp troubleshooting.md troubleshooting/common-issues.md
cp debugging.md troubleshooting/
cp pending_deletions.md features/
cp flow.svg assets/
```

### Phase 2: Consolidate Overlapping Docs (Requires Editing)

**Merge content from multiple files:**

1. **features/viewing-automation.md**
   - Extract viewing automation sections from `rules-guide.md`
   - Add examples and use cases
   - Link to webhook setup

2. **features/storage-management.md**
   - Extract from `global_storage_gate_guide.md`
   - Add grace/dormant configuration
   - Link to deletion system guide

3. **configuration/rules-guide.md**
   - Keep how-to sections from existing `rules-guide.md`
   - Remove conceptual overlaps (now in rules-explained.md)
   - Focus on step-by-step creation

4. **configuration/global-settings.md**
   - Storage gate configuration
   - Dry run mode
   - Auto-assign toggle
   - Cleanup intervals

### Phase 3: Create New Content (Optional but Recommended)

**Create these guides:**

1. **guides/best-practices.md**
   - Recommended rule configurations
   - Storage management tips
   - Common mistakes to avoid

2. **guides/migration.md**
   - Upgrading from old versions
   - Config changes needed
   - Breaking changes

3. **troubleshooting/known-issues.md**
   - Current bugs
   - Workarounds
   - Planned fixes

4. **reference/configuration-schema.md**
   - JSON structure reference
   - All available options
   - Default values

5. **reference/api.md**
   - Webhook endpoint documentation
   - Request/response formats
   - Error codes

---

## Migration Strategy

### Option A: Immediate Switch (Recommended)

1. **Create new docs/ folder structure**
2. **Copy files from old → new**
3. **Replace old docs/ with restructured version**
4. **Update all documentation.html links**

**Pros:** Clean break, no confusion  
**Cons:** Existing bookmarks break

---

### Option B: Gradual Migration

1. **Keep old docs/ as-is**
2. **Create docs-v2/ with new structure**
3. **Add banner to old docs: "New documentation available at..."**
4. **Switch after 1-2 releases**

**Pros:** Existing links still work  
**Cons:** Dual maintenance temporarily

---

## Key Improvements

✅ **Clear learning paths** - New users know where to start  
✅ **Concepts separated from how-to** - Understand before doing  
✅ **No duplication** - One source of truth per topic  
✅ **Better navigation** - Logical hierarchy  
✅ **Comprehensive guides** - Deletion system & tags fully explained  
✅ **Quick start** - Get working in 5 minutes  
✅ **Tutorial** - Step-by-step first series  

---

## Files to Deprecate (After Migration)

These are replaced by consolidated/improved versions:

- ❌ `global_storage_gate_guide.md` → Consolidated into `deletion-system.md` + `features/storage-management.md`
- ❌ `documentation.html` → Content extracted into markdown guides
- ❌ Old `index.md` → Replaced by comprehensive `README.md`

Keep for 1-2 releases with deprecation notices, then remove.

---

## Testing Checklist

Before going live:

- [ ] All internal links work
- [ ] Images/diagrams display correctly
- [ ] Code blocks render properly
- [ ] No broken cross-references
- [ ] Learning paths make sense
- [ ] New users can follow quick start
- [ ] Existing users can find advanced topics

---

## Rollout Plan

**Week 1:**
- Copy existing files to new structure
- Test all links
- Get feedback from beta testers

**Week 2:**
- Create consolidated docs (viewing-automation, storage-management)
- Create new reference docs (schema, API)
- Final testing

**Week 3:**
- Replace old docs with new structure
- Add deprecation notices to old files
- Update GitHub README to point to new docs

**Week 4:**
- Monitor for issues
- Fix broken links
- Gather user feedback

---

## Questions?

- **Discord/GitHub:** Post questions about migration
- **Feedback:** What's missing from new structure?
- **Contributions:** PRs welcome for new guides
